"""
OMNI Hybrid Morphology Intent Resolver.

This module separates:
1. The machine/platform the user asked for.
2. The animal/creature traits the user wants to borrow.

This prevents prompts like "manta-ray-inspired drone" from becoming an
underwater manta robot by default. Explicit platform intent should usually win.
"""

from __future__ import annotations

from typing import Any, Dict, List
import re


try:
    from .biomorphic_trait_library import (
        find_all_creature_records,
        creature_record_to_morphology_hints,
    )
except ImportError:
    from biomorphic_trait_library import (
        find_all_creature_records,
        creature_record_to_morphology_hints,
    )


PLATFORM_KEYWORDS = {
    "aerial_drone": [
        "drone", "uav", "quadcopter", "hexacopter", "multirotor",
        "aerial robot", "flying robot", "reconnaissance drone",
    ],
    "rover": [
        "rover", "ugv", "ground robot", "wheeled robot", "tracked robot",
        "crawler rover", "inspection rover",
    ],
    "aquatic_robot": [
        "underwater", "aquatic", "submarine", "auv", "rov",
        "marine", "shallow water", "swimming robot",
    ],
    "legged_robot": [
        "walker", "walking robot", "legged robot", "quadruped",
        "hexapod", "crawler", "terrain walker",
    ],
    "robot_arm": [
        "robot arm", "manipulator", "gripper", "end effector",
    ],
    "surface_boat": [
        "boat", "surface vessel", "water surface", "floating robot",
    ],
}


def _term_matches(text: str, term: str) -> bool:
    """
    Match platform terms without letting short acronyms leak into longer words.

    Example:
        "rov" should match "ROV" but not the "rov" inside "rover".
    """
    term = str(term or "").lower().strip()
    if not term:
        return False

    if term.replace("_", "").replace("-", "").isalnum() and " " not in term:
        pattern = r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])"
        return re.search(pattern, text) is not None

    return term in text


def _contains_any(text: str, terms: List[str]) -> bool:
    return any(_term_matches(text, term) for term in terms)


def detect_platform_intent(prompt: str) -> Dict[str, Any]:
    text = str(prompt or "").lower()

    matches = []
    for platform, terms in PLATFORM_KEYWORDS.items():
        if _contains_any(text, terms):
            matches.append(platform)

    if not matches:
        return {
            "requested_platform": "",
            "resolved_platform": "",
            "platform_priority": "no_explicit_platform",
            "all_matches": [],
        }

    # Priority: if the user says drone, rover, underwater, etc., preserve it.
    priority_order = [
        "aerial_drone",
        "rover",
        "aquatic_robot",
        "legged_robot",
        "robot_arm",
        "surface_boat",
    ]

    for candidate in priority_order:
        if candidate in matches:
            return {
                "requested_platform": candidate,
                "resolved_platform": candidate,
                "platform_priority": "explicit_user_request",
                "all_matches": matches,
            }

    return {
        "requested_platform": matches[0],
        "resolved_platform": matches[0],
        "platform_priority": "explicit_user_request",
        "all_matches": matches,
    }


def _unique(items: List[Any]) -> List[Any]:
    result = []
    seen = set()

    for item in items:
        key = str(item)
        if key not in seen:
            seen.add(key)
            result.append(item)

    return result


def _merge_trait_hints(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not records:
        return {}

    hint_records = [creature_record_to_morphology_hints(record) for record in records]
    primary = dict(hint_records[0])

    all_features: List[str] = []
    all_rules: List[str] = []
    all_hard_negatives: List[str] = []
    all_body_segments: List[str] = []
    all_terrain: List[str] = []
    all_secondary_modes: List[str] = []

    trait_sources = []

    for hints in hint_records:
        creature = hints.get("source_creature", "")

        features = list(hints.get("specialized_features", []) or [])
        rules = list(hints.get("cad_rules", []) or [])

        all_features.extend(features)
        all_rules.extend(rules)
        all_hard_negatives.extend(list(hints.get("hard_negatives", []) or []))
        all_body_segments.extend(list(hints.get("body_segments", []) or []))
        all_terrain.extend(list(hints.get("terrain", []) or []))
        all_secondary_modes.extend(list(hints.get("locomotion_secondary", []) or []))

        trait_sources.append({
            "source_creature": creature,
            "creature_class": hints.get("creature_class", ""),
            "morphology_archetype": hints.get("morphology_archetype", ""),
            "robot_family": hints.get("robot_family", ""),
            "traits_used": features,
            "cad_rules": rules,
        })

    primary["source_creature"] = "_".join(
        [str(h.get("source_creature", "")) for h in hint_records if h.get("source_creature")]
    )
    primary["specialized_features"] = _unique(all_features)
    primary["cad_rules"] = _unique(all_rules)
    primary["hard_negatives"] = _unique(all_hard_negatives)
    primary["body_segments"] = _unique(all_body_segments)
    primary["terrain"] = _unique(all_terrain)
    primary["locomotion_secondary"] = _unique(all_secondary_modes)
    primary["trait_sources"] = trait_sources

    return primary


def _platform_adapted_family(platform: str, merged_hints: Dict[str, Any]) -> str:
    if platform == "aerial_drone":
        return "hybrid_biomorphic_drone"

    if platform == "rover":
        return "biomorphic_rover"

    if platform == "aquatic_robot":
        # If user asked for underwater and animal is aquatic, keep aquatic form.
        return merged_hints.get("robot_family") or "biomorphic_underwater_robot"

    if platform == "legged_robot":
        return merged_hints.get("robot_family") or "hybrid_biomorphic_walker"

    if platform == "robot_arm":
        return "biomorphic_manipulator"

    if platform == "surface_boat":
        return "biomorphic_surface_vessel"

    return merged_hints.get("robot_family") or "hybrid_biomorphic_platform"


def _platform_body_posture(platform: str, fallback: str) -> str:
    if platform == "aerial_drone":
        return "aerial"
    if platform == "rover":
        return "low_slung"
    if platform == "aquatic_robot":
        return "aquatic"
    if platform == "legged_robot":
        return fallback or "standing"
    if platform == "robot_arm":
        return "mounted"
    if platform == "surface_boat":
        return "aquatic"
    return fallback or "standing"


def _platform_body_segments(platform: str, merged_hints: Dict[str, Any]) -> List[str]:
    if platform == "aerial_drone":
        return ["central_fuselage", "left_trait_surface", "right_trait_surface", "tail_stabilizer", "sensor_pod"]

    if platform == "rover":
        return ["low_chassis", "trait_inspired_shell", "front_sensor_head", "rear_stabilizer"]

    if platform == "robot_arm":
        return ["base", "shoulder_module", "arm_link", "trait_inspired_end_effector"]

    if platform == "surface_boat":
        return ["central_hull", "left_stabilizer", "right_stabilizer", "sensor_mast"]

    return list(merged_hints.get("body_segments", []) or ["central_body"])


def _platform_appendage_count(platform: str, merged_hints: Dict[str, Any]) -> int:
    if platform == "aerial_drone":
        # Fins/wings/stabilizer surfaces, not legs.
        return 2

    if platform == "rover":
        # Keep rover body primary; animal traits become shell/stabilizers/pads.
        return 0

    if platform == "robot_arm":
        return 1

    if platform == "surface_boat":
        return 2

    return int(merged_hints.get("appendage_count", 0) or 0)


def adapt_traits_to_platform(
    platform_intent: Dict[str, Any],
    merged_hints: Dict[str, Any],
) -> Dict[str, Any]:
    platform = platform_intent.get("resolved_platform", "")

    if not platform:
        merged_hints["intent_mode"] = "creature_primary"
        merged_hints["hybridization_strategy"] = {
            "mode": "creature_primary",
            "base_platform_locked": False,
            "trait_blend_count": len(merged_hints.get("trait_sources", [])) or 1,
        }
        return merged_hints

    adapted = dict(merged_hints)

    adapted["robot_family"] = _platform_adapted_family(platform, merged_hints)
    adapted["body_posture"] = _platform_body_posture(platform, merged_hints.get("body_posture", ""))
    adapted["body_segments"] = _platform_body_segments(platform, merged_hints)
    adapted["appendage_count"] = _platform_appendage_count(platform, merged_hints)

    source_creature = adapted.get("source_creature", "creature")
    adapted["morphology_archetype"] = f"{platform}_with_{source_creature}_traits"

    adapted["intent_mode"] = "platform_primary_trait_adapted"
    adapted["platform_intent"] = platform_intent
    adapted["hybridization_strategy"] = {
        "mode": "platform_primary_trait_adapted",
        "base_platform_locked": True,
        "trait_blend_count": len(adapted.get("trait_sources", [])) or 1,
    }

    adapted.setdefault("hard_negatives", [])
    adapted["hard_negatives"] = _unique(
        list(adapted.get("hard_negatives", []) or [])
        + [
            "do not replace explicit user platform with pure animal body plan",
            "do not ignore requested machine type",
            "do not create unrelated generic robot template",
        ]
    )

    adapted.setdefault("cad_rules", [])
    adapted["cad_rules"] = _unique(
        list(adapted.get("cad_rules", []) or [])
        + [
            f"Preserve explicit platform intent: {platform}.",
            "Translate creature traits into mechanically useful platform features.",
            "Use animal traits as design modifiers, not mandatory literal anatomy.",
        ]
    )

    return adapted


def resolve_morphology_intent(prompt: str) -> Dict[str, Any]:
    """
    Resolve platform + creature trait intent.

    Returns:
        {
          "matched": bool,
          "platform_intent": {...},
          "trait_sources": [...],
          "morphology_hints": {...}
        }
    """
    text = str(prompt or "").lower()

    platform_intent = detect_platform_intent(text)
    creature_records = find_all_creature_records(text)

    if not creature_records:
        return {
            "matched": False,
            "platform_intent": platform_intent,
            "trait_sources": [],
            "morphology_hints": {},
        }

    merged = _merge_trait_hints(creature_records)
    adapted = adapt_traits_to_platform(platform_intent, merged)

    adapted["matched"] = True
    adapted["platform_intent"] = platform_intent

    return {
        "matched": True,
        "platform_intent": platform_intent,
        "trait_sources": adapted.get("trait_sources", []),
        "morphology_hints": adapted,
    }


if __name__ == "__main__":
    import json

    examples = [
        "Design a manta-ray-inspired underwater exploration robot",
        "Design a manta-ray-inspired drone for indoor reconnaissance",
        "Design a gecko-inspired rover for wall inspection",
        "Design a drone with manta ray fins, dragonfly agility, and crab-like landing legs",
        "Design a rover with turtle armor and gecko adhesive pads",
    ]

    for example in examples:
        print("\nMISSION:", example)
        print(json.dumps(resolve_morphology_intent(example), indent=2))
