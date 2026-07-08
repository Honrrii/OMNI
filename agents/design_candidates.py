"""
Vega structured design candidates — deterministic normalizer and extractor.

No LLM calls. No network calls. No file I/O.
Normalizes raw candidate dicts into stable, schema-compliant objects.
Candidate IDs are positional and deterministic: vega_candidate_1, vega_candidate_2, ...
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List

_ID_PREFIX = "vega_candidate"


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip() or default


def _safe_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(v) for v in value if v is not None]
    return []


def normalize_candidate(raw: Any, index: int) -> Dict[str, Any]:
    """
    Normalize one raw candidate dict into a stable schema object.
    index is 1-based (1, 2, 3, ...).
    """
    if not isinstance(raw, dict):
        raw = {}

    return {
        "id": f"{_ID_PREFIX}_{index}",
        "name": _safe_str(raw.get("name"), f"Design Candidate {index}"),
        "concept": _safe_str(raw.get("concept")),
        "platform": _safe_str(raw.get("platform"), "unknown"),
        "mobility_type": _safe_str(raw.get("mobility_type"), "unknown"),
        "morphology_notes": _safe_str(raw.get("morphology_notes")),
        "key_components": _safe_list(raw.get("key_components")),
        "strengths": _safe_list(raw.get("strengths")),
        "risks": _safe_list(raw.get("risks")),
        "required_validation": _safe_list(raw.get("required_validation")),
        "assumptions": _safe_list(raw.get("assumptions")),
        "recommended": bool(raw.get("recommended", False)),
    }


def normalize_candidates(raw_list: Any) -> List[Dict[str, Any]]:
    """
    Normalize a list of raw candidate dicts.
    Returns a list of stable schema objects with IDs vega_candidate_1, vega_candidate_2, ...
    Non-list input returns an empty list.
    """
    if not isinstance(raw_list, list):
        return []
    return [normalize_candidate(item, i + 1) for i, item in enumerate(raw_list)]


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------

def _extract_from_json_block(text: str) -> List[Any]:
    """Return design_candidates list from the first parseable fenced JSON block."""
    for match in re.finditer(r"```(?:json)?\s*(\{[\s\S]*?\}|\[[\s\S]*?\])\s*```", text):
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            candidates = data.get("design_candidates")
            if isinstance(candidates, list):
                return candidates
        elif isinstance(data, list):
            return data
    return []


def _field_value(section: str, label: str) -> str:
    """
    Extract the value after '- Label:' in a markdown section.
    Captures inline content and any continuation lines before the next bullet or heading.
    """
    pattern = re.compile(
        r"-\s*" + re.escape(label) + r":\s*(.*?)(?=\n\s*-|\n\s*#|$)",
        re.DOTALL | re.IGNORECASE,
    )
    m = pattern.search(section)
    if not m:
        return ""
    return m.group(1).strip()


def _extract_from_markdown(text: str) -> List[Dict[str, Any]]:
    """Parse ### Alternative N sections from a Vega markdown report."""
    sections = re.split(r"(?=###\s+Alternative\s+\d+)", text, flags=re.IGNORECASE)
    candidates = []
    for section in sections:
        if not re.match(r"###\s+Alternative\s+\d+", section.strip(), re.IGNORECASE):
            continue
        raw: Dict[str, Any] = {}

        heading = re.match(r"###\s+(Alternative\s+\d+)", section.strip(), re.IGNORECASE)
        if heading:
            raw["name"] = heading.group(1)

        concept = _field_value(section, "Concept")
        if concept:
            raw["concept"] = concept

        why = _field_value(section, "Why it is interesting")
        if why:
            raw["strengths"] = [why]

        concerns = _field_value(section, "Practical concerns")
        if not concerns:
            concerns = _field_value(section, "Practical concern")
        if concerns:
            raw["risks"] = [concerns]

        candidates.append(raw)
    return candidates


def extract_design_candidates_from_text(text: str) -> List[Dict[str, Any]]:
    """
    Extract structured design candidates from Vega's design report.

    Strategy (in order):
    1. Fenced JSON block containing a 'design_candidates' key.
    2. Markdown '### Alternative N' headings (fallback).

    Result is always passed through normalize_candidates() so IDs are stable.
    """
    if not isinstance(text, str) or not text.strip():
        return []

    raw = _extract_from_json_block(text)
    if raw:
        return normalize_candidates(raw)

    raw = _extract_from_markdown(text)
    return normalize_candidates(raw)
