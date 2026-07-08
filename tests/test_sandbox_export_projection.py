"""Phase 11 Stage 4: additive sandbox findings_projection export envelope tests.

Standalone helper — no mission/export integration, no file I/O. The envelope
mirrors the documented Phase 10 vocabulary (schema/source/origin_fields/count/
items) plus an additive source_schema. Deterministic and filesystem-free.
"""

from backend.app.sandbox.export_projection import build_sandbox_findings_projection
from backend.app.sandbox.finding_projection import project_sandbox_findings
from backend.app.sandbox.report import SandboxCheckResult, SandboxReport
from backend.app.sandbox.runner import run_sandbox

ENVELOPE_KEYS = {"schema", "source", "source_schema", "origin_fields", "count", "items"}

_UNITS_FAIL = {"declared_total_mass_kg": 2.0, "component_masses_kg": [1.0, 1.4]}
_DIM_FAIL = {
    "quantity": {"name": "battery_mass", "dimension": "mass"},
    "expected_dimension": "length",
}
_EQ_FAIL = {"left": "V", "right": "I * R", "values": {"V": 10, "I": 3, "R": 4}}
_ARTIFACT_FAIL = {
    "artifact": {"name": 5, "type": "robot"},  # name wrong type, mass_kg missing
    "required_fields": {"name": "str", "type": "str", "mass_kg": "number"},
}


# ---------------------------------------------------------------------------
# 1-3. envelope shape, fixed values, count invariant
# ---------------------------------------------------------------------------
def test_envelope_exact_key_set():
    env = build_sandbox_findings_projection(run_sandbox("units_math", _UNITS_FAIL))
    assert set(env.keys()) == ENVELOPE_KEYS


def test_envelope_fixed_values():
    env = build_sandbox_findings_projection(run_sandbox("units_math", _UNITS_FAIL))
    assert env["schema"] == "omni.sandbox.findings_projection.v1"
    assert env["source_schema"] == "omni.sandbox.report.v1"
    assert env["origin_fields"] == ["checks"]


def test_count_equals_len_items():
    env = build_sandbox_findings_projection(run_sandbox("units_math", _UNITS_FAIL))
    assert env["count"] == len(env["items"])
    assert env["count"] == 1


# ---------------------------------------------------------------------------
# 4. source derivation
# ---------------------------------------------------------------------------
def test_source_derivation_units_math():
    env = build_sandbox_findings_projection(run_sandbox("units_math", _UNITS_FAIL))
    assert env["source"] == "sandbox_units_math"


def test_source_fallback_when_sandbox_missing():
    env = build_sandbox_findings_projection({"checks": []})
    assert env["source"] == "sandbox"


def test_source_fallback_when_sandbox_empty_string():
    env = build_sandbox_findings_projection({"sandbox": "", "checks": []})
    assert env["source"] == "sandbox"


# ---------------------------------------------------------------------------
# 5. end-to-end projection variety
# ---------------------------------------------------------------------------
def test_variety_units_math():
    report = run_sandbox("units_math", _UNITS_FAIL)
    env = build_sandbox_findings_projection(report)
    assert env["source"] == "sandbox_units_math"
    assert env["items"] == project_sandbox_findings(report)
    assert env["count"] == len(env["items"]) == 1


def test_variety_dimensional_consistency():
    report = run_sandbox("dimensional_consistency", _DIM_FAIL)
    env = build_sandbox_findings_projection(report)
    assert env["source"] == "sandbox_dimensional_consistency"
    assert env["items"] == project_sandbox_findings(report)
    assert env["count"] == len(env["items"]) == 1


def test_variety_equation_sanity():
    report = run_sandbox("equation_sanity", _EQ_FAIL)
    env = build_sandbox_findings_projection(report)
    assert env["source"] == "sandbox_equation_sanity"
    assert env["items"] == project_sandbox_findings(report)
    assert env["count"] == len(env["items"]) == 1


def test_variety_artifact_shape():
    report = run_sandbox("artifact_shape", _ARTIFACT_FAIL)
    env = build_sandbox_findings_projection(report)
    assert env["source"] == "sandbox_artifact_shape"
    assert env["items"] == project_sandbox_findings(report)
    assert env["count"] == len(env["items"])


# ---------------------------------------------------------------------------
# 6. empty projections
# ---------------------------------------------------------------------------
def test_passing_report_yields_empty_envelope():
    report = run_sandbox(
        "units_math",
        {"declared_total_mass_kg": 2.4, "component_masses_kg": [1.0, 1.4]},
    )
    env = build_sandbox_findings_projection(report)
    assert env["count"] == 0
    assert env["items"] == []
    assert set(env.keys()) == ENVELOPE_KEYS


def test_skipped_report_yields_empty_envelope():
    env = build_sandbox_findings_projection(run_sandbox("units_math", {}))
    assert env["count"] == 0
    assert env["items"] == []


def test_unknown_report_yields_empty_envelope():
    env = build_sandbox_findings_projection(run_sandbox("ros2_colcon", {"x": 1}))
    assert env["count"] == 0
    assert env["items"] == []
    # Source still derives from the (unknown) sandbox name.
    assert env["source"] == "sandbox_ros2_colcon"


# ---------------------------------------------------------------------------
# 7. artifact_shape multi-finding count + deterministic order
# ---------------------------------------------------------------------------
def test_artifact_shape_multi_finding_count_and_order():
    report = run_sandbox("artifact_shape", _ARTIFACT_FAIL)
    env = build_sandbox_findings_projection(report)
    assert env["count"] == 2
    assert [item["code"] for item in env["items"]] == [
        "artifact_shape.field.mass_kg",
        "artifact_shape.field.name",
    ]


# ---------------------------------------------------------------------------
# 8. dict/dataclass parity
# ---------------------------------------------------------------------------
def test_dict_dataclass_parity():
    report = run_sandbox("artifact_shape", _ARTIFACT_FAIL)
    from_obj = build_sandbox_findings_projection(report)
    from_dict = build_sandbox_findings_projection(report.to_dict())
    assert from_obj == from_dict


# ---------------------------------------------------------------------------
# 9. raw report untouched
# ---------------------------------------------------------------------------
def test_raw_report_not_mutated_and_no_findings_keys():
    report = run_sandbox("units_math", _UNITS_FAIL)
    before = report.to_dict()

    build_sandbox_findings_projection(report)

    after = report.to_dict()
    assert after == before
    assert "findings" not in after
    assert "findings_projection" not in after
    for check in after["checks"]:
        assert "findings" not in check
        assert "findings_projection" not in check


def test_mutating_envelope_does_not_mutate_source_report():
    report = run_sandbox("units_math", _UNITS_FAIL)
    original_meta = dict(report.checks[0].metadata)

    env = build_sandbox_findings_projection(report)
    env["items"].append({"injected": True})
    env["origin_fields"].append("mutated")
    env["items"][0]["metadata"]["check_metadata"]["delta_kg"] = 999

    # Source report unchanged.
    assert report.checks[0].metadata == original_meta
    # A fresh envelope is unaffected by the mutation above.
    fresh = build_sandbox_findings_projection(report)
    assert fresh["count"] == 1
    assert fresh["origin_fields"] == ["checks"]


def test_envelope_uses_fresh_list_objects():
    report = run_sandbox("units_math", _UNITS_FAIL)
    a = build_sandbox_findings_projection(report)
    b = build_sandbox_findings_projection(report)
    a["origin_fields"].append("x")
    a["items"].append("y")
    assert b["origin_fields"] == ["checks"]
    assert len(b["items"]) == 1


# ---------------------------------------------------------------------------
# 10. helper accepts a hand-built report dict too
# ---------------------------------------------------------------------------
def test_hand_built_report_dict_projects():
    report = SandboxReport(
        sandbox="units_math",
        status="completed",
        checks=[
            SandboxCheckResult(
                check_id="check.failing",
                ok=False,
                severity="warning",
                message="off",
                expected="2.4 kg",
                actual="2.0 kg",
            ),
            SandboxCheckResult(
                check_id="check.passing", ok=True, severity="info", message="ok"
            ),
        ],
    )
    env = build_sandbox_findings_projection(report.to_dict())
    assert env["count"] == 1
    assert env["items"][0]["code"] == "check.failing"
    assert env["source"] == "sandbox_units_math"


def test_unsupported_report_type_raises():
    import pytest

    with pytest.raises(TypeError):
        build_sandbox_findings_projection("not a report")
