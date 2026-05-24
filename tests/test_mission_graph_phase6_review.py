"""Phase 6 — Mission Graph Reviewer tests."""
from __future__ import annotations

from backend.app.mission_graph.reviewer import MissionGraphReview, MissionGraphReviewIssue, review_graph
from backend.app.mission_graph.schemas import (
    CadFeature,
    Component,
    ConsistencyWarning,
    DataBus,
    MissionKnowledgeGraph,
    Morphology,
    PowerRail,
    Ros2Node,
)


def _graph(**kwargs) -> MissionKnowledgeGraph:
    return MissionKnowledgeGraph(
        graph_id="test", generated_at="2026-05-24T00:00:00+00:00", **kwargs
    )


# ---------------------------------------------------------------------------
# Return type and empty-graph contract
# ---------------------------------------------------------------------------

def test_review_returns_mission_graph_review_instance():
    assert isinstance(review_graph(_graph()), MissionGraphReview)


def test_review_empty_graph_no_warnings():
    review = review_graph(_graph())
    assert review.graph_id == "test"
    assert review.component_coverage.total == 0
    assert review.ros2_coverage.total_nodes == 0
    assert review.morphology_cad_coverage.total_cad_features == 0
    assert review.warnings == []


# ---------------------------------------------------------------------------
# Platform fields
# ---------------------------------------------------------------------------

def test_platform_fields_preserved():
    review = review_graph(_graph(platform="rover", platform_normalized="ground-rover"))
    assert review.platform == "rover"
    assert review.platform_normalized == "ground-rover"


# ---------------------------------------------------------------------------
# Component coverage counts
# ---------------------------------------------------------------------------

def test_component_coverage_counts():
    graph = _graph(components=[
        Component(id="c1", name="A", power_rail_id="r1", data_bus_id="b1", body_region_id="rg1"),
        Component(id="c2", name="B"),  # all links missing
    ])
    cov = review_graph(graph).component_coverage
    assert cov.total == 2
    assert cov.with_power_rail_id == 1
    assert cov.with_data_bus_id == 1
    assert cov.with_body_region_id == 1


def test_component_warnings_emitted_for_missing_links():
    review = review_graph(_graph(components=[Component(id="c1", name="Sensor")]))
    w = review.warnings
    assert any("power_rail_id" in x and "Sensor" in x for x in w)
    assert any("data_bus_id" in x and "Sensor" in x for x in w)
    assert any("body_region_id" in x and "Sensor" in x for x in w)


def test_no_warnings_for_fully_linked_component():
    graph = _graph(components=[Component(
        id="c1", name="MCU",
        power_rail_id="r1", data_bus_id="b1", body_region_id="rg1",
    )])
    review = review_graph(graph)
    assert not any("MCU" in w for w in review.warnings)


# ---------------------------------------------------------------------------
# ROS2 coverage counts
# ---------------------------------------------------------------------------

def test_ros2_coverage_counts():
    graph = _graph(ros2_nodes=[
        Ros2Node(id="n1", name="sensor_node", component_ids=["c1"]),
        Ros2Node(id="n2", name="control_node"),
    ])
    cov = review_graph(graph).ros2_coverage
    assert cov.total_nodes == 2
    assert cov.nodes_with_component_ids == 1


def test_ros2_node_warning_emitted():
    review = review_graph(_graph(ros2_nodes=[Ros2Node(id="n1", name="lonely_node")]))
    assert any("lonely_node" in w and "component_ids" in w for w in review.warnings)


# ---------------------------------------------------------------------------
# Morphology / CAD coverage
# ---------------------------------------------------------------------------

def test_morphology_cad_coverage_counts():
    graph = _graph(
        morphology=[Morphology(id="m1", description="Chassis")],
        cad_features=[
            CadFeature(id="f1", body_region_id="rg1"),
            CadFeature(id="f2"),
        ],
    )
    cov = review_graph(graph).morphology_cad_coverage
    assert cov.total_morphology == 1
    assert cov.total_cad_features == 2
    assert cov.cad_features_with_body_region_id == 1


def test_cad_feature_warning_emitted():
    review = review_graph(_graph(cad_features=[CadFeature(id="feat.001")]))
    assert any("feat.001" in w and "body_region_id" in w for w in review.warnings)


def test_body_regions_counted():
    from backend.app.mission_graph.schemas import BodyRegion
    graph = _graph(body_regions=[BodyRegion(id="rg1", name="Front")])
    assert review_graph(graph).morphology_cad_coverage.total_body_regions == 1


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------

def test_recommendation_for_missing_power_rails():
    graph = _graph(components=[Component(id="c1", name="X"), Component(id="c2", name="Y")])
    recs = review_graph(graph).recommendations
    assert any("power" in r.lower() and "2" in r for r in recs)


def test_recommendation_for_missing_data_buses():
    graph = _graph(components=[Component(id="c1", name="X")])
    recs = review_graph(graph).recommendations
    assert any("interface" in r.lower() or "data bus" in r.lower() for r in recs)


def test_recommendation_no_platform_detected():
    recs = review_graph(_graph()).recommendations
    assert any("platform" in r.lower() for r in recs)


def test_recommendation_unrecognized_platform():
    graph = _graph(platform="zeppelin", platform_normalized="")
    recs = review_graph(graph).recommendations
    assert any("zeppelin" in r for r in recs)


def test_no_platform_recommendation_when_normalized_present():
    graph = _graph(platform="rover", platform_normalized="ground-rover")
    recs = review_graph(graph).recommendations
    assert not any("could not be normalized" in r for r in recs)
    assert not any("No platform detected" in r for r in recs)


# ---------------------------------------------------------------------------
# Consistency warnings pass-through
# ---------------------------------------------------------------------------

def test_consistency_warnings_preserved():
    cw = ConsistencyWarning(id="w1", code="ORPHAN_TOPIC", message="topic has no subscribers")
    review = review_graph(_graph(consistency_warnings=[cw]))
    assert len(review.consistency_warnings) == 1
    assert review.consistency_warnings[0].code == "ORPHAN_TOPIC"


def test_consistency_warnings_empty_by_default():
    assert review_graph(_graph()).consistency_warnings == []


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

def test_review_is_deterministic():
    graph = _graph(
        platform="drone",
        platform_normalized="drone-uav",
        components=[Component(id="c1", name="ESC", power_notes="12V")],
        ros2_nodes=[Ros2Node(id="n1", name="motor_node")],
    )
    assert review_graph(graph).model_dump() == review_graph(graph).model_dump()


# ---------------------------------------------------------------------------
# Structured issues — stable codes, categories, related_ids
# ---------------------------------------------------------------------------

def test_issues_field_is_list_of_review_issues():
    review = review_graph(_graph())
    assert isinstance(review.issues, list)
    assert all(isinstance(i, MissionGraphReviewIssue) for i in review.issues)


def test_issues_empty_for_empty_graph():
    assert review_graph(_graph()).issues == []


def test_issues_empty_for_fully_linked_component():
    graph = _graph(components=[Component(
        id="c1", name="MCU",
        power_rail_id="r1", data_bus_id="b1", body_region_id="rg1",
    )])
    comp_issues = [i for i in review_graph(graph).issues if "c1" in i.related_ids]
    assert comp_issues == []


def test_issue_codes_for_missing_component_links():
    graph = _graph(components=[Component(id="c1", name="Sensor")])
    codes = {i.code for i in review_graph(graph).issues if "c1" in i.related_ids}
    assert codes == {"COMP_MISSING_POWER_RAIL", "COMP_MISSING_DATA_BUS", "COMP_MISSING_BODY_REGION"}


def test_issue_category_component():
    graph = _graph(components=[Component(id="c1", name="Sensor")])
    for issue in review_graph(graph).issues:
        if "c1" in issue.related_ids:
            assert issue.category == "component"


def test_issue_related_ids_contain_component_id():
    graph = _graph(components=[Component(id="c99", name="Widget")])
    for issue in review_graph(graph).issues:
        if issue.code.startswith("COMP_"):
            assert "c99" in issue.related_ids


def test_issue_code_node_missing_component_link():
    graph = _graph(ros2_nodes=[Ros2Node(id="n1", name="lonely_node")])
    node_issues = [i for i in review_graph(graph).issues if "n1" in i.related_ids]
    assert len(node_issues) == 1
    assert node_issues[0].code == "NODE_MISSING_COMPONENT_LINK"
    assert node_issues[0].category == "ros2"


def test_issue_code_cad_missing_body_region():
    graph = _graph(cad_features=[CadFeature(id="feat.001")])
    feat_issues = [i for i in review_graph(graph).issues if "feat.001" in i.related_ids]
    assert len(feat_issues) == 1
    assert feat_issues[0].code == "CAD_MISSING_BODY_REGION"
    assert feat_issues[0].category == "cad"


def test_issue_severity_is_warning():
    graph = _graph(
        components=[Component(id="c1", name="X")],
        ros2_nodes=[Ros2Node(id="n1", name="Y")],
        cad_features=[CadFeature(id="f1")],
    )
    for issue in review_graph(graph).issues:
        assert issue.severity == "warning"


def test_warnings_derived_from_issue_messages():
    """warnings list must equal [i.message for i in issues] — they stay in sync."""
    graph = _graph(
        components=[Component(id="c1", name="Sensor")],
        ros2_nodes=[Ros2Node(id="n1", name="nav_node")],
    )
    review = review_graph(graph)
    assert review.warnings == [i.message for i in review.issues]


def test_issues_deterministic():
    graph = _graph(
        components=[Component(id="c1", name="X")],
        ros2_nodes=[Ros2Node(id="n1", name="Y")],
    )
    r1 = review_graph(graph)
    r2 = review_graph(graph)
    assert [i.model_dump() for i in r1.issues] == [i.model_dump() for i in r2.issues]
