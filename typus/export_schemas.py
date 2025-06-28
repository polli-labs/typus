"""Utility to export JSON Schemas for all Pydantic models."""

import json
from importlib import import_module
from pathlib import Path

MODELS = [
    "typus.models.taxon.Taxon",
    "typus.models.lineage.LineageMap",
    "typus.models.clade.Clade",
    "typus.models.classification.HierarchicalClassificationResult",
    "typus.models.geometry.BBox",
    "typus.models.geometry.EncodedMask",
    "typus.models.detection.InstancePrediction",
    "typus.models.detection.ImageDetectionResult",
]


def main() -> None:
    root = Path(__file__).resolve().parent / "schemas"
    root.mkdir(exist_ok=True)
    for dotted in MODELS:
        mod_name, cls_name = dotted.rsplit(".", 1)
        cls = getattr(import_module(mod_name), cls_name)
        schema = cls.model_json_schema()
        schema_json = json.dumps(schema, indent=2)
        (root / f"{cls_name}.json").write_text(schema_json + "\n")
        print(f"wrote {cls_name}.json")


if __name__ == "__main__":
    main()
