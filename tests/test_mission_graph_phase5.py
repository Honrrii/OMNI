"""
Phase 5A tests: Mission Knowledge Graph v0.1.

All tests use synthetic fixture data written to tmp_path.
No LLM calls. No real mission folders are read or modified.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.app.mission_graph.builder import build_graph
from backend.app.mission_graph.schemas import MissionKnowledgeGraph
from backend.app.mission_graph.validators import check_graph


# ---------------------------------------------------------------------------
# Synthetic fixture factories
# ---------------------------------------------------------------------------

def _minimal_mission_result(mission: str = "Design a palm-sized rover with ROS2.") -> dict:
    return {
        "mission": mission,
        "mission_id": "test-mission-001",
        "status": "complete",
        "structured_agent_outputs": {
            "sky": {
                "agent_id": "sky",
                "role": "robotics_software_architecture",
                "status": "structured",
                "ros2_package_plan": {
                    "package_name": "test_rover",
                    "nodes": [
                        {
                            "name": "sensor_node",
                            "purpose": "Reads sensors.",
                            "publishes_to": ["sensor_data"],
                            "subscribes_to": [],
                            "services": [],
                            "parameters": ["freq"],
                        },
                        {
                            "name": "control_node",
                            "purpose": "Controls motors.",
                            "publishes_to": ["cmd_vel"],
                            "subscribes_to": ["sensor_data"],
                            "services": ["get_status"],
                            "parameters": ["max_speed"],
                        },
                    ],
                    "topics": ["sensor_data", "cmd_vel"],
                    "launch_files": ["launch/rover.launch.py"],
                    "config_files": [],
                    "tests": ["test/sensor_test.py"],
                },
            },
            "isy": {
                "agent_id": "isy",
                "role": "physics_controls_feasibility",
                "status": "structured",
                "major_subsystems": [
                    {
                        "name": "Locomotion",
                        "purpose": "Move the rover.",
                        "inputs": ["Power", "ROS2 commands"],
                        "outputs": ["Motion"],
                        "notes": ["Must handle uneven terrain."],
                    }
                ],
                "mass_and_geometry_assumptions": [
                    "Total mass ~500g.",
                    "Footprint 100mm x 60mm.",
                ],
                "validation_items": [
                    "Torque calculation under load.",
                    "Stability on slopes.",
                ],
            },
            "oli": {
                "agent_id": "oli",
                "role": "cad_visual_artifacts",
                "status": "structured",
                "fusion360_modeling_plan": [
                    {
                        "step": "Create chassis",
                        "purpose": "Structural base.",
                        "geometry": "Flat rectangular prism.",
                        "parameters": ["L:100mm", "W:60mm", "H:10mm"],
                    },
                ],
                "component_layout": [
                    {"component": "Chassis", "placement": "Bottom", "reason": "Support."},
                ],
            },
            "korva": {
                "agent_id": "korva",
                "role": "hardware_electronics_embedded",
                "status": "structured",
                "component_list": [
                    {
                        "component": "Raspberry Pi",
                        "role": "Compute",
                        "interface": "USB, UART",
                        "power_notes": "5V, 2.5A",
                    },
                    {
                        "component": "Li-Po Battery",
                        "role": "Power Source",
                        "interface": "BMS",
                        "power_notes": "3.7V nominal",
                    },
                ],
                "power_assumptions": [
                    "3.7V Li-Po, approx 1.5W total draw.",
                    "5V regulator for compute.",
                ],
                "communication_buses": [
                    "I2C for sensors, UART for telemetry, GPIO for motors.",
                ],
                "wiring_plan": ["Connect Pi to motor driver via GPIO."],
            },
        },
        "artifacts": {
            "fusion360_concept": {
                "owner": "Oli",
                "summary": "Compact rover chassis.",
                "modeling_plan": [],
            },
            "component_tree": {},
        },
        "export_manifest": {
            "folder_name": "test_rover_folder",
            "files_to_generate_next": [
                "agent_reports/sky.md",
                "artifacts/ros2_node_graph.json",
                "generated_ros2/rover_node.py",
            ],
            "status": "ready",
        },
        "validation": {},
    }


def _validation_report() -> dict:
    return {
        "verdict": "CONDITIONAL PASS",
        "score": 8.5,
        "confidence_scores": {
            "Systems Engineering": 9.0,
            "Physics": 8.5,
            "Electrical / Power": 6.0,
        },
        "missing_evidence": ["No prototype test data provided."],
        "required_next_tests": ["Collect sensor data logs."],
    }


def _provenance_record() -> dict:
    return {
        "system": "OMNI Harness",
        "mission_id": "test-mission-001",
        "agent_count": 2,
        "agents": [
            {
                "agent_id": "sky",
                "agent_name": "Sky",
                "status": "completed",
                "started_at": "2026-05-24T00:00:00+00:00",
                "finished_at": "2026-05-24T00:01:00+00:00",
                "errors": [],
                "evidence_type": "llm_generated",
                "human_review_required": True,
            },
            {
                "agent_id": "korva",
                "agent_name": "Korva",
                "status": "completed",
                "errors": [],
                "evidence_type": "llm_generated",
                "human_review_required": True,
            },
        ],
    }


def _write_fixture(folder: Path, include_optional: bool = True) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "mission_result.json").write_text(
        json.dumps(_minimal_mission_result()), encoding="utf-8"
    )
    if include_optional:
        (folder / "validation_report.json").write_text(
            json.dumps(_validation_report()), encoding="utf-8"
        )
        (folder / "next_artifacts.json").write_text(
            json.dumps(["ROS2 node graph diagram.", "Wiring diagram."]), encoding="utf-8"
        )
        (folder / "provenance_record.json").write_text(
            json.dumps(_provenance_record()), encoding="utf-8"
        )


# ---------------------------------------------------------------------------
# 1. Minimal graph creation
# ---------------------------------------------------------------------------

def test_minimal_graph_creation(tmp_path):
    """build_graph() on a minimal fixture returns a MissionKnowledgeGraph."""
    folder = tmp_path / "mission_minimal"
    _write_fixture(folder)

    graph = build_graph(folder)

    assert isinstance(graph, MissionKnowledgeGraph)
    assert graph.mission_id == "test-mission-001"
    assert "rover" in graph.mission_text.lower()
    assert graph.schema_version == "0.1"
    assert graph.generated_at  # non-empty timestamp
    assert graph.graph_id      # non-empty uuid-fragment


# ---------------------------------------------------------------------------
# 2. ROS2 node/topic extraction and cross-reference
# ---------------------------------------------------------------------------

def test_ros2_node_topic_extraction_and_crossref(tmp_path):
    folder = tmp_path / "mission_ros2"
    _write_fixture(folder)
    graph = build_graph(folder)

    assert len(graph.ros2_nodes) == 2, f"Expected 2 nodes, got {len(graph.ros2_nodes)}"
    assert len(graph.ros2_topics) == 2, f"Expected 2 topics, got {len(graph.ros2_topics)}"

    node_names = {n.name for n in graph.ros2_nodes}
    assert "sensor_node" in node_names
    assert "control_node" in node_names

    topic_names = {t.name for t in graph.ros2_topics}
    assert "sensor_data" in topic_names
    assert "cmd_vel" in topic_names

    # sensor_data: published by sensor_node, subscribed by control_node.
    sensor_topic = next(t for t in graph.ros2_topics if t.name == "sensor_data")
    sensor_node_id = next(n.id for n in graph.ros2_nodes if n.name == "sensor_node")
    control_node_id = next(n.id for n in graph.ros2_nodes if n.name == "control_node")

    assert sensor_node_id in sensor_topic.publishers, (
        f"sensor_node should be a publisher of sensor_data. "
        f"publishers={sensor_topic.publishers}"
    )
    assert control_node_id in sensor_topic.subscribers, (
        f"control_node should be a subscriber of sensor_data. "
        f"subscribers={sensor_topic.subscribers}"
    )

    # cmd_vel: published by control_node, no subscribers.
    cmd_topic = next(t for t in graph.ros2_topics if t.name == "cmd_vel")
    assert control_node_id in cmd_topic.publishers


# ---------------------------------------------------------------------------
# 3. Validation report extraction
# ---------------------------------------------------------------------------

def test_validation_report_extraction(tmp_path):
    folder = tmp_path / "mission_validation"
    _write_fixture(folder)
    graph = build_graph(folder)

    assert graph.validation_checks, "validation_checks should be non-empty"

    check_names = [c.name for c in graph.validation_checks]
    assert "Systems Engineering" in check_names
    assert "Physics" in check_names

    # Confidence score ≥ 8.0 → PASS.
    se_check = next(c for c in graph.validation_checks if c.name == "Systems Engineering")
    assert se_check.status == "PASS", f"Expected PASS, got {se_check.status}"

    # missing_evidence entries → FAIL checks.
    fail_checks = [c for c in graph.validation_checks if c.status == "FAIL"]
    assert fail_checks, "Expected at least one FAIL check from missing_evidence"
    assert any("prototype" in c.notes.lower() for c in fail_checks)

    # Next-artifacts list populated.
    assert "ROS2 node graph diagram." in graph.next_artifacts


# ---------------------------------------------------------------------------
# 4. Missing optional files handled gracefully
# ---------------------------------------------------------------------------

def test_missing_optional_files_handled_gracefully(tmp_path):
    """Only mission_result.json present. No crash; graph still valid."""
    folder = tmp_path / "mission_sparse"
    _write_fixture(folder, include_optional=False)

    graph = build_graph(folder)

    assert isinstance(graph, MissionKnowledgeGraph)
    # Optional collections default to empty; no exception raised.
    assert graph.validation_checks == []
    assert graph.next_artifacts == []
    assert graph.provenance == []
    # Missing optional files should produce LOAD_WARNING consistency warnings.
    all_codes = [w.code for w in graph.consistency_warnings]
    assert "LOAD_WARNING" in all_codes, (
        f"Expected LOAD_WARNING for missing optional files. Got codes: {all_codes}"
    )
    # At least the validation_report.json load warning must be present.
    load_msgs = [w.message for w in graph.consistency_warnings if w.code == "LOAD_WARNING"]
    assert any("validation_report" in m for m in load_msgs), (
        f"Expected a LOAD_WARNING mentioning validation_report.json. Got: {load_msgs}"
    )


# ---------------------------------------------------------------------------
# 5. Consistency warning generation
# ---------------------------------------------------------------------------

def test_orphan_topic_warning(tmp_path):
    """A topic not referenced by any node generates ORPHAN_TOPIC warning."""
    from backend.app.mission_graph.schemas import (
        MissionKnowledgeGraph,
        Ros2Node,
        Ros2Topic,
    )

    graph = MissionKnowledgeGraph(
        graph_id="g001",
        generated_at="2026-05-24T00:00:00+00:00",
        ros2_nodes=[
            Ros2Node(id="node.sensor", name="sensor_node", publishes_to=["sensor_data"]),
        ],
        ros2_topics=[
            Ros2Topic(id="topic.sensor_data", name="sensor_data",
                      publishers=["node.sensor"], subscribers=[]),
            # orphan — no publishers, no subscribers
            Ros2Topic(id="topic.orphan", name="orphan_topic",
                      publishers=[], subscribers=[]),
        ],
    )

    warnings = check_graph(graph)
    codes = [w.code for w in warnings]
    assert "ORPHAN_TOPIC" in codes, f"Expected ORPHAN_TOPIC. Got: {codes}"
    orphan_warn = next(w for w in warnings if w.code == "ORPHAN_TOPIC")
    assert "topic.orphan" in orphan_warn.related_ids


def test_missing_requirements_warning():
    """Graph with no requirements gets MISSING_REQUIREMENTS warning."""
    from backend.app.mission_graph.schemas import MissionKnowledgeGraph

    graph = MissionKnowledgeGraph(
        graph_id="g002",
        generated_at="2026-05-24T00:00:00+00:00",
        requirements=[],
    )
    warnings = check_graph(graph)
    codes = [w.code for w in warnings]
    assert "MISSING_REQUIREMENTS" in codes


def test_validation_fail_surfaces_as_error():
    """A ValidationCheck with status=FAIL becomes a VALIDATION_FAIL error warning."""
    from backend.app.mission_graph.schemas import MissionKnowledgeGraph, ValidationCheck

    graph = MissionKnowledgeGraph(
        graph_id="g003",
        generated_at="2026-05-24T00:00:00+00:00",
        validation_checks=[
            ValidationCheck(
                id="check.000",
                name="Missing Evidence",
                status="FAIL",
                notes="No prototype data.",
            )
        ],
    )
    warnings = check_graph(graph)
    fail_warns = [w for w in warnings if w.code == "VALIDATION_FAIL"]
    assert fail_warns, "Expected VALIDATION_FAIL warning"
    assert fail_warns[0].severity == "error"
    assert "check.000" in fail_warns[0].related_ids


# ---------------------------------------------------------------------------
# 6. omni_graph.py --help
# ---------------------------------------------------------------------------

def test_omni_graph_help(capsys):
    import omni_graph

    with pytest.raises(SystemExit):
        with patch.object(sys, "argv", ["omni_graph", "--help"]):
            omni_graph.main()

    out = capsys.readouterr().out
    assert "--from" in out, f"--from not in help output:\n{out}"
    assert "--out" in out, f"--out not in help output:\n{out}"


# ---------------------------------------------------------------------------
# 7. Smoke test: write graph JSON to tmp_path
# ---------------------------------------------------------------------------

def test_smoke_write_graph_to_tmp(tmp_path):
    """
    Full pipeline: build graph from fixture folder, write to tmp_path,
    read back and verify it is valid JSON with expected keys.
    """
    folder = tmp_path / "mission_smoke"
    _write_fixture(folder)

    graph = build_graph(folder)
    out_file = tmp_path / "mission_knowledge_graph.json"
    out_file.write_text(graph.model_dump_json(indent=2), encoding="utf-8")

    assert out_file.exists()
    data = json.loads(out_file.read_text("utf-8"))

    required_keys = {
        "graph_id", "schema_version", "generated_at", "mission_id",
        "mission_text", "platform", "ros2_nodes", "ros2_topics",
        "components", "validation_checks", "consistency_warnings",
    }
    missing = required_keys - data.keys()
    assert not missing, f"Graph JSON missing keys: {missing}"

    assert isinstance(data["ros2_nodes"], list)
    assert isinstance(data["consistency_warnings"], list)
    assert data["schema_version"] == "0.1"


# ---------------------------------------------------------------------------
# Phase 5B — Graph Relationship Enrichment
# ---------------------------------------------------------------------------

def test_platform_normalized_ground_rover():
    """'rover' platform normalizes to 'ground-rover'."""
    from backend.app.mission_graph.enrichment import enrich_graph
    from backend.app.mission_graph.schemas import MissionKnowledgeGraph
    graph = MissionKnowledgeGraph(
        graph_id="e001", generated_at="2026-05-24T00:00:00+00:00",
        platform="rover",
    )
    enrich_graph(graph)
    assert graph.platform_normalized == "ground-rover"


def test_platform_normalized_unknown_slugified():
    """Unknown platform value is slugified into platform_normalized."""
    from backend.app.mission_graph.enrichment import enrich_graph
    from backend.app.mission_graph.schemas import MissionKnowledgeGraph
    graph = MissionKnowledgeGraph(
        graph_id="e002", generated_at="2026-05-24T00:00:00+00:00",
        platform="My Custom Bot",
    )
    enrich_graph(graph)
    assert graph.platform_normalized == "my-custom-bot"


def test_component_linked_to_power_rail():
    """Component with '5V' in power_notes gets power_rail_id set."""
    from backend.app.mission_graph.enrichment import enrich_graph
    from backend.app.mission_graph.schemas import Component, MissionKnowledgeGraph, PowerRail
    graph = MissionKnowledgeGraph(
        graph_id="e003", generated_at="2026-05-24T00:00:00+00:00",
        components=[Component(id="comp.000", name="MCU", power_notes="5V, 100mA")],
        power_rails=[PowerRail(id="rail.000", label="5V Rail", voltage_hint="5V")],
    )
    enrich_graph(graph)
    assert graph.components[0].power_rail_id == "rail.000"


def test_component_linked_to_data_bus():
    """Component with 'UART' in interface gets data_bus_id set."""
    from backend.app.mission_graph.enrichment import enrich_graph
    from backend.app.mission_graph.schemas import Component, DataBus, MissionKnowledgeGraph
    graph = MissionKnowledgeGraph(
        graph_id="e004", generated_at="2026-05-24T00:00:00+00:00",
        components=[Component(id="comp.000", name="GPS Module", interface="UART serial link")],
        data_buses=[DataBus(id="bus.000", label="UART Bus", protocol="UART")],
    )
    enrich_graph(graph)
    assert graph.components[0].data_bus_id == "bus.000"


def test_node_component_cross_reference():
    """Node.component_ids populated when component keyword appears in node text."""
    from backend.app.mission_graph.enrichment import enrich_graph
    from backend.app.mission_graph.schemas import Component, MissionKnowledgeGraph, Ros2Node
    graph = MissionKnowledgeGraph(
        graph_id="e005", generated_at="2026-05-24T00:00:00+00:00",
        components=[Component(id="comp.000", name="IMU Sensor", role="sensing")],
        ros2_nodes=[Ros2Node(id="node.sensor", name="sensor_node", purpose="Reads IMU data")],
    )
    enrich_graph(graph)
    assert "comp.000" in graph.ros2_nodes[0].component_ids


def test_enrich_graph_idempotent():
    """Running enrich_graph twice does not create duplicate links."""
    from backend.app.mission_graph.enrichment import enrich_graph
    from backend.app.mission_graph.schemas import (
        Component, DataBus, MissionKnowledgeGraph, PowerRail, Ros2Node,
    )
    graph = MissionKnowledgeGraph(
        graph_id="e006", generated_at="2026-05-24T00:00:00+00:00",
        components=[Component(
            id="comp.000", name="Sensor Board", role="sensing",
            power_notes="3.3V, 50mA", interface="I2C",
        )],
        power_rails=[PowerRail(id="rail.000", label="3.3V Rail", voltage_hint="3.3V")],
        data_buses=[DataBus(id="bus.000", label="I2C Bus", protocol="I2C")],
        ros2_nodes=[Ros2Node(id="node.sensor", name="sensor_node", purpose="Reads sensor data")],
    )
    enrich_graph(graph)
    enrich_graph(graph)
    comp = graph.components[0]
    node = graph.ros2_nodes[0]
    assert comp.power_rail_id == "rail.000"
    assert comp.data_bus_id == "bus.000"
    assert node.component_ids.count("comp.000") == 1


def test_enrich_empty_graph_no_crash():
    """enrich_graph on a minimal empty graph does not raise."""
    from backend.app.mission_graph.enrichment import enrich_graph
    from backend.app.mission_graph.schemas import MissionKnowledgeGraph
    graph = MissionKnowledgeGraph(
        graph_id="e007", generated_at="2026-05-24T00:00:00+00:00",
    )
    enrich_graph(graph)
    assert graph.platform_normalized == ""


def test_body_regions_inferred_from_morphology():
    """When morphology exists and body_regions is empty, regions are created."""
    from backend.app.mission_graph.enrichment import enrich_graph
    from backend.app.mission_graph.schemas import MissionKnowledgeGraph, Morphology
    graph = MissionKnowledgeGraph(
        graph_id="e008", generated_at="2026-05-24T00:00:00+00:00",
        morphology=[Morphology(id="morph.000", description="Compact 100mm chassis")],
    )
    enrich_graph(graph)
    assert graph.body_regions, "body_regions should have at least one entry after enrichment"
    assert graph.morphology[0].body_region_ids, "morph.body_region_ids should be populated"
    region_id = graph.morphology[0].body_region_ids[0]
    assert region_id in [r.id for r in graph.body_regions]


def test_enrichment_called_in_builder(tmp_path):
    """build_graph returns platform_normalized set, proving enrich_graph is wired."""
    folder = tmp_path / "mission_enrichment"
    _write_fixture(folder)
    graph = build_graph(folder)
    assert graph.platform_normalized == "ground-rover", (
        f"Expected 'ground-rover', got '{graph.platform_normalized}'"
    )
