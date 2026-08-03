"""Portable spatial-observation contracts.

The models in this module describe evidence at an observation boundary. They
do not prescribe a tracker, decoder, annotation store, or model runtime.
"""

from __future__ import annotations

import enum
import math
import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .geometry import BBoxXYWHNorm

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_OPEN_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$")


class _SpatialModel(BaseModel):
    """Strict immutable base for wire contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class Presence(str, enum.Enum):
    PRESENT = "present"
    ABSENT = "absent"
    UNKNOWN = "unknown"


class Visibility(str, enum.Enum):
    VISIBLE = "visible"
    PARTIAL = "partial"
    OCCLUDED = "occluded"
    OUT_OF_FRAME = "out_of_frame"
    UNKNOWN = "unknown"


class ResolutionStatus(str, enum.Enum):
    RESOLVABLE = "resolvable"
    NOT_RESOLVABLE = "not_resolvable"
    NOT_ASSESSED = "not_assessed"
    UNKNOWN = "unknown"


class CoordinateUnit(str, enum.Enum):
    NORMALIZED = "normalized"
    PIXEL = "pixel"


class CoordinateOrigin(str, enum.Enum):
    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"
    CARTESIAN = "cartesian"


class AxisDirection(str, enum.Enum):
    RIGHT = "right"
    LEFT = "left"
    DOWN = "down"
    UP = "up"


class PointSemantics(str, enum.Enum):
    SAMPLE = "sample"
    PIXEL_CENTER = "pixel_center"
    CONTINUOUS = "continuous"


class BBoxEdgeConvention(str, enum.Enum):
    CONTINUOUS = "continuous"
    HALF_OPEN = "half_open"
    CLOSED = "closed"


class MaskGridAlignment(str, enum.Enum):
    PIXEL_CENTERS = "pixel_centers"
    PIXEL_EDGES = "pixel_edges"
    CONTINUOUS = "continuous"


class BoundsPolicy(str, enum.Enum):
    REJECT = "reject"
    CLAMP = "clamp"
    ALLOW = "allow"


class NumericRepresentation(str, enum.Enum):
    FLOAT32 = "float32"
    FLOAT64 = "float64"
    INTEGER = "integer"


class RoundingMode(str, enum.Enum):
    NONE = "none"
    FLOOR = "floor"
    CEIL = "ceil"
    TRUNCATE = "truncate"
    HALF_UP = "half_up"


class Invertibility(str, enum.Enum):
    EXACT = "exact"
    APPROXIMATE = "approximate"
    NONE = "none"


class SpatialExtent(_SpatialModel):
    """Closed coordinate-domain bounds."""

    x_min: float
    y_min: float
    x_max: float
    y_max: float

    @model_validator(mode="after")
    def _ordered_and_finite(self) -> "SpatialExtent":
        values = (self.x_min, self.y_min, self.x_max, self.y_max)
        if not all(math.isfinite(value) for value in values):
            raise ValueError("coordinate extent must be finite")
        if self.x_max <= self.x_min or self.y_max <= self.y_min:
            raise ValueError("coordinate extent maxima must exceed minima")
        return self


class RasterDimensions(_SpatialModel):
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class CoordinateSpace(_SpatialModel):
    """Explicit coordinate interpretation for portable spatial evidence."""

    space_id: str
    unit: CoordinateUnit
    origin: CoordinateOrigin
    x_axis: AxisDirection
    y_axis: AxisDirection
    extent: SpatialExtent
    dimensions: RasterDimensions
    asset_id: str
    crop_id: str | None = None
    point_semantics: PointSemantics
    bbox_edge_convention: BBoxEdgeConvention
    mask_grid_alignment: MaskGridAlignment
    bounds_policy: BoundsPolicy
    numeric_representation: NumericRepresentation
    aliases: tuple[str, ...] = ()

    @field_validator("space_id", "asset_id", "crop_id")
    @classmethod
    def _valid_open_name(cls, value: str | None) -> str | None:
        if value is not None and not _OPEN_NAME_RE.fullmatch(value):
            raise ValueError("identifier must be non-empty portable token text")
        return value

    @field_validator("aliases")
    @classmethod
    def _valid_aliases(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(values)) != len(values):
            raise ValueError("coordinate-space aliases must be unique")
        if any(not _OPEN_NAME_RE.fullmatch(value) for value in values):
            raise ValueError("coordinate-space aliases must be portable token text")
        return values

    @model_validator(mode="after")
    def _unit_matches_extent(self) -> "CoordinateSpace":
        if self.unit is CoordinateUnit.NORMALIZED:
            expected = (0.0, 0.0, 1.0, 1.0)
            actual = (
                self.extent.x_min,
                self.extent.y_min,
                self.extent.x_max,
                self.extent.y_max,
            )
            if actual != expected:
                raise ValueError("normalized coordinate spaces require extent [0, 0, 1, 1]")
        return self


Matrix2x3 = tuple[
    tuple[float, float, float],
    tuple[float, float, float],
]


class TransformStep(_SpatialModel):
    """One replayable affine step in an ordered transform chain.

    ``method`` carries product-compatible labels such as
    ``clip-crop-unmap-v1``. The affine matrix, spaces, and numeric policy are
    the primitive contract.
    """

    from_space: str
    to_space: str
    kind: str = "affine_2d"
    method: str
    matrix_2x3: Matrix2x3
    rounding: RoundingMode
    bounds_policy: BoundsPolicy
    invertibility: Invertibility
    round_trip_tolerance: float | None = Field(default=None, ge=0.0)

    @field_validator("from_space", "to_space", "kind", "method")
    @classmethod
    def _valid_names(cls, value: str) -> str:
        if not _OPEN_NAME_RE.fullmatch(value):
            raise ValueError("transform identifiers must be portable token text")
        return value

    @field_validator("matrix_2x3")
    @classmethod
    def _finite_matrix(cls, matrix: Matrix2x3) -> Matrix2x3:
        if not all(math.isfinite(value) for row in matrix for value in row):
            raise ValueError("transform matrix must be finite")
        return matrix

    @model_validator(mode="after")
    def _coherent_invertibility(self) -> "TransformStep":
        (a, b, _), (d, e, _) = self.matrix_2x3
        determinant = a * e - b * d
        if self.invertibility is not Invertibility.NONE and math.isclose(determinant, 0.0):
            raise ValueError("an invertible affine transform requires a non-singular matrix")
        if self.invertibility is Invertibility.NONE and self.round_trip_tolerance is not None:
            raise ValueError("a non-invertible transform cannot declare round-trip tolerance")
        if self.invertibility is not Invertibility.NONE and self.round_trip_tolerance is None:
            raise ValueError("an invertible transform must declare round-trip tolerance")
        return self

    def apply_point(self, x: float, y: float) -> tuple[float, float]:
        """Apply the affine matrix and declared rounding policy to one point."""
        (a, b, c), (d, e, f) = self.matrix_2x3
        return self._round(a * x + b * y + c), self._round(d * x + e * y + f)

    def _round(self, value: float) -> float:
        if self.rounding is RoundingMode.NONE:
            return value
        if self.rounding is RoundingMode.FLOOR:
            return float(math.floor(value))
        if self.rounding is RoundingMode.CEIL:
            return float(math.ceil(value))
        if self.rounding is RoundingMode.TRUNCATE:
            return float(math.trunc(value))
        return math.copysign(float(math.floor(abs(value) + 0.5)), value)


class TransformChain(_SpatialModel):
    """Coordinate-space registry plus an ordered, composable step chain."""

    spaces: tuple[CoordinateSpace, ...]
    steps: tuple[TransformStep, ...]

    @model_validator(mode="after")
    def _connected(self) -> "TransformChain":
        if not self.spaces:
            raise ValueError("a transform chain requires coordinate-space context")
        ids = [space.space_id for space in self.spaces]
        if len(set(ids)) != len(ids):
            raise ValueError("coordinate-space ids must be unique")
        aliases = [alias for space in self.spaces for alias in space.aliases]
        if len(set(aliases)) != len(aliases) or set(ids).intersection(aliases):
            raise ValueError("coordinate-space aliases must be globally unique")
        known = set(ids)
        for index, step in enumerate(self.steps):
            if step.from_space not in known or step.to_space not in known:
                raise ValueError("every transform step must reference declared coordinate spaces")
            if index and self.steps[index - 1].to_space != step.from_space:
                raise ValueError("transform steps must form one ordered, contiguous chain")
        return self

    def apply_point(
        self, x: float, y: float, *, from_space: str, to_space: str
    ) -> tuple[float, float]:
        """Apply the complete declared path between two spaces."""
        resolved = {
            name: space.space_id
            for space in self.spaces
            for name in (space.space_id, *space.aliases)
        }
        try:
            from_space = resolved[from_space]
            to_space = resolved[to_space]
        except KeyError as exc:
            raise ValueError(f"unknown coordinate space: {exc.args[0]}") from exc
        if from_space == to_space:
            return x, y
        current = from_space
        result = (x, y)
        for step in self.steps:
            if step.from_space != current:
                continue
            result = step.apply_point(*result)
            current = step.to_space
            if current == to_space:
                return result
        raise ValueError(f"no contiguous transform path from {from_space} to {to_space}")


class PointMeasurement(_SpatialModel):
    kind: Literal["point"] = "point"
    coordinate_space: str
    x: float
    y: float
    measurement_role: str | None = None

    @field_validator("coordinate_space", "measurement_role")
    @classmethod
    def _valid_names(cls, value: str | None) -> str | None:
        if value is not None and not _OPEN_NAME_RE.fullmatch(value):
            raise ValueError("measurement names must be portable token text")
        return value

    @field_validator("x", "y")
    @classmethod
    def _finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("point coordinates must be finite")
        return value


class BBoxMeasurement(_SpatialModel):
    kind: Literal["bbox"] = "bbox"
    coordinate_space: str
    bbox: BBoxXYWHNorm
    measurement_role: str | None = None

    @field_validator("coordinate_space", "measurement_role")
    @classmethod
    def _valid_names(cls, value: str | None) -> str | None:
        if value is not None and not _OPEN_NAME_RE.fullmatch(value):
            raise ValueError("measurement names must be portable token text")
        return value


class MaskReference(_SpatialModel):
    kind: Literal["mask"] = "mask"
    coordinate_space: str
    uri: str
    sha256: str
    media_type: str
    measurement_role: str | None = None

    @field_validator("coordinate_space", "measurement_role")
    @classmethod
    def _valid_names(cls, value: str | None) -> str | None:
        if value is not None and not _OPEN_NAME_RE.fullmatch(value):
            raise ValueError("measurement names must be portable token text")
        return value

    @field_validator("sha256")
    @classmethod
    def _sha256(cls, value: str) -> str:
        if not _SHA256_RE.fullmatch(value):
            raise ValueError("sha256 must be a lowercase hexadecimal SHA-256 digest")
        return value

    @field_validator("uri", "media_type")
    @classmethod
    def _non_empty_reference_text(cls, value: str) -> str:
        if not value:
            raise ValueError("mask URI and media type must be non-empty")
        return value


SpatialMeasurement = Annotated[
    PointMeasurement | BBoxMeasurement | MaskReference,
    Field(discriminator="kind"),
]


class SourceObservationLocator(_SpatialModel):
    """Source-authored identity; time is carried, never derived from FPS."""

    clip_id: str
    event_id: str
    point_index: int = Field(ge=0)
    frame_index: int = Field(ge=0)
    time_sec: float = Field(ge=0.0)

    @field_validator("clip_id", "event_id")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("source locator ids must be non-empty")
        return value

    @field_validator("time_sec")
    @classmethod
    def _finite_time(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("source time must be finite")
        return value


class TimeBase(_SpatialModel):
    numerator: int = Field(gt=0)
    denominator: int = Field(gt=0)


class EvidenceFrameReference(_SpatialModel):
    """Exact decoded evidence-frame identity."""

    media_sha256: str
    decoded_frame_index: int = Field(ge=0)
    pts: int
    pts_time_base: TimeBase
    pts_table_sha256: str

    @field_validator("media_sha256", "pts_table_sha256")
    @classmethod
    def _sha256(cls, value: str) -> str:
        if not _SHA256_RE.fullmatch(value):
            raise ValueError("hash fields must be lowercase hexadecimal SHA-256 digests")
        return value

    @property
    def pts_seconds(self) -> float:
        return self.pts * self.pts_time_base.numerator / self.pts_time_base.denominator


class TaskResolvability(_SpatialModel):
    localization: ResolutionStatus
    segmentation: ResolutionStatus


class ObservationProvenance(_SpatialModel):
    """Orthogonal producer and derivation axes with auditable method identity."""

    producer: str
    derivation: str
    method: str | None = None
    version: str | None = None
    source_hashes: dict[str, str] = Field(default_factory=dict)

    @field_validator("producer", "derivation", "method", "version")
    @classmethod
    def _valid_open_names(cls, value: str | None) -> str | None:
        if value is not None and not _OPEN_NAME_RE.fullmatch(value):
            raise ValueError("provenance values must be portable token text")
        return value

    @field_validator("source_hashes")
    @classmethod
    def _valid_hashes(cls, values: dict[str, str]) -> dict[str, str]:
        for key, value in values.items():
            if not _OPEN_NAME_RE.fullmatch(key) or not _SHA256_RE.fullmatch(value):
                raise ValueError("source hashes require portable keys and SHA-256 values")
        return values


class SpatialObservation(_SpatialModel):
    """One portable observation with optional spatial evidence."""

    observation_id: str
    subject_id: str
    parent_observation_ids: tuple[str, ...] = ()
    presence: Presence
    visibility: Visibility
    resolvability: TaskResolvability
    measurement: SpatialMeasurement | None = None
    source_locator: SourceObservationLocator | None = None
    evidence_frame: EvidenceFrameReference | None = None
    transforms: TransformChain
    provenance: ObservationProvenance

    @field_validator("observation_id", "subject_id")
    @classmethod
    def _non_empty_id(cls, value: str) -> str:
        if not value:
            raise ValueError("observation and subject ids must be non-empty")
        return value

    @field_validator("parent_observation_ids")
    @classmethod
    def _non_empty_parent_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not value for value in values):
            raise ValueError("parent observation ids must be non-empty")
        return values

    @model_validator(mode="after")
    def _coherent_observation(self) -> "SpatialObservation":
        if len(set(self.parent_observation_ids)) != len(self.parent_observation_ids):
            raise ValueError("parent observation ids must be unique")
        if self.observation_id in self.parent_observation_ids:
            raise ValueError("an observation cannot parent itself")
        known_spaces = {
            name: space
            for space in self.transforms.spaces
            for name in (space.space_id, *space.aliases)
        }
        if self.measurement is not None:
            if self.presence is Presence.ABSENT:
                raise ValueError("an absent observation cannot carry a spatial measurement")
            space = known_spaces.get(self.measurement.coordinate_space)
            if space is None:
                raise ValueError("a spatial measurement requires declared coordinate-space context")
            if isinstance(self.measurement, BBoxMeasurement):
                if space.unit is not CoordinateUnit.NORMALIZED:
                    raise ValueError("BBoxMeasurement requires a normalized coordinate space")
                if space.origin is not CoordinateOrigin.TOP_LEFT:
                    raise ValueError("BBoxMeasurement requires top-left origin")
            if (
                isinstance(self.measurement, PointMeasurement)
                and space.bounds_policy is BoundsPolicy.REJECT
            ):
                if not (
                    space.extent.x_min <= self.measurement.x <= space.extent.x_max
                    and space.extent.y_min <= self.measurement.y <= space.extent.y_max
                ):
                    raise ValueError("point measurement lies outside its coordinate-space extent")
        return self
