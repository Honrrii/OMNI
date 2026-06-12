"""Artifact shape sandbox check (Phase 11 Stage 2).

Validate that a dict-shaped artifact carries required fields with expected
primitive types. Pure Python only — no jsonschema, no external binaries, no I/O.

Expected input shape::

    {
        "artifact_name": "sandbox_candidate",
        "artifact": {"name": "test_robot", "type": "robot", "mass_kg": 2.4},
        "required_fields": {"name": "str", "type": "str", "mass_kg": "number"},
    }

Outcomes:
- all required fields present with correct type -> status "passed" (one passing check)
- missing field(s) / wrong type(s)             -> status "completed", one
                                                   "warning" check per offending
                                                   field, ordered by sorted name
- missing/invalid schema                        -> status "skipped", one "info" check
"""
from __future__ import annotations

from typing import Any, Optional

from backend.app.sandbox.report import SandboxCheckResult, SandboxReport

_SANDBOX_NAME = "artifact_shape"


# Type tokens -> predicate. "number" accepts int/float but not bool.
def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


_TYPE_PREDICATES = {
    "str": lambda v: isinstance(v, str),
    "number": _is_number,
    "int": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "float": lambda v: isinstance(v, float),
    "bool": lambda v: isinstance(v, bool),
    "list": lambda v: isinstance(v, list),
    "dict": lambda v: isinstance(v, dict),
}


def _actual_type_name(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, str):
        return "str"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "dict"
    if value is None:
        return "null"
    return type(value).__name__


def _skip(message: str) -> SandboxReport:
    return SandboxReport(
        sandbox=_SANDBOX_NAME,
        status="skipped",
        checks=[
            SandboxCheckResult(
                check_id="artifact_shape.input",
                ok=True,
                severity="info",
                message=message,
                metadata={"reason": "missing_or_invalid_input"},
            )
        ],
    )


def run_artifact_shape_check(inputs: Optional[dict[str, Any]]) -> SandboxReport:
    """Run the deterministic artifact shape check over ``inputs``."""
    if not isinstance(inputs, dict):
        return _skip("artifact_shape requires a dict of inputs; none was provided.")

    artifact = inputs.get("artifact")
    if not isinstance(artifact, dict):
        return _skip("artifact_shape requires an 'artifact' dict.")

    required = inputs.get("required_fields")
    if not isinstance(required, dict) or not required:
        return _skip(
            "artifact_shape requires a non-empty 'required_fields' mapping."
        )

    # Validate the schema's own type tokens before evaluating the artifact.
    for field_name, type_token in required.items():
        if not isinstance(field_name, str):
            return _skip("artifact_shape 'required_fields' keys must be strings.")
        if not isinstance(type_token, str) or type_token not in _TYPE_PREDICATES:
            return _skip(
                "artifact_shape 'required_fields' values must be one of: "
                + ", ".join(sorted(_TYPE_PREDICATES))
                + "."
            )

    artifact_name = inputs.get("artifact_name")
    artifact_name = (
        artifact_name
        if isinstance(artifact_name, str) and artifact_name.strip()
        else "artifact"
    )

    problems: list[SandboxCheckResult] = []
    # Deterministic ordering by sorted field name.
    for field_name in sorted(required):
        type_token = required[field_name]
        predicate = _TYPE_PREDICATES[type_token]

        if field_name not in artifact:
            problems.append(
                SandboxCheckResult(
                    check_id=f"artifact_shape.field.{field_name}",
                    ok=False,
                    severity="warning",
                    message=(
                        f"Artifact '{artifact_name}' is missing required field "
                        f"'{field_name}'."
                    ),
                    expected=type_token,
                    actual="missing",
                    metadata={
                        "field": field_name,
                        "problem": "missing_field",
                        "expected_type": type_token,
                    },
                )
            )
            continue

        value = artifact[field_name]
        if not predicate(value):
            problems.append(
                SandboxCheckResult(
                    check_id=f"artifact_shape.field.{field_name}",
                    ok=False,
                    severity="warning",
                    message=(
                        f"Artifact '{artifact_name}' field '{field_name}' has type "
                        f"'{_actual_type_name(value)}', expected '{type_token}'."
                    ),
                    expected=type_token,
                    actual=_actual_type_name(value),
                    metadata={
                        "field": field_name,
                        "problem": "wrong_type",
                        "expected_type": type_token,
                        "actual_type": _actual_type_name(value),
                    },
                )
            )

    if problems:
        return SandboxReport(
            sandbox=_SANDBOX_NAME,
            status="completed",
            checks=problems,
        )

    check = SandboxCheckResult(
        check_id="artifact_shape.ok",
        ok=True,
        severity="info",
        message=f"Artifact '{artifact_name}' has all required fields with expected types.",
        metadata={
            "artifact_name": artifact_name,
            "checked_fields": sorted(required),
        },
    )
    return SandboxReport(
        sandbox=_SANDBOX_NAME,
        status="passed",
        checks=[check],
    )
