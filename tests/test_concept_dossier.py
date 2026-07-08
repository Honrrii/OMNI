"""
Tests for OMNI Phase 18A — Concept Dossier Manifest.

All tests are local, deterministic, and run without LLM calls,
internet access, simulation, image generation, or CAD execution.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

import backend.app.export.export_manager as em
from backend.app.concept_dossier.manifest import (
    build_concept_dossier_manifest,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DRONE_MISSION = "Design a quadcopter UAV for aerial bridge inspection."
_ROVER_MISSION = "Build a wheeled ground rover for pipeline inspection."
_GENERIC_MISSION = "Design a robot system for warehouse automation."

_UNSAFE_PHRASES = [
    "validated",
    "certified",
    "safe to fly",
    "airworthy",
    "flight-ready",
    "fabrication-ready",
    "deployment-ready",
    "production-ready",
    "simulation verified",
]

_PANEL_IDS = {
    "mission_overview",
    "visual_bay_preview",
    "engineering_brain",
    "safety_boundary",
    "blueprint_placeholders",
}


def _make_mission_result(
    mission: str = _GENERIC_MISSION,
    result_id: str = "phase18a-test",
    artifacts: dict | None = None,
) -> dict:
    return {
        "mission": mission,
        "result_id": result_id,
        "final_report": "",
        "final_decision": "",
        "agents": {},
        "artifacts": artifacts or {},
        "validation": {},
        "critique": {},
        "revision": {},
        "status": "complete",
    }


def _export(mission_result: dict, tmp_path: Path) -> dict:
    mp = pytest.MonkeyPatch()
    mp.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")
    try:
        result = em.export_mission_files(mission_result, validate_ros2=False)
    finally:
        mp.undo()
    return result


def _export_text(mission_text: str, tmp_path: Path) -> dict:
    return _export(_make_mission_result(mission=mission_text), tmp_path)


def _get_panel(manifest: dict, panel_id: str) -> dict | None:
    return next(
        (p for p in manifest.get("dossier_panels", []) if p["id"] == panel_id),
        None,
    )


def _descriptive_text(manifest: dict) -> str:
    """Collect descriptive text excluding blocked_claims fields."""
    parts: list[str] = []

    def _collect(obj: object) -> None:
        if isinstance(obj, str):
            parts.append(obj)
        elif isinstance(obj, list):
            for item in obj:
                _collect(item)
        elif isinstance(obj, dict):
            for key, val in obj.items():
                if key == "blocked_claims":
                    continue
                _collect(val)

    _collect(manifest)
    return " ".join(parts).lower()


def _write_stub_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. build_concept_dossier_manifest returns schema / status
# ---------------------------------------------------------------------------

class TestManifestTopLevel:
    def test_returns_dict(self):
        result = build_concept_dossier_manifest()
        assert isinstance(result, dict)

    def test_schema_field(self):
        result = build_concept_dossier_manifest()
        assert result["schema"] == "concept_dossier_manifest.v1"

    def test_status_field(self):
        result = build_concept_dossier_manifest()
        assert result["status"] == "generated"

    def test_module_field(self):
        result = build_concept_dossier_manifest()
        assert result["module"] == "concept_dossier"

    def test_all_top_level_keys_present(self):
        result = build_concept_dossier_manifest()
        for key in (
            "module", "schema", "status", "concept_stage_only",
            "mission_title", "platform_intent", "mission_type",
            "hero_visual", "dossier_panels", "allowed_visual_modes",
            "blocked_claims", "safety_notes", "source_reports",
        ):
            assert key in result, f"Missing top-level key '{key}'"


# ---------------------------------------------------------------------------
# 2. Manifest includes concept_stage_only true
# ---------------------------------------------------------------------------

class TestConceptStageOnly:
    def test_concept_stage_only_is_true(self):
        result = build_concept_dossier_manifest()
        assert result["concept_stage_only"] is True

    def test_concept_stage_only_is_bool(self):
        result = build_concept_dossier_manifest()
        assert isinstance(result["concept_stage_only"], bool)

    def test_concept_stage_only_not_overridden_by_mission_result(self):
        mr = _make_mission_result()
        result = build_concept_dossier_manifest(mission_result=mr)
        assert result["concept_stage_only"] is True


# ---------------------------------------------------------------------------
# 3. Manifest includes mission overview panel
# ---------------------------------------------------------------------------

class TestMissionOverviewPanel:
    def test_mission_overview_panel_present(self):
        result = build_concept_dossier_manifest(mission_text=_DRONE_MISSION)
        panel = _get_panel(result, "mission_overview")
        assert panel is not None

    def test_mission_overview_status_available(self):
        result = build_concept_dossier_manifest(mission_text=_DRONE_MISSION)
        panel = _get_panel(result, "mission_overview")
        assert panel["status"] == "available"

    def test_mission_overview_panel_type_is_summary(self):
        result = build_concept_dossier_manifest(mission_text=_DRONE_MISSION)
        panel = _get_panel(result, "mission_overview")
        assert panel["panel_type"] == "summary"

    def test_mission_overview_has_items(self):
        result = build_concept_dossier_manifest(mission_text=_DRONE_MISSION)
        panel = _get_panel(result, "mission_overview")
        assert isinstance(panel.get("items"), list) and len(panel["items"]) >= 1

    def test_mission_title_from_mission_text(self):
        result = build_concept_dossier_manifest(mission_text=_DRONE_MISSION)
        assert result["mission_title"] == _DRONE_MISSION

    def test_mission_title_from_mission_result(self):
        mr = _make_mission_result(mission=_ROVER_MISSION)
        result = build_concept_dossier_manifest(mission_result=mr)
        assert result["mission_title"] == _ROVER_MISSION

    def test_platform_intent_from_artifacts(self):
        mr = _make_mission_result(
            artifacts={"mission_intent": {"platform_intent": "drone UAV", "mission_type": "aerial"}},
        )
        result = build_concept_dossier_manifest(mission_result=mr)
        assert result["platform_intent"] == "drone UAV"

    def test_mission_type_from_artifacts(self):
        mr = _make_mission_result(
            artifacts={"mission_intent": {"platform_intent": "rover", "mission_type": "inspection"}},
        )
        result = build_concept_dossier_manifest(mission_result=mr)
        assert result["mission_type"] == "inspection"

    def test_default_title_when_no_mission_provided(self):
        result = build_concept_dossier_manifest()
        assert result["mission_title"] == "Untitled Mission"

    def test_mission_item_present_in_overview_items(self):
        result = build_concept_dossier_manifest(mission_text=_DRONE_MISSION)
        panel = _get_panel(result, "mission_overview")
        labels = [item["label"] for item in panel["items"]]
        assert "Mission" in labels


# ---------------------------------------------------------------------------
# 4. Manifest includes visual bay panel
# ---------------------------------------------------------------------------

class TestVisualBayPanel:
    def test_visual_bay_panel_present(self):
        result = build_concept_dossier_manifest()
        panel = _get_panel(result, "visual_bay_preview")
        assert panel is not None

    def test_visual_bay_panel_type(self):
        result = build_concept_dossier_manifest()
        panel = _get_panel(result, "visual_bay_preview")
        assert panel["panel_type"] == "visual_inventory"

    def test_visual_bay_missing_when_no_export_dir(self):
        result = build_concept_dossier_manifest()
        panel = _get_panel(result, "visual_bay_preview")
        assert panel["status"] == "missing"

    def test_visual_bay_missing_when_manifest_absent(self, tmp_path):
        result = build_concept_dossier_manifest(export_dir=tmp_path)
        panel = _get_panel(result, "visual_bay_preview")
        assert panel["status"] == "missing"


# ---------------------------------------------------------------------------
# 5. Manifest includes engineering brain panel
# ---------------------------------------------------------------------------

class TestEngineeringBrainPanel:
    def test_engineering_brain_panel_present(self):
        result = build_concept_dossier_manifest()
        panel = _get_panel(result, "engineering_brain")
        assert panel is not None

    def test_engineering_brain_panel_type(self):
        result = build_concept_dossier_manifest()
        panel = _get_panel(result, "engineering_brain")
        assert panel["panel_type"] == "engineering_summary"

    def test_engineering_brain_missing_when_no_export_dir(self):
        result = build_concept_dossier_manifest()
        panel = _get_panel(result, "engineering_brain")
        assert panel["status"] == "missing"

    def test_engineering_brain_missing_when_files_absent(self, tmp_path):
        result = build_concept_dossier_manifest(export_dir=tmp_path)
        panel = _get_panel(result, "engineering_brain")
        assert panel["status"] == "missing"


# ---------------------------------------------------------------------------
# 6. Missing Visual Bay report does not crash
# ---------------------------------------------------------------------------

class TestMissingVisualBayNoCrash:
    def test_no_crash_without_export_dir(self):
        result = build_concept_dossier_manifest(mission_text=_DRONE_MISSION)
        assert result["schema"] == "concept_dossier_manifest.v1"

    def test_no_crash_with_empty_export_dir(self, tmp_path):
        result = build_concept_dossier_manifest(
            mission_text=_DRONE_MISSION,
            export_dir=tmp_path,
        )
        assert result["schema"] == "concept_dossier_manifest.v1"

    def test_visual_bay_panel_status_is_missing_not_error(self, tmp_path):
        result = build_concept_dossier_manifest(export_dir=tmp_path)
        panel = _get_panel(result, "visual_bay_preview")
        assert panel["status"] == "missing"
        assert "error" not in panel

    def test_corrupted_visual_bay_manifest_does_not_crash(self, tmp_path):
        (tmp_path / "visual_bay_manifest.json").write_text("NOT_JSON", encoding="utf-8")
        result = build_concept_dossier_manifest(export_dir=tmp_path)
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# 7. Missing engineering reports do not crash
# ---------------------------------------------------------------------------

class TestMissingEngineeringReportsNoCrash:
    def test_no_crash_without_engineering_files(self, tmp_path):
        result = build_concept_dossier_manifest(
            mission_text=_DRONE_MISSION,
            export_dir=tmp_path,
        )
        assert result["schema"] == "concept_dossier_manifest.v1"

    def test_engineering_panel_status_is_missing_not_error(self, tmp_path):
        result = build_concept_dossier_manifest(export_dir=tmp_path)
        panel = _get_panel(result, "engineering_brain")
        assert panel["status"] == "missing"
        assert "error" not in panel

    def test_partial_engineering_files_does_not_crash(self, tmp_path):
        _write_stub_json(
            tmp_path / "engineering_knowledge_selection_report.json",
            {"schema": "engineering_knowledge_selection_report.v1", "selected_check_count": 5},
        )
        # readiness and calc missing
        result = build_concept_dossier_manifest(export_dir=tmp_path)
        assert isinstance(result, dict)
        panel = _get_panel(result, "engineering_brain")
        assert panel["status"] == "available"

    def test_corrupted_engineering_file_does_not_crash(self, tmp_path):
        (tmp_path / "engineering_knowledge_selection_report.json").write_text(
            "GARBAGE", encoding="utf-8"
        )
        result = build_concept_dossier_manifest(export_dir=tmp_path)
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# 8. Existing Visual Bay GLTF preview is referenced when present
# ---------------------------------------------------------------------------

class TestGltfPreviewReference:
    def test_hero_visual_type_is_gltf_placeholder(self):
        result = build_concept_dossier_manifest()
        assert result["hero_visual"]["type"] == "visual_bay_gltf_placeholder"

    def test_hero_visual_path_is_gltf(self):
        result = build_concept_dossier_manifest()
        assert "preview_scene.gltf" in result["hero_visual"]["path"]

    def test_hero_visual_not_cad_accurate_is_true(self):
        result = build_concept_dossier_manifest()
        assert result["hero_visual"]["not_cad_accurate"] is True

    def test_gltf_exists_false_when_file_absent(self, tmp_path):
        result = build_concept_dossier_manifest(export_dir=tmp_path)
        assert result["hero_visual"]["gltf_exists"] is False

    def test_gltf_exists_true_when_file_present(self, tmp_path):
        gltf_dir = tmp_path / "generated_visual_bay"
        gltf_dir.mkdir()
        (gltf_dir / "preview_scene.gltf").write_text("{}", encoding="utf-8")
        result = build_concept_dossier_manifest(export_dir=tmp_path)
        assert result["hero_visual"]["gltf_exists"] is True

    def test_visual_bay_panel_references_gltf_when_present(self, tmp_path):
        _write_stub_json(tmp_path / "visual_bay_manifest.json", {"status": "available"})
        gltf_dir = tmp_path / "generated_visual_bay"
        gltf_dir.mkdir()
        (gltf_dir / "preview_scene.gltf").write_text("{}", encoding="utf-8")
        result = build_concept_dossier_manifest(export_dir=tmp_path)
        panel = _get_panel(result, "visual_bay_preview")
        assert panel["status"] == "available"
        assert panel["gltf_preview_available"] is True
        assert panel["gltf_preview_path"] == "generated_visual_bay/preview_scene.gltf"


# ---------------------------------------------------------------------------
# 9. Engineering brain counts are summarised when reports exist
# ---------------------------------------------------------------------------

class TestEngineeringBrainSummary:
    @pytest.fixture
    def export_dir_with_brain(self, tmp_path) -> Path:
        _write_stub_json(
            tmp_path / "engineering_knowledge_selection_report.json",
            {"schema": "...", "selected_check_count": 7, "platform_intent": "drone"},
        )
        _write_stub_json(
            tmp_path / "engineering_input_readiness_report.json",
            {
                "schema": "...",
                "readiness_summary": {
                    "overall_status": "inputs_missing",
                    "total_checks": 7,
                    "ready_count": 0,
                    "partial_count": 0,
                    "missing_count": 7,
                },
            },
        )
        _write_stub_json(
            tmp_path / "engineering_calculation_report.json",
            {
                "schema": "...",
                "computed_metric_count": 0,
                "blocked_calculation_count": 7,
                "calculation_performed": False,
            },
        )
        return tmp_path

    def test_engineering_panel_status_available(self, export_dir_with_brain):
        result = build_concept_dossier_manifest(export_dir=export_dir_with_brain)
        panel = _get_panel(result, "engineering_brain")
        assert panel["status"] == "available"

    def test_summary_has_selected_check_count(self, export_dir_with_brain):
        result = build_concept_dossier_manifest(export_dir=export_dir_with_brain)
        panel = _get_panel(result, "engineering_brain")
        assert panel["summary"]["selected_check_count"] == 7

    def test_summary_has_readiness_overall_status(self, export_dir_with_brain):
        result = build_concept_dossier_manifest(export_dir=export_dir_with_brain)
        panel = _get_panel(result, "engineering_brain")
        assert panel["summary"]["readiness_overall_status"] == "inputs_missing"

    def test_summary_has_computed_metric_count(self, export_dir_with_brain):
        result = build_concept_dossier_manifest(export_dir=export_dir_with_brain)
        panel = _get_panel(result, "engineering_brain")
        assert panel["summary"]["computed_metric_count"] == 0

    def test_summary_has_blocked_calculation_count(self, export_dir_with_brain):
        result = build_concept_dossier_manifest(export_dir=export_dir_with_brain)
        panel = _get_panel(result, "engineering_brain")
        assert panel["summary"]["blocked_calculation_count"] == 7

    def test_items_list_present(self, export_dir_with_brain):
        result = build_concept_dossier_manifest(export_dir=export_dir_with_brain)
        panel = _get_panel(result, "engineering_brain")
        assert isinstance(panel.get("items"), list) and len(panel["items"]) >= 1

    def test_source_reports_reference_brain_files(self, export_dir_with_brain):
        result = build_concept_dossier_manifest(export_dir=export_dir_with_brain)
        sources = result["source_reports"]
        assert "knowledge_selection" in sources
        assert "input_readiness" in sources
        assert "calculation" in sources


# ---------------------------------------------------------------------------
# 10. Blocked claims include CAD/fabrication/flight/deployment/validation
# ---------------------------------------------------------------------------

class TestBlockedClaims:
    _REQUIRED_BLOCKED = [
        "CAD-accurate",
        "fabrication-ready",
        "flight-ready",
        "airworthy",
        "deployment-ready",
        "engineering validated",
        "simulation verified",
    ]

    def test_blocked_claims_is_list(self):
        result = build_concept_dossier_manifest()
        assert isinstance(result["blocked_claims"], list)

    def test_blocked_claims_nonempty(self):
        result = build_concept_dossier_manifest()
        assert len(result["blocked_claims"]) >= 1

    @pytest.mark.parametrize("phrase", _REQUIRED_BLOCKED)
    def test_required_phrase_in_blocked_claims(self, phrase):
        result = build_concept_dossier_manifest()
        assert phrase in result["blocked_claims"], (
            f"'{phrase}' missing from blocked_claims"
        )

    def test_safety_boundary_panel_has_blocked_claims(self):
        result = build_concept_dossier_manifest()
        panel = _get_panel(result, "safety_boundary")
        assert isinstance(panel.get("blocked_claims"), list)
        assert len(panel["blocked_claims"]) >= 1


# ---------------------------------------------------------------------------
# 11. No unsafe positive claims appear in manifest text
# ---------------------------------------------------------------------------

class TestNoUnsafeClaims:
    @pytest.mark.parametrize("phrase", _UNSAFE_PHRASES)
    def test_phrase_absent_from_descriptive_text(self, phrase):
        result = build_concept_dossier_manifest(mission_text=_DRONE_MISSION)
        text = _descriptive_text(result)
        assert phrase not in text, (
            f"Unsafe phrase '{phrase}' found in concept dossier manifest"
        )

    def test_safety_notes_nonempty(self):
        result = build_concept_dossier_manifest()
        assert isinstance(result["safety_notes"], list)
        assert len(result["safety_notes"]) >= 1

    def test_hero_visual_label_free_of_unsafe_phrases(self):
        result = build_concept_dossier_manifest()
        label = result["hero_visual"]["label"].lower()
        for phrase in _UNSAFE_PHRASES:
            assert phrase not in label


# ---------------------------------------------------------------------------
# 12. Export writes concept_dossier_manifest.json
# ---------------------------------------------------------------------------

class TestExportWritesDossierFile:
    def test_concept_dossier_manifest_json_written(self, tmp_path):
        result = _export_text(_GENERIC_MISSION, tmp_path)
        export_dir = Path(result["export_dir"])
        assert (export_dir / "concept_dossier_manifest.json").exists()

    def test_concept_dossier_manifest_is_valid_json(self, tmp_path):
        result = _export_text(_GENERIC_MISSION, tmp_path)
        export_dir = Path(result["export_dir"])
        data = json.loads((export_dir / "concept_dossier_manifest.json").read_text())
        assert isinstance(data, dict)

    def test_concept_dossier_file_in_files_list(self, tmp_path):
        result = _export_text(_GENERIC_MISSION, tmp_path)
        assert any("concept_dossier_manifest" in f for f in result["files"])

    def test_dossier_schema_in_written_file(self, tmp_path):
        result = _export_text(_GENERIC_MISSION, tmp_path)
        export_dir = Path(result["export_dir"])
        data = json.loads((export_dir / "concept_dossier_manifest.json").read_text())
        assert data["schema"] == "concept_dossier_manifest.v1"

    def test_dossier_panels_in_written_file(self, tmp_path):
        result = _export_text(_GENERIC_MISSION, tmp_path)
        export_dir = Path(result["export_dir"])
        data = json.loads((export_dir / "concept_dossier_manifest.json").read_text())
        assert isinstance(data.get("dossier_panels"), list)

    def test_engineering_brain_panel_available_in_written_file(self, tmp_path):
        """Engineering brain panel should be available because export runs 17E first."""
        result = _export_text(_DRONE_MISSION, tmp_path)
        export_dir = Path(result["export_dir"])
        data = json.loads((export_dir / "concept_dossier_manifest.json").read_text())
        panel = next(
            (p for p in data["dossier_panels"] if p["id"] == "engineering_brain"),
            None,
        )
        assert panel is not None
        assert panel["status"] == "available"


# ---------------------------------------------------------------------------
# 13. Export returns top-level concept_dossier
# ---------------------------------------------------------------------------

class TestExportReturnsDossier:
    def test_concept_dossier_key_in_result(self, tmp_path):
        result = _export_text(_GENERIC_MISSION, tmp_path)
        assert "concept_dossier" in result

    def test_concept_dossier_is_dict(self, tmp_path):
        result = _export_text(_GENERIC_MISSION, tmp_path)
        assert isinstance(result["concept_dossier"], dict)

    def test_concept_dossier_status_generated(self, tmp_path):
        result = _export_text(_GENERIC_MISSION, tmp_path)
        assert result["concept_dossier"]["status"] == "generated"

    def test_concept_dossier_has_schema(self, tmp_path):
        result = _export_text(_GENERIC_MISSION, tmp_path)
        assert "schema" in result["concept_dossier"]

    def test_concept_dossier_has_panel_count(self, tmp_path):
        result = _export_text(_GENERIC_MISSION, tmp_path)
        assert "panel_count" in result["concept_dossier"]
        assert isinstance(result["concept_dossier"]["panel_count"], int)
        assert result["concept_dossier"]["panel_count"] == 5

    def test_concept_dossier_has_report_path(self, tmp_path):
        result = _export_text(_GENERIC_MISSION, tmp_path)
        assert "report_path" in result["concept_dossier"]
        assert Path(result["concept_dossier"]["report_path"]).exists()

    def test_failure_containment(self, tmp_path):
        with patch(
            "backend.app.export.export_manager._write_concept_dossier",
            side_effect=RuntimeError("simulated dossier failure"),
        ):
            result = _export_text(_GENERIC_MISSION, tmp_path)
        assert result["status"] == "exported"
        assert result["concept_dossier"]["status"] == "failed"

    def test_export_succeeds_when_dossier_raises(self, tmp_path):
        with patch(
            "backend.app.export.export_manager._write_concept_dossier",
            side_effect=RuntimeError("simulated failure"),
        ):
            result = _export_text(_GENERIC_MISSION, tmp_path)
        assert result["status"] == "exported"


# ---------------------------------------------------------------------------
# 14. Existing export keys remain unchanged
# ---------------------------------------------------------------------------

class TestExistingExportKeysUnchanged:
    _REQUIRED_KEYS = (
        "status", "folder_name", "export_dir", "files", "file_count",
        "ros2_generation", "ros2_validation", "fusion360_generation",
        "kicad_generation", "kicad_validation", "morphology_validation",
        "mission_report", "graph_review", "cortex", "aeroforge",
        "visual_bay", "engineering_brain",
    )

    def test_all_pre_existing_keys_present(self, tmp_path):
        result = _export_text(_GENERIC_MISSION, tmp_path)
        for key in self._REQUIRED_KEYS:
            assert key in result, f"Pre-existing key '{key}' missing after Phase 18A"

    def test_concept_dossier_is_additive(self, tmp_path):
        result = _export_text(_GENERIC_MISSION, tmp_path)
        assert "concept_dossier" in result
        for key in self._REQUIRED_KEYS:
            assert key in result

    def test_export_status_still_exported(self, tmp_path):
        result = _export_text(_GENERIC_MISSION, tmp_path)
        assert result["status"] == "exported"

    def test_cortex_keys_intact(self, tmp_path):
        result = _export_text(_GENERIC_MISSION, tmp_path)
        for key in ("design_understanding", "candidate_evaluation",
                    "mission_intent", "pluto_safety_gate"):
            assert key in result["cortex"]

    def test_engineering_brain_still_present(self, tmp_path):
        result = _export_text(_GENERIC_MISSION, tmp_path)
        assert "engineering_brain" in result
        assert isinstance(result["engineering_brain"], dict)
