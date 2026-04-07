import numpy as np
from src.effects import (
    LayerEffect, apply_effects,
    apply_outline, apply_drop_shadow, apply_inner_shadow,
    apply_hue_sat, apply_gradient_map, apply_glow, apply_pattern_overlay,
)


def _make_square(size=16, color=(255, 0, 0, 255)):
    pixels = np.zeros((size, size, 4), dtype=np.uint8)
    q = size // 4
    pixels[q:size-q, q:size-q] = color
    return pixels


class TestLayerEffect:
    def test_create_effect(self):
        fx = LayerEffect("outline", True, {"color": (0, 0, 0, 255), "thickness": 1,
                                            "mode": "outer", "connectivity": 4})
        assert fx.type == "outline"
        assert fx.enabled is True
        assert fx.params["thickness"] == 1

    def test_disabled_effect_skipped(self):
        pixels = _make_square()
        fx = LayerEffect("outline", False, {"color": (0, 0, 0, 255), "thickness": 1,
                                             "mode": "outer", "connectivity": 4})
        result = apply_effects(pixels, [fx])
        assert np.array_equal(result, pixels)


class TestOutline:
    def test_outer_outline_adds_pixels(self):
        pixels = _make_square(16, (255, 0, 0, 255))
        result = apply_outline(pixels, color=(0, 0, 0, 255), thickness=1,
                               mode="outer", connectivity=4)
        orig_opaque = np.sum(pixels[:, :, 3] > 0)
        result_opaque = np.sum(result[:, :, 3] > 0)
        assert result_opaque > orig_opaque

    def test_inner_outline_doesnt_expand(self):
        pixels = _make_square(16, (255, 0, 0, 255))
        result = apply_outline(pixels, color=(0, 0, 0, 255), thickness=1,
                               mode="inner", connectivity=4)
        orig_opaque = np.sum(pixels[:, :, 3] > 0)
        result_opaque = np.sum(result[:, :, 3] > 0)
        assert result_opaque == orig_opaque

    def test_8_connectivity_more_pixels(self):
        pixels = _make_square(16, (255, 0, 0, 255))
        result4 = apply_outline(pixels, (0, 0, 0, 255), 1, "outer", 4)
        result8 = apply_outline(pixels, (0, 0, 0, 255), 1, "outer", 8)
        count4 = np.sum(result4[:, :, 3] > 0)
        count8 = np.sum(result8[:, :, 3] > 0)
        assert count8 >= count4


class TestDropShadow:
    def test_shadow_adds_pixels_behind(self):
        pixels = _make_square(16, (255, 0, 0, 255))
        result = apply_drop_shadow(pixels, color=(0, 0, 0, 255),
                                   offset_x=2, offset_y=2, blur=0, opacity=1.0)
        orig_opaque = np.sum(pixels[:, :, 3] > 0)
        result_opaque = np.sum(result[:, :, 3] > 0)
        assert result_opaque > orig_opaque

    def test_zero_offset_no_visible_shadow(self):
        pixels = _make_square(16, (255, 0, 0, 255))
        result = apply_drop_shadow(pixels, (0, 0, 0, 255), 0, 0, 0, 1.0)
        orig_opaque = np.sum(pixels[:, :, 3] > 0)
        result_opaque = np.sum(result[:, :, 3] > 0)
        assert result_opaque == orig_opaque


class TestInnerShadow:
    def test_inner_shadow_doesnt_expand(self):
        pixels = _make_square(16, (255, 0, 0, 255))
        result = apply_inner_shadow(pixels, (0, 0, 0, 255), 1, 1, 0, 0.5)
        orig_opaque = np.sum(pixels[:, :, 3] > 0)
        result_opaque = np.sum(result[:, :, 3] > 0)
        assert result_opaque == orig_opaque


class TestHueSat:
    def test_zero_shift_near_identity(self):
        pixels = _make_square(16, (255, 0, 0, 255))
        result = apply_hue_sat(pixels, hue=0, saturation=1.0, value=0)
        np.testing.assert_allclose(result.astype(float), pixels.astype(float), atol=1)

    def test_hue_shift_changes_color(self):
        pixels = _make_square(16, (255, 0, 0, 255))
        result = apply_hue_sat(pixels, hue=120, saturation=1.0, value=0)
        opaque = result[:, :, 3] > 0
        assert np.mean(result[opaque, 1]) > np.mean(result[opaque, 0])


class TestGradientMap:
    def test_two_stop_gradient(self):
        pixels = _make_square(16, (128, 128, 128, 255))
        stops = [(0.0, (0, 0, 0, 255)), (1.0, (255, 255, 255, 255))]
        result = apply_gradient_map(pixels, stops=stops, opacity=1.0)
        opaque = result[:, :, 3] > 0
        avg = np.mean(result[opaque, 0])
        assert 100 < avg < 200


class TestGlow:
    def test_glow_adds_brightness(self):
        pixels = _make_square(16, (255, 255, 255, 255))
        result = apply_glow(pixels, threshold=200, radius=2, intensity=1.0,
                            tint=(255, 255, 255, 255))
        orig_bright = np.sum(pixels[:, :, 3] > 0)
        result_bright = np.sum(result[:, :, 3] > 0)
        assert result_bright >= orig_bright


class TestPatternOverlay:
    def test_pattern_clipped_to_alpha(self):
        pixels = _make_square(16, (255, 0, 0, 255))
        result = apply_pattern_overlay(pixels, pattern="checkerboard",
                                       blend_mode="multiply", opacity=0.5,
                                       scale=1, offset_x=0, offset_y=0)
        orig_transparent = pixels[:, :, 3] == 0
        assert np.all(result[orig_transparent, 3] == 0)


class TestApplyEffects:
    def test_multiple_effects_applied_in_order(self):
        pixels = _make_square(16, (255, 0, 0, 255))
        effects = [
            LayerEffect("outline", True, {"color": (0, 0, 0, 255), "thickness": 1,
                                           "mode": "outer", "connectivity": 4}),
            LayerEffect("drop_shadow", True, {"color": (0, 0, 0, 255),
                                               "offset_x": 2, "offset_y": 2,
                                               "blur": 0, "opacity": 0.7}),
        ]
        result = apply_effects(pixels, effects)
        orig_opaque = np.sum(pixels[:, :, 3] > 0)
        result_opaque = np.sum(result[:, :, 3] > 0)
        assert result_opaque > orig_opaque
