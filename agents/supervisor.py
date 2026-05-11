import json
from datetime import datetime
from typing import Any, Dict

from agents.robotics_agent import RoboticsAgent
from agents.research_agent import ResearchAgent
from agents.code_agent import CodeAgent
from agents.critic_agent import CriticAgent
from agents.design_agent import DesignAgent
from agents.artifact_synthesizer import synthesize_artifacts
from backend.app.omni_core.llm_router import call_llm
from agents.validator_agent import ValidatorAgent

from backend.app.omni_core.formatters import (
    compact_context as format_compact_context,
    safe_folder_name,
    sanitize_legacy_names as format_sanitize_legacy_names,
    sanitize_payload as format_sanitize_payload,
)

from memory.memory_manager import get_recent_memory, add_mission_to_memory


class SupervisorAgent:
    def __init__(self):
        self.name = "Omni"

        # Frontend-facing OMNI identities:
        # Omni -> mission orchestration and final system integration
        # Vega -> creative design expansion and morphology exploration
        # Sky -> robotics, ROS2, autonomy, drones, software architecture
        # Korva -> electronics, embedded systems, wiring, PCB, hardware architecture
        # Isy -> physics, controls, dynamics, feasibility
        # Oli -> CAD, Fusion 360, 3D concepts, visual artifacts
        # Pluto -> risk, failure analysis, safety gates
        # QaZ -> validation, scoring, requirements verification
        self.design_agent = DesignAgent()
        self.robotics_agent = RoboticsAgent()
        self.research_agent = ResearchAgent()
        self.code_agent = CodeAgent()
        self.critic_agent = CriticAgent()
        self.validator_agent = ValidatorAgent()

    # ---------------------------------------------------------
    # Shared formatting / sanitation wrappers
    # ---------------------------------------------------------
    def sanitize_legacy_names(self, text: Any) -> Any:
        """
        Compatibility wrapper.

        The real implementation now lives in:
        backend.app.omni_core.formatters
        """
        return format_sanitize_legacy_names(text)

    def sanitize_payload(self, payload: Any) -> Any:
        """
        Recursively sanitize strings in dicts/lists using the centralized formatter.
        """
        return format_sanitize_payload(payload)

    def compact_context(self, text: Any, limit: int = 9000) -> str:
        """
        Prevent later prompts from becoming massive after large agent outputs.
        """
        return format_compact_context(text, limit=limit)

    def safe_agent_run(self, agent_label, fn, fallback_message):
        """
        Keeps the mission pipeline from crashing if one external model
        or agent call fails. The frontend still gets a complete structured result.
        """
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

    def parse_json_object(self, raw_text: Any) -> Dict[str, Any]:
        """
        Parse a JSON object from an LLM response.

        Handles both clean JSON and occasional fenced JSON output.
        """
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

    # ---------------------------------------------------------
    # Mission planning
    # ---------------------------------------------------------
    def run_omni_strategy(self, mission, memory_context):
        omni_prompt = f"""
You are Omni, the system orchestrator inside an engineering AI command system.

You are not a fictional superhero.
You are not Reed Richards.
You are the mission-level intelligence responsible for coordinating specialist agents.

Your specialty is ONLY:
- mission strategy
- system-level priorities
- build phases
- decision gates
- human approval checkpoints
- how specialist outputs should connect
- what should become a visual artifact in the dashboard

Do NOT focus on:
- detailed ROS2 code
- deep physics derivations
- CAD blueprint details
- failure critique unless it affects mission strategy

Current Mission:
{mission}

Relevant Previous Memory:
{memory_context}

Use the following OMNI agent names:
- Omni: mission orchestration and system integration
- Vega: creative design expansion, morphology, and unconventional concept alternatives
- Sky: robotics, ROS2, drones, autonomy, software architecture
- Korva: electronics, embedded systems, wiring, PCB, hardware architecture
- Isy: physics, controls, dynamics, feasibility
- Oli: CAD, Fusion 360, 3D concepts, visual artifacts
- Pluto: risk, failure analysis, safety gates
- QaZ: validation, scoring, requirements verification

Return your output in this exact format:

# Omni — Mission Strategy / System Integration

## Mission Objective
Define the mission in one clear engineering objective.

## System Priorities
List the top 3-5 priorities for this mission.

## Build Phases
Break the mission into phases:
1. Concept
2. Prototype
3. Simulation
4. Validation
5. Human Approval
6. Next Mission

## Human Approval Gates
List what Henry must approve before moving forward.

## Specialist Assignments
Explain what Vega, Sky, Korva, Isy, Oli, Pluto, and QaZ should each produce.

## Dashboard Artifacts Needed
List the visual artifacts the OMNI dashboard should generate.

## Omni's Initial Strategic Recommendation
Give the next best action before specialist work begins.
"""
        return self.sanitize_legacy_names(call_llm(omni_prompt, role="Omni"))

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
                "responsibility": "Defines the mission strategy, connects specialist outputs, and produces the revised final blueprint.",
            },
            {
                "id": "vega",
                "name": "Vega",
                "role": "Creative Design Expansion / Morphology Exploration",
                "color": "violet",
                "responsibility": "Generates unconventional but physically plausible design alternatives before the engineering agents produce structured outputs.",
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
                "responsibility": "Scores the mission output, identifies missing evidence, and recommends next validation tests.",
            },
        ]

    def build_council_events(self):
        return [
            {
                "step": "1",
                "actor": "Omni",
                "event": "Mission strategy created",
                "description": "Omni converts the user mission into system priorities, build phases, and specialist assignments.",
            },
            {
                "step": "2",
                "actor": "Vega",
                "event": "Creative design alternatives generated",
                "description": "Vega expands the mission into unconventional but physically plausible morphology and design options.",
            },
            {
                "step": "3",
                "actor": "Sky / Korva / Isy / Oli",
                "event": "Specialist drafts generated",
                "description": "Core engineering agents generate first-pass domain reports using Omni strategy and Vega design context.",
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
                "description": "Omni returns reports, critique, validation, artifacts, and export-ready mission data.",
            },
        ]

    # ---------------------------------------------------------
    # Korva hardware report
    # ---------------------------------------------------------
    def run_korva_hardware_report(self, mission, memory_context, omni_strategy, design_report=""):
        """
        Temporary Korva implementation until we create agents/hardware_agent.py.
        """
        korva_prompt = f"""
You are Korva, the hardware, electronics, embedded systems, wiring, and PCB intelligence inside OMNI.

You are not a fictional superhero.
You are an engineering specialist focused on practical electronics and hardware integration.

Current Mission:
{mission}

Relevant Previous Memory:
{memory_context}

Omni Strategy:
{omni_strategy}

Vega Design Context:
{design_report}

Return your output in this exact format:

# Korva — Hardware / Electronics / Embedded Systems

## Hardware Architecture
Describe the main electronics architecture.

## Component List
List the likely components and their role.

## Wiring Plan
Describe power wiring, signal wiring, sensor connections, actuator connections, and communication buses.

## Power Assumptions
List voltage, current, battery, adapter, or regulator assumptions that must be checked.

## Embedded Systems Notes
Explain what microcontroller, Raspberry Pi, GPIO, serial, I2C, SPI, PWM, or USB considerations matter.

## PCB / Prototyping Direction
Explain whether this should begin on breadboard, perfboard, custom PCB, or modular wiring.

## Hardware Risks
List hardware-specific risks.

## Missing Hardware Information
List what Henry still needs to measure, choose, or confirm.
"""
        return self.sanitize_legacy_names(call_llm(korva_prompt, role="Korva"))

    # ---------------------------------------------------------
    # Critique normalization
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
            "required_fixes": [
                "Review Pluto critique manually and convert issues into engineering requirements."
            ],
            "stop_conditions": [
                "Do not move into hardware testing until safety-critical assumptions are checked."
            ],
            "revision_priorities": [
                "Revise final blueprint using Pluto critique."
            ],
        }

    # ---------------------------------------------------------
    # Revision loop
    # ---------------------------------------------------------
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
        critique_json = json.dumps(structured_critique, indent=2, default=str)

        revision_prompt = f"""
You are Omni, the mission orchestrator.

Your job is to produce the revised final blueprint after reading:
- Omni's initial strategy
- Vega's creative alternatives
- Sky's robotics/ROS2 report
- Korva's hardware/electronics report
- Isy's physics/control report
- Oli's CAD/Fusion 360 report
- Pluto's critique
- Structured critique JSON

You must revise the mission output. Do not merely summarize the reports.
You must explicitly incorporate Pluto's critique into the final recommendations.
You must use Vega's ideas only when they are practical enough to validate.

Current Mission:
{mission}

Relevant Previous Memory:
{memory_context}

Omni Initial Strategy:
{omni_strategy}

Vega Creative Expansion:
{design_report}

Sky Report:
{sky_report}

Korva Report:
{korva_report}

Isy Report:
{isy_report}

Oli Report:
{oli_report}

Pluto Critique:
{pluto_report}

Structured Critique JSON:
{critique_json}

Return your output in this exact format:

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
        return self.sanitize_legacy_names(call_llm(revision_prompt, role="Omni"))

    def build_revision_payload(self, revised_blueprint, structured_critique):
        return {
            "status": "revised",
            "revised_by": "Omni",
            "based_on": [
                "Vega creative expansion",
                "Sky report",
                "Korva report",
                "Isy report",
                "Oli report",
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
        try:
            artifacts_text = json.dumps(artifacts, indent=2, default=str)
        except Exception:
            artifacts_text = str(artifacts)

        try:
            critique_text = json.dumps(critique_payload, indent=2, default=str)
        except Exception:
            critique_text = str(critique_payload)

        try:
            revision_text = json.dumps(revision_payload, indent=2, default=str)
        except Exception:
            revision_text = str(revision_payload)

        return f"""
# Final Mission Report To Validate

{final_report}

---

# Structured Critique To Validate

{critique_text}

---

# Revision Payload To Validate

{revision_text}

---

# Synthesized Artifacts To Validate

{artifacts_text}
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
                "artifacts/export_files.json",
            ],
            "status": "planned",
        }

    # ---------------------------------------------------------
    # Main pipeline
    # ---------------------------------------------------------
    def run_mission_structured(self, mission):
        print(f"\n[{self.name}] Mission received.")
        print(f"[{self.name}] Deploying OMNI council...\n")

        created_at = datetime.now().isoformat()
        result_id = created_at.replace(":", "-").replace(".", "-")
        export_manifest = self.build_export_manifest(mission, result_id)

        memory_context = get_recent_memory()

        mission_with_memory = f"""
Current Mission:
{mission}

Relevant Previous Memory:
{memory_context}
"""

        # 1. Omni creates mission strategy.
        omni_strategy = self.safe_agent_run(
            "Omni",
            lambda: self.run_omni_strategy(mission, memory_context),
            "Omni could not generate a strategy. Continue with direct specialist review.",
        )

        # 2. Vega creates creative alternatives before specialists run.
        design_input = f"""
{mission_with_memory}

Omni Strategy:
{omni_strategy}
"""
        design_report = self.safe_agent_run(
            "Vega",
            lambda: self.design_agent.run(design_input),
            "Vega could not generate creative alternatives. Continue with standard practical design assumptions.",
        )

        # Keep specialist context useful, but avoid runaway prompt size.
        mission_with_design_context = self.compact_context(
            f"""
{mission_with_memory}

Omni Strategy:
{omni_strategy}

Vega Creative Expansion:
{design_report}
""",
            limit=12000,
        )

        # 3. Specialist agents generate first-pass domain outputs.
        sky_report = self.safe_agent_run(
            "Sky",
            lambda: self.robotics_agent.run(mission_with_design_context),
            "Sky could not generate a robotics/ROS2 report.",
        )

        isy_report = self.safe_agent_run(
            "Isy",
            lambda: self.research_agent.run(mission_with_design_context),
            "Isy could not generate a physics/controls/feasibility report.",
        )

        oli_report = self.safe_agent_run(
            "Oli",
            lambda: self.code_agent.run(mission_with_design_context),
            "Oli could not generate a CAD/code/artifact report.",
        )

        # 4. Korva hardware report.
        korva_report = self.safe_agent_run(
            "Korva",
            lambda: self.run_korva_hardware_report(
                mission=mission,
                memory_context=memory_context,
                omni_strategy=omni_strategy,
                design_report=design_report,
            ),
            "Korva could not generate a hardware/electronics report.",
        )

        # 5. Combine outputs for Pluto critique.
        combined_outputs = self.compact_context(
            f"""
Omni Strategy:
{omni_strategy}

Vega Creative Expansion:
{design_report}

Sky Report:
{sky_report}

Korva Report:
{korva_report}

Isy Report:
{isy_report}

Oli Report:
{oli_report}
""",
            limit=18000,
        )

        # 6. Pluto performs failure/risk critique.
        pluto_report = self.safe_agent_run(
            "Pluto",
            lambda: self.critic_agent.run(mission_with_design_context, combined_outputs),
            "Pluto could not generate a risk critique. Treat mission as yellow-risk until manually reviewed.",
        )

        # 7. Convert Pluto critique into structured JSON.
        critique_payload = self.safe_agent_run(
            "Critique JSON Builder",
            lambda: self.build_structured_critique(
                mission=mission,
                critic_output=pluto_report,
            ),
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

        # 8. Omni revises final blueprint using Pluto critique and Vega design context.
        revised_blueprint = self.safe_agent_run(
            "Omni Revision",
            lambda: self.revise_final_blueprint(
                mission=mission,
                memory_context=memory_context,
                omni_strategy=omni_strategy,
                design_report=design_report,
                sky_report=sky_report,
                korva_report=korva_report,
                isy_report=isy_report,
                oli_report=oli_report,
                pluto_report=pluto_report,
                structured_critique=critique_payload,
            ),
            "Omni could not generate a revised blueprint. Use agent reports and Pluto critique as the decision basis.",
        )

        revision_payload = self.build_revision_payload(
            revised_blueprint=revised_blueprint,
            structured_critique=critique_payload,
        )

        # 9. Artifact synthesizer creates dashboard-ready and export-ready artifacts.
        artifacts = synthesize_artifacts(
            mission=mission,
            omni_output=omni_strategy,
            sky_output=sky_report,
            korva_output=korva_report,
            isy_output=isy_report,
            oli_output=oli_report,
            pluto_output=pluto_report,
        )

        artifacts = self.sanitize_payload(artifacts)

        # 10. Add design/revision/export planning without breaking existing artifact schema.
        if not isinstance(artifacts, dict):
            artifacts = {}

        artifacts["design_alternatives"] = {
            "owner": "Vega",
            "content": design_report,
        }
        artifacts["revision_summary"] = revision_payload
        artifacts["export_manifest"] = export_manifest

        if "hardware_architecture" not in artifacts or not artifacts["hardware_architecture"]:
            artifacts["hardware_architecture"] = [
                {
                    "subsystem": "Hardware Architecture",
                    "components": [],
                    "power_or_signal_notes": korva_report,
                    "interfaces": ["unknown"],
                    "owner": "Korva",
                }
            ]

        # 11. Build final report before QaZ validation.
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

        # 12. QaZ validates revised report + artifacts.
        validation_input = self.build_validation_input(
            final_report=final_report,
            artifacts=artifacts,
            critique_payload=critique_payload,
            revision_payload=revision_payload,
        )

        try:
            validation_report = self.validator_agent.validate(
                mission=mission,
                artifact_text=validation_input,
                artifact_type="robotics_design",
            )
            validation_payload = self.build_validation_payload(validation_report)

        except Exception as error:
            validation_payload = self.build_validation_fallback(error)

        # 13. Attach QaZ validation to final report.
        final_report_with_validation = f"""
{final_report}

---

## QaZ — Engineering Validation Report

{validation_payload["report"]}
"""

        final_report_with_validation = self.sanitize_legacy_names(
            final_report_with_validation
        )

        # 14. Save memory summary.
        memory_summary = f"""
Omni: {str(omni_strategy)[:500]}

Vega: {str(design_report)[:500]}

Sky: {str(sky_report)[:500]}

Korva: {str(korva_report)[:500]}

Isy: {str(isy_report)[:500]}

Oli: {str(oli_report)[:500]}

Pluto: {str(pluto_report)[:500]}

Revision Risk Level: {critique_payload.get("risk_level", "yellow")}
Revision Required Fixes: {critique_payload.get("required_fixes", [])[:5]}

QaZ Validation Verdict: {validation_payload.get("verdict", "unknown")}
QaZ Score: {validation_payload.get("score", "unknown")}/10
QaZ Missing Evidence: {validation_payload.get("missing_evidence", [])[:5]}
QaZ Required Next Tests: {validation_payload.get("required_next_tests", [])[:5]}
"""

        add_mission_to_memory(mission, self.sanitize_legacy_names(memory_summary))

        # 15. Return structured payload for frontend/dashboard.
        result = {
            "mission": mission,
            "created_at": created_at,
            "result_id": result_id,
            "memory_used": self.sanitize_legacy_names(memory_context),
            "agent_council": self.build_agent_council(),
            "council_events": self.build_council_events(),

            # OMNI-native agent keys only.
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

            "critique": critique_payload,
            "revision": revision_payload,
            "final_decision": revised_blueprint,
            "final_report": final_report_with_validation,
            "artifacts": artifacts,
            "validation": validation_payload,
            "export_manifest": export_manifest,
            "timeline": self.build_council_events(),
            "status": "complete",
        }

        return self.sanitize_payload(result)

    def run_mission(self, mission):
        """
        Main method used by backend routes.
        Returns the full structured result.
        """
        return self.run_mission_structured(mission)

    def run(self, mission):
        """
        Compatibility alias for backend code that calls supervisor.run().
        """
        return self.run_mission_structured(mission)

    def run_mission_text_only(self, mission):
        """
        Legacy method for scripts that only expect plain text.
        """
        structured_result = self.run_mission_structured(mission)
        return structured_result["final_report"]