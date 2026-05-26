import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import wait as _futures_wait
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from agents.robotics_agent import RoboticsAgent
from agents.research_agent import ResearchAgent
from agents.code_agent import CodeAgent
from agents.critic_agent import CriticAgent
from agents.design_agent import DesignAgent
from agents.design_candidates import extract_design_candidates_from_text
from agents.candidate_evaluator import evaluate_design_candidates
from backend.app.omni_core.mission_intent import compile_mission_intent
from agents.artifact_synthesizer import synthesize_artifacts
from agents.validator_agent import ValidatorAgent

from backend.app.omni_core.llm_router import call_llm

from backend.app.omni_core.formatters import (
    compact_context as format_compact_context,
    safe_folder_name,
    sanitize_legacy_names as format_sanitize_legacy_names,
    sanitize_payload as format_sanitize_payload,
)

from memory.memory_manager import get_recent_memory, add_mission_to_memory


from backend.app.omni_core.mission_state import MissionState


try:
    from backend.app.omni_core.telemetry import (
        log_agent_failed,
        log_agent_finished,
        log_agent_started,
        log_mission_finished,
        log_mission_started,
        log_synthesis_finished,
        log_synthesis_started,
    )
except Exception:
    def log_mission_started(state): pass
    def log_mission_finished(state): pass
    def log_agent_started(state, agent_id): pass
    def log_agent_finished(state, agent_id, parsed_output): pass
    def log_agent_failed(state, agent_id, error): pass
    def log_synthesis_started(state): pass
    def log_synthesis_finished(state, artifact_keys): pass


class SupervisorAgent:
    def __init__(self):
        self.name = "Omni"

        # Frontend-facing OMNI identities:
        self.design_agent = DesignAgent()       # Vega
        self.robotics_agent = RoboticsAgent()   # Sky
        self.research_agent = ResearchAgent()   # Isy
        self.code_agent = CodeAgent()           # Oli
        self.critic_agent = CriticAgent()       # Pluto
        self.validator_agent = ValidatorAgent() # QaZ

    # ---------------------------------------------------------
    # Shared formatting / sanitation wrappers
    # ---------------------------------------------------------
    def sanitize_legacy_names(self, text: Any) -> Any:
        return format_sanitize_legacy_names(text)

    def sanitize_payload(self, payload: Any) -> Any:
        return format_sanitize_payload(payload)

    def compact_context(self, text: Any, limit: int = 9000) -> str:
        return format_compact_context(text, limit=limit)

    def state_to_dict(self, state: MissionState) -> Dict[str, Any]:
        if hasattr(state, "to_dict"):
            return state.to_dict()

        return {
            "mission_id": getattr(state, "mission_id", None),
            "mission_text": getattr(state, "mission_text", None),
            "status": getattr(state, "status", None),
            "structured_outputs": getattr(state, "structured_outputs", {}),
            "warnings": getattr(state, "warnings", []),
            "errors": getattr(state, "errors", []),
            "metadata": getattr(state, "metadata", {}),
        }

    # ---------------------------------------------------------
    # JSON parsing
    # ---------------------------------------------------------
    def parse_json_object(self, raw_text: Any) -> Dict[str, Any]:
        if isinstance(raw_text, dict):
            return raw_text

        text = str(raw_text or "").strip()

        if text.startswith("```"):
            text = text.strip("`").strip()
            if text.lower().startswith("json"):
                text = text[4:].strip()

        try:
            parsed = json.loads(text)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            pass

        start = text.find("{")
        end = text.rfind("}")

        if start != -1 and end != -1 and end > start:
            try:
                parsed = json.loads(text[start : end + 1])
                return parsed if isinstance(parsed, dict) else {}
            except Exception:
                return {}

        return {}

    def parse_text_agent_output(
        self,
        raw: Any,
        state: MissionState,
        agent_id: str,
        role: str,
    ) -> Dict[str, Any]:
        parsed = self.parse_json_object(raw)

        if parsed:
            parsed.setdefault("agent_id", agent_id)
            parsed.setdefault("role", role)
            parsed.setdefault("status", "structured")
            return self.sanitize_payload(parsed)

        return {
            "agent_id": agent_id,
            "role": role,
            "status": "unstructured_fallback",
            "content": {"raw_report": str(raw or "")},
            "warnings": ["Agent returned markdown/plain text instead of structured JSON."],
        }

    def parse_structured_agent_output(
        self,
        raw: Any,
        state: MissionState,
        agent_id: str,
        role: str,
    ) -> Dict[str, Any]:
        parsed = self.parse_json_object(raw)

        if parsed:
            parsed.setdefault("agent_id", agent_id)
            parsed.setdefault("role", role)
            parsed.setdefault("status", "structured")
            return self.sanitize_payload(parsed)

        return {
            "agent_id": agent_id,
            "role": role,
            "status": "json_parse_fallback",
            "content": {"raw_report": str(raw or "")},
            "warnings": [f"{agent_id} did not return valid JSON. Raw output was preserved."],
        }

    # ---------------------------------------------------------
    # State-aware agent runner
    # ---------------------------------------------------------
    def run_state_step(
        self,
        state: MissionState,
        agent_id: str,
        agent_name: str,
        role: str,
        prompt_builder: Callable[[MissionState], str],
        runner: Callable[[str], Any],
        parser: Optional[Callable[[Any, MissionState], Dict[str, Any]]] = None,
        fallback_message: str = "Agent failed. Continue with fallback assumptions.",
    ) -> Tuple[str, Dict[str, Any]]:
        try:
            state.start_agent(agent_id=agent_id, agent_name=agent_name)
            log_agent_started(state, agent_id)

            prompt = prompt_builder(state)
            raw = runner(prompt)

            if raw is None or raw == "":
                raw = fallback_message

            raw = self.sanitize_payload(raw)

            if parser is None:
                parsed = self.parse_text_agent_output(raw, state, agent_id, role)
            else:
                parsed = parser(raw, state)

            if not isinstance(parsed, dict):
                parsed = {
                    "agent_id": agent_id,
                    "role": role,
                    "status": "parser_fallback",
                    "content": {"raw_report": str(raw or "")},
                    "warnings": ["Parser did not return a dictionary. Raw output was preserved."],
                }

            parsed = self.sanitize_payload(parsed)
            state.finish_agent(agent_id=agent_id, raw_output=str(raw), parsed_output=parsed)
            log_agent_finished(state, agent_id, parsed)
            return str(raw), parsed

        except Exception as exc:
            error_message = f"{type(exc).__name__}: {exc}"
            fallback_raw = self.sanitize_legacy_names(
                f"# {agent_name} — Error / Fallback\n\n"
                f"{fallback_message}\n\n"
                f"Technical detail: {error_message}"
            )
            fallback_parsed = {
                "agent_id": agent_id,
                "role": role,
                "status": "error_fallback",
                "content": {"raw_report": fallback_raw},
                "errors": [error_message],
                "warnings": ["This step failed during execution. OMNI continued with fallback output."],
            }

            try:
                state.fail_agent(agent_id=agent_id, error=error_message, raw_output=fallback_raw)
                state.structured_outputs[agent_id] = fallback_parsed
            except Exception:
                pass

            log_agent_failed(state, agent_id, error_message)
            return fallback_raw, fallback_parsed

    def get_agent_raw(self, state: MissionState, agent_id: str) -> str:
        record = getattr(state, "agent_records", {}).get(agent_id)

        if record is None:
            return ""

        if isinstance(record, dict):
            return str(record.get("raw_output") or "")

        return str(getattr(record, "raw_output", "") or "")

    # ---------------------------------------------------------
    # Agent schemas and prompt builders
    # ---------------------------------------------------------
    def get_agent_schema(self, agent_id: str) -> Dict[str, Any]:
        schemas = {
            "sky": {
                "agent_id": "sky",
                "role": "robotics_software_architecture",
                "mission_interpretation": "string",
                "robotics_architecture_summary": "string",
                "ros2_package_plan": {
                    "package_name": "string",
                    "nodes": [
                        {
                            "name": "string",
                            "purpose": "string",
                            "subscribes_to": ["string"],
                            "publishes_to": ["string"],
                            "services": ["string"],
                            "parameters": ["string"],
                        }
                    ],
                    "topics": ["string"],
                    "launch_files": ["string"],
                    "config_files": ["string"],
                    "tests": ["string"],
                },
                "autonomy_plan": ["string"],
                "sensor_stack": ["string"],
                "simulation_plan": ["string"],
                "data_flow": ["string"],
                "implementation_risks": ["string"],
                "handoff_to_artifact_synthesis": {
                    "ros2_node_graph_notes": ["string"],
                    "test_checklist_notes": ["string"],
                    "next_artifacts": ["string"],
                },
            },
            "isy": {
                "agent_id": "isy",
                "role": "physics_controls_feasibility",
                "system_goal": "string",
                "physical_feasibility_summary": "string",
                "major_subsystems": [
                    {
                        "name": "string",
                        "purpose": "string",
                        "inputs": ["string"],
                        "outputs": ["string"],
                        "notes": ["string"],
                    }
                ],
                "mass_and_geometry_assumptions": ["string"],
                "stability_considerations": ["string"],
                "controls_strategy": ["string"],
                "dynamics_notes": ["string"],
                "power_motion_relationships": ["string"],
                "known_unknowns": ["string"],
                "validation_items": ["string"],
                "handoff_to_artifact_synthesis": {
                    "component_tree_candidates": ["string"],
                    "blueprint_plan_notes": ["string"],
                    "risk_matrix_notes": ["string"],
                },
            },
            "oli": {
                "agent_id": "oli",
                "role": "cad_visual_artifacts",
                "cad_direction_summary": "string",
                "fusion360_modeling_plan": [
                    {
                        "step": "string",
                        "purpose": "string",
                        "geometry": "string",
                        "parameters": ["string"],
                    }
                ],
                "component_layout": [
                    {
                        "component": "string",
                        "placement": "string",
                        "reason": "string",
                    }
                ],
                "mechanical_design_notes": ["string"],
                "fabrication_notes": ["string"],
                "visual_artifact_plan": ["string"],
                "cad_risks": ["string"],
                "handoff_to_artifact_synthesis": {
                    "component_tree_notes": ["string"],
                    "blueprint_plan_notes": ["string"],
                    "fusion360_concept_notes": ["string"],
                    "next_artifacts": ["string"],
                },
            },
            "korva": {
                "agent_id": "korva",
                "role": "hardware_electronics_embedded",
                "hardware_architecture_summary": "string",
                "component_list": [
                    {
                        "component": "string",
                        "role": "string",
                        "interface": "string",
                        "power_notes": "string",
                    }
                ],
                "wiring_plan": ["string"],
                "power_assumptions": ["string"],
                "embedded_systems_notes": ["string"],
                "communication_buses": ["string"],
                "pcb_or_prototyping_direction": "string",
                "hardware_risks": ["string"],
                "missing_hardware_information": ["string"],
                "handoff_to_artifact_synthesis": {
                    "hardware_architecture_notes": ["string"],
                    "risk_matrix_notes": ["string"],
                    "approval_gate_notes": ["string"],
                    "next_artifacts": ["string"],
                },
            },
        }
        return schemas.get(agent_id, {})

    def build_omni_strategy_prompt(self, state: MissionState, memory_context: str) -> str:
        return f"""
You are Omni, the system orchestrator inside an engineering AI command system.

You are not a fictional superhero.
You are the mission-level intelligence responsible for coordinating specialist agents.

Your specialty is ONLY:
- mission strategy
- system-level priorities
- build phases
- decision gates
- human approval checkpoints
- how specialist outputs should connect
- what should become a visual artifact in the dashboard

Current Mission:
{state.mission_text}

Relevant Previous Memory:
{memory_context}

Use these OMNI agent names:
- Omni: mission orchestration and system integration
- Vega: creative design expansion, morphology, unconventional concept alternatives
- Sky: robotics, ROS2, drones, autonomy, software architecture
- Korva: electronics, embedded systems, wiring, PCB, hardware architecture
- Isy: physics, controls, dynamics, feasibility
- Oli: CAD, Fusion 360, 3D concepts, visual artifacts
- Pluto: risk, failure analysis, safety gates
- QaZ: validation, scoring, requirements verification

Return your output in this exact markdown format:

# Omni — Mission Strategy / System Integration

## Mission Objective
Define the mission in one clear engineering objective.

## System Priorities
List the top 3-5 priorities for this mission.

## Build Phases
Break the mission into phases.

## Human Approval Gates
List what Henry must approve before moving forward.

## Specialist Assignments
Explain what Vega, Sky, Korva, Isy, Oli, Pluto, and QaZ should each produce.

## Dashboard Artifacts Needed
List the visual artifacts the OMNI dashboard should generate.

## Omni's Initial Strategic Recommendation
Give the next best action before specialist work begins.
"""

    def build_vega_prompt(self, state: MissionState, memory_context: str) -> str:
        return f"""
Current Mission:
{state.mission_text}

Relevant Previous Memory:
{memory_context}

Omni Strategy:
{self.get_agent_raw(state, "omni")}

You are Vega, OMNI's creative design expansion and morphology exploration agent.

Generate unconventional but physically plausible design alternatives.

Focus on:
- morphology
- body layout
- silhouette
- mechanical inspiration
- aesthetic alternatives that can still become engineering concepts
- what should be passed to Sky, Korva, Isy, and Oli

Do not use fictional superhero references.
"""

    def build_specialist_context(self, state: MissionState, memory_context: str) -> str:
        return self.compact_context(
            f"""
Mission:
{state.mission_text}

Relevant Previous Memory:
{memory_context}

Omni Strategy:
{self.get_agent_raw(state, "omni")}

Vega Creative Design Context:
{self.get_agent_raw(state, "vega")}

Current Structured Outputs:
{json.dumps(state.structured_outputs, indent=2, default=str)}
""",
            limit=14000,
        )

    def build_json_agent_prompt(self, state: MissionState, memory_context: str, agent_id: str, name: str, purpose: str) -> str:
        schema = self.get_agent_schema(agent_id)
        return f"""
You are {name}, {purpose} inside OMNI.

{self.build_specialist_context(state, memory_context)}

Return STRICT JSON only. No markdown. No prose outside JSON.
Use this schema exactly, filling values with mission-specific engineering content:

{json.dumps(schema, indent=2)}
"""

    def build_sky_prompt(self, state: MissionState, memory_context: str) -> str:
        return self.build_json_agent_prompt(
            state,
            memory_context,
            "sky",
            "Sky",
            "the robotics, ROS2, drones, autonomy, and software architecture agent",
        )

    def build_isy_prompt(self, state: MissionState, memory_context: str) -> str:
        return self.build_json_agent_prompt(
            state,
            memory_context,
            "isy",
            "Isy",
            "the physics, controls, dynamics, and feasibility agent",
        )

    def build_oli_prompt(self, state: MissionState, memory_context: str) -> str:
        return self.build_json_agent_prompt(
            state,
            memory_context,
            "oli",
            "Oli",
            "the CAD, Fusion 360, 3D concept, and visual artifact agent",
        )

    def build_korva_prompt(self, state: MissionState, memory_context: str) -> str:
        return self.build_json_agent_prompt(
            state,
            memory_context,
            "korva",
            "Korva",
            "the hardware, electronics, embedded systems, wiring, and PCB architecture agent",
        )

    def build_pluto_context(self, state: MissionState, memory_context: str) -> str:
        return self.compact_context(
            f"""
Current Mission:
{state.mission_text}

Relevant Previous Memory:
{memory_context}

Omni Strategy:
{self.get_agent_raw(state, "omni")}

Vega Creative Expansion:
{self.get_agent_raw(state, "vega")}
""",
            limit=12000,
        )

    def build_pluto_combined_outputs(self, state: MissionState) -> str:
        return self.compact_context(
            f"""
Omni Strategy:
{self.get_agent_raw(state, "omni")}

Vega Creative Expansion:
{self.get_agent_raw(state, "vega")}

Structured Specialist Outputs:
{json.dumps(state.structured_outputs, indent=2, default=str)}

Sky Raw Report:
{self.get_agent_raw(state, "sky")}

Korva Raw Report:
{self.get_agent_raw(state, "korva")}

Isy Raw Report:
{self.get_agent_raw(state, "isy")}

Oli Raw Report:
{self.get_agent_raw(state, "oli")}
""",
            limit=18000,
        )

    # ---------------------------------------------------------
    # Legacy compatibility methods
    # ---------------------------------------------------------
    def safe_agent_run(self, agent_label, fn, fallback_message):
        try:
            result = fn()
            if result is None or result == "":
                result = fallback_message
            return self.sanitize_payload(result)
        except Exception as exc:
            return self.sanitize_legacy_names(
                f"# {agent_label} — Error / Fallback\n\n"
                f"{fallback_message}\n\n"
                f"Technical detail: {type(exc).__name__}: {exc}"
            )

    def run_omni_strategy(self, mission, memory_context):
        temp_state = MissionState(mission_text=mission)
        prompt = self.build_omni_strategy_prompt(temp_state, memory_context)
        return self.sanitize_legacy_names(call_llm(prompt, role="Omni"))

    def run_korva_hardware_report(self, mission, memory_context, omni_strategy, design_report=""):
        temp_state = MissionState(mission_text=mission)
        temp_state.finish_agent("omni", str(omni_strategy), {"raw_report": omni_strategy})
        temp_state.finish_agent("vega", str(design_report), {"raw_report": design_report})
        prompt = self.build_korva_prompt(temp_state, memory_context)
        return self.sanitize_legacy_names(call_llm(prompt, role="Korva"))

    # ---------------------------------------------------------
    # Agent council metadata
    # ---------------------------------------------------------
    def build_agent_council(self):
        return [
            {
                "id": "omni",
                "name": "Omni",
                "role": "Mission Orchestrator / Systems Intelligence",
                "color": "red",
                "responsibility": "Defines mission strategy, connects specialist outputs, and produces the revised final blueprint.",
            },
            {
                "id": "vega",
                "name": "Vega",
                "role": "Creative Design Expansion / Morphology Exploration",
                "color": "violet",
                "responsibility": "Generates unconventional but physically plausible design alternatives.",
            },
            {
                "id": "sky",
                "name": "Sky",
                "role": "Robotics, ROS2, Drones, and Autonomy",
                "color": "blue",
                "responsibility": "Generates software architecture, ROS2 nodes, topics, launch plans, and simulation workflow.",
            },
            {
                "id": "korva",
                "name": "Korva",
                "role": "Hardware, Electronics, Embedded Systems, and PCB",
                "color": "black_white_outline",
                "responsibility": "Generates hardware architecture, wiring logic, electronics constraints, power assumptions, and PCB direction.",
            },
            {
                "id": "isy",
                "name": "Isy",
                "role": "Physics, Controls, Dynamics, and Feasibility",
                "color": "sunset_orange",
                "responsibility": "Checks physical feasibility, control logic, dynamics, torque, mass, stability, and sensor-fusion concerns.",
            },
            {
                "id": "oli",
                "name": "Oli",
                "role": "CAD, Fusion 360, 3D Concepts, and Visual Artifacts",
                "color": "white_silver",
                "responsibility": "Generates CAD-ready concepts, Fusion 360 modeling steps, component layout, and visual artifact plans.",
            },
            {
                "id": "pluto",
                "name": "Pluto",
                "role": "Risk, Failure Analysis, and Safety Gates",
                "color": "velvet",
                "responsibility": "Finds dangerous assumptions, failure modes, unsafe tests, missing requirements, and stop conditions.",
            },
            {
                "id": "qaz",
                "name": "QaZ",
                "role": "Validation, Scoring, and Requirements Verification",
                "color": "light_pink",
                "responsibility": "Scores mission output, identifies missing evidence, and recommends next validation tests.",
            },
        ]

    def build_council_events(self):
        return [
            {
                "step": "1",
                "actor": "Omni",
                "event": "Mission strategy created",
                "description": "Omni converts the user mission into priorities, build phases, and specialist assignments.",
            },
            {
                "step": "2",
                "actor": "Vega",
                "event": "Creative design alternatives generated",
                "description": "Vega expands the mission into unconventional but physically plausible options.",
            },
            {
                "step": "3",
                "actor": "Sky / Isy / Oli / Korva",
                "event": "Structured specialist outputs generated",
                "description": "Core engineering agents generate structured JSON for artifact synthesis.",
            },
            {
                "step": "4",
                "actor": "Pluto",
                "event": "Critique generated",
                "description": "Pluto reviews the drafts for unsafe assumptions, failure modes, and missing requirements.",
            },
            {
                "step": "5",
                "actor": "Omni",
                "event": "Revision pass completed",
                "description": "Omni revises the final blueprint using the specialist reports and Pluto critique.",
            },
            {
                "step": "6",
                "actor": "QaZ",
                "event": "Validation completed",
                "description": "QaZ validates the revised mission report and artifacts.",
            },
            {
                "step": "7",
                "actor": "Omni",
                "event": "Final package assembled",
                "description": "Omni returns reports, critique, validation, artifacts, state, and export-ready mission data.",
            },
        ]

    # ---------------------------------------------------------
    # Critique and revision
    # ---------------------------------------------------------
    def build_structured_critique(self, mission, critic_output):
        critique_text = self.sanitize_legacy_names(critic_output)
        prompt = f"""
You are Omni converting Pluto's critique into structured JSON.

Mission:
{mission}

Pluto Critique:
{critique_text}

Return ONLY valid JSON using this schema:
{{
  "risk_level": "green | yellow | red",
  "issues_found": ["..."],
  "required_fixes": ["..."],
  "stop_conditions": ["..."],
  "revision_priorities": ["..."]
}}

Rules:
- Do not use markdown.
- Do not include explanations outside JSON.
- Keep each list item short and actionable.
"""
        raw_json = call_llm(prompt, role="Omni")
        parsed = self.parse_json_object(raw_json)

        if parsed:
            return self.sanitize_payload(parsed)

        return {
            "risk_level": "yellow",
            "issues_found": [critique_text[:600]],
            "required_fixes": ["Review Pluto critique manually and convert issues into engineering requirements."],
            "stop_conditions": ["Do not move into hardware testing until safety-critical assumptions are checked."],
            "revision_priorities": ["Revise final blueprint using Pluto critique."],
        }

    def build_revision_prompt(
        self,
        state: MissionState,
        memory_context: str,
        structured_critique: Dict[str, Any],
    ) -> str:
        return f"""
You are Omni, the mission orchestrator.

Your job is to produce the revised final blueprint after reading:
- Omni's initial strategy
- Vega's creative alternatives
- Sky's structured robotics/ROS2 output
- Korva's structured hardware/electronics output
- Isy's structured physics/control output
- Oli's structured CAD/Fusion 360 output
- Pluto's critique
- Structured critique JSON

You must revise the mission output. Do not merely summarize the reports.
You must explicitly incorporate Pluto's critique into the final recommendations.
You must use Vega's ideas only when they are practical enough to validate.

Current Mission:
{state.mission_text}

Relevant Previous Memory:
{memory_context}

Raw Agent Reports:
Omni:
{self.get_agent_raw(state, "omni")}

Vega:
{self.get_agent_raw(state, "vega")}

Pluto:
{self.get_agent_raw(state, "pluto")}

Structured Specialist Outputs:
{json.dumps(state.structured_outputs, indent=2, default=str)}

Structured Critique JSON:
{json.dumps(structured_critique, indent=2, default=str)}

Return your output in this exact markdown format:

# Omni — Revised Final Blueprint

## Mission Summary
Briefly restate what is being built.

## Final System Direction
Describe the recommended system architecture after specialist review.

## Creative Direction Selected
State which Vega concept/direction should be kept, modified, or rejected.

## Key Revisions From Pluto's Critique
List the changes made because of Pluto's critique.

## Recommended Build Order
Give the correct engineering build sequence.

## Required Human Decisions
List what Henry must decide before the next build phase.

## First Artifact To Generate
Choose the single most important next artifact and explain why.

## Safety Gate
State what must be true before hardware, CAD automation, ROS2 code generation, or simulation begins.

## OMNI Final Decision
Give the final go/no-go style decision.
"""

    def revise_final_blueprint(
        self,
        mission,
        memory_context,
        omni_strategy,
        design_report,
        sky_report,
        korva_report,
        isy_report,
        oli_report,
        pluto_report,
        structured_critique,
    ):
        temp_state = MissionState(mission_text=mission)
        temp_state.finish_agent("omni", str(omni_strategy), {"raw_report": omni_strategy})
        temp_state.finish_agent("vega", str(design_report), {"raw_report": design_report})
        temp_state.finish_agent("sky", str(sky_report), {"raw_report": sky_report})
        temp_state.finish_agent("korva", str(korva_report), {"raw_report": korva_report})
        temp_state.finish_agent("isy", str(isy_report), {"raw_report": isy_report})
        temp_state.finish_agent("oli", str(oli_report), {"raw_report": oli_report})
        temp_state.finish_agent("pluto", str(pluto_report), {"raw_report": pluto_report})

        prompt = self.build_revision_prompt(temp_state, memory_context, structured_critique)
        return self.sanitize_legacy_names(call_llm(prompt, role="Omni"))

    def build_revision_payload(self, revised_blueprint, structured_critique):
        return {
            "status": "revised",
            "revised_by": "Omni",
            "based_on": [
                "Vega creative expansion",
                "Sky structured robotics output",
                "Korva structured hardware output",
                "Isy structured feasibility output",
                "Oli structured CAD output",
                "Pluto critique",
                "QaZ validation readiness requirements",
            ],
            "risk_level": structured_critique.get("risk_level", "yellow"),
            "changes_made": structured_critique.get("revision_priorities", []),
            "required_fixes": structured_critique.get("required_fixes", []),
            "final_blueprint": revised_blueprint,
        }

    # ---------------------------------------------------------
    # Validation
    # ---------------------------------------------------------
    def build_validation_input(self, final_report, artifacts, critique_payload, revision_payload):
        return f"""
# Final Mission Report To Validate

{final_report}

---

# Structured Critique To Validate

{json.dumps(critique_payload, indent=2, default=str)}

---

# Revision Payload To Validate

{json.dumps(revision_payload, indent=2, default=str)}

---

# Synthesized Artifacts To Validate

{json.dumps(artifacts, indent=2, default=str)}
"""

    def build_validation_payload(self, validation_report):
        return {
            "verdict": validation_report.verdict,
            "score": validation_report.overall_score,
            "report": self.sanitize_legacy_names(validation_report.to_markdown()),
            "confidence_scores": validation_report.confidence_scores,
            "missing_evidence": validation_report.missing_evidence,
            "required_next_tests": validation_report.required_next_tests,
        }

    def build_validation_fallback(self, error: Exception):
        return {
            "verdict": "warning",
            "score": 0,
            "report": (
                "# QaZ — Engineering Validation Fallback\n\n"
                "QaZ validation failed during execution. Treat this mission as unvalidated "
                "until the validator is fixed and rerun.\n\n"
                f"Technical detail: {type(error).__name__}: {error}"
            ),
            "confidence_scores": {},
            "missing_evidence": [
                "QaZ validation did not complete successfully.",
                "Manual engineering review is required.",
            ],
            "required_next_tests": [
                "Rerun QaZ validation after fixing the validator error.",
                "Do not proceed to hardware testing without validation.",
            ],
        }

    # ---------------------------------------------------------
    # Export metadata
    # ---------------------------------------------------------
    def build_export_manifest(self, mission, result_id):
        folder_name = safe_folder_name(f"{mission}_{result_id}")
        return {
            "folder_name": folder_name,
            "files_to_generate_next": [
                "mission.json",
                "mission_report.md",
                "agent_reports/omni.md",
                "agent_reports/vega.md",
                "agent_reports/sky.md",
                "agent_reports/korva.md",
                "agent_reports/isy.md",
                "agent_reports/oli.md",
                "agent_reports/pluto.md",
                "agent_reports/qaz.md",
                "artifacts/ros2_node_graph.json",
                "artifacts/component_tree.json",
                "artifacts/risk_matrix.csv",
                "artifacts/test_checklist.md",
                "artifacts/approval_gates.md",
                "artifacts/fusion360_concept.json",
                "artifacts/ros2_package_plan.json",
                "artifacts/hardware_architecture.json",
                "artifacts/design_alternatives.json",
                "artifacts/structured_agent_outputs.json",
                "artifacts/mission_state.json",
                "artifacts/export_files.json",
            ],
            "status": "planned",
        }

    # ---------------------------------------------------------
    # Artifacts
    # ---------------------------------------------------------
    def build_state_based_artifacts(self, state: MissionState, mission: str, reason: str) -> Dict[str, Any]:
        sky = state.structured_outputs.get("sky", {})
        isy = state.structured_outputs.get("isy", {})
        oli = state.structured_outputs.get("oli", {})
        korva = state.structured_outputs.get("korva", {})

        sky_ros2_plan = sky.get("ros2_package_plan", {}) if isinstance(sky, dict) else {}

        return {
            "synthesis_status": "state_based",
            "reason": reason,
            "mission": mission,
            "ros2_package_plan": sky_ros2_plan,
            "ros2_node_graph": sky_ros2_plan.get("nodes", []),
            "component_tree": {
                "physics_subsystems": isy.get("major_subsystems", []) if isinstance(isy, dict) else [],
                "cad_layout": oli.get("component_layout", []) if isinstance(oli, dict) else [],
                "hardware_components": korva.get("component_list", []) if isinstance(korva, dict) else [],
            },
            "hardware_architecture": [
                {
                    "owner": "Korva",
                    "summary": korva.get("hardware_architecture_summary", "") if isinstance(korva, dict) else "",
                    "components": korva.get("component_list", []) if isinstance(korva, dict) else [],
                    "wiring_plan": korva.get("wiring_plan", []) if isinstance(korva, dict) else [],
                    "power_assumptions": korva.get("power_assumptions", []) if isinstance(korva, dict) else [],
                }
            ],
            "fusion360_concept": {
                "owner": "Oli",
                "summary": oli.get("cad_direction_summary", "") if isinstance(oli, dict) else "",
                "modeling_plan": oli.get("fusion360_modeling_plan", []) if isinstance(oli, dict) else [],
                "component_layout": oli.get("component_layout", []) if isinstance(oli, dict) else [],
                "fabrication_notes": oli.get("fabrication_notes", []) if isinstance(oli, dict) else [],
            },
            "risk_matrix": {
                "sky": sky.get("implementation_risks", []) if isinstance(sky, dict) else [],
                "isy": isy.get("known_unknowns", []) if isinstance(isy, dict) else [],
                "oli": oli.get("cad_risks", []) if isinstance(oli, dict) else [],
                "korva": korva.get("hardware_risks", []) if isinstance(korva, dict) else [],
            },
            "test_checklist": {
                "sky_tests": sky_ros2_plan.get("tests", []),
                "isy_validation_items": isy.get("validation_items", []) if isinstance(isy, dict) else [],
                "korva_missing_info": korva.get("missing_hardware_information", []) if isinstance(korva, dict) else [],
                "oli_next_artifacts": oli.get("handoff_to_artifact_synthesis", {}).get("next_artifacts", []) if isinstance(oli, dict) else [],
            },
        }

    def run_artifact_synthesis(
        self,
        state: MissionState,
        mission: str,
        omni_strategy: str,
        sky_report: str,
        korva_report: str,
        isy_report: str,
        oli_report: str,
        pluto_report: str,
    ) -> Dict[str, Any]:
        """
        Default behavior avoids the artifact_synthesizer OpenAI call because that
        call previously blocked the whole mission run.

        To re-enable LLM artifact synthesis later:
            export OMNI_USE_LLM_ARTIFACT_SYNTHESIS=1
        """
        use_llm_synthesis = os.getenv("OMNI_USE_LLM_ARTIFACT_SYNTHESIS", "0") == "1"

        if not use_llm_synthesis:
            state.add_warning(
                "Skipped LLM artifact synthesizer. Using state-based artifact synthesis. "
                "Set OMNI_USE_LLM_ARTIFACT_SYNTHESIS=1 to re-enable the old synthesizer."
            )
            return self.build_state_based_artifacts(
                state=state,
                mission=mission,
                reason="LLM artifact synthesizer disabled by default to prevent blocking mission runs.",
            )

        try:
            artifacts = synthesize_artifacts(
                mission=mission,
                omni_output=omni_strategy,
                sky_output=sky_report,
                korva_output=korva_report,
                isy_output=isy_report,
                oli_output=oli_report,
                pluto_output=pluto_report,
            )
            return self.sanitize_payload(artifacts if isinstance(artifacts, dict) else {})

        except Exception as exc:
            state.add_warning(
                "Artifact synthesis failed. Using state-based fallback artifacts. "
                f"Technical detail: {type(exc).__name__}: {exc}"
            )
            return self.build_state_based_artifacts(
                state=state,
                mission=mission,
                reason=f"Artifact synthesizer failed: {type(exc).__name__}: {exc}",
            )

    def enrich_artifacts_from_state(
        self,
        state: MissionState,
        artifacts: Dict[str, Any],
        design_report: str,
        revision_payload: Dict[str, Any],
        export_manifest: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not isinstance(artifacts, dict):
            artifacts = {}

        sky = state.structured_outputs.get("sky", {})
        isy = state.structured_outputs.get("isy", {})
        oli = state.structured_outputs.get("oli", {})
        korva = state.structured_outputs.get("korva", {})
        sky_ros2_plan = sky.get("ros2_package_plan", {}) if isinstance(sky, dict) else {}

        artifacts["structured_agent_outputs"] = {
            "sky": sky,
            "isy": isy,
            "oli": oli,
            "korva": korva,
        }
        artifacts["mission_state_summary"] = {
            "mission_id": getattr(state, "mission_id", None),
            "status": getattr(state, "status", None),
            "structured_agents": list(getattr(state, "structured_outputs", {}).keys()),
            "warnings": getattr(state, "warnings", []),
            "errors": getattr(state, "errors", []),
        }
        try:
            mission_text = getattr(state, "mission_text", "")
            artifacts["mission_intent"] = compile_mission_intent(mission_text)
        except Exception:
            artifacts["mission_intent"] = {"error": "mission intent compilation failed"}
        design_candidates = extract_design_candidates_from_text(design_report)
        artifacts["design_alternatives"] = {
            "owner": "Vega",
            "content": design_report,
            "candidates": design_candidates,
        }
        artifacts["design_candidates"] = design_candidates
        if design_candidates:
            try:
                mission_text = getattr(state, "mission_text", "")
                artifacts["candidate_evaluation"] = evaluate_design_candidates(
                    design_candidates, mission_text=mission_text
                )
            except Exception:
                artifacts["candidate_evaluation"] = {"candidates_evaluated": 0, "error": "evaluation failed"}
        artifacts["revision_summary"] = revision_payload
        artifacts["export_manifest"] = export_manifest

        artifacts.setdefault("ros2_package_plan", sky_ros2_plan)
        artifacts.setdefault("ros2_node_graph", sky_ros2_plan.get("nodes", []))
        artifacts.setdefault(
            "component_tree",
            {
                "physics_subsystems": isy.get("major_subsystems", []) if isinstance(isy, dict) else [],
                "cad_layout": oli.get("component_layout", []) if isinstance(oli, dict) else [],
                "hardware_components": korva.get("component_list", []) if isinstance(korva, dict) else [],
            },
        )
        artifacts.setdefault(
            "fusion360_concept",
            {
                "owner": "Oli",
                "cad_direction_summary": oli.get("cad_direction_summary", "") if isinstance(oli, dict) else "",
                "fusion360_modeling_plan": oli.get("fusion360_modeling_plan", []) if isinstance(oli, dict) else [],
                "component_layout": oli.get("component_layout", []) if isinstance(oli, dict) else [],
                "fabrication_notes": oli.get("fabrication_notes", []) if isinstance(oli, dict) else [],
            },
        )
        artifacts.setdefault(
            "hardware_architecture",
            [
                {
                    "subsystem": "Hardware Architecture",
                    "components": korva.get("component_list", []) if isinstance(korva, dict) else [],
                    "power_or_signal_notes": korva.get("power_assumptions", []) if isinstance(korva, dict) else [],
                    "interfaces": korva.get("communication_buses", []) if isinstance(korva, dict) else [],
                    "wiring_plan": korva.get("wiring_plan", []) if isinstance(korva, dict) else [],
                    "owner": "Korva",
                }
            ],
        )
        artifacts.setdefault(
            "risk_matrix",
            {
                "sky_implementation_risks": sky.get("implementation_risks", []) if isinstance(sky, dict) else [],
                "korva_hardware_risks": korva.get("hardware_risks", []) if isinstance(korva, dict) else [],
                "isy_known_unknowns": isy.get("known_unknowns", []) if isinstance(isy, dict) else [],
                "oli_cad_risks": oli.get("cad_risks", []) if isinstance(oli, dict) else [],
            },
        )
        artifacts.setdefault(
            "test_checklist",
            {
                "sky_tests": sky_ros2_plan.get("tests", []),
                "isy_validation_items": isy.get("validation_items", []) if isinstance(isy, dict) else [],
                "korva_missing_info": korva.get("missing_hardware_information", []) if isinstance(korva, dict) else [],
                "oli_next_artifacts": oli.get("handoff_to_artifact_synthesis", {}).get("next_artifacts", []) if isinstance(oli, dict) else [],
            },
        )
        return self.sanitize_payload(artifacts)

    # ---------------------------------------------------------
    # Parallel specialist runner (Phase 4A)
    # ---------------------------------------------------------
    def _run_specialists_parallel(
        self,
        state: MissionState,
        memory_context: str,
    ) -> Tuple[str, str, str, str]:
        """
        Run Sky, Isy, Oli, Korva concurrently.

        Invariants enforced here:
        - All prompts are built on the main thread before any worker starts
          (frozen state snapshot — workers never read state).
        - Worker threads only return raw strings or raise; they never touch state.
        - All state mutations (start_agent, finish_agent, fail_agent) happen on
          the main thread in deterministic order: sky → isy → oli → korva.

        Returns (sky_report, isy_report, oli_report, korva_report).
        """
        _TIMEOUT = 300  # seconds; one hanging specialist will not block indefinitely

        # Build all prompts before any thread starts.
        _SPECIALISTS: List[Tuple] = [
            (
                "sky", "Sky", "robotics_software_architecture",
                self.build_sky_prompt(state, memory_context),
                self.robotics_agent.run,
                "Sky could not generate a robotics/ROS2 structured report.",
            ),
            (
                "isy", "Isy", "physics_controls_feasibility",
                self.build_isy_prompt(state, memory_context),
                self.research_agent.run,
                "Isy could not generate a physics/controls/feasibility structured report.",
            ),
            (
                "oli", "Oli", "cad_visual_artifacts",
                self.build_oli_prompt(state, memory_context),
                self.code_agent.run,
                "Oli could not generate a CAD/Fusion 360 structured report.",
            ),
            (
                "korva", "Korva", "hardware_electronics_embedded",
                self.build_korva_prompt(state, memory_context),
                lambda p: call_llm(p, role="Korva"),
                "Korva could not generate a hardware/electronics structured report.",
            ),
        ]

        print(f"[{self.name}] Parallel specialists: sky, isy, oli, korva")

        # Worker: pure function — returns raw string, never touches state.
        def _worker(prompt: str, runner: Callable) -> str:
            raw = runner(prompt)
            return self.sanitize_payload(raw if raw is not None else "")

        # Submit all four concurrently.
        with ThreadPoolExecutor(max_workers=4) as pool:
            future_map: Dict = {
                pool.submit(_worker, prompt, runner): i
                for i, (_, _, _, prompt, runner, _) in enumerate(_SPECIALISTS)
            }
            done, not_done = _futures_wait(future_map, timeout=_TIMEOUT)
            for fut in not_done:
                fut.cancel()

        # Collect raw results indexed by order position.
        raw_results: Dict[int, Any] = {}
        for fut, i in future_map.items():
            if fut in not_done:
                raw_results[i] = TimeoutError(
                    f"{_SPECIALISTS[i][0]} timed out after {_TIMEOUT}s"
                )
            elif fut.exception() is not None:
                raw_results[i] = fut.exception()
            else:
                raw_results[i] = fut.result()

        # Deterministic merge on the main thread: sky → isy → oli → korva.
        reports: List[str] = []
        for i, (agent_id, agent_name, role, _, _, fallback_message) in enumerate(_SPECIALISTS):
            result = raw_results.get(i, RuntimeError(f"{agent_id}: no result collected"))

            if isinstance(result, BaseException):
                error_message = f"{type(result).__name__}: {result}"
                print(
                    f"[{self.name}] Parallel specialist {agent_id} failed: {error_message}",
                    file=sys.stderr,
                )
                fallback_raw = self.sanitize_legacy_names(
                    f"# {agent_name} — Error / Fallback\n\n"
                    f"{fallback_message}\n\n"
                    f"Technical detail: {error_message}"
                )
                fallback_parsed = {
                    "agent_id": agent_id,
                    "role": role,
                    "status": "error_fallback",
                    "content": {"raw_report": fallback_raw},
                    "errors": [error_message],
                    "warnings": [
                        "This step failed during parallel execution. "
                        "OMNI continued with fallback output."
                    ],
                }
                state.start_agent(agent_id=agent_id, agent_name=agent_name)
                try:
                    state.fail_agent(
                        agent_id=agent_id,
                        error=error_message,
                        raw_output=fallback_raw,
                    )
                    state.structured_outputs[agent_id] = fallback_parsed
                except Exception:
                    pass
                log_agent_failed(state, agent_id, error_message)
                reports.append(fallback_raw)

            else:
                raw = str(result)
                parsed = self.parse_structured_agent_output(raw, state, agent_id, role)
                state.start_agent(agent_id=agent_id, agent_name=agent_name)
                state.finish_agent(agent_id=agent_id, raw_output=raw, parsed_output=parsed)
                log_agent_finished(state, agent_id, parsed)
                reports.append(raw)

        return tuple(reports)  # (sky_report, isy_report, oli_report, korva_report)

    # ---------------------------------------------------------
    # Main pipeline
    # ---------------------------------------------------------
    def run_mission_structured(self, mission, use_parallel_specialists: bool = False):
        print(f"\n[{self.name}] Mission received.")
        print(f"[{self.name}] Deploying OMNI council...\n")

        state = MissionState(mission_text=mission)
        state.set_status("running")

        created_at = getattr(state, "created_at", datetime.now().isoformat())
        result_id = str(getattr(state, "mission_id", created_at)).replace(":", "-").replace(".", "-")
        export_manifest = self.build_export_manifest(mission, result_id)
        memory_context = get_recent_memory()

        state.metadata["created_at"] = created_at
        state.metadata["result_id"] = result_id
        state.metadata["export_manifest"] = export_manifest
        state.metadata["memory_used"] = memory_context

        log_mission_started(state)

        # 1. Omni strategy.
        omni_strategy, _ = self.run_state_step(
            state=state,
            agent_id="omni",
            agent_name="Omni",
            role="mission_strategy",
            prompt_builder=lambda s: self.build_omni_strategy_prompt(s, memory_context),
            runner=lambda prompt: call_llm(prompt, role="Omni"),
            parser=lambda raw, s: self.parse_text_agent_output(raw, s, "omni", "mission_strategy"),
            fallback_message="Omni could not generate a strategy. Continue with direct specialist review.",
        )

        # 2. Vega creative expansion.
        design_report, _ = self.run_state_step(
            state=state,
            agent_id="vega",
            agent_name="Vega",
            role="creative_design_expansion",
            prompt_builder=lambda s: self.build_vega_prompt(s, memory_context),
            runner=lambda prompt: self.design_agent.run(prompt),
            parser=lambda raw, s: self.parse_text_agent_output(raw, s, "vega", "creative_design_expansion"),
            fallback_message="Vega could not generate creative alternatives. Continue with standard practical design assumptions.",
        )

        # 3. Structured specialist agents.
        if use_parallel_specialists:
            sky_report, isy_report, oli_report, korva_report = (
                self._run_specialists_parallel(state, memory_context)
            )
        else:
            sky_report, _ = self.run_state_step(
                state=state,
                agent_id="sky",
                agent_name="Sky",
                role="robotics_software_architecture",
                prompt_builder=lambda s: self.build_sky_prompt(s, memory_context),
                runner=lambda prompt: self.robotics_agent.run(prompt),
                parser=lambda raw, s: self.parse_structured_agent_output(raw, s, "sky", "robotics_software_architecture"),
                fallback_message="Sky could not generate a robotics/ROS2 structured report.",
            )

            isy_report, _ = self.run_state_step(
                state=state,
                agent_id="isy",
                agent_name="Isy",
                role="physics_controls_feasibility",
                prompt_builder=lambda s: self.build_isy_prompt(s, memory_context),
                runner=lambda prompt: self.research_agent.run(prompt),
                parser=lambda raw, s: self.parse_structured_agent_output(raw, s, "isy", "physics_controls_feasibility"),
                fallback_message="Isy could not generate a physics/controls/feasibility structured report.",
            )

            oli_report, _ = self.run_state_step(
                state=state,
                agent_id="oli",
                agent_name="Oli",
                role="cad_visual_artifacts",
                prompt_builder=lambda s: self.build_oli_prompt(s, memory_context),
                runner=lambda prompt: self.code_agent.run(prompt),
                parser=lambda raw, s: self.parse_structured_agent_output(raw, s, "oli", "cad_visual_artifacts"),
                fallback_message="Oli could not generate a CAD/Fusion 360 structured report.",
            )

            korva_report, _ = self.run_state_step(
                state=state,
                agent_id="korva",
                agent_name="Korva",
                role="hardware_electronics_embedded",
                prompt_builder=lambda s: self.build_korva_prompt(s, memory_context),
                runner=lambda prompt: call_llm(prompt, role="Korva"),
                parser=lambda raw, s: self.parse_structured_agent_output(raw, s, "korva", "hardware_electronics_embedded"),
                fallback_message="Korva could not generate a hardware/electronics structured report.",
            )

        # 4. Pluto critique.
        pluto_report, _ = self.run_state_step(
            state=state,
            agent_id="pluto",
            agent_name="Pluto",
            role="risk_failure_safety_review",
            prompt_builder=lambda s: self.build_pluto_combined_outputs(s),
            runner=lambda combined_outputs: self.critic_agent.run(
                self.build_pluto_context(state, memory_context),
                combined_outputs,
            ),
            parser=lambda raw, s: self.parse_text_agent_output(raw, s, "pluto", "risk_failure_safety_review"),
            fallback_message="Pluto could not generate a risk critique. Treat mission as yellow-risk until manually reviewed.",
        )

        # 5. Structured critique.
        critique_payload = self.safe_agent_run(
            "Critique JSON Builder",
            lambda: self.build_structured_critique(mission=mission, critic_output=pluto_report),
            "Could not structure Pluto critique.",
        )

        if not isinstance(critique_payload, dict):
            critique_payload = {
                "risk_level": "yellow",
                "issues_found": ["Critique could not be converted into structured JSON."],
                "required_fixes": ["Manually review Pluto critique."],
                "stop_conditions": ["Do not perform hardware tests without manual review."],
                "revision_priorities": ["Convert critique into explicit requirements."],
            }

        state.structured_outputs["critique"] = critique_payload

        # 6. Omni revision.
        revised_blueprint, _ = self.run_state_step(
            state=state,
            agent_id="omni_revision",
            agent_name="Omni Revision",
            role="revised_final_blueprint",
            prompt_builder=lambda s: self.build_revision_prompt(s, memory_context, critique_payload),
            runner=lambda prompt: call_llm(prompt, role="Omni"),
            parser=lambda raw, s: self.parse_text_agent_output(raw, s, "omni_revision", "revised_final_blueprint"),
            fallback_message="Omni could not generate a revised blueprint. Use agent reports and Pluto critique as the decision basis.",
        )

        revision_payload = self.build_revision_payload(revised_blueprint, critique_payload)
        state.structured_outputs["revision"] = revision_payload

        # 7. Artifact synthesis.
        state.set_status("synthesizing")
        log_synthesis_started(state)
        state.build_synthesis_input()

        artifacts = self.run_artifact_synthesis(
            state=state,
            mission=mission,
            omni_strategy=omni_strategy,
            sky_report=sky_report,
            korva_report=korva_report,
            isy_report=isy_report,
            oli_report=oli_report,
            pluto_report=pluto_report,
        )

        artifacts = self.enrich_artifacts_from_state(
            state=state,
            artifacts=artifacts,
            design_report=design_report,
            revision_payload=revision_payload,
            export_manifest=export_manifest,
        )

        state.synthesized_artifacts = artifacts
        log_synthesis_finished(state, artifact_keys=list(artifacts.keys()) if isinstance(artifacts, dict) else [])

        # 8. Build final report before QaZ validation.
        final_report = f"""
# OMNI Mission Report

## Mission
{mission}

---

## Omni — Mission Strategy / System Integration
{omni_strategy}

---

## Vega — Creative Design Expansion
{design_report}

---

## Sky — Robotics / ROS2 / Autonomy
{sky_report}

---

## Korva — Hardware / Electronics / Embedded Systems
{korva_report}

---

## Isy — Physics / Controls / Dynamics
{isy_report}

---

## Oli — CAD / Fusion 360 / Visual Artifacts
{oli_report}

---

## Pluto — Failure / Safety / Risk Critique
{pluto_report}

---

## Omni — Revised Final Blueprint
{revised_blueprint}
"""
        final_report = self.sanitize_legacy_names(final_report)

        # 9. QaZ validation.
        validation_input = self.build_validation_input(
            final_report=final_report,
            artifacts=artifacts,
            critique_payload=critique_payload,
            revision_payload=revision_payload,
        )

        try:
            state.start_agent(agent_id="qaz", agent_name="QaZ")
            log_agent_started(state, "qaz")

            validation_report = self.validator_agent.validate(
                mission=mission,
                artifact_text=validation_input,
                artifact_type="robotics_design",
            )
            validation_payload = self.build_validation_payload(validation_report)

            state.finish_agent(
                agent_id="qaz",
                raw_output=validation_payload["report"],
                parsed_output=validation_payload,
            )
            log_agent_finished(state, "qaz", validation_payload)

        except Exception as error:
            validation_payload = self.build_validation_fallback(error)
            try:
                state.fail_agent(
                    agent_id="qaz",
                    error=f"{type(error).__name__}: {error}",
                    raw_output=validation_payload["report"],
                )
                state.structured_outputs["qaz"] = validation_payload
            except Exception:
                pass
            log_agent_failed(state, "qaz", f"{type(error).__name__}: {error}")

        # 10. Final report with validation.
        final_report_with_validation = f"""
{final_report}

---

## QaZ — Engineering Validation Report

{validation_payload["report"]}
"""
        final_report_with_validation = self.sanitize_legacy_names(final_report_with_validation)

        # 11. Save memory summary.
        memory_summary = f"""
Omni: {str(omni_strategy)[:500]}

Vega: {str(design_report)[:500]}

Sky Structured Status: {state.structured_outputs.get("sky", {}).get("status", "unknown")}
Sky: {str(sky_report)[:500]}

Korva Structured Status: {state.structured_outputs.get("korva", {}).get("status", "unknown")}
Korva: {str(korva_report)[:500]}

Isy Structured Status: {state.structured_outputs.get("isy", {}).get("status", "unknown")}
Isy: {str(isy_report)[:500]}

Oli Structured Status: {state.structured_outputs.get("oli", {}).get("status", "unknown")}
Oli: {str(oli_report)[:500]}

Pluto: {str(pluto_report)[:500]}

Revision Risk Level: {critique_payload.get("risk_level", "yellow")}
Revision Required Fixes: {critique_payload.get("required_fixes", [])[:5]}

QaZ Validation Verdict: {validation_payload.get("verdict", "unknown")}
QaZ Score: {validation_payload.get("score", "unknown")}/10
QaZ Missing Evidence: {validation_payload.get("missing_evidence", [])[:5]}
QaZ Required Next Tests: {validation_payload.get("required_next_tests", [])[:5]}
"""
        try:
            add_mission_to_memory(mission, self.sanitize_legacy_names(memory_summary))
        except Exception as exc:
            state.add_warning(f"Memory write failed: {type(exc).__name__}: {exc}")

        # 12. Return structured payload for frontend/dashboard.
        state.set_status("complete")
        log_mission_finished(state)

        result = {
            "mission": mission,
            "mission_id": getattr(state, "mission_id", result_id),
            "created_at": created_at,
            "result_id": result_id,
            "memory_used": self.sanitize_legacy_names(memory_context),
            "agent_council": self.build_agent_council(),
            "council_events": self.build_council_events(),
            "agents": {
                "omni": omni_strategy,
                "vega": design_report,
                "sky": sky_report,
                "korva": korva_report,
                "isy": isy_report,
                "oli": oli_report,
                "pluto": pluto_report,
                "qaz": validation_payload["report"],
            },
            "structured_agent_outputs": {
                "sky": state.structured_outputs.get("sky", {}),
                "isy": state.structured_outputs.get("isy", {}),
                "oli": state.structured_outputs.get("oli", {}),
                "korva": state.structured_outputs.get("korva", {}),
            },
            "mission_state": self.state_to_dict(state),
            "critique": critique_payload,
            "revision": revision_payload,
            "final_decision": revised_blueprint,
            "final_report": final_report_with_validation,
            "artifacts": artifacts,
            "validation": validation_payload,
            "export_manifest": export_manifest,
            "timeline": self.build_council_events(),
            "telemetry": {
                "enabled": True,
                "path": "logs/telemetry/mission_runs.jsonl",
            },
            "status": "complete",
        }

        return self.sanitize_payload(result)

    def run_mission(self, mission):
        return self.run_mission_structured(mission)

    def run(self, mission):
        return self.run_mission_structured(mission)

    def run_mission_text_only(self, mission):
        structured_result = self.run_mission_structured(mission)
        return structured_result["final_report"]
