from datetime import datetime
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agents.supervisor import SupervisorAgent
from agents.mission_interpreter_agent import MissionInterpreterAgent
from memory.memory_manager import get_recent_memory
from backend.app.export.export_manager import export_mission_files
from backend.app.omni_core.omni_forge_service import (
    run_omni_forge_validation,
    run_omni_forge_cad_script_generation,
)


app = FastAPI(title="OMNI Command API")


# ---------------------------------------------------------
# CORS CONFIG
# Allows your React frontend to talk to the FastAPI backend.
# Frontend usually runs on http://localhost:5173 with Vite.
# ---------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------
# GLOBAL AGENT INSTANCES
# ---------------------------------------------------------
supervisor = SupervisorAgent()
interpreter = MissionInterpreterAgent()


# ---------------------------------------------------------
# REQUEST MODELS
# ---------------------------------------------------------
class MissionRequest(BaseModel):
    mission: str


class ForgeMissionRequest(BaseModel):
    mission: str


class MissionExportRequest(BaseModel):
    mission_result: Dict[str, Any]


class InterpretRequest(BaseModel):
    idea: str
    context: str = ""


class InterpretAndRunRequest(BaseModel):
    idea: str
    context: str = ""
    auto_export: bool = False


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


def sanitize_legacy_names(value: Any) -> Any:
    """
    Recursively removes old Marvel/Avengers naming from API responses.

    This gives the frontend OMNI-native data even if older modules still
    return older labels.
    """
    replacements = {
        "Reed Richards": "Omni",
        "Tony Stark": "Sky",
        "Bruce Banner": "Isy",
        "Hank Pym": "Oli",
        "Ultron": "Pluto",
        "Vision": "QaZ",
        "Shuri": "Korva",
        "AI Avengers": "OMNI",
        "Marvel Geniuses HQ": "OMNI Command",
        "Marvel Geniuses": "OMNI",
        "Bruce": "Isy",
        "Tony": "Sky",
        "Hank": "Oli",
        "Reed": "Omni",
    }

    if isinstance(value, str):
        cleaned = value
        for old, new in replacements.items():
            cleaned = cleaned.replace(old, new)
        return cleaned

    if isinstance(value, list):
        return [sanitize_legacy_names(item) for item in value]

    if isinstance(value, dict):
        return {
            key: sanitize_legacy_names(item)
            for key, item in value.items()
        }

    return value


def remove_legacy_agent_keys(agents: Any) -> Any:
    """
    The supervisor may temporarily return both legacy keys and new OMNI keys.

    This removes old keys from the API output while preserving the new keys.
    """
    if not isinstance(agents, dict):
        return agents

    preferred_keys = ["omni", "sky", "korva", "isy", "oli", "pluto", "qaz"]

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

    # Case 1: supervisor returns plain text.
    if isinstance(raw_result, str):
        final_output = sanitize_legacy_names(raw_result)

        return {
            "mission": mission,
            "created_at": created_at,
            "result_id": created_at.replace(":", "-").replace(".", "-"),
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
        result = sanitize_legacy_names(raw_result.copy())

        final_output = (
            result.get("final_decision")
            or result.get("final_report")
            or result.get("final_synthesis")
            or result.get("revision", {}).get("final_blueprint")
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
            "result_id": result.get(
                "result_id",
                created_at.replace(":", "-").replace(".", "-"),
            ),
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

        return sanitize_legacy_names(normalized)

    # Case 3: unexpected return type.
    final_output = sanitize_legacy_names(str(raw_result))

    return {
        "mission": mission,
        "created_at": created_at,
        "result_id": created_at.replace(":", "-").replace(".", "-"),
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


def run_supervisor_mission(mission: str) -> Dict[str, Any]:
    """
    Runs the OMNI supervisor and returns a normalized mission result.

    Used by both /api/mission/run and /api/mission/interpret-and-run.
    """
    if hasattr(supervisor, "run_mission_structured"):
        raw_result = supervisor.run_mission_structured(mission)

    elif hasattr(supervisor, "run"):
        raw_result = supervisor.run(mission)

    else:
        raise AttributeError(
            "SupervisorAgent must have either run_mission_structured() or run()."
        )

    return normalize_mission_result(mission, raw_result)


# ---------------------------------------------------------
# ROUTES
# ---------------------------------------------------------
@app.get("/")
def home():
    return {
        "message": "OMNI Command backend is running",
        "docs": "Visit http://127.0.0.1:8000/docs to test the API.",
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/health")
def health_check():
    return {
        "status": "online",
        "service": "OMNI Command API",
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/memory")
def read_memory():
    try:
        memory = get_recent_memory()
        return {
            "memory": sanitize_legacy_names(memory),
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read memory: {str(error)}",
        )


@app.post("/api/mission/interpret")
def interpret_mission(request: InterpretRequest):
    """
    Echo turns a rough human idea into a structured OMNI mission prompt.

    This does not run the full OMNI council.
    It only returns the expanded mission and planning metadata.
    """
    idea = request.idea.strip()
    context = request.context.strip()

    if not idea:
        raise HTTPException(
            status_code=400,
            detail="Idea cannot be empty.",
        )

    try:
        interpretation = interpreter.interpret(idea=idea, context=context)

        return {
            "status": "success",
            "message": "Echo interpreted the idea successfully.",
            "interpretation": sanitize_legacy_names(interpretation),
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Mission interpretation failed: {str(error)}",
        )


@app.post("/api/mission/interpret-and-run")
def interpret_and_run_mission(request: InterpretAndRunRequest):
    """
    Echo interprets a rough idea, then OMNI runs the expanded mission.

    If auto_export is true, the completed mission result is also exported
    into outputs/omni_missions/.
    """
    idea = request.idea.strip()
    context = request.context.strip()

    if not idea:
        raise HTTPException(
            status_code=400,
            detail="Idea cannot be empty.",
        )

    try:
        interpretation = interpreter.interpret(idea=idea, context=context)
        interpretation = sanitize_legacy_names(interpretation)

        expanded_mission = interpretation.get("expanded_mission")

        if not expanded_mission:
            raise ValueError("Echo did not return an expanded_mission field.")

        mission_result = run_supervisor_mission(expanded_mission)
        mission_result["echo_interpretation"] = interpretation
        mission_result["original_idea"] = idea

        export_result = None

        if request.auto_export:
            export_result = export_mission_files(mission_result)

        return {
            "status": "success",
            "message": "Echo interpreted the idea and OMNI completed the mission.",
            "interpretation": interpretation,
            "mission_result": mission_result,
            "export": export_result,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Interpret-and-run failed: {str(error)}",
        )


@app.post("/api/mission/run")
def run_mission(request: MissionRequest):
    mission = request.mission.strip()

    if not mission:
        raise HTTPException(
            status_code=400,
            detail="Mission cannot be empty.",
        )

    try:
        return run_supervisor_mission(mission)

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Mission failed: {str(error)}",
        )


@app.post("/forge/validate")
def forge_validate(request: ForgeMissionRequest):
    """
    OMNI Forge Level 2 endpoint.

    Takes a mission prompt and returns:
    - structured mission schema
    - validation report
    - CAD parameter plan when supported

    This does not generate a CAD script.
    This does not execute printer or workshop hardware actions.
    """
    mission = request.mission.strip()

    if not mission:
        raise HTTPException(
            status_code=400,
            detail="Mission cannot be empty.",
        )

    try:
        return run_omni_forge_validation(mission)

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"OMNI Forge validation failed: {str(error)}",
        )


@app.post("/forge/generate-cad-script")
def forge_generate_cad_script(request: ForgeMissionRequest):
    """
    OMNI Forge Level 3 endpoint.

    Takes a mission prompt and returns:
    - structured mission schema
    - validation report
    - CAD parameter plan
    - generated CadQuery script saved to disk

    This does not execute the script.
    This does not start fabrication.
    This does not control printers or physical devices.
    """
    mission = request.mission.strip()

    if not mission:
        raise HTTPException(
            status_code=400,
            detail="Mission cannot be empty.",
        )

    try:
        return run_omni_forge_cad_script_generation(mission)

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"OMNI Forge CAD script generation failed: {str(error)}",
        )


@app.post("/api/mission/export")
def export_mission(request: MissionExportRequest):
    """
    Writes a completed mission result into outputs/omni_missions/<mission_folder>/.

    This endpoint expects the full JSON response from /api/mission/run.
    The frontend calls this using the current missionResult.raw object.
    """
    try:
        mission_result = sanitize_legacy_names(request.mission_result)

        if not isinstance(mission_result, dict):
            raise ValueError("mission_result must be a JSON object.")

        if "mission" not in mission_result:
            raise ValueError("mission_result must include a mission field.")

        export_result = export_mission_files(mission_result)

        return {
            "status": "success",
            "message": "Mission files exported successfully.",
            "export": export_result,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Mission export failed: {str(error)}",
        )