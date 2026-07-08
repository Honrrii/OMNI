"""
Tests for OMNI Phase 17A — Engineering Knowledge Registry.

All tests are local, deterministic, and run without LLM calls,
internet access, simulation, or computation.
"""
from __future__ import annotations

import pytest

from backend.app.engineering.knowledge_registry import (
    get_engineering_knowledge_entry,
    get_engineering_knowledge_registry,
    list_engineering_domains,
    list_engineering_knowledge_entries,
    select_engineering_knowledge_for_platform,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REQUIRED_ENTRY_IDS = {
    "mass_budget",
    "power_budget",
    "battery_runtime_estimate",
    "torque_required_basic",
    "thrust_to_weight_ratio",
    "center_of_mass_check",
    "sensor_coverage_check",
    "thermal_risk_basic",
    "urdf_visual_readiness",
    "gazebo_physics_readiness",
    "simulation_readiness",
    "safety_margin_review",
}

_REQUIRED_DOMAINS = {
    "mechanical",
    "electrical",
    "robotics",
    "aerospace_concept",
    "simulation",
    "safety",
}

_BLOCKED_CLAIM_PHRASES = {
    "validated",
    "certified",
    "airworthy",
    "flight-ready",
    "fabrication-ready",
    "deployment-ready",
    "production-ready",
}

_FIELDS_TO_SCAN = ["title", "description", "assumptions", "safety_notes", "confidence_rules"]


def _safe_text_from_entry(entry: dict) -> str:
    """Concatenate all descriptive fields (not blocked_claims) for phrase scanning."""
    parts = []
    for field in _FIELDS_TO_SCAN:
        val = entry.get(field, "")
        if isinstance(val, str):
            parts.append(val)
        elif isinstance(val, list):
            parts.extend(str(v) for v in val)
    return " ".join(parts).lower()


# ---------------------------------------------------------------------------
# 1. Registry existence and minimum entry count
# ---------------------------------------------------------------------------

class TestRegistryExistence:
    def test_registry_returns_list(self):
        reg = get_engineering_knowledge_registry()
        assert isinstance(reg, list)

    def test_minimum_twelve_entries(self):
        reg = get_engineering_knowledge_registry()
        assert len(reg) >= 12

    def test_all_required_ids_present(self):
        ids = {e["id"] for e in get_engineering_knowledge_registry()}
        missing = _REQUIRED_ENTRY_IDS - ids
        assert not missing, f"Missing required entry IDs: {missing}"


# ---------------------------------------------------------------------------
# 2. Entry schema completeness
# ---------------------------------------------------------------------------

class TestEntrySchema:
    _REQUIRED_FIELDS = [
        "id", "domain", "title", "description",
        "required_inputs", "optional_inputs",
        "computed_outputs", "unit_expectations",
        "assumptions", "missing_input_behavior",
        "confidence_rules", "safety_notes", "blocked_claims",
    ]

    @pytest.fixture
    def all_entries(self):
        return get_engineering_knowledge_registry()

    def test_all_entries_have_required_fields(self, all_entries):
        for entry in all_entries:
            for field in self._REQUIRED_FIELDS:
                assert field in entry, (
                    f"Entry '{entry.get('id')}' missing required field '{field}'"
                )

    def test_id_is_nonempty_string(self, all_entries):
        for entry in all_entries:
            assert isinstance(entry["id"], str) and entry["id"].strip()

    def test_domain_is_nonempty_string(self, all_entries):
        for entry in all_entries:
            assert isinstance(entry["domain"], str) and entry["domain"].strip()

    def test_title_is_nonempty_string(self, all_entries):
        for entry in all_entries:
            assert isinstance(entry["title"], str) and entry["title"].strip()

    def test_description_is_nonempty_string(self, all_entries):
        for entry in all_entries:
            assert isinstance(entry["description"], str) and entry["description"].strip()

    def test_required_inputs_is_list(self, all_entries):
        for entry in all_entries:
            assert isinstance(entry["required_inputs"], list)

    def test_optional_inputs_is_list(self, all_entries):
        for entry in all_entries:
            assert isinstance(entry["optional_inputs"], list)

    def test_computed_outputs_is_list(self, all_entries):
        for entry in all_entries:
            assert isinstance(entry["computed_outputs"], list)

    def test_unit_expectations_is_dict(self, all_entries):
        for entry in all_entries:
            assert isinstance(entry["unit_expectations"], dict)

    def test_assumptions_is_nonempty_list(self, all_entries):
        for entry in all_entries:
            assert isinstance(entry["assumptions"], list) and len(entry["assumptions"]) >= 1

    def test_missing_input_behavior_is_do_not_compute(self, all_entries):
        for entry in all_entries:
            assert entry["missing_input_behavior"] == "do_not_compute"

    def test_confidence_rules_is_nonempty_list(self, all_entries):
        for entry in all_entries:
            assert isinstance(entry["confidence_rules"], list) and len(entry["confidence_rules"]) >= 1

    def test_safety_notes_is_nonempty_list(self, all_entries):
        for entry in all_entries:
            assert isinstance(entry["safety_notes"], list) and len(entry["safety_notes"]) >= 1

    def test_blocked_claims_is_nonempty_list(self, all_entries):
        for entry in all_entries:
            assert isinstance(entry["blocked_claims"], list) and len(entry["blocked_claims"]) >= 1

    def test_ids_are_unique(self, all_entries):
        ids = [e["id"] for e in all_entries]
        assert len(ids) == len(set(ids)), "Duplicate entry IDs found"


# ---------------------------------------------------------------------------
# 3. Domain coverage (minimum 6 domains)
# ---------------------------------------------------------------------------

class TestDomainCoverage:
    def test_minimum_six_domains(self):
        domains = list_engineering_domains()
        assert len(domains) >= 6

    def test_all_required_domains_present(self):
        domains = set(list_engineering_domains())
        missing = _REQUIRED_DOMAINS - domains
        assert not missing, f"Missing required domains: {missing}"

    def test_list_engineering_domains_returns_sorted_list(self):
        domains = list_engineering_domains()
        assert domains == sorted(domains)

    def test_each_required_domain_has_at_least_one_entry(self):
        for domain in _REQUIRED_DOMAINS:
            entries = list_engineering_knowledge_entries(domain=domain)
            assert len(entries) >= 1, f"Domain '{domain}' has no entries"


# ---------------------------------------------------------------------------
# 4. get_engineering_knowledge_entry
# ---------------------------------------------------------------------------

class TestGetEntry:
    def test_returns_entry_for_known_id(self):
        entry = get_engineering_knowledge_entry("mass_budget")
        assert entry is not None
        assert entry["id"] == "mass_budget"

    def test_returns_none_for_unknown_id(self):
        assert get_engineering_knowledge_entry("nonexistent_xyz") is None

    def test_returns_none_for_empty_string(self):
        assert get_engineering_knowledge_entry("") is None

    def test_all_required_ids_are_retrievable(self):
        for entry_id in _REQUIRED_ENTRY_IDS:
            entry = get_engineering_knowledge_entry(entry_id)
            assert entry is not None, f"Could not retrieve entry '{entry_id}'"

    def test_returned_entry_is_a_copy(self):
        entry1 = get_engineering_knowledge_entry("mass_budget")
        entry2 = get_engineering_knowledge_entry("mass_budget")
        entry1["title"] = "MUTATED"
        assert entry2["title"] != "MUTATED"


# ---------------------------------------------------------------------------
# 5. list_engineering_knowledge_entries filtering
# ---------------------------------------------------------------------------

class TestListEntries:
    def test_no_filter_returns_all(self):
        all_entries = list_engineering_knowledge_entries()
        assert len(all_entries) == len(get_engineering_knowledge_registry())

    def test_filter_by_mechanical(self):
        entries = list_engineering_knowledge_entries(domain="mechanical")
        assert all(e["domain"] == "mechanical" for e in entries)
        assert len(entries) >= 1

    def test_filter_by_electrical(self):
        entries = list_engineering_knowledge_entries(domain="electrical")
        assert all(e["domain"] == "electrical" for e in entries)
        assert len(entries) >= 1

    def test_filter_by_robotics(self):
        entries = list_engineering_knowledge_entries(domain="robotics")
        assert all(e["domain"] == "robotics" for e in entries)
        assert len(entries) >= 1

    def test_filter_by_aerospace_concept(self):
        entries = list_engineering_knowledge_entries(domain="aerospace_concept")
        assert all(e["domain"] == "aerospace_concept" for e in entries)
        assert len(entries) >= 1

    def test_filter_by_simulation(self):
        entries = list_engineering_knowledge_entries(domain="simulation")
        assert all(e["domain"] == "simulation" for e in entries)
        assert len(entries) >= 1

    def test_filter_by_safety(self):
        entries = list_engineering_knowledge_entries(domain="safety")
        assert all(e["domain"] == "safety" for e in entries)
        assert len(entries) >= 1

    def test_unknown_domain_returns_empty(self):
        entries = list_engineering_knowledge_entries(domain="nonexistent_domain")
        assert entries == []


# ---------------------------------------------------------------------------
# 6. Concept-stage safety wording in every entry
# ---------------------------------------------------------------------------

class TestConceptStageSafetyWording:
    _REQUIRED_PHRASES = [
        "concept",
        "no engineering validation",
        "no simulation",
        "no fabrication",
    ]

    def test_every_entry_has_concept_stage_wording(self):
        for entry in get_engineering_knowledge_registry():
            text = _safe_text_from_entry(entry).lower()
            for phrase in self._REQUIRED_PHRASES:
                assert phrase in text, (
                    f"Entry '{entry['id']}' missing safety phrase '{phrase}'"
                )

    def test_safety_notes_not_empty_for_all_entries(self):
        for entry in get_engineering_knowledge_registry():
            notes = entry.get("safety_notes", [])
            assert notes, f"Entry '{entry['id']}' has empty safety_notes"

    def test_no_entry_claims_validation_in_descriptive_fields(self):
        for entry in get_engineering_knowledge_registry():
            text = _safe_text_from_entry(entry).lower()
            assert "no engineering validation implied" in text, (
                f"Entry '{entry['id']}' missing 'no engineering validation implied'"
            )


# ---------------------------------------------------------------------------
# 7. Blocked unsafe claim phrases (not in descriptive fields)
# ---------------------------------------------------------------------------

class TestBlockedUnsafeClaims:
    def test_no_unsafe_claims_in_title(self):
        for entry in get_engineering_knowledge_registry():
            title = entry.get("title", "").lower()
            for phrase in _BLOCKED_CLAIM_PHRASES:
                assert phrase not in title, (
                    f"Entry '{entry['id']}' title contains blocked phrase '{phrase}'"
                )

    def test_no_unsafe_claims_in_description(self):
        for entry in get_engineering_knowledge_registry():
            desc = entry.get("description", "").lower()
            for phrase in _BLOCKED_CLAIM_PHRASES:
                assert phrase not in desc, (
                    f"Entry '{entry['id']}' description contains blocked phrase '{phrase}'"
                )

    def test_no_unsafe_claims_in_assumptions(self):
        for entry in get_engineering_knowledge_registry():
            text = " ".join(entry.get("assumptions", [])).lower()
            for phrase in _BLOCKED_CLAIM_PHRASES:
                assert phrase not in text, (
                    f"Entry '{entry['id']}' assumptions contain blocked phrase '{phrase}'"
                )

    def test_no_unsafe_claims_in_safety_notes(self):
        for entry in get_engineering_knowledge_registry():
            text = " ".join(entry.get("safety_notes", [])).lower()
            for phrase in _BLOCKED_CLAIM_PHRASES:
                assert phrase not in text, (
                    f"Entry '{entry['id']}' safety_notes contain blocked phrase '{phrase}'"
                )

    def test_no_unsafe_claims_in_confidence_rules(self):
        for entry in get_engineering_knowledge_registry():
            text = " ".join(entry.get("confidence_rules", [])).lower()
            for phrase in _BLOCKED_CLAIM_PHRASES:
                assert phrase not in text, (
                    f"Entry '{entry['id']}' confidence_rules contain blocked phrase '{phrase}'"
                )

    def test_blocked_claims_field_lists_expected_phrases(self):
        for entry in get_engineering_knowledge_registry():
            bc = [p.lower() for p in entry.get("blocked_claims", [])]
            assert "validated" in bc, f"Entry '{entry['id']}' blocked_claims missing 'validated'"
            assert "certified" in bc, f"Entry '{entry['id']}' blocked_claims missing 'certified'"


# ---------------------------------------------------------------------------
# 8. Platform selection — UAV
# ---------------------------------------------------------------------------

class TestPlatformSelectionUav:
    @pytest.mark.parametrize("intent", [
        "drone", "UAV", "quadcopter", "aerial vehicle", "multirotor",
        "vtol platform", "rotor craft",
    ])
    def test_uav_platform_includes_thrust_to_weight(self, intent):
        entries = select_engineering_knowledge_for_platform(intent)
        ids = {e["id"] for e in entries}
        assert "thrust_to_weight_ratio" in ids

    def test_uav_platform_includes_simulation_readiness(self):
        entries = select_engineering_knowledge_for_platform("drone")
        ids = {e["id"] for e in entries}
        assert "simulation_readiness" in ids

    def test_uav_platform_returns_nonempty(self):
        entries = select_engineering_knowledge_for_platform("UAV")
        assert len(entries) >= 1


# ---------------------------------------------------------------------------
# 9. Platform selection — Rover
# ---------------------------------------------------------------------------

class TestPlatformSelectionRover:
    @pytest.mark.parametrize("intent", [
        "rover", "ground robot", "wheeled vehicle", "crawler", "tracked robot",
    ])
    def test_rover_platform_includes_torque_required(self, intent):
        entries = select_engineering_knowledge_for_platform(intent)
        ids = {e["id"] for e in entries}
        assert "torque_required_basic" in ids

    def test_rover_platform_includes_simulation_readiness(self):
        entries = select_engineering_knowledge_for_platform("rover")
        ids = {e["id"] for e in entries}
        assert "simulation_readiness" in ids

    def test_rover_platform_returns_nonempty(self):
        entries = select_engineering_knowledge_for_platform("wheeled vehicle")
        assert len(entries) >= 1


# ---------------------------------------------------------------------------
# 10. Platform selection — Manipulator
# ---------------------------------------------------------------------------

class TestPlatformSelectionManipulator:
    @pytest.mark.parametrize("intent", [
        "manipulator", "robot arm", "gripper", "robotic arm",
    ])
    def test_manipulator_platform_includes_torque_required(self, intent):
        entries = select_engineering_knowledge_for_platform(intent)
        ids = {e["id"] for e in entries}
        assert "torque_required_basic" in ids

    def test_manipulator_platform_includes_safety_margin_review(self):
        entries = select_engineering_knowledge_for_platform("robot arm")
        ids = {e["id"] for e in entries}
        assert "safety_margin_review" in ids

    def test_manipulator_platform_returns_nonempty(self):
        entries = select_engineering_knowledge_for_platform("gripper")
        assert len(entries) >= 1


# ---------------------------------------------------------------------------
# 11. Platform selection — Unknown / None
# ---------------------------------------------------------------------------

class TestPlatformSelectionUnknown:
    @pytest.mark.parametrize("intent", [None, "", "something unknown", "spaceship"])
    def test_unknown_returns_conservative_base(self, intent):
        entries = select_engineering_knowledge_for_platform(intent)
        ids = {e["id"] for e in entries}
        assert "mass_budget" in ids
        assert "power_budget" in ids
        assert "sensor_coverage_check" in ids
        assert "safety_margin_review" in ids
        assert "simulation_readiness" in ids

    def test_unknown_does_not_include_thrust_to_weight(self):
        entries = select_engineering_knowledge_for_platform(None)
        ids = {e["id"] for e in entries}
        assert "thrust_to_weight_ratio" not in ids

    def test_unknown_returns_nonempty(self):
        entries = select_engineering_knowledge_for_platform(None)
        assert len(entries) >= 1


# ---------------------------------------------------------------------------
# 12. Platform selection entries are registry subsets
# ---------------------------------------------------------------------------

class TestPlatformSelectionSubset:
    def test_uav_selection_entries_exist_in_registry(self):
        reg_ids = {e["id"] for e in get_engineering_knowledge_registry()}
        sel_ids = {e["id"] for e in select_engineering_knowledge_for_platform("drone")}
        assert sel_ids.issubset(reg_ids)

    def test_rover_selection_entries_exist_in_registry(self):
        reg_ids = {e["id"] for e in get_engineering_knowledge_registry()}
        sel_ids = {e["id"] for e in select_engineering_knowledge_for_platform("rover")}
        assert sel_ids.issubset(reg_ids)

    def test_manipulator_selection_entries_exist_in_registry(self):
        reg_ids = {e["id"] for e in get_engineering_knowledge_registry()}
        sel_ids = {e["id"] for e in select_engineering_knowledge_for_platform("manipulator")}
        assert sel_ids.issubset(reg_ids)

    def test_unknown_selection_entries_exist_in_registry(self):
        reg_ids = {e["id"] for e in get_engineering_knowledge_registry()}
        sel_ids = {e["id"] for e in select_engineering_knowledge_for_platform(None)}
        assert sel_ids.issubset(reg_ids)

    def test_selection_entries_have_valid_schema(self):
        for intent in ("drone", "rover", "manipulator", None):
            for entry in select_engineering_knowledge_for_platform(intent):
                assert "id" in entry
                assert "domain" in entry
                assert "safety_notes" in entry


# ---------------------------------------------------------------------------
# 13. Registry returns independent copies (mutation safety)
# ---------------------------------------------------------------------------

class TestMutationSafety:
    def test_mutating_registry_copy_does_not_affect_subsequent_calls(self):
        reg1 = get_engineering_knowledge_registry()
        original_title = reg1[0]["title"]
        reg1[0]["title"] = "MUTATED"
        reg2 = get_engineering_knowledge_registry()
        assert reg2[0]["title"] == original_title

    def test_mutating_entry_copy_does_not_affect_registry(self):
        entry = get_engineering_knowledge_entry("power_budget")
        original = entry["title"]
        entry["title"] = "CHANGED"
        assert get_engineering_knowledge_entry("power_budget")["title"] == original

    def test_mutating_filtered_list_does_not_affect_registry(self):
        entries = list_engineering_knowledge_entries(domain="mechanical")
        if entries:
            entries[0]["title"] = "MUTATED"
        fresh = list_engineering_knowledge_entries(domain="mechanical")
        if fresh:
            assert fresh[0]["title"] != "MUTATED"


# ---------------------------------------------------------------------------
# 14. Specific required entry content
# ---------------------------------------------------------------------------

class TestSpecificEntryContent:
    def test_mass_budget_domain_is_mechanical(self):
        e = get_engineering_knowledge_entry("mass_budget")
        assert e["domain"] == "mechanical"

    def test_power_budget_domain_is_electrical(self):
        e = get_engineering_knowledge_entry("power_budget")
        assert e["domain"] == "electrical"

    def test_battery_runtime_domain_is_electrical(self):
        e = get_engineering_knowledge_entry("battery_runtime_estimate")
        assert e["domain"] == "electrical"

    def test_torque_required_domain_is_robotics(self):
        e = get_engineering_knowledge_entry("torque_required_basic")
        assert e["domain"] == "robotics"

    def test_thrust_to_weight_domain_is_aerospace_concept(self):
        e = get_engineering_knowledge_entry("thrust_to_weight_ratio")
        assert e["domain"] == "aerospace_concept"

    def test_simulation_readiness_domain_is_simulation(self):
        e = get_engineering_knowledge_entry("simulation_readiness")
        assert e["domain"] == "simulation"

    def test_safety_margin_review_domain_is_safety(self):
        e = get_engineering_knowledge_entry("safety_margin_review")
        assert e["domain"] == "safety"

    def test_battery_runtime_has_capacity_and_power_inputs(self):
        e = get_engineering_knowledge_entry("battery_runtime_estimate")
        inputs = e["required_inputs"]
        assert any("capacity" in i for i in inputs)
        assert any("power" in i for i in inputs)

    def test_thrust_to_weight_has_thrust_and_mass_inputs(self):
        e = get_engineering_knowledge_entry("thrust_to_weight_ratio")
        inputs = e["required_inputs"]
        assert any("thrust" in i for i in inputs)
        assert any("mass" in i for i in inputs)

    def test_torque_required_has_load_and_moment_inputs(self):
        e = get_engineering_knowledge_entry("torque_required_basic")
        inputs = e["required_inputs"]
        assert any("load" in i for i in inputs)
        assert any("moment" in i for i in inputs)


# ---------------------------------------------------------------------------
# 15. No LLM / internet / computation / simulation references in public API
# ---------------------------------------------------------------------------

class TestNoExecutionClaims:
    _EXECUTION_PHRASES = [
        "llm", "gpt", "openai", "http://", "https://", "requests.get",
        "subprocess", "os.system", "launch_sim", "gazebo.launch",
        "ros2 launch",
    ]

    def test_no_execution_phrases_in_descriptions(self):
        for entry in get_engineering_knowledge_registry():
            desc = entry.get("description", "").lower()
            for phrase in self._EXECUTION_PHRASES:
                assert phrase not in desc, (
                    f"Entry '{entry['id']}' description contains forbidden phrase '{phrase}'"
                )

    def test_no_execution_phrases_in_assumptions(self):
        for entry in get_engineering_knowledge_registry():
            text = " ".join(entry.get("assumptions", [])).lower()
            for phrase in self._EXECUTION_PHRASES:
                assert phrase not in text


# ---------------------------------------------------------------------------
# 16. Helper function return types
# ---------------------------------------------------------------------------

class TestHelperReturnTypes:
    def test_get_registry_returns_list_of_dicts(self):
        result = get_engineering_knowledge_registry()
        assert isinstance(result, list)
        assert all(isinstance(e, dict) for e in result)

    def test_get_entry_returns_dict_or_none(self):
        assert isinstance(get_engineering_knowledge_entry("mass_budget"), dict)
        assert get_engineering_knowledge_entry("nonexistent") is None

    def test_list_entries_no_filter_returns_list(self):
        assert isinstance(list_engineering_knowledge_entries(), list)

    def test_list_entries_with_filter_returns_list(self):
        assert isinstance(list_engineering_knowledge_entries(domain="safety"), list)

    def test_list_domains_returns_list_of_strings(self):
        domains = list_engineering_domains()
        assert isinstance(domains, list)
        assert all(isinstance(d, str) for d in domains)

    def test_select_for_platform_returns_list_of_dicts(self):
        result = select_engineering_knowledge_for_platform("drone")
        assert isinstance(result, list)
        assert all(isinstance(e, dict) for e in result)


# ---------------------------------------------------------------------------
# 17. Case-insensitive platform matching
# ---------------------------------------------------------------------------

class TestCaseInsensitivePlatformMatching:
    def test_uav_uppercase(self):
        ids = {e["id"] for e in select_engineering_knowledge_for_platform("UAV")}
        assert "thrust_to_weight_ratio" in ids

    def test_drone_mixed_case(self):
        ids = {e["id"] for e in select_engineering_knowledge_for_platform("Drone")}
        assert "thrust_to_weight_ratio" in ids

    def test_rover_uppercase(self):
        ids = {e["id"] for e in select_engineering_knowledge_for_platform("ROVER")}
        assert "torque_required_basic" in ids

    def test_manipulator_uppercase(self):
        ids = {e["id"] for e in select_engineering_knowledge_for_platform("MANIPULATOR")}
        assert "torque_required_basic" in ids


# ---------------------------------------------------------------------------
# 18. Confidence rules mention LOW confidence at concept stage
# ---------------------------------------------------------------------------

class TestConfidenceRules:
    def test_every_entry_has_low_confidence_rule(self):
        for entry in get_engineering_knowledge_registry():
            rules = " ".join(entry.get("confidence_rules", [])).lower()
            assert "low" in rules, (
                f"Entry '{entry['id']}' confidence_rules do not mention LOW confidence"
            )

    def test_every_entry_confidence_rules_nonempty(self):
        for entry in get_engineering_knowledge_registry():
            assert len(entry.get("confidence_rules", [])) >= 1
