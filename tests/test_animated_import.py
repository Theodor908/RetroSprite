"""Tests for animated format import parsers and timeline builder."""
import pytest
import tempfile
import os
from PIL import Image
from src.animated_import import (
    ImportedAnimation, ImportSettings, build_timeline_from_import,
)
from src.animation import AnimationTimeline


class TestParseGif:
    def _make_gif(self, frames, durations=None, disposal=2):
        """Helper: create a GIF file from RGBA PIL images."""
        if durations is None:
            durations = [100] * len(frames)
        path = os.path.join(tempfile.mkdtemp(), "test.gif")
        # Convert RGBA to P mode for GIF
        p_frames = []
        for img in frames:
            p_img = img.convert("RGB").convert("P", palette=Image.ADAPTIVE, colors=255)
            p_frames.append(p_img)
        p_frames[0].save(
            path, save_all=True, append_images=p_frames[1:],
            duration=durations, loop=0, disposal=disposal
        )
        return path

    def test_parse_gif_frames(self):
        from src.animated_import import parse_gif
        imgs = [
            Image.new("RGBA", (4, 4), (255, 0, 0, 255)),
            Image.new("RGBA", (4, 4), (0, 255, 0, 255)),
            Image.new("RGBA", (4, 4), (0, 0, 255, 255)),
        ]
        path = self._make_gif(imgs, durations=[50, 100, 200])
        result = parse_gif(path)
        assert len(result.frames) == 3
        assert result.width == 4
        assert result.height == 4
        assert result.durations == [50, 100, 200]
        assert result.source_path == path

    def test_parse_gif_single_frame(self):
        from src.animated_import import parse_gif
        img = Image.new("RGBA", (8, 8), (255, 0, 0, 255))
        path = self._make_gif([img])
        result = parse_gif(path)
        assert len(result.frames) == 1

    def test_parse_gif_missing_duration(self):
        from src.animated_import import parse_gif
        path = os.path.join(tempfile.mkdtemp(), "test.gif")
        img = Image.new("P", (4, 4), 1)
        img.save(path)
        result = parse_gif(path)
        assert result.durations == [100]

    def test_parse_gif_empty_raises(self):
        from src.animated_import import parse_gif
        path = os.path.join(tempfile.mkdtemp(), "bad.gif")
        with open(path, "wb") as f:
            f.write(b"not a gif")
        with pytest.raises((ValueError, Exception)):
            parse_gif(path)

    def test_parse_source_path_preserved(self):
        from src.animated_import import parse_gif
        img = Image.new("RGBA", (4, 4), (255, 0, 0, 255))
        path = self._make_gif([img])
        result = parse_gif(path)
        assert result.source_path == path


class TestParseApng:
    def test_parse_apng_frames(self):
        from src.animated_import import parse_apng
        path = os.path.join(tempfile.mkdtemp(), "test.apng")
        imgs = [
            Image.new("RGBA", (4, 4), (255, 0, 0, 255)),
            Image.new("RGBA", (4, 4), (0, 255, 0, 255)),
            Image.new("RGBA", (4, 4), (0, 0, 255, 255)),
        ]
        imgs[0].save(
            path, save_all=True, append_images=imgs[1:],
            duration=[50, 100, 150], loop=0, disposal=2, format="PNG"
        )
        result = parse_apng(path)
        assert len(result.frames) == 3
        assert result.width == 4
        assert result.height == 4
        assert result.source_path == path

    def test_parse_apng_from_png_extension(self):
        from src.animated_import import parse_apng
        path = os.path.join(tempfile.mkdtemp(), "test.png")
        imgs = [
            Image.new("RGBA", (4, 4), (255, 0, 0, 255)),
            Image.new("RGBA", (4, 4), (0, 255, 0, 255)),
        ]
        imgs[0].save(
            path, save_all=True, append_images=imgs[1:],
            duration=[100, 100], loop=0, disposal=2, format="PNG"
        )
        result = parse_apng(path)
        assert len(result.frames) == 2


class TestParseWebp:
    def test_parse_webp_frames(self):
        from src.animated_import import parse_webp
        path = os.path.join(tempfile.mkdtemp(), "test.webp")
        imgs = [
            Image.new("RGBA", (4, 4), (255, 0, 0, 255)),
            Image.new("RGBA", (4, 4), (0, 255, 0, 255)),
            Image.new("RGBA", (4, 4), (0, 0, 255, 255)),
        ]
        imgs[0].save(
            path, save_all=True, append_images=imgs[1:],
            duration=[50, 100, 150], loop=0, lossless=True, format="WEBP"
        )
        result = parse_webp(path)
        assert len(result.frames) == 3
        assert result.width == 4
        assert result.height == 4
        assert result.durations == [50, 100, 150]
        assert result.source_path == path


class TestBuildNewProject:
    def _make_animation(self, n_frames=3, w=8, h=8, durations=None):
        frames = [Image.new("RGBA", (w, h), (i * 80, 0, 0, 255))
                  for i in range(n_frames)]
        if durations is None:
            durations = [50 + i * 50 for i in range(n_frames)]
        return ImportedAnimation(
            frames=frames, durations=durations,
            width=w, height=h,
            palette=[(255, 0, 0, 255), (0, 255, 0, 255)],
            source_path="/tmp/test.gif",
        )

    def test_build_new_project(self):
        anim = self._make_animation(3)
        settings = ImportSettings(mode="new_project", resize="match",
                                  timing="original")
        timeline, palette = build_timeline_from_import(anim, settings)
        assert timeline.frame_count == 3
        assert timeline.width == 8
        assert timeline.height == 8
        assert timeline.get_frame_obj(0).duration_ms == 50
        assert timeline.get_frame_obj(1).duration_ms == 100
        assert timeline.get_frame_obj(2).duration_ms == 150

    def test_build_new_project_palette(self):
        anim = self._make_animation(2)
        settings = ImportSettings(mode="new_project", resize="match",
                                  timing="original")
        timeline, palette = build_timeline_from_import(anim, settings)
        assert palette is not None
        assert len(palette) == 2
        assert palette[0] == (255, 0, 0, 255)

    def test_build_timing_normalize(self):
        anim = self._make_animation(3, durations=[50, 100, 200])
        settings = ImportSettings(mode="new_project", resize="match",
                                  timing="project_fps")
        timeline, _ = build_timeline_from_import(anim, settings,
                                                  project_fps=10)
        for i in range(3):
            assert timeline.get_frame_obj(i).duration_ms == 100

    def test_build_timing_original(self):
        anim = self._make_animation(3, durations=[33, 66, 99])
        settings = ImportSettings(mode="new_project", resize="match",
                                  timing="original")
        timeline, _ = build_timeline_from_import(anim, settings)
        assert timeline.get_frame_obj(0).duration_ms == 33
        assert timeline.get_frame_obj(1).duration_ms == 66
        assert timeline.get_frame_obj(2).duration_ms == 99


class TestBuildInsert:
    def _make_animation(self, n_frames=2, w=8, h=8):
        frames = [Image.new("RGBA", (w, h), (255, 0, 0, 255))
                  for _ in range(n_frames)]
        return ImportedAnimation(
            frames=frames, durations=[100] * n_frames,
            width=w, height=h, palette=None,
            source_path="/tmp/test.gif",
        )

    def test_build_insert_frames(self):
        """Frames inserted sequentially after current_index."""
        existing = AnimationTimeline(8, 8)
        existing.add_frame()  # now 2 frames
        existing.set_current(0)
        anim = self._make_animation(3)
        settings = ImportSettings(mode="insert", resize="scale",
                                  timing="original")
        timeline, palette = build_timeline_from_import(
            anim, settings, existing_timeline=existing)
        assert timeline.frame_count == 5

    def test_build_insert_palette_none(self):
        existing = AnimationTimeline(8, 8)
        anim = self._make_animation(1)
        settings = ImportSettings(mode="insert", resize="scale",
                                  timing="original")
        _, palette = build_timeline_from_import(
            anim, settings, existing_timeline=existing)
        assert palette is None

    def test_build_insert_resize_scale(self):
        """Imported 16x16 frames scaled down to 8x8 canvas."""
        existing = AnimationTimeline(8, 8)
        anim = self._make_animation(1, w=16, h=16)
        settings = ImportSettings(mode="insert", resize="scale",
                                  timing="original")
        timeline, _ = build_timeline_from_import(
            anim, settings, existing_timeline=existing)
        assert timeline.width == 8
        assert timeline.height == 8
        inserted = timeline.get_frame_obj(1)
        assert inserted.layers[0].pixels.width == 8

    def test_build_insert_resize_crop(self):
        """Imported 16x16 frames centered and cropped to 8x8 canvas."""
        existing = AnimationTimeline(8, 8)
        anim = self._make_animation(1, w=16, h=16)
        settings = ImportSettings(mode="insert", resize="crop",
                                  timing="original")
        timeline, _ = build_timeline_from_import(
            anim, settings, existing_timeline=existing)
        assert timeline.width == 8
        assert timeline.height == 8

    def test_build_insert_resize_match(self):
        """Canvas resized to match imported dimensions."""
        existing = AnimationTimeline(8, 8)
        existing.current_frame_obj().layers[0].pixels.set_pixel(0, 0, (255, 0, 0, 255))
        anim = self._make_animation(1, w=16, h=16)
        settings = ImportSettings(mode="insert", resize="match",
                                  timing="original")
        timeline, _ = build_timeline_from_import(
            anim, settings, existing_timeline=existing)
        assert timeline.width == 16
        assert timeline.height == 16
        assert existing.get_frame_obj(0).layers[0].pixels.width == 16


class TestApngDetection:
    def test_png_apng_detection(self):
        """An APNG saved with .png extension should be detected as animated."""
        from src.animated_import import parse_apng
        path = os.path.join(tempfile.mkdtemp(), "animation.png")
        imgs = [
            Image.new("RGBA", (4, 4), (255, 0, 0, 255)),
            Image.new("RGBA", (4, 4), (0, 255, 0, 255)),
        ]
        imgs[0].save(
            path, save_all=True, append_images=imgs[1:],
            duration=[100, 100], loop=0, disposal=2, format="PNG"
        )
        img = Image.open(path)
        assert getattr(img, "n_frames", 1) > 1
        img.close()
        result = parse_apng(path)
        assert len(result.frames) == 2
