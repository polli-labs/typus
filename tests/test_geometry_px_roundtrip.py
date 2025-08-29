"""Tests for pixel ↔ normalized bbox conversion round-trips."""

import pytest

from typus.models.geometry import BBoxXYWHNorm, from_xyxy_px, to_xyxy_px


class TestPixelNormalizedRoundtrip:
    """Test round-trip conversions between pixel and normalized coordinates."""

    @pytest.mark.parametrize("W,H", [
        (100, 100),      # Square
        (1920, 1080),    # HD video
        (640, 480),      # VGA
        (3840, 2160),    # 4K
        (1, 1),          # Edge case
        (800, 600),      # 4:3 aspect ratio
    ])
    def test_roundtrip_accuracy(self, W: int, H: int):
        """Test that pixel -> norm -> pixel conversion is accurate within 0.5px."""
        # Test various bbox configurations
        test_cases = [
            # (x1, y1, x2, y2) in pixels
            (10, 20, 50, 60),           # Small bbox
            (0, 0, W//2, H//2),         # Top-left quadrant
            (W//2, H//2, W, H),         # Bottom-right quadrant  
            (0, 0, W, H),               # Full image
            (W//4, H//4, 3*W//4, 3*H//4), # Centered box
            (1, 1, 2, 2),               # Minimal size
        ]
        
        for x1_orig, y1_orig, x2_orig, y2_orig in test_cases:
            # Skip invalid cases
            if x2_orig <= x1_orig or y2_orig <= y1_orig:
                continue
            if x1_orig < 0 or y1_orig < 0 or x2_orig > W or y2_orig > H:
                continue
            
            # Convert pixels to normalized
            bbox_norm = from_xyxy_px(x1_orig, y1_orig, x2_orig, y2_orig, W, H)
            
            # Convert back to pixels
            x1_round, y1_round, x2_round, y2_round = to_xyxy_px(bbox_norm, W, H)
            
            # Check accuracy within 0.5 pixels
            assert abs(x1_round - x1_orig) <= 0.5, f"x1 error: {abs(x1_round - x1_orig)}"
            assert abs(y1_round - y1_orig) <= 0.5, f"y1 error: {abs(y1_round - y1_orig)}"
            assert abs(x2_round - x2_orig) <= 0.5, f"x2 error: {abs(x2_round - x2_orig)}"
            assert abs(y2_round - y2_orig) <= 0.5, f"y2 error: {abs(y2_round - y2_orig)}"

    def test_edge_coordinates(self):
        """Test conversion of edge and corner coordinates."""
        W, H = 100, 100
        
        # Full image bbox
        bbox = from_xyxy_px(0, 0, W, H, W, H)
        assert bbox.x == 0.0
        assert bbox.y == 0.0
        assert bbox.w == 1.0  
        assert bbox.h == 1.0
        
        # Convert back
        x1, y1, x2, y2 = to_xyxy_px(bbox, W, H)
        assert x1 == 0
        assert y1 == 0
        assert x2 == W
        assert y2 == H

    def test_small_bboxes(self):
        """Test conversion of very small bboxes."""
        W, H = 1000, 1000
        
        # 1-pixel bbox
        bbox = from_xyxy_px(100, 200, 101, 201, W, H)
        assert bbox.w == 1.0 / W
        assert bbox.h == 1.0 / H
        
        # Convert back  
        x1, y1, x2, y2 = to_xyxy_px(bbox, W, H)
        assert abs(x1 - 100) <= 0.5
        assert abs(y1 - 200) <= 0.5
        assert abs(x2 - 101) <= 0.5
        assert abs(y2 - 201) <= 0.5

    def test_fractional_pixels(self):
        """Test handling of fractional pixel coordinates."""
        W, H = 100, 100
        
        # Fractional input coordinates
        bbox = from_xyxy_px(10.3, 20.7, 50.9, 60.1, W, H)
        
        # Should create valid normalized bbox
        assert 0 <= bbox.x <= 1
        assert 0 <= bbox.y <= 1
        assert 0 < bbox.w <= 1
        assert 0 < bbox.h <= 1
        
        # Round-trip should be close
        x1, y1, x2, y2 = to_xyxy_px(bbox, W, H)
        assert abs(x1 - 10.3) <= 0.5
        assert abs(y1 - 20.7) <= 0.5
        assert abs(x2 - 50.9) <= 0.5
        assert abs(y2 - 60.1) <= 0.5

    def test_clamping_behavior(self):
        """Test that out-of-bounds coordinates are clamped properly."""
        W, H = 100, 100
        
        # Negative coordinates should be clamped to 0
        bbox = from_xyxy_px(-10, -5, 50, 60, W, H)
        assert bbox.x == 0.0
        assert bbox.y == 0.0
        
        # Convert back - should stay clamped
        x1, y1, x2, y2 = to_xyxy_px(bbox, W, H)
        assert x1 == 0
        assert y1 == 0

    def test_invalid_xyxy_input(self):
        """Test error handling for invalid xyxy input."""
        W, H = 100, 100
        
        # x2 < x1
        with pytest.raises(ValueError, match="xyxy invalid"):
            from_xyxy_px(50, 20, 40, 60, W, H)
        
        # y2 < y1  
        with pytest.raises(ValueError, match="xyxy invalid"):
            from_xyxy_px(10, 60, 50, 50, W, H)
        
        # Equal coordinates (zero width/height)
        with pytest.raises(ValueError, match="xyxy invalid"):
            from_xyxy_px(10, 20, 10, 60, W, H)

    def test_consistency_across_image_sizes(self):
        """Test that normalized coordinates are consistent across different image sizes."""
        # Same relative bbox in different image sizes
        relative_coords = (0.1, 0.2, 0.5, 0.6)  # 10%, 20% to 50%, 60%
        
        image_sizes = [(100, 100), (200, 150), (1920, 1080)]
        normalized_bboxes = []
        
        for W, H in image_sizes:
            # Convert relative coords to pixels for this image size
            x1 = int(relative_coords[0] * W)
            y1 = int(relative_coords[1] * H) 
            x2 = int(relative_coords[2] * W)
            y2 = int(relative_coords[3] * H)
            
            # Create normalized bbox
            bbox = from_xyxy_px(x1, y1, x2, y2, W, H)
            normalized_bboxes.append(bbox)
        
        # All normalized bboxes should be very similar
        # (small differences due to integer pixel quantization are expected)
        base_bbox = normalized_bboxes[0]
        for bbox in normalized_bboxes[1:]:
            assert abs(bbox.x - base_bbox.x) < 0.01, "x coordinates should be similar"
            assert abs(bbox.y - base_bbox.y) < 0.01, "y coordinates should be similar"
            assert abs(bbox.w - base_bbox.w) < 0.01, "widths should be similar"
            assert abs(bbox.h - base_bbox.h) < 0.01, "heights should be similar"