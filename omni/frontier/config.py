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


# --- Phase 3: real Claude Code provider configuration -----------------------
#
# Distinct from FrontierLabConfig on purpose: FrontierLabConfig is
# orchestrator-owned authority (budgets, participants) that must stay
# provider-neutral. ClaudeProviderConfig is adapter-owned settings — how to
# launch a real `claude` process — that the orchestrator never reads. See
# `omni/frontier/claude_provider.py`'s module docstring.

PROVIDER_MODE_MOCK = "mock"
PROVIDER_MODE_CLAUDE_LIVE = "claude-live"
PROVIDER_MODES: tuple[str, ...] = (PROVIDER_MODE_MOCK, PROVIDER_MODE_CLAUDE_LIVE)


@dataclass(frozen=True)
class ClaudeProviderConfig:
    """Settings for launching the real Claude Code CLI as a research agent.

    `provider_mode` defaults to `"mock"` — this is the critical default
    behavior guarantee from the Phase 3 mission: constructing this config
    with no arguments must never imply a real model call. Only
    `scripts/omni_frontier_lab.py run-claude-shift` explicitly builds one
    with `provider_mode="claude-live"`.
    """

    provider_mode: str = PROVIDER_MODE_MOCK
    claude_executable: str = "claude"
    claude_timeout_seconds: int = 180
    claude_max_output_bytes: int = 400_000

    def __post_init__(self) -> None:
        if self.provider_mode not in PROVIDER_MODES:
            raise ValueError(
                f"ClaudeProviderConfig.provider_mode must be one of {PROVIDER_MODES}; "
                f"got {self.provider_mode!r}"
            )
        if not self.claude_executable or not self.claude_executable.strip():
            raise ValueError("ClaudeProviderConfig.claude_executable must be a non-empty string")
        if self.claude_timeout_seconds < 1:
            raise ValueError(
                f"ClaudeProviderConfig.claude_timeout_seconds must be >= 1; "
                f"got {self.claude_timeout_seconds!r}"
            )
        if self.claude_max_output_bytes < 1:
            raise ValueError(
                f"ClaudeProviderConfig.claude_max_output_bytes must be >= 1; "
                f"got {self.claude_max_output_bytes!r}"
            )


DEFAULT_CLAUDE_PROVIDER_CONFIG = ClaudeProviderConfig()


# --- Phase 4B: real Codex provider configuration ----------------------------
#
# Mirrors ClaudeProviderConfig's shape and the same reasoning: adapter-owned
# settings the orchestrator never reads, kept separate from
# FrontierLabConfig's provider-neutral authority. See
# `omni/frontier/codex_provider.py`'s module docstring for what "codex-live"
# actually launches and how it is bounded to read-only access.

PROVIDER_MODE_CODEX_LIVE = "codex-live"
CODEX_PROVIDER_MODES: tuple[str, ...] = (PROVIDER_MODE_MOCK, PROVIDER_MODE_CODEX_LIVE)


@dataclass(frozen=True)
class CodexProviderConfig:
    """Settings for launching the real Codex CLI as a research agent.

    `provider_mode` defaults to `"mock"` for the same reason
    `ClaudeProviderConfig.provider_mode` does: constructing this config with
    no arguments must never imply a real model call.
    """

    provider_mode: str = PROVIDER_MODE_MOCK
    codex_executable: str = "codex"
    codex_timeout_seconds: int = 180
    codex_max_output_bytes: int = 400_000

    def __post_init__(self) -> None:
        if self.provider_mode not in CODEX_PROVIDER_MODES:
            raise ValueError(
                f"CodexProviderConfig.provider_mode must be one of {CODEX_PROVIDER_MODES}; "
                f"got {self.provider_mode!r}"
            )
        if not self.codex_executable or not self.codex_executable.strip():
            raise ValueError("CodexProviderConfig.codex_executable must be a non-empty string")
        if self.codex_timeout_seconds < 1:
            raise ValueError(
                f"CodexProviderConfig.codex_timeout_seconds must be >= 1; "
                f"got {self.codex_timeout_seconds!r}"
            )
        if self.codex_max_output_bytes < 1:
            raise ValueError(
                f"CodexProviderConfig.codex_max_output_bytes must be >= 1; "
                f"got {self.codex_max_output_bytes!r}"
            )


DEFAULT_CODEX_PROVIDER_CONFIG = CodexProviderConfig()
