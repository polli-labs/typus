"""Tests for BBoxXYWHNorm canonical geometry type."""

import pytest

from typus.models.geometry import BBoxXYWHNorm


class TestBBoxXYWHNormValidation:
    """Test validation of canonical bbox constraints."""

    def test_valid_bbox_creation(self):
        """Test creating valid bboxes."""
        # Normal case
        bbox = BBoxXYWHNorm(x=0.1, y=0.2, w=0.5, h=0.6)
        assert bbox.x == 0.1
        assert bbox.y == 0.2
        assert bbox.w == 0.5
        assert bbox.h == 0.6

    def test_boundary_cases(self):
        """Test boundary value handling."""
        # Minimum valid bbox
        bbox1 = BBoxXYWHNorm(x=0.0, y=0.0, w=0.001, h=0.001)
        assert bbox1.x == 0.0
        assert bbox1.y == 0.0

        # Maximum valid bbox (full image)
        bbox2 = BBoxXYWHNorm(x=0.0, y=0.0, w=1.0, h=1.0)
        assert bbox2.w == 1.0
        assert bbox2.h == 1.0

        # Edge case: x + w = 1 (should be allowed)
        bbox3 = BBoxXYWHNorm(x=0.5, y=0.0, w=0.5, h=0.5)
        assert bbox3.x + bbox3.w == 1.0

    def test_frozen_immutability(self):
        """Test that bbox is immutable after creation."""
        bbox = BBoxXYWHNorm(x=0.1, y=0.2, w=0.5, h=0.6)
        
        with pytest.raises(TypeError):
            bbox.x = 0.5  # Should raise error due to frozen=True

    def test_coordinate_range_validation(self):
        """Test coordinate range constraints."""
        # x, y must be >= 0 and <= 1
        with pytest.raises(ValueError):
            BBoxXYWHNorm(x=-0.1, y=0.2, w=0.5, h=0.6)
        
        with pytest.raises(ValueError):
            BBoxXYWHNorm(x=1.1, y=0.2, w=0.5, h=0.6)
        
        with pytest.raises(ValueError):
            BBoxXYWHNorm(x=0.1, y=-0.1, w=0.5, h=0.6)
        
        with pytest.raises(ValueError):
            BBoxXYWHNorm(x=0.1, y=1.1, w=0.5, h=0.6)

    def test_size_validation(self):
        """Test width and height constraints."""
        # w, h must be > 0 and <= 1
        with pytest.raises(ValueError):
            BBoxXYWHNorm(x=0.1, y=0.2, w=0.0, h=0.6)
        
        with pytest.raises(ValueError):
            BBoxXYWHNorm(x=0.1, y=0.2, w=-0.1, h=0.6)
        
        with pytest.raises(ValueError):
            BBoxXYWHNorm(x=0.1, y=0.2, w=1.1, h=0.6)
        
        with pytest.raises(ValueError):
            BBoxXYWHNorm(x=0.1, y=0.2, w=0.5, h=0.0)

    def test_non_finite_rejection(self):
        """Test rejection of non-finite coordinates with precise error messages."""
        # NaN values with field-specific messages
        with pytest.raises(ValueError, match="non-finite coordinate"):
            BBoxXYWHNorm(x=float('nan'), y=0.2, w=0.5, h=0.6)
        
        with pytest.raises(ValueError, match="non-finite coordinate"):
            BBoxXYWHNorm(x=0.1, y=float('nan'), w=0.5, h=0.6)
        
        with pytest.raises(ValueError, match="non-finite coordinate"):
            BBoxXYWHNorm(x=0.1, y=0.2, w=float('nan'), h=0.6)
        
        with pytest.raises(ValueError, match="non-finite coordinate"):
            BBoxXYWHNorm(x=0.1, y=0.2, w=0.5, h=float('nan'))
        
        # Infinite values
        with pytest.raises(ValueError, match="non-finite coordinate"):
            BBoxXYWHNorm(x=float('inf'), y=0.2, w=0.5, h=0.6)
        
        with pytest.raises(ValueError, match="non-finite coordinate"):
            BBoxXYWHNorm(x=0.1, y=0.2, w=float('-inf'), h=0.6)
    
    def test_bounds_exceeded_errors(self):
        """Test specific error messages for bounds violations."""
        # x + w > 1 + EPS
        with pytest.raises(ValueError, match="x \\+ w exceeds 1"):
            BBoxXYWHNorm(x=0.6, y=0.2, w=0.5, h=0.3)  # 0.6 + 0.5 = 1.1 > 1
        
        # y + h > 1 + EPS  
        with pytest.raises(ValueError, match="y \\+ h exceeds 1"):
            BBoxXYWHNorm(x=0.1, y=0.7, w=0.3, h=0.4)  # 0.7 + 0.4 = 1.1 > 1
        
        # Negative width
        with pytest.raises(ValueError, match="greater than 0"):
            BBoxXYWHNorm(x=0.1, y=0.2, w=-0.1, h=0.3)
        
        # Zero height  
        with pytest.raises(ValueError, match="greater than 0"):
            BBoxXYWHNorm(x=0.1, y=0.2, w=0.3, h=0.0)

    def test_edge_case_epsilon_tolerance(self):
        """Test handling of values very close to boundaries."""
        # Values very close to 1.0 + epsilon should work
        eps = 1e-9
        bbox = BBoxXYWHNorm(x=0.5, y=0.5, w=0.5, h=0.5)
        
        # This should pass as x + w ≈ 1.0 within epsilon
        bbox2 = BBoxXYWHNorm(x=0.5, y=0.5, w=0.5 - eps, h=0.5 - eps)
        assert abs((bbox2.x + bbox2.w) - 1.0) < eps

    def test_json_serialization(self):
        """Test JSON serialization and deserialization."""
        bbox = BBoxXYWHNorm(x=0.1, y=0.2, w=0.5, h=0.6)
        
        # Serialize to dict
        bbox_dict = bbox.model_dump()
        expected = {"x": 0.1, "y": 0.2, "w": 0.5, "h": 0.6}
        assert bbox_dict == expected
        
        # Deserialize from dict
        bbox_restored = BBoxXYWHNorm.model_validate(bbox_dict)
        assert bbox_restored == bbox

    def test_description_fields(self):
        """Test that field descriptions are present in schema."""
        schema = BBoxXYWHNorm.model_json_schema()
        
        assert "Left coordinate" in schema["properties"]["x"]["description"]
        assert "Top coordinate" in schema["properties"]["y"]["description"]
        assert "Width" in schema["properties"]["w"]["description"]
        assert "Height" in schema["properties"]["h"]["description"]