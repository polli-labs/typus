"""Contract tests grounded in the promoted POL-2068 observation artifact."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Callable

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from typus.models.spatial import (
    ObservationProvenance,
    PointMeasurement,
    ResolutionStatus,
    SpatialObservation,
)

FIXTURE = Path(__file__).parent / "fixtures" / "spatial" / "pol-2068-observation.json"


def _payload() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text())


def test_real_pol_2068_observation_round_trips_and_replays_transform() -> None:
    observation = SpatialObservation.model_validate_json(FIXTURE.read_text())
    restored = SpatialObservation.model_validate_json(observation.model_dump_json())

    assert restored == observation
    assert restored.source_locator is not None
    assert restored.source_locator.frame_index == 79
    assert restored.evidence_frame is not None
    assert restored.evidence_frame.decoded_frame_index == 79
    assert restored.evidence_frame.pts_seconds == pytest.approx(1.3389830508474576)

    assert restored.measurement is not None
    assert isinstance(restored.measurement, PointMeasurement)
    source_point = restored.transforms.apply_point(
        restored.measurement.x,
        restored.measurement.y,
        from_space="display-content-normalized-v2",
        to_space="source-frame-normalized-v1",
    )
    assert source_point == pytest.approx((0.6164884690422869, 0.2953347174123158))


@pytest.mark.parametrize("missing_reference", ["source_locator", "evidence_frame"])
def test_source_and_evidence_references_are_independently_optional(missing_reference: str) -> None:
    payload = _payload()
    payload[missing_reference] = None
    observation = SpatialObservation.model_validate(payload)
    assert getattr(observation, missing_reference) is None


def test_presence_visibility_and_task_resolvability_are_independent() -> None:
    payload = _payload()
    payload["measurement"] = None
    payload["visibility"] = "occluded"
    payload["resolvability"] = {
        "localization": ResolutionStatus.NOT_RESOLVABLE,
        "segmentation": ResolutionStatus.NOT_RESOLVABLE,
    }
    observation = SpatialObservation.model_validate(payload)
    assert observation.presence.value == "present"
    assert observation.measurement is None


def test_human_corrected_and_imputed_provenance_remain_distinct() -> None:
    corrected = ObservationProvenance(
        producer="human", derivation="corrected", method="review", version="v1"
    )
    imputed = ObservationProvenance(
        producer="human", derivation="imputed", method="review", version="v1"
    )
    assert corrected.model_dump() != imputed.model_dump()


def _add_implicit_fps(value: dict[str, Any]) -> None:
    assert isinstance(value["source_locator"], dict)
    value["source_locator"]["fps"] = 30


def _drop_measurement_space(value: dict[str, Any]) -> None:
    assert isinstance(value["measurement"], dict)
    value["measurement"].pop("coordinate_space")


def _use_unknown_space(value: dict[str, Any]) -> None:
    assert isinstance(value["measurement"], dict)
    value["measurement"]["coordinate_space"] = "missing-space"


def _drop_presence(value: dict[str, Any]) -> None:
    value.pop("presence")


def _make_incomplete_bbox(value: dict[str, Any]) -> None:
    value["measurement"] = {
        "kind": "bbox",
        "coordinate_space": "display-content-normalized-v2",
    }


def _put_point_outside_extent(value: dict[str, Any]) -> None:
    assert isinstance(value["measurement"], dict)
    value["measurement"]["x"] = 1.1


def _measure_absent_subject(value: dict[str, Any]) -> None:
    value["presence"] = "absent"


@pytest.mark.parametrize(
    "mutate",
    [
        _add_implicit_fps,
        _drop_measurement_space,
        _drop_presence,
        _make_incomplete_bbox,
    ],
)
def test_exported_schema_rejects_structural_contract_cases(
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    schema = SpatialObservation.model_json_schema()
    payload = copy.deepcopy(_payload())
    mutate(payload)
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    assert errors
    with pytest.raises(ValidationError):
        SpatialObservation.model_validate(payload)


@pytest.mark.parametrize(
    "mutate",
    [_use_unknown_space, _put_point_outside_extent, _measure_absent_subject],
)
def test_python_contract_rejects_cross_field_semantic_cases(
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    payload = copy.deepcopy(_payload())
    mutate(payload)
    with pytest.raises(ValidationError):
        SpatialObservation.model_validate(payload)
