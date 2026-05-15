from __future__ import annotations

AIRCRAFT_AEROSPACE_CAD_MODULE = {
    "module": "Aircraft_Aerospace_CAD",
    "version": "1.0",
    "domain": "aerospace_cad",
    "software": ["Autodesk Fusion 360"],
    "workspaces": ["Form / T-Spline", "Surface", "Solid"],

    "mission_triggers": [
        "aircraft",
        "aerospace",
        "uav",
        "fixed-wing",
        "fuselage",
        "wing",
        "airfoil",
        "control surface",
        "nacelle",
        "empennage",
        "drone airplane",
        "rc plane",
    ],

    "lod_levels": {
        "LoD-1": {
            "goal": "visual_concept",
            "include": ["outer mold line", "major silhouette surfaces", "basic panel splits"],
            "exclude": ["internal frames", "mechanical linkages", "wire routing"],
        },
        "LoD-2": {
            "goal": "rc_uav_functional_prototype",
            "include": ["motor mounts", "control surface geometry", "access hatches"],
            "exclude": ["fine aesthetic panels", "liveries", "insignias"],
        },
        "LoD-3": {
            "goal": "cfd_aerodynamic_analysis",
            "include": ["watertight surfaces", "airfoil coordinates", "clean trailing edges"],
            "exclude": ["non-aerodynamic cosmetic features"],
        },
        "LoD-4": {
            "goal": "manufacturing_or_3d_print",
            "include": ["wall thickness", "draft angles", "support clearances", "toleranced mounting holes"],
            "exclude": ["decorative splits with no structural role"],
        },
        "LoD-5": {
            "goal": "full_engineering_assembly",
            "include": ["internal structures", "bulkheads", "spar locations", "CG-aware mass distribution"],
            "exclude": [],
        },
    },

    "hard_rules": [
        {
            "id": "AC.R.001",
            "name": "LoD must be declared before CAD generation",
            "rule": "OMNI must classify the project level of detail before creating aircraft geometry.",
            "severity": "blocker",
        },
        {
            "id": "AC.R.002",
            "name": "Canvas calibration is mandatory",
            "rule": "Reference images must be calibrated to real-world dimensions before being used for CAD modeling.",
            "severity": "blocker",
        },
        {
            "id": "AC.R.003",
            "name": "Use orthographic references",
            "rule": "Use orthographic engineering drawings, not perspective photos, for dimensional aircraft modeling.",
            "severity": "warning",
        },
        {
            "id": "AC.R.004",
            "name": "Model one side and mirror symmetric aircraft",
            "rule": "For bilaterally symmetric aircraft geometry, model one side and mirror the other.",
            "severity": "warning",
        },
        {
            "id": "AC.R.005",
            "name": "Complex lofts require guide rails",
            "rule": "Wing, fuselage, nacelle, and fairing lofts should use guide rails to prevent twisted geometry.",
            "severity": "blocker",
        },
        {
            "id": "AC.R.006",
            "name": "Stitch surfaces before export",
            "rule": "Surface patches must be stitched into watertight bodies before CFD, printing, or simulation export.",
            "severity": "blocker",
        },
        {
            "id": "AC.R.007",
            "name": "Use correct component context",
            "rule": "Aircraft bodies should be created inside named components, not loose root-level bodies.",
            "severity": "warning",
        },
        {
            "id": "AC.R.008",
            "name": "Check tangency at aerodynamic junctions",
            "rule": "Wing-fuselage, nacelle-pylon, and tail junctions should be checked for smooth continuity.",
            "severity": "warning",
        },
    ],

    "reusable_patterns": {
        "aircraft_assembly_tree": [
            "AIRCRAFT",
            "FUSELAGE/Nose_Section",
            "FUSELAGE/Forward_Fuselage",
            "FUSELAGE/Main_Fuselage",
            "FUSELAGE/Tail_Cone",
            "WING_PORT/MainSurface",
            "WING_PORT/Aileron",
            "WING_PORT/Flap",
            "WING_STBD/MainSurface",
            "EMPENNAGE/Horizontal_Stabilizer",
            "EMPENNAGE/Vertical_Stabilizer",
            "EMPENNAGE/Elevator",
            "EMPENNAGE/Rudder",
            "PROPULSION/Nacelle_or_Motor_Mount",
        ],

        "fuselage_t_spline_workflow": [
            "Create bounding envelope",
            "Create primary fuselage volume",
            "Adjust cross-section loops at nose, cockpit, cabin, and tail",
            "Verify side, top, and front silhouettes",
            "Apply symmetry",
            "Inspect surface continuity",
            "Convert/stitch into clean body",
        ],

        "wing_loft_workflow": [
            "Define root chord",
            "Define tip chord",
            "Set sweep angle",
            "Set dihedral angle",
            "Create root airfoil profile",
            "Create tip airfoil profile",
            "Loft with leading-edge and trailing-edge guide rails",
            "Split control surfaces after full wing body is complete",
        ],

        "control_surface_workflow": [
            "Complete full wing or tail surface first",
            "Sketch hinge and boundary lines",
            "Use split-body workflow",
            "Move each surface into its own named component",
            "Validate naming and separation",
        ],
    },

    "validation_gates": {
        "AC.G.001_project_initialization": [
            "LoD declared",
            "Aircraft type declared",
            "Reference source declared",
            "Primary dimensions available or explicitly estimated",
            "Required aircraft surfaces identified",
        ],
        "AC.G.002_canvas_and_reference": [
            "Units are millimeters",
            "Reference geometry is orthographic when precision is required",
            "Side/top/front views are aligned if using blueprints",
            "Reference scale is known or marked as conceptual",
        ],
        "AC.G.003_surface_integrity": [
            "No obvious open surface gaps",
            "Wing/fuselage junctions are resolved",
            "Major aerodynamic surfaces are continuous",
            "Lofted wings use guide rails",
        ],
        "AC.G.004_assembly_completeness": [
            "Fuselage exists",
            "Main wing exists",
            "Empennage exists when applicable",
            "Control surfaces are represented or intentionally omitted",
            "Propulsion mount or nacelle exists when applicable",
            "No major bodies remain unnamed",
        ],
    },

    "failure_modes": [
        {
            "id": "AC.F.001",
            "name": "Twisted loft surface",
            "symptom": "Wing or fairing surface twists unexpectedly.",
            "likely_cause": "Missing guide rails or bad loft profile alignment.",
            "fix": "Add leading-edge and trailing-edge guide rails.",
        },
        {
            "id": "AC.F.002",
            "name": "Asymmetric fuselage",
            "symptom": "Left and right fuselage sides do not match.",
            "likely_cause": "Symmetry was not established before editing.",
            "fix": "Rebuild using symmetry or mirror workflow.",
        },
        {
            "id": "AC.F.003",
            "name": "Open edges prevent stitching",
            "symptom": "Surface cannot become a clean solid.",
            "likely_cause": "Gaps between patches.",
            "fix": "Patch, bridge, or rebuild surface boundaries.",
        },
        {
            "id": "AC.F.004",
            "name": "Lumpy surface",
            "symptom": "Organic aircraft surfaces have waves or dents.",
            "likely_cause": "Too many T-Spline control points.",
            "fix": "Reduce control points and rebuild cleaner topology.",
        },
    ],
}


def mission_matches_aircraft_cad(mission_text: str) -> bool:
    lowered = mission_text.lower()
    return any(trigger in lowered for trigger in AIRCRAFT_AEROSPACE_CAD_MODULE["mission_triggers"])


def get_aircraft_cad_context(mission_text: str) -> str:
    if not mission_matches_aircraft_cad(mission_text):
        return ""

    rules = AIRCRAFT_AEROSPACE_CAD_MODULE["hard_rules"]
    patterns = AIRCRAFT_AEROSPACE_CAD_MODULE["reusable_patterns"]
    gates = AIRCRAFT_AEROSPACE_CAD_MODULE["validation_gates"]

    lines: list[str] = []
    lines.append("AIRCRAFT / AEROSPACE CAD KNOWLEDGE CONTEXT")
    lines.append("Use this context when generating Fusion 360, CAD morphology, or aerospace-style vehicle geometry.")
    lines.append("")
    lines.append("Hard rules:")
    for rule in rules:
        lines.append(f"- [{rule['id']}] {rule['name']}: {rule['rule']}")

    lines.append("")
    lines.append("Reusable aircraft assembly tree:")
    for item in patterns["aircraft_assembly_tree"]:
        lines.append(f"- {item}")

    lines.append("")
    lines.append("Wing loft workflow:")
    for step in patterns["wing_loft_workflow"]:
        lines.append(f"- {step}")

    lines.append("")
    lines.append("Validation gates:")
    for gate_name, checks in gates.items():
        lines.append(f"- {gate_name}:")
        for check in checks:
            lines.append(f"  - {check}")

    return "\n".join(lines)