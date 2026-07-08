"""
Tests for OMNI Phase 17D — Engineering Calculation Engine.

All tests are local, deterministic, and run without LLM calls,
internet access, simulation, or external computation.
"""
from __future__ import annotations

import math
import pytest

from backend.app.engineering.calculation_engine import (
    _G,
    _to_float,
    build_engineering_calculation_report,
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

_RESULT_FIELDS = [
    "check_id", "status", "metric_id", "value", "unit",
    "formula", "input_values", "input_sources",
    "assumptions", "warnings", "confidence", "safety_note",
]

_BLOCKED_FIELDS = [
    "check_id", "status", "reason", "missing_inputs", "required_inputs",
]

_REPORT_TOP_LEVEL_FIELDS = [
    "schema", "status", "phase", "platform_intent",
    "platform_resolution_source", "calculation_performed",
    "supported_calculation_count", "computed_metric_count",
    "blocked_calculation_count", "results", "blocked_results",
    "safety_notes", "blocked_claims", "rationale",
]

# Canonical numeric inputs (engine-specific names, not registry names)
_BAT_INPUTS  = {"battery_capacity_wh": 100.0, "average_power_w": 50.0}
_PWR_INPUTS  = {"voltage_v": 12.0, "current_a": 5.0}
_TWR_INPUTS  = {"total_thrust_n": 50.0, "mass_kg": 2.0}
_ALL_DRONE   = {**_BAT_INPUTS, **_PWR_INPUTS, **_TWR_INPUTS}

_EXPECTED_RUNTIME  = 2.0                        # 100 / 50
_EXPECTED_POWER    = 60.0                        # 12 * 5
_EXPECTED_TWR      = 50.0 / (2.0 * _G)          # ≈ 2.549


def _get_result(report: dict, check_id: str) -> dict | None:
    return next((r for r in report["results"] if r["check_id"] == check_id), None)


def _get_blocked(report: dict, check_id: str) -> dict | None:
    return next((b for b in report["blocked_results"] if b["check_id"] == check_id), None)


def _descriptive_text(report: dict) -> str:
    parts = [
        report.get("rationale", ""),
        " ".join(report.get("safety_notes", [])),
    ]
    for r in report.get("results", []):
        parts.append(r.get("safety_note", ""))
        parts.extend(r.get("assumptions", []))
        parts.append(r.get("confidence", ""))
    return " ".join(parts).lower()


# ---------------------------------------------------------------------------
# 1. Report generates with schema / status / phase
# ---------------------------------------------------------------------------

class TestReportTopLevel:
    def test_returns_dict(self):
        report = build_engineering_calculation_report()
        assert isinstance(report, dict)

    def test_schema_field(self):
        report = build_engineering_calculation_report()
        assert report["schema"] == "engineering_calculation_report.v1"

    def test_status_field(self):
        report = build_engineering_calculation_report()
        assert report["status"] == "generated"

    def test_phase_field(self):
        report = build_engineering_calculation_report()
        assert report["phase"] == "17D"

    def test_all_top_level_fields_present(self):
        report = build_engineering_calculation_report()
        for field in _REPORT_TOP_LEVEL_FIELDS:
            assert field in report, f"Report missing top-level field '{field}'"

    def test_results_is_list(self):
        report = build_engineering_calculation_report()
        assert isinstance(report["results"], list)

    def test_blocked_results_is_list(self):
        report = build_engineering_calculation_report()
        assert isinstance(report["blocked_results"], list)


# ---------------------------------------------------------------------------
# 2. battery_runtime_estimate computes correctly
# ---------------------------------------------------------------------------

class TestBatteryRuntimeCalculation:
    @pytest.fixture
    def report(self):
        return build_engineering_calculation_report(
            platform_intent="drone",
            provided_inputs=_BAT_INPUTS,
        )

    def test_battery_runtime_appears_in_results(self, report):
        result = _get_result(report, "battery_runtime_estimate")
        assert result is not None, "battery_runtime_estimate not in results"

    def test_status_is_computed(self, report):
        assert _get_result(report, "battery_runtime_estimate")["status"] == "computed"

    def test_value_is_correct(self, report):
        result = _get_result(report, "battery_runtime_estimate")
        assert math.isclose(result["value"], _EXPECTED_RUNTIME, rel_tol=1e-9)

    def test_metric_id_is_runtime_hours(self, report):
        assert _get_result(report, "battery_runtime_estimate")["metric_id"] == "runtime_hours"

    def test_unit_is_hours(self, report):
        assert _get_result(report, "battery_runtime_estimate")["unit"] == "hours"

    def test_runtime_higher_capacity(self):
        report = build_engineering_calculation_report(
            platform_intent="drone",
            provided_inputs={"battery_capacity_wh": 200.0, "average_power_w": 50.0},
        )
        result = _get_result(report, "battery_runtime_estimate")
        assert math.isclose(result["value"], 4.0, rel_tol=1e-9)

    def test_runtime_higher_power(self):
        report = build_engineering_calculation_report(
            platform_intent="rover",
            provided_inputs={"battery_capacity_wh": 100.0, "average_power_w": 100.0},
        )
        result = _get_result(report, "battery_runtime_estimate")
        assert math.isclose(result["value"], 1.0, rel_tol=1e-9)


# ---------------------------------------------------------------------------
# 3. power_budget computes correctly
# ---------------------------------------------------------------------------

class TestPowerBudgetCalculation:
    @pytest.fixture
    def report(self):
        return build_engineering_calculation_report(
            platform_intent="drone",
            provided_inputs=_PWR_INPUTS,
        )

    def test_power_budget_appears_in_results(self, report):
        result = _get_result(report, "power_budget")
        assert result is not None, "power_budget not in results"

    def test_status_is_computed(self, report):
        assert _get_result(report, "power_budget")["status"] == "computed"

    def test_value_is_correct(self, report):
        result = _get_result(report, "power_budget")
        assert math.isclose(result["value"], _EXPECTED_POWER, rel_tol=1e-9)

    def test_metric_id_is_power_w(self, report):
        assert _get_result(report, "power_budget")["metric_id"] == "power_w"

    def test_unit_is_watts(self, report):
        assert _get_result(report, "power_budget")["unit"] == "W"

    def test_zero_current_gives_zero_power(self):
        report = build_engineering_calculation_report(
            platform_intent="drone",
            provided_inputs={"voltage_v": 12.0, "current_a": 0.0},
        )
        result = _get_result(report, "power_budget")
        assert result is not None
        assert math.isclose(result["value"], 0.0, abs_tol=1e-12)

    def test_zero_voltage_gives_zero_power(self):
        report = build_engineering_calculation_report(
            platform_intent="drone",
            provided_inputs={"voltage_v": 0.0, "current_a": 5.0},
        )
        result = _get_result(report, "power_budget")
        assert result is not None
        assert math.isclose(result["value"], 0.0, abs_tol=1e-12)


# ---------------------------------------------------------------------------
# 4. thrust_to_weight_ratio computes correctly
# ---------------------------------------------------------------------------

class TestThrustToWeightCalculation:
    @pytest.fixture
    def report(self):
        return build_engineering_calculation_report(
            platform_intent="drone",
            provided_inputs=_TWR_INPUTS,
        )

    def test_twr_appears_in_results(self, report):
        result = _get_result(report, "thrust_to_weight_ratio")
        assert result is not None, "thrust_to_weight_ratio not in results"

    def test_status_is_computed(self, report):
        assert _get_result(report, "thrust_to_weight_ratio")["status"] == "computed"

    def test_value_is_correct(self, report):
        result = _get_result(report, "thrust_to_weight_ratio")
        assert math.isclose(result["value"], _EXPECTED_TWR, rel_tol=1e-9)

    def test_metric_id_is_twr(self, report):
        assert _get_result(report, "thrust_to_weight_ratio")["metric_id"] == "twr"

    def test_unit_is_dimensionless(self, report):
        assert _get_result(report, "thrust_to_weight_ratio")["unit"] == "dimensionless"

    def test_twr_with_unit_mass(self):
        report = build_engineering_calculation_report(
            platform_intent="drone",
            provided_inputs={"total_thrust_n": 10.0, "mass_kg": 1.0},
        )
        result = _get_result(report, "thrust_to_weight_ratio")
        expected = 10.0 / (1.0 * _G)
        assert math.isclose(result["value"], expected, rel_tol=1e-9)

    def test_formula_contains_gravity_constant(self, report):
        result = _get_result(report, "thrust_to_weight_ratio")
        assert "9.80665" in result["formula"]


# ---------------------------------------------------------------------------
# 5. Missing inputs block calculation
# ---------------------------------------------------------------------------

class TestMissingInputsBlock:
    def test_no_inputs_blocks_all_supported_checks(self):
        report = build_engineering_calculation_report(platform_intent="drone")
        for calc_id in ("battery_runtime_estimate", "power_budget", "thrust_to_weight_ratio"):
            blocked = _get_blocked(report, calc_id)
            assert blocked is not None, f"Expected '{calc_id}' in blocked_results"

    def test_missing_all_inputs_reason_is_inputs_missing(self):
        report = build_engineering_calculation_report(platform_intent="drone")
        blocked = _get_blocked(report, "battery_runtime_estimate")
        assert blocked["reason"] == "inputs_missing"

    def test_blocked_result_lists_all_required_inputs(self):
        report = build_engineering_calculation_report(platform_intent="drone")
        blocked = _get_blocked(report, "battery_runtime_estimate")
        assert set(blocked["missing_inputs"]) == {"battery_capacity_wh", "average_power_w"}

    def test_computed_metric_count_is_zero_with_no_inputs(self):
        report = build_engineering_calculation_report(platform_intent="drone")
        assert report["computed_metric_count"] == 0


# ---------------------------------------------------------------------------
# 6. Partial inputs block calculation
# ---------------------------------------------------------------------------

class TestPartialInputsBlock:
    def test_one_of_two_battery_inputs_gives_partial(self):
        report = build_engineering_calculation_report(
            platform_intent="drone",
            provided_inputs={"battery_capacity_wh": 100.0},
        )
        blocked = _get_blocked(report, "battery_runtime_estimate")
        assert blocked is not None
        assert blocked["reason"] == "inputs_partial"

    def test_partial_missing_inputs_lists_absent_key(self):
        report = build_engineering_calculation_report(
            platform_intent="drone",
            provided_inputs={"battery_capacity_wh": 100.0},
        )
        blocked = _get_blocked(report, "battery_runtime_estimate")
        assert "average_power_w" in blocked["missing_inputs"]

    def test_partial_inputs_not_in_results(self):
        report = build_engineering_calculation_report(
            platform_intent="drone",
            provided_inputs={"total_thrust_n": 50.0},  # missing mass_kg
        )
        assert _get_result(report, "thrust_to_weight_ratio") is None

    def test_one_of_two_pwr_inputs_gives_partial(self):
        report = build_engineering_calculation_report(
            platform_intent="drone",
            provided_inputs={"voltage_v": 12.0},
        )
        blocked = _get_blocked(report, "power_budget")
        assert blocked["reason"] == "inputs_partial"


# ---------------------------------------------------------------------------
# 7. Unsupported checks are reported as unsupported_calculation
# ---------------------------------------------------------------------------

class TestUnsupportedChecks:
    _UNSUPPORTED_FOR_DRONE = {
        "mass_budget", "thermal_risk_basic",
        "simulation_readiness", "safety_margin_review",
    }

    @pytest.fixture
    def report(self):
        return build_engineering_calculation_report(
            platform_intent="drone",
            provided_inputs=_ALL_DRONE,
        )

    def test_unsupported_checks_appear_in_blocked_results(self, report):
        blocked_ids = {b["check_id"] for b in report["blocked_results"]}
        assert self._UNSUPPORTED_FOR_DRONE.issubset(blocked_ids), (
            f"Missing unsupported checks: {self._UNSUPPORTED_FOR_DRONE - blocked_ids}"
        )

    def test_unsupported_reason_is_correct(self, report):
        for check_id in self._UNSUPPORTED_FOR_DRONE:
            blocked = _get_blocked(report, check_id)
            assert blocked is not None
            assert blocked["reason"] == "unsupported_calculation", (
                f"Check '{check_id}' has wrong reason: {blocked['reason']}"
            )

    def test_unsupported_checks_have_empty_missing_inputs(self, report):
        for check_id in self._UNSUPPORTED_FOR_DRONE:
            blocked = _get_blocked(report, check_id)
            assert blocked["missing_inputs"] == []

    def test_unsupported_check_status_is_not_computed(self, report):
        for check_id in self._UNSUPPORTED_FOR_DRONE:
            blocked = _get_blocked(report, check_id)
            assert blocked["status"] == "not_computed"


# ---------------------------------------------------------------------------
# 8. average_power_w <= 0 blocks battery runtime
# ---------------------------------------------------------------------------

class TestBatteryRuntimeDomainConstraints:
    @pytest.mark.parametrize("power_val", [0, 0.0, -1.0, -100.0])
    def test_non_positive_power_blocks_calculation(self, power_val):
        report = build_engineering_calculation_report(
            platform_intent="drone",
            provided_inputs={"battery_capacity_wh": 100.0, "average_power_w": power_val},
        )
        assert _get_result(report, "battery_runtime_estimate") is None
        blocked = _get_blocked(report, "battery_runtime_estimate")
        assert blocked is not None
        assert blocked["reason"] == "invalid_input"

    def test_small_positive_power_computes(self):
        report = build_engineering_calculation_report(
            platform_intent="drone",
            provided_inputs={"battery_capacity_wh": 100.0, "average_power_w": 0.001},
        )
        result = _get_result(report, "battery_runtime_estimate")
        assert result is not None
        assert math.isclose(result["value"], 100_000.0, rel_tol=1e-6)


# ---------------------------------------------------------------------------
# 9. mass_kg <= 0 blocks thrust-to-weight
# ---------------------------------------------------------------------------

class TestThrustToWeightDomainConstraints:
    @pytest.mark.parametrize("mass_val", [0, 0.0, -0.5, -10.0])
    def test_non_positive_mass_blocks_calculation(self, mass_val):
        report = build_engineering_calculation_report(
            platform_intent="drone",
            provided_inputs={"total_thrust_n": 50.0, "mass_kg": mass_val},
        )
        assert _get_result(report, "thrust_to_weight_ratio") is None
        blocked = _get_blocked(report, "thrust_to_weight_ratio")
        assert blocked is not None
        assert blocked["reason"] == "invalid_input"

    def test_small_positive_mass_computes(self):
        report = build_engineering_calculation_report(
            platform_intent="drone",
            provided_inputs={"total_thrust_n": 1.0, "mass_kg": 0.001},
        )
        result = _get_result(report, "thrust_to_weight_ratio")
        assert result is not None
        expected = 1.0 / (0.001 * _G)
        assert math.isclose(result["value"], expected, rel_tol=1e-9)

    def test_negative_thrust_does_not_block(self):
        # Negative thrust is physically odd but the engine does not block it;
        # only mass constraint is enforced for this calculation.
        report = build_engineering_calculation_report(
            platform_intent="drone",
            provided_inputs={"total_thrust_n": -5.0, "mass_kg": 2.0},
        )
        result = _get_result(report, "thrust_to_weight_ratio")
        assert result is not None
        assert result["value"] < 0


# ---------------------------------------------------------------------------
# 10. Negative voltage / current blocks power budget
# ---------------------------------------------------------------------------

class TestPowerBudgetDomainConstraints:
    @pytest.mark.parametrize("voltage", [-0.001, -12.0, -100.0])
    def test_negative_voltage_blocks(self, voltage):
        report = build_engineering_calculation_report(
            platform_intent="drone",
            provided_inputs={"voltage_v": voltage, "current_a": 5.0},
        )
        assert _get_result(report, "power_budget") is None
        blocked = _get_blocked(report, "power_budget")
        assert blocked["reason"] == "invalid_input"

    @pytest.mark.parametrize("current", [-0.001, -5.0, -100.0])
    def test_negative_current_blocks(self, current):
        report = build_engineering_calculation_report(
            platform_intent="drone",
            provided_inputs={"voltage_v": 12.0, "current_a": current},
        )
        assert _get_result(report, "power_budget") is None
        blocked = _get_blocked(report, "power_budget")
        assert blocked["reason"] == "invalid_input"

    def test_both_zero_gives_zero_power(self):
        report = build_engineering_calculation_report(
            platform_intent="drone",
            provided_inputs={"voltage_v": 0.0, "current_a": 0.0},
        )
        result = _get_result(report, "power_budget")
        assert result is not None
        assert math.isclose(result["value"], 0.0, abs_tol=1e-12)


# ---------------------------------------------------------------------------
# 11. Numeric strings are converted safely
# ---------------------------------------------------------------------------

class TestNumericStringConversion:
    def test_battery_runtime_with_string_inputs(self):
        report = build_engineering_calculation_report(
            platform_intent="drone",
            provided_inputs={"battery_capacity_wh": "100", "average_power_w": "50"},
        )
        result = _get_result(report, "battery_runtime_estimate")
        assert result is not None
        assert math.isclose(result["value"], _EXPECTED_RUNTIME, rel_tol=1e-9)

    def test_twr_with_string_inputs(self):
        report = build_engineering_calculation_report(
            platform_intent="drone",
            provided_inputs={"total_thrust_n": "50.0", "mass_kg": "2.0"},
        )
        result = _get_result(report, "thrust_to_weight_ratio")
        assert result is not None
        assert math.isclose(result["value"], _EXPECTED_TWR, rel_tol=1e-9)

    def test_power_budget_with_string_inputs(self):
        report = build_engineering_calculation_report(
            platform_intent="drone",
            provided_inputs={"voltage_v": "12.0", "current_a": "5.0"},
        )
        result = _get_result(report, "power_budget")
        assert result is not None
        assert math.isclose(result["value"], _EXPECTED_POWER, rel_tol=1e-9)

    def test_string_conversion_adds_warning(self):
        report = build_engineering_calculation_report(
            platform_intent="drone",
            provided_inputs={"battery_capacity_wh": "100", "average_power_w": "50"},
        )
        result = _get_result(report, "battery_runtime_estimate")
        assert isinstance(result["warnings"], list) and len(result["warnings"]) >= 1

    def test_to_float_converts_integer_string(self):
        val, err = _to_float("42")
        assert err is None
        assert math.isclose(val, 42.0)

    def test_to_float_converts_float_string(self):
        val, err = _to_float("3.14")
        assert err is None
        assert math.isclose(val, 3.14)

    def test_to_float_converts_negative_string(self):
        val, err = _to_float("-5.0")
        assert err is None
        assert math.isclose(val, -5.0)


# ---------------------------------------------------------------------------
# 12. Non-numeric strings block calculation
# ---------------------------------------------------------------------------

class TestNonNumericStringsBlock:
    @pytest.mark.parametrize("bad_val", ["abc", "not_a_number", "N/A", "two", "1e999999x"])
    def test_non_numeric_string_blocks_battery(self, bad_val):
        report = build_engineering_calculation_report(
            platform_intent="drone",
            provided_inputs={"battery_capacity_wh": bad_val, "average_power_w": 50.0},
        )
        assert _get_result(report, "battery_runtime_estimate") is None
        blocked = _get_blocked(report, "battery_runtime_estimate")
        assert blocked["reason"] == "invalid_input"

    def test_non_numeric_string_blocks_twr(self):
        report = build_engineering_calculation_report(
            platform_intent="drone",
            provided_inputs={"total_thrust_n": "heavy", "mass_kg": 2.0},
        )
        assert _get_result(report, "thrust_to_weight_ratio") is None
        blocked = _get_blocked(report, "thrust_to_weight_ratio")
        assert blocked["reason"] == "invalid_input"

    def test_to_float_rejects_non_numeric_string(self):
        val, err = _to_float("not_a_number")
        assert val is None
        assert err is not None

    def test_to_float_rejects_empty_string(self):
        val, err = _to_float("")
        assert val is None
        assert err is not None


# ---------------------------------------------------------------------------
# 13. NaN and infinity block calculation
# ---------------------------------------------------------------------------

class TestNanInfinityBlock:
    @pytest.mark.parametrize("bad_val", [
        float("nan"), float("inf"), float("-inf"),
        "nan", "NaN", "inf", "Inf", "-inf",
    ])
    def test_nan_inf_blocks_battery(self, bad_val):
        report = build_engineering_calculation_report(
            platform_intent="drone",
            provided_inputs={"battery_capacity_wh": bad_val, "average_power_w": 50.0},
        )
        assert _get_result(report, "battery_runtime_estimate") is None
        blocked = _get_blocked(report, "battery_runtime_estimate")
        assert blocked["reason"] == "invalid_input"

    @pytest.mark.parametrize("bad_val", [float("nan"), float("inf")])
    def test_nan_inf_blocks_twr(self, bad_val):
        report = build_engineering_calculation_report(
            platform_intent="drone",
            provided_inputs={"total_thrust_n": bad_val, "mass_kg": 2.0},
        )
        assert _get_result(report, "thrust_to_weight_ratio") is None

    def test_to_float_rejects_nan(self):
        val, err = _to_float(float("nan"))
        assert val is None and err is not None

    def test_to_float_rejects_inf(self):
        val, err = _to_float(float("inf"))
        assert val is None and err is not None

    def test_to_float_rejects_neg_inf(self):
        val, err = _to_float(float("-inf"))
        assert val is None and err is not None

    def test_to_float_rejects_nan_string(self):
        val, err = _to_float("nan")
        assert val is None and err is not None

    def test_to_float_rejects_inf_string(self):
        val, err = _to_float("inf")
        assert val is None and err is not None


# ---------------------------------------------------------------------------
# 14. calculation_performed is True only if at least one metric computed
# ---------------------------------------------------------------------------

class TestCalculationPerformed:
    def test_false_when_no_inputs(self):
        report = build_engineering_calculation_report(platform_intent="drone")
        assert report["calculation_performed"] is False

    def test_false_with_only_invalid_inputs(self):
        report = build_engineering_calculation_report(
            platform_intent="drone",
            provided_inputs={"battery_capacity_wh": "abc", "average_power_w": "xyz"},
        )
        assert report["calculation_performed"] is False

    def test_true_when_battery_runtime_computes(self):
        report = build_engineering_calculation_report(
            platform_intent="drone",
            provided_inputs=_BAT_INPUTS,
        )
        assert report["calculation_performed"] is True

    def test_true_when_power_budget_computes(self):
        report = build_engineering_calculation_report(
            platform_intent="drone",
            provided_inputs=_PWR_INPUTS,
        )
        assert report["calculation_performed"] is True

    def test_true_when_twr_computes(self):
        report = build_engineering_calculation_report(
            platform_intent="drone",
            provided_inputs=_TWR_INPUTS,
        )
        assert report["calculation_performed"] is True

    def test_calculation_performed_is_bool(self):
        report = build_engineering_calculation_report()
        assert isinstance(report["calculation_performed"], bool)


# ---------------------------------------------------------------------------
# 15. computed_metric_count is correct
# ---------------------------------------------------------------------------

class TestComputedMetricCount:
    def test_zero_when_no_inputs(self):
        report = build_engineering_calculation_report(platform_intent="drone")
        assert report["computed_metric_count"] == 0

    def test_one_when_battery_only(self):
        report = build_engineering_calculation_report(
            platform_intent="drone",
            provided_inputs=_BAT_INPUTS,
        )
        assert report["computed_metric_count"] == 1

    def test_two_when_battery_and_power(self):
        report = build_engineering_calculation_report(
            platform_intent="drone",
            provided_inputs={**_BAT_INPUTS, **_PWR_INPUTS},
        )
        assert report["computed_metric_count"] == 2

    def test_three_when_all_drone_inputs_provided(self):
        report = build_engineering_calculation_report(
            platform_intent="drone",
            provided_inputs=_ALL_DRONE,
        )
        assert report["computed_metric_count"] == 3

    def test_count_matches_results_list_length(self):
        report = build_engineering_calculation_report(
            platform_intent="drone",
            provided_inputs=_ALL_DRONE,
        )
        assert report["computed_metric_count"] == len(report["results"])


# ---------------------------------------------------------------------------
# 16. blocked_calculation_count is correct
# ---------------------------------------------------------------------------

class TestBlockedCalculationCount:
    def test_count_matches_blocked_results_list_length(self):
        for inputs in ({}, _BAT_INPUTS, _ALL_DRONE):
            report = build_engineering_calculation_report(
                platform_intent="drone",
                provided_inputs=inputs,
            )
            assert report["blocked_calculation_count"] == len(report["blocked_results"])

    def test_all_checks_blocked_when_no_inputs(self):
        report = build_engineering_calculation_report(platform_intent="drone")
        # 7 total drone checks, 0 computed
        assert report["blocked_calculation_count"] == 7

    def test_blocked_decreases_as_inputs_added(self):
        r0 = build_engineering_calculation_report(platform_intent="drone")
        r1 = build_engineering_calculation_report(
            platform_intent="drone", provided_inputs=_BAT_INPUTS
        )
        assert r1["blocked_calculation_count"] < r0["blocked_calculation_count"]

    def test_unsupported_always_contributes_to_blocked(self):
        report = build_engineering_calculation_report(
            platform_intent="drone",
            provided_inputs=_ALL_DRONE,
        )
        # 4 unsupported checks always blocked even with all inputs
        unsupported_count = sum(
            1 for b in report["blocked_results"]
            if b["reason"] == "unsupported_calculation"
        )
        assert unsupported_count == 4


# ---------------------------------------------------------------------------
# 17. Results include required metadata fields
# ---------------------------------------------------------------------------

class TestResultMetadata:
    @pytest.fixture
    def full_report(self):
        return build_engineering_calculation_report(
            platform_intent="drone",
            provided_inputs=_ALL_DRONE,
        )

    def test_all_result_fields_present(self, full_report):
        for result in full_report["results"]:
            for field in _RESULT_FIELDS:
                assert field in result, (
                    f"Result '{result.get('check_id')}' missing field '{field}'"
                )

    def test_formula_is_nonempty_string(self, full_report):
        for result in full_report["results"]:
            assert isinstance(result["formula"], str) and result["formula"].strip()

    def test_unit_is_nonempty_string(self, full_report):
        for result in full_report["results"]:
            assert isinstance(result["unit"], str) and result["unit"].strip()

    def test_input_values_is_dict_of_floats(self, full_report):
        for result in full_report["results"]:
            assert isinstance(result["input_values"], dict)
            for v in result["input_values"].values():
                assert isinstance(v, float)

    def test_input_sources_maps_all_inputs(self, full_report):
        for result in full_report["results"]:
            for k in result["input_values"]:
                assert k in result["input_sources"]
                assert result["input_sources"][k] == "provided_inputs"

    def test_assumptions_is_nonempty_list(self, full_report):
        for result in full_report["results"]:
            assert isinstance(result["assumptions"], list) and len(result["assumptions"]) >= 1

    def test_warnings_is_list(self, full_report):
        for result in full_report["results"]:
            assert isinstance(result["warnings"], list)

    def test_confidence_is_concept_estimate(self, full_report):
        for result in full_report["results"]:
            assert result["confidence"] == "concept_estimate"

    def test_safety_note_is_nonempty_string(self, full_report):
        for result in full_report["results"]:
            assert isinstance(result["safety_note"], str) and result["safety_note"].strip()

    def test_blocked_results_have_required_fields(self, full_report):
        for blocked in full_report["blocked_results"]:
            for field in _BLOCKED_FIELDS:
                assert field in blocked, (
                    f"Blocked result '{blocked.get('check_id')}' missing field '{field}'"
                )


# ---------------------------------------------------------------------------
# 18. No unsafe positive claims in output
# ---------------------------------------------------------------------------

class TestNoUnsafeClaims:
    @pytest.mark.parametrize("phrase", _UNSAFE_PHRASES)
    def test_phrase_absent_from_descriptive_fields(self, phrase):
        for intent, inputs in [
            ("drone", _ALL_DRONE),
            ("rover", {**_BAT_INPUTS, **_PWR_INPUTS, **_TORQ_INPUTS}),
            (None, {}),
        ]:
            report = build_engineering_calculation_report(
                platform_intent=intent, provided_inputs=inputs
            )
            text = _descriptive_text(report)
            assert phrase not in text, (
                f"Unsafe phrase '{phrase}' found for platform_intent='{intent}'"
            )

    def test_rationale_free_of_unsafe_phrases(self):
        report = build_engineering_calculation_report(
            platform_intent="drone", provided_inputs=_ALL_DRONE
        )
        rationale = report["rationale"].lower()
        for phrase in _UNSAFE_PHRASES:
            assert phrase not in rationale

    def test_safety_header_free_of_unsafe_phrases(self):
        report = build_engineering_calculation_report(platform_intent="drone")
        header = report["safety_notes"][0].lower()
        for phrase in _UNSAFE_PHRASES:
            assert phrase not in header

    def test_twr_safety_note_does_not_claim_airworthiness(self):
        report = build_engineering_calculation_report(
            platform_intent="drone", provided_inputs=_TWR_INPUTS
        )
        result = _get_result(report, "thrust_to_weight_ratio")
        note = result["safety_note"].lower()
        for phrase in _UNSAFE_PHRASES:
            assert phrase not in note


# ---------------------------------------------------------------------------
# 19. Provided inputs are not mutated
# ---------------------------------------------------------------------------

class TestProvidedInputsNotMutated:
    def test_dict_keys_unchanged_after_call(self):
        inputs = {"battery_capacity_wh": 100.0, "average_power_w": 50.0}
        original_keys = set(inputs.keys())
        build_engineering_calculation_report(
            platform_intent="drone", provided_inputs=inputs
        )
        assert set(inputs.keys()) == original_keys

    def test_dict_values_unchanged_after_call(self):
        inputs = {"battery_capacity_wh": 100.0, "average_power_w": 50.0}
        build_engineering_calculation_report(
            platform_intent="drone", provided_inputs=inputs
        )
        assert inputs["battery_capacity_wh"] == 100.0
        assert inputs["average_power_w"] == 50.0

    def test_none_provided_inputs_does_not_raise(self):
        report = build_engineering_calculation_report(
            platform_intent="drone", provided_inputs=None
        )
        assert isinstance(report, dict)

    def test_empty_dict_provided_inputs_does_not_raise(self):
        report = build_engineering_calculation_report(
            platform_intent="drone", provided_inputs={}
        )
        assert isinstance(report, dict)

    def test_results_list_mutation_does_not_affect_second_call(self):
        report1 = build_engineering_calculation_report(
            platform_intent="drone", provided_inputs=_BAT_INPUTS
        )
        original_value = report1["results"][0]["value"]
        report1["results"][0]["value"] = 9999.9
        report2 = build_engineering_calculation_report(
            platform_intent="drone", provided_inputs=_BAT_INPUTS
        )
        assert report2["results"][0]["value"] == original_value


# ---------------------------------------------------------------------------
# Helper: _to_float edge cases
# ---------------------------------------------------------------------------

class TestToFloatHelper:
    def test_accepts_int(self):
        val, err = _to_float(42)
        assert err is None and math.isclose(val, 42.0)

    def test_accepts_float(self):
        val, err = _to_float(3.14)
        assert err is None and math.isclose(val, 3.14)

    def test_accepts_zero(self):
        val, err = _to_float(0)
        assert err is None and val == 0.0

    def test_accepts_negative(self):
        val, err = _to_float(-7.5)
        assert err is None and math.isclose(val, -7.5)

    def test_rejects_bool_true(self):
        val, err = _to_float(True)
        assert val is None and err is not None

    def test_rejects_bool_false(self):
        val, err = _to_float(False)
        assert val is None and err is not None

    def test_rejects_none(self):
        val, err = _to_float(None)
        assert val is None and err is not None

    def test_rejects_list(self):
        val, err = _to_float([1, 2])
        assert val is None and err is not None

    def test_rejects_dict(self):
        val, err = _to_float({"a": 1})
        assert val is None and err is not None


# Rover-specific alias used by test 16
_TORQ_INPUTS = {"load_kg": 5.0, "moment_arm_m": 0.3}
