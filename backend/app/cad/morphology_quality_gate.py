"""
OMNI CAD Morphology Quality Gate.

Validates a MorphologySpec before it is handed to the Fusion 360 / CadQuery
generator. Produces a structured result compatible with OMNI's existing
reliability/validation style: PASS / WARN / FAIL plus a score.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

try:
    from .cad_morphology_ir import MorphologySpec
except ImportError:  # Allows direct script execution from this folder.
    from cad_morphology_ir import MorphologySpec  # type: ignore


LEGGED_FAMILIES = {
    "insectoid_legged_robot",
    "hexapod_robot",
    "quadruped_robot",
    "sci_fi_walker",
}


@dataclass
class MorphologyFinding:
    check: str
    status: str  # PASS | WARN | FAIL
    message: str
    recommendation: str = ""


@dataclass
class MorphologyGateResult:
    verdict: str
    overall_score: float
    morphology_family: str
    body_posture: str
    findings: List[MorphologyFinding] = field(default_factory=list)
    hard_negative_violations: List[str] = field(default_factory=list)
    missing_elements: List[str] = field(default_factory=list)
    recommended_fixes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verdict": self.verdict,
            "overall_score": self.overall_score,
            "morphology_family": self.morphology_family,
            "body_posture": self.body_posture,
            "findings": [
                {
                    "check": finding.check,
                    "status": finding.status,
                    "message": finding.message,
                    "recommendation": finding.recommendation,
                }
                for finding in self.findings
            ],
            "hard_negative_violations": self.hard_negative_violations,
            "missing_elements": self.missing_elements,
            "recommended_fixes": self.recommended_fixes,
        }

    def to_markdown(self) -> str:
        lines = [
            "# CAD Morphology Quality Gate Report",
            "",
            f"**Verdict:** {self.verdict}",
            f"**Score:** {self.overall_score:.1f} / 10.0",
            f"**Family:** {self.morphology_family}",
            f"**Posture:** {self.body_posture}",
            "",
            "## Findings",
        ]
        for finding in self.findings:
            icon = {"PASS": "✓", "WARN": "⚠", "FAIL": "✗"}.get(finding.status, "?")
            lines.append(f"- {icon} **{finding.check}**: {finding.message}")
            if finding.recommendation:
                lines.append(f"  - Fix: {finding.recommendation}")

        if self.hard_negative_violations:
            lines.extend(["", "## Hard-Negative Violations"])
            lines.extend(f"- {item}" for item in self.hard_negative_violations)
        if self.missing_elements:
            lines.extend(["", "## Missing Elements"])
            lines.extend(f"- {item}" for item in self.missing_elements)
        if self.recommended_fixes:
            lines.extend(["", "## Recommended Fixes"])
            lines.extend(f"- {item}" for item in self.recommended_fixes)
        return "\n".join(lines)


def _check_family_not_generic(spec: MorphologySpec) -> MorphologyFinding:
    if spec.morphology_family == "generic_robotic_platform":
        return MorphologyFinding(
            check="morphology_family",
            status="WARN",
            message="Morphology family is generic_robotic_platform. Mission may not have been specific enough.",
            recommendation="Provide more specific mission keywords such as insect, hexapod, rover, drone, manipulator, or tracked.",
        )
    return MorphologyFinding(
        check="morphology_family",
        status="PASS",
        message=f"Morphology family detected: {spec.morphology_family}.",
    )


def _check_body_segmentation(spec: MorphologySpec) -> MorphologyFinding:
    if not spec.primary_segments:
        return MorphologyFinding(
            check="body_segmentation",
            status="FAIL",
            message="No body segments defined.",
            recommendation="Add at least one BodySegment to primary_segments.",
        )

    if spec.morphology_family in LEGGED_FAMILIES and len(spec.primary_segments) < 2:
        return MorphologyFinding(
            check="body_segmentation",
            status="FAIL",
            message="Legged robot has only one body segment. Segmented morphology is required.",
            recommendation="Add head/thorax/abdomen or pelvis/torso/head segments at different Z heights.",
        )

    if spec.morphology_family in {"insectoid_legged_robot", "hexapod_robot"}:
        names = {segment.name.lower() for segment in spec.primary_segments}
        if not ({"head", "thorax"} <= names or {"head", "main_body"} <= names):
            return MorphologyFinding(
                check="body_segmentation",
                status="WARN",
                message="Insectoid/hexapod morphology should include recognizable head and thorax/main body segments.",
                recommendation="Name body segments clearly so the Fusion generator can create labeled geometry.",
            )

    return MorphologyFinding(
        check="body_segmentation",
        status="PASS",
        message=f"{len(spec.primary_segments)} body segments defined.",
    )


def _check_verticality(spec: MorphologySpec) -> MorphologyFinding:
    if spec.morphology_family not in LEGGED_FAMILIES:
        return MorphologyFinding(
            check="verticality",
            status="PASS",
            message="Verticality check not required for this morphology family.",
        )

    vs = spec.vertical_structure
    if spec.body_posture != "standing":
        return MorphologyFinding(
            check="verticality",
            status="FAIL",
            message=f"Legged robot posture is '{spec.body_posture}', not standing.",
            recommendation="Set body_posture='standing' for legged/walking morphology.",
        )
    if not vs.body_elevated_above_ground:
        return MorphologyFinding(
            check="verticality",
            status="FAIL",
            message="Body is not elevated above ground for a standing robot.",
            recommendation="Set body_elevated_above_ground=True and body_elevation_mm > 30.",
        )
    if vs.body_elevation_mm < 20:
        return MorphologyFinding(
            check="verticality",
            status="WARN",
            message=f"Body elevation is only {vs.body_elevation_mm:.0f}mm — very low for a standing robot.",
            recommendation="Increase body_elevation_mm to at least 40mm for realistic leg geometry.",
        )

    z_values = [segment.z_base_mm for segment in spec.primary_segments]
    if z_values and max(z_values) - min(z_values) < 5:
        return MorphologyFinding(
            check="verticality",
            status="WARN",
            message="Body segments are at nearly the same Z height — possible flat-plate fallback.",
            recommendation="Use different z_base_mm values for major body segments.",
        )

    return MorphologyFinding(
        check="verticality",
        status="PASS",
        message=f"Body elevation: {vs.body_elevation_mm:.0f}mm. Segment Z span: {min(z_values):.0f}–{max(z_values):.0f}mm.",
    )


def _expected_min_leg_count(spec: MorphologySpec, mission_text: str) -> int:
    text = mission_text.lower()
    if spec.morphology_family == "hexapod_robot" or "hexapod" in text:
        return 6
    if spec.morphology_family == "quadruped_robot" or "quadruped" in text:
        return 4
    if "spider" in text or "arachnid" in text or "octopod" in text:
        return 8
    if spec.morphology_family in LEGGED_FAMILIES:
        return 2 if spec.morphology_family == "sci_fi_walker" else 4
    return 0


def _check_appendages(spec: MorphologySpec, mission_text: str) -> MorphologyFinding:
    if spec.morphology_family not in LEGGED_FAMILIES:
        return MorphologyFinding(
            check="appendages",
            status="PASS",
            message="Appendage ground-contact check not required for this family.",
        )

    legs = [app for app in spec.appendages if app.appendage_type == "leg"]
    expected_min = _expected_min_leg_count(spec, mission_text)
    if len(legs) < expected_min:
        return MorphologyFinding(
            check="appendages",
            status="FAIL",
            message=f"Only {len(legs)} legs defined; expected at least {expected_min} for {spec.morphology_family}.",
            recommendation="Add leg Appendage objects with ground_contact=True and side-mounted anchors.",
        )

    no_contact = [app.name for app in legs if not app.ground_contact]
    if no_contact:
        return MorphologyFinding(
            check="appendages",
            status="FAIL",
            message=f"Legs without ground_contact=True: {', '.join(no_contact)}.",
            recommendation="All walking legs must have ground_contact=True.",
        )

    zero_x = [app.name for app in legs if abs(app.attach_x_mm) < 1.0]
    if zero_x:
        return MorphologyFinding(
            check="appendages",
            status="WARN",
            message=f"Some legs attach at X=0 centerline: {', '.join(zero_x)}.",
            recommendation="Attach legs to the sides of the body/thorax using non-zero X coordinates.",
        )

    return MorphologyFinding(
        check="appendages",
        status="PASS",
        message=f"{len(legs)} legs defined, all with ground contact.",
    )


def _check_anchors(spec: MorphologySpec) -> MorphologyFinding:
    if spec.morphology_family not in LEGGED_FAMILIES:
        return MorphologyFinding("anchor_points", "PASS", "Anchor-point check not required for this family.")

    if not spec.anchor_points:
        return MorphologyFinding(
            check="anchor_points",
            status="WARN",
            message="No anchor points defined for legged morphology.",
            recommendation="Define named side anchors for each leg so the CAD generator can place joints deterministically.",
        )

    side_anchors = [anchor for anchor in spec.anchor_points if abs(anchor.x_mm) > 1.0]
    if len(side_anchors) < max(2, spec.count_appendages("leg") // 2):
        return MorphologyFinding(
            check="anchor_points",
            status="WARN",
            message="Few side-mounted anchors were defined relative to leg count.",
            recommendation="Add paired left/right anchors along the body/thorax.",
        )

    return MorphologyFinding(
        check="anchor_points",
        status="PASS",
        message=f"{len(spec.anchor_points)} anchor points defined.",
    )


def _check_hard_negatives(spec: MorphologySpec) -> List[str]:
    violations: List[str] = []
    if spec.morphology_family in LEGGED_FAMILIES and not spec.hard_negatives:
        violations.append("No hard_negatives defined for legged robot — generator may fall back to generic shapes.")

    if spec.morphology_family in LEGGED_FAMILIES:
        bad_values = ["aerial", "radial-symmetric-drone", "drone", "quadcopter"]
        searchable = " ".join(
            [
                spec.body_posture,
                spec.silhouette,
                spec.symmetry_strategy,
                spec.notes,
                " ".join(segment.name + " " + segment.label for segment in spec.primary_segments),
                " ".join(app.name + " " + app.appendage_type for app in spec.appendages),
            ]
        ).lower()
        for value in bad_values:
            if value in searchable and value not in " ".join(spec.hard_negatives).lower():
                violations.append(f"Possible hard-negative pattern in generated spec: '{value}'")

    return violations


def _check_quality_checklist(spec: MorphologySpec) -> MorphologyFinding:
    if not spec.quality_checklist:
        return MorphologyFinding(
            check="quality_checklist",
            status="WARN",
            message="No quality checklist items defined.",
            recommendation="Add quality_checklist items so downstream generators and validators can verify morphology intent.",
        )
    return MorphologyFinding(
        check="quality_checklist",
        status="PASS",
        message=f"{len(spec.quality_checklist)} quality checklist items defined.",
    )


def _check_mission_alignment(spec: MorphologySpec, mission_text: str) -> MorphologyFinding:
    text = mission_text.lower()
    family = spec.morphology_family
    mismatches = []

    if family == "aerial_drone" and any(kw in text for kw in ["legged", "walking", "hexapod"]):
        mismatches.append("Mission mentions legged/walking keywords but family is aerial_drone.")
    if family in {"insectoid_legged_robot", "hexapod_robot", "quadruped_robot", "sci_fi_walker"} and any(
        kw in text for kw in ["quadcopter", "uav", "propeller"]
    ):
        mismatches.append("Mission mentions drone keywords but family is legged robot.")
    if "hexapod" in text and family != "hexapod_robot":
        mismatches.append("Mission explicitly says hexapod but family is not hexapod_robot.")
    if "insect" in text and family == "hexapod_robot" and "hexapod" not in text:
        mismatches.append("Mission says insect-inspired, but family was resolved as generic hexapod_robot.")

    if mismatches:
        return MorphologyFinding(
            check="mission_alignment",
            status="WARN",
            message=" ".join(mismatches),
            recommendation="Check _detect_family and family_hint resolution in cad_morphology_planner.py.",
        )

    return MorphologyFinding(
        check="mission_alignment",
        status="PASS",
        message=f"Morphology family '{family}' appears consistent with mission text.",
    )


def _score(findings: List[MorphologyFinding], violations: List[str]) -> float:
    value = {"PASS": 10.0, "WARN": 6.0, "FAIL": 1.0}
    if not findings:
        return 0.0
    raw = sum(value.get(finding.status, 5.0) for finding in findings) / len(findings)
    violation_penalty = min(3.0, len(violations) * 1.0)
    fail_count = sum(1 for finding in findings if finding.status == "FAIL")
    fail_penalty = min(4.0, fail_count * 1.5)
    score = max(0.0, min(10.0, raw - violation_penalty - fail_penalty))
    if fail_count > 0:
        score = min(score, 6.5)
    return round(score, 2)


def _verdict(score: float, findings: List[MorphologyFinding], violations: List[str]) -> str:
    fail_count = sum(1 for finding in findings if finding.status == "FAIL")
    if fail_count >= 2 or score < 4.0 or len(violations) >= 2:
        return "FAIL"
    if fail_count > 0 or score < 7.0 or violations:
        return "WARN"
    return "PASS"


def validate_morphology_spec(spec: MorphologySpec, mission_text: str = "") -> MorphologyGateResult:
    findings = [
        _check_family_not_generic(spec),
        _check_body_segmentation(spec),
        _check_verticality(spec),
        _check_appendages(spec, mission_text),
        _check_anchors(spec),
        _check_quality_checklist(spec),
        _check_mission_alignment(spec, mission_text),
    ]
    violations = _check_hard_negatives(spec)
    missing = [finding.message for finding in findings if finding.status == "FAIL"]
    fixes = [finding.recommendation for finding in findings if finding.status in {"FAIL", "WARN"} and finding.recommendation]
    score = _score(findings, violations)
    verdict = _verdict(score, findings, violations)

    return MorphologyGateResult(
        verdict=verdict,
        overall_score=score,
        morphology_family=spec.morphology_family,
        body_posture=spec.body_posture,
        findings=findings,
        hard_negative_violations=violations,
        missing_elements=missing,
        recommended_fixes=fixes,
    )


def validate_morphology_spec_dict(spec_dict: Dict[str, Any], mission_text: str = "") -> Dict[str, Any]:
    spec = MorphologySpec.from_dict(spec_dict)
    return validate_morphology_spec(spec, mission_text).to_dict()
