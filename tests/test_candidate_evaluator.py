"""
Tests for agents/candidate_evaluator.py — deterministic OMNI candidate evaluator.

All tests are deterministic. No LLM calls. No network calls.
"""
import pytest

from agents.candidate_evaluator import (
    evaluate_design_candidates,
    _sky_score,
    _isy_score,
    _korva_score,
    _oli_score,
    _pluto_score,
    _qaz_score,
    _overall_score,
    _RECOMMENDED_BOOST,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clear_candidate(recommended=False):
    """Well-specified candidate — all fields populated, no risks, no assumptions."""
    return {
        "id": "vega_candidate_1",
        "name": "Tracked Crawler",
        "platform": "ground-rover",
        "mobility_type": "tracked",
        "morphology_notes": "Wide flat chassis with magnetic adhesion pads",
        "key_components": ["magnetic tracks", "IMU", "camera", "motor driver", "LiPo battery"],
        "strengths": ["stable on metal surfaces", "low center of gravity", "modular"],
        "risks": [],
        "required_validation": ["torque calculation", "weight estimate", "power budget"],
        "assumptions": [],
        "recommended": recommended,
    }


def _vague_candidate(recommended=False):
    """Sparse candidate — unknown platform/mobility, no components or validation."""
    return {
        "id": "vega_candidate_2",
        "name": "Mystery Design",
        "platform": "unknown",
        "mobility_type": "unknown",
        "morphology_notes": "",
        "key_components": [],
        "strengths": [],
        "risks": [],
        "required_validation": [],
        "assumptions": [],
        "recommended": recommended,
    }


def _risky_candidate():
    """Candidate with many risks and assumptions."""
    return {
        "id": "vega_candidate_3",
        "name": "Risky Design",
        "platform": "drone-uav",
        "mobility_type": "aerial",
        "morphology_notes": "Hexacopter frame",
        "key_components": ["rotors", "ESC"],
        "strengths": ["fast"],
        "risks": ["motor failure", "battery drain", "signal loss", "wind instability", "overheating"],
        "required_validation": [],
        "assumptions": ["calm weather", "flat launch pad", "GPS available", "FAA clearance", "stable wifi"],
        "recommended": False,
    }


# ---------------------------------------------------------------------------
# Empty / degenerate input
# ---------------------------------------------------------------------------

class TestEmptyInput:

    def test_empty_list_returns_safe_result(self):
        result = evaluate_design_candidates([])
        assert result["candidates_evaluated"] == 0
        assert result["evaluations"] == []
        assert result["recommended_candidate_id"] is None
        assert result["ranking"] == []
        assert isinstance(result["council_summary"], str)
        assert isinstance(result["open_questions"], list)

    def test_non_list_input_treated_as_empty(self):
        for bad in (None, "string", 42, {}):
            result = evaluate_design_candidates(bad)
            assert result["candidates_evaluated"] == 0

    def test_empty_returns_no_candidates_summary(self):
        result = evaluate_design_candidates([])
        assert "No candidates" in result["council_summary"]


# ---------------------------------------------------------------------------
# Single candidate
# ---------------------------------------------------------------------------

class TestSingleCandidate:

    def test_one_candidate_evaluated(self):
        result = evaluate_design_candidates([_clear_candidate()])
        assert result["candidates_evaluated"] == 1
        assert len(result["evaluations"]) == 1

    def test_one_candidate_recommended_id(self):
        result = evaluate_design_candidates([_clear_candidate()])
        assert result["recommended_candidate_id"] == "vega_candidate_1"

    def test_one_candidate_ranking_length(self):
        result = evaluate_design_candidates([_clear_candidate()])
        assert result["ranking"] == ["vega_candidate_1"]

    def test_one_candidate_all_score_keys_present(self):
        result = evaluate_design_candidates([_clear_candidate()])
        ev = result["evaluations"][0]
        for key in ("sky_score", "isy_score", "korva_score", "oli_score", "pluto_score", "qaz_score", "overall_score"):
            assert key in ev, f"Missing score key: {key}"

    def test_one_candidate_vague_evaluates_without_crash(self):
        result = evaluate_design_candidates([_vague_candidate()])
        assert result["candidates_evaluated"] == 1

    def test_non_dict_candidate_does_not_crash(self):
        result = evaluate_design_candidates(["not a dict", None, 42])
        assert result["candidates_evaluated"] == 3


# ---------------------------------------------------------------------------
# Score bounds
# ---------------------------------------------------------------------------

class TestScoreBounds:

    def _all_scores(self, c):
        ev = evaluate_design_candidates([c])["evaluations"][0]
        return [
            ev["sky_score"], ev["isy_score"], ev["korva_score"],
            ev["oli_score"], ev["pluto_score"], ev["qaz_score"],
            ev["overall_score"],
        ]

    def test_clear_candidate_scores_in_bounds(self):
        for score in self._all_scores(_clear_candidate()):
            assert 0.0 <= score <= 1.0, f"Out of bounds: {score}"

    def test_vague_candidate_scores_in_bounds(self):
        for score in self._all_scores(_vague_candidate()):
            assert 0.0 <= score <= 1.0, f"Out of bounds: {score}"

    def test_risky_candidate_scores_in_bounds(self):
        for score in self._all_scores(_risky_candidate()):
            assert 0.0 <= score <= 1.0, f"Out of bounds: {score}"

    def test_empty_dict_candidate_scores_in_bounds(self):
        for score in self._all_scores({}):
            assert 0.0 <= score <= 1.0, f"Out of bounds: {score}"

    def test_overall_with_recommended_boost_still_in_bounds(self):
        c = _clear_candidate(recommended=True)
        ev = evaluate_design_candidates([c])["evaluations"][0]
        assert 0.0 <= ev["overall_score"] <= 1.0


# ---------------------------------------------------------------------------
# Specialist axis scoring
# ---------------------------------------------------------------------------

class TestAxisScores:

    def test_clear_candidate_sky_score_above_vague(self):
        assert _sky_score(_clear_candidate()) > _sky_score(_vague_candidate())

    def test_clear_candidate_korva_score_above_vague(self):
        assert _korva_score(_clear_candidate()) > _korva_score(_vague_candidate())

    def test_clear_candidate_oli_score_above_vague(self):
        assert _oli_score(_clear_candidate()) > _oli_score(_vague_candidate())

    def test_clear_candidate_qaz_score_above_vague(self):
        assert _qaz_score(_clear_candidate()) > _qaz_score(_vague_candidate())

    def test_risky_candidate_pluto_score_lower_than_clear(self):
        assert _pluto_score(_risky_candidate()) < _pluto_score(_clear_candidate())

    def test_high_risk_burden_lowers_pluto_score(self):
        no_risks = {**_clear_candidate(), "risks": []}
        many_risks = {**_clear_candidate(), "risks": ["r1", "r2", "r3", "r4", "r5"]}
        assert _pluto_score(many_risks) < _pluto_score(no_risks)

    def test_validation_listed_raises_qaz_score(self):
        no_val = {**_clear_candidate(), "required_validation": []}
        with_val = {**_clear_candidate(), "required_validation": ["x", "y", "z"]}
        assert _qaz_score(with_val) > _qaz_score(no_val)

    def test_unknown_platform_lowers_sky_score(self):
        known = _clear_candidate()
        unknown = {**_clear_candidate(), "platform": "unknown"}
        assert _sky_score(known) > _sky_score(unknown)

    def test_morphology_notes_raises_oli_score(self):
        no_morph = {**_clear_candidate(), "morphology_notes": ""}
        with_morph = {**_clear_candidate(), "morphology_notes": "Wide low-profile chassis"}
        assert _oli_score(with_morph) > _oli_score(no_morph)

    def test_high_assumption_burden_lowers_isy_score(self):
        no_assum = {**_clear_candidate(), "assumptions": []}
        many_assum = {**_clear_candidate(), "assumptions": ["a1", "a2", "a3", "a4", "a5"]}
        assert _isy_score(many_assum) < _isy_score(no_assum)


# ---------------------------------------------------------------------------
# Ranking and recommended_candidate_id
# ---------------------------------------------------------------------------

class TestRanking:

    def test_three_candidates_produce_ranking(self):
        candidates = [_clear_candidate(), _vague_candidate(), _risky_candidate()]
        result = evaluate_design_candidates(candidates)
        assert len(result["ranking"]) == 3

    def test_clear_candidate_ranks_first_over_vague(self):
        candidates = [_vague_candidate(), _clear_candidate()]
        result = evaluate_design_candidates(candidates)
        assert result["ranking"][0] == "vega_candidate_1"  # clear is id 1

    def test_recommended_candidate_id_is_top_ranked(self):
        candidates = [_clear_candidate(), _vague_candidate(), _risky_candidate()]
        result = evaluate_design_candidates(candidates)
        assert result["recommended_candidate_id"] == result["ranking"][0]

    def test_ranking_is_deterministic(self):
        candidates = [_clear_candidate(), _vague_candidate(), _risky_candidate()]
        r1 = evaluate_design_candidates(candidates)
        r2 = evaluate_design_candidates(candidates)
        assert r1["ranking"] == r2["ranking"]
        assert r1["recommended_candidate_id"] == r2["recommended_candidate_id"]

    def test_recommended_true_is_small_boost_not_guaranteed_winner(self):
        """A vague candidate with recommended=True should NOT beat a well-specified one."""
        clear_no_rec = _clear_candidate(recommended=False)
        vague_with_rec = _vague_candidate(recommended=True)
        candidates = [clear_no_rec, vague_with_rec]
        result = evaluate_design_candidates(candidates)
        # Clear candidate (vega_candidate_1) must outrank vague despite recommended=True
        assert result["ranking"][0] == "vega_candidate_1"

    def test_recommended_boost_quantified(self):
        """Recommended boost must equal _RECOMMENDED_BOOST and not exceed it."""
        c = _vague_candidate(recommended=False)
        c_rec = {**c, "recommended": True}
        axes = {"sky": 0.0, "isy": 0.3, "korva": 0.0, "oli": 0.0, "pluto": 1.0, "qaz": 0.0}
        base = _overall_score(c, axes)
        boosted = _overall_score(c_rec, axes)
        assert abs(boosted - base - _RECOMMENDED_BOOST) < 1e-6

    def test_clear_candidate_beats_vague_in_overall(self):
        clear_ev = evaluate_design_candidates([_clear_candidate()])["evaluations"][0]
        vague_ev = evaluate_design_candidates([_vague_candidate()])["evaluations"][0]
        assert clear_ev["overall_score"] > vague_ev["overall_score"]

    def test_candidate_with_components_and_validation_beats_sparse(self):
        rich = {
            "id": "vega_candidate_1",
            "name": "Rich",
            "platform": "ground-rover",
            "mobility_type": "wheeled",
            "morphology_notes": "Compact differential drive",
            "key_components": ["wheels", "motor", "encoder", "IMU", "camera"],
            "strengths": ["fast", "simple"],
            "risks": [],
            "required_validation": ["speed test", "power budget"],
            "assumptions": [],
            "recommended": False,
        }
        sparse = {
            "id": "vega_candidate_2",
            "name": "Sparse",
            "platform": "unknown",
            "mobility_type": "unknown",
            "morphology_notes": "",
            "key_components": [],
            "strengths": [],
            "risks": [],
            "required_validation": [],
            "assumptions": [],
            "recommended": False,
        }
        rich_ev = evaluate_design_candidates([rich])["evaluations"][0]
        sparse_ev = evaluate_design_candidates([sparse])["evaluations"][0]
        assert rich_ev["overall_score"] > sparse_ev["overall_score"]


# ---------------------------------------------------------------------------
# Output structure
# ---------------------------------------------------------------------------

class TestOutputStructure:

    def test_all_top_level_keys_present(self):
        result = evaluate_design_candidates([_clear_candidate()])
        for key in ("candidates_evaluated", "evaluations", "recommended_candidate_id",
                    "ranking", "council_summary", "open_questions"):
            assert key in result, f"Missing key: {key}"

    def test_evaluations_carry_id_and_name(self):
        result = evaluate_design_candidates([_clear_candidate()])
        ev = result["evaluations"][0]
        assert ev["id"] == "vega_candidate_1"
        assert ev["name"] == "Tracked Crawler"

    def test_council_summary_mentions_top_candidate(self):
        result = evaluate_design_candidates([_clear_candidate()])
        assert "Tracked Crawler" in result["council_summary"]

    def test_council_summary_mentions_candidate_count(self):
        result = evaluate_design_candidates([_clear_candidate(), _vague_candidate()])
        assert "2" in result["council_summary"]

    def test_open_questions_is_list(self):
        result = evaluate_design_candidates([_clear_candidate()])
        assert isinstance(result["open_questions"], list)

    def test_open_questions_flags_unknown_platform(self):
        result = evaluate_design_candidates([_vague_candidate()])
        combined = " ".join(result["open_questions"]).lower()
        assert "platform" in combined

    def test_open_questions_flags_missing_validation(self):
        c = {**_clear_candidate(), "required_validation": []}
        result = evaluate_design_candidates([c])
        combined = " ".join(result["open_questions"]).lower()
        assert "validation" in combined

    def test_open_questions_empty_when_everything_clear(self):
        """A fully-specified candidate should generate no open questions."""
        result = evaluate_design_candidates([_clear_candidate()])
        # Platform, mobility known; validation listed; components listed; morphology present
        assert result["open_questions"] == []

    def test_candidates_evaluated_count_matches(self):
        result = evaluate_design_candidates([_clear_candidate(), _vague_candidate(), _risky_candidate()])
        assert result["candidates_evaluated"] == 3
        assert len(result["evaluations"]) == 3
        assert len(result["ranking"]) == 3


# ---------------------------------------------------------------------------
# Artifact payload compatibility (simulate supervisor wiring)
# ---------------------------------------------------------------------------

class TestArtifactPayloadCompatibility:

    def _simulate_artifact_wiring(self, design_candidates):
        """Simulate what supervisor.enrich_artifacts_from_state does."""
        artifacts = {
            "design_alternatives": {"owner": "Vega", "content": "markdown report"},
            "design_candidates": design_candidates,
        }
        if design_candidates:
            artifacts["candidate_evaluation"] = evaluate_design_candidates(design_candidates)
        return artifacts

    def test_candidate_evaluation_present_when_candidates_exist(self):
        candidates = [_clear_candidate(), _vague_candidate()]
        artifacts = self._simulate_artifact_wiring(candidates)
        assert "candidate_evaluation" in artifacts

    def test_candidate_evaluation_absent_when_no_candidates(self):
        artifacts = self._simulate_artifact_wiring([])
        assert "candidate_evaluation" not in artifacts

    def test_design_alternatives_content_preserved(self):
        candidates = [_clear_candidate()]
        artifacts = self._simulate_artifact_wiring(candidates)
        assert artifacts["design_alternatives"]["content"] == "markdown report"

    def test_design_candidates_key_preserved(self):
        candidates = [_clear_candidate(), _vague_candidate()]
        artifacts = self._simulate_artifact_wiring(candidates)
        assert artifacts["design_candidates"] == candidates

    def test_candidate_evaluation_has_expected_keys(self):
        candidates = [_clear_candidate()]
        artifacts = self._simulate_artifact_wiring(candidates)
        ev = artifacts["candidate_evaluation"]
        for key in ("candidates_evaluated", "evaluations", "recommended_candidate_id",
                    "ranking", "council_summary", "open_questions"):
            assert key in ev

    def test_candidate_evaluation_recommended_id_matches_ranking(self):
        candidates = [_clear_candidate(), _vague_candidate()]
        artifacts = self._simulate_artifact_wiring(candidates)
        ev = artifacts["candidate_evaluation"]
        assert ev["recommended_candidate_id"] == ev["ranking"][0]
