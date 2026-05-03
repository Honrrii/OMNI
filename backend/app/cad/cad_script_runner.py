import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List


ALLOWED_SCRIPT_ROOT = Path("outputs/omni_forge/cad_scripts").resolve()

FORBIDDEN_SNIPPETS = [
    "import os",
    "from os",
    "subprocess",
    "socket",
    "requests",
    "urllib",
    "shutil",
    "eval(",
    "exec(",
    "__import__",
    "pickle",
    "Path('/",
    'Path("/',
]


def execute_generated_cad_script(
    script_path: str,
    timeout_seconds: int = 60,
) -> Dict[str, Any]:
    """
    Execute a generated OMNI Forge CAD script.

    Safety boundaries:
    - Only runs scripts inside outputs/omni_forge/cad_scripts
    - Only runs .py files
    - Performs a lightweight static scan for risky code patterns
    - Uses a subprocess timeout
    - Does not control printers or physical devices
    """

    try:
        resolved_script_path = _resolve_allowed_script_path(script_path)
        script_text = resolved_script_path.read_text(encoding="utf-8")

        safety_report = _scan_script_for_risky_patterns(script_text)

        if safety_report["status"] != "pass":
            return {
                "status": "blocked",
                "message": "CAD script execution blocked by safety scan.",
                "script_path": str(resolved_script_path),
                "safety_report": safety_report,
                "execution": None,
                "exported_files": [],
            }

        start_time = time.time()

        completed = subprocess.run(
            [sys.executable, str(resolved_script_path)],
            cwd=str(resolved_script_path.parent),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )

        duration_seconds = round(time.time() - start_time, 3)

        exported_files = _collect_exported_files(resolved_script_path.parent)

        status = "success" if completed.returncode == 0 else "failed"

        if completed.returncode == 0 and not exported_files:
            status = "warning"

        return {
            "status": status,
            "message": _build_execution_message(status, completed.returncode, exported_files),
            "script_path": str(resolved_script_path),
            "safety_report": safety_report,
            "execution": {
                "return_code": completed.returncode,
                "duration_seconds": duration_seconds,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "timeout_seconds": timeout_seconds,
            },
            "exported_files": exported_files,
            "human_review_required_before_fabrication": True,
            "physical_execution_performed": False,
        }

    except subprocess.TimeoutExpired as error:
        return {
            "status": "failed",
            "message": f"CAD script execution timed out after {timeout_seconds} seconds.",
            "script_path": script_path,
            "safety_report": None,
            "execution": {
                "return_code": None,
                "duration_seconds": timeout_seconds,
                "stdout": error.stdout,
                "stderr": error.stderr,
                "timeout_seconds": timeout_seconds,
            },
            "exported_files": [],
            "human_review_required_before_fabrication": True,
            "physical_execution_performed": False,
        }

    except Exception as error:
        return {
            "status": "failed",
            "message": f"CAD script execution failed: {str(error)}",
            "script_path": script_path,
            "safety_report": None,
            "execution": None,
            "exported_files": [],
            "human_review_required_before_fabrication": True,
            "physical_execution_performed": False,
        }


def _resolve_allowed_script_path(script_path: str) -> Path:
    candidate = Path(script_path).expanduser().resolve()

    if candidate.suffix != ".py":
        raise ValueError("Only Python .py CAD scripts can be executed.")

    if not candidate.exists():
        raise FileNotFoundError(f"CAD script not found: {candidate}")

    if ALLOWED_SCRIPT_ROOT not in candidate.parents:
        raise ValueError(
            "Refusing to execute script outside outputs/omni_forge/cad_scripts."
        )

    return candidate


def _scan_script_for_risky_patterns(script_text: str) -> Dict[str, Any]:
    matches: List[str] = []

    for snippet in FORBIDDEN_SNIPPETS:
        if snippet in script_text:
            matches.append(snippet)

    if matches:
        return {
            "status": "blocked",
            "blocked_patterns": matches,
            "message": "Potentially risky code patterns were found.",
        }

    return {
        "status": "pass",
        "blocked_patterns": [],
        "message": "No forbidden code patterns detected.",
    }


def _collect_exported_files(script_dir: Path) -> List[Dict[str, Any]]:
    exports_dir = script_dir / "exports"

    if not exports_dir.exists():
        return []

    exported_files = []

    for path in sorted(exports_dir.iterdir()):
        if path.suffix.lower() in [".step", ".stp", ".stl", ".3mf"]:
            exported_files.append(
                {
                    "filename": path.name,
                    "path": str(path),
                    "suffix": path.suffix.lower(),
                    "size_bytes": path.stat().st_size,
                }
            )

    return exported_files


def _build_execution_message(status: str, return_code: int, exported_files: List[Dict[str, Any]]) -> str:
    if status == "success":
        return f"CAD script executed successfully and exported {len(exported_files)} file(s)."

    if status == "warning":
        return "CAD script executed, but no exported STEP/STL files were found."

    return f"CAD script failed with return code {return_code}."