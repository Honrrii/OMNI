"""
OMNI Frontier Research experiment contracts (Phase 1).

Structured, validated shapes for a single frontier research experiment: its
hypothesis, its lightweight prioritization score, its lifecycle status, and
— when concluded — which of `CONCLUSION_STATES` applies and the evidence
that must accompany it. Mirrors `omni/autodev/packets.py`'s validation
style: invalid data raises `ValueError` at construction time.

`.omni-lab/schemas/frontier_experiment.schema.json` is the provider-neutral
wire contract for this same shape — see `tests/test_frontier_schemas.py`
for the drift check between the two.

This module only builds and validates experiment records. It does not run
an experiment, write an archive to disk, or call a model API — see
`.omni-lab/protocols/EXPERIMENT_LIFECYCLE.md` for the archive convention
(`.omni-lab/experiments/OMNI-FRONTIER-XXXX/`) this record is meant to live
inside once a human or agent writes it out.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field

from omni.frontier.protocol import PROTOCOL_VERSION, validate_thread_id

EXPERIMENT_STATUSES = ("PROPOSED", "IN_PROGRESS", "COMPLETE")

# Research must not be forced into binary success/failure — see
# .omni-lab/protocols/EXPERIMENT_LIFECYCLE.md.
CONCLUSION_STATES = (
    "CONFIRMED",
    "REFUTED",
    "SUPPORTED",
    "PROMISING_UNPROVEN",
    "INCONCLUSIVE",
    "BLOCKED_BY_REQUIRED_EVIDENCE",
)

SCORE_DIMENSIONS = (
    "omni_alignment",
    "potential_impact",
    "information_gain",
    "generalizability",
    "novelty",
    "experimentalability",
    "risk",
    "implementation_cost",
)


def _require_nonempty(value: str, field_name: str, shape_name: str) -> None:
    if not value or not value.strip():
        raise ValueError(f"{shape_name}.{field_name} must be a non-empty string")


def _require_nonempty_list(items: list[str], field_name: str, shape_name: str) -> None:
    if not items:
        raise ValueError(f"{shape_name}.{field_name} must be non-empty")
    for item in items:
        if not item or not item.strip():
            raise ValueError(
                f"{shape_name}.{field_name} must not contain empty or "
                f"whitespace-only entries"
            )


@dataclass
class FrontierResearchScore:
    """Lightweight prioritization score, 0-5 per dimension.

    Not authoritative — see `.omni-lab/protocols/EXPERIMENT_LIFECYCLE.md`:
    "Do not treat this score as absolute truth. It exists to help
    prioritize research effort and prevent low-value novelty chasing."
    `total()` is a plain convenience sum for sorting a backlog by rough
    priority; it is not a validated or weighted formula, and higher is not
    unconditionally better (a high `risk` or `implementation_cost` score
    should pull priority down, not up — this method does not encode that
    judgment for you).
    """

    omni_alignment: int
    potential_impact: int
    information_gain: int
    generalizability: int
    novelty: int
    experimentalability: int
    risk: int
    implementation_cost: int

    def __post_init__(self) -> None:
        for dimension in SCORE_DIMENSIONS:
            value = getattr(self, dimension)
            if not isinstance(value, int) or isinstance(value, bool) or not (0 <= value <= 5):
                raise ValueError(
                    f"FrontierResearchScore.{dimension} must be an int in 0..5; "
                    f"got {value!r}"
                )

    def total(self) -> int:
        return sum(getattr(self, dimension) for dimension in SCORE_DIMENSIONS)


@dataclass
class FrontierExperiment:
    """One frontier research experiment record.

    `status` tracks lifecycle progress (`PROPOSED` -> `IN_PROGRESS` ->
    `COMPLETE`); `conclusion_state` tracks the *epistemic* result and is
    required once `status` is `COMPLETE`.

    Marking an experiment `COMPLETE` requires: `conclusion_state` set,
    `experiment_plan` describing what was actually run, `limitations`
    non-empty, `remaining_uncertainty` non-empty, and
    `recommended_next_action` non-empty — a completed experiment that
    can't say what it did, what's missing, or what's next is not a
    completed experiment.

    `evidence` must additionally be non-empty for every conclusion state
    *except* `BLOCKED_BY_REQUIRED_EVIDENCE`, which by definition means the
    evidence needed to conclude anything could not be obtained.

    `competing_hypotheses` and `counterevidence` are intentionally not
    required to be non-empty: an experiment with no known competing
    hypothesis or no counterevidence found is a legitimate state, not a
    missing field — forcing a non-empty entry there would just as likely
    produce a fabricated strawman.
    """

    experiment_id: str
    title: str
    hypothesis: str
    scoring: FrontierResearchScore
    created_at: str
    mechanism: str = ""
    competing_hypotheses: list[str] = field(default_factory=list)
    predicted_evidence: list[str] = field(default_factory=list)
    experiment_plan: str = ""
    safety_notes: list[str] = field(default_factory=list)
    participants: list[str] = field(default_factory=list)
    status: str = "PROPOSED"
    conclusion_state: str | None = None
    evidence: list[str] = field(default_factory=list)
    counterevidence: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    remaining_uncertainty: str = ""
    recommended_next_action: str = ""
    protocol_version: str = PROTOCOL_VERSION

    def __post_init__(self) -> None:
        validate_thread_id(self.experiment_id)
        _require_nonempty(self.title, "title", "FrontierExperiment")
        _require_nonempty(self.hypothesis, "hypothesis", "FrontierExperiment")
        _require_nonempty(self.created_at, "created_at", "FrontierExperiment")
        if self.protocol_version != PROTOCOL_VERSION:
            raise ValueError(
                f"FrontierExperiment.protocol_version {self.protocol_version!r} does "
                f"not match the current PROTOCOL_VERSION {PROTOCOL_VERSION!r}"
            )
        if self.status not in EXPERIMENT_STATUSES:
            raise ValueError(
                f"invalid FrontierExperiment.status {self.status!r}; "
                f"must be one of {EXPERIMENT_STATUSES}"
            )
        if self.conclusion_state is not None and self.conclusion_state not in CONCLUSION_STATES:
            raise ValueError(
                f"invalid FrontierExperiment.conclusion_state "
                f"{self.conclusion_state!r}; must be one of {CONCLUSION_STATES} or None"
            )
        if self.status == "COMPLETE" and self.conclusion_state is None:
            raise ValueError(
                "FrontierExperiment.conclusion_state is required when status is "
                "COMPLETE — research must not be forced into a binary done/not-done "
                "state without recording which CONCLUSION_STATES applies"
            )
        if self.conclusion_state is not None:
            self._require_conclusion_evidence()

    def _require_conclusion_evidence(self) -> None:
        _require_nonempty(
            self.experiment_plan, "experiment_plan", "FrontierExperiment (concluded)"
        )
        _require_nonempty_list(
            self.limitations, "limitations", "FrontierExperiment (concluded)"
        )
        _require_nonempty(
            self.remaining_uncertainty,
            "remaining_uncertainty",
            "FrontierExperiment (concluded)",
        )
        _require_nonempty(
            self.recommended_next_action,
            "recommended_next_action",
            "FrontierExperiment (concluded)",
        )
        if self.conclusion_state != "BLOCKED_BY_REQUIRED_EVIDENCE":
            _require_nonempty_list(
                self.evidence, "evidence", "FrontierExperiment (concluded)"
            )


def to_dict(experiment: FrontierExperiment) -> dict:
    return asdict(experiment)


def to_json(experiment: FrontierExperiment) -> str:
    return json.dumps(to_dict(experiment), indent=2) + "\n"


def frontier_experiment_from_dict(data: dict) -> FrontierExperiment:
    payload = dict(data)
    scoring = payload.get("scoring")
    if isinstance(scoring, dict):
        payload["scoring"] = FrontierResearchScore(**scoring)
    return FrontierExperiment(**payload)
