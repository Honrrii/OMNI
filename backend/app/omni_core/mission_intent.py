"""
OMNI Phase 12A — Deterministic structured mission intent compiler.

Extracts machine-readable intent fields from free-form mission text.
No LLM calls. No network calls. No file I/O.

Used by:
  - agents/supervisor.py (artifacts["mission_intent"])
  - tests/test_mission_intent.py

Platform resolution delegates to backend.app.platform_intent to stay
consistent with the graph builder and design evaluator.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set

from backend.app.platform_intent import resolve_platform_slug


# ---------------------------------------------------------------------------
# Keyword tables
# ---------------------------------------------------------------------------

# mobility_type signals: keyword → label stored in mobility_requirements
_MOBILITY_KEYWORDS: Dict[str, str] = {
    "tracked":   "tracked locomotion",
    "wheeled":   "wheeled locomotion",
    "legged":    "legged locomotion",
    "walking":   "legged locomotion",
    "aerial":    "aerial locomotion",
    "flying":    "aerial locomotion",
    "hover":     "hovering",
    "underwater": "underwater propulsion",
    "swimming":  "underwater propulsion",
    "rolling":   "wheeled locomotion",
    "magnetic":  "magnetic adhesion",
    "crawling":  "tracked/crawling locomotion",
    "crawler":   "tracked/crawling locomotion",
}

# sensing signals: keyword → label stored in sensing_requirements
_SENSING_KEYWORDS: Dict[str, str] = {
    "camera":    "camera",
    "imu":       "IMU",
    "lidar":     "LiDAR",
    "gps":       "GPS",
    "ultrasonic": "ultrasonic sensor",
    "infrared":  "infrared sensor",
    "sonar":     "sonar",
    "depth sensor": "depth sensor",
    "encoder":   "encoder",
    "compass":   "compass/magnetometer",
    "gyro":      "gyroscope",
    "accelerometer": "accelerometer",
    "thermal":   "thermal imaging",
    "radar":     "radar",
    "microphone": "microphone",
    "pressure sensor": "pressure sensor",
}

# required output signals: keyword → label stored in required_outputs
_OUTPUT_KEYWORDS: Dict[str, str] = {
    "ros2":        "ROS2 package",
    "ros 2":       "ROS2 package",
    "cad":         "CAD model",
    "fusion":      "Fusion 360 model",
    "kicad":       "KiCAD schematic",
    "urdf":        "URDF/Xacro robot description",
    "xacro":       "URDF/Xacro robot description",
    "simulation":  "simulation environment",
    "gazebo":      "Gazebo simulation",
    "rviz":        "RViz visualization",
    "validation":  "validation checklist",
    "export":      "export artifacts",
    "blueprint":   "engineering blueprint",
    "nav2":        "Nav2 navigation stack",
    "launch file": "ROS2 launch file",
    "package.xml": "ROS2 package.xml",
    "pcb":         "PCB design",
    "wiring":      "wiring diagram",
    "bom":         "bill of materials",
}

# constraint signals: keyword → label stored in constraints
_CONSTRAINT_KEYWORDS: Dict[str, str] = {
    "battery":    "battery / power source",
    "power":      "power budget",
    "weight":     "weight limit",
    "payload":    "payload capacity",
    "size":       "size constraint",
    "budget":     "cost budget",
    "waterproof": "waterproofing requirement",
    "temperature": "temperature range",
    "environment": "operating environment",
    "indoor":     "indoor-only operation",
    "outdoor":    "outdoor operation",
    "range":      "operating range",
    "speed":      "speed requirement",
    "runtime":    "runtime / endurance",
    "endurance":  "runtime / endurance",
    "clearance":  "mechanical clearance",
}

# operating environment signals
_ENV_KEYWORDS: Dict[str, str] = {
    "indoor":      "indoor",
    "outdoor":     "outdoor",
    "underwater":  "underwater",
    "aerial":      "aerial",
    "underground": "underground",
    "warehouse":   "warehouse / industrial floor",
    "factory":     "factory floor",
    "lab":         "laboratory",
    "terrain":     "outdoor terrain",
    "metal surface": "metal surface / ferromagnetic",
    "steel":       "metal surface / ferromagnetic",
    "floor":       "floor surface",
    "pipe":        "pipe / confined space",
    "confined":    "confined space",
    "marine":      "marine environment",
    "ocean":       "ocean / open water",
}

# domain signals: keyword → domain name
_DOMAIN_KEYWORDS: Dict[str, str] = {
    "ros2":           "ROS2",
    "ros 2":          "ROS2",
    "robotics":       "robotics",
    "robot":          "robotics",
    "rover":          "robotics",
    "drone":          "drone / UAV",
    "uav":            "drone / UAV",
    "cad":            "CAD",
    "fusion":         "CAD",
    "3d print":       "3D printing",
    "pcb":            "electronics",
    "kicad":          "electronics",
    "embedded":       "embedded systems",
    "raspberry pi":   "embedded systems",
    "arduino":        "embedded systems",
    "motor driver":   "embedded systems",
    "computer vision": "computer vision",
    "camera":         "computer vision",
    "simulation":     "simulation",
    "gazebo":         "simulation",
    "nav2":           "navigation",
    "navigation":     "navigation",
    "autonomy":       "autonomous systems",
    "autonomous":     "autonomous systems",
    "inspection":     "inspection / NDT",
    "ndt":            "inspection / NDT",
}

# mission_type signals: priority-ordered (first match wins)
_MISSION_TYPE_PATTERNS: List[tuple[str, str]] = [
    ("inspection",      "inspection"),
    ("survey",          "survey"),
    ("navigation",      "navigation"),
    ("delivery",        "delivery"),
    ("manipulation",    "manipulation"),
    ("pick and place",  "pick-and-place"),
    ("search",          "search"),
    ("rescue",          "rescue"),
    ("mapping",         "mapping"),
    ("maps",            "mapping"),
    ("exploration",     "exploration"),
    ("monitoring",      "monitoring"),
    ("patrol",          "patrol"),
    ("transport",       "transport"),
    ("assembly",        "assembly"),
]

# success criteria signals
_SUCCESS_KEYWORDS: Dict[str, str] = {
    "detect":      "detection capability",
    "inspect":     "inspection coverage",
    "navigate":    "autonomous navigation",
    "map":         "map generation",
    "scan":        "scanning coverage",
    "identify":    "object identification",
    "avoid":       "obstacle avoidance",
    "deliver":     "delivery success rate",
    "survive":     "environmental survival",
    "endure":      "endurance target",
    "complete":    "mission completion",
    "return":      "return-to-home",
}

# safety_mode signals
_SAFETY_KEYWORDS: Set[str] = {
    "metal", "magnetic", "high voltage", "explosive", "chemical",
    "corrosive", "underwater", "aerial", "nuclear", "hazardous",
    "confined", "pipe", "remote", "unmanned",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _lower(text: Any) -> str:
    return (text or "").lower()


def _extract_labels(text_lower: str, keyword_map: Dict[str, str]) -> List[str]:
    """Return unique ordered labels for all keywords found in text_lower."""
    seen: Set[str] = set()
    results: List[str] = []
    for kw in sorted(keyword_map, key=len, reverse=True):
        if kw in text_lower:
            label = keyword_map[kw]
            if label not in seen:
                seen.add(label)
                results.append(label)
    return results


def _infer_mission_type(text_lower: str) -> str:
    for kw, mtype in _MISSION_TYPE_PATTERNS:
        if kw in text_lower:
            return mtype
    return "general engineering"


def _infer_safety_mode(text_lower: str) -> str:
    for kw in _SAFETY_KEYWORDS:
        if kw in text_lower:
            return "elevated"
    return "standard"


def _build_open_questions(
    mission_text: str,
    platform_intent: Optional[str],
    sensing: List[str],
    mobility: List[str],
    constraints: List[str],
) -> List[str]:
    questions: List[str] = []
    text_lower = _lower(mission_text)

    if not platform_intent:
        questions.append("What platform type or vehicle class should this mission target?")

    if not sensing:
        questions.append("What sensing modalities are required (camera, IMU, LiDAR, GPS, etc.)?")

    if not mobility:
        questions.append("What locomotion or mobility approach is required?")

    # Vague text heuristic: very short missions are likely underspecified
    word_count = len(mission_text.split())
    if word_count < 10:
        questions.append("The mission description is very short — please provide more detail about objectives, environment, and constraints.")

    # Check for missing performance targets
    perf_words = ("speed", "range", "endurance", "runtime", "payload", "weight", "size")
    if not any(w in text_lower for w in perf_words):
        questions.append("What are the key performance requirements (speed, range, payload, endurance, size)?")

    # Power / energy
    if not any(w in text_lower for w in ("battery", "power", "voltage", "watt", "amp", "energy")):
        questions.append("What is the power source and energy budget?")

    return questions


# ---------------------------------------------------------------------------
# Augmentation strippers
# ---------------------------------------------------------------------------

# Markers inserted by main.py / knowledge_context_builder when a mission is
# sent to the Agent Council.  Everything from any of these markers onward is
# retrieved context, not the user's mission, and must not pollute extraction.
_AUGMENTATION_MARKERS: List[str] = [
    "OMNI LOCAL KNOWLEDGE CONTEXT",
    "Relevant retrieved knowledge excerpts:",
    "Instruction to OMNI Agent Council:",
    # guard against future variants
    "[Knowledge Hit ",
    "Real ROS2 package knowledge context",
]


def clean_mission_text_for_intent(text: str) -> str:
    """
    Return only the user-authored portion of a (possibly augmented) mission.

    Strips everything from the first known augmentation marker onward so that
    compile_mission_intent() never extracts sensors, outputs, or domains from
    retrieved knowledge excerpts or council instructions.
    """
    if not isinstance(text, str):
        return ""
    for marker in _AUGMENTATION_MARKERS:
        idx = text.find(marker)
        if idx != -1:
            text = text[:idx]
    return text.strip()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compile_mission_intent(mission_text: str) -> Dict[str, Any]:
    """
    Compile a structured intent summary from free-form mission text.

    Deterministic. No LLM. No network. No file I/O.

    Returns:
      raw_mission, mission_type, platform_intent, detected_domains,
      operating_environment, mobility_requirements, sensing_requirements,
      required_outputs, success_criteria, constraints, assumptions,
      open_questions, safety_mode.
    """
    if not isinstance(mission_text, str):
        mission_text = ""

    clean_text = clean_mission_text_for_intent(mission_text)
    text_lower = _lower(clean_text)

    platform_intent = resolve_platform_slug(clean_text)
    mission_type = _infer_mission_type(text_lower)
    detected_domains = _extract_labels(text_lower, _DOMAIN_KEYWORDS)
    operating_environment = _extract_labels(text_lower, _ENV_KEYWORDS)
    mobility_requirements = _extract_labels(text_lower, _MOBILITY_KEYWORDS)
    sensing_requirements = _extract_labels(text_lower, _SENSING_KEYWORDS)
    required_outputs = _extract_labels(text_lower, _OUTPUT_KEYWORDS)
    success_criteria = _extract_labels(text_lower, _SUCCESS_KEYWORDS)
    constraints = _extract_labels(text_lower, _CONSTRAINT_KEYWORDS)
    safety_mode = _infer_safety_mode(text_lower)

    assumptions: List[str] = [
        "This is a concept-stage interpretation. No hardware specs are validated.",
        "Unknown measurements must be confirmed before physical implementation.",
    ]

    open_questions = _build_open_questions(
        clean_text, platform_intent, sensing_requirements, mobility_requirements, constraints
    )

    return {
        "raw_mission":           clean_text,
        "mission_type":          mission_type,
        "platform_intent":       platform_intent,
        "detected_domains":      detected_domains,
        "operating_environment": operating_environment,
        "mobility_requirements": mobility_requirements,
        "sensing_requirements":  sensing_requirements,
        "required_outputs":      required_outputs,
        "success_criteria":      success_criteria,
        "constraints":           constraints,
        "assumptions":           assumptions,
        "open_questions":        open_questions,
        "safety_mode":           safety_mode,
    }
