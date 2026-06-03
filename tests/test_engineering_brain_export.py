"""
Tests for OMNI Phase 17E — Engineering Brain Export Integration.

Verifies that export_mission_files writes all three engineering brain
report files, returns the correct top-level engineering_brain summary,
and handles failure without breaking the overall export.

No LLM calls. No network calls. No simulation launched.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

import backend.app.export.export_manager as em

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_UAV_MISSION  = "Design a quadcopter UAV for aerial inspection."
_ROVER_MISSION = "Build a wheeled ground rover for pipe inspection."
_GENERIC_MISSION = "Design a robot system for warehouse automation."

_ENGINEERING_FILES = [
    "engineering_knowledge_selection_report.json",
    "engineering_input_readiness_report.json",
    "engineering_calculation_report.json",
]


def _make_mission_result(
    mission: str = _GENERIC_MISSION,
    result_id: str = "phase17e-test",
    artifacts: dict | None = None,
    engineering_inputs: dict | None = None,
) -> dict:
    base: dict = {
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
    if engineering_inputs is not None:
        base["engineering_inputs"] = engineering_inputs
    return base


def _export(mission_result: dict, tmp_path: Path) -> dict:
    mp = pytest.MonkeyPatch()
    mp.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")
    try:
        result = em.export_mission_files(mission_result, validate_ros2=False)
    finally:
        mp.undo()
    return result


def _export_text(mission_text: str, tmp_path: Path, **kwargs) -> dict:
    return _export(_make_mission_result(mission=mission_text, **kwargs), tmp_path)


def _read_report(result: dict, filename: str) -> dict:
    export_dir = Path(result["export_dir"])
    return json.loads((export_dir / filename).read_text())


# ---------------------------------------------------------------------------
# 1. Export writes all three engineering report files
# ---------------------------------------------------------------------------

class TestEngineeringFilesWritten:
    def test_knowledge_selection_report_written(self, tmp_path):
        result = _export_text(_GENERIC_MISSION, tmp_path)
        export_dir = Path(result["export_dir"])
        assert (export_dir / "engineering_knowledge_selection_report.json").exists()

    def test_input_readiness_report_written(self, tmp_path):
        result = _export_text(_GENERIC_MISSION, tmp_path)
        export_dir = Path(result["export_dir"])
        assert (export_dir / "engineering_input_readiness_report.json").exists()

    def test_calculation_report_written(self, tmp_path):
        result = _export_text(_GENERIC_MISSION, tmp_path)
        export_dir = Path(result["export_dir"])
        assert (export_dir / "engineering_calculation_report.json").exists()

    def test_all_three_files_written(self, tmp_path):
        result = _export_text(_GENERIC_MISSION, tmp_path)
        export_dir = Path(result["export_dir"])
        for fname in _ENGINEERING_FILES:
            assert (export_dir / fname).exists(), f"Missing: {fname}"

    def test_all_three_files_are_valid_json(self, tmp_path):
        result = _export_text(_GENERIC_MISSION, tmp_path)
        export_dir = Path(result["export_dir"])
        for fname in _ENGINEERING_FILES:
            data = json.loads((export_dir / fname).read_text())
            assert isinstance(data, dict), f"{fname} is not a JSON object"

    def test_engineering_files_listed_in_files(self, tmp_path):
        result = _export_text(_GENERIC_MISSION, tmp_path)
        files_str = " ".join(result["files"])
        assert "engineering_knowledge_selection_report" in files_str
        assert "engineering_input_readiness_report" in files_str
        assert "engineering_calculation_report" in files_str


# ---------------------------------------------------------------------------
# 2. Export returns top-level engineering_brain
# ---------------------------------------------------------------------------

class TestEngineeringBrainTopLevel:
    def test_engineering_brain_key_in_result(self, tmp_path):
        result = _export_text(_GENERIC_MISSION, tmp_path)
        assert "engineering_brain" in result

    def test_engineering_brain_is_dict(self, tmp_path):
        result = _export_text(_GENERIC_MISSION, tmp_path)
        assert isinstance(result["engineering_brain"], dict)

    def test_engineering_brain_status_generated(self, tmp_path):
        result = _export_text(_GENERIC_MISSION, tmp_path)
        assert result["engineering_brain"]["status"] == "generated"

    def test_engineering_brain_has_knowledge_selection(self, tmp_path):
        result = _export_text(_GENERIC_MISSION, tmp_path)
        assert "knowledge_selection" in result["engineering_brain"]

    def test_engineering_brain_has_input_readiness(self, tmp_path):
        result = _export_text(_GENERIC_MISSION, tmp_path)
        assert "input_readiness" in result["engineering_brain"]

    def test_engineering_brain_has_calculations(self, tmp_path):
        result = _export_text(_GENERIC_MISSION, tmp_path)
        assert "calculations" in result["engineering_brain"]

    def test_knowledge_selection_summary_has_schema(self, tmp_path):
        result = _export_text(_GENERIC_MISSION, tmp_path)
        ks = result["engineering_brain"]["knowledge_selection"]
        assert "schema" in ks

    def test_knowledge_selection_summary_has_selected_check_count(self, tmp_path):
        result = _export_text(_GENERIC_MISSION, tmp_path)
        ks = result["engineering_brain"]["knowledge_selection"]
        assert "selected_check_count" in ks
        assert isinstance(ks["selected_check_count"], int)

    def test_knowledge_selection_summary_has_report_path(self, tmp_path):
        result = _export_text(_GENERIC_MISSION, tmp_path)
        ks = result["engineering_brain"]["knowledge_selection"]
        assert "report_path" in ks
        assert Path(ks["report_path"]).exists()

    def test_input_readiness_summary_has_overall_status(self, tmp_path):
        result = _export_text(_GENERIC_MISSION, tmp_path)
        ir = result["engineering_brain"]["input_readiness"]
        assert "overall_status" in ir

    def test_input_readiness_summary_has_report_path(self, tmp_path):
        result = _export_text(_GENERIC_MISSION, tmp_path)
        ir = result["engineering_brain"]["input_readiness"]
        assert "report_path" in ir
        assert Path(ir["report_path"]).exists()

    def test_calculations_summary_has_calculation_performed(self, tmp_path):
        result = _export_text(_GENERIC_MISSION, tmp_path)
        calc = result["engineering_brain"]["calculations"]
        assert "calculation_performed" in calc

    def test_calculations_summary_has_computed_metric_count(self, tmp_path):
        result = _export_text(_GENERIC_MISSION, tmp_path)
        calc = result["engineering_brain"]["calculations"]
        assert "computed_metric_count" in calc

    def test_calculations_summary_has_report_path(self, tmp_path):
        result = _export_text(_GENERIC_MISSION, tmp_path)
        calc = result["engineering_brain"]["calculations"]
        assert "report_path" in calc
        assert Path(calc["report_path"]).exists()


# ---------------------------------------------------------------------------
# 3. UAV mission selects thrust_to_weight_ratio
# ---------------------------------------------------------------------------

class TestUavMissionSelection:
    def test_uav_selection_report_contains_twr(self, tmp_path):
        result = _export_text(_UAV_MISSION, tmp_path)
        report = _read_report(result, "engineering_knowledge_selection_report.json")
        check_ids = [c["check_id"] for c in report.get("selected_checks", [])]
        assert "thrust_to_weight_ratio" in check_ids

    def test_uav_readiness_report_contains_twr_check(self, tmp_path):
        result = _export_text(_UAV_MISSION, tmp_path)
        report = _read_report(result, "engineering_input_readiness_report.json")
        check_ids = [c["check_id"] for c in report.get("checks", [])]
        assert "thrust_to_weight_ratio" in check_ids

    def test_uav_platform_intent_resolved_in_brain(self, tmp_path):
        result = _export_text(_UAV_MISSION, tmp_path)
        eb = result["engineering_brain"]
        platform = eb["knowledge_selection"].get("platform_intent", "")
        assert platform != "", "platform_intent should be resolved for a UAV mission"

    def test_uav_via_artifacts_mission_intent(self, tmp_path):
        mr = _make_mission_result(
            mission=_UAV_MISSION,
            artifacts={
                "mission_intent": {
                    "platform_intent": "drone inspection UAV",
                }
            },
        )
        result = _export(mr, tmp_path)
        report = _read_report(result, "engineering_knowledge_selection_report.json")
        check_ids = [c["check_id"] for c in report.get("selected_checks", [])]
        assert "thrust_to_weight_ratio" in check_ids


# ---------------------------------------------------------------------------
# 4. Missing inputs produce no calculations and blocked results
# ---------------------------------------------------------------------------

class TestMissingInputsProduceNoCalculations:
    def test_calculation_performed_false_with_no_inputs(self, tmp_path):
        result = _export_text(_UAV_MISSION, tmp_path)
        calc = result["engineering_brain"]["calculations"]
        assert calc["calculation_performed"] is False

    def test_computed_metric_count_zero_with_no_inputs(self, tmp_path):
        result = _export_text(_UAV_MISSION, tmp_path)
        calc = result["engineering_brain"]["calculations"]
        assert calc["computed_metric_count"] == 0

    def test_overall_readiness_missing_with_no_inputs(self, tmp_path):
        result = _export_text(_UAV_MISSION, tmp_path)
        ir = result["engineering_brain"]["input_readiness"]
        assert ir["overall_status"] == "inputs_missing"

    def test_calc_report_has_blocked_results_when_no_inputs(self, tmp_path):
        result = _export_text(_UAV_MISSION, tmp_path)
        report = _read_report(result, "engineering_calculation_report.json")
        assert len(report.get("blocked_results", [])) > 0

    def test_calc_report_results_empty_when_no_inputs(self, tmp_path):
        result = _export_text(_UAV_MISSION, tmp_path)
        report = _read_report(result, "engineering_calculation_report.json")
        assert report.get("results", []) == []

    def test_readiness_checks_all_inputs_missing(self, tmp_path):
        result = _export_text(_UAV_MISSION, tmp_path)
        report = _read_report(result, "engineering_input_readiness_report.json")
        for chk in report.get("checks", []):
            assert chk["readiness_status"] == "inputs_missing"


# ---------------------------------------------------------------------------
# 5. Explicit provided engineering inputs allow supported calculations
# ---------------------------------------------------------------------------

class TestProvidedInputsAllowCalculations:
    # Engine-specific input names for supported calculations
    _UAV_CALC_INPUTS = {
        "total_thrust_n": 50.0,
        "mass_kg": 2.0,
        "battery_capacity_wh": 100.0,
        "average_power_w": 50.0,
        "voltage_v": 12.0,
        "current_a": 5.0,
    }

    def test_calculation_performed_true_with_twr_inputs(self, tmp_path):
        mr = _make_mission_result(
            mission=_UAV_MISSION,
            engineering_inputs=self._UAV_CALC_INPUTS,
        )
        result = _export(mr, tmp_path)
        calc = result["engineering_brain"]["calculations"]
        assert calc["calculation_performed"] is True

    def test_computed_metric_count_nonzero_with_inputs(self, tmp_path):
        mr = _make_mission_result(
            mission=_UAV_MISSION,
            engineering_inputs=self._UAV_CALC_INPUTS,
        )
        result = _export(mr, tmp_path)
        calc = result["engineering_brain"]["calculations"]
        assert calc["computed_metric_count"] >= 1

    def test_twr_result_appears_in_calc_report(self, tmp_path):
        mr = _make_mission_result(
            mission=_UAV_MISSION,
            engineering_inputs={"total_thrust_n": 50.0, "mass_kg": 2.0},
        )
        result = _export(mr, tmp_path)
        report = _read_report(result, "engineering_calculation_report.json")
        result_ids = [r["check_id"] for r in report.get("results", [])]
        assert "thrust_to_weight_ratio" in result_ids

    def test_twr_value_is_numeric_in_report(self, tmp_path):
        import math
        mr = _make_mission_result(
            mission=_UAV_MISSION,
            engineering_inputs={"total_thrust_n": 50.0, "mass_kg": 2.0},
        )
        result = _export(mr, tmp_path)
        report = _read_report(result, "engineering_calculation_report.json")
        twr = next(
            (r for r in report.get("results", []) if r["check_id"] == "thrust_to_weight_ratio"),
            None,
        )
        assert twr is not None
        assert isinstance(twr["value"], (int, float))
        assert not math.isnan(twr["value"])

    def test_engineering_inputs_from_artifacts_field(self, tmp_path):
        mr = _make_mission_result(
            mission=_UAV_MISSION,
            artifacts={
                "engineering_inputs": {"total_thrust_n": 50.0, "mass_kg": 2.0}
            },
        )
        result = _export(mr, tmp_path)
        report = _read_report(result, "engineering_calculation_report.json")
        result_ids = [r["check_id"] for r in report.get("results", [])]
        assert "thrust_to_weight_ratio" in result_ids

    def test_battery_runtime_computed_when_inputs_provided(self, tmp_path):
        mr = _make_mission_result(
            mission=_UAV_MISSION,
            engineering_inputs={
                "battery_capacity_wh": 100.0,
                "average_power_w": 50.0,
            },
        )
        result = _export(mr, tmp_path)
        report = _read_report(result, "engineering_calculation_report.json")
        result_ids = [r["check_id"] for r in report.get("results", [])]
        assert "battery_runtime_estimate" in result_ids


# ---------------------------------------------------------------------------
# 6. No unsafe claims appear in reports
# ---------------------------------------------------------------------------

class TestNoUnsafeClaimsInExportedReports:
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

    def _collect_descriptive_text(self, report: dict) -> str:
        """Collect descriptive text from a report, excluding blocked_claims fields."""
        parts = []
        for key, val in report.items():
            if key in ("blocked_claims",):
                continue
            if isinstance(val, str):
                parts.append(val)
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, str):
                        parts.append(item)
                    elif isinstance(item, dict):
                        for k2, v2 in item.items():
                            if k2 in ("blocked_claims",):
                                continue
                            if isinstance(v2, str):
                                parts.append(v2)
                            elif isinstance(v2, list):
                                parts.extend(str(x) for x in v2 if isinstance(x, str))
        return " ".join(parts).lower()

    @pytest.mark.parametrize("phrase", _UNSAFE_PHRASES)
    def test_phrase_absent_from_selection_report(self, phrase, tmp_path):
        result = _export_text(_UAV_MISSION, tmp_path)
        report = _read_report(result, "engineering_knowledge_selection_report.json")
        text = self._collect_descriptive_text(report)
        assert phrase not in text, (
            f"Unsafe phrase '{phrase}' found in knowledge selection report"
        )

    @pytest.mark.parametrize("phrase", _UNSAFE_PHRASES)
    def test_phrase_absent_from_readiness_report(self, phrase, tmp_path):
        result = _export_text(_UAV_MISSION, tmp_path)
        report = _read_report(result, "engineering_input_readiness_report.json")
        text = self._collect_descriptive_text(report)
        assert phrase not in text, (
            f"Unsafe phrase '{phrase}' found in input readiness report"
        )

    @pytest.mark.parametrize("phrase", _UNSAFE_PHRASES)
    def test_phrase_absent_from_calc_report(self, phrase, tmp_path):
        mr = _make_mission_result(
            mission=_UAV_MISSION,
            engineering_inputs={"total_thrust_n": 50.0, "mass_kg": 2.0},
        )
        result = _export(mr, tmp_path)
        report = _read_report(result, "engineering_calculation_report.json")
        text = self._collect_descriptive_text(report)
        assert phrase not in text, (
            f"Unsafe phrase '{phrase}' found in calculation report"
        )


# ---------------------------------------------------------------------------
# 7. Existing export keys remain unchanged
# ---------------------------------------------------------------------------

class TestExistingExportKeysUnchanged:
    _REQUIRED_KEYS = (
        "status", "folder_name", "export_dir", "files", "file_count",
        "ros2_generation", "ros2_validation", "fusion360_generation",
        "kicad_generation", "kicad_validation", "morphology_validation",
        "mission_report", "graph_review", "cortex", "aeroforge", "visual_bay",
    )

    def test_all_pre_existing_keys_still_present(self, tmp_path):
        result = _export_text(_GENERIC_MISSION, tmp_path)
        for key in self._REQUIRED_KEYS:
            assert key in result, f"Pre-existing key '{key}' missing from export result"

    def test_engineering_brain_key_is_additive(self, tmp_path):
        result = _export_text(_GENERIC_MISSION, tmp_path)
        assert "engineering_brain" in result
        for key in self._REQUIRED_KEYS:
            assert key in result, f"Key '{key}' lost after adding engineering_brain"

    def test_export_status_still_exported(self, tmp_path):
        result = _export_text(_GENERIC_MISSION, tmp_path)
        assert result["status"] == "exported"

    def test_cortex_keys_intact(self, tmp_path):
        result = _export_text(_GENERIC_MISSION, tmp_path)
        cortex = result["cortex"]
        for key in ("design_understanding", "candidate_evaluation",
                    "mission_intent", "pluto_safety_gate"):
            assert key in cortex, f"cortex key '{key}' missing"

    def test_visual_bay_key_intact(self, tmp_path):
        result = _export_text(_GENERIC_MISSION, tmp_path)
        assert "visual_bay" in result
        assert isinstance(result["visual_bay"], dict)


# ---------------------------------------------------------------------------
# 8. Failure containment — engineering brain failure must not break export
# ---------------------------------------------------------------------------

class TestEngineeringBrainFailureContainment:
    def test_export_succeeds_when_brain_raises(self, tmp_path):
        with patch(
            "backend.app.export.export_manager._write_engineering_brain",
            side_effect=RuntimeError("simulated brain failure"),
        ):
            result = _export_text(_GENERIC_MISSION, tmp_path)
        assert result["status"] == "exported"

    def test_engineering_brain_status_failed_on_error(self, tmp_path):
        with patch(
            "backend.app.export.export_manager._write_engineering_brain",
            side_effect=RuntimeError("simulated brain failure"),
        ):
            result = _export_text(_GENERIC_MISSION, tmp_path)
        assert result["engineering_brain"]["status"] == "failed"

    def test_engineering_brain_error_field_present_on_failure(self, tmp_path):
        with patch(
            "backend.app.export.export_manager._write_engineering_brain",
            side_effect=RuntimeError("simulated brain failure"),
        ):
            result = _export_text(_GENERIC_MISSION, tmp_path)
        assert "error" in result["engineering_brain"]

    def test_other_export_keys_intact_on_brain_failure(self, tmp_path):
        with patch(
            "backend.app.export.export_manager._write_engineering_brain",
            side_effect=RuntimeError("simulated brain failure"),
        ):
            result = _export_text(_GENERIC_MISSION, tmp_path)
        for key in ("status", "files", "cortex", "visual_bay"):
            assert key in result

    def test_error_message_truncated_to_safe_length(self, tmp_path):
        long_error = "x" * 1000
        with patch(
            "backend.app.export.export_manager._write_engineering_brain",
            side_effect=RuntimeError(long_error),
        ):
            result = _export_text(_GENERIC_MISSION, tmp_path)
        error_str = result["engineering_brain"].get("error", "")
        assert len(error_str) <= 500


# ---------------------------------------------------------------------------
# 9. Report file content has correct schema fields
# ---------------------------------------------------------------------------

class TestReportFileContent:
    def test_selection_report_has_schema_field(self, tmp_path):
        result = _export_text(_GENERIC_MISSION, tmp_path)
        report = _read_report(result, "engineering_knowledge_selection_report.json")
        assert report.get("schema") == "engineering_knowledge_selection_report.v1"

    def test_selection_report_has_phase_17b(self, tmp_path):
        result = _export_text(_GENERIC_MISSION, tmp_path)
        report = _read_report(result, "engineering_knowledge_selection_report.json")
        assert report.get("phase") == "17B"

    def test_readiness_report_has_schema_field(self, tmp_path):
        result = _export_text(_GENERIC_MISSION, tmp_path)
        report = _read_report(result, "engineering_input_readiness_report.json")
        assert report.get("schema") == "engineering_input_readiness_report.v1"

    def test_readiness_report_has_phase_17c(self, tmp_path):
        result = _export_text(_GENERIC_MISSION, tmp_path)
        report = _read_report(result, "engineering_input_readiness_report.json")
        assert report.get("phase") == "17C"

    def test_calc_report_has_schema_field(self, tmp_path):
        result = _export_text(_GENERIC_MISSION, tmp_path)
        report = _read_report(result, "engineering_calculation_report.json")
        assert report.get("schema") == "engineering_calculation_report.v1"

    def test_calc_report_has_phase_17d(self, tmp_path):
        result = _export_text(_GENERIC_MISSION, tmp_path)
        report = _read_report(result, "engineering_calculation_report.json")
        assert report.get("phase") == "17D"

    def test_calc_report_calculation_performed_is_bool(self, tmp_path):
        result = _export_text(_GENERIC_MISSION, tmp_path)
        report = _read_report(result, "engineering_calculation_report.json")
        assert isinstance(report.get("calculation_performed"), bool)

    def test_selection_report_selected_checks_is_list(self, tmp_path):
        result = _export_text(_GENERIC_MISSION, tmp_path)
        report = _read_report(result, "engineering_knowledge_selection_report.json")
        assert isinstance(report.get("selected_checks"), list)

    def test_readiness_report_checks_is_list(self, tmp_path):
        result = _export_text(_GENERIC_MISSION, tmp_path)
        report = _read_report(result, "engineering_input_readiness_report.json")
        assert isinstance(report.get("checks"), list)

    def test_calc_report_results_is_list(self, tmp_path):
        result = _export_text(_GENERIC_MISSION, tmp_path)
        report = _read_report(result, "engineering_calculation_report.json")
        assert isinstance(report.get("results"), list)

    def test_calc_report_blocked_results_is_list(self, tmp_path):
        result = _export_text(_GENERIC_MISSION, tmp_path)
        report = _read_report(result, "engineering_calculation_report.json")
        assert isinstance(report.get("blocked_results"), list)


# ---------------------------------------------------------------------------
# 10. _extract_engineering_inputs helper
# ---------------------------------------------------------------------------

class TestExtractEngineeringInputs:
    def test_returns_none_when_no_inputs(self):
        from backend.app.export.export_manager import _extract_engineering_inputs
        mr = _make_mission_result()
        assert _extract_engineering_inputs(mr) is None

    def test_returns_from_engineering_inputs_top_level(self):
        from backend.app.export.export_manager import _extract_engineering_inputs
        mr = _make_mission_result(engineering_inputs={"mass_kg": 2.0})
        result = _extract_engineering_inputs(mr)
        assert result == {"mass_kg": 2.0}

    def test_returns_from_artifacts_engineering_inputs(self):
        from backend.app.export.export_manager import _extract_engineering_inputs
        mr = _make_mission_result(
            artifacts={"engineering_inputs": {"battery_capacity_wh": 100.0}}
        )
        result = _extract_engineering_inputs(mr)
        assert result == {"battery_capacity_wh": 100.0}

    def test_artifacts_takes_priority_over_top_level(self):
        from backend.app.export.export_manager import _extract_engineering_inputs
        mr = _make_mission_result(
            artifacts={"engineering_inputs": {"from": "artifacts"}},
            engineering_inputs={"from": "top_level"},
        )
        result = _extract_engineering_inputs(mr)
        assert result == {"from": "artifacts"}

    def test_returns_none_for_non_dict_mission_result(self):
        from backend.app.export.export_manager import _extract_engineering_inputs
        assert _extract_engineering_inputs(None) is None
        assert _extract_engineering_inputs("not a dict") is None

    def test_returns_none_for_empty_engineering_inputs_dict(self):
        from backend.app.export.export_manager import _extract_engineering_inputs
        mr = _make_mission_result(engineering_inputs={})
        assert _extract_engineering_inputs(mr) is None
