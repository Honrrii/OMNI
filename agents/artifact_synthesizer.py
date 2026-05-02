import json
import re
from agents.llm_clients import openai_client


def get_empty_artifacts():
    return {
        "ros2_node_graph": {
            "nodes": [],
            "edges": [],
        },
        "component_tree": [],
        "blueprint_plan": [],
        "hardware_architecture": [],
        "fusion360_concept": {
            "parameters": [],
            "modeling_steps": [],
            "components": [],
            "manufacturing_notes": [],
            "missing_cad_inputs": [],
        },
        "ros2_package_plan": {
            "package_name": "",
            "nodes": [],
            "topics": [],
            "services": [],
            "launch_files": [],
            "folder_structure": [],
            "starter_files": [],
            "missing_ros2_inputs": [],
        },
        "risk_matrix": [],
        "test_checklist": [],
        "approval_gates": [],
        "export_files": [],
        "next_artifacts": [],
    }


def sanitize_legacy_names(value):
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
        "Reed": "Omni",
        "Tony": "Sky",
        "Bruce": "Isy",
        "Hank": "Oli",
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


def mission_mentions_ros2(mission, sky_report):
    combined = f"{mission}\n{sky_report}".lower()
    return any(term in combined for term in ["ros2", "ros 2", "node", "topic", "launch"])


def mission_mentions_cad(mission, oli_report):
    combined = f"{mission}\n{oli_report}".lower()
    return any(
        term in combined
        for term in ["fusion 360", "fusion360", "cad", "3d", "chassis", "enclosure", "modeling"]
    )


def safe_id(text):
    value = re.sub(r"[^a-zA-Z0-9_]+", "_", text.strip().lower())
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "item"


def extract_ros2_nodes_from_report(sky_report):
    """
    Extracts common ROS2 node names from Sky's report.
    Looks for names like:
    - rover_control_node
    - distance_sensor_node
    - camera_node
    """
    if not sky_report:
        return []

    matches = re.findall(r"\b[a-zA-Z][a-zA-Z0-9_]*_node\b", sky_report)
    unique = []

    for match in matches:
        clean = match.strip()
        if clean not in unique:
            unique.append(clean)

    return unique


def infer_node_type(node_name):
    name = node_name.lower()

    if any(term in name for term in ["camera", "imu", "distance", "ultrasonic", "sensor", "lidar"]):
        return "sensor"

    if any(term in name for term in ["control", "controller", "cmd", "motor", "actuator"]):
        return "control"

    if any(term in name for term in ["battery", "telemetry", "monitor", "logger"]):
        return "telemetry"

    if any(term in name for term in ["planning", "nav", "path"]):
        return "planning"

    return "utility"


def extract_ros2_topics_from_report(sky_report):
    """
    Extracts ROS2 topic names from Sky's report.
    Looks for /cmd_vel, /imu_data, /camera/image_raw, etc.
    """
    if not sky_report:
        return []

    matches = re.findall(r"\/[a-zA-Z0-9_\/]+", sky_report)
    ignored = {"/", "/10"}
    unique = []

    for match in matches:
        clean = match.strip().rstrip(".,;:)")
        if clean not in ignored and clean not in unique:
            unique.append(clean)

    return unique


def infer_message_type(topic):
    lower = topic.lower()

    if "cmd_vel" in lower:
        return "geometry_msgs/Twist"

    if "imu" in lower:
        return "sensor_msgs/Imu"

    if "camera" in lower or "image" in lower:
        return "sensor_msgs/Image"

    if "battery" in lower:
        return "sensor_msgs/BatteryState"

    if "distance" in lower or "range" in lower or "ultrasonic" in lower:
        return "std_msgs/Float32"

    return "unknown"


def infer_topic_purpose(topic):
    lower = topic.lower()

    if "cmd_vel" in lower:
        return "Velocity command topic for rover motion control."

    if "imu" in lower:
        return "Publishes orientation and motion data from the IMU."

    if "camera" in lower or "image" in lower:
        return "Publishes camera frames for perception or monitoring."

    if "battery" in lower:
        return "Publishes battery or power status."

    if "distance" in lower or "range" in lower or "ultrasonic" in lower:
        return "Publishes obstacle distance readings."

    return "ROS2 communication topic inferred from Sky report."


def repair_ros2_artifacts(artifacts, mission, sky_report):
    """
    Repairs weak ROS2 artifacts when the LLM produced empty node graph/package plan
    even though Sky's report contains useful node/topic details.
    """
    if not mission_mentions_ros2(mission, sky_report):
        return artifacts

    ros2_graph = artifacts.setdefault("ros2_node_graph", {"nodes": [], "edges": []})
    ros2_plan = artifacts.setdefault("ros2_package_plan", get_empty_artifacts()["ros2_package_plan"])

    nodes = ros2_graph.get("nodes", [])
    edges = ros2_graph.get("edges", [])

    extracted_nodes = extract_ros2_nodes_from_report(sky_report)
    extracted_topics = extract_ros2_topics_from_report(sky_report)

    if not extracted_nodes:
        extracted_nodes = [
            "rover_control_node",
            "distance_sensor_node",
            "imu_sensor_node",
            "camera_node",
            "battery_monitor_node",
        ]

    if not extracted_topics:
        extracted_topics = [
            "/cmd_vel",
            "/distance_data",
            "/imu_data",
            "/camera/image_raw",
            "/battery_status",
        ]

    if not nodes:
        nodes = [
            {
                "id": safe_id(node_name),
                "label": node_name,
                "type": infer_node_type(node_name),
                "description": f"ROS2 node inferred from Sky report: {node_name}.",
            }
            for node_name in extracted_nodes
        ]

    if not edges:
        control_id = safe_id("rover_control_node")
        node_ids = {node["id"] for node in nodes}

        topic_sources = {
            "/distance_data": "distance_sensor_node",
            "/imu_data": "imu_sensor_node",
            "/camera/image_raw": "camera_node",
            "/battery_status": "battery_monitor_node",
        }

        for topic in extracted_topics:
            if topic == "/cmd_vel":
                continue

            source_node = topic_sources.get(topic, "")
            source_id = safe_id(source_node) if source_node else ""

            if source_id in node_ids and control_id in node_ids:
                edges.append(
                    {
                        "source": source_id,
                        "target": control_id,
                        "topic": topic,
                        "message_type": infer_message_type(topic),
                    }
                )

    ros2_graph["nodes"] = nodes
    ros2_graph["edges"] = edges
    artifacts["ros2_node_graph"] = ros2_graph

    if not ros2_plan.get("package_name"):
        package_match = re.search(r"\b([a-zA-Z][a-zA-Z0-9_]*rover[a-zA-Z0-9_]*)\b", sky_report)
        ros2_plan["package_name"] = package_match.group(1).lower() if package_match else "smart_rover"

    if not ros2_plan.get("nodes"):
        ros2_plan["nodes"] = [
            {
                "name": node_name,
                "language": "python",
                "purpose": f"ROS2 node inferred from Sky report: {node_name}.",
                "publishes": [
                    topic for topic in extracted_topics
                    if safe_id(node_name).replace("_node", "") in topic.replace("/", "_")
                ],
                "subscribes": [],
                "parameters": [],
            }
            for node_name in extracted_nodes
        ]

    if not ros2_plan.get("topics"):
        ros2_plan["topics"] = [
            {
                "name": topic,
                "message_type": infer_message_type(topic),
                "purpose": infer_topic_purpose(topic),
            }
            for topic in extracted_topics
        ]

    if not ros2_plan.get("launch_files"):
        package_name = ros2_plan.get("package_name") or "smart_rover"
        ros2_plan["launch_files"] = [
            {
                "name": f"{package_name}_launch.py",
                "purpose": "Launches the core ROS2 rover nodes for integration testing.",
                "nodes_started": extracted_nodes,
            }
        ]

    if not ros2_plan.get("folder_structure"):
        package_name = ros2_plan.get("package_name") or "smart_rover"
        ros2_plan["folder_structure"] = [
            f"{package_name}/",
            f"{package_name}/package.xml",
            f"{package_name}/setup.py",
            f"{package_name}/launch/{package_name}_launch.py",
            f"{package_name}/{package_name}/",
            f"{package_name}/test/",
        ]

    if not ros2_plan.get("starter_files"):
        package_name = ros2_plan.get("package_name") or "smart_rover"
        ros2_plan["starter_files"] = [
            {
                "path": f"{package_name}/package.xml",
                "purpose": "ROS2 package metadata and dependencies.",
            },
            {
                "path": f"{package_name}/setup.py",
                "purpose": "Python package build configuration.",
            },
            {
                "path": f"{package_name}/launch/{package_name}_launch.py",
                "purpose": "Launches the rover ROS2 nodes.",
            },
        ]

    if not ros2_plan.get("missing_ros2_inputs"):
        ros2_plan["missing_ros2_inputs"] = [
            "Confirm exact sensor drivers and ROS2 packages.",
            "Confirm whether nodes should be Python or C++.",
            "Confirm topic names before generating package files.",
            "Confirm simulation target: Gazebo, RViz-only, or physical rover first.",
        ]

    artifacts["ros2_package_plan"] = ros2_plan
    return artifacts


def repair_fusion360_artifacts(artifacts, mission, oli_report):
    """
    Repairs weak Fusion 360 artifacts when the LLM leaves parameters/components empty.
    """
    if not mission_mentions_cad(mission, oli_report):
        return artifacts

    concept = artifacts.setdefault("fusion360_concept", get_empty_artifacts()["fusion360_concept"])

    if not concept.get("parameters"):
        concept["parameters"] = [
            {
                "name": "chassis_length",
                "value": "unknown",
                "unit": "mm",
                "reason": "Henry must confirm final rover length before CAD modeling.",
            },
            {
                "name": "chassis_width",
                "value": "unknown",
                "unit": "mm",
                "reason": "Henry must confirm final rover width before CAD modeling.",
            },
            {
                "name": "wheel_diameter",
                "value": "unknown",
                "unit": "mm",
                "reason": "Wheel size affects chassis clearance and motor placement.",
            },
            {
                "name": "mounting_hole_diameter",
                "value": "unknown",
                "unit": "mm",
                "reason": "Mounting holes depend on actual component screws and standoffs.",
            },
        ]

    if not concept.get("components"):
        concept["components"] = [
            {
                "name": "Main Chassis Plate",
                "body_or_component": "component",
                "purpose": "Base structure for mounting rover electronics, motors, sensors, and battery.",
                "mounting_or_clearance_notes": "Requires confirmed component footprints, screw sizes, and cable clearances.",
            },
            {
                "name": "Motor Mounts",
                "body_or_component": "component",
                "purpose": "Secure the two DC gear motors to the chassis.",
                "mounting_or_clearance_notes": "Requires actual motor dimensions and shaft alignment.",
            },
            {
                "name": "Sensor Front Bracket",
                "body_or_component": "component",
                "purpose": "Holds ultrasonic sensor and optional camera/front-facing module.",
                "mounting_or_clearance_notes": "Requires sensor field-of-view and height clearance checks.",
            },
            {
                "name": "Battery Bay",
                "body_or_component": "component",
                "purpose": "Secures battery while keeping center of gravity low.",
                "mounting_or_clearance_notes": "Requires actual battery dimensions and strap/cable routing.",
            },
        ]

    if not concept.get("modeling_steps"):
        concept["modeling_steps"] = [
            {
                "step": "Create chassis base sketch",
                "fusion360_action": "sketch",
                "details": "Sketch a rectangular chassis using confirmed length and width parameters.",
            },
            {
                "step": "Extrude chassis plate",
                "fusion360_action": "extrude",
                "details": "Extrude the chassis to a printable plate thickness after choosing material.",
            },
            {
                "step": "Add motor mounting zones",
                "fusion360_action": "sketch",
                "details": "Place motor mount holes using actual motor bracket dimensions.",
            },
            {
                "step": "Add electronics mounting holes",
                "fusion360_action": "sketch",
                "details": "Add Raspberry Pi, sensor, IMU, and battery mounting features.",
            },
            {
                "step": "Add edge fillets",
                "fusion360_action": "fillet",
                "details": "Round exposed chassis edges for safer handling.",
            },
            {
                "step": "Inspect clearances",
                "fusion360_action": "inspect",
                "details": "Check wheel clearance, cable routing, sensor field of view, and battery access.",
            },
        ]

    if not concept.get("manufacturing_notes"):
        concept["manufacturing_notes"] = [
            "Start as a 3D-printed prototype before designing a custom PCB or final chassis.",
            "Avoid final CAD dimensions until component footprints are measured.",
            "Use fillets on exposed edges and leave service access for wiring.",
            "Keep the battery low and centered to improve stability.",
        ]

    missing = concept.get("missing_cad_inputs", [])
    required_missing = [
        "Final chassis length, width, and thickness.",
        "Exact DC gear motor dimensions and mounting pattern.",
        "Wheel diameter and axle/shaft geometry.",
        "Battery dimensions and weight.",
        "Raspberry Pi mounting hole pattern and standoff height.",
        "Material choice: PLA, PETG, acrylic, aluminum, or other.",
    ]

    for item in required_missing:
        if item not in missing:
            missing.append(item)

    concept["missing_cad_inputs"] = missing
    artifacts["fusion360_concept"] = concept
    return artifacts


def repair_export_files(artifacts):
    """
    Ensures the export_files artifact is useful even when the LLM returns only 1-2 files.
    """
    standard_files = [
        {
            "path": "mission.json",
            "file_type": "json",
            "purpose": "Full structured OMNI mission response.",
            "generated_from": "Artifact Synthesizer",
        },
        {
            "path": "mission_report.md",
            "file_type": "md",
            "purpose": "Readable mission report with agent outputs and validation.",
            "generated_from": "Omni",
        },
        {
            "path": "agent_reports/sky.md",
            "file_type": "md",
            "purpose": "Sky robotics and ROS2 architecture report.",
            "generated_from": "Sky",
        },
        {
            "path": "agent_reports/korva.md",
            "file_type": "md",
            "purpose": "Korva hardware and electronics report.",
            "generated_from": "Korva",
        },
        {
            "path": "agent_reports/isy.md",
            "file_type": "md",
            "purpose": "Isy physics, controls, and feasibility report.",
            "generated_from": "Isy",
        },
        {
            "path": "agent_reports/oli.md",
            "file_type": "md",
            "purpose": "Oli CAD and Fusion 360 concept report.",
            "generated_from": "Oli",
        },
        {
            "path": "agent_reports/pluto.md",
            "file_type": "md",
            "purpose": "Pluto risk critique and safety gates.",
            "generated_from": "Pluto",
        },
        {
            "path": "agent_reports/qaz.md",
            "file_type": "md",
            "purpose": "QaZ validation report.",
            "generated_from": "QaZ",
        },
        {
            "path": "artifacts/ros2_node_graph.json",
            "file_type": "json",
            "purpose": "ROS2 node graph for dashboard visualization.",
            "generated_from": "Artifact Synthesizer",
        },
        {
            "path": "artifacts/fusion360_concept.json",
            "file_type": "json",
            "purpose": "Fusion 360 concept parameters, components, and modeling steps.",
            "generated_from": "Artifact Synthesizer",
        },
        {
            "path": "artifacts/ros2_package_plan.json",
            "file_type": "json",
            "purpose": "ROS2 package scaffold plan.",
            "generated_from": "Artifact Synthesizer",
        },
        {
            "path": "artifacts/risk_matrix.csv",
            "file_type": "csv",
            "purpose": "Risk matrix export for engineering review.",
            "generated_from": "Pluto",
        },
        {
            "path": "artifacts/test_checklist.md",
            "file_type": "md",
            "purpose": "Validation and safety test checklist.",
            "generated_from": "QaZ",
        },
    ]

    existing = artifacts.get("export_files", [])
    existing_paths = {
        item.get("path")
        for item in existing
        if isinstance(item, dict)
    }

    for item in standard_files:
        if item["path"] not in existing_paths:
            existing.append(item)

    artifacts["export_files"] = existing
    return artifacts


def repair_next_artifacts(artifacts):
    required = [
        {
            "name": "ROS2 Node Graph",
            "artifact_type": "ros2_graph",
            "purpose": "Visualize ROS2 nodes, topics, and message flow.",
            "generated_by": "Sky",
        },
        {
            "name": "Fusion 360 Concept",
            "artifact_type": "fusion360_concept",
            "purpose": "Prepare CAD modeling parameters, component layout, and missing measurements.",
            "generated_by": "Oli",
        },
        {
            "name": "Hardware Wiring Plan",
            "artifact_type": "wiring_plan",
            "purpose": "Document power, GPIO, I2C, PWM, and sensor wiring.",
            "generated_by": "Korva",
        },
        {
            "name": "Risk Matrix",
            "artifact_type": "risk_matrix",
            "purpose": "Track major failure modes, severity, likelihood, and mitigation.",
            "generated_by": "Pluto",
        },
        {
            "name": "Mission Export Bundle",
            "artifact_type": "export_bundle",
            "purpose": "Package mission report, agent reports, and artifacts into files.",
            "generated_by": "Omni",
        },
    ]

    existing = artifacts.get("next_artifacts", [])
    existing_names = {
        item.get("name")
        for item in existing
        if isinstance(item, dict)
    }

    for item in required:
        if item["name"] not in existing_names:
            existing.append(item)

    artifacts["next_artifacts"] = existing
    return artifacts


def repair_artifacts(artifacts, mission, sky_report, oli_report):
    artifacts = repair_ros2_artifacts(artifacts, mission, sky_report)
    artifacts = repair_fusion360_artifacts(artifacts, mission, oli_report)
    artifacts = repair_export_files(artifacts)
    artifacts = repair_next_artifacts(artifacts)
    return artifacts


def synthesize_artifacts(
    mission,
    reed_output=None,
    tony_output=None,
    bruce_output=None,
    hank_output=None,
    ultron_output=None,
    korva_output=None,
    omni_output=None,
    sky_output=None,
    isy_output=None,
    oli_output=None,
    pluto_output=None,
):
    """
    Converts OMNI agent reports into visualization-ready and export-ready artifacts.

    Backward compatibility:
    - supervisor.py may still call this with reed_output, tony_output, etc.
    - Newer code can call it with omni_output, sky_output, korva_output, etc.
    """

    omni_report = sanitize_legacy_names(omni_output or reed_output or "")
    sky_report = sanitize_legacy_names(sky_output or tony_output or "")
    korva_report = sanitize_legacy_names(korva_output or "")
    isy_report = sanitize_legacy_names(isy_output or bruce_output or "")
    oli_report = sanitize_legacy_names(oli_output or hank_output or "")
    pluto_report = sanitize_legacy_names(pluto_output or ultron_output or "")

    prompt = f"""
You are the Artifact Synthesizer for OMNI Command.

Your job is to convert multi-agent engineering reports into STRICT visualization-ready and export-ready JSON.

You are not part of a superhero system.
Use only these OMNI agent names:
- Omni: mission orchestration and system integration
- Sky: robotics, ROS2, drones, autonomy, software architecture
- Korva: hardware, electronics, embedded systems, wiring, PCB
- Isy: physics, controls, dynamics, feasibility
- Oli: CAD, Fusion 360, 3D concepts, visual artifacts
- Pluto: risk, failure analysis, safety gates
- QaZ: validation, scoring, requirements verification
- Henry: human decision maker

Return ONLY valid JSON.
Do not include markdown.
Do not include explanations.
Do not include code fences.

Mission:
{mission}

Omni Report:
{omni_report}

Sky Report:
{sky_report}

Korva Report:
{korva_report}

Isy Report:
{isy_report}

Oli Report:
{oli_report}

Pluto Report:
{pluto_report}

Return JSON with this exact top-level structure:

{{
  "ros2_node_graph": {{
    "nodes": [
      {{
        "id": "string",
        "label": "string",
        "type": "sensor | control | planning | actuator | telemetry | utility | supervisor | compute | visualization | storage | interface",
        "description": "string"
      }}
    ],
    "edges": [
      {{
        "source": "string",
        "target": "string",
        "topic": "string",
        "message_type": "string"
      }}
    ]
  }},

  "component_tree": [
    {{
      "name": "string",
      "category": "mechanical | electrical | sensor | actuator | compute | software | safety | visualization | power | communication | enclosure",
      "purpose": "string",
      "owner": "Omni | Sky | Korva | Isy | Oli | Pluto | QaZ | Henry",
      "children": []
    }}
  ],

  "blueprint_plan": [
    {{
      "zone": "string",
      "component": "string",
      "placement": "string",
      "notes": "string",
      "owner": "Omni | Sky | Korva | Isy | Oli | Pluto | QaZ | Henry"
    }}
  ],

  "hardware_architecture": [
    {{
      "subsystem": "string",
      "components": ["string"],
      "power_or_signal_notes": "string",
      "interfaces": ["GPIO | I2C | SPI | UART | USB | PWM | CAN | analog | power | unknown"],
      "owner": "Korva"
    }}
  ],

  "fusion360_concept": {{
    "parameters": [
      {{
        "name": "string",
        "value": "string",
        "unit": "mm | deg | count | g | kg | unknown",
        "reason": "string"
      }}
    ],
    "modeling_steps": [
      {{
        "step": "string",
        "fusion360_action": "sketch | extrude | revolve | fillet | chamfer | pattern | shell | joint | assemble | inspect",
        "details": "string"
      }}
    ],
    "components": [
      {{
        "name": "string",
        "body_or_component": "body | component | assembly",
        "purpose": "string",
        "mounting_or_clearance_notes": "string"
      }}
    ],
    "manufacturing_notes": ["string"],
    "missing_cad_inputs": ["string"]
  }},

  "ros2_package_plan": {{
    "package_name": "string",
    "nodes": [
      {{
        "name": "string",
        "language": "python | cpp | unknown",
        "purpose": "string",
        "publishes": ["string"],
        "subscribes": ["string"],
        "parameters": ["string"]
      }}
    ],
    "topics": [
      {{
        "name": "string",
        "message_type": "string",
        "purpose": "string"
      }}
    ],
    "services": [
      {{
        "name": "string",
        "service_type": "string",
        "purpose": "string"
      }}
    ],
    "launch_files": [
      {{
        "name": "string",
        "purpose": "string",
        "nodes_started": ["string"]
      }}
    ],
    "folder_structure": ["string"],
    "starter_files": [
      {{
        "path": "string",
        "purpose": "string"
      }}
    ],
    "missing_ros2_inputs": ["string"]
  }},

  "risk_matrix": [
    {{
      "risk": "string",
      "severity": "low | medium | high | critical",
      "likelihood": "low | medium | high",
      "mitigation": "string",
      "owner": "Omni | Sky | Korva | Isy | Oli | Pluto | QaZ | Henry"
    }}
  ],

  "test_checklist": [
    {{
      "subsystem": "string",
      "test": "string",
      "success_criteria": "string",
      "safety_note": "string",
      "owner": "Omni | Sky | Korva | Isy | Oli | Pluto | QaZ | Henry",
      "status": "pending"
    }}
  ],

  "approval_gates": [
    {{
      "gate": "string",
      "required_decision": "string",
      "reason": "string",
      "owner": "Henry",
      "status": "needs_review"
    }}
  ],

  "export_files": [
    {{
      "path": "string",
      "file_type": "json | md | txt | csv | py | cpp | xml | yaml | launch.py",
      "purpose": "string",
      "generated_from": "Omni | Sky | Korva | Isy | Oli | Pluto | QaZ | Artifact Synthesizer"
    }}
  ],

  "next_artifacts": [
    {{
      "name": "string",
      "artifact_type": "ros2_graph | component_tree | wiring_plan | blueprint | risk_matrix | checklist | report | dashboard_panel | fusion360_concept | fusion360_script | ros2_package | export_bundle",
      "purpose": "string",
      "generated_by": "Omni | Sky | Korva | Isy | Oli | Pluto | QaZ"
    }}
  ]
}}

Rules:
- Keep artifact entries practical and concise.
- Every risk must include a mitigation.
- Every approval gate must require a human decision from Henry.
- If the mission has ROS2 relevance, ros2_node_graph and ros2_package_plan must not be empty.
- If the mission has CAD or Fusion 360 relevance, fusion360_concept must not be empty.
- Do not invent final exact hardware specs unless the agent reports clearly imply them.
- Use "unknown" when exact units, message types, dimensions, or interfaces are not specified.
- Make the output useful for frontend visualization and future file export.
- Do not use Reed, Tony, Bruce, Hank, Ultron, Vision, Shuri, Avengers, or Marvel anywhere.
"""

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You produce strict JSON for OMNI engineering visualization "
                        "artifacts. You never use Marvel or Avengers naming."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        artifacts = json.loads(content)
        artifacts = normalize_artifacts(sanitize_legacy_names(artifacts))
        artifacts = repair_artifacts(
            artifacts=artifacts,
            mission=mission,
            sky_report=sky_report,
            oli_report=oli_report,
        )

        return normalize_artifacts(sanitize_legacy_names(artifacts))

    except Exception as error:
        print(f"[Artifact Synthesizer] Failed to generate artifacts: {error}")

        artifacts = get_empty_artifacts()
        artifacts = repair_artifacts(
            artifacts=artifacts,
            mission=mission,
            sky_report=sky_report,
            oli_report=oli_report,
        )

        return normalize_artifacts(sanitize_legacy_names(artifacts))


def normalize_artifacts(artifacts):
    default = get_empty_artifacts()

    if not isinstance(artifacts, dict):
        return default

    for key, value in default.items():
        if key not in artifacts:
            artifacts[key] = value

    if not isinstance(artifacts.get("ros2_node_graph"), dict):
        artifacts["ros2_node_graph"] = default["ros2_node_graph"]

    if "nodes" not in artifacts["ros2_node_graph"]:
        artifacts["ros2_node_graph"]["nodes"] = []

    if "edges" not in artifacts["ros2_node_graph"]:
        artifacts["ros2_node_graph"]["edges"] = []

    list_keys = [
        "component_tree",
        "blueprint_plan",
        "hardware_architecture",
        "risk_matrix",
        "test_checklist",
        "approval_gates",
        "export_files",
        "next_artifacts",
    ]

    for key in list_keys:
        if not isinstance(artifacts.get(key), list):
            artifacts[key] = []

    if not isinstance(artifacts.get("fusion360_concept"), dict):
        artifacts["fusion360_concept"] = default["fusion360_concept"]

    for key, value in default["fusion360_concept"].items():
        if key not in artifacts["fusion360_concept"]:
            artifacts["fusion360_concept"][key] = value

        if not isinstance(artifacts["fusion360_concept"].get(key), list):
            artifacts["fusion360_concept"][key] = value

    if not isinstance(artifacts.get("ros2_package_plan"), dict):
        artifacts["ros2_package_plan"] = default["ros2_package_plan"]

    for key, value in default["ros2_package_plan"].items():
        if key not in artifacts["ros2_package_plan"]:
            artifacts["ros2_package_plan"][key] = value

        if isinstance(value, list) and not isinstance(artifacts["ros2_package_plan"].get(key), list):
            artifacts["ros2_package_plan"][key] = value

    return sanitize_legacy_names(artifacts)