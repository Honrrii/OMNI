"""
Local Auto Dev protected path policy.

Defines which repo-relative paths Auto Dev must not touch without
dedicated human review, and why. This module only matches a single path
string against glob patterns — it does not scan a git diff, enumerate
changed files, or enforce anything against a real change set. That is a
future layer.
"""
from __future__ import annotations

import fnmatch
import posixpath

from omni.autodev.config import DEFAULT_PROTECTED_PATH_RULES
from omni.autodev.models import AutoDevProtectedPathRule


def default_protected_path_rules() -> list[AutoDevProtectedPathRule]:
    return [
        AutoDevProtectedPathRule(pattern=pattern, reason=reason)
        for pattern, reason in DEFAULT_PROTECTED_PATH_RULES
    ]


def _normalize(path: str) -> str:
    return posixpath.normpath(path.replace("\\", "/"))


def match_protected_path(
    path: str,
    rules: list[AutoDevProtectedPathRule] | None = None,
) -> AutoDevProtectedPathRule | None:
    """Return the first protected path rule whose pattern matches `path`.

    `path` is treated as a repo-relative path (leading "./" and backslashes
    are normalized away). Returns None if no rule matches.
    """
    candidates = default_protected_path_rules() if rules is None else rules
    normalized = _normalize(path)
    for rule in candidates:
        if fnmatch.fnmatch(normalized, rule.pattern):
            return rule
    return None
