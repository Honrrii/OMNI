"""
OMNI — Shared deterministic platform intent resolver.

Single source of truth for platform keyword tables, context signals, and the
ranking algorithm that selects a platform from free-form mission text.

Used by:
  - backend.app.cortex.design_evaluator
  - backend.app.mission_graph.builder
  - backend.app.mission_graph.enrichment

No imports from other OMNI modules — safe for anyone to import without cycles.
No LLM calls. No network calls.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Keyword → platform-slug mapping
# Longer keys are more specific and get higher base scores when matched.
# Matching is always word-boundary-aware so "rov" cannot fire inside "rover".
# ---------------------------------------------------------------------------

PLATFORM_KEYWORDS: Dict[str, str] = {
    "manta ray":    "manta-ray-uuv",
    "insect robot": "insect-robot",
    "hexacopter":   "drone-uav",
    "quadcopter":   "drone-uav",
    "hexapod":      "hexapod",
    "quadruped":    "quadruped",
    "robot arm":    "robot-arm",
    "humanoid":     "humanoid",
    "submarine":    "auv",
    "crawler":      "ground-rover",
    "drone":        "drone-uav",
    "uav":          "drone-uav",
    "auv":          "auv",
    "rov":          "rov",
    "rover":        "ground-rover",
    "arm":          "robot-arm",
}

# Context signals used to break ties when multiple platform keywords match.
# Checked via substring so "traverse" matches "traversing", "rotor" matches "rotors".
# Score = keyword_length + 2 × context_hits — higher wins.
PLATFORM_CONTEXT_SIGNALS: Dict[str, Set[str]] = {
    "ground-rover": {
        "rover", "crawler", "crawl", "traverse", "traversing",
        "wheel", "wheeled", "track", "tracked", "magnetic",
        "terrain", "ground", "metal", "surface", "rolling", "floor",
    },
    "drone-uav": {
        "drone", "fly", "flying", "aerial", "propeller", "rotor",
        "airborne", "altitude", "hover", "flight", "sky",
        "quadcopter", "hexacopter", "uav",
    },
    "rov": {
        "underwater", "subsea", "tethered", "ocean", "sea",
        "marine", "submerged", "depth", "remotely operated",
    },
    "auv": {
        "underwater", "subsea", "autonomous", "ocean", "sea",
        "marine", "submerged",
    },
    "manta-ray-uuv": {"underwater", "ray", "ocean", "marine", "fin"},
    "robot-arm": {
        "manipulation", "pick", "place", "grasp", "dof",
        "joint", "wrist", "elbow", "shoulder",
    },
    "hexapod":      {"hexapod", "six", "leg", "legged", "walking"},
    "quadruped":    {"four", "leg", "legged", "walking", "canine"},
    "humanoid":     {"bipedal", "biped", "walk", "human", "upright"},
    "insect-robot": {"insect", "leg", "legged", "walking", "six"},
}


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def word_present(keyword: str, text_lower: str) -> bool:
    """True iff keyword appears as a complete token in text_lower.

    Prevents short keys like 'rov' from firing as substrings of 'rover'.
    """
    return bool(re.search(r"\b" + re.escape(keyword) + r"\b", text_lower))


def rank_platform_matches(text: str) -> List[Tuple[float, str, str]]:
    """Return (score, platform_slug, matched_keyword) for every platform keyword
    found in *text*, sorted by score descending.

    score = keyword_length + 2 × context_signal_hits

    Only the first (longest-keyword) match per platform slug is kept.
    Word-boundary matching prevents substring false-positives.
    """
    lower = text.lower()
    seen: Set[str] = set()
    ranked: List[Tuple[float, str, str]] = []

    for key in sorted(PLATFORM_KEYWORDS, key=len, reverse=True):
        if not word_present(key, lower):
            continue
        slug = PLATFORM_KEYWORDS[key]
        if slug in seen:
            continue
        seen.add(slug)
        ctx_hits = sum(
            1 for sig in PLATFORM_CONTEXT_SIGNALS.get(slug, set())
            if sig in lower
        )
        score = float(len(key) + ctx_hits * 2)
        ranked.append((score, slug, key))

    ranked.sort(key=lambda t: t[0], reverse=True)
    return ranked


# ---------------------------------------------------------------------------
# Public convenience functions
# ---------------------------------------------------------------------------

def resolve_platform_slug(text: str) -> Optional[str]:
    """Return the best-matching platform slug (e.g. 'ground-rover'), or None."""
    ranked = rank_platform_matches(text)
    return ranked[0][1] if ranked else None


def resolve_platform_keyword(text: str) -> str:
    """Return the raw matched keyword (e.g. 'rover'), or '' when nothing matches.

    Used by the mission graph builder to populate graph.platform so that
    the human-readable raw keyword is preserved alongside the normalized slug.
    """
    ranked = rank_platform_matches(text)
    return ranked[0][2] if ranked else ""
