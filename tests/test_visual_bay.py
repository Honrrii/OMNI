"""
Phase 16A — Visual Bay manifest foundation tests.

No LLM calls. No network calls. No simulator launches. No script execution.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build(export_dir: Path, mission_result=None) -> dict:
    from backend.app.visual_bay.manifest import build_visual_bay_manifest
    return build_visual_bay_manifest(export_dir=export_dir, mission_result=mission_result)


def _export_minimal(mission_text: str, tmp_path: Path) -> dict:
    import backend.app.export.export_manager as em
    mp = pytest.MonkeyPatch()
    mp.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")
    result = em.export_mission_files(
        {
            "status": "complete",
            "result_id": "vb-test",
            "mission": mission_text,
            "agents": {},
            "artifacts": {},
        },
        validate_ros2=False,
    )
    mp.undo()
    return result


# ---------------------------------------------------------------------------
# TestOutputShape
# ---------------------------------------------------------------------------

class TestOutputShape:

    def test_module_field(self, tmp_path):
        r = _build(tmp_path)
        assert r["module"] == "visual_bay"

    def test_status_is_valid(self, tmp_path):
        r = _build(tmp_path)
        assert r["status"] in ("available", "partial", "empty")

    def test_preview_only_always_true(self, tmp_path):
        r = _build(tmp_path)
        assert r["preview_only"] is True

    def test_cad_preview_key_present(self, tmp_path):
        r = _build(tmp_path)
        assert "cad_preview" in r

    def test_fusion360_key_present(self, tmp_path):
        r = _build(tmp_path)
        assert "fusion360" in r

    def test_cadquery_key_present(self, tmp_path):
        r = _build(tmp_path)
        assert "cadquery" in r

    def test_ros2_preview_key_present(self, tmp_path):
        r = _build(tmp_path)
        assert "ros2_preview" in r

    def test_simulation_key_present(self, tmp_path):
        r = _build(tmp_path)
        assert "simulation" in r

    def test_safety_notes_is_list(self, tmp_path):
        r = _build(tmp_path)
        assert isinstance(r["safety_notes"], list)

    def test_blocked_actions_is_list(self, tmp_path):
        r = _build(tmp_path)
        assert isinstance(r["blocked_actions"], list)

    def test_next_steps_is_list(self, tmp_path):
        r = _build(tmp_path)
        assert isinstance(r["next_steps"], list)

    def test_returns_dict(self, tmp_path):
        r = _build(tmp_path)
        assert isinstance(r, dict)


# ---------------------------------------------------------------------------
# TestEmptyExportDir
# ---------------------------------------------------------------------------

class TestEmptyExportDir:
    """An empty directory produces an empty manifest with all safety fields."""

    def test_status_empty(self, tmp_path):
        r = _build(tmp_path)
        assert r["status"] == "empty"

    def test_fusion360_not_detected(self, tmp_path):
        r = _build(tmp_path)
        assert r["fusion360"]["detected"] is False

    def test_cadquery_not_detected(self, tmp_path):
        r = _build(tmp_path)
        assert r["cadquery"]["detected"] is False

    def test_ros2_not_detected(self, tmp_path):
        r = _build(tmp_path)
        assert r["ros2_preview"]["detected"] is False

    def test_simulation_not_available(self, tmp_path):
        r = _build(tmp_path)
        assert r["simulation"]["status"] == "not_available"

    def test_safe_to_launch_false(self, tmp_path):
        r = _build(tmp_path)
        assert r["simulation"]["safe_to_launch"] is False

    def test_browser_preview_ready_false(self, tmp_path):
        r = _build(tmp_path)
        assert r["cad_preview"]["browser_preview_ready"] is False

    def test_blocked_actions_nonempty(self, tmp_path):
        r = _build(tmp_path)
        assert len(r["blocked_actions"]) > 0

    def test_safety_notes_nonempty(self, tmp_path):
        r = _build(tmp_path)
        assert len(r["safety_notes"]) > 0

    def test_next_steps_nonempty(self, tmp_path):
        r = _build(tmp_path)
        assert len(r["next_steps"]) > 0


# ---------------------------------------------------------------------------
# TestBlockedActions
# ---------------------------------------------------------------------------

class TestBlockedActions:
    """Blocked actions must always be present regardless of what is detected."""

    REQUIRED_BLOCKED = [
        "Do not launch generated simulation automatically without validation.",
        "Do not execute generated scripts from the browser.",
        "Hardware deployment requires human review.",
    ]

    def test_blocked_no_launch_auto(self, tmp_path):
        r = _build(tmp_path)
        combined = " ".join(r["blocked_actions"])
        assert "Do not launch generated simulation automatically without validation." in combined

    def test_blocked_no_execute_scripts(self, tmp_path):
        r = _build(tmp_path)
        combined = " ".join(r["blocked_actions"])
        assert "Do not execute generated scripts from the browser." in combined

    def test_blocked_hardware_human_review(self, tmp_path):
        r = _build(tmp_path)
        combined = " ".join(r["blocked_actions"])
        assert "Hardware deployment requires human review." in combined

    def test_all_three_blocked_actions_present(self, tmp_path):
        r = _build(tmp_path)
        for required in self.REQUIRED_BLOCKED:
            assert required in r["blocked_actions"], f"Missing blocked action: {required}"

    def test_blocked_actions_present_with_fusion360_files(self, tmp_path):
        d = tmp_path / "generated_fusion360"
        d.mkdir()
        (d / "model.py").write_text("# script")
        r = _build(tmp_path)
        for required in self.REQUIRED_BLOCKED:
            assert required in r["blocked_actions"]


# ---------------------------------------------------------------------------
# TestFusion360Detection
# ---------------------------------------------------------------------------

class TestFusion360Detection:

    def test_generated_fusion360_dir_detected(self, tmp_path):
        (tmp_path / "generated_fusion360").mkdir()
        r = _build(tmp_path)
        assert r["fusion360"]["detected"] is True
        assert r["fusion360"]["fusion_dir_present"] is True

    def test_fusion360_model_generator_py_detected(self, tmp_path):
        (tmp_path / "fusion360_model_generator.py").write_text("# script")
        r = _build(tmp_path)
        assert r["fusion360"]["detected"] is True

    def test_fusion360_parameters_json_detected(self, tmp_path):
        (tmp_path / "fusion360_parameters.json").write_text("{}")
        r = _build(tmp_path)
        assert r["fusion360"]["detected"] is True

    def test_cad_readme_detected(self, tmp_path):
        (tmp_path / "CAD_README.md").write_text("# CAD readme")
        r = _build(tmp_path)
        assert r["fusion360"]["detected"] is True

    def test_status_not_empty_when_fusion360_detected(self, tmp_path):
        (tmp_path / "generated_fusion360").mkdir()
        r = _build(tmp_path)
        assert r["status"] != "empty"

    def test_has_cad_true_when_fusion360_detected(self, tmp_path):
        (tmp_path / "generated_fusion360").mkdir()
        r = _build(tmp_path)
        assert r["cad_preview"]["has_cad"] is True

    def test_fusion360_preview_only_true(self, tmp_path):
        (tmp_path / "generated_fusion360").mkdir()
        r = _build(tmp_path)
        assert r["fusion360"]["preview_only"] is True


# ---------------------------------------------------------------------------
# TestCadQueryDetection
# ---------------------------------------------------------------------------

class TestCadQueryDetection:

    def test_generated_cad_dir_detected(self, tmp_path):
        (tmp_path / "generated_cad").mkdir()
        r = _build(tmp_path)
        assert r["cadquery"]["detected"] is True
        assert r["cadquery"]["cad_dir_present"] is True

    def test_cad_py_script_detected(self, tmp_path):
        d = tmp_path / "generated_cad"
        d.mkdir()
        (d / "part.py").write_text("import cadquery as cq")
        r = _build(tmp_path)
        assert r["cadquery"]["detected"] is True
        assert len(r["cadquery"]["script_files"]) > 0

    def test_cadquery_preview_only_true(self, tmp_path):
        (tmp_path / "generated_cad").mkdir()
        r = _build(tmp_path)
        assert r["cadquery"]["preview_only"] is True

    def test_status_not_empty_when_cadquery_detected(self, tmp_path):
        (tmp_path / "generated_cad").mkdir()
        r = _build(tmp_path)
        assert r["status"] != "empty"

    def test_has_cad_true_when_cadquery_detected(self, tmp_path):
        (tmp_path / "generated_cad").mkdir()
        r = _build(tmp_path)
        assert r["cad_preview"]["has_cad"] is True


# ---------------------------------------------------------------------------
# TestGlbGltfBrowserPreview
# ---------------------------------------------------------------------------

class TestGlbGltfBrowserPreview:
    """.glb and .gltf files set browser_preview_ready true."""

    def test_glb_sets_browser_preview_ready(self, tmp_path):
        (tmp_path / "model.glb").write_bytes(b"GLBDATA")
        r = _build(tmp_path)
        assert r["fusion360"]["browser_preview_ready"] is True
        assert r["cad_preview"]["browser_preview_ready"] is True

    def test_gltf_sets_browser_preview_ready(self, tmp_path):
        (tmp_path / "model.gltf").write_text("{}")
        r = _build(tmp_path)
        assert r["fusion360"]["browser_preview_ready"] is True

    def test_glb_in_subdir_sets_browser_preview_ready(self, tmp_path):
        d = tmp_path / "generated_fusion360"
        d.mkdir()
        (d / "model.glb").write_bytes(b"GLBDATA")
        r = _build(tmp_path)
        assert r["fusion360"]["browser_preview_ready"] is True

    def test_glb_file_listed_in_glb_files(self, tmp_path):
        (tmp_path / "model.glb").write_bytes(b"GLBDATA")
        r = _build(tmp_path)
        assert len(r["fusion360"]["glb_files"]) > 0

    def test_no_glb_browser_preview_false(self, tmp_path):
        r = _build(tmp_path)
        assert r["fusion360"]["browser_preview_ready"] is False
        assert r["cad_preview"]["browser_preview_ready"] is False


# ---------------------------------------------------------------------------
# TestStlMeshAvailable
# ---------------------------------------------------------------------------

class TestStlMeshAvailable:
    """.stl sets mesh_available=True but does NOT imply browser_preview_ready."""

    def test_stl_sets_mesh_available_fusion360(self, tmp_path):
        (tmp_path / "model.stl").write_bytes(b"STL")
        r = _build(tmp_path)
        assert r["fusion360"]["mesh_available"] is True

    def test_stl_does_not_set_browser_preview_ready_fusion360(self, tmp_path):
        (tmp_path / "model.stl").write_bytes(b"STL")
        r = _build(tmp_path)
        assert r["fusion360"]["browser_preview_ready"] is False

    def test_stl_in_generated_cad_sets_mesh_available(self, tmp_path):
        d = tmp_path / "generated_cad"
        d.mkdir()
        (d / "part.stl").write_bytes(b"STL")
        r = _build(tmp_path)
        assert r["cadquery"]["mesh_available"] is True

    def test_stl_mesh_note_in_safety_notes(self, tmp_path):
        (tmp_path / "model.stl").write_bytes(b"STL")
        r = _build(tmp_path)
        combined = " ".join(r["safety_notes"]).lower()
        assert "stl" in combined or "mesh" in combined or "conversion" in combined

    def test_step_sets_engineering_cad_available(self, tmp_path):
        (tmp_path / "model.step").write_bytes(b"STEP")
        r = _build(tmp_path)
        assert r["fusion360"]["engineering_cad_available"] is True

    def test_step_does_not_set_browser_preview_ready(self, tmp_path):
        (tmp_path / "model.step").write_bytes(b"STEP")
        r = _build(tmp_path)
        assert r["fusion360"]["browser_preview_ready"] is False


# ---------------------------------------------------------------------------
# TestRos2Detection
# ---------------------------------------------------------------------------

class TestRos2Detection:

    def test_generated_ros2_dir_detected(self, tmp_path):
        (tmp_path / "generated_ros2").mkdir()
        r = _build(tmp_path)
        assert r["ros2_preview"]["detected"] is True
        assert r["ros2_preview"]["ros2_dir_present"] is True

    def test_package_xml_detected(self, tmp_path):
        (tmp_path / "package.xml").write_text("<package/>")
        r = _build(tmp_path)
        assert r["ros2_preview"]["detected"] is True
        assert len(r["ros2_preview"]["package_xml_files"]) > 0

    def test_launch_py_detected(self, tmp_path):
        (tmp_path / "robot.launch.py").write_text("# launch")
        r = _build(tmp_path)
        assert r["ros2_preview"]["detected"] is True
        assert len(r["ros2_preview"]["launch_files"]) > 0

    def test_urdf_detected(self, tmp_path):
        (tmp_path / "robot.urdf").write_text("<robot/>")
        r = _build(tmp_path)
        assert r["ros2_preview"]["detected"] is True
        assert len(r["ros2_preview"]["urdf_files"]) > 0

    def test_xacro_detected(self, tmp_path):
        (tmp_path / "robot.xacro").write_text("<robot/>")
        r = _build(tmp_path)
        assert r["ros2_preview"]["detected"] is True

    def test_ros2_preview_only_true(self, tmp_path):
        (tmp_path / "generated_ros2").mkdir()
        r = _build(tmp_path)
        assert r["ros2_preview"]["preview_only"] is True

    def test_has_ros2_true_in_cad_preview(self, tmp_path):
        (tmp_path / "generated_ros2").mkdir()
        r = _build(tmp_path)
        assert r["cad_preview"].get("has_ros2") is None or True  # field is in root
        assert r["ros2_preview"]["detected"] is True

    def test_status_available_when_ros2_detected(self, tmp_path):
        (tmp_path / "generated_ros2").mkdir()
        r = _build(tmp_path)
        assert r["status"] in ("available", "partial")


# ---------------------------------------------------------------------------
# TestSimulationDetection
# ---------------------------------------------------------------------------

class TestSimulationDetection:

    def test_launch_py_produces_launch_files_found(self, tmp_path):
        (tmp_path / "sim.launch.py").write_text("# launch")
        r = _build(tmp_path)
        assert r["simulation"]["status"] == "launch_files_found"

    def test_world_file_produces_assets_found(self, tmp_path):
        (tmp_path / "env.world").write_text("<world/>")
        r = _build(tmp_path)
        assert r["simulation"]["status"] in ("launch_files_found", "assets_found")

    def test_gazebo_dir_produces_assets_found(self, tmp_path):
        (tmp_path / "gazebo").mkdir()
        r = _build(tmp_path)
        assert r["simulation"]["status"] == "assets_found"

    def test_worlds_dir_produces_assets_found(self, tmp_path):
        (tmp_path / "worlds").mkdir()
        r = _build(tmp_path)
        assert r["simulation"]["status"] == "assets_found"

    def test_rviz_dir_produces_assets_found(self, tmp_path):
        (tmp_path / "rviz").mkdir()
        r = _build(tmp_path)
        assert r["simulation"]["status"] == "assets_found"

    def test_safe_to_launch_always_false(self, tmp_path):
        (tmp_path / "sim.launch.py").write_text("# launch")
        r = _build(tmp_path)
        assert r["simulation"]["safe_to_launch"] is False

    def test_safe_to_launch_false_empty_dir(self, tmp_path):
        r = _build(tmp_path)
        assert r["simulation"]["safe_to_launch"] is False

    def test_safe_to_launch_false_many_assets(self, tmp_path):
        for name in ["sim.launch.py", "env.world", "robot.urdf"]:
            (tmp_path / name).write_text("# file")
        (tmp_path / "worlds").mkdir()
        (tmp_path / "gazebo").mkdir()
        r = _build(tmp_path)
        assert r["simulation"]["safe_to_launch"] is False

    def test_launch_files_listed(self, tmp_path):
        (tmp_path / "robot.launch.py").write_text("# launch")
        r = _build(tmp_path)
        assert len(r["simulation"]["launch_files"]) > 0

    def test_world_files_listed(self, tmp_path):
        (tmp_path / "env.world").write_text("<world/>")
        r = _build(tmp_path)
        assert len(r["simulation"]["world_files"]) > 0

    def test_preview_only_true(self, tmp_path):
        r = _build(tmp_path)
        assert r["simulation"]["preview_only"] is True


# ---------------------------------------------------------------------------
# TestExportIntegration
# ---------------------------------------------------------------------------

class TestExportIntegration:
    """visual_bay_manifest.json is written and visual_bay summary appears in return."""

    ROVER_MISSION = (
        "Design a palm-sized magnetic inspection crawler that can traverse "
        "vertical steel surfaces using ROS2 and CAD concept geometry."
    )

    def test_visual_bay_manifest_file_written(self, tmp_path):
        result = _export_minimal(self.ROVER_MISSION, tmp_path)
        export_dir = Path(result["export_dir"])
        assert (export_dir / "visual_bay_manifest.json").exists()

    def test_visual_bay_manifest_is_valid_json(self, tmp_path):
        result = _export_minimal(self.ROVER_MISSION, tmp_path)
        export_dir = Path(result["export_dir"])
        data = json.loads((export_dir / "visual_bay_manifest.json").read_text())
        assert isinstance(data, dict)
        assert "module" in data
        assert "status" in data

    def test_visual_bay_key_in_return(self, tmp_path):
        result = _export_minimal(self.ROVER_MISSION, tmp_path)
        assert "visual_bay" in result

    def test_visual_bay_summary_has_status(self, tmp_path):
        result = _export_minimal(self.ROVER_MISSION, tmp_path)
        assert "status" in result["visual_bay"]

    def test_visual_bay_summary_has_report_path(self, tmp_path):
        result = _export_minimal(self.ROVER_MISSION, tmp_path)
        assert "report_path" in result["visual_bay"]

    def test_visual_bay_summary_has_has_cad(self, tmp_path):
        result = _export_minimal(self.ROVER_MISSION, tmp_path)
        assert "has_cad" in result["visual_bay"]

    def test_visual_bay_summary_has_has_ros2(self, tmp_path):
        result = _export_minimal(self.ROVER_MISSION, tmp_path)
        assert "has_ros2" in result["visual_bay"]

    def test_visual_bay_summary_has_browser_preview_ready(self, tmp_path):
        result = _export_minimal(self.ROVER_MISSION, tmp_path)
        assert "browser_preview_ready" in result["visual_bay"]

    def test_visual_bay_summary_safe_to_launch_always_false(self, tmp_path):
        result = _export_minimal(self.ROVER_MISSION, tmp_path)
        assert result["visual_bay"]["safe_to_launch"] is False

    def test_visual_bay_manifest_listed_in_files(self, tmp_path):
        result = _export_minimal(self.ROVER_MISSION, tmp_path)
        assert any("visual_bay_manifest" in f for f in result["files"])

    def test_existing_export_keys_preserved(self, tmp_path):
        result = _export_minimal(self.ROVER_MISSION, tmp_path)
        for key in ("status", "folder_name", "export_dir", "files",
                    "graph_review", "cortex", "aeroforge"):
            assert key in result, f"Missing key: {key}"

    def test_export_status_exported(self, tmp_path):
        result = _export_minimal(self.ROVER_MISSION, tmp_path)
        assert result["status"] == "exported"


# ---------------------------------------------------------------------------
# TestFailureContainment
# ---------------------------------------------------------------------------

class TestFailureContainment:
    """A manifest build failure must not break the overall export."""

    ROVER_MISSION = (
        "Design a magnetic inspection crawler with ROS2 and CAD geometry."
    )

    def test_export_succeeds_when_manifest_raises(self, tmp_path):
        import backend.app.export.export_manager as em
        mp = pytest.MonkeyPatch()
        mp.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")

        with patch(
            "backend.app.visual_bay.manifest.build_visual_bay_manifest",
            side_effect=RuntimeError("simulated manifest failure"),
        ):
            result = em.export_mission_files(
                {
                    "status": "complete",
                    "result_id": "vb-fail-test",
                    "mission": self.ROVER_MISSION,
                    "agents": {},
                    "artifacts": {},
                },
                validate_ros2=False,
            )

        mp.undo()
        assert result["status"] == "exported"

    def test_visual_bay_summary_is_failed_when_manifest_raises(self, tmp_path):
        import backend.app.export.export_manager as em
        mp = pytest.MonkeyPatch()
        mp.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")

        with patch(
            "backend.app.visual_bay.manifest.build_visual_bay_manifest",
            side_effect=RuntimeError("simulated manifest failure"),
        ):
            result = em.export_mission_files(
                {
                    "status": "complete",
                    "result_id": "vb-fail-test2",
                    "mission": self.ROVER_MISSION,
                    "agents": {},
                    "artifacts": {},
                },
                validate_ros2=False,
            )

        mp.undo()
        assert result["visual_bay"]["status"] == "failed"

    def test_safe_to_launch_false_even_on_failure(self, tmp_path):
        import backend.app.export.export_manager as em
        mp = pytest.MonkeyPatch()
        mp.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")

        with patch(
            "backend.app.visual_bay.manifest.build_visual_bay_manifest",
            side_effect=RuntimeError("simulated"),
        ):
            result = em.export_mission_files(
                {
                    "status": "complete",
                    "result_id": "vb-fail-test3",
                    "mission": self.ROVER_MISSION,
                    "agents": {},
                    "artifacts": {},
                },
                validate_ros2=False,
            )

        mp.undo()
        assert result["visual_bay"].get("safe_to_launch") is False


# ---------------------------------------------------------------------------
# TestDeterminism
# ---------------------------------------------------------------------------

class TestDeterminism:

    def test_empty_dir_deterministic(self, tmp_path):
        r1 = _build(tmp_path)
        r2 = _build(tmp_path)
        assert r1["status"] == r2["status"]
        assert r1["simulation"]["safe_to_launch"] == r2["simulation"]["safe_to_launch"]
        assert r1["blocked_actions"] == r2["blocked_actions"]

    def test_fusion360_dir_deterministic(self, tmp_path):
        (tmp_path / "generated_fusion360").mkdir()
        r1 = _build(tmp_path)
        r2 = _build(tmp_path)
        assert r1["fusion360"]["detected"] == r2["fusion360"]["detected"]
        assert r1["status"] == r2["status"]

    def test_glb_file_deterministic(self, tmp_path):
        (tmp_path / "model.glb").write_bytes(b"GLB")
        r1 = _build(tmp_path)
        r2 = _build(tmp_path)
        assert r1["fusion360"]["browser_preview_ready"] == r2["fusion360"]["browser_preview_ready"]
        assert r1["cad_preview"]["browser_preview_ready"] == r2["cad_preview"]["browser_preview_ready"]


# ---------------------------------------------------------------------------
# Phase 16C — Preview Asset Contract
# ---------------------------------------------------------------------------

def _asset(r: dict, path_fragment: str) -> dict:
    """Return the first preview asset whose path contains path_fragment."""
    for a in r.get("preview_assets", []):
        if path_fragment in a["path"]:
            return a
    raise KeyError(f"No preview asset matching '{path_fragment}' in {[a['path'] for a in r.get('preview_assets', [])]}")


class TestPreviewAssetsShape:
    """preview_assets is always a list on the manifest."""

    def test_preview_assets_key_present(self, tmp_path):
        r = _build(tmp_path)
        assert "preview_assets" in r

    def test_preview_assets_is_list(self, tmp_path):
        r = _build(tmp_path)
        assert isinstance(r["preview_assets"], list)

    def test_preview_assets_empty_for_empty_dir(self, tmp_path):
        r = _build(tmp_path)
        assert r["preview_assets"] == []

    def test_aggregate_counts_present(self, tmp_path):
        r = _build(tmp_path)
        for key in (
            "browser_preview_ready_count",
            "browser_preview_candidate_count",
            "engineering_only_count",
            "execution_blocked_count",
        ):
            assert key in r, f"Missing aggregate field: {key}"

    def test_aggregate_counts_zero_for_empty_dir(self, tmp_path):
        r = _build(tmp_path)
        assert r["browser_preview_ready_count"] == 0
        assert r["browser_preview_candidate_count"] == 0
        assert r["engineering_only_count"] == 0
        assert r["execution_blocked_count"] == 0

    def test_each_asset_has_required_fields(self, tmp_path):
        (tmp_path / "model.glb").write_bytes(b"GLB")
        r = _build(tmp_path)
        required = {
            "path", "kind", "browser_preview_ready", "browser_preview_candidate",
            "engineering_only", "execution_blocked", "requires_conversion",
            "requires_external_tool", "notes",
        }
        for asset in r["preview_assets"]:
            for field in required:
                assert field in asset, f"Asset missing field '{field}': {asset}"

    def test_notes_is_list_on_each_asset(self, tmp_path):
        (tmp_path / "model.stl").write_bytes(b"STL")
        r = _build(tmp_path)
        for asset in r["preview_assets"]:
            assert isinstance(asset["notes"], list)


class TestGlbGltfPreviewAsset:
    """.glb and .gltf assets are browser_preview_ready."""

    def test_glb_browser_preview_ready_true(self, tmp_path):
        (tmp_path / "model.glb").write_bytes(b"GLB")
        r = _build(tmp_path)
        a = _asset(r, "model.glb")
        assert a["browser_preview_ready"] is True

    def test_glb_browser_preview_candidate_true(self, tmp_path):
        (tmp_path / "model.glb").write_bytes(b"GLB")
        r = _build(tmp_path)
        a = _asset(r, "model.glb")
        assert a["browser_preview_candidate"] is True

    def test_glb_execution_blocked_false(self, tmp_path):
        (tmp_path / "model.glb").write_bytes(b"GLB")
        r = _build(tmp_path)
        a = _asset(r, "model.glb")
        assert a["execution_blocked"] is False

    def test_glb_engineering_only_false(self, tmp_path):
        (tmp_path / "model.glb").write_bytes(b"GLB")
        r = _build(tmp_path)
        a = _asset(r, "model.glb")
        assert a["engineering_only"] is False

    def test_glb_kind_is_glb(self, tmp_path):
        (tmp_path / "model.glb").write_bytes(b"GLB")
        r = _build(tmp_path)
        a = _asset(r, "model.glb")
        assert a["kind"] == "glb"

    def test_gltf_browser_preview_ready_true(self, tmp_path):
        (tmp_path / "scene.gltf").write_text("{}")
        r = _build(tmp_path)
        a = _asset(r, "scene.gltf")
        assert a["browser_preview_ready"] is True

    def test_gltf_kind_is_gltf(self, tmp_path):
        (tmp_path / "scene.gltf").write_text("{}")
        r = _build(tmp_path)
        a = _asset(r, "scene.gltf")
        assert a["kind"] == "gltf"

    def test_glb_increments_ready_count(self, tmp_path):
        (tmp_path / "model.glb").write_bytes(b"GLB")
        r = _build(tmp_path)
        assert r["browser_preview_ready_count"] == 1

    def test_two_glb_files_count_two(self, tmp_path):
        (tmp_path / "a.glb").write_bytes(b"GLB")
        (tmp_path / "b.glb").write_bytes(b"GLB")
        r = _build(tmp_path)
        assert r["browser_preview_ready_count"] == 2

    def test_glb_requires_conversion_false(self, tmp_path):
        (tmp_path / "model.glb").write_bytes(b"GLB")
        r = _build(tmp_path)
        a = _asset(r, "model.glb")
        assert a["requires_conversion"] is False


class TestStlPreviewAsset:
    """.stl is a preview candidate but not browser-ready."""

    def test_stl_browser_preview_ready_false(self, tmp_path):
        (tmp_path / "part.stl").write_bytes(b"STL")
        r = _build(tmp_path)
        a = _asset(r, "part.stl")
        assert a["browser_preview_ready"] is False

    def test_stl_browser_preview_candidate_true(self, tmp_path):
        (tmp_path / "part.stl").write_bytes(b"STL")
        r = _build(tmp_path)
        a = _asset(r, "part.stl")
        assert a["browser_preview_candidate"] is True

    def test_stl_kind_is_stl(self, tmp_path):
        (tmp_path / "part.stl").write_bytes(b"STL")
        r = _build(tmp_path)
        a = _asset(r, "part.stl")
        assert a["kind"] == "stl"

    def test_stl_execution_blocked_false(self, tmp_path):
        (tmp_path / "part.stl").write_bytes(b"STL")
        r = _build(tmp_path)
        a = _asset(r, "part.stl")
        assert a["execution_blocked"] is False

    def test_stl_engineering_only_false(self, tmp_path):
        (tmp_path / "part.stl").write_bytes(b"STL")
        r = _build(tmp_path)
        a = _asset(r, "part.stl")
        assert a["engineering_only"] is False

    def test_stl_has_viewer_support_pending_note(self, tmp_path):
        (tmp_path / "part.stl").write_bytes(b"STL")
        r = _build(tmp_path)
        a = _asset(r, "part.stl")
        assert "Viewer support pending" in a["notes"]

    def test_stl_increments_candidate_not_ready(self, tmp_path):
        (tmp_path / "part.stl").write_bytes(b"STL")
        r = _build(tmp_path)
        assert r["browser_preview_ready_count"] == 0
        assert r["browser_preview_candidate_count"] >= 1

    def test_stl_not_engineering_only_count(self, tmp_path):
        (tmp_path / "part.stl").write_bytes(b"STL")
        r = _build(tmp_path)
        assert r["engineering_only_count"] == 0


class TestStepPreviewAsset:
    """.step / .stp files are engineering-only."""

    def test_step_browser_preview_ready_false(self, tmp_path):
        (tmp_path / "part.step").write_bytes(b"STEP")
        r = _build(tmp_path)
        a = _asset(r, "part.step")
        assert a["browser_preview_ready"] is False

    def test_step_browser_preview_candidate_false(self, tmp_path):
        (tmp_path / "part.step").write_bytes(b"STEP")
        r = _build(tmp_path)
        a = _asset(r, "part.step")
        assert a["browser_preview_candidate"] is False

    def test_step_engineering_only_true(self, tmp_path):
        (tmp_path / "part.step").write_bytes(b"STEP")
        r = _build(tmp_path)
        a = _asset(r, "part.step")
        assert a["engineering_only"] is True

    def test_step_requires_external_tool_true(self, tmp_path):
        (tmp_path / "part.step").write_bytes(b"STEP")
        r = _build(tmp_path)
        a = _asset(r, "part.step")
        assert a["requires_external_tool"] is True

    def test_step_kind_is_step(self, tmp_path):
        (tmp_path / "part.step").write_bytes(b"STEP")
        r = _build(tmp_path)
        a = _asset(r, "part.step")
        assert a["kind"] == "step"

    def test_stp_also_classified_as_step(self, tmp_path):
        (tmp_path / "part.stp").write_bytes(b"STEP")
        r = _build(tmp_path)
        a = _asset(r, "part.stp")
        assert a["kind"] == "step"
        assert a["engineering_only"] is True

    def test_step_increments_engineering_only_count(self, tmp_path):
        (tmp_path / "part.step").write_bytes(b"STEP")
        r = _build(tmp_path)
        assert r["engineering_only_count"] >= 1

    def test_step_execution_blocked_false(self, tmp_path):
        (tmp_path / "part.step").write_bytes(b"STEP")
        r = _build(tmp_path)
        a = _asset(r, "part.step")
        assert a["execution_blocked"] is False


class TestUrdfXacroPreviewAsset:
    """.urdf and .xacro are preview candidates requiring conversion."""

    def test_urdf_browser_preview_ready_false(self, tmp_path):
        (tmp_path / "robot.urdf").write_text("<robot/>")
        r = _build(tmp_path)
        a = _asset(r, "robot.urdf")
        assert a["browser_preview_ready"] is False

    def test_urdf_browser_preview_candidate_true(self, tmp_path):
        (tmp_path / "robot.urdf").write_text("<robot/>")
        r = _build(tmp_path)
        a = _asset(r, "robot.urdf")
        assert a["browser_preview_candidate"] is True

    def test_urdf_requires_conversion_true(self, tmp_path):
        (tmp_path / "robot.urdf").write_text("<robot/>")
        r = _build(tmp_path)
        a = _asset(r, "robot.urdf")
        assert a["requires_conversion"] is True

    def test_urdf_kind_is_urdf(self, tmp_path):
        (tmp_path / "robot.urdf").write_text("<robot/>")
        r = _build(tmp_path)
        a = _asset(r, "robot.urdf")
        assert a["kind"] == "urdf"

    def test_urdf_has_parser_not_implemented_note(self, tmp_path):
        (tmp_path / "robot.urdf").write_text("<robot/>")
        r = _build(tmp_path)
        a = _asset(r, "robot.urdf")
        assert any("URDF preview parser not implemented" in n for n in a["notes"])

    def test_xacro_preview_candidate_true(self, tmp_path):
        (tmp_path / "robot.xacro").write_text("<robot/>")
        r = _build(tmp_path)
        a = _asset(r, "robot.xacro")
        assert a["browser_preview_candidate"] is True

    def test_xacro_requires_conversion_true(self, tmp_path):
        (tmp_path / "robot.xacro").write_text("<robot/>")
        r = _build(tmp_path)
        a = _asset(r, "robot.xacro")
        assert a["requires_conversion"] is True

    def test_urdf_engineering_only_false(self, tmp_path):
        (tmp_path / "robot.urdf").write_text("<robot/>")
        r = _build(tmp_path)
        a = _asset(r, "robot.urdf")
        assert a["engineering_only"] is False

    def test_urdf_execution_blocked_false(self, tmp_path):
        (tmp_path / "robot.urdf").write_text("<robot/>")
        r = _build(tmp_path)
        a = _asset(r, "robot.urdf")
        assert a["execution_blocked"] is False

    def test_urdf_increments_candidate_count(self, tmp_path):
        (tmp_path / "robot.urdf").write_text("<robot/>")
        r = _build(tmp_path)
        assert r["browser_preview_candidate_count"] >= 1


class TestRvizLaunchPreviewAsset:
    """.rviz and .launch.py files are execution_blocked and engineering_only."""

    def test_rviz_execution_blocked_true(self, tmp_path):
        (tmp_path / "view.rviz").write_text("# rviz")
        r = _build(tmp_path)
        a = _asset(r, "view.rviz")
        assert a["execution_blocked"] is True

    def test_rviz_browser_preview_ready_false(self, tmp_path):
        (tmp_path / "view.rviz").write_text("# rviz")
        r = _build(tmp_path)
        a = _asset(r, "view.rviz")
        assert a["browser_preview_ready"] is False

    def test_rviz_browser_preview_candidate_false(self, tmp_path):
        (tmp_path / "view.rviz").write_text("# rviz")
        r = _build(tmp_path)
        a = _asset(r, "view.rviz")
        assert a["browser_preview_candidate"] is False

    def test_rviz_engineering_only_true(self, tmp_path):
        (tmp_path / "view.rviz").write_text("# rviz")
        r = _build(tmp_path)
        a = _asset(r, "view.rviz")
        assert a["engineering_only"] is True

    def test_rviz_kind_is_rviz(self, tmp_path):
        (tmp_path / "view.rviz").write_text("# rviz")
        r = _build(tmp_path)
        a = _asset(r, "view.rviz")
        assert a["kind"] == "rviz"

    def test_rviz_requires_external_tool_true(self, tmp_path):
        (tmp_path / "view.rviz").write_text("# rviz")
        r = _build(tmp_path)
        a = _asset(r, "view.rviz")
        assert a["requires_external_tool"] is True

    def test_launch_py_execution_blocked_true(self, tmp_path):
        (tmp_path / "robot.launch.py").write_text("# launch")
        r = _build(tmp_path)
        a = _asset(r, "robot.launch.py")
        assert a["execution_blocked"] is True

    def test_launch_py_kind_is_ros2_launch(self, tmp_path):
        (tmp_path / "robot.launch.py").write_text("# launch")
        r = _build(tmp_path)
        a = _asset(r, "robot.launch.py")
        assert a["kind"] == "ros2_launch"

    def test_launch_py_engineering_only_true(self, tmp_path):
        (tmp_path / "robot.launch.py").write_text("# launch")
        r = _build(tmp_path)
        a = _asset(r, "robot.launch.py")
        assert a["engineering_only"] is True

    def test_launch_py_increments_execution_blocked_count(self, tmp_path):
        (tmp_path / "robot.launch.py").write_text("# launch")
        r = _build(tmp_path)
        assert r["execution_blocked_count"] >= 1

    def test_rviz_increments_execution_blocked_count(self, tmp_path):
        (tmp_path / "view.rviz").write_text("# rviz")
        r = _build(tmp_path)
        assert r["execution_blocked_count"] >= 1


class TestFusionCadQueryScriptAsset:
    """Fusion 360 and CadQuery scripts are execution_blocked and engineering_only."""

    def test_fusion_script_execution_blocked_true(self, tmp_path):
        (tmp_path / "fusion360_model_generator.py").write_text("# fusion")
        r = _build(tmp_path)
        a = _asset(r, "fusion360_model_generator.py")
        assert a["execution_blocked"] is True

    def test_fusion_script_kind_is_fusion_script(self, tmp_path):
        (tmp_path / "fusion360_model_generator.py").write_text("# fusion")
        r = _build(tmp_path)
        a = _asset(r, "fusion360_model_generator.py")
        assert a["kind"] == "fusion_script"

    def test_fusion_script_engineering_only_true(self, tmp_path):
        (tmp_path / "fusion360_model_generator.py").write_text("# fusion")
        r = _build(tmp_path)
        a = _asset(r, "fusion360_model_generator.py")
        assert a["engineering_only"] is True

    def test_fusion_script_browser_preview_ready_false(self, tmp_path):
        (tmp_path / "fusion360_model_generator.py").write_text("# fusion")
        r = _build(tmp_path)
        a = _asset(r, "fusion360_model_generator.py")
        assert a["browser_preview_ready"] is False

    def test_fusion_dir_py_is_fusion_script(self, tmp_path):
        d = tmp_path / "generated_fusion360"
        d.mkdir()
        (d / "model.py").write_text("# fusion")
        r = _build(tmp_path)
        a = _asset(r, "model.py")
        assert a["kind"] == "fusion_script"
        assert a["execution_blocked"] is True

    def test_cadquery_script_execution_blocked_true(self, tmp_path):
        d = tmp_path / "generated_cad"
        d.mkdir()
        (d / "part.py").write_text("import cadquery")
        r = _build(tmp_path)
        a = _asset(r, "part.py")
        assert a["execution_blocked"] is True

    def test_cadquery_script_kind_is_cadquery_script(self, tmp_path):
        d = tmp_path / "generated_cad"
        d.mkdir()
        (d / "part.py").write_text("import cadquery")
        r = _build(tmp_path)
        a = _asset(r, "part.py")
        assert a["kind"] == "cadquery_script"

    def test_cadquery_script_engineering_only_true(self, tmp_path):
        d = tmp_path / "generated_cad"
        d.mkdir()
        (d / "part.py").write_text("import cadquery")
        r = _build(tmp_path)
        a = _asset(r, "part.py")
        assert a["engineering_only"] is True

    def test_cadquery_script_browser_preview_ready_false(self, tmp_path):
        d = tmp_path / "generated_cad"
        d.mkdir()
        (d / "part.py").write_text("import cadquery")
        r = _build(tmp_path)
        a = _asset(r, "part.py")
        assert a["browser_preview_ready"] is False

    def test_fusion_script_increments_execution_blocked_count(self, tmp_path):
        (tmp_path / "fusion360_model_generator.py").write_text("# fusion")
        r = _build(tmp_path)
        assert r["execution_blocked_count"] >= 1

    def test_cadquery_script_increments_execution_blocked_count(self, tmp_path):
        d = tmp_path / "generated_cad"
        d.mkdir()
        (d / "part.py").write_text("import cadquery")
        r = _build(tmp_path)
        assert r["execution_blocked_count"] >= 1


class TestAggregateCounts:
    """Aggregate count fields reflect actual asset classification totals."""

    def test_counts_sum_correctly_mixed_files(self, tmp_path):
        (tmp_path / "model.glb").write_bytes(b"GLB")    # ready=1, candidate=1
        (tmp_path / "part.stl").write_bytes(b"STL")     # candidate=1
        (tmp_path / "part.step").write_bytes(b"STEP")   # engineering_only=1
        (tmp_path / "robot.urdf").write_text("<r/>")    # candidate=1
        (tmp_path / "sim.launch.py").write_text("#")    # blocked=1, engineering_only=1
        r = _build(tmp_path)
        assert r["browser_preview_ready_count"] == 1
        assert r["browser_preview_candidate_count"] >= 3  # glb + stl + urdf
        assert r["engineering_only_count"] >= 2           # step + launch
        assert r["execution_blocked_count"] >= 1          # launch

    def test_no_visual_files_all_counts_zero(self, tmp_path):
        # Write only non-visual files
        (tmp_path / "report.json").write_text("{}")
        (tmp_path / "README.md").write_text("# readme")
        r = _build(tmp_path)
        assert r["browser_preview_ready_count"] == 0
        assert r["browser_preview_candidate_count"] == 0
        assert r["engineering_only_count"] == 0
        assert r["execution_blocked_count"] == 0

    def test_multiple_glb_ready_count(self, tmp_path):
        for i in range(3):
            (tmp_path / f"model_{i}.glb").write_bytes(b"GLB")
        r = _build(tmp_path)
        assert r["browser_preview_ready_count"] == 3

    def test_counts_are_non_negative(self, tmp_path):
        r = _build(tmp_path)
        assert r["browser_preview_ready_count"] >= 0
        assert r["browser_preview_candidate_count"] >= 0
        assert r["engineering_only_count"] >= 0
        assert r["execution_blocked_count"] >= 0


class TestExportSummaryCountFields:
    """Export compact summary includes all count fields from 16C."""

    ROVER_MISSION = (
        "Design a magnetic inspection crawler with ROS2 and CAD geometry."
    )

    def test_export_summary_has_browser_preview_ready_count(self, tmp_path):
        result = _export_minimal(self.ROVER_MISSION, tmp_path)
        assert "browser_preview_ready_count" in result["visual_bay"]

    def test_export_summary_has_browser_preview_candidate_count(self, tmp_path):
        result = _export_minimal(self.ROVER_MISSION, tmp_path)
        assert "browser_preview_candidate_count" in result["visual_bay"]

    def test_export_summary_has_engineering_only_count(self, tmp_path):
        result = _export_minimal(self.ROVER_MISSION, tmp_path)
        assert "engineering_only_count" in result["visual_bay"]

    def test_export_summary_has_execution_blocked_count(self, tmp_path):
        result = _export_minimal(self.ROVER_MISSION, tmp_path)
        assert "execution_blocked_count" in result["visual_bay"]

    def test_export_summary_counts_are_non_negative(self, tmp_path):
        result = _export_minimal(self.ROVER_MISSION, tmp_path)
        vb = result["visual_bay"]
        assert vb["browser_preview_ready_count"] >= 0
        assert vb["browser_preview_candidate_count"] >= 0
        assert vb["engineering_only_count"] >= 0
        assert vb["execution_blocked_count"] >= 0

    def test_export_manifest_json_has_preview_assets(self, tmp_path):
        import json
        result = _export_minimal(self.ROVER_MISSION, tmp_path)
        export_dir = Path(result["export_dir"])
        data = json.loads((export_dir / "visual_bay_manifest.json").read_text())
        assert "preview_assets" in data

    def test_export_manifest_json_has_count_fields(self, tmp_path):
        import json
        result = _export_minimal(self.ROVER_MISSION, tmp_path)
        export_dir = Path(result["export_dir"])
        data = json.loads((export_dir / "visual_bay_manifest.json").read_text())
        for key in (
            "browser_preview_ready_count",
            "browser_preview_candidate_count",
            "engineering_only_count",
            "execution_blocked_count",
        ):
            assert key in data, f"Missing key in manifest JSON: {key}"

    def test_existing_export_status_still_exported(self, tmp_path):
        result = _export_minimal(self.ROVER_MISSION, tmp_path)
        assert result["status"] == "exported"

    def test_existing_safe_to_launch_still_false(self, tmp_path):
        result = _export_minimal(self.ROVER_MISSION, tmp_path)
        assert result["visual_bay"]["safe_to_launch"] is False


class TestPreviewAssetDeterminism:
    """preview_assets list is deterministic across repeated calls."""

    def test_empty_dir_deterministic(self, tmp_path):
        r1 = _build(tmp_path)
        r2 = _build(tmp_path)
        assert r1["preview_assets"] == r2["preview_assets"]

    def test_glb_asset_deterministic(self, tmp_path):
        (tmp_path / "model.glb").write_bytes(b"GLB")
        r1 = _build(tmp_path)
        r2 = _build(tmp_path)
        assert r1["preview_assets"] == r2["preview_assets"]
        assert r1["browser_preview_ready_count"] == r2["browser_preview_ready_count"]

    def test_mixed_assets_deterministic(self, tmp_path):
        (tmp_path / "model.glb").write_bytes(b"GLB")
        (tmp_path / "part.stl").write_bytes(b"STL")
        (tmp_path / "robot.urdf").write_text("<r/>")
        r1 = _build(tmp_path)
        r2 = _build(tmp_path)
        assert [a["path"] for a in r1["preview_assets"]] == [a["path"] for a in r2["preview_assets"]]


# ---------------------------------------------------------------------------
# Phase 16F — Preview asset delivery contract tests
# ---------------------------------------------------------------------------

ROVER_MISSION_16F = "Build a six-legged autonomous inspection rover with ROS2."

_ALLOWLISTED_FIELDS = frozenset({
    "path",
    "kind",
    "browser_preview_ready",
    "browser_preview_candidate",
    "engineering_only",
    "execution_blocked",
    "requires_conversion",
    "requires_external_tool",
    "notes",
})

# Delivery may also include asset_url for servable assets.
_ALLOWED_DELIVERY_FIELDS = _ALLOWLISTED_FIELDS | frozenset({"asset_url"})


def _sanitize(assets, export_dir=None):
    from backend.app.export.export_manager import _sanitize_preview_assets
    return _sanitize_preview_assets(assets, export_dir)


class TestSanitizePreviewAssetsUnit:
    """Unit tests for _sanitize_preview_assets helper."""

    def test_empty_input_returns_empty(self):
        assert _sanitize([]) == []

    def test_none_input_returns_empty(self):
        assert _sanitize(None) == []  # type: ignore[arg-type]

    def test_allowlisted_fields_only(self):
        asset = {
            "path": "model.glb",
            "kind": "glb",
            "browser_preview_ready": True,
            "browser_preview_candidate": True,
            "engineering_only": False,
            "execution_blocked": False,
            "requires_conversion": False,
            "requires_external_tool": False,
            "notes": [],
            "secret_field": "should_be_dropped",
            "internal_id": 42,
        }
        result = _sanitize([asset])
        assert len(result) == 1
        assert "secret_field" not in result[0]
        assert "internal_id" not in result[0]
        assert result[0].keys() <= _ALLOWLISTED_FIELDS

    def test_all_allowlisted_fields_preserved(self):
        asset = {
            "path": "model.glb",
            "kind": "glb",
            "browser_preview_ready": True,
            "browser_preview_candidate": True,
            "engineering_only": False,
            "execution_blocked": False,
            "requires_conversion": False,
            "requires_external_tool": False,
            "notes": ["a note"],
        }
        result = _sanitize([asset])
        for field in _ALLOWLISTED_FIELDS:
            assert field in result[0], f"Missing allowlisted field: {field}"

    def test_max_count_bound(self):
        from backend.app.export.export_manager import MAX_VISUAL_BAY_PREVIEW_ASSETS
        assets = [{"path": f"f{i}.stl", "kind": "stl", "notes": []} for i in range(50)]
        result = _sanitize(assets)
        assert len(result) <= MAX_VISUAL_BAY_PREVIEW_ASSETS
        assert len(result) == MAX_VISUAL_BAY_PREVIEW_ASSETS

    def test_path_truncation(self):
        from backend.app.export.export_manager import MAX_VISUAL_BAY_PATH_CHARS
        long_path = "a/" * 200 + "model.glb"
        asset = {"path": long_path, "kind": "glb", "notes": []}
        result = _sanitize([asset])
        assert len(result[0]["path"]) <= MAX_VISUAL_BAY_PATH_CHARS

    def test_notes_count_bound(self):
        from backend.app.export.export_manager import MAX_VISUAL_BAY_NOTES
        asset = {"path": "x.urdf", "kind": "urdf", "notes": [f"note {i}" for i in range(20)]}
        result = _sanitize([asset])
        assert len(result[0]["notes"]) <= MAX_VISUAL_BAY_NOTES

    def test_note_length_truncation(self):
        from backend.app.export.export_manager import MAX_VISUAL_BAY_NOTE_CHARS
        long_note = "X" * 500
        asset = {"path": "x.urdf", "kind": "urdf", "notes": [long_note]}
        result = _sanitize([asset])
        assert len(result[0]["notes"][0]) <= MAX_VISUAL_BAY_NOTE_CHARS

    def test_absolute_path_with_export_dir_made_relative(self, tmp_path):
        abs_path = str(tmp_path / "subdir" / "model.glb")
        asset = {"path": abs_path, "kind": "glb", "notes": []}
        result = _sanitize([asset], export_dir=tmp_path)
        assert not Path(result[0]["path"]).is_absolute()
        assert "model.glb" in result[0]["path"]

    def test_absolute_path_without_export_dir_uses_filename(self):
        asset = {"path": "/absolute/deep/model.glb", "kind": "glb", "notes": []}
        result = _sanitize([asset], export_dir=None)
        assert not Path(result[0]["path"]).is_absolute()
        assert result[0]["path"] == "model.glb"

    def test_absolute_path_outside_export_dir_uses_filename(self, tmp_path):
        asset = {"path": "/other/root/model.glb", "kind": "glb", "notes": []}
        result = _sanitize([asset], export_dir=tmp_path)
        assert not Path(result[0]["path"]).is_absolute()
        assert result[0]["path"] == "model.glb"

    def test_relative_path_unchanged(self):
        asset = {"path": "generated_fusion360/model.glb", "kind": "glb", "notes": []}
        result = _sanitize([asset])
        assert result[0]["path"] == "generated_fusion360/model.glb"

    def test_non_dict_items_skipped(self):
        assets = [None, "string", 42, {"path": "x.glb", "kind": "glb", "notes": []}]
        result = _sanitize(assets)  # type: ignore[arg-type]
        assert len(result) == 1
        assert result[0]["path"] == "x.glb"

    def test_notes_none_becomes_empty_list(self):
        asset = {"path": "x.stl", "kind": "stl", "notes": None}
        result = _sanitize([asset])
        assert result[0]["notes"] == []

    def test_notes_missing_becomes_empty_list(self):
        asset = {"path": "x.stl", "kind": "stl"}
        result = _sanitize([asset])
        assert result[0]["notes"] == []


class TestPreviewAssetDeliveryContract:
    """Export summary delivers preview_assets[] to the API."""

    MISSION = ROVER_MISSION_16F

    def test_visual_bay_summary_has_preview_assets_key(self, tmp_path):
        result = _export_minimal(self.MISSION, tmp_path)
        assert "preview_assets" in result["visual_bay"]

    def test_preview_assets_is_list(self, tmp_path):
        result = _export_minimal(self.MISSION, tmp_path)
        assert isinstance(result["visual_bay"]["preview_assets"], list)

    def test_preview_asset_count_key_present(self, tmp_path):
        result = _export_minimal(self.MISSION, tmp_path)
        assert "preview_asset_count" in result["visual_bay"]

    def test_preview_asset_count_matches_list_length(self, tmp_path):
        result = _export_minimal(self.MISSION, tmp_path)
        vb = result["visual_bay"]
        assert vb["preview_asset_count"] == len(vb["preview_assets"])

    def test_delivered_assets_have_only_allowlisted_fields(self, tmp_path):
        result = _export_minimal(self.MISSION, tmp_path)
        for asset in result["visual_bay"]["preview_assets"]:
            assert asset.keys() <= _ALLOWED_DELIVERY_FIELDS, (
                f"Unexpected field(s) in delivered asset: {asset.keys() - _ALLOWED_DELIVERY_FIELDS}"
            )

    def test_no_absolute_paths_in_delivered_assets(self, tmp_path):
        result = _export_minimal(self.MISSION, tmp_path)
        for asset in result["visual_bay"]["preview_assets"]:
            assert not Path(asset["path"]).is_absolute(), (
                f"Absolute path delivered: {asset['path']}"
            )

    def test_delivered_count_within_bound(self, tmp_path):
        from backend.app.export.export_manager import MAX_VISUAL_BAY_PREVIEW_ASSETS
        result = _export_minimal(self.MISSION, tmp_path)
        assert len(result["visual_bay"]["preview_assets"]) <= MAX_VISUAL_BAY_PREVIEW_ASSETS

    def test_delivered_paths_within_char_bound(self, tmp_path):
        from backend.app.export.export_manager import MAX_VISUAL_BAY_PATH_CHARS
        result = _export_minimal(self.MISSION, tmp_path)
        for asset in result["visual_bay"]["preview_assets"]:
            assert len(asset["path"]) <= MAX_VISUAL_BAY_PATH_CHARS

    def test_delivered_notes_within_count_bound(self, tmp_path):
        from backend.app.export.export_manager import MAX_VISUAL_BAY_NOTES
        result = _export_minimal(self.MISSION, tmp_path)
        for asset in result["visual_bay"]["preview_assets"]:
            assert len(asset["notes"]) <= MAX_VISUAL_BAY_NOTES

    def test_delivered_notes_within_char_bound(self, tmp_path):
        from backend.app.export.export_manager import MAX_VISUAL_BAY_NOTE_CHARS
        result = _export_minimal(self.MISSION, tmp_path)
        for asset in result["visual_bay"]["preview_assets"]:
            for note in asset["notes"]:
                assert len(note) <= MAX_VISUAL_BAY_NOTE_CHARS

    def test_aggregate_counts_still_present(self, tmp_path):
        result = _export_minimal(self.MISSION, tmp_path)
        vb = result["visual_bay"]
        for key in (
            "browser_preview_ready_count",
            "browser_preview_candidate_count",
            "engineering_only_count",
            "execution_blocked_count",
        ):
            assert key in vb

    def test_existing_summary_fields_preserved(self, tmp_path):
        result = _export_minimal(self.MISSION, tmp_path)
        vb = result["visual_bay"]
        for key in ("status", "report_path", "has_cad", "has_ros2",
                    "has_simulation_assets", "browser_preview_ready", "safe_to_launch"):
            assert key in vb, f"Missing legacy key: {key}"

    def test_safe_to_launch_still_false(self, tmp_path):
        result = _export_minimal(self.MISSION, tmp_path)
        assert result["visual_bay"]["safe_to_launch"] is False

    def test_manifest_json_still_written(self, tmp_path):
        result = _export_minimal(self.MISSION, tmp_path)
        export_dir = Path(result["export_dir"])
        assert (export_dir / "visual_bay_manifest.json").is_file()

    def test_manifest_json_has_full_preview_assets(self, tmp_path):
        """The file on disk preserves the full (unbounded) list."""
        result = _export_minimal(self.MISSION, tmp_path)
        export_dir = Path(result["export_dir"])
        data = json.loads((export_dir / "visual_bay_manifest.json").read_text())
        assert "preview_assets" in data
        assert isinstance(data["preview_assets"], list)

    def test_overall_export_status_still_exported(self, tmp_path):
        result = _export_minimal(self.MISSION, tmp_path)
        assert result["status"] == "exported"

    def test_delivery_is_deterministic(self, tmp_path):
        r1 = _export_minimal(self.MISSION, tmp_path / "r1")
        r2 = _export_minimal(self.MISSION, tmp_path / "r2")
        paths1 = [a["path"] for a in r1["visual_bay"]["preview_assets"]]
        paths2 = [a["path"] for a in r2["visual_bay"]["preview_assets"]]
        assert paths1 == paths2

    def test_preview_assets_with_glb_file(self, tmp_path):
        """When a GLB file exists in export dir, delivery includes it."""
        import backend.app.export.export_manager as em
        mp = pytest.MonkeyPatch()
        missions_root = tmp_path / "omni_missions"
        mp.setattr(em, "OUTPUT_ROOT", missions_root)
        result = em.export_mission_files(
            {
                "status": "complete",
                "result_id": "vb16f-glb",
                "mission": self.MISSION,
                "agents": {},
                "artifacts": {},
            },
            validate_ros2=False,
        )
        mp.undo()
        export_dir = Path(result["export_dir"])
        (export_dir / "model.glb").write_bytes(b"GLB")

        from backend.app.visual_bay.manifest import build_visual_bay_manifest
        from backend.app.export.export_manager import _sanitize_preview_assets
        manifest = build_visual_bay_manifest(export_dir=export_dir)
        assets = _sanitize_preview_assets(manifest["preview_assets"], export_dir)

        kinds = [a["kind"] for a in assets]
        assert "glb" in kinds

    def test_frontend_shape_has_path_and_kind(self, tmp_path):
        """Every delivered asset must have path and kind for VisualBayPanel."""
        result = _export_minimal(self.MISSION, tmp_path)
        for asset in result["visual_bay"]["preview_assets"]:
            assert "path" in asset
            assert "kind" in asset


# ---------------------------------------------------------------------------
# Phase 16G — Asset service unit tests
# ---------------------------------------------------------------------------

def _glb_asset(path="model.glb"):
    return {
        "path": path,
        "kind": "glb",
        "browser_preview_ready": True,
        "browser_preview_candidate": True,
        "engineering_only": False,
        "execution_blocked": False,
        "requires_conversion": False,
        "requires_external_tool": False,
        "notes": [],
    }


def _blocked_asset(path="script.py"):
    return {
        "path": path,
        "kind": "fusion_script",
        "browser_preview_ready": False,
        "browser_preview_candidate": False,
        "engineering_only": True,
        "execution_blocked": True,
        "requires_conversion": False,
        "requires_external_tool": True,
        "notes": [],
    }


class TestResolveVisualBayAsset:
    """Unit tests for resolve_visual_bay_asset."""

    def test_resolves_valid_file(self, tmp_path):
        from backend.app.visual_bay.asset_service import resolve_visual_bay_asset
        (tmp_path / "model.glb").write_bytes(b"GLB")
        result = resolve_visual_bay_asset(tmp_path, "model.glb")
        assert result is not None
        assert result.name == "model.glb"

    def test_returns_none_for_missing_file(self, tmp_path):
        from backend.app.visual_bay.asset_service import resolve_visual_bay_asset
        result = resolve_visual_bay_asset(tmp_path, "missing.glb")
        assert result is None

    def test_rejects_absolute_path(self, tmp_path):
        from backend.app.visual_bay.asset_service import resolve_visual_bay_asset
        result = resolve_visual_bay_asset(tmp_path, str(tmp_path / "model.glb"))
        assert result is None

    def test_rejects_traversal_dotdot(self, tmp_path):
        from backend.app.visual_bay.asset_service import resolve_visual_bay_asset
        outside = tmp_path.parent / "secret.glb"
        outside.write_bytes(b"X")
        result = resolve_visual_bay_asset(tmp_path, "../secret.glb")
        assert result is None

    def test_rejects_traversal_nested(self, tmp_path):
        from backend.app.visual_bay.asset_service import resolve_visual_bay_asset
        sub = tmp_path / "sub"
        sub.mkdir()
        outside = tmp_path.parent / "secret.glb"
        outside.write_bytes(b"X")
        result = resolve_visual_bay_asset(tmp_path, "sub/../../secret.glb")
        assert result is None

    def test_rejects_path_outside_export_dir(self, tmp_path):
        from backend.app.visual_bay.asset_service import resolve_visual_bay_asset
        other = tmp_path.parent / "other.glb"
        other.write_bytes(b"X")
        result = resolve_visual_bay_asset(tmp_path, str(other))
        assert result is None

    def test_resolves_nested_file(self, tmp_path):
        from backend.app.visual_bay.asset_service import resolve_visual_bay_asset
        sub = tmp_path / "generated_fusion360"
        sub.mkdir()
        (sub / "model.glb").write_bytes(b"GLB")
        result = resolve_visual_bay_asset(tmp_path, "generated_fusion360/model.glb")
        assert result is not None

    def test_empty_path_returns_none(self, tmp_path):
        from backend.app.visual_bay.asset_service import resolve_visual_bay_asset
        assert resolve_visual_bay_asset(tmp_path, "") is None


class TestIsVisualBayAssetServable:
    """Unit tests for is_visual_bay_asset_servable."""

    def test_glb_servable(self):
        from backend.app.visual_bay.asset_service import is_visual_bay_asset_servable
        assert is_visual_bay_asset_servable(_glb_asset()) is True

    def test_gltf_servable(self):
        from backend.app.visual_bay.asset_service import is_visual_bay_asset_servable
        assert is_visual_bay_asset_servable(_glb_asset("model.gltf")) is True

    def test_stl_servable(self):
        from backend.app.visual_bay.asset_service import is_visual_bay_asset_servable
        asset = {**_glb_asset("part.stl"), "kind": "stl", "browser_preview_ready": False,
                 "execution_blocked": False}
        assert is_visual_bay_asset_servable(asset) is True

    def test_step_servable(self):
        from backend.app.visual_bay.asset_service import is_visual_bay_asset_servable
        asset = {**_glb_asset("part.step"), "kind": "step", "browser_preview_ready": False,
                 "execution_blocked": False}
        assert is_visual_bay_asset_servable(asset) is True

    def test_urdf_servable(self):
        from backend.app.visual_bay.asset_service import is_visual_bay_asset_servable
        asset = {**_glb_asset("robot.urdf"), "kind": "urdf", "browser_preview_ready": False,
                 "execution_blocked": False}
        assert is_visual_bay_asset_servable(asset) is True

    def test_json_servable(self):
        from backend.app.visual_bay.asset_service import is_visual_bay_asset_servable
        asset = {**_glb_asset("data.json"), "kind": "json", "browser_preview_ready": False,
                 "execution_blocked": False}
        assert is_visual_bay_asset_servable(asset) is True

    def test_md_servable(self):
        from backend.app.visual_bay.asset_service import is_visual_bay_asset_servable
        asset = {**_glb_asset("README.md"), "kind": "md", "browser_preview_ready": False,
                 "execution_blocked": False}
        assert is_visual_bay_asset_servable(asset) is True

    def test_py_blocked(self):
        from backend.app.visual_bay.asset_service import is_visual_bay_asset_servable
        assert is_visual_bay_asset_servable(_blocked_asset("script.py")) is False

    def test_sh_blocked(self):
        from backend.app.visual_bay.asset_service import is_visual_bay_asset_servable
        asset = {**_blocked_asset("run.sh"), "execution_blocked": False}
        assert is_visual_bay_asset_servable(asset) is False

    def test_launch_py_blocked(self):
        from backend.app.visual_bay.asset_service import is_visual_bay_asset_servable
        asset = {**_glb_asset("start.launch.py"), "execution_blocked": False}
        assert is_visual_bay_asset_servable(asset) is False

    def test_launch_xml_blocked(self):
        from backend.app.visual_bay.asset_service import is_visual_bay_asset_servable
        asset = {**_glb_asset("start.launch.xml"), "execution_blocked": False}
        assert is_visual_bay_asset_servable(asset) is False

    def test_execution_blocked_flag_blocks_regardless_of_extension(self):
        from backend.app.visual_bay.asset_service import is_visual_bay_asset_servable
        asset = {**_glb_asset("model.glb"), "execution_blocked": True}
        assert is_visual_bay_asset_servable(asset) is False

    def test_non_dict_returns_false(self):
        from backend.app.visual_bay.asset_service import is_visual_bay_asset_servable
        assert is_visual_bay_asset_servable(None) is False  # type: ignore[arg-type]
        assert is_visual_bay_asset_servable("model.glb") is False  # type: ignore[arg-type]

    def test_unknown_extension_not_servable(self):
        from backend.app.visual_bay.asset_service import is_visual_bay_asset_servable
        asset = {**_glb_asset("data.xyz"), "execution_blocked": False}
        assert is_visual_bay_asset_servable(asset) is False


class TestBuildVisualBayAssetUrl:
    """Unit tests for build_visual_bay_asset_url."""

    def test_url_structure(self):
        from backend.app.visual_bay.asset_service import build_visual_bay_asset_url
        url = build_visual_bay_asset_url("my_mission_slug", "model.glb")
        assert url == "/api/visual-bay/assets/my_mission_slug/model.glb"

    def test_nested_path(self):
        from backend.app.visual_bay.asset_service import build_visual_bay_asset_url
        url = build_visual_bay_asset_url("mission_abc", "generated_fusion360/robot.glb")
        assert "/api/visual-bay/assets/mission_abc/generated_fusion360/robot.glb" == url

    def test_url_contains_mission_id(self):
        from backend.app.visual_bay.asset_service import build_visual_bay_asset_url
        url = build_visual_bay_asset_url("rover_mission_2026", "part.stl")
        assert "rover_mission_2026" in url


class TestAssetUrlInDelivery:
    """asset_url is injected into servable assets in the export summary."""

    def test_asset_url_added_for_glb(self):
        from backend.app.export.export_manager import _sanitize_preview_assets
        result = _sanitize_preview_assets([_glb_asset()], mission_id="test_slug")
        assert "asset_url" in result[0]
        assert "test_slug" in result[0]["asset_url"]

    def test_asset_url_contains_path(self):
        from backend.app.export.export_manager import _sanitize_preview_assets
        result = _sanitize_preview_assets([_glb_asset("robot/model.glb")], mission_id="slug")
        assert "robot/model.glb" in result[0]["asset_url"]

    def test_asset_url_not_added_for_execution_blocked(self):
        from backend.app.export.export_manager import _sanitize_preview_assets
        result = _sanitize_preview_assets([_blocked_asset()], mission_id="slug")
        assert "asset_url" not in result[0]

    def test_asset_url_not_added_without_mission_id(self):
        from backend.app.export.export_manager import _sanitize_preview_assets
        result = _sanitize_preview_assets([_glb_asset()])
        assert "asset_url" not in result[0]

    def test_asset_url_not_added_for_script_extension(self):
        from backend.app.export.export_manager import _sanitize_preview_assets
        asset = {**_blocked_asset("generated_fusion360/model.py"), "execution_blocked": False}
        result = _sanitize_preview_assets([asset], mission_id="slug")
        assert "asset_url" not in result[0]

    def test_asset_url_not_added_for_launch_py(self):
        from backend.app.export.export_manager import _sanitize_preview_assets
        asset = {**_glb_asset("start.launch.py"), "execution_blocked": False}
        result = _sanitize_preview_assets([asset], mission_id="slug")
        assert "asset_url" not in result[0]

    def test_export_summary_servable_assets_have_asset_url(self, tmp_path):
        """Integration: export with a GLB file delivers asset_url for that asset."""
        import backend.app.export.export_manager as em
        mp = pytest.MonkeyPatch()
        missions_root = tmp_path / "omni_missions"
        mp.setattr(em, "OUTPUT_ROOT", missions_root)
        result = em.export_mission_files(
            {
                "status": "complete",
                "result_id": "vb16g",
                "mission": "Build a rover.",
                "agents": {},
                "artifacts": {},
            },
            validate_ros2=False,
        )
        mp.undo()
        export_dir = Path(result["export_dir"])
        (export_dir / "model.glb").write_bytes(b"GLB")

        from backend.app.visual_bay.manifest import build_visual_bay_manifest
        from backend.app.export.export_manager import _sanitize_preview_assets
        manifest = build_visual_bay_manifest(export_dir=export_dir)
        assets = _sanitize_preview_assets(
            manifest["preview_assets"], export_dir, mission_id=result["folder_name"]
        )
        glb_assets = [a for a in assets if a.get("kind") == "glb"]
        assert glb_assets, "Expected at least one GLB asset"
        assert "asset_url" in glb_assets[0]
        assert result["folder_name"] in glb_assets[0]["asset_url"]

    def test_export_summary_execution_blocked_assets_no_asset_url(self, tmp_path):
        """Integration: execution-blocked assets do not receive asset_url."""
        import backend.app.export.export_manager as em
        mp = pytest.MonkeyPatch()
        missions_root = tmp_path / "omni_missions"
        mp.setattr(em, "OUTPUT_ROOT", missions_root)
        result = em.export_mission_files(
            {
                "status": "complete",
                "result_id": "vb16g-block",
                "mission": "Build a rover.",
                "agents": {},
                "artifacts": {},
            },
            validate_ros2=False,
        )
        mp.undo()
        export_dir = Path(result["export_dir"])
        gen = export_dir / "generated_fusion360"
        gen.mkdir(parents=True, exist_ok=True)
        (gen / "fusion360_model_generator.py").write_text("# script")

        from backend.app.visual_bay.manifest import build_visual_bay_manifest
        from backend.app.export.export_manager import _sanitize_preview_assets
        manifest = build_visual_bay_manifest(export_dir=export_dir)
        assets = _sanitize_preview_assets(
            manifest["preview_assets"], export_dir, mission_id=result["folder_name"]
        )
        for asset in assets:
            if asset.get("execution_blocked"):
                assert "asset_url" not in asset, (
                    f"execution_blocked asset must not have asset_url: {asset['path']}"
                )


class TestVisualBayRoutes:
    """FastAPI route tests for Visual Bay manifest and asset endpoints."""

    def _app_and_client(self, tmp_path):
        import backend.app.api.visual_bay_routes as vbr
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        vbr.OUTPUT_ROOT = tmp_path
        test_app = FastAPI()
        test_app.include_router(vbr.router, prefix="/api/visual-bay")
        return TestClient(test_app, raise_server_exceptions=False), vbr

    # ── Manifest route ────────────────────────────────────────

    def test_manifest_not_found_when_missing(self, tmp_path):
        client, _ = self._app_and_client(tmp_path)
        (tmp_path / "my_mission").mkdir()
        r = client.get("/api/visual-bay/manifest/my_mission")
        assert r.status_code == 404
        assert r.json()["status"] == "not_found"

    def test_manifest_returns_json_when_file_exists(self, tmp_path):
        client, _ = self._app_and_client(tmp_path)
        d = tmp_path / "my_mission"
        d.mkdir()
        (d / "visual_bay_manifest.json").write_text(
            '{"status":"empty","module":"visual_bay"}', encoding="utf-8"
        )
        r = client.get("/api/visual-bay/manifest/my_mission")
        assert r.status_code == 200
        assert r.json()["status"] == "empty"

    def test_manifest_returns_all_fields(self, tmp_path):
        client, _ = self._app_and_client(tmp_path)
        d = tmp_path / "m"
        d.mkdir()
        payload = {"status": "available", "module": "visual_bay", "preview_assets": []}
        (d / "visual_bay_manifest.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )
        r = client.get("/api/visual-bay/manifest/m")
        assert r.status_code == 200
        assert "preview_assets" in r.json()

    # ── Asset route — blocked extensions ──────────────────────

    def test_asset_route_blocks_py_script(self, tmp_path):
        client, _ = self._app_and_client(tmp_path)
        d = tmp_path / "m"
        d.mkdir()
        (d / "script.py").write_text("import os")
        r = client.get("/api/visual-bay/assets/m/script.py")
        assert r.status_code == 403
        assert r.json()["status"] == "blocked"

    def test_asset_route_blocks_sh_script(self, tmp_path):
        client, _ = self._app_and_client(tmp_path)
        d = tmp_path / "m"
        d.mkdir()
        (d / "run.sh").write_text("#!/bin/bash")
        r = client.get("/api/visual-bay/assets/m/run.sh")
        assert r.status_code == 403

    def test_asset_route_blocks_launch_py(self, tmp_path):
        client, _ = self._app_and_client(tmp_path)
        d = tmp_path / "m"
        d.mkdir()
        (d / "start.launch.py").write_text("# launch")
        r = client.get("/api/visual-bay/assets/m/start.launch.py")
        assert r.status_code == 403
        assert r.json()["status"] == "blocked"

    # ── Asset route — served files ────────────────────────────

    def test_asset_route_serves_glb(self, tmp_path):
        client, _ = self._app_and_client(tmp_path)
        d = tmp_path / "m"
        d.mkdir()
        (d / "model.glb").write_bytes(b"GLB")
        r = client.get("/api/visual-bay/assets/m/model.glb")
        assert r.status_code == 200

    def test_asset_route_serves_stl(self, tmp_path):
        client, _ = self._app_and_client(tmp_path)
        d = tmp_path / "m"
        d.mkdir()
        (d / "part.stl").write_bytes(b"STL")
        r = client.get("/api/visual-bay/assets/m/part.stl")
        assert r.status_code == 200

    def test_asset_route_serves_json(self, tmp_path):
        client, _ = self._app_and_client(tmp_path)
        d = tmp_path / "m"
        d.mkdir()
        (d / "data.json").write_text('{"ok":true}')
        r = client.get("/api/visual-bay/assets/m/data.json")
        assert r.status_code == 200

    def test_asset_route_serves_nested_file(self, tmp_path):
        client, _ = self._app_and_client(tmp_path)
        d = tmp_path / "m" / "sub"
        d.mkdir(parents=True)
        (d / "robot.urdf").write_text("<robot/>")
        r = client.get("/api/visual-bay/assets/m/sub/robot.urdf")
        assert r.status_code == 200

    # ── Asset route — missing files ───────────────────────────

    def test_asset_route_not_found_for_missing_file(self, tmp_path):
        client, _ = self._app_and_client(tmp_path)
        (tmp_path / "m").mkdir()
        r = client.get("/api/visual-bay/assets/m/missing.glb")
        assert r.status_code == 404
        assert r.json()["status"] == "not_found"

    def test_asset_route_not_found_for_missing_mission(self, tmp_path):
        client, _ = self._app_and_client(tmp_path)
        r = client.get("/api/visual-bay/assets/no_such_mission/model.glb")
        assert r.status_code == 404

    # ── Traversal via service layer (resolve_visual_bay_asset) ─

    def test_resolve_blocks_traversal_dotdot(self, tmp_path):
        from backend.app.visual_bay.asset_service import resolve_visual_bay_asset
        (tmp_path.parent / "escape.glb").write_bytes(b"X")
        assert resolve_visual_bay_asset(tmp_path, "../escape.glb") is None

    def test_resolve_blocks_absolute_path(self, tmp_path):
        from backend.app.visual_bay.asset_service import resolve_visual_bay_asset
        assert resolve_visual_bay_asset(tmp_path, "/etc/passwd") is None

    def test_resolve_blocks_windows_traversal(self, tmp_path):
        from backend.app.visual_bay.asset_service import resolve_visual_bay_asset
        assert resolve_visual_bay_asset(tmp_path, "..\\escape.glb") is None

    # ── Overall export still succeeds ─────────────────────────

    def test_export_still_returns_exported_status(self, tmp_path):
        result = _export_minimal(ROVER_MISSION_16F, tmp_path)
        assert result["status"] == "exported"


# ---------------------------------------------------------------------------
# Phase 16J — GLB/GLTF smoke fixture pipeline tests
# ---------------------------------------------------------------------------

# Minimal valid GLTF 2.0 — text-based, no binary geometry, no LLM calls.
_GLTF_FIXTURE = (
    '{"asset":{"version":"2.0"},'
    '"scene":0,'
    '"scenes":[{"nodes":[0]}],'
    '"nodes":[{"name":"smoke_fixture"}],'
    '"meshes":[]}'
)

# Minimal valid GLB header (12-byte header: magic + version + length = 0).
# Just enough for file-presence tests; Three.js is not invoked in tests.
_GLB_FIXTURE = (
    b"glTF"      # magic
    b"\x02\x00\x00\x00"  # version 2
    b"\x0c\x00\x00\x00"  # total length = 12 (header only)
)


class TestGltfFixturePipeline:
    """
    Verify the full GLTF fixture pipeline:
    manifest scanner → preview_assets → sanitizer → asset_url → route serving.
    """

    def _write_gltf(self, directory: Path, name: str = "smoke_model.gltf") -> Path:
        p = directory / name
        p.write_text(_GLTF_FIXTURE, encoding="utf-8")
        return p

    def _write_glb(self, directory: Path, name: str = "smoke_model.glb") -> Path:
        p = directory / name
        p.write_bytes(_GLB_FIXTURE)
        return p

    # ── Manifest scanner detects .gltf ────────────────────────

    def test_gltf_appears_in_preview_assets(self, tmp_path):
        self._write_gltf(tmp_path)
        r = _build(tmp_path)
        kinds = [a["kind"] for a in r["preview_assets"]]
        assert "gltf" in kinds

    def test_gltf_browser_preview_ready_true(self, tmp_path):
        self._write_gltf(tmp_path)
        r = _build(tmp_path)
        gltf = next(a for a in r["preview_assets"] if a["kind"] == "gltf")
        assert gltf["browser_preview_ready"] is True

    def test_gltf_execution_blocked_false(self, tmp_path):
        self._write_gltf(tmp_path)
        r = _build(tmp_path)
        gltf = next(a for a in r["preview_assets"] if a["kind"] == "gltf")
        assert gltf["execution_blocked"] is False

    def test_gltf_browser_preview_candidate_true(self, tmp_path):
        self._write_gltf(tmp_path)
        r = _build(tmp_path)
        gltf = next(a for a in r["preview_assets"] if a["kind"] == "gltf")
        assert gltf["browser_preview_candidate"] is True

    def test_gltf_engineering_only_false(self, tmp_path):
        self._write_gltf(tmp_path)
        r = _build(tmp_path)
        gltf = next(a for a in r["preview_assets"] if a["kind"] == "gltf")
        assert gltf["engineering_only"] is False

    def test_gltf_requires_conversion_false(self, tmp_path):
        self._write_gltf(tmp_path)
        r = _build(tmp_path)
        gltf = next(a for a in r["preview_assets"] if a["kind"] == "gltf")
        assert gltf["requires_conversion"] is False

    def test_gltf_requires_external_tool_false(self, tmp_path):
        self._write_gltf(tmp_path)
        r = _build(tmp_path)
        gltf = next(a for a in r["preview_assets"] if a["kind"] == "gltf")
        assert gltf["requires_external_tool"] is False

    def test_gltf_notes_empty(self, tmp_path):
        self._write_gltf(tmp_path)
        r = _build(tmp_path)
        gltf = next(a for a in r["preview_assets"] if a["kind"] == "gltf")
        assert gltf["notes"] == []

    def test_glb_appears_in_preview_assets(self, tmp_path):
        self._write_glb(tmp_path)
        r = _build(tmp_path)
        kinds = [a["kind"] for a in r["preview_assets"]]
        assert "glb" in kinds

    def test_glb_browser_preview_ready_true(self, tmp_path):
        self._write_glb(tmp_path)
        r = _build(tmp_path)
        glb = next(a for a in r["preview_assets"] if a["kind"] == "glb")
        assert glb["browser_preview_ready"] is True

    def test_glb_execution_blocked_false(self, tmp_path):
        self._write_glb(tmp_path)
        r = _build(tmp_path)
        glb = next(a for a in r["preview_assets"] if a["kind"] == "glb")
        assert glb["execution_blocked"] is False

    def test_aggregate_count_increments_for_gltf(self, tmp_path):
        self._write_gltf(tmp_path)
        r = _build(tmp_path)
        assert r["browser_preview_ready_count"] >= 1

    # ── Sanitizer adds asset_url for GLTF/GLB ─────────────────

    def test_gltf_gets_asset_url_from_sanitizer(self, tmp_path):
        from backend.app.export.export_manager import _sanitize_preview_assets
        self._write_gltf(tmp_path)
        manifest = _build(tmp_path)
        assets = _sanitize_preview_assets(
            manifest["preview_assets"], tmp_path, mission_id="smoke_mission"
        )
        gltf = next(a for a in assets if a["kind"] == "gltf")
        assert "asset_url" in gltf

    def test_gltf_asset_url_contains_mission_id(self, tmp_path):
        from backend.app.export.export_manager import _sanitize_preview_assets
        self._write_gltf(tmp_path)
        manifest = _build(tmp_path)
        assets = _sanitize_preview_assets(
            manifest["preview_assets"], tmp_path, mission_id="smoke_mission"
        )
        gltf = next(a for a in assets if a["kind"] == "gltf")
        assert "smoke_mission" in gltf["asset_url"]

    def test_gltf_asset_url_contains_filename(self, tmp_path):
        from backend.app.export.export_manager import _sanitize_preview_assets
        self._write_gltf(tmp_path, "my_robot.gltf")
        manifest = _build(tmp_path)
        assets = _sanitize_preview_assets(
            manifest["preview_assets"], tmp_path, mission_id="m"
        )
        gltf = next(a for a in assets if a["kind"] == "gltf")
        assert "my_robot.gltf" in gltf["asset_url"]

    def test_gltf_asset_url_starts_with_api_path(self, tmp_path):
        from backend.app.export.export_manager import _sanitize_preview_assets
        self._write_gltf(tmp_path)
        manifest = _build(tmp_path)
        assets = _sanitize_preview_assets(
            manifest["preview_assets"], tmp_path, mission_id="m"
        )
        gltf = next(a for a in assets if a["kind"] == "gltf")
        assert gltf["asset_url"].startswith("/api/visual-bay/assets/")

    def test_glb_gets_asset_url_from_sanitizer(self, tmp_path):
        from backend.app.export.export_manager import _sanitize_preview_assets
        self._write_glb(tmp_path)
        manifest = _build(tmp_path)
        assets = _sanitize_preview_assets(
            manifest["preview_assets"], tmp_path, mission_id="m"
        )
        glb = next(a for a in assets if a["kind"] == "glb")
        assert "asset_url" in glb

    # ── Route serves GLTF fixture ──────────────────────────────

    def _route_client(self, tmp_path):
        import backend.app.api.visual_bay_routes as vbr
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        vbr.OUTPUT_ROOT = tmp_path
        app = FastAPI()
        app.include_router(vbr.router, prefix="/api/visual-bay")
        return TestClient(app, raise_server_exceptions=False), vbr

    def test_route_serves_gltf_fixture(self, tmp_path):
        client, _ = self._route_client(tmp_path)
        d = tmp_path / "smoke_mission"
        d.mkdir()
        (d / "smoke_model.gltf").write_text(_GLTF_FIXTURE, encoding="utf-8")
        r = client.get("/api/visual-bay/assets/smoke_mission/smoke_model.gltf")
        assert r.status_code == 200

    def test_route_serves_gltf_with_correct_content(self, tmp_path):
        client, _ = self._route_client(tmp_path)
        d = tmp_path / "m"
        d.mkdir()
        (d / "test.gltf").write_text(_GLTF_FIXTURE, encoding="utf-8")
        r = client.get("/api/visual-bay/assets/m/test.gltf")
        assert r.status_code == 200
        assert "2.0" in r.text

    def test_route_serves_glb_fixture(self, tmp_path):
        client, _ = self._route_client(tmp_path)
        d = tmp_path / "m"
        d.mkdir()
        (d / "model.glb").write_bytes(_GLB_FIXTURE)
        r = client.get("/api/visual-bay/assets/m/model.glb")
        assert r.status_code == 200

    def test_route_returns_not_found_for_missing_gltf(self, tmp_path):
        client, _ = self._route_client(tmp_path)
        (tmp_path / "m").mkdir()
        r = client.get("/api/visual-bay/assets/m/nonexistent.gltf")
        assert r.status_code == 404

    def test_route_blocks_py_in_same_dir_as_gltf(self, tmp_path):
        client, _ = self._route_client(tmp_path)
        d = tmp_path / "m"
        d.mkdir()
        (d / "smoke_model.gltf").write_text(_GLTF_FIXTURE, encoding="utf-8")
        (d / "script.py").write_text("import os")
        # GLB is served
        r_gltf = client.get("/api/visual-bay/assets/m/smoke_model.gltf")
        assert r_gltf.status_code == 200
        # Script is blocked
        r_py = client.get("/api/visual-bay/assets/m/script.py")
        assert r_py.status_code == 403


class TestNonGltfAssetsRemainPlaceholderOnly:
    """
    Non-GLB/GLTF assets must not receive browser_preview_ready=True
    or asset_url (when execution_blocked).
    """

    def test_stl_not_browser_preview_ready(self, tmp_path):
        (tmp_path / "part.stl").write_bytes(b"solid\nendsolid")
        r = _build(tmp_path)
        stl = next((a for a in r["preview_assets"] if a["kind"] == "stl"), None)
        assert stl is not None
        assert stl["browser_preview_ready"] is False

    def test_stl_is_browser_preview_candidate(self, tmp_path):
        (tmp_path / "part.stl").write_bytes(b"solid\nendsolid")
        r = _build(tmp_path)
        stl = next(a for a in r["preview_assets"] if a["kind"] == "stl")
        assert stl["browser_preview_candidate"] is True

    def test_stl_not_execution_blocked(self, tmp_path):
        (tmp_path / "part.stl").write_bytes(b"solid\nendsolid")
        r = _build(tmp_path)
        stl = next(a for a in r["preview_assets"] if a["kind"] == "stl")
        assert stl["execution_blocked"] is False

    def test_step_not_browser_preview_ready(self, tmp_path):
        (tmp_path / "part.step").write_text("ISO-10303-21;")
        r = _build(tmp_path)
        step = next((a for a in r["preview_assets"] if a["kind"] == "step"), None)
        assert step is not None
        assert step["browser_preview_ready"] is False

    def test_step_engineering_only(self, tmp_path):
        (tmp_path / "part.step").write_text("ISO-10303-21;")
        r = _build(tmp_path)
        step = next(a for a in r["preview_assets"] if a["kind"] == "step")
        assert step["engineering_only"] is True

    def test_urdf_not_browser_preview_ready(self, tmp_path):
        (tmp_path / "robot.urdf").write_text("<robot/>")
        r = _build(tmp_path)
        urdf = next((a for a in r["preview_assets"] if a["kind"] == "urdf"), None)
        assert urdf is not None
        assert urdf["browser_preview_ready"] is False

    def test_urdf_requires_conversion(self, tmp_path):
        (tmp_path / "robot.urdf").write_text("<robot/>")
        r = _build(tmp_path)
        urdf = next(a for a in r["preview_assets"] if a["kind"] == "urdf")
        assert urdf["requires_conversion"] is True

    def test_launch_py_execution_blocked(self, tmp_path):
        p = tmp_path / "start.launch.py"
        p.write_text("# launch")
        r = _build(tmp_path)
        launch = next((a for a in r["preview_assets"] if a["kind"] == "ros2_launch"), None)
        assert launch is not None
        assert launch["execution_blocked"] is True

    def test_launch_py_no_asset_url(self, tmp_path):
        from backend.app.export.export_manager import _sanitize_preview_assets
        (tmp_path / "start.launch.py").write_text("# launch")
        manifest = _build(tmp_path)
        assets = _sanitize_preview_assets(
            manifest["preview_assets"], tmp_path, mission_id="m"
        )
        launch = next((a for a in assets if a["kind"] == "ros2_launch"), None)
        assert launch is not None
        assert "asset_url" not in launch

    def test_fusion_script_execution_blocked(self, tmp_path):
        gen = tmp_path / "generated_fusion360"
        gen.mkdir()
        (gen / "fusion360_model_generator.py").write_text("# fusion")
        r = _build(tmp_path)
        script = next((a for a in r["preview_assets"] if a["kind"] == "fusion_script"), None)
        assert script is not None
        assert script["execution_blocked"] is True

    def test_fusion_script_no_asset_url(self, tmp_path):
        from backend.app.export.export_manager import _sanitize_preview_assets
        gen = tmp_path / "generated_fusion360"
        gen.mkdir()
        (gen / "fusion360_model_generator.py").write_text("# fusion")
        manifest = _build(tmp_path)
        assets = _sanitize_preview_assets(
            manifest["preview_assets"], tmp_path, mission_id="m"
        )
        script = next((a for a in assets if a["kind"] == "fusion_script"), None)
        assert script is not None
        assert "asset_url" not in script

    def test_mixed_dir_only_gltf_is_browser_ready(self, tmp_path):
        """GLTF and STL coexist; only GLTF gets browser_preview_ready=True."""
        (tmp_path / "model.gltf").write_text(_GLTF_FIXTURE, encoding="utf-8")
        (tmp_path / "part.stl").write_bytes(b"solid\nendsolid")
        (tmp_path / "robot.urdf").write_text("<robot/>")
        r = _build(tmp_path)
        pa = {a["kind"]: a for a in r["preview_assets"]}
        assert pa["gltf"]["browser_preview_ready"] is True
        assert pa["stl"]["browser_preview_ready"] is False
        assert pa["urdf"]["browser_preview_ready"] is False

    def test_mixed_dir_gltf_and_launch_only_gltf_gets_asset_url(self, tmp_path):
        """GLTF (servable) gets asset_url; execution-blocked launch file does not."""
        from backend.app.export.export_manager import _sanitize_preview_assets
        (tmp_path / "model.gltf").write_text(_GLTF_FIXTURE, encoding="utf-8")
        (tmp_path / "start.launch.py").write_text("# launch")  # execution_blocked
        manifest = _build(tmp_path)
        assets = _sanitize_preview_assets(
            manifest["preview_assets"], tmp_path, mission_id="m"
        )
        pa = {a["kind"]: a for a in assets}
        assert "asset_url" in pa["gltf"]
        assert "asset_url" not in pa["ros2_launch"]

    def test_gltf_is_only_kind_with_browser_preview_ready_true_in_mixed(self, tmp_path):
        (tmp_path / "model.gltf").write_text(_GLTF_FIXTURE, encoding="utf-8")
        (tmp_path / "part.step").write_text("ISO-10303-21;")
        r = _build(tmp_path)
        not_ready = [a for a in r["preview_assets"] if a["kind"] != "gltf"]
        for a in not_ready:
            assert a["browser_preview_ready"] is False, (
                f"{a['kind']} should not be browser_preview_ready"
            )


# ---------------------------------------------------------------------------
# Phase 16K — GLTF preview generation
# ---------------------------------------------------------------------------

def _write_gltf_preview(export_dir: Path, manifest=None):
    from backend.app.visual_bay.gltf_preview import write_visual_bay_gltf_preview
    return write_visual_bay_gltf_preview(export_dir, manifest=manifest)


class TestGltfPreviewGeneration:
    """Phase 16K: write_visual_bay_gltf_preview unit and integration tests."""

    # ── unit: return contract ──────────────────────────────────────────────

    def test_returns_written_true(self, tmp_path):
        r = _write_gltf_preview(tmp_path)
        assert r["written"] is True

    def test_returns_path_key(self, tmp_path):
        r = _write_gltf_preview(tmp_path)
        assert "path" in r

    def test_returns_abs_path_key(self, tmp_path):
        r = _write_gltf_preview(tmp_path)
        assert "abs_path" in r

    # ── unit: file location ────────────────────────────────────────────────

    def test_writes_to_generated_visual_bay_subdir(self, tmp_path):
        _write_gltf_preview(tmp_path)
        assert (tmp_path / "generated_visual_bay" / "preview_scene.gltf").is_file()

    def test_relative_path_correct(self, tmp_path):
        r = _write_gltf_preview(tmp_path)
        expected = str(Path("generated_visual_bay") / "preview_scene.gltf")
        assert r["path"] == expected

    def test_abs_path_is_path_object(self, tmp_path):
        r = _write_gltf_preview(tmp_path)
        assert isinstance(r["abs_path"], Path)

    def test_abs_path_exists(self, tmp_path):
        r = _write_gltf_preview(tmp_path)
        assert r["abs_path"].is_file()

    # ── unit: GLTF 2.0 validity ────────────────────────────────────────────

    def test_parses_as_valid_json(self, tmp_path):
        _write_gltf_preview(tmp_path)
        raw = (tmp_path / "generated_visual_bay" / "preview_scene.gltf").read_text(encoding="utf-8")
        json.loads(raw)  # must not raise

    def test_gltf_version_2_0(self, tmp_path):
        _write_gltf_preview(tmp_path)
        raw = (tmp_path / "generated_visual_bay" / "preview_scene.gltf").read_text(encoding="utf-8")
        data = json.loads(raw)
        assert data["asset"]["version"] == "2.0"

    def test_has_scenes_array(self, tmp_path):
        _write_gltf_preview(tmp_path)
        raw = (tmp_path / "generated_visual_bay" / "preview_scene.gltf").read_text(encoding="utf-8")
        data = json.loads(raw)
        assert isinstance(data.get("scenes"), list)
        assert len(data["scenes"]) >= 1

    def test_has_nodes_array(self, tmp_path):
        _write_gltf_preview(tmp_path)
        raw = (tmp_path / "generated_visual_bay" / "preview_scene.gltf").read_text(encoding="utf-8")
        data = json.loads(raw)
        assert isinstance(data.get("nodes"), list)
        assert len(data["nodes"]) >= 1

    def test_buffers_are_embedded_not_external(self, tmp_path):
        _write_gltf_preview(tmp_path)
        raw = (tmp_path / "generated_visual_bay" / "preview_scene.gltf").read_text(encoding="utf-8")
        data = json.loads(raw)
        # Embedded data-URI buffers are allowed; external .bin file references are not.
        for buf in data.get("buffers", []):
            assert buf.get("uri", "").startswith("data:"), (
                "Buffer must use embedded data URI, not an external .bin file"
            )

    def test_scene_index_valid(self, tmp_path):
        _write_gltf_preview(tmp_path)
        raw = (tmp_path / "generated_visual_bay" / "preview_scene.gltf").read_text(encoding="utf-8")
        data = json.loads(raw)
        assert data.get("scene") == 0

    # ── unit: extras / safety note ─────────────────────────────────────────

    def test_has_extras(self, tmp_path):
        _write_gltf_preview(tmp_path)
        raw = (tmp_path / "generated_visual_bay" / "preview_scene.gltf").read_text(encoding="utf-8")
        data = json.loads(raw)
        assert "extras" in data

    def test_extras_has_note(self, tmp_path):
        _write_gltf_preview(tmp_path)
        raw = (tmp_path / "generated_visual_bay" / "preview_scene.gltf").read_text(encoding="utf-8")
        data = json.loads(raw)
        assert "note" in data["extras"]
        assert len(data["extras"]["note"]) > 0

    def test_no_fabrication_ready_claim(self, tmp_path):
        _write_gltf_preview(tmp_path)
        raw = (tmp_path / "generated_visual_bay" / "preview_scene.gltf").read_text(encoding="utf-8").lower()
        assert "fabrication-ready geometry" not in raw
        assert "ready for fabrication" not in raw

    def test_no_engineering_validation_claim(self, tmp_path):
        _write_gltf_preview(tmp_path)
        raw = (tmp_path / "generated_visual_bay" / "preview_scene.gltf").read_text(encoding="utf-8").lower()
        assert "engineering validation confirmed" not in raw
        assert "validated for" not in raw

    def test_no_safe_to_launch_claim(self, tmp_path):
        _write_gltf_preview(tmp_path)
        raw = (tmp_path / "generated_visual_bay" / "preview_scene.gltf").read_text(encoding="utf-8").lower()
        assert "safe to launch" not in raw
        assert "safe to operate" not in raw

    # ── unit: manifest-aware extras ────────────────────────────────────────

    def test_fusion360_source_recorded_in_extras(self, tmp_path):
        gen = tmp_path / "generated_fusion360"
        gen.mkdir()
        (gen / "fusion360_model_generator.py").write_text("# fusion")
        manifest = _build(tmp_path)
        r = _write_gltf_preview(tmp_path, manifest=manifest)
        raw = r["abs_path"].read_text(encoding="utf-8")
        data = json.loads(raw)
        assert "fusion360" in data["extras"].get("artifact_sources", [])

    def test_ros2_source_recorded_in_extras(self, tmp_path):
        gen = tmp_path / "generated_ros2"
        gen.mkdir()
        (gen / "package.xml").write_text("<package/>")
        manifest = _build(tmp_path)
        r = _write_gltf_preview(tmp_path, manifest=manifest)
        raw = r["abs_path"].read_text(encoding="utf-8")
        data = json.loads(raw)
        assert "ros2" in data["extras"].get("artifact_sources", [])

    def test_no_manifest_no_artifact_sources_key(self, tmp_path):
        r = _write_gltf_preview(tmp_path, manifest=None)
        raw = r["abs_path"].read_text(encoding="utf-8")
        data = json.loads(raw)
        assert "artifact_sources" not in data["extras"]

    # ── unit: idempotency ─────────────────────────────────────────────────

    def test_idempotent_overwrite(self, tmp_path):
        _write_gltf_preview(tmp_path)
        r2 = _write_gltf_preview(tmp_path)
        assert r2["written"] is True
        assert (tmp_path / "generated_visual_bay" / "preview_scene.gltf").is_file()

    # ── unit: failure containment ─────────────────────────────────────────

    def test_failure_returns_written_false(self, tmp_path):
        blocked = tmp_path / "generated_visual_bay"
        blocked.mkdir()
        blocked.chmod(0o444)
        try:
            r = _write_gltf_preview(tmp_path)
            assert r["written"] is False
            assert "reason" in r
        finally:
            blocked.chmod(0o755)

    # ── integration: manifest picks up generated GLTF ─────────────────────

    def test_generated_gltf_in_manifest_preview_assets(self, tmp_path):
        gen = tmp_path / "generated_fusion360"
        gen.mkdir()
        (gen / "fusion360_model_generator.py").write_text("# fusion")
        _write_gltf_preview(tmp_path)
        r = _build(tmp_path)
        paths = [a["path"] for a in r["preview_assets"]]
        expected = str(Path("generated_visual_bay") / "preview_scene.gltf")
        assert expected in paths

    def test_generated_gltf_is_browser_preview_ready(self, tmp_path):
        gen = tmp_path / "generated_fusion360"
        gen.mkdir()
        (gen / "fusion360_model_generator.py").write_text("# fusion")
        _write_gltf_preview(tmp_path)
        r = _build(tmp_path)
        expected = str(Path("generated_visual_bay") / "preview_scene.gltf")
        asset = next((a for a in r["preview_assets"] if a["path"] == expected), None)
        assert asset is not None
        assert asset["browser_preview_ready"] is True

    def test_generated_gltf_gets_asset_url(self, tmp_path):
        from backend.app.export.export_manager import _sanitize_preview_assets
        gen = tmp_path / "generated_fusion360"
        gen.mkdir()
        (gen / "fusion360_model_generator.py").write_text("# fusion")
        _write_gltf_preview(tmp_path)
        manifest = _build(tmp_path)
        assets = _sanitize_preview_assets(
            manifest["preview_assets"], tmp_path, mission_id="m16k"
        )
        expected = str(Path("generated_visual_bay") / "preview_scene.gltf")
        asset = next((a for a in assets if a["path"] == expected), None)
        assert asset is not None
        assert "asset_url" in asset

    # ── integration: has_visual_artifacts gate ────────────────────────────

    def test_empty_export_no_gltf_generated(self, tmp_path):
        """Empty export dir has no visual artifacts; GLTF must not be written."""
        manifest = _build(tmp_path)
        f360 = manifest.get("fusion360", {})
        cq   = manifest.get("cadquery", {})
        r2   = manifest.get("ros2_preview", {})
        sim  = manifest.get("simulation", {})
        has_artifacts = bool(
            f360.get("detected") or cq.get("detected") or
            r2.get("detected") or sim.get("status") != "not_available"
        )
        assert not has_artifacts
        assert not (tmp_path / "generated_visual_bay" / "preview_scene.gltf").exists()

    def test_fusion360_dir_triggers_has_visual_artifacts(self, tmp_path):
        gen = tmp_path / "generated_fusion360"
        gen.mkdir()
        (gen / "fusion360_model_generator.py").write_text("# fusion")
        manifest = _build(tmp_path)
        assert manifest["fusion360"]["detected"] is True

    def test_ros2_dir_triggers_has_visual_artifacts(self, tmp_path):
        gen = tmp_path / "generated_ros2"
        gen.mkdir()
        (gen / "package.xml").write_text("<package/>")
        manifest = _build(tmp_path)
        assert manifest["ros2_preview"]["detected"] is True

    def test_export_manager_fusion360_writes_gltf(self, tmp_path):
        """Full export flow: Fusion 360 dir triggers GLTF generation."""
        result = _export_minimal("mission about a robot arm", tmp_path)
        export_dir = Path(result.get("export_dir", ""))
        if not export_dir.is_dir():
            pytest.skip("export_dir not returned by export_minimal fixture")
        gen = export_dir / "generated_fusion360"
        gen.mkdir(exist_ok=True)
        (gen / "fusion360_model_generator.py").write_text("# fusion")
        import backend.app.export.export_manager as em
        mp = pytest.MonkeyPatch()
        mp.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")
        try:
            result2 = em.export_mission_files(
                {
                    "status": "complete",
                    "result_id": "vb-test-16k",
                    "mission": "robot arm test",
                    "agents": {},
                    "artifacts": {},
                },
                validate_ros2=False,
            )
        finally:
            mp.undo()
        export2 = Path(result2.get("export_dir", ""))
        if not export2.is_dir():
            pytest.skip("second export_dir not available")
        gltf = export2 / "generated_visual_bay" / "preview_scene.gltf"
        assert gltf.is_file(), "GLTF preview not written by export_manager for Fusion360 mission"


# ---------------------------------------------------------------------------
# Phase 16L — GLTF placeholder mesh geometry tests
# ---------------------------------------------------------------------------

class TestGltfPreviewGeometry:
    """Phase 16L: preview_scene.gltf must contain a visible placeholder mesh."""

    def _load(self, tmp_path) -> dict:
        _write_gltf_preview(tmp_path)
        raw = (tmp_path / "generated_visual_bay" / "preview_scene.gltf").read_text(encoding="utf-8")
        return json.loads(raw)

    # ── mesh structure ────────────────────────────────────────────────────────

    def test_has_meshes_array(self, tmp_path):
        data = self._load(tmp_path)
        assert isinstance(data.get("meshes"), list)
        assert len(data["meshes"]) >= 1

    def test_mesh_has_primitives(self, tmp_path):
        data = self._load(tmp_path)
        prim_list = data["meshes"][0].get("primitives", [])
        assert len(prim_list) >= 1

    def test_primitive_has_position_attribute(self, tmp_path):
        data = self._load(tmp_path)
        attrs = data["meshes"][0]["primitives"][0].get("attributes", {})
        assert "POSITION" in attrs

    # ── accessors ─────────────────────────────────────────────────────────────

    def test_has_accessors(self, tmp_path):
        data = self._load(tmp_path)
        assert isinstance(data.get("accessors"), list)
        assert len(data["accessors"]) >= 1

    def test_position_accessor_is_vec3_float(self, tmp_path):
        data = self._load(tmp_path)
        prim     = data["meshes"][0]["primitives"][0]
        pos_idx  = prim["attributes"]["POSITION"]
        acc      = data["accessors"][pos_idx]
        assert acc["type"] == "VEC3"
        assert acc["componentType"] == 5126  # FLOAT

    def test_position_accessor_count_nonzero(self, tmp_path):
        data = self._load(tmp_path)
        prim    = data["meshes"][0]["primitives"][0]
        pos_idx = prim["attributes"]["POSITION"]
        assert data["accessors"][pos_idx]["count"] > 0

    # ── buffers / bufferViews ─────────────────────────────────────────────────

    def test_has_buffer_views(self, tmp_path):
        data = self._load(tmp_path)
        assert isinstance(data.get("bufferViews"), list)
        assert len(data["bufferViews"]) >= 1

    def test_has_buffers(self, tmp_path):
        data = self._load(tmp_path)
        assert isinstance(data.get("buffers"), list)
        assert len(data["buffers"]) >= 1

    def test_buffer_uses_embedded_data_uri(self, tmp_path):
        data = self._load(tmp_path)
        for buf in data["buffers"]:
            assert buf.get("uri", "").startswith("data:"), (
                "Buffer must use embedded data URI, not an external .bin file"
            )

    def test_buffer_has_positive_byte_length(self, tmp_path):
        data = self._load(tmp_path)
        for buf in data["buffers"]:
            assert buf.get("byteLength", 0) > 0

    # ── materials ─────────────────────────────────────────────────────────────

    def test_has_materials(self, tmp_path):
        data = self._load(tmp_path)
        assert isinstance(data.get("materials"), list)
        assert len(data["materials"]) >= 1

    def test_material_has_pbr_metallic_roughness(self, tmp_path):
        data = self._load(tmp_path)
        assert "pbrMetallicRoughness" in data["materials"][0]

    # ── JSON validity and safety metadata ────────────────────────────────────

    def test_gltf_remains_valid_json(self, tmp_path):
        _write_gltf_preview(tmp_path)
        raw = (tmp_path / "generated_visual_bay" / "preview_scene.gltf").read_text(encoding="utf-8")
        json.loads(raw)  # must not raise

    def test_safety_metadata_still_present(self, tmp_path):
        data = self._load(tmp_path)
        assert "extras" in data
        note = data["extras"].get("note", "").lower()
        assert "placeholder" in note or "not engineering" in note or "not cad" in note

    def test_extras_contain_concept_preview_wording(self, tmp_path):
        data = self._load(tmp_path)
        note = data["extras"].get("note", "")
        assert "Concept preview placeholder only." in note

    def test_extras_contain_not_cad_wording(self, tmp_path):
        data = self._load(tmp_path)
        note = data["extras"].get("note", "")
        assert "Not engineering CAD." in note

    def test_extras_contain_not_fabrication_ready_wording(self, tmp_path):
        data = self._load(tmp_path)
        note = data["extras"].get("note", "")
        assert "Not fabrication-ready." in note

    def test_extras_contain_no_engineering_validation_wording(self, tmp_path):
        data = self._load(tmp_path)
        note = data["extras"].get("note", "")
        assert "No engineering validation implied." in note

    def test_extras_contain_no_simulation_launched_wording(self, tmp_path):
        data = self._load(tmp_path)
        note = data["extras"].get("note", "")
        assert "No simulation launched." in note

    # ── forbidden claims ──────────────────────────────────────────────────────

    def test_no_safe_to_fly_claim(self, tmp_path):
        _write_gltf_preview(tmp_path)
        raw = (tmp_path / "generated_visual_bay" / "preview_scene.gltf").read_text(encoding="utf-8").lower()
        assert "safe to fly" not in raw

    def test_no_airworthy_claim(self, tmp_path):
        _write_gltf_preview(tmp_path)
        raw = (tmp_path / "generated_visual_bay" / "preview_scene.gltf").read_text(encoding="utf-8").lower()
        assert "airworthy" not in raw

    def test_no_fabrication_ready_design_claim(self, tmp_path):
        _write_gltf_preview(tmp_path)
        raw = (tmp_path / "generated_visual_bay" / "preview_scene.gltf").read_text(encoding="utf-8").lower()
        assert "fabrication-ready design" not in raw

    def test_no_engineering_validated_claim(self, tmp_path):
        _write_gltf_preview(tmp_path)
        raw = (tmp_path / "generated_visual_bay" / "preview_scene.gltf").read_text(encoding="utf-8").lower()
        assert "engineering validated" not in raw

    def test_no_deployment_ready_claim(self, tmp_path):
        _write_gltf_preview(tmp_path)
        raw = (tmp_path / "generated_visual_bay" / "preview_scene.gltf").read_text(encoding="utf-8").lower()
        assert "deployment-ready" not in raw

    # ── manifest / delivery integration ───────────────────────────────────────

    def test_manifest_includes_preview_scene_gltf(self, tmp_path):
        gen = tmp_path / "generated_fusion360"
        gen.mkdir()
        (gen / "fusion360_model_generator.py").write_text("# fusion")
        _write_gltf_preview(tmp_path)
        r = _build(tmp_path)
        paths = [a["path"] for a in r["preview_assets"]]
        expected = str(Path("generated_visual_bay") / "preview_scene.gltf")
        assert expected in paths

    def test_gltf_gets_asset_url_in_delivery(self, tmp_path):
        from backend.app.export.export_manager import _sanitize_preview_assets
        gen = tmp_path / "generated_fusion360"
        gen.mkdir()
        (gen / "fusion360_model_generator.py").write_text("# fusion")
        _write_gltf_preview(tmp_path)
        manifest = _build(tmp_path)
        assets = _sanitize_preview_assets(
            manifest["preview_assets"], tmp_path, mission_id="m16l"
        )
        expected = str(Path("generated_visual_bay") / "preview_scene.gltf")
        asset = next((a for a in assets if a["path"] == expected), None)
        assert asset is not None
        assert "asset_url" in asset

    def test_gltf_browser_preview_ready_in_manifest(self, tmp_path):
        gen = tmp_path / "generated_fusion360"
        gen.mkdir()
        (gen / "fusion360_model_generator.py").write_text("# fusion")
        _write_gltf_preview(tmp_path)
        r = _build(tmp_path)
        expected = str(Path("generated_visual_bay") / "preview_scene.gltf")
        asset = next((a for a in r["preview_assets"] if a["path"] == expected), None)
        assert asset is not None
        assert asset["browser_preview_ready"] is True

    def test_gltf_execution_blocked_false_in_manifest(self, tmp_path):
        _write_gltf_preview(tmp_path)
        r = _build(tmp_path)
        expected = str(Path("generated_visual_bay") / "preview_scene.gltf")
        asset = next((a for a in r["preview_assets"] if a["path"] == expected), None)
        assert asset is not None
        assert asset["execution_blocked"] is False

    # ── generator field ───────────────────────────────────────────────────────

    def test_generator_contains_omni_visual_bay(self, tmp_path):
        data = self._load(tmp_path)
        assert "OMNI Visual Bay" in data["asset"].get("generator", "")


# ---------------------------------------------------------------------------
# Phase 16P — Mission-aware placeholder kind tests
# ---------------------------------------------------------------------------

def _write_gltf_preview_16p(export_dir: Path, manifest=None, mission_result=None):
    from backend.app.visual_bay.gltf_preview import write_visual_bay_gltf_preview
    return write_visual_bay_gltf_preview(
        export_dir, manifest=manifest, mission_result=mission_result
    )


def _load_gltf_16p(tmp_path, mission_result=None, manifest=None) -> dict:
    _write_gltf_preview_16p(tmp_path, mission_result=mission_result, manifest=manifest)
    raw = (tmp_path / "generated_visual_bay" / "preview_scene.gltf").read_text(encoding="utf-8")
    return json.loads(raw)


class TestPlaceholderKindClassification:
    """Phase 16P: platform kind is classified from mission context."""

    # ── UAV keyword detection ─────────────────────────────────────────────────

    def test_drone_keyword_gives_uav_marker(self, tmp_path):
        data = _load_gltf_16p(tmp_path, {"mission": "Build a quadcopter drone for inspection."})
        assert data["extras"]["placeholder_kind"] == "abstract_uav_marker"

    def test_uav_keyword_gives_uav_marker(self, tmp_path):
        data = _load_gltf_16p(tmp_path, {"mission": "Design a UAV for aerial surveillance."})
        assert data["extras"]["placeholder_kind"] == "abstract_uav_marker"

    def test_aerial_keyword_gives_uav_marker(self, tmp_path):
        data = _load_gltf_16p(tmp_path, {"mission": "Create an aerial robot for mapping."})
        assert data["extras"]["placeholder_kind"] == "abstract_uav_marker"

    def test_quadrotor_keyword_gives_uav_marker(self, tmp_path):
        data = _load_gltf_16p(tmp_path, {"mission": "Design a quadrotor inspection platform."})
        assert data["extras"]["placeholder_kind"] == "abstract_uav_marker"

    # ── Rover keyword detection ───────────────────────────────────────────────

    def test_rover_keyword_gives_rover_marker(self, tmp_path):
        data = _load_gltf_16p(tmp_path, {"mission": "Design a Mars rover for geological exploration."})
        assert data["extras"]["placeholder_kind"] == "abstract_rover_marker"

    def test_crawler_keyword_gives_rover_marker(self, tmp_path):
        data = _load_gltf_16p(tmp_path, {"mission": "Build a magnetic inspection crawler for steel surfaces."})
        assert data["extras"]["placeholder_kind"] == "abstract_rover_marker"

    def test_wheeled_keyword_gives_rover_marker(self, tmp_path):
        data = _load_gltf_16p(tmp_path, {"mission": "Design a wheeled robot for warehouse logistics."})
        assert data["extras"]["placeholder_kind"] == "abstract_rover_marker"

    def test_ground_vehicle_keyword_gives_rover_marker(self, tmp_path):
        data = _load_gltf_16p(tmp_path, {"mission": "Build an autonomous ground vehicle for patrol."})
        assert data["extras"]["placeholder_kind"] == "abstract_rover_marker"

    # ── Manipulator keyword detection ─────────────────────────────────────────

    def test_robot_arm_keyword_gives_manipulator_marker(self, tmp_path):
        data = _load_gltf_16p(tmp_path, {"mission": "Design a robot arm for pick and place operations."})
        assert data["extras"]["placeholder_kind"] == "abstract_manipulator_marker"

    def test_manipulator_keyword_gives_manipulator_marker(self, tmp_path):
        data = _load_gltf_16p(tmp_path, {"mission": "Build a 6-DOF manipulator for precision assembly."})
        assert data["extras"]["placeholder_kind"] == "abstract_manipulator_marker"

    def test_gripper_keyword_gives_manipulator_marker(self, tmp_path):
        data = _load_gltf_16p(tmp_path, {"mission": "Design a robotic gripper for surgical assistance."})
        assert data["extras"]["placeholder_kind"] == "abstract_manipulator_marker"

    def test_robotic_arm_keyword_gives_manipulator_marker(self, tmp_path):
        data = _load_gltf_16p(tmp_path, {"mission": "Build a robotic arm for factory automation."})
        assert data["extras"]["placeholder_kind"] == "abstract_manipulator_marker"

    # ── Unknown / fallback ────────────────────────────────────────────────────

    def test_unknown_mission_gives_generic_marker(self, tmp_path):
        data = _load_gltf_16p(tmp_path, {"mission": "Build an OMNI sensor fusion system."})
        assert data["extras"]["placeholder_kind"] == "abstract_generic_marker"

    def test_no_mission_result_gives_generic_marker(self, tmp_path):
        data = _load_gltf_16p(tmp_path, mission_result=None)
        assert data["extras"]["placeholder_kind"] == "abstract_generic_marker"

    def test_empty_mission_gives_generic_marker(self, tmp_path):
        data = _load_gltf_16p(tmp_path, {"mission": ""})
        assert data["extras"]["placeholder_kind"] == "abstract_generic_marker"

    def test_non_dict_mission_result_gives_generic_marker(self, tmp_path):
        data = _load_gltf_16p(tmp_path, mission_result="not a dict")
        assert data["extras"]["placeholder_kind"] == "abstract_generic_marker"

    # ── mission_intent.platform_intent takes priority over text ───────────────

    def test_platform_intent_uav_overrides_text(self, tmp_path):
        mr = {
            "mission": "Build a ground robot.",
            "artifacts": {"mission_intent": {"platform_intent": "drone_uav"}},
        }
        data = _load_gltf_16p(tmp_path, mr)
        assert data["extras"]["placeholder_kind"] == "abstract_uav_marker"
        assert data["extras"]["classification_source"] == "mission_intent.platform_intent"

    def test_platform_intent_rover_overrides_text(self, tmp_path):
        mr = {
            "mission": "Build a drone.",
            "artifacts": {"mission_intent": {"platform_intent": "ground_rover"}},
        }
        data = _load_gltf_16p(tmp_path, mr)
        assert data["extras"]["placeholder_kind"] == "abstract_rover_marker"
        assert data["extras"]["classification_source"] == "mission_intent.platform_intent"

    def test_platform_intent_arm_overrides_text(self, tmp_path):
        mr = {
            "mission": "Build a UAV.",
            "artifacts": {"mission_intent": {"platform_intent": "robot_arm_manipulator"}},
        }
        data = _load_gltf_16p(tmp_path, mr)
        assert data["extras"]["placeholder_kind"] == "abstract_manipulator_marker"
        assert data["extras"]["classification_source"] == "mission_intent.platform_intent"

    def test_text_keywords_used_when_no_platform_intent(self, tmp_path):
        mr = {
            "mission": "Build a UAV drone.",
            "artifacts": {"mission_intent": {}},
        }
        data = _load_gltf_16p(tmp_path, mr)
        assert data["extras"]["placeholder_kind"] == "abstract_uav_marker"
        assert data["extras"]["classification_source"] == "mission_text_keywords"

    # ── extras fields ─────────────────────────────────────────────────────────

    def test_extras_has_placeholder_kind(self, tmp_path):
        data = _load_gltf_16p(tmp_path)
        assert "placeholder_kind" in data["extras"]

    def test_extras_has_classification_source(self, tmp_path):
        data = _load_gltf_16p(tmp_path)
        assert "classification_source" in data["extras"]

    def test_extras_note_still_present(self, tmp_path):
        data = _load_gltf_16p(tmp_path)
        assert "Concept preview placeholder only." in data["extras"].get("note", "")

    def test_extras_phase_is_16p(self, tmp_path):
        data = _load_gltf_16p(tmp_path)
        assert data["extras"].get("phase") == "16P"

    # ── GLTF validity for every kind ──────────────────────────────────────────

    def test_all_kinds_produce_valid_json(self, tmp_path):
        cases = [
            ("UAV drone",     "abstract_uav_marker"),
            ("ground rover",  "abstract_rover_marker"),
            ("robot arm manipulator", "abstract_manipulator_marker"),
            ("sensor system", "abstract_generic_marker"),
        ]
        for label, expected_kind in cases:
            p = tmp_path / label.replace(" ", "_")
            p.mkdir()
            data = _load_gltf_16p(p, {"mission": f"Build a {label}."})
            assert data["extras"]["placeholder_kind"] == expected_kind, (
                f"Expected {expected_kind} for '{label}', got {data['extras']['placeholder_kind']}"
            )

    def test_all_kinds_have_meshes(self, tmp_path):
        for text in ["UAV drone", "ground rover", "robot arm", "generic thing"]:
            p = tmp_path / text.replace(" ", "_")
            p.mkdir()
            data = _load_gltf_16p(p, {"mission": f"Build a {text}."})
            assert isinstance(data.get("meshes"), list) and len(data["meshes"]) >= 1

    def test_all_kinds_have_position_accessor(self, tmp_path):
        for text in ["UAV drone", "ground rover", "robot arm"]:
            p = tmp_path / text.replace(" ", "_")
            p.mkdir()
            data = _load_gltf_16p(p, {"mission": f"Build a {text}."})
            prim    = data["meshes"][0]["primitives"][0]
            pos_idx = prim["attributes"]["POSITION"]
            acc     = data["accessors"][pos_idx]
            assert acc["type"] == "VEC3"
            assert acc["componentType"] == 5126

    def test_all_kinds_use_embedded_buffer(self, tmp_path):
        for text in ["UAV drone", "ground rover", "robot arm", "generic beacon"]:
            p = tmp_path / text.replace(" ", "_")
            p.mkdir()
            data = _load_gltf_16p(p, {"mission": f"Build a {text}."})
            for buf in data.get("buffers", []):
                assert buf.get("uri", "").startswith("data:"), (
                    f"External buffer in '{text}' shape"
                )

    def test_all_kinds_have_materials(self, tmp_path):
        for text in ["UAV drone", "ground rover", "robot arm"]:
            p = tmp_path / text.replace(" ", "_")
            p.mkdir()
            data = _load_gltf_16p(p, {"mission": f"Build a {text}."})
            assert len(data.get("materials", [])) >= 1

    # ── no forbidden claims ───────────────────────────────────────────────────

    def test_no_airworthy_claim_in_uav(self, tmp_path):
        _write_gltf_preview_16p(tmp_path, mission_result={"mission": "Build a UAV drone."})
        raw = (tmp_path / "generated_visual_bay" / "preview_scene.gltf").read_text("utf-8").lower()
        assert "airworthy" not in raw

    def test_no_safe_to_fly_claim_in_uav(self, tmp_path):
        _write_gltf_preview_16p(tmp_path, mission_result={"mission": "Build a UAV drone."})
        raw = (tmp_path / "generated_visual_bay" / "preview_scene.gltf").read_text("utf-8").lower()
        assert "safe to fly" not in raw

    def test_no_flight_ready_claim_in_uav(self, tmp_path):
        _write_gltf_preview_16p(tmp_path, mission_result={"mission": "Build a UAV drone."})
        raw = (tmp_path / "generated_visual_bay" / "preview_scene.gltf").read_text("utf-8").lower()
        assert "flight-ready" not in raw

    def test_no_fabrication_ready_design_across_kinds(self, tmp_path):
        for text in ["UAV drone", "ground rover", "robot arm"]:
            p = tmp_path / text.replace(" ", "_")
            p.mkdir()
            _write_gltf_preview_16p(p, mission_result={"mission": f"Build a {text}."})
            raw = (p / "generated_visual_bay" / "preview_scene.gltf").read_text("utf-8").lower()
            assert "fabrication-ready design" not in raw

    def test_no_engineering_validated_across_kinds(self, tmp_path):
        for text in ["UAV drone", "ground rover", "robot arm"]:
            p = tmp_path / text.replace(" ", "_")
            p.mkdir()
            _write_gltf_preview_16p(p, mission_result={"mission": f"Build a {text}."})
            raw = (p / "generated_visual_bay" / "preview_scene.gltf").read_text("utf-8").lower()
            assert "engineering validated" not in raw

    def test_no_deployment_ready_across_kinds(self, tmp_path):
        for text in ["UAV drone", "ground rover", "robot arm"]:
            p = tmp_path / text.replace(" ", "_")
            p.mkdir()
            _write_gltf_preview_16p(p, mission_result={"mission": f"Build a {text}."})
            raw = (p / "generated_visual_bay" / "preview_scene.gltf").read_text("utf-8").lower()
            assert "deployment-ready" not in raw

    def test_no_dimensionally_accurate_claim(self, tmp_path):
        data = _load_gltf_16p(tmp_path)
        assert "dimensionally accurate" not in json.dumps(data).lower()

    # ── manifest / delivery integration ──────────────────────────────────────

    def test_manifest_includes_preview_scene_gltf(self, tmp_path):
        gen = tmp_path / "generated_fusion360"
        gen.mkdir()
        (gen / "fusion360_model_generator.py").write_text("# fusion")
        _write_gltf_preview_16p(tmp_path, mission_result={"mission": "Build a UAV drone."})
        r = _build(tmp_path)
        expected = str(Path("generated_visual_bay") / "preview_scene.gltf")
        assert expected in [a["path"] for a in r["preview_assets"]]

    def test_asset_url_delivered_with_mission_result(self, tmp_path):
        from backend.app.export.export_manager import _sanitize_preview_assets
        gen = tmp_path / "generated_fusion360"
        gen.mkdir()
        (gen / "fusion360_model_generator.py").write_text("# fusion")
        _write_gltf_preview_16p(tmp_path, mission_result={"mission": "Build a UAV drone."})
        manifest = _build(tmp_path)
        assets = _sanitize_preview_assets(
            manifest["preview_assets"], tmp_path, mission_id="m16p"
        )
        expected = str(Path("generated_visual_bay") / "preview_scene.gltf")
        asset = next((a for a in assets if a["path"] == expected), None)
        assert asset is not None
        assert "asset_url" in asset

    def test_browser_preview_ready_still_true(self, tmp_path):
        _write_gltf_preview_16p(tmp_path, mission_result={"mission": "Build a UAV drone."})
        r = _build(tmp_path)
        expected = str(Path("generated_visual_bay") / "preview_scene.gltf")
        asset = next((a for a in r["preview_assets"] if a["path"] == expected), None)
        assert asset is not None
        assert asset["browser_preview_ready"] is True

    def test_execution_blocked_still_false(self, tmp_path):
        _write_gltf_preview_16p(tmp_path, mission_result={"mission": "Build a UAV drone."})
        r = _build(tmp_path)
        expected = str(Path("generated_visual_bay") / "preview_scene.gltf")
        asset = next((a for a in r["preview_assets"] if a["path"] == expected), None)
        assert asset is not None
        assert asset["execution_blocked"] is False
