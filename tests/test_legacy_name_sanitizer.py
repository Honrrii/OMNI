"""Phase 10 Stage 2A guard: prove the backend legacy-name sanitizer is idempotent.

The canonical backend sanitizer lives in backend/app/omni_core/formatters.py.
Before any sanitize-once collapse across call sites, these tests prove that
running the sanitizer multiple times yields the same result as running it once,
for plain strings and for nested missionResult-shaped payloads.

No network, no model calls, no outputs/ fixtures — pure deterministic data.
"""

import json

from backend.app.omni_core.formatters import (
    sanitize_legacy_names,
    sanitize_payload,
)

# Legacy tokens that must never survive sanitization, paired with the
# OMNI-safe name each should resolve to. Used to keep assertions honest.
LEGACY_TO_OMNI = {
    "Reed Richards": "Omni",
    "Tony Stark": "Sky",
    "Bruce Banner": "Isy",
    "Hank Pym": "Oli",
    "Ultron": "Pluto",
    "Vision": "QaZ",
    "Shuri": "Korva",
    "AI Avengers": "OMNI",
    "Marvel Geniuses HQ": "OMNI Command",
}

LEGACY_TOKENS = tuple(LEGACY_TO_OMNI.keys())


def sanitize_n_times(text, n):
    result = text
    for _ in range(n):
        result = sanitize_legacy_names(result)
    return result


def sanitize_payload_n_times(payload, n):
    result = payload
    for _ in range(n):
        result = sanitize_payload(result)
    return result


# ---------------------------------------------------------------------------
# 1. String replacement
# ---------------------------------------------------------------------------

def test_full_names_become_omni_safe():
    for legacy, omni in LEGACY_TO_OMNI.items():
        out = sanitize_legacy_names(legacy)
        assert out == omni, f"{legacy!r} -> {out!r}, expected {omni!r}"


def test_first_names_become_omni_safe():
    assert sanitize_legacy_names("Tony") == "Sky"
    assert sanitize_legacy_names("Bruce") == "Isy"
    assert sanitize_legacy_names("Hank") == "Oli"
    assert sanitize_legacy_names("Reed") == "Omni"


def test_replacement_inside_sentence():
    text = "Tony Stark and Bruce Banner reviewed Ultron's plan with Vision."
    out = sanitize_legacy_names(text)
    assert "Tony Stark" not in out
    assert "Bruce Banner" not in out
    assert "Ultron" not in out
    assert "Vision" not in out
    assert "Sky" in out
    assert "Isy" in out
    assert "Pluto" in out
    assert "QaZ" in out


def test_non_string_passthrough():
    assert sanitize_legacy_names(42) == 42
    assert sanitize_legacy_names(None) is None
    assert sanitize_legacy_names(True) is True


# ---------------------------------------------------------------------------
# 2. sanitize_legacy_names idempotency
# ---------------------------------------------------------------------------

def test_string_idempotent_once_equals_twice():
    text = "Reed Richards leads AI Avengers; Tony Stark and Vision assist."
    once = sanitize_legacy_names(text)
    twice = sanitize_legacy_names(once)
    assert once == twice


def test_string_idempotent_once_equals_five_passes():
    text = (
        "Marvel Geniuses HQ dispatched Hank Pym and Shuri while "
        "Reed reviewed Ultron's critique for Vision validation."
    )
    once = sanitize_n_times(text, 1)
    five = sanitize_n_times(text, 5)
    assert once == five
    for token in LEGACY_TOKENS:
        assert token not in five


# ---------------------------------------------------------------------------
# 3. sanitize_payload nested behavior
# ---------------------------------------------------------------------------

def test_payload_handles_strings_lists_and_dicts():
    payload = {
        "Tony Stark": "Bruce Banner",
        "members": ["Reed Richards", "Vision", "plain text"],
        "nested": {"Ultron": {"note": "Shuri built it"}},
    }
    out = sanitize_payload(payload)

    # dict keys sanitized
    assert "Sky" in out
    assert "Tony Stark" not in out
    # dict values sanitized
    assert out["Sky"] == "Isy"
    # list items sanitized
    assert out["members"] == ["Omni", "QaZ", "plain text"]
    # nested dict keys and values sanitized
    assert "Pluto" in out["nested"]
    assert out["nested"]["Pluto"]["note"] == "Korva built it"


def test_payload_preserves_scalars():
    payload = {
        "flag": True,
        "off": False,
        "count": 7,
        "ratio": 3.14,
        "missing": None,
        "label": "Tony Stark",
    }
    out = sanitize_payload(payload)
    assert out["flag"] is True
    assert out["off"] is False
    assert out["count"] == 7
    assert out["ratio"] == 3.14
    assert out["missing"] is None
    assert out["label"] == "Sky"


# ---------------------------------------------------------------------------
# 4. sanitize_payload idempotency
# ---------------------------------------------------------------------------

def test_payload_idempotent_once_equals_five_passes():
    payload = {
        "Reed Richards": ["Tony Stark", {"Vision": "Ultron"}],
        "report": "AI Avengers and Marvel Geniuses HQ shipped it.",
        "meta": {"lead": "Shuri", "depth": {"Bruce Banner": ["Hank Pym"]}},
    }
    once = sanitize_payload_n_times(payload, 1)
    five = sanitize_payload_n_times(payload, 5)
    assert once == five


# ---------------------------------------------------------------------------
# 5. missionResult-shaped payload
# ---------------------------------------------------------------------------

def _mission_result_payload():
    return {
        "mission": "Tony Stark requests a recon drone from AI Avengers",
        "agents": ["Reed Richards", "Bruce Banner", "Vision", "Shuri"],
        "artifacts": [
            {
                "name": "Ultron control script",
                "content": "Generated by Hank Pym under Marvel Geniuses HQ.",
                "Vision": "validated",
            },
            {
                "name": "thermal model",
                "content": ["Reed's notes", "Tony's review"],
            },
        ],
        "final_report": "AI Avengers delivered. Reed Richards signed off.",
        "critique": {"Ultron": "needs rework", "by": "Vision"},
        "revision": ["Bruce Banner patched it", "Hank Pym retested"],
        "memory_used": {"Shuri": True, "prior_lead": "Reed Richards", "count": 3},
    }


def test_mission_result_idempotent_and_clean():
    payload = _mission_result_payload()
    once = sanitize_payload_n_times(payload, 1)
    five = sanitize_payload_n_times(payload, 5)
    assert once == five

    serialized = json.dumps(five)
    for token in LEGACY_TOKENS:
        assert token not in serialized, f"legacy token survived: {token!r}"
    # also the short first names embedded in content
    assert "Reed's" not in serialized
    assert "Tony's" not in serialized

    # expected OMNI-safe names present after sanitization
    for omni in ("Omni", "Sky", "Isy", "QaZ", "Korva", "Pluto", "Oli", "OMNI"):
        assert omni in serialized, f"expected OMNI-safe name missing: {omni!r}"

    # structure/scalars preserved
    assert five["memory_used"]["count"] == 3
    assert five["memory_used"]["Korva"] is True
    assert five["agents"] == ["Omni", "Isy", "QaZ", "Korva"]


# ---------------------------------------------------------------------------
# 6. Stage 2B: normalize_mission_result output boundary stays fully sanitized.
#
# Stage 2B removed the redundant first sanitizer pass in
# normalize_mission_result (backend/app/main.py); the output-boundary
# sanitizer still covers the whole normalized payload. These tests pin that
# the function's output carries no legacy tokens and is sanitizer-stable.
# ---------------------------------------------------------------------------

from backend.app.main import normalize_mission_result  # noqa: E402


def test_normalize_mission_result_structured_payload_is_clean():
    raw_result = {
        "mission": "Tony Stark requests a recon drone from AI Avengers",
        "agents": {
            "reed_richards": {"role": "lead", "note": "Reed Richards coordinating"},
            "vision": {"role": "validator", "note": "Vision engineering validation"},
        },
        "final_report": "Reed Richards signed off. Ultron's critique resolved.",
        "final_synthesis": "Bruce Banner and Shuri delivered the build.",
        "artifacts": [
            {"name": "Ultron control script", "content": "Generated by Hank Pym."},
        ],
        "critique": {"Ultron": "needs rework", "by": "Vision"},
        "revision": {"final_blueprint": "Vision validated Reed Richards's design"},
    }

    out = normalize_mission_result(raw_result["mission"], raw_result)

    serialized = json.dumps(out, default=str)
    for token in LEGACY_TOKENS:
        assert token not in serialized, f"legacy token survived: {token!r}"

    for omni in ("Omni", "Sky", "Isy", "QaZ", "Korva", "Pluto", "Oli", "OMNI"):
        assert omni in serialized, f"expected OMNI-safe name missing: {omni!r}"

    # Output boundary fully sanitized -> a further pass is a no-op.
    assert sanitize_payload(out) == out


def test_normalize_mission_result_fallback_without_mission_key():
    # raw_result lacks "mission"; only final_report / final_synthesis carry
    # legacy names. The output boundary must still sanitize them.
    raw_result = {
        "final_report": "Reed Richards led; AI Avengers shipped it.",
        "final_synthesis": "Ultron's critique handled by Bruce Banner.",
    }

    out = normalize_mission_result("Marvel Geniuses HQ tasking", raw_result)

    serialized = json.dumps(out, default=str)
    for token in LEGACY_TOKENS:
        assert token not in serialized, f"legacy token survived: {token!r}"

    # The mission argument itself is sanitized into the output.
    assert "Marvel Geniuses HQ" not in out["mission"]
    assert "OMNI Command" in out["mission"]

    assert "Omni" in serialized
    assert "Isy" in serialized

    assert sanitize_payload(out) == out
