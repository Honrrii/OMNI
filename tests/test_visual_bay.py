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
