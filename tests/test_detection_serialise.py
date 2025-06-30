import json

import pytest

from typus.constants import RankLevel
from typus.models.classification import (
    HierarchicalClassificationResult,
    TaskPrediction,
    TaxonomyContext,
)
from typus.models.detection import ImageDetectionResult, InstancePrediction
from typus.models.detection_utils import from_coco, to_coco
from typus.models.geometry import BBox, BBoxFormat, EncodedMask, MaskEncoding

# Sample Data
SAMPLE_BBOX_XYXY_REL = BBox(coords=(0.1, 0.1, 0.5, 0.5), fmt=BBoxFormat.XYXY_REL)
SAMPLE_BBOX_XYXY_ABS = BBox(coords=(10, 10, 50, 50), fmt=BBoxFormat.XYXY_ABS)
SAMPLE_BBOX_CXCYWH_REL = BBox(
    coords=(0.3, 0.3, 0.4, 0.4), fmt=BBoxFormat.CXCYWH_REL
)  # (0.1,0.1,0.5,0.5) in xyxy

SAMPLE_MASK_POLYGON = EncodedMask(
    data=[
        [10.0, 10.0],
        [50.0, 10.0],
        [50.0, 50.0],
        [10.0, 50.0],
    ],  # List[List[float]] -> List of [x,y] points
    encoding=MaskEncoding.POLYGON,
    bbox_hint=SAMPLE_BBOX_XYXY_ABS,
)
SAMPLE_MASK_RLE = EncodedMask(
    data="someRLEdataString",  # Placeholder RLE string data
    encoding=MaskEncoding.RLE_COCO,
    bbox_hint=SAMPLE_BBOX_XYXY_ABS,
)

# Create a sample task prediction with taxon predictions

SAMPLE_TASK_PREDICTION = TaskPrediction(
    rank_level=RankLevel.L10,  # species
    temperature=1.0,
    predictions=[(123, 0.9), (124, 0.1)],
)

SAMPLE_TAXONOMY_CONTEXT = TaxonomyContext(source="CoL2024", version="v1.0")
SAMPLE_HIERARCHICAL_CLASSIFICATION = HierarchicalClassificationResult(
    taxonomy_context=SAMPLE_TAXONOMY_CONTEXT, tasks=[SAMPLE_TASK_PREDICTION]
)

SAMPLE_INSTANCE_PREDICTION_FULL = InstancePrediction(
    instance_id=1,
    bbox=SAMPLE_BBOX_XYXY_REL,
    mask=SAMPLE_MASK_POLYGON,
    score=0.95,
    taxon_id=123,
    classification=SAMPLE_HIERARCHICAL_CLASSIFICATION,
)

SAMPLE_INSTANCE_PREDICTION_NO_MASK_NO_CLASS = InstancePrediction(
    instance_id=2, bbox=SAMPLE_BBOX_CXCYWH_REL, score=0.88
)

SAMPLE_TAXONOMY_CONTEXT = TaxonomyContext(
    taxonomy_id="test_taxonomy_v1", lca_graph_id="test_lca_graph_v1"
)

SAMPLE_IMAGE_DETECTION_RESULT = ImageDetectionResult(
    width=1000,
    height=800,
    instances=[SAMPLE_INSTANCE_PREDICTION_FULL, SAMPLE_INSTANCE_PREDICTION_NO_MASK_NO_CLASS],
    taxonomy_context=SAMPLE_TAXONOMY_CONTEXT,
)

# --- Test Cases ---


def test_bbox_serialisation():
    bbox = SAMPLE_BBOX_XYXY_REL
    json_data = bbox.to_json()
    data = json.loads(json_data)
    assert data["coords"] == [0.1, 0.1, 0.5, 0.5]
    assert data["fmt"] == "xyxyRel"

    new_bbox = BBox.model_validate_json(json_data)
    assert new_bbox == bbox


def test_encoded_mask_serialisation_polygon():
    mask = SAMPLE_MASK_POLYGON
    json_data = mask.to_json()
    data = json.loads(json_data)
    assert data["data"] == [[10.0, 10.0], [50.0, 10.0], [50.0, 50.0], [10.0, 50.0]]
    assert data["encoding"] == "polygon"
    assert data["bboxHint"]["coords"] == [10, 10, 50, 50]

    new_mask = EncodedMask.model_validate_json(json_data)
    assert new_mask == mask


def test_encoded_mask_serialisation_rle():
    mask = SAMPLE_MASK_RLE
    json_data = mask.to_json()
    data = json.loads(json_data)
    assert data["data"] == "someRLEdataString"
    assert data["encoding"] == "rleCoco"

    new_mask = EncodedMask.model_validate_json(json_data)
    assert new_mask == mask


def test_instance_prediction_serialisation():
    instance = SAMPLE_INSTANCE_PREDICTION_FULL
    json_data = instance.to_json()
    # Not loading and checking every field, Pydantic handles this.
    # Main check is if it serializes and deserializes back.
    new_instance = InstancePrediction.model_validate_json(json_data)
    assert new_instance == instance


def test_image_detection_result_serialisation():
    result = SAMPLE_IMAGE_DETECTION_RESULT
    json_data = result.to_json()
    # Main check is if it serializes and deserializes back.
    new_result = ImageDetectionResult.model_validate_json(json_data)
    assert new_result == result
    assert new_result.width == 1000
    assert len(new_result.instances) == 2
    assert new_result.instances[0].bbox.fmt == BBoxFormat.XYXY_REL


# --- COCO Utils Tests ---

CATEGORY_MAP = {123: 1, 456: 2}  # typus_taxon_id -> coco_category_id


def test_to_coco_basic():
    image_res = ImageDetectionResult(
        width=100,
        height=100,
        instances=[
            InstancePrediction(
                instance_id=1,
                bbox=BBox(coords=(0.1, 0.1, 0.5, 0.5), fmt=BBoxFormat.XYXY_REL),
                score=0.9,
                taxon_id=123,
            ),
            InstancePrediction(
                instance_id=2,
                bbox=BBox(coords=(10, 10, 30, 30), fmt=BBoxFormat.XYXY_ABS),
                score=0.8,
                taxon_id=456,
            ),
            InstancePrediction(
                instance_id=3,
                bbox=BBox(coords=(0.6, 0.6, 0.2, 0.2), fmt=BBoxFormat.CXCYWH_REL),
                score=0.7,
                taxon_id=123,
            ),
            InstancePrediction(
                instance_id=4,
                bbox=BBox(coords=(70, 70, 20, 20), fmt=BBoxFormat.CXCYWH_ABS),
                score=0.6,
                taxon_id=12345,
            ),  # This taxon_id is not in CATEGORY_MAP
        ],
    )
    coco_dict = to_coco(image_res, CATEGORY_MAP)

    assert "annotations" in coco_dict
    assert (
        len(coco_dict["annotations"]) == 3
    )  # One instance is filtered due to missing category_map entry

    ann1 = coco_dict["annotations"][0]
    assert ann1["category_id"] == 1  # Mapped from taxon_id 123
    assert ann1["id"] == 1
    assert pytest.approx(ann1["bbox"]) == [
        10.0,
        10.0,
        40.0,
        40.0,
    ]  # 0.1*100, 0.1*100, (0.5-0.1)*100, (0.5-0.1)*100

    ann2 = coco_dict["annotations"][1]
    assert ann2["category_id"] == 2  # Mapped from taxon_id 456
    assert ann2["id"] == 2
    assert pytest.approx(ann2["bbox"]) == [
        10.0,
        10.0,
        20.0,
        20.0,
    ]  # Absolute XYXY(10,10,30,30) -> COCO[x,y,w,h]

    ann3 = coco_dict["annotations"][2]
    assert ann3["category_id"] == 1  # Mapped from taxon_id 123
    assert ann3["id"] == 3
    # cxcywh_rel: cx=0.6, cy=0.6, w=0.2, h=0.2 -> x1=0.5, y1=0.5, x2=0.7, y2=0.7
    # abs_w = 0.2*100 = 20, abs_h = 0.2*100 = 20
    # abs_x = (0.6*100) - (20/2) = 60-10 = 50
    # abs_y = (0.6*100) - (20/2) = 60-10 = 50
    assert pytest.approx(ann3["bbox"]) == [50.0, 50.0, 20.0, 20.0]


def test_to_coco_with_polygon_mask():
    # Polygon data: List[List[float]] -> list of [x,y] points
    # COCO polygon: [x1,y1,x2,y2,...]
    # Our utils.py flattens this: [coord for poly in polygons for point in poly for coord in point]
    # If data = [[10,10],[20,10],[15,20]], it becomes [10,10,20,10,15,20]
    polygon_data = [[10.0, 10.0], [50.0, 10.0], [50.0, 50.0], [10.0, 50.0]]
    mask = EncodedMask(data=polygon_data, encoding=MaskEncoding.POLYGON)
    instance = InstancePrediction(
        instance_id=1, bbox=SAMPLE_BBOX_XYXY_ABS, mask=mask, score=0.9, taxon_id=123
    )
    image_res = ImageDetectionResult(width=100, height=100, instances=[instance])

    coco_dict = to_coco(image_res, CATEGORY_MAP)
    assert len(coco_dict["annotations"]) == 1
    ann = coco_dict["annotations"][0]
    assert "segmentation" in ann
    # Expected: flatten List[List[float]] points
    expected_segmentation = [10.0, 10.0, 50.0, 10.0, 50.0, 50.0, 10.0, 50.0]
    assert ann["segmentation"] == expected_segmentation


def test_to_coco_with_rle_mask():
    # RLE data is string, assumed to be coco `counts` string.
    # utils.py creates segmentation: {"counts": instance.mask.data, "size": [image.height, image.width]}
    rle_data = "someRLEStringCounts"
    mask = EncodedMask(data=rle_data, encoding=MaskEncoding.RLE_COCO)
    instance = InstancePrediction(
        instance_id=1, bbox=SAMPLE_BBOX_XYXY_ABS, mask=mask, score=0.9, taxon_id=123
    )
    image_res = ImageDetectionResult(width=100, height=100, instances=[instance])

    coco_dict = to_coco(image_res, CATEGORY_MAP)
    assert len(coco_dict["annotations"]) == 1
    ann = coco_dict["annotations"][0]
    assert "segmentation" in ann
    assert ann["segmentation"] == {"counts": rle_data, "size": [100, 100]}


def test_from_coco_basic():
    coco_data = {
        "images": [{"id": 1, "width": 100, "height": 100}],
        "annotations": [
            {
                "image_id": 1,
                "id": 101,
                "category_id": 1,
                "bbox": [10, 10, 40, 40],
                "score": 0.9,
            },  # xywh_abs -> xyxy_rel: 0.1,0.1,0.5,0.5
            {
                "image_id": 1,
                "id": 102,
                "category_id": 2,
                "bbox": [50, 50, 20, 20],
                "score": 0.8,
            },  # xywh_abs -> xyxy_rel: 0.5,0.5,0.7,0.7
        ],
        "categories": [  # Not used by from_coco directly for taxon_id mapping currently
            {"id": 1, "name": "catA"},
            {"id": 2, "name": "catB"},
        ],
    }
    results = from_coco(coco_data)
    assert len(results) == 1
    img_res = results[0]
    assert img_res.width == 100
    assert img_res.height == 100
    assert len(img_res.instances) == 2

    inst1 = img_res.instances[0]
    assert inst1.instance_id == 101
    assert inst1.score == 0.9
    assert inst1.bbox.fmt == BBoxFormat.XYXY_REL
    assert pytest.approx(inst1.bbox.coords) == (
        0.1,
        0.1,
        0.5,
        0.5,
    )  # (10/100, 10/100, (10+40)/100, (10+40)/100)
    assert inst1.mask is None
    assert inst1.taxon_id is None  # No reverse mapping implemented

    inst2 = img_res.instances[1]
    assert inst2.instance_id == 102
    assert pytest.approx(inst2.bbox.coords) == (
        0.5,
        0.5,
        0.7,
        0.7,
    )  # (50/100, 50/100, (50+20)/100, (50+20)/100)


def test_from_coco_with_polygon_mask():
    # COCO polygon: [x1,y1,x2,y2,...] or [[x1,y1,x2,y2,...], ...]
    # typus polygon data for EncodedMask: List[List[float]] (list of [x,y] points)
    # utils.py from_coco for polygon: if flat list [x,y,x,y..] -> [[x,y],[x,y]...]
    coco_segmentation_flat = [10.0, 10.0, 50.0, 10.0, 50.0, 50.0, 10.0, 50.0]  # Single polygon
    expected_typus_polygon_data = [[10.0, 10.0], [50.0, 10.0], [50.0, 50.0], [10.0, 50.0]]

    coco_data = {
        "images": [{"id": 1, "width": 100, "height": 100}],
        "annotations": [
            {
                "image_id": 1,
                "id": 101,
                "category_id": 1,
                "bbox": [10, 10, 40, 40],
                "score": 0.9,
                "segmentation": coco_segmentation_flat,
            }
        ],
    }
    results = from_coco(coco_data)
    assert len(results) == 1
    img_res = results[0]
    assert len(img_res.instances) == 1
    inst = img_res.instances[0]
    assert inst.mask is not None
    assert inst.mask.encoding == MaskEncoding.POLYGON
    assert inst.mask.data == expected_typus_polygon_data


def test_from_coco_with_rle_mask():
    # COCO RLE: {"counts": "rleString", "size": [h,w]}
    # typus RLE data for EncodedMask: "rleString" (the counts part)
    coco_rle_segmentation = {"counts": "someRLEStringCounts", "size": [100, 100]}

    coco_data = {
        "images": [{"id": 1, "width": 100, "height": 100}],
        "annotations": [
            {
                "image_id": 1,
                "id": 101,
                "category_id": 1,
                "bbox": [10, 10, 40, 40],
                "score": 0.9,
                "segmentation": coco_rle_segmentation,
            }
        ],
    }
    results = from_coco(coco_data)
    assert len(results) == 1
    img_res = results[0]
    assert len(img_res.instances) == 1
    inst = img_res.instances[0]
    assert inst.mask is not None
    assert inst.mask.encoding == MaskEncoding.RLE_COCO
    assert inst.mask.data == "someRLEStringCounts"
    assert inst.mask.bbox_hint is not None  # bbox_hint is added by from_coco
    assert inst.mask.bbox_hint.fmt == BBoxFormat.XYXY_REL
    assert pytest.approx(inst.mask.bbox_hint.coords) == (0.1, 0.1, 0.5, 0.5)


def test_from_coco_multiple_images():
    coco_data = {
        "images": [{"id": 1, "width": 100, "height": 100}, {"id": 2, "width": 200, "height": 200}],
        "annotations": [
            {"image_id": 1, "id": 101, "category_id": 1, "bbox": [10, 10, 40, 40], "score": 0.9},
            {"image_id": 2, "id": 201, "category_id": 1, "bbox": [20, 20, 80, 80], "score": 0.85},
        ],
    }
    results = from_coco(coco_data)
    assert len(results) == 2

    res1 = next(r for r in results if r.width == 100)
    res2 = next(r for r in results if r.width == 200)

    assert len(res1.instances) == 1
    assert res1.instances[0].instance_id == 101
    assert pytest.approx(res1.instances[0].bbox.coords) == (0.1, 0.1, 0.5, 0.5)

    assert len(res2.instances) == 1
    assert res2.instances[0].instance_id == 201
    assert pytest.approx(res2.instances[0].bbox.coords) == (
        0.1,
        0.1,
        0.5,
        0.5,
    )  # 20/200=0.1, (20+80)/200=0.5


def test_to_coco_empty_instances():
    image_res = ImageDetectionResult(width=100, height=100, instances=[])
    coco_dict = to_coco(image_res, CATEGORY_MAP)
    assert coco_dict["annotations"] == []


def test_from_coco_empty_annotations():
    coco_data = {"images": [{"id": 1, "width": 100, "height": 100}], "annotations": []}
    results = from_coco(coco_data)
    assert len(results) == 1
    assert results[0].instances == []


def test_from_coco_no_images_key():
    coco_data = {
        "annotations": [
            {"image_id": 1, "id": 101, "category_id": 1, "bbox": [10, 10, 40, 40], "score": 0.9}
        ]
    }
    results = from_coco(coco_data)
    assert results == []  # No image information to create ImageDetectionResult


def test_from_coco_no_annotations_key():
    coco_data = {"images": [{"id": 1, "width": 100, "height": 100}]}
    results = from_coco(coco_data)
    assert len(results) == 1
    assert results[0].instances == []


# Ensure pytest can find and run these tests.
# The necessary imports and sample data are included.
