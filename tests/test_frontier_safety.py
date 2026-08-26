"""
Phase 1 guard: OMNI Frontier Research safety/isolation policy
(omni/frontier/safety.py) classifies protected vs. research branch names
correctly. This is the "safety-policy configuration ... represented
programmatically" the framework's verification requires — deterministic
Python, not a rule an agent has to remember from a prompt.
"""
from __future__ import annotations

from omni.frontier.safety import (
    HARD_SAFETY_RULES,
    PROTECTED_BRANCHES,
    RESEARCH_BRANCH_PREFIXES,
    is_protected_branch,
    is_research_branch,
)


def test_protected_branches_are_read_only():
    for branch in PROTECTED_BRANCHES:
        assert is_protected_branch(branch)
        assert not is_research_branch(branch)


def test_research_branch_prefixes_produce_valid_research_branches():
    for prefix in RESEARCH_BRANCH_PREFIXES:
        branch = f"{prefix}omni-frontier-0001"
        assert is_research_branch(branch)
        assert not is_protected_branch(branch)


def test_bare_prefix_without_experiment_slug_is_not_a_research_branch():
    for prefix in RESEARCH_BRANCH_PREFIXES:
        assert not is_research_branch(prefix)
        assert not is_research_branch(prefix.rstrip("/"))


def test_arbitrary_branch_is_neither_protected_nor_research():
    assert not is_protected_branch("omni/agentic-production-cleanup")
    assert not is_research_branch("omni/agentic-production-cleanup")


def test_classification_functions_reject_non_string_input_safely():
    for value in (None, 123, ["main"]):
        assert is_protected_branch(value) is False
        assert is_research_branch(value) is False


def test_hard_safety_rules_are_nonempty_and_stable():
    assert len(HARD_SAFETY_RULES) >= 10
    assert "No force pushes." in HARD_SAFETY_RULES
    assert "Human approval required before promotion into normal OMNI development." in HARD_SAFETY_RULES
    for rule in HARD_SAFETY_RULES:
        assert isinstance(rule, str) and rule.strip()
