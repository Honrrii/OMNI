"""
Tests for agents/design_candidates.py — Vega structured design candidate normalizer.

All tests are deterministic. No LLM calls. No network calls.
"""
import pytest

from agents.design_candidates import (
    normalize_candidate,
    normalize_candidates,
    extract_design_candidates_from_text,
    _ID_PREFIX,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_raw(
    name="Crawler Bot",
    concept="Low-profile tracked crawler",
    platform="ground-rover",
    mobility_type="tracked",
    morphology_notes="Wide flat chassis",
    key_components=None,
    strengths=None,
    risks=None,
    required_validation=None,
    assumptions=None,
    recommended=False,
):
    return {
        "name": name,
        "concept": concept,
        "platform": platform,
        "mobility_type": mobility_type,
        "morphology_notes": morphology_notes,
        "key_components": key_components or ["tracks", "IMU", "camera"],
        "strengths": strengths or ["stable on uneven surfaces"],
        "risks": risks or ["motor torque may be insufficient"],
        "required_validation": required_validation or ["torque calculation"],
        "assumptions": assumptions or ["ground is metallic"],
        "recommended": recommended,
    }


# ---------------------------------------------------------------------------
# Single candidate normalisation
# ---------------------------------------------------------------------------

class TestNormalizeCandidate:

    def test_stable_id_index_1(self):
        result = normalize_candidate({}, 1)
        assert result["id"] == "vega_candidate_1"

    def test_stable_id_index_2(self):
        result = normalize_candidate({}, 2)
        assert result["id"] == "vega_candidate_2"

    def test_stable_id_index_3(self):
        result = normalize_candidate({}, 3)
        assert result["id"] == "vega_candidate_3"

    def test_id_uses_prefix_constant(self):
        result = normalize_candidate({}, 7)
        assert result["id"] == f"{_ID_PREFIX}_7"

    def test_all_required_fields_present(self):
        result = normalize_candidate({}, 1)
        required = [
            "id", "name", "concept", "platform", "mobility_type",
            "morphology_notes", "key_components", "strengths", "risks",
            "required_validation", "assumptions", "recommended",
        ]
        for field in required:
            assert field in result, f"Missing field: {field}"

    def test_missing_name_gets_default(self):
        result = normalize_candidate({}, 1)
        assert result["name"] == "Design Candidate 1"

    def test_missing_name_default_uses_index(self):
        result = normalize_candidate({}, 3)
        assert result["name"] == "Design Candidate 3"

    def test_missing_platform_gets_unknown(self):
        result = normalize_candidate({}, 1)
        assert result["platform"] == "unknown"

    def test_missing_mobility_type_gets_unknown(self):
        result = normalize_candidate({}, 1)
        assert result["mobility_type"] == "unknown"

    def test_missing_concept_gets_empty_string(self):
        result = normalize_candidate({}, 1)
        assert result["concept"] == ""

    def test_missing_morphology_notes_gets_empty_string(self):
        result = normalize_candidate({}, 1)
        assert result["morphology_notes"] == ""

    def test_missing_list_fields_get_empty_lists(self):
        result = normalize_candidate({}, 1)
        for field in ("key_components", "strengths", "risks", "required_validation", "assumptions"):
            assert result[field] == [], f"{field} should default to []"

    def test_recommended_defaults_to_false(self):
        result = normalize_candidate({}, 1)
        assert result["recommended"] is False

    def test_recommended_true_preserved(self):
        result = normalize_candidate({"recommended": True}, 1)
        assert result["recommended"] is True

    def test_full_candidate_passes_through(self):
        raw = _make_raw(recommended=True)
        result = normalize_candidate(raw, 2)
        assert result["id"] == "vega_candidate_2"
        assert result["name"] == "Crawler Bot"
        assert result["concept"] == "Low-profile tracked crawler"
        assert result["platform"] == "ground-rover"
        assert result["mobility_type"] == "tracked"
        assert result["morphology_notes"] == "Wide flat chassis"
        assert "tracks" in result["key_components"]
        assert "stable on uneven surfaces" in result["strengths"]
        assert "motor torque may be insufficient" in result["risks"]
        assert "torque calculation" in result["required_validation"]
        assert "ground is metallic" in result["assumptions"]
        assert result["recommended"] is True

    def test_non_dict_input_treated_as_empty(self):
        result = normalize_candidate("not a dict", 1)
        assert result["id"] == "vega_candidate_1"
        assert result["name"] == "Design Candidate 1"
        assert result["platform"] == "unknown"

    def test_none_input_treated_as_empty(self):
        result = normalize_candidate(None, 1)
        assert result["id"] == "vega_candidate_1"

    def test_list_fields_stringify_items(self):
        raw = {"strengths": [1, 2.5, "fast"]}
        result = normalize_candidate(raw, 1)
        assert result["strengths"] == ["1", "2.5", "fast"]

    def test_non_list_value_for_list_field_becomes_empty(self):
        raw = {"key_components": "tracks"}
        result = normalize_candidate(raw, 1)
        assert result["key_components"] == []

    def test_none_items_in_list_are_filtered(self):
        raw = {"risks": [None, "overheating", None]}
        result = normalize_candidate(raw, 1)
        assert result["risks"] == ["overheating"]

    def test_whitespace_only_string_gets_default(self):
        raw = {"name": "   ", "platform": "  "}
        result = normalize_candidate(raw, 1)
        assert result["name"] == "Design Candidate 1"
        assert result["platform"] == "unknown"


# ---------------------------------------------------------------------------
# List normalisation
# ---------------------------------------------------------------------------

class TestNormalizeCandidates:

    def test_empty_list_returns_empty(self):
        assert normalize_candidates([]) == []

    def test_non_list_returns_empty(self):
        assert normalize_candidates(None) == []
        assert normalize_candidates("string") == []
        assert normalize_candidates(42) == []
        assert normalize_candidates({}) == []

    def test_single_candidate_gets_id_1(self):
        result = normalize_candidates([_make_raw()])
        assert len(result) == 1
        assert result[0]["id"] == "vega_candidate_1"

    def test_two_candidates_stable_ids(self):
        result = normalize_candidates([_make_raw(name="A"), _make_raw(name="B")])
        assert len(result) == 2
        assert result[0]["id"] == "vega_candidate_1"
        assert result[1]["id"] == "vega_candidate_2"

    def test_three_candidates_stable_ids(self):
        raw = [
            _make_raw(name="Crawler", platform="ground-rover"),
            _make_raw(name="Drone", platform="drone-uav", mobility_type="aerial"),
            _make_raw(name="AUV", platform="auv", mobility_type="submarine"),
        ]
        result = normalize_candidates(raw)
        assert len(result) == 3
        assert result[0]["id"] == "vega_candidate_1"
        assert result[1]["id"] == "vega_candidate_2"
        assert result[2]["id"] == "vega_candidate_3"

    def test_three_candidates_names_preserved(self):
        raw = [
            _make_raw(name="Crawler"),
            _make_raw(name="Drone"),
            _make_raw(name="AUV"),
        ]
        result = normalize_candidates(raw)
        assert result[0]["name"] == "Crawler"
        assert result[1]["name"] == "Drone"
        assert result[2]["name"] == "AUV"

    def test_ids_deterministic_on_repeat(self):
        raw = [_make_raw(name="X"), _make_raw(name="Y")]
        first = normalize_candidates(raw)
        second = normalize_candidates(raw)
        assert first[0]["id"] == second[0]["id"]
        assert first[1]["id"] == second[1]["id"]

    def test_ids_deterministic_regardless_of_content(self):
        raw_a = [_make_raw(name="Alpha"), _make_raw(name="Beta")]
        raw_b = [_make_raw(name="Gamma"), _make_raw(name="Delta")]
        result_a = normalize_candidates(raw_a)
        result_b = normalize_candidates(raw_b)
        assert result_a[0]["id"] == result_b[0]["id"] == "vega_candidate_1"
        assert result_a[1]["id"] == result_b[1]["id"] == "vega_candidate_2"

    def test_missing_fields_filled_with_safe_defaults(self):
        result = normalize_candidates([{}])
        c = result[0]
        assert c["id"] == "vega_candidate_1"
        assert c["name"] == "Design Candidate 1"
        assert c["platform"] == "unknown"
        assert c["mobility_type"] == "unknown"
        assert c["recommended"] is False
        assert isinstance(c["key_components"], list)
        assert isinstance(c["strengths"], list)
        assert isinstance(c["risks"], list)

    def test_one_recommended_candidate_preserved(self):
        raw = [
            _make_raw(name="Safe Pick", recommended=False),
            _make_raw(name="Best Pick", recommended=True),
            _make_raw(name="Long Shot", recommended=False),
        ]
        result = normalize_candidates(raw)
        assert result[0]["recommended"] is False
        assert result[1]["recommended"] is True
        assert result[2]["recommended"] is False


# ---------------------------------------------------------------------------
# Artifact payload compatibility
# ---------------------------------------------------------------------------

class TestArtifactPayloadCompatibility:

    def test_design_alternatives_text_survives_alongside_candidates(self):
        """Existing design_alternatives key must not be overwritten by design_candidates."""
        design_report = "## Creative Design Alternatives\n\n### Alternative 1\n- Concept: Crawler"
        artifacts = {}
        artifacts["design_alternatives"] = {"owner": "Vega", "content": design_report}
        artifacts.setdefault("design_candidates", [])

        assert artifacts["design_alternatives"]["content"] == design_report
        assert artifacts["design_alternatives"]["owner"] == "Vega"
        assert artifacts["design_candidates"] == []

    def test_design_candidates_added_without_removing_other_artifact_keys(self):
        artifacts = {
            "ros2_node_graph": {"nodes": [], "edges": []},
            "component_tree": [],
            "risk_matrix": [],
            "design_alternatives": {"owner": "Vega", "content": "some text"},
        }
        candidates = normalize_candidates([_make_raw(name="Option A"), _make_raw(name="Option B")])
        artifacts["design_candidates"] = candidates

        assert "ros2_node_graph" in artifacts
        assert "component_tree" in artifacts
        assert "risk_matrix" in artifacts
        assert "design_alternatives" in artifacts
        assert len(artifacts["design_candidates"]) == 2

    def test_structured_candidates_coexist_with_markdown_text(self):
        markdown_report = "## Creative Design Alternatives\n### Alternative 1\n- Concept: Drone inspection"
        raw = [
            {"name": "Drone", "platform": "drone-uav", "recommended": True},
            {"name": "Rover", "platform": "ground-rover"},
        ]
        candidates = normalize_candidates(raw)
        artifacts = {
            "design_alternatives": {"owner": "Vega", "content": markdown_report},
            "design_candidates": candidates,
        }

        assert artifacts["design_alternatives"]["content"] == markdown_report
        assert len(artifacts["design_candidates"]) == 2
        assert artifacts["design_candidates"][0]["id"] == "vega_candidate_1"
        assert artifacts["design_candidates"][1]["id"] == "vega_candidate_2"

    def test_setdefault_does_not_overwrite_existing_candidates(self):
        candidates = normalize_candidates([_make_raw(name="Pre-loaded")])
        artifacts = {"design_candidates": candidates}
        artifacts.setdefault("design_candidates", [])
        assert len(artifacts["design_candidates"]) == 1
        assert artifacts["design_candidates"][0]["name"] == "Pre-loaded"


# ---------------------------------------------------------------------------
# extract_design_candidates_from_text — JSON path
# ---------------------------------------------------------------------------

_FENCED_JSON_3 = """\
## Creative Design Alternatives

### Alternative 1
- Concept: Tracked crawler
- Why it is interesting: stable on uneven terrain
- Practical concerns: heavier than wheeled

```json
{
  "design_candidates": [
    {"name": "Tracked Crawler", "concept": "Low-slung tracked platform", "platform": "ground-rover", "mobility_type": "tracked", "recommended": false},
    {"name": "Wheeled Rover", "concept": "Fast wheeled base", "platform": "ground-rover", "mobility_type": "wheeled", "recommended": true},
    {"name": "Inspection Drone", "concept": "Aerial camera platform", "platform": "drone-uav", "mobility_type": "aerial", "recommended": false}
  ]
}
```
"""

_MARKDOWN_3 = """\
## Creative Design Alternatives

### Alternative 1
- Concept: Tracked crawler for metal surfaces
- Why it is interesting: magnetic adhesion possible
- Practical concerns: motor torque requirements unknown

### Alternative 2
- Concept: Wheeled rover with wide stance
- Why it is interesting: simple drivetrain
- Practical concerns: may slip on steep inclines

### Alternative 3
- Concept: Legged hexapod
- Why it is interesting: steps over obstacles
- Practical concerns: complex gait control

## Recommended Direction
- Best option: Alternative 1
"""

_MARKDOWN_2 = """\
## Creative Design Alternatives

### Alternative 1
- Concept: Aquatic drone hull
- Why it is interesting: hydrodynamic efficiency
- Practical concerns: waterproofing electronics

### Alternative 2
- Concept: Surface skimmer
- Why it is interesting: faster than submerged
- Practical concerns: waves cause instability
"""


class TestExtractFromJsonBlock:

    def test_parses_fenced_json_design_candidates(self):
        result = extract_design_candidates_from_text(_FENCED_JSON_3)
        assert len(result) == 3

    def test_stable_ids_from_json_block(self):
        result = extract_design_candidates_from_text(_FENCED_JSON_3)
        assert result[0]["id"] == "vega_candidate_1"
        assert result[1]["id"] == "vega_candidate_2"
        assert result[2]["id"] == "vega_candidate_3"

    def test_json_block_names_preserved(self):
        result = extract_design_candidates_from_text(_FENCED_JSON_3)
        assert result[0]["name"] == "Tracked Crawler"
        assert result[1]["name"] == "Wheeled Rover"
        assert result[2]["name"] == "Inspection Drone"

    def test_json_block_platform_preserved(self):
        result = extract_design_candidates_from_text(_FENCED_JSON_3)
        assert result[0]["platform"] == "ground-rover"
        assert result[2]["platform"] == "drone-uav"

    def test_json_block_recommended_flag_preserved(self):
        result = extract_design_candidates_from_text(_FENCED_JSON_3)
        assert result[0]["recommended"] is False
        assert result[1]["recommended"] is True
        assert result[2]["recommended"] is False

    def test_json_block_missing_fields_get_defaults(self):
        text = '```json\n{"design_candidates": [{"name": "Sparse"}]}\n```'
        result = extract_design_candidates_from_text(text)
        assert len(result) == 1
        assert result[0]["platform"] == "unknown"
        assert result[0]["mobility_type"] == "unknown"
        assert result[0]["key_components"] == []

    def test_json_block_preferred_over_markdown_alternatives(self):
        text = _FENCED_JSON_3  # Contains both markdown and json block
        result = extract_design_candidates_from_text(text)
        # JSON block has 3 named candidates; markdown section has only Alternative 1
        assert result[0]["name"] == "Tracked Crawler"

    def test_invalid_json_falls_through_to_markdown(self):
        text = "```json\n{bad json\n```\n### Alternative 1\n- Concept: Fallback\n- Why it is interesting: works\n- Practical concerns: slow\n"
        result = extract_design_candidates_from_text(text)
        assert len(result) == 1
        assert result[0]["id"] == "vega_candidate_1"


# ---------------------------------------------------------------------------
# extract_design_candidates_from_text — Markdown fallback path
# ---------------------------------------------------------------------------

class TestExtractFromMarkdown:

    def test_parses_three_alternatives(self):
        result = extract_design_candidates_from_text(_MARKDOWN_3)
        assert len(result) == 3

    def test_parses_two_alternatives(self):
        result = extract_design_candidates_from_text(_MARKDOWN_2)
        assert len(result) == 2

    def test_stable_ids_from_markdown(self):
        result = extract_design_candidates_from_text(_MARKDOWN_3)
        assert result[0]["id"] == "vega_candidate_1"
        assert result[1]["id"] == "vega_candidate_2"
        assert result[2]["id"] == "vega_candidate_3"

    def test_name_from_heading(self):
        result = extract_design_candidates_from_text(_MARKDOWN_3)
        assert "Alternative 1" in result[0]["name"]
        assert "Alternative 2" in result[1]["name"]
        assert "Alternative 3" in result[2]["name"]

    def test_concept_extracted(self):
        result = extract_design_candidates_from_text(_MARKDOWN_3)
        assert "Tracked crawler" in result[0]["concept"]
        assert "Wheeled rover" in result[1]["concept"]
        assert "Legged hexapod" in result[2]["concept"]

    def test_strengths_from_why_interesting(self):
        result = extract_design_candidates_from_text(_MARKDOWN_3)
        assert result[0]["strengths"] == ["magnetic adhesion possible"]
        assert result[1]["strengths"] == ["simple drivetrain"]

    def test_risks_from_practical_concerns(self):
        result = extract_design_candidates_from_text(_MARKDOWN_3)
        assert "motor torque requirements unknown" in result[0]["risks"][0]
        assert "steep inclines" in result[1]["risks"][0]

    def test_two_alt_concept_extracted(self):
        result = extract_design_candidates_from_text(_MARKDOWN_2)
        assert "Aquatic drone hull" in result[0]["concept"]
        assert "Surface skimmer" in result[1]["concept"]

    def test_empty_string_returns_empty(self):
        assert extract_design_candidates_from_text("") == []

    def test_whitespace_only_returns_empty(self):
        assert extract_design_candidates_from_text("   \n\n  ") == []

    def test_non_string_returns_empty(self):
        assert extract_design_candidates_from_text(None) == []
        assert extract_design_candidates_from_text(42) == []
        assert extract_design_candidates_from_text([]) == []

    def test_text_with_no_alternatives_returns_empty(self):
        assert extract_design_candidates_from_text("Some generic text with no alternatives.") == []

    def test_ids_deterministic_on_repeat(self):
        a = extract_design_candidates_from_text(_MARKDOWN_3)
        b = extract_design_candidates_from_text(_MARKDOWN_3)
        assert [c["id"] for c in a] == [c["id"] for c in b]


# ---------------------------------------------------------------------------
# Supervisor-style artifact wiring (no LLM, simulates enrich_artifacts_from_state)
# ---------------------------------------------------------------------------

class TestSupervisorArtifactWiring:

    def _simulate_enrich(self, design_report: str) -> dict:
        """Simulate what supervisor.enrich_artifacts_from_state does for design fields."""
        artifacts: dict = {
            "ros2_node_graph": {"nodes": [], "edges": []},
            "risk_matrix": [],
        }
        design_candidates = extract_design_candidates_from_text(design_report)
        artifacts["design_alternatives"] = {
            "owner": "Vega",
            "content": design_report,
            "candidates": design_candidates,
        }
        artifacts["design_candidates"] = design_candidates
        return artifacts

    def test_design_candidates_non_empty_for_json_report(self):
        artifacts = self._simulate_enrich(_FENCED_JSON_3)
        assert len(artifacts["design_candidates"]) == 3

    def test_design_candidates_non_empty_for_markdown_report(self):
        artifacts = self._simulate_enrich(_MARKDOWN_3)
        assert len(artifacts["design_candidates"]) == 3

    def test_design_alternatives_content_preserved(self):
        artifacts = self._simulate_enrich(_MARKDOWN_3)
        assert artifacts["design_alternatives"]["content"] == _MARKDOWN_3

    def test_design_alternatives_owner_preserved(self):
        artifacts = self._simulate_enrich(_MARKDOWN_3)
        assert artifacts["design_alternatives"]["owner"] == "Vega"

    def test_design_alternatives_candidates_key_present(self):
        artifacts = self._simulate_enrich(_MARKDOWN_3)
        assert "candidates" in artifacts["design_alternatives"]

    def test_design_alternatives_candidates_matches_design_candidates(self):
        artifacts = self._simulate_enrich(_MARKDOWN_3)
        assert artifacts["design_alternatives"]["candidates"] == artifacts["design_candidates"]

    def test_candidate_ids_stable_in_payload(self):
        artifacts = self._simulate_enrich(_MARKDOWN_3)
        ids = [c["id"] for c in artifacts["design_candidates"]]
        assert ids == ["vega_candidate_1", "vega_candidate_2", "vega_candidate_3"]

    def test_other_artifact_keys_not_removed(self):
        artifacts = self._simulate_enrich(_MARKDOWN_2)
        assert "ros2_node_graph" in artifacts
        assert "risk_matrix" in artifacts

    def test_empty_report_produces_empty_candidates(self):
        artifacts = self._simulate_enrich("")
        assert artifacts["design_candidates"] == []
        assert artifacts["design_alternatives"]["candidates"] == []
        assert artifacts["design_alternatives"]["content"] == ""
