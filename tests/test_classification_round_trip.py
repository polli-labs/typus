import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import TypeAdapter

from typus.models.classification import (
    ClassificationResult,
    ClassificationSourceKind,
    DecisionPolicyKind,
    ScoreSemantics,
    TaxonCandidate,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "classification"
SCHEMA_PATH = Path(__file__).parents[1] / "typus" / "schemas" / "ClassificationResult.json"

FIXTURE_NAMES = [
    "raw_inference",
    "hierarchy_repair",
    "temperature_scaled_chow",
    "temperature_chow_hierarchy_repair",
    "curated_taxon_card",
    "synthetic_demo_cache",
    "cache_replay",
]


@pytest.mark.parametrize("fixture_name", FIXTURE_NAMES)
def test_classification_fixture_round_trips_against_schema(fixture_name):
    payload = _fixture_payload(fixture_name)
    result = ClassificationResult.model_validate(payload)
    serialized = json.loads(result.to_json(indent=2))

    assert serialized == payload
    Draft202012Validator(_classification_schema()).validate(serialized)
    assert ClassificationResult.model_validate_json(json.dumps(serialized)) == result

    # TODO(POL-980 PR4): run this same fixture corpus through generated TS types in polli.
    assert TypeAdapter(ClassificationResult).validate_python(serialized) == result


def test_fixture_semantics_cover_required_producer_flows():
    raw = ClassificationResult.model_validate(_fixture_payload("raw_inference"))
    assert raw.provenance.source_kind is ClassificationSourceKind.MODEL_INFERENCE
    assert raw.provenance.model_evidence is not None
    assert raw.provenance.calibration is None
    assert raw.provenance.decision_policies == []
    assert raw.outcomes is None

    repaired = ClassificationResult.model_validate(_fixture_payload("hierarchy_repair"))
    assert repaired.provenance.decision_policies[0].kind is DecisionPolicyKind.HIERARCHY_REPAIR
    assert repaired.outcomes is not None
    assert repaired.outcomes[1].adjustment.suppressed_from is not None

    chow = ClassificationResult.model_validate(_fixture_payload("temperature_scaled_chow"))
    assert chow.provenance.calibration is not None
    assert chow.provenance.calibration.method.value == "temperature_scaling"
    assert chow.provenance.decision_policies[0].kind is (
        DecisionPolicyKind.MAX_PROBABILITY_THRESHOLD
    )
    assert chow.ranks[0].candidates[0].score_semantics is (
        ScoreSemantics.TEMPERATURE_SCALED_RANK_PROBABILITY
    )

    composed = ClassificationResult.model_validate(
        _fixture_payload("temperature_chow_hierarchy_repair")
    )
    assert [policy.kind for policy in composed.provenance.decision_policies] == [
        DecisionPolicyKind.MAX_PROBABILITY_THRESHOLD,
        DecisionPolicyKind.HIERARCHY_REPAIR,
    ]
    assert composed.outcomes is not None
    assert all(outcome.derived_from_policy_id == "p1" for outcome in composed.outcomes)

    curated = ClassificationResult.model_validate(_fixture_payload("curated_taxon_card"))
    assert curated.provenance.source_kind is ClassificationSourceKind.CURATED_TAXON_CARD
    assert all(
        candidate.score_semantics is ScoreSemantics.AUTHORED_ASSERTION_WEIGHT
        for rank in curated.ranks
        for candidate in rank.candidates
    )
    assert curated.outcomes is None

    demo = ClassificationResult.model_validate(_fixture_payload("synthetic_demo_cache"))
    assert demo.provenance.source_kind is ClassificationSourceKind.SYNTHETIC_DEMO
    assert demo.provenance.decision_policies[0].kind is DecisionPolicyKind.DEMO_PROJECTION
    assert all(
        isinstance(candidate, TaxonCandidate) and candidate.taxon_snapshot is not None
        for candidate in demo.ranks[0].candidates
    )

    replay = ClassificationResult.model_validate(_fixture_payload("cache_replay"))
    assert replay.provenance.source_kind is ClassificationSourceKind.CACHE_REPLAY
    assert replay.provenance.decision_policies == []
    assert replay.outcomes is None
    replay_candidate = replay.ranks[0].candidates[0]
    assert isinstance(replay_candidate, TaxonCandidate)
    assert replay_candidate.taxon_snapshot is not None


def _fixture_payload(fixture_name: str):
    return json.loads((FIXTURE_DIR / f"{fixture_name}.json").read_text())


def _classification_schema():
    return json.loads(SCHEMA_PATH.read_text())
