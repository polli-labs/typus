"""Utility to export JSON Schemas for all Pydantic models."""

from importlib import import_module
from pathlib import Path

MODELS = [
    "typus.models.taxon.Taxon",
    "typus.models.lineage.LineageMap",
    "typus.models.clade.Clade",
    "typus.models.classification.HierarchicalClassificationResult",
]


def main() -> None:
    root = Path(__file__).resolve().parent / "schemas"
    root.mkdir(exist_ok=True)
    for dotted in MODELS:
        mod_name, cls_name = dotted.rsplit(".", 1)
        cls = getattr(import_module(mod_name), cls_name)
        schema = cls.model_json_schema(indent=2)
        (root / f"{cls_name}.json").write_text(schema + "\n")
        print(f"wrote {cls_name}.json")


if __name__ == "__main__":
    main()
