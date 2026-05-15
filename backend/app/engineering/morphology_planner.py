"""
backend/app/engineering/morphology_planner.py

OMNI Morphology Engine — Planner
================================
Converts natural-language mission text into a structured MorphologyPlan.

This is the first deterministic body-plan resolver for OMNI.
It does not call an LLM. It uses pattern scoring so the output is stable,
debuggable, and safe to feed into CAD, KiCad, ROS2, and validators.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Tuple

from backend.app.engineering.design_intent_schema import (
    MorphologyPlan,
    MorphologyConfidence,
    ProjectFamily,
    LocomotionType,
    ScaleClass,
)
from backend.app.knowledge.morphology_pattern_library import (
    PATTERN_KEYWORDS,
    SCALE_KEYWORDS,
    build_pattern,
    get_all_pattern_names,
)


def normalize_text(text: str) -> str:
    """
    Normalize mission text for keyword matching.
    Keeps hyphenated phrases searchable by also making them space-equivalent.
    """
    text = str(text or "").lower()
    text = text.replace("_", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def keyword_matches(text: str, keywords: List[str]) -> List[str]:
    """
    Return all keywords that appear in the normalized text.

    Uses substring matching intentionally because mission text often contains
    phrases like 'six-legged', 'fixed-wing', 'insect-inspired', etc.
    """
    normalized = normalize_text(text)
    matches: List[str] = []

    for keyword in keywords:
        key = normalize_text(keyword)
        if not key:
            continue

        if key in normalized:
            matches.append(keyword)

    return matches


def score_patterns(mission_text: str) -> Dict[str, Dict[str, Any]]:
    """
    Score all morphology patterns against mission text.
    """
    scores: Dict[str, Dict[str, Any]] = {}

    for pattern_name, keywords in PATTERN_KEYWORDS.items():
        matches = keyword_matches(mission_text, keywords)

        scores[pattern_name] = {
            "pattern": pattern_name,
            "score": len(matches),
            "matched_keywords": matches,
        }

    return scores


def choose_best_pattern(
    scores: Dict[str, Dict[str, Any]]
) -> Tuple[str, Dict[str, Any], List[str]]:
    """
    Choose the highest-scoring pattern.

    Returns:
    - winning pattern name
    - winning score record
    - warning list
    """
    warnings: List[str] = []

    if not scores:
        warnings.append("No morphology patterns were available. Falling back to unknown.")
        return "unknown", {"score": 0, "matched_keywords": []}, warnings

    ranked = sorted(
        scores.values(),
        key=lambda item: item.get("score", 0),
        reverse=True,
    )

    winner = ranked[0]
    winner_score = int(winner.get("score", 0))
    winner_name = str(winner.get("pattern", "unknown"))

    if winner_score <= 0:
        warnings.append(
            "No strong morphology keyword match found. Falling back to sensor_module-style generic morphology."
        )
        return "sensor_module", {
            "pattern": "sensor_module",
            "score": 0,
            "matched_keywords": [],
        }, warnings

    tied = [
        item
        for item in ranked
        if int(item.get("score", 0)) == winner_score and winner_score > 0
    ]

    if len(tied) > 1:
        tied_names = [str(item.get("pattern", "unknown")) for item in tied]
        warnings.append(
            "Multiple morphology patterns tied with the same score: "
            + ", ".join(tied_names)
        )

        # Tie-break priority. More specific morphologies win over generic ones.
        priority = [
            "segmented_insect_robot",
            "fixed_wing_uav",
            "vtol_uav",
            "quadcopter_drone",
            "robot_arm",
            "wheeled_rover",
            "aquatic_robot",
            "humanoid",
            "sensor_module",
        ]

        for preferred in priority:
            for item in tied:
                if item.get("pattern") == preferred:
                    return preferred, item, warnings

    return winner_name, winner, warnings


def infer_confidence(
    winning_score: int,
    warnings: List[str],
    second_best_score: int = 0,
) -> MorphologyConfidence:
    """
    Convert scoring into a confidence label.
    """
    if warnings and "Multiple morphology patterns tied" in " ".join(warnings):
        return MorphologyConfidence.AMBIGUOUS

    if winning_score >= 4 and winning_score >= second_best_score + 2:
        return MorphologyConfidence.HIGH

    if winning_score >= 2:
        return MorphologyConfidence.MEDIUM

    if winning_score == 1:
        return MorphologyConfidence.LOW

    return MorphologyConfidence.LOW


def infer_scale(mission_text: str) -> tuple[ScaleClass, List[str]]:
    """
    Infer physical scale from mission text.
    """
    matched: List[str] = []

    for scale_class, keywords in SCALE_KEYWORDS.items():
        hits = keyword_matches(mission_text, keywords)
        if hits:
            matched.extend(hits)
            return scale_class, matched

    return ScaleClass.UNKNOWN, matched


def add_cross_pattern_warnings(
    plan: MorphologyPlan,
    scores: Dict[str, Dict[str, Any]],
) -> None:
    """
    Add warnings when mission text contains signs of competing morphology.
    """
    active = plan.morphology_id

    competing_hits = []
    for pattern_name, record in scores.items():
        if pattern_name == active:
            continue

        score = int(record.get("score", 0))
        if score > 0:
            competing_hits.append((pattern_name, score, record.get("matched_keywords", [])))

    competing_hits.sort(key=lambda item: item[1], reverse=True)

    if competing_hits:
        top = competing_hits[0]
        plan.warnings.append(
            f"Competing morphology signal detected: {top[0]} "
            f"with keywords {top[2]}."
        )


def enforce_family_specific_safety(plan: MorphologyPlan) -> None:
    """
    Add extra avoid rules for known morphology families.
    """
    if plan.project_family == ProjectFamily.BIO_INSPIRED_GROUND:
        extra_avoid = [
            "MODEL_NAME contains drone",
            "PROJECT_TYPE equals drone",
            "four motor quadcopter layout",
            "rotor arm cross body",
        ]
        for item in extra_avoid:
            if item not in plan.body_plan.avoid_features:
                plan.body_plan.avoid_features.append(item)

    if plan.project_family == ProjectFamily.FIXED_WING_UAV:
        extra_required = [
            "aircraft-style symmetry",
            "wing and tail surfaces",
            "control surface representation",
        ]
        for item in extra_required:
            if item not in plan.body_plan.required_features:
                plan.body_plan.required_features.append(item)

    if plan.project_family == ProjectFamily.QUADCOPTER_DRONE:
        extra_required = [
            "four motor layout",
            "flight controller location",
            "battery tray",
        ]
        for item in extra_required:
            if item not in plan.body_plan.required_features:
                plan.body_plan.required_features.append(item)


def plan_morphology(mission_text: str) -> MorphologyPlan:
    """
    Main public API.

    Converts mission text into a MorphologyPlan.
    """
    mission_text = str(mission_text or "")

    scores = score_patterns(mission_text)
    ranked = sorted(
        scores.values(),
        key=lambda item: item.get("score", 0),
        reverse=True,
    )

    winner_name, winner_record, warnings = choose_best_pattern(scores)

    try:
        plan = build_pattern(winner_name)
    except Exception:
        # Fallback should almost never happen unless the registry is broken.
        plan = build_pattern("sensor_module")
        warnings.append(
            f"Requested pattern '{winner_name}' was not registered. Used sensor_module fallback."
        )

    scale, scale_keywords = infer_scale(mission_text)
    plan.scale = scale

    winning_score = int(winner_record.get("score", 0))
    second_best_score = 0
    if len(ranked) > 1:
        second_best_score = int(ranked[1].get("score", 0))

    plan.confidence = infer_confidence(
        winning_score=winning_score,
        warnings=warnings,
        second_best_score=second_best_score,
    )

    plan.matched_pattern = winner_name
    plan.matched_keywords = list(winner_record.get("matched_keywords", []))
    plan.warnings.extend(warnings)

    if scale == ScaleClass.UNKNOWN:
        plan.warnings.append(
            "Scale was not explicitly detected. Downstream generators should use conservative default dimensions."
        )
    else:
        plan.matched_keywords.extend(scale_keywords)

    add_cross_pattern_warnings(plan, scores)
    enforce_family_specific_safety(plan)

    return plan


def plan_morphology_dict(mission_text: str) -> Dict[str, Any]:
    """
    Dict wrapper for export_manager and JSON writing.
    Supports both Pydantic v1 and v2.
    """
    plan = plan_morphology(mission_text)

    if hasattr(plan, "model_dump"):
        return plan.model_dump(mode="json")

    return json.loads(plan.json())


def plan_morphology_json(mission_text: str) -> str:
    """
    JSON wrapper for CLI/debug usage.
    """
    return json.dumps(plan_morphology_dict(mission_text), indent=2)


def main() -> None:
    if len(sys.argv) > 1:
        mission_text = " ".join(sys.argv[1:])
    else:
        mission_text = sys.stdin.read()

    print(plan_morphology_json(mission_text))


if __name__ == "__main__":
    main()