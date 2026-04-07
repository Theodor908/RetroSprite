"""Tests for project save/load."""
import os
import pytest
from PIL import Image
from src.pixel_data import PixelGrid
from src.animation import AnimationTimeline, Frame
from src.palette import Palette
from src.project import save_project, load_project
from src.reference_image import ReferenceImage


class TestProject:
    def test_save_and_load_roundtrip(self, tmp_path):
        path = str(tmp_path / "test.retro")

        # Set up a timeline with 2 frames and some pixels
        timeline = AnimationTimeline(8, 8)
        timeline.current_layer().set_pixel(0, 0, (255, 0, 0, 255))
        timeline.add_frame()
        timeline.set_current(1)
        timeline.current_layer().set_pixel(3, 3, (0, 255, 0, 255))
        timeline.fps = 15

        palette = Palette("NES")
        palette.select(2)

        save_project(path, timeline, palette)
        assert os.path.exists(path)

        loaded_tl, loaded_pal, _, _, _ = load_project(path)
        assert loaded_tl.width == 8
        assert loaded_tl.height == 8
        assert loaded_tl.frame_count == 2
        assert loaded_tl.current_index == 1
        assert loaded_tl.fps == 15
        assert loaded_tl.get_frame(0).get_pixel(0, 0) == (255, 0, 0, 255)
        assert loaded_tl.get_frame(1).get_pixel(3, 3) == (0, 255, 0, 255)
        assert loaded_pal.name == "NES"
        assert loaded_pal.selected_index == 2

    def test_load_preserves_custom_palette_colors(self, tmp_path):
        path = str(tmp_path / "custom.retro")

        timeline = AnimationTimeline(4, 4)
        palette = Palette("Pico-8")
        palette.add_color((123, 45, 67, 255))

        save_project(path, timeline, palette)
        _, loaded_pal, _, _, _ = load_project(path)
        assert (123, 45, 67, 255) in loaded_pal.colors

    def test_v2_saves_layer_data(self, tmp_path):
        """Verify v2 format saves and loads layer information."""
        path = str(tmp_path / "layers.retro")

        timeline = AnimationTimeline(4, 4)
        frame = timeline.current_frame_obj()
        frame.layers[0].pixels.set_pixel(0, 0, (255, 0, 0, 255))
        frame.add_layer("Top Layer")
        frame.layers[1].pixels.set_pixel(1, 1, (0, 255, 0, 255))
        frame.layers[1].opacity = 0.5
        frame.layers[1].visible = False

        palette = Palette("Pico-8")
        save_project(path, timeline, palette)

        loaded_tl, _, _, _, _ = load_project(path)
        loaded_frame = loaded_tl.get_frame_obj(0)
        assert len(loaded_frame.layers) == 2
        assert loaded_frame.layers[0].name == "Layer 1"
        assert loaded_frame.layers[1].name == "Top Layer"
        assert loaded_frame.layers[1].opacity == 0.5
        assert loaded_frame.layers[1].visible is False
        assert loaded_frame.layers[0].pixels.get_pixel(0, 0) == (255, 0, 0, 255)
        assert loaded_frame.layers[1].pixels.get_pixel(1, 1) == (0, 255, 0, 255)


class TestReferenceImagePersistence:
    def test_save_load_with_reference_image(self, tmp_path):
        """Reference image should roundtrip through save/load."""
        path = str(tmp_path / "ref_test.retro")
        timeline = AnimationTimeline(8, 8)
        palette = Palette("Pico-8")

        ref_img = Image.new("RGBA", (20, 15), (255, 0, 0, 128))
        ref = ReferenceImage(image=ref_img, x=3, y=5, scale=0.5,
                             opacity=0.7, visible=False, path="/tmp/photo.png")

        save_project(path, timeline, palette, reference_image=ref)
        loaded_tl, loaded_pal, _, loaded_ref, _ = load_project(path)

        assert loaded_ref is not None
        assert loaded_ref.x == 3
        assert loaded_ref.y == 5
        assert loaded_ref.scale == 0.5
        assert loaded_ref.opacity == pytest.approx(0.7)
        assert loaded_ref.visible is False
        assert loaded_ref.path == "/tmp/photo.png"
        assert loaded_ref.image.size == (20, 15)
        assert loaded_ref.image.getpixel((0, 0)) == (255, 0, 0, 128)

    def test_save_load_without_reference_image(self, tmp_path):
        """No reference image should load as None."""
        path = str(tmp_path / "no_ref.retro")
        timeline = AnimationTimeline(8, 8)
        palette = Palette("Pico-8")

        save_project(path, timeline, palette)
        loaded_tl, loaded_pal, _, loaded_ref, _ = load_project(path)
        assert loaded_ref is None

    def test_load_old_version_file_returns_none_reference(self, tmp_path):
        """Files without reference_image key should return None."""
        import json
        path = str(tmp_path / "old.retro")
        old_project = {
            "version": 5, "width": 8, "height": 8, "fps": 10,
            "current_frame": 0, "color_mode": "rgba",
            "palette_name": "Pico-8",
            "palette_colors": [[0, 0, 0, 255]],
            "selected_color_index": 0,
            "tilesets": {},
            "frames": [{"name": "Frame 1", "layers": [{
                "name": "Layer 1",
                "visible": True, "opacity": 1.0, "blend_mode": "normal",
                "locked": False, "depth": 0, "is_group": False,
                "effects": [], "clipping": False
            }], "active_layer": 0}],
            "tags": [], "tool_settings": {}
        }
        with open(path, "w") as f:
            json.dump(old_project, f)

        loaded_tl, loaded_pal, _, loaded_ref, _ = load_project(path)
        assert loaded_ref is None
        assert loaded_tl.width == 8
