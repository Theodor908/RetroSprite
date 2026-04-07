"""Tests for the unified selection model and set operations."""
import pytest
from src.pixel_data import PixelGrid


class TestSelectionOperations:
    """Test selection set operations (add/subtract/intersect)."""

    def _make_app_stub(self):
        """Create a minimal stub with selection state."""
        class Stub:
            _selection_pixels = None
            def _apply_selection_op(self, new_pixels, event_state=0):
                shift_held = event_state & 0x1
                ctrl_held = event_state & 0x4
                existing = self._selection_pixels or set()
                if shift_held and ctrl_held:
                    return existing & new_pixels
                elif shift_held:
                    return existing | new_pixels
                elif ctrl_held:
                    return existing - new_pixels
                else:
                    return new_pixels
        return Stub()

    def test_replace_selection(self):
        stub = self._make_app_stub()
        stub._selection_pixels = {(0, 0), (1, 1)}
        result = stub._apply_selection_op({(2, 2), (3, 3)}, event_state=0)
        assert result == {(2, 2), (3, 3)}

    def test_add_selection_shift(self):
        stub = self._make_app_stub()
        stub._selection_pixels = {(0, 0), (1, 1)}
        result = stub._apply_selection_op({(2, 2)}, event_state=0x1)
        assert result == {(0, 0), (1, 1), (2, 2)}

    def test_subtract_selection_ctrl(self):
        stub = self._make_app_stub()
        stub._selection_pixels = {(0, 0), (1, 1), (2, 2)}
        result = stub._apply_selection_op({(1, 1)}, event_state=0x4)
        assert result == {(0, 0), (2, 2)}

    def test_intersect_selection_shift_ctrl(self):
        stub = self._make_app_stub()
        stub._selection_pixels = {(0, 0), (1, 1), (2, 2)}
        result = stub._apply_selection_op({(1, 1), (3, 3)}, event_state=0x5)
        assert result == {(1, 1)}

    def test_add_to_empty(self):
        stub = self._make_app_stub()
        result = stub._apply_selection_op({(5, 5)}, event_state=0x1)
        assert result == {(5, 5)}

    def test_subtract_from_empty(self):
        stub = self._make_app_stub()
        result = stub._apply_selection_op({(5, 5)}, event_state=0x4)
        assert result == set()

    def test_rect_to_pixel_set(self):
        """Rect select should produce correct pixel set."""
        x0, y0, x1, y1 = 2, 3, 4, 5
        w, h = 10, 10
        pixels = {(px, py) for px in range(max(0, x0), min(w, x1 + 1))
                  for py in range(max(0, y0), min(h, y1 + 1))}
        assert len(pixels) == 3 * 3
        assert (2, 3) in pixels
        assert (4, 5) in pixels
        assert (5, 5) not in pixels


class TestSelectionIntegration:
    """Integration tests for selection + copy + fill with unified model."""

    def test_fill_pixel_set(self):
        grid = PixelGrid(10, 10)
        selection = {(2, 2), (3, 3), (4, 4)}
        color = (255, 0, 0, 255)
        for (px, py) in selection:
            grid.set_pixel(px, py, color)
        assert grid.get_pixel(2, 2) == color
        assert grid.get_pixel(0, 0) == (0, 0, 0, 0)

    def test_delete_pixel_set(self):
        grid = PixelGrid(10, 10)
        for x in range(10):
            for y in range(10):
                grid.set_pixel(x, y, (100, 100, 100, 255))
        selection = {(5, 5), (6, 6)}
        for (px, py) in selection:
            grid.set_pixel(px, py, (0, 0, 0, 0))
        assert grid.get_pixel(5, 5) == (0, 0, 0, 0)
        assert grid.get_pixel(4, 4) == (100, 100, 100, 255)

    def test_copy_from_pixel_set(self):
        grid = PixelGrid(10, 10)
        grid.set_pixel(2, 3, (255, 0, 0, 255))
        grid.set_pixel(4, 5, (0, 255, 0, 255))
        selection = {(2, 3), (4, 5)}
        xs = [p[0] for p in selection]
        ys = [p[1] for p in selection]
        x0, y0 = min(xs), min(ys)
        x1, y1 = max(xs), max(ys)
        w = x1 - x0 + 1
        h = y1 - y0 + 1
        clip = PixelGrid(w, h)
        for (px, py) in selection:
            color = grid.get_pixel(px, py)
            clip.set_pixel(px - x0, py - y0, color)
        assert clip.get_pixel(0, 0) == (255, 0, 0, 255)
        assert clip.get_pixel(2, 2) == (0, 255, 0, 255)
        assert clip.get_pixel(1, 1) == (0, 0, 0, 0)
