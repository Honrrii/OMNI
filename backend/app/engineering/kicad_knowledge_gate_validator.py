from __future__ import annotations

import csv
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class KiCadGateIssue:
    rule_id: str
    severity: str
    message: str
    file: Optional[str] = None


REQUIRED_KICAD_FILES = [
    ".kicad_pro",
    ".kicad_sch",
    ".kicad_pcb",
]

REQUIRED_SUPPORT_FILES = [
    "README.md",
    "electronics_architecture.json",
    "power_budget.json",
    "connector_map.json",
    "bom.csv",
    "kicad_knowledge_context.md",
]


def resolve_kicad_dir(root_path: str | Path) -> Path:
    """
    Accept either:
    - mission export folder
    - generated_kicad folder directly
    """
    root = Path(root_path).resolve()

    if root.name == "generated_kicad":
        return root

    generated_kicad = root / "generated_kicad"
    if generated_kicad.exists():
        return generated_kicad

    return root


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def load_json(path: Path) -> tuple[Optional[Any], Optional[str]]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:
        return None, str(exc)


def load_csv_rows(path: Path) -> tuple[List[Dict[str, str]], Optional[str]]:
    try:
        with path.open("r", encoding="utf-8", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            return list(reader), None
    except Exception as exc:
        return [], str(exc)


def find_first_file_with_suffix(root: Path, suffix: str) -> Optional[Path]:
    matches = sorted(root.glob(f"*{suffix}"))
    return matches[0] if matches else None


def relative_file(root: Path, path: Optional[Path]) -> Optional[str]:
    if path is None:
        return None

    try:
        return str(path.relative_to(root))
    except Exception:
        return str(path)


def add_issue(
    issues: List[KiCadGateIssue],
    rule_id: str,
    severity: str,
    message: str,
    file: Optional[str] = None,
) -> None:
    issues.append(
        KiCadGateIssue(
            rule_id=rule_id,
            severity=severity,
            message=message,
            file=file,
        )
    )


def validate_required_files(kicad_dir: Path) -> List[KiCadGateIssue]:
    issues: List[KiCadGateIssue] = []

    if not kicad_dir.exists():
        add_issue(
            issues,
            "KICAD.PATH.001",
            "blocker",
            f"KiCad directory does not exist: {kicad_dir}",
        )
        return issues

    for filename in REQUIRED_SUPPORT_FILES:
        path = kicad_dir / filename
        if not path.exists():
            add_issue(
                issues,
                f"KICAD.FS.{filename.upper().replace('.', '_')}",
                "blocker",
                f"Missing required KiCad support artifact: {filename}",
                filename,
            )

    for suffix in REQUIRED_KICAD_FILES:
        path = find_first_file_with_suffix(kicad_dir, suffix)
        if path is None:
            add_issue(
                issues,
                f"KICAD.FS.{suffix.upper().replace('.', '_')}",
                "blocker",
                f"Missing required KiCad project file ending in {suffix}.",
            )

    return issues


def validate_readme(kicad_dir: Path) -> List[KiCadGateIssue]:
    issues: List[KiCadGateIssue] = []
    path = kicad_dir / "README.md"

    if not path.exists():
        return issues

    text = read_text(path).lower()

    if "placeholder" not in text and "not fabrication-ready" not in text:
        add_issue(
            issues,
            "KICAD.README.001",
            "warning",
            "README should explicitly warn that the KiCad package is a starter placeholder and not fabrication-ready.",
            "README.md",
        )

    expected_terms = [
        "erc",
        "drc",
        "footprint",
        "power",
        "connector",
    ]

    for term in expected_terms:
        if term not in text:
            add_issue(
                issues,
                f"KICAD.README.{term.upper()}",
                "warning",
                f"README should mention {term} review before real PCB fabrication.",
                "README.md",
            )

    return issues


def validate_knowledge_context(kicad_dir: Path) -> List[KiCadGateIssue]:
    issues: List[KiCadGateIssue] = []
    path = kicad_dir / "kicad_knowledge_context.md"

    if not path.exists():
        return issues

    text = read_text(path)

    required_phrases = {
        "KICAD.CTX.001": "KICAD / PCB DESIGN KNOWLEDGE CONTEXT",
        "KICAD.CTX.002": "The schematic is the source of truth",
        "KICAD.CTX.003": "Every schematic symbol must have a validated footprint",
        "KICAD.CTX.004": "Run ERC before PCB layout",
        "KICAD.CTX.005": "Run DRC before Gerber",
        "KICAD.CTX.006": "Power traces should be wider than signal traces",
        "KICAD.CTX.007": "Gerber exports must include drill files",
    }

    for rule_id, phrase in required_phrases.items():
        if phrase.lower() not in text.lower():
            add_issue(
                issues,
                rule_id,
                "warning",
                f"KiCad knowledge context is missing expected rule phrase: {phrase}",
                "kicad_knowledge_context.md",
            )

    return issues


def validate_json_artifacts(kicad_dir: Path) -> List[KiCadGateIssue]:
    issues: List[KiCadGateIssue] = []

    json_files = [
        "electronics_architecture.json",
        "power_budget.json",
        "connector_map.json",
    ]

    for filename in json_files:
        path = kicad_dir / filename
        if not path.exists():
            continue

        data, error = load_json(path)

        if error:
            add_issue(
                issues,
                f"KICAD.JSON.{filename.upper().replace('.', '_')}",
                "blocker",
                f"{filename} is not valid JSON: {error}",
                filename,
            )
            continue

        if not isinstance(data, dict):
            add_issue(
                issues,
                f"KICAD.JSON.{filename.upper().replace('.', '_')}.TYPE",
                "warning",
                f"{filename} should contain a JSON object.",
                filename,
            )
            continue

        if not data:
            add_issue(
                issues,
                f"KICAD.JSON.{filename.upper().replace('.', '_')}.EMPTY",
                "warning",
                f"{filename} is empty.",
                filename,
            )

    power_budget_path = kicad_dir / "power_budget.json"
    if power_budget_path.exists():
        power_budget, error = load_json(power_budget_path)

        if isinstance(power_budget, dict):
            expected_power_terms = [
                "battery",
                "logic",
                "voltage",
                "current",
                "notes",
            ]

            power_text = json.dumps(power_budget, default=str).lower()

            for term in expected_power_terms:
                if term not in power_text:
                    add_issue(
                        issues,
                        f"KICAD.POWER.{term.upper()}",
                        "warning",
                        f"Power budget should mention {term}.",
                        "power_budget.json",
                    )

    connector_map_path = kicad_dir / "connector_map.json"
    if connector_map_path.exists():
        connector_map, error = load_json(connector_map_path)

        if isinstance(connector_map, dict):
            if not connector_map:
                add_issue(
                    issues,
                    "KICAD.CONNECTOR.001",
                    "warning",
                    "Connector map is empty. KiCad package should define at least power, debug, sensor, and actuator connectors.",
                    "connector_map.json",
                )

            connector_text = json.dumps(connector_map, default=str).lower()
            expected_connector_terms = [
                "power",
                "debug",
                "sensor",
                "actuator",
            ]

            for term in expected_connector_terms:
                if term not in connector_text:
                    add_issue(
                        issues,
                        f"KICAD.CONNECTOR.{term.upper()}",
                        "warning",
                        f"Connector map should include a {term}-related connector.",
                        "connector_map.json",
                    )

    return issues


def validate_bom(kicad_dir: Path) -> List[KiCadGateIssue]:
    issues: List[KiCadGateIssue] = []
    path = kicad_dir / "bom.csv"

    if not path.exists():
        return issues

    rows, error = load_csv_rows(path)

    if error:
        add_issue(
            issues,
            "KICAD.BOM.001",
            "blocker",
            f"bom.csv could not be read: {error}",
            "bom.csv",
        )
        return issues

    if not rows:
        add_issue(
            issues,
            "KICAD.BOM.002",
            "warning",
            "BOM is empty. Starter package should include at least placeholder controller, regulator, connector, and actuator-driver entries.",
            "bom.csv",
        )
        return issues

    required_columns = [
        "reference",
        "quantity",
        "component",
        "value",
        "footprint",
        "notes",
    ]

    first_row = rows[0]
    for column in required_columns:
        if column not in first_row:
            add_issue(
                issues,
                f"KICAD.BOM.COL.{column.upper()}",
                "warning",
                f"BOM is missing expected column: {column}",
                "bom.csv",
            )

    bom_text = json.dumps(rows, default=str).lower()

    expected_parts = [
        "controller",
        "regulator",
        "connector",
    ]

    for part in expected_parts:
        if part not in bom_text:
            add_issue(
                issues,
                f"KICAD.BOM.PART.{part.upper()}",
                "warning",
                f"BOM should include a {part}-related placeholder component.",
                "bom.csv",
            )

    if "tbd" not in bom_text:
        add_issue(
            issues,
            "KICAD.BOM.003",
            "info",
            "BOM does not contain TBD values. If this is a starter package, TBD placeholders are expected until real components are selected.",
            "bom.csv",
        )

    return issues


def validate_kicad_project_files(kicad_dir: Path) -> List[KiCadGateIssue]:
    issues: List[KiCadGateIssue] = []

    pro_path = find_first_file_with_suffix(kicad_dir, ".kicad_pro")
    sch_path = find_first_file_with_suffix(kicad_dir, ".kicad_sch")
    pcb_path = find_first_file_with_suffix(kicad_dir, ".kicad_pcb")

    if pro_path:
        data, error = load_json(pro_path)

        if error:
            add_issue(
                issues,
                "KICAD.PRO.001",
                "blocker",
                f"KiCad project file is not valid JSON: {error}",
                relative_file(kicad_dir, pro_path),
            )
        elif isinstance(data, dict):
            if "meta" not in data:
                add_issue(
                    issues,
                    "KICAD.PRO.002",
                    "warning",
                    "KiCad project file should contain metadata.",
                    relative_file(kicad_dir, pro_path),
                )

    if sch_path:
        text = read_text(sch_path)
        lower = text.lower()

        if "(kicad_sch" not in lower:
            add_issue(
                issues,
                "KICAD.SCH.001",
                "blocker",
                "Schematic file does not appear to be a KiCad schematic.",
                relative_file(kicad_dir, sch_path),
            )

        if "placeholder" in lower:
            add_issue(
                issues,
                "KICAD.SCH.002",
                "warning",
                "Schematic is still a starter placeholder. It is not ready for ERC, layout, or fabrication.",
                relative_file(kicad_dir, sch_path),
            )

        if "run erc" not in lower and "erc" not in lower:
            add_issue(
                issues,
                "KICAD.SCH.003",
                "info",
                "Schematic title block should remind user to run ERC.",
                relative_file(kicad_dir, sch_path),
            )

    if pcb_path:
        text = read_text(pcb_path)
        lower = text.lower()

        if "(kicad_pcb" not in lower:
            add_issue(
                issues,
                "KICAD.PCB.001",
                "blocker",
                "PCB file does not appear to be a KiCad PCB file.",
                relative_file(kicad_dir, pcb_path),
            )

        if "edge.cuts" not in lower:
            add_issue(
                issues,
                "KICAD.PCB.002",
                "warning",
                "PCB file should define an Edge.Cuts layer for board outline work.",
                relative_file(kicad_dir, pcb_path),
            )

        if "placeholder" in lower:
            add_issue(
                issues,
                "KICAD.PCB.003",
                "warning",
                "PCB is still a starter placeholder. Board outline, zones, footprints, routing, and DRC are not complete.",
                relative_file(kicad_dir, pcb_path),
            )

        if "run drc" not in lower and "drc" not in lower:
            add_issue(
                issues,
                "KICAD.PCB.004",
                "info",
                "PCB title block should remind user to run DRC before manufacturing export.",
                relative_file(kicad_dir, pcb_path),
            )

    return issues


def validate_manufacturing_readiness(kicad_dir: Path) -> List[KiCadGateIssue]:
    issues: List[KiCadGateIssue] = []

    gerber_dirs = [
        path for path in kicad_dir.iterdir()
        if path.is_dir() and "gerber" in path.name.lower()
    ] if kicad_dir.exists() else []

    drill_files = list(kicad_dir.glob("*.drl"))

    if not gerber_dirs:
        add_issue(
            issues,
            "KICAD.MFG.001",
            "info",
            "No Gerber output folder detected. This is expected for a starter package, but required before PCB manufacturing.",
        )

    if not drill_files:
        add_issue(
            issues,
            "KICAD.MFG.002",
            "info",
            "No drill file detected. Drill files are required with Gerber exports before PCB manufacturing.",
        )

    return issues


def validate_kicad_package(root_path: str | Path) -> Dict[str, Any]:
    kicad_dir = resolve_kicad_dir(root_path)

    issues: List[KiCadGateIssue] = []

    issues.extend(validate_required_files(kicad_dir))

    if not kicad_dir.exists():
        return build_report(kicad_dir, issues)

    issues.extend(validate_readme(kicad_dir))
    issues.extend(validate_knowledge_context(kicad_dir))
    issues.extend(validate_json_artifacts(kicad_dir))
    issues.extend(validate_bom(kicad_dir))
    issues.extend(validate_kicad_project_files(kicad_dir))
    issues.extend(validate_manufacturing_readiness(kicad_dir))

    return build_report(kicad_dir, issues)


def build_report(kicad_dir: Path, issues: List[KiCadGateIssue]) -> Dict[str, Any]:
    blocker_count = sum(1 for issue in issues if issue.severity == "blocker")
    warning_count = sum(1 for issue in issues if issue.severity == "warning")
    info_count = sum(1 for issue in issues if issue.severity == "info")

    if blocker_count > 0:
        status = "failed"
    elif warning_count > 0:
        status = "passed_with_warnings"
    else:
        status = "passed"

    return {
        "validator": "kicad_knowledge_gate_validator",
        "kicad_dir": str(kicad_dir),
        "status": status,
        "summary": {
            "blockers": blocker_count,
            "warnings": warning_count,
            "info": info_count,
            "total_issues": len(issues),
        },
        "issues": [asdict(issue) for issue in issues],
    }


def main() -> None:
    if len(sys.argv) < 2:
        print(
            "Usage: python -m backend.app.engineering.kicad_knowledge_gate_validator "
            "<mission_export_dir_or_generated_kicad_dir>"
        )
        raise SystemExit(1)

    result = validate_kicad_package(sys.argv[1])
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()