"""
Self-test for scripts/omni_metrics_baseline.py (OMNI Phase 10 Stage 0).

Runs the baseline script against a tiny synthetic repo fixture only.
Never runs the full suite, never runs a mission, never calls a model.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from copy import deepcopy
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "omni_metrics_baseline.py"

VALID_STATUSES = {"MEASURED", "ESTIMATED", "DEFERRED"}
REQUIRED_METRIC_KEYS = {
    "metric", "unit", "status", "value", "source", "method", "captured_at", "notes",
}
REQUIRED_ENTRY_KEYS = {
    "captured_at", "repo_commit", "mission_count_sampled", "pytest_seconds",
    "pytest_collected", "metrics", "audit_number_reproduction", "deferred",
}


def _load_module():
    spec = importlib.util.spec_from_file_location("omni_metrics_baseline", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


baseline = _load_module()


# ---------------------------------------------------------------------------
# Fixture: tiny synthetic repo with three missions of known size
# ---------------------------------------------------------------------------

def _iso(hour: int, minute: int, second: int) -> str:
    return f"2026-06-01T{hour:02d}:{minute:02d}:{second:02d}+00:00"


def _mission_payload(mission_text: str, runtime_seconds: int, n_warnings: int) -> dict:
    agent_records = {
        agent_id: {
            "agent_id": agent_id,
            "agent_name": agent_id,
            "status": "completed",
            "parsed_output": {"warnings": []},
        }
        for agent_id in ["omni", "vega", "sky", "isy", "oli", "korva",
                         "pluto", "omni_revision", "qaz"]
    }
    return {
        "mission": mission_text,
        "artifacts": {"a": 1, "b": 2, "c": 3},
        "critique": {"issues_found": ["i1", "i2"]},
        "validation": {"missing_evidence": ["m1"], "required_next_tests": ["t1"]},
        "mission_state": {
            "created_at": _iso(10, 0, 0),
            "updated_at": _iso(10, runtime_seconds // 60, runtime_seconds % 60),
            "warnings": [f"w{i}" for i in range(n_warnings)],
            "agent_records": agent_records,
        },
    }


@pytest.fixture()
def synthetic_repo(tmp_path: Path) -> dict:
    missions_root = tmp_path / "outputs" / "omni_missions"
    specs = [
        ("m1_design_a_drone", "Design a survey drone", 30, 1, 100),
        ("m2_design_a_rover", "Design a rover with ROS2", 60, 2, 5_000),
        ("m3_design_a_bracket", "Design a CAD bracket", 90, 3, 20_000),
    ]
    expected = {"file_counts": [], "total_bytes": [], "payload_bytes": []}

    for name, text, runtime, warnings, filler_bytes in specs:
        mission_dir = missions_root / name
        mission_dir.mkdir(parents=True)
        payload = _mission_payload(text, runtime, warnings)
        payload_text = json.dumps(payload)
        (mission_dir / "mission.json").write_text(payload_text, encoding="utf-8")
        (mission_dir / "artifacts").mkdir()
        (mission_dir / "artifacts" / "filler.bin").write_bytes(b"x" * filler_bytes)
        (mission_dir / "provenance_record.json").write_text('{"stages": []}', encoding="utf-8")

        expected["file_counts"].append(3)
        expected["total_bytes"].append(
            len(payload_text.encode("utf-8")) + filler_bytes + len('{"stages": []}')
        )
        expected["payload_bytes"].append(len(json.dumps(json.loads(payload_text))))

    telemetry_dir = tmp_path / "logs" / "telemetry"
    telemetry_dir.mkdir(parents=True)
    events = [
        {"timestamp": _iso(9, 0, 0), "event_type": "mission_started", "mission_id": "t1"},
        {"timestamp": _iso(9, 0, 0), "event_type": "agent_started", "mission_id": "t1", "agent_id": "omni"},
        {"timestamp": _iso(9, 1, 0), "event_type": "mission_finished", "mission_id": "t1"},
    ]
    (telemetry_dir / "mission_runs.jsonl").write_text(
        "\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8"
    )

    return {"root": tmp_path, "expected": expected}


def _run(repo_root: Path, output: Path, extra_args: list[str] | None = None) -> dict:
    argv = [
        "--repo-root", str(repo_root),
        "--output", str(output),
        "--skip-pytest",
    ] + (extra_args or [])
    assert baseline.main(argv) == 0
    return json.loads(output.read_text(encoding="utf-8"))


def _metrics_by_name(entry: dict) -> dict:
    return {m["metric"]: m for m in entry["metrics"]}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_runs_and_produces_required_shape(synthetic_repo, tmp_path):
    output = tmp_path / "out" / "baseline.json"
    document = _run(synthetic_repo["root"], output)

    assert document["schema_version"] == baseline.SCHEMA_VERSION
    assert isinstance(document["history"], list) and len(document["history"]) == 1

    entry = document["history"][0]
    assert REQUIRED_ENTRY_KEYS <= set(entry.keys())
    assert entry["mission_count_sampled"] == 3
    assert entry["pytest_seconds"] is None
    assert entry["pytest_collected"] is None

    for metric in entry["metrics"]:
        assert REQUIRED_METRIC_KEYS <= set(metric.keys()), metric.get("metric")

    for claim in entry["audit_number_reproduction"]:
        assert claim["status"] in {"REPRODUCED", "DID_NOT_REPRODUCE", "NOT_FOUND"}


def test_distribution_math_is_correct(synthetic_repo, tmp_path):
    output = tmp_path / "baseline.json"
    entry = _run(synthetic_repo["root"], output)["history"][0]
    metrics = _metrics_by_name(entry)
    expected = synthetic_repo["expected"]

    file_counts = metrics["exported_mission_file_count"]["value"]
    assert file_counts == {
        "min": min(expected["file_counts"]),
        "median": 3,
        "max": max(expected["file_counts"]),
        "n_samples": 3,
    }

    total_bytes = metrics["exported_mission_bytes"]["value"]
    ordered = sorted(expected["total_bytes"])
    assert total_bytes == {
        "min": ordered[0], "median": ordered[1], "max": ordered[2], "n_samples": 3,
    }

    payload = metrics["serialized_payload_bytes_per_mission"]["value"]
    ordered = sorted(expected["payload_bytes"])
    assert payload == {
        "min": ordered[0], "median": ordered[1], "max": ordered[2], "n_samples": 3,
    }

    runtime = metrics["mission_runtime_seconds"]["value"]
    assert runtime == {"min": 30, "median": 60, "max": 90, "n_samples": 3}

    telemetry_runtime = metrics["telemetry_mission_runtime_seconds"]["value"]
    assert telemetry_runtime == {"min": 60, "median": 60, "max": 60, "n_samples": 1}

    warnings = metrics["warning_finding_count_per_mission"]["value"]
    # per mission: state warnings (1..3) + critique 2 + validation 1+1 = warnings+4
    assert warnings == {"min": 5, "median": 6, "max": 7, "n_samples": 3}

    activations = metrics["specialist_agent_activation_count_per_mission"]["value"]
    assert activations == {"min": 6, "median": 6, "max": 6, "n_samples": 3}

    largest = metrics["largest_mission_dir_by_bytes"]["value"]
    assert largest["path"] == "m3_design_a_bracket"

    types = metrics["mission_type_distribution"]["value"]
    assert types == {"drone": 1, "rover": 1, "cad": 1}


def test_every_metric_has_valid_status(synthetic_repo, tmp_path):
    output = tmp_path / "baseline.json"
    entry = _run(synthetic_repo["root"], output)["history"][0]
    for metric in entry["metrics"]:
        assert metric["status"] in VALID_STATUSES, metric["metric"]
        assert metric["method"], metric["metric"]


def test_deferred_metrics_have_mechanism_notes(synthetic_repo, tmp_path):
    output = tmp_path / "baseline.json"
    entry = _run(synthetic_repo["root"], output)["history"][0]

    deferred_metric_names = {
        m["metric"] for m in entry["metrics"] if m["status"] == "DEFERRED"
    }
    deferred_entries = {d["metric"]: d for d in entry["deferred"]}

    # --skip-pytest must defer pytest metrics; instrumentation metrics always deferred.
    assert "test_suite_wall_seconds" in deferred_metric_names
    assert "pytest_collected_count" in deferred_metric_names
    assert "prompt_bytes_per_model_call" in deferred_metric_names

    assert deferred_metric_names <= set(deferred_entries.keys())
    for name in deferred_metric_names:
        detail = deferred_entries[name]
        assert detail["required_mechanism"].strip(), name
        assert detail["reason"].strip(), name
        cost = detail["estimated_cost"]
        assert set(cost.keys()) == {
            "paid_calls", "suite_minutes", "requires_runtime_instrumentation",
        }


def test_second_run_appends_history_without_overwriting(synthetic_repo, tmp_path):
    output = tmp_path / "baseline.json"
    first = _run(synthetic_repo["root"], output)
    first_entry = deepcopy(first["history"][0])

    second = _run(synthetic_repo["root"], output)
    assert len(second["history"]) == 2
    assert second["history"][0] == first_entry


def test_max_missions_caps_sampling(synthetic_repo, tmp_path):
    output = tmp_path / "baseline.json"
    entry = _run(synthetic_repo["root"], output, ["--max-missions", "2"])["history"][0]
    assert entry["mission_count_sampled"] == 2
    # Deterministic: sorted order means m1 and m2 are sampled.
    assert entry["metrics"][0]["metric"] == "mission_count_sampled"


def test_handles_missing_artifact_dirs_gracefully(tmp_path):
    empty_repo = tmp_path / "empty_repo"
    empty_repo.mkdir()
    output = tmp_path / "baseline.json"
    entry = _run(empty_repo, output)["history"][0]

    assert entry["mission_count_sampled"] == 0
    metrics = _metrics_by_name(entry)
    assert metrics["exported_mission_bytes"]["value"]["n_samples"] == 0
    assert metrics["telemetry_mission_runtime_seconds"]["value"]["n_samples"] == 0
    for claim in entry["audit_number_reproduction"]:
        assert claim["status"] == "NOT_FOUND"


def test_does_not_import_hosted_sdks_or_runtime_llm_clients():
    # 1. Static check: no import statement mentions a denylisted module.
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    import_lines = [
        line.strip() for line in source.splitlines()
        if re.match(r"\s*(import|from)\s+", line)
    ]
    denylist = tuple(baseline.HOSTED_SDK_DENYLIST) + tuple(
        baseline.RUNTIME_LLM_MODULE_DENYLIST
    ) + ("agents", "backend")
    for line in import_lines:
        for banned in denylist:
            root = banned.split(".")[0]
            assert not re.match(rf"(import|from)\s+{re.escape(root)}\b", line), (
                f"forbidden import in baseline script: {line}"
            )

    # 2. Runtime check: importing the module did not pull any denylisted
    #    module into sys.modules.
    for banned in baseline.HOSTED_SDK_DENYLIST + baseline.RUNTIME_LLM_MODULE_DENYLIST:
        loaded_by_script = banned in sys.modules and "omni_metrics_baseline" in str(
            getattr(sys.modules[banned], "__loader__", "")
        )
        assert not loaded_by_script, f"baseline script loaded {banned}"


def test_refuses_to_clobber_foreign_output_file(synthetic_repo, tmp_path):
    output = tmp_path / "not_a_baseline.json"
    output.write_text('{"something": "else"}', encoding="utf-8")
    with pytest.raises(SystemExit):
        baseline.main([
            "--repo-root", str(synthetic_repo["root"]),
            "--output", str(output),
            "--skip-pytest",
        ])
    # Original content preserved.
    assert json.loads(output.read_text(encoding="utf-8")) == {"something": "else"}
