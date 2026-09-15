"""Trusted exact-byte replacement and Git rendering; never execute proposals."""
from __future__ import annotations

import io
from pathlib import Path
import tempfile
import tokenize

from omni.autodev.protected_paths import (
    GLOB_METACHARACTERS, match_protected_path, normalize_repo_relative_path, spec_matches,
)
from omni.testcube.candidate_models import FIRST_TRIAL_FORBIDDEN, strict_json, validate_edit_proposal
from omni.testcube.collector import (
    _FULL_SHA, _changes, _read_regular, _scope_violations, _source_snapshot, _tree_modes,
)
from omni.testcube.isolated_runner import CollectionError

MAX_SOURCE_BYTES = 1024 * 1024


class RendererFailure(RuntimeError):
    """Trusted rendering or re-application inconsistency, never INVALID_OUTPUT."""


def validate_edit_path(path, task, policy):
    p = policy.candidate_policy
    if (normalize_repo_relative_path(path) != path or
        any(c in path for c in GLOB_METACHARACTERS) or
        any(ord(c) < 32 or ord(c) == 127 for c in path) or
        not path.endswith(".py") or path not in task.allowed_paths or
        not any(spec_matches(rule, path) for rule in p.allowed_paths) or
        path in task.validation_paths or match_protected_path(path) or
        any(spec_matches(rule, path.lower()) for rule in FIRST_TRIAL_FORBIDDEN) or
        any(spec_matches(rule, path) for rule in task.forbidden_paths + p.forbidden_paths)):
        raise ValueError("edit path outside human-owned authority")


def _text_source(raw):
    # Deliberately LF-only, UTF-8 without BOM. Byte I/O never normalizes text.
    raw.decode("utf-8", errors="strict")
    if b"\0" in raw or b"\r" in raw or raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError("unsupported source text/newline form")
    try:
        encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
    except SyntaxError as exc:
        raise ValueError("unsupported Python source encoding") from exc
    if encoding != "utf-8":
        raise ValueError("unsupported Python source encoding")


def _copy_at_base(source, tree, base, git):
    git.run(tree.parent, "clone", "--no-local", "--no-hardlinks", "--no-checkout", "--", str(source), str(tree))
    git.run(tree, "config", "--remove-section", "remote.origin")
    git.run(tree, "checkout", "--detach", base)
    observed = _source_snapshot(tree, git)
    if observed["head"] != base or not observed["clean"]:
        raise RendererFailure("render copy is not clean at pinned base")


def render_edits(*, proposal, task, policy, source, base, source_snapshot, git, scratch_parent):
    """Return canonical patch bytes after fresh-copy application and scope checks.

    ValueError denotes an unsupported proposal. Trusted Git/I/O failures have
    a distinct classification. The supplied Git logger lives in the receipt;
    disposable repositories and their configuration are never archived.
    """
    try:
        return _render(proposal, task, policy, source, base, source_snapshot, git, scratch_parent)
    except (CollectionError, OSError) as exc:
        raise RendererFailure("trusted Git/render I/O failed") from exc


def _render(proposal, task, policy, source, base, source_snapshot, git, scratch_parent):
    data = strict_json(validate_edit_proposal(strict_json(proposal)))
    task.validate_policy(policy)
    if (not _FULL_SHA.fullmatch(base) or not source_snapshot["clean"] or
        source_snapshot["head"] != base or _source_snapshot(source, git) != source_snapshot):
        raise RendererFailure("source integrity/base changed before rendering")
    if _tree_modes(git.text(source, "ls-tree", "-r", "-z", base)):
        raise ValueError("unsupported symlinks/submodules")
    grouped = {}
    for edit in data["edits"]:
        validate_edit_path(edit["path"], task, policy)
        grouped.setdefault(edit["path"], []).append(edit)
    if not 1 <= len(grouped) <= task.max_touched_files:
        raise ValueError("too many edited files")
    with tempfile.TemporaryDirectory(prefix="renderer-", dir=scratch_parent) as temporary:
        root = Path(temporary)
        tree = root / "render"
        _copy_at_base(source, tree, base, git)
        expected = {}
        original_modes = {}
        for path, edits in sorted(grouped.items()):
            target = tree / path
            entry = git.text(tree, "ls-tree", "-z", base, "--", path)
            if (not entry or _tree_modes(entry) or target.resolve() != target or
                not target.is_file()):
                raise ValueError("edit requires an existing regular base file")
            # No attributes (filters, encoding, diff drivers, EOL transforms)
            # are supported on edited files in this first transport version.
            if git.text(tree, "check-attr", "--cached", "--all", "-z", "--", path):
                raise ValueError("attributes on edited source are unsupported")
            if target.stat().st_size > MAX_SOURCE_BYTES:
                raise ValueError("source file too large")
            raw = _read_regular(target, MAX_SOURCE_BYTES)
            _text_source(raw)
            blob = entry.split("\t", 1)[0].split()[2]
            if git.text(tree, "hash-object", "--no-filters", "--", path).strip() != blob:
                raise RendererFailure("checkout bytes differ from pinned blob")
            ranges = []
            for edit in edits:
                before, after = (edit[name].encode("utf-8") for name in ("before", "after"))
                start = raw.find(before)
                # Search from start+1 to count overlapping occurrences too.
                if start < 0 or raw.find(before, start + 1) >= 0:
                    raise ValueError("before must occur exactly once in original base")
                ranges.append((start, start + len(before), after))
            ranges.sort()
            if any(left[1] > right[0] for left, right in zip(ranges, ranges[1:])):
                raise ValueError("overlapping original source ranges")
            replaced = raw
            for start, end, after in reversed(ranges):
                replaced = replaced[:start] + after + replaced[end:]
            _text_source(replaced)
            if replaced == raw:
                raise ValueError("edit plan makes no change")
            expected[path] = replaced
            original_modes[path] = target.stat().st_mode
            target.write_bytes(replaced)
        patch_path = root / "patch.diff"
        # Write bytes directly: process stdout decoding must not touch patches.
        git.run(tree, "diff", "--binary", "--no-ext-diff", "--no-textconv", "--no-renames",
                "--full-index", "--no-color", "--diff-algorithm=myers", "--no-indent-heuristic",
                "--unified=3", "--src-prefix=a/", "--dst-prefix=b/", "--inter-hunk-context=0",
                f"--output={patch_path}", base, "--")
        if patch_path.stat().st_size > policy.max_patch_bytes:
            raise ValueError("rendered patch exceeds max_patch_bytes")
        patch = _read_regular(patch_path, policy.max_patch_bytes)
        if not patch.startswith(b"diff --git ") or b"\0" in patch:
            raise RendererFailure("trusted Git emitted unsupported patch")
        fresh = root / "verify"
        _copy_at_base(source, fresh, base, git)
        applied = git.run(fresh, "apply", "--index", "--binary", "--whitespace=nowarn", "--",
                          str(patch_path), required=False)[0]
        if applied.returncode != 0:
            raise RendererFailure("trusted patch failed fresh-base re-application")
        changes = _changes(fresh, base, git)
        if (set(changes["touched_files"]) != set(expected) or
            any(change["status"] != "M" for change in changes["changes"]) or
            _tree_modes(git.text(fresh, "ls-files", "--stage", "-z"))):
            raise RendererFailure("rendered diff does not match edit paths/types")
        for path in changes["touched_files"]:
            validate_edit_path(path, task, policy)
            if (_read_regular(fresh / path, MAX_SOURCE_BYTES + 64 * 1024) != expected[path] or
                (fresh / path).stat().st_mode != original_modes[path] or
                (tree / path).stat().st_mode != original_modes[path]):
                raise RendererFailure("re-applied source bytes/mode disagree")
        if _scope_violations(changes, policy):
            raise ValueError("rendered diff exceeds human-owned scope/line bounds")
        if _source_snapshot(source, git) != source_snapshot:
            raise RendererFailure("trusted source changed during rendering")
        return patch
