from typing import Dict, List

from backend.app.engineering.domains.workshop_parts.workshop_part_schema import WorkshopPartSpec


def validate_workshop_part(spec: WorkshopPartSpec) -> Dict:
    """
    Validate a workshop part specification.

    Level 1 validation checks completeness, fabrication readiness,
    and safety reminders.
    """

    passed_checks: List[str] = []
    warnings: List[str] = []
    blockers: List[str] = []

    # Required basics
    if spec.part_type != "unknown":
        passed_checks.append("Part type detected.")
    else:
        blockers.append("Part type is unknown.")

    if spec.target_device:
        passed_checks.append("Target device detected.")
    else:
        warnings.append("Target device is missing or unclear.")

    if spec.mounting_style:
        passed_checks.append("Mounting style detected.")
    else:
        warnings.append("Mounting style is missing.")

    if spec.material:
        passed_checks.append(f"Material selected: {spec.material}.")
    else:
        warnings.append("Material is missing.")

    if spec.fabrication_method == "fdm_3d_printing":
        passed_checks.append("Fabrication method set to FDM 3D printing.")

    # Printability reminders
    if spec.material == "PLA":
        passed_checks.append("PLA is suitable for a first prototype.")
    elif spec.material in ["ABS", "carbon_fiber"]:
        warnings.append(f"{spec.material} may require more controlled printing conditions.")

    # Angle-specific validation
    if spec.part_type == "camera_mount":
        if spec.angle_degrees is not None:
            passed_checks.append(f"Camera angle specified: {spec.angle_degrees} degrees.")
        else:
            warnings.append("Camera mount angle is not specified.")

    # Existing missing requirements from inference
    for item in spec.missing_requirements:
        warnings.append(item)

    status = "pass"
    if warnings:
        status = "warning"
    if blockers:
        status = "blocked"

    return {
        "domain": "workshop_parts",
        "status": status,
        "passed_checks": passed_checks,
        "warnings": warnings,
        "blockers": blockers,
        "safety_notes": spec.safety_notes,
    }