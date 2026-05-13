# backend/app/core/telemetry.py

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


DEFAULT_TELEMETRY_DIR = Path("logs/telemetry")
DEFAULT_TELEMETRY_FILE = DEFAULT_TELEMETRY_DIR / "mission_runs.jsonl"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_telemetry_dir() -> None:
    DEFAULT_TELEMETRY_DIR.mkdir(parents=True, exist_ok=True)


def log_event(
    event_type: str,
    mission_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
    telemetry_file: Path = DEFAULT_TELEMETRY_FILE,
) -> None:
    """
    Append one JSON event per line.

    This intentionally does not use a database yet.
    JSONL is easy to inspect, grep, parse, and migrate later.
    """
    ensure_telemetry_dir()

    event = {
        "timestamp": utc_now_iso(),
        "event_type": event_type,
        "mission_id": mission_id,
        "agent_id": agent_id,
        "payload": payload or {},
    }

    with telemetry_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def log_mission_started(state: Any) -> None:
    log_event(
        event_type="mission_started",
        mission_id=getattr(state, "mission_id", None),
        payload={
            "mission_text": getattr(state, "mission_text", ""),
            "status": getattr(state, "status", ""),
        },
    )


def log_mission_finished(state: Any) -> None:
    log_event(
        event_type="mission_finished",
        mission_id=getattr(state, "mission_id", None),
        payload={
            "status": getattr(state, "status", ""),
            "warnings": getattr(state, "warnings", []),
            "errors": getattr(state, "errors", []),
        },
    )


def log_agent_started(state: Any, agent_id: str) -> None:
    log_event(
        event_type="agent_started",
        mission_id=getattr(state, "mission_id", None),
        agent_id=agent_id,
    )


def log_agent_finished(state: Any, agent_id: str, parsed_output: Dict[str, Any]) -> None:
    log_event(
        event_type="agent_finished",
        mission_id=getattr(state, "mission_id", None),
        agent_id=agent_id,
        payload={
            "parsed_keys": list(parsed_output.keys()) if isinstance(parsed_output, dict) else [],
            "status": "completed",
        },
    )


def log_agent_failed(state: Any, agent_id: str, error: str) -> None:
    log_event(
        event_type="agent_failed",
        mission_id=getattr(state, "mission_id", None),
        agent_id=agent_id,
        payload={
            "error": error,
        },
    )


def log_synthesis_started(state: Any) -> None:
    log_event(
        event_type="artifact_synthesis_started",
        mission_id=getattr(state, "mission_id", None),
    )


def log_synthesis_finished(state: Any, artifact_keys: list[str]) -> None:
    log_event(
        event_type="artifact_synthesis_finished",
        mission_id=getattr(state, "mission_id", None),
        payload={
            "artifact_keys": artifact_keys,
        },
    )