import json
from typing import Any, Dict

from agents.llm_clients import call_chatgpt
from backend.app.knowledge.ros2_pattern_library import build_ros2_context_block


class MissionInterpreterAgent:
    """
    Echo: turns rough human ideas into structured OMNI missions.

    Echo does not solve the engineering mission directly.
    Echo prepares the mission so Omni, Sky, Korva, Isy, Oli, Pluto, and QaZ
    can run the real council workflow.
    """

    def __init__(self):
        self.name = "Echo"
        self.role = "Mission Interpreter / Prompt Expansion Agent"

    def interpret(self, idea: str, context: str = "") -> Dict[str, Any]:
        if not idea or not idea.strip():
            return self._fallback_response(
                idea="",
                reason="No idea was provided.",
            )

        clean_idea = idea.strip()
        clean_context = context.strip() if context else ""

        ros2_context = build_ros2_context_block(
            f"{clean_idea}\n\n{clean_context}",
            limit=5,
        )

        prompt = f"""
You are Echo, the Mission Interpreter inside OMNI Command.

Your job is to take Henry's rough, casual, incomplete project idea and convert it into a clear, detailed OMNI mission prompt.

You are NOT solving the mission.
You are NOT writing the final engineering report.
You are preparing the mission so the OMNI council can run it.

OMNI council agents:
- Omni: mission orchestration and systems integration
- Sky: robotics, ROS2, drones, autonomy, software architecture
- Korva: hardware, electronics, embedded systems, wiring, PCB
- Isy: physics, controls, dynamics, feasibility
- Oli: CAD, Fusion 360, 3D concepts, visual artifacts
- Pluto: risk, failure analysis, safety gates
- QaZ: validation, scoring, requirements verification
- Henry: human decision maker

Henry's rough idea:
{clean_idea}

Additional context, attachment notes, or user-provided background:
{clean_context}

Real ROS2 package knowledge base context:
{ros2_context}

Return ONLY valid JSON.
Do not include markdown.
Do not include code fences.
Do not include explanations outside JSON.

Return this exact JSON structure:

{{
  "agent": "Echo",
  "mission_title": "short title",
  "expanded_mission": "full detailed mission prompt for OMNI",
  "detected_domains": ["ROS2", "robotics", "CAD", "Fusion 360", "embedded systems"],
  "required_agents": ["omni", "sky", "korva", "isy", "oli", "pluto", "qaz"],
  "project_type": "robotics | drone | cad | web_app | embedded | computer_vision | ros2 | mixed",
  "complexity": "low | medium | high | extreme",
  "auto_run_ready": true,
  "missing_inputs": [
    "specific missing information Henry should confirm"
  ],
  "assumptions": [
    "safe assumptions Echo made while expanding the mission"
  ],
  "safety_notes": [
    "important safety or caution notes"
  ],
  "suggested_first_build_phase": "clear first phase recommendation",
  "export_expectations": [
    "files or artifacts OMNI should generate"
  ]
}}

Rules:
- Preserve Henry's intent and tone, but make the mission engineering-ready.
- If Henry's idea is vague, make reasonable safe assumptions.
- Do not invent exact hardware specs.
- Always tell OMNI to list unknown measurements as things Henry must confirm.
- If the idea involves ROS2, request node graph, topics, message types, launch plan, package plan, and test commands.
- If the idea involves CAD or Fusion 360, request CAD parameters, component layout, mounting constraints, materials, clearances, and missing measurements.
- If the idea involves physical hardware, request safety gates, risk matrix, wiring plan, power budget assumptions, and validation checklist.
- If the idea is too vague, still create a useful expanded mission and set auto_run_ready to true unless it is unsafe or impossible.

ROS2 knowledge base rules:
- Use the ROS2 package knowledge base context when the idea involves ROS2, robotics, navigation, motor control, robot description, launch files, URDF, RViz, Nav2, or ros2_control.
- If relevant patterns mention launch folders, config folders, URDF/Xacro, RViz, params, topic contracts, or controller YAMLs, include those in the expanded mission requirements.
- For ROS2 missions, request export-ready package files including package.xml, setup.py or CMakeLists.txt, setup.cfg for Python packages, launch files, config YAML, docs/topic_contracts.md, docs/node_graph.md, and scripts/test_topics.sh.
- For rover or mobile robot missions, consider whether the mission should mention Nav2, robot description, URDF/Xacro, RViz visualization, motor control, sensor topics, and controller configuration.
- Do not claim that the system is physically ready. Keep hardware testing gated behind measurements, wiring review, power budget review, mechanical stability review, and emergency stop conditions.
"""

        try:
            raw = call_chatgpt(prompt)
            data = json.loads(raw)

            return self._normalize_response(data, clean_idea, ros2_context)

        except Exception as error:
            return self._fallback_response(
                idea=clean_idea,
                reason=f"Echo failed to parse model output: {str(error)}",
                ros2_context=ros2_context,
            )

    def _normalize_response(
        self,
        data: Dict[str, Any],
        original_idea: str,
        ros2_context: str = "",
    ) -> Dict[str, Any]:
        if not isinstance(data, dict):
            return self._fallback_response(
                idea=original_idea,
                reason="Echo returned a non-dictionary response.",
                ros2_context=ros2_context,
            )

        expanded = data.get("expanded_mission") or self._basic_expansion(
            original_idea,
            ros2_context=ros2_context,
        )

        normalized = {
            "agent": "Echo",
            "mission_title": data.get("mission_title") or "Interpreted OMNI Mission",
            "expanded_mission": expanded,
            "detected_domains": self._as_list(data.get("detected_domains")),
            "required_agents": self._as_list(
                data.get("required_agents")
                or ["omni", "sky", "korva", "isy", "oli", "pluto", "qaz"]
            ),
            "project_type": data.get("project_type") or "mixed",
            "complexity": data.get("complexity") or "medium",
            "auto_run_ready": bool(data.get("auto_run_ready", True)),
            "missing_inputs": self._as_list(data.get("missing_inputs")),
            "assumptions": self._as_list(data.get("assumptions")),
            "safety_notes": self._as_list(data.get("safety_notes")),
            "suggested_first_build_phase": (
                data.get("suggested_first_build_phase")
                or "Start with a concept-stage blueprint, then validate requirements before hardware testing."
            ),
            "export_expectations": self._as_list(data.get("export_expectations")),
            "original_idea": original_idea,
            "ros2_context_used": bool(ros2_context),
        }

        if not normalized["detected_domains"]:
            normalized["detected_domains"] = self._infer_domains(original_idea)

        if not normalized["missing_inputs"]:
            normalized["missing_inputs"] = [
                "Exact dimensions, power requirements, component models, materials, and test environment must be confirmed by Henry."
            ]

        if not normalized["assumptions"]:
            normalized["assumptions"] = [
                "This should begin as a concept-stage mission before physical implementation.",
                "Unknown measurements should be listed instead of invented.",
            ]

        if not normalized["safety_notes"]:
            normalized["safety_notes"] = [
                "Do not proceed to physical testing until wiring, power, motion, and stop conditions are reviewed."
            ]

        if not normalized["export_expectations"]:
            normalized["export_expectations"] = self._default_export_expectations(
                original_idea
            )

        return normalized

    def _fallback_response(
        self,
        idea: str,
        reason: str,
        ros2_context: str = "",
    ) -> Dict[str, Any]:
        return {
            "agent": "Echo",
            "mission_title": "Interpreted OMNI Mission",
            "expanded_mission": self._basic_expansion(
                idea,
                ros2_context=ros2_context,
            ),
            "detected_domains": self._infer_domains(idea),
            "required_agents": ["omni", "sky", "korva", "isy", "oli", "pluto", "qaz"],
            "project_type": "mixed",
            "complexity": "medium",
            "auto_run_ready": True,
            "missing_inputs": [
                "Exact components, dimensions, materials, power requirements, software stack, and testing environment must be confirmed."
            ],
            "assumptions": [
                "The project should start as a concept-stage blueprint.",
                "Unknown measurements should be listed as items Henry must confirm.",
            ],
            "safety_notes": [
                "Do not perform hardware or motion testing until power, wiring, mechanical stability, and stop conditions are reviewed."
            ],
            "suggested_first_build_phase": "Generate a detailed OMNI blueprint and export-ready artifacts first.",
            "export_expectations": self._default_export_expectations(idea),
            "original_idea": idea,
            "fallback_reason": reason,
            "ros2_context_used": bool(ros2_context),
        }

    def _basic_expansion(self, idea: str, ros2_context: str = "") -> str:
        clean_idea = idea.strip() if idea else "Henry wants to explore a new engineering project."
        domains = self._infer_domains(clean_idea)
        ros2_relevant = "ROS2" in domains or "robotics" in domains

        ros2_requirements = ""

        if ros2_relevant:
            ros2_requirements = f"""

Because this mission appears to involve ROS2 or robotics, also include:
- ROS2 package plan
- ROS2 node graph
- topic contracts with publishers, subscribers, and message types
- launch file plan
- config YAML or parameter YAML plan
- docs/topic_contracts.md
- docs/node_graph.md
- scripts/test_topics.sh
- package.xml dependencies
- setup.py and setup.cfg for Python ROS2 packages
- URDF/Xacro and RViz requirements if robot description or visualization is relevant
- Nav2 considerations if navigation, localization, maps, or path planning are relevant
- ros2_control considerations if motor control, actuators, controllers, or hardware interfaces are relevant

Real ROS2 package knowledge context to apply:
{ros2_context}
"""

        return f"""
Interpret Henry's rough project idea and turn it into a full OMNI engineering mission.

Original idea:
{clean_idea}

Create a detailed concept-stage engineering plan. Include:
- mission objective
- system requirements
- hardware architecture
- software architecture
- ROS2 architecture if relevant
- CAD or Fusion 360 concept if relevant
- wiring and power assumptions if hardware is involved
- risk matrix
- safety gates
- validation checklist
- missing measurements Henry must confirm
- export-ready artifacts
- revised final blueprint after Pluto critique
- QaZ validation
{ros2_requirements}

Do not invent final dimensions, torque values, current capacity, material choice, or payload mass. List unknowns as measurements Henry must confirm before implementation or hardware testing.
""".strip()

    def _default_export_expectations(self, idea: str) -> list:
        domains = self._infer_domains(idea)

        expectations = [
            "mission report",
            "agent reports",
            "structured artifacts",
            "risk matrix",
            "validation checklist",
        ]

        if "ROS2" in domains or "robotics" in domains:
            expectations.extend(
                [
                    "ROS2 package plan",
                    "ROS2 node graph",
                    "topic contracts",
                    "launch file plan",
                    "package.xml",
                    "setup.py",
                    "setup.cfg",
                    "config YAML",
                    "docs/topic_contracts.md",
                    "docs/node_graph.md",
                    "scripts/test_topics.sh",
                ]
            )

        if "CAD" in domains:
            expectations.extend(
                [
                    "Fusion 360 concept",
                    "CAD parameters",
                    "component layout",
                    "mounting constraints",
                ]
            )

        return expectations

    def _infer_domains(self, idea: str) -> list:
        text = (idea or "").lower()
        domains = []

        if any(
            term in text
            for term in [
                "ros2",
                "ros 2",
                "node",
                "topic",
                "launch",
                "nav2",
                "rviz",
                "urdf",
                "xacro",
                "ros2_control",
                "controller",
            ]
        ):
            domains.append("ROS2")

        if any(
            term in text
            for term in ["robot", "rover", "arm", "servo", "motor", "drone"]
        ):
            domains.append("robotics")

        if any(
            term in text
            for term in ["fusion", "cad", "3d print", "chassis", "enclosure"]
        ):
            domains.append("CAD")

        if any(
            term in text
            for term in [
                "raspberry pi",
                "arduino",
                "sensor",
                "imu",
                "gpio",
                "pcb",
                "wiring",
                "embedded",
                "motor driver",
            ]
        ):
            domains.append("embedded systems")

        if any(
            term in text
            for term in ["camera", "vision", "image", "detect", "tracking"]
        ):
            domains.append("computer vision")

        if not domains:
            domains.append("engineering planning")

        return domains

    def _as_list(self, value: Any) -> list:
        if value is None:
            return []

        if isinstance(value, list):
            return value

        return [value]