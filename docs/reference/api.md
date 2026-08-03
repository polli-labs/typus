# API Reference (auto)

::: typus.models.geometry
    options:
      members:
        - BBoxXYWHNorm
        - to_xyxy_px
        - from_xyxy_px

::: typus.models.spatial
    options:
      members:
        - CoordinateSpace
        - TransformStep
        - TransformChain
        - PointMeasurement
        - BBoxMeasurement
        - MaskReference
        - SourceObservationLocator
        - EvidenceFrameReference
        - ObservationProvenance
        - SpatialObservation

::: typus.ops.bbox
    options:
      members:
        - iou_xyxy
        - area_xyxy
        - intersect_xyxy
        - union_xyxy
        - clamp_xyxy
        - to_xywh_px
        - from_xywh_px
        - xyxy_to_xywh
        - xywh_to_xyxy
