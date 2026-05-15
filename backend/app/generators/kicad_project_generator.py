from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


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
    - morphology_electronics_context.json
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
        morphology_plan: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        project_name = self._safe_project_name(mission_slug)
        morphology_plan = self._as_dict(morphology_plan)

        project_dir = self.output_root / mission_slug / "generated_kicad"
        project_dir.mkdir(parents=True, exist_ok=True)

        morphology_context = self._build_morphology_electronics_context(
            morphology_plan
        )

        enriched_plan = self._enrich_electronics_plan_with_morphology(
            electronics_plan=electronics_plan,
            morphology_context=morphology_context,
        )

        context_source = self._build_context_source(
            mission_text=mission_text,
            electronics_plan=enriched_plan,
            morphology_context=morphology_context,
        )
        kicad_context = self._build_kicad_context(context_source)

        files: Dict[str, str] = {}

        files["README.md"] = self._write_readme(
            project_dir=project_dir,
            project_name=project_name,
            plan=enriched_plan,
            kicad_context=kicad_context,
            morphology_context=morphology_context,
        )

        files["electronics_architecture.json"] = self._write_json(
            project_dir=project_dir,
            filename="electronics_architecture.json",
            data=enriched_plan,
        )

        files["power_budget.json"] = self._write_json(
            project_dir=project_dir,
            filename="power_budget.json",
            data=self._as_dict(enriched_plan.get("power_budget", {})),
        )

        files["connector_map.json"] = self._write_json(
            project_dir=project_dir,
            filename="connector_map.json",
            data=self._as_dict(enriched_plan.get("connector_map", {})),
        )

        files["bom.csv"] = self._write_bom(
            project_dir=project_dir,
            bom=self._as_list(enriched_plan.get("bom", [])),
        )

        if morphology_context:
            files["morphology_electronics_context.json"] = self._write_json(
                project_dir=project_dir,
                filename="morphology_electronics_context.json",
                data=morphology_context,
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
            morphology_context=morphology_context,
        )

        files[f"{project_name}.kicad_pcb"] = self._write_placeholder_pcb(
            project_dir=project_dir,
            project_name=project_name,
            morphology_context=morphology_context,
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

    def _safe_kicad_string(self, value: Any) -> str:
        return str(value or "").replace('"', "'").replace("\n", " ").strip()

    def _as_dict(self, value: Any) -> Dict[str, Any]:
        return value if isinstance(value, dict) else {}

    def _as_list(self, value: Any) -> List[Any]:
        return value if isinstance(value, list) else []

    def _as_bom_list(self, value: Any) -> List[Dict[str, Any]]:
        if not isinstance(value, list):
            return []

        cleaned: List[Dict[str, Any]] = []
        for item in value:
            if isinstance(item, dict):
                cleaned.append(item)
            else:
                cleaned.append({"component": str(item)})
        return cleaned

    def _append_unique(self, target: List[Any], values: List[Any]) -> List[Any]:
        existing = {str(item) for item in target}

        for value in values:
            if value is None:
                continue

            value_text = str(value).strip()
            if not value_text or value_text in existing:
                continue

            target.append(value)
            existing.add(value_text)

        return target

    def _json_safe_copy(self, value: Any) -> Any:
        try:
            return json.loads(json.dumps(value, default=str))
        except Exception:
            return {}

    # ---------------------------------------------------------------------
    # Morphology integration
    # ---------------------------------------------------------------------

    def _build_morphology_electronics_context(
        self,
        morphology_plan: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not morphology_plan:
            return {}

        body_plan = self._as_dict(morphology_plan.get("body_plan", {}))
        electronics_intent = self._as_dict(
            morphology_plan.get("electronics_intent", {})
        )
        ros2_intent = self._as_dict(morphology_plan.get("ros2_intent", {}))

        return {
            "morphology_id": morphology_plan.get("morphology_id", ""),
            "project_family": morphology_plan.get("project_family", ""),
            "display_name": morphology_plan.get("display_name", ""),
            "scale": morphology_plan.get("scale", ""),
            "locomotion_type": morphology_plan.get("locomotion_type", ""),
            "body_segments": self._as_list(body_plan.get("segments", [])),
            "required_features": self._as_list(
                body_plan.get("required_features", [])
            ),
            "avoid_features": self._as_list(body_plan.get("avoid_features", [])),
            "mounting_points": self._as_list(body_plan.get("mounting_points", [])),
            "primary_pcb_location": electronics_intent.get(
                "primary_pcb_location",
                "",
            ),
            "battery_location": electronics_intent.get("battery_location", ""),
            "sensor_connectors": self._as_list(
                electronics_intent.get("sensor_connectors", [])
            ),
            "actuator_connectors": self._as_list(
                electronics_intent.get("actuator_connectors", [])
            ),
            "power_rails": self._as_list(
                electronics_intent.get("power_rails", [])
            ),
            "ros2_frames": self._as_list(
                ros2_intent.get("recommended_frames", [])
            ),
            "ros2_nodes": self._as_list(
                ros2_intent.get("recommended_nodes", [])
            ),
            "ros2_topics": self._as_list(
                ros2_intent.get("recommended_topics", [])
            ),
        }

    def _enrich_electronics_plan_with_morphology(
        self,
        electronics_plan: Dict[str, Any],
        morphology_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        plan = self._json_safe_copy(electronics_plan)
        if not isinstance(plan, dict):
            plan = {}

        if not morphology_context:
            return plan

        plan["morphology_electronics_context"] = morphology_context

        architecture = self._as_dict(plan.get("electronics_architecture", {}))
        architecture["morphology_id"] = morphology_context.get("morphology_id", "")
        architecture["project_family"] = morphology_context.get("project_family", "")
        architecture["body_segments"] = morphology_context.get("body_segments", [])
        architecture["primary_pcb_location"] = morphology_context.get(
            "primary_pcb_location",
            "",
        )
        architecture["battery_location"] = morphology_context.get(
            "battery_location",
            "",
        )
        architecture["morphology_mounting_points"] = morphology_context.get(
            "mounting_points",
            [],
        )
        architecture["morphology_required_features"] = morphology_context.get(
            "required_features",
            [],
        )

        sensor_interfaces = self._as_list(architecture.get("sensor_interfaces", []))
        self._append_unique(
            sensor_interfaces,
            morphology_context.get("sensor_connectors", []),
        )
        architecture["sensor_interfaces"] = sensor_interfaces

        actuator_interfaces = self._as_list(
            architecture.get("actuator_interfaces", [])
        )
        self._append_unique(
            actuator_interfaces,
            morphology_context.get("actuator_connectors", []),
        )
        architecture["actuator_interfaces"] = actuator_interfaces

        architecture["morphology_power_rails"] = morphology_context.get(
            "power_rails",
            [],
        )

        plan["electronics_architecture"] = architecture

        power_budget = self._as_dict(plan.get("power_budget", {}))
        power_budget["morphology_primary_pcb_location"] = morphology_context.get(
            "primary_pcb_location",
            "",
        )
        power_budget["morphology_battery_location"] = morphology_context.get(
            "battery_location",
            "",
        )
        power_budget["morphology_power_rails"] = morphology_context.get(
            "power_rails",
            [],
        )

        notes = self._as_list(power_budget.get("notes", []))
        self._append_unique(
            notes,
            [
                (
                    "Morphology-aware placement: main PCB should be hosted in "
                    f"{morphology_context.get('primary_pcb_location', 'TBD')}."
                ),
                (
                    "Morphology-aware placement: battery should be hosted in "
                    f"{morphology_context.get('battery_location', 'TBD')}."
                ),
                (
                    "Route sensor connectors according to morphology intent: "
                    + ", ".join(
                        str(item)
                        for item in morphology_context.get("sensor_connectors", [])
                    )
                ),
                (
                    "Route actuator connectors according to morphology intent: "
                    + ", ".join(
                        str(item)
                        for item in morphology_context.get("actuator_connectors", [])
                    )
                ),
            ],
        )
        power_budget["notes"] = notes
        plan["power_budget"] = power_budget

        connector_map = self._as_dict(plan.get("connector_map", {}))
        primary_pcb_location = str(
            morphology_context.get("primary_pcb_location", "")
        ).strip()
        battery_location = str(morphology_context.get("battery_location", "")).strip()

        if primary_pcb_location:
            connector_map["MORPH_PCB_LOCATION"] = primary_pcb_location

        if battery_location:
            connector_map["MORPH_BATTERY_LOCATION"] = battery_location

        for index, connector in enumerate(
            morphology_context.get("sensor_connectors", []),
            start=1,
        ):
            connector_map[f"MORPH_SENSOR_{index}"] = connector

        for index, connector in enumerate(
            morphology_context.get("actuator_connectors", []),
            start=1,
        ):
            connector_map[f"MORPH_ACTUATOR_{index}"] = connector

        plan["connector_map"] = connector_map

        bom = self._as_bom_list(plan.get("bom", []))

        for index, connector in enumerate(
            morphology_context.get("sensor_connectors", []),
            start=1,
        ):
            bom.append(
                {
                    "reference": f"MS{index}",
                    "quantity": 1,
                    "component": "Morphology sensor connector",
                    "value": connector,
                    "footprint": "TBD",
                    "notes": (
                        "Sensor connector required by morphology electronics intent."
                    ),
                }
            )

        for index, connector in enumerate(
            morphology_context.get("actuator_connectors", []),
            start=1,
        ):
            bom.append(
                {
                    "reference": f"MA{index}",
                    "quantity": 1,
                    "component": "Morphology actuator connector",
                    "value": connector,
                    "footprint": "TBD",
                    "notes": (
                        "Actuator connector required by morphology electronics intent."
                    ),
                }
            )

        if primary_pcb_location:
            bom.append(
                {
                    "reference": "MP1",
                    "quantity": 1,
                    "component": "Main PCB placement zone",
                    "value": primary_pcb_location,
                    "footprint": "Mechanical/placement TBD",
                    "notes": "Main PCB location from morphology_plan electronics_intent.",
                }
            )

        if battery_location:
            bom.append(
                {
                    "reference": "MB1",
                    "quantity": 1,
                    "component": "Battery placement zone",
                    "value": battery_location,
                    "footprint": "Mechanical/placement TBD",
                    "notes": "Battery location from morphology_plan electronics_intent.",
                }
            )

        plan["bom"] = bom

        return plan

    # ---------------------------------------------------------------------
    # Context generation
    # ---------------------------------------------------------------------

    def _build_context_source(
        self,
        mission_text: str,
        electronics_plan: Dict[str, Any],
        morphology_context: Dict[str, Any],
    ) -> str:
        payload = {
            "mission_text": mission_text.strip(),
            "electronics_plan": electronics_plan,
            "morphology_electronics_context": morphology_context,
        }

        return json.dumps(payload, indent=2, sort_keys=True)

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
        data: Any,
    ) -> str:
        path = project_dir / filename
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
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
        morphology_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        path = project_dir / "README.md"

        morphology_context = morphology_context or {}

        knowledge_context_line = (
            "- kicad_knowledge_context.md"
            if kicad_context
            else "- kicad_knowledge_context.md was not generated because no KiCad trigger/context was detected."
        )

        morphology_context_line = (
            "- morphology_electronics_context.json"
            if morphology_context
            else "- morphology_electronics_context.json was not generated because no morphology_plan was provided."
        )

        morphology_section = "No morphology electronics context was provided."

        if morphology_context:
            morphology_section = f"""- Morphology ID: {morphology_context.get("morphology_id", "unknown")}
- Project Family: {morphology_context.get("project_family", "unknown")}
- Main PCB Location: {morphology_context.get("primary_pcb_location", "TBD")}
- Battery Location: {morphology_context.get("battery_location", "TBD")}
- Body Segments: {", ".join(str(item) for item in morphology_context.get("body_segments", []))}
- Sensor Connectors: {", ".join(str(item) for item in morphology_context.get("sensor_connectors", []))}
- Actuator Connectors: {", ".join(str(item) for item in morphology_context.get("actuator_connectors", []))}
- Power Rails: {", ".join(str(item) for item in morphology_context.get("power_rails", []))}"""

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
{morphology_context_line}
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

## Morphology Electronics Context

{morphology_section}

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

    def _write_placeholder_schematic(
        self,
        project_dir: Path,
        project_name: str,
        morphology_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        path = project_dir / f"{project_name}.kicad_sch"
        morphology_context = morphology_context or {}

        morphology_id = self._safe_kicad_string(
            morphology_context.get("morphology_id", "none")
        )
        pcb_location = self._safe_kicad_string(
            morphology_context.get("primary_pcb_location", "TBD")
        )
        battery_location = self._safe_kicad_string(
            morphology_context.get("battery_location", "TBD")
        )

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
    (comment 4 "Morphology ID: {morphology_id}; PCB: {pcb_location}; Battery: {battery_location}.")
  )
)
"""
        path.write_text(content, encoding="utf-8")
        return str(path)

    def _write_placeholder_pcb(
        self,
        project_dir: Path,
        project_name: str,
        morphology_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        path = project_dir / f"{project_name}.kicad_pcb"
        morphology_context = morphology_context or {}

        morphology_id = self._safe_kicad_string(
            morphology_context.get("morphology_id", "none")
        )
        pcb_location = self._safe_kicad_string(
            morphology_context.get("primary_pcb_location", "TBD")
        )
        battery_location = self._safe_kicad_string(
            morphology_context.get("battery_location", "TBD")
        )

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
    (36 "B.SilkS" user "F.Silkscreen")
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
    (comment 4 "Morphology ID: {morphology_id}; PCB: {pcb_location}; Battery: {battery_location}.")
  )
)
"""
        path.write_text(content, encoding="utf-8")
        return str(path)