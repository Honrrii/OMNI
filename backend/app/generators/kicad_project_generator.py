from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any, Dict, List


try:
    from backend.app.knowledge.kicad_pcb_pattern_library import get_kicad_context
except Exception:
    try:
        from knowledge.kicad_pcb_pattern_library import get_kicad_context
    except Exception:
        get_kicad_context = None


class KiCadProjectGenerator:
    """
    Generates a starter KiCad electronics package for an OMNI mission.

    This generator currently creates:
    - README.md
    - electronics_architecture.json
    - power_budget.json
    - connector_map.json
    - bom.csv
    - kicad_knowledge_context.md
    - <project>.kicad_pro
    - <project>.kicad_sch
    - <project>.kicad_pcb

    The KiCad schematic and PCB files are intentionally starter placeholders.
    They are meant to provide a project shell and engineering context, not a
    fabrication-ready board.
    """

    def __init__(self, output_root: str | Path):
        self.output_root = Path(output_root)

    def generate(
        self,
        mission_slug: str,
        electronics_plan: Dict[str, Any],
        mission_text: str = "",
    ) -> Dict[str, str]:
        project_name = self._safe_project_name(mission_slug)

        project_dir = self.output_root / mission_slug / "generated_kicad"
        project_dir.mkdir(parents=True, exist_ok=True)

        context_source = self._build_context_source(
            mission_text=mission_text,
            electronics_plan=electronics_plan,
        )
        kicad_context = self._build_kicad_context(context_source)

        files: Dict[str, str] = {}

        files["README.md"] = self._write_readme(
            project_dir=project_dir,
            project_name=project_name,
            plan=electronics_plan,
            kicad_context=kicad_context,
        )

        files["electronics_architecture.json"] = self._write_json(
            project_dir=project_dir,
            filename="electronics_architecture.json",
            data=electronics_plan,
        )

        files["power_budget.json"] = self._write_json(
            project_dir=project_dir,
            filename="power_budget.json",
            data=self._as_dict(electronics_plan.get("power_budget", {})),
        )

        files["connector_map.json"] = self._write_json(
            project_dir=project_dir,
            filename="connector_map.json",
            data=self._as_dict(electronics_plan.get("connector_map", {})),
        )

        files["bom.csv"] = self._write_bom(
            project_dir=project_dir,
            bom=self._as_list(electronics_plan.get("bom", [])),
        )

        if kicad_context:
            files["kicad_knowledge_context.md"] = self._write_text(
                project_dir=project_dir,
                filename="kicad_knowledge_context.md",
                content=kicad_context,
            )

        files[f"{project_name}.kicad_pro"] = self._write_kicad_project(
            project_dir=project_dir,
            project_name=project_name,
        )

        files[f"{project_name}.kicad_sch"] = self._write_placeholder_schematic(
            project_dir=project_dir,
            project_name=project_name,
        )

        files[f"{project_name}.kicad_pcb"] = self._write_placeholder_pcb(
            project_dir=project_dir,
            project_name=project_name,
        )

        return files

    # ---------------------------------------------------------------------
    # General helpers
    # ---------------------------------------------------------------------

    def _safe_project_name(self, mission_slug: str) -> str:
        name = mission_slug.replace("-", "_").strip()
        name = re.sub(r"[^A-Za-z0-9_]+", "_", name)
        name = re.sub(r"_+", "_", name).strip("_")

        if not name:
            return "omni_kicad_project"

        if name[0].isdigit():
            name = f"omni_{name}"

        return name

    def _as_dict(self, value: Any) -> Dict[str, Any]:
        return value if isinstance(value, dict) else {}

    def _as_list(self, value: Any) -> List[Dict[str, Any]]:
        if not isinstance(value, list):
            return []

        cleaned: List[Dict[str, Any]] = []
        for item in value:
            if isinstance(item, dict):
                cleaned.append(item)
            else:
                cleaned.append({"component": str(item)})
        return cleaned

    def _build_context_source(
        self,
        mission_text: str,
        electronics_plan: Dict[str, Any],
    ) -> str:
        plan_text = json.dumps(electronics_plan, indent=2, sort_keys=True)

        if mission_text.strip():
            return f"{mission_text.strip()}\n\n{plan_text}"

        return plan_text

    def _build_kicad_context(self, context_source: str) -> str:
        if get_kicad_context is None:
            return ""

        try:
            return get_kicad_context(context_source).strip()
        except Exception as exc:
            return (
                "KICAD / PCB DESIGN KNOWLEDGE CONTEXT\n\n"
                "OMNI attempted to load the KiCad PCB knowledge context, "
                f"but context generation failed.\n\nError: {exc}"
            )

    def _write_text(self, project_dir: Path, filename: str, content: str) -> str:
        path = project_dir / filename
        path.write_text(content.rstrip() + "\n", encoding="utf-8")
        return str(path)

    def _write_json(
        self,
        project_dir: Path,
        filename: str,
        data: Dict[str, Any],
    ) -> str:
        path = project_dir / filename
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return str(path)

    # ---------------------------------------------------------------------
    # README / documentation
    # ---------------------------------------------------------------------

    def _write_readme(
        self,
        project_dir: Path,
        project_name: str,
        plan: Dict[str, Any],
        kicad_context: str = "",
    ) -> str:
        path = project_dir / "README.md"

        knowledge_context_line = (
            "- kicad_knowledge_context.md"
            if kicad_context
            else "- kicad_knowledge_context.md was not generated because no KiCad trigger/context was detected."
        )

        text = f"""# KiCad Electronics Package — {project_name}

This folder was generated by OMNI.

## Purpose

Generate an initial electronics design package for the mission.

This package is intended to help start a robotics electronics workflow. It is not fabrication-ready by default.

## Included Artifacts

- electronics_architecture.json
- power_budget.json
- connector_map.json
- bom.csv
{knowledge_context_line}
- {project_name}.kicad_pro
- {project_name}.kicad_sch
- {project_name}.kicad_pcb

## Current Status

The KiCad schematic and PCB are starter placeholders.

Before fabrication, review and complete:

- schematic symbols
- footprints
- power rails
- connectors
- battery input protection
- voltage regulation
- motor driver current paths
- sensor interfaces
- ERC results
- DRC results
- Gerber and drill exports

## Electronics Summary

{plan.get("summary", "No summary provided.")}

## OMNI KiCad Rules To Remember

- The schematic is the source of truth.
- Every symbol needs a validated footprint.
- Run ERC before PCB layout.
- Run DRC before manufacturing export.
- Use PWR_FLAG symbols at power input nodes.
- Keep power traces wider than signal traces.
- Label connectors clearly on silkscreen.
- Include drill files with Gerber exports.
- Review all electrical choices before connecting real hardware.
"""
        path.write_text(text, encoding="utf-8")
        return str(path)

    # ---------------------------------------------------------------------
    # BOM generation
    # ---------------------------------------------------------------------

    def _write_bom(self, project_dir: Path, bom: List[Dict[str, Any]]) -> str:
        path = project_dir / "bom.csv"

        fieldnames = [
            "reference",
            "quantity",
            "component",
            "value",
            "footprint",
            "notes",
        ]

        with path.open("w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for row in bom:
                writer.writerow(
                    {
                        "reference": row.get("reference", ""),
                        "quantity": row.get("quantity", ""),
                        "component": row.get("component", ""),
                        "value": row.get("value", ""),
                        "footprint": row.get("footprint", ""),
                        "notes": row.get("notes", ""),
                    }
                )

        return str(path)

    # ---------------------------------------------------------------------
    # KiCad project shell
    # ---------------------------------------------------------------------

    def _write_kicad_project(self, project_dir: Path, project_name: str) -> str:
        path = project_dir / f"{project_name}.kicad_pro"

        content = {
            "board": {
                "design_settings": {
                    "defaults": {},
                    "rules": {},
                }
            },
            "boards": [],
            "cvpcb": {},
            "erc": {},
            "libraries": {},
            "meta": {
                "filename": f"{project_name}.kicad_pro",
                "version": 1,
            },
            "net_settings": {},
            "pcbnew": {},
            "schematic": {},
            "sheets": [],
            "text_variables": {},
        }

        path.write_text(json.dumps(content, indent=2), encoding="utf-8")
        return str(path)

    def _write_placeholder_schematic(self, project_dir: Path, project_name: str) -> str:
        path = project_dir / f"{project_name}.kicad_sch"

        content = f"""(kicad_sch
  (version 20230121)
  (generator "OMNI")
  (paper "A4")
  (title_block
    (title "{project_name}")
    (company "OMNI Generated Electronics Package")
    (comment 1 "Starter schematic placeholder. Review and complete before use.")
    (comment 2 "Run ERC before PCB layout.")
    (comment 3 "Every symbol must have a validated footprint.")
  )
)
"""
        path.write_text(content, encoding="utf-8")
        return str(path)

    def _write_placeholder_pcb(self, project_dir: Path, project_name: str) -> str:
        path = project_dir / f"{project_name}.kicad_pcb"

        content = f"""(kicad_pcb
  (version 20240108)
  (generator "OMNI")
  (general)
  (paper "A4")
  (layers
    (0 "F.Cu" signal)
    (31 "B.Cu" signal)
    (32 "B.Adhes" user "B.Adhesive")
    (33 "F.Adhes" user "F.Adhesive")
    (34 "B.Paste" user)
    (35 "F.Paste" user)
    (36 "B.SilkS" user "B.Silkscreen")
    (37 "F.SilkS" user "F.Silkscreen")
    (38 "B.Mask" user)
    (39 "F.Mask" user)
    (44 "Edge.Cuts" user)
  )
  (title_block
    (title "{project_name}")
    (company "OMNI Generated Electronics Package")
    (comment 1 "Starter PCB placeholder. Review and complete before use.")
    (comment 2 "Run DRC before Gerber export.")
    (comment 3 "Define Edge.Cuts, GND zone, trace widths, connector labels, and drill outputs.")
  )
)
"""
        path.write_text(content, encoding="utf-8")
        return str(path)