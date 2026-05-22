"""
Small OMNI helper for writing morphology artifacts into a mission output folder.

This is optional, but useful for wiring the morphology compiler into
fusion360_script_generator.py or export_manager.py without duplicating JSON logic.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

try:
    from .cad_morphology_planner import infer_morphology_spec
    from .morphology_quality_gate import validate_morphology_spec
except ImportError:
    from cad_morphology_planner import infer_morphology_spec  # type: ignore
    from morphology_quality_gate import validate_morphology_spec  # type: ignore


def build_morphology_artifacts(mission_text: str) -> Dict[str, Any]:
    spec = infer_morphology_spec(mission_text)
    gate = validate_morphology_spec(spec, mission_text)
    return {
        "morphology_spec": spec.to_dict(),
        "morphology_quality_gate": gate.to_dict(),
    }


def write_morphology_artifacts(mission_text: str, output_dir: str | Path) -> Dict[str, Path]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    artifacts = build_morphology_artifacts(mission_text)
    spec_path = output_path / "morphology_spec.json"
    gate_path = output_path / "morphology_quality_gate.json"

    spec_path.write_text(json.dumps(artifacts["morphology_spec"], indent=2), encoding="utf-8")
    gate_path.write_text(json.dumps(artifacts["morphology_quality_gate"], indent=2), encoding="utf-8")

    return {
        "morphology_spec": spec_path,
        "morphology_quality_gate": gate_path,
    }
