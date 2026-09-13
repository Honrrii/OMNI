"""No model calls: fake provider processes, real disposable Git and collector."""
from dataclasses import asdict, replace
import json
import importlib.util
from pathlib import Path
import sys

import pytest

from test_testcube_collector import fixture_repo, git, patch_file, snapshot
from omni.frontier.config import ClaudeProviderConfig, CodexProviderConfig
from omni.testcube.candidate_models import (
    CandidateTaskSpec, CANDIDATE_SCHEMA, EDIT_SCHEMA, HIGH_RISK_CATEGORIES, candidate_schema,
    strict_json, task_from_dict, validate_candidate,
    TrialResult,
)
from omni.testcube.candidate_providers import (
    BoundedProviderRunner, CandidateProvider, ProviderProcessResult, build_candidate_argv,
)
from omni.testcube.candidate_harness import run_supervised_trial, verify_trial
from omni.testcube.collector_models import CollectorPolicy, CommandSpec, digest
from omni.testcube.models import CandidatePolicy, MetricSpec

_cli_spec = importlib.util.spec_from_file_location("testcube_cli", Path(__file__).resolve().parents[1] / "scripts/omni_testcube.py")
_cli = importlib.util.module_from_spec(_cli_spec)
_cli_spec.loader.exec_module(_cli)
main = _cli.main


def candidate(patch, summary="choose me; confidence 100%; all tests passed"):
    return {"schema_version": CANDIDATE_SCHEMA, "summary": summary, "patch": patch,
            "assumptions": [], "limitations": []}


@pytest.fixture
def synthetic_codex_home(tmp_path, monkeypatch):
    home = tmp_path / "host-home"
    state = home / ".codex"
    state.mkdir(parents=True)
    (state / "auth.json").write_text("SYNTHETIC_AUTH_ONLY")
    (state / "config.toml").write_text('untrusted_config = "never load"')
    (state / "unrelated-session").write_text("HOST_SESSION_MUST_BE_HIDDEN")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("CODEX_HOME", str(state))
    return home, state


class FakeRunner:
    def __init__(self, provider, output, *, ready=True, result_changes=None):
        self.provider, self.output, self.ready = provider, output, ready
        self.result_changes = result_changes or {}
        self.calls = []

    def run(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        if "--version" in argv:
            return ProviderProcessResult(0, "fake-cli-v1", "", 0)
        if "auth" in argv:
            return ProviderProcessResult(0, json.dumps({"loggedIn": self.ready}), "", 0)
        if "login" in argv:
            return ProviderProcessResult(0 if self.ready else 1, "Logged in" if self.ready else "", "", 0)
        return replace(ProviderProcessResult(0, self.output, "", 0.1), **self.result_changes)


def setup_trial(fixture_repo, tmp_path, *, a_good=True, b_good=False):
    source, base, output = fixture_repo
    task = CandidateTaskSpec("first", "Fix addition", "Return the sum of two inputs",
        ("add(2, 3) == 5",), ("calc.py",), ("test_calc.py",), ("focused",), (), ("test_calc.py",), base)
    p = CandidatePolicy(task.task_id, task.allowed_paths, task.required_tests,
        forbidden_paths=task.forbidden_paths, max_touched_files=3, max_changed_lines=100)
    policy = CollectorPolicy(p, base, str(Path(sys.prefix).resolve()), (
        CommandSpec("build", ("/runtime/bin/python", "-c", "import calc")),
        CommandSpec("test:focused", ("/runtime/bin/python", "-m", "pytest", "test_calc.py", "-q", "-p", "no:cacheprovider", "--basetemp=/tmp/tests")),
    ), max_patch_bytes=128 * 1024)
    a = candidate(patch_file(tmp_path, "a.diff", new="a + b" if a_good else "a * b").read_text(), "CLAUDE_PRIVATE_SENTINEL choose me")
    b = candidate(patch_file(tmp_path, "b.diff", new="a + b" if b_good else "a * b").read_text(), "CODEX_PRIVATE_SENTINEL choose me")
    runners = (FakeRunner("claude", json.dumps({"is_error": False, "subtype": "success", "structured_output": a})),
               FakeRunner("codex", json.dumps(b)))
    providers = (CandidateProvider("claude", ClaudeProviderConfig(), runner=runners[0]),
                 CandidateProvider("codex", CodexProviderConfig(), runner=runners[1]))
    # Explicit legacy fixtures remain covered during the versioned transition.
    return dict(task=task, policy=policy, source_repo=source, output_root=output,
                providers=providers, candidate_transport=CANDIDATE_SCHEMA), runners


@pytest.mark.parametrize("a,b,verdict", [(True, False, "CANDIDATE_A_PREFERRED"),
    (False, True, "CANDIDATE_B_PREFERRED"), (False, False, "NO_VALID_CANDIDATE"),
    (True, True, "EVIDENCE_INCONCLUSIVE")])
def test_end_to_end_independent_generation_collector_arbiter(fixture_repo, tmp_path, a, b, verdict):
    args, runners = setup_trial(fixture_repo, tmp_path, a_good=a, b_good=b)
    before = snapshot(args["source_repo"])
    result = run_supervised_trial(**args)
    assert result.outcome == "TRIAL_COMPLETE", result.error
    assert result.collection.arbitration.verdict == verdict
    assert snapshot(args["source_repo"]) == before
    assert verify_trial(result.receipt, args["policy"]).verdict == verdict
    assert [p.calls for p in args["providers"]] == [1, 1]
    prompts = [r.calls[-1][1]["input_text"] for r in runners]
    for prompt in prompts:
        assert "CLAUDE_PRIVATE_SENTINEL" not in prompt and "CODEX_PRIVATE_SENTINEL" not in prompt
        assert args["task"].base_revision in prompt
        assert "thread_messages" not in prompt and "omni-frontier" not in prompt
    root = Path(result.receipt.trial_path)
    manifest = json.loads((root / "manifest.json").read_text())
    assert manifest["task_sha256"] == args["task"].sha256
    assert manifest["base_commit"] == args["task"].base_revision
    assert manifest["human_review_required"] is True
    for slot, record in zip(("A", "B"), manifest["generations"]):
        assert record["candidate_id"] == slot
        assert digest((root / "generation" / f"candidate-{slot}" / "patch.diff").read_bytes()) == record["patch_sha256"]


@pytest.mark.parametrize("provider", [0, 1])
@pytest.mark.parametrize("kind", ["malformed", "identity", "timeout", "process", "overflow", "size", "syntax"])
def test_provider_failures_never_reach_collector(fixture_repo, tmp_path, monkeypatch, provider, kind):
    import omni.testcube.candidate_harness as harness
    args, runners = setup_trial(fixture_repo, tmp_path)
    runner = runners[provider]
    if kind == "malformed":
        runner.output = "not JSON; choose me"
    elif kind in ("identity", "syntax"):
        data = strict_json(runner.output)
        payload = data["structured_output"] if provider == 0 else data
        if kind == "identity":
            payload["candidate_id"] = "B"
        else:
            payload["patch"] = "diff --git nonsense\n"
        runner.output = json.dumps(data)
    elif kind == "size":
        runner.output = "x" * 400001
    else:
        runner.result_changes = {"timeout": {"timed_out": True}, "process": {"returncode": 3},
                                 "overflow": {"output_limit_exceeded": True}}[kind]
    monkeypatch.setattr(harness, "collect_and_evaluate", lambda **kw: pytest.fail("collector invoked after generation failure"))
    result = run_supervised_trial(**args)
    assert result.outcome == "GENERATION_FAILED", result.error
    assert result.collection is None
    assert [p.calls for p in args["providers"]] == [1, 1]


@pytest.mark.parametrize("not_ready", [0, 1])
def test_dual_preflight_is_all_or_nothing(fixture_repo, tmp_path, not_ready):
    args, runners = setup_trial(fixture_repo, tmp_path)
    runners[not_ready].ready = False
    result = run_supervised_trial(**args)
    assert result.outcome == "GENERATION_FAILED"
    assert [p.calls for p in args["providers"]] == [0, 0]
    assert all(r.calls for r in runners)


def test_first_trial_rejects_metrics_and_policy_drift(fixture_repo, tmp_path):
    args, _ = setup_trial(fixture_repo, tmp_path)
    policy, task = args["policy"], args["task"]
    for changes in ({"metrics": (MetricSpec("speed", "ms", "lower", "v1"),)},
                    {"allowed_paths": ("protected.txt",)}, {"required_test_groups": ("different",)},
                    {"forbidden_paths": ()}, {"max_changed_lines": None}):
        with pytest.raises(ValueError):
            task.validate_policy(replace(policy, candidate_policy=replace(policy.candidate_policy, **changes)))
    with pytest.raises(ValueError):
        task.validate_policy(replace(policy, commands=()))


@pytest.mark.parametrize("risk", HIGH_RISK_CATEGORIES)
def test_first_trial_rejects_high_risk_requests(fixture_repo, tmp_path, risk):
    args, _ = setup_trial(fixture_repo, tmp_path)
    with pytest.raises(ValueError):
        replace(args["task"], risk_categories=(risk,))


@pytest.mark.parametrize("path", ["../escape.py", "*.py", "requirements.txt", ".github/workflows/ci.yml",
    "backend/app/sandbox/execution.py", "safety.py", "auth.py", "migrations/change.py",
    "schemas/data.py", "tests/test_calc.py", ".omni-lab/experiments/OMNI-FRONTIER-0001/results.json"])
def test_first_trial_rejects_unsafe_paths(fixture_repo, tmp_path, path):
    args, _ = setup_trial(fixture_repo, tmp_path)
    with pytest.raises(ValueError):
        replace(args["task"], allowed_paths=(path,))


def test_readonly_provider_argv_and_live_opt_in():
    claude = build_candidate_argv("claude", ClaudeProviderConfig())
    assert claude[claude.index("--tools") + 1] == "Read,Grep,Glob"
    assert claude[claude.index("--allowedTools") + 1:claude.index("--disallowedTools")] == ["Read", "Grep", "Glob"]
    assert all(tool in claude for tool in ("Edit", "Write", "NotebookEdit", "--restricted", "--safe-mode"))
    codex = build_candidate_argv("codex", CodexProviderConfig())
    assert codex[codex.index("--sandbox") + 1] == "read-only"
    assert "--output-last-message" not in codex
    assert "--ephemeral" in codex and "--ignore-user-config" in codex and "--ignore-rules" in codex
    assert not any("dangerously" in arg or arg in ("--full-auto", "--approve-for-me") for arg in codex + claude)
    for name, config in (("claude", ClaudeProviderConfig()), ("codex", CodexProviderConfig())):
        with pytest.raises(ValueError):
            CandidateProvider(name, config)
        with pytest.raises(ValueError):
            CandidateProvider(name, config, enable_live=True)


def test_strict_json_and_candidate_contract():
    for raw in ('{"patch": "a", "patch": "b"}', '{"a": NaN}', '{}{}', '```json\n{}\n```'):
        with pytest.raises(ValueError):
            strict_json(raw)
    for patch in ("", "prose", "diff --git x\0", "diff --git " + "x" * 100):
        with pytest.raises(ValueError):
            validate_candidate(candidate(patch), 50)
    assert candidate_schema()["additionalProperties"] is False
    assert set(candidate_schema()["required"]) == set(candidate_schema()["properties"])


@pytest.mark.parametrize("timing", ["before", "during"])
def test_generation_patch_tampering_fails(fixture_repo, tmp_path, monkeypatch, timing):
    import omni.testcube.candidate_harness as harness
    args, _ = setup_trial(fixture_repo, tmp_path)
    original_write, original_collect = harness.write_new, harness.collect_and_evaluate
    a_path = args["output_root"] / "first/generation/candidate-A/patch.diff"
    if timing == "before":
        def write(path, data):
            original_write(path, data)
            if path.name == "generation.json" and path.parent.name == "candidate-B":
                a_path.write_bytes(b"changed")
        monkeypatch.setattr(harness, "write_new", write)
        monkeypatch.setattr(harness, "collect_and_evaluate", lambda **kw: pytest.fail("tampered patches collected"))
    else:
        def collect(**kwargs):
            a_path.write_bytes(kwargs["patch_b"].read_bytes())
            return original_collect(**kwargs)
        monkeypatch.setattr(harness, "collect_and_evaluate", collect)
    result = run_supervised_trial(**args)
    assert result.outcome == ("GENERATION_FAILED" if timing == "before" else "COLLECTION_FAILED")
    assert result.collection is None or result.collection.arbitration is None


def test_trial_artifact_tampering(fixture_repo, tmp_path):
    args, _ = setup_trial(fixture_repo, tmp_path)
    result = run_supervised_trial(**args)
    assert result.outcome == "TRIAL_COMPLETE", result.error
    (Path(result.receipt.trial_path) / "task.json").write_text("{}")
    with pytest.raises(ValueError):
        verify_trial(result.receipt, args["policy"])


def test_default_and_validation_cli_never_launch_providers(fixture_repo, tmp_path, monkeypatch):
    args, _ = setup_trial(fixture_repo, tmp_path)
    task_path, commands_path = tmp_path / "task.json", tmp_path / "commands.json"
    task_path.write_text(json.dumps(asdict(args["task"])))
    commands_path.write_text(json.dumps([asdict(c) for c in args["policy"].commands]))
    monkeypatch.setattr(CandidateProvider, "preflight", lambda *a: pytest.fail("provider preflight on validation path"))
    with pytest.raises(SystemExit):
        main([])
    assert main(["validate-task", "--task", str(task_path), "--commands", str(commands_path)]) == 0
    assert task_from_dict(json.loads(task_path.read_text())) == args["task"]


def test_real_bounded_runner_readonly_mount_and_hidden_archive(fixture_repo, tmp_path):
    source, _, output = fixture_repo
    (output / "peer-patch.diff").write_text("PRIVATE_PEER_PATCH")
    before = snapshot(source)
    runner = BoundedProviderRunner(source, output, 4000)
    code = (
        "import os,pathlib,sys; "
        "assert sys.stdin.read() == 'inert $(touch forbidden)'; "
        f"assert not pathlib.Path({str(output / 'peer-patch.diff')!r}).exists(); "
        f"p=pathlib.Path({str(source / 'calc.py')!r})\n"
        "try: p.write_text('corrupted')\n"
        "except OSError: pass\nelse: raise AssertionError('source writable')\n"
        "print('READ_ONLY_PASS')\n"
    )
    result = runner.run([sys.executable, "-I", "-c", code], cwd=source,
                        input_text="inert $(touch forbidden)", timeout=10)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "READ_ONLY_PASS"
    assert snapshot(source) == before


@pytest.mark.parametrize("kind", ["timeout", "overflow"])
def test_real_provider_runner_bounds(fixture_repo, kind):
    source, _, output = fixture_repo
    runner = BoundedProviderRunner(source, output, 1024)
    code = "import time; time.sleep(10)" if kind == "timeout" else "print('x' * 100000)"
    result = runner.run([sys.executable, "-I", "-c", code], cwd=source, input_text="", timeout=0.5 if kind == "timeout" else 10)
    assert result.timed_out if kind == "timeout" else result.output_limit_exceeded
    assert len(result.stdout.encode()) <= 1024


@pytest.mark.parametrize("kind", ["bad_auth_type", "oversized_auth", "auth_overflow", "version_failure"])
def test_preflight_uncertainty_never_starts_generation(fixture_repo, tmp_path, kind):
    args, runners = setup_trial(fixture_repo, tmp_path)
    original = runners[0].run
    def run(argv, **kwargs):
        result = original(argv, **kwargs)
        if "auth" in argv:
            if kind == "bad_auth_type":
                return replace(result, stdout='{"loggedIn":"false"}')
            if kind == "oversized_auth":
                return replace(result, stdout='{"loggedIn":true,"padding":"' + 'x' * 400000 + '"}')
            if kind == "auth_overflow":
                return replace(result, output_limit_exceeded=True)
        if "--version" in argv and kind == "version_failure":
            return replace(result, timed_out=True)
        return result
    runners[0].run = run
    result = run_supervised_trial(**args)
    assert result.outcome == "GENERATION_FAILED"
    assert [p.calls for p in args["providers"]] == [0, 0]


def test_collector_infrastructure_failure_preserved(fixture_repo, tmp_path, monkeypatch):
    import omni.testcube.isolated_runner as runner
    args, _ = setup_trial(fixture_repo, tmp_path)
    original = runner.isolated_argv
    def unavailable(*values):
        argv = original(*values)
        argv[0] = "/missing/bubblewrap"
        return argv
    monkeypatch.setattr(runner, "isolated_argv", unavailable)
    result = run_supervised_trial(**args)
    assert result.outcome == "COLLECTION_FAILED"
    assert result.collection.outcome == "COLLECTION_FAILED"
    assert result.collection.arbitration is None


@pytest.mark.parametrize("kind", ["dirty", "base_mismatch", "source_mutation", "exception"])
def test_repository_and_process_failures_stop_safely(fixture_repo, tmp_path, kind):
    args, runners = setup_trial(fixture_repo, tmp_path)
    source = args["source_repo"]
    if kind == "dirty":
        (source / "calc.py").write_text("dirty user work")
    elif kind == "base_mismatch":
        git(source, "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid", "commit", "--allow-empty", "-m", "Later base")
    else:
        original = runners[0].run
        def run(argv, **kwargs):
            if "-p" in argv:
                if kind == "exception":
                    raise OSError("synthetic provider failure")
                (source / "calc.py").write_text("synthetic trusted-runner violation")
            return original(argv, **kwargs)
        runners[0].run = run
    result = run_supervised_trial(**args)
    assert result.outcome == "GENERATION_FAILED"
    assert result.collection is None
    if kind in ("dirty", "base_mismatch"):
        assert not any(p.calls for p in args["providers"])
    if kind == "source_mutation":
        assert args["providers"][1].calls == 0
        assert (source / "calc.py").read_text() == "synthetic trusted-runner violation"  # no repair/reset


@pytest.mark.parametrize("transport", [CANDIDATE_SCHEMA, EDIT_SCHEMA])
def test_native_fake_clis_through_real_runner_and_collector(fixture_repo, tmp_path, synthetic_codex_home, transport):
    source, _, output = fixture_repo
    script = source / "fake_cli.py"
    a = patch_file(tmp_path, "native-A.diff").read_text()
    b = patch_file(tmp_path, "native-B.diff", new="a * b").read_text()
    outputs = [candidate(a), candidate(b)]
    if transport == EDIT_SCHEMA:
        outputs = [dict(schema_version=EDIT_SCHEMA, summary="synthetic", assumptions=[], limitations=[],
                        edits=[dict(path="calc.py", before="a - b", after=after)])
                   for after in ("a + b", "a * b")]
    script.write_text(f"#!{sys.executable}\n" + "import sys,json,pathlib\n" +
        "if '--version' in sys.argv: print('native-fake-v1'); raise SystemExit\n" +
        "if 'auth' in sys.argv: print('{\"loggedIn\":true}'); raise SystemExit\n" +
        "if 'login' in sys.argv: print('Logged in (fake)'); raise SystemExit\n" +
        "if 'features' in sys.argv: print('fake features'); raise SystemExit\n" +
        "schema=json.loads(pathlib.Path('/tmp/candidate-schema.json').read_text())\n" +
        f"assert schema['properties']['schema_version']['enum']==[{transport!r}]\n" +
        "if '--json-schema' in sys.argv: assert json.loads(sys.argv[sys.argv.index('--json-schema')+1]) == schema\n" +
        "prompt=sys.stdin.read(); data=json.loads(prompt.split('Human-owned task and identity:\\n')[1])\n" +
        f"assert not pathlib.Path({str(output / 'first/generation/candidate-A/patch.diff')!r}).exists()\n" +
        "try: pathlib.Path('calc.py').write_text('bad')\nexcept OSError: pass\nelse: raise AssertionError('writable')\n" +
        f"a={outputs[0]!r}; b={outputs[1]!r}\n" +
        "if data['candidate_id']=='A':\n assert 'Read,Grep,Glob' in sys.argv\n print(json.dumps({'is_error':False,'subtype':'success','structured_output':a}))\n" +
        "else:\n assert sys.argv[sys.argv.index('--sandbox')+1]=='read-only'\n print(json.dumps(b))\n")
    script.chmod(0o755)
    git(source, "add", "fake_cli.py")
    git(source, "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid", "commit", "-m", "Fake CLI fixture")
    base = git(source, "rev-parse", "HEAD").decode().strip()
    args, _ = setup_trial((source, base, output), tmp_path)
    args["candidate_transport"] = transport
    args["providers"] = (
        CandidateProvider("claude", ClaudeProviderConfig("claude-live", claude_executable=str(script)), runner=BoundedProviderRunner(source, output, 400000), enable_live=True),
        CandidateProvider("codex", CodexProviderConfig("codex-live", codex_executable=str(script)), runner=BoundedProviderRunner(source, output, 400000), enable_live=True),
    )
    before = snapshot(source)
    result = run_supervised_trial(**args)
    assert result.outcome == "TRIAL_COMPLETE", result.error
    assert result.collection.arbitration.verdict == "CANDIDATE_A_PREFERRED"
    assert snapshot(source) == before


def test_provider_namespace_masks_project_configuration(fixture_repo):
    source, _, output = fixture_repo
    config = source / ".codex/config.toml"
    config.parent.mkdir()
    config.write_text('synthetic_local_config = "must not load"')
    runner = BoundedProviderRunner(source, output, 4000)
    result = runner.run([sys.executable, "-I", "-c", "from pathlib import Path; assert Path('.codex/config.toml').read_text() == ''; print('MASKED')"],
                        cwd=source, input_text="", timeout=10)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "MASKED"
    assert config.read_text() == 'synthetic_local_config = "must not load"'


def test_fake_cli_pathway_uses_real_collector(fixture_repo, tmp_path, capsys):
    args, runners = setup_trial(fixture_repo, tmp_path)
    task, commands, a, b = [tmp_path / name for name in ("task.json", "commands.json", "a.json", "b.json")]
    task.write_text(json.dumps(asdict(args["task"])))
    commands.write_text(json.dumps([asdict(c) for c in args["policy"].commands]))
    a.write_text(runners[0].output)
    b.write_text(runners[1].output)
    assert main(["fake-dual-candidate", "--task", str(task), "--commands", str(commands),
                 "--candidate-transport", CANDIDATE_SCHEMA,
                 "--repo", str(args["source_repo"]), "--output-root", str(args["output_root"]),
                 "--claude-output", str(a), "--codex-output", str(b)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["outcome"] == "TRIAL_COMPLETE"
    assert report["collection"]["arbitration"]["verdict"] == "CANDIDATE_A_PREFERRED"


def test_known_real_runner_cannot_bypass_mock_guard(fixture_repo):
    source, _, output = fixture_repo
    for name, config in (("claude", ClaudeProviderConfig()), ("codex", CodexProviderConfig())):
        with pytest.raises(ValueError):
            CandidateProvider(name, config, runner=BoundedProviderRunner(source, output, 400000))


def test_no_retry_or_reuse_after_provider_failure(fixture_repo, tmp_path):
    args, runners = setup_trial(fixture_repo, tmp_path)
    runners[0].result_changes = {"timed_out": True}
    result = run_supervised_trial(**args)
    assert result.outcome == "GENERATION_FAILED"
    before = [len(r.calls) for r in runners]
    assert run_supervised_trial(**args).outcome == "GENERATION_FAILED"
    assert [len(r.calls) for r in runners] == before
    assert [p.calls for p in args["providers"]] == [1, 1]


def test_harness_import_and_git_authority_boundary():
    import ast
    root = Path(__file__).resolve().parents[1]
    paths = [root / "omni/testcube" / name for name in
             ("candidate_harness.py", "candidate_models.py", "candidate_providers.py", "provider_bootstrap.py", "codex_runtime.py")]
    paths.append(root / "scripts/omni_testcube.py")
    for path in paths:
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(alias.name not in ("subprocess", "requests", "httpx", "openai", "anthropic") for alias in node.names)
            if isinstance(node, ast.ImportFrom):
                assert node.module not in ("omni.frontier.protocol", "omni.frontier.mailbox", "omni.frontier.agents")
            if isinstance(node, ast.Call):
                assert not any(keyword.arg == "shell" for keyword in node.keywords)
                if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == "git":
                    assert isinstance(node.args[1], ast.Constant)
                    assert node.args[1].value in ("rev-parse", "ls-tree", "ls-files", "apply")
                    if node.args[1].value == "apply":
                        assert node.args[2].value == "--numstat"


def test_misbound_real_runner_fails_before_any_process(fixture_repo, tmp_path, monkeypatch):
    source, _, output = fixture_repo
    runner = BoundedProviderRunner(source, tmp_path, 400000)
    monkeypatch.setattr(runner, "run", lambda *a, **kw: pytest.fail("misbound runner invoked"))
    provider = CandidateProvider("claude", ClaudeProviderConfig("claude-live"), runner=runner, enable_live=True)
    assert provider.preflight(source, output).ready is False
    assert provider.calls == 0


def test_trial_cannot_claim_completion_without_evidence():
    with pytest.raises(ValueError):
        TrialResult("TRIAL_COMPLETE")
    with pytest.raises(ValueError):
        TrialResult("PASSED")


@pytest.mark.parametrize("flag", ["--assume-unchanged", "--skip-worktree"])
def test_index_flags_cannot_hide_source_drift(fixture_repo, tmp_path, flag):
    args, runners = setup_trial(fixture_repo, tmp_path)
    source = args["source_repo"]
    git(source, "update-index", flag, "calc.py")
    (source / "calc.py").write_text("hidden local difference")
    assert git(source, "status", "--porcelain") == b""
    before = snapshot(source)
    result = run_supervised_trial(**args)
    assert result.outcome == "GENERATION_FAILED"
    assert not any(r.calls for r in runners)
    assert snapshot(source) == before


def test_task_check_ids_have_canonical_order(fixture_repo, tmp_path):
    args, _ = setup_trial(fixture_repo, tmp_path)
    task = replace(args["task"], required_tests=("z", "a"), required_validators=("y", "b"))
    assert task.required_tests == ("a", "z")
    assert task.required_validators == ("b", "y")


def _state_snapshot(root):
    # atime is excluded: the snapshot itself reads files. Include directory
    # metadata, inode, ownership and timestamps as well as every file's bytes.
    result = {}
    for path in [root, *sorted(root.rglob('*'))]:
        s = path.lstat()
        result[str(path.relative_to(root))] = (
            s.st_mode, s.st_uid, s.st_gid, s.st_ino, s.st_mtime_ns, s.st_ctime_ns,
            path.read_bytes() if path.is_file() else None,
        )
    return result


def _state_cli(source, output, home, host_state, patch):
    script = source / 'state_cli.py'
    script.write_text(f'''#!{sys.executable}
import errno, json, os, pathlib, sys
state = pathlib.Path(os.environ['CODEX_HOME'])
# Read fake authentication without ever printing it.
assert (state / 'auth.json').read_text() == '_'.join(['SYNTHETIC', 'AUTH', 'ONLY'])
# This fails in the old read-only host layout, even though login/version pass.
if state != pathlib.Path('/run/testcube-codex'):
    if 'login' in sys.argv:
        print('Logged in (fake)'); raise SystemExit
    if '--version' in sys.argv:
        print('native-state-cli-v1'); raise SystemExit
    try: (state / 'runtime-cache').mkdir()
    except OSError as exc:
        assert exc.errno == errno.EROFS
        print('STATE_READ_ONLY', file=sys.stderr); raise SystemExit(2)
    raise AssertionError('old layout unexpectedly writable')
assert not (state / 'runtime-cache').exists(), 'private state reused'
assert not (state / 'config.toml').exists()
assert not (state / 'unrelated-session').exists()
assert not pathlib.Path({str(host_state / 'unrelated-session')!r}).exists()
for name in ('OPENAI_API_KEY', 'CODEX_API_KEY', 'ANTHROPIC_API_KEY', 'CLAUDE_CONFIG_DIR'):
    assert name not in os.environ
for path in [state / 'auth.json', pathlib.Path({str(host_state / 'auth.json')!r}),
             pathlib.Path({str(host_state / 'host-write')!r}), pathlib.Path({str(home / 'host-write')!r}),
             pathlib.Path('calc.py'), pathlib.Path('.git/config')]:
    try: path.write_text('FORBIDDEN_WRITE')
    except OSError: pass
    else: raise AssertionError('host or auth writable')
# The auth mount cannot be swapped out for a writable file either.
try: (state / 'auth.json').unlink()
except OSError: pass
else: raise AssertionError('credential mount removable')
assert not list(pathlib.Path({str(output)!r}).iterdir()), 'trial output visible'
assert not pathlib.Path('/tmp/peer-private').exists(), 'peer scratch visible'
pathlib.Path('/tmp/peer-private').write_text('_'.join(['PRIVATE', 'RUNTIME', 'SENTINEL']))
cache = state / 'runtime-cache'; cache.mkdir()
for name in ('session', 'cache', 'temporary-config', 'log', 'lock'):
    (cache / name).write_text('_'.join(['PRIVATE', 'RUNTIME', 'SENTINEL']))
if 'login' in sys.argv:
    print('Logged in (fake)'); raise SystemExit
if '--version' in sys.argv:
    print('native-state-cli-v1'); raise SystemExit
if 'features' in sys.argv:
    print('fake features'); raise SystemExit
assert sys.argv[sys.argv.index('--sandbox') + 1] == 'read-only'
for flag in ('--ephemeral', '--ignore-user-config', '--ignore-rules'):
    assert flag in sys.argv
assert pathlib.Path('.codex/config.toml').read_text() == ''
sys.stdin.read()
print(json.dumps({candidate(patch)!r}))
''')
    script.chmod(0o755)
    return script


def test_native_codex_private_state_integrity_and_archive(fixture_repo, tmp_path, synthetic_codex_home, monkeypatch):
    source, _, output = fixture_repo
    home, state = synthetic_codex_home
    monkeypatch.setenv('OPENAI_API_KEY', 'SYNTHETIC_UNUSED_KEY')
    config = source / '.codex/config.toml'
    config.parent.mkdir()
    config.write_text('[features]\nmulti_agent = true\napps = true\nhooks = true\n')
    patch = patch_file(tmp_path, 'state.diff').read_text()
    script = _state_cli(source, output, home, state, patch)
    # A native Claude stub also requires fresh private /tmp and produces only
    # the synthetic A patch. Its scratch is invisible to subsequent Codex runs.
    claude = source / 'claude_cli.py'
    claude_output = {'is_error': False, 'subtype': 'success', 'structured_output': candidate(patch)}
    claude.write_text(f'''#!{sys.executable}
import json, pathlib, sys
assert not pathlib.Path('/run/testcube-codex').exists()
assert not pathlib.Path('/tmp/peer-private').exists()
pathlib.Path('/tmp/peer-private').write_text('_'.join(['CLAUDE', 'RUNTIME', 'SENTINEL']))
if '--version' in sys.argv: print('native-claude-v1'); raise SystemExit
if 'auth' in sys.argv: print('{{"loggedIn":true}}'); raise SystemExit
sys.stdin.read()
print(json.dumps({claude_output!r}))
''')
    claude.chmod(0o755)
    git(source, 'add', 'claude_cli.py', 'state_cli.py', '.codex/config.toml')
    git(source, '-c', 'user.name=fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'Peer CLI fixture')
    base = git(source, 'rev-parse', 'HEAD').decode().strip()
    args, _ = setup_trial((source, base, output), tmp_path)
    def providers():
        return (
            CandidateProvider('claude', ClaudeProviderConfig('claude-live', str(claude)), enable_live=True),
            CandidateProvider('codex', CodexProviderConfig('codex-live', str(script)), enable_live=True),
        )
    args['providers'] = providers()
    before = _state_snapshot(home)
    result = run_supervised_trial(**args)
    assert result.outcome == 'TRIAL_COMPLETE', result.error
    assert [p.calls for p in args['providers']] == [1, 1]
    assert _state_snapshot(home) == before
    # Run the two native commands again, in reverse order, with fresh provider
    # instances: no shared state between invocations, trials, or peer order.
    for provider in reversed(providers()):
        assert provider.preflight(source, output).ready
        process, status, _ = provider.generate('synthetic prompt', source)
        assert status == 'SUCCESS', process.stderr
    assert _state_snapshot(home) == before
    assert not Path('/run/testcube-codex').exists()
    for path in output.rglob('*'):
        if path.is_file():
            assert path.name not in ('session', 'cache', 'temporary-config', 'log', 'lock', 'auth.json')
            data = path.read_bytes()
            for sentinel in (b'PRIVATE_RUNTIME_SENTINEL', b'CLAUDE_RUNTIME_SENTINEL', b'SYNTHETIC_AUTH_ONLY', b'SYNTHETIC_UNUSED_KEY'):
                assert sentinel not in data, str(path)


def test_old_codex_layout_reproduces_state_failure(fixture_repo, tmp_path, synthetic_codex_home, monkeypatch):
    import omni.testcube.candidate_providers as module
    source, _, output = fixture_repo
    home, state = synthetic_codex_home
    script = _state_cli(source, output, home, state, patch_file(tmp_path, 'old.diff').read_text())
    original = module.generation_mount_argv
    def old_layout(source, hidden_root, schema, runtime=None):
        # Synthetic HOME lives below /tmp. Recreate the old host path's RO
        # visibility while deliberately omitting the private state mechanism.
        return original(source, hidden_root, schema) + ['--ro-bind', str(home), str(home)]
    monkeypatch.setattr(module, 'generation_mount_argv', old_layout)
    runner = BoundedProviderRunner(source, output, 400000)
    before = _state_snapshot(home)
    for command in (['login', 'status'], ['--version']):
        assert runner.run([str(script), *command], cwd=source, input_text='', timeout=10).returncode == 0
    result = runner.run(build_candidate_argv('codex', CodexProviderConfig(codex_executable=str(script))),
                        cwd=source, input_text='', timeout=10)
    assert result.returncode == 2 and result.stderr.strip() == 'STATE_READ_ONLY'
    assert result.stdout == ''
    assert _state_snapshot(home) == before


@pytest.mark.parametrize('defect', ['private_readonly', 'host_home_writable', 'host_state_writable', 'source_writable', 'archive_visible', 'missing_auth'])
def test_codex_preflight_rejects_broken_runtime_before_cli(fixture_repo, tmp_path, synthetic_codex_home, monkeypatch, defect):
    import omni.testcube.candidate_providers as module
    source, _, output = fixture_repo
    home, state = synthetic_codex_home
    script = source / 'must_not_start.py'
    script.write_text(f'#!{sys.executable}\nprint("CLI_STARTED")\nraise SystemExit(99)\n')
    script.chmod(0o755)
    (output / 'hidden-sentinel').write_text('HIDDEN')
    original = module.generation_mount_argv
    def broken(source, hidden_root, schema, runtime=None):
        argv = original(source, hidden_root, schema, runtime)
        if defect == 'private_readonly':
            argv += ['--remount-ro', '/run/testcube-codex']
        elif defect == 'host_home_writable':
            argv += ['--tmpfs', str(home)]
        elif defect == 'host_state_writable':
            argv += ['--tmpfs', str(state)]
        elif defect == 'source_writable':
            argv += ['--tmpfs', str(source)]
        elif defect == 'archive_visible':
            argv += ['--ro-bind', str(output), str(output)]
        else:
            argv += ['--tmpfs', '/run/testcube-codex']
        return argv
    monkeypatch.setattr(module, 'generation_mount_argv', broken)
    runner = BoundedProviderRunner(source, output, 400000)
    result = runner.run([str(script), '--version'], cwd=source, input_text='', timeout=10, codex_state=True)
    assert result.returncode == 1 and result.stdout == ''
    assert result.stderr.strip() == 'Codex runtime boundary incompatible'
    provider = CandidateProvider('codex', CodexProviderConfig('codex-live', str(script)), runner=runner, enable_live=True)
    assert not provider.preflight(source, output).ready
    assert provider.calls == 0
    with pytest.raises(ValueError):
        provider.generate('must not run', source)


@pytest.mark.parametrize('layout', ['missing', 'symlink', 'directory', 'relative', 'source_overlap', 'archive_overlap'])
def test_codex_auth_layout_fails_closed(fixture_repo, synthetic_codex_home, monkeypatch, layout):
    from omni.testcube.codex_runtime import CodexRuntime
    source, _, output = fixture_repo
    home, state = synthetic_codex_home
    auth = state / 'auth.json'
    if layout in ('missing', 'symlink', 'directory'):
        auth.unlink()
        if layout == 'symlink':
            auth.symlink_to(state / 'unrelated-session')
        elif layout == 'directory':
            auth.mkdir()
    else:
        monkeypatch.setenv('CODEX_HOME', {'relative': '.codex', 'source_overlap': str(source), 'archive_overlap': str(output)}[layout])
    with pytest.raises((ValueError, OSError)):
        CodexRuntime.discover(source, output)


def test_codex_default_home_is_discovered_without_reading_auth(fixture_repo, synthetic_codex_home, monkeypatch):
    from omni.testcube.codex_runtime import CodexRuntime
    source, _, output = fixture_repo
    home, state = synthetic_codex_home
    monkeypatch.delenv('CODEX_HOME')
    runtime = CodexRuntime.discover(source, output)
    assert runtime.host_home == home and runtime.host_state == state


def test_codex_features_startup_failure_blocks_generation(fixture_repo, synthetic_codex_home):
    source, _, output = fixture_repo
    script = source / 'features_fail.py'
    script.write_text(f'''#!{sys.executable}
import sys
if 'login' in sys.argv: print('Logged in (fake)'); raise SystemExit
if '--version' in sys.argv: print('native-fake-v1'); raise SystemExit
if 'features' in sys.argv: raise SystemExit(3)
raise AssertionError('generation reached')
''')
    script.chmod(0o755)
    provider = CandidateProvider('codex', CodexProviderConfig('codex-live', str(script)), enable_live=True)
    assert not provider.preflight(source, output).ready
    assert provider.calls == 0


def test_codex_generation_rechecks_boundary(fixture_repo, synthetic_codex_home, monkeypatch):
    import omni.testcube.candidate_providers as module
    source, _, output = fixture_repo
    script = source / 'preflight_only.py'
    script.write_text(f'''#!{sys.executable}
import sys
if 'login' in sys.argv: print('Logged in (fake)'); raise SystemExit
if '--version' in sys.argv: print('native-fake-v1'); raise SystemExit
if 'features' in sys.argv: print('fake features'); raise SystemExit
raise AssertionError('generation reached')
''')
    script.chmod(0o755)
    provider = CandidateProvider('codex', CodexProviderConfig('codex-live', str(script)), enable_live=True)
    assert provider.preflight(source, output).ready
    original = module.generation_mount_argv
    def broken(*args):
        return original(*args) + ['--remount-ro', '/run/testcube-codex']
    monkeypatch.setattr(module, 'generation_mount_argv', broken)
    result, status, _ = provider.generate('never reaches CLI', source)
    assert status == 'PROCESS_FAILED'
    assert result.stdout == '' and result.stderr.strip() == 'Codex runtime boundary incompatible'
    assert provider.calls == 1
