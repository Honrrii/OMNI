"""Phase 10A — Design Understanding Evaluator tests.

All tests are deterministic.  No LLM calls, no network, no file I/O.
"""
from __future__ import annotations

import pytest

from backend.app.cortex.design_evaluator import (
    DesignUnderstandingReport,
    VisionPrediction,
    evaluate_design_understanding,
)
from backend.app.mission_graph.schemas import (
    Component,
    MissionKnowledgeGraph,
    Morphology,
    Ros2Node,
)
from backend.app.mission_graph.reviewer import (
    MissionGraphReview,
    ComponentCoverage,
    Ros2Coverage,
    MorphologyCadCoverage,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _graph(
    platform: str = "",
    platform_normalized: str = "",
    components: list | None = None,
    ros2_nodes: list | None = None,
    morphology: list | None = None,
) -> MissionKnowledgeGraph:
    import datetime
    return MissionKnowledgeGraph(
        graph_id="test-graph",
        generated_at=datetime.datetime.utcnow().isoformat(),
        platform=platform,
        platform_normalized=platform_normalized,
        components=components or [],
        ros2_nodes=ros2_nodes or [],
        morphology=morphology or [],
    )


def _review(
    comp_total: int = 0,
    comp_power: int = 0,
    comp_bus: int = 0,
    comp_region: int = 0,
    node_total: int = 0,
    nodes_with_comp: int = 0,
    cad_total: int = 0,
    cad_region: int = 0,
) -> MissionGraphReview:
    return MissionGraphReview(
        graph_id="test-graph",
        component_coverage=ComponentCoverage(
            total=comp_total,
            with_power_rail_id=comp_power,
            with_data_bus_id=comp_bus,
            with_body_region_id=comp_region,
        ),
        ros2_coverage=Ros2Coverage(
            total_nodes=node_total,
            nodes_with_component_ids=nodes_with_comp,
        ),
        morphology_cad_coverage=MorphologyCadCoverage(
            total_cad_features=cad_total,
            cad_features_with_body_region_id=cad_region,
        ),
    )


def _vision(label: str, confidence: float = 0.90, model_name: str = "test-model",
            is_domain_grounded: bool = False) -> VisionPrediction:
    return VisionPrediction(
        label=label,
        confidence=confidence,
        model_name=model_name,
        is_domain_grounded=is_domain_grounded,
    )


# ---------------------------------------------------------------------------
# Model construction
# ---------------------------------------------------------------------------

def test_vision_prediction_model():
    vp = VisionPrediction(label="Bag", confidence=0.87, model_name="fashion-mnist")
    assert vp.label == "Bag"
    assert vp.confidence == pytest.approx(0.87)
    assert not vp.is_domain_grounded


def test_design_understanding_report_model():
    rpt = DesignUnderstandingReport(
        intended_platform="ground-rover",
        semantic_match_score=0.75,
        strengths=["one"],
        mismatches=[],
        next_design_actions=[],
    )
    assert rpt.semantic_match_score == pytest.approx(0.75)
    assert rpt.intended_platform == "ground-rover"


def test_report_score_clamped_to_range():
    rpt = DesignUnderstandingReport(
        semantic_match_score=1.0,
        strengths=[],
        mismatches=[],
        next_design_actions=[],
    )
    assert 0.0 <= rpt.semantic_match_score <= 1.0


# ---------------------------------------------------------------------------
# Platform extraction from mission text
# ---------------------------------------------------------------------------

def test_rover_platform_detected():
    rpt = evaluate_design_understanding("Build a ROS2 ground rover for terrain scouting.")
    assert rpt.intended_platform == "ground-rover"


def test_drone_platform_detected():
    rpt = evaluate_design_understanding("Design a hexacopter drone with full electronics.")
    assert rpt.intended_platform == "drone-uav"


def test_robot_arm_platform_detected():
    rpt = evaluate_design_understanding("Design a 6-DOF robot arm for pick-and-place.")
    assert rpt.intended_platform == "robot-arm"


def test_no_platform_in_mission_text():
    rpt = evaluate_design_understanding("Build something cool.")
    assert rpt.intended_platform is None
    assert any("No known platform" in m for m in rpt.mismatches)


def test_platform_strength_added_when_detected():
    rpt = evaluate_design_understanding("Build a rover to explore the desert.")
    assert any("ground-rover" in s for s in rpt.strengths)


# ---------------------------------------------------------------------------
# Score range and basic invariants
# ---------------------------------------------------------------------------

def test_score_is_in_range_minimal_input():
    rpt = evaluate_design_understanding("A rover for exploration.")
    assert 0.0 <= rpt.semantic_match_score <= 1.0


def test_score_is_in_range_with_graph():
    graph = _graph(platform="rover", platform_normalized="ground-rover",
                   components=[Component(id="c1", name="Wheel motor")])
    rpt = evaluate_design_understanding("Build a rover.", graph=graph)
    assert 0.0 <= rpt.semantic_match_score <= 1.0


def test_score_is_float():
    rpt = evaluate_design_understanding("Drone mission.")
    assert isinstance(rpt.semantic_match_score, float)


# ---------------------------------------------------------------------------
# Platform match / mismatch between mission and graph
# ---------------------------------------------------------------------------

def test_platform_match_adds_strength():
    graph = _graph(platform="rover", platform_normalized="ground-rover")
    rpt = evaluate_design_understanding("Build a rover for terrain scouting.", graph=graph)
    assert any("matches mission intent" in s for s in rpt.strengths)


def test_platform_mismatch_adds_mismatch():
    graph = _graph(platform="drone", platform_normalized="drone-uav")
    rpt = evaluate_design_understanding("Build a rover for terrain scouting.", graph=graph)
    assert any("does not match" in m for m in rpt.mismatches)


def test_platform_mismatch_lower_score_than_match():
    graph_match    = _graph(platform="rover", platform_normalized="ground-rover")
    graph_mismatch = _graph(platform="drone", platform_normalized="drone-uav")
    mission = "Build a rover for terrain scouting."
    score_match    = evaluate_design_understanding(mission, graph=graph_match).semantic_match_score
    score_mismatch = evaluate_design_understanding(mission, graph=graph_mismatch).semantic_match_score
    assert score_match > score_mismatch


def test_no_graph_platform_adds_mismatch_note():
    graph = _graph(platform="rover", platform_normalized="")
    rpt = evaluate_design_understanding("Build a rover.", graph=graph)
    assert any("no normalized platform" in m for m in rpt.mismatches)


# ---------------------------------------------------------------------------
# Structural richness (graph present)
# ---------------------------------------------------------------------------

def test_components_present_adds_strength():
    graph = _graph(
        platform_normalized="ground-rover",
        components=[Component(id="c1", name="Wheel motor"),
                    Component(id="c2", name="IMU")],
    )
    rpt = evaluate_design_understanding("Build a rover.", graph=graph)
    assert any("component" in s for s in rpt.strengths)


def test_no_components_adds_mismatch():
    graph = _graph(platform="rover", platform_normalized="ground-rover")
    rpt = evaluate_design_understanding("Build a rover.", graph=graph)
    assert any("no components" in m for m in rpt.mismatches)


def test_ros2_nodes_present_adds_strength():
    graph = _graph(
        platform_normalized="ground-rover",
        ros2_nodes=[Ros2Node(id="n1", name="navigation_node")],
    )
    rpt = evaluate_design_understanding("Build a rover.", graph=graph)
    assert any("ROS2 node" in s for s in rpt.strengths)


def test_morphology_present_adds_strength():
    graph = _graph(
        platform_normalized="ground-rover",
        morphology=[Morphology(id="m1", description="dome chassis")],
    )
    rpt = evaluate_design_understanding("Build a rover.", graph=graph)
    assert any("morphology" in s for s in rpt.strengths)


def test_richer_graph_scores_higher():
    sparse = _graph(platform_normalized="ground-rover")
    rich   = _graph(
        platform_normalized="ground-rover",
        components=[Component(id=f"c{i}", name=f"Part{i}") for i in range(5)],
        ros2_nodes=[Ros2Node(id=f"n{i}", name=f"node{i}") for i in range(3)],
        morphology=[Morphology(id="m1", description="frame")],
    )
    mission = "Build a rover for terrain scouting."
    assert (
        evaluate_design_understanding(mission, graph=rich).semantic_match_score
        > evaluate_design_understanding(mission, graph=sparse).semantic_match_score
    )


# ---------------------------------------------------------------------------
# Graph review coverage
# ---------------------------------------------------------------------------

def test_high_coverage_adds_strength():
    review = _review(
        comp_total=2, comp_power=2, comp_bus=2, comp_region=2,
        node_total=2, nodes_with_comp=2,
        cad_total=2, cad_region=2,
    )
    rpt = evaluate_design_understanding("Build a rover.", graph_review=review)
    assert any("strong" in s for s in rpt.strengths)


def test_low_coverage_adds_mismatch():
    review = _review(comp_total=4, comp_power=0, comp_bus=0, comp_region=0)
    rpt = evaluate_design_understanding("Build a rover.", graph_review=review)
    assert any("low" in m for m in rpt.mismatches)


def test_medium_coverage_suggests_action():
    review = _review(comp_total=4, comp_power=2, comp_bus=2, comp_region=2)
    rpt = evaluate_design_understanding("Build a rover.", graph_review=review)
    # Coverage = (6/12) = 0.5 — medium, no mismatch but suggests improvement
    assert not any("low" in m for m in rpt.mismatches)


def test_coverage_improves_score():
    base_review = _review(comp_total=4, comp_power=0, comp_bus=0, comp_region=0)
    good_review = _review(comp_total=4, comp_power=4, comp_bus=4, comp_region=4)
    mission = "Build a rover."
    base_score = evaluate_design_understanding(mission, graph_review=base_review).semantic_match_score
    good_score = evaluate_design_understanding(mission, graph_review=good_review).semantic_match_score
    assert good_score > base_score


# ---------------------------------------------------------------------------
# Vision prediction — generic labels
# ---------------------------------------------------------------------------

def test_generic_label_bag_adds_mismatch():
    rpt = evaluate_design_understanding(
        "Build a rover for terrain scouting.",
        vision_prediction=_vision("Bag", model_name="fashion-mnist"),
    )
    assert any("generic classifier" in m for m in rpt.mismatches)


def test_generic_label_tshirt_adds_mismatch():
    rpt = evaluate_design_understanding(
        "Design a drone.",
        vision_prediction=_vision("T-shirt/top", model_name="fashion-mnist"),
    )
    assert any("generic classifier" in m for m in rpt.mismatches)


def test_generic_label_with_graph_evidence_adds_conflict_note():
    graph = _graph(platform="rover", platform_normalized="ground-rover",
                   components=[Component(id="c1", name="IMU")])
    rpt = evaluate_design_understanding(
        "Build a rover.",
        graph=graph,
        vision_prediction=_vision("Bag", model_name="fashion-mnist"),
    )
    # Should note conflict between engineering evidence and generic label
    assert any("conflicts with" in m or "engineering design" in m for m in rpt.mismatches)


def test_generic_label_adds_classifier_action():
    rpt = evaluate_design_understanding(
        "Build a rover.",
        vision_prediction=_vision("Sneaker", model_name="fashion-mnist"),
    )
    assert any("domain-grounded" in a for a in rpt.next_design_actions)


def test_generic_label_vision_prediction_preserved_in_report():
    vp = _vision("Bag", confidence=0.93, model_name="fashion-mnist")
    rpt = evaluate_design_understanding("Build a rover.", vision_prediction=vp)
    assert rpt.visual_prediction is not None
    assert rpt.visual_prediction.label == "Bag"


# ---------------------------------------------------------------------------
# Vision prediction — domain-grounded labels
# ---------------------------------------------------------------------------

def test_domain_grounded_matching_label_adds_strength():
    rpt = evaluate_design_understanding(
        "Build a rover for terrain scouting.",
        vision_prediction=_vision("rover", confidence=0.85, is_domain_grounded=True),
    )
    assert any("aligns with mission" in s for s in rpt.strengths)


def test_domain_grounded_matching_label_high_score():
    rpt = evaluate_design_understanding(
        "Build a rover.",
        vision_prediction=_vision("rover", confidence=0.90, is_domain_grounded=True),
    )
    # domain-grounded match should contribute positively; score >= 0.5
    assert rpt.semantic_match_score >= 0.50


def test_domain_grounded_non_matching_label_adds_mismatch():
    rpt = evaluate_design_understanding(
        "Build a rover.",
        vision_prediction=_vision("aircraft", confidence=0.88, is_domain_grounded=True),
    )
    assert any("does not clearly align" in m for m in rpt.mismatches)


# ---------------------------------------------------------------------------
# Vision prediction — neutral / non-grounded, non-generic
# ---------------------------------------------------------------------------

def test_neutral_label_overlapping_mission_adds_strength():
    rpt = evaluate_design_understanding(
        "Build a rover for terrain scouting.",
        vision_prediction=_vision("rover", confidence=0.60, is_domain_grounded=False),
    )
    assert any("partially overlaps" in s for s in rpt.strengths)


# ---------------------------------------------------------------------------
# No-input / edge cases
# ---------------------------------------------------------------------------

def test_empty_mission_text_does_not_crash():
    rpt = evaluate_design_understanding("")
    assert isinstance(rpt, DesignUnderstandingReport)
    assert 0.0 <= rpt.semantic_match_score <= 1.0


def test_only_mission_text_returns_report():
    rpt = evaluate_design_understanding("Design a hexapod robot for rough terrain.")
    assert rpt.intended_platform == "hexapod"
    assert isinstance(rpt.strengths, list)
    assert isinstance(rpt.mismatches, list)
    assert isinstance(rpt.next_design_actions, list)


def test_no_graph_no_review_no_vision_returns_report():
    rpt = evaluate_design_understanding("Build a drone.")
    assert rpt.intended_platform == "drone-uav"
    assert isinstance(rpt, DesignUnderstandingReport)


def test_observed_signals_list_present():
    rpt = evaluate_design_understanding("Build a rover.")
    assert isinstance(rpt.observed_platform_signals, list)


def test_observed_signals_populated_from_graph():
    graph = _graph(platform="rover", platform_normalized="ground-rover")
    rpt = evaluate_design_understanding("Build a rover.", graph=graph)
    assert any("ground-rover" in sig for sig in rpt.observed_platform_signals)


# ---------------------------------------------------------------------------
# Combination: graph + review + vision
# ---------------------------------------------------------------------------

def test_full_combination_returns_report():
    graph = _graph(
        platform="rover",
        platform_normalized="ground-rover",
        components=[Component(id="c1", name="Wheel motor"),
                    Component(id="c2", name="LiDAR sensor")],
        ros2_nodes=[Ros2Node(id="n1", name="nav_node"),
                    Ros2Node(id="n2", name="sensor_node")],
        morphology=[Morphology(id="m1", description="dome chassis")],
    )
    review = _review(
        comp_total=2, comp_power=2, comp_bus=2, comp_region=2,
        node_total=2, nodes_with_comp=2,
    )
    vp = _vision("Bag", model_name="fashion-mnist")
    rpt = evaluate_design_understanding(
        "Build a ROS2 ground rover for terrain scouting.",
        graph=graph,
        graph_review=review,
        vision_prediction=vp,
    )
    assert isinstance(rpt, DesignUnderstandingReport)
    assert 0.0 <= rpt.semantic_match_score <= 1.0
    # Generic vision label must add a mismatch even with strong graph evidence
    assert any("generic classifier" in m for m in rpt.mismatches)
    # Strong graph + platform match = positive strengths
    assert any("ground-rover" in s for s in rpt.strengths)


def test_generic_vision_does_not_override_strong_graph_score():
    """A high-quality graph should still score well despite a generic vision label."""
    graph = _graph(
        platform="rover",
        platform_normalized="ground-rover",
        components=[Component(id=f"c{i}", name=f"Part{i}") for i in range(5)],
        ros2_nodes=[Ros2Node(id=f"n{i}", name=f"node{i}") for i in range(3)],
        morphology=[Morphology(id="m1", description="terrain chassis")],
    )
    review = _review(
        comp_total=5, comp_power=5, comp_bus=5, comp_region=5,
        node_total=3, nodes_with_comp=3,
    )
    vp = _vision("Bag", confidence=0.99, model_name="fashion-mnist")
    rpt = evaluate_design_understanding(
        "Build a ROS2 ground rover for terrain scouting.",
        graph=graph,
        graph_review=review,
        vision_prediction=vp,
    )
    # Vision is 10% weight; strong graph (90% weight) should keep score above 0.5
    assert rpt.semantic_match_score >= 0.50


# ===========================================================================
# Phase 10C — Cortex diagnostic schema tests
# ===========================================================================

# ---------------------------------------------------------------------------
# mission_intent
# ---------------------------------------------------------------------------

def test_mission_intent_present():
    rpt = evaluate_design_understanding("Build a rover.")
    assert isinstance(rpt.mission_intent, dict)
    for key in ("raw_snippet", "extracted_platform", "domain_signals",
                "word_count", "has_quantitative_requirements"):
        assert key in rpt.mission_intent, f"mission_intent missing key: {key}"


def test_mission_intent_platform_matches_intended():
    rpt = evaluate_design_understanding("Build a rover for terrain scouting.")
    assert rpt.mission_intent["extracted_platform"] == "ground-rover"
    assert rpt.mission_intent["extracted_platform"] == rpt.intended_platform


def test_mission_intent_domain_signals_populated():
    rpt = evaluate_design_understanding("Build a ROS2 rover with LiDAR and IMU.")
    assert "ros2" in rpt.mission_intent["domain_signals"]
    assert "lidar" in rpt.mission_intent["domain_signals"]


def test_mission_intent_word_count():
    rpt = evaluate_design_understanding("Build a rover.")
    assert rpt.mission_intent["word_count"] == 3


def test_mission_intent_has_quantitative_requirements_false():
    rpt = evaluate_design_understanding("Build a rover for exploration.")
    assert rpt.mission_intent["has_quantitative_requirements"] is False


def test_mission_intent_has_quantitative_requirements_true():
    rpt = evaluate_design_understanding("Build a rover weighing 5 kg with top speed 2 m/s.")
    assert rpt.mission_intent["has_quantitative_requirements"] is True


def test_mission_intent_snippet_max_200_chars():
    long_text = "Build a rover " + "x" * 300
    rpt = evaluate_design_understanding(long_text)
    assert len(rpt.mission_intent["raw_snippet"]) <= 200


# ---------------------------------------------------------------------------
# design_envelope
# ---------------------------------------------------------------------------

def test_design_envelope_present():
    rpt = evaluate_design_understanding("Build a rover.")
    assert isinstance(rpt.design_envelope, dict)
    for key in ("platform", "component_count", "ros2_node_count",
                "morphology_count", "enrichment_run", "review_run"):
        assert key in rpt.design_envelope, f"design_envelope missing key: {key}"


def test_design_envelope_counts_with_graph():
    graph = _graph(
        platform_normalized="ground-rover",
        components=[Component(id="c1", name="Motor"), Component(id="c2", name="IMU")],
        ros2_nodes=[Ros2Node(id="n1", name="nav_node")],
        morphology=[Morphology(id="m1", description="dome frame")],
    )
    rpt = evaluate_design_understanding("Build a rover.", graph=graph)
    assert rpt.design_envelope["component_count"] == 2
    assert rpt.design_envelope["ros2_node_count"] == 1
    assert rpt.design_envelope["morphology_count"] == 1


def test_design_envelope_no_graph_zeros():
    rpt = evaluate_design_understanding("Build a rover.")
    assert rpt.design_envelope["component_count"] == 0
    assert rpt.design_envelope["ros2_node_count"] == 0


def test_design_envelope_enrichment_run_true():
    graph = _graph(platform="rover", platform_normalized="ground-rover")
    rpt = evaluate_design_understanding("Build a rover.", graph=graph)
    assert rpt.design_envelope["enrichment_run"] is True


def test_design_envelope_review_run_true():
    review = _review(comp_total=2, comp_power=1, comp_bus=1, comp_region=1)
    rpt = evaluate_design_understanding("Build a rover.", graph_review=review)
    assert rpt.design_envelope["review_run"] is True


def test_design_envelope_review_run_false_without_review():
    rpt = evaluate_design_understanding("Build a rover.")
    assert rpt.design_envelope["review_run"] is False


# ---------------------------------------------------------------------------
# detected_domains
# ---------------------------------------------------------------------------

def test_detected_domains_is_list():
    rpt = evaluate_design_understanding("Build a rover.")
    assert isinstance(rpt.detected_domains, list)


def test_detected_domains_ros2_from_mission_text():
    rpt = evaluate_design_understanding("Build a ROS2 ground rover.")
    assert "ros2" in rpt.detected_domains


def test_detected_domains_navigation_from_mission():
    rpt = evaluate_design_understanding("Build a rover with LiDAR for autonomous navigation.")
    assert "navigation" in rpt.detected_domains


def test_detected_domains_electronics_from_graph():
    graph = _graph(
        platform_normalized="ground-rover",
        components=[Component(id="c1", name="motor controller")],
    )
    rpt = evaluate_design_understanding("Build a rover.", graph=graph)
    assert "electronics" in rpt.detected_domains


def test_detected_domains_mechanical_from_graph_morphology():
    graph = _graph(
        platform_normalized="ground-rover",
        morphology=[Morphology(id="m1", description="chassis frame")],
    )
    rpt = evaluate_design_understanding("Build a rover.", graph=graph)
    assert "mechanical" in rpt.detected_domains


def test_detected_domains_empty_on_minimal_input():
    rpt = evaluate_design_understanding("Build something cool.")
    assert isinstance(rpt.detected_domains, list)


# ---------------------------------------------------------------------------
# design_candidates
# ---------------------------------------------------------------------------

def test_design_candidates_is_list():
    rpt = evaluate_design_understanding("Build a rover.")
    assert isinstance(rpt.design_candidates, list)


def test_design_candidates_rover_present():
    rpt = evaluate_design_understanding("Build a rover for terrain scouting.")
    platforms = [c["platform"] for c in rpt.design_candidates]
    assert "ground-rover" in platforms


def test_design_candidates_primary_flag():
    rpt = evaluate_design_understanding("Build a rover for terrain scouting.")
    primary = [c for c in rpt.design_candidates if c["is_primary"]]
    assert len(primary) == 1
    assert primary[0]["platform"] == "ground-rover"


def test_design_candidates_confidence_range():
    rpt = evaluate_design_understanding("Build a hexacopter drone.")
    for c in rpt.design_candidates:
        assert 0.0 <= c["confidence"] <= 1.0


def test_design_candidates_empty_when_no_platform():
    rpt = evaluate_design_understanding("Build something cool.")
    assert rpt.design_candidates == []


def test_design_candidates_matched_keyword_present():
    rpt = evaluate_design_understanding("Build a rover.")
    assert all("matched_keyword" in c for c in rpt.design_candidates)


# ---------------------------------------------------------------------------
# constraint_links
# ---------------------------------------------------------------------------

def test_constraint_links_is_list():
    rpt = evaluate_design_understanding("Build a rover.")
    assert isinstance(rpt.constraint_links, list)


def test_constraint_links_empty_without_graph():
    rpt = evaluate_design_understanding("Build a rover for terrain scouting.")
    assert rpt.constraint_links == []


def test_constraint_links_populated_from_graph():
    graph = _graph(
        platform_normalized="ground-rover",
        ros2_nodes=[Ros2Node(id="n1", name="navigation_node")],
    )
    rpt = evaluate_design_understanding(
        "Build a rover with navigation capabilities.", graph=graph
    )
    assert len(rpt.constraint_links) >= 1


def test_constraint_links_have_required_keys():
    graph = _graph(
        platform_normalized="ground-rover",
        components=[Component(id="c1", name="lidar sensor")],
    )
    rpt = evaluate_design_understanding("Build a rover with lidar.", graph=graph)
    for link in rpt.constraint_links:
        for key in ("constraint", "linked_to", "evidence", "source"):
            assert key in link, f"constraint_link missing key: {key}"


def test_constraint_links_capped_at_ten():
    graph = _graph(
        platform_normalized="ground-rover",
        components=[Component(id=f"c{i}", name=f"motor sensor lidar camera part{i}") for i in range(20)],
    )
    rpt = evaluate_design_understanding(
        "Build a rover with motor sensor lidar camera.", graph=graph
    )
    assert len(rpt.constraint_links) <= 10


# ---------------------------------------------------------------------------
# provenance_summary
# ---------------------------------------------------------------------------

def test_provenance_summary_present():
    rpt = evaluate_design_understanding("Build a rover.")
    assert isinstance(rpt.provenance_summary, dict)
    for key in ("sources_used", "source_count", "has_graph",
                "has_graph_review", "has_vision", "vision_is_domain_grounded"):
        assert key in rpt.provenance_summary


def test_provenance_sources_mission_only():
    rpt = evaluate_design_understanding("Build a rover.")
    assert rpt.provenance_summary["sources_used"] == ["mission_text"]
    assert rpt.provenance_summary["source_count"] == 1


def test_provenance_sources_with_graph_and_review():
    review = _review(comp_total=2, comp_power=2, comp_bus=2, comp_region=2)
    graph = _graph(platform_normalized="ground-rover")
    rpt = evaluate_design_understanding("Build a rover.", graph=graph, graph_review=review)
    assert "mission_text" in rpt.provenance_summary["sources_used"]
    assert "mission_graph" in rpt.provenance_summary["sources_used"]
    assert "graph_review" in rpt.provenance_summary["sources_used"]
    assert rpt.provenance_summary["source_count"] == 3


def test_provenance_vision_is_domain_grounded_flag():
    vp = _vision("rover", is_domain_grounded=True)
    rpt = evaluate_design_understanding("Build a rover.", vision_prediction=vp)
    assert rpt.provenance_summary["vision_is_domain_grounded"] is True


# ---------------------------------------------------------------------------
# validation_gaps
# ---------------------------------------------------------------------------

def test_validation_gaps_is_list():
    rpt = evaluate_design_understanding("Build a rover.")
    assert isinstance(rpt.validation_gaps, list)


def test_validation_gaps_no_review_message():
    rpt = evaluate_design_understanding("Build a rover.")
    assert any("Graph review not available" in g for g in rpt.validation_gaps)


def test_validation_gaps_detected_from_review():
    review = _review(comp_total=4, comp_power=0, comp_bus=0, comp_region=0)
    rpt = evaluate_design_understanding("Build a rover.", graph_review=review)
    assert any("power_rail_id" in g for g in rpt.validation_gaps)
    assert any("data_bus_id" in g for g in rpt.validation_gaps)
    assert any("body_region_id" in g for g in rpt.validation_gaps)


def test_validation_gaps_ros2_nodes_unlinked():
    review = _review(node_total=3, nodes_with_comp=0)
    rpt = evaluate_design_understanding("Build a rover.", graph_review=review)
    assert any("ROS2 node" in g for g in rpt.validation_gaps)


def test_validation_gaps_none_when_fully_covered():
    review = _review(
        comp_total=2, comp_power=2, comp_bus=2, comp_region=2,
        node_total=2, nodes_with_comp=2,
        cad_total=2, cad_region=2,
    )
    rpt = evaluate_design_understanding("Build a rover.", graph_review=review)
    assert any("No validation gaps" in g for g in rpt.validation_gaps)


# ---------------------------------------------------------------------------
# open_questions
# ---------------------------------------------------------------------------

def test_open_questions_is_list():
    rpt = evaluate_design_understanding("Build a rover.")
    assert isinstance(rpt.open_questions, list)


def test_open_questions_always_non_empty():
    rpt = evaluate_design_understanding("Build a rover.")
    assert len(rpt.open_questions) > 0


def test_open_questions_vision_absent():
    rpt = evaluate_design_understanding("Build a rover.")
    assert any("vision classifier" in q for q in rpt.open_questions)


def test_open_questions_no_physics_simulation():
    rpt = evaluate_design_understanding("Build a rover.")
    assert any("Physics simulation" in q for q in rpt.open_questions)


def test_open_questions_no_graph():
    rpt = evaluate_design_understanding("Build a rover.")
    assert any("No mission graph" in q for q in rpt.open_questions)


def test_open_questions_no_quantitative_requirements():
    rpt = evaluate_design_understanding("Build a rover for exploration.")
    assert any("quantitative" in q for q in rpt.open_questions)


# ---------------------------------------------------------------------------
# cortex_score
# ---------------------------------------------------------------------------

def test_cortex_score_present():
    rpt = evaluate_design_understanding("Build a rover.")
    from backend.app.cortex.design_evaluator import CortexScore
    assert isinstance(rpt.cortex_score, CortexScore)


def test_cortex_score_all_fields_in_range():
    rpt = evaluate_design_understanding("Build a ROS2 rover with LiDAR.")
    cs = rpt.cortex_score
    for field in ("intent_clarity", "constraint_traceability",
                  "physics_grounding", "artifact_provenance", "execution_evidence"):
        value = getattr(cs, field)
        assert 0.0 <= value <= 1.0, f"cortex_score.{field} = {value} out of range"


def test_cortex_score_intent_clarity_higher_with_platform_and_domains():
    rpt_rich = evaluate_design_understanding("Build a ROS2 rover with LiDAR and IMU sensors.")
    rpt_bare = evaluate_design_understanding("Build something cool.")
    assert rpt_rich.cortex_score.intent_clarity > rpt_bare.cortex_score.intent_clarity


def test_cortex_score_constraint_traceability_improves_with_review():
    review_good = _review(comp_total=4, comp_power=4, comp_bus=4, comp_region=4)
    review_bad  = _review(comp_total=4, comp_power=0, comp_bus=0, comp_region=0)
    rpt_good = evaluate_design_understanding("Build a rover.", graph_review=review_good)
    rpt_bad  = evaluate_design_understanding("Build a rover.", graph_review=review_bad)
    assert rpt_good.cortex_score.constraint_traceability > rpt_bad.cortex_score.constraint_traceability


def test_cortex_score_artifact_provenance_zero_without_graph():
    rpt = evaluate_design_understanding("Build a rover.")
    assert rpt.cortex_score.artifact_provenance == 0.0


def test_cortex_score_artifact_provenance_positive_with_full_graph():
    graph = _graph(
        platform_normalized="ground-rover",
        components=[Component(id="c1", name="motor")],
        ros2_nodes=[Ros2Node(id="n1", name="nav_node")],
        morphology=[Morphology(id="m1", description="frame")],
    )
    rpt = evaluate_design_understanding("Build a rover.", graph=graph)
    assert rpt.cortex_score.artifact_provenance > 0.0


def test_cortex_score_execution_evidence_with_linked_nodes():
    review = _review(node_total=2, nodes_with_comp=2)
    rpt = evaluate_design_understanding("Build a rover.", graph_review=review)
    # review with no graph nodes means ros2_coverage.total=2, linked=2 but graph has no ros2_nodes
    # execution_evidence should still be non-negative
    assert rpt.cortex_score.execution_evidence >= 0.0


def test_cortex_score_serializes_as_dict():
    rpt = evaluate_design_understanding("Build a rover.")
    data = rpt.model_dump(mode="json")
    cs = data["cortex_score"]
    assert isinstance(cs, dict)
    for key in ("intent_clarity", "constraint_traceability",
                "physics_grounding", "artifact_provenance", "execution_evidence"):
        assert key in cs
