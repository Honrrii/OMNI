"""
core/formatters.py
==================
Single source of truth for all text formatting, name sanitization,
and content normalization across the OMNI system.

Previously, sanitize_legacy_names() was duplicated in:
  - supervisor.py
  - critic_agent.py
  - validator_agent.py
  - artifact_synthesizer.py
  - main.py

All of those now import from here.
"""

from __future__ import annotations

import re
from typing import Any


# ---------------------------------------------------------------------------
# Legacy name map — every Marvel/Avengers reference to its OMNI equivalent.
# Add entries here if new ones surface; do NOT add one-off replacements
# anywhere else in the codebase.
# ---------------------------------------------------------------------------
_LEGACY_NAME_MAP: dict[str, str] = {
    "Reed Richards": "Omni",
    "Tony Stark": "Sky",
    "Bruce Banner": "Isy",
    "Hank Pym": "Oli",
    "Ultron": "Pluto",
    "Vision": "QaZ",
    "Shuri": "Korva",
    "AI Avengers": "OMNI",
    "Marvel Geniuses HQ": "OMNI Command",
    "Marvel Geniuses": "OMNI",
    # Phrase-level replacements
    "Reed's Final Strategic Recommendation": "Omni's Final Strategic Recommendation",
    "READY FOR VISION VALIDATION": "READY FOR QaZ VALIDATION",
    "Vision engineering validation": "QaZ engineering validation",
    "Use Ultron's critique": "Use Pluto's critique",
    # Short first-name replacements — keep these LAST so they don't
    # interfere with the longer full-name replacements above.
    "Tony": "Sky",
    "Bruce": "Isy",
    "Hank": "Oli",
    "Reed": "Omni",
}


def sanitize_legacy_names(text: str) -> str:
    """
    Replace all Marvel/Avengers naming with OMNI-native agent names.

    Works only on plain strings. For nested structures use
    sanitize_payload().
    """
    if not isinstance(text, str):
        return text

    result = text
    for old, new in _LEGACY_NAME_MAP.items():
        result = result.replace(old, new)
    return result


def sanitize_payload(payload: Any) -> Any:
    """
    Recursively sanitize legacy names inside any nested structure
    including dict keys, dict values, lists, and plain strings.
    """
    if isinstance(payload, str):
        return sanitize_legacy_names(payload)

    if isinstance(payload, list):
        return [sanitize_payload(item) for item in payload]

    if isinstance(payload, dict):
        return {
            sanitize_legacy_names(key) if isinstance(key, str) else key: sanitize_payload(value)
            for key, value in payload.items()
        }

    return payload


# ---------------------------------------------------------------------------
# Context compaction — keeps prompts from blowing up after large agent outputs.
# ---------------------------------------------------------------------------

def compact_context(text: str, limit: int = 9000) -> str:
    """
    Truncates long context blocks, keeping the beginning and end.

    The beginning preserves mission intent; the end preserves the most
    recent agent conclusions. The middle (often verbose elaboration) is
    dropped with a visible marker.
    """
    if not isinstance(text, str):
        text = str(text)

    if len(text) <= limit:
        return text

    head = text[: limit // 2]
    tail = text[-limit // 2 :]
    return (
        f"{head}\n\n"
        f"...[context compacted — {len(text) - limit} chars removed]...\n\n"
        f"{tail}"
    )


# ---------------------------------------------------------------------------
# Safe folder/file name helpers.
# ---------------------------------------------------------------------------

def safe_folder_name(text: str, max_len: int = 80) -> str:
    """
    Convert arbitrary text into a safe file-system folder name.
    """
    value = str(text or "omni_mission").lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value[:max_len] or "omni_mission"


def safe_agent_name(text: str) -> str:
    """
    Convert an agent name into a safe snake_case identifier.
    Example: "Agent Name" → "agent_name"
    """
    return safe_folder_name(text)