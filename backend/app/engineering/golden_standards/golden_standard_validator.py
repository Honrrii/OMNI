from dataclasses import dataclass, field
from typing import Any, Dict, List

from backend.app.engineering.golden_standards.golden_standard_registry import (
    GoldenStandard,
    get_golden_standard,
)


@dataclass
class GoldenStandardValidationResult:
    """
    Result object returned after checking a mission against an OMNI Golden Standard.
    """

    standard_id: str
    standard_name: str
    status: str
    score: float

    passed_artifacts: List[str] = field(default_factory=list)
    missing_artifacts: List[str] = field(default_factory=list)

    passed_calculations: List[str] = field(default_factory=list)
    missing_calculations: List[str] = field(default_factory=list)

    passed_validation_checks: List[str] = field(default_factory=list)
    missing_validation_checks: List[str] = field(default_factory=list)

    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "standard_id": self.standard_id,
            "standard_name": self.standard_name,
            "status": self.status,
            "score": self.score,
            "passed_artifacts": self.passed_artifacts,
            "missing_artifacts": self.missing_artifacts,
            "passed_calculations": self.passed_calculations,
            "missing_calculations": self.missing_calculations,
            "passed_validation_checks": self.passed_validation_checks,
            "missing_validation_checks": self.missing_validation_checks,
            "notes": self.notes,
        }


def _normalize(value: str) -> str:
    """
    Normalize strings so small naming differences do not break validation.
    Example:
    'Thrust-to-Weight Ratio' -> 'thrust_to_weight_ratio'
    """

    return (
        value.lower()
        .replace("-", "_")
        .replace(" ", "_")
        .replace("/", "_")
        .strip()
    )


def _flatten_keys(data: Any, keys: List[str] | None = None) -> List[str]:
    """
    Recursively collect all dictionary keys from a nested mission result.
    This lets the validator inspect flexible mission_result structures.
    """

    if keys is None:
        keys = []

    if isinstance(data, dict):
        for key, value in data.items():
            keys.append(_normalize(str(key)))
            _flatten_keys(value, keys)

    elif isinstance(data, list):
        for item in data:
            _flatten_keys(item, keys)

    return keys


def _contains_required_item(flattened_keys: List[str], required_item: str) -> bool:
    """
    Checks if a required artifact/calculation/check appears in the mission result.

    Important:
    We allow the mission result key to be more specific than the required item,
    but we do not allow a vague key to satisfy a more specific requirement.

    Example:
    - "thrust_to_weight_ratio_reasonable_check" can satisfy
      "thrust_to_weight_ratio_reasonable"
    - "thrust_to_weight_ratio" should NOT satisfy
      "thrust_to_weight_ratio_reasonable"
    """

    normalized_required = _normalize(required_item)

    return any(
        normalized_required == key
        or normalized_required in key
        for key in flattened_keys
    )


def validate_against_golden_standard(
    mission_result: Dict[str, Any],
    standard_id: str,
) -> GoldenStandardValidationResult:
    """
    Validate a mission result against one of OMNI's official Golden Standards.

    This does not prove the engineering is physically correct yet.
    It checks whether the required sections, calculations, and validation
    artifacts exist in the mission output.
    """

    standard: GoldenStandard = get_golden_standard(standard_id)
    flattened_keys = _flatten_keys(mission_result)

    passed_artifacts = []
    missing_artifacts = []

    for artifact in standard.required_artifacts:
        if _contains_required_item(flattened_keys, artifact):
            passed_artifacts.append(artifact)
        else:
            missing_artifacts.append(artifact)

    passed_calculations = []
    missing_calculations = []

    for calculation in standard.required_calculations:
        if _contains_required_item(flattened_keys, calculation):
            passed_calculations.append(calculation)
        else:
            missing_calculations.append(calculation)

    passed_validation_checks = []
    missing_validation_checks = []

    for check in standard.required_validation_checks:
        if _contains_required_item(flattened_keys, check):
            passed_validation_checks.append(check)
        else:
            missing_validation_checks.append(check)

    total_required = (
        len(standard.required_artifacts)
        + len(standard.required_calculations)
        + len(standard.required_validation_checks)
    )

    total_passed = (
        len(passed_artifacts)
        + len(passed_calculations)
        + len(passed_validation_checks)
    )

    score = round(total_passed / total_required, 2) if total_required else 0.0

    if score >= 0.90:
        status = "passed"
    elif score >= 0.50:
        status = "partial"
    else:
        status = "failed"

    notes = [
        "This validation checks structural completeness, not full physical correctness.",
        "Future validators should verify numerical calculations and source-backed assumptions.",
    ]

    return GoldenStandardValidationResult(
        standard_id=standard.id,
        standard_name=standard.name,
        status=status,
        score=score,
        passed_artifacts=passed_artifacts,
        missing_artifacts=missing_artifacts,
        passed_calculations=passed_calculations,
        missing_calculations=missing_calculations,
        passed_validation_checks=passed_validation_checks,
        missing_validation_checks=missing_validation_checks,
        notes=notes,
    )