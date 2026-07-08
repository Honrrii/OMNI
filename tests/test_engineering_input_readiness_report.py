"""
Tests for OMNI Phase 17C — Engineering Input Readiness Report.

All tests are local, deterministic, and run without LLM calls,
internet access, simulation, or numeric computation.
"""
from __future__ import annotations

import pytest

from backend.app.engineering.input_readiness_report import (
    _is_present,
    build_engineering_input_readiness_report,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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

_REPORT_TOP_LEVEL_FIELDS = [
    "schema", "status", "phase", "platform_intent",
    "platform_resolution_source", "calculation_performed",
    "readiness_summary", "checks", "missing_input_summary",
    "ready_check_ids", "blocked_claims", "safety_notes", "rationale",
]

_READINESS_SUMMARY_FIELDS = [
    "total_checks", "ready_count", "partial_count",
    "missing_count", "overall_status",
]

_CHECK_FIELDS = [
    "check_id", "domain", "title", "required_inputs", "provided_inputs",
    "missing_inputs", "readiness_status", "calculation_status",
    "missing_input_behavior", "safety_notes", "blocked_claims",
]

# Known registry entries and their required_inputs (from Phase 17A):
# thrust_to_weight_ratio  → ["total_thrust_n", "total_mass_kg"]
# battery_runtime_estimate → ["battery_capacity_wh", "average_power_draw_w"]
# torque_required_basic   → ["load_kg", "moment_arm_m"]
# mass_budget             → ["target_mass_kg", "subsystem_mass_estimates"]

_TWR_INPUTS   = {"total_thrust_n": 25.0, "total_mass_kg": 2.5}
_BAT_INPUTS   = {"battery_capacity_wh": 100.0, "average_power_draw_w": 50.0}
_TORQ_INPUTS  = {"load_kg": 5.0, "moment_arm_m": 0.3}
_MASS_INPUTS  = {"target_mass_kg": 2.0, "subsystem_mass_estimates": [0.5, 0.8, 0.7]}


def _get_check(report: dict, check_id: str) -> dict | None:
    for chk in report["checks"]:
        if chk["check_id"] == check_id:
            return chk
    return None


def _check_ids(report: dict) -> set:
    return {chk["check_id"] for chk in report["checks"]}


def _descriptive_text(report: dict) -> str:
    """Collect all descriptive text fields, excluding blocked_claims lists."""
    parts = [
        report.get("rationale", ""),
        " ".join(report.get("safety_notes", [])),
    ]
    for chk in report.get("checks", []):
        parts.append(chk.get("title", ""))
        parts.extend(chk.get("safety_notes", []))
        parts.append(chk.get("readiness_status", ""))
        parts.append(chk.get("calculation_status", ""))
    return " ".join(parts).lower()


# ---------------------------------------------------------------------------
# 1. Report generates with schema / status / phase
# ---------------------------------------------------------------------------

class TestReportTopLevel:
    def test_returns_dict(self):
        report = build_engineering_input_readiness_report()
        assert isinstance(report, dict)

    def test_schema_field(self):
        report = build_engineering_input_readiness_report()
        assert report["schema"] == "engineering_input_readiness_report.v1"

    def test_status_field(self):
        report = build_engineering_input_readiness_report()
        assert report["status"] == "generated"

    def test_phase_field(self):
        report = build_engineering_input_readiness_report()
        assert report["phase"] == "17C"

    def test_all_top_level_fields_present(self):
        report = build_engineering_input_readiness_report()
        for field in _REPORT_TOP_LEVEL_FIELDS:
            assert field in report, f"Report missing top-level field '{field}'"

    def test_readiness_summary_has_required_fields(self):
        report = build_engineering_input_readiness_report()
        for field in _READINESS_SUMMARY_FIELDS:
            assert field in report["readiness_summary"], (
                f"readiness_summary missing '{field}'"
            )

    def test_checks_is_list(self):
        report = build_engineering_input_readiness_report()
        assert isinstance(report["checks"], list)

    def test_total_checks_matches_checks_list(self):
        report = build_engineering_input_readiness_report()
        assert report["readiness_summary"]["total_checks"] == len(report["checks"])


# ---------------------------------------------------------------------------
# 2. No provided_inputs produces inputs_missing
# ---------------------------------------------------------------------------

class TestNoprovidedInputs:
    @pytest.fixture
    def report(self):
        return build_engineering_input_readiness_report(platform_intent="drone")

    def test_overall_status_is_inputs_missing(self, report):
        assert report["readiness_summary"]["overall_status"] == "inputs_missing"

    def test_every_check_is_inputs_missing(self, report):
        for chk in report["checks"]:
            assert chk["readiness_status"] == "inputs_missing", (
                f"Check '{chk['check_id']}' expected inputs_missing, "
                f"got '{chk['readiness_status']}'"
            )

    def test_ready_count_is_zero(self, report):
        assert report["readiness_summary"]["ready_count"] == 0

    def test_partial_count_is_zero(self, report):
        assert report["readiness_summary"]["partial_count"] == 0

    def test_ready_check_ids_is_empty(self, report):
        assert report["ready_check_ids"] == []

    def test_provided_inputs_field_is_empty_for_all_checks(self, report):
        for chk in report["checks"]:
            assert chk["provided_inputs"] == [], (
                f"Check '{chk['check_id']}' has unexpected provided_inputs"
            )

    @pytest.mark.parametrize("intent", ["drone", "rover", "manipulator", None])
    def test_no_inputs_all_missing_for_all_platforms(self, intent):
        report = build_engineering_input_readiness_report(platform_intent=intent)
        for chk in report["checks"]:
            assert chk["readiness_status"] == "inputs_missing"


# ---------------------------------------------------------------------------
# 3. Full provided inputs → inputs_ready_for_calculation
# ---------------------------------------------------------------------------

class TestFullInputsReady:
    def test_twr_check_ready_when_both_inputs_provided(self):
        report = build_engineering_input_readiness_report(
            platform_intent="drone",
            provided_inputs=_TWR_INPUTS,
        )
        chk = _get_check(report, "thrust_to_weight_ratio")
        assert chk is not None
        assert chk["readiness_status"] == "inputs_ready_for_calculation"

    def test_twr_provided_inputs_lists_both_keys(self):
        report = build_engineering_input_readiness_report(
            platform_intent="drone",
            provided_inputs=_TWR_INPUTS,
        )
        chk = _get_check(report, "thrust_to_weight_ratio")
        assert set(chk["provided_inputs"]) == {"total_thrust_n", "total_mass_kg"}

    def test_twr_missing_inputs_is_empty_when_all_provided(self):
        report = build_engineering_input_readiness_report(
            platform_intent="drone",
            provided_inputs=_TWR_INPUTS,
        )
        chk = _get_check(report, "thrust_to_weight_ratio")
        assert chk["missing_inputs"] == []

    def test_twr_in_ready_check_ids(self):
        report = build_engineering_input_readiness_report(
            platform_intent="drone",
            provided_inputs=_TWR_INPUTS,
        )
        assert "thrust_to_weight_ratio" in report["ready_check_ids"]

    def test_torque_check_ready_when_all_provided(self):
        report = build_engineering_input_readiness_report(
            platform_intent="rover",
            provided_inputs=_TORQ_INPUTS,
        )
        chk = _get_check(report, "torque_required_basic")
        assert chk is not None
        assert chk["readiness_status"] == "inputs_ready_for_calculation"

    def test_overall_status_partial_when_only_one_check_ready(self):
        report = build_engineering_input_readiness_report(
            platform_intent="drone",
            provided_inputs=_TWR_INPUTS,  # only covers thrust_to_weight_ratio
        )
        # Other checks still missing so overall should be partial or missing
        overall = report["readiness_summary"]["overall_status"]
        assert overall in ("inputs_partial", "inputs_missing")


# ---------------------------------------------------------------------------
# 4. Partial provided inputs → inputs_partial
# ---------------------------------------------------------------------------

class TestPartialInputs:
    def test_twr_partial_when_only_one_input_provided(self):
        report = build_engineering_input_readiness_report(
            platform_intent="drone",
            provided_inputs={"total_thrust_n": 25.0},   # missing total_mass_kg
        )
        chk = _get_check(report, "thrust_to_weight_ratio")
        assert chk["readiness_status"] == "inputs_partial"

    def test_missing_inputs_lists_absent_key(self):
        report = build_engineering_input_readiness_report(
            platform_intent="drone",
            provided_inputs={"total_thrust_n": 25.0},
        )
        chk = _get_check(report, "thrust_to_weight_ratio")
        assert "total_mass_kg" in chk["missing_inputs"]

    def test_provided_inputs_lists_present_key(self):
        report = build_engineering_input_readiness_report(
            platform_intent="drone",
            provided_inputs={"total_thrust_n": 25.0},
        )
        chk = _get_check(report, "thrust_to_weight_ratio")
        assert "total_thrust_n" in chk["provided_inputs"]

    def test_overall_partial_when_some_checks_partial(self):
        report = build_engineering_input_readiness_report(
            platform_intent="drone",
            provided_inputs={"total_thrust_n": 25.0},
        )
        overall = report["readiness_summary"]["overall_status"]
        assert overall == "inputs_partial"

    def test_partial_count_incremented(self):
        report = build_engineering_input_readiness_report(
            platform_intent="drone",
            provided_inputs={"total_thrust_n": 25.0},
        )
        assert report["readiness_summary"]["partial_count"] >= 1


# ---------------------------------------------------------------------------
# 5. Numeric zero counts as present
# ---------------------------------------------------------------------------

class TestZeroCountsAsPresent:
    def test_zero_thrust_counts_as_present(self):
        provided = {"total_thrust_n": 0, "total_mass_kg": 2.5}
        report = build_engineering_input_readiness_report(
            platform_intent="drone",
            provided_inputs=provided,
        )
        chk = _get_check(report, "thrust_to_weight_ratio")
        assert "total_thrust_n" in chk["provided_inputs"]

    def test_zero_for_both_inputs_gives_ready(self):
        provided = {"total_thrust_n": 0, "total_mass_kg": 0}
        report = build_engineering_input_readiness_report(
            platform_intent="drone",
            provided_inputs=provided,
        )
        chk = _get_check(report, "thrust_to_weight_ratio")
        assert chk["readiness_status"] == "inputs_ready_for_calculation"

    def test_zero_float_counts_as_present(self):
        assert _is_present(0.0) is True

    def test_zero_int_counts_as_present(self):
        assert _is_present(0) is True

    def test_nonzero_number_counts_as_present(self):
        assert _is_present(42.5) is True
        assert _is_present(-1) is True


# ---------------------------------------------------------------------------
# 6. False counts as present
# ---------------------------------------------------------------------------

class TestFalseCountsAsPresent:
    def test_false_counts_as_present_helper(self):
        assert _is_present(False) is True

    def test_false_value_for_input_marks_it_as_provided(self):
        provided = {"total_thrust_n": False, "total_mass_kg": 2.5}
        report = build_engineering_input_readiness_report(
            platform_intent="drone",
            provided_inputs=provided,
        )
        chk = _get_check(report, "thrust_to_weight_ratio")
        assert "total_thrust_n" in chk["provided_inputs"]

    def test_false_for_both_inputs_gives_ready(self):
        provided = {"total_thrust_n": False, "total_mass_kg": False}
        report = build_engineering_input_readiness_report(
            platform_intent="drone",
            provided_inputs=provided,
        )
        chk = _get_check(report, "thrust_to_weight_ratio")
        assert chk["readiness_status"] == "inputs_ready_for_calculation"

    def test_true_also_counts_as_present(self):
        assert _is_present(True) is True


# ---------------------------------------------------------------------------
# 7. None, empty string, empty list, empty dict count as missing
# ---------------------------------------------------------------------------

class TestMissingValueTypes:
    @pytest.mark.parametrize("missing_val", [None, "", [], {}])
    def test_is_present_returns_false(self, missing_val):
        assert _is_present(missing_val) is False

    @pytest.mark.parametrize("missing_val", [None, "", [], {}])
    def test_check_partial_when_one_input_is_missing_value(self, missing_val):
        provided = {"total_thrust_n": missing_val, "total_mass_kg": 2.5}
        report = build_engineering_input_readiness_report(
            platform_intent="drone",
            provided_inputs=provided,
        )
        chk = _get_check(report, "thrust_to_weight_ratio")
        assert chk["readiness_status"] == "inputs_partial"
        assert "total_thrust_n" in chk["missing_inputs"]

    @pytest.mark.parametrize("missing_val", [None, "", [], {}])
    def test_check_missing_when_all_inputs_are_missing_values(self, missing_val):
        provided = {"total_thrust_n": missing_val, "total_mass_kg": missing_val}
        report = build_engineering_input_readiness_report(
            platform_intent="drone",
            provided_inputs=provided,
        )
        chk = _get_check(report, "thrust_to_weight_ratio")
        assert chk["readiness_status"] == "inputs_missing"

    def test_key_exists_but_none_still_missing(self):
        provided = {"total_thrust_n": None, "total_mass_kg": None}
        report = build_engineering_input_readiness_report(
            platform_intent="drone",
            provided_inputs=provided,
        )
        chk = _get_check(report, "thrust_to_weight_ratio")
        assert set(chk["missing_inputs"]) == {"total_thrust_n", "total_mass_kg"}
        assert chk["provided_inputs"] == []


# ---------------------------------------------------------------------------
# 8. No calculation is performed
# ---------------------------------------------------------------------------

class TestNoCalculationPerformed:
    def test_no_result_field_in_checks(self):
        provided = {**_TWR_INPUTS}
        report = build_engineering_input_readiness_report(
            platform_intent="drone",
            provided_inputs=provided,
        )
        for chk in report["checks"]:
            assert "result" not in chk
            assert "value" not in chk
            assert "computed_value" not in chk

    def test_no_numeric_output_values_in_report(self):
        provided = {**_TWR_INPUTS, **_BAT_INPUTS}
        report = build_engineering_input_readiness_report(
            platform_intent="drone",
            provided_inputs=provided,
        )
        assert "thrust_to_weight_ratio" not in report
        assert "hover_margin_ratio" not in report
        assert "estimated_runtime_h" not in report

    def test_ready_check_has_no_computed_output_values(self):
        provided = {**_TWR_INPUTS}
        report = build_engineering_input_readiness_report(
            platform_intent="drone",
            provided_inputs=provided,
        )
        chk = _get_check(report, "thrust_to_weight_ratio")
        assert chk["readiness_status"] == "inputs_ready_for_calculation"
        # readiness does not mean calculation happened
        assert "thrust_to_weight_ratio" not in chk
        assert "hover_margin" not in chk


# ---------------------------------------------------------------------------
# 9. calculation_performed is False
# ---------------------------------------------------------------------------

class TestCalculationPerformedIsFalse:
    @pytest.mark.parametrize("intent,inputs", [
        ("drone", _TWR_INPUTS),
        ("rover", _TORQ_INPUTS),
        ("manipulator", _TORQ_INPUTS),
        (None, {}),
    ])
    def test_calculation_performed_is_false(self, intent, inputs):
        report = build_engineering_input_readiness_report(
            platform_intent=intent,
            provided_inputs=inputs,
        )
        assert report["calculation_performed"] is False

    def test_calculation_performed_type_is_bool(self):
        report = build_engineering_input_readiness_report()
        assert isinstance(report["calculation_performed"], bool)


# ---------------------------------------------------------------------------
# 10. calculation_status is not_computed_phase_17c
# ---------------------------------------------------------------------------

class TestCalculationStatus:
    @pytest.mark.parametrize("intent,inputs", [
        ("drone", _TWR_INPUTS),
        ("rover", {}),
        (None, _MASS_INPUTS),
    ])
    def test_all_checks_have_correct_calculation_status(self, intent, inputs):
        report = build_engineering_input_readiness_report(
            platform_intent=intent,
            provided_inputs=inputs,
        )
        for chk in report["checks"]:
            assert chk["calculation_status"] == "not_computed_phase_17c", (
                f"Check '{chk['check_id']}' has wrong calculation_status"
            )

    def test_ready_check_still_has_not_computed_status(self):
        provided = {**_TWR_INPUTS}
        report = build_engineering_input_readiness_report(
            platform_intent="drone",
            provided_inputs=provided,
        )
        chk = _get_check(report, "thrust_to_weight_ratio")
        assert chk["readiness_status"] == "inputs_ready_for_calculation"
        assert chk["calculation_status"] == "not_computed_phase_17c"


# ---------------------------------------------------------------------------
# 11. UAV readiness includes thrust_to_weight_ratio
# ---------------------------------------------------------------------------

class TestUavReadiness:
    @pytest.mark.parametrize("intent", ["drone", "UAV", "quadcopter", "aerial"])
    def test_uav_includes_twr_check(self, intent):
        report = build_engineering_input_readiness_report(platform_intent=intent)
        assert "thrust_to_weight_ratio" in _check_ids(report)

    def test_uav_twr_ready_when_inputs_provided(self):
        report = build_engineering_input_readiness_report(
            platform_intent="drone",
            provided_inputs=_TWR_INPUTS,
        )
        chk = _get_check(report, "thrust_to_weight_ratio")
        assert chk["readiness_status"] == "inputs_ready_for_calculation"

    def test_uav_twr_missing_when_no_inputs(self):
        report = build_engineering_input_readiness_report(platform_intent="drone")
        chk = _get_check(report, "thrust_to_weight_ratio")
        assert chk["readiness_status"] == "inputs_missing"


# ---------------------------------------------------------------------------
# 12. Rover readiness includes torque_required_basic
# ---------------------------------------------------------------------------

class TestRoverReadiness:
    @pytest.mark.parametrize("intent", ["rover", "ground robot", "wheeled vehicle"])
    def test_rover_includes_torque_check(self, intent):
        report = build_engineering_input_readiness_report(platform_intent=intent)
        assert "torque_required_basic" in _check_ids(report)

    def test_rover_torque_ready_when_inputs_provided(self):
        report = build_engineering_input_readiness_report(
            platform_intent="rover",
            provided_inputs=_TORQ_INPUTS,
        )
        chk = _get_check(report, "torque_required_basic")
        assert chk["readiness_status"] == "inputs_ready_for_calculation"

    def test_rover_torque_missing_when_no_inputs(self):
        report = build_engineering_input_readiness_report(platform_intent="rover")
        chk = _get_check(report, "torque_required_basic")
        assert chk["readiness_status"] == "inputs_missing"


# ---------------------------------------------------------------------------
# 13. Manipulator readiness includes torque_required_basic
# ---------------------------------------------------------------------------

class TestManipulatorReadiness:
    @pytest.mark.parametrize("intent", ["manipulator", "robot arm", "gripper"])
    def test_manipulator_includes_torque_check(self, intent):
        report = build_engineering_input_readiness_report(platform_intent=intent)
        assert "torque_required_basic" in _check_ids(report)

    def test_manipulator_torque_ready_when_inputs_provided(self):
        report = build_engineering_input_readiness_report(
            platform_intent="manipulator",
            provided_inputs=_TORQ_INPUTS,
        )
        chk = _get_check(report, "torque_required_basic")
        assert chk["readiness_status"] == "inputs_ready_for_calculation"

    def test_manipulator_includes_safety_margin_review(self):
        report = build_engineering_input_readiness_report(platform_intent="robot arm")
        assert "safety_margin_review" in _check_ids(report)


# ---------------------------------------------------------------------------
# 14. Unknown platform uses conservative base checks
# ---------------------------------------------------------------------------

class TestUnknownPlatformReadiness:
    @pytest.mark.parametrize("intent", [None, "", "unrecognised", "spaceship"])
    def test_conservative_base_checks_present(self, intent):
        report = build_engineering_input_readiness_report(platform_intent=intent)
        ids = _check_ids(report)
        assert "mass_budget" in ids
        assert "power_budget" in ids
        assert "sensor_coverage_check" in ids
        assert "safety_margin_review" in ids
        assert "simulation_readiness" in ids

    def test_unknown_does_not_include_twr(self):
        report = build_engineering_input_readiness_report(platform_intent=None)
        assert "thrust_to_weight_ratio" not in _check_ids(report)

    def test_overall_missing_when_no_inputs_and_unknown_platform(self):
        report = build_engineering_input_readiness_report()
        assert report["readiness_summary"]["overall_status"] == "inputs_missing"


# ---------------------------------------------------------------------------
# 15. Missing input summary is deduped
# ---------------------------------------------------------------------------

class TestMissingInputSummaryDedup:
    def test_missing_input_summary_has_no_duplicates(self):
        report = build_engineering_input_readiness_report(platform_intent="drone")
        summary = report["missing_input_summary"]
        assert len(summary) == len(set(summary)), "missing_input_summary contains duplicates"

    def test_missing_input_summary_is_list(self):
        report = build_engineering_input_readiness_report()
        assert isinstance(report["missing_input_summary"], list)

    def test_missing_input_summary_nonempty_when_inputs_absent(self):
        report = build_engineering_input_readiness_report(platform_intent="drone")
        assert len(report["missing_input_summary"]) >= 1

    def test_missing_input_summary_empty_when_all_ready(self):
        # Provide every required input for every UAV check
        all_inputs = {
            **_TWR_INPUTS,
            **_BAT_INPUTS,
            "target_mass_kg": 2.0,
            "subsystem_mass_estimates": [0.5, 0.8],
            "supply_capacity_w": 200.0,
            "subsystem_power_estimates_w": [50.0, 30.0],
            "efficiency_factor": 0.9,
            "depth_of_discharge_fraction": 0.8,
            "component_list": ["ESC", "motor"],
            "power_dissipation_estimates_w": [10.0, 5.0],
            "platform_description": "drone",
            "declared_margins": {"mass": 0.2},
        }
        report = build_engineering_input_readiness_report(
            platform_intent="drone",
            provided_inputs=all_inputs,
        )
        assert report["missing_input_summary"] == []

    def test_provided_inputs_for_twr_not_in_missing_summary(self):
        provided = {**_TWR_INPUTS}
        report = build_engineering_input_readiness_report(
            platform_intent="drone",
            provided_inputs=provided,
        )
        for key in _TWR_INPUTS:
            assert key not in report["missing_input_summary"]


# ---------------------------------------------------------------------------
# 16. Ready check IDs are listed
# ---------------------------------------------------------------------------

class TestReadyCheckIds:
    def test_ready_check_ids_is_list(self):
        report = build_engineering_input_readiness_report()
        assert isinstance(report["ready_check_ids"], list)

    def test_ready_check_ids_empty_when_no_inputs(self):
        report = build_engineering_input_readiness_report(platform_intent="drone")
        assert report["ready_check_ids"] == []

    def test_ready_check_ids_contains_twr_when_inputs_provided(self):
        report = build_engineering_input_readiness_report(
            platform_intent="drone",
            provided_inputs=_TWR_INPUTS,
        )
        assert "thrust_to_weight_ratio" in report["ready_check_ids"]

    def test_ready_check_ids_does_not_contain_partial_checks(self):
        report = build_engineering_input_readiness_report(
            platform_intent="drone",
            provided_inputs={"total_thrust_n": 25.0},  # partial for twr
        )
        assert "thrust_to_weight_ratio" not in report["ready_check_ids"]

    def test_ready_count_matches_ready_check_ids_length(self):
        provided = {**_TWR_INPUTS, **_BAT_INPUTS}
        report = build_engineering_input_readiness_report(
            platform_intent="drone",
            provided_inputs=provided,
        )
        assert report["readiness_summary"]["ready_count"] == len(report["ready_check_ids"])

    def test_ready_check_ids_are_valid_check_ids(self):
        provided = {**_TWR_INPUTS}
        report = build_engineering_input_readiness_report(
            platform_intent="drone",
            provided_inputs=provided,
        )
        all_ids = _check_ids(report)
        for rid in report["ready_check_ids"]:
            assert rid in all_ids


# ---------------------------------------------------------------------------
# 17. Blocked claims and safety notes are aggregated
# ---------------------------------------------------------------------------

class TestAggregation:
    def test_blocked_claims_is_list(self):
        report = build_engineering_input_readiness_report(platform_intent="drone")
        assert isinstance(report["blocked_claims"], list)

    def test_blocked_claims_deduped(self):
        report = build_engineering_input_readiness_report(platform_intent="drone")
        bc = report["blocked_claims"]
        assert len(bc) == len(set(bc)), "blocked_claims contains duplicates"

    def test_blocked_claims_nonempty(self):
        report = build_engineering_input_readiness_report(platform_intent="drone")
        assert len(report["blocked_claims"]) >= 1

    def test_validated_in_blocked_claims(self):
        report = build_engineering_input_readiness_report(platform_intent="drone")
        assert "validated" in report["blocked_claims"]

    def test_safety_notes_is_list(self):
        report = build_engineering_input_readiness_report(platform_intent="drone")
        assert isinstance(report["safety_notes"], list)

    def test_safety_notes_deduped(self):
        report = build_engineering_input_readiness_report(platform_intent="drone")
        sn = report["safety_notes"]
        assert len(sn) == len(set(sn)), "safety_notes contains duplicates"

    def test_safety_header_is_first_safety_note(self):
        report = build_engineering_input_readiness_report(platform_intent="drone")
        assert report["safety_notes"][0].startswith("No engineering calculation performed.")

    def test_check_safety_notes_nonempty(self):
        report = build_engineering_input_readiness_report(platform_intent="drone")
        for chk in report["checks"]:
            assert len(chk["safety_notes"]) >= 1, (
                f"Check '{chk['check_id']}' has empty safety_notes"
            )

    def test_check_blocked_claims_nonempty(self):
        report = build_engineering_input_readiness_report(platform_intent="drone")
        for chk in report["checks"]:
            assert len(chk["blocked_claims"]) >= 1, (
                f"Check '{chk['check_id']}' has empty blocked_claims"
            )


# ---------------------------------------------------------------------------
# 18. No unsafe positive claims in output
# ---------------------------------------------------------------------------

class TestNoUnsafeClaims:
    @pytest.mark.parametrize("phrase", _UNSAFE_PHRASES)
    def test_unsafe_phrase_absent_from_descriptive_fields(self, phrase):
        for intent in ("drone", "rover", "manipulator", None):
            report = build_engineering_input_readiness_report(
                platform_intent=intent,
                provided_inputs=_TWR_INPUTS if intent == "drone" else _TORQ_INPUTS,
            )
            text = _descriptive_text(report)
            assert phrase not in text, (
                f"Unsafe phrase '{phrase}' found in descriptive fields "
                f"for platform_intent='{intent}'"
            )

    def test_rationale_free_of_unsafe_phrases(self):
        for intent in ("drone", "rover", "manipulator", None):
            report = build_engineering_input_readiness_report(platform_intent=intent)
            rationale = report["rationale"].lower()
            for phrase in _UNSAFE_PHRASES:
                assert phrase not in rationale, (
                    f"Unsafe phrase '{phrase}' found in rationale for '{intent}'"
                )

    def test_safety_header_free_of_unsafe_phrases(self):
        report = build_engineering_input_readiness_report(platform_intent="drone")
        header = report["safety_notes"][0].lower()
        for phrase in _UNSAFE_PHRASES:
            assert phrase not in header


# ---------------------------------------------------------------------------
# 19. Mutation safety
# ---------------------------------------------------------------------------

class TestMutationSafety:
    def test_mutating_checks_does_not_affect_second_call(self):
        report1 = build_engineering_input_readiness_report(platform_intent="drone")
        if report1["checks"]:
            report1["checks"][0]["title"] = "MUTATED"
        report2 = build_engineering_input_readiness_report(platform_intent="drone")
        if report2["checks"]:
            assert report2["checks"][0]["title"] != "MUTATED"

    def test_mutating_safety_notes_does_not_affect_second_call(self):
        report1 = build_engineering_input_readiness_report(platform_intent="rover")
        original_len = len(report1["safety_notes"])
        report1["safety_notes"].append("INJECTED")
        report2 = build_engineering_input_readiness_report(platform_intent="rover")
        assert len(report2["safety_notes"]) == original_len

    def test_mutating_provided_inputs_dict_does_not_affect_report(self):
        inputs = {"total_thrust_n": 25.0, "total_mass_kg": 2.5}
        report = build_engineering_input_readiness_report(
            platform_intent="drone",
            provided_inputs=inputs,
        )
        chk_before = _get_check(report, "thrust_to_weight_ratio")
        status_before = chk_before["readiness_status"]
        # mutate the original dict after report is built
        inputs["total_thrust_n"] = None
        chk_after = _get_check(report, "thrust_to_weight_ratio")
        assert chk_after["readiness_status"] == status_before

    def test_mutating_blocked_claims_does_not_affect_second_call(self):
        report1 = build_engineering_input_readiness_report(platform_intent="drone")
        original_len = len(report1["blocked_claims"])
        report1["blocked_claims"].append("INJECTED")
        report2 = build_engineering_input_readiness_report(platform_intent="drone")
        assert len(report2["blocked_claims"]) == original_len

    def test_mutating_ready_check_ids_does_not_affect_second_call(self):
        provided = {**_TWR_INPUTS}
        report1 = build_engineering_input_readiness_report(
            platform_intent="drone",
            provided_inputs=provided,
        )
        original_len = len(report1["ready_check_ids"])
        report1["ready_check_ids"].append("fake_check_id")
        report2 = build_engineering_input_readiness_report(
            platform_intent="drone",
            provided_inputs=provided,
        )
        assert len(report2["ready_check_ids"]) == original_len
