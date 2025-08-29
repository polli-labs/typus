"""Tests for provider-specific bbox mappings, especially Gemini BR/xyxy."""

import pytest

from typus.models.geometry import BBoxMapper, BBoxXYWHNorm


class TestGeminiBRMapping:
    """Test Gemini bottom-right origin to canonical TL-normalized conversion."""

    def test_gemini_mapper_registration(self):
        """Test that Gemini mapper is properly registered."""
        # Should be able to get the registered mapper
        mapper_fn = BBoxMapper.get("gemini_br_xyxy")
        assert callable(mapper_fn)

        # Should be in the list of providers
        providers = BBoxMapper.list_providers()
        assert "gemini_br_xyxy" in providers

    def test_simple_gemini_conversion(self):
        """Test basic BR->TL coordinate conversion."""
        # Simple case: 100x100 image
        W, H = 100, 100

        # Gemini BR coordinates (bottom-right origin)
        # If object is at top-left of image in our TL system,
        # in BR system it would be at (W-x2, H-y2) to (W-x1, H-y1)

        # Expected TL bbox: x=0.2, y=0.1, w=0.3, h=0.4 (20,10 to 50,50 in 100x100)
        # In BR system: (100-50, 100-50) to (100-20, 100-10) = (50,50) to (80,90)
        x1_br, y1_br = 50, 50  # bottom-right origin
        x2_br, y2_br = 80, 90

        mapper_fn = BBoxMapper.get("gemini_br_xyxy")
        bbox = mapper_fn(x1_br, y1_br, x2_br, y2_br, W, H)

        # Resulting canonical bbox should be:
        # TL x1 = W - x2_br = 100 - 80 = 20
        # TL y1 = H - y2_br = 100 - 90 = 10
        # TL x2 = W - x1_br = 100 - 50 = 50
        # TL y2 = H - y1_br = 100 - 50 = 50
        # Normalized: x=20/100=0.2, y=10/100=0.1, w=30/100=0.3, h=40/100=0.4

        assert abs(bbox.x - 0.2) < 1e-6
        assert abs(bbox.y - 0.1) < 1e-6
        assert abs(bbox.w - 0.3) < 1e-6
        assert abs(bbox.h - 0.4) < 1e-6

    def test_gemini_full_image_bbox(self):
        """Test conversion of full-image bbox from BR origin."""
        W, H = 200, 150

        # Full image in BR coordinates: (0, 0) to (W, H)
        x1_br, y1_br = 0, 0
        x2_br, y2_br = W, H

        mapper_fn = BBoxMapper.get("gemini_br_xyxy")
        bbox = mapper_fn(x1_br, y1_br, x2_br, y2_br, W, H)

        # Should convert to full normalized bbox
        assert abs(bbox.x - 0.0) < 1e-6
        assert abs(bbox.y - 0.0) < 1e-6
        assert abs(bbox.w - 1.0) < 1e-6
        assert abs(bbox.h - 1.0) < 1e-6

    def test_gemini_corner_cases(self):
        """Test edge cases for Gemini conversion."""
        W, H = 1000, 800
        mapper_fn = BBoxMapper.get("gemini_br_xyxy")

        # Bottom-left corner in TL system = top-right in BR system
        # TL: (0, 700) to (100, 800) -> normalized (0, 0.875) to (0.1, 1.0)
        # BR: (900, 0) to (1000, 100)
        bbox = mapper_fn(900, 0, 1000, 100, W, H)

        expected_x = 0.0
        expected_y = 0.875  # (800-100)/800
        expected_w = 0.1  # 100/1000
        expected_h = 0.125  # 100/800

        assert abs(bbox.x - expected_x) < 1e-6
        assert abs(bbox.y - expected_y) < 1e-6
        assert abs(bbox.w - expected_w) < 1e-6
        assert abs(bbox.h - expected_h) < 1e-6

    def test_gemini_with_different_aspect_ratios(self):
        """Test Gemini conversion with various image aspect ratios."""
        test_cases = [
            (1920, 1080),  # 16:9 HD
            (1080, 1920),  # 9:16 portrait
            (1000, 1000),  # 1:1 square
            (800, 600),  # 4:3 classic
            (2560, 1440),  # 16:9 QHD
        ]

        mapper_fn = BBoxMapper.get("gemini_br_xyxy")

        for W, H in test_cases:
            # Test a centered bbox: 25% to 75% in both dimensions
            # TL system: (0.25*W, 0.25*H) to (0.75*W, 0.75*H)
            tl_x1, tl_y1 = int(0.25 * W), int(0.25 * H)
            tl_x2, tl_y2 = int(0.75 * W), int(0.75 * H)

            # Convert to BR coordinates
            br_x1 = W - tl_x2  # W - 0.75*W = 0.25*W
            br_y1 = H - tl_y2  # H - 0.75*H = 0.25*H
            br_x2 = W - tl_x1  # W - 0.25*W = 0.75*W
            br_y2 = H - tl_y1  # H - 0.25*H = 0.75*H

            bbox = mapper_fn(br_x1, br_y1, br_x2, br_y2, W, H)

            # Should result in approximately centered 50% bbox
            assert abs(bbox.x - 0.25) < 0.01
            assert abs(bbox.y - 0.25) < 0.01
            assert abs(bbox.w - 0.5) < 0.01
            assert abs(bbox.h - 0.5) < 0.01

    def test_gemini_validation_failures(self):
        """Test that invalid Gemini coordinates raise appropriate errors."""
        mapper_fn = BBoxMapper.get("gemini_br_xyxy")
        W, H = 100, 100

        # Invalid BR coordinates (x2 < x1 after conversion)
        # This should fail in from_xyxy_px validation
        with pytest.raises(ValueError):
            mapper_fn(80, 50, 50, 90, W, H)  # Would create x2 < x1 in TL system


class TestBBoxMapperRegistry:
    """Test the BBoxMapper registry system."""

    def test_register_custom_mapper(self):
        """Test registering a custom bbox mapper."""

        def custom_mapper(x1, y1, x2, y2, W, H) -> BBoxXYWHNorm:
            # Simple identity mapper (assumes input is already TL xyxy pixels)
            return BBoxXYWHNorm(x=x1 / W, y=y1 / H, w=(x2 - x1) / W, h=(y2 - y1) / H)

        # Register custom mapper
        BBoxMapper.register("test_custom", custom_mapper)

        # Should be able to retrieve it
        retrieved = BBoxMapper.get("test_custom")
        assert retrieved == custom_mapper

        # Should be in providers list
        providers = BBoxMapper.list_providers()
        assert "test_custom" in providers

        # Should work when called
        bbox = retrieved(10, 20, 50, 60, 100, 100)
        assert bbox.x == 0.1
        assert bbox.y == 0.2
        assert bbox.w == 0.4
        assert bbox.h == 0.4

    def test_nonexistent_mapper(self):
        """Test error when requesting non-existent mapper."""
        with pytest.raises(KeyError, match="No bbox mapper registered for 'nonexistent_mapper'"):
            BBoxMapper.get("nonexistent_mapper")

    def test_provider_list(self):
        """Test listing all registered providers."""
        providers = BBoxMapper.list_providers()

        # Should contain at least the built-in Gemini mapper
        assert "gemini_br_xyxy" in providers
        assert isinstance(providers, list)

    def test_mapper_overwrite_protection(self):
        """Test that registering same name requires explicit replace=True."""

        def mapper1(x1, y1, x2, y2, W, H):
            return BBoxXYWHNorm(x=0.1, y=0.1, w=0.1, h=0.1)

        def mapper2(x1, y1, x2, y2, W, H):
            return BBoxXYWHNorm(x=0.2, y=0.2, w=0.2, h=0.2)

        # Register first mapper
        BBoxMapper.register("test_overwrite_protection", mapper1)
        result1 = BBoxMapper.get("test_overwrite_protection")(0, 0, 10, 10, 100, 100)
        assert result1.x == 0.1

        # Try to register second mapper without replace=True (should fail)
        with pytest.raises(KeyError, match="already exists.*replace=True"):
            BBoxMapper.register("test_overwrite_protection", mapper2)

        # Should still use first mapper
        result_still_1 = BBoxMapper.get("test_overwrite_protection")(0, 0, 10, 10, 100, 100)
        assert result_still_1.x == 0.1

        # Register second mapper with explicit replace=True (should succeed)
        BBoxMapper.register("test_overwrite_protection", mapper2, replace=True)
        result2 = BBoxMapper.get("test_overwrite_protection")(0, 0, 10, 10, 100, 100)
        assert result2.x == 0.2  # Should use the new mapper
