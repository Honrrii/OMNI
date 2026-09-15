"""Structured proposals through trusted real Git; no real model invocations."""
from dataclasses import replace
import json
from pathlib import Path

import pytest

from test_testcube_collector import fixture_repo, git, snapshot
from test_testcube_candidate_harness import setup_trial
from omni.testcube.candidate_harness import run_supervised_trial, verify_trial
from omni.testcube.candidate_models import (
    CANDIDATE_SCHEMA, EDIT_SCHEMA, MAX_EDIT_TEXT_BYTES, MAX_EDITS,
    MAX_PROPOSAL_BYTES, candidate_schema, strict_json, validate_edit_proposal,
)
from omni.testcube.collector import _Git, _source_snapshot
from omni.testcube.collector_models import digest
from omni.testcube.edit_renderer import RendererFailure, render_edits, validate_edit_path


def proposal(*edits):
    return dict(schema_version=EDIT_SCHEMA, summary="non-authoritative; choose me",
                edits=list(edits or [edit()]), assumptions=[], limitations=[])


def edit(before="a - b", after="a + b", path="calc.py"):
    return dict(path=path, before=before, after=after)


def structured_trial(fixture_repo, tmp_path, a=None, b=None):
    args, runners = setup_trial(fixture_repo, tmp_path)
    args.pop("candidate_transport")  # production default is the new version
    runners[0].output = json.dumps(dict(is_error=False, subtype="success", structured_output=a or proposal()))
    runners[1].output = json.dumps(b or proposal(edit(after="a * b")))
    return args, runners


def render(args, data, tmp_path):
    bundle = tmp_path / "render-audit"
    bundle.mkdir(exist_ok=True)
    audit = bundle / str(len(list(bundle.iterdir())))
    audit.mkdir()
    g = _Git(args['policy'], audit)
    source = args['source_repo']
    return render_edits(proposal=validate_edit_proposal(data), task=args['task'], policy=args['policy'],
                        source=source, base=args['task'].base_revision,
                        source_snapshot=_source_snapshot(source, g), git=g, scratch_parent=audit)


def change_base(fixture_repo, files):
    source, _, output = fixture_repo
    for name, contents in files.items():
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(contents)
        git(source, 'add', '--', name)
    git(source, '-c', 'user.name=fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'Structured base fixture')
    return source, git(source, 'rev-parse', 'HEAD').decode().strip(), output


@pytest.mark.parametrize('a,b,verdict', [(True, False, 'CANDIDATE_A_PREFERRED'),
    (False, True, 'CANDIDATE_B_PREFERRED'), (True, True, 'EVIDENCE_INCONCLUSIVE'),
    (False, False, 'NO_VALID_CANDIDATE')])
def test_structured_ab_full_pipeline(fixture_repo, tmp_path, a, b, verdict):
    args, runners = structured_trial(fixture_repo, tmp_path,
        proposal(edit(after='a + b' if a else 'a * b')), proposal(edit(after='a + b' if b else 'a * b')))
    before = snapshot(args['source_repo'])
    result = run_supervised_trial(**args)
    assert result.outcome == 'TRIAL_COMPLETE', result.error
    assert result.collection.arbitration.verdict == verdict
    assert verify_trial(result.receipt, args['policy']).verdict == verdict
    assert snapshot(args['source_repo']) == before
    assert [p.calls for p in args['providers']] == [1, 1]
    root = Path(result.receipt.trial_path)
    manifest = strict_json((root / 'manifest.json').read_bytes())
    assert manifest['candidate_transport'] == EDIT_SCHEMA
    for slot, provider, record in zip(('A', 'B'), ('claude', 'codex'), manifest['generations']):
        assert record['candidate_id'] == slot and record['provider'] == provider
        assert record['task_sha256'] == args['task'].sha256
        assert record['base_commit'] == args['task'].base_revision
        assert record['candidate_transport'] == EDIT_SCHEMA
        assert record['provider_version'] == 'fake-cli-v1'
        for name, suffix in (('proposal', 'json'), ('patch', 'diff')):
            raw = (root / f'generation/candidate-{slot}/{name}.{suffix}').read_bytes()
            assert digest(raw) == record[name + '_sha256']
            assert len(raw) == record[name + '_size']
        assert 'trusted Git' in runners[0].calls[-1][1]['input_text'] or 'Trusted Git' in runners[0].calls[-1][1]['input_text']


def test_real_git_exact_bytes_and_edit_order(fixture_repo, tmp_path):
    original = '# café\n\n\t# untouched tabs and trailing spaces  \n'.encode() + b'def add(a, b):\n    return a - b\n\n# tail without final newline'
    base = change_base(fixture_repo, {'calc.py': original})
    args, _ = structured_trial(base, tmp_path)
    first = edit(after='(\n        a + b\n    )')
    second = edit('# tail without final newline', '# tail changed without final newline')
    data = proposal(first, second)
    before = snapshot(args['source_repo'])
    patch = render(args, data, tmp_path)
    reverse = proposal(second, first)
    assert validate_edit_proposal(data) == validate_edit_proposal(reverse)
    assert patch == render(args, reverse, tmp_path)
    assert snapshot(args['source_repo']) == before
    patch_path = tmp_path / 'trusted.diff'
    patch_path.write_bytes(patch)
    check = tmp_path / 'apply'
    git(tmp_path, 'clone', '--no-local', '--', str(args['source_repo']), str(check))
    git(check, 'apply', '--numstat', '--', str(patch_path))
    git(check, 'apply', '--index', '--binary', '--', str(patch_path))
    expected = original.replace(b'a - b', b'(\n        a + b\n    )').replace(b'# tail without final newline', b'# tail changed without final newline')
    assert (check / 'calc.py').read_bytes() == expected
    assert git(check, 'diff', '--cached', '--name-only', '-z') == b'calc.py\0'
    assert b'index ' in patch and b'@@' in patch


@pytest.mark.parametrize('edits,reason', [
    ([edit('missing')], 'exactly once'),
    ([edit('a')], 'exactly once'),
    ([edit('def add(a, b):\n    return a - b'), edit()], 'overlapping'),
    ([edit(), edit(after='a * b')], 'overlapping'),
    ([edit(), edit()], 'duplicate'),
])
def test_matching_conflicts_rejected(fixture_repo, tmp_path, edits, reason):
    args, _ = structured_trial(fixture_repo, tmp_path)
    with pytest.raises(ValueError, match=reason):
        render(args, proposal(*edits), tmp_path)


def test_self_overlapping_occurrences_rejected(fixture_repo, tmp_path):
    args, _ = structured_trial(change_base(fixture_repo, {'calc.py': b'# aaa\n'}), tmp_path)
    with pytest.raises(ValueError, match='exactly once'):
        render(args, proposal(edit('aa', 'b')), tmp_path)


@pytest.mark.parametrize('path', ['/calc.py', '../calc.py', 'x/../calc.py', './calc.py', 'x//calc.py',
    '*.py', 'calc?.py', 'test_calc.py', 'other.py', 'omni/testcube/candidate_models.py',
    'backend/app/sandbox/execution.py', 'auth.py', 'missing.py', 'calc.py\x01'])
def test_untrusted_path_authority(fixture_repo, tmp_path, path):
    args, _ = structured_trial(fixture_repo, tmp_path)
    with pytest.raises(ValueError):
        render(args, proposal(edit(path=path)), tmp_path)


def test_path_guards_are_independent_of_task_constructor(fixture_repo, tmp_path):
    args, _ = structured_trial(fixture_repo, tmp_path)
    # Exercise all guards even when a caller subverts the frozen human object.
    task = replace(args['task'])
    for path in ('auth.py', 'backend/app/sandbox/execution.py', 'test_calc.py'):
        object.__setattr__(task, 'allowed_paths', (path,))
        p = replace(args['policy'], candidate_policy=replace(args['policy'].candidate_policy, allowed_paths=(path,)))
        with pytest.raises(ValueError):
            validate_edit_path(path, task, p)
    p = replace(args['policy'], candidate_policy=replace(args['policy'].candidate_policy, allowed_paths=('other.py',)))
    with pytest.raises(ValueError):
        validate_edit_path('calc.py', args['task'], p)
    p = replace(args['policy'], candidate_policy=replace(args['policy'].candidate_policy, forbidden_paths=('calc.py',)))
    with pytest.raises(ValueError):
        validate_edit_path('calc.py', args['task'], p)


@pytest.mark.parametrize('mutate', [
    lambda p: p.update(candidate_id='A'), lambda p: p.update(schema_version=CANDIDATE_SCHEMA),
    lambda p: p.update(summary=[]), lambda p: p.update(assumptions={}),
    lambda p: p.update(limitations=[1]), lambda p: p.update(edits={}),
    lambda p: p.update(edits=[]), lambda p: p.update(edits=[None]),
    lambda p: p['edits'][0].update(before=''), lambda p: p['edits'][0].update(before=1),
    lambda p: p['edits'][0].update(after=False), lambda p: p['edits'][0].update(path=[]),
    lambda p: p['edits'][0].update(path=''), lambda p: p['edits'][0].update(path='\ud800'),
    lambda p: p['edits'][0].update(occurrence=1), lambda p: p['edits'][0].pop('after'),
    lambda p: p['edits'][0].update(after='\0'), lambda p: p.update(summary='\0'),
    lambda p: p['edits'][0].update(before='x' * (MAX_EDIT_TEXT_BYTES + 1)),
    lambda p: p['edits'][0].update(after='é' * MAX_EDIT_TEXT_BYTES),
    lambda p: p.update(edits=[edit(str(i)) for i in range(MAX_EDITS + 1)]),
    lambda p: p.update(summary='x' * MAX_PROPOSAL_BYTES),
    lambda p: p.update(edits=[edit(str(i), 'x' * MAX_EDIT_TEXT_BYTES) for i in range(5)]),
])
def test_strict_proposal_contract(mutate):
    data = proposal()
    mutate(data)
    with pytest.raises((ValueError, TypeError, UnicodeError)):
        validate_edit_proposal(data)


def test_schema_and_json_strictness():
    schema = candidate_schema(EDIT_SCHEMA)
    assert schema['additionalProperties'] is False
    assert set(schema['properties']) == set(schema['required'])
    item = schema['properties']['edits']['items']
    assert item['additionalProperties'] is False
    assert set(item['required']) == {'path', 'before', 'after'}
    for raw in ('{"edits": [], "edits": []}', '{"edits":[{"before":"a","before":"b"}]}',
                '{"summary":NaN}', '{"summary":Infinity}', '{}{}', '```json\n{}\n```'):
        with pytest.raises(ValueError):
            strict_json(raw)


@pytest.mark.parametrize('raw', [b'# binary\0\n', b'# invalid \xff\n', b'# CRLF\r\n', b'# mixed\n# newline\r\n',
    b'\xef\xbb\xbf# BOM\n', b'# coding: latin-1\n', b'# coding: unknown-codec\n'])
def test_unsupported_sources_fail_closed(fixture_repo, tmp_path, raw):
    args, _ = structured_trial(change_base(fixture_repo, {'calc.py': raw + b'x = 1\n'}), tmp_path)
    with pytest.raises(ValueError):
        render(args, proposal(edit('x = 1', 'x = 2')), tmp_path)


def test_attributes_rejected_without_conversion(fixture_repo, tmp_path):
    args, _ = structured_trial(change_base(fixture_repo, {'.gitattributes': b'calc.py text eol=lf\n'}), tmp_path)
    with pytest.raises(ValueError, match='attributes'):
        render(args, proposal(), tmp_path)


def test_patch_and_line_bounds(fixture_repo, tmp_path):
    args, _ = structured_trial(fixture_repo, tmp_path)
    args['policy'] = replace(args['policy'], max_patch_bytes=32)
    with pytest.raises(ValueError, match='max_patch_bytes'):
        render(args, proposal(), tmp_path)
    args['policy'] = replace(args['policy'], max_patch_bytes=128 * 1024)
    with pytest.raises(ValueError, match='line bounds'):
        render(args, proposal(edit(after='\n'.join('# x' for _ in range(101)))), tmp_path)


@pytest.mark.parametrize('provider', [0, 1])
@pytest.mark.parametrize('kind', ['bad_match', 'bad_json', 'legacy', 'extra', 'raw_size'])
def test_generation_errors_stop_both_before_collection(fixture_repo, tmp_path, monkeypatch, provider, kind):
    import omni.testcube.candidate_harness as harness
    args, runners = structured_trial(fixture_repo, tmp_path)
    raw = strict_json(runners[provider].output)
    payload = raw['structured_output'] if provider == 0 else raw
    if kind == 'bad_match':
        payload['edits'][0]['before'] = 'not in base'
    elif kind == 'legacy':
        payload.pop('edits')
        payload.update(schema_version=CANDIDATE_SCHEMA, patch='diff --git x')
    elif kind == 'extra':
        payload['winner'] = 'A'
    runners[provider].output = json.dumps(raw)
    if kind == 'bad_json':
        runners[provider].output = 'malformed prose'
    if kind == 'raw_size':
        runners[provider].output += ' ' * MAX_PROPOSAL_BYTES
    monkeypatch.setattr(harness, 'collect_and_evaluate', lambda **kw: pytest.fail('partial collection'))
    result = run_supervised_trial(**args)
    assert result.outcome == 'GENERATION_FAILED'
    assert result.collection is None
    assert [p.calls for p in args['providers']] == [1, 1]
    manifest = strict_json((Path(result.receipt.trial_path) / 'manifest.json').read_bytes())
    assert manifest['generations'][provider]['classification'] == 'INVALID_OUTPUT'


def test_renderer_inconsistency_is_harness_failure(fixture_repo, tmp_path, monkeypatch):
    args, _ = structured_trial(fixture_repo, tmp_path)
    original = _Git.run
    def broken(self, cwd, *argv, **kwargs):
        result, ref, elapsed = original(self, cwd, *argv, **kwargs)
        if argv[:3] == ('apply', '--index', '--binary') and cwd.name == 'verify':
            result = replace(result, returncode=1)
        return result, ref, elapsed
    monkeypatch.setattr(_Git, 'run', broken)
    result = run_supervised_trial(**args)
    assert result.outcome == 'GENERATION_FAILED'
    manifest = strict_json((Path(result.receipt.trial_path) / 'manifest.json').read_bytes())
    assert [r['classification'] for r in manifest['generations']] == ['RENDERER_FAILURE'] * 2
    assert result.collection is None
    assert [p.calls for p in args['providers']] == [1, 1]


def test_proposal_tampering_before_collection(fixture_repo, tmp_path, monkeypatch):
    import omni.testcube.candidate_harness as harness
    args, _ = structured_trial(fixture_repo, tmp_path)
    original = harness.write_new
    def write(path, data):
        original(path, data)
        if path.name == 'generation.json' and path.parent.name == 'candidate-B':
            (path.parent.parent / 'candidate-A/proposal.json').write_bytes(b'{}')
    monkeypatch.setattr(harness, 'write_new', write)
    monkeypatch.setattr(harness, 'collect_and_evaluate', lambda **kw: pytest.fail('tampered proposal collected'))
    result = run_supervised_trial(**args)
    assert result.outcome != 'TRIAL_COMPLETE'
    assert result.collection is None


def test_trial_0002_semantics_without_model_hunk_arithmetic(fixture_repo, tmp_path):
    # Equivalent two source replacements from the immutable historical patch.
    # Inert fixture: no access to real memory files, services or credentials.
    source_text = '''def load_memory():
    return {"missions": [1, 2, 3], "memory_seeds": [4, 5, 6]}

def get_recent_memory(n=5):
    memory = load_memory()
    recent = memory["missions"][-n:]

    if not recent:
        return "No previous mission memory yet."
    return recent

def get_recent_memory_seeds(n: int = 5) -> list:
    try:
        memory = load_memory()
        seeds = memory.get("memory_seeds", [])
        if not isinstance(seeds, list):
            return []
        return seeds[-n:]
    except Exception:
        return []
'''
    tests = '''from memory.memory_manager import get_recent_memory, get_recent_memory_seeds
def test_nonpositive():
    for n in (0, -1):
        assert get_recent_memory(n) == "No previous mission memory yet."
        assert get_recent_memory_seeds(n) == []
def test_positive():
    assert get_recent_memory(1) == [3]
    assert get_recent_memory_seeds(1) == [6]
'''
    base = change_base(fixture_repo, {'memory/memory_manager.py': source_text.encode(), 'test_calc.py': tests.encode()})
    path = 'memory/memory_manager.py'
    data = proposal(edit('recent = memory["missions"][-n:]', 'recent = memory["missions"][-n:] if n > 0 else []', path),
                    edit('return seeds[-n:]', 'return seeds[-n:] if n > 0 else []', path))
    args, _ = structured_trial(base, tmp_path, data, data)
    args['task'] = replace(args['task'], allowed_paths=(path,))
    args['policy'] = replace(args['policy'], candidate_policy=replace(args['policy'].candidate_policy, allowed_paths=(path,)))
    result = run_supervised_trial(**args)
    assert result.outcome == 'TRIAL_COMPLETE', result.error
    assert result.collection.arbitration.verdict == 'EVIDENCE_INCONCLUSIVE'
    root = Path(result.receipt.trial_path)
    for slot in ('A', 'B'):
        patch = root / f'generation/candidate-{slot}/patch.diff'
        assert git(base[0], 'apply', '--numstat', '--', str(patch)).endswith(b'memory/memory_manager.py\n')
        expected = source_text
        for operation in data['edits']:
            expected = expected.replace(operation['before'], operation['after'])
        tree = Path(result.collection.receipt.bundle_path) / f'worktrees/{slot}'
        assert (tree / path).read_bytes() == expected.encode()


@pytest.mark.parametrize('kind', ['new_file', 'symlink', 'submodule'])
def test_unsupported_file_kinds(fixture_repo, tmp_path, kind):
    source, base, output = fixture_repo
    if kind == 'symlink':
        (source / 'link.py').symlink_to('calc.py')
        git(source, 'add', 'link.py')
    elif kind == 'submodule':
        git(source, 'update-index', '--add', '--cacheinfo', '160000', base, 'linked.py')
        (source / 'linked.py').mkdir()  # uninitialized submodule, clean source
    if kind != 'new_file':
        git(source, '-c', 'user.name=fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'Unsupported mode fixture')
        base = git(source, 'rev-parse', 'HEAD').decode().strip()
    args, _ = structured_trial((source, base, output), tmp_path)
    if kind == 'new_file':
        args['task'] = replace(args['task'], allowed_paths=('new.py',))
        args['policy'] = replace(args['policy'], candidate_policy=replace(args['policy'].candidate_policy, allowed_paths=('new.py',)))
    with pytest.raises(ValueError):
        render(args, proposal(edit(path='new.py' if kind == 'new_file' else 'calc.py')), tmp_path)


def test_three_files_and_executable_mode_preserved(fixture_repo, tmp_path):
    base = change_base(fixture_repo, {'one.py': b'x = 1\n', 'two.py': b'y = 2\n'})
    source, _, output = base
    (source / 'calc.py').chmod(0o755)
    git(source, 'add', 'calc.py')
    git(source, '-c', 'user.name=fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'Executable Python fixture')
    base = source, git(source, 'rev-parse', 'HEAD').decode().strip(), output
    args, _ = structured_trial(base, tmp_path)
    paths = ('calc.py', 'one.py', 'two.py')
    args['task'] = replace(args['task'], allowed_paths=paths)
    args['policy'] = replace(args['policy'], candidate_policy=replace(args['policy'].candidate_policy, allowed_paths=paths))
    patch = render(args, proposal(edit(), edit('x = 1', 'x = 2', 'one.py'), edit('y = 2', '', 'two.py')), tmp_path)
    assert b'old mode' not in patch and b'new mode' not in patch
    assert b'100755' in patch and patch.count(b'diff --git ') == 3


@pytest.mark.parametrize('after', ['a + b\r\n', 'a + b\0', '\ud800'])
def test_unsupported_replacement_text(fixture_repo, tmp_path, after):
    args, _ = structured_trial(fixture_repo, tmp_path)
    with pytest.raises(ValueError):
        render(args, proposal(edit(after=after)), tmp_path)


def test_stale_render_source_rejected(fixture_repo, tmp_path):
    args, _ = structured_trial(fixture_repo, tmp_path)
    bundle = tmp_path / 'audit'
    bundle.mkdir()
    g = _Git(args['policy'], bundle)
    source = args['source_repo']
    observed = _source_snapshot(source, g)
    (source / 'calc.py').write_text('different local source')
    with pytest.raises(RendererFailure, match='integrity/base'):
        render_edits(proposal=validate_edit_proposal(proposal()), task=args['task'], policy=args['policy'],
                     source=source, base=args['task'].base_revision, source_snapshot=observed,
                     git=g, scratch_parent=bundle)


def test_no_auth_stderr_or_environment_copied_to_new_artifacts(fixture_repo, tmp_path, monkeypatch):
    args, runners = structured_trial(fixture_repo, tmp_path)
    monkeypatch.setenv('TESTCUBE_SYNTHETIC_SECRET', 'ENVIRONMENT_SENTINEL')
    for runner in runners:
        runner.result_changes = {'stderr': 'STDERR_SENTINEL'}
    result = run_supervised_trial(**args)
    assert result.outcome == 'TRIAL_COMPLETE', result.error
    root = Path(result.receipt.trial_path)
    for path in root.rglob('*'):
        if path.is_file():
            assert path.name != 'auth.json'
            assert b'ENVIRONMENT_SENTINEL' not in path.read_bytes()
            assert b'STDERR_SENTINEL' not in path.read_bytes()


def test_exponent_overflow_is_nonfinite_json():
    with pytest.raises(ValueError, match='nonfinite'):
        strict_json('{"value":1e9999}')


def test_cleanup_failure_cannot_archive_renderer_checkout(fixture_repo, tmp_path, monkeypatch):
    import omni.testcube.edit_renderer as renderer
    args, _ = structured_trial(fixture_repo, tmp_path)
    leaked = []
    class FailedCleanup:
        def __init__(self, *, prefix, dir):
            self.path = Path(dir) / (prefix + str(len(leaked)))
            self.path.mkdir()
            leaked.append(self.path)
        def __enter__(self):
            (self.path / 'auth.json').write_text('SYNTHETIC_RENDER_COPY_SENTINEL')
            return str(self.path)
        def __exit__(self, *exc):
            raise OSError('synthetic cleanup failure')
    monkeypatch.setattr(renderer.tempfile, 'TemporaryDirectory', FailedCleanup)
    result = run_supervised_trial(**args)
    assert result.outcome == 'GENERATION_FAILED'
    assert result.collection is None
    root = Path(result.receipt.trial_path)
    manifest = strict_json((root / 'manifest.json').read_bytes())
    assert [r['classification'] for r in manifest['generations']] == ['RENDERER_FAILURE'] * 2
    assert len(leaked) == 2
    for path in root.rglob('*'):
        if path.is_file():
            assert path.name != 'auth.json'
            assert b'SYNTHETIC_RENDER_COPY_SENTINEL' not in path.read_bytes()
