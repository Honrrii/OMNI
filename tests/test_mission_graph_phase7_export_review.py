"""Phase 7 — Mission Knowledge Graph review export integration tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _write_mission_json(folder: Path, mission_text: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    data = {
        "mission": mission_text,
        "result_id": "phase7-test",
        "agents": {},
        "artifacts": {},
        "status": "complete",
    }
    path = folder / "mission.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Unit tests for _write_graph_review helper
# ---------------------------------------------------------------------------

def test_write_graph_review_creates_both_files(tmp_path):
    """Helper writes mission_graph.json and mission_graph_review.json."""
    folder = tmp_path / "mission"
    _write_mission_json(folder, "Build a ground rover for terrain scouting.")

    from backend.app.export.export_manager import _write_graph_review
    result = _write_graph_review(folder)

    assert (folder / "mission_graph.json").exists()
    assert (folder / "mission_graph_review.json").exists()
    assert result["status"] == "reviewed"


def test_write_graph_review_returns_paths(tmp_path):
    """Return dict includes graph_path and review_path pointing to written files."""
    folder = tmp_path / "mission"
    _write_mission_json(folder, "Build a ground rover for terrain scouting.")

    from backend.app.export.export_manager import _write_graph_review
    result = _write_graph_review(folder)

    assert Path(result["graph_path"]).exists()
    assert Path(result["review_path"]).exists()


def test_write_graph_review_json_has_required_top_level_keys(tmp_path):
    """mission_graph_review.json contains all required top-level fields."""
    folder = tmp_path / "mission"
    _write_mission_json(folder, "Build a ground rover for terrain scouting.")

    from backend.app.export.export_manager import _write_graph_review
    _write_graph_review(folder)

    review = json.loads((folder / "mission_graph_review.json").read_text())
    for key in (
        "graph_id", "platform", "platform_normalized",
        "component_coverage", "ros2_coverage", "morphology_cad_coverage",
        "issues", "warnings", "recommendations", "consistency_warnings",
    ):
        assert key in review, f"Missing key in mission_graph_review.json: {key}"


def test_write_graph_review_coverage_shape(tmp_path):
    """Coverage sub-objects have the expected field shapes."""
    folder = tmp_path / "mission"
    _write_mission_json(folder, "Build a ground rover for terrain scouting.")

    from backend.app.export.export_manager import _write_graph_review
    _write_graph_review(folder)

    review = json.loads((folder / "mission_graph_review.json").read_text())

    comp = review["component_coverage"]
    assert "total" in comp and "with_power_rail_id" in comp
    assert "with_data_bus_id" in comp and "with_body_region_id" in comp

    ros2 = review["ros2_coverage"]
    assert "total_nodes" in ros2 and "nodes_with_component_ids" in ros2

    morph = review["morphology_cad_coverage"]
    assert "total_morphology" in morph
    assert "total_body_regions" in morph
    assert "total_cad_features" in morph


def test_write_graph_review_platform_normalized_rover(tmp_path):
    """Platform 'rover' is detected from mission text and normalized."""
    folder = tmp_path / "mission"
    _write_mission_json(folder, "Build a ground rover for terrain scouting.")

    from backend.app.export.export_manager import _write_graph_review
    _write_graph_review(folder)

    review = json.loads((folder / "mission_graph_review.json").read_text())
    assert review["platform"] == "rover"
    assert review["platform_normalized"] == "ground-rover"


def test_write_graph_review_list_fields(tmp_path):
    """issues, warnings, recommendations, and consistency_warnings are lists."""
    folder = tmp_path / "mission"
    _write_mission_json(folder, "Build a ground rover for terrain scouting.")

    from backend.app.export.export_manager import _write_graph_review
    _write_graph_review(folder)

    review = json.loads((folder / "mission_graph_review.json").read_text())
    assert isinstance(review["issues"], list)
    assert isinstance(review["warnings"], list)
    assert isinstance(review["recommendations"], list)
    assert isinstance(review["consistency_warnings"], list)


def test_write_graph_review_no_mission_json_does_not_crash(tmp_path):
    """Helper handles a folder with no mission.json without raising."""
    empty_folder = tmp_path / "empty"
    empty_folder.mkdir()

    from backend.app.export.export_manager import _write_graph_review
    result = _write_graph_review(empty_folder)

    assert "status" in result


def test_write_graph_review_mission_graph_json_has_graph_id(tmp_path):
    """mission_graph.json is a valid graph dump with a graph_id."""
    folder = tmp_path / "mission"
    _write_mission_json(folder, "Build a ground rover for terrain scouting.")

    from backend.app.export.export_manager import _write_graph_review
    result = _write_graph_review(folder)

    graph_data = json.loads((folder / "mission_graph.json").read_text())
    assert "graph_id" in graph_data
    assert graph_data["graph_id"] == result["graph_id"]


def test_write_graph_review_counts_in_return(tmp_path):
    """Return dict exposes issue_count, warning_count, recommendation_count."""
    folder = tmp_path / "mission"
    _write_mission_json(folder, "Build a ground rover for terrain scouting.")

    from backend.app.export.export_manager import _write_graph_review
    result = _write_graph_review(folder)

    review = json.loads((folder / "mission_graph_review.json").read_text())
    assert result["issue_count"] == len(review["issues"])
    assert result["warning_count"] == len(review["warnings"])
    assert result["recommendation_count"] == len(review["recommendations"])


# ---------------------------------------------------------------------------
# Integration tests — full export_mission_files pipeline
# ---------------------------------------------------------------------------

def test_export_mission_files_creates_graph_review(tmp_path, monkeypatch):
    """Full export pipeline creates mission_graph_review.json in the export dir."""
    import backend.app.export.export_manager as em
    monkeypatch.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")

    mission_result = {
        "mission": "Design an autonomous navigation system for land surveying.",
        "result_id": "phase7-integration",
        "agents": {},
        "artifacts": {},
        "status": "complete",
    }

    result = em.export_mission_files(mission_result, validate_ros2=False)

    export_dir = Path(result["export_dir"])
    review_path = export_dir / "mission_graph_review.json"

    assert review_path.exists(), f"Expected {review_path} to exist"

    review = json.loads(review_path.read_text())
    assert "issues" in review
    assert "warnings" in review
    assert "recommendations" in review
    assert "consistency_warnings" in review


def test_export_mission_files_creates_mission_graph_json(tmp_path, monkeypatch):
    """Full export pipeline also writes mission_graph.json alongside the review."""
    import backend.app.export.export_manager as em
    monkeypatch.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")

    mission_result = {
        "mission": "Design an autonomous navigation system for land surveying.",
        "result_id": "phase7-graph-json",
        "agents": {},
        "artifacts": {},
        "status": "complete",
    }

    result = em.export_mission_files(mission_result, validate_ros2=False)

    export_dir = Path(result["export_dir"])
    assert (export_dir / "mission_graph.json").exists()


def test_export_mission_files_return_has_graph_review_key(tmp_path, monkeypatch):
    """export_mission_files return dict includes 'graph_review' key."""
    import backend.app.export.export_manager as em
    monkeypatch.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")

    mission_result = {
        "mission": "Design an autonomous navigation system for land surveying.",
        "result_id": "phase7-return-key",
        "agents": {},
        "artifacts": {},
        "status": "complete",
    }

    result = em.export_mission_files(mission_result, validate_ros2=False)

    assert "graph_review" in result
    gr = result["graph_review"]
    assert gr is not None
    assert gr.get("status") == "reviewed"


def test_export_mission_files_graph_review_files_in_file_list(tmp_path, monkeypatch):
    """mission_graph_review.json and mission_graph.json appear in the export files list."""
    import backend.app.export.export_manager as em
    monkeypatch.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")

    mission_result = {
        "mission": "Design an autonomous navigation system for land surveying.",
        "result_id": "phase7-file-list",
        "agents": {},
        "artifacts": {},
        "status": "complete",
    }

    result = em.export_mission_files(mission_result, validate_ros2=False)

    files = result["files"]
    assert any("mission_graph_review.json" in f for f in files)
    assert any("mission_graph.json" in f for f in files)
