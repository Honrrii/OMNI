#!/usr/bin/env python3
"""
OMNI Harness — CLI mission runner.

Runs the OMNI multi-agent engineering pipeline and writes a timestamped,
immutable output folder under outputs/omni_missions/.

Usage:
    python omni_harness.py "Design a palm-sized rover with ROS2"
    python omni_harness.py "Design a drone" --dry-run
    python omni_harness.py --help

Output folder format:
    outputs/omni_missions/2026-05-22_1430_design_a_palm_sized_rover/

Files written (when available):
    mission_result.json      — full supervisor result dict
    mission_report.md        — final_report text
    validation_report.json   — validation payload
    provenance_record.json   — per-agent provenance from mission_state
    next_artifacts.json      — next_artifacts collected from agent outputs
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OUTPUT_ROOT = Path("outputs") / "omni_missions"
SLUG_MAX_LEN = 55


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _slugify(text: str, max_len: int = SLUG_MAX_LEN) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = text.strip("_")
    return text[:max_len] or "omni_mission"


def _make_folder_name(mission: str) -> str:
    ts = datetime.now().strftime("%Y-%m-%d_%H%M")
    slug = _slugify(mission)
    return f"{ts}_{slug}"


def _create_output_folder(output_root: Path, mission: str) -> Path:
    """
    Create a new timestamped folder. Never overwrites a previous run.

    If a folder with the same minute-timestamp already exists (unlikely but
    possible when running back-to-back tests), a numeric suffix is appended.
    """
    output_root.mkdir(parents=True, exist_ok=True)
    base_name = _make_folder_name(mission)
    candidate = output_root / base_name

    if not candidate.exists():
        candidate.mkdir(parents=True, exist_ok=False)
        return candidate

    for i in range(2, 1000):
        candidate = output_root / f"{base_name}_{i}"
        if not candidate.exists():
            candidate.mkdir(parents=True, exist_ok=False)
            return candidate

    raise RuntimeError(
        f"Could not create a unique output folder after 999 attempts: {base_name}"
    )


# ---------------------------------------------------------------------------
# File writers
# ---------------------------------------------------------------------------

def _write_json(path: Path, data: Any) -> None:
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )


def _write_text(path: Path, content: str) -> None:
    path.write_text(str(content or ""), encoding="utf-8")


# ---------------------------------------------------------------------------
# Artifact extraction helpers
# ---------------------------------------------------------------------------

def _extract_next_artifacts(result: Dict[str, Any]) -> List[str]:
    """
    Collect next_artifacts strings from agent structured outputs and
    the top-level artifacts dict. Returns deduplicated list.
    """
    seen: set = set()
    collected: List[str] = []

    def _add(item: Any) -> None:
        s = str(item).strip()
        if s and s not in seen:
            seen.add(s)
            collected.append(s)

    # Per-agent handoff blocks (sky, oli, korva carry next_artifacts)
    structured = result.get("structured_agent_outputs", {})
    if isinstance(structured, dict):
        for agent_id in ("sky", "oli", "korva"):
            agent_out = structured.get(agent_id, {})
            if not isinstance(agent_out, dict):
                continue
            handoff = agent_out.get("handoff_to_artifact_synthesis", {})
            if not isinstance(handoff, dict):
                continue
            for item in handoff.get("next_artifacts", []):
                _add(item)

    # Top-level artifacts.next_artifacts
    top_artifacts = result.get("artifacts", {})
    if isinstance(top_artifacts, dict):
        for item in top_artifacts.get("next_artifacts", []):
            _add(item)

    return collected


def _build_provenance_record(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a provenance record directly from the serialized mission_state dict
    returned in the supervisor result.

    Does NOT reconstruct MissionState dataclasses. Reads agent_records as plain
    dicts to avoid fragile reconstruction. Defaults gracefully when data is absent.
    """
    mission_state = result.get("mission_state", {})

    if not isinstance(mission_state, dict):
        return {
            "system": "OMNI Harness",
            "agents": [],
            "note": "mission_state was not present or not a dict in the result.",
        }

    agent_records_raw = mission_state.get("agent_records", {})

    if not isinstance(agent_records_raw, dict):
        return {
            "system": "OMNI Harness",
            "mission_id": mission_state.get("mission_id"),
            "agents": [],
            "note": "agent_records was not present or not a dict in mission_state.",
        }

    agents = []
    for agent_id, record in agent_records_raw.items():
        if not isinstance(record, dict):
            continue
        agents.append(
            {
                "agent_id": agent_id,
                "agent_name": record.get("agent_name", agent_id),
                "status": record.get("status", "unknown"),
                "started_at": record.get("started_at"),
                "finished_at": record.get("finished_at"),
                "errors": record.get("errors", []),
                "evidence_type": "llm_generated",
                "human_review_required": True,
            }
        )

    return {
        "system": "OMNI Harness",
        "mission_id": mission_state.get("mission_id"),
        "created_at": mission_state.get("created_at"),
        "agent_count": len(agents),
        "agents": agents,
        "note": (
            "Provenance derived from serialized mission_state.agent_records. "
            "All LLM-generated outputs are provisional and require human review "
            "before any hardware use."
        ),
    }


# ---------------------------------------------------------------------------
# Dry-run path
# ---------------------------------------------------------------------------

def _run_dry_run(output_root: Path, mission: str) -> None:
    """
    Create the output folder and write placeholder files without any LLM calls.
    Used to verify folder creation, naming, and file-writing logic.
    """
    print()
    print("[OMNI Harness] DRY RUN — no LLM calls will be made.")
    print(f"[OMNI Harness] Mission: {mission[:120]}")

    folder = _create_output_folder(output_root, mission)
    print(f"[OMNI Harness] Output folder: {folder}")

    _write_json(
        folder / "mission_result.json",
        {
            "dry_run": True,
            "mission": mission,
            "status": "dry_run",
            "note": "Placeholder — no mission was executed.",
        },
    )
    _write_text(
        folder / "mission_report.md",
        f"# OMNI Dry Run\n\nMission: {mission}\n\nNo execution performed.\n",
    )
    _write_json(
        folder / "validation_report.json",
        {"status": "dry_run", "note": "No validation performed."},
    )
    _write_json(
        folder / "provenance_record.json",
        {
            "system": "OMNI Harness",
            "agents": [],
            "note": "Dry run — no agents ran.",
        },
    )
    _write_json(folder / "next_artifacts.json", [])

    written = sorted(f.name for f in folder.iterdir())
    print("[OMNI Harness] Files written:")
    for name in written:
        print(f"  {name}")
    print(f"\n[OMNI Harness] Dry run complete. Folder: {folder}")
    print()


# ---------------------------------------------------------------------------
# Live mission run path
# ---------------------------------------------------------------------------

def _run_mission(output_root: Path, mission: str) -> None:
    """
    Full mission run: execute the supervisor pipeline and write outputs.
    Creates the output folder before running so partial results are preserved
    even if the mission fails mid-way.
    """
    print()
    print("[OMNI Harness] Mission received.")
    print(f"[OMNI Harness] {mission[:120]}")

    folder = _create_output_folder(output_root, mission)
    print(f"[OMNI Harness] Output folder: {folder}")

    # Run the mission ---------------------------------------------------
    result: Dict[str, Any]
    try:
        from agents.supervisor import SupervisorAgent

        supervisor = SupervisorAgent()
        print("[OMNI Harness] Running OMNI council...")
        raw = supervisor.run_mission_structured(mission)

        if isinstance(raw, dict):
            result = raw
        else:
            result = {
                "mission": mission,
                "status": "complete",
                "final_report": str(raw),
                "note": "Supervisor returned a non-dict; stored as final_report.",
            }

    except Exception as exc:
        print(f"[OMNI Harness] Mission execution failed: {exc}", file=sys.stderr)
        result = {
            "mission": mission,
            "status": "failed",
            "error": f"{type(exc).__name__}: {exc}",
        }

    # Write files -------------------------------------------------------
    errors: List[str] = []

    # 1. mission_result.json — always written
    try:
        _write_json(folder / "mission_result.json", result)
        print("  [ok] mission_result.json")
    except Exception as exc:
        errors.append(f"mission_result.json: {exc}")
        print(f"  [fail] mission_result.json — {exc}", file=sys.stderr)

    # 2. mission_report.md
    try:
        report_text = (
            result.get("final_report")
            or result.get("final_synthesis")
            or result.get("final_decision")
            or ""
        )
        _write_text(folder / "mission_report.md", report_text)
        print("  [ok] mission_report.md")
    except Exception as exc:
        errors.append(f"mission_report.md: {exc}")
        print(f"  [fail] mission_report.md — {exc}", file=sys.stderr)

    # 3. validation_report.json
    try:
        validation = result.get("validation")
        _write_json(
            folder / "validation_report.json",
            validation if validation is not None else {"status": "not_available"},
        )
        status_note = "ok" if validation is not None else "not available"
        print(f"  [ok] validation_report.json ({status_note})")
    except Exception as exc:
        errors.append(f"validation_report.json: {exc}")
        print(f"  [fail] validation_report.json — {exc}", file=sys.stderr)

    # 4. provenance_record.json
    try:
        provenance = _build_provenance_record(result)
        _write_json(folder / "provenance_record.json", provenance)
        agent_count = len(provenance.get("agents", []))
        print(f"  [ok] provenance_record.json ({agent_count} agent records)")
    except Exception as exc:
        errors.append(f"provenance_record.json: {exc}")
        _write_json(
            folder / "provenance_record.json",
            {"agents": [], "error": f"{type(exc).__name__}: {exc}"},
        )
        print(f"  [warn] provenance_record.json — defaulted to empty: {exc}", file=sys.stderr)

    # 5. next_artifacts.json
    try:
        next_artifacts = _extract_next_artifacts(result)
        _write_json(folder / "next_artifacts.json", next_artifacts)
        print(f"  [ok] next_artifacts.json ({len(next_artifacts)} items)")
    except Exception as exc:
        errors.append(f"next_artifacts.json: {exc}")
        _write_json(folder / "next_artifacts.json", [])
        print(f"  [warn] next_artifacts.json — defaulted to empty: {exc}", file=sys.stderr)

    if errors:
        print(f"\n[OMNI Harness] Completed with {len(errors)} write error(s).")
    else:
        print(f"\n[OMNI Harness] Mission complete.")

    print(f"[OMNI Harness] Output: {folder}")
    print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="omni_harness",
        description=(
            "OMNI Harness — CLI mission runner.\n\n"
            "Runs the OMNI multi-agent engineering pipeline and writes a\n"
            "timestamped immutable output folder under outputs/omni_missions/.\n\n"
            "Examples:\n"
            "  python omni_harness.py \"Design a palm-sized rover with ROS2\"\n"
            "  python omni_harness.py \"Design an insect robot\" --dry-run\n"
            "  python omni_harness.py --help\n\n"
            "Output folder format:\n"
            "  outputs/omni_missions/2026-05-22_1430_design_a_palm_sized_rover/\n\n"
            "Files written:\n"
            "  mission_result.json      full supervisor result\n"
            "  mission_report.md        final_report text\n"
            "  validation_report.json   validation payload\n"
            "  provenance_record.json   per-agent provenance\n"
            "  next_artifacts.json      next_artifacts from agent outputs\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "mission",
        nargs="?",
        metavar="MISSION",
        help="Engineering mission string to run through the OMNI council.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Write placeholder files without making LLM calls. "
            "Tests folder creation and file-writing logic."
        ),
    )
    parser.add_argument(
        "--output-root",
        default="outputs/omni_missions",
        metavar="PATH",
        help="Root directory for mission output folders. Default: outputs/omni_missions",
    )

    args = parser.parse_args()

    if args.mission is None:
        parser.print_help()
        sys.exit(0)

    mission = args.mission.strip()
    if not mission:
        print("Error: mission string cannot be empty.", file=sys.stderr)
        sys.exit(1)

    output_root = Path(args.output_root)

    if args.dry_run:
        _run_dry_run(output_root, mission)
    else:
        _run_mission(output_root, mission)


if __name__ == "__main__":
    main()
