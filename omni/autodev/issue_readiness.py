"""
Local Auto Dev issue readiness checker.

Reads a local Markdown/text issue body file and reports whether it contains
the required Auto Dev sections. Deterministic heading text matching only —
no network, no GitHub API, no `gh` CLI, no LLM calls.
"""
from __future__ import annotations

import re
from pathlib import Path

from omni.autodev.config import DEFAULT_REQUIRED_ISSUE_SECTIONS
from omni.autodev.models import AutoDevIssueReadiness

_HEADING_RE = re.compile(r"^#{1,6}\s+(.*)$")
_FENCE_RE = re.compile(r"^```")


def _normalize_heading(text: str) -> str:
    text = text.strip().rstrip(":")
    text = re.sub(r"\s+", " ", text)
    return text.lower()


def _extract_headings(text: str) -> list[str]:
    """Return markdown heading text, ignoring lines inside fenced code blocks."""
    headings = []
    in_fence = False
    for line in text.splitlines():
        stripped = line.strip()
        if _FENCE_RE.match(stripped):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = _HEADING_RE.match(stripped)
        if match:
            headings.append(match.group(1).strip())
    return headings


def check_issue_text(text: str) -> AutoDevIssueReadiness:
    """Check raw issue body text for required Auto Dev sections."""
    alias_to_canonical: dict[str, str] = {}
    for canonical, aliases in DEFAULT_REQUIRED_ISSUE_SECTIONS:
        for alias in aliases:
            alias_to_canonical[_normalize_heading(alias)] = canonical

    found: set[str] = set()
    for heading in _extract_headings(text):
        canonical = alias_to_canonical.get(_normalize_heading(heading))
        if canonical:
            found.add(canonical)

    section_names = [canonical for canonical, _ in DEFAULT_REQUIRED_ISSUE_SECTIONS]
    present = [name for name in section_names if name in found]
    missing = [name for name in section_names if name not in found]

    return AutoDevIssueReadiness(
        verdict="READY" if not missing else "NEEDS_DETAIL",
        present_sections=present,
        missing_sections=missing,
        warnings=[],
    )


def check_issue_file(path: Path) -> AutoDevIssueReadiness:
    """Check a local issue body file for required Auto Dev sections.

    Raises FileNotFoundError with a clear message if the path does not
    exist or is not a regular file.
    """
    if not path.is_file():
        raise FileNotFoundError(f"issue file not found: {path}")
    return check_issue_text(path.read_text(encoding="utf-8"))
