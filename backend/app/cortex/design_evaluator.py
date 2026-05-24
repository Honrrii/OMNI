"""
OMNI Cortex Phase 10A — Design Understanding Evaluator.

Deterministic, no LLM calls, no network calls.

Given a mission text plus optional graph, graph review, and vision prediction,
returns a DesignUnderstandingReport that explains how well the generated design
matches the mission intent.

Vision predictions from generic classifiers (e.g. Fashion-MNIST) are treated as
weak signals, not ground truth.  When a generic label conflicts with mission /
graph evidence, a mismatch is recorded explaining that the classifier is not
domain-grounded.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

from pydantic import BaseModel, Field

from backend.app.mission_graph.schemas import MissionKnowledgeGraph
from backend.app.mission_graph.reviewer import MissionGraphReview


# ---------------------------------------------------------------------------
# Internal keyword tables
# ---------------------------------------------------------------------------

# Longest-match first (sorted at call-time); mirrors enrichment._PLATFORM_ALIASES.
_PLATFORM_KEYWORDS: Dict[str, str] = {
    "manta ray":    "manta-ray-uuv",
    "insect robot": "insect-robot",
    "hexacopter":   "drone-uav",
    "quadcopter":   "drone-uav",
    "hexapod":      "hexapod",
    "quadruped":    "quadruped",
    "robot arm":    "robot-arm",
    "humanoid":     "humanoid",
    "submarine":    "auv",
    "drone":        "drone-uav",
    "uav":          "drone-uav",
    "auv":          "auv",
    "rov":          "rov",
    "rover":        "ground-rover",
    "arm":          "robot-arm",
}

_DOMAIN_SIGNAL_WORDS: Set[str] = {
    "ros2", "ros", "robotic", "robot",
    "drone", "uav", "hexacopter", "quadcopter",
    "rover", "autonomous", "autonomy",
    "lidar", "imu", "camera", "sensor",
    "motor", "servo", "actuator",
    "pcb", "kicad", "electronics",
    "fusion360", "cad", "stl", "step",
    "simulation", "gazebo", "rviz",
    "arm", "gripper", "manipulator",
}

# Labels that indicate a generic, non-domain-grounded classifier.
# Includes all Fashion-MNIST class names and common non-engineering labels.
_GENERIC_CLASSIFIER_LABELS: Set[str] = {
    "t-shirt/top", "t-shirt", "top",
    "trouser", "trousers",
    "pullover", "dress", "coat",
    "sandal", "shirt", "sneaker",
    "bag", "ankle boot", "ankle-boot",
    "notebook", "envelope", "container",
    "packet", "chest", "case",
    "briefcase", "backpack",
}


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class VisionPrediction(BaseModel):
    """A single prediction from any vision classifier."""

    label: str
    confidence: float = Field(ge=0.0, le=1.0)
    model_name: str = ""
    # True only for classifiers explicitly trained on engineering / CAD imagery.
    is_domain_grounded: bool = False


class DesignUnderstandingReport(BaseModel):
    """
    Deterministic evaluation of whether the generated design matches
    the mission intent.
    """

    intended_platform: Optional[str] = None
    observed_platform_signals: List[str] = Field(default_factory=list)
    visual_prediction: Optional[VisionPrediction] = None
    semantic_match_score: float = Field(ge=0.0, le=1.0)
    strengths: List[str] = Field(default_factory=list)
    mismatches: List[str] = Field(default_factory=list)
    next_design_actions: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_platform(text: str) -> Optional[str]:
    """Return the platform slug for the first keyword found (longest match first)."""
    lower = text.lower()
    for key in sorted(_PLATFORM_KEYWORDS, key=len, reverse=True):
        if key in lower:
            return _PLATFORM_KEYWORDS[key]
    return None


def _extract_domain_signals(text: str) -> List[str]:
    lower = text.lower()
    return sorted({w for w in _DOMAIN_SIGNAL_WORDS if w in lower})


def _is_generic_label(label: str) -> bool:
    return label.strip().lower() in _GENERIC_CLASSIFIER_LABELS


def _label_overlaps_mission(label: str, mission_text: str) -> bool:
    """Return True if any word in the label appears in the mission text."""
    stopwords = {"", "a", "an", "the", "of", "in", "on"}
    label_words = set(re.split(r"\W+", label.lower())) - stopwords
    mission_words = set(re.split(r"\W+", mission_text.lower()))
    return bool(label_words & mission_words)


def _compute_coverage_score(graph_review: MissionGraphReview) -> Optional[float]:
    """Aggregate relationship-coverage ratio across component, ROS2, and CAD axes."""
    ratios: List[float] = []
    comp = graph_review.component_coverage
    ros2 = graph_review.ros2_coverage
    morph = graph_review.morphology_cad_coverage

    if comp.total > 0:
        ratios.append(
            (comp.with_power_rail_id + comp.with_data_bus_id + comp.with_body_region_id)
            / (comp.total * 3)
        )
    if ros2.total_nodes > 0:
        ratios.append(ros2.nodes_with_component_ids / ros2.total_nodes)
    if morph.total_cad_features > 0:
        ratios.append(morph.cad_features_with_body_region_id / morph.total_cad_features)

    if not ratios:
        return None
    return sum(ratios) / len(ratios)


# ---------------------------------------------------------------------------
# Public evaluator
# ---------------------------------------------------------------------------

def evaluate_design_understanding(
    mission_text: str,
    graph: Optional[MissionKnowledgeGraph] = None,
    graph_review: Optional[MissionGraphReview] = None,
    vision_prediction: Optional[VisionPrediction] = None,
) -> DesignUnderstandingReport:
    """
    Return a DesignUnderstandingReport by cross-referencing mission intent,
    graph content, graph review coverage, and an optional vision prediction.

    Scoring weights:
      - Platform alignment   35 %
      - Structural richness  30 %  (only if graph provided)
      - Coverage quality     25 %  (only if graph_review provided)
      - Vision alignment     10 %  (only if vision_prediction provided)

    Weights are renormalised so the total always sums to 1.0.
    """
    strengths: List[str] = []
    mismatches: List[str] = []
    next_design_actions: List[str] = []
    observed_platform_signals: List[str] = []

    # Accumulate weighted sub-scores: (score, weight)
    sub_scores: List[Tuple[float, float]] = []

    # ── 1. Intended platform from mission text ────────────────────────────────
    intended_platform = _extract_platform(mission_text)

    if intended_platform:
        strengths.append(
            f"Mission text clearly identifies platform: '{intended_platform}'."
        )
    else:
        mismatches.append(
            "No known platform could be identified in the mission text."
        )
        next_design_actions.append(
            "Add explicit platform keywords (rover, drone, arm, hexapod, …) "
            "to the mission text."
        )

    # ── 2. Graph-based signals ────────────────────────────────────────────────
    graph_platform_normalized: Optional[str] = None
    graph_component_count = 0
    graph_node_count = 0
    graph_morphology_count = 0

    if graph is not None:
        graph_platform_normalized = graph.platform_normalized or None
        graph_component_count = len(graph.components)
        graph_node_count = len(graph.ros2_nodes)
        graph_morphology_count = len(graph.morphology)

        if graph_platform_normalized:
            observed_platform_signals.append(
                f"graph.platform_normalized = '{graph_platform_normalized}'"
            )
        if graph.platform:
            observed_platform_signals.append(f"graph.platform = '{graph.platform}'")

        # Collect structural keyword hits
        text_sources = (
            [c.name.lower() for c in graph.components]
            + [n.name.lower() for n in graph.ros2_nodes]
            + [m.description.lower() for m in graph.morphology]
        )
        for word in _DOMAIN_SIGNAL_WORDS:
            if any(word in src for src in text_sources):
                sig = f"'{word}' found in graph structure"
                if sig not in observed_platform_signals:
                    observed_platform_signals.append(sig)

        # Platform alignment sub-score
        if intended_platform and graph_platform_normalized:
            if intended_platform == graph_platform_normalized:
                strengths.append(
                    f"Graph platform '{graph_platform_normalized}' matches mission intent."
                )
                sub_scores.append((1.0, 0.35))
            else:
                mismatches.append(
                    f"Graph platform '{graph_platform_normalized}' does not match "
                    f"mission platform '{intended_platform}'."
                )
                next_design_actions.append(
                    f"Verify the graph was built from the correct mission; "
                    f"expected '{intended_platform}', got '{graph_platform_normalized}'."
                )
                sub_scores.append((0.2, 0.35))
        elif intended_platform:
            mismatches.append(
                f"Mission expects platform '{intended_platform}' but the graph has "
                "no normalized platform (enrichment may not have run)."
            )
            next_design_actions.append("Run enrich_graph() before building the review.")
            sub_scores.append((0.4, 0.35))
        else:
            sub_scores.append((0.1, 0.35))

        # Structural richness sub-score
        richness = min(1.0, (
            min(graph_component_count / 5, 1.0) * 0.40
            + min(graph_node_count / 3, 1.0) * 0.35
            + min(graph_morphology_count / 2, 1.0) * 0.25
        ))
        sub_scores.append((richness, 0.30))

        if graph_component_count > 0:
            strengths.append(
                f"Graph contains {graph_component_count} component(s)."
            )
        else:
            mismatches.append("Graph has no components — design may be incomplete.")
            next_design_actions.append(
                "Add hardware components to the mission graph."
            )

        if graph_node_count > 0:
            strengths.append(f"Graph contains {graph_node_count} ROS2 node(s).")
        if graph_morphology_count > 0:
            strengths.append(
                f"Graph has {graph_morphology_count} morphology description(s)."
            )

    else:
        # No graph — platform sub-score based on mission text only
        plat_score = 0.4 if intended_platform else 0.1
        sub_scores.append((plat_score, 0.35))

    # ── 3. Graph review coverage quality ─────────────────────────────────────
    if graph_review is not None:
        coverage_score = _compute_coverage_score(graph_review)
        if coverage_score is not None:
            sub_scores.append((coverage_score, 0.25))
            if coverage_score >= 0.70:
                strengths.append(
                    f"Graph review coverage is strong ({coverage_score:.0%})."
                )
            elif coverage_score >= 0.40:
                next_design_actions.append(
                    f"Improve graph relationship coverage (currently {coverage_score:.0%}) "
                    "by enriching component power rails, data buses, and body regions."
                )
            else:
                mismatches.append(
                    f"Graph relationship coverage is low ({coverage_score:.0%}); "
                    "design traceability is weak."
                )
                next_design_actions.append(
                    "Run a full enrichment pass and add missing power/bus/region data."
                )

        if graph_review.consistency_warnings:
            next_design_actions.append(
                f"Resolve {len(graph_review.consistency_warnings)} "
                "graph consistency warning(s)."
            )

    # ── 4. Vision prediction ──────────────────────────────────────────────────
    if vision_prediction is not None:
        raw_label = vision_prediction.label
        conf = vision_prediction.confidence
        generic = _is_generic_label(raw_label)
        overlaps = _label_overlaps_mission(raw_label, mission_text)
        model_tag = f"'{vision_prediction.model_name}'" if vision_prediction.model_name else "unknown model"

        if generic:
            vision_score = 0.3
            mismatches.append(
                f"Vision prediction '{raw_label}' ({conf:.0%} confidence) comes from "
                f"a generic classifier ({model_tag}) that is not trained on engineering "
                "or CAD imagery. This label must not be used to evaluate design correctness."
            )
            if intended_platform or observed_platform_signals:
                mismatches.append(
                    "Mission/graph evidence strongly indicates an engineering design; "
                    f"the generic label '{raw_label}' conflicts with that context."
                )
            next_design_actions.append(
                "Replace the generic vision classifier with a domain-grounded CAD/"
                "robotics image classifier before using visual predictions for design "
                "validation."
            )
        elif vision_prediction.is_domain_grounded:
            if overlaps:
                vision_score = min(1.0, 0.70 + conf * 0.30)
                strengths.append(
                    f"Domain-grounded vision model predicts '{raw_label}' ({conf:.0%}), "
                    "which aligns with mission intent."
                )
            else:
                vision_score = max(0.0, 0.50 - conf * 0.30)
                mismatches.append(
                    f"Domain-grounded vision model predicts '{raw_label}' ({conf:.0%}), "
                    "which does not clearly align with mission intent."
                )
                next_design_actions.append(
                    f"Review whether the rendered output matches the intended "
                    f"'{intended_platform or 'unknown'}' design."
                )
        else:
            # Non-generic, not domain-grounded — neutral signal
            vision_score = 0.5
            if overlaps:
                strengths.append(
                    f"Vision prediction '{raw_label}' partially overlaps mission keywords."
                )

        sub_scores.append((vision_score, 0.10))

    # ── 5. Final weighted score ───────────────────────────────────────────────
    if sub_scores:
        total_weight = sum(w for _, w in sub_scores)
        raw = sum(s * w for s, w in sub_scores) / total_weight
        semantic_match_score = round(max(0.0, min(1.0, raw)), 3)
    else:
        semantic_match_score = 0.0

    # ── 6. Safety fallbacks ───────────────────────────────────────────────────
    if not strengths and not mismatches:
        mismatches.append(
            "Insufficient data to evaluate design understanding."
        )
    if semantic_match_score < 0.5 and not next_design_actions:
        next_design_actions.append(
            "Review the mission graph for platform, component, and morphology completeness."
        )

    return DesignUnderstandingReport(
        intended_platform=intended_platform,
        observed_platform_signals=observed_platform_signals,
        visual_prediction=vision_prediction,
        semantic_match_score=semantic_match_score,
        strengths=strengths,
        mismatches=mismatches,
        next_design_actions=next_design_actions,
    )
