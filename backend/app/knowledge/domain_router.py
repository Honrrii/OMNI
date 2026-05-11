from typing import Dict, List


KNOWLEDGE_DOMAINS: Dict[str, Dict] = {
    "fabrication_patterns": {
        "description": "Manufacturing methods, joints, mounts, brackets, shells, fasteners, materials, and build constraints.",
        "keywords": [
            "fabricate", "fabrication", "manufacture", "manufacturing",
            "3d print", "3d printable", "print", "printed", "material",
            "bracket", "mount", "fastener", "bolt", "screw", "joint",
            "frame", "chassis", "assembly", "fixture", "laser cut",
            "cnc", "sheet metal", "armor", "panel", "panels"
        ],
    },
    "sci_fi_mechanical_forms": {
        "description": "Futuristic, unconventional, armored, cinematic, biomechanical, and experimental mechanical form language.",
        "keywords": [
            "sci-fi", "scifi", "futuristic", "sleek", "armored",
            "mech", "exoskeleton", "alien", "organic", "biomechanical",
            "folding", "transforming", "cybernetic", "industrial design",
            "aesthetic", "concept art", "unconventional"
        ],
    },
    "bio_inspired_robotics": {
        "description": "Biomimetic movement, insect-like locomotion, compliant bodies, tendon systems, gripping, crawling, walking, and adaptive structures.",
        "keywords": [
            "bio", "biological", "bio-inspired", "biomimetic", "biomimicry",
            "insect", "spider", "legged", "legs", "crawler", "walking",
            "tendon", "muscle", "compliant", "soft robotics", "wing",
            "fish", "snake", "gripper", "terrain adaptation"
        ],
    },
    "autonomous_machine_architecture": {
        "description": "Perception, planning, ROS2 graphs, sensor fusion, control loops, navigation, localization, mapping, and robotic decision-making.",
        "keywords": [
            "autonomous", "autonomy", "navigation", "perception",
            "planner", "planning", "sensor", "sensor fusion", "camera",
            "imu", "lidar", "control", "controller", "ros2", "node",
            "topic", "state machine", "behavior tree", "mapping",
            "localization", "slam", "edge agent"
        ],
    },
}


def route_knowledge_domains(mission_text: str) -> List[str]:
    mission = mission_text.lower()
    selected_domains = []

    for domain_name, domain_info in KNOWLEDGE_DOMAINS.items():
        for keyword in domain_info["keywords"]:
            if keyword in mission:
                selected_domains.append(domain_name)
                break

    return selected_domains


def build_knowledge_context(mission_text: str) -> Dict:
    selected_domains = route_knowledge_domains(mission_text)

    return {
        "mission_text": mission_text,
        "selected_domains": selected_domains,
        "domain_summaries": {
            domain: KNOWLEDGE_DOMAINS[domain]["description"]
            for domain in selected_domains
        },
    }
