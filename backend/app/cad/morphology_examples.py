"""
OMNI CAD Morphology golden example smoke tests.

Run from the repo root after copying these files into OMNI:
    PYTHONPATH=$PWD python -m backend.app.cad.morphology_examples

Or run directly:
    python backend/app/cad/morphology_examples.py

Expected output:
    Results: 4/4 examples passed
"""

from __future__ import annotations

import json
import sys
from typing import Any, Dict, List

try:
    from .cad_morphology_planner import infer_morphology_spec
    from .morphology_quality_gate import validate_morphology_spec
except ImportError:  # Allows direct script execution from this folder.
    from cad_morphology_planner import infer_morphology_spec  # type: ignore
    from morphology_quality_gate import validate_morphology_spec  # type: ignore


GOLDEN_EXAMPLES: List[Dict[str, Any]] = [
    {
        "name": "Palm-sized insect exploration robot",
        "mission": "Design a palm-sized insect-inspired exploration robot",
        "expected_family": "insectoid_legged_robot",
        "expected_posture": "standing",
        "expected_min_legs": 6,
        "must_have_hard_negatives": True,
    },
    {
        "name": "Sci-fi hexapod inspection robot",
        "mission": "Design a sci-fi hexapod inspection robot with raised body and sensor head",
        "expected_family": "hexapod_robot",
        "expected_posture": "standing",
        "expected_min_legs": 6,
        "must_have_hard_negatives": True,
    },
    {
        "name": "Compact quadcopter drone",
        "mission": "Design a compact quadcopter drone",
        "expected_family": "aerial_drone",
        "expected_posture": "aerial",
        "expected_min_legs": 0,
        "must_have_hard_negatives": False,
    },
    {
        "name": "Tracked rover for indoor inspection",
        "mission": "Design a tracked rover for indoor inspection",
        "expected_family": "tracked_rover",
        "expected_posture": "low_slung",
        "expected_min_legs": 0,
        "must_have_hard_negatives": False,
    },
    {
        "name": "Gecko wall-climbing inspection robot",
        "mission": "Design a gecko-inspired wall-climbing inspection robot",
        "expected_family": "wall_climbing_robot",
        "expected_posture": "low_slung",
        "expected_min_legs": 4,
        "must_have_hard_negatives": True,
    },
    {
        "name": "Snake pipe inspection robot",
        "mission": "Design a snake-like pipe inspection robot with modular body segments",
        "expected_family": "serpentine_robot",
        "expected_posture": "segmented_chain",
        "expected_min_legs": 0,
        "must_have_hard_negatives": True,
    },
    {
        "name": "Manta-ray underwater exploration robot",
        "mission": "Design a manta-ray-inspired underwater exploration robot",
        "expected_family": "aquatic_glider_robot",
        "expected_posture": "aquatic",
        "expected_min_legs": 0,
        "must_have_hard_negatives": True,
    },
    {
        "name": "Bird-inspired reconnaissance drone",
        "mission": "Design a bird-inspired reconnaissance drone with wing-like stabilizers",
        "expected_family": "winged_uav",
        "expected_posture": "aerial",
        "expected_min_legs": 0,
        "must_have_hard_negatives": True,
    },
    {
        "name": "Crab shoreline exploration robot",
        "mission": "Design a crab-like shoreline exploration robot with lateral walking legs",
        "expected_family": "crustacean_walker",
        "expected_posture": "low_slung",
        "expected_min_legs": 8,
        "must_have_hard_negatives": True,
    },
    {
        "name": "Wolf quadruped scout robot",
        "mission": "Design a wolf-inspired quadruped scout robot with sensor head and tail stabilizer",
        "expected_family": "quadruped_robot",
        "expected_posture": "standing",
        "expected_min_legs": 4,
        "must_have_hard_negatives": True,
    },
]


def run_golden_examples(verbose: bool = True) -> bool:
    """Run all golden examples. Returns True only if every example passes."""
    all_passed = True
    results = []

    for example in GOLDEN_EXAMPLES:
        spec = infer_morphology_spec(example["mission"])
        gate = validate_morphology_spec(spec, example["mission"])
        legs = [app for app in spec.appendages if app.appendage_type == "leg"]

        checks = []
        failures = []

        if spec.morphology_family == example["expected_family"]:
            checks.append(("family", "PASS", spec.morphology_family))
        else:
            detail = f"got {spec.morphology_family}, want {example['expected_family']}"
            checks.append(("family", "FAIL", detail))
            failures.append(f"family mismatch: {detail}")

        if spec.body_posture == example["expected_posture"]:
            checks.append(("posture", "PASS", spec.body_posture))
        else:
            detail = f"got {spec.body_posture}, want {example['expected_posture']}"
            checks.append(("posture", "FAIL", detail))
            failures.append(f"posture mismatch: {detail}")

        if len(legs) >= example["expected_min_legs"]:
            checks.append(("leg_count", "PASS", f"{len(legs)} legs"))
        else:
            detail = f"{len(legs)} legs, need >= {example['expected_min_legs']}"
            checks.append(("leg_count", "FAIL", detail))
            failures.append(f"leg count: {detail}")

        if example.get("must_have_hard_negatives") and not spec.hard_negatives:
            checks.append(("hard_negatives", "FAIL", "no hard negatives defined"))
            failures.append("missing hard negatives")
        else:
            checks.append(("hard_negatives", "PASS", f"{len(spec.hard_negatives)} hard negatives"))

        gate_ok = gate.verdict in {"PASS", "WARN"}
        checks.append(("gate_verdict", "PASS" if gate_ok else "FAIL", gate.verdict))
        if not gate_ok:
            failures.append(f"gate verdict: {gate.verdict}")

        overall = "PASS" if not failures else "FAIL"
        if failures:
            all_passed = False

        results.append(
            {
                "name": example["name"],
                "overall": overall,
                "checks": checks,
                "failures": failures,
                "gate_score": gate.overall_score,
                "gate_verdict": gate.verdict,
                "morphology_family": spec.morphology_family,
                "body_posture": spec.body_posture,
                "leg_count": len(legs),
                "segment_count": len(spec.primary_segments),
                "anchor_count": len(spec.anchor_points),
                "hard_negative_count": len(spec.hard_negatives),
            }
        )

    if verbose:
        print("\n" + "=" * 72)
        print("OMNI CAD Morphology — Golden Example Results")
        print("=" * 72)
        for result in results:
            icon = "✓" if result["overall"] == "PASS" else "✗"
            print(f"\n{icon} {result['name']}")
            print(f"   Family:    {result['morphology_family']}")
            print(f"   Posture:   {result['body_posture']}")
            print(f"   Legs:      {result['leg_count']}")
            print(f"   Segments:  {result['segment_count']}")
            print(f"   Anchors:   {result['anchor_count']}")
            print(f"   Gate:      {result['gate_verdict']} ({result['gate_score']:.1f}/10)")
            for check_name, status, detail in result["checks"]:
                c_icon = "  ✓" if status == "PASS" else "  ✗"
                print(f"{c_icon} {check_name}: {detail}")
            if result["failures"]:
                print("   FAILURES:")
                for failure in result["failures"]:
                    print(f"     - {failure}")
        print("\n" + "=" * 72)
        passed = sum(1 for result in results if result["overall"] == "PASS")
        print(f"Results: {passed}/{len(results)} examples passed")
        print("=" * 72 + "\n")

    return all_passed


def print_example_spec(mission: str) -> None:
    """Print the full JSON spec and gate report for one mission."""
    spec = infer_morphology_spec(mission)
    gate = validate_morphology_spec(spec, mission)
    print(json.dumps(spec.to_dict(), indent=2))
    print("\n--- Gate Result ---")
    print(gate.to_markdown())


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--spec":
        print_example_spec(" ".join(sys.argv[2:]) or "Design a palm-sized insect-inspired exploration robot")
    else:
        sys.exit(0 if run_golden_examples(verbose=True) else 1)
