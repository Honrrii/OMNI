#!/usr/bin/env python3
"""
OMNI Phase 10 — Stage 0 baseline capture.

Captures current-state numbers for the Phase 10 metrics plan by reading
artifacts that already exist:

  - logs/telemetry/mission_runs.jsonl   (per-mission / per-agent events)
  - outputs/omni_missions/<id>/         (real exported mission folders)
  - one timed run of the existing pytest suite (unless --skip-pytest)

Hard guarantees:
  - Read-only against every repo artifact except its own output file.
  - Never runs a mission. Never calls a model. Never imports hosted SDKs
    or OMNI runtime LLM clients (see HOSTED_SDK_DENYLIST below).
  - Re-runnable: each run appends a dated history entry to the output
    JSON and never overwrites previous entries.

Usage:
    python scripts/omni_metrics_baseline.py --pretty
    python scripts/omni_metrics_baseline.py --skip-pytest --max-missions 5
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

SCHEMA_VERSION = "0.1"

DEFAULT_OUTPUT_RELPATH = Path("docs") / "metrics" / "baseline.json"
MISSIONS_RELPATH = Path("outputs") / "omni_missions"
TELEMETRY_RELPATH = Path("logs") / "telemetry" / "mission_runs.jsonl"

# Hard ceiling so a hung suite cannot wedge baseline capture.
PYTEST_TIMEOUT_SECONDS = 3600

# Modules this script must never import (asserted by tests/test_metrics_baseline.py).
HOSTED_SDK_DENYLIST = (
    "openai",
    "anthropic",
    "google.generativeai",
    "google.genai",
    "google.api_core",
    "boto3",
    "azure.ai",
    "cohere",
    "mistralai",
)
RUNTIME_LLM_MODULE_DENYLIST = (
    "agents.llm_clients",
    "agents.supervisor",
    "backend.app.omni_core.llm_router",
    "backend.app.nvidia_client",
)

# Mission lifecycle steps backed by an LLM call, as recorded in
# mission_state.agent_records (qaz is deterministic and excluded).
LLM_STEP_IDS = frozenset(
    {"omni", "vega", "sky", "isy", "oli", "korva", "pluto", "omni_revision"}
)
# The supervisor's critique-structuring step (build_structured_critique) makes
# one additional LLM call that is not instrumented as an agent record.
UNINSTRUMENTED_LLM_CALLS = 1

SPECIALIST_IDS = frozenset({"vega", "sky", "isy", "oli", "korva", "pluto"})

# Ordered, deterministic mission-type keyword rules. First pass collects all
# matching types; >1 distinct match -> "mixed", 0 -> "other".
MISSION_TYPE_RULES = (
    ("drone", ("drone", "uav", "quadcopter", "ducted fan", "aerial", "aircraft", "fixed-wing", "fixed_wing")),
    ("rover", ("rover",)),
    ("robot_arm", ("robot arm", "robotic arm", "manipulator", "gripper", "robot_arm")),
    ("pcb", ("pcb", "circuit board", "kicad")),
    ("electronics", ("electronics", "embedded", "wiring", "microcontroller")),
    ("cad", ("cad", "enclosure", "bracket", "fusion 360", "fusion360", "3d print", "3d-print")),
)

AUDIT_CLAIM_PAYLOAD_BYTES = 497157
AUDIT_CLAIM_EXPORT_FILES = 189
AUDIT_CLAIM_LLM_CALLS = 9


def utc_now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def infer_repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def get_git_commit(repo_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        commit = result.stdout.strip()
        if result.returncode == 0 and re.fullmatch(r"[0-9a-f]{7,40}", commit):
            return commit
    except Exception:
        pass
    return "UNKNOWN"


def parse_iso(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def summarize_distribution(values: List[float]) -> Dict[str, Any]:
    """min/median/max/n_samples summary; nulls when no samples exist."""
    clean = [v for v in values if isinstance(v, (int, float))]
    if not clean:
        return {"min": None, "median": None, "max": None, "n_samples": 0}
    return {
        "min": min(clean),
        "median": statistics.median(clean),
        "max": max(clean),
        "n_samples": len(clean),
    }


def infer_mission_type(folder_name: str, mission_text: str) -> str:
    haystack = f"{folder_name} {mission_text}".lower().replace("_", " ")
    matched = [mtype for mtype, terms in MISSION_TYPE_RULES
               if any(term in haystack for term in terms)]
    if not matched:
        return "other"
    if len(set(matched)) > 1:
        return "mixed"
    return matched[0]


def _safe_load_json(path: Path) -> Optional[Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _count_warnings_and_findings(payload: Dict[str, Any], mission_dir: Path) -> int:
    """
    Count warning/finding items across the divergent shapes that exist today.

    Counted (exact paths, see P10-VAL-001):
      - mission_state.warnings (list[str])
      - mission_state.agent_records[*].parsed_output.warnings (list[str])
      - critique.issues_found (payload key, falling back to critique.json)
      - validation.missing_evidence + validation.required_next_tests
      - mission_graph_review.json: issues + consistency_warnings
        (graph 'warnings' list is excluded: documented duplicate of issues)
    Shapes may overlap semantically; this is a raw pre-unification count.
    """
    total = 0

    state = payload.get("mission_state") or {}
    if isinstance(state, dict):
        warnings = state.get("warnings")
        if isinstance(warnings, list):
            total += len(warnings)
        records = state.get("agent_records")
        if isinstance(records, dict):
            for record in records.values():
                if not isinstance(record, dict):
                    continue
                parsed = record.get("parsed_output")
                if isinstance(parsed, dict) and isinstance(parsed.get("warnings"), list):
                    total += len(parsed["warnings"])

    critique = payload.get("critique")
    if not isinstance(critique, dict):
        critique = _safe_load_json(mission_dir / "critique.json")
    if isinstance(critique, dict) and isinstance(critique.get("issues_found"), list):
        total += len(critique["issues_found"])

    validation = payload.get("validation")
    if not isinstance(validation, dict):
        validation = _safe_load_json(mission_dir / "validation.json") or _safe_load_json(
            mission_dir / "validation_report.json"
        )
    if isinstance(validation, dict):
        for key in ("missing_evidence", "required_next_tests"):
            if isinstance(validation.get(key), list):
                total += len(validation[key])

    graph_review = _safe_load_json(mission_dir / "mission_graph_review.json")
    if isinstance(graph_review, dict):
        for key in ("issues", "consistency_warnings"):
            if isinstance(graph_review.get(key), list):
                total += len(graph_review[key])

    return total


def scan_mission_dir(mission_dir: Path) -> Dict[str, Any]:
    """
    Build one per-mission sample from an outputs/omni_missions/<id>/ folder.

    Handles both folder flavors:
      - export-manager folders (mission.json)
      - harness folders (mission_result.json)
    Dry-run / unparsable payloads keep file/byte stats but contribute no
    payload-derived samples.
    """
    files = [p for p in mission_dir.rglob("*") if p.is_file()]
    sample: Dict[str, Any] = {
        "name": mission_dir.name,
        "file_count": len(files),
        "total_bytes": sum(p.stat().st_size for p in files),
        "payload_serialized_bytes": None,
        "payload_file_bytes": None,
        "artifact_count": None,
        "provenance_bytes": None,
        "warning_finding_count": None,
        "runtime_seconds": None,
        "llm_call_estimate": None,
        "specialist_activations": None,
        "mission_type": infer_mission_type(mission_dir.name, ""),
        "dry_run": False,
    }

    payload_path = None
    for candidate in ("mission.json", "mission_result.json"):
        if (mission_dir / candidate).is_file():
            payload_path = mission_dir / candidate
            break

    provenance_path = mission_dir / "provenance_record.json"
    if provenance_path.is_file():
        sample["provenance_bytes"] = provenance_path.stat().st_size

    if payload_path is None:
        return sample

    sample["payload_file_bytes"] = payload_path.stat().st_size
    payload = _safe_load_json(payload_path)
    if not isinstance(payload, dict):
        return sample
    if payload.get("dry_run") is True:
        sample["dry_run"] = True
        return sample

    # Serialized payload bytes: same method as the Phase 10 audit measurement
    # (json.dumps with default separators over the parsed payload).
    sample["payload_serialized_bytes"] = len(json.dumps(payload, default=str))

    artifacts = payload.get("artifacts")
    if isinstance(artifacts, (dict, list)):
        sample["artifact_count"] = len(artifacts)

    sample["mission_type"] = infer_mission_type(
        mission_dir.name, str(payload.get("mission", ""))[:2000]
    )
    sample["warning_finding_count"] = _count_warnings_and_findings(payload, mission_dir)

    state = payload.get("mission_state")
    if isinstance(state, dict):
        created = parse_iso(state.get("created_at"))
        updated = parse_iso(state.get("updated_at"))
        if created and updated and updated >= created:
            sample["runtime_seconds"] = round((updated - created).total_seconds(), 3)

        records = state.get("agent_records")
        if isinstance(records, dict):
            llm_steps = sum(1 for agent_id in records if agent_id in LLM_STEP_IDS)
            sample["llm_call_estimate"] = llm_steps + UNINSTRUMENTED_LLM_CALLS
            sample["specialist_activations"] = sum(
                1 for agent_id in records if agent_id in SPECIALIST_IDS
            )

    return sample


def scan_missions(missions_root: Path, max_missions: Optional[int]) -> List[Dict[str, Any]]:
    if not missions_root.is_dir():
        return []
    dirs = sorted(p for p in missions_root.iterdir() if p.is_dir())
    if max_missions is not None:
        dirs = dirs[:max_missions]
    return [scan_mission_dir(d) for d in dirs]


def parse_telemetry(telemetry_path: Path) -> Dict[str, Any]:
    """
    Parse mission_runs.jsonl into per-mission runtimes and agent-start counts.

    Returns {"available": bool, "runtimes": [...], "agent_started_counts": [...],
             "llm_step_counts": [...], "mission_count": int, "parse_errors": int}
    """
    result: Dict[str, Any] = {
        "available": telemetry_path.is_file(),
        "runtimes": [],
        "agent_started_counts": [],
        "llm_step_counts": [],
        "mission_count": 0,
        "parse_errors": 0,
    }
    if not result["available"]:
        return result

    missions: Dict[str, Dict[str, Any]] = {}
    with telemetry_path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                result["parse_errors"] += 1
                continue
            mission_id = event.get("mission_id")
            if not mission_id:
                continue
            record = missions.setdefault(
                mission_id, {"started": None, "finished": None, "agents_started": []}
            )
            event_type = event.get("event_type")
            timestamp = parse_iso(event.get("timestamp"))
            if event_type == "mission_started":
                record["started"] = timestamp
            elif event_type == "mission_finished":
                record["finished"] = timestamp
            elif event_type == "agent_started":
                record["agents_started"].append(event.get("agent_id"))

    for record in missions.values():
        started, finished = record["started"], record["finished"]
        agents = record["agents_started"]
        if started is None and finished is None and not agents:
            continue
        result["mission_count"] += 1
        if started and finished and finished >= started:
            result["runtimes"].append(round((finished - started).total_seconds(), 3))
        if agents:
            result["agent_started_counts"].append(len(agents))
            llm_steps = sum(1 for a in agents if a in LLM_STEP_IDS)
            result["llm_step_counts"].append(llm_steps + UNINSTRUMENTED_LLM_CALLS)

    return result


def run_pytest_metrics(repo_root: Path) -> Dict[str, Any]:
    """
    One collect-only pass (test count) and one timed quiet run (wall seconds).
    Matches scripts/omni_smoke.sh: PYTEST_DISABLE_PLUGIN_AUTOLOAD=1.
    """
    import os

    env = dict(os.environ)
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    outcome: Dict[str, Any] = {
        "collected": None,
        "wall_seconds": None,
        "summary": "",
        "error": None,
    }

    try:
        collect = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q"],
            cwd=str(repo_root),
            env=env,
            capture_output=True,
            text=True,
            timeout=600,
        )
        match = re.search(r"(\d+)\s+tests?\s+collected", collect.stdout)
        if match is None:
            match = re.search(r"collected\s+(\d+)\s+items?", collect.stdout)
        if match:
            outcome["collected"] = int(match.group(1))
    except Exception as exc:  # noqa: BLE001 - recorded, never raised
        outcome["error"] = f"collect: {type(exc).__name__}: {exc}"
        return outcome

    try:
        start = time.monotonic()
        run = subprocess.run(
            [sys.executable, "-m", "pytest", "-q"],
            cwd=str(repo_root),
            env=env,
            capture_output=True,
            text=True,
            timeout=PYTEST_TIMEOUT_SECONDS,
        )
        outcome["wall_seconds"] = round(time.monotonic() - start, 2)
        tail = [l for l in run.stdout.strip().splitlines() if l.strip()]
        outcome["summary"] = tail[-1] if tail else ""
        if run.returncode != 0:
            outcome["error"] = f"pytest exited {run.returncode}"
    except subprocess.TimeoutExpired:
        outcome["error"] = f"pytest run exceeded {PYTEST_TIMEOUT_SECONDS}s timeout"
    except Exception as exc:  # noqa: BLE001
        outcome["error"] = f"run: {type(exc).__name__}: {exc}"

    return outcome


# ---------------------------------------------------------------------------
# Metric assembly
# ---------------------------------------------------------------------------

def _metric(
    metric: str,
    unit: str,
    status: str,
    value: Any,
    source: str,
    method: str,
    notes: str,
) -> Dict[str, Any]:
    return {
        "metric": metric,
        "unit": unit,
        "status": status,
        "value": value,
        "source": source,
        "method": method,
        "captured_at": utc_now_iso(),
        "notes": notes,
    }


def _deferred_entry(
    metric: str,
    reason: str,
    required_mechanism: str,
    paid_calls: bool,
    suite_minutes: Optional[float],
    requires_runtime_instrumentation: bool,
) -> Dict[str, Any]:
    return {
        "metric": metric,
        "reason": reason,
        "required_mechanism": required_mechanism,
        "estimated_cost": {
            "paid_calls": paid_calls,
            "suite_minutes": suite_minutes,
            "requires_runtime_instrumentation": requires_runtime_instrumentation,
        },
    }


def _samples(missions: List[Dict[str, Any]], key: str) -> List[float]:
    return [m[key] for m in missions if isinstance(m.get(key), (int, float))]


def build_audit_reproduction(
    missions: List[Dict[str, Any]], telemetry: Dict[str, Any]
) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []

    def nearest(values: List[float], expected: int):
        return min(values, key=lambda v: abs(v - expected)) if values else None

    payload_sizes = _samples(missions, "payload_serialized_bytes")
    observed = nearest(payload_sizes, AUDIT_CLAIM_PAYLOAD_BYTES)
    if observed is None:
        status, notes = "NOT_FOUND", "No parsable mission payloads found."
    elif observed == AUDIT_CLAIM_PAYLOAD_BYTES:
        status, notes = "REPRODUCED", "Exact match found in a sampled mission payload."
    else:
        status = "DID_NOT_REPRODUCE"
        notes = (
            f"Closest sampled payload was {observed} B across {len(payload_sizes)} "
            "missions. Method: len(json.dumps(parsed payload)) with default separators."
        )
    entries.append({
        "claim": "497157_payload_bytes",
        "expected": AUDIT_CLAIM_PAYLOAD_BYTES,
        "status": status,
        "observed": observed,
        "source": str(MISSIONS_RELPATH),
        "notes": notes,
    })

    file_counts = _samples(missions, "file_count")
    observed = nearest(file_counts, AUDIT_CLAIM_EXPORT_FILES)
    if observed is None:
        status, notes = "NOT_FOUND", "No mission folders found."
    elif observed == AUDIT_CLAIM_EXPORT_FILES:
        status, notes = "REPRODUCED", "A sampled mission folder contains exactly 189 files."
    else:
        status = "DID_NOT_REPRODUCE"
        notes = f"Closest sampled folder has {observed} files across {len(file_counts)} missions."
    entries.append({
        "claim": "189_export_files",
        "expected": AUDIT_CLAIM_EXPORT_FILES,
        "status": status,
        "observed": observed,
        "source": str(MISSIONS_RELPATH),
        "notes": notes,
    })

    llm_estimates = _samples(missions, "llm_call_estimate") + telemetry.get("llm_step_counts", [])
    observed = statistics.median(llm_estimates) if llm_estimates else None
    if observed is None:
        status, notes = "NOT_FOUND", "No agent records or telemetry events available."
    elif observed == AUDIT_CLAIM_LLM_CALLS:
        status = "REPRODUCED"
        notes = (
            "Median of per-mission estimates equals 9. Derivation: instrumented "
            "LLM-backed lifecycle steps (omni, vega, sky, isy, oli, korva, pluto, "
            "omni_revision) + 1 uninstrumented critique-structuring call. "
            "ESTIMATED, not direct provider metering."
        )
    else:
        status = "DID_NOT_REPRODUCE"
        notes = (
            f"Median per-mission estimate is {observed} (same derivation: "
            "instrumented LLM steps + 1 uninstrumented critique call)."
        )
    entries.append({
        "claim": "9_llm_calls",
        "expected": AUDIT_CLAIM_LLM_CALLS,
        "status": status,
        "observed": observed,
        "source": f"{MISSIONS_RELPATH} mission_state.agent_records + {TELEMETRY_RELPATH}",
        "notes": notes,
    })

    return entries


def build_history_entry(
    repo_root: Path,
    missions: List[Dict[str, Any]],
    telemetry: Dict[str, Any],
    pytest_outcome: Optional[Dict[str, Any]],
    skip_pytest: bool,
) -> Dict[str, Any]:
    missions_src = str(MISSIONS_RELPATH)
    telemetry_src = str(TELEMETRY_RELPATH)
    live = [m for m in missions if not m["dry_run"]]

    metrics: List[Dict[str, Any]] = []
    deferred: List[Dict[str, Any]] = []

    no_missions_note = "" if missions else "No mission folders found; zero samples."

    metrics.append(_metric(
        "mission_count_sampled", "missions", "MEASURED", len(missions),
        missions_src, "count of subdirectories under outputs/omni_missions",
        no_missions_note or f"{len(live)} non-dry-run missions of {len(missions)} sampled.",
    ))

    type_counts: Dict[str, int] = {}
    for m in missions:
        type_counts[m["mission_type"]] = type_counts.get(m["mission_type"], 0) + 1
    metrics.append(_metric(
        "mission_type_distribution", "missions", "MEASURED", type_counts,
        missions_src,
        "deterministic keyword rules over folder name + mission text "
        "(drone/rover/robot_arm/pcb/electronics/cad; >1 match=mixed, 0=other)",
        "Type inference is filename/content keyword based; no model calls.",
    ))

    metrics.append(_metric(
        "mission_runtime_seconds", "seconds", "MEASURED",
        summarize_distribution(_samples(live, "runtime_seconds")),
        missions_src,
        "mission_state.updated_at - mission_state.created_at per persisted payload",
        "Covers the supervisor pipeline span only; excludes knowledge-context "
        "build and export time. Fresh full-request wall clock is DEFERRED.",
    ))

    metrics.append(_metric(
        "telemetry_mission_runtime_seconds", "seconds", "MEASURED",
        summarize_distribution(telemetry.get("runtimes", [])),
        telemetry_src,
        "mission_finished.timestamp - mission_started.timestamp per mission_id",
        "" if telemetry.get("available") else "Telemetry file not found; zero samples.",
    ))

    metrics.append(_metric(
        "model_call_count_per_mission", "calls", "ESTIMATED",
        summarize_distribution(
            _samples(live, "llm_call_estimate") + telemetry.get("llm_step_counts", [])
        ),
        f"{missions_src} + {telemetry_src}",
        "count of LLM-backed lifecycle steps in agent_records/telemetry "
        "(omni, vega, sky, isy, oli, korva, pluto, omni_revision) "
        "+ 1 uninstrumented critique-structuring call",
        "ESTIMATED: derived from instrumented steps, not provider metering. "
        "True token/call accounting is DEFERRED.",
    ))

    metrics.append(_metric(
        "specialist_agent_activation_count_per_mission", "activations", "MEASURED",
        summarize_distribution(_samples(live, "specialist_activations")),
        missions_src,
        "agent_records keys intersected with {vega, sky, isy, oli, korva, pluto}",
        "QaZ excluded (deterministic validator, not an LLM specialist).",
    ))

    payload_dist = summarize_distribution(_samples(live, "payload_serialized_bytes"))
    metrics.append(_metric(
        "serialized_payload_bytes_per_mission", "bytes", "MEASURED",
        payload_dist, missions_src,
        "len(json.dumps(parsed mission payload)) with default separators, "
        "per mission.json / mission_result.json",
        "Same method as the Phase 10 audit number for comparability.",
    ))

    metrics.append(_metric(
        "mission_payload_file_bytes_on_disk", "bytes", "MEASURED",
        summarize_distribution(_samples(live, "payload_file_bytes")),
        missions_src,
        "os.stat size of mission.json / mission_result.json",
        "Larger than serialized bytes because export writes indent=2 JSON.",
    ))

    metrics.append(_metric(
        "frontend_payload_bytes_per_mission", "bytes", "ESTIMATED",
        payload_dist, missions_src,
        "proxy: serialized mission payload bytes (the object returned to and "
        "held by the frontend, and re-POSTed on export)",
        "Excludes HTTP overhead/compression. Export round trip is ~2x this "
        "value. True browser transfer measurement is DEFERRED.",
    ))

    metrics.append(_metric(
        "operator_brief_bytes", "bytes", "ESTIMATED",
        payload_dist, missions_src,
        "proxy: serialized mission payload bytes",
        "No OperatorBrief exists yet (Phase 10 Stage 4); today's operator-facing "
        "payload IS the full mission payload.",
    ))

    metrics.append(_metric(
        "artifact_count_per_mission", "artifacts", "MEASURED",
        summarize_distribution(_samples(live, "artifact_count")),
        missions_src,
        "len(payload['artifacts']) keys/items per mission payload",
        "Counts structured artifact entries, not exported files.",
    ))

    metrics.append(_metric(
        "exported_mission_file_count", "files", "MEASURED",
        summarize_distribution(_samples(missions, "file_count")),
        missions_src,
        "recursive count of regular files per mission directory",
        "Includes harness-flavor folders (5-file layout) and export-manager "
        "folders; both lifecycles are part of the current baseline.",
    ))

    metrics.append(_metric(
        "exported_mission_bytes", "bytes", "MEASURED",
        summarize_distribution(_samples(missions, "total_bytes")),
        missions_src,
        "sum of file sizes recursively per mission directory",
        "",
    ))

    metrics.append(_metric(
        "warning_finding_count_per_mission", "findings", "MEASURED",
        summarize_distribution(_samples(live, "warning_finding_count")),
        missions_src,
        "sum across divergent shapes: mission_state.warnings + per-agent "
        "parsed_output.warnings + critique.issues_found + "
        "validation.missing_evidence + validation.required_next_tests + "
        "graph review issues + consistency_warnings (graph 'warnings' list "
        "excluded as a documented duplicate of issues)",
        "Raw pre-unification count; shapes overlap semantically (P10-VAL-001).",
    ))

    metrics.append(_metric(
        "provenance_report_bytes_per_mission", "bytes", "MEASURED",
        summarize_distribution(_samples(missions, "provenance_bytes")),
        missions_src,
        "os.stat size of provenance_record.json where present",
        "n_samples reflects missions that have a provenance_record.json.",
    ))

    if missions:
        biggest_bytes = max(missions, key=lambda m: m["total_bytes"])
        biggest_files = max(missions, key=lambda m: m["file_count"])
        largest_bytes_value: Any = {
            "path": biggest_bytes["name"], "bytes": biggest_bytes["total_bytes"],
        }
        largest_files_value: Any = {
            "path": biggest_files["name"], "files": biggest_files["file_count"],
        }
    else:
        largest_bytes_value = {"path": None, "bytes": None}
        largest_files_value = {"path": None, "files": None}

    metrics.append(_metric(
        "largest_mission_dir_by_bytes", "bytes", "MEASURED", largest_bytes_value,
        missions_src, "argmax of recursive byte totals per mission directory",
        no_missions_note,
    ))
    metrics.append(_metric(
        "largest_mission_dir_by_file_count", "files", "MEASURED", largest_files_value,
        missions_src, "argmax of recursive file counts per mission directory",
        no_missions_note,
    ))

    # ----- pytest metrics ---------------------------------------------------
    pytest_seconds: Optional[float] = None
    pytest_collected: Optional[int] = None

    if skip_pytest:
        reason = "Full pytest execution skipped via --skip-pytest."
        mechanism = (
            "Re-run scripts/omni_metrics_baseline.py without --skip-pytest. "
            "One timed `pytest -q` run of the existing suite; no instrumentation, "
            "no paid calls (suite mocks all LLM clients)."
        )
        for name, unit in (("test_suite_wall_seconds", "seconds"),
                           ("pytest_collected_count", "tests")):
            metrics.append(_metric(
                name, unit, "DEFERRED", None, "pytest",
                "timed subprocess run of `pytest -q` (skipped this run)", reason,
            ))
            deferred.append(_deferred_entry(
                name, reason, mechanism,
                paid_calls=False, suite_minutes=10.0,
                requires_runtime_instrumentation=False,
            ))
    else:
        outcome = pytest_outcome or {}
        pytest_seconds = outcome.get("wall_seconds")
        pytest_collected = outcome.get("collected")
        error = outcome.get("error")
        notes = outcome.get("summary", "")
        if error:
            notes = f"{notes} [{error}]".strip()

        if pytest_collected is not None:
            metrics.append(_metric(
                "pytest_collected_count", "tests", "MEASURED", pytest_collected,
                "pytest",
                "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest --collect-only -q",
                notes,
            ))
        else:
            metrics.append(_metric(
                "pytest_collected_count", "tests", "DEFERRED", None, "pytest",
                "pytest --collect-only -q", notes or "collection failed",
            ))
            deferred.append(_deferred_entry(
                "pytest_collected_count", notes or "collection failed",
                "Fix collection environment and re-run baseline script.",
                paid_calls=False, suite_minutes=1.0,
                requires_runtime_instrumentation=False,
            ))

        if pytest_seconds is not None:
            metrics.append(_metric(
                "test_suite_wall_seconds", "seconds", "MEASURED", pytest_seconds,
                "pytest",
                "time.monotonic around PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 `pytest -q`",
                notes,
            ))
        else:
            metrics.append(_metric(
                "test_suite_wall_seconds", "seconds", "DEFERRED", None, "pytest",
                "timed subprocess run of `pytest -q`", notes or "run failed",
            ))
            deferred.append(_deferred_entry(
                "test_suite_wall_seconds", notes or "run failed",
                "Re-run baseline script when the suite can complete.",
                paid_calls=False, suite_minutes=10.0,
                requires_runtime_instrumentation=False,
            ))

    # ----- permanently deferred (this stage) metrics --------------------------
    permanently_deferred = (
        (
            "fresh_mission_wall_clock_seconds", "seconds",
            "True end-to-end wall clock (request to export) for a fresh mission "
            "requires running a live mission against hosted LLM providers.",
            "Run one mission via the existing pipeline with timing captured at "
            "the API boundary; or wait for Stage 5+ telemetry which records the "
            "full request span. Historical pipeline spans are reported above.",
            True, None, False,
        ),
        (
            "prompt_bytes_per_model_call", "bytes",
            "Prompts are not persisted anywhere; only responses are stored in "
            "agent_records.raw_output.",
            "Add len(prompt) logging in SupervisorAgent.run_state_step "
            "(agents/supervisor.py) — runtime instrumentation, Stage 5 scope.",
            False, None, True,
        ),
        (
            "hosted_token_usage_per_mission", "tokens",
            "Token counts are not recorded; provider usage objects are discarded "
            "in agents/llm_clients.py.",
            "Capture response.usage in the LLM client wrappers or read provider "
            "billing exports — runtime instrumentation or a live mission.",
            True, None, True,
        ),
        (
            "frontend_render_time_ms", "milliseconds",
            "No browser performance telemetry exists.",
            "Measure with browser devtools/Performance API against a running "
            "frontend; out of scope for artifact-based capture.",
            False, None, True,
        ),
    )
    for name, unit, reason, mechanism, paid, minutes, instrumentation in permanently_deferred:
        metrics.append(_metric(
            name, unit, "DEFERRED", None, "n/a (not capturable from artifacts)",
            "see deferred.required_mechanism", reason,
        ))
        deferred.append(_deferred_entry(
            name, reason, mechanism,
            paid_calls=paid, suite_minutes=minutes,
            requires_runtime_instrumentation=instrumentation,
        ))

    return {
        "captured_at": utc_now_iso(),
        "repo_commit": get_git_commit(repo_root),
        "mission_count_sampled": len(missions),
        "pytest_seconds": pytest_seconds,
        "pytest_collected": pytest_collected,
        "metrics": metrics,
        "audit_number_reproduction": build_audit_reproduction(missions, telemetry),
        "deferred": deferred,
    }


# ---------------------------------------------------------------------------
# Output handling — append-only history
# ---------------------------------------------------------------------------

def load_history_document(output_path: Path) -> Dict[str, Any]:
    if output_path.is_file():
        try:
            document = json.loads(output_path.read_text(encoding="utf-8"))
            if isinstance(document, dict) and isinstance(document.get("history"), list):
                return document
        except json.JSONDecodeError:
            pass
        # Never destroy an unreadable/foreign file silently.
        raise SystemExit(
            f"Refusing to overwrite {output_path}: existing file is not a "
            "baseline document. Move it aside or pass a different --output."
        )
    return {"schema_version": SCHEMA_VERSION, "history": []}


def write_history_document(output_path: Path, document: Dict[str, Any], pretty: bool) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    indent = 2 if pretty else None
    output_path.write_text(
        json.dumps(document, indent=indent, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="omni_metrics_baseline",
        description="OMNI Phase 10 Stage 0 — capture baseline metrics from "
                    "existing artifacts. Read-only; never runs missions or models.",
    )
    parser.add_argument("--repo-root", type=Path, default=infer_repo_root(),
                        help="Repo root (default: inferred from script location).")
    parser.add_argument("--output", type=Path, default=None,
                        help="Output JSON path (default: <repo-root>/docs/metrics/baseline.json).")
    parser.add_argument("--skip-pytest", action="store_true",
                        help="Skip the timed full pytest run (marks those metrics DEFERRED).")
    parser.add_argument("--max-missions", type=int, default=None,
                        help="Cap the number of mission folders sampled (default: no cap).")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    output_path = args.output if args.output is not None else repo_root / DEFAULT_OUTPUT_RELPATH

    missions = scan_missions(repo_root / MISSIONS_RELPATH, args.max_missions)
    telemetry = parse_telemetry(repo_root / TELEMETRY_RELPATH)
    pytest_outcome = None if args.skip_pytest else run_pytest_metrics(repo_root)

    entry = build_history_entry(
        repo_root=repo_root,
        missions=missions,
        telemetry=telemetry,
        pytest_outcome=pytest_outcome,
        skip_pytest=args.skip_pytest,
    )

    document = load_history_document(output_path)
    document["history"].append(entry)
    write_history_document(output_path, document, pretty=args.pretty)

    measured = sum(1 for m in entry["metrics"] if m["status"] == "MEASURED")
    estimated = sum(1 for m in entry["metrics"] if m["status"] == "ESTIMATED")
    deferred = sum(1 for m in entry["metrics"] if m["status"] == "DEFERRED")
    print(f"[omni_metrics_baseline] missions sampled: {len(missions)}")
    print(f"[omni_metrics_baseline] metrics: {measured} MEASURED, "
          f"{estimated} ESTIMATED, {deferred} DEFERRED")
    print(f"[omni_metrics_baseline] history entries: {len(document['history'])}")
    print(f"[omni_metrics_baseline] wrote: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
