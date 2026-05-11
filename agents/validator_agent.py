from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import re

from backend.app.omni_core.formatters import (
    sanitize_legacy_names as format_sanitize_legacy_names,
)


@dataclass
class ValidationFinding:
    category: str
    status: str  # PASS, WARNING, FAIL
    message: str
    recommendation: str
    source_basis: str


@dataclass
class ValidationReport:
    verdict: str
    overall_score: float
    findings: List[ValidationFinding] = field(default_factory=list)
    missing_evidence: List[str] = field(default_factory=list)
    required_next_tests: List[str] = field(default_factory=list)
    confidence_scores: Dict[str, float] = field(default_factory=dict)

    def to_markdown(self) -> str:
        lines = []
        lines.append("# QaZ Validation Report\n")
        lines.append(f"## Verdict\n**{self.verdict}**\n")
        lines.append(f"## Overall Score\n**{self.overall_score:.1f}/10**\n")

        lines.append("## Confidence Scores")
        for key, value in self.confidence_scores.items():
            lines.append(f"- {key}: {value:.1f}/10")
        lines.append("")

        lines.append("## Findings")
        for finding in self.findings:
            lines.append(f"### {finding.status}: {finding.category}")
            lines.append(f"{finding.message}")
            lines.append(f"**Recommendation:** {finding.recommendation}")
            lines.append(f"**Source basis:** {finding.source_basis}\n")

        if self.missing_evidence:
            lines.append("## Missing Evidence")
            for item in self.missing_evidence:
                lines.append(f"- {item}")
            lines.append("")

        if self.required_next_tests:
            lines.append("## Required Next Tests")
            for test in self.required_next_tests:
                lines.append(f"- {test}")
            lines.append("")

        return "\n".join(lines)


class ValidatorAgent:
    """
    QaZ: OMNI engineering validator.

    QaZ is intentionally stricter than a normal summarizer:
    - A concept can be useful without being fully validated.
    - PASS should require objective evidence, measurements, and test readiness.
    - Most early robotics/CAD/ROS2 missions should be CONDITIONAL PASS, not PASS.
    """

    def __init__(self):
        self.name = "QaZ"
        self.role = "Validation, Scoring, and Requirements Verification"
        self.source_map = {
            "systems": "NASA Systems Engineering Handbook",
            "controls": "Feedback Systems by Åström and Murray",
            "robotics": "Underactuated Robotics by Russ Tedrake",
            "planning": "Planning Algorithms by Steven LaValle",
            "physics": "OpenStax College Physics 2e",
            "mechanics": "Mechanics of Materials by David Roylance",
            "estimation": "Kalman and Bayesian Filters in Python by Roger Labbe",
            "cad": "Fusion 360 / CAD design-for-manufacturing best practices",
            "ros2": "ROS2 package, node, topic, launch, and test workflow best practices",
            "evidence": "Objective engineering evidence and test-log review",
        }

    def validate(
        self,
        mission: str,
        artifact_text: str,
        artifact_type: str = "engineering_report",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ValidationReport:
        metadata = metadata or {}
        mission = self._as_text(mission)
        text = self._sanitize_legacy_names(artifact_text or "")

        findings: List[ValidationFinding] = []

        findings.extend(self._systems_engineering_check(mission, text))
        findings.extend(self._physics_check(text))
        findings.extend(self._mechanical_check(text))
        findings.extend(self._electrical_check(text))
        findings.extend(self._controls_check(text))
        findings.extend(self._robotics_dynamics_check(mission, text))
        findings.extend(self._planning_check(text))
        findings.extend(self._estimation_check(text))
        findings.extend(self._ros2_check(mission, text))
        findings.extend(self._cad_check(mission, text))
        findings.extend(self._objective_evidence_check(text))
        findings.extend(self._safety_gate_check(text))

        missing = self._collect_missing_evidence(findings)
        next_tests = self._recommend_next_tests(findings, artifact_type)
        scores = self._score_by_category(findings)
        overall = self._overall_score(scores, findings)
        verdict = self._verdict_from_score(overall, findings, text)

        return ValidationReport(
            verdict=verdict,
            overall_score=overall,
            findings=findings,
            missing_evidence=missing,
            required_next_tests=next_tests,
            confidence_scores=scores,
        )

    # -------------------------
    # Core checks
    # -------------------------

    def _systems_engineering_check(
        self,
        mission: str,
        text: str,
    ) -> List[ValidationFinding]:
        findings = []
        required_terms = {
            "mission objective": ["mission objective", "objective", "goal"],
            "stakeholder need": ["stakeholder", "user need", "intended user", "Henry"],
            "requirements": ["requirement", "shall", "must", "required"],
            "assumptions": ["assumption", "assuming", "assume"],
            "constraints": ["constraint", "limit", "boundary", "safe operating"],
            "verification": [
                "verify",
                "verification",
                "inspection",
                "analysis",
                "demonstration",
                "test",
            ],
            "validation": [
                "validate",
                "validation",
                "intended use",
                "operational environment",
            ],
            "risk": ["risk", "failure", "hazard", "mitigation", "safety"],
            "approval gates": [
                "approval gate",
                "human approval",
                "needs_review",
                "Henry must approve",
            ],
        }

        for label, terms in required_terms.items():
            if self._contains_any(text, terms):
                findings.append(
                    self._pass(
                        "Systems Engineering",
                        f"Found evidence for {label}.",
                        "Keep this traceable to a specific requirement, artifact, or test.",
                        self.source_map["systems"],
                    )
                )
            else:
                findings.append(
                    self._fail(
                        "Systems Engineering",
                        f"Missing {label}.",
                        f"Add a clear {label} section before treating the artifact as valid.",
                        self.source_map["systems"],
                    )
                )

        return findings

    def _physics_check(self, text: str) -> List[ValidationFinding]:
        findings = []

        unit_patterns = [
            r"\bkg\b",
            r"\bg\b",
            r"\bN\b",
            r"\bNm\b",
            r"\bN·m\b",
            r"\bm/s\b",
            r"\bm/s\^2\b",
            r"\bW\b",
            r"\bJ\b",
            r"\bV\b",
            r"\bA\b",
            r"\bmA\b",
            r"\bOhm\b",
            r"\bΩ\b",
            r"\bmm\b",
            r"\bcm\b",
            r"\bm\b",
            r"\bdeg\b",
            r"\bdegree",
        ]

        number_with_unit = any(re.search(pattern, text) for pattern in unit_patterns)
        has_numbers = bool(re.search(r"\b\d+(\.\d+)?\b", text))

        if number_with_unit:
            findings.append(
                self._pass(
                    "Physics",
                    "Physical units were found.",
                    "Ensure every numerical engineering claim includes units and uncertainty where possible.",
                    self.source_map["physics"],
                )
            )
        else:
            findings.append(
                self._fail(
                    "Physics",
                    "No physical units were detected.",
                    "Add SI units for mass, length, force, torque, power, current, voltage, and speed.",
                    self.source_map["physics"],
                )
            )

        if has_numbers and number_with_unit:
            findings.append(
                self._pass(
                    "Physics",
                    "Numerical values with units appear in the artifact.",
                    "Tie numerical values to assumptions, equations, or measurement sources.",
                    self.source_map["physics"],
                )
            )
        else:
            findings.append(
                self._warning(
                    "Physics",
                    "Few or no numerical engineering values were found.",
                    "Add actual estimates for mass, dimensions, torque, current draw, range, and timing.",
                    self.source_map["physics"],
                )
            )

        physics_terms = [
            "force",
            "mass",
            "weight",
            "torque",
            "energy",
            "power",
            "velocity",
            "acceleration",
            "moment of inertia",
        ]

        if self._contains_any(text, physics_terms):
            findings.append(
                self._pass(
                    "Physics",
                    "Basic physics quantities are discussed.",
                    "Tie these quantities to equations or estimates.",
                    self.source_map["physics"],
                )
            )
        else:
            findings.append(
                self._fail(
                    "Physics",
                    "The output does not discuss basic force, mass, torque, or power relationships.",
                    "Add first-principles sanity checks using Newtonian mechanics and power reasoning.",
                    self.source_map["physics"],
                )
            )

        return findings

    def _mechanical_check(self, text: str) -> List[ValidationFinding]:
        findings = []

        mechanical_terms = [
            "stress",
            "strain",
            "bending",
            "torsion",
            "stiffness",
            "yield",
            "fracture",
            "fatigue",
            "load path",
            "factor of safety",
            "clearance",
            "mounting",
            "vibration",
            "backlash",
            "servo overload",
        ]

        if self._contains_any(text, mechanical_terms):
            findings.append(
                self._pass(
                    "Mechanical",
                    "Mechanical strength, mounting, or movement concerns are present.",
                    "Connect each concern to a specific geometry, material, load case, or inspection test.",
                    self.source_map["mechanics"],
                )
            )
        else:
            findings.append(
                self._fail(
                    "Mechanical",
                    "No serious mechanical validation was found.",
                    "Add stress, bending, clearance, mounting, load path, vibration, and factor-of-safety checks.",
                    self.source_map["mechanics"],
                )
            )

        if self._contains_any(
            text,
            [
                "material",
                "aluminum",
                "carbon fiber",
                "steel",
                "pla",
                "petg",
                "abs",
                "acrylic",
            ],
        ):
            findings.append(
                self._pass(
                    "Mechanical",
                    "Material assumptions were found.",
                    "Add material properties such as density, Young's modulus, yield strength, or print settings.",
                    self.source_map["mechanics"],
                )
            )
        else:
            findings.append(
                self._warning(
                    "Mechanical",
                    "No material assumption was found.",
                    "Specify material choice and why it is appropriate.",
                    self.source_map["mechanics"],
                )
            )

        if self._contains_any(
            text,
            ["mounting hole", "standoff", "screw", "m3", "clearance", "cutout"],
        ):
            findings.append(
                self._pass(
                    "Mechanical",
                    "Mounting or clearance language was found.",
                    "Verify mounting dimensions against actual component datasheets.",
                    self.source_map["mechanics"],
                )
            )
        else:
            findings.append(
                self._warning(
                    "Mechanical",
                    "Mounting and clearance evidence is weak.",
                    "Add hole patterns, standoffs, screw sizes, cable clearances, and service access.",
                    self.source_map["mechanics"],
                )
            )

        return findings

    def _electrical_check(self, text: str) -> List[ValidationFinding]:
        findings = []
        electrical_terms = [
            "battery",
            "voltage",
            "current",
            "amp",
            "watt",
            "power",
            "esc",
            "motor",
            "servo",
            "resistor",
            "capacitor",
            "wire",
            "connector",
            "gpio",
            "i2c",
            "spi",
            "uart",
            "pwm",
            "regulator",
        ]

        if self._contains_any(text, electrical_terms):
            findings.append(
                self._pass(
                    "Electrical / Power",
                    "Electrical or power-system terms were found.",
                    "Add current draw, voltage compatibility, thermal risk, wire gauge, and grounding assumptions.",
                    self.source_map["physics"],
                )
            )
        else:
            findings.append(
                self._warning(
                    "Electrical / Power",
                    "No electrical or power validation was found.",
                    "For robotics artifacts, include power supply, current, voltage, wiring, and heat checks.",
                    self.source_map["physics"],
                )
            )

        has_voltage = bool(
            re.search(r"\b\d+(\.\d+)?\s?V\b", text, flags=re.IGNORECASE)
        ) or self._contains_any(text, ["voltage"])

        has_current = bool(
            re.search(r"\b\d+(\.\d+)?\s?(A|mA)\b", text, flags=re.IGNORECASE)
        ) or self._contains_any(text, ["current draw", "current"])

        has_power_risk = self._contains_any(
            text,
            ["power supply", "voltage drop", "overcurrent", "short", "thermal", "heat"],
        )

        if has_voltage and has_current and has_power_risk:
            findings.append(
                self._pass(
                    "Electrical / Power",
                    "Voltage, current, and power-risk concerns are present.",
                    "Confirm these values with component datasheets or measurements.",
                    self.source_map["physics"],
                )
            )
        else:
            findings.append(
                self._warning(
                    "Electrical / Power",
                    "Power validation is incomplete.",
                    "Add voltage levels, estimated current draw per component, total current budget, and overcurrent protection.",
                    self.source_map["physics"],
                )
            )

        return findings

    def _controls_check(self, text: str) -> List[ValidationFinding]:
        findings = []

        controls_terms = [
            "feedback",
            "controller",
            "pid",
            "lqr",
            "stability",
            "sensor",
            "actuator",
            "disturbance",
            "noise",
            "latency",
            "closed loop",
            "open loop",
            "overshoot",
            "settling",
        ]

        if self._contains_any(text, controls_terms):
            findings.append(
                self._pass(
                    "Controls",
                    "Control-system concepts were found.",
                    "Specify the loop: measured state, desired state, controller, actuator, and disturbance.",
                    self.source_map["controls"],
                )
            )
        else:
            findings.append(
                self._fail(
                    "Controls",
                    "No control-system validation was found.",
                    "Add sensors, actuators, feedback loop, stability concern, noise, disturbance, and latency checks.",
                    self.source_map["controls"],
                )
            )

        if self._contains_any(
            text,
            [
                "stability",
                "unstable",
                "oscillation",
                "overshoot",
                "settling",
                "backlash",
            ],
        ):
            findings.append(
                self._pass(
                    "Controls",
                    "Stability-related language was found.",
                    "Add a concrete stability test, servo sweep test, or simulation.",
                    self.source_map["controls"],
                )
            )
        else:
            findings.append(
                self._warning(
                    "Controls",
                    "No stability discussion was found.",
                    "Mention how the system avoids oscillation, runaway behavior, or unstable response.",
                    self.source_map["controls"],
                )
            )

        return findings

    def _robotics_dynamics_check(
        self,
        mission: str,
        text: str,
    ) -> List[ValidationFinding]:
        findings = []

        robotics_terms = [
            "dynamics",
            "state",
            "input",
            "constraint",
            "trajectory",
            "actuator limit",
            "sensor",
            "servo",
            "robot",
            "ros2",
            "node",
            "center of mass",
            "moment of inertia",
        ]

        if self._contains_any(text, robotics_terms):
            findings.append(
                self._pass(
                    "Robotics Dynamics",
                    "Robotics dynamics or robotic-system concepts were found.",
                    "Include mass, center of mass, inertia, actuator limits, and sensor limits where applicable.",
                    self.source_map["robotics"],
                )
            )
        else:
            findings.append(
                self._fail(
                    "Robotics Dynamics",
                    "No robotics dynamics validation was found.",
                    "Add state, input, constraints, dynamics, actuator limits, and physical-system discussion.",
                    self.source_map["robotics"],
                )
            )

        mission_lower = mission.lower()
        text_lower = text.lower()
        drone_mission = any(
            word in mission_lower or word in text_lower
            for word in [
                "drone",
                "quadcopter",
                "hexacopter",
                "multirotor",
                "uav",
            ]
        )

        if drone_mission:
            if self._contains_any(
                text,
                [
                    "thrust-to-weight",
                    "thrust to weight",
                    "payload",
                    "total thrust",
                    "hover throttle",
                ],
            ):
                findings.append(
                    self._pass(
                        "Drone Feasibility",
                        "Drone payload or thrust feasibility is considered.",
                        "Include actual estimated values and margin.",
                        self.source_map["robotics"],
                    )
                )
            else:
                findings.append(
                    self._fail(
                        "Drone Feasibility",
                        "Drone mentioned, but no thrust-to-weight or payload feasibility check was found.",
                        "Add total mass, payload mass, total thrust, hover throttle, and thrust margin.",
                        self.source_map["robotics"],
                    )
                )

        return findings

    def _planning_check(self, text: str) -> List[ValidationFinding]:
        findings = []

        planning_items = {
            "state space": ["state space", "state vector", "system state"],
            "action space": ["action space", "control input", "operator action"],
            "initial state": ["initial state", "start condition"],
            "goal state": ["goal state", "target condition"],
            "constraints": ["obstacle", "constraint", "collision", "boundary", "limit"],
            "feasibility": ["feasible", "feasibility"],
            "optimality": ["optimal", "cost", "efficiency"],
        }

        for label, terms in planning_items.items():
            if self._contains_any(text, terms):
                findings.append(
                    self._pass(
                        "Planning / Autonomy",
                        f"Found planning evidence for {label}.",
                        "Make sure this is stated explicitly and tied to a test.",
                        self.source_map["planning"],
                    )
                )
            else:
                findings.append(
                    self._warning(
                        "Planning / Autonomy",
                        f"Missing explicit {label}.",
                        f"Add {label} to the autonomy or behavior-planning section.",
                        self.source_map["planning"],
                    )
                )

        return findings

    def _estimation_check(self, text: str) -> List[ValidationFinding]:
        findings = []

        estimation_terms = [
            "kalman",
            "bayesian",
            "filter",
            "sensor fusion",
            "imu",
            "gps",
            "camera",
            "lidar",
            "state estimation",
            "measurement noise",
            "process noise",
            "ultrasonic",
        ]

        if self._contains_any(text, estimation_terms):
            findings.append(
                self._pass(
                    "Estimation / Sensor Fusion",
                    "State estimation or sensor-fusion language was found.",
                    "Add state vector, measurement model, process noise, and measurement noise assumptions.",
                    self.source_map["estimation"],
                )
            )
        else:
            findings.append(
                self._warning(
                    "Estimation / Sensor Fusion",
                    "No state-estimation or sensor-fusion validation was found.",
                    "For autonomous robots, add IMU/camera/range-sensor fusion and uncertainty handling.",
                    self.source_map["estimation"],
                )
            )

        if self._contains_any(
            text,
            ["measurement noise", "process noise", "calibration", "drift", "latency"],
        ):
            findings.append(
                self._pass(
                    "Estimation / Sensor Fusion",
                    "Calibration, drift, latency, or noise concerns are present.",
                    "Turn these into specific calibration and logging tests.",
                    self.source_map["estimation"],
                )
            )
        else:
            findings.append(
                self._warning(
                    "Estimation / Sensor Fusion",
                    "Sensor uncertainty details are incomplete.",
                    "Add calibration procedure, drift handling, latency assumptions, and measurement noise.",
                    self.source_map["estimation"],
                )
            )

        return findings

    def _ros2_check(self, mission: str, text: str) -> List[ValidationFinding]:
        findings = []

        mission_mentions_ros2 = "ros2" in mission.lower() or "ros2" in text.lower()

        if not mission_mentions_ros2:
            return findings

        ros2_terms = [
            "node",
            "topic",
            "message_type",
            "launch",
            "package",
            "publisher",
            "subscriber",
        ]

        if self._contains_any(text, ros2_terms):
            findings.append(
                self._pass(
                    "ROS2 Architecture",
                    "ROS2 architecture evidence was found.",
                    "Keep nodes, topics, message types, launch files, and tests traceable.",
                    self.source_map["ros2"],
                )
            )
        else:
            findings.append(
                self._fail(
                    "ROS2 Architecture",
                    "ROS2 was requested, but architecture evidence is missing.",
                    "Add package name, nodes, topics, message types, launch files, and test commands.",
                    self.source_map["ros2"],
                )
            )

        if self._contains_any(
            text,
            [
                "ros2 launch",
                "ros2 topic",
                "ros2 node",
                "launch.py",
                "package.xml",
                "cmakelists",
            ],
        ):
            findings.append(
                self._pass(
                    "ROS2 Architecture",
                    "ROS2 command, launch, or package evidence was found.",
                    "Generate these as exportable files in the next phase.",
                    self.source_map["ros2"],
                )
            )
        else:
            findings.append(
                self._warning(
                    "ROS2 Architecture",
                    "ROS2 export-readiness is incomplete.",
                    "Add launch file names, package.xml/CMakeLists expectations, and practical ROS2 test commands.",
                    self.source_map["ros2"],
                )
            )

        return findings

    def _cad_check(self, mission: str, text: str) -> List[ValidationFinding]:
        findings = []

        mission_mentions_cad = any(
            term in mission.lower() or term in text.lower()
            for term in [
                "fusion 360",
                "cad",
                "enclosure",
                "blueprint",
                "3d model",
            ]
        )

        if not mission_mentions_cad:
            return findings

        if self._contains_any(
            text,
            [
                "fusion 360",
                "cad",
                "sketch",
                "extrude",
                "fillet",
                "component",
                "assembly",
            ],
        ):
            findings.append(
                self._pass(
                    "CAD / Fusion 360",
                    "CAD or Fusion 360 modeling evidence was found.",
                    "Convert this into parameters, named components, and modeling steps.",
                    self.source_map["cad"],
                )
            )
        else:
            findings.append(
                self._fail(
                    "CAD / Fusion 360",
                    "CAD was requested, but modeling evidence is missing.",
                    "Add Fusion 360 parameters, sketches, extrusions, components, mounting points, and manufacturing notes.",
                    self.source_map["cad"],
                )
            )

        if self._contains_any(
            text,
            [
                "mm",
                "mounting",
                "clearance",
                "standoff",
                "screw",
                "cutout",
                "manufacturing",
            ],
        ):
            findings.append(
                self._pass(
                    "CAD / Fusion 360",
                    "CAD dimension, mounting, or manufacturing evidence was found.",
                    "Verify these against actual part dimensions before modeling.",
                    self.source_map["cad"],
                )
            )
        else:
            findings.append(
                self._warning(
                    "CAD / Fusion 360",
                    "CAD readiness is incomplete.",
                    "Add dimensions in mm, mounting holes, clearances, component zones, material, and manufacturing method.",
                    self.source_map["cad"],
                )
            )

        return findings

    def _objective_evidence_check(self, text: str) -> List[ValidationFinding]:
        findings = []

        evidence_terms = [
            "test result",
            "logged result",
            "measured",
            "measurement",
            "datasheet",
            "benchmark",
            "simulation result",
            "prototype test",
            "verified with",
            "validated by",
            "observed",
        ]

        if self._contains_any(text, evidence_terms):
            findings.append(
                self._pass(
                    "Objective Evidence",
                    "Some objective-evidence language was found.",
                    "Attach real measurements, logs, screenshots, CAD studies, or ROS2 bag files when available.",
                    self.source_map["evidence"],
                )
            )
        else:
            findings.append(
                self._warning(
                    "Objective Evidence",
                    "No real objective evidence or test logs were found.",
                    "Do not treat this as fully validated until measured data, logs, or simulation results exist.",
                    self.source_map["evidence"],
                )
            )

        placeholder_terms = [
            "unknown",
            "must be checked",
            "needs to measure",
            "still needs",
            "estimate",
            "assumption",
            "assumed",
            "to be confirmed",
            "should be tested",
            "pending",
        ]

        if self._contains_any(text, placeholder_terms):
            findings.append(
                self._warning(
                    "Objective Evidence",
                    "The artifact still contains unresolved assumptions or pending checks.",
                    "Resolve unknowns before claiming final readiness.",
                    self.source_map["evidence"],
                )
            )

        return findings

    def _safety_gate_check(self, text: str) -> List[ValidationFinding]:
        findings = []

        if self._contains_any(
            text,
            [
                "stop condition",
                "safety gate",
                "do not",
                "must not",
                "unsafe",
                "needs_review",
            ],
        ):
            findings.append(
                self._pass(
                    "Safety Gates",
                    "Safety gates or stop conditions were found.",
                    "Keep safety gates visible in the dashboard and export manifest.",
                    self.source_map["systems"],
                )
            )
        else:
            findings.append(
                self._fail(
                    "Safety Gates",
                    "No safety gates or stop conditions were found.",
                    "Add explicit stop conditions before any physical test.",
                    self.source_map["systems"],
                )
            )

        return findings

    # -------------------------
    # Scoring and aggregation
    # -------------------------

    def _score_by_category(
        self,
        findings: List[ValidationFinding],
    ) -> Dict[str, float]:
        value = {
            "PASS": 9.0,
            "WARNING": 5.5,
            "FAIL": 1.5,
        }

        categories: Dict[str, List[float]] = {}

        for finding in findings:
            categories.setdefault(finding.category, [])
            categories[finding.category].append(value.get(finding.status, 5.0))

        scores = {}
        for category, vals in categories.items():
            if vals:
                scores[category] = sum(vals) / len(vals)

        return scores

    def _overall_score(
        self,
        scores: Dict[str, float],
        findings: List[ValidationFinding],
    ) -> float:
        if not scores:
            return 0.0

        raw = sum(scores.values()) / len(scores)

        warning_count = sum(1 for finding in findings if finding.status == "WARNING")
        fail_count = sum(1 for finding in findings if finding.status == "FAIL")

        penalty = min(2.5, warning_count * 0.12 + fail_count * 0.45)
        score = max(0.0, min(10.0, raw - penalty))

        # Prevent concept-stage reports from receiving perfect scores while
        # they still contain warnings.
        if warning_count > 0:
            score = min(score, 8.6)

        if fail_count > 0:
            score = min(score, 7.4)

        return round(score, 2)

    def _verdict_from_score(
        self,
        score: float,
        findings: List[ValidationFinding],
        text: str,
    ) -> str:
        fail_count = sum(1 for finding in findings if finding.status == "FAIL")
        warning_count = sum(1 for finding in findings if finding.status == "WARNING")

        has_objective_evidence_warning = any(
            finding.category == "Objective Evidence"
            and finding.status in {"WARNING", "FAIL"}
            for finding in findings
        )

        has_pending_unknowns = self._contains_any(
            text,
            [
                "unknown",
                "must be checked",
                "needs to measure",
                "still needs",
                "pending",
                "to be confirmed",
            ],
        )

        if fail_count >= 4 or score < 5.0:
            return "FAIL"

        if fail_count > 0:
            return "CONDITIONAL PASS"

        if warning_count > 0 or has_objective_evidence_warning or has_pending_unknowns:
            return "CONDITIONAL PASS"

        if score < 9.0:
            return "CONDITIONAL PASS"

        return "PASS"

    def _collect_missing_evidence(
        self,
        findings: List[ValidationFinding],
    ) -> List[str]:
        missing = []

        for finding in findings:
            if finding.status in {"FAIL", "WARNING"}:
                missing.append(finding.message)

        return self._dedupe_preserve_order(missing)

    def _recommend_next_tests(
        self,
        findings: List[ValidationFinding],
        artifact_type: str,
    ) -> List[str]:
        tests = []
        categories_with_failures = {
            finding.category
            for finding in findings
            if finding.status == "FAIL"
        }
        categories_with_warnings = {
            finding.category
            for finding in findings
            if finding.status == "WARNING"
        }

        if "Systems Engineering" in categories_with_failures:
            tests.append(
                "Create a requirements-verification-validation matrix before continuing."
            )

        if (
            "Physics" in categories_with_failures
            or "Physics" in categories_with_warnings
        ):
            tests.append(
                "Run a unit and dimensional-analysis pass on every numerical claim."
            )

        if (
            "Mechanical" in categories_with_failures
            or "Mechanical" in categories_with_warnings
        ):
            tests.append(
                "Measure component mass, estimate load path, and verify mounting/clearance dimensions."
            )

        if (
            "Electrical / Power" in categories_with_failures
            or "Electrical / Power" in categories_with_warnings
        ):
            tests.append(
                "Create a power budget with voltage, estimated current draw per component, total current, and protection method."
            )

        if (
            "Controls" in categories_with_failures
            or "Controls" in categories_with_warnings
        ):
            tests.append(
                "Define the closed-loop control architecture and run a servo sweep/stability test."
            )

        if (
            "Robotics Dynamics" in categories_with_failures
            or "Drone Feasibility" in categories_with_failures
        ):
            tests.append(
                "Calculate mass, thrust-to-weight ratio, center of mass, moment of inertia, and actuator limits."
            )

        if (
            "Planning / Autonomy" in categories_with_failures
            or "Planning / Autonomy" in categories_with_warnings
        ):
            tests.append(
                "Define state space, action space, initial state, goal state, constraints, and feasibility criterion."
            )

        if (
            "Estimation / Sensor Fusion" in categories_with_failures
            or "Estimation / Sensor Fusion" in categories_with_warnings
        ):
            tests.append(
                "Define sensor suite, state vector, prediction model, measurement model, calibration method, and noise assumptions."
            )

        if (
            "ROS2 Architecture" in categories_with_failures
            or "ROS2 Architecture" in categories_with_warnings
        ):
            tests.append(
                "Generate ROS2 package files, launch file, node tests, and topic echo verification commands."
            )

        if (
            "CAD / Fusion 360" in categories_with_failures
            or "CAD / Fusion 360" in categories_with_warnings
        ):
            tests.append(
                "Create Fusion 360 parameters, mounting dimensions, material assumptions, and an enclosure clearance checklist."
            )

        if "Objective Evidence" in categories_with_warnings:
            tests.append(
                "Collect objective evidence: measurements, datasheets, simulation logs, ROS2 bag output, or prototype test results."
            )

        if "Safety Gates" in categories_with_failures:
            tests.append(
                "Define stop conditions before running any hardware or movement test."
            )

        if not tests:
            tests.append(
                "Proceed to simulation or prototype test with logged results as objective evidence."
            )

        return self._dedupe_preserve_order(tests)

    # -------------------------
    # Helpers
    # -------------------------

    def _contains_any(self, text: str, terms: List[str]) -> bool:
        lower = self._as_text(text).lower()
        return any(term.lower() in lower for term in terms)

    def _sanitize_legacy_names(self, text: Any) -> Any:
        """
        Compatibility wrapper around the centralized OMNI formatter.

        This replaces the old local replacement dictionary.
        """
        return format_sanitize_legacy_names(text)

    def _as_text(self, value: Any) -> str:
        if value is None:
            return ""
        return str(value)

    def _dedupe_preserve_order(self, items: List[str]) -> List[str]:
        seen = set()
        deduped = []

        for item in items:
            if item not in seen:
                seen.add(item)
                deduped.append(item)

        return deduped

    def _pass(
        self,
        category: str,
        message: str,
        recommendation: str,
        source: str,
    ) -> ValidationFinding:
        return ValidationFinding(
            category=category,
            status="PASS",
            message=message,
            recommendation=recommendation,
            source_basis=source,
        )

    def _warning(
        self,
        category: str,
        message: str,
        recommendation: str,
        source: str,
    ) -> ValidationFinding:
        return ValidationFinding(
            category=category,
            status="WARNING",
            message=message,
            recommendation=recommendation,
            source_basis=source,
        )

    def _fail(
        self,
        category: str,
        message: str,
        recommendation: str,
        source: str,
    ) -> ValidationFinding:
        return ValidationFinding(
            category=category,
            status="FAIL",
            message=message,
            recommendation=recommendation,
            source_basis=source,
        )