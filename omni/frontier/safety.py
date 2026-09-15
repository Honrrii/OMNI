"""
OMNI Frontier Research safety/isolation policy (Phase 1).

The deterministic, testable slice of the isolation model described in
`.omni-lab/protocols/SAFETY_RULES.md`: which branch names are protected
(read-only from an autonomous research session) versus a valid disposable
research branch. Per `docs/agentic/repository_invariants.md`'s "deterministic
enforcement belongs in Python, tests, schemas, or hooks," this is Python
rather than a rule an agent has to remember from a prompt.

`HARD_SAFETY_RULES` is plain data (like `omni/autodev/config.py`'s
`DEFAULT_PROTECTED_AREAS`), not enforcement — it exists so the rule text has
one canonical source instead of being retyped across docs.

Nothing here creates a branch, launches a worktree, or runs git. This
module only classifies branch-name strings and holds policy text.
"""
from __future__ import annotations

# Trusted branches: read-only from an autonomous research session. "main" is
# this repository's actual default branch; "development" is the reserved
# name for a future integration trunk described in SAFETY_RULES.md and is
# listed here even though it does not exist yet, so the policy does not need
# to change the moment it's created.
PROTECTED_BRANCHES = ("main", "development")

# A disposable research branch must start with one of these prefixes.
RESEARCH_BRANCH_PREFIXES = (
    "autonomous-lab/",
    "claude/",
    "codex/",
    "integration/",
)


def is_protected_branch(name: str) -> bool:
    """Is `name` a trusted branch that a research session must treat as
    read-only (no commit, no push, no merge into it without explicit human
    approval)?
    """
    return isinstance(name, str) and name.strip() in PROTECTED_BRANCHES


def is_research_branch(name: str) -> bool:
    """Is `name` a valid disposable research branch?

    Must start with one of `RESEARCH_BRANCH_PREFIXES` followed by a
    non-empty experiment slug — the bare prefix alone (`"claude/"`, no
    slug) does not count, because every research branch must name the
    experiment it belongs to for the archive convention in
    `.omni-lab/protocols/EXPERIMENT_LIFECYCLE.md` to make sense.
    """
    if not isinstance(name, str):
        return False
    for prefix in RESEARCH_BRANCH_PREFIXES:
        if name.startswith(prefix) and name[len(prefix):].strip():
            return True
    return False


# The hard rules from .omni-lab/protocols/SAFETY_RULES.md, kept here as the
# one canonical list the docs and the skill both quote from rather than
# retyping. Enforcing these against a real git operation is future work —
# Phase 1 only defines and documents them.
HARD_SAFETY_RULES: tuple[str, ...] = (
    "No force pushes.",
    "No deleting protected branches.",
    "No rewriting protected history.",
    "No weakening tests merely to obtain a green result.",
    "No silently modifying validation thresholds.",
    "No modifying .git configuration to bypass protections.",
    "No accessing secrets or credentials.",
    "No uncontrolled deployment.",
    "No automatically merging research results into trusted OMNI development.",
    "No treating one agent's claim as proof.",
    "No agent certifying its own implementation.",
    "Human approval required before promotion into normal OMNI development.",
)
