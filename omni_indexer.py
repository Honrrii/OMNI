#!/usr/bin/env python3
"""
OMNI Indexer — lightweight SQLite mission index.

Stores mission metadata after each harness run. Never replaces or modifies
output folders or generated artifacts.

Usage (standalone):
    python omni_indexer.py --db /tmp/omni/index.db --list
    python omni_indexer.py --db /tmp/omni/index.db --list --limit 5
    python omni_indexer.py --help

Programmatic:
    from omni_indexer import index_mission, list_missions
    rowid = index_mission(db_path, output_folder, result, next_artifacts)
    rows  = list_missions(db_path, limit=20)
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_DDL = """
CREATE TABLE IF NOT EXISTS missions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id          TEXT,
    timestamp           TEXT    NOT NULL,
    mission_text        TEXT,
    status              TEXT,
    output_path         TEXT,
    artifact_types      TEXT,
    warnings_count      INTEGER DEFAULT 0,
    blockers_count      INTEGER DEFAULT 0,
    validation_score    REAL,
    next_artifacts_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_missions_timestamp ON missions (timestamp);
CREATE INDEX IF NOT EXISTS idx_missions_status    ON missions (status);
"""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _open_db(db_path: Path) -> sqlite3.Connection:
    """Open (or create) the database and ensure schema exists."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    with conn:
        conn.executescript(_DDL)
    return conn


def _to_json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return "[]"


def _to_float_or_none(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Metadata extraction
# ---------------------------------------------------------------------------

def _extract_metadata(
    output_folder: Path,
    result: Dict[str, Any],
    next_artifacts: Optional[List[str]],
) -> Dict[str, Any]:
    """
    Derive all indexable fields from a mission result dict.
    Every extraction is defensive — missing keys produce safe defaults.
    """
    mission_state = result.get("mission_state") or {}
    if not isinstance(mission_state, dict):
        mission_state = {}

    # mission_id
    mission_id = result.get("mission_id") or mission_state.get("mission_id") or None

    # mission_text — cap at 2 000 chars to guard against huge LLM prompts
    mission_text = str(
        result.get("mission") or result.get("mission_text") or ""
    )[:2000]

    # status
    status = str(result.get("status") or "unknown")

    # artifact_types — keys of the top-level artifacts dict
    artifacts = result.get("artifacts") or {}
    if isinstance(artifacts, dict):
        artifact_types: List[str] = list(artifacts.keys())
    else:
        artifact_types = []

    # warnings_count — length of mission_state.warnings
    raw_warnings = mission_state.get("warnings") or []
    warnings_count = len(raw_warnings) if isinstance(raw_warnings, list) else 0

    # blockers_count — from reliability_report if present
    reliability = result.get("reliability_report") or {}
    if isinstance(reliability, dict):
        raw_blockers = reliability.get("blockers") or []
        blockers_count = len(raw_blockers) if isinstance(raw_blockers, list) else 0
    else:
        blockers_count = 0

    # validation_score
    validation = result.get("validation") or {}
    raw_score = validation.get("score") if isinstance(validation, dict) else None
    validation_score = _to_float_or_none(raw_score)

    # next_artifacts — use supplied list; fall back to artifacts.next_artifacts
    if next_artifacts is None:
        fallback = artifacts.get("next_artifacts") if isinstance(artifacts, dict) else []
        next_artifacts = fallback if isinstance(fallback, list) else []

    return {
        "mission_id": mission_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mission_text": mission_text,
        "status": status,
        "output_path": str(output_folder),
        "artifact_types": _to_json(artifact_types),
        "warnings_count": warnings_count,
        "blockers_count": blockers_count,
        "validation_score": validation_score,
        "next_artifacts_json": _to_json(next_artifacts),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def index_mission(
    db_path: Path,
    output_folder: Path,
    result: Dict[str, Any],
    next_artifacts: Optional[List[str]] = None,
) -> int:
    """
    Insert one mission metadata row into the SQLite index.

    Returns the rowid of the inserted row.
    Raises sqlite3.Error (or OSError) on failure — callers should wrap in
    try/except if they want graceful degradation.
    """
    meta = _extract_metadata(output_folder, result, next_artifacts)
    conn = _open_db(db_path)
    try:
        with conn:
            cursor = conn.execute(
                """
                INSERT INTO missions (
                    mission_id, timestamp, mission_text, status, output_path,
                    artifact_types, warnings_count, blockers_count,
                    validation_score, next_artifacts_json
                ) VALUES (
                    :mission_id, :timestamp, :mission_text, :status, :output_path,
                    :artifact_types, :warnings_count, :blockers_count,
                    :validation_score, :next_artifacts_json
                )
                """,
                meta,
            )
        return cursor.lastrowid
    finally:
        conn.close()


def list_missions(db_path: Path, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Return the most recent mission rows, newest first.
    Returns an empty list if the database does not yet exist.
    """
    if not db_path.exists():
        return []

    conn = _open_db(db_path)
    try:
        rows = conn.execute(
            """
            SELECT id, mission_id, timestamp, mission_text, status,
                   output_path, artifact_types, warnings_count, blockers_count,
                   validation_score, next_artifacts_json
            FROM   missions
            ORDER  BY timestamp DESC
            LIMIT  ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# CLI display helper
# ---------------------------------------------------------------------------

def _print_rows(db_path: Path, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        print(f"No missions indexed in: {db_path}")
        return

    print(f"\n{'─' * 72}")
    print(f"  OMNI Mission Index  —  {db_path}")
    print(f"  {len(rows)} row(s) shown (most recent first)")
    print(f"{'─' * 72}\n")

    for row in rows:
        ts = (row.get("timestamp") or "")[:19].replace("T", " ")
        status = str(row.get("status") or "?")
        text = (row.get("mission_text") or "")[:60]
        path = row.get("output_path") or ""
        warnings = row.get("warnings_count") or 0
        blockers = row.get("blockers_count") or 0
        score = row.get("validation_score")
        score_str = f"{score:.1f}" if score is not None else "—"

        try:
            artifact_count = len(json.loads(row.get("artifact_types") or "[]"))
        except Exception:
            artifact_count = "?"

        try:
            next_count = len(json.loads(row.get("next_artifacts_json") or "[]"))
        except Exception:
            next_count = "?"

        print(f"  [{row['id']:>4}]  {ts}  [{status:<12}]")
        print(f"         Mission  : {text}")
        print(f"         Folder   : {path}")
        print(
            f"         Artifacts: {artifact_count}  "
            f"Warnings: {warnings}  "
            f"Blockers: {blockers}  "
            f"Score: {score_str}  "
            f"Next: {next_count}"
        )
        print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="omni_indexer",
        description=(
            "OMNI Indexer — lightweight SQLite mission index.\n\n"
            "Stores and queries metadata from OMNI harness runs.\n"
            "Never modifies output folders or generated artifacts.\n\n"
            "Examples:\n"
            "  python omni_indexer.py --db /tmp/omni/index.db --list\n"
            "  python omni_indexer.py --db /tmp/omni/index.db --list --limit 5\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--db",
        required=True,
        metavar="PATH",
        help="Path to the SQLite index database.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List indexed missions, most recent first.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        metavar="N",
        help="Maximum rows to show with --list. Default: 20",
    )

    args = parser.parse_args()
    db_path = Path(args.db)

    if args.list:
        rows = list_missions(db_path, limit=args.limit)
        _print_rows(db_path, rows)
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
