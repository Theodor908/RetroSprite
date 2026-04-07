# Batch 7: File Formats & Export — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix hardcoded export scales, add WebP/APNG animated export, PSD layer-aware import, and unify all exports behind a single dialog.

**Architecture:** New backend modules (`animated_export.py`, `psd_import.py`, `export_png_single` in `export.py`) handle format-specific logic. A unified `ExportDialog` Tkinter Toplevel replaces 3 separate export paths. CLI gets new format choices. All animated exports use per-frame `duration_ms`.

**Tech Stack:** Python 3.8+, Pillow (WebP/APNG/PNG), psd-tools>=1.9 (PSD import), NumPy, Tkinter

**Spec:** `docs/superpowers/specs/2026-03-12-file-formats-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `src/export.py` | Modify | Add `export_png_single()` shared backend |
| `src/animation.py` | Modify | Fix `export_gif` to use per-frame `duration_ms` |
| `src/animated_export.py` | Create | `export_webp()` and `export_apng()` functions |
| `src/psd_import.py` | Create | `load_psd()` — PSD file import with layer-aware parsing |
| `src/ui/export_dialog.py` | Create | `ExportDialog` Toplevel + `ExportSettings` dataclass |
| `src/scripting.py` | Modify | Refactor `export_png` → delegate to `export_png_single`, add `export_webp`/`export_apng` |
| `src/cli.py` | Modify | Add webp/apng/psd format support to export+batch |
| `src/app.py` | Modify | Unified "Export..." menu, PSD in Open dialog, threaded dispatch |
| `requirements.txt` | Modify | Add `psd-tools>=1.9` |
| `tests/test_file_formats.py` | Create | All new tests (~18 tests) |

---

## Chunk 1: Backend Export Functions

### Task 1: export_png_single — Shared PNG Export Backend

**Files:**
- Modify: `src/export.py:69` (append after `export_png_sequence`)
- Modify: `src/scripting.py:74-93` (refactor `export_png` to delegate)
- Test: `tests/test_file_formats.py`

**Context:** Currently `app.py:_save_png` (line 2249) hardcodes `scale=8` and `scripting.py:export_png` (line 74) has its own flatten+scale+save logic. The spec requires a single shared backend in `export.py` that both delegate to.

- [ ] **Step 1: Write failing tests for `export_png_single`**

In `tests/test_file_formats.py`:

```python
"""Tests for Batch 7: File Formats & Export features."""
import numpy as np
import pytest
import tempfile
import os
from PIL import Image

from src.animation import AnimationTimeline, Frame
from src.layer import Layer
from src.palette import Palette
from src.export import export_png_single


class TestExportPNGSingle:
    def setup_method(self):
        self.timeline = AnimationTimeline(8, 8)
        # Paint a red pixel at (0,0) on frame 0
        frame = self.timeline.get_frame_obj(0)
        frame.active_layer.pixels.set_pixel(0, 0, (255, 0, 0, 255))

    def test_export_1x(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.png")
            export_png_single(self.timeline, path, frame=0, scale=1)
            img = Image.open(path)
            assert img.size == (8, 8)
            assert img.getpixel((0, 0))[:3] == (255, 0, 0)

    def test_export_2x(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.png")
            export_png_single(self.timeline, path, frame=0, scale=2)
            img = Image.open(path)
            assert img.size == (16, 16)

    def test_export_4x(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.png")
            export_png_single(self.timeline, path, frame=0, scale=4)
            img = Image.open(path)
            assert img.size == (32, 32)

    def test_export_specific_layer(self):
        frame = self.timeline.get_frame_obj(0)
        frame.add_layer("Layer 2")
        frame.layers[1].pixels.set_pixel(1, 1, (0, 255, 0, 255))
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.png")
            export_png_single(self.timeline, path, frame=0, scale=1,
                              layer="Layer 2")
            img = Image.open(path)
            # Should have green at (1,1), transparent at (0,0)
            assert img.getpixel((1, 1))[:3] == (0, 255, 0)
            assert img.getpixel((0, 0))[3] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_file_formats.py::TestExportPNGSingle -v`
Expected: FAIL — `ImportError: cannot import name 'export_png_single'`

- [ ] **Step 3: Implement `export_png_single` in `src/export.py`**

Append to `src/export.py` after `export_png_sequence`:

```python
def export_png_single(timeline, path: str, frame: int = 0, scale: int = 1,
                      layer: int | str | None = None) -> None:
    """Export a single frame as PNG with user-chosen scale.

    This is the shared backend for PNG export used by both the GUI and CLI.
    """
    frame_obj = timeline.get_frame_obj(frame)
    if layer is not None:
        if isinstance(layer, str):
            target = next((l for l in frame_obj.layers if l.name == layer), None)
            if target is None:
                raise ValueError(f"Layer '{layer}' not found")
        else:
            if 0 <= layer < len(frame_obj.layers):
                target = frame_obj.layers[layer]
            else:
                raise ValueError(f"Layer index {layer} out of range")
        img = target.pixels.to_pil_image()
    else:
        grid = frame_obj.flatten()
        img = grid.to_pil_image()

    if scale > 1:
        img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
    img.save(path)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_file_formats.py::TestExportPNGSingle -v`
Expected: 4 PASSED

- [ ] **Step 5: Refactor `RetroSpriteAPI.export_png` to delegate**

In `src/scripting.py`, replace lines 74-93 (`export_png` method) with:

```python
    def export_png(self, path: str, frame: int = 0, scale: int = 1,
                   layer: int | str | None = None) -> None:
        from src.export import export_png_single
        export_png_single(self.timeline, path, frame=frame, scale=scale,
                          layer=layer)
```

- [ ] **Step 6: Run full test suite to verify no regressions**

Run: `python -m pytest tests/ -v`
Expected: All tests pass (including existing `test_interop_color.py` tests that use `api.export_png`)

---

### Task 2: Fix export_gif Per-Frame Duration

**Files:**
- Modify: `src/animation.py:369-391` (`export_gif` method)
- Test: `tests/test_file_formats.py`

**Context:** `AnimationTimeline.export_gif` (line 387) currently uses a single `frame_duration` for all frames: `duration_ms if duration_ms is not None else 1000 // fps`. Each `Frame` object already has a `duration_ms` attribute (default 100). The fix uses per-frame durations as a list when no explicit `duration_ms` override is given.

- [ ] **Step 1: Write failing test for per-frame GIF duration**

Add to `tests/test_file_formats.py`:

```python
class TestGIFPerFrameDuration:
    def test_export_gif_uses_per_frame_duration(self):
        timeline = AnimationTimeline(4, 4)
        timeline.add_frame()
        # Set different durations
        timeline.get_frame_obj(0).duration_ms = 200
        timeline.get_frame_obj(1).duration_ms = 500
        # Paint something so frames aren't identical
        timeline.get_frame_obj(0).active_layer.pixels.set_pixel(0, 0, (255, 0, 0, 255))
        timeline.get_frame_obj(1).active_layer.pixels.set_pixel(0, 0, (0, 255, 0, 255))
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.gif")
            timeline.export_gif(path, fps=10, scale=1)
            # Read back and verify frame durations
            gif = Image.open(path)
            gif.seek(0)
            d0 = gif.info.get("duration", 100)
            gif.seek(1)
            d1 = gif.info.get("duration", 100)
            assert d0 == 200
            assert d1 == 500
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_file_formats.py::TestGIFPerFrameDuration -v`
Expected: FAIL — durations are equal (both 100ms from `1000 // fps`)

- [ ] **Step 3: Fix `export_gif` to use per-frame durations**

In `src/animation.py`, replace lines 387-391 of `export_gif`:

Old code:
```python
        frame_duration = duration_ms if duration_ms is not None else 1000 // fps
        frames[0].save(
            filepath, save_all=True, append_images=frames[1:],
            duration=frame_duration, loop=0, transparency=255, disposal=2
        )
```

New code:
```python
        if duration_ms is not None:
            durations = duration_ms
        else:
            durations = [f.duration_ms for f in self._frames]
        frames[0].save(
            filepath, save_all=True, append_images=frames[1:],
            duration=durations, loop=0, transparency=255, disposal=2
        )
```

- [ ] **Step 4: Run tests to verify pass**

Run: `python -m pytest tests/test_file_formats.py::TestGIFPerFrameDuration tests/test_interop_color.py -v`
Expected: All PASSED

---

### Task 3: WebP and APNG Animated Export

**Files:**
- Create: `src/animated_export.py`
- Modify: `src/scripting.py` (add `export_webp`, `export_apng` methods)
- Test: `tests/test_file_formats.py`

**Context:** Both functions follow the same pattern: flatten each frame, scale, collect PIL images, save with `save_all=True`. Per-frame durations come from `frame.duration_ms`. WebP uses `format="WEBP", lossless=True`. APNG uses `format="PNG", disposal=2`.

- [ ] **Step 1: Write failing tests for WebP and APNG export**

Add to `tests/test_file_formats.py`:

```python
from src.animated_export import export_webp, export_apng


class TestWebPExport:
    def setup_method(self):
        self.timeline = AnimationTimeline(4, 4)
        self.timeline.add_frame()
        self.timeline.get_frame_obj(0).active_layer.pixels.set_pixel(
            0, 0, (255, 0, 0, 255))
        self.timeline.get_frame_obj(1).active_layer.pixels.set_pixel(
            0, 0, (0, 255, 0, 255))

    def test_export_webp_creates_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.webp")
            export_webp(self.timeline, path, scale=1)
            assert os.path.exists(path)
            img = Image.open(path)
            assert img.format == "WEBP"

    def test_export_webp_frame_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.webp")
            export_webp(self.timeline, path, scale=1)
            img = Image.open(path)
            # Count frames
            n = 0
            try:
                while True:
                    img.seek(n)
                    n += 1
            except EOFError:
                pass
            assert n == 2

    def test_export_webp_scaled(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.webp")
            export_webp(self.timeline, path, scale=2)
            img = Image.open(path)
            assert img.size == (8, 8)


class TestAPNGExport:
    def setup_method(self):
        self.timeline = AnimationTimeline(4, 4)
        self.timeline.add_frame()
        self.timeline.get_frame_obj(0).active_layer.pixels.set_pixel(
            0, 0, (255, 0, 0, 255))
        self.timeline.get_frame_obj(1).active_layer.pixels.set_pixel(
            0, 0, (0, 255, 0, 255))

    def test_export_apng_creates_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.apng")
            export_apng(self.timeline, path, scale=1)
            assert os.path.exists(path)

    def test_export_apng_frame_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.apng")
            export_apng(self.timeline, path, scale=1)
            img = Image.open(path)
            assert getattr(img, 'n_frames', 1) == 2

    def test_export_apng_scaled(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.apng")
            export_apng(self.timeline, path, scale=2)
            img = Image.open(path)
            assert img.size == (8, 8)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_file_formats.py::TestWebPExport tests/test_file_formats.py::TestAPNGExport -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.animated_export'`

- [ ] **Step 3: Create `src/animated_export.py`**

```python
"""WebP and APNG animated export for RetroSprite."""
from __future__ import annotations
from PIL import Image


def export_webp(timeline, path: str, scale: int = 1, loop: int = 0) -> None:
    """Export animation as lossless WebP.

    Uses Pillow save_all with per-frame durations from timeline frames.
    """
    frames: list[Image.Image] = []
    durations: list[int] = []

    for frame_obj in timeline._frames:
        grid = frame_obj.flatten()
        img = grid.to_pil_image()
        if scale > 1:
            img = img.resize((img.width * scale, img.height * scale),
                             Image.NEAREST)
        frames.append(img)
        durations.append(frame_obj.duration_ms)

    frames[0].save(
        path, save_all=True, append_images=frames[1:],
        duration=durations, loop=loop, lossless=True, format="WEBP"
    )


def export_apng(timeline, path: str, scale: int = 1, loop: int = 0) -> None:
    """Export animation as APNG.

    Uses Pillow save_all with disposal=2 (clear) and per-frame durations.
    """
    frames: list[Image.Image] = []
    durations: list[int] = []

    for frame_obj in timeline._frames:
        grid = frame_obj.flatten()
        img = grid.to_pil_image()
        if scale > 1:
            img = img.resize((img.width * scale, img.height * scale),
                             Image.NEAREST)
        frames.append(img)
        durations.append(frame_obj.duration_ms)

    frames[0].save(
        path, save_all=True, append_images=frames[1:],
        duration=durations, loop=loop, disposal=2, format="PNG"
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_file_formats.py::TestWebPExport tests/test_file_formats.py::TestAPNGExport -v`
Expected: 6 PASSED

- [ ] **Step 5: Add `export_webp` and `export_apng` to scripting API**

In `src/scripting.py`, add after the `export_frames` method (line ~107):

```python
    def export_webp(self, path: str, scale: int = 1) -> None:
        """Export animation as lossless WebP."""
        from src.animated_export import export_webp as _export_webp
        _export_webp(self.timeline, path, scale=scale)

    def export_apng(self, path: str, scale: int = 1) -> None:
        """Export animation as APNG."""
        from src.animated_export import export_apng as _export_apng
        _export_apng(self.timeline, path, scale=scale)
```

- [ ] **Step 6: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All pass

---

## Chunk 2: PSD Import

### Task 4: PSD Import Module

**Files:**
- Create: `src/psd_import.py`
- Modify: `requirements.txt`
- Test: `tests/test_file_formats.py`

**Context:** PSD import uses `psd-tools` library. Each PSD layer is converted to a RetroSprite Layer. Pixel data comes from `layer.topil().convert("RGBA")` then `numpy.array(...)`. Groups get `is_group=True`. Blend modes are mapped from PSD names to RetroSprite names. Opacity is PSD 0-255 → 0.0-1.0. Colors are extracted for palette (capped at 256).

**Blend mode mapping (spec section 2):**
- `normal` → `normal`, `multiply` → `multiply`, `screen` → `screen`, `overlay` → `overlay`
- `darken` → `darken`, `lighten` → `lighten`, `difference` → `difference`
- `linear dodge` → `addition`, `subtract` → `subtract`
- All others → `normal` (fallback)

- [ ] **Step 1: Add psd-tools to requirements.txt**

In `requirements.txt`, add after the last line:

```
psd-tools>=1.9
```

- [ ] **Step 2: Install the dependency**

Run: `pip install psd-tools>=1.9`

- [ ] **Step 3: Write failing tests for PSD import**

**Important:** Pillow cannot write PSD files (read-only plugin). Tests must create minimal PSD binaries using a helper function that writes the raw PSD binary format, or use `psd-tools` programmatic API if available.

Add to `tests/test_file_formats.py`:

```python
import struct
from src.psd_import import load_psd, PSD_BLEND_MAP


def _create_test_psd(path, width, height, color=(255, 0, 0, 255), mode="RGBA"):
    """Create a minimal PSD file with a flat composite image.

    Writes a valid PSD binary: header, empty color mode data, empty image
    resources, empty layer/mask section, and raw image data.
    """
    if mode == "RGB":
        channels = 3
        depth = 8
        color_mode = 3  # RGB
        pixel_data = []
        # PSD stores channels planar: all R, then all G, then all B
        for c in range(3):
            for _ in range(height):
                for _ in range(width):
                    pixel_data.append(color[c])
    else:  # RGBA
        channels = 4
        depth = 8
        color_mode = 3  # RGB (alpha is extra channel)
        pixel_data = []
        # PSD stores channels planar: R, G, B first, then alpha as extra channel
        for c in range(4):
            for _ in range(height):
                for _ in range(width):
                    pixel_data.append(color[c])

    with open(path, 'wb') as f:
        # Signature
        f.write(b'8BPS')
        # Version
        f.write(struct.pack('>H', 1))
        # Reserved
        f.write(b'\x00' * 6)
        # Channels
        f.write(struct.pack('>H', channels))
        # Height, Width
        f.write(struct.pack('>I', height))
        f.write(struct.pack('>I', width))
        # Depth (bits per channel)
        f.write(struct.pack('>H', depth))
        # Color mode (3 = RGB)
        f.write(struct.pack('>H', color_mode))
        # Color mode data length
        f.write(struct.pack('>I', 0))
        # Image resources length
        f.write(struct.pack('>I', 0))
        # Layer and mask information length
        f.write(struct.pack('>I', 0))
        # Image data: compression = 0 (raw)
        f.write(struct.pack('>H', 0))
        # Raw pixel data (planar)
        f.write(bytes(pixel_data))


class TestPSDImport:
    """Test PSD import with programmatically created PSD files."""

    def test_load_psd_basic(self):
        """Test that load_psd returns timeline and palette."""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "test.psd")
            _create_test_psd(path, 8, 8, color=(255, 0, 0, 255))

            timeline, palette = load_psd(path)
            assert timeline.width == 8
            assert timeline.height == 8
            assert timeline.frame_count == 1
            assert len(palette.colors) > 0

    def test_load_psd_pixel_data(self):
        """Test that pixel data is preserved."""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "test.psd")
            _create_test_psd(path, 4, 4, color=(0, 255, 0, 255))

            timeline, palette = load_psd(path)
            frame = timeline.get_frame_obj(0)
            # At least one layer should have the green pixel
            found = False
            for layer in frame.layers:
                px = layer.pixels.get_pixel(0, 0)
                if px and px[1] == 255:
                    found = True
                    break
            assert found, "Green pixel not found in any layer"

    def test_load_psd_dimensions(self):
        """Test various PSD sizes."""
        for size in [(16, 16), (32, 32), (64, 48)]:
            with tempfile.TemporaryDirectory() as tmp:
                path = os.path.join(tmp, "test.psd")
                _create_test_psd(path, size[0], size[1],
                                 color=(128, 128, 128, 255))
                timeline, palette = load_psd(path)
                assert timeline.width == size[0]
                assert timeline.height == size[1]


class TestPSDBlendMap:
    def test_known_modes(self):
        assert PSD_BLEND_MAP["normal"] == "normal"
        assert PSD_BLEND_MAP["multiply"] == "multiply"
        assert PSD_BLEND_MAP["screen"] == "screen"
        assert PSD_BLEND_MAP["overlay"] == "overlay"
        assert PSD_BLEND_MAP["darken"] == "darken"
        assert PSD_BLEND_MAP["lighten"] == "lighten"
        assert PSD_BLEND_MAP["difference"] == "difference"
        assert PSD_BLEND_MAP["linear dodge"] == "addition"
        assert PSD_BLEND_MAP["subtract"] == "subtract"

    def test_fallback_is_normal(self):
        # Unknown modes should not be in the map; fallback handled in code
        assert "color burn" not in PSD_BLEND_MAP


class TestPSDColorModes:
    def test_rgb_psd(self):
        """Test that RGB PSD (no alpha channel) imports correctly."""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "rgb.psd")
            _create_test_psd(path, 4, 4, color=(255, 0, 0), mode="RGB")
            timeline, palette = load_psd(path)
            assert timeline.width == 4
            frame = timeline.get_frame_obj(0)
            # Should have at least one layer with red pixels
            px = frame.layers[0].pixels.get_pixel(0, 0)
            assert px[0] == 255  # red channel
            assert px[3] == 255  # alpha should be 255 (added)

    def test_rgba_psd(self):
        """Test that RGBA PSD imports correctly."""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "rgba.psd")
            _create_test_psd(path, 4, 4, color=(0, 0, 255, 128))
            timeline, palette = load_psd(path)
            frame = timeline.get_frame_obj(0)
            px = frame.layers[0].pixels.get_pixel(0, 0)
            assert px[2] == 255  # blue channel
            assert px[3] == 128  # alpha pass-through
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `python -m pytest tests/test_file_formats.py::TestPSDImport tests/test_file_formats.py::TestPSDBlendMap tests/test_file_formats.py::TestPSDColorModes -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.psd_import'`

- [ ] **Step 5: Create `src/psd_import.py`**

```python
"""PSD file import for RetroSprite using psd-tools."""
from __future__ import annotations
import numpy as np
from PIL import Image

from src.animation import AnimationTimeline, Frame
from src.layer import Layer
from src.palette import Palette

# Map PSD blend mode names to RetroSprite blend mode names.
# psd-tools exposes blend_mode.name which is the human-readable form (lowercase).
PSD_BLEND_MAP = {
    "normal": "normal",
    "multiply": "multiply",
    "screen": "screen",
    "overlay": "overlay",
    "darken": "darken",
    "lighten": "lighten",
    "difference": "difference",
    "linear dodge": "addition",
    "subtract": "subtract",
}


def _extract_palette(layers_pixels: list[np.ndarray], max_colors: int = 256) -> list[tuple]:
    """Extract unique opaque colors from layer pixel arrays, capped at max_colors."""
    colors = set()
    for pixels in layers_pixels:
        if pixels is None:
            continue
        h, w = pixels.shape[:2]
        flat = pixels.reshape(-1, 4)
        # Only opaque pixels
        opaque = flat[flat[:, 3] > 0]
        for row in opaque:
            colors.add(tuple(int(v) for v in row))
            if len(colors) >= max_colors:
                return list(colors)[:max_colors]
    return list(colors) if colors else [(0, 0, 0, 255)]


def load_psd(path: str) -> tuple[AnimationTimeline, Palette]:
    """Import a PSD file with layer-aware parsing.

    Returns an AnimationTimeline (single frame) and a Palette extracted
    from the PSD's colors.

    Layer mapping:
    - PSD layers -> RetroSprite layers with pixel data
    - Groups -> layers with is_group=True and depth from nesting
    - Blend modes mapped via PSD_BLEND_MAP (unknown -> "normal")
    - Opacity: PSD 0-255 -> RetroSprite 0.0-1.0
    - Visibility preserved
    """
    from psd_tools import PSDImage

    psd = PSDImage.open(path)
    width, height = psd.width, psd.height

    timeline = AnimationTimeline(width, height)
    frame = timeline.get_frame_obj(0)
    # Remove the default empty layer — we'll add PSD layers
    frame.layers.clear()

    layers_pixels = []

    def _process_layers(psd_layers, depth=0):
        """Recursively process PSD layers."""
        for psd_layer in psd_layers:
            if psd_layer.is_group():
                # Create a group layer
                group = Layer(psd_layer.name, width, height)
                group.is_group = True
                group.depth = depth
                group.visible = psd_layer.is_visible()
                group.opacity = psd_layer.opacity / 255.0
                frame.layers.append(group)
                # Process children at deeper depth
                _process_layers(psd_layer, depth + 1)
            else:
                # Create a regular layer
                layer = Layer(psd_layer.name, width, height)
                layer.visible = psd_layer.is_visible()
                layer.opacity = psd_layer.opacity / 255.0

                # Map blend mode
                blend_name = psd_layer.blend_mode.name
                # psd-tools uses underscored names; normalize
                blend_name = blend_name.replace("_", " ").lower()
                layer.blend_mode = PSD_BLEND_MAP.get(blend_name, "normal")

                # Extract pixel data
                try:
                    pil_img = psd_layer.topil()
                    if pil_img is not None:
                        pil_img = pil_img.convert("RGBA")
                        # PSD layers can have offsets — paste into full-size canvas
                        full = Image.new("RGBA", (width, height), (0, 0, 0, 0))
                        full.paste(pil_img, (psd_layer.left, psd_layer.top))
                        pixels = np.array(full, dtype=np.uint8)
                        layer.pixels._pixels = pixels
                        layers_pixels.append(pixels)
                except Exception:
                    # Failed to extract pixels — leave layer empty
                    pass

                layer.depth = depth
                frame.layers.append(layer)

    _process_layers(psd)

    # If no layers were found (e.g., flat PSD), use composite
    if not frame.layers:
        layer = Layer("Background", width, height)
        composite = psd.composite().convert("RGBA")
        pixels = np.array(composite, dtype=np.uint8)
        layer.pixels._pixels = pixels
        layers_pixels.append(pixels)
        frame.layers.append(layer)

    frame.active_layer_index = 0

    # Extract palette
    palette = Palette("Imported")
    extracted = _extract_palette(layers_pixels)
    palette.colors.clear()
    palette.colors.extend(extracted)

    return timeline, palette
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_file_formats.py::TestPSDImport tests/test_file_formats.py::TestPSDBlendMap tests/test_file_formats.py::TestPSDColorModes -v`
Expected: All PASSED

- [ ] **Step 7: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All pass

---

## Chunk 3: CLI Updates

### Task 5: CLI — Add WebP, APNG, and PSD Support

**Files:**
- Modify: `src/cli.py:21-22` (export subparser `--format` choices)
- Modify: `src/cli.py:34` (batch subparser `--format` choices)
- Modify: `src/cli.py:50-59` (`_detect_format` function)
- Modify: `src/cli.py:82-83` (input file detection in `cmd_export`)
- Modify: `src/cli.py:96-116` (format dispatch in `cmd_export`)
- Modify: `src/cli.py:133` (batch extension map)
- Test: `tests/test_file_formats.py`

**Context:** CLI currently supports `png`, `gif`, `sheet`, `frames` formats. Need to add `webp` and `apng` to both `export` and `batch` subcommands, update `_detect_format` for new extensions, add `.psd` to input detection, and add format dispatch for the new formats.

- [ ] **Step 1: Write failing tests for CLI new formats**

Add to `tests/test_file_formats.py`:

```python
from src.cli import cmd_export, _detect_format, build_parser


class TestCLINewFormats:
    def test_detect_format_webp(self):
        assert _detect_format("output.webp") == "webp"

    def test_detect_format_apng(self):
        assert _detect_format("output.apng") == "apng"

    def test_detect_format_png_unchanged(self):
        assert _detect_format("output.png") == "png"

    def test_detect_format_gif_unchanged(self):
        assert _detect_format("output.gif") == "gif"

    def test_export_parser_has_webp(self):
        parser = build_parser()
        args = parser.parse_args(["export", "in.retro", "out.webp", "--format", "webp"])
        assert args.format == "webp"

    def test_export_parser_has_apng(self):
        parser = build_parser()
        args = parser.parse_args(["export", "in.retro", "out.apng", "--format", "apng"])
        assert args.format == "apng"

    def test_batch_parser_has_webp(self):
        parser = build_parser()
        args = parser.parse_args(["batch", "indir", "outdir", "--format", "webp"])
        assert args.format == "webp"

    def test_batch_parser_has_apng(self):
        parser = build_parser()
        args = parser.parse_args(["batch", "indir", "outdir", "--format", "apng"])
        assert args.format == "apng"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_file_formats.py::TestCLINewFormats -v`
Expected: FAIL — `_detect_format("output.webp")` returns `"png"` (current default)

- [ ] **Step 3: Update `_detect_format` in `src/cli.py`**

Replace `_detect_format` function (lines 50-59):

```python
def _detect_format(output_path: str) -> str:
    """Auto-detect format from file extension."""
    ext = os.path.splitext(output_path)[1].lower()
    if ext == ".gif":
        return "gif"
    elif ext == ".json":
        return "sheet"
    elif ext == ".webp":
        return "webp"
    elif ext == ".apng":
        return "apng"
    elif ext == ".png":
        return "png"
    return "png"
```

- [ ] **Step 4: Update export subparser `--format` choices**

In `build_parser`, change line 21:

Old: `exp.add_argument("--format", choices=["png", "gif", "sheet", "frames"],`
New: `exp.add_argument("--format", choices=["png", "gif", "sheet", "frames", "webp", "apng"],`

- [ ] **Step 5: Update batch subparser `--format` choices**

In `build_parser`, change line 34:

Old: `bat.add_argument("--format", choices=["png", "gif", "sheet"],`
New: `bat.add_argument("--format", choices=["png", "gif", "sheet", "webp", "apng"],`

- [ ] **Step 6: Add format dispatch in `cmd_export`**

In `cmd_export`, after the `elif fmt == "frames":` block (after line 111), add:

```python
        elif fmt == "webp":
            from src.animated_export import export_webp
            export_webp(timeline, output_path, scale=scale)
        elif fmt == "apng":
            from src.animated_export import export_apng
            export_apng(timeline, output_path, scale=scale)
```

- [ ] **Step 7: Add `.psd` input detection in `cmd_export`**

In `cmd_export`, update the input extension detection block (lines 82-87). Change:

Old:
```python
        ext = os.path.splitext(input_path)[1].lower()
        if ext in ('.ase', '.aseprite'):
            from src.aseprite_import import load_aseprite
            timeline, palette = load_aseprite(input_path)
        else:
            timeline, palette = load_project(input_path)
```

New:
```python
        ext = os.path.splitext(input_path)[1].lower()
        if ext in ('.ase', '.aseprite'):
            from src.aseprite_import import load_aseprite
            timeline, palette = load_aseprite(input_path)
        elif ext == '.psd':
            from src.psd_import import load_psd
            timeline, palette = load_psd(input_path)
        else:
            timeline, palette = load_project(input_path)
```

- [ ] **Step 8: Update `cmd_batch` extension map**

In `cmd_batch`, change line 133:

Old: `ext = {"png": ".png", "gif": ".gif", "sheet": ".png"}[format]`
New: `ext = {"png": ".png", "gif": ".gif", "sheet": ".png", "webp": ".webp", "apng": ".apng"}[format]`

- [ ] **Step 9: Run tests to verify they pass**

Run: `python -m pytest tests/test_file_formats.py::TestCLINewFormats -v`
Expected: 8 PASSED

- [ ] **Step 10: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All pass

---

## Chunk 4: Unified Export Dialog & App Integration

### Task 6: ExportSettings Dataclass and ExportDialog

**Files:**
- Create: `src/ui/export_dialog.py`
- Test: `tests/test_file_formats.py`

**Context:** The `ExportDialog` is a Tkinter Toplevel that provides a unified interface for all export formats. It returns an `ExportSettings` dataclass or `None` on cancel. Format change shows/hides relevant options. Scale defaults to last-used. The `[Export]` button triggers a file save dialog with format-appropriate extension filter. Output size preview updates live.

No GUI tests for ExportDialog (Tkinter tests are fragile). We test only the `ExportSettings` dataclass.

- [ ] **Step 1: Write test for ExportSettings dataclass**

Add to `tests/test_file_formats.py`:

```python
from src.ui.export_dialog import ExportSettings


class TestExportSettings:
    def test_default_values(self):
        settings = ExportSettings(
            format="png", scale=1, frame=0, layer=None,
            columns=0, output_path="/tmp/out.png"
        )
        assert settings.format == "png"
        assert settings.scale == 1
        assert settings.frame == 0
        assert settings.layer is None
        assert settings.columns == 0
        assert settings.output_path == "/tmp/out.png"

    def test_all_formats(self):
        for fmt in ["png", "gif", "webp", "apng", "sheet", "frames"]:
            s = ExportSettings(format=fmt, scale=2, frame=0, layer=None,
                               columns=0, output_path=f"/tmp/out.{fmt}")
            assert s.format == fmt

    def test_layer_name(self):
        s = ExportSettings(format="png", scale=1, frame=0, layer="Layer 2",
                           columns=0, output_path="/tmp/out.png")
        assert s.layer == "Layer 2"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_file_formats.py::TestExportSettings -v`
Expected: FAIL — `ImportError: cannot import name 'ExportSettings'`

- [ ] **Step 3: Create `src/ui/export_dialog.py`**

```python
"""Unified export dialog for RetroSprite."""
from __future__ import annotations
import tkinter as tk
from tkinter import filedialog
from dataclasses import dataclass
from src.ui.theme import (
    BG_DEEP, BG_PANEL, TEXT_PRIMARY, TEXT_SECONDARY,
    ACCENT_CYAN, ACCENT_MAGENTA, BUTTON_BG, BUTTON_HOVER,
)


@dataclass
class ExportSettings:
    """Settings returned by ExportDialog."""
    format: str       # "png", "gif", "webp", "apng", "sheet", "frames"
    scale: int        # 1-16
    frame: int        # frame index (for png single)
    layer: str | None  # layer name or None for flattened
    columns: int      # sheet columns (0=auto)
    output_path: str  # file path from save dialog


# File extension filters per format
_FORMAT_FILTERS = {
    "png": [("PNG files", "*.png")],
    "gif": [("GIF files", "*.gif")],
    "webp": [("WebP files", "*.webp")],
    "apng": [("APNG files", "*.apng *.png")],
    "sheet": [("PNG files", "*.png")],
    "frames": [("PNG files", "*.png")],
}

# Default extensions per format
_FORMAT_EXT = {
    "png": ".png",
    "gif": ".gif",
    "webp": ".webp",
    "apng": ".apng",
    "sheet": ".png",
    "frames": ".png",
}

# Formats that support per-frame options
_SINGLE_FRAME_FORMATS = {"png"}
# Formats that support layer selection
_LAYER_FORMATS = {"png", "frames"}
# Formats that support columns option
_COLUMN_FORMATS = {"sheet"}


class ExportDialog(tk.Toplevel):
    """Unified export dialog for all RetroSprite export formats.

    Usage:
        dialog = ExportDialog(parent, timeline, palette, last_settings)
        parent.wait_window(dialog)
        settings = dialog.result  # ExportSettings or None
    """

    def __init__(self, parent, timeline, palette, last_settings=None):
        super().__init__(parent)
        self.title("Export...")
        self.configure(bg=BG_DEEP)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._timeline = timeline
        self._palette = palette
        self._last = last_settings or {}
        self.result: ExportSettings | None = None

        self._build_ui()
        self._on_format_change()
        self._update_preview()

        # Center on parent
        self.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        w = self.winfo_width()
        h = self.winfo_height()
        self.geometry(f"+{px + (pw - w) // 2}+{py + (ph - h) // 2}")

    def _build_ui(self):
        pad = {"padx": 8, "pady": 4}
        font = ("Consolas", 9)

        # --- Format ---
        row = tk.Frame(self, bg=BG_DEEP)
        row.pack(fill="x", **pad)
        tk.Label(row, text="Format:", bg=BG_DEEP, fg=TEXT_PRIMARY,
                 font=font, width=10, anchor="w").pack(side="left")
        self._fmt_var = tk.StringVar(value=self._last.get("format", "png"))
        formats = ["png", "gif", "webp", "apng", "sheet", "frames"]
        self._fmt_menu = tk.OptionMenu(row, self._fmt_var, *formats,
                                        command=lambda _: self._on_format_change())
        self._fmt_menu.config(bg=BUTTON_BG, fg=TEXT_PRIMARY, font=font,
                              activebackground=BUTTON_HOVER,
                              highlightthickness=0)
        self._fmt_menu.pack(side="left", fill="x", expand=True)

        # --- Scale ---
        scale_row = tk.Frame(self, bg=BG_DEEP)
        scale_row.pack(fill="x", **pad)
        tk.Label(scale_row, text="Scale:", bg=BG_DEEP, fg=TEXT_PRIMARY,
                 font=font, width=10, anchor="w").pack(side="left")
        self._scale_var = tk.IntVar(value=self._last.get("scale", 1))
        for s in [1, 2, 4, 8]:
            tk.Radiobutton(
                scale_row, text=f"{s}x", variable=self._scale_var, value=s,
                bg=BG_DEEP, fg=TEXT_PRIMARY, selectcolor=BG_PANEL,
                activebackground=BG_DEEP, activeforeground=ACCENT_CYAN,
                font=font, command=self._update_preview
            ).pack(side="left", padx=2)
        tk.Label(scale_row, text="Custom:", bg=BG_DEEP, fg=TEXT_SECONDARY,
                 font=font).pack(side="left", padx=(8, 2))
        self._custom_scale = tk.Spinbox(
            scale_row, from_=1, to=16, width=3, font=font,
            bg=BG_PANEL, fg=TEXT_PRIMARY, buttonbackground=BUTTON_BG,
            command=self._on_custom_scale
        )
        self._custom_scale.pack(side="left")
        self._custom_scale.bind("<Return>", lambda e: self._on_custom_scale())

        # --- Frame selector ---
        self._frame_row = tk.Frame(self, bg=BG_DEEP)
        self._frame_row.pack(fill="x", **pad)
        tk.Label(self._frame_row, text="Frame:", bg=BG_DEEP, fg=TEXT_PRIMARY,
                 font=font, width=10, anchor="w").pack(side="left")
        self._frame_var = tk.StringVar(value="current")
        tk.Radiobutton(
            self._frame_row, text="Current frame", variable=self._frame_var,
            value="current", bg=BG_DEEP, fg=TEXT_PRIMARY,
            selectcolor=BG_PANEL, font=font
        ).pack(side="left")
        tk.Radiobutton(
            self._frame_row, text="All frames", variable=self._frame_var,
            value="all", bg=BG_DEEP, fg=TEXT_PRIMARY,
            selectcolor=BG_PANEL, font=font
        ).pack(side="left")

        # --- Layer selector ---
        self._layer_row = tk.Frame(self, bg=BG_DEEP)
        self._layer_row.pack(fill="x", **pad)
        tk.Label(self._layer_row, text="Layer:", bg=BG_DEEP, fg=TEXT_PRIMARY,
                 font=font, width=10, anchor="w").pack(side="left")
        layer_names = ["All (flattened)"]
        frame_obj = self._timeline.get_frame_obj(self._timeline.current_index)
        layer_names += [l.name for l in frame_obj.layers]
        self._layer_var = tk.StringVar(value="All (flattened)")
        self._layer_menu = tk.OptionMenu(self._layer_row, self._layer_var,
                                          *layer_names)
        self._layer_menu.config(bg=BUTTON_BG, fg=TEXT_PRIMARY, font=font,
                                activebackground=BUTTON_HOVER,
                                highlightthickness=0)
        self._layer_menu.pack(side="left", fill="x", expand=True)

        # --- Sheet columns ---
        self._col_row = tk.Frame(self, bg=BG_DEEP)
        self._col_row.pack(fill="x", **pad)
        tk.Label(self._col_row, text="Columns:", bg=BG_DEEP, fg=TEXT_PRIMARY,
                 font=font, width=10, anchor="w").pack(side="left")
        self._col_var = tk.IntVar(value=0)
        self._col_spin = tk.Spinbox(
            self._col_row, from_=0, to=100, width=4, font=font,
            textvariable=self._col_var,
            bg=BG_PANEL, fg=TEXT_PRIMARY, buttonbackground=BUTTON_BG,
        )
        self._col_spin.pack(side="left")
        tk.Label(self._col_row, text="(0 = auto)", bg=BG_DEEP,
                 fg=TEXT_SECONDARY, font=font).pack(side="left", padx=4)

        # --- Output size preview ---
        self._preview_label = tk.Label(
            self, text="Output: --", bg=BG_DEEP, fg=ACCENT_CYAN,
            font=("Consolas", 9, "bold")
        )
        self._preview_label.pack(fill="x", **pad)

        # --- Buttons ---
        btn_row = tk.Frame(self, bg=BG_DEEP)
        btn_row.pack(fill="x", padx=8, pady=8)
        tk.Button(
            btn_row, text="Export", command=self._on_export,
            bg=ACCENT_CYAN, fg=BG_DEEP, font=("Consolas", 9, "bold"),
            activebackground=ACCENT_MAGENTA, width=10
        ).pack(side="right", padx=4)
        tk.Button(
            btn_row, text="Cancel", command=self._on_cancel,
            bg=BUTTON_BG, fg=TEXT_PRIMARY, font=font,
            activebackground=BUTTON_HOVER, width=10
        ).pack(side="right", padx=4)

    def _on_format_change(self):
        fmt = self._fmt_var.get()
        # Hide all optional rows first
        self._frame_row.pack_forget()
        self._layer_row.pack_forget()
        self._col_row.pack_forget()
        # Re-pack in correct order, before the preview label
        if fmt in _SINGLE_FRAME_FORMATS:
            self._frame_row.pack(fill="x", padx=8, pady=4,
                                 before=self._preview_label)
        if fmt in _LAYER_FORMATS:
            self._layer_row.pack(fill="x", padx=8, pady=4,
                                 before=self._preview_label)
        if fmt in _COLUMN_FORMATS:
            self._col_row.pack(fill="x", padx=8, pady=4,
                               before=self._preview_label)
        self._update_preview()

    def _on_custom_scale(self):
        try:
            val = int(self._custom_scale.get())
            if 1 <= val <= 16:
                self._scale_var.set(val)
                self._update_preview()
        except ValueError:
            pass

    def _update_preview(self):
        s = self._scale_var.get()
        w = self._timeline.width * s
        h = self._timeline.height * s
        fmt = self._fmt_var.get()
        if fmt == "sheet":
            fc = self._timeline.frame_count
            cols = self._col_var.get() or fc
            rows = (fc + cols - 1) // cols
            w = self._timeline.width * s * cols
            h = self._timeline.height * s * rows
        self._preview_label.config(text=f"Output: {w}\u00d7{h} px")

    def _on_export(self):
        fmt = self._fmt_var.get()
        filters = _FORMAT_FILTERS.get(fmt, [("All files", "*.*")])
        ext = _FORMAT_EXT.get(fmt, ".png")
        path = filedialog.asksaveasfilename(
            parent=self, filetypes=filters, defaultextension=ext
        )
        if not path:
            return

        frame_idx = self._timeline.current_index
        if fmt in _SINGLE_FRAME_FORMATS and self._frame_var.get() == "all":
            frame_idx = -1  # signal "all frames" — caller handles

        layer = None
        if fmt in _LAYER_FORMATS:
            layer_val = self._layer_var.get()
            if layer_val != "All (flattened)":
                layer = layer_val

        self.result = ExportSettings(
            format=fmt,
            scale=self._scale_var.get(),
            frame=frame_idx,
            layer=layer,
            columns=self._col_var.get(),
            output_path=path,
        )
        self.destroy()

    def _on_cancel(self):
        self.result = None
        self.destroy()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_file_formats.py::TestExportSettings -v`
Expected: 3 PASSED

---

### Task 7: App Integration — Unified Export & PSD Open

**Files:**
- Modify: `src/app.py:195-290` (`_build_menu` — File and Animation menus)
- Modify: `src/app.py:1939-1963` (replace `_export_gif`)
- Modify: `src/app.py:2249-2272` (replace `_save_png` and `_export_sprite_sheet`)
- Modify: `src/app.py:2179-2218` (`_open_project` — add PSD)
- No test (GUI — consistent with existing test patterns)

**Context:** The spec requires:
1. Remove "Save as PNG..." and "Export Sprite Sheet..." from File menu
2. Remove "Export GIF..." from Animation menu
3. Add "Export..." (`Ctrl+Shift+E`) to File menu
4. Add PSD to Open dialog filetypes
5. New `_show_export_dialog()` method dispatches to backends with threaded animated export

- [ ] **Step 1: Update `_build_menu` — File menu**

In `src/app.py`, in `_build_menu()`, replace these two lines from the File menu:

Old (lines 213-215):
```python
        file_menu.add_command(label="Save as PNG...", command=self._save_png)
        file_menu.add_command(label="Export Sprite Sheet...",
                              command=self._export_sprite_sheet)
```

New:
```python
        file_menu.add_command(label="Export...", command=self._show_export_dialog,
                              accelerator="Ctrl+Shift+E")
```

- [ ] **Step 2: Update `_build_menu` — Animation menu**

In `src/app.py`, remove the "Export GIF..." line from the Animation menu.

Old (line 289):
```python
        anim_menu.add_command(label="Export GIF...", command=self._export_gif)
```

Delete this line entirely.

- [ ] **Step 3: Add `_export_settings` state to `__init__`**

In `src/app.py`, after `self._display_effects = True` (line 145), add:

```python
        # Export dialog last-used settings
        self._export_settings = {}
```

- [ ] **Step 4: Add `Ctrl+Shift+E` keybinding**

In `src/app.py`, in `_bind_keys()`, add:

```python
        self.root.bind("<Control-Shift-E>", lambda e: self._show_export_dialog())
```

Find the existing `_bind_keys` method and add this line there.

- [ ] **Step 5: Add `_show_export_dialog` method**

In `src/app.py`, replace the old `_save_png` and `_export_sprite_sheet` methods (lines 2249-2272) with:

```python
    def _show_export_dialog(self):
        """Open the unified export dialog and dispatch to backend."""
        from src.ui.export_dialog import ExportDialog
        dialog = ExportDialog(self.root, self.timeline, self.palette,
                              self._export_settings)
        self.root.wait_window(dialog)
        settings = dialog.result
        if settings is None:
            return

        # Remember settings for next time
        self._export_settings = {
            "format": settings.format,
            "scale": settings.scale,
        }

        path = settings.output_path
        fmt = settings.format

        if not self.api.emit("before_export", {"filepath": path, "format": fmt}):
            return

        # Animated formats run in background thread
        if fmt in ("gif", "webp", "apng"):
            self._update_status(f"Exporting {fmt.upper()}...")

            def worker():
                try:
                    if fmt == "gif":
                        self.timeline.export_gif(path, fps=self.timeline.fps,
                                                 scale=settings.scale)
                    elif fmt == "webp":
                        from src.animated_export import export_webp
                        export_webp(self.timeline, path, scale=settings.scale)
                    elif fmt == "apng":
                        from src.animated_export import export_apng
                        export_apng(self.timeline, path, scale=settings.scale)
                    self.root.after(0, lambda: self.api.emit(
                        "after_export", {"filepath": path, "format": fmt}))
                    self.root.after(0, lambda: show_info(
                        self.root, "Export", f"Exported to {path}"))
                except Exception as e:
                    self.root.after(0, lambda: show_error(
                        self.root, "Export Error", str(e)))
                finally:
                    self.root.after(0, lambda: self._update_status(""))

            import threading
            threading.Thread(target=worker, daemon=True).start()
        else:
            # Synchronous formats
            try:
                if fmt == "png":
                    from src.export import export_png_single
                    export_png_single(self.timeline, path,
                                      frame=settings.frame, scale=settings.scale,
                                      layer=settings.layer)
                elif fmt == "sheet":
                    from src.export import save_sprite_sheet
                    save_sprite_sheet(self.timeline, path,
                                     scale=settings.scale,
                                     columns=settings.columns)
                elif fmt == "frames":
                    from src.export import export_png_sequence
                    export_png_sequence(self.timeline, path,
                                       scale=settings.scale,
                                       layer=settings.layer)
                self.api.emit("after_export", {"filepath": path, "format": fmt})
                show_info(self.root, "Export", f"Exported to {path}")
            except Exception as e:
                show_error(self.root, "Export Error", str(e))
```

- [ ] **Step 6: Remove old `_export_gif` method**

In `src/app.py`, delete the `_export_gif` method (lines 1939-1963). It's fully replaced by the unified dialog.

- [ ] **Step 7: Add PSD to Open dialog**

In `src/app.py`, in `_open_project()` (line 2185), update the filetypes:

Old:
```python
            filetypes=[("RetroSprite Projects", "*.retro"),
                       ("Aseprite Files", "*.ase;*.aseprite"),
                       ("All files", "*.*")]
```

New:
```python
            filetypes=[("RetroSprite Projects", "*.retro"),
                       ("Aseprite Files", "*.ase;*.aseprite"),
                       ("Photoshop Files", "*.psd"),
                       ("All files", "*.*")]
```

- [ ] **Step 8: Restructure `_open_project` as if/elif/elif/else for PSD support**

**Critical:** The existing code is `if ext in ('.ase', ...): ... else: ...`. Adding PSD requires converting to `if/elif/elif/else` so the PSD branch doesn't fall through to the `.retro` loader. Replace the entire ext detection + load block (lines 2193-2208) with:

Old:
```python
        ext = os.path.splitext(path)[1].lower()
        if ext in ('.ase', '.aseprite'):
            from src.aseprite_import import load_aseprite
            try:
                self.timeline, palette = load_aseprite(path)
                self.palette.colors = palette.colors
                self.palette.selected_index = 0
            except Exception as e:
                show_error(self.root, "Import Error", str(e))
                return
        else:
            try:
                self.timeline, self.palette = load_project(path)
            except Exception as e:
                show_error(self.root, "Open Error", str(e))
                return
```

New:
```python
        ext = os.path.splitext(path)[1].lower()
        if ext in ('.ase', '.aseprite'):
            from src.aseprite_import import load_aseprite
            try:
                self.timeline, palette = load_aseprite(path)
                self.palette.colors = palette.colors
                self.palette.selected_index = 0
            except Exception as e:
                show_error(self.root, "Import Error", str(e))
                return
        elif ext == '.psd':
            from src.psd_import import load_psd
            try:
                self.timeline, palette = load_psd(path)
                self.palette.colors = palette.colors
                self.palette.selected_index = 0
            except Exception as e:
                show_error(self.root, "Import Error", str(e))
                return
        else:
            try:
                self.timeline, self.palette = load_project(path)
            except Exception as e:
                show_error(self.root, "Open Error", str(e))
                return
```

The post-load state updates (lines 2209-2218: `self.api.timeline = self.timeline`, `self._reset_state()`, etc.) remain unchanged and execute for all branches on success.

- [ ] **Step 9: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All pass (no GUI tests for this task — changes are UI-only)

---

### Task 8: Update requirements.txt

**Files:**
- Modify: `requirements.txt`

**Context:** This was already done in Task 4 Step 1, but verify it's correct.

- [ ] **Step 1: Verify requirements.txt has psd-tools**

Read `requirements.txt` and confirm it contains `psd-tools>=1.9`.

- [ ] **Step 2: Run full test suite one final time**

Run: `python -m pytest tests/ -v --tb=short`
Expected: All tests pass, including all new `test_file_formats.py` tests (~18 new tests)

---

## Summary

| Task | Description | New Tests | Dependencies |
|------|-------------|-----------|--------------|
| 1 | `export_png_single` + scripting refactor | 4 | None |
| 2 | Fix `export_gif` per-frame duration | 1 | None |
| 3 | WebP + APNG animated export | 6 | None |
| 4 | PSD import | 7 | None |
| 5 | CLI new format support | 8 | Tasks 3, 4 |
| 6 | ExportSettings + ExportDialog | 3 | None |
| 7 | App integration (menu, dispatch, PSD open) | 0 (GUI) | Tasks 1-6 |
| 8 | requirements.txt verification | 0 | Task 4 |

**Parallelizable:** Tasks 1, 2, 3, 4, 6 are independent and can run in parallel.
**Sequential:** Task 5 needs Tasks 3+4. Task 7 needs all prior tasks. Task 8 is a final verification.

**Total new tests:** ~29
**No git commits** per user's standing instruction.
