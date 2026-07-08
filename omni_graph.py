#!/usr/bin/env python3
"""
OMNI Graph — Mission Knowledge Graph v0.1 offline builder.

Reads a harness-produced mission folder and builds a structured
Mission Knowledge Graph JSON file.

Usage:
    python3 omni_graph.py --from outputs/omni_missions/<folder> --out /tmp/graph.json
    python3 omni_graph.py --help

Files read from the mission folder (all optional except mission_result.json):
    mission_result.json
    validation_report.json
    next_artifacts.json
    provenance_record.json

Output:
    A single mission_knowledge_graph.json written to --out path.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="omni_graph",
        description=(
            "OMNI Graph — Mission Knowledge Graph v0.1 offline builder.\n\n"
            "Reads a harness-produced mission folder and writes a structured\n"
            "Mission Knowledge Graph JSON file.\n\n"
            "Examples:\n"
            "  python3 omni_graph.py \\\n"
            "      --from outputs/omni_missions/2026-05-23_1911_design_a_rover \\\n"
            "      --out /tmp/mission_knowledge_graph.json\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--from",
        dest="mission_folder",
        metavar="FOLDER",
        help="Path to a harness-produced mission folder (contains mission_result.json).",
    )
    parser.add_argument(
        "--out",
        dest="output_path",
        metavar="PATH",
        help="Output path for the mission_knowledge_graph.json file.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        default=True,
        help="Write indented JSON (default: true).",
    )

    args = parser.parse_args()

    if not args.mission_folder or not args.output_path:
        parser.print_help()
        sys.exit(0)

    folder = Path(args.mission_folder)
    out_path = Path(args.output_path)

    if not folder.exists():
        print(f"[omni_graph] Error: mission folder not found: {folder}", file=sys.stderr)
        sys.exit(1)

    print(f"[omni_graph] Reading mission folder: {folder}")

    try:
        from backend.app.mission_graph.builder import build_graph
        graph = build_graph(folder)
    except Exception as exc:
        print(f"[omni_graph] Build failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    indent = 2 if args.pretty else None
    out_path.write_text(graph.model_dump_json(indent=indent), encoding="utf-8")

    n_warn = len(graph.consistency_warnings)
    print(f"[omni_graph] Graph written: {out_path}")
    print(
        f"[omni_graph] "
        f"Nodes: {len(graph.ros2_nodes)}  "
        f"Topics: {len(graph.ros2_topics)}  "
        f"Components: {len(graph.components)}  "
        f"CadFeatures: {len(graph.cad_features)}"
    )
    print(
        f"[omni_graph] "
        f"PowerRails: {len(graph.power_rails)}  "
        f"DataBuses: {len(graph.data_buses)}  "
        f"ValidationChecks: {len(graph.validation_checks)}"
    )
    if n_warn:
        print(f"[omni_graph] Consistency warnings: {n_warn}")
        for w in graph.consistency_warnings:
            tag = w.severity.upper()
            print(f"  [{tag}] {w.code}: {w.message}")
    else:
        print("[omni_graph] No consistency warnings.")


if __name__ == "__main__":
    main()
