"""Guard the public API against shipping a Pydantic model with no JSON Schema.

Coverage is resolved by *class identity*, never by bare class name. A model is
covered when it is exported by ``typus.export_schemas.MODELS`` directly, or when
it is transitively reachable from a ``MODELS`` entry's fields (Pydantic emits
those into the container schema's ``$defs``, and ``make schemas-check``
regenerates them, so they stay fresh).

Name-based matching would let a new, schema-less public model pass simply by
sharing a bare name with an existing schema stem, ``$defs`` key, or ``MODELS``
tail -- including names that are not even Pydantic models (enums such as
``RankLevel`` or ``BBoxFormat`` appear as ``$defs`` keys). Note that a base
class is *not* covered by its subclasses: Pydantic inlines the concrete
discriminated-union variants and never references the base, which is exactly why
``BaseCandidate`` needs its own entry.
"""

from __future__ import annotations

import inspect
from importlib import import_module
from pathlib import Path
from typing import get_args

from pydantic import BaseModel

import typus
from typus.export_schemas import MODELS


def _resolve(dotted_path: str) -> type[BaseModel]:
    module_name, class_name = dotted_path.rsplit(".", 1)
    resolved = getattr(import_module(module_name), class_name)
    assert isinstance(resolved, type) and issubclass(
        resolved, BaseModel
    ), f"{dotted_path} in export_schemas.MODELS is not a pydantic BaseModel"
    return resolved


def _model_types(annotation: object) -> set[type[BaseModel]]:
    """Every ``BaseModel`` subclass appearing anywhere inside a type annotation.

    Recurses through ``Optional``/``Union``, ``list``/``dict`` parameters and
    ``Annotated`` metadata, which is how discriminated unions are declared here.
    """
    # Check parameters first: on Python 3.10 ``isinstance(list[X], type)`` is
    # True, so testing for a class up front would swallow every container.
    args = get_args(annotation)
    if args:
        found: set[type[BaseModel]] = set()
        for arg in args:
            found |= _model_types(arg)
        return found
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return {annotation}
    return set()


def _covered_models() -> set[type[BaseModel]]:
    """``MODELS`` classes plus every model transitively reachable from them."""
    covered: set[type[BaseModel]] = set()
    pending = [_resolve(dotted_path) for dotted_path in MODELS]

    while pending:
        model = pending.pop()
        if model in covered:
            continue
        covered.add(model)
        for field in model.model_fields.values():
            pending.extend(_model_types(field.annotation) - covered)

    return covered


def _public_models() -> dict[str, type[BaseModel]]:
    return {
        name: value
        for name in typus.__all__
        if inspect.isclass(value := getattr(typus, name)) and issubclass(value, BaseModel)
    }


def test_public_pydantic_models_have_exported_schemas() -> None:
    covered = _covered_models()

    missing = sorted(
        f"{model.__module__}.{model.__name__}"
        for model in _public_models().values()
        if model not in covered
    )

    assert not missing, (
        "Public Pydantic models missing schema coverage: "
        f"{missing}. Add each to typus/export_schemas.py MODELS and run `make schemas`."
    )


def test_committed_schemas_match_the_export_list() -> None:
    """``typus/schemas/`` holds exactly one file per ``MODELS`` entry.

    ``make schemas-check`` runs ``git diff --exit-code typus/schemas``, which is
    blind to files that were never committed and to orphans left behind when a
    model leaves ``MODELS``. An orphan would otherwise keep satisfying coverage
    forever with no freshness gate.
    """
    schema_root = Path(typus.__file__).resolve().parent / "schemas"
    committed = {path.stem for path in schema_root.glob("*.json")}
    expected = {dotted_path.rsplit(".", 1)[-1] for dotted_path in MODELS}

    assert committed == expected, (
        f"typus/schemas is out of sync with export_schemas.MODELS. "
        f"Missing files: {sorted(expected - committed)}; "
        f"orphaned files: {sorted(committed - expected)}. Run `make schemas`."
    )
