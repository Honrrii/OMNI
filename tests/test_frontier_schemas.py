"""
Phase 1 guard: the provider-neutral wire schemas
(.omni-lab/schemas/frontier_message.schema.json,
.omni-lab/schemas/frontier_experiment.schema.json) parse as valid JSON and
have not drifted from the Python contracts they mirror
(omni/frontier/protocol.py, omni/frontier/experiments.py). No jsonschema
validator dependency is added for this — OMNI's Python-side enforcement
lives in the dataclasses (see test_frontier_protocol.py,
test_frontier_experiments.py); this file only guards against the schema
and the dataclasses silently disagreeing about the enums and required
fields both are supposed to share.
"""
from __future__ import annotations

import json
from pathlib import Path

from omni.frontier.experiments import CONCLUSION_STATES, EXPERIMENT_STATUSES, SCORE_DIMENSIONS
from omni.frontier.protocol import MESSAGE_TYPES, PROTOCOL_VERSION

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMAS_DIR = REPO_ROOT / ".omni-lab" / "schemas"


def _load_schema(filename: str) -> dict:
    return json.loads((SCHEMAS_DIR / filename).read_text())


def test_message_schema_is_valid_json_with_expected_shape():
    schema = _load_schema("frontier_message.schema.json")
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {
        "thread_id",
        "sequence",
        "from_agent",
        "to_agent",
        "message_type",
        "claim",
        "created_at",
        "protocol_version",
    }


def test_message_schema_type_enum_matches_python_message_types():
    schema = _load_schema("frontier_message.schema.json")
    assert set(schema["properties"]["message_type"]["enum"]) == set(MESSAGE_TYPES)


def test_message_schema_protocol_version_matches_python_constant():
    schema = _load_schema("frontier_message.schema.json")
    assert schema["properties"]["protocol_version"]["const"] == PROTOCOL_VERSION


def test_experiment_schema_is_valid_json_with_expected_shape():
    schema = _load_schema("frontier_experiment.schema.json")
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {
        "experiment_id",
        "title",
        "hypothesis",
        "scoring",
        "created_at",
        "status",
        "protocol_version",
    }


def test_experiment_schema_status_and_conclusion_enums_match_python():
    schema = _load_schema("frontier_experiment.schema.json")
    assert set(schema["properties"]["status"]["enum"]) == set(EXPERIMENT_STATUSES)
    # conclusion_state's schema enum carries a literal null alongside the
    # string states, since the field itself is ["string", "null"].
    schema_conclusion_states = {v for v in schema["properties"]["conclusion_state"]["enum"] if v is not None}
    assert schema_conclusion_states == set(CONCLUSION_STATES)


def test_experiment_schema_scoring_dimensions_match_python():
    schema = _load_schema("frontier_experiment.schema.json")
    scoring_schema = schema["properties"]["scoring"]
    assert set(scoring_schema["required"]) == set(SCORE_DIMENSIONS)
    for dimension in SCORE_DIMENSIONS:
        bounds = scoring_schema["properties"][dimension]
        assert bounds["minimum"] == 0
        assert bounds["maximum"] == 5


def test_experiment_schema_protocol_version_matches_python_constant():
    schema = _load_schema("frontier_experiment.schema.json")
    assert schema["properties"]["protocol_version"]["const"] == PROTOCOL_VERSION
