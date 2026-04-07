# Import/Export Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close all 5 import/export parity gaps (GIF, APNG, WebP, PNG sequence, sprite sheet) so RetroSprite can import every animated format it exports.

**Architecture:** Hybrid pipeline — thin format-specific parsers all produce a shared `ImportedAnimation` dataclass, a shared Tkinter import dialog collects user preferences (`ImportSettings`), and a single `build_timeline_from_import()` function constructs or modifies the timeline. Format-specific pre-dialogs handle sprite sheet grid config and PNG sequence file selection.

**Tech Stack:** Python 3.8+, Pillow (ImageSequence, Image), NumPy, Tkinter, json, os, re

**Spec:** `docs/superpowers/specs/2026-04-06-import-parity-design.md`

---

### Task 1: Fix sprite sheet export duration bug

**Files:**
- Modify: `src/export.py:38`
- Test: `tests/test_export.py`

This is a prerequisite — the existing export hardcodes `"duration": 100` instead of using the actual frame duration. Without this fix, roundtripping sprite sheets will silently lose timing data.

- [ ] **Step 1: Write failing test**

Add to `tests/test_export.py`:

```python
def test_sprite_sheet_preserves_frame_duration(self):
    tl = AnimationTimeline(8, 8)
    tl.add_frame()
    tl.get_frame_obj(0).duration_ms = 50
    tl.get_frame_obj(1).duration_ms = 200
    sheet, meta = build_sprite_sheet(tl, scale=1)
    assert meta["frames"][0]["duration"] == 50
    assert meta["frames"][1]["duration"] == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_export.py::TestSpriteSheet::test_sprite_sheet_preserves_frame_duration -v`
Expected: FAIL — both durations will be 100

- [ ] **Step 3: Fix the hardcoded duration**

In `src/export.py`, line 38, change:

```python
            "duration": 100,
```

to:

```python
            "duration": timeline.get_frame_obj(i).duration_ms,
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_export.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/export.py tests/test_export.py
git commit -m "fix: sprite sheet export now preserves per-frame duration_ms"
```

---

### Task 2: ImportedAnimation dataclass and GIF parser

**Files:**
- Create: `src/animated_import.py`
- Create: `tests/test_animated_import.py`

- [ ] **Step 1: Write failing tests for GIF parser**

Create `tests/test_animated_import.py`:

```python
"""Tests for animated format import parsers and timeline builder."""
import pytest
import tempfile
import os
from PIL import Image


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
        # 3 frames: red, green, blue — each 4x4
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
        # Create a GIF without explicit duration info
        path = os.path.join(tempfile.mkdtemp(), "test.gif")
        img = Image.new("P", (4, 4), 1)
        img.save(path)
        result = parse_gif(path)
        assert result.durations == [100]  # default

    def test_parse_gif_empty_raises(self):
        from src.animated_import import parse_gif
        # Write a corrupted/non-GIF file with .gif extension
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_animated_import.py::TestParseGif -v`
Expected: FAIL — `src.animated_import` does not exist

- [ ] **Step 3: Implement ImportedAnimation and parse_gif**

Create `src/animated_import.py`:

```python
"""Animated format import (GIF, APNG, WebP) and timeline builder."""
from __future__ import annotations
from dataclasses import dataclass
from PIL import Image, ImageSequence


@dataclass
class ImportedAnimation:
    """Common structure produced by all format parsers."""
    frames: list[Image.Image]
    durations: list[int]
    width: int
    height: int
    palette: list[tuple[int, int, int, int]] | None
    source_path: str


@dataclass
class ImportSettings:
    """User choices from the import dialog."""
    mode: str       # "new_project" or "insert"
    resize: str     # "match", "scale", "crop"
    timing: str     # "original" or "project_fps"


def _extract_palette(img: Image.Image) -> list[tuple[int, int, int, int]] | None:
    """Extract palette colors from a P-mode image, or None."""
    if img.mode != "P":
        return None
    raw = img.getpalette()
    if raw is None:
        return None
    colors = []
    for i in range(0, min(len(raw), 768), 3):
        colors.append((raw[i], raw[i + 1], raw[i + 2], 255))
    return colors if colors else None


def parse_gif(path: str) -> ImportedAnimation:
    """Parse an animated GIF into ImportedAnimation.

    Handles GIF disposal methods by maintaining a running canvas
    and compositing each frame according to its disposal method.
    """
    img = Image.open(path)
    if img.format != "GIF":
        raise ValueError(f"Not a GIF file: {path}")

    palette = _extract_palette(img)
    width, height = img.size
    frames: list[Image.Image] = []
    durations: list[int] = []

    # Running canvas for proper disposal handling
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))

    for frame_idx, frame in enumerate(ImageSequence.Iterator(img)):
        # Get disposal method (0=unspecified, 1=leave, 2=restore bg, 3=restore prev)
        disposal = getattr(img, "disposal_method", 0)

        # Save canvas state before pasting (for disposal=3)
        prev_canvas = canvas.copy()

        # Paste current frame onto canvas
        rgba_frame = frame.convert("RGBA")
        canvas.paste(rgba_frame, (0, 0), rgba_frame)

        # Store the composited result
        frames.append(canvas.copy())

        # Get duration (default 100ms if missing or 0)
        dur = frame.info.get("duration", 100)
        if dur <= 0:
            dur = 100
        durations.append(dur)

        # Apply disposal for next frame
        if disposal == 2:
            # Restore to background (transparent)
            canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        elif disposal == 3:
            # Restore to previous
            canvas = prev_canvas

        # disposal 0 or 1: leave canvas as-is

    if not frames:
        raise ValueError(f"No frames found in GIF: {path}")

    return ImportedAnimation(
        frames=frames,
        durations=durations,
        width=width,
        height=height,
        palette=palette,
        source_path=path,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_animated_import.py::TestParseGif -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/animated_import.py tests/test_animated_import.py
git commit -m "feat: add ImportedAnimation dataclass and GIF parser with disposal handling"
```

---

### Task 3: APNG and WebP parsers

**Files:**
- Modify: `src/animated_import.py`
- Modify: `tests/test_animated_import.py`

- [ ] **Step 1: Write failing tests for APNG and WebP parsers**

Add to `tests/test_animated_import.py`:

```python
class TestParseApng:
    def test_parse_apng_frames(self):
        from src.animated_import import parse_apng
        # Create a 3-frame APNG programmatically
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
        # Save APNG with .png extension
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_animated_import.py::TestParseApng tests/test_animated_import.py::TestParseWebp -v`
Expected: FAIL — `parse_apng` and `parse_webp` not defined

- [ ] **Step 3: Implement parse_apng and parse_webp**

Add to `src/animated_import.py`, after `parse_gif`:

```python
def _parse_animated_image(path: str, format_name: str) -> ImportedAnimation:
    """Shared parser for APNG and WebP animated images.

    Both formats are handled identically by Pillow's ImageSequence.
    """
    img = Image.open(path)
    width, height = img.size
    n_frames = getattr(img, "n_frames", 1)

    frames: list[Image.Image] = []
    durations: list[int] = []

    for frame in ImageSequence.Iterator(img):
        frames.append(frame.convert("RGBA").copy())
        dur = frame.info.get("duration", 100)
        if dur <= 0:
            dur = 100
        durations.append(dur)

    if not frames:
        raise ValueError(f"No frames found in {format_name} file: {path}")

    return ImportedAnimation(
        frames=frames,
        durations=durations,
        width=width,
        height=height,
        palette=None,
        source_path=path,
    )


def parse_apng(path: str) -> ImportedAnimation:
    """Parse an animated PNG (APNG) into ImportedAnimation."""
    return _parse_animated_image(path, "APNG")


def parse_webp(path: str) -> ImportedAnimation:
    """Parse an animated WebP into ImportedAnimation."""
    return _parse_animated_image(path, "WebP")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_animated_import.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/animated_import.py tests/test_animated_import.py
git commit -m "feat: add APNG and WebP parsers using shared ImageSequence logic"
```

---

### Task 4: PNG sequence parser

**Files:**
- Create: `src/sequence_import.py`
- Create: `tests/test_sequence_import.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_sequence_import.py`:

```python
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
        # Create files with numbers that would sort wrong lexically
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_sequence_import.py::TestPngSequence -v`
Expected: FAIL — `src.sequence_import` does not exist

- [ ] **Step 3: Implement PNG sequence parser**

Create `src/sequence_import.py`:

```python
"""PNG sequence and sprite sheet import parsers."""
from __future__ import annotations
import json
import os
import re
from PIL import Image
from src.animated_import import ImportedAnimation


def _natural_sort_key(path: str):
    """Sort key that handles embedded numbers naturally.

    'frame_2.png' sorts before 'frame_10.png'.
    """
    name = os.path.basename(path)
    return [int(c) if c.isdigit() else c.lower()
            for c in re.split(r'(\d+)', name)]


def scan_folder_for_pngs(folder: str) -> list[str]:
    """Scan a folder for numbered PNG files, return naturally sorted paths."""
    paths = []
    for name in os.listdir(folder):
        if name.lower().endswith(".png"):
            paths.append(os.path.join(folder, name))
    paths.sort(key=_natural_sort_key)
    return paths


def parse_png_sequence(paths: list[str]) -> ImportedAnimation:
    """Parse a list of PNG file paths into ImportedAnimation.

    Args:
        paths: Pre-sorted list of PNG file paths.

    Returns:
        ImportedAnimation with all frames loaded, durations defaulting to 100ms.
    """
    if not paths:
        raise ValueError("No frames provided for PNG sequence import")

    frames: list[Image.Image] = []
    for p in paths:
        img = Image.open(p).convert("RGBA")
        frames.append(img)

    width, height = frames[0].size
    durations = [100] * len(frames)
    source = os.path.dirname(paths[0]) if paths else ""

    return ImportedAnimation(
        frames=frames,
        durations=durations,
        width=width,
        height=height,
        palette=None,
        source_path=source,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_sequence_import.py::TestPngSequence -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/sequence_import.py tests/test_sequence_import.py
git commit -m "feat: add PNG sequence parser with natural sort folder scanning"
```

---

### Task 5: Sprite sheet parsers (JSON + grid)

**Files:**
- Modify: `src/sequence_import.py`
- Modify: `tests/test_sequence_import.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_sequence_import.py`:

```python
class TestSpriteSheetJson:
    def test_parse_sprite_sheet_json(self):
        from src.sequence_import import parse_sprite_sheet_json
        tmpdir = tempfile.mkdtemp()
        # Create a 2-frame horizontal sprite sheet (16x8, each frame 8x8)
        sheet = Image.new("RGBA", (16, 8), (0, 0, 0, 0))
        sheet.paste(Image.new("RGBA", (8, 8), (255, 0, 0, 255)), (0, 0))
        sheet.paste(Image.new("RGBA", (8, 8), (0, 255, 0, 255)), (8, 0))
        png_path = os.path.join(tmpdir, "sheet.png")
        sheet.save(png_path)
        # Create JSON sidecar
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
        # 4x3 grid of 8x8 frames = 32x24 sheet with 12 frames
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
        # Verify first frame is red-ish (col=0, row=0 → (0,0,0,255))
        px = result.frames[0].getpixel((0, 0))
        assert px == (0, 0, 0, 255)
        # Verify second frame (col=1, row=0 → (60,0,0,255))
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_sequence_import.py::TestSpriteSheetJson tests/test_sequence_import.py::TestSpriteSheetGrid -v`
Expected: FAIL — functions not defined

- [ ] **Step 3: Implement sprite sheet parsers**

Add to `src/sequence_import.py`:

```python
def parse_sprite_sheet_json(png_path: str, json_path: str) -> ImportedAnimation:
    """Parse a sprite sheet using RetroSprite's JSON sidecar metadata.

    The JSON contains a "frames" array with {x, y, w, h, duration} per frame
    and a "size" object with {w, h} for the original frame dimensions.
    """
    with open(json_path, "r") as f:
        meta = json.load(f)

    sheet = Image.open(png_path).convert("RGBA")
    frame_defs = meta["frames"]
    if not frame_defs:
        raise ValueError(f"No frames defined in JSON: {json_path}")

    scale = meta.get("scale", 1)
    orig_w = meta["size"]["w"]
    orig_h = meta["size"]["h"]

    frames: list[Image.Image] = []
    durations: list[int] = []

    for fd in frame_defs:
        region = sheet.crop((fd["x"], fd["y"],
                             fd["x"] + fd["w"], fd["y"] + fd["h"]))
        # If exported at scale > 1, resize back to original dimensions
        if scale > 1:
            region = region.resize((orig_w, orig_h), Image.NEAREST)
        frames.append(region)
        durations.append(fd.get("duration", 100))

    return ImportedAnimation(
        frames=frames,
        durations=durations,
        width=orig_w,
        height=orig_h,
        palette=None,
        source_path=png_path,
    )


def parse_sprite_sheet_grid(path: str, cols: int, rows: int,
                            frame_w: int, frame_h: int) -> ImportedAnimation:
    """Parse a sprite sheet by slicing it into a uniform grid.

    Frames are read left-to-right, top-to-bottom.
    """
    if cols <= 0 or rows <= 0:
        raise ValueError("No frames: cols and rows must be > 0")

    sheet = Image.open(path).convert("RGBA")
    frames: list[Image.Image] = []

    for row in range(rows):
        for col in range(cols):
            x = col * frame_w
            y = row * frame_h
            if x + frame_w > sheet.width or y + frame_h > sheet.height:
                continue  # skip incomplete cells at edges
            region = sheet.crop((x, y, x + frame_w, y + frame_h))
            frames.append(region)

    if not frames:
        raise ValueError(f"No frames extracted from sprite sheet: {path}")

    durations = [100] * len(frames)

    return ImportedAnimation(
        frames=frames,
        durations=durations,
        width=frame_w,
        height=frame_h,
        palette=None,
        source_path=path,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_sequence_import.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/sequence_import.py tests/test_sequence_import.py
git commit -m "feat: add sprite sheet JSON and grid parsers"
```

---

### Task 6: Timeline builder (build_timeline_from_import)

**Files:**
- Modify: `src/animated_import.py`
- Modify: `tests/test_animated_import.py`

- [ ] **Step 1: Write failing tests for new project mode**

Add to `tests/test_animated_import.py`:

```python
from src.animated_import import (
    ImportedAnimation, ImportSettings, build_timeline_from_import,
)
from src.animation import AnimationTimeline


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
        # 1000 / 10 fps = 100ms per frame
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_animated_import.py::TestBuildNewProject -v`
Expected: FAIL — `build_timeline_from_import` not defined

- [ ] **Step 3: Implement build_timeline_from_import (new project mode)**

Add to `src/animated_import.py`:

```python
from src.animation import AnimationTimeline, Frame
from src.layer import Layer
from src.pixel_data import PixelGrid
import numpy as np


def build_timeline_from_import(
    animation: ImportedAnimation,
    settings: ImportSettings,
    existing_timeline: AnimationTimeline | None = None,
    project_fps: int = 10,
) -> tuple[AnimationTimeline, list[tuple[int, int, int, int]] | None]:
    """Build or modify a timeline from imported animation data.

    Returns:
        (timeline, palette_colors) — palette_colors is None in insert mode.
    """
    if settings.mode == "new_project":
        return _build_new_project(animation, settings, project_fps)
    else:
        return _build_insert(animation, settings, existing_timeline, project_fps)


def _compute_duration(settings: ImportSettings, original_ms: int,
                      project_fps: int) -> int:
    if settings.timing == "project_fps":
        return max(1, 1000 // project_fps)
    return original_ms


def _build_new_project(
    animation: ImportedAnimation,
    settings: ImportSettings,
    project_fps: int,
) -> tuple[AnimationTimeline, list[tuple[int, int, int, int]] | None]:
    timeline = AnimationTimeline(animation.width, animation.height)
    timeline._frames.clear()

    for i, (pil_img, dur) in enumerate(zip(animation.frames, animation.durations)):
        frame = Frame(animation.width, animation.height,
                      name=f"Frame {i + 1}")
        frame.layers.clear()
        layer = Layer("Layer 1", animation.width, animation.height)
        layer.pixels = PixelGrid.from_pil_image(pil_img)
        frame.layers.append(layer)
        frame.active_layer_index = 0
        frame.duration_ms = _compute_duration(settings, dur, project_fps)
        timeline._frames.append(frame)

    return timeline, animation.palette
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_animated_import.py::TestBuildNewProject -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/animated_import.py tests/test_animated_import.py
git commit -m "feat: add build_timeline_from_import for new project mode"
```

---

### Task 7: Timeline builder — insert mode

**Files:**
- Modify: `src/animated_import.py`
- Modify: `tests/test_animated_import.py`

- [ ] **Step 1: Write failing tests for insert mode**

Add to `tests/test_animated_import.py`:

```python
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
        # Original 2 + 3 inserted = 5
        assert timeline.frame_count == 5
        # Inserted after index 0, so at positions 1, 2, 3
        # Original frame 1 is now at index 4

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
        # Inserted frame should be 8x8
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
        # Paint something in the existing frame so we can verify it gets resized
        existing.current_frame_obj().layers[0].pixels.set_pixel(0, 0, (255, 0, 0, 255))
        anim = self._make_animation(1, w=16, h=16)
        settings = ImportSettings(mode="insert", resize="match",
                                  timing="original")
        timeline, _ = build_timeline_from_import(
            anim, settings, existing_timeline=existing)
        assert timeline.width == 16
        assert timeline.height == 16
        # Existing frame should also be 16x16 now
        assert existing.get_frame_obj(0).layers[0].pixels.width == 16
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_animated_import.py::TestBuildInsert -v`
Expected: FAIL — `_build_insert` not implemented

- [ ] **Step 3: Implement insert mode**

Add to `src/animated_import.py`, replacing the placeholder in `build_timeline_from_import`:

```python
def _resize_frame_pixels(frame: Frame, new_w: int, new_h: int) -> None:
    """Resize all layers in a frame to new dimensions (pad with transparent)."""
    for layer in frame.layers:
        old_img = layer.pixels.to_pil_image()
        new_img = Image.new("RGBA", (new_w, new_h), (0, 0, 0, 0))
        new_img.paste(old_img, (0, 0))
        layer.pixels = PixelGrid.from_pil_image(new_img)
    frame.width = new_w
    frame.height = new_h


def _build_insert(
    animation: ImportedAnimation,
    settings: ImportSettings,
    existing_timeline: AnimationTimeline,
    project_fps: int,
) -> tuple[AnimationTimeline, None]:
    canvas_w = existing_timeline.width
    canvas_h = existing_timeline.height

    # Handle resize strategy
    if settings.resize == "match":
        # Resize canvas and all existing frames to imported dimensions
        new_w, new_h = animation.width, animation.height
        if new_w != canvas_w or new_h != canvas_h:
            for frame_obj in existing_timeline._frames:
                _resize_frame_pixels(frame_obj, new_w, new_h)
            existing_timeline.width = new_w
            existing_timeline.height = new_h
            canvas_w, canvas_h = new_w, new_h

    insert_after = existing_timeline.current_index

    for i, (pil_img, dur) in enumerate(zip(animation.frames, animation.durations)):
        # Apply resize to imported frame
        if settings.resize == "scale" and (pil_img.size != (canvas_w, canvas_h)):
            pil_img = pil_img.resize((canvas_w, canvas_h), Image.NEAREST)
        elif settings.resize == "crop":
            # Center and crop
            cropped = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
            offset_x = (canvas_w - animation.width) // 2
            offset_y = (canvas_h - animation.height) // 2
            cropped.paste(pil_img, (offset_x, offset_y))
            pil_img = cropped

        frame = Frame(canvas_w, canvas_h,
                      name=f"Imported {i + 1}")
        frame.layers.clear()
        layer = Layer("Layer 1", canvas_w, canvas_h)
        layer.pixels = PixelGrid.from_pil_image(pil_img)
        frame.layers.append(layer)
        frame.active_layer_index = 0
        frame.duration_ms = _compute_duration(settings, dur, project_fps)

        idx = insert_after + 1 + i
        existing_timeline._frames.insert(idx, frame)

    existing_timeline.sync_layers()
    return existing_timeline, None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_animated_import.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/animated_import.py tests/test_animated_import.py
git commit -m "feat: add insert mode to build_timeline_from_import with resize strategies"
```

---

### Task 8: Shared import dialog

**Files:**
- Create: `src/ui/import_dialog.py`

This is a Tkinter dialog — no automated tests (UI components follow the existing ExportDialog pattern which also has no unit tests). Styling follows `src/ui/export_dialog.py` conventions exactly.

- [ ] **Step 1: Create the import dialog**

Create `src/ui/import_dialog.py`:

```python
"""Import dialogs for RetroSprite — animated, sprite sheet, PNG sequence."""
from __future__ import annotations
import os
import tkinter as tk
from tkinter import filedialog
from src.animated_import import ImportSettings
from src.ui.theme import (
    BG_DEEP, BG_PANEL, TEXT_PRIMARY, TEXT_SECONDARY,
    ACCENT_CYAN, ACCENT_MAGENTA, BUTTON_BG, BUTTON_HOVER,
)


class ImportDialog(tk.Toplevel):
    """Shared import options dialog shown after parsing an animated file.

    Collects: project mode, canvas resize strategy, timing preference.

    Usage:
        dialog = ImportDialog(parent, n_frames=12, src_w=64, src_h=48,
                              duration_range=(50, 200), source_name="explosion.gif",
                              canvas_w=32, canvas_h=32, project_fps=10)
        parent.wait_window(dialog)
        settings = dialog.result  # ImportSettings or None
    """

    def __init__(self, parent, *, n_frames: int, src_w: int, src_h: int,
                 duration_range: tuple[int, int], source_name: str,
                 canvas_w: int, canvas_h: int, project_fps: int):
        super().__init__(parent)
        self.title("Import Animation")
        self.configure(bg=BG_DEEP)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._src_w = src_w
        self._src_h = src_h
        self._canvas_w = canvas_w
        self._canvas_h = canvas_h
        self._project_fps = project_fps
        self.result: ImportSettings | None = None

        self._build_ui(n_frames, source_name, duration_range)

        # Center on parent
        self.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        w = self.winfo_width()
        h = self.winfo_height()
        self.geometry(f"+{px + (pw - w) // 2}+{py + (ph - h) // 2}")

    def _build_ui(self, n_frames, source_name, duration_range):
        font = ("Consolas", 9)
        pad = {"padx": 10, "pady": 4}

        # Source info
        info = f"{source_name}  ({n_frames} frames, {self._src_w}\u00d7{self._src_h})"
        tk.Label(self, text=info, bg=BG_DEEP, fg=ACCENT_CYAN,
                 font=("Consolas", 9, "bold")).pack(**pad, anchor="w")

        # --- Project Mode ---
        tk.Label(self, text="Project Mode", bg=BG_DEEP, fg=TEXT_SECONDARY,
                 font=font).pack(**pad, anchor="w")
        self._mode_var = tk.StringVar(value="new_project")
        for val, label in [("new_project", "New Project (replaces current canvas)"),
                           ("insert", "Insert as Frames (after current frame)")]:
            tk.Radiobutton(
                self, text=label, variable=self._mode_var, value=val,
                bg=BG_DEEP, fg=TEXT_PRIMARY, selectcolor=BG_PANEL,
                activebackground=BG_DEEP, activeforeground=ACCENT_CYAN,
                font=font, command=self._on_mode_change,
            ).pack(padx=20, anchor="w")

        # --- Canvas Size (insert mode only) ---
        self._resize_frame = tk.Frame(self, bg=BG_DEEP)
        self._resize_frame.pack(fill="x", **pad)
        tk.Label(self._resize_frame, text="Canvas Size", bg=BG_DEEP,
                 fg=TEXT_SECONDARY, font=font).pack(anchor="w")
        self._resize_var = tk.StringVar(value="scale")
        for val, label in [
            ("match", f"Resize canvas to match ({self._src_w}\u00d7{self._src_h})"),
            ("scale", f"Scale import to fit canvas ({self._canvas_w}\u00d7{self._canvas_h})"),
            ("crop", "Center and crop to canvas"),
        ]:
            tk.Radiobutton(
                self._resize_frame, text=label, variable=self._resize_var,
                value=val, bg=BG_DEEP, fg=TEXT_PRIMARY, selectcolor=BG_PANEL,
                activebackground=BG_DEEP, activeforeground=ACCENT_CYAN,
                font=font,
            ).pack(padx=20, anchor="w")

        # --- Timing ---
        tk.Label(self, text="Timing", bg=BG_DEEP, fg=TEXT_SECONDARY,
                 font=font).pack(**pad, anchor="w")
        self._timing_var = tk.StringVar(value="original")
        min_d, max_d = duration_range
        fps_ms = max(1, 1000 // self._project_fps)
        for val, label in [
            ("original", f"Keep original timing ({min_d}\u2013{max_d}ms per frame)"),
            ("project_fps", f"Use project FPS ({fps_ms}ms per frame)"),
        ]:
            tk.Radiobutton(
                self, text=label, variable=self._timing_var, value=val,
                bg=BG_DEEP, fg=TEXT_PRIMARY, selectcolor=BG_PANEL,
                activebackground=BG_DEEP, activeforeground=ACCENT_CYAN,
                font=font,
            ).pack(padx=20, anchor="w")

        # --- Buttons ---
        btn_row = tk.Frame(self, bg=BG_DEEP)
        btn_row.pack(fill="x", pady=(12, 8), padx=10)
        cancel_btn = tk.Button(
            btn_row, text="Cancel", bg=BUTTON_BG, fg=TEXT_PRIMARY,
            font=font, relief="flat", padx=16, pady=4,
            command=self._on_cancel)
        cancel_btn.pack(side="right", padx=4)
        import_btn = tk.Button(
            btn_row, text="Import", bg=ACCENT_CYAN, fg=BG_DEEP,
            font=("Consolas", 9, "bold"), relief="flat", padx=16, pady=4,
            command=self._on_import)
        import_btn.pack(side="right", padx=4)

        self._on_mode_change()

    def _on_mode_change(self):
        if self._mode_var.get() == "new_project":
            for child in self._resize_frame.winfo_children():
                child.configure(state="disabled")
        else:
            for child in self._resize_frame.winfo_children():
                child.configure(state="normal")

    def _on_cancel(self):
        self.result = None
        self.destroy()

    def _on_import(self):
        self.result = ImportSettings(
            mode=self._mode_var.get(),
            resize=self._resize_var.get(),
            timing=self._timing_var.get(),
        )
        self.destroy()
```

- [ ] **Step 2: Manually verify the dialog renders**

Run: `python -c "import tkinter as tk; root=tk.Tk(); root.withdraw(); from src.ui.import_dialog import ImportDialog; d=ImportDialog(root, n_frames=12, src_w=64, src_h=48, duration_range=(50,200), source_name='test.gif', canvas_w=32, canvas_h=32, project_fps=10); root.mainloop()"`

Expected: Dialog appears with all three sections, radio buttons work, Cancel closes, Import closes with result.

- [ ] **Step 3: Commit**

```bash
git add src/ui/import_dialog.py
git commit -m "feat: add shared ImportDialog for animated format imports"
```

---

### Task 9: Sprite sheet and PNG sequence pre-dialogs

**Files:**
- Modify: `src/ui/import_dialog.py`

- [ ] **Step 1: Add SpriteSheetDialog**

Add to `src/ui/import_dialog.py`:

```python
class SpriteSheetDialog(tk.Toplevel):
    """Pre-dialog for sprite sheet import — JSON or manual grid config.

    Usage:
        dialog = SpriteSheetDialog(parent, png_path)
        parent.wait_window(dialog)
        result = dialog.result
        # result is ("json", json_path) or ("grid", cols, rows, fw, fh) or None
    """

    def __init__(self, parent, png_path: str):
        super().__init__(parent)
        self.title("Import Sprite Sheet")
        self.configure(bg=BG_DEEP)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._png_path = png_path
        self.result = None

        self._build_ui()

        self.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        w = self.winfo_width()
        h = self.winfo_height()
        self.geometry(f"+{px + (pw - w) // 2}+{py + (ph - h) // 2}")

    def _build_ui(self):
        font = ("Consolas", 9)
        pad = {"padx": 10, "pady": 4}

        self._mode_var = tk.StringVar(value="json")

        # JSON mode
        tk.Radiobutton(
            self, text="Use JSON metadata (RetroSprite format)",
            variable=self._mode_var, value="json",
            bg=BG_DEEP, fg=TEXT_PRIMARY, selectcolor=BG_PANEL,
            activebackground=BG_DEEP, activeforeground=ACCENT_CYAN,
            font=font, command=self._on_mode_change,
        ).pack(**pad, anchor="w")

        json_row = tk.Frame(self, bg=BG_DEEP)
        json_row.pack(fill="x", padx=20, pady=2)
        self._json_path_var = tk.StringVar(value="")
        self._json_browse_btn = tk.Button(
            json_row, text="Browse .json", bg=BUTTON_BG, fg=TEXT_PRIMARY,
            font=font, relief="flat", command=self._browse_json)
        self._json_browse_btn.pack(side="left")
        self._json_label = tk.Label(
            json_row, textvariable=self._json_path_var,
            bg=BG_DEEP, fg=TEXT_SECONDARY, font=font)
        self._json_label.pack(side="left", padx=8)

        # Grid mode
        tk.Radiobutton(
            self, text="Manual grid",
            variable=self._mode_var, value="grid",
            bg=BG_DEEP, fg=TEXT_PRIMARY, selectcolor=BG_PANEL,
            activebackground=BG_DEEP, activeforeground=ACCENT_CYAN,
            font=font, command=self._on_mode_change,
        ).pack(**pad, anchor="w")

        grid_frame = tk.Frame(self, bg=BG_DEEP)
        grid_frame.pack(fill="x", padx=20, pady=2)
        self._grid_widgets = []
        self._cols_var = tk.IntVar(value=4)
        self._rows_var = tk.IntVar(value=3)
        self._fw_var = tk.IntVar(value=32)
        self._fh_var = tk.IntVar(value=32)
        for label_text, var in [("Columns:", self._cols_var),
                                ("Rows:", self._rows_var),
                                ("Frame W:", self._fw_var),
                                ("Frame H:", self._fh_var)]:
            lbl = tk.Label(grid_frame, text=label_text, bg=BG_DEEP,
                           fg=TEXT_PRIMARY, font=font)
            lbl.pack(side="left", padx=(4, 0))
            spin = tk.Spinbox(grid_frame, from_=1, to=999, width=4,
                              textvariable=var, font=font,
                              bg=BG_PANEL, fg=TEXT_PRIMARY,
                              buttonbackground=BUTTON_BG)
            spin.pack(side="left", padx=(0, 4))
            self._grid_widgets.extend([lbl, spin])

        # Preview
        self._preview_var = tk.StringVar(value="")
        tk.Label(self, textvariable=self._preview_var, bg=BG_DEEP,
                 fg=ACCENT_MAGENTA, font=font).pack(**pad, anchor="w")

        # Buttons
        btn_row = tk.Frame(self, bg=BG_DEEP)
        btn_row.pack(fill="x", pady=(12, 8), padx=10)
        tk.Button(
            btn_row, text="Cancel", bg=BUTTON_BG, fg=TEXT_PRIMARY,
            font=font, relief="flat", padx=16, pady=4,
            command=self._on_cancel).pack(side="right", padx=4)
        tk.Button(
            btn_row, text="Next \u2192", bg=ACCENT_CYAN, fg=BG_DEEP,
            font=("Consolas", 9, "bold"), relief="flat", padx=16, pady=4,
            command=self._on_next).pack(side="right", padx=4)

        self._on_mode_change()

    def _on_mode_change(self):
        is_json = self._mode_var.get() == "json"
        state_json = "normal" if is_json else "disabled"
        state_grid = "disabled" if is_json else "normal"
        self._json_browse_btn.configure(state=state_json)
        for w in self._grid_widgets:
            w.configure(state=state_grid)

    def _browse_json(self):
        path = filedialog.askopenfilename(
            parent=self, filetypes=[("JSON files", "*.json")],
            initialdir=os.path.dirname(self._png_path))
        if path:
            self._json_path_var.set(os.path.basename(path))
            self._json_full_path = path

    def _on_cancel(self):
        self.result = None
        self.destroy()

    def _on_next(self):
        if self._mode_var.get() == "json":
            json_path = getattr(self, "_json_full_path", "")
            if not json_path:
                return  # no file selected
            self.result = ("json", json_path)
        else:
            self.result = ("grid", self._cols_var.get(), self._rows_var.get(),
                           self._fw_var.get(), self._fh_var.get())
        self.destroy()


class PngSequenceDialog(tk.Toplevel):
    """Pre-dialog for PNG sequence import — folder scan or multi-select.

    Usage:
        dialog = PngSequenceDialog(parent)
        parent.wait_window(dialog)
        result = dialog.result  # list[str] of PNG paths, or None
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Import PNG Sequence")
        self.configure(bg=BG_DEEP)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.result: list[str] | None = None
        self._paths: list[str] = []

        self._build_ui()

        self.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        w = self.winfo_width()
        h = self.winfo_height()
        self.geometry(f"+{px + (pw - w) // 2}+{py + (ph - h) // 2}")

    def _build_ui(self):
        font = ("Consolas", 9)
        pad = {"padx": 10, "pady": 4}

        self._mode_var = tk.StringVar(value="folder")

        # Folder scan mode
        tk.Radiobutton(
            self, text="Scan folder for numbered PNGs",
            variable=self._mode_var, value="folder",
            bg=BG_DEEP, fg=TEXT_PRIMARY, selectcolor=BG_PANEL,
            activebackground=BG_DEEP, activeforeground=ACCENT_CYAN,
            font=font,
        ).pack(**pad, anchor="w")

        folder_row = tk.Frame(self, bg=BG_DEEP)
        folder_row.pack(fill="x", padx=20, pady=2)
        self._folder_btn = tk.Button(
            folder_row, text="Browse Folder", bg=BUTTON_BG, fg=TEXT_PRIMARY,
            font=font, relief="flat", command=self._browse_folder)
        self._folder_btn.pack(side="left")
        self._folder_info = tk.StringVar(value="")
        tk.Label(folder_row, textvariable=self._folder_info,
                 bg=BG_DEEP, fg=TEXT_SECONDARY, font=font).pack(side="left", padx=8)

        # Multi-select mode
        tk.Radiobutton(
            self, text="Select individual files",
            variable=self._mode_var, value="files",
            bg=BG_DEEP, fg=TEXT_PRIMARY, selectcolor=BG_PANEL,
            activebackground=BG_DEEP, activeforeground=ACCENT_CYAN,
            font=font,
        ).pack(**pad, anchor="w")

        files_row = tk.Frame(self, bg=BG_DEEP)
        files_row.pack(fill="x", padx=20, pady=2)
        self._files_btn = tk.Button(
            files_row, text="Browse Files", bg=BUTTON_BG, fg=TEXT_PRIMARY,
            font=font, relief="flat", command=self._browse_files)
        self._files_btn.pack(side="left")
        self._files_info = tk.StringVar(value="")
        tk.Label(files_row, textvariable=self._files_info,
                 bg=BG_DEEP, fg=TEXT_SECONDARY, font=font).pack(side="left", padx=8)

        # Buttons
        btn_row = tk.Frame(self, bg=BG_DEEP)
        btn_row.pack(fill="x", pady=(12, 8), padx=10)
        tk.Button(
            btn_row, text="Cancel", bg=BUTTON_BG, fg=TEXT_PRIMARY,
            font=font, relief="flat", padx=16, pady=4,
            command=self._on_cancel).pack(side="right", padx=4)
        tk.Button(
            btn_row, text="Next \u2192", bg=ACCENT_CYAN, fg=BG_DEEP,
            font=("Consolas", 9, "bold"), relief="flat", padx=16, pady=4,
            command=self._on_next).pack(side="right", padx=4)

    def _browse_folder(self):
        from src.sequence_import import scan_folder_for_pngs
        folder = filedialog.askdirectory(parent=self)
        if folder:
            self._paths = scan_folder_for_pngs(folder)
            if self._paths:
                first = os.path.basename(self._paths[0])
                last = os.path.basename(self._paths[-1])
                self._folder_info.set(
                    f"Found: {first} ... {last} ({len(self._paths)} files)")
            else:
                self._folder_info.set("No PNG files found")

    def _browse_files(self):
        from src.sequence_import import _natural_sort_key
        files = filedialog.askopenfilenames(
            parent=self, filetypes=[("PNG files", "*.png")])
        if files:
            self._paths = sorted(files, key=_natural_sort_key)
            self._files_info.set(f"{len(self._paths)} files selected")

    def _on_cancel(self):
        self.result = None
        self.destroy()

    def _on_next(self):
        if self._paths:
            self.result = self._paths
        self.destroy()
```

- [ ] **Step 2: Manually verify both dialogs render**

Run: `python -c "import tkinter as tk; root=tk.Tk(); root.withdraw(); from src.ui.import_dialog import SpriteSheetDialog; d=SpriteSheetDialog(root, '/tmp/test.png'); root.mainloop()"`

Run: `python -c "import tkinter as tk; root=tk.Tk(); root.withdraw(); from src.ui.import_dialog import PngSequenceDialog; d=PngSequenceDialog(root); root.mainloop()"`

Expected: Both dialogs render correctly with radio buttons, browse buttons, Next/Cancel.

- [ ] **Step 3: Commit**

```bash
git add src/ui/import_dialog.py
git commit -m "feat: add SpriteSheetDialog and PngSequenceDialog pre-dialogs"
```

---

### Task 10: Menu wiring — _import_animation in file_ops.py

**Files:**
- Modify: `src/file_ops.py`
- Modify: `src/app.py:257`

- [ ] **Step 1: Add _import_animation to FileOpsMixin**

Add to `src/file_ops.py`, after the `_open_image` method (after line 168):

```python
    def _import_animation(self):
        """Import animated files (GIF, APNG, WebP, sprite sheet, PNG sequence)."""
        from src.ui.dialogs import show_error
        path = ask_open_file(
            self.root,
            filetypes=[
                ("Animated files", "*.gif;*.apng;*.webp"),
                ("PNG / Sprite Sheet", "*.png"),
                ("All files", "*.*"),
            ]
        )
        if not path:
            return

        ext = os.path.splitext(path)[1].lower()
        try:
            animation = self._parse_import_file(path, ext)
        except Exception as e:
            show_error(self.root, "Import Error", str(e))
            return

        if animation is None:
            return  # user cancelled a sub-dialog

        # Show shared import dialog
        from src.ui.import_dialog import ImportDialog
        dur_min = min(animation.durations)
        dur_max = max(animation.durations)
        dialog = ImportDialog(
            self.root,
            n_frames=len(animation.frames),
            src_w=animation.width,
            src_h=animation.height,
            duration_range=(dur_min, dur_max),
            source_name=os.path.basename(animation.source_path),
            canvas_w=self.timeline.width,
            canvas_h=self.timeline.height,
            project_fps=self.timeline.fps,
        )
        self.root.wait_window(dialog)
        settings = dialog.result
        if settings is None:
            return

        # Build timeline
        from src.animated_import import build_timeline_from_import
        try:
            if settings.mode == "new_project":
                if not self._check_save_before():
                    return
                timeline, palette_colors = build_timeline_from_import(
                    animation, settings, project_fps=self.timeline.fps)
                self.timeline = timeline
                self.api.timeline = self.timeline
                if palette_colors:
                    self.palette.colors = palette_colors
                    self.palette.selected_index = 0
                self._reset_state()
                self.root.title(
                    f"RetroSprite - {os.path.basename(path)}")
                self.right_panel.palette_panel.palette = self.palette
                self.right_panel.palette_panel.refresh()
                self.timeline_panel.set_timeline(self.timeline)
                self._refresh_all()
            else:
                self._push_undo()
                build_timeline_from_import(
                    animation, settings,
                    existing_timeline=self.timeline,
                    project_fps=self.timeline.fps)
                self.timeline_panel.set_timeline(self.timeline)
                self._refresh_all()
        except Exception as e:
            show_error(self.root, "Import Error", str(e))

    def _parse_import_file(self, path: str, ext: str):
        """Parse a file into ImportedAnimation based on extension.

        Returns ImportedAnimation or None if user cancels a sub-dialog.
        """
        from src.ui.dialogs import show_error

        if ext == ".gif":
            from src.animated_import import parse_gif
            return parse_gif(path)
        elif ext == ".apng":
            from src.animated_import import parse_apng
            return parse_apng(path)
        elif ext == ".webp":
            from src.animated_import import parse_webp
            return parse_webp(path)
        elif ext == ".png":
            return self._handle_png_import(path)
        else:
            raise ValueError(f"Unsupported format: {ext}")

    def _handle_png_import(self, path: str):
        """Handle .png files — detect APNG or show format chooser."""
        from PIL import Image as PILImage

        img = PILImage.open(path)
        n_frames = getattr(img, "n_frames", 1)
        img.close()

        if n_frames > 1:
            # It's an APNG
            from src.animated_import import parse_apng
            return parse_apng(path)

        # Ambiguous .png — ask user
        chooser = tk.Toplevel(self.root)
        chooser.title("PNG Import Type")
        chooser.configure(bg="#0d0d12")
        chooser.resizable(False, False)
        chooser.transient(self.root)
        chooser.grab_set()

        result = {"choice": None}
        font = ("Consolas", 9)

        tk.Label(chooser, text="How should this PNG be imported?",
                 bg="#0d0d12", fg="#e0e0e8", font=font).pack(padx=16, pady=(12, 8))

        for val, label in [("image", "Single Image"),
                           ("sheet", "Sprite Sheet"),
                           ("sequence", "PNG Sequence")]:
            tk.Button(
                chooser, text=label, bg="#1a1a2e", fg="#e0e0e8",
                font=font, relief="flat", width=20, pady=4,
                command=lambda v=val: (result.update(choice=v),
                                       chooser.destroy()),
            ).pack(padx=16, pady=2)

        tk.Button(
            chooser, text="Cancel", bg="#1a1a2e", fg="#7a7a9a",
            font=font, relief="flat", width=20, pady=4,
            command=chooser.destroy,
        ).pack(padx=16, pady=(2, 12))

        self.root.wait_window(chooser)

        choice = result["choice"]
        if choice is None:
            return None
        elif choice == "image":
            # Fall through to existing image import
            self._open_image_from_path(path)
            return None  # handled separately
        elif choice == "sheet":
            from src.ui.import_dialog import SpriteSheetDialog
            dialog = SpriteSheetDialog(self.root, path)
            self.root.wait_window(dialog)
            if dialog.result is None:
                return None
            if dialog.result[0] == "json":
                from src.sequence_import import parse_sprite_sheet_json
                return parse_sprite_sheet_json(path, dialog.result[1])
            else:
                _, cols, rows, fw, fh = dialog.result
                from src.sequence_import import parse_sprite_sheet_grid
                return parse_sprite_sheet_grid(path, cols, rows, fw, fh)
        elif choice == "sequence":
            from src.ui.import_dialog import PngSequenceDialog
            dialog = PngSequenceDialog(self.root)
            self.root.wait_window(dialog)
            if dialog.result is None:
                return None
            from src.sequence_import import parse_png_sequence
            return parse_png_sequence(dialog.result)
        return None

    def _open_image_from_path(self, path: str):
        """Import a single image into the current layer (no file dialog)."""
        try:
            img = Image.open(path).convert("RGBA")
            w, h = self.timeline.width, self.timeline.height
            if img.size != (w, h):
                img = img.resize((w, h), Image.NEAREST)
            grid = PixelGrid.from_pil_image(img)
            frame_obj = self.timeline.current_frame_obj()
            frame_obj.active_layer.pixels = grid
            self._refresh_canvas()
        except Exception as e:
            from src.ui.dialogs import show_error
            show_error(self.root, "Open Error", str(e))
```

- [ ] **Step 2: Add menu item in app.py**

In `src/app.py`, after line 257 (`file_menu.add_command(label="Open Image...", command=self._open_image)`), add:

```python
        file_menu.add_command(label="Import Animation...",
                              command=self._import_animation)
```

- [ ] **Step 3: Manual smoke test**

Run: `python main.py`

1. File menu should show "Import Animation..." between "Open Image..." and "Export..."
2. Click it → file dialog appears with GIF/APNG/WebP/PNG filters
3. Select a GIF → ImportDialog appears with correct frame count and dimensions
4. Click Import → new project created with GIF frames

- [ ] **Step 4: Commit**

```bash
git add src/file_ops.py src/app.py
git commit -m "feat: wire Import Animation menu item with full format dispatch"
```

---

### Task 11: APNG detection test

**Files:**
- Modify: `tests/test_animated_import.py`

- [ ] **Step 1: Write test for APNG-as-.png detection**

Add to `tests/test_animated_import.py`:

```python
class TestApngDetection:
    def test_png_apng_detection(self):
        """An APNG saved with .png extension should be detected as animated."""
        from PIL import Image
        path = os.path.join(tempfile.mkdtemp(), "animation.png")
        imgs = [
            Image.new("RGBA", (4, 4), (255, 0, 0, 255)),
            Image.new("RGBA", (4, 4), (0, 255, 0, 255)),
        ]
        imgs[0].save(
            path, save_all=True, append_images=imgs[1:],
            duration=[100, 100], loop=0, disposal=2, format="PNG"
        )
        # Verify Pillow detects multiple frames
        img = Image.open(path)
        assert getattr(img, "n_frames", 1) > 1
        img.close()
        # parse_apng should handle it
        from src.animated_import import parse_apng
        result = parse_apng(path)
        assert len(result.frames) == 2
```

- [ ] **Step 2: Run test to verify it passes**

Run: `python -m pytest tests/test_animated_import.py::TestApngDetection -v`
Expected: PASS (parser already works, this just validates the detection path)

- [ ] **Step 3: Commit**

```bash
git add tests/test_animated_import.py
git commit -m "test: add APNG-as-.png detection test"
```

---

### Task 12: Update README

**Files:**
- Modify: `README.md:46`

- [ ] **Step 1: Update the import line in README**

In `README.md`, line 46, change:

```
- Import: Aseprite (.ase/.aseprite), Photoshop (.psd), common image formats
```

to:

```
- Import: Aseprite (.ase/.aseprite), Photoshop (.psd), GIF, APNG, WebP (animated), PNG sequence, Sprite Sheet (PNG + JSON / manual grid), common image formats
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: update README with new animated import formats"
```

---

### Task 13: Full integration test

**Files:** None — verification only

- [ ] **Step 1: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: ALL PASS (485+ existing tests + ~25 new tests)

- [ ] **Step 2: Manual roundtrip test**

1. Open RetroSprite: `python main.py`
2. Create a 3-frame animation with different colors
3. Export as GIF
4. Import Animation → select the GIF → New Project → Keep original timing → Import
5. Verify 3 frames are loaded with correct colors
6. Export as sprite sheet (PNG + JSON)
7. Import Animation → select the PNG → Sprite Sheet → Use JSON → Next → New Project → Import
8. Verify frames match the original

- [ ] **Step 3: Verify insert mode**

1. Create a 2-frame project
2. Import Animation → select a GIF → Insert as Frames → Scale to fit → Import
3. Verify new frames appear after current frame, total frame count is correct
