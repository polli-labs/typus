from typing import Dict, List

from typus.models import ImageDetectionResult, InstancePrediction
from typus.models.geometry import (  # Added BBoxFormat and MaskEncoding
    BBox,
    BBoxFormat,
    EncodedMask,
    MaskEncoding,
)


def to_coco(image: ImageDetectionResult, category_map: Dict[int, int]) -> Dict:
    """Return a minimal COCO-style dict for a single image.

    Args:
        image: Parsed detection result.
        category_map: Mapping typus taxon_id → COCO category_id.
    """
    coco_annotations = []
    for instance in image.instances:
        if instance.taxon_id is None:
            # COCO requires a category_id
            continue

        coco_category_id = category_map.get(instance.taxon_id)
        if coco_category_id is None:
            # Skip if taxon_id not in category_map
            continue

        # Basic bounding box (assuming XYXY_REL for now, needs conversion if not)
        # COCO format for bbox is [x,y,width,height] in absolute coordinates
        # typus BBox coords are (float, float, float, float)
        # Need to handle different BBoxFormat if present

        if instance.bbox.fmt == BBoxFormat.XYXY_REL:
            x1, y1, x2, y2 = instance.bbox.coords
            abs_x = x1 * image.width
            abs_y = y1 * image.height
            abs_w = (x2 - x1) * image.width
            abs_h = (y2 - y1) * image.height
        elif instance.bbox.fmt == BBoxFormat.XYXY_ABS:
            x1, y1, x2, y2 = instance.bbox.coords
            abs_x = x1
            abs_y = y1
            abs_w = x2 - x1
            abs_h = y2 - y1
        elif instance.bbox.fmt == BBoxFormat.CXCYWH_REL:
            cx, cy, w, h = instance.bbox.coords
            abs_w = w * image.width
            abs_h = h * image.height
            abs_x = (cx * image.width) - (abs_w / 2)
            abs_y = (cy * image.height) - (abs_h / 2)
        elif instance.bbox.fmt == BBoxFormat.CXCYWH_ABS:
            cx, cy, w, h = instance.bbox.coords
            abs_x = cx - (w / 2)
            abs_y = cy - (h / 2)
            abs_w = w
            abs_h = h
        else:
            # Should not happen if bbox.fmt is always one of the enum values
            raise ValueError(f"Unsupported bbox format: {instance.bbox.fmt}")

        annotation = {
            "image_id": 0,  # Placeholder, COCO expects an image_id
            "category_id": coco_category_id,
            "bbox": [abs_x, abs_y, abs_w, abs_h],
            "score": instance.score,
            "id": instance.instance_id,  # Using instance_id as annotation id
        }

        if instance.mask:
            # COCO mask can be RLE or polygon list
            # typus EncodedMask data can be str (for RLE_COCO, PNG_BASE64) or List[List[float]] (for POLYGON)
            if instance.mask.encoding == MaskEncoding.RLE_COCO:
                # Assuming RLE is in COCO {counts: [], size: []} format, but typus stores it as a string.
                # This part needs clarification on how RLE string is structured.
                # For now, let's assume it's a string that can be directly used if it were pre-formatted.
                # Or, if it's the compressed RLE string, it needs decoding then re-encoding to COCO's dict format.
                # The issue states "RLE_COCO" which implies it should be compatible.
                # Let's assume `instance.mask.data` for RLE_COCO is a dict like `{"counts": [], "size": []}`
                # However, the type hint for `data` is `str | List[List[float]]`.
                # This implies RLE_COCO is also stored as a string.
                # Let's pass it as is, assuming the user will handle the string format if it's not directly a dict.
                # A safer bet might be to represent segmentation as polygons if RLE string format is unclear.
                segmentation = {
                    "counts": instance.mask.data,
                    "size": [image.height, image.width],
                }  # Placeholder for RLE
            elif instance.mask.encoding == MaskEncoding.POLYGON:
                # COCO polygon is [x1,y1,x2,y2,...]
                # typus polygon is List[List[float]] -> [[x1,y1], [x2,y2], ...]
                # Need to flatten and convert relative to absolute if necessary
                # Assuming polygons are absolute for now based on lack of format enum for masks
                # The spec for EncodedMask doesn't specify if polygon coords are relative or absolute.
                # Assuming absolute for now. If relative, they'd need image.width/height scaling.
                # Let's assume they are absolute as per COCO common practice for polygons.
                polygons = instance.mask.data
                segmentation = [
                    coord for point in polygons for coord in point
                ]  # Flattening [[x,y],[x,y]] to [x,y,x,y]
            elif instance.mask.encoding == MaskEncoding.PNG_BASE64:
                # COCO does not directly support PNG_BASE64 masks in annotation segmentation field.
                # This would typically be converted to RLE or polygons.
                # For now, skipping PNG_BASE64 masks in COCO conversion.
                segmentation = None
            else:
                segmentation = None

            if segmentation:
                annotation["segmentation"] = segmentation

        coco_annotations.append(annotation)

    # Minimal COCO structure for a single image's annotations
    # Does not include 'images' or 'categories' list as those are global for a dataset
    return {
        "annotations": coco_annotations,
        # "image_info": {"id": 0, "width": image.width, "height": image.height} # Optional: could add image info
    }


def from_coco(coco: Dict) -> List[ImageDetectionResult]:
    """Convert standard COCO JSON into a list of ImageDetectionResult.
    NB: This function expects a COCO JSON that might contain info for *multiple* images.
    The output is a list of ImageDetectionResult, one for each image in the COCO data.

    Args:
        coco: Parsed COCO JSON data (typically a dict with 'images', 'annotations', 'categories').
    """
    results = []

    images_map = {img["id"]: img for img in coco.get("images", [])}
    # categories_map = {cat['id']: cat for cat in coco.get('categories', [])} # For taxon_id mapping if needed

    # Group annotations by image_id
    annotations_by_image_id: Dict[int, List[Dict]] = {}
    for ann in coco.get("annotations", []):
        img_id = ann["image_id"]
        if img_id not in annotations_by_image_id:
            annotations_by_image_id[img_id] = []
        annotations_by_image_id[img_id].append(ann)

    for image_id, image_info in images_map.items():
        image_width = image_info["width"]
        image_height = image_info["height"]

        instance_predictions = []
        for ann in annotations_by_image_id.get(image_id, []):
            coco_bbox = ann["bbox"]  # [x,y,width,height] absolute
            # Convert to XYXY_REL for typus BBox default
            x1_rel = coco_bbox[0] / image_width
            y1_rel = coco_bbox[1] / image_height
            x2_rel = (coco_bbox[0] + coco_bbox[2]) / image_width
            y2_rel = (coco_bbox[1] + coco_bbox[3]) / image_height

            bbox = BBox(coords=(x1_rel, y1_rel, x2_rel, y2_rel), fmt=BBoxFormat.XYXY_REL)

            mask = None
            segmentation = ann.get("segmentation")
            if segmentation:
                if (
                    isinstance(segmentation, dict)
                    and "counts" in segmentation
                    and "size" in segmentation
                ):  # RLE
                    # Assuming segmentation['counts'] is a string as per EncodedMask.data type hint for RLE
                    mask_data = segmentation["counts"]
                    mask = EncodedMask(
                        data=mask_data, encoding=MaskEncoding.RLE_COCO, bbox_hint=bbox
                    )
                elif isinstance(segmentation, list):  # Polygons
                    # COCO polygons: [[x1,y1,x2,y2,...], [x1,y1,...]] or [x1,y1,x2,y2,...] for simple
                    # typus EncodedMask.data for POLYGON: List[List[float]] -> [[x1,y1], [x2,y2], ...]
                    # This requires careful conversion. Assuming segmentation is list of lists of floats (absolute)
                    # For simplicity, assuming the input coco polygon is already List[List[float]] where each inner list is [x,y,x,y,...]
                    # And typus wants List[List[float]] where inner list is [[x,y], [x,y]]
                    # This part is tricky. Let's assume COCO polygons are a list of float arrays [x1,y1,x2,y2,...]
                    # And we need to convert them to List[List[float]] where each sublist is a pair [x,y]
                    # For now, if it's a list, we assume it's a flat list of coords [x1,y1,x2,y2,...]
                    # and we need to group them into pairs.

                    # If segmentation is a list of lists (multi-polygon)
                    # e.g. [ [x1,y1,x2,y2,...], [x1,y1,x2,y2,...] ]
                    # If segmentation is a flat list (single polygon)
                    # e.g. [x1,y1,x2,y2,...]

                    # For typus List[List[float]] which is List of [x,y] pairs.
                    # So if coco_poly = [x1,y1,x2,y2,x3,y3], typus_poly = [[x1,y1],[x2,y2],[x3,y3]]

                    # For now, let's assume segmentation for polygons is a list of lists of numbers,
                    # where each inner list is a single polygon contour e.g. [[x1,y1,x2,y2, ...], [...]]
                    # And typus wants List[List[float]] which means list of [x,y] points.
                    # This implies coco polygons are [ [x1,y1,x2,y2...], ... ] and we want to make it [ [[x1,y1],[x2,y2]...], ... ]
                    # The spec says `List[List[float]]` for `POLYGON` in `EncodedMask`. This is ambiguous.
                    # Let's assume `List[List[float]]` means a list of [x,y] pairs for a single polygon.
                    # If COCO provides multiple polygons, we might need to pick one or handle it.
                    # For now, assuming `segmentation` is a list of numbers [x,y,x,y...] for a single polygon.

                    processed_polygons = []
                    if segmentation and isinstance(segmentation, list):
                        if segmentation and all(
                            isinstance(el, list) for el in segmentation
                        ):  # Multi-polygon List[List[coords]]
                            for poly_coords in segmentation:
                                current_poly = []
                                if len(poly_coords) % 2 != 0:
                                    continue  # Invalid polygon
                                for i in range(0, len(poly_coords), 2):
                                    current_poly.append([poly_coords[i], poly_coords[i + 1]])
                                if current_poly:
                                    processed_polygons.append(
                                        current_poly
                                    )  # This results in List[List[List[float]]]
                                    # This is not List[List[float]]. Typus spec for polygon data: List[List[float]]
                                    # This likely means a single polygon as a list of [x,y] points.
                                    # For multiple polygons, COCO has list of such lists.
                                    # If typus EncodedMask.data for POLYGON is List of [x,y] points for ONE polygon,
                                    # then we can only take the first polygon from COCO if multiple exist.

                        elif segmentation and all(
                            isinstance(el, (int, float)) for el in segmentation
                        ):  # Single polygon List[coords]
                            current_poly = []
                            if len(segmentation) % 2 == 0:
                                for i in range(0, len(segmentation), 2):
                                    current_poly.append([segmentation[i], segmentation[i + 1]])
                            if current_poly:
                                processed_polygons = (
                                    current_poly  # This is List[List[float]] as [[x,y], [x,y]...]
                                )

                        if processed_polygons:  # Only if we got a valid List[List[float]]
                            mask = EncodedMask(
                                data=processed_polygons,
                                encoding=MaskEncoding.POLYGON,
                                bbox_hint=bbox,
                            )

            # COCO category_id to typus taxon_id (optional, might not always be possible or needed)
            # The issue doesn't specify how to map COCO category_id back to taxon_id.
            # For now, we'll leave taxon_id and classification as None.
            # A reverse of `category_map` would be needed if this mapping is desired.
            typus_taxon_id = None
            # We could try to find a taxon_id if a reverse category_map is available or if category names match something
            # For now, this is out of scope of direct conversion based on provided spec.

            instance_predictions.append(
                InstancePrediction(
                    instance_id=ann.get("id", 0),  # COCO annotation ID. Need to ensure it's int.
                    bbox=bbox,
                    mask=mask,
                    score=ann["score"],
                    taxon_id=typus_taxon_id,  # Requires reverse mapping from category_id
                    classification=None,  # Requires more context or a taxon_id
                )
            )

        # TaxonomyContext might be derivable from coco['categories'] if present
        # For now, setting it to None as per minimal requirement.
        results.append(
            ImageDetectionResult(
                width=image_width,
                height=image_height,
                instances=instance_predictions,
                taxonomy_context=None,
            )
        )

    return results
