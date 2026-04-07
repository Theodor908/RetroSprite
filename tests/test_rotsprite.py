import numpy as np
from src.rotsprite import color_distance, scale2x, rotsprite_rotate, fast_rotate


class TestColorDistance:
    def test_identical_colors(self):
        assert color_distance((255, 0, 0, 255), (255, 0, 0, 255)) == 0

    def test_different_colors(self):
        assert color_distance((255, 0, 0, 255), (0, 0, 0, 255)) == 255

    def test_full_distance(self):
        assert color_distance((0, 0, 0, 0), (255, 255, 255, 255)) == 1020

    def test_partial_distance(self):
        assert color_distance((100, 100, 100, 255), (110, 90, 100, 255)) == 20


class TestScale2x:
    def test_single_pixel(self):
        pixels = np.zeros((1, 1, 4), dtype=np.uint8)
        pixels[0, 0] = [255, 0, 0, 255]
        result = scale2x(pixels)
        assert result.shape == (2, 2, 4)
        assert np.all(result[:, :, 0] == 255)

    def test_uniform_2x2(self):
        pixels = np.full((2, 2, 4), [0, 255, 0, 255], dtype=np.uint8)
        result = scale2x(pixels)
        assert result.shape == (4, 4, 4)
        assert np.all(result[:, :, 1] == 255)

    def test_edge_detection(self):
        """Scale2x should smooth diagonal edges."""
        pixels = np.zeros((3, 3, 4), dtype=np.uint8)
        pixels[0, 0] = [255, 255, 255, 255]
        pixels[1, 1] = [255, 255, 255, 255]
        pixels[2, 2] = [255, 255, 255, 255]
        result = scale2x(pixels)
        assert result.shape == (6, 6, 4)
        white_count_orig = 3
        white_count_result = np.sum(result[:, :, 3] > 0)
        assert white_count_result > white_count_orig


class TestFastRotate:
    def test_90_degrees(self):
        pixels = np.zeros((4, 4, 4), dtype=np.uint8)
        pixels[0, :] = [255, 0, 0, 255]  # red top row
        result = fast_rotate(pixels, 90)
        assert result.shape == (4, 4, 4)
        # After 90° CW rotation, top row should become right column
        assert np.all(result[:, 3, 0] == 255)

    def test_0_degrees_identity(self):
        pixels = np.zeros((4, 4, 4), dtype=np.uint8)
        pixels[1, 2] = [0, 255, 0, 255]
        result = fast_rotate(pixels, 0)
        assert np.array_equal(result, pixels)

    def test_360_degrees_identity(self):
        pixels = np.zeros((4, 4, 4), dtype=np.uint8)
        pixels[1, 2] = [0, 255, 0, 255]
        result = fast_rotate(pixels, 360)
        assert np.array_equal(result, pixels)

    def test_custom_pivot(self):
        pixels = np.zeros((8, 8, 4), dtype=np.uint8)
        pixels[0, 0] = [255, 0, 0, 255]
        result = fast_rotate(pixels, 90, pivot=(0, 0))
        assert result.shape == (8, 8, 4)


class TestRotspriteRotate:
    def test_90_degrees_preserves_shape(self):
        pixels = np.zeros((8, 8, 4), dtype=np.uint8)
        pixels[0, :] = [255, 0, 0, 255]  # red top row
        result = rotsprite_rotate(pixels, 90)
        assert result.shape == (8, 8, 4)

    def test_0_degrees_identity(self):
        pixels = np.zeros((8, 8, 4), dtype=np.uint8)
        pixels[2, 3] = [0, 255, 0, 255]
        result = rotsprite_rotate(pixels, 0)
        # Should be essentially identical at 0 degrees
        assert result[2, 3, 1] == 255

    def test_no_new_colors(self):
        """RotSprite should not introduce colors not in the original."""
        pixels = np.zeros((8, 8, 4), dtype=np.uint8)
        pixels[2:6, 2:6] = [255, 0, 0, 255]  # red square
        result = rotsprite_rotate(pixels, 45)
        # Every non-transparent pixel should be red
        opaque = result[:, :, 3] > 0
        if np.any(opaque):
            assert np.all(result[opaque, 0] == 255)
            assert np.all(result[opaque, 1] == 0)
            assert np.all(result[opaque, 2] == 0)
