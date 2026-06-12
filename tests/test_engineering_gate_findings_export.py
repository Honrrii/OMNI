"""Phase 10 Stage 3F — additive findings_projection in engineering gate reports.

The export adds a normalized, read-only findings_projection envelope to the
KiCad and morphology gate report dicts (and their on-disk JSON). It must be
purely additive: all legacy report fields stay intact, no top-level "findings"
field is introduced, and the live validators themselves still emit no
findings_projection.

No LLM calls. No network. Export is driven via export_mission_files with
OUTPUT_ROOT redirected to tmp_path.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import backend.app.export.export_manager as em

# Mission text with a strong electronics signal so the KiCad starter package
# (and therefore its knowledge gate report) is generated on the normal path.
_KICAD_MISSION = (
    "Design a wheeled rover with a custom PCB electronics board: a "
    "microcontroller, voltage regulator, battery input, IMU sensor, and "
    "motor driver connectors."
)


def _export(mission_text: str, tmp_path: Path) -> dict:
    mission_result = {
        "mission": mission_text,
        "result_id": "phase10-3f",
        "final_report": "",
        "final_decision": "",
        "agents": {},
        "artifacts": {},
        "validation": {},
        "critique": {},
        "revision": {},
        "status": "complete",
    }
    mp = pytest.MonkeyPatch()
    mp.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")
    try:
        return em.export_mission_files(mission_result, validate_ros2=False)
    finally:
        mp.undo()


def _assert_envelope(fp: dict, *, schema: str, source: str) -> None:
    assert set(fp) == {"schema", "source", "origin_fields", "count", "items"}
    assert fp["schema"] == schema
    assert fp["source"] == source
    assert fp["origin_fields"] == ["issues"]
    assert isinstance(fp["items"], list)
    assert fp["count"] == len(fp["items"])


# ---------------------------------------------------------------------------
# Morphology gate report (always written)
# ---------------------------------------------------------------------------

def test_morphology_report_file_has_findings_projection(tmp_path):
    result = _export(_KICAD_MISSION, tmp_path)
    export_dir = Path(result["export_dir"])
    report = json.loads(
        (export_dir / "artifacts" / "morphology_gate_report.json").read_text()
    )

    assert "findings_projection" in report
    assert "findings" not in report
    _assert_envelope(
        report["findings_projection"],
        schema="omni.engineering.morphology_gate.findings_projection.v1",
        source="morphology_gate_report",
    )
    assert report["findings_projection"]["count"] == len(report["issues"])


def test_morphology_return_projection_matches_file(tmp_path):
    result = _export(_KICAD_MISSION, tmp_path)
    export_dir = Path(result["export_dir"])
    on_disk = json.loads(
        (export_dir / "artifacts" / "morphology_gate_report.json").read_text()
    )
    assert (
        result["morphology_validation"]["findings_projection"]
        == on_disk["findings_projection"]
    )


def test_morphology_report_preserves_legacy_fields(tmp_path):
    result = _export(_KICAD_MISSION, tmp_path)
    report = result["morphology_validation"]
    for key in ("validator", "status", "summary", "issues"):
        assert key in report, f"legacy morphology field missing: {key}"
    assert "findings" not in report


# ---------------------------------------------------------------------------
# KiCad knowledge gate report (written on the normal generation path)
# ---------------------------------------------------------------------------

def test_kicad_report_file_has_findings_projection(tmp_path):
    result = _export(_KICAD_MISSION, tmp_path)
    export_dir = Path(result["export_dir"])
    report_path = export_dir / "generated_kicad" / "kicad_knowledge_gate_report.json"

    assert report_path.exists(), (
        "expected the KiCad knowledge gate report on the normal path; "
        f"kicad_generation status={result.get('kicad_generation', {}).get('status')!r}"
    )
    report = json.loads(report_path.read_text())

    assert "findings_projection" in report
    assert "findings" not in report
    _assert_envelope(
        report["findings_projection"],
        schema="omni.engineering.kicad_knowledge_gate.findings_projection.v1",
        source="kicad_knowledge_gate_report",
    )
    assert report["findings_projection"]["count"] == len(report["issues"])


def test_kicad_return_projection_matches_file(tmp_path):
    result = _export(_KICAD_MISSION, tmp_path)
    export_dir = Path(result["export_dir"])
    report_path = export_dir / "generated_kicad" / "kicad_knowledge_gate_report.json"
    assert report_path.exists()
    on_disk = json.loads(report_path.read_text())

    assert (
        result["kicad_validation"]["findings_projection"]
        == on_disk["findings_projection"]
    )


def test_kicad_generation_knowledge_gate_projection_matches_validation(tmp_path):
    result = _export(_KICAD_MISSION, tmp_path)
    kicad_generation = result["kicad_generation"]
    assert isinstance(kicad_generation, dict)
    assert kicad_generation.get("status") == "generated"

    kg = kicad_generation["knowledge_gate"]
    assert "findings_projection" in kg
    assert (
        kg["findings_projection"]
        == result["kicad_validation"]["findings_projection"]
    )


def test_kicad_report_preserves_legacy_fields(tmp_path):
    result = _export(_KICAD_MISSION, tmp_path)
    report = result["kicad_validation"]
    for key in ("validator", "status", "summary", "issues"):
        assert key in report, f"legacy kicad field missing: {key}"
    assert "findings" not in report


# ---------------------------------------------------------------------------
# Raw validators still emit no findings_projection (regression guard)
# ---------------------------------------------------------------------------

def test_raw_validators_emit_no_findings_projection(tmp_path):
    from backend.app.engineering.kicad_knowledge_gate_validator import (
        validate_kicad_package,
    )
    from backend.app.engineering.morphology_gate_validator import (
        validate_morphology_export,
    )

    kreport = validate_kicad_package(tmp_path / "nope_kicad")
    mreport = validate_morphology_export(tmp_path / "nope_export")
    assert "findings_projection" not in kreport
    assert "findings_projection" not in mreport
