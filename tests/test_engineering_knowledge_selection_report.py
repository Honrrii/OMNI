"""
Tests for OMNI Phase 17B — Engineering Knowledge Selection Report.

All tests are local, deterministic, and run without LLM calls,
internet access, simulation, or numeric computation.
"""
from __future__ import annotations

import pytest

from backend.app.engineering.knowledge_selection_report import (
    build_engineering_knowledge_selection_report,
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

_CHECK_SCHEMA_FIELDS = [
    "check_id", "domain", "title",
    "required_inputs", "optional_inputs", "computed_outputs",
    "missing_inputs", "assumptions", "missing_input_behavior",
    "confidence_rule", "safety_notes", "blocked_claims",
]

_REPORT_TOP_LEVEL_FIELDS = [
    "schema", "status", "phase", "platform_intent",
    "platform_resolution_source", "selected_check_count",
    "selected_checks", "required_input_summary", "missing_input_summary",
    "blocked_claims", "safety_notes", "calculation_status", "rationale",
]


def _check_ids(report: dict) -> set:
    return {c["check_id"] for c in report["selected_checks"]}


def _descriptive_text(report: dict) -> str:
    """
    Concatenate all descriptive fields that should be free of unsafe claims.
    Excludes 'blocked_claims' fields (which list phrases intentionally).
    """
    parts = [
        report.get("rationale", ""),
        " ".join(report.get("safety_notes", [])),
        " ".join(report.get("required_input_summary", [])),
        " ".join(report.get("missing_input_summary", [])),
    ]
    for chk in report.get("selected_checks", []):
        parts.append(chk.get("title", ""))
        parts.extend(chk.get("assumptions", []))
        parts.append(chk.get("confidence_rule", ""))
        parts.extend(chk.get("safety_notes", []))
    return " ".join(parts).lower()


# ---------------------------------------------------------------------------
# 1. Report generates with schema / status / phase
# ---------------------------------------------------------------------------

class TestReportTopLevel:
    def test_returns_dict(self):
        report = build_engineering_knowledge_selection_report()
        assert isinstance(report, dict)

    def test_schema_field(self):
        report = build_engineering_knowledge_selection_report()
        assert report["schema"] == "engineering_knowledge_selection_report.v1"

    def test_status_field(self):
        report = build_engineering_knowledge_selection_report()
        assert report["status"] == "generated"

    def test_phase_field(self):
        report = build_engineering_knowledge_selection_report()
        assert report["phase"] == "17B"

    def test_all_top_level_fields_present(self):
        report = build_engineering_knowledge_selection_report()
        for field in _REPORT_TOP_LEVEL_FIELDS:
            assert field in report, f"Report missing top-level field '{field}'"

    def test_selected_checks_is_list(self):
        report = build_engineering_knowledge_selection_report()
        assert isinstance(report["selected_checks"], list)

    def test_selected_check_count_matches_list_length(self):
        report = build_engineering_knowledge_selection_report()
        assert report["selected_check_count"] == len(report["selected_checks"])


# ---------------------------------------------------------------------------
# 2. UAV platform check selection
# ---------------------------------------------------------------------------

class TestUavPlatformSelection:
    @pytest.fixture
    def uav_report(self):
        return build_engineering_knowledge_selection_report(platform_intent="drone")

    def test_selects_thrust_to_weight(self, uav_report):
        assert "thrust_to_weight_ratio" in _check_ids(uav_report)

    def test_selects_battery_runtime(self, uav_report):
        assert "battery_runtime_estimate" in _check_ids(uav_report)

    def test_selects_simulation_readiness(self, uav_report):
        assert "simulation_readiness" in _check_ids(uav_report)

    def test_selects_safety_margin_review(self, uav_report):
        assert "safety_margin_review" in _check_ids(uav_report)

    @pytest.mark.parametrize("intent", ["drone", "UAV", "quadcopter", "vtol platform", "aerial"])
    def test_uav_keywords_trigger_uav_selection(self, intent):
        report = build_engineering_knowledge_selection_report(platform_intent=intent)
        assert "thrust_to_weight_ratio" in _check_ids(report)


# ---------------------------------------------------------------------------
# 3. Rover platform check selection
# ---------------------------------------------------------------------------

class TestRoverPlatformSelection:
    @pytest.fixture
    def rover_report(self):
        return build_engineering_knowledge_selection_report(platform_intent="rover")

    def test_selects_torque_required(self, rover_report):
        assert "torque_required_basic" in _check_ids(rover_report)

    def test_selects_power_budget(self, rover_report):
        assert "power_budget" in _check_ids(rover_report)

    def test_selects_simulation_readiness(self, rover_report):
        assert "simulation_readiness" in _check_ids(rover_report)

    def test_selects_safety_margin_review(self, rover_report):
        assert "safety_margin_review" in _check_ids(rover_report)

    @pytest.mark.parametrize("intent", ["rover", "ground robot", "wheeled vehicle", "crawler"])
    def test_rover_keywords_trigger_rover_selection(self, intent):
        report = build_engineering_knowledge_selection_report(platform_intent=intent)
        assert "torque_required_basic" in _check_ids(report)


# ---------------------------------------------------------------------------
# 4. Manipulator platform check selection
# ---------------------------------------------------------------------------

class TestManipulatorPlatformSelection:
    @pytest.fixture
    def manip_report(self):
        return build_engineering_knowledge_selection_report(platform_intent="manipulator")

    def test_selects_torque_required(self, manip_report):
        assert "torque_required_basic" in _check_ids(manip_report)

    def test_selects_safety_margin_review(self, manip_report):
        assert "safety_margin_review" in _check_ids(manip_report)

    def test_selects_simulation_readiness(self, manip_report):
        assert "simulation_readiness" in _check_ids(manip_report)

    @pytest.mark.parametrize("intent", ["manipulator", "robot arm", "gripper", "robotic arm"])
    def test_manipulator_keywords_trigger_selection(self, intent):
        report = build_engineering_knowledge_selection_report(platform_intent=intent)
        assert "torque_required_basic" in _check_ids(report)


# ---------------------------------------------------------------------------
# 5. Unknown platform returns conservative base checks
# ---------------------------------------------------------------------------

class TestUnknownPlatformSelection:
    @pytest.fixture
    def unknown_report(self):
        return build_engineering_knowledge_selection_report()

    def test_includes_mass_budget(self, unknown_report):
        assert "mass_budget" in _check_ids(unknown_report)

    def test_includes_power_budget(self, unknown_report):
        assert "power_budget" in _check_ids(unknown_report)

    def test_includes_sensor_coverage_check(self, unknown_report):
        assert "sensor_coverage_check" in _check_ids(unknown_report)

    def test_includes_safety_margin_review(self, unknown_report):
        assert "safety_margin_review" in _check_ids(unknown_report)

    def test_includes_simulation_readiness(self, unknown_report):
        assert "simulation_readiness" in _check_ids(unknown_report)

    def test_does_not_include_thrust_to_weight(self, unknown_report):
        assert "thrust_to_weight_ratio" not in _check_ids(unknown_report)

    @pytest.mark.parametrize("intent", [None, "", "unrecognised platform", "spaceship"])
    def test_unknown_intents_give_conservative_base(self, intent):
        report = build_engineering_knowledge_selection_report(platform_intent=intent)
        ids = _check_ids(report)
        assert "mass_budget" in ids
        assert "safety_margin_review" in ids
        assert "simulation_readiness" in ids


# ---------------------------------------------------------------------------
# 6. Explicit platform_intent overrides mission text
# ---------------------------------------------------------------------------

class TestExplicitPlatformIntentOverride:
    def test_explicit_overrides_conflicting_mission_text(self):
        report = build_engineering_knowledge_selection_report(
            platform_intent="rover",
            mission_text="build a drone for aerial inspection",
        )
        ids = _check_ids(report)
        assert "torque_required_basic" in ids
        assert "thrust_to_weight_ratio" not in ids

    def test_explicit_overrides_mission_result_text(self):
        mission_result = {"mission": "build a drone for aerial inspection"}
        report = build_engineering_knowledge_selection_report(
            mission_result=mission_result,
            platform_intent="rover",
        )
        ids = _check_ids(report)
        assert "torque_required_basic" in ids
        assert "thrust_to_weight_ratio" not in ids

    def test_resolution_source_is_explicit_when_given(self):
        report = build_engineering_knowledge_selection_report(
            platform_intent="drone",
            mission_text="build a rover",
        )
        assert report["platform_resolution_source"] == "explicit_platform_intent"


# ---------------------------------------------------------------------------
# 7. mission_result.artifacts.mission_intent.platform_intent resolution
# ---------------------------------------------------------------------------

class TestMissionResultArtifactsResolution:
    def _make_mission_result(self, platform: str) -> dict:
        return {
            "artifacts": {
                "mission_intent": {
                    "platform_intent": platform,
                }
            }
        }

    def test_drone_from_artifacts(self):
        report = build_engineering_knowledge_selection_report(
            mission_result=self._make_mission_result("drone inspection"),
        )
        assert "thrust_to_weight_ratio" in _check_ids(report)

    def test_rover_from_artifacts(self):
        report = build_engineering_knowledge_selection_report(
            mission_result=self._make_mission_result("wheeled ground rover"),
        )
        assert "torque_required_basic" in _check_ids(report)

    def test_manipulator_from_artifacts(self):
        report = build_engineering_knowledge_selection_report(
            mission_result=self._make_mission_result("robot arm for welding"),
        )
        assert "torque_required_basic" in _check_ids(report)

    def test_resolution_source_is_artifacts_field(self):
        report = build_engineering_knowledge_selection_report(
            mission_result=self._make_mission_result("uav platform"),
        )
        assert report["platform_resolution_source"] == (
            "mission_result.artifacts.mission_intent.platform_intent"
        )

    def test_artifacts_used_only_when_no_explicit_intent(self):
        report = build_engineering_knowledge_selection_report(
            mission_result=self._make_mission_result("rover platform"),
            platform_intent="manipulator",
        )
        # explicit wins
        assert "torque_required_basic" in _check_ids(report)
        assert report["platform_resolution_source"] == "explicit_platform_intent"


# ---------------------------------------------------------------------------
# 8. Mission text fallback keyword classification
# ---------------------------------------------------------------------------

class TestMissionTextFallback:
    def test_uav_from_mission_text(self):
        report = build_engineering_knowledge_selection_report(
            mission_text="design a quadcopter for bridge inspection",
        )
        assert "thrust_to_weight_ratio" in _check_ids(report)

    def test_rover_from_mission_text(self):
        report = build_engineering_knowledge_selection_report(
            mission_text="build a wheeled robot for floor inspection",
        )
        assert "torque_required_basic" in _check_ids(report)

    def test_manipulator_from_mission_text(self):
        report = build_engineering_knowledge_selection_report(
            mission_text="create a gripper for pick and place tasks",
        )
        assert "torque_required_basic" in _check_ids(report)

    def test_resolution_source_is_mission_text_keywords(self):
        report = build_engineering_knowledge_selection_report(
            mission_text="aerial drone platform",
        )
        assert report["platform_resolution_source"] == "mission_text_keywords"

    def test_mission_result_text_fallback_when_no_explicit_or_artifacts(self):
        mission_result = {"mission": "build a rover for inspection"}
        report = build_engineering_knowledge_selection_report(
            mission_result=mission_result,
        )
        assert "torque_required_basic" in _check_ids(report)
        assert report["platform_resolution_source"] == "mission_result_text_keywords"


# ---------------------------------------------------------------------------
# 9. selected_checks contain required schema fields
# ---------------------------------------------------------------------------

class TestSelectedCheckSchema:
    @pytest.fixture
    def report(self):
        return build_engineering_knowledge_selection_report(platform_intent="drone")

    def test_each_check_has_required_fields(self, report):
        for chk in report["selected_checks"]:
            for field in _CHECK_SCHEMA_FIELDS:
                assert field in chk, f"Check '{chk.get('check_id')}' missing field '{field}'"

    def test_check_id_is_nonempty_string(self, report):
        for chk in report["selected_checks"]:
            assert isinstance(chk["check_id"], str) and chk["check_id"].strip()

    def test_domain_is_nonempty_string(self, report):
        for chk in report["selected_checks"]:
            assert isinstance(chk["domain"], str) and chk["domain"].strip()

    def test_title_is_nonempty_string(self, report):
        for chk in report["selected_checks"]:
            assert isinstance(chk["title"], str) and chk["title"].strip()

    def test_required_inputs_is_list(self, report):
        for chk in report["selected_checks"]:
            assert isinstance(chk["required_inputs"], list)

    def test_missing_inputs_is_list(self, report):
        for chk in report["selected_checks"]:
            assert isinstance(chk["missing_inputs"], list)

    def test_missing_input_behavior_is_do_not_compute(self, report):
        for chk in report["selected_checks"]:
            assert chk["missing_input_behavior"] == "do_not_compute"

    def test_safety_notes_is_nonempty_list(self, report):
        for chk in report["selected_checks"]:
            assert isinstance(chk["safety_notes"], list) and len(chk["safety_notes"]) >= 1

    def test_blocked_claims_is_nonempty_list(self, report):
        for chk in report["selected_checks"]:
            assert isinstance(chk["blocked_claims"], list) and len(chk["blocked_claims"]) >= 1


# ---------------------------------------------------------------------------
# 10. missing_inputs initially equals required_inputs
# ---------------------------------------------------------------------------

class TestMissingInputsEqualsRequired:
    @pytest.mark.parametrize("intent", ["drone", "rover", "manipulator", None])
    def test_missing_inputs_equals_required_inputs(self, intent):
        report = build_engineering_knowledge_selection_report(platform_intent=intent)
        for chk in report["selected_checks"]:
            assert chk["missing_inputs"] == chk["required_inputs"], (
                f"Check '{chk['check_id']}': missing_inputs != required_inputs"
            )

    def test_missing_input_summary_equals_required_input_summary(self):
        report = build_engineering_knowledge_selection_report(platform_intent="drone")
        assert report["missing_input_summary"] == report["required_input_summary"]

    def test_missing_input_summary_is_list(self):
        report = build_engineering_knowledge_selection_report()
        assert isinstance(report["missing_input_summary"], list)

    def test_required_input_summary_is_list(self):
        report = build_engineering_knowledge_selection_report()
        assert isinstance(report["required_input_summary"], list)


# ---------------------------------------------------------------------------
# 11. blocked_claims are aggregated and deduped
# ---------------------------------------------------------------------------

class TestBlockedClaimsAggregation:
    def test_blocked_claims_is_list(self):
        report = build_engineering_knowledge_selection_report(platform_intent="drone")
        assert isinstance(report["blocked_claims"], list)

    def test_blocked_claims_are_deduped(self):
        report = build_engineering_knowledge_selection_report(platform_intent="drone")
        bc = report["blocked_claims"]
        assert len(bc) == len(set(bc)), "blocked_claims contain duplicates"

    def test_blocked_claims_nonempty_when_checks_selected(self):
        report = build_engineering_knowledge_selection_report(platform_intent="rover")
        assert len(report["blocked_claims"]) >= 1

    def test_common_blocked_claim_validated_present(self):
        report = build_engineering_knowledge_selection_report(platform_intent="drone")
        assert "validated" in report["blocked_claims"]

    def test_common_blocked_claim_certified_present(self):
        report = build_engineering_knowledge_selection_report(platform_intent="drone")
        assert "certified" in report["blocked_claims"]


# ---------------------------------------------------------------------------
# 12. safety_notes are aggregated and deduped
# ---------------------------------------------------------------------------

class TestSafetyNotesAggregation:
    def test_safety_notes_is_list(self):
        report = build_engineering_knowledge_selection_report(platform_intent="drone")
        assert isinstance(report["safety_notes"], list)

    def test_safety_notes_are_deduped(self):
        report = build_engineering_knowledge_selection_report(platform_intent="drone")
        sn = report["safety_notes"]
        assert len(sn) == len(set(sn)), "safety_notes contain duplicates"

    def test_safety_header_is_first_note(self):
        report = build_engineering_knowledge_selection_report(platform_intent="drone")
        assert report["safety_notes"][0].startswith("Engineering checks selected.")

    def test_safety_notes_nonempty_for_all_platforms(self):
        for intent in ("drone", "rover", "manipulator", None):
            report = build_engineering_knowledge_selection_report(platform_intent=intent)
            assert len(report["safety_notes"]) >= 1

    def test_safety_notes_contain_no_calculation_phrase(self):
        report = build_engineering_knowledge_selection_report(platform_intent="drone")
        combined = " ".join(report["safety_notes"]).lower()
        assert "no engineering calculation performed" in combined


# ---------------------------------------------------------------------------
# 13. No numeric calculations performed
# ---------------------------------------------------------------------------

class TestNoNumericCalculations:
    def test_selected_checks_have_no_numeric_values_in_outputs(self):
        for intent in ("drone", "rover", "manipulator", None):
            report = build_engineering_knowledge_selection_report(platform_intent=intent)
            for chk in report["selected_checks"]:
                for val in chk.get("computed_outputs", []):
                    # computed_outputs are field-name strings, not numeric results
                    assert isinstance(val, str), (
                        f"Check '{chk['check_id']}' computed_outputs contains "
                        f"a non-string value: {val!r}"
                    )

    def test_report_contains_no_numeric_result_field(self):
        report = build_engineering_knowledge_selection_report(platform_intent="drone")
        assert "result" not in report
        assert "value" not in report
        assert "computed_value" not in report

    def test_required_input_summary_contains_only_strings(self):
        report = build_engineering_knowledge_selection_report(platform_intent="drone")
        for item in report["required_input_summary"]:
            assert isinstance(item, str)


# ---------------------------------------------------------------------------
# 14. calculation_status is not_computed_phase_17b
# ---------------------------------------------------------------------------

class TestCalculationStatus:
    @pytest.mark.parametrize("intent", ["drone", "rover", "manipulator", None, ""])
    def test_calculation_status_is_not_computed(self, intent):
        report = build_engineering_knowledge_selection_report(platform_intent=intent)
        assert report["calculation_status"] == "not_computed_phase_17b"

    def test_calculation_status_present_for_mission_result_input(self):
        report = build_engineering_knowledge_selection_report(
            mission_result={"mission": "build a drone"},
        )
        assert report["calculation_status"] == "not_computed_phase_17b"


# ---------------------------------------------------------------------------
# 15. No unsafe positive claims in output
# ---------------------------------------------------------------------------

class TestNoUnsafePositiveClaims:
    @pytest.mark.parametrize("phrase", _UNSAFE_PHRASES)
    def test_unsafe_phrase_absent_from_descriptive_fields(self, phrase):
        for intent in ("drone", "rover", "manipulator", None):
            report = build_engineering_knowledge_selection_report(platform_intent=intent)
            text = _descriptive_text(report)
            assert phrase not in text, (
                f"Unsafe phrase '{phrase}' found in descriptive fields "
                f"for platform_intent='{intent}'"
            )

    def test_rationale_free_of_unsafe_phrases(self):
        for intent in ("drone", "rover", "manipulator", None):
            report = build_engineering_knowledge_selection_report(platform_intent=intent)
            rationale = report["rationale"].lower()
            for phrase in _UNSAFE_PHRASES:
                assert phrase not in rationale, (
                    f"Unsafe phrase '{phrase}' found in rationale for '{intent}'"
                )

    def test_safety_header_free_of_unsafe_phrases(self):
        report = build_engineering_knowledge_selection_report(platform_intent="drone")
        header = report["safety_notes"][0].lower()
        for phrase in _UNSAFE_PHRASES:
            assert phrase not in header, (
                f"Unsafe phrase '{phrase}' found in safety header"
            )


# ---------------------------------------------------------------------------
# 16. Mutation safety
# ---------------------------------------------------------------------------

class TestMutationSafety:
    def test_mutating_selected_checks_does_not_affect_second_call(self):
        report1 = build_engineering_knowledge_selection_report(platform_intent="drone")
        if report1["selected_checks"]:
            report1["selected_checks"][0]["title"] = "MUTATED"
        report2 = build_engineering_knowledge_selection_report(platform_intent="drone")
        if report2["selected_checks"]:
            assert report2["selected_checks"][0]["title"] != "MUTATED"

    def test_mutating_safety_notes_does_not_affect_second_call(self):
        report1 = build_engineering_knowledge_selection_report(platform_intent="rover")
        original_len = len(report1["safety_notes"])
        report1["safety_notes"].append("INJECTED")
        report2 = build_engineering_knowledge_selection_report(platform_intent="rover")
        assert len(report2["safety_notes"]) == original_len

    def test_mutating_blocked_claims_does_not_affect_second_call(self):
        report1 = build_engineering_knowledge_selection_report(platform_intent="rover")
        original_len = len(report1["blocked_claims"])
        report1["blocked_claims"].append("INJECTED_CLAIM")
        report2 = build_engineering_knowledge_selection_report(platform_intent="rover")
        assert len(report2["blocked_claims"]) == original_len

    def test_mutating_required_input_summary_does_not_affect_second_call(self):
        report1 = build_engineering_knowledge_selection_report(platform_intent="drone")
        original = list(report1["required_input_summary"])
        report1["required_input_summary"].append("injected_input")
        report2 = build_engineering_knowledge_selection_report(platform_intent="drone")
        assert report2["required_input_summary"] == original
