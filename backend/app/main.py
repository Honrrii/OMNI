from datetime import datetime
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agents.supervisor import SupervisorAgent
from agents.mission_interpreter_agent import MissionInterpreterAgent
from memory.memory_manager import get_recent_memory

from backend.app.export.export_manager import export_mission_files
from backend.app.knowledge.knowledge_context_builder import build_omni_knowledge_context
from backend.app.omni_core.formatters import sanitize_payload
from backend.app.omni_core.mission_result_normalizer import normalize_mission_result
from backend.app.omni_core.omni_forge_service import (
    run_omni_forge_validation,
    run_omni_forge_cad_script_generation,
    run_omni_forge_cad_script_execution,
)
from backend.app.ros.ros_status_service import get_ros_status
from backend.app.api.ml_routes import router as ml_router
from backend.app.api.ml_lab_routes import router as ml_lab_router
from backend.app.api.reliability_routes import router as reliability_router
from backend.app.api.visual_bay_routes import router as visual_bay_router


app = FastAPI(title="OMNI Command API")

app.include_router(reliability_router, prefix="/api/reliability", tags=["reliability"])

app.include_router(ml_router, prefix="/api/ml", tags=["ml"])
app.include_router(ml_lab_router, prefix="/api/ml/v2", tags=["omnitorch-learning"])

app.include_router(visual_bay_router, prefix="/api/visual-bay", tags=["visual-bay"])


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


class ForgeScriptExecutionRequest(BaseModel):
    script_path: str


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
# SHARED SANITIZER WRAPPER
# ---------------------------------------------------------
def sanitize_legacy_names(value: Any) -> Any:
    """
    Compatibility wrapper.

    Older code in main.py still calls sanitize_legacy_names(), but the actual
    implementation now lives in backend.app.omni_core.formatters.
    """
    return sanitize_payload(value)


def format_knowledge_context_for_prompt(knowledge_context: Dict[str, Any]) -> str:
    """
    Converts OMNI's retrieved local knowledge into a compact prompt block.

    This lets the Agent Council use the knowledge without flooding the prompt.
    """
    selected_domains = knowledge_context.get("selected_domains", [])
    domain_summaries = knowledge_context.get("domain_summaries", {})
    retrieved_knowledge = knowledge_context.get("retrieved_knowledge", [])

    lines = [
        "OMNI LOCAL KNOWLEDGE CONTEXT",
        "",
        "Selected knowledge domains:",
    ]

    if selected_domains:
        for domain in selected_domains:
            summary = domain_summaries.get(domain, "")
            lines.append(f"- {domain}: {summary}")
    else:
        lines.append("- None selected")

    lines.extend(
        [
            "",
            "Relevant retrieved knowledge excerpts:",
        ]
    )

    if retrieved_knowledge:
        for i, item in enumerate(retrieved_knowledge, start=1):
            excerpt = str(item.get("text", ""))[:700].replace("\n", " ")
            matched_terms = ", ".join(item.get("matched_terms", []))

            lines.extend(
                [
                    "",
                    f"[Knowledge Hit {i}]",
                    f"Domain: {item.get('domain', 'unknown')}",
                    f"Source: {item.get('source_file', 'unknown')}",
                    f"Chunk: {item.get('chunk_id', 'unknown')}",
                    f"Matched terms: {matched_terms}",
                    f"Excerpt: {excerpt}",
                ]
            )
    else:
        lines.append("- No local knowledge chunks retrieved.")

    return "\n".join(lines)


def run_supervisor_mission(mission: str) -> Dict[str, Any]:
    """
    Runs the OMNI supervisor and returns a normalized mission result.

    Used by both /api/mission/run and /api/mission/interpret-and-run.

    This also attaches OMNI's local knowledge context so missions can be
    influenced by the local PDF knowledge library.
    """
    knowledge_context = build_omni_knowledge_context(mission_text=mission, top_k=8)
    knowledge_prompt_block = format_knowledge_context_for_prompt(knowledge_context)

    mission_with_knowledge = f"""
{mission}

{knowledge_prompt_block}

Instruction to OMNI Agent Council:
Use the local knowledge context as grounding material when it is relevant.
Do not copy it blindly. Apply it as engineering reference material for CAD,
ROS2 architecture, autonomy planning, fabrication decisions, and validation.
"""

    if hasattr(supervisor, "run_mission_structured"):
        raw_result = supervisor.run_mission_structured(mission_with_knowledge)

    elif hasattr(supervisor, "run"):
        raw_result = supervisor.run(mission_with_knowledge)

    else:
        raise AttributeError(
            "SupervisorAgent must have either run_mission_structured() or run()."
        )

    normalized_result = normalize_mission_result(mission, raw_result)
    normalized_result["knowledge_context"] = sanitize_legacy_names(knowledge_context)

    return sanitize_legacy_names(normalized_result)


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


@app.get("/ros/status")
def ros_status():
    """
    OMNI Simulation Level 1 endpoint.

    Read-only ROS2 status dashboard data.
    This does not move robots, launch Gazebo, or control hardware.
    """
    try:
        return get_ros_status()

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"ROS status check failed: {str(error)}",
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
            "mission_result": sanitize_legacy_names(mission_result),
            "export": sanitize_legacy_names(export_result),
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
        return sanitize_legacy_names(run_omni_forge_validation(mission))

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
        return sanitize_legacy_names(run_omni_forge_cad_script_generation(mission))

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"OMNI Forge CAD script generation failed: {str(error)}",
        )


@app.post("/forge/execute-cad-script")
def forge_execute_cad_script(request: ForgeScriptExecutionRequest):
    """
    OMNI Forge Level 4 endpoint.

    Executes a previously generated CadQuery script and exports CAD files.

    This does not start fabrication.
    This does not control printers or physical devices.
    """
    script_path = request.script_path.strip()

    if not script_path:
        raise HTTPException(
            status_code=400,
            detail="script_path cannot be empty.",
        )

    try:
        return sanitize_legacy_names(run_omni_forge_cad_script_execution(script_path))

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"OMNI Forge CAD script execution failed: {str(error)}",
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
            "export": sanitize_legacy_names(export_result),
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Mission export failed: {str(error)}",
        )