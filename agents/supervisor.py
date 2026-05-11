import json
from datetime import datetime

from agents.robotics_agent import RoboticsAgent
from agents.research_agent import ResearchAgent
from agents.code_agent import CodeAgent
from agents.critic_agent import CriticAgent
from agents.design_agent import DesignAgent
from agents.artifact_synthesizer import synthesize_artifacts
from agents.llm_clients import call_chatgpt
from agents.validator_agent import ValidatorAgent

from memory.memory_manager import get_recent_memory, add_mission_to_memory


class SupervisorAgent:
    def __init__(self):
        self.name = "Omni"

        # Frontend-facing OMNI identities:
        # Omni -> mission orchestration and final system integration
        # DesignAgent -> Gemini-powered creative design expansion
        # RoboticsAgent -> Sky
        # ResearchAgent -> Isy
        # CodeAgent -> Oli
        # CriticAgent -> Pluto
        # ValidatorAgent -> QaZ
        self.design_agent = DesignAgent()
        self.robotics_agent = RoboticsAgent()
        self.research_agent = ResearchAgent()
        self.code_agent = CodeAgent()
        self.critic_agent = CriticAgent()
        self.validator_agent = ValidatorAgent()

    # ---------------------------------------------------------
    # Naming cleanup
    # ---------------------------------------------------------
    def sanitize_legacy_names(self, text):
        """
        Removes old Marvel/Avengers naming from generated text.
        This lets older agent files keep working while the public product
        branding becomes OMNI-native.
        """
        if not isinstance(text, str):
            return text

        return (
            text
            .replace("Reed Richards", "Omni")
            .replace("Tony Stark", "Sky")
            .replace("Bruce Banner", "Isy")
            .replace("Hank Pym", "Oli")
            .replace("Ultron", "Pluto")
            .replace("Vision", "QaZ")
            .replace("Shuri", "Korva")
            .replace("AI Avengers", "OMNI")
            .replace("Marvel Geniuses HQ", "OMNI Command")
            .replace("Marvel Geniuses", "OMNI")
            .replace("Reed's Final Strategic Recommendation", "Omni's Final Strategic Recommendation")
            .replace("READY FOR VISION VALIDATION", "READY FOR QaZ VALIDATION")
            .replace("Vision engineering validation", "QaZ engineering validation")
            .replace("Use Ultron's critique", "Use Pluto's critique")
            .replace("Tony", "Sky")
            .replace("Bruce", "Isy")
            .replace("Hank", "Oli")
            .replace("Reed", "Omni")
        )

    def sanitize_payload(self, payload):
        """
        Recursively sanitizes strings inside dicts/lists.
        """
        if isinstance(payload, str):
            return self.sanitize_legacy_names(payload)

        if isinstance(payload, list):
            return [self.sanitize_payload(item) for item in payload]

        if isinstance(payload, dict):
            return {
                key: self.sanitize_payload(value)
                for key, value in payload.items()
            }

        return payload

    def safe_agent_run(self, agent_label, fn, fallback_message):
        """
        Keeps the whole mission pipeline from crashing if one external model
        or agent call fails. The frontend still gets a complete structured result.
        """
        try:
            result = fn()
            return self.sanitize_legacy_names(result or fallback_message)
        except Exception as exc:
            return self.sanitize_legacy_names(
                f"# {agent_label} — Error / Fallback\n\n"
                f"{fallback_message}\n\n"
                f"Technical detail: {type(exc).__name__}: {exc}"
            )

    def compact_context(self, text, limit=9000):
        """
        Prevents later prompts from becoming massive after Gemini/design output.
        Keeps the beginning and end, which usually preserve mission intent and key conclusions.
        """
        if not isinstance(text, str):
            text = str(text)

        if len(text) <= limit:
            return text

        head = text[: limit // 2]
        tail = text[-limit // 2 :]
        return f"{head}\n\n...[context compacted for prompt efficiency]...\n\n{tail}"

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
- Gemini Design: creative design expansion and unconventional concept alternatives
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
Explain what Gemini Design, Sky, Korva, Isy, Oli, Pluto, and QaZ should each produce.

## Dashboard Artifacts Needed
List the visual artifacts the OMNI dashboard should generate.

## Omni's Initial Strategic Recommendation
Give the next best action before specialist work begins.
"""
        return self.sanitize_legacy_names(call_chatgpt(omni_prompt))

    # ---------------------------------------------------------
    # Agent council
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
                "id": "design",
                "name": "Gemini Design",
                "role": "Creative Design Expansion / Concept Alternatives",
                "color": "green",
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
                "actor": "Gemini Design",
                "event": "Creative design alternatives generated",
                "description": "Gemini Design expands the mission into unconventional but physically plausible morphology and design options.",
            },
            {
                "step": "3",
                "actor": "Sky / Korva / Isy / Oli",
                "event": "Specialist drafts generated",
                "description": "Core engineering agents generate first-pass domain reports using Omni strategy and Gemini Design context.",
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

Gemini Design Context:
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
        return self.sanitize_legacy_names(call_chatgpt(korva_prompt))

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
        raw_json = call_chatgpt(prompt)

        try:
            parsed = json.loads(raw_json)
            return self.sanitize_payload(parsed)
        except Exception:
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
- Gemini Design's creative alternatives
- Sky's robotics/ROS2 report
- Korva's hardware/electronics report
- Isy's physics/control report
- Oli's CAD/Fusion 360 report
- Pluto's critique
- Structured critique JSON

You must revise the mission output. Do not merely summarize the reports.
You must explicitly incorporate Pluto's critique into the final recommendations.
You must use Gemini Design's ideas only when they are practical enough to validate.

Current Mission:
{mission}

Relevant Previous Memory:
{memory_context}

Omni Initial Strategy:
{omni_strategy}

Gemini Design Creative Expansion:
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
State which Gemini Design concept/direction should be kept, modified, or rejected.

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
        return self.sanitize_legacy_names(call_chatgpt(revision_prompt))

    def build_revision_payload(self, revised_blueprint, structured_critique):
        return {
            "status": "revised",
            "revised_by": "Omni",
            "based_on": [
                "Gemini Design creative expansion",
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

    # ---------------------------------------------------------
    # Export metadata
    # ---------------------------------------------------------
    def build_export_manifest(self, mission, result_id):
        safe_name = (
            mission.lower()
            .replace(" ", "_")
            .replace("/", "_")
            .replace("\\", "_")
        )
        safe_name = "".join(
            ch for ch in safe_name
            if ch.isalnum() or ch in ["_", "-"]
        )
        safe_name = safe_name[:80] or "omni_mission"

        folder_name = f"{safe_name}_{result_id}"

        return {
            "folder_name": folder_name,
            "files_to_generate_next": [
                "mission.json",
                "mission_report.md",
                "agent_reports/omni.md",
                "agent_reports/design.md",
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
                "artifacts/fusion360_concept.md",
                "artifacts/ros2_package_plan.md",
                "artifacts/hardware_architecture.json",
                "artifacts/design_alternatives.md",
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

        # 2. Gemini Design creates creative alternatives before specialists run.
        design_input = f"""
{mission_with_memory}

Omni Strategy:
{omni_strategy}
"""
        design_report = self.safe_agent_run(
            "Gemini Design",
            lambda: self.design_agent.run(design_input),
            "Gemini Design could not generate creative alternatives. Continue with standard practical design assumptions.",
        )

        # Keep specialist context useful, but avoid runaway prompt size.
        mission_with_design_context = self.compact_context(
            f"""
{mission_with_memory}

Omni Strategy:
{omni_strategy}

Gemini Design Creative Expansion:
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

Gemini Design Creative Expansion:
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

        # 8. Omni revises final blueprint using Pluto critique and Gemini Design.
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
            "owner": "Gemini Design",
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

## Gemini Design — Creative Design Expansion
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

        validation_report = self.validator_agent.validate(
            mission=mission,
            artifact_text=validation_input,
            artifact_type="robotics_design",
        )

        validation_payload = self.build_validation_payload(validation_report)

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
Omni: {omni_strategy[:500]}

Gemini Design: {design_report[:500]}

Sky: {sky_report[:500]}

Korva: {korva_report[:500]}

Isy: {isy_report[:500]}

Oli: {oli_report[:500]}

Pluto: {pluto_report[:500]}

Revision Risk Level: {critique_payload.get("risk_level", "yellow")}
Revision Required Fixes: {critique_payload.get("required_fixes", [])[:5]}

QaZ Validation Verdict: {validation_report.verdict}
QaZ Score: {validation_report.overall_score}/10
QaZ Missing Evidence: {validation_report.missing_evidence[:5]}
QaZ Required Next Tests: {validation_report.required_next_tests[:5]}
"""

        add_mission_to_memory(mission, self.sanitize_legacy_names(memory_summary))

        # 15. Return structured payload for frontend/dashboard.
        return {
            "mission": mission,
            "created_at": created_at,
            "result_id": result_id,
            "memory_used": self.sanitize_legacy_names(memory_context),
            "agent_council": self.build_agent_council(),
            "council_events": self.build_council_events(),

            # OMNI-native agent keys only.
            "agents": {
                "omni": omni_strategy,
                "design": design_report,
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

    def run_mission(self, mission):
        """
        Main method used by backend routes.
        Returns the full structured result.
        """
        return self.run_mission_structured(mission)

    def run_mission_text_only(self, mission):
        """
        Legacy method for scripts that only expect plain text.
        """
        structured_result = self.run_mission_structured(mission)
        return structured_result["final_report"]
