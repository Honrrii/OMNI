import argparse
import json
import os
import signal
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_BUILD_TIMEOUT_SECONDS = 90
DEFAULT_LAUNCH_TIMEOUT_SECONDS = 10


def run_command(
    command: List[str],
    cwd: Path,
    timeout: int = 60,
    env: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Runs a shell command safely and captures output.
    """
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )

        return {
            "command": " ".join(command),
            "returncode": completed.returncode,
            "passed": completed.returncode == 0,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
            "timeout": False,
        }

    except subprocess.TimeoutExpired as error:
        return {
            "command": " ".join(command),
            "returncode": None,
            "passed": False,
            "stdout": (error.stdout or "").strip() if isinstance(error.stdout, str) else "",
            "stderr": (error.stderr or "").strip() if isinstance(error.stderr, str) else "",
            "timeout": True,
            "error": f"Command timed out after {timeout} seconds.",
        }

    except Exception as error:
        return {
            "command": " ".join(command),
            "returncode": None,
            "passed": False,
            "stdout": "",
            "stderr": "",
            "timeout": False,
            "error": str(error),
        }


def source_ros_environment_command(extra_setup: Optional[Path] = None) -> str:
    """
    Returns a bash prefix that sources ROS2 Humble and optionally a workspace install.
    """
    parts = ["source /opt/ros/humble/setup.bash"]

    if extra_setup:
        parts.append(f"source {extra_setup}")

    return " && ".join(parts)


def run_bash_command(
    command: str,
    cwd: Path,
    timeout: int = 60,
) -> Dict[str, Any]:
    """
    Runs a bash command after sourcing ROS2 Humble.
    """
    return run_command(
        ["bash", "-lc", command],
        cwd=cwd,
        timeout=timeout,
        env=os.environ.copy(),
    )


def detect_package_name(workspace_dir: Path) -> str:
    """
    Finds the first ROS2 package folder inside a generated_ros2 workspace.
    Skips colcon folders.
    """
    blocked = {"build", "install", "log", ".git", "__pycache__"}

    candidates = []

    for path in workspace_dir.iterdir():
        if not path.is_dir():
            continue

        if path.name in blocked:
            continue

        if (path / "package.xml").exists():
            candidates.append(path.name)

    if not candidates:
        raise FileNotFoundError(
            f"No ROS2 package folder with package.xml found in {workspace_dir}"
        )

    return sorted(candidates)[0]


def check_expected_files(workspace_dir: Path, package_name: str) -> Dict[str, Any]:
    package_dir = workspace_dir / package_name

    expected_files = [
        "package.xml",
        "setup.py",
        "setup.cfg",
        "README.md",
        f"launch/{package_name}_launch.py",
        "config/omni_params.yaml",
        "docs/topic_contracts.md",
        "docs/node_graph.md",
        "scripts/test_topics.sh",
        f"urdf/{package_name}.urdf.xacro",
        f"rviz/{package_name}.rviz",
        f"resource/{package_name}",
        "test/test_generated_package.py",
        f"{package_name}/__init__.py",
    ]

    missing = []
    present = []

    for rel_path in expected_files:
        full_path = package_dir / rel_path

        if full_path.exists():
            present.append(rel_path)
        else:
            missing.append(rel_path)

    node_files = sorted(
        str(path.relative_to(package_dir))
        for path in (package_dir / package_name).glob("*_node.py")
    )

    return {
        "passed": len(missing) == 0 and len(node_files) > 0,
        "package_dir": str(package_dir),
        "present_files": present,
        "missing_files": missing,
        "node_files": node_files,
        "node_file_count": len(node_files),
    }


def read_expected_topics(workspace_dir: Path, package_name: str) -> List[str]:
    """
    Extracts expected topic names from docs/topic_contracts.md.
    """
    topic_file = workspace_dir / package_name / "docs" / "topic_contracts.md"

    if not topic_file.exists():
        return []

    topics = []

    for line in topic_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()

        if not line.startswith("| `"):
            continue

        parts = line.split("|")

        if len(parts) < 3:
            continue

        topic = parts[1].strip().strip("`").strip()

        if topic.startswith("/"):
            topics.append(topic)

    return sorted(set(topics))


def colcon_build(workspace_dir: Path, package_name: str) -> Dict[str, Any]:
    command = (
        "source /opt/ros/humble/setup.bash && "
        f"colcon build --packages-select {package_name}"
    )

    return run_bash_command(
        command=command,
        cwd=workspace_dir,
        timeout=DEFAULT_BUILD_TIMEOUT_SECONDS,
    )


def list_installed_files(workspace_dir: Path, package_name: str) -> Dict[str, Any]:
    share_dir = workspace_dir / "install" / package_name / "share" / package_name

    if not share_dir.exists():
        return {
            "passed": False,
            "share_dir": str(share_dir),
            "files": [],
            "missing_reason": "Package share directory does not exist.",
        }

    files = sorted(
        str(path.relative_to(share_dir))
        for path in share_dir.rglob("*")
        if path.is_file()
    )

    required_installed = [
        "package.xml",
        "README.md",
        f"launch/{package_name}_launch.py",
        "config/omni_params.yaml",
        "docs/topic_contracts.md",
        "docs/node_graph.md",
        "scripts/test_topics.sh",
        f"urdf/{package_name}.urdf.xacro",
        f"rviz/{package_name}.rviz",
    ]

    missing = [item for item in required_installed if item not in files]

    return {
        "passed": len(missing) == 0,
        "share_dir": str(share_dir),
        "files": files,
        "missing_files": missing,
    }


def run_smoke_script(workspace_dir: Path, package_name: str) -> Dict[str, Any]:
    script_path = (
        workspace_dir
        / "install"
        / package_name
        / "share"
        / package_name
        / "scripts"
        / "test_topics.sh"
    )

    if not script_path.exists():
        return {
            "command": str(script_path),
            "passed": False,
            "error": "Smoke test script does not exist in installed package share directory.",
        }

    command = (
        "source /opt/ros/humble/setup.bash && "
        f"source {workspace_dir / 'install' / 'setup.bash'} && "
        f"bash {script_path}"
    )

    return run_bash_command(
        command=command,
        cwd=workspace_dir,
        timeout=30,
    )


def launch_package_and_check(
    workspace_dir: Path,
    package_name: str,
    expected_topics: List[str],
    launch_seconds: int = DEFAULT_LAUNCH_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    """
    Launches the generated package briefly, checks nodes and topics, then stops the process.

    This intentionally runs only for a short period because generated nodes may spin forever.
    """
    launch_command = (
        "source /opt/ros/humble/setup.bash && "
        f"source {workspace_dir / 'install' / 'setup.bash'} && "
        f"ros2 launch {package_name} {package_name}_launch.py"
    )

    process = None

    try:
        process = subprocess.Popen(
            ["bash", "-lc", launch_command],
            cwd=str(workspace_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            preexec_fn=os.setsid,
            env=os.environ.copy(),
        )

        time.sleep(launch_seconds)

        node_list_result = run_bash_command(
            command=(
                "source /opt/ros/humble/setup.bash && "
                f"source {workspace_dir / 'install' / 'setup.bash'} && "
                "ros2 node list"
            ),
            cwd=workspace_dir,
            timeout=15,
        )

        topic_list_result = run_bash_command(
            command=(
                "source /opt/ros/humble/setup.bash && "
                f"source {workspace_dir / 'install' / 'setup.bash'} && "
                "ros2 topic list"
            ),
            cwd=workspace_dir,
            timeout=15,
        )

        nodes = [
            line.strip()
            for line in node_list_result.get("stdout", "").splitlines()
            if line.strip().startswith("/")
        ]

        topics = [
            line.strip()
            for line in topic_list_result.get("stdout", "").splitlines()
            if line.strip().startswith("/")
        ]

        missing_topics = [
            topic for topic in expected_topics if topic not in topics
        ]

        return {
            "passed": node_list_result["passed"]
            and topic_list_result["passed"]
            and len(nodes) > 0
            and len(missing_topics) == 0,
            "launch_command": launch_command,
            "launch_seconds": launch_seconds,
            "nodes": nodes,
            "topics": topics,
            "expected_topics": expected_topics,
            "missing_expected_topics": missing_topics,
            "node_list_result": node_list_result,
            "topic_list_result": topic_list_result,
        }

    except Exception as error:
        return {
            "passed": False,
            "launch_command": launch_command,
            "error": str(error),
        }

    finally:
        if process and process.poll() is None:
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGINT)
                time.sleep(2)

                if process.poll() is None:
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                    time.sleep(1)

                if process.poll() is None:
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)

            except Exception:
                pass


def write_report_files(
    workspace_dir: Path,
    package_name: str,
    report: Dict[str, Any],
) -> Dict[str, str]:
    package_dir = workspace_dir / package_name
    reports_dir = package_dir / "build_reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    json_path = reports_dir / "build_report.json"
    md_path = reports_dir / "build_report.md"

    json_path.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    md_path.write_text(
        generate_markdown_report(report),
        encoding="utf-8",
    )

    return {
        "json_report": str(json_path),
        "markdown_report": str(md_path),
    }


def generate_markdown_report(report: Dict[str, Any]) -> str:
    package_name = report.get("package_name", "unknown")
    status = "PASSED" if report.get("passed") else "FAILED"

    lines = [
        f"# ROS2 Build Validation Report — {package_name}",
        "",
        f"**Status:** {status}",
        f"**Generated at:** {report.get('validated_at', 'unknown')}",
        f"**Workspace:** `{report.get('workspace_dir', '')}`",
        "",
        "## Summary",
        "",
    ]

    checks = report.get("checks", {})

    for check_name, check in checks.items():
        if isinstance(check, dict):
            check_status = "PASSED" if check.get("passed") else "FAILED"
            lines.append(f"- **{check_name}:** {check_status}")

    lines.extend(["", "## Expected Files", ""])

    file_check = checks.get("expected_files", {})
    for item in file_check.get("present_files", []):
        lines.append(f"- ✅ `{item}`")

    for item in file_check.get("missing_files", []):
        lines.append(f"- ❌ `{item}`")

    lines.extend(["", "## Nodes and Topics", ""])

    launch_check = checks.get("launch_check", {})

    if launch_check:
        lines.append("### Nodes")
        for node in launch_check.get("nodes", []):
            lines.append(f"- `{node}`")

        lines.append("")
        lines.append("### Topics")
        for topic in launch_check.get("topics", []):
            lines.append(f"- `{topic}`")

        missing_topics = launch_check.get("missing_expected_topics", [])
        if missing_topics:
            lines.append("")
            lines.append("### Missing Expected Topics")
            for topic in missing_topics:
                lines.append(f"- ❌ `{topic}`")

    lines.extend(["", "## Notes", ""])

    lines.append(
        "This validator confirms package structure, colcon build status, installed share files, "
        "smoke test script availability, and optional launch/topic behavior."
    )
    lines.append(
        "It does not prove physical hardware readiness. Hardware tests still require wiring review, "
        "power budget review, mechanical safety review, and emergency stop conditions."
    )

    return "\n".join(lines) + "\n"


def validate_ros2_package(
    workspace_dir: Path,
    package_name: Optional[str] = None,
    run_launch_check: bool = True,
    clean_build: bool = False,
) -> Dict[str, Any]:
    workspace_dir = Path(workspace_dir).resolve()

    if not workspace_dir.exists():
        raise FileNotFoundError(f"Workspace does not exist: {workspace_dir}")

    if package_name is None:
        package_name = detect_package_name(workspace_dir)

    if clean_build:
        for folder in ["build", "install", "log"]:
            target = workspace_dir / folder
            if target.exists():
                subprocess.run(["rm", "-rf", str(target)], check=False)

    expected_topics = read_expected_topics(workspace_dir, package_name)

    checks = {}

    checks["expected_files"] = check_expected_files(workspace_dir, package_name)
    checks["colcon_build"] = colcon_build(workspace_dir, package_name)
    checks["installed_files"] = list_installed_files(workspace_dir, package_name)
    checks["smoke_script"] = run_smoke_script(workspace_dir, package_name)

    if run_launch_check:
        checks["launch_check"] = launch_package_and_check(
            workspace_dir=workspace_dir,
            package_name=package_name,
            expected_topics=expected_topics,
        )

    passed = all(
        check.get("passed", False)
        for check in checks.values()
        if isinstance(check, dict)
    )

    report = {
        "validator": "OMNI ROS2 Build Validator",
        "validated_at": datetime.now().isoformat(),
        "workspace_dir": str(workspace_dir),
        "package_name": package_name,
        "passed": passed,
        "checks": checks,
    }

    report_paths = write_report_files(workspace_dir, package_name, report)
    report["report_paths"] = report_paths

    return report


def main():
    parser = argparse.ArgumentParser(description="Validate a generated OMNI ROS2 package.")
    parser.add_argument(
        "workspace_dir",
        help="Path to the generated_ros2 workspace folder.",
    )
    parser.add_argument(
        "--package",
        default=None,
        help="Package name. If omitted, the validator auto-detects it.",
    )
    parser.add_argument(
        "--no-launch",
        action="store_true",
        help="Skip ros2 launch/node/topic validation.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove build/install/log before validating.",
    )

    args = parser.parse_args()

    report = validate_ros2_package(
        workspace_dir=Path(args.workspace_dir),
        package_name=args.package,
        run_launch_check=not args.no_launch,
        clean_build=args.clean,
    )

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()