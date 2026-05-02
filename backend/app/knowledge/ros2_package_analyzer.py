import ast
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_EXAMPLES_DIR = PROJECT_ROOT / "knowledge" / "ros2_examples"
DEFAULT_PATTERNS_DIR = PROJECT_ROOT / "knowledge" / "ros2_patterns"


TEXT_FILE_EXTENSIONS = {
    ".py",
    ".xml",
    ".yaml",
    ".yml",
    ".md",
    ".txt",
    ".cfg",
    ".launch",
    ".xacro",
    ".urdf",
    ".rviz",
}


def safe_name(value: str, fallback: str = "ros2_package") -> str:
    text = str(value or fallback).lower().strip()
    text = re.sub(r"[^a-z0-9_]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or fallback


def read_text_safe(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def relative_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except Exception:
        return str(path)


def list_files(package_dir: Path) -> List[str]:
    files = []

    for path in package_dir.rglob("*"):
        if path.is_file():
            if any(part.startswith(".") for part in path.parts):
                continue

            files.append(relative_path(path, package_dir))

    return sorted(files)


def list_directories(package_dir: Path) -> List[str]:
    directories = []

    for path in package_dir.rglob("*"):
        if path.is_dir():
            if any(part.startswith(".") for part in path.parts):
                continue

            directories.append(relative_path(path, package_dir))

    return sorted(directories)


def detect_package_name(package_dir: Path) -> str:
    package_xml = package_dir / "package.xml"

    if package_xml.exists():
        try:
            root = ET.fromstring(read_text_safe(package_xml))
            name = root.findtext("name")

            if name:
                return name.strip()
        except Exception:
            pass

    setup_py = package_dir / "setup.py"

    if setup_py.exists():
        text = read_text_safe(setup_py)
        match = re.search(r'name\s*=\s*["\']([^"\']+)["\']', text)

        if match:
            return match.group(1).strip()

        match = re.search(r'package_name\s*=\s*["\']([^"\']+)["\']', text)

        if match:
            return match.group(1).strip()

    return safe_name(package_dir.name)


def parse_package_xml(package_dir: Path) -> Dict[str, Any]:
    package_xml = package_dir / "package.xml"

    result = {
        "exists": package_xml.exists(),
        "name": None,
        "version": None,
        "description": None,
        "maintainers": [],
        "licenses": [],
        "buildtool_dependencies": [],
        "dependencies": [],
        "test_dependencies": [],
        "exec_dependencies": [],
        "build_dependencies": [],
        "exports": [],
    }

    if not package_xml.exists():
        return result

    try:
        root = ET.fromstring(read_text_safe(package_xml))

        result["name"] = root.findtext("name")
        result["version"] = root.findtext("version")
        result["description"] = root.findtext("description")

        for item in root.findall("maintainer"):
            result["maintainers"].append(
                {
                    "name": (item.text or "").strip(),
                    "email": item.attrib.get("email", ""),
                }
            )

        for item in root.findall("license"):
            if item.text:
                result["licenses"].append(item.text.strip())

        dependency_tags = {
            "buildtool_depend": "buildtool_dependencies",
            "depend": "dependencies",
            "test_depend": "test_dependencies",
            "exec_depend": "exec_dependencies",
            "build_depend": "build_dependencies",
        }

        for tag, key in dependency_tags.items():
            for item in root.findall(tag):
                if item.text:
                    result[key].append(item.text.strip())

        export_node = root.find("export")
        if export_node is not None:
            for child in list(export_node):
                result["exports"].append(
                    {
                        "tag": child.tag,
                        "text": (child.text or "").strip(),
                    }
                )

    except Exception as error:
        result["parse_error"] = str(error)

    return result


def parse_setup_py(package_dir: Path) -> Dict[str, Any]:
    setup_py = package_dir / "setup.py"

    result = {
        "exists": setup_py.exists(),
        "console_scripts": [],
        "packages": [],
        "data_files": [],
        "install_requires": [],
        "raw_package_name": None,
    }

    if not setup_py.exists():
        return result

    text = read_text_safe(setup_py)

    package_name_match = re.search(r'package_name\s*=\s*["\']([^"\']+)["\']', text)
    if package_name_match:
        result["raw_package_name"] = package_name_match.group(1)

    console_scripts = re.findall(
        r'["\']([^"\']+\s*=\s*[^"\']+:main)["\']',
        text,
    )
    result["console_scripts"] = sorted(console_scripts)

    install_requires_match = re.search(
        r"install_requires\s*=\s*\[([^\]]*)\]",
        text,
        re.DOTALL,
    )
    if install_requires_match:
        result["install_requires"] = re.findall(
            r'["\']([^"\']+)["\']',
            install_requires_match.group(1),
        )

    packages_match = re.search(
        r"packages\s*=\s*\[([^\]]*)\]",
        text,
        re.DOTALL,
    )
    if packages_match:
        result["packages"] = re.findall(
            r'["\']([^"\']+)["\']',
            packages_match.group(1),
        )

    if "data_files" in text:
        result["has_data_files"] = True
        result["data_file_hints"] = {
            "resource_marker": "resource/" in text,
            "package_xml": "package.xml" in text,
            "launch_files": "/launch" in text or "launch/" in text,
            "config_files": "/config" in text or "config/" in text,
            "rviz_files": "/rviz" in text or "rviz/" in text,
            "urdf_files": "/urdf" in text or "urdf/" in text,
        }

    return result


def analyze_python_node(path: Path, package_dir: Path) -> Dict[str, Any]:
    text = read_text_safe(path)

    node = {
        "file": relative_path(path, package_dir),
        "classes": [],
        "functions": [],
        "imports": [],
        "publishers": [],
        "subscribers": [],
        "timers": [],
        "parameters": [],
        "logger_messages": [],
        "has_main": False,
        "uses_rclpy": "rclpy" in text,
    }

    try:
        tree = ast.parse(text)

        for item in ast.walk(tree):
            if isinstance(item, ast.Import):
                for alias in item.names:
                    node["imports"].append(alias.name)

            elif isinstance(item, ast.ImportFrom):
                module = item.module or ""
                for alias in item.names:
                    node["imports"].append(f"{module}.{alias.name}")

            elif isinstance(item, ast.ClassDef):
                node["classes"].append(item.name)

            elif isinstance(item, ast.FunctionDef):
                node["functions"].append(item.name)

                if item.name == "main":
                    node["has_main"] = True

    except Exception as error:
        node["ast_parse_error"] = str(error)

    publisher_matches = re.findall(
        r'create_publisher\s*\(\s*([^,\n]+)\s*,\s*["\']([^"\']+)["\']',
        text,
    )
    for msg_type, topic in publisher_matches:
        node["publishers"].append(
            {
                "topic": topic,
                "message_type_hint": msg_type.strip(),
            }
        )

    subscriber_matches = re.findall(
        r'create_subscription\s*\(\s*([^,\n]+)\s*,\s*["\']([^"\']+)["\']',
        text,
    )
    for msg_type, topic in subscriber_matches:
        node["subscribers"].append(
            {
                "topic": topic,
                "message_type_hint": msg_type.strip(),
            }
        )

    timer_matches = re.findall(r"create_timer\s*\(\s*([^,\n]+)", text)
    node["timers"] = [value.strip() for value in timer_matches]

    parameter_matches = re.findall(
        r'declare_parameter\s*\(\s*["\']([^"\']+)["\']',
        text,
    )
    node["parameters"] = sorted(set(parameter_matches))

    logger_matches = re.findall(
        r'get_logger\(\)\.(?:info|warn|warning|error|debug)\s*\(\s*["\']([^"\']+)["\']',
        text,
    )
    node["logger_messages"] = logger_matches[:10]

    return node


def analyze_launch_file(path: Path, package_dir: Path) -> Dict[str, Any]:
    text = read_text_safe(path)

    launch = {
        "file": relative_path(path, package_dir),
        "nodes": [],
        "includes": [],
        "declared_arguments": [],
        "launch_configurations": [],
        "uses_launch_description": "LaunchDescription" in text,
    }

    node_blocks = re.findall(r"Node\s*\((.*?)\)", text, re.DOTALL)

    for block in node_blocks:
        package_match = re.search(r'package\s*=\s*["\']([^"\']+)["\']', block)
        executable_match = re.search(r'executable\s*=\s*["\']([^"\']+)["\']', block)
        name_match = re.search(r'name\s*=\s*["\']([^"\']+)["\']', block)

        launch["nodes"].append(
            {
                "package": package_match.group(1) if package_match else "",
                "executable": executable_match.group(1) if executable_match else "",
                "name": name_match.group(1) if name_match else "",
            }
        )

    include_matches = re.findall(r"IncludeLaunchDescription\s*\((.*?)\)", text, re.DOTALL)
    launch["includes"] = [match.strip()[:240] for match in include_matches]

    argument_matches = re.findall(
        r'DeclareLaunchArgument\s*\(\s*["\']([^"\']+)["\']',
        text,
    )
    launch["declared_arguments"] = sorted(set(argument_matches))

    configuration_matches = re.findall(
        r'LaunchConfiguration\s*\(\s*["\']([^"\']+)["\']',
        text,
    )
    launch["launch_configurations"] = sorted(set(configuration_matches))

    return launch


def analyze_config_files(package_dir: Path) -> List[Dict[str, Any]]:
    configs = []

    for path in package_dir.rglob("*"):
        if not path.is_file():
            continue

        if path.suffix.lower() not in {".yaml", ".yml", ".rviz", ".cfg"}:
            continue

        text = read_text_safe(path)

        configs.append(
            {
                "file": relative_path(path, package_dir),
                "extension": path.suffix.lower(),
                "line_count": len(text.splitlines()),
                "has_ros_parameters": "ros__parameters" in text,
                "top_level_keys_hint": extract_yaml_like_keys(text),
            }
        )

    return sorted(configs, key=lambda item: item["file"])


def extract_yaml_like_keys(text: str) -> List[str]:
    keys = []

    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue

        match = re.match(r"^([A-Za-z0-9_/\-]+)\s*:", line)

        if match:
            keys.append(match.group(1))

        if len(keys) >= 20:
            break

    return keys


def classify_package(pattern: Dict[str, Any]) -> str:
    folders = set(pattern.get("folders", []))
    dependencies = set(pattern.get("package_xml", {}).get("dependencies", []))
    files = pattern.get("files", [])

    lower_files = " ".join(files).lower()
    lower_deps = " ".join(dependencies).lower()

    if any("nav2" in dep.lower() for dep in dependencies) or "nav2" in lower_files:
        return "navigation"

    if "urdf" in folders or "xacro" in lower_files or "robot_state_publisher" in lower_deps:
        return "robot_description"

    if "launch" in folders and ("config" in folders or "param" in folders):
        return "bringup"

    if any("camera" in file.lower() for file in files):
        return "perception"

    if any("test" in folder for folder in folders):
        return "test_or_demo"

    return "general_ros2_package"


def extract_topic_contracts(nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    contracts = {}

    for node in nodes:
        node_name = Path(node["file"]).stem

        for pub in node.get("publishers", []):
            topic = pub.get("topic")
            if not topic:
                continue

            contracts.setdefault(
                topic,
                {
                    "topic": topic,
                    "message_type_hints": set(),
                    "publishers": [],
                    "subscribers": [],
                },
            )

            contracts[topic]["publishers"].append(node_name)
            contracts[topic]["message_type_hints"].add(pub.get("message_type_hint", ""))

        for sub in node.get("subscribers", []):
            topic = sub.get("topic")
            if not topic:
                continue

            contracts.setdefault(
                topic,
                {
                    "topic": topic,
                    "message_type_hints": set(),
                    "publishers": [],
                    "subscribers": [],
                },
            )

            contracts[topic]["subscribers"].append(node_name)
            contracts[topic]["message_type_hints"].add(sub.get("message_type_hint", ""))

    normalized = []

    for item in contracts.values():
        normalized.append(
            {
                "topic": item["topic"],
                "message_type_hints": sorted(
                    value for value in item["message_type_hints"] if value
                ),
                "publishers": sorted(set(item["publishers"])),
                "subscribers": sorted(set(item["subscribers"])),
            }
        )

    return sorted(normalized, key=lambda item: item["topic"])


def analyze_ros2_package(package_dir: Path) -> Dict[str, Any]:
    package_dir = Path(package_dir).resolve()

    if not package_dir.exists():
        raise FileNotFoundError(f"Package directory does not exist: {package_dir}")

    if not package_dir.is_dir():
        raise NotADirectoryError(f"Package path is not a directory: {package_dir}")

    package_name = detect_package_name(package_dir)
    files = list_files(package_dir)
    folders = list_directories(package_dir)

    python_nodes = []

    for path in package_dir.rglob("*.py"):
        relative = relative_path(path, package_dir)

        if relative.startswith("test/"):
            continue

        if path.name == "setup.py":
            continue

        python_nodes.append(analyze_python_node(path, package_dir))

    launch_files = []

    for path in package_dir.rglob("*.py"):
        if "launch" in path.parts or path.name.endswith("_launch.py"):
            launch_files.append(analyze_launch_file(path, package_dir))

    package_xml = parse_package_xml(package_dir)
    setup_py = parse_setup_py(package_dir)
    config_files = analyze_config_files(package_dir)
    topic_contracts = extract_topic_contracts(python_nodes)

    pattern = {
        "analyzer": "OMNI ROS2 Package Analyzer",
        "analyzed_at": datetime.now().isoformat(),
        "package_name": package_name,
        "package_dir": str(package_dir),
        "package_type": "unknown",
        "files": files,
        "folders": folders,
        "package_xml": package_xml,
        "setup_py": setup_py,
        "python_nodes": python_nodes,
        "launch_files": launch_files,
        "config_files": config_files,
        "topic_contracts": topic_contracts,
        "structure_features": {
            "has_package_xml": (package_dir / "package.xml").exists(),
            "has_setup_py": (package_dir / "setup.py").exists(),
            "has_setup_cfg": (package_dir / "setup.cfg").exists(),
            "has_launch_folder": (package_dir / "launch").exists(),
            "has_config_folder": (package_dir / "config").exists(),
            "has_param_folder": (package_dir / "param").exists(),
            "has_urdf_folder": (package_dir / "urdf").exists(),
            "has_rviz_folder": (package_dir / "rviz").exists(),
            "has_resource_marker": (package_dir / "resource" / package_name).exists(),
            "has_test_folder": (package_dir / "test").exists(),
        },
        "omni_lessons": [],
    }

    pattern["package_type"] = classify_package(pattern)
    pattern["omni_lessons"] = generate_omni_lessons(pattern)

    return pattern


def generate_omni_lessons(pattern: Dict[str, Any]) -> List[str]:
    lessons = []

    features = pattern.get("structure_features", {})

    if features.get("has_package_xml"):
        lessons.append("A ROS2 package should include package.xml with dependencies and build type.")

    if features.get("has_setup_py"):
        lessons.append("A Python ROS2 package should include setup.py with console_scripts entry points.")

    if features.get("has_setup_cfg"):
        lessons.append("A Python ROS2 package should include setup.cfg so ros2 launch can find executables in lib/<package_name>.")

    if features.get("has_launch_folder"):
        lessons.append("Launch files should live in launch/ and start nodes through launch_ros.actions.Node.")

    if features.get("has_config_folder") or features.get("has_param_folder"):
        lessons.append("Config or parameter YAML files should be exported when nodes need reusable runtime settings.")

    if features.get("has_resource_marker"):
        lessons.append("Ament Python packages need a resource/<package_name> marker file.")

    if pattern.get("topic_contracts"):
        lessons.append("Topic contracts should identify publishers, subscribers, and message type hints.")

    if not lessons:
        lessons.append("This package provides a general ROS2 structure pattern for future OMNI package generation.")

    return lessons


def save_pattern(pattern: Dict[str, Any], output_dir: Path = DEFAULT_PATTERNS_DIR) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    package_name = safe_name(pattern.get("package_name", "ros2_package"))
    output_path = output_dir / f"{package_name}_pattern.json"

    output_path.write_text(
        json.dumps(pattern, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return output_path


def analyze_and_save(package_dir: Path, output_dir: Path = DEFAULT_PATTERNS_DIR) -> Dict[str, Any]:
    pattern = analyze_ros2_package(package_dir)
    saved_path = save_pattern(pattern, output_dir)

    return {
        "status": "analyzed",
        "package_name": pattern["package_name"],
        "package_type": pattern["package_type"],
        "saved_path": str(saved_path),
        "node_count": len(pattern.get("python_nodes", [])),
        "launch_file_count": len(pattern.get("launch_files", [])),
        "topic_contract_count": len(pattern.get("topic_contracts", [])),
        "lessons": pattern.get("omni_lessons", []),
    }


def analyze_examples(
    examples_dir: Path = DEFAULT_EXAMPLES_DIR,
    output_dir: Path = DEFAULT_PATTERNS_DIR,
) -> List[Dict[str, Any]]:
    examples_dir = Path(examples_dir)
    results = []

    if not examples_dir.exists():
        return results

    for package_dir in sorted(examples_dir.iterdir()):
        if not package_dir.is_dir():
            continue

        try:
            results.append(analyze_and_save(package_dir, output_dir))
        except Exception as error:
            results.append(
                {
                    "status": "failed",
                    "package_dir": str(package_dir),
                    "error": str(error),
                }
            )

    return results


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Analyze ROS2 packages for OMNI.")
    parser.add_argument(
        "package_dir",
        nargs="?",
        default=None,
        help="Path to a ROS2 package folder. If omitted, analyzes knowledge/ros2_examples.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_PATTERNS_DIR),
        help="Directory where pattern JSON files are saved.",
    )

    args = parser.parse_args()

    if args.package_dir:
        result = analyze_and_save(Path(args.package_dir), Path(args.output_dir))
    else:
        result = analyze_examples(DEFAULT_EXAMPLES_DIR, Path(args.output_dir))

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()