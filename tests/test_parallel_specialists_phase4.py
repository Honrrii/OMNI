"""
Phase 4A tests: parallel specialist runner.

Uses stub/mock runners — no LLM calls are made.

Tests:
  1. Serial mode is the default (use_parallel_specialists=False)
  2. Parallel mode records all four specialist outputs in agent_records
  3. MissionState is mutated only on the main thread (deterministic merge phase)
  4. One failed specialist becomes a failed agent record; others continue
  5. --parallel appears in omni_harness --help output
"""
from __future__ import annotations

import inspect
import sys
import threading
from unittest.mock import patch

import pytest

from backend.app.omni_core.mission_state import MissionState


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_GOOD_SKY   = '{"agent_id": "sky",   "role": "robotics_software_architecture",   "status": "structured"}'
_GOOD_ISY   = '{"agent_id": "isy",   "role": "physics_controls_feasibility",     "status": "structured"}'
_GOOD_OLI   = '{"agent_id": "oli",   "role": "cad_visual_artifacts",             "status": "structured"}'
_GOOD_KORVA = '{"agent_id": "korva", "role": "hardware_electronics_embedded",    "status": "structured"}'


def _make_supervisor():
    from agents.supervisor import SupervisorAgent
    return SupervisorAgent()


# ---------------------------------------------------------------------------
# 1. Serial mode is the default
# ---------------------------------------------------------------------------

def test_serial_is_default():
    sig = inspect.signature(_make_supervisor().run_mission_structured)
    param = sig.parameters.get("use_parallel_specialists")
    assert param is not None, "use_parallel_specialists parameter not found on run_mission_structured"
    assert param.default is False, (
        f"use_parallel_specialists default must be False, got {param.default!r}"
    )


# ---------------------------------------------------------------------------
# 2. Parallel mode records all four specialist outputs
# ---------------------------------------------------------------------------

def test_parallel_records_all_four_specialists():
    state = MissionState(mission_text="Design a palm-sized rover with ROS2.")
    sup = _make_supervisor()

    with (
        patch.object(sup.robotics_agent, "run", return_value=_GOOD_SKY),
        patch.object(sup.research_agent, "run", return_value=_GOOD_ISY),
        patch.object(sup.code_agent,     "run", return_value=_GOOD_OLI),
        patch("agents.supervisor.call_llm", return_value=_GOOD_KORVA),
    ):
        reports = sup._run_specialists_parallel(state, memory_context="")

    assert len(reports) == 4, f"Expected 4 reports, got {len(reports)}"

    for agent_id in ("sky", "isy", "oli", "korva"):
        assert agent_id in state.agent_records, f"{agent_id} missing from agent_records"
        assert state.agent_records[agent_id].status == "completed", (
            f"{agent_id} status should be 'completed', "
            f"got {state.agent_records[agent_id].status!r}"
        )

    # Merge order must be sky → isy → oli → korva
    sky_raw, isy_raw, oli_raw, korva_raw = reports
    assert "sky"   in sky_raw
    assert "isy"   in isy_raw
    assert "oli"   in oli_raw
    assert "korva" in korva_raw


# ---------------------------------------------------------------------------
# 3. MissionState mutated only on main thread (deterministic merge phase)
# ---------------------------------------------------------------------------

def test_worker_threads_do_not_mutate_state():
    """
    Verify that state.start_agent() is only ever called from the main thread.
    Workers must return raw values and never touch state.
    """
    state = MissionState(mission_text="Thread safety check.")
    sup = _make_supervisor()

    main_thread_name = threading.main_thread().name
    caller_threads: list[str] = []

    original_start = state.start_agent

    def _tracking_start(agent_id: str, agent_name: str) -> None:
        caller_threads.append(threading.current_thread().name)
        original_start(agent_id=agent_id, agent_name=agent_name)

    # Shadow the bound method on the instance so _run_specialists_parallel
    # calls our wrapper instead.
    state.start_agent = _tracking_start  # type: ignore[method-assign]

    with (
        patch.object(sup.robotics_agent, "run", return_value=_GOOD_SKY),
        patch.object(sup.research_agent, "run", return_value=_GOOD_ISY),
        patch.object(sup.code_agent,     "run", return_value=_GOOD_OLI),
        patch("agents.supervisor.call_llm", return_value=_GOOD_KORVA),
    ):
        sup._run_specialists_parallel(state, memory_context="")

    assert caller_threads, "start_agent was never called"
    for caller in caller_threads:
        assert caller == main_thread_name, (
            f"state.start_agent() was called from non-main thread {caller!r}; "
            "workers must not mutate MissionState"
        )


# ---------------------------------------------------------------------------
# 4. One failed specialist → failed agent record; others continue
# ---------------------------------------------------------------------------

def test_one_failed_specialist_becomes_failed_agent_record():
    """
    Sky raises RuntimeError. Isy, Oli, Korva succeed.
    Verify: sky → failed; isy, oli, korva → completed.
    The overall call must not raise.
    """
    state = MissionState(mission_text="Resilience test mission.")
    sup = _make_supervisor()

    sky_exc = RuntimeError("LLM timeout")

    with (
        patch.object(sup.robotics_agent, "run", side_effect=sky_exc),
        patch.object(sup.research_agent, "run", return_value=_GOOD_ISY),
        patch.object(sup.code_agent,     "run", return_value=_GOOD_OLI),
        patch("agents.supervisor.call_llm", return_value=_GOOD_KORVA),
    ):
        reports = sup._run_specialists_parallel(state, memory_context="")

    assert len(reports) == 4, f"Expected 4 reports even with one failure, got {len(reports)}"

    # Sky must be a failed record.
    assert "sky" in state.agent_records, "sky missing from agent_records after failure"
    sky_rec = state.agent_records["sky"]
    assert sky_rec.status == "failed", (
        f"sky status should be 'failed', got {sky_rec.status!r}"
    )
    assert any("LLM timeout" in e for e in sky_rec.errors), (
        f"sky errors should contain 'LLM timeout', got {sky_rec.errors!r}"
    )

    # Other specialists must have completed.
    for agent_id in ("isy", "oli", "korva"):
        assert agent_id in state.agent_records, f"{agent_id} missing from agent_records"
        rec = state.agent_records[agent_id]
        assert rec.status == "completed", (
            f"{agent_id} should be 'completed', got {rec.status!r}"
        )


# ---------------------------------------------------------------------------
# 5. --parallel appears in omni_harness --help
# ---------------------------------------------------------------------------

def test_parallel_flag_in_omni_harness_help(capsys):
    import omni_harness

    with pytest.raises(SystemExit):
        with patch.object(sys, "argv", ["omni_harness", "--help"]):
            omni_harness.main()

    out = capsys.readouterr().out
    assert "--parallel" in out, (
        f"--parallel not found in omni_harness --help output:\n{out}"
    )
