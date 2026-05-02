import json
from pathlib import Path
from typing import Any, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PATTERNS_DIR = PROJECT_ROOT / "knowledge" / "ros2_patterns"


def load_json_file(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_ros2_patterns(patterns_dir: Path = DEFAULT_PATTERNS_DIR) -> List[Dict[str, Any]]:
    patterns_dir = Path(patterns_dir)

    if not patterns_dir.exists():
        return []

    patterns = []

    for path in sorted(patterns_dir.glob("*_pattern.json")):
        data = load_json_file(path)

        if data:
            data["_pattern_file"] = str(path)
            patterns.append(data)

    return patterns


def summarize_pattern(pattern: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "package_name": pattern.get("package_name", "unknown"),
        "package_type": pattern.get("package_type", "unknown"),
        "files": pattern.get("files", []),
        "folders": pattern.get("folders", []),
        "dependencies": pattern.get("package_xml", {}).get("dependencies", []),
        "buildtool_dependencies": pattern.get("package_xml", {}).get(
            "buildtool_dependencies", []
        ),
        "test_dependencies": pattern.get("package_xml", {}).get("test_dependencies", []),
        "console_scripts": pattern.get("setup_py", {}).get("console_scripts", []),
        "launch_files": [
            launch.get("file")
            for launch in pattern.get("launch_files", [])
            if launch.get("file")
        ],
        "config_files": [
            config.get("file")
            for config in pattern.get("config_files", [])
            if config.get("file")
        ],
        "topic_contracts": pattern.get("topic_contracts", []),
        "structure_features": pattern.get("structure_features", {}),
        "lessons": pattern.get("omni_lessons", []),
    }


def get_ros2_pattern_summaries(
    patterns_dir: Path = DEFAULT_PATTERNS_DIR,
) -> List[Dict[str, Any]]:
    return [summarize_pattern(pattern) for pattern in load_ros2_patterns(patterns_dir)]


def score_pattern_relevance(pattern: Dict[str, Any], mission_text: str) -> int:
    text = mission_text.lower()
    package_name = str(pattern.get("package_name", "")).lower()
    package_type = str(pattern.get("package_type", "")).lower()
    files = " ".join(pattern.get("files", [])).lower()
    folders = " ".join(pattern.get("folders", [])).lower()

    score = 0

    keyword_rules = [
        ("nav", ["nav", "navigation", "mapping", "localization", "path planning"]),
        ("bringup", ["bringup", "launch", "startup", "robot stack"]),
        ("description", ["urdf", "xacro", "robot description", "model", "mesh"]),
        ("control", ["control", "controller", "motor", "actuator", "ros2_control"]),
        ("perception", ["camera", "vision", "image", "detect", "tracking"]),
        ("demo", ["example", "demo", "tutorial", "publisher", "subscriber"]),
        ("topic", ["topic", "publisher", "subscriber", "message"]),
    ]

    combined_pattern_text = f"{package_name} {package_type} {files} {folders}"

    for pattern_keyword, mission_keywords in keyword_rules:
        if pattern_keyword in combined_pattern_text:
            for mission_keyword in mission_keywords:
                if mission_keyword in text:
                    score += 3

    for word in package_name.replace("_", " ").split():
        if word and word in text:
            score += 2

    if "ros2" in text or "ros 2" in text:
        score += 1

    if "rover" in text and (
        "turtlebot" in package_name or "nav2" in package_name or "control" in package_name
    ):
        score += 4

    if "drone" in text and ("control" in package_name or "demo" in package_type):
        score += 2

    return score


def get_relevant_ros2_patterns(
    mission_text: str,
    limit: int = 5,
    patterns_dir: Path = DEFAULT_PATTERNS_DIR,
) -> List[Dict[str, Any]]:
    patterns = load_ros2_patterns(patterns_dir)

    scored = []

    for pattern in patterns:
        score = score_pattern_relevance(pattern, mission_text)
        summary = summarize_pattern(pattern)
        summary["relevance_score"] = score
        scored.append(summary)

    scored.sort(key=lambda item: item["relevance_score"], reverse=True)

    return [item for item in scored[:limit] if item["relevance_score"] > 0]


def get_ros2_lessons(
    mission_text: str = "",
    limit: int = 12,
    patterns_dir: Path = DEFAULT_PATTERNS_DIR,
) -> List[str]:
    if mission_text:
        patterns = get_relevant_ros2_patterns(mission_text, limit=8, patterns_dir=patterns_dir)
    else:
        patterns = get_ros2_pattern_summaries(patterns_dir)

    lessons = []

    for pattern in patterns:
        package_name = pattern.get("package_name", "unknown_package")

        for lesson in pattern.get("lessons", []):
            entry = f"{package_name}: {lesson}"

            if entry not in lessons:
                lessons.append(entry)

            if len(lessons) >= limit:
                return lessons

    return lessons


def build_ros2_context_block(mission_text: str, limit: int = 5) -> str:
    relevant_patterns = get_relevant_ros2_patterns(mission_text, limit=limit)
    lessons = get_ros2_lessons(mission_text, limit=12)

    if not relevant_patterns and not lessons:
        return "No ROS2 package patterns are available yet."

    lines = [
        "ROS2 Pattern Knowledge Base:",
        "",
        "Relevant package patterns:",
    ]

    for pattern in relevant_patterns:
        lines.append(
            f"- {pattern['package_name']} ({pattern['package_type']}), "
            f"score={pattern['relevance_score']}"
        )

        folders = ", ".join(pattern.get("folders", [])[:8])
        dependencies = ", ".join(pattern.get("dependencies", [])[:8])
        launch_files = ", ".join(pattern.get("launch_files", [])[:6])
        config_files = ", ".join(pattern.get("config_files", [])[:6])

        if folders:
            lines.append(f"  folders: {folders}")

        if dependencies:
            lines.append(f"  dependencies: {dependencies}")

        if launch_files:
            lines.append(f"  launch files: {launch_files}")

        if config_files:
            lines.append(f"  config files: {config_files}")

        if pattern.get("topic_contracts"):
            lines.append("  topic contracts:")
            for contract in pattern["topic_contracts"][:6]:
                lines.append(
                    f"    - {contract.get('topic')}: "
                    f"pub={contract.get('publishers', [])}, "
                    f"sub={contract.get('subscribers', [])}, "
                    f"types={contract.get('message_type_hints', [])}"
                )

    lines.append("")
    lines.append("Lessons OMNI should apply:")

    for lesson in lessons:
        lines.append(f"- {lesson}")

    return "\n".join(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Load and summarize OMNI ROS2 patterns.")
    parser.add_argument(
        "--mission",
        default="",
        help="Optional mission text used to select relevant ROS2 patterns.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Number of relevant patterns to return.",
    )

    args = parser.parse_args()

    print(build_ros2_context_block(args.mission, limit=args.limit))


if __name__ == "__main__":
    main()