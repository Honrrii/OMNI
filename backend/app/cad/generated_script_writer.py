import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


def write_generated_cad_script(
    script_text: str,
    mission_text: str,
    cad_plan: Dict[str, Any],
    output_root: str = "outputs/omni_forge/cad_scripts",
) -> Dict[str, Any]:
    """
    Write a generated CAD script and metadata file to disk.

    This does not run the script.
    It only saves the generated script so the user can review it first.
    """

    output_dir = Path(output_root)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    part_type = cad_plan.get("part_type", "workshop_part")
    mission_slug = _slugify(mission_text)[:60]

    script_filename = f"{timestamp}_{part_type}_{mission_slug}.py"
    metadata_filename = f"{timestamp}_{part_type}_{mission_slug}.json"

    script_path = output_dir / script_filename
    metadata_path = output_dir / metadata_filename

    script_path.write_text(script_text, encoding="utf-8")

    metadata = {
        "created_at": datetime.now().isoformat(),
        "mission_text": mission_text,
        "part_type": part_type,
        "cad_plan": cad_plan,
        "script_path": str(script_path),
        "metadata_path": str(metadata_path),
        "execution_status": "not_executed",
        "human_review_required": True,
        "safety_note": "Generated CAD scripts must be reviewed before fabrication.",
    }

    metadata_path.write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )

    return {
        "status": "success",
        "script_path": str(script_path),
        "metadata_path": str(metadata_path),
        "script_filename": script_filename,
        "metadata_filename": metadata_filename,
        "human_review_required": True,
    }


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text)
    return text.strip("_") or "omni_forge_script"