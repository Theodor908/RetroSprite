"""Tests for PNG sequence and sprite sheet import parsers."""
import pytest
import tempfile
import os
import json
from PIL import Image


class TestPngSequence:
    def test_parse_png_sequence(self):
        from src.sequence_import import parse_png_sequence
        tmpdir = tempfile.mkdtemp()
        paths = []
        for i in range(4):
            p = os.path.join(tmpdir, f"frame_{i:03d}.png")
            img = Image.new("RGBA", (8, 8), (i * 60, 0, 0, 255))
            img.save(p)
            paths.append(p)
        result = parse_png_sequence(paths)
        assert len(result.frames) == 4
        assert result.width == 8
        assert result.height == 8
        assert result.durations == [100, 100, 100, 100]
        assert result.source_path == tmpdir

    def test_parse_png_sequence_natural_sort(self):
        from src.sequence_import import scan_folder_for_pngs
        tmpdir = tempfile.mkdtemp()
        for name in ["frame_1.png", "frame_2.png", "frame_10.png", "frame_20.png"]:
            Image.new("RGBA", (4, 4), (255, 0, 0, 255)).save(
                os.path.join(tmpdir, name))
        paths = scan_folder_for_pngs(tmpdir)
        names = [os.path.basename(p) for p in paths]
        assert names == ["frame_1.png", "frame_2.png", "frame_10.png", "frame_20.png"]

    def test_parse_png_sequence_empty_raises(self):
        from src.sequence_import import parse_png_sequence
        with pytest.raises(ValueError, match="No frames"):
            parse_png_sequence([])


class TestSpriteSheetJson:
    def test_parse_sprite_sheet_json(self):
        from src.sequence_import import parse_sprite_sheet_json
        tmpdir = tempfile.mkdtemp()
        sheet = Image.new("RGBA", (16, 8), (0, 0, 0, 0))
        sheet.paste(Image.new("RGBA", (8, 8), (255, 0, 0, 255)), (0, 0))
        sheet.paste(Image.new("RGBA", (8, 8), (0, 255, 0, 255)), (8, 0))
        png_path = os.path.join(tmpdir, "sheet.png")
        sheet.save(png_path)
        meta = {
            "frames": [
                {"x": 0, "y": 0, "w": 8, "h": 8, "duration": 50},
                {"x": 8, "y": 0, "w": 8, "h": 8, "duration": 200},
            ],
            "size": {"w": 8, "h": 8},
            "scale": 1,
        }
        json_path = os.path.join(tmpdir, "sheet.json")
        with open(json_path, "w") as f:
            json.dump(meta, f)
        result = parse_sprite_sheet_json(png_path, json_path)
        assert len(result.frames) == 2
        assert result.width == 8
        assert result.height == 8
        assert result.durations == [50, 200]

    def test_parse_sprite_sheet_json_durations(self):
        from src.sequence_import import parse_sprite_sheet_json
        tmpdir = tempfile.mkdtemp()
        sheet = Image.new("RGBA", (12, 4), (0, 0, 0, 0))
        png_path = os.path.join(tmpdir, "sheet.png")
        sheet.save(png_path)
        meta = {
            "frames": [
                {"x": 0, "y": 0, "w": 4, "h": 4, "duration": 33},
                {"x": 4, "y": 0, "w": 4, "h": 4, "duration": 66},
                {"x": 8, "y": 0, "w": 4, "h": 4, "duration": 99},
            ],
            "size": {"w": 4, "h": 4},
            "scale": 1,
        }
        json_path = os.path.join(tmpdir, "sheet.json")
        with open(json_path, "w") as f:
            json.dump(meta, f)
        result = parse_sprite_sheet_json(png_path, json_path)
        assert result.durations == [33, 66, 99]


class TestSpriteSheetGrid:
    def test_parse_sprite_sheet_grid(self):
        from src.sequence_import import parse_sprite_sheet_grid
        tmpdir = tempfile.mkdtemp()
        sheet = Image.new("RGBA", (32, 24), (0, 0, 0, 0))
        for row in range(3):
            for col in range(4):
                color = (col * 60, row * 80, 0, 255)
                cell = Image.new("RGBA", (8, 8), color)
                sheet.paste(cell, (col * 8, row * 8))
        path = os.path.join(tmpdir, "grid.png")
        sheet.save(path)
        result = parse_sprite_sheet_grid(path, cols=4, rows=3,
                                         frame_w=8, frame_h=8)
        assert len(result.frames) == 12
        assert result.width == 8
        assert result.height == 8
        assert result.durations == [100] * 12
        px = result.frames[0].getpixel((0, 0))
        assert px == (0, 0, 0, 255)
        px = result.frames[1].getpixel((0, 0))
        assert px == (60, 0, 0, 255)

    def test_parse_sprite_sheet_grid_empty_raises(self):
        from src.sequence_import import parse_sprite_sheet_grid
        tmpdir = tempfile.mkdtemp()
        sheet = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
        path = os.path.join(tmpdir, "tiny.png")
        sheet.save(path)
        with pytest.raises(ValueError, match="No frames"):
            parse_sprite_sheet_grid(path, cols=0, rows=0,
                                    frame_w=8, frame_h=8)
