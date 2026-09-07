"""Real disposable Git copies and harmless commands; no model invocation."""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from omni.testcube.collector import (
    CollectionError, _changes, _Git, arbitrate_collected,
    cleanup_collection, collect_and_evaluate,
)
from omni.testcube.collector_models import BenchmarkSpec, CollectorPolicy, CommandSpec, digest
from omni.testcube.models import CandidatePolicy, MetricSpec, candidate_evidence_from_dict


def git(repo, *argv, check=True):
    proc = subprocess.run(["git", "-c", "core.hooksPath=/dev/null", *argv], cwd=repo,
                          capture_output=True, check=check,
                          env={"PATH": "/usr/bin:/bin", "GIT_CONFIG_NOSYSTEM": "1",
                               "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_TERMINAL_PROMPT": "0"})
    return proc.stdout


def snapshot(repo):
    # Exact bytes, including index/config/refs and tracked source. Ignore no
    # file in these small synthetic repositories.
    return {str(path.relative_to(repo)): path.read_bytes()
            for path in repo.rglob("*") if path.is_file() and not path.is_symlink()}


@pytest.fixture
def fixture_repo(tmp_path):
    repo = tmp_path / "source"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    (repo / "calc.py").write_text("def add(a, b):\n    return a - b\n")
    (repo / "test_calc.py").write_text("from calc import add\ndef test_add():\n    assert add(2, 3) == 5\n")
    (repo / "protected.txt").write_text("protected fixture\n")
    git(repo, "add", "--", "calc.py", "test_calc.py", "protected.txt")
    git(repo, "-c", "user.name=TestCube fixture", "-c", "user.email=testcube@example.invalid",
        "commit", "-m", "Synthetic base")
    base = git(repo, "rev-parse", "HEAD").decode().strip()
    output = tmp_path / "evidence"
    output.mkdir()
    return repo, base, output


def patch_file(tmp_path, name, old="a - b", new="a + b", path="calc.py"):
    patch = (f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n"
             f"@@ -1,2 +1,2 @@\n def add(a, b):\n-    return {old}\n+    return {new}\n")
    dest = tmp_path / name
    dest.write_text(patch)
    return dest


def policy(base, evaluation_id="trial", **changes):
    p = CandidatePolicy(evaluation_id, ("calc.py",), ("focused",), forbidden_paths=("protected.txt",))
    commands = (
        CommandSpec("build", ("/runtime/bin/python", "-c", "import calc")),
        CommandSpec("test:focused", ("/runtime/bin/python", "-m", "pytest", "test_calc.py", "-q", "-p", "no:cacheprovider", "--basetemp=/tmp/pytest")),
    )
    return CollectorPolicy(**(dict(candidate_policy=p, base_revision=base,
                                  runtime_root=str(Path(sys.prefix).resolve()), commands=commands) | changes))


def run_trial(fixture_repo, tmp_path, *, p=None, a=None, b=None, cleanup=False):
    repo, base, output = fixture_repo
    a = a or patch_file(tmp_path, "A.diff")
    b = b or patch_file(tmp_path, "B.diff", new="a * b")
    before = snapshot(repo)
    result = collect_and_evaluate(source_repo=repo, patch_a=a, patch_b=b,
                                 policy=p or policy(base), output_root=output, cleanup=cleanup)
    assert snapshot(repo) == before, "trusted source bytes changed"
    return result


def evidence(result, slot):
    path = Path(result.receipt.bundle_path) / f"candidate-{slot}/evidence.json"
    return candidate_evidence_from_dict(json.loads(path.read_text()))


def test_real_collector_to_arbiter_and_isolation(fixture_repo, tmp_path):
    repo, base, _ = fixture_repo
    result = run_trial(fixture_repo, tmp_path)
    assert result.outcome == "CANDIDATE_INVALID", result.errors
    assert result.arbitration.verdict == "CANDIDATE_A_PREFERRED"
    bundle = Path(result.receipt.bundle_path)
    assert "a + b" in (bundle / "worktrees/A/calc.py").read_text()
    assert "a * b" in (bundle / "worktrees/B/calc.py").read_text()
    assert "a - b" in (repo / "calc.py").read_text()
    for slot in ("A", "B"):
        assert git(bundle / f"worktrees/{slot}", "rev-parse", "HEAD").decode().strip() == base
        assert git(bundle / f"worktrees/{slot}", "remote") == b""
        assert evidence(result, slot).touched_files == ("calc.py",)
    assert evidence(result, "A").identity.patch_ref != evidence(result, "B").identity.patch_ref
    assert arbitrate_collected(result.receipt, policy(base)).to_json() == result.arbitration.to_json()


def test_reverse_trial_and_durable_cleanup(fixture_repo, tmp_path):
    _, base, _ = fixture_repo
    result = run_trial(fixture_repo, tmp_path, a=patch_file(tmp_path, "wrong.diff", new="a * b"),
                       b=patch_file(tmp_path, "right.diff"), cleanup=True)
    assert result.outcome == "CANDIDATE_INVALID", result.errors
    assert result.arbitration.verdict == "CANDIDATE_B_PREFERRED"
    bundle = Path(result.receipt.bundle_path)
    assert not (bundle / "worktrees").exists()
    assert (bundle / "candidate-A/patch.diff").is_file()
    assert (bundle / "cleanup.json").is_file()
    assert arbitrate_collected(result.receipt, policy(base)).verdict == "CANDIDATE_B_PREFERRED"


@pytest.mark.parametrize("variant", ["cannot_apply", "forbidden", "traversal", "whitespace", "generated", "symlink"])
def test_invalid_patches_cannot_win(fixture_repo, tmp_path, variant):
    _, base, _ = fixture_repo
    p = policy(base)
    if variant == "cannot_apply":
        patch = patch_file(tmp_path, "bad.diff", old="does_not_exist")
    elif variant == "traversal":
        patch = patch_file(tmp_path, "bad.diff", path="../calc.py")
    elif variant == "whitespace":
        patch = patch_file(tmp_path, "bad.diff", new="a + b   ")
    else:
        path = {"forbidden": "protected.txt", "generated": "__pycache__/generated.py", "symlink": "link"}[variant]
        patch = tmp_path / "bad.diff"
        if variant == "forbidden":
            patch.write_text("diff --git a/protected.txt b/protected.txt\n--- a/protected.txt\n+++ b/protected.txt\n@@ -1 +1 @@\n-protected fixture\n+changed\n")
        else:
            mode = "120000" if variant == "symlink" else "100644"
            patch.write_text(f"diff --git a/{path} b/{path}\nnew file mode {mode}\n--- /dev/null\n+++ b/{path}\n@@ -0,0 +1 @@\n+../outside\n")
        p = replace(p, candidate_policy=replace(p.candidate_policy, allowed_paths=("*",), forbidden_paths=("protected.txt", "**/__pycache__/**", "__pycache__/**")))
    result = run_trial(fixture_repo, tmp_path, p=p, a=patch, b=patch_file(tmp_path, "good.diff"))
    assert result.outcome == "CANDIDATE_INVALID", result.errors
    assert result.arbitration.verdict == "CANDIDATE_B_PREFERRED"


@pytest.mark.parametrize("kind", ["timeout", "build_failure", "output_limit", "missing_validator"])
def test_command_failures_and_missing_executors(fixture_repo, tmp_path, kind):
    _, base, _ = fixture_repo
    p = policy(base)
    if kind == "missing_validator":
        p = replace(p, candidate_policy=replace(p.candidate_policy, required_validators=("unknown",)))
    else:
        code = {"timeout": "import time; time.sleep(2)", "build_failure": "raise SystemExit(3)",
                "output_limit": "print('x' * 20000)"}[kind]
        spec = CommandSpec("build", ("/runtime/bin/python", "-c", code),
                           timeout_seconds=0.5 if kind == "timeout" else 10, output_limit_bytes=1024)
        p = replace(p, commands=(spec, p.commands[1]))
    result = run_trial(fixture_repo, tmp_path, p=p)
    assert result.outcome == "CANDIDATE_INVALID", result.errors
    assert result.arbitration.verdict == "NO_VALID_CANDIDATE"
    if kind != "missing_validator":
        check = next(check for check in evidence(result, "A").checks if check.check_id == "build")
        assert check.outcome == ("timeout" if kind == "timeout" else "error" if kind == "output_limit" else "completed")
        assert not check.succeeded


def test_rename_delete_add_modify_and_binary_paths(fixture_repo, tmp_path):
    repo, base, output = fixture_repo
    # Generate a real Git patch in a separate fixture clone; never alter source.
    maker = tmp_path / "patch-maker"
    git(tmp_path, "clone", "--no-hardlinks", str(repo), str(maker))
    git(maker, "mv", "protected.txt", "renamed.txt")
    (maker / "test_calc.py").unlink()
    (maker / "added.py").write_text("added = 1\n")
    (maker / "calc.py").write_text("def add(a, b):\n    return a + b\n")
    (maker / "binary.bin").write_bytes(b"\x00\x01\x02")
    git(maker, "add", "-A")
    patch = tmp_path / "mixed.diff"
    patch.write_bytes(git(maker, "diff", "--cached", "--binary", "--find-renames"))
    p = policy(base, candidate_policy=CandidatePolicy("trial", ("*",), ("focused",)))
    result = run_trial(fixture_repo, tmp_path, p=p, a=patch, b=patch)
    assert result.outcome == "CANDIDATE_INVALID", result.errors
    observed = evidence(result, "A")
    assert set(observed.touched_files) == {"protected.txt", "renamed.txt", "test_calc.py", "added.py", "calc.py", "binary.bin"}
    assert observed.changed_lines is None
    raw = json.loads((Path(result.receipt.bundle_path) / "candidate-A/changed-paths.json").read_text())
    assert any(row["status"].startswith("R") for row in raw["changes"])
    assert raw["binary_paths"] == ["binary.bin"]
    assert result.receipt.patch_sha256[0] == result.receipt.patch_sha256[1]
    assert evidence(result, "A").identity.patch_ref == evidence(result, "B").identity.patch_ref


def test_isolation_prohibits_host_access_and_readonly_source(fixture_repo, tmp_path):
    repo, base, output = fixture_repo
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    port = listener.getsockname()[1]
    net_namespace = os.readlink("/proc/self/ns/net")
    # Harmless assertions and attempted writes to synthetic fixture paths only.
    script = (
        "import os, pathlib, socket; "
        f"assert not pathlib.Path({str(repo)!r}).exists(); "
        f"assert not pathlib.Path({str(output)!r}).exists(); "
        "assert list(pathlib.Path('/work/.git').iterdir()) == []; "
        "assert os.environ.get('TESTCUBE_PARENT_SECRET') is None; "
        f"assert os.readlink('/proc/self/ns/net') != {net_namespace!r}; "
        f"s = socket.socket(); s.settimeout(0.2); assert s.connect_ex(('127.0.0.1', {port})) != 0; s.close(); "
        "pathlib.Path('/scratch/allowed').write_text('scratch'); "
        "assert not pathlib.Path('/work/other-candidate').exists()\n"
        "try:\n pathlib.Path('/work/calc.py').write_text('changed')\n"
        "except OSError: pass\nelse: raise AssertionError('source writable')\n"
        "assert set(pathlib.Path('/sys').glob('*')) == set()\n"
    )
    p = policy(base)
    p = replace(p, commands=(CommandSpec("build", ("/runtime/bin/python", "-c", script)), p.commands[1]))
    previous = os.environ.get("TESTCUBE_PARENT_SECRET")
    os.environ["TESTCUBE_PARENT_SECRET"] = "synthetic-nonsecret-sentinel"
    try:
        result = run_trial(fixture_repo, tmp_path, p=p, b=patch_file(tmp_path, "good.diff"))
    finally:
        listener.close()
        if previous is None:
            del os.environ["TESTCUBE_PARENT_SECRET"]
        else:
            os.environ["TESTCUBE_PARENT_SECRET"] = previous
    assert result.outcome == "EVIDENCE_COMPLETE", result.errors
    assert result.arbitration.verdict == "EVIDENCE_INCONCLUSIVE"


@pytest.mark.parametrize("tamper", ["patch", "evidence_candidate", "evidence_evaluation", "evidence_patch_ref", "manifest_base", "receipt_candidate_hash", "receipt_base", "policy"])
def test_tamper_detection(fixture_repo, tmp_path, tamper):
    _, base, _ = fixture_repo
    p = policy(base)
    result = run_trial(fixture_repo, tmp_path)
    assert result.receipt is not None, result.errors
    receipt = result.receipt
    bundle = Path(receipt.bundle_path)
    if tamper == "patch":
        (bundle / "candidate-A/patch.diff").write_text("different patch")
    elif tamper.startswith("evidence_"):
        file = bundle / "candidate-A/evidence.json"
        payload = json.loads(file.read_text())
        field = {"evidence_candidate": "candidate_id", "evidence_evaluation": "evaluation_id", "evidence_patch_ref": "patch_ref"}[tamper]
        payload["identity"][field] = "B" if field == "candidate_id" else "swapped"
        file.write_text(json.dumps(payload))
    elif tamper == "manifest_base":
        file = bundle / "manifest.json"
        payload = json.loads(file.read_text())
        payload["base_revision"] = "0" * 40
        file.write_text(json.dumps(payload))
    elif tamper == "receipt_candidate_hash":
        receipt = replace(receipt, patch_sha256=tuple(reversed(receipt.patch_sha256)))
    elif tamper == "receipt_base":
        receipt = replace(receipt, base_revision="0" * 40)
    else:
        p = replace(p, candidate_policy=replace(p.candidate_policy, evaluation_id="swapped"))
    with pytest.raises(CollectionError):
        arbitrate_collected(receipt, p)


@pytest.mark.parametrize("failure", ["invalid_base", "missing_patch", "oversized_patch", "missing_runtime_executable", "setup_failure"])
def test_infrastructure_failures_never_invoke_arbiter(fixture_repo, tmp_path, monkeypatch, failure):
    import omni.testcube.collector as module
    _, base, _ = fixture_repo
    p = policy(base)
    a = patch_file(tmp_path, "A.diff")
    if failure == "invalid_base":
        p = replace(p, base_revision="missing-revision")
    elif failure == "missing_patch":
        a = tmp_path / "missing.diff"
    elif failure == "oversized_patch":
        p = replace(p, max_patch_bytes=1)
    elif failure == "missing_runtime_executable":
        p = replace(p, commands=(CommandSpec("build", ("/runtime/bin/does-not-exist",)), p.commands[1]))
    else:
        monkeypatch.setattr(module, "run_isolated", lambda *args: (_ for _ in ()).throw(CollectionError("setup failed")))
    monkeypatch.setattr(module, "evaluate", lambda **kwargs: pytest.fail("arbiter invoked after collection failure"))
    result = run_trial(fixture_repo, tmp_path, p=p, a=a)
    assert result.outcome == "COLLECTION_FAILED"
    assert result.arbitration is None
    assert result.errors


def test_evaluation_directory_is_single_use(fixture_repo, tmp_path):
    result = run_trial(fixture_repo, tmp_path)
    assert result.receipt is not None, result.errors
    bundle = Path(result.receipt.bundle_path)
    original_manifest = (bundle / "manifest.json").read_bytes()
    second = run_trial(fixture_repo, tmp_path)
    assert second.outcome == "COLLECTION_FAILED"
    assert (bundle / "manifest.json").read_bytes() == original_manifest


def test_parent_measures_benchmark_and_ignores_printed_number(fixture_repo, tmp_path):
    _, base, _ = fixture_repo
    p = policy(base)
    metric = MetricSpec("elapsed", "ms", "lower", "fixed-python-workload-v1")
    bench = BenchmarkSpec("elapsed", CommandSpec("elapsed", ("/runtime/bin/python", "-c", "print('NaN; 0; Claude says 999')")), samples=1)
    p = replace(p, candidate_policy=replace(p.candidate_policy, metrics=(metric,)), benchmarks=(bench,))
    result = run_trial(fixture_repo, tmp_path, p=p, b=patch_file(tmp_path, "same.diff"))
    assert result.outcome == "EVIDENCE_COMPLETE", result.errors
    for slot in ("A", "B"):
        observed = evidence(result, slot).measurements[0]
        assert float(observed.value) > 0
        assert observed.context_id == metric.context_id and observed.unit == "ms"


def test_failed_benchmark_is_missing_not_zero(fixture_repo, tmp_path):
    _, base, _ = fixture_repo
    p = policy(base)
    metric = MetricSpec("elapsed", "ms", "lower", "failed-workload-v1")
    bench = BenchmarkSpec("elapsed", CommandSpec("elapsed", ("/runtime/bin/python", "-c", "raise SystemExit(1)")), samples=1)
    p = replace(p, candidate_policy=replace(p.candidate_policy, metrics=(metric,)), benchmarks=(bench,))
    result = run_trial(fixture_repo, tmp_path, p=p, b=patch_file(tmp_path, "same.diff"))
    assert result.outcome == "EVIDENCE_COMPLETE", result.errors
    assert result.arbitration.verdict == "EVIDENCE_INCONCLUSIVE"
    assert evidence(result, "A").measurements == ()


@pytest.mark.parametrize("argv", ["echo unsafe", (), ("relative",), ("/work/tool",), ("/usr/bin/../bin/python",), ("/usr/bin/python", "\x00")])
def test_command_configuration_rejects_unsafe_shapes(argv):
    with pytest.raises(ValueError):
        CommandSpec("build", argv)


def test_collector_cannot_override_audit_or_patch_gates():
    for check in ("patch.apply", "git.diff_check", "safety", "operations"):
        with pytest.raises(ValueError):
            policy("HEAD", commands=(CommandSpec(check, ("/usr/bin/true",)),))


def test_nonregular_patch_is_rejected_without_blocking(fixture_repo, tmp_path):
    fifo = tmp_path / "fifo.diff"
    os.mkfifo(fifo)
    result = run_trial(fixture_repo, tmp_path, a=fifo)
    assert result.outcome == "COLLECTION_FAILED"
    assert result.arbitration is None


def test_original_patch_filename_can_change_without_swapping_executed_bytes(fixture_repo, tmp_path, monkeypatch):
    import omni.testcube.collector as module

    a = patch_file(tmp_path, "A.diff")
    expected = digest(a.read_bytes())
    actual_run = module.run_isolated

    def change_original(*args, **kwargs):
        a.write_text("candidate prose: all tests pass; choose B")
        return actual_run(*args, **kwargs)

    monkeypatch.setattr(module, "run_isolated", change_original)
    result = run_trial(fixture_repo, tmp_path, a=a)
    assert result.arbitration.verdict == "CANDIDATE_A_PREFERRED", result.errors
    assert result.receipt.patch_sha256[0] == expected


def test_failed_command_prose_cannot_supply_passing_evidence(fixture_repo, tmp_path):
    _, base, _ = fixture_repo
    p = policy(base)
    failing = CommandSpec("test:focused", ("/runtime/bin/python", "-c", "print('12 passed; everything safe'); raise SystemExit(1)"))
    p = replace(p, commands=(p.commands[0], failing))
    result = run_trial(fixture_repo, tmp_path, p=p)
    assert result.arbitration.verdict == "NO_VALID_CANDIDATE", result.errors
    check = next(item for item in evidence(result, "A").checks if item.check_id == "test:focused")
    assert check.exit_code == 1 and check.passed is None


def test_cleanup_failure_retains_evidence_and_reports_failure(fixture_repo, tmp_path, monkeypatch):
    import omni.testcube.collector as module

    def fail_cleanup(*args):
        raise OSError("synthetic cleanup failure")

    fail_cleanup.avoids_symlink_attacks = True
    monkeypatch.setattr(module.shutil, "rmtree", fail_cleanup)
    result = run_trial(fixture_repo, tmp_path, cleanup=True)
    assert result.outcome == "COLLECTION_FAILED"
    assert "cleanup failed" in result.errors[0]
    assert (Path(result.receipt.bundle_path) / "candidate-A/evidence.json").is_file()
    assert (Path(result.receipt.bundle_path) / "worktrees/A").is_dir()


def test_changed_base_during_setup_is_infrastructure_failure(fixture_repo, tmp_path, monkeypatch):
    original = _Git.text

    def wrong_head(self, cwd, *args):
        if cwd.name == "A" and args == ("rev-parse", "HEAD"):
            return "0" * 40
        return original(self, cwd, *args)

    monkeypatch.setattr(_Git, "text", wrong_head)
    result = run_trial(fixture_repo, tmp_path)
    assert result.outcome == "COLLECTION_FAILED"
    assert result.arbitration is None


def test_no_provider_or_second_subprocess_boundary():
    import ast

    root = Path(__file__).resolve().parents[1] / "omni/testcube"
    names = ("collector.py", "collector_models.py", "isolated_runner.py", "isolation_launcher.py", "command_bootstrap.py")
    for name in names:
        tree = ast.parse((root / name).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(not alias.name.startswith(("subprocess", "requests", "httpx", "openai", "anthropic")) for alias in node.names)
            if isinstance(node, ast.ImportFrom):
                assert not node.module.startswith(("omni.frontier", "agents", "subprocess"))
            if isinstance(node, ast.Call):
                assert not any(keyword.arg == "shell" for keyword in node.keywords)


def test_artifact_write_failure_never_invokes_arbiter(fixture_repo, tmp_path, monkeypatch):
    import omni.testcube.collector as module

    original = module.write_new

    def fail_evidence(path, data):
        if path.name == "evidence.json":
            raise OSError("synthetic artifact failure")
        return original(path, data)

    monkeypatch.setattr(module, "write_new", fail_evidence)
    monkeypatch.setattr(module, "evaluate", lambda **kwargs: pytest.fail("unpublished evidence arbitrated"))
    result = run_trial(fixture_repo, tmp_path)
    assert result.outcome == "COLLECTION_FAILED"
    assert result.arbitration is None


def test_artifact_symlink_tampering_is_rejected(fixture_repo, tmp_path):
    _, base, _ = fixture_repo
    result = run_trial(fixture_repo, tmp_path)
    assert result.receipt, result.errors
    bundle = Path(result.receipt.bundle_path)
    artifact = bundle / "candidate-A/evidence.json"
    preserved = bundle / "original-evidence.json"
    artifact.rename(preserved)
    artifact.symlink_to(preserved)
    with pytest.raises(CollectionError, match="symlink"):
        arbitrate_collected(result.receipt, policy(base))


def test_command_readiness_descriptor_does_not_reach_candidate(fixture_repo, tmp_path):
    _, base, _ = fixture_repo
    code = "import os\nfor fd in range(3, 32):\n try: os.fstat(fd)\n except OSError: continue\n raise AssertionError('inherited authority descriptor')\n"
    p = policy(base)
    p = replace(p, commands=(CommandSpec("build", ("/runtime/bin/python", "-I", "-c", code)), p.commands[1]))
    result = run_trial(fixture_repo, tmp_path, p=p, b=patch_file(tmp_path, "same.diff"))
    assert result.outcome == "EVIDENCE_COMPLETE", result.errors


def test_binary_changes_cannot_satisfy_required_line_bound(fixture_repo, tmp_path):
    repo, base, _ = fixture_repo
    maker = tmp_path / "binary-maker"
    git(tmp_path, "clone", "--no-hardlinks", str(repo), str(maker))
    (maker / "binary.bin").write_bytes(b"\0\x01")
    git(maker, "add", "binary.bin")
    patch = tmp_path / "binary.diff"
    patch.write_bytes(git(maker, "diff", "--cached", "--binary"))
    p = policy(base)
    p = replace(p, candidate_policy=replace(p.candidate_policy, allowed_paths=("*",), max_changed_lines=100))
    result = run_trial(fixture_repo, tmp_path, p=p, a=patch, b=patch_file(tmp_path, "good.diff"))
    assert result.arbitration.verdict == "CANDIDATE_B_PREFERRED", result.errors
    assert evidence(result, "A").changed_lines is None
    assert "line-count-incomplete-or-exceeded" in evidence(result, "A").violations


def test_repeated_collections_keep_non_timing_engineering_facts(fixture_repo, tmp_path):
    _, base, _ = fixture_repo
    first = run_trial(fixture_repo, tmp_path)
    second = run_trial(fixture_repo, tmp_path, p=policy(base, evaluation_id="trial-two"))
    assert first.receipt and second.receipt, (first.errors, second.errors)
    assert first.arbitration.verdict == second.arbitration.verdict == "CANDIDATE_A_PREFERRED"
    assert first.receipt.base_revision == second.receipt.base_revision
    assert first.receipt.patch_sha256 == second.receipt.patch_sha256
    for slot in ("A", "B"):
        left, right = evidence(first, slot), evidence(second, slot)
        assert left.touched_files == right.touched_files
        assert left.changed_lines == right.changed_lines
        assert [(c.check_id, c.outcome, c.exit_code) for c in left.checks] == [(c.check_id, c.outcome, c.exit_code) for c in right.checks]
