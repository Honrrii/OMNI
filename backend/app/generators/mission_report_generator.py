from pathlib import Path
from datetime import datetime
import json
import re
from typing import Any, Dict, Optional


def _slugify(text: str) -> str:
    """
    Convert a mission title into a safe folder/file name.
    """
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = text.strip("_")
    return text[:80] or "omni_mission"


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    """
    Write structured JSON with clean indentation.
    """
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _collect_exported_files(export_dir: Path) -> list[str]:
    """
    Collect human-relevant exported files inside a mission export folder.

    This intentionally skips generated build/cache artifacts so the
    mission report stays readable and professional.
    """
    if not export_dir.exists():
        return []

    ignored_parts = {
        "__pycache__",
        ".pytest_cache",
        "build",
        "install",
        "log",
    }

    ignored_suffixes = {
        ".pyc",
        ".pyo",
        ".log",
    }

    files = []

    for file_path in export_dir.rglob("*"):
        if not file_path.is_file():
            continue

        relative_path = file_path.relative_to(export_dir)

        if any(part in ignored_parts for part in relative_path.parts):
            continue

        if file_path.suffix in ignored_suffixes:
            continue

        files.append(str(relative_path))

    return sorted(files)


def _extract_artifacts(mission_result: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Extract artifact data from an OMNI mission result without assuming
    one exact backend schema.
    """
    if not mission_result:
        return {}

    if "artifacts" in mission_result and isinstance(mission_result["artifacts"], dict):
        return mission_result["artifacts"]

    return mission_result


def generate_mission_report(
    mission_text: str,
    mission_result: Optional[Dict[str, Any]] = None,
    validation_result: Optional[Dict[str, Any]] = None,
    output_root: str | Path = "outputs/omni_missions",
    mission_slug: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate a professional OMNI mission report, artifact manifest,
    and provenance record for an engineering mission.

    This creates:
    - OMNI_MISSION_REPORT.md
    - artifact_manifest.json
    - provenance_record.json
    """

    slug = mission_slug or _slugify(mission_text)
    export_dir = Path(output_root) / slug
    export_dir.mkdir(parents=True, exist_ok=True)

    created_at = datetime.utcnow().isoformat() + "Z"
    artifacts = _extract_artifacts(mission_result)
    exported_files_before_report = _collect_exported_files(export_dir)

    validation_status = "NOT_RUN"
    validation_summary = "No validation result was provided."

    if validation_result:
        validation_status = str(
            validation_result.get("status")
            or validation_result.get("overall_status")
            or validation_result.get("result")
            or "UNKNOWN"
        )
        validation_summary = str(
            validation_result.get("summary")
            or validation_result.get("message")
            or "Validation completed, but no summary was provided."
        )

    artifact_manifest = {
        "mission": mission_text,
        "mission_slug": slug,
        "created_at": created_at,
        "output_directory": str(export_dir),
        "validation_status": validation_status,
        "exported_files": exported_files_before_report,
        "artifact_sections_detected": list(artifacts.keys()) if isinstance(artifacts, dict) else [],
    }

    provenance_record = {
        "mission": mission_text,
        "mission_slug": slug,
        "created_at": created_at,
        "system": "OMNI",
        "record_type": "engineering_provenance",
        "stages": [
            {
                "stage": "Observe",
                "description": "Captured the user's natural-language engineering mission.",
            },
            {
                "stage": "Command",
                "description": "Converted the mission into structured engineering intent.",
            },
            {
                "stage": "Generate",
                "description": "Produced robotics, CAD, software, validation, or planning artifacts.",
            },
            {
                "stage": "Validate",
                "description": "Reviewed available outputs for risks, blockers, and approval needs.",
                "status": validation_status,
            },
            {
                "stage": "Report",
                "description": "Generated a mission dossier for human review and future development.",
            },
        ],
    }

    report_path = export_dir / "OMNI_MISSION_REPORT.md"
    manifest_path = export_dir / "artifact_manifest.json"
    provenance_path = export_dir / "provenance_record.json"

    report_md = _build_report_markdown(
        mission_text=mission_text,
        created_at=created_at,
        mission_slug=slug,
        artifacts=artifacts,
        validation_status=validation_status,
        validation_summary=validation_summary,
        exported_files=exported_files_before_report,
        provenance_record=provenance_record,
    )

    report_path.write_text(report_md, encoding="utf-8")
    _write_json(manifest_path, artifact_manifest)
    _write_json(provenance_path, provenance_record)

    exported_files_after_report = _collect_exported_files(export_dir)

    return {
        "status": "generated",
        "mission_slug": slug,
        "output_directory": str(export_dir),
        "report_file": str(report_path),
        "artifact_manifest": str(manifest_path),
        "provenance_record": str(provenance_path),
        "exported_files": exported_files_after_report,
    }


def _build_report_markdown(
    mission_text: str,
    created_at: str,
    mission_slug: str,
    artifacts: Dict[str, Any],
    validation_status: str,
    validation_summary: str,
    exported_files: list[str],
    provenance_record: Dict[str, Any],
) -> str:
    """
    Build the final Markdown mission report.
    """

    artifact_section = _format_artifacts(artifacts)
    exported_files_section = _format_exported_files(exported_files)
    provenance_section = _format_provenance(provenance_record)

    return f"""# OMNI Mission Report

## 1. Mission Summary

**Mission ID:** `{mission_slug}`  
**Created:** `{created_at}`  

**User Mission:**

> {mission_text}

OMNI processed this mission as a structured robotics engineering request and generated a mission dossier for review, iteration, and future implementation.

---

## 2. Generated Artifact Overview

{artifact_section}

---

## 3. Validation Summary

**Validation Status:** `{validation_status}`

{validation_summary}

---

## 4. Engineering Review Notes

This report is intended to support human engineering review. Any generated CAD, ROS2, electronics, fabrication, or control outputs should be checked before real-world deployment.

Recommended review areas:

- Mechanical feasibility
- Electrical safety
- Power budget assumptions
- ROS2 node and topic correctness
- CAD manufacturability
- Sensor and actuator compatibility
- Human approval before hardware execution

---

## 5. Engineering Provenance

{provenance_section}

---

## 6. Exported Files

{exported_files_section}

---

## 7. Human Approval Gate

Before using this mission for physical hardware, a human reviewer should confirm:

- The design assumptions are realistic.
- The generated files match the intended system.
- The validation status contains no unresolved blockers.
- Any safety-critical decisions have been reviewed manually.

---

Generated by **OMNI — Multi-Agent AI Robotics Builder**.
"""


def _format_artifacts(artifacts: Dict[str, Any]) -> str:
    if not artifacts:
        return "No structured artifacts were provided to the report generator."

    lines = []

    for key, value in artifacts.items():
        title = key.replace("_", " ").title()
        lines.append(f"### {title}")

        if isinstance(value, (dict, list)):
            preview = json.dumps(value, indent=2)
            if len(preview) > 2500:
                preview = preview[:2500] + "\n... truncated for report readability ..."
            lines.append(f"```json\n{preview}\n```")
        else:
            text = str(value)
            if len(text) > 2500:
                text = text[:2500] + "\n... truncated for report readability ..."
            lines.append(text)

        lines.append("")

    return "\n".join(lines)


def _format_exported_files(exported_files: list[str]) -> str:
    if not exported_files:
        return "No previously exported files were detected before report generation."

    return "\n".join(f"- `{file}`" for file in exported_files)


def _format_provenance(provenance_record: Dict[str, Any]) -> str:
    stages = provenance_record.get("stages", [])

    if not stages:
        return "No provenance stages were recorded."

    lines = []

    for stage in stages:
        name = stage.get("stage", "Unknown")
        description = stage.get("description", "")
        status = stage.get("status")

        if status:
            lines.append(f"- **{name}:** {description} Status: `{status}`")
        else:
            lines.append(f"- **{name}:** {description}")

    return "\n".join(lines)