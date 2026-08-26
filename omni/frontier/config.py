"""
OMNI Frontier Research Lab — Phase 2B deterministic orchestration config.

Plain, immutable configuration for the mock research-shift orchestrator:
participant identities and the bounds that keep any run of the orchestrator
finite. Mirrors `omni/autodev/config.py`'s style — this module holds data
only, no I/O, no model calls, no network access.

Nothing here is agent-writable. `ShiftOrchestrator` (`omni/frontier/orchestrator.py`)
holds one `FrontierLabConfig` instance for the lifetime of a shift and reads
it to enforce bounds; no code path lets a `ResearchAgent` mutate it (see
`docs/agentic/repository_invariants.md`'s "deterministic enforcement belongs
in Python... not something an agent could talk past").
"""
from __future__ import annotations

from dataclasses import dataclass

from omni.frontier.experiments import FrontierResearchScore

# The only two research-agent identities Phase 2B's mock orchestrator knows
# how to route between. Real provider identities (Phase 3+) reuse these same
# strings — the orchestrator routes on identity, not on adapter class.
CLAUDE_AGENT_ID = "claude"
CODEX_AGENT_ID = "codex"
HUMAN_AGENT_ID = "human"

DEFAULT_PARTICIPANTS: tuple[str, ...] = (CLAUDE_AGENT_ID, CODEX_AGENT_ID)

# A deterministic placeholder score used only when the mock orchestrator
# creates a FrontierExperiment record for a mock shift. Real research
# threads score their own experiment per
# .omni-lab/protocols/EXPERIMENT_LIFECYCLE.md; this fixed score exists
# solely so Phase 2B's mock shift can construct a valid FrontierExperiment
# without inventing a scoring policy that belongs to a later phase.
MOCK_SHIFT_SCORE = FrontierResearchScore(
    omni_alignment=3,
    potential_impact=3,
    information_gain=3,
    generalizability=2,
    novelty=2,
    experimentalability=3,
    risk=1,
    implementation_cost=2,
)


@dataclass(frozen=True)
class FrontierLabConfig:
    """Bounds the deterministic orchestrator enforces for one research shift.

    Every bound here is orchestrator-owned: an agent may request an action
    (e.g. `ResearchTurnResult.requested_control`) but nothing in
    `omni/frontier/agents.py` or `omni/frontier/orchestrator.py` lets an
    agent's turn result raise, lower, or remove one of these numbers. See
    the module docstring.

    Defaults are conservative and sized for the Phase 2B mock demonstration
    (three debate rounds, ~12 agent turns) — not tuned for a real research
    session, which is future work.
    """

    participants: tuple[str, ...] = DEFAULT_PARTICIPANTS
    max_debate_rounds: int = 3
    max_agent_turns: int = 12
    max_experiment_retries: int = 2
    max_invalid_messages: int = 3
    max_consecutive_agent_failures: int = 2

    def __post_init__(self) -> None:
        if not self.participants or len(set(self.participants)) != len(self.participants):
            raise ValueError(
                f"FrontierLabConfig.participants must be a non-empty tuple of "
                f"unique agent identities; got {self.participants!r}"
            )
        for name in (
            "max_debate_rounds",
            "max_agent_turns",
            "max_experiment_retries",
            "max_invalid_messages",
            "max_consecutive_agent_failures",
        ):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError(
                    f"FrontierLabConfig.{name} must be a positive int; got {value!r}"
                )


DEFAULT_LAB_CONFIG = FrontierLabConfig()
