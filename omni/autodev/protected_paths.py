"""
Local Auto Dev protected path policy.

Defines which repo-relative paths Auto Dev must not touch without
dedicated human review, and why. This module only matches a single path
string against glob patterns — it does not scan a git diff, enumerate
changed files, or enforce anything against a real change set. That is a
future layer.

This module also owns OMNI's one shared repository-relative path contract:
`normalize_repo_relative_path` (strict — fails closed on malformed,
absolute, drive-qualified, UNC, or repository-escaping input) and
`spec_matches` (literal/prefix/glob scope matching). `omni/autodev/packets.py`
reuses both rather than re-implementing path handling, per
`docs/agentic/packet_contracts.md`.
"""
from __future__ import annotations

import fnmatch
import posixpath

from omni.autodev.config import DEFAULT_PROTECTED_PATH_RULES
from omni.autodev.models import AutoDevProtectedPathRule

# fnmatch's special characters. A scope/policy specification containing any
# of these is treated as a glob; one containing none of these is treated as
# a literal path or directory prefix. Shared with packets.py, which also
# uses this set to reject glob metacharacters in RepairPacket.allowed_repair_scope
# (that field must be concrete paths only, not patterns).
GLOB_METACHARACTERS = "*?[]"


def default_protected_path_rules() -> list[AutoDevProtectedPathRule]:
    return [
        AutoDevProtectedPathRule(pattern=pattern, reason=reason)
        for pattern, reason in DEFAULT_PROTECTED_PATH_RULES
    ]


def normalize_repo_relative_path(path: str) -> str:
    """Normalize `path` to a repository-relative POSIX path.

    This is the strict contract for a *concrete candidate path* (a path
    something would actually touch), not for a scope specification that
    may contain glob metacharacters — see `spec_matches` for those.

    Raises `ValueError` — never returns a fallback value — for input that
    is:

    - not a string, or empty/whitespace-only
    - `.` (resolves to the repository root itself)
    - an absolute POSIX path, a UNC path, or any path starting with `/`
      after backslash normalization (a leading `/` is unsafe regardless of
      whether it came from `/foo`, `//server/share/foo`, or `///`)
    - a Windows drive-qualified path (`C:\\...`, `C:/...`)
    - a path containing a literal `..` component anywhere (e.g.
      `../x`, `a/../../b`) — rejected outright, not just when it would
      net-escape the repository root after normalization, so this check
      alone also makes repository-escaping structurally impossible

    Backslashes are normalized to `/`, and redundant `./` segments,
    repeated separators, and a trailing separator are collapsed via
    `posixpath.normpath`.

    Callers enforcing a path-based policy (protected paths, repair scope)
    must fail closed: catch nothing here and let `ValueError` propagate,
    rather than treating an invalid path as an ordinary non-match.
    """
    if not isinstance(path, str) or not path.strip():
        raise ValueError(f"path must be a non-empty string: {path!r}")

    candidate = path.strip().replace("\\", "/")

    if len(candidate) >= 2 and candidate[1] == ":" and candidate[0].isalpha():
        raise ValueError(f"drive-qualified paths are not allowed: {path!r}")

    if candidate.startswith("/"):
        raise ValueError(f"absolute or UNC-style paths are not allowed: {path!r}")

    if ".." in candidate.split("/"):
        raise ValueError(f"path must not contain a '..' component: {path!r}")

    normalized = posixpath.normpath(candidate)

    if normalized == ".":
        raise ValueError(f"path must not resolve to the repository root itself: {path!r}")

    return normalized


def _is_glob_spec(spec: str) -> bool:
    return any(ch in spec for ch in GLOB_METACHARACTERS)


def spec_matches(spec: str, candidate: str) -> bool:
    """Does `candidate` (an already-normalized repo-relative POSIX path)
    fall under scope/policy specification `spec`?

    `spec` may be:

    - a literal repository-relative path — matches only that exact path
    - a repository-relative directory prefix — matches that path and
      everything under it (`omni/autodev` matches `omni/autodev/x.py` but
      not `omni/autodev_extra/x.py`)
    - a glob specification containing `* ? [ ]` — matched with `fnmatchcase`.
      A glob ending in `/**` also matches its own bare directory root
      (`frontend/**` matches `frontend` and `frontend/`, not just files
      under it), since `fnmatch` alone has no trailing segment for `**`
      to consume against a bare directory path.

    `spec` is normalized the same way as a candidate path (backslashes,
    redundant separators) but is *not* run through
    `normalize_repo_relative_path` — a specification is allowed to be a
    prefix or contain glob metacharacters, which that strict contract
    exists specifically to reject for concrete paths.

    Matching is case-sensitive on every host: these are repository-relative
    POSIX names, not native filesystem lookups. Host case normalization must
    not change a deterministic scope verdict.
    """
    normalized_spec = posixpath.normpath(spec.strip().replace("\\", "/"))
    if _is_glob_spec(normalized_spec):
        if fnmatch.fnmatchcase(candidate, normalized_spec):
            return True
        if normalized_spec.endswith("/**") and candidate == normalized_spec[: -len("/**")]:
            return True
        return False
    return candidate == normalized_spec or candidate.startswith(normalized_spec + "/")


def match_protected_path(
    path: str,
    rules: list[AutoDevProtectedPathRule] | None = None,
) -> AutoDevProtectedPathRule | None:
    """Return the first protected path rule whose pattern matches `path`.

    `path` is normalized via `normalize_repo_relative_path`, which raises
    `ValueError` for empty, malformed, absolute, drive-qualified, UNC, or
    repository-escaping input — this function fails closed rather than
    treating invalid input as an ordinary unprotected `None`. A caller
    enforcing this policy must not catch that error and continue as if the
    path were unprotected.

    Returns `None` if the path is valid but does not match any rule.
    """
    normalized = normalize_repo_relative_path(path)
    candidates = default_protected_path_rules() if rules is None else rules
    for rule in candidates:
        if spec_matches(rule.pattern, normalized):
            return rule
    return None
