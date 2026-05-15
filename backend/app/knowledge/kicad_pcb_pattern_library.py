from __future__ import annotations


KICAD_PCB_MODULE = {
    "module": "KiCad_PCB_Design",
    "version": "1.0",
    "domain": "robotics_electronics",
    "software": ["KiCad 8.0"],

    "mission_triggers": [
        "kicad",
        "pcb",
        "schematic",
        "electronics",
        "circuit board",
        "motor driver",
        "sensor board",
        "power distribution",
        "gerber",
        "drill file",
        "footprint",
        "symbol",
        "bom",
        "battery input",
        "voltage regulator",
        "microcontroller",
        "connector",
    ],

    "project_files": {
        ".kicad_pro": "Project configuration and metadata.",
        ".kicad_sch": "Schematic definition and logical netlist source of truth.",
        ".kicad_pcb": "Physical PCB layout, traces, zones, and footprints.",
        ".kicad_sym": "Custom schematic symbol library.",
        ".pretty/": "Custom footprint library folder containing .kicad_mod files.",
        "Gerbers/": "Fabrication output folder.",
        "*.drl": "Drill file for fabricated holes.",
        "*.zip": "Manufacturing archive submitted to PCB vendor.",
    },

    "core_rules": [
        {
            "id": "KICAD.R.001",
            "severity": "blocker",
            "rule": "The schematic is the source of truth. Never fix connectivity only in the PCB editor.",
        },
        {
            "id": "KICAD.R.002",
            "severity": "blocker",
            "rule": "Every schematic symbol must have a validated footprint before PCB layout begins.",
        },
        {
            "id": "KICAD.R.003",
            "severity": "blocker",
            "rule": "Run ERC before PCB layout and resolve all errors.",
        },
        {
            "id": "KICAD.R.004",
            "severity": "blocker",
            "rule": "Run DRC before Gerber/manufacturing export and resolve all errors.",
        },
        {
            "id": "KICAD.R.005",
            "severity": "warning",
            "rule": "Use PWR_FLAG symbols at power input nodes.",
        },
        {
            "id": "KICAD.R.006",
            "severity": "warning",
            "rule": "Standardize power net names globally. Do not mix VCC and 5V for the same rail.",
        },
        {
            "id": "KICAD.R.007",
            "severity": "warning",
            "rule": "Use project-local libraries for custom symbols and footprints.",
        },
        {
            "id": "KICAD.R.008",
            "severity": "warning",
            "rule": "Power traces should be wider than signal traces.",
        },
        {
            "id": "KICAD.R.009",
            "severity": "warning",
            "rule": "Unused pins should have No-Connect flags.",
        },
        {
            "id": "KICAD.R.010",
            "severity": "warning",
            "rule": "Gerber exports must include drill files.",
        },
    ],

    "schematic_workflow": [
        "Create a dedicated KiCad project folder.",
        "Open Schematic Editor.",
        "Add symbols.",
        "Add power symbols.",
        "Wire components.",
        "Assign component values.",
        "Add No-Connect flags for unused pins.",
        "Annotate components.",
        "Run ERC and fix all issues.",
    ],

    "custom_symbol_workflow": [
        "Create a project-local symbol library.",
        "Create the new symbol.",
        "Draw the symbol body.",
        "Add pins using datasheet pin names and pin numbers.",
        "Set correct electrical pin types.",
        "Use VCC at top, GND at bottom, data/control signals on sides.",
        "Place the symbol in schematic.",
        "Run ERC to validate pin types and connectivity.",
    ],

    "custom_footprint_workflow": [
        "Create a project-local footprint library.",
        "Create new footprint.",
        "Set footprint type: Through Hole or SMD.",
        "Draw silkscreen outline using datasheet dimensions.",
        "Set grid to pin pitch.",
        "Place pads with exact numbering.",
        "Use rectangular pad for Pin 1.",
        "Add pin labels on silkscreen.",
        "Add keepout area for external modules.",
        "Verify physical fit in 3D viewer.",
        "Assign footprint to symbol.",
    ],

    "pcb_layout_workflow": [
        "Verify all schematic symbols have footprints.",
        "Import manufacturer design rules before layout.",
        "Update PCB from schematic.",
        "Place components by function.",
        "Define board outline on Edge.Cuts.",
        "Pour GND copper zone.",
        "Route power first, then critical signals, then remaining signals.",
        "Use wider traces for power rails.",
        "Use vias only when needed to change layers.",
        "Refill copper zones after edits.",
        "Run DRC and fix all issues.",
    ],

    "manufacturing_export_workflow": [
        "Run final DRC.",
        "Create dedicated Gerber output folder.",
        "Plot Gerbers: F.Cu, B.Cu, F.Mask, B.Mask, F.Silkscreen, B.Silkscreen, Edge.Cuts.",
        "Generate drill files.",
        "Zip fabrication outputs only.",
        "Upload to PCB manufacturer and verify layer count, dimensions, thickness, and finish.",
    ],

    "robotics_electronics_patterns": [
        {
            "name": "Power Input Protection",
            "use_case": "Battery-powered robot board.",
            "components": ["Battery connector", "Power switch", "Schottky diode", "Fuse or protection stage"],
            "layout_notes": [
                "Place protection near battery input.",
                "Use wider traces for battery and motor current.",
                "Clearly label polarity on silkscreen.",
            ],
        },
        {
            "name": "I2C Sensor Interface",
            "use_case": "IMU, OLED, environmental sensor, or sensor module.",
            "components": ["VCC", "GND", "SDA", "SCL", "4.7K pullups if missing"],
            "layout_notes": [
                "Use explicit SDA and SCL net labels.",
                "Avoid reversing SDA and SCL.",
                "Keep sensor connectors labeled.",
            ],
        },
        {
            "name": "Decoupling Capacitor",
            "use_case": "Noise suppression for IC power pins.",
            "components": ["100nF ceramic capacitor"],
            "layout_notes": [
                "Place capacitor close to IC VCC pin.",
                "Connect between VCC and GND.",
            ],
        },
        {
            "name": "Motor Driver Interface",
            "use_case": "Rover, robot arm, insect robot, or mobile robot actuator board.",
            "components": ["Motor driver IC/module", "Motor connectors", "PWM/control pins", "Power input", "GND"],
            "layout_notes": [
                "Separate high-current motor paths from low-current logic paths.",
                "Use wider traces for motor current.",
                "Label motor polarity and channels.",
            ],
        },
        {
            "name": "Module Breakout Footprint",
            "use_case": "Mounting sensor/display/microcontroller modules.",
            "components": ["Through-hole headers", "Silkscreen outline", "Keepout area"],
            "layout_notes": [
                "Match physical module dimensions.",
                "Mark Pin 1 clearly.",
                "Use keepout region so other components do not overlap the module body.",
            ],
        },
    ],

    "validation_checks": {
        "project_structure": [
            "Project has .kicad_pro.",
            "Project has .kicad_sch.",
            "PCB projects should eventually include .kicad_pcb.",
        ],
        "schematic": [
            "All components are annotated.",
            "All components have values.",
            "All power rails are named consistently.",
            "Power input nodes have PWR_FLAG.",
            "Unused pins have No-Connect flags.",
            "ERC has zero errors before PCB layout.",
        ],
        "symbol_footprint": [
            "Every symbol has an assigned footprint.",
            "Custom symbol pin numbers match datasheet.",
            "Custom footprint pad numbers match symbol pin numbers.",
            "Pin 1 is visibly marked.",
        ],
        "pcb_layout": [
            "Board outline exists on Edge.Cuts.",
            "Ground zone exists and is filled.",
            "Power traces are wider than signal traces.",
            "Silkscreen labels important connectors.",
            "DRC has zero errors before export.",
        ],
        "manufacturing_export": [
            "Gerbers exported.",
            "Drill files exported.",
            "Fabrication zip excludes source project files.",
        ],
    },

    "common_errors": [
        "Using generic symbols for specific modules.",
        "Floating wire endpoints.",
        "Missing PWR_FLAG on power rails.",
        "Incorrect pin electrical type in custom symbols.",
        "Using close-enough footprints without datasheet verification.",
        "Forgetting to refill copper zones.",
        "Silkscreen text too small.",
        "Power traces same width as signal traces.",
        "Reversing SDA and SCL.",
        "Starting PCB layout without manufacturer design rules.",
        "Missing keepout zone on module footprints.",
    ],
}


def mission_matches_kicad(mission_text: str) -> bool:
    lowered = mission_text.lower()
    return any(trigger in lowered for trigger in KICAD_PCB_MODULE["mission_triggers"])


def get_kicad_context(mission_text: str) -> str:
    if not mission_matches_kicad(mission_text):
        return ""

    lines: list[str] = []
    lines.append("KICAD / PCB DESIGN KNOWLEDGE CONTEXT")
    lines.append("Use this context when generating electronics plans, KiCad project plans, schematics, PCB layouts, BOMs, or manufacturing exports.")
    lines.append("")

    lines.append("Core rules:")
    for rule in KICAD_PCB_MODULE["core_rules"]:
        lines.append(f"- [{rule['id']}] {rule['rule']}")

    lines.append("")
    lines.append("KiCad project files:")
    for file_name, role in KICAD_PCB_MODULE["project_files"].items():
        lines.append(f"- {file_name}: {role}")

    lines.append("")
    lines.append("Schematic workflow:")
    for step in KICAD_PCB_MODULE["schematic_workflow"]:
        lines.append(f"- {step}")

    lines.append("")
    lines.append("PCB layout workflow:")
    for step in KICAD_PCB_MODULE["pcb_layout_workflow"]:
        lines.append(f"- {step}")

    lines.append("")
    lines.append("Robotics electronics patterns:")
    for pattern in KICAD_PCB_MODULE["robotics_electronics_patterns"]:
        lines.append(f"- {pattern['name']}: {pattern['use_case']}")
        for note in pattern.get("layout_notes", []):
            lines.append(f"  - {note}")

    lines.append("")
    lines.append("Validation checks:")
    for group_name, checks in KICAD_PCB_MODULE["validation_checks"].items():
        lines.append(f"- {group_name}:")
        for check in checks:
            lines.append(f"  - {check}")

    return "\n".join(lines)