"""
OMNI Biomorphic Trait Library.

This module loads structured creature-inspired engineering traits from
knowledge/biomimicry/*.json and exposes deterministic lookup helpers for the
CAD Morphology Planner.

Design purpose:
- Do not hardcode 100+ animals inside the planner.
- Keep creature knowledge data-driven.
- Convert animal inspiration into engineering-relevant morphology traits.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def _repo_root() -> Path:
    """
    Resolve repo root from backend/app/cad/biomorphic_trait_library.py.

    Expected location:
        <repo>/backend/app/cad/biomorphic_trait_library.py
    """
    return Path(__file__).resolve().parents[3]


def _knowledge_dir() -> Path:
    return _repo_root() / "knowledge" / "biomimicry"


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_creature_traits() -> Dict[str, Any]:
    """Load the full creature trait database."""
    return _load_json(_knowledge_dir() / "creature_traits.json")


def load_morphology_archetypes() -> Dict[str, Any]:
    """Load morphology archetype definitions."""
    return _load_json(_knowledge_dir() / "morphology_archetypes.json")


def all_creature_records() -> Dict[str, Dict[str, Any]]:
    data = load_creature_traits()
    creatures = data.get("creatures", {})
    return creatures if isinstance(creatures, dict) else {}


def normalize_creature_name(value: str) -> str:
    return str(value or "").lower().strip().replace("-", "_").replace(" ", "_")


def find_creature_record(query: str) -> Optional[Dict[str, Any]]:
    """
    Find the first creature record mentioned in a prompt.

    Matching uses both canonical creature names and aliases.
    """
    text = str(query or "").lower()
    if not text:
        return None

    for creature_name, record in all_creature_records().items():
        canonical = str(creature_name).lower().replace("_", " ")

        candidates = {canonical, str(creature_name).lower()}
        for alias in record.get("aliases", []) or []:
            candidates.add(str(alias).lower())

        for candidate in candidates:
            if candidate and candidate in text:
                result = dict(record)
                result["creature"] = creature_name
                return result

    return None


def find_all_creature_records(query: str) -> List[Dict[str, Any]]:
    """
    Return all creature records mentioned in a prompt.
    Useful later for hybrid creatures like 'gecko-dragonfly robot'.
    """
    text = str(query or "").lower()
    matches: List[Dict[str, Any]] = []

    for creature_name, record in all_creature_records().items():
        candidates = {str(creature_name).lower().replace("_", " "), str(creature_name).lower()}
        for alias in record.get("aliases", []) or []:
            candidates.add(str(alias).lower())

        if any(candidate and candidate in text for candidate in candidates):
            result = dict(record)
            result["creature"] = creature_name
            matches.append(result)

    return matches


def creature_record_to_morphology_hints(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert a creature record into planner-friendly morphology hints.

    This does not create final CAD geometry. It creates a normalized contract
    that the morphology planner can merge into MorphologySpec.
    """
    if not isinstance(record, dict):
        return {}

    locomotion = record.get("locomotion", {}) or {}

    return {
        "source_creature": record.get("creature", ""),
        "creature_class": record.get("creature_class", ""),
        "morphology_archetype": record.get("morphology_archetype", ""),
        "robot_family": record.get("robot_family", ""),
        "body_posture": record.get("body_posture", ""),
        "symmetry": record.get("symmetry", "bilateral"),
        "appendage_count": int(record.get("appendage_count", 0) or 0),
        "body_segments": list(record.get("body_segments", []) or []),
        "locomotion_primary": locomotion.get("primary", ""),
        "locomotion_secondary": list(locomotion.get("secondary", []) or []),
        "terrain": list(locomotion.get("terrain", []) or []),
        "specialized_features": list(record.get("specialized_features", []) or []),
        "cad_rules": list(record.get("cad_rules", []) or []),
        "hard_negatives": list(record.get("hard_negatives", []) or []),
    }


def infer_biomorphic_hints(prompt: str) -> Dict[str, Any]:
    """
    Detect creature inspiration from prompt and return normalized hints.
    Empty dict means no known creature was detected.
    """
    record = find_creature_record(prompt)
    if not record:
        return {}

    hints = creature_record_to_morphology_hints(record)
    hints["matched"] = True
    return hints


def describe_known_creatures() -> List[str]:
    """Return sorted creature keys known to the library."""
    return sorted(all_creature_records().keys())


if __name__ == "__main__":
    print("Known creatures:")
    for name in describe_known_creatures():
        print(f"- {name}")

    examples = [
        "Design a gecko-inspired wall-climbing inspection robot",
        "Design a snake-like pipe inspection robot",
        "Design a manta-ray-inspired underwater exploration robot",
        "Design a wolf-inspired quadruped scout robot",
    ]

    print("\nExample detections:")
    for example in examples:
        print("\nMISSION:", example)
        print(json.dumps(infer_biomorphic_hints(example), indent=2))
