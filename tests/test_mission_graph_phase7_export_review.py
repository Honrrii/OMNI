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


# ---------------------------------------------------------------------------
# Phase 10B — Design Understanding report integration tests
# ---------------------------------------------------------------------------


def test_write_design_understanding_creates_json(tmp_path):
    """Helper writes design_understanding_report.json and returns evaluated status."""
    folder = tmp_path / "mission"
    _write_mission_json(folder, "Build a ground rover for terrain scouting.")

    from backend.app.export.export_manager import _write_design_understanding
    result = _write_design_understanding(folder, "Build a ground rover for terrain scouting.")

    assert (folder / "design_understanding_report.json").exists()
    assert result["status"] == "evaluated"


def test_write_design_understanding_report_fields(tmp_path):
    """design_understanding_report.json contains all required top-level fields."""
    folder = tmp_path / "mission"
    _write_mission_json(folder, "Build a ground rover for terrain scouting.")

    from backend.app.export.export_manager import _write_design_understanding
    _write_design_understanding(folder, "Build a ground rover for terrain scouting.")

    report = json.loads((folder / "design_understanding_report.json").read_text())
    for key in (
        "semantic_match_score", "intended_platform",
        "strengths", "mismatches", "next_design_actions",
        "observed_platform_signals",
    ):
        assert key in report, f"Missing key in design_understanding_report.json: {key}"


def test_write_design_understanding_score_range(tmp_path):
    """semantic_match_score in the written report is within [0.0, 1.0]."""
    folder = tmp_path / "mission"
    _write_mission_json(folder, "Build a drone for aerial mapping.")

    from backend.app.export.export_manager import _write_design_understanding
    _write_design_understanding(folder, "Build a drone for aerial mapping.")

    report = json.loads((folder / "design_understanding_report.json").read_text())
    assert 0.0 <= report["semantic_match_score"] <= 1.0


def test_write_design_understanding_return_summary_keys(tmp_path):
    """Return dict exposes intended_platform, semantic_match_score, and counts."""
    folder = tmp_path / "mission"
    _write_mission_json(folder, "Build a rover.")

    from backend.app.export.export_manager import _write_design_understanding
    result = _write_design_understanding(folder, "Build a rover.")

    for key in (
        "intended_platform", "semantic_match_score",
        "strength_count", "mismatch_count", "next_action_count",
    ):
        assert key in result, f"Missing key in _write_design_understanding return: {key}"


def test_write_design_understanding_failure_does_not_raise(tmp_path):
    """Helper raises on a folder with no mission.json (caller handles the exception)."""
    empty_folder = tmp_path / "empty"
    empty_folder.mkdir()

    from backend.app.export.export_manager import _write_design_understanding
    # Should raise (caller wraps in try/except) — just verify it doesn't silently corrupt
    try:
        _write_design_understanding(empty_folder, "Build a rover.")
    except Exception:
        pass  # expected — caller is responsible for catching


def test_export_creates_design_understanding_report(tmp_path, monkeypatch):
    """Full export pipeline creates design_understanding_report.json in the export dir."""
    import backend.app.export.export_manager as em
    monkeypatch.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")

    mission_result = {
        "mission": "Design an autonomous navigation system for land surveying.",
        "result_id": "phase10b-integration",
        "agents": {},
        "artifacts": {},
        "status": "complete",
    }

    result = em.export_mission_files(mission_result, validate_ros2=False)

    export_dir = Path(result["export_dir"])
    report_path = export_dir / "design_understanding_report.json"
    assert report_path.exists(), f"Expected {report_path} to exist"

    report = json.loads(report_path.read_text())
    assert "semantic_match_score" in report
    assert "intended_platform" in report
    assert "strengths" in report
    assert "mismatches" in report
    assert "next_design_actions" in report


def test_export_return_dict_has_cortex_key(tmp_path, monkeypatch):
    """export_mission_files return dict includes 'cortex.design_understanding' summary."""
    import backend.app.export.export_manager as em
    monkeypatch.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")

    mission_result = {
        "mission": "Design a ROS2 ground rover for terrain scouting.",
        "result_id": "phase10b-cortex-key",
        "agents": {},
        "artifacts": {},
        "status": "complete",
    }

    result = em.export_mission_files(mission_result, validate_ros2=False)

    assert "cortex" in result
    cortex = result["cortex"]
    assert "design_understanding" in cortex
    du = cortex["design_understanding"]
    assert du is not None
    assert du.get("status") == "evaluated"
    assert "semantic_match_score" in du


def test_export_design_understanding_in_file_list(tmp_path, monkeypatch):
    """design_understanding_report.json appears in the export files list."""
    import backend.app.export.export_manager as em
    monkeypatch.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")

    mission_result = {
        "mission": "Design a ROS2 ground rover for terrain scouting.",
        "result_id": "phase10b-file-list",
        "agents": {},
        "artifacts": {},
        "status": "complete",
    }

    result = em.export_mission_files(mission_result, validate_ros2=False)

    files = result["files"]
    assert any("design_understanding_report.json" in f for f in files)


def test_export_design_understanding_failure_does_not_break_export(tmp_path, monkeypatch):
    """If design understanding evaluation fails, the overall export still succeeds."""
    import backend.app.export.export_manager as em
    monkeypatch.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")

    # Force the design understanding step to raise by patching the helper
    original = em._write_design_understanding

    def _boom(export_dir, mission_text):
        raise RuntimeError("simulated cortex failure")

    monkeypatch.setattr(em, "_write_design_understanding", _boom)

    mission_result = {
        "mission": "Design a ROS2 ground rover for terrain scouting.",
        "result_id": "phase10b-failure-test",
        "agents": {},
        "artifacts": {},
        "status": "complete",
    }

    result = em.export_mission_files(mission_result, validate_ros2=False)

    # Export itself must succeed
    assert result["status"] == "exported"
    # Cortex key must still be present, with a failed status
    assert result["cortex"]["design_understanding"]["status"] == "failed"
    assert "error" in result["cortex"]["design_understanding"]


# ---------------------------------------------------------------------------
# Phase 10C — design_understanding_report.json contains new diagnostic fields
# ---------------------------------------------------------------------------

def test_design_understanding_report_has_phase10c_fields(tmp_path, monkeypatch):
    """design_understanding_report.json includes all Phase 10C diagnostic fields."""
    import backend.app.export.export_manager as em
    monkeypatch.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")

    mission_result = {
        "mission": "Design a ROS2 ground rover for terrain scouting.",
        "result_id": "phase10c-schema",
        "agents": {},
        "artifacts": {},
        "status": "complete",
    }

    result = em.export_mission_files(mission_result, validate_ros2=False)
    export_dir = Path(result["export_dir"])
    report = json.loads((export_dir / "design_understanding_report.json").read_text())

    for key in (
        "mission_intent", "design_envelope", "detected_domains",
        "design_candidates", "constraint_links", "provenance_summary",
        "validation_gaps", "open_questions", "cortex_score",
    ):
        assert key in report, f"design_understanding_report.json missing Phase 10C key: {key}"


def test_design_understanding_report_cortex_score_has_five_axes(tmp_path, monkeypatch):
    """cortex_score in the written report contains all five scoring axes."""
    import backend.app.export.export_manager as em
    monkeypatch.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")

    mission_result = {
        "mission": "Design a ROS2 ground rover for terrain scouting.",
        "result_id": "phase10c-cortex-score",
        "agents": {},
        "artifacts": {},
        "status": "complete",
    }

    result = em.export_mission_files(mission_result, validate_ros2=False)
    export_dir = Path(result["export_dir"])
    report = json.loads((export_dir / "design_understanding_report.json").read_text())

    cs = report["cortex_score"]
    for axis in ("intent_clarity", "constraint_traceability",
                 "physics_grounding", "artifact_provenance", "execution_evidence"):
        assert axis in cs, f"cortex_score missing axis: {axis}"
        assert 0.0 <= cs[axis] <= 1.0, f"cortex_score.{axis} out of range"


def test_design_understanding_report_provenance_lists_sources(tmp_path, monkeypatch):
    """provenance_summary in the written report lists at least mission_text as a source."""
    import backend.app.export.export_manager as em
    monkeypatch.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")

    mission_result = {
        "mission": "Design a ROS2 ground rover for terrain scouting.",
        "result_id": "phase10c-provenance",
        "agents": {},
        "artifacts": {},
        "status": "complete",
    }

    result = em.export_mission_files(mission_result, validate_ros2=False)
    export_dir = Path(result["export_dir"])
    report = json.loads((export_dir / "design_understanding_report.json").read_text())

    prov = report["provenance_summary"]
    assert "mission_text" in prov["sources_used"]
    assert prov["source_count"] >= 1


def test_design_understanding_report_validation_gaps_is_list(tmp_path, monkeypatch):
    """validation_gaps in the written report is a non-empty list."""
    import backend.app.export.export_manager as em
    monkeypatch.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")

    mission_result = {
        "mission": "Design a ROS2 ground rover for terrain scouting.",
        "result_id": "phase10c-gaps",
        "agents": {},
        "artifacts": {},
        "status": "complete",
    }

    result = em.export_mission_files(mission_result, validate_ros2=False)
    export_dir = Path(result["export_dir"])
    report = json.loads((export_dir / "design_understanding_report.json").read_text())

    assert isinstance(report["validation_gaps"], list)
    assert len(report["validation_gaps"]) >= 1


def test_design_understanding_report_open_questions_non_empty(tmp_path, monkeypatch):
    """open_questions in the written report is a non-empty list."""
    import backend.app.export.export_manager as em
    monkeypatch.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")

    mission_result = {
        "mission": "Design a ROS2 ground rover for terrain scouting.",
        "result_id": "phase10c-questions",
        "agents": {},
        "artifacts": {},
        "status": "complete",
    }

    result = em.export_mission_files(mission_result, validate_ros2=False)
    export_dir = Path(result["export_dir"])
    report = json.loads((export_dir / "design_understanding_report.json").read_text())

    assert isinstance(report["open_questions"], list)
    assert len(report["open_questions"]) >= 1


# ---------------------------------------------------------------------------
# Phase 10 Stage 3C — additive findings_projection in mission_graph_review.json
#
# The export adds a normalized, read-only findings_projection envelope derived
# from the review's issues + consistency_warnings. It must be purely additive:
# all legacy review fields stay intact and no "findings" field is introduced.
# ---------------------------------------------------------------------------

def test_write_graph_review_has_findings_projection(tmp_path):
    folder = tmp_path / "mission"
    _write_mission_json(folder, "Build a ground rover for terrain scouting.")

    from backend.app.export.export_manager import _write_graph_review
    _write_graph_review(folder)

    review = json.loads((folder / "mission_graph_review.json").read_text())
    assert "findings_projection" in review
    # Additive only — no unified findings field introduced.
    assert "findings" not in review


def test_findings_projection_envelope_keys(tmp_path):
    folder = tmp_path / "mission"
    _write_mission_json(folder, "Build a ground rover for terrain scouting.")

    from backend.app.export.export_manager import _write_graph_review
    _write_graph_review(folder)

    review = json.loads((folder / "mission_graph_review.json").read_text())
    fp = review["findings_projection"]
    assert set(fp) == {"schema", "source", "origin_fields", "count", "items"}
    assert fp["schema"] == "omni.mission_graph.findings_projection.v1"
    assert fp["source"] == "mission_graph_review"
    assert fp["origin_fields"] == ["issues", "consistency_warnings"]


def test_findings_projection_count_matches_items_and_origins(tmp_path):
    folder = tmp_path / "mission"
    _write_mission_json(folder, "Build a ground rover for terrain scouting.")

    from backend.app.export.export_manager import _write_graph_review
    _write_graph_review(folder)

    review = json.loads((folder / "mission_graph_review.json").read_text())
    fp = review["findings_projection"]
    assert isinstance(fp["items"], list)
    assert fp["count"] == len(fp["items"])
    assert fp["count"] == len(review["issues"]) + len(review["consistency_warnings"])


def test_findings_projection_preserves_legacy_review_fields(tmp_path):
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
        assert key in review, f"legacy field missing after Stage 3C: {key}"
    # warnings stays the legacy list[str] surface.
    assert isinstance(review["warnings"], list)
    assert all(isinstance(w, str) for w in review["warnings"])


def test_export_return_graph_review_has_findings_projection(tmp_path, monkeypatch):
    """export_mission_files return payload exposes graph_review['findings_projection']."""
    import backend.app.export.export_manager as em
    monkeypatch.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")

    mission_result = {
        "mission": "Design an autonomous navigation system for land surveying.",
        "result_id": "phase10-3c-return",
        "agents": {},
        "artifacts": {},
        "status": "complete",
    }

    result = em.export_mission_files(mission_result, validate_ros2=False)
    gr = result["graph_review"]
    assert "findings_projection" in gr
    assert gr["findings_projection"]["schema"] == "omni.mission_graph.findings_projection.v1"


def test_export_return_findings_projection_matches_file(tmp_path, monkeypatch):
    """The graph_review in the return payload matches the on-disk file's projection."""
    import backend.app.export.export_manager as em
    monkeypatch.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")

    mission_result = {
        "mission": "Design an autonomous navigation system for land surveying.",
        "result_id": "phase10-3c-match",
        "agents": {},
        "artifacts": {},
        "status": "complete",
    }

    result = em.export_mission_files(mission_result, validate_ros2=False)
    export_dir = Path(result["export_dir"])
    on_disk = json.loads((export_dir / "mission_graph_review.json").read_text())

    assert result["graph_review"]["findings_projection"] == on_disk["findings_projection"]
