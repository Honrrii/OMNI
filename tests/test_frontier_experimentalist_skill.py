"""
Phase 2A guard: `.agents/skills/omni-frontier-experimentalist/SKILL.md`
exists at the canonical path, references the canonical Frontier Research
protocol instead of inventing a competing one, and preserves the Phase 1
safety boundaries.

These checks intentionally avoid a byte-for-byte comparison of the
markdown file (brittle) and instead check the invariants that matter: the
skill points at the same enforced contracts
(omni/frontier/protocol.py, omni/frontier/experiments.py) that
`omni-frontier-architect` uses, recognizes every message type and
conclusion state those modules define, and does not silently expand
Phase 1/2A scope (auto-invocation, orchestration, scheduling).
"""
from __future__ import annotations

import re
from pathlib import Path

from omni.frontier.experiments import CONCLUSION_STATES
from omni.frontier.protocol import MESSAGE_TYPES

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = (
    REPO_ROOT
    / ".agents"
    / "skills"
    / "omni-frontier-experimentalist"
    / "SKILL.md"
)
ARCHITECT_SKILL_PATH = (
    REPO_ROOT / ".claude" / "skills" / "omni-frontier-architect" / "SKILL.md"
)


def _skill_text() -> str:
    return SKILL_PATH.read_text()


def _frontmatter(text: str) -> dict[str, str]:
    match = re.match(r"^---\n(.*?)\n---\n", text, flags=re.DOTALL)
    assert match, "SKILL.md must start with a --- frontmatter block"
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


def test_skill_file_exists_at_canonical_agents_path():
    assert SKILL_PATH.is_file(), (
        f"expected the Codex Frontier Experimentalist skill at {SKILL_PATH}, "
        "matching the .agents/skills/<name>/SKILL.md convention already "
        "used by .agents/skills/omni-reviewer/SKILL.md"
    )


def test_skill_frontmatter_declares_expected_name_and_a_description():
    fields = _frontmatter(_skill_text())
    assert fields.get("name") == "omni-frontier-experimentalist"
    assert fields.get("description"), "SKILL.md frontmatter must have a non-empty description"


def test_skill_references_canonical_frontier_protocol_docs():
    text = _skill_text()
    for doc in (
        ".omni-lab/README.md",
        ".omni-lab/protocols/FRONTIER_RESEARCH_PROTOCOL.md",
        ".omni-lab/protocols/EXPERIMENT_LIFECYCLE.md",
        ".omni-lab/protocols/SAFETY_RULES.md",
        "omni/frontier/protocol.py",
        "omni/frontier/experiments.py",
        "omni/frontier/safety.py",
    ):
        assert doc in text, f"SKILL.md must reference canonical doc {doc!r}"


def test_skill_references_the_complementary_architect_skill():
    text = _skill_text()
    assert "omni-frontier-architect" in text
    assert ARCHITECT_SKILL_PATH.is_file(), (
        "the Phase 1 Claude-side skill this file complements must still exist"
    )


def test_skill_recognizes_every_existing_message_type():
    text = _skill_text()
    for message_type in MESSAGE_TYPES:
        assert message_type in text, (
            f"SKILL.md must recognize existing FrontierMessage type "
            f"{message_type!r} rather than silently dropping or replacing it"
        )


def test_skill_recognizes_every_existing_conclusion_state():
    text = _skill_text()
    for state in CONCLUSION_STATES:
        assert state in text, (
            f"SKILL.md must recognize existing FrontierExperiment conclusion "
            f"state {state!r} rather than defining a competing vocabulary"
        )


def test_skill_does_not_define_a_conflicting_message_type_vocabulary():
    text = _skill_text()
    # A conflicting protocol would introduce its own *_TYPES-shaped constant
    # or a differently-named message-type enum. Guard against the skill
    # inventing one instead of pointing at omni/frontier/protocol.py.
    assert "MESSAGE_TYPES" not in text or "omni.frontier.protocol" in text or "omni/frontier/protocol.py" in text
    forbidden_markers = ("CODEX_MESSAGE_TYPES", "codex_message_types", "class CodexMessage")
    for marker in forbidden_markers:
        assert marker not in text, f"SKILL.md must not define a parallel Codex-only protocol ({marker!r} found)"


def test_skill_preserves_phase_1_and_2a_safety_boundaries():
    text = _skill_text()
    required_boundaries = (
        "Do not build orchestration",
        "Do not invoke Codex automatically",
        "Do not create automatic Claude<->Codex communication",
        "Do not create scheduling",
        "Do not modify trusted OMNI architecture",
        "Do not push or merge into",
        "force-pushing",
    )
    for phrase in required_boundaries:
        assert phrase in text, f"SKILL.md must preserve safety boundary text: {phrase!r}"


def test_skill_states_the_producer_and_reviewer_roles_are_out_of_scope():
    text = _skill_text()
    assert "omni-producer" in text
    assert "omni-reviewer" in text
