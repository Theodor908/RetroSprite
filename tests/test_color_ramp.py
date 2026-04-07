"""Tests for color ramp generator."""
import pytest
from src.palette import generate_ramp


class TestGenerateRamp:
    def test_rgb_ramp_2_steps(self):
        ramp = generate_ramp((0, 0, 0, 255), (255, 255, 255, 255), 2, "rgb")
        assert len(ramp) == 2
        assert ramp[0] == (0, 0, 0, 255)
        assert ramp[1] == (255, 255, 255, 255)

    def test_rgb_ramp_3_steps(self):
        ramp = generate_ramp((0, 0, 0, 255), (255, 255, 255, 255), 3, "rgb")
        assert len(ramp) == 3
        assert ramp[1] == (128, 128, 128, 255)

    def test_rgb_ramp_preserves_alpha(self):
        ramp = generate_ramp((255, 0, 0, 0), (255, 0, 0, 255), 3, "rgb")
        assert ramp[0][3] == 0
        assert ramp[1][3] == 128
        assert ramp[2][3] == 255

    def test_hsv_ramp_2_steps(self):
        ramp = generate_ramp((255, 0, 0, 255), (0, 0, 255, 255), 2, "hsv")
        assert len(ramp) == 2
        assert ramp[0] == (255, 0, 0, 255)
        assert ramp[1] == (0, 0, 255, 255)

    def test_hsv_ramp_shortest_path(self):
        ramp = generate_ramp((255, 0, 0, 255), (0, 0, 255, 255), 3, "hsv")
        assert len(ramp) == 3
        mid = ramp[1]
        assert mid[2] > 0  # should have blue component

    def test_ramp_step_count(self):
        for n in [2, 5, 10, 16, 32]:
            ramp = generate_ramp((0, 0, 0, 255), (255, 255, 255, 255), n, "rgb")
            assert len(ramp) == n
