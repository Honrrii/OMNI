"""
OMNI Cortex Phase 10A/10C — Design Understanding Evaluator.

Deterministic, no LLM calls, no network calls.

Given a mission text plus optional graph, graph review, and vision prediction,
returns a DesignUnderstandingReport that explains how well the generated design
matches the mission intent, with full Cortex diagnostic state.

Vision predictions from generic classifiers (e.g. Fashion-MNIST) are treated as
weak signals, not ground truth.  When a generic label conflicts with mission /
graph evidence, a mismatch is recorded explaining that the classifier is not
domain-grounded.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple

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

# Keyword sets used to detect engineering sub-domains.
_DOMAIN_CATEGORIES: Dict[str, Set[str]] = {
    "ros2":        {"ros2", "ros", "gazebo", "rviz"},
    "mechanical":  {"cad", "stl", "step", "fusion360", "morphology"},
    "electronics": {"pcb", "kicad", "electronics", "motor", "servo", "actuator"},
    "navigation":  {"lidar", "imu", "camera", "autonomous", "autonomy", "sensor"},
    "software":    {"ros2", "node", "package", "script"},
}

# Words that indicate quantitative performance requirements in mission text.
_PERF_WORDS: Set[str] = {
    "weight", "mass", "kg", "gram", "speed", "velocity",
    "range", "battery", "watt", "volt", "meter", "payload",
    "altitude", "depth", "torque", "rpm", "frequency",
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


class CortexScore(BaseModel):
    """Five-axis diagnostic score computed deterministically from available evidence."""

    intent_clarity: float = Field(ge=0.0, le=1.0, default=0.0)
    constraint_traceability: float = Field(ge=0.0, le=1.0, default=0.0)
    physics_grounding: float = Field(ge=0.0, le=1.0, default=0.0)
    artifact_provenance: float = Field(ge=0.0, le=1.0, default=0.0)
    execution_evidence: float = Field(ge=0.0, le=1.0, default=0.0)


class DesignUnderstandingReport(BaseModel):
    """
    Deterministic Cortex diagnostic report.

    Expresses: "Here is what I think the mission means. Here is the design
    envelope.  Here is what I assumed.  Here is what I validated.  Here is
    what is still unverified."

    Phase 10A fields (backward-compatible, always present):
      intended_platform, observed_platform_signals, visual_prediction,
      semantic_match_score, strengths, mismatches, next_design_actions.

    Phase 10C additions:
      mission_intent, design_envelope, detected_domains, design_candidates,
      constraint_links, provenance_summary, validation_gaps, open_questions,
      cortex_score.
    """

    # ── Phase 10A fields ─────────────────────────────────────────────────────
    intended_platform: Optional[str] = None
    observed_platform_signals: List[str] = Field(default_factory=list)
    visual_prediction: Optional[VisionPrediction] = None
    semantic_match_score: float = Field(ge=0.0, le=1.0)
    strengths: List[str] = Field(default_factory=list)
    mismatches: List[str] = Field(default_factory=list)
    next_design_actions: List[str] = Field(default_factory=list)

    # ── Phase 10C diagnostic fields ──────────────────────────────────────────
    mission_intent: Dict[str, Any] = Field(default_factory=dict)
    design_envelope: Dict[str, Any] = Field(default_factory=dict)
    detected_domains: List[str] = Field(default_factory=list)
    design_candidates: List[Dict[str, Any]] = Field(default_factory=list)
    constraint_links: List[Dict[str, Any]] = Field(default_factory=list)
    provenance_summary: Dict[str, Any] = Field(default_factory=dict)
    validation_gaps: List[str] = Field(default_factory=list)
    open_questions: List[str] = Field(default_factory=list)
    cortex_score: CortexScore = Field(default_factory=CortexScore)


# ---------------------------------------------------------------------------
# Internal helpers — Phase 10A
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
# Internal helpers — Phase 10C
# ---------------------------------------------------------------------------

def _detect_domains(
    mission_text: str,
    graph: Optional[MissionKnowledgeGraph],
) -> List[str]:
    """Return sorted list of engineering sub-domains detected in mission + graph."""
    lower = mission_text.lower()
    active: Set[str] = set()

    for domain, keywords in _DOMAIN_CATEGORIES.items():
        if any(kw in lower for kw in keywords):
            active.add(domain)

    if graph is not None:
        graph_text = " ".join(
            [c.name.lower() for c in graph.components]
            + [n.name.lower() for n in graph.ros2_nodes]
            + [m.description.lower() for m in graph.morphology]
        )
        for domain, keywords in _DOMAIN_CATEGORIES.items():
            if any(kw in graph_text for kw in keywords):
                active.add(domain)

        if graph.ros2_nodes:
            active.update({"ros2", "software"})
        if graph.morphology:
            active.add("mechanical")
        if graph.components:
            active.add("electronics")

    return sorted(active)


def _build_mission_intent(
    mission_text: str,
    intended_platform: Optional[str],
    domain_signals: List[str],
) -> Dict[str, Any]:
    lower = mission_text.lower()
    return {
        "raw_snippet": mission_text[:200].strip(),
        "extracted_platform": intended_platform,
        "domain_signals": domain_signals,
        "word_count": len(mission_text.split()) if mission_text else 0,
        "has_quantitative_requirements": any(w in lower for w in _PERF_WORDS),
    }


def _build_design_envelope(
    intended_platform: Optional[str],
    graph: Optional[MissionKnowledgeGraph],
    graph_review: Optional[MissionGraphReview],
) -> Dict[str, Any]:
    envelope: Dict[str, Any] = {
        "platform": intended_platform,
        "component_count": 0,
        "ros2_node_count": 0,
        "morphology_count": 0,
        "enrichment_run": False,
        "review_run": graph_review is not None,
    }
    if graph is not None:
        envelope["component_count"] = len(graph.components)
        envelope["ros2_node_count"] = len(graph.ros2_nodes)
        envelope["morphology_count"] = len(graph.morphology)
        envelope["enrichment_run"] = bool(graph.platform_normalized)
    return envelope


def _build_design_candidates(
    mission_text: str,
    intended_platform: Optional[str],
) -> List[Dict[str, Any]]:
    """Ranked list of platform candidates matched in the mission text."""
    lower = mission_text.lower()
    candidates: List[Dict[str, Any]] = []
    seen: Set[str] = set()

    for key in sorted(_PLATFORM_KEYWORDS, key=len, reverse=True):
        if key in lower:
            platform = _PLATFORM_KEYWORDS[key]
            if platform not in seen:
                is_primary = platform == intended_platform
                candidates.append({
                    "platform": platform,
                    "matched_keyword": key,
                    "confidence": 0.90 if is_primary else 0.55,
                    "is_primary": is_primary,
                })
                seen.add(platform)

    return candidates


def _build_constraint_links(
    mission_text: str,
    graph: Optional[MissionKnowledgeGraph],
) -> List[Dict[str, Any]]:
    """Link mission keywords to graph elements where names overlap."""
    if graph is None:
        return []

    links: List[Dict[str, Any]] = []
    lower = mission_text.lower()
    mission_words = set(re.split(r"\W+", lower)) - {"", "a", "an", "the", "for", "to", "of", "in", "with"}

    def _match(name: str) -> List[str]:
        # Split on both non-word chars and underscores so "navigation_node" → {"navigation", "node"}
        name_words = {w for w in re.split(r"[\W_]+", name.lower()) if len(w) > 3}
        return sorted(name_words & mission_words)

    for node in graph.ros2_nodes:
        matched = _match(node.name)
        if matched:
            links.append({
                "constraint": node.name,
                "linked_to": f"ros2_node:{node.id}",
                "evidence": matched,
                "source": "mission_text",
            })

    for comp in graph.components:
        matched = _match(comp.name)
        if matched:
            links.append({
                "constraint": comp.name,
                "linked_to": f"component:{comp.id}",
                "evidence": matched,
                "source": "mission_text",
            })

    for morph in graph.morphology:
        matched = _match(morph.description)
        if matched:
            links.append({
                "constraint": morph.description,
                "linked_to": f"morphology:{morph.id}",
                "evidence": matched,
                "source": "mission_text",
            })

    return links[:10]  # cap to avoid bloat


def _build_provenance_summary(
    graph: Optional[MissionKnowledgeGraph],
    graph_review: Optional[MissionGraphReview],
    vision_prediction: Optional[VisionPrediction],
) -> Dict[str, Any]:
    sources: List[str] = ["mission_text"]
    if graph is not None:
        sources.append("mission_graph")
    if graph_review is not None:
        sources.append("graph_review")
    if vision_prediction is not None:
        sources.append("vision_prediction")

    return {
        "sources_used": sources,
        "source_count": len(sources),
        "has_graph": graph is not None,
        "has_graph_review": graph_review is not None,
        "has_vision": vision_prediction is not None,
        "vision_is_domain_grounded": (
            vision_prediction.is_domain_grounded if vision_prediction else False
        ),
    }


def _extract_validation_gaps(
    graph_review: Optional[MissionGraphReview],
) -> List[str]:
    """List specific coverage gaps from the graph review."""
    if graph_review is None:
        return ["Graph review not available — validation gaps unknown."]

    gaps: List[str] = []
    comp = graph_review.component_coverage
    if comp.total > 0:
        missing_power = comp.total - comp.with_power_rail_id
        missing_bus = comp.total - comp.with_data_bus_id
        missing_region = comp.total - comp.with_body_region_id
        if missing_power:
            gaps.append(f"{missing_power} component(s) missing power_rail_id.")
        if missing_bus:
            gaps.append(f"{missing_bus} component(s) missing data_bus_id.")
        if missing_region:
            gaps.append(f"{missing_region} component(s) missing body_region_id.")

    ros2 = graph_review.ros2_coverage
    if ros2.total_nodes > 0:
        missing_comp = ros2.total_nodes - ros2.nodes_with_component_ids
        if missing_comp:
            gaps.append(f"{missing_comp} ROS2 node(s) not linked to components.")

    morph = graph_review.morphology_cad_coverage
    if morph.total_cad_features > 0:
        missing_region = morph.total_cad_features - morph.cad_features_with_body_region_id
        if missing_region:
            gaps.append(f"{missing_region} CAD feature(s) missing body_region_id.")

    if not gaps:
        gaps.append("No validation gaps detected in graph review.")
    return gaps


def _generate_open_questions(
    mission_text: str,
    graph: Optional[MissionKnowledgeGraph],
    graph_review: Optional[MissionGraphReview],
    vision_prediction: Optional[VisionPrediction],
) -> List[str]:
    """Open questions: things the evaluator cannot confirm with available evidence."""
    questions: List[str] = []

    if vision_prediction is None or not vision_prediction.is_domain_grounded:
        questions.append(
            "No domain-grounded vision classifier provided — visual design validation is unavailable."
        )

    lower = mission_text.lower()
    if not any(w in lower for w in _PERF_WORDS):
        questions.append(
            "Mission text lacks quantitative performance requirements "
            "(weight, speed, range, power, etc.)."
        )

    if graph is None:
        questions.append(
            "No mission graph provided — structural design assumptions are unverified."
        )
    elif not graph.ros2_nodes:
        questions.append("No ROS2 nodes in graph — software architecture is undefined.")

    if graph_review is None:
        questions.append(
            "Graph review has not run — component/node coverage is unverified."
        )

    questions.append(
        "Physics simulation (Gazebo / URDF / SDF) not linked — dynamic behaviour is unvalidated."
    )

    return questions


def _compute_cortex_score(
    intended_platform: Optional[str],
    detected_domains: List[str],
    graph: Optional[MissionKnowledgeGraph],
    graph_review: Optional[MissionGraphReview],
    coverage_score: Optional[float],
) -> CortexScore:
    # intent_clarity: platform detected + breadth of domain signals
    if intended_platform and detected_domains:
        intent_clarity = min(1.0, 0.60 + len(detected_domains) * 0.08)
    elif intended_platform:
        intent_clarity = 0.50
    elif detected_domains:
        intent_clarity = 0.30
    else:
        intent_clarity = 0.10

    # constraint_traceability: driven by graph review coverage
    if coverage_score is not None:
        constraint_traceability = coverage_score
    elif graph is not None:
        constraint_traceability = 0.30  # graph present but no review
    else:
        constraint_traceability = 0.10

    # physics_grounding: always low without simulation; morphology raises it slightly
    if graph and graph.morphology:
        physics_grounding = 0.30
    elif graph and graph.components:
        physics_grounding = 0.20
    else:
        physics_grounding = 0.10

    # artifact_provenance: what fraction of graph axes are populated
    if graph:
        has_comp = bool(graph.components)
        has_node = bool(graph.ros2_nodes)
        has_morph = bool(graph.morphology)
        artifact_provenance = (
            (0.40 if has_comp else 0.0)
            + (0.35 if has_node else 0.0)
            + (0.25 if has_morph else 0.0)
        )
    else:
        artifact_provenance = 0.0

    # execution_evidence: ROS2 nodes linked to components is the best proxy
    if graph and graph.ros2_nodes and graph_review:
        ros2 = graph_review.ros2_coverage
        if ros2.total_nodes > 0:
            execution_evidence = (ros2.nodes_with_component_ids / ros2.total_nodes) * 0.5
        else:
            execution_evidence = 0.0
    elif graph and graph.ros2_nodes:
        execution_evidence = 0.20
    else:
        execution_evidence = 0.0

    return CortexScore(
        intent_clarity=round(min(1.0, max(0.0, intent_clarity)), 3),
        constraint_traceability=round(min(1.0, max(0.0, constraint_traceability)), 3),
        physics_grounding=round(min(1.0, max(0.0, physics_grounding)), 3),
        artifact_provenance=round(min(1.0, max(0.0, artifact_provenance)), 3),
        execution_evidence=round(min(1.0, max(0.0, execution_evidence)), 3),
    )


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
    coverage_score: Optional[float] = None
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

    # ── 7. Phase 10C diagnostic fields ───────────────────────────────────────
    domain_signals = _extract_domain_signals(mission_text)
    detected_domains = _detect_domains(mission_text, graph)
    mission_intent = _build_mission_intent(mission_text, intended_platform, domain_signals)
    design_envelope = _build_design_envelope(intended_platform, graph, graph_review)
    design_candidates = _build_design_candidates(mission_text, intended_platform)
    constraint_links = _build_constraint_links(mission_text, graph)
    provenance_summary = _build_provenance_summary(graph, graph_review, vision_prediction)
    validation_gaps = _extract_validation_gaps(graph_review)
    open_questions = _generate_open_questions(mission_text, graph, graph_review, vision_prediction)
    cortex_score = _compute_cortex_score(
        intended_platform, detected_domains, graph, graph_review, coverage_score
    )

    return DesignUnderstandingReport(
        # Phase 10A
        intended_platform=intended_platform,
        observed_platform_signals=observed_platform_signals,
        visual_prediction=vision_prediction,
        semantic_match_score=semantic_match_score,
        strengths=strengths,
        mismatches=mismatches,
        next_design_actions=next_design_actions,
        # Phase 10C
        mission_intent=mission_intent,
        design_envelope=design_envelope,
        detected_domains=detected_domains,
        design_candidates=design_candidates,
        constraint_links=constraint_links,
        provenance_summary=provenance_summary,
        validation_gaps=validation_gaps,
        open_questions=open_questions,
        cortex_score=cortex_score,
    )
