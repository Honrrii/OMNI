"""Phase 11 Stage 0a guard: prove the mission result normalizer is self-idempotent.

The sanitizer path already has idempotency coverage (test_legacy_name_sanitizer)
and normalize_mission_result has output-boundary stability coverage there too.
This file pins the missing piece directly: feeding the normalizer's own output
back into it must be a no-op for a structured dict payload that carries stable
created_at / result_id / mission.

    normalize_mission_result(mission, normalize_mission_result(mission, raw))
        == normalize_mission_result(mission, raw)

This matters before sandbox work: sandbox reports/findings may flow through the
normalization/export paths, so "run twice, no change" must hold for structured
payloads.

Volatile fallback paths (plain string / unexpected types) mint a fresh
datetime.now() created_at and result_id on every call by design, so they are
intentionally NOT asserted to be byte-identical here. Idempotency is scoped to
structured dict payloads with stable IDs/timestamps.

No network, no model calls, no filesystem — pure deterministic data.
"""

from backend.app.omni_core.mission_result_normalizer import (
    normalize_mission_result,
)


# A realistic, already-OMNI-clean structured mission result with stable
# identity fields. Built once and copied per-test so a test can never mutate
# shared state for another.
def _structured_mission_result():
    return {
        "mission": "Design a recon quadruped for OMNI Command",
        "created_at": "2026-06-12T10-30-00-000000",
        "result_id": "2026-06-12T10-30-00-000000",
        "status": "complete",
        "agents": {
            "omni": "Omni coordinated the mission.",
            "sky": "Sky drafted the ROS2 node graph.",
            "korva": "Korva specified the power budget.",
            "isy": "Isy checked torque and stability.",
            "oli": "Oli produced the CAD concept.",
            "pluto": "Pluto flagged two unsafe assumptions.",
            "qaz": "QaZ scored the blueprint at 0.82.",
            "vega": "Vega explored three morphologies.",
        },
        "agent_council": [
            {
                "id": "omni",
                "name": "Omni",
                "role": "Mission Orchestrator / Systems Intelligence",
                "color": "red",
                "responsibility": "Coordinates the mission.",
            },
        ],
        "council_events": [
            {"agent": "Omni", "event": "started"},
            {"agent": "Omni", "event": "completed"},
        ],
        "critique": {"by": "Pluto", "note": "Two assumptions need rework."},
        "revision": {"final_blueprint": "Revised quadruped blueprint."},
        "final_decision": "Revised quadruped blueprint.",
        "final_report": "Revised quadruped blueprint.",
        "artifacts": {
            "mission_overview": {
                "title": "Mission Overview",
                "description": "High-level interpretation.",
                "content": "Mission: recon quadruped.",
            },
        },
        "validation": {"score": 0.82, "passed": True},
        "timeline": [
            {"step": "1", "title": "Mission Received", "description": "Accepted."},
        ],
        "export_manifest": {"files": ["mission.json"]},
    }


def test_structured_payload_self_idempotent():
    raw = _structured_mission_result()
    mission = raw["mission"]

    first = normalize_mission_result(mission, raw)
    second = normalize_mission_result(mission, first)

    # Feeding the normalizer's own output back in is a no-op.
    assert second == first


def test_structured_payload_self_idempotent_five_passes():
    raw = _structured_mission_result()
    mission = raw["mission"]

    result = normalize_mission_result(mission, raw)
    first = result
    for _ in range(4):
        result = normalize_mission_result(mission, result)

    # Stable after the first normalization, all the way through repeated passes.
    assert result == first


def test_structured_payload_preserves_created_at_and_result_id():
    raw = _structured_mission_result()
    mission = raw["mission"]

    out = normalize_mission_result(mission, raw)

    assert out["created_at"] == raw["created_at"]
    assert out["result_id"] == raw["result_id"]


def test_structured_payload_preserves_mission():
    raw = _structured_mission_result()

    # Even if the caller passes a different mission argument, an explicit
    # mission in the payload is authoritative and preserved unchanged.
    out = normalize_mission_result("a different mission argument", raw)

    assert out["mission"] == raw["mission"]
