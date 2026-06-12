"""
omni_core/mission_result_normalizer.py
=======================================
Lightweight mission-result normalization, extracted from backend/app/main.py.

This module converts raw supervisor output into the clean OMNI API response
shape. It deliberately depends only on the standard library and the canonical
sanitizer in backend.app.omni_core.formatters, so importing it does NOT pull in
FastAPI, ML routes, torch, or other heavy backend wiring.

Behavior is identical to the original main.py implementation. Where the old
code called main.py's local sanitize_legacy_names() wrapper, this module calls
sanitize_payload() directly — the wrapper was nothing more than a passthrough
to sanitize_payload().
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from backend.app.omni_core.formatters import sanitize_payload


# ---------------------------------------------------------
# OMNI DEFAULT FALLBACKS
# These are only used if the supervisor returns plain text
# or an unexpected response.
# ---------------------------------------------------------
def default_timeline():
    return [
        {
            "step": "1",
            "title": "Mission Received",
            "description": "OMNI accepted the user objective.",
        },
        {
            "step": "2",
            "title": "Agent Council Deployed",
            "description": "Specialist intelligences were assigned to the mission.",
        },
        {
            "step": "3",
            "title": "Critique and Revision Completed",
            "description": "Pluto reviewed the drafts and Omni revised the blueprint.",
        },
        {
            "step": "4",
            "title": "Validation Completed",
            "description": "QaZ validated the revised mission output.",
        },
        {
            "step": "5",
            "title": "Artifacts Prepared",
            "description": "OMNI organized the mission into export-ready artifacts.",
        },
    ]


def default_agent_council():
    return [
        {
            "id": "echo",
            "name": "Echo",
            "role": "Mission Interpreter / Prompt Expansion Agent",
            "color": "cyan",
            "responsibility": "Transforms rough human ideas into structured OMNI missions.",
        },
        {
            "id": "omni",
            "name": "Omni",
            "role": "Mission Orchestrator / Systems Intelligence",
            "color": "red",
            "responsibility": "Coordinates the mission and produces the revised final blueprint.",
        },
        {
            "id": "sky",
            "name": "Sky",
            "role": "Robotics, ROS2, Drones, and Autonomy",
            "color": "blue",
            "responsibility": "Generates ROS2 architecture, software plans, node graphs, and simulation workflows.",
        },
        {
            "id": "korva",
            "name": "Korva",
            "role": "Hardware, Electronics, Embedded Systems, and PCB",
            "color": "black_white_outline",
            "responsibility": "Generates wiring, power, embedded systems, component, and PCB direction.",
        },
        {
            "id": "isy",
            "name": "Isy",
            "role": "Physics, Controls, Dynamics, and Feasibility",
            "color": "sunset_orange",
            "responsibility": "Checks physics, controls, stability, dynamics, and feasibility.",
        },
        {
            "id": "oli",
            "name": "Oli",
            "role": "CAD, Fusion 360, 3D Concepts, and Visual Artifacts",
            "color": "white_silver",
            "responsibility": "Creates Fusion 360 concepts, CAD-ready modeling plans, and visual artifacts.",
        },
        {
            "id": "pluto",
            "name": "Pluto",
            "role": "Risk, Failure Analysis, and Safety Gates",
            "color": "velvet",
            "responsibility": "Finds unsafe assumptions, failure modes, missing requirements, and stop conditions.",
        },
        {
            "id": "qaz",
            "name": "QaZ",
            "role": "Validation, Scoring, and Requirements Verification",
            "color": "light_pink",
            "responsibility": "Scores the output, identifies missing evidence, and recommends validation tests.",
        },
        {
            "id": "vega",
            "name": "Vega",
            "role": "Design Morphology, Aesthetics, and Form Exploration",
            "color": "violet",
            "responsibility": "Explores creative design language, morphology, and visual engineering concepts.",
        },
    ]


def default_agents_from_text(final_output: str):
    return {
        "omni": final_output,
        "sky": "No Sky report returned.",
        "korva": "No Korva report returned.",
        "isy": "No Isy report returned.",
        "oli": "No Oli report returned.",
        "pluto": "No Pluto critique returned.",
        "qaz": "No QaZ validation returned.",
        "vega": "No Vega design report returned.",
    }


def build_default_artifacts(mission: str, final_output: str):
    return {
        "mission_overview": {
            "title": "Mission Overview",
            "description": "High-level interpretation of the user mission.",
            "content": f"Mission: {mission}",
        },
        "engineering_blueprint": {
            "title": "Engineering Blueprint",
            "description": "Synthesized output from the OMNI mission system.",
            "content": final_output,
        },
        "next_build_steps": {
            "title": "Next Build Steps",
            "description": "Suggested continuation path for implementation.",
            "content": [
                "Review the generated blueprint.",
                "Identify missing assumptions.",
                "Convert the strongest sections into artifacts.",
                "Move into CAD, ROS2, electronics, or code implementation.",
                "Run the mission again with more specific constraints.",
            ],
        },
        "risk_review": {
            "title": "Risk Review",
            "description": "Early feasibility risks to keep the mission grounded.",
            "content": [
                "Missing measurements or constraints.",
                "Unrealistic hardware assumptions.",
                "Output may need engineering validation.",
                "CAD, ROS2, PCB, and simulation plans should be tested separately.",
            ],
        },
    }


def remove_legacy_agent_keys(agents: Any) -> Any:
    """
    The supervisor may temporarily return both legacy keys and new OMNI keys.

    This removes old keys from the API output while preserving the new keys.
    """
    if not isinstance(agents, dict):
        return agents

    preferred_keys = [
        "omni",
        "sky",
        "korva",
        "isy",
        "oli",
        "pluto",
        "qaz",
        "vega",
    ]

    if any(key in agents for key in preferred_keys):
        return {
            key: agents[key]
            for key in preferred_keys
            if key in agents
        }

    legacy_to_omni = {
        "reed_richards": "omni",
        "tony_stark": "sky",
        "shuri": "korva",
        "bruce_banner": "isy",
        "hank_pym": "oli",
        "ultron": "pluto",
        "vision": "qaz",
    }

    cleaned = {}
    for old_key, new_key in legacy_to_omni.items():
        if old_key in agents:
            cleaned[new_key] = agents[old_key]

    return cleaned or agents


def normalize_mission_result(mission: str, raw_result: Any) -> Dict[str, Any]:
    """
    Converts supervisor output into a clean OMNI API response.

    Important:
    If the supervisor already returns a structured dict, do NOT wrap the
    entire dict into final_synthesis. Return the structured payload and
    add frontend-friendly aliases.
    """
    created_at = datetime.now().isoformat()
    result_id = created_at.replace(":", "-").replace(".", "-")

    # Case 1: supervisor returns plain text.
    if isinstance(raw_result, str):
        final_output = sanitize_payload(raw_result)

        return {
            "mission": mission,
            "created_at": created_at,
            "result_id": result_id,
            "agent_council": default_agent_council(),
            "council_events": [],
            "agents": default_agents_from_text(final_output),
            "critique": None,
            "revision": None,
            "final_decision": final_output,
            "final_report": final_output,
            "final_synthesis": final_output,
            "artifacts": build_default_artifacts(mission, final_output),
            "validation": None,
            "export_manifest": None,
            "timeline": default_timeline(),
            "status": "complete",
        }

    # Case 2: supervisor returns structured dict.
    if isinstance(raw_result, dict):
        # Sanitize once at the output boundary below (return sanitize_payload(
        # normalized)). The sanitizer is idempotent over nested payloads, so the
        # earlier per-field pass here was redundant.
        result = raw_result.copy()

        revision = result.get("revision", {})
        if not isinstance(revision, dict):
            revision = {}

        final_output = (
            result.get("final_decision")
            or result.get("final_report")
            or result.get("final_synthesis")
            or revision.get("final_blueprint")
            or result.get("response")
            or result.get("result")
            or result.get("message")
            or "No final OMNI output returned."
        )

        agents = remove_legacy_agent_keys(result.get("agents", {}))

        normalized = {
            **result,

            # Stable top-level fields for frontend.
            "mission": result.get("mission", mission),
            "created_at": result.get("created_at", created_at),
            "result_id": result.get("result_id", result_id),
            "agent_council": result.get("agent_council", default_agent_council()),
            "council_events": result.get("council_events", []),
            "agents": agents,
            "critique": result.get("critique"),
            "revision": result.get("revision"),
            "final_decision": result.get("final_decision", final_output),
            "final_report": result.get("final_report", final_output),

            # Frontend compatibility alias.
            # This should be a clean string, not str(result).
            "final_synthesis": final_output,

            "artifacts": result.get(
                "artifacts",
                build_default_artifacts(mission, final_output),
            ),
            "validation": result.get("validation"),
            "export_manifest": result.get("export_manifest"),
            "timeline": result.get("timeline", default_timeline()),
            "status": result.get("status", "complete"),
        }

        return sanitize_payload(normalized)

    # Case 3: unexpected return type.
    final_output = sanitize_payload(str(raw_result))

    return {
        "mission": mission,
        "created_at": created_at,
        "result_id": result_id,
        "agent_council": default_agent_council(),
        "council_events": [],
        "agents": default_agents_from_text(final_output),
        "critique": None,
        "revision": None,
        "final_decision": final_output,
        "final_report": final_output,
        "final_synthesis": final_output,
        "artifacts": build_default_artifacts(mission, final_output),
        "validation": None,
        "export_manifest": None,
        "timeline": default_timeline(),
        "status": "complete",
    }
