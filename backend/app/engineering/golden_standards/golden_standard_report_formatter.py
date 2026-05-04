from typing import Any, Dict, List


def _format_list(title: str, items: List[str]) -> List[str]:
    """
    Format a list section for a readable validation report.
    """

    lines = [f"{title}:"]

    if not items:
        lines.append("- None")
        return lines

    for item in items:
        lines.append(f"- {item}")

    return lines


def format_golden_standard_report(report: Dict[str, Any]) -> str:
    """
    Converts a Golden Standard validation dictionary into a clean,
    human-readable report.

    This is intended for frontend display, exported reports, and debugging.
    """

    if not report:
        return "No Golden Standard report available."

    standard_id = report.get("standard_id", "Unknown")
    standard_name = report.get("standard_name", "Unknown Standard")
    status = report.get("status", "unknown")
    score = report.get("score", 0.0)

    lines = [
        f"Golden Standard Validation Report",
        f"Standard: {standard_id} — {standard_name}",
        f"Status: {status.upper()}",
        f"Score: {score}",
        "",
    ]

    lines.extend(_format_list("Passed Artifacts", report.get("passed_artifacts", [])))
    lines.append("")

    lines.extend(_format_list("Missing Artifacts", report.get("missing_artifacts", [])))
    lines.append("")

    lines.extend(_format_list("Passed Calculations", report.get("passed_calculations", [])))
    lines.append("")

    lines.extend(_format_list("Missing Calculations", report.get("missing_calculations", [])))
    lines.append("")

    lines.extend(
        _format_list(
            "Passed Validation Checks",
            report.get("passed_validation_checks", []),
        )
    )
    lines.append("")

    lines.extend(
        _format_list(
            "Missing Validation Checks",
            report.get("missing_validation_checks", []),
        )
    )
    lines.append("")

    lines.extend(_format_list("Notes", report.get("notes", [])))

    return "\n".join(lines)