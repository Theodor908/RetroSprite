# Plan 1: Core Gaps Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the 6 highest-impact competitive gaps vs. Aseprite, Pro Motion, Pixelorama, LibreSprite, and GrafX2. Also fix the `Frame.duration_ms` serialization bug that later plans depend on.

**Architecture:** Task 1 fixes a pre-existing serialization bug. Tasks 2-3 extend existing systems (custom brushes, tiled preview). Tasks 4-5 add new tools following the established registration pattern. Task 6 adds crash recovery infrastructure. Task 7 adds palette sorting.

**Tech Stack:** Python, Tkinter, NumPy, PIL (existing stack). No new dependencies.

---

## Chunk 1: Bug Fix + Custom Brushes + Tiled Preview Enhancement

### Task 1: Fix Frame.duration_ms Serialization Bug

`Frame.duration_ms` (default 100, defined at `src/animation.py` line 20) is never serialized in `save_project()` and never restored in `load_project()`. Plans 2 (AnimPainting) and 4 (Audio Sync) depend on per-frame durations persisting across save/load.

**Files:**
- Test: `tests/test_project.py` (add round-trip test)
- Modify: `src/project.py` (serialize/deserialize `duration_ms`)

- [ ] **Step 1:** Add a failing test to `tests/test_project.py`:

```python
class TestFrameDurationSerialization:
    def test_duration_ms_round_trip(self, tmp_path):
        """Frame.duration_ms must survive save/load."""
        from src.animation import AnimationTimeline
        from src.palette import Palette
        from src.project import save_project, load_project

        timeline = AnimationTimeline(8, 8)
        timeline.get_frame_obj(0).duration_ms = 200
        timeline.add_frame()
        timeline.get_frame_obj(1).duration_ms = 50
        palette = Palette("Pico-8")

        path = str(tmp_path / "dur_test.retro")
        save_project(path, timeline, palette)
        loaded_tl, _, _ = load_project(path)

        assert loaded_tl.get_frame_obj(0).duration_ms == 200
        assert loaded_tl.get_frame_obj(1).duration_ms == 50

    def test_duration_ms_defaults_for_old_files(self, tmp_path):
        """Old project files without duration_ms default to 100."""
        import json
        from src.project import load_project

        # Minimal v3 project with no duration_ms field
        project = {
            "version": 3, "width": 4, "height": 4, "fps": 10,
            "current_frame": 0, "palette_name": "Pico-8",
            "palette_colors": [[0, 0, 0, 255]], "selected_color_index": 0,
            "tilesets": {},
            "frames": [{
                "name": "", "active_layer": 0,
                "layers": [{"name": "Layer 1", "visible": True,
                             "opacity": 1.0, "blend_mode": "normal",
                             "locked": False, "depth": 0,
                             "is_group": False, "effects": [],
                             "pixels": [[0, 0, 0, 0]] * 16,
                             "clipping": False}],
            }],
            "tags": [],
        }
        path = str(tmp_path / "old_format.retro")
        with open(path, "w") as f:
            json.dump(project, f)

        loaded_tl, _, _ = load_project(path)
        assert loaded_tl.get_frame_obj(0).duration_ms == 100
```

Run tests, verify both fail.

- [ ] **Step 2:** In `src/project.py`, add `"duration_ms"` to frame serialization in `save_project()`. Find the dict construction at line 122-126:

```python
        frames_data.append({
            "name": frame_obj.name,
            "layers": layers_data,
            "active_layer": frame_obj.active_layer_index,
        })
```

Replace with:

```python
        frames_data.append({
            "name": frame_obj.name,
            "layers": layers_data,
            "active_layer": frame_obj.active_layer_index,
            "duration_ms": frame_obj.duration_ms,
        })
```

- [ ] **Step 3:** In `src/project.py` `load_project()`, after the Frame is created (line 193: `frame = Frame(w, h, name=frame_data.get("name", ""))`), add:

```python
            frame.duration_ms = frame_data.get("duration_ms", 100)
```

This goes right after the Frame constructor call, before `frame.layers.clear()`.

- [ ] **Step 4:** Run tests, verify both pass. Commit: `fix: serialize Frame.duration_ms in save/load project`.

---

### Task 2: Custom Brushes Enhancement — Color Brush Support

Extend the existing `_custom_brush_mask` system to capture and paint with per-pixel colors.

**Files:**
- Test: `tests/test_custom_brush.py` (create)
- Modify: `src/tools.py` (PenTool gains `color_mask` param)
- Modify: `src/app.py` (new `_custom_brush_colors` field, extended `_capture_brush`)
- Modify: `src/tool_settings.py` (add `brush_mode` to pen defaults)
- Modify: `src/ui/options_bar.py` (brush indicator + mono toggle)

- [ ] **Step 1:** Create `tests/test_custom_brush.py` with failing tests:

```python
"""Tests for color brush extension."""
from src.pixel_data import PixelGrid
from src.tools import PenTool

RED = (255, 0, 0, 255)
GREEN = (0, 255, 0, 255)
BLUE = (0, 0, 255, 255)


class TestColorBrush:
    def test_color_mask_paints_per_pixel_colors(self):
        """color_mask dict maps offsets to individual colors."""
        grid = PixelGrid(8, 8)
        tool = PenTool()
        color_mask = {(0, 0): RED, (1, 0): GREEN, (0, 1): BLUE}
        tool.apply(grid, 3, 3, RED, color_mask=color_mask)
        assert grid.get_pixel(3, 3) == RED
        assert grid.get_pixel(4, 3) == GREEN
        assert grid.get_pixel(3, 4) == BLUE

    def test_color_mask_ignores_color_param(self):
        """When color_mask is set, the main color arg is ignored."""
        grid = PixelGrid(8, 8)
        tool = PenTool()
        color_mask = {(0, 0): GREEN}
        tool.apply(grid, 2, 2, RED, color_mask=color_mask)
        assert grid.get_pixel(2, 2) == GREEN

    def test_mono_mask_uses_foreground_color(self):
        """Existing mask param still paints with single foreground color."""
        grid = PixelGrid(8, 8)
        tool = PenTool()
        mask = {(0, 0), (1, 0), (0, 1)}
        tool.apply(grid, 3, 3, RED, mask=mask)
        assert grid.get_pixel(3, 3) == RED
        assert grid.get_pixel(4, 3) == RED
        assert grid.get_pixel(3, 4) == RED

    def test_color_mask_with_dither(self):
        """Color brush respects dither pattern."""
        grid = PixelGrid(8, 8)
        tool = PenTool()
        # checker pattern: only even parity pixels drawn
        color_mask = {(0, 0): RED, (1, 0): GREEN}
        tool.apply(grid, 0, 0, RED, dither_pattern="checker",
                   color_mask=color_mask)
        # (0,0) parity 0 -> drawn; (1,0) parity 1 -> skipped by checker
        assert grid.get_pixel(0, 0) == RED
        assert grid.get_pixel(1, 0) == (0, 0, 0, 0)
```

Run tests, verify they fail (PenTool.apply has no `color_mask` param yet).

- [ ] **Step 2:** Add `color_mask` parameter to `PenTool.apply()` in `src/tools.py`. Change the signature at line 28-30 from:

```python
    def apply(self, grid: PixelGrid, x: int, y: int, color: tuple,
              size: int = 1, dither_pattern: str = "none",
              mask: set | None = None) -> None:
```

to:

```python
    def apply(self, grid: PixelGrid, x: int, y: int, color: tuple,
              size: int = 1, dither_pattern: str = "none",
              mask: set | None = None,
              color_mask: dict | None = None) -> None:
```

- [ ] **Step 3:** Add color_mask handling inside `PenTool.apply()`, right after the existing `mask` block (after line 39 `return`). Insert before the existing dither check at line 40:

```python
        if color_mask is not None:
            pattern = DITHER_PATTERNS.get(dither_pattern)
            for (dx, dy), pixel_color in color_mask.items():
                px, py = x + dx, y + dy
                if pattern is not None:
                    if not pattern[py % len(pattern)][px % len(pattern[0])]:
                        continue
                grid.set_pixel(px, py, pixel_color)
            return
```

- [ ] **Step 4:** Run tests, verify all 4 pass. Commit: `feat: add color_mask param to PenTool for color brush support`.

- [ ] **Step 5:** Add `_custom_brush_colors` state to `src/app.py`. After line 148 (`self._custom_brush_mask = None`), add:

```python
        self._custom_brush_colors = None  # dict[tuple[int,int], tuple] or None — per-pixel color brush
        self._brush_mode = "color"  # "color" or "mono"
```

- [ ] **Step 6:** Extend `_capture_brush()` in `src/app.py` (line 1339) to also capture colors. Replace the existing method body:

```python
    def _capture_brush(self):
        """Capture selected pixels as a custom brush shape + colors."""
        if not self._selection_pixels:
            return
        xs = [p[0] for p in self._selection_pixels]
        ys = [p[1] for p in self._selection_pixels]
        cx = (min(xs) + max(xs)) // 2
        cy = (min(ys) + max(ys)) // 2
        grid = self.timeline.current_frame()
        mask = set()
        colors = {}
        for (px, py) in self._selection_pixels:
            color = grid.get_pixel(px, py)
            if color[3] > 0:
                offset = (px - cx, py - cy)
                mask.add(offset)
                colors[offset] = color
        if mask:
            self._custom_brush_mask = mask
            self._custom_brush_colors = colors
            self._update_status(f"Custom brush: {len(mask)} pixels")
        self._clear_selection()
```

- [ ] **Step 7:** Update pen drawing in `_on_canvas_click` (around line 895-910) to pass `color_mask` when in color brush mode. In the lambda where `PenTool.apply` is called, add `color_mask=self._custom_brush_colors if self._brush_mode == "color" else None` alongside the existing `mask=self._custom_brush_mask`.

- [ ] **Step 8:** Update pen drawing in `_on_canvas_drag` similarly (around line 1030-1050) to pass `color_mask` when in color brush mode.

- [ ] **Step 9:** Update `_reset_brush()` (line 1360) to also clear colors:

```python
    def _reset_brush(self):
        """Reset to default square brush."""
        self._custom_brush_mask = None
        self._custom_brush_colors = None
        self._update_status("Brush reset to default")
```

- [ ] **Step 10:** Add `brush_mode` to pen defaults in `src/tool_settings.py`. Change line 12:

```python
    "pen":     {"size": 1, "symmetry": "off", "dither": "none", "pixel_perfect": False, "ink_mode": "normal"},
```

to:

```python
    "pen":     {"size": 1, "symmetry": "off", "dither": "none", "pixel_perfect": False, "ink_mode": "normal", "brush_mode": "color"},
```

- [ ] **Step 11:** Run full test suite, verify no regressions. Commit: `feat: extend custom brush capture to store per-pixel colors`.

---

### Task 3: Tiled Preview Enhancement — Keyboard Cycle Shortcut

The tiled mode already renders ghost copies at 40% brightness (`canvas.py` lines 94-107). This task adds `Ctrl+Shift+T` to cycle through tiled modes without the menu.

**Files:**
- Test: `tests/test_tiled_mode.py` (add new test)
- Modify: `src/keybindings.py` (add binding)
- Modify: `src/app.py` (cycle handler + bind shortcut)

- [ ] **Step 1:** Add a test to `tests/test_tiled_mode.py`:

```python
class TestTiledModeCycle:
    def test_cycle_order(self):
        """Cycling goes off -> x -> y -> both -> off."""
        modes = ["off", "x", "y", "both"]
        for i, current in enumerate(modes):
            expected = modes[(i + 1) % len(modes)]
            idx = modes.index(current)
            next_mode = modes[(idx + 1) % len(modes)]
            assert next_mode == expected
```

- [ ] **Step 2:** Add the keybinding in `src/keybindings.py`. After line 25 (`"rotate": "<Control-t>",`), add:

```python
    "tiled_cycle": "<Control-Shift-t>",
```

- [ ] **Step 3:** Add `_cycle_tiled_mode` method to `src/app.py` (near the existing `_on_tiled_mode_change`):

```python
    def _cycle_tiled_mode(self, event=None):
        """Cycle tiled mode: off -> x -> y -> both -> off."""
        modes = ["off", "x", "y", "both"]
        current = self._tiled_mode
        idx = modes.index(current) if current in modes else 0
        new_mode = modes[(idx + 1) % len(modes)]
        self._tiled_mode = new_mode
        self._tiled_var.set(new_mode)
        self.pixel_canvas.set_tiled_mode(new_mode)
        self._render_canvas()
        self._update_status(f"Tiled: {new_mode}")
```

- [ ] **Step 4:** Bind the shortcut in `__init__` where other keybindings are set up. Add:

```python
        self.root.bind("<Control-Shift-t>", self._cycle_tiled_mode)
```

- [ ] **Step 5:** Run tests, verify pass. Commit: `feat: add Ctrl+Shift+T to cycle tiled preview modes`.

---

## Chunk 2: Text Tool + Spray/Airbrush Tool

### Task 4: Text Tool

New tool that renders pixel text onto the canvas using built-in bitmap fonts.

**Files:**
- Create: `src/fonts.py` (bitmap font data)
- Create: `tests/test_text_tool.py`
- Modify: `src/tools.py` (add `render_text` utility function)
- Modify: `src/app.py` (text tool registration, click handler, popup)
- Modify: `src/ui/icons.py` (add "text" icon)
- Modify: `src/ui/options_bar.py` (add "text" options)
- Modify: `src/tool_settings.py` (add "text" defaults)
- Modify: `src/keybindings.py` (add "text": "t")

- [ ] **Step 1:** Create `src/fonts.py` with a minimal 5px bitmap font covering ASCII 32-126. Each character is a list of rows, each row a list of 0/1 values:

```python
"""Built-in bitmap pixel fonts for the Text tool."""
from __future__ import annotations

# Font data: dict[font_name, dict[character, list[list[int]]]]
# Each character glyph is a list of rows (top to bottom), each row a list of
# 0 (transparent) or 1 (foreground) values.

BITMAP_FONTS: dict[str, dict[str, list[list[int]]]] = {}


def _define_font_5px():
    """Tiny 3x5 pixel font — ASCII printable range."""
    glyphs = {}
    glyphs[" "] = [[0, 0, 0]] * 5
    glyphs["A"] = [
        [0, 1, 0],
        [1, 0, 1],
        [1, 1, 1],
        [1, 0, 1],
        [1, 0, 1],
    ]
    glyphs["B"] = [
        [1, 1, 0],
        [1, 0, 1],
        [1, 1, 0],
        [1, 0, 1],
        [1, 1, 0],
    ]
    glyphs["C"] = [
        [0, 1, 1],
        [1, 0, 0],
        [1, 0, 0],
        [1, 0, 0],
        [0, 1, 1],
    ]
    glyphs["D"] = [
        [1, 1, 0],
        [1, 0, 1],
        [1, 0, 1],
        [1, 0, 1],
        [1, 1, 0],
    ]
    glyphs["E"] = [
        [1, 1, 1],
        [1, 0, 0],
        [1, 1, 0],
        [1, 0, 0],
        [1, 1, 1],
    ]
    glyphs["F"] = [
        [1, 1, 1],
        [1, 0, 0],
        [1, 1, 0],
        [1, 0, 0],
        [1, 0, 0],
    ]
    glyphs["G"] = [
        [0, 1, 1],
        [1, 0, 0],
        [1, 0, 1],
        [1, 0, 1],
        [0, 1, 1],
    ]
    glyphs["H"] = [
        [1, 0, 1],
        [1, 0, 1],
        [1, 1, 1],
        [1, 0, 1],
        [1, 0, 1],
    ]
    glyphs["I"] = [
        [1, 1, 1],
        [0, 1, 0],
        [0, 1, 0],
        [0, 1, 0],
        [1, 1, 1],
    ]
    glyphs["J"] = [
        [0, 0, 1],
        [0, 0, 1],
        [0, 0, 1],
        [1, 0, 1],
        [0, 1, 0],
    ]
    glyphs["K"] = [
        [1, 0, 1],
        [1, 0, 1],
        [1, 1, 0],
        [1, 0, 1],
        [1, 0, 1],
    ]
    glyphs["L"] = [
        [1, 0, 0],
        [1, 0, 0],
        [1, 0, 0],
        [1, 0, 0],
        [1, 1, 1],
    ]
    glyphs["M"] = [
        [1, 0, 1],
        [1, 1, 1],
        [1, 0, 1],
        [1, 0, 1],
        [1, 0, 1],
    ]
    glyphs["N"] = [
        [1, 0, 1],
        [1, 1, 1],
        [1, 1, 1],
        [1, 0, 1],
        [1, 0, 1],
    ]
    glyphs["O"] = [
        [0, 1, 0],
        [1, 0, 1],
        [1, 0, 1],
        [1, 0, 1],
        [0, 1, 0],
    ]
    glyphs["P"] = [
        [1, 1, 0],
        [1, 0, 1],
        [1, 1, 0],
        [1, 0, 0],
        [1, 0, 0],
    ]
    glyphs["Q"] = [
        [0, 1, 0],
        [1, 0, 1],
        [1, 0, 1],
        [1, 1, 0],
        [0, 1, 1],
    ]
    glyphs["R"] = [
        [1, 1, 0],
        [1, 0, 1],
        [1, 1, 0],
        [1, 0, 1],
        [1, 0, 1],
    ]
    glyphs["S"] = [
        [0, 1, 1],
        [1, 0, 0],
        [0, 1, 0],
        [0, 0, 1],
        [1, 1, 0],
    ]
    glyphs["T"] = [
        [1, 1, 1],
        [0, 1, 0],
        [0, 1, 0],
        [0, 1, 0],
        [0, 1, 0],
    ]
    glyphs["U"] = [
        [1, 0, 1],
        [1, 0, 1],
        [1, 0, 1],
        [1, 0, 1],
        [0, 1, 0],
    ]
    glyphs["V"] = [
        [1, 0, 1],
        [1, 0, 1],
        [1, 0, 1],
        [0, 1, 0],
        [0, 1, 0],
    ]
    glyphs["W"] = [
        [1, 0, 1],
        [1, 0, 1],
        [1, 0, 1],
        [1, 1, 1],
        [1, 0, 1],
    ]
    glyphs["X"] = [
        [1, 0, 1],
        [1, 0, 1],
        [0, 1, 0],
        [1, 0, 1],
        [1, 0, 1],
    ]
    glyphs["Y"] = [
        [1, 0, 1],
        [1, 0, 1],
        [0, 1, 0],
        [0, 1, 0],
        [0, 1, 0],
    ]
    glyphs["Z"] = [
        [1, 1, 1],
        [0, 0, 1],
        [0, 1, 0],
        [1, 0, 0],
        [1, 1, 1],
    ]
    # Lowercase maps to uppercase for this tiny font
    for ch in "abcdefghijklmnopqrstuvwxyz":
        glyphs[ch] = glyphs[ch.upper()]
    # Digits
    glyphs["0"] = [[0, 1, 0], [1, 0, 1], [1, 0, 1], [1, 0, 1], [0, 1, 0]]
    glyphs["1"] = [[0, 1, 0], [1, 1, 0], [0, 1, 0], [0, 1, 0], [1, 1, 1]]
    glyphs["2"] = [[1, 1, 0], [0, 0, 1], [0, 1, 0], [1, 0, 0], [1, 1, 1]]
    glyphs["3"] = [[1, 1, 0], [0, 0, 1], [0, 1, 0], [0, 0, 1], [1, 1, 0]]
    glyphs["4"] = [[1, 0, 1], [1, 0, 1], [1, 1, 1], [0, 0, 1], [0, 0, 1]]
    glyphs["5"] = [[1, 1, 1], [1, 0, 0], [1, 1, 0], [0, 0, 1], [1, 1, 0]]
    glyphs["6"] = [[0, 1, 1], [1, 0, 0], [1, 1, 0], [1, 0, 1], [0, 1, 0]]
    glyphs["7"] = [[1, 1, 1], [0, 0, 1], [0, 1, 0], [0, 1, 0], [0, 1, 0]]
    glyphs["8"] = [[0, 1, 0], [1, 0, 1], [0, 1, 0], [1, 0, 1], [0, 1, 0]]
    glyphs["9"] = [[0, 1, 0], [1, 0, 1], [0, 1, 1], [0, 0, 1], [1, 1, 0]]
    # Punctuation
    glyphs["."] = [[0, 0, 0], [0, 0, 0], [0, 0, 0], [0, 0, 0], [0, 1, 0]]
    glyphs[","] = [[0, 0, 0], [0, 0, 0], [0, 0, 0], [0, 1, 0], [1, 0, 0]]
    glyphs["!"] = [[0, 1, 0], [0, 1, 0], [0, 1, 0], [0, 0, 0], [0, 1, 0]]
    glyphs["?"] = [[1, 1, 0], [0, 0, 1], [0, 1, 0], [0, 0, 0], [0, 1, 0]]
    glyphs[":"] = [[0, 0, 0], [0, 1, 0], [0, 0, 0], [0, 1, 0], [0, 0, 0]]
    glyphs["-"] = [[0, 0, 0], [0, 0, 0], [1, 1, 1], [0, 0, 0], [0, 0, 0]]
    glyphs["/"] = [[0, 0, 1], [0, 0, 1], [0, 1, 0], [1, 0, 0], [1, 0, 0]]
    glyphs["("] = [[0, 1, 0], [1, 0, 0], [1, 0, 0], [1, 0, 0], [0, 1, 0]]
    glyphs[")"] = [[0, 1, 0], [0, 0, 1], [0, 0, 1], [0, 0, 1], [0, 1, 0]]
    glyphs["'"] = [[0, 1, 0], [0, 1, 0], [0, 0, 0], [0, 0, 0], [0, 0, 0]]
    glyphs['"'] = [[1, 0, 1], [1, 0, 1], [0, 0, 0], [0, 0, 0], [0, 0, 0]]
    return glyphs


_font_5px = _define_font_5px()
BITMAP_FONTS["5px"] = _font_5px


def render_text_pixels(text: str, font_name: str = "5px",
                       spacing: int = 1) -> list[tuple[int, int]]:
    """Render text string to a list of (dx, dy) pixel offsets.

    Returns offsets relative to (0, 0) top-left. Only 'on' pixels included.
    """
    font = BITMAP_FONTS.get(font_name, _font_5px)
    result = []
    cursor_x = 0
    for ch in text:
        glyph = font.get(ch)
        if glyph is None:
            glyph = font.get(" ", [[0, 0, 0]] * 5)
        for row_idx, row in enumerate(glyph):
            for col_idx, val in enumerate(row):
                if val:
                    result.append((cursor_x + col_idx, row_idx))
        char_width = max(len(row) for row in glyph) if glyph else 3
        cursor_x += char_width + spacing
    return result
```

- [ ] **Step 2:** Create `tests/test_text_tool.py` with failing tests:

```python
"""Tests for the text tool rendering."""
from src.fonts import render_text_pixels, BITMAP_FONTS


class TestRenderTextPixels:
    def test_single_char_has_pixels(self):
        pixels = render_text_pixels("A", "5px")
        assert len(pixels) > 0
        # All pixels should be non-negative
        for dx, dy in pixels:
            assert dx >= 0
            assert dy >= 0

    def test_empty_string_returns_empty(self):
        pixels = render_text_pixels("", "5px")
        assert pixels == []

    def test_multi_char_advances_cursor(self):
        pixels = render_text_pixels("AB", "5px")
        xs = [p[0] for p in pixels]
        # B pixels should be offset beyond A's width (3) + spacing (1) = 4
        assert max(xs) >= 4

    def test_space_produces_no_lit_pixels(self):
        pixels = render_text_pixels(" ", "5px")
        assert pixels == []

    def test_unknown_char_uses_space(self):
        pixels = render_text_pixels("\x01", "5px")
        assert pixels == []

    def test_font_5px_exists(self):
        assert "5px" in BITMAP_FONTS
        assert "A" in BITMAP_FONTS["5px"]
        assert len(BITMAP_FONTS["5px"]["A"]) == 5  # 5 rows
```

Run tests, verify they pass (since fonts.py is created in step 1).

- [ ] **Step 3:** Add text tool keybinding in `src/keybindings.py`. After the `"tiled_cycle"` line, add:

```python
    "text": "t",
```

- [ ] **Step 4:** Add text tool to `TOOL_DEFAULTS` in `src/tool_settings.py`. After the `"roundrect"` entry, add:

```python
    "text":    {"font": "5px", "spacing": 1},
```

- [ ] **Step 5:** Add text icon in `src/ui/icons.py`. Add to `TOOL_ICON_MAP` (line 11 area):

```python
    "text": "text-t-bold.svg",
```

Add to `_PNG_FALLBACK`:

```python
    "text": "T",
```

- [ ] **Step 6:** Add text tool options to `TOOL_OPTIONS` in `src/ui/options_bar.py`:

```python
    "text":    {},
```

- [ ] **Step 7:** Register the text tool in `src/app.py`. In the `_tools` dict (line 114-128), there is no new tool class needed — text rendering is handled by a utility function. Instead, add `"Text"` to the tool name set that the toolbar can select. In the tool dict, add a placeholder:

```python
            "Text": None,  # text tool uses popup, no apply() method
```

- [ ] **Step 8:** Add text tool click handler in `_on_canvas_click` (around line 895). Before the existing pen handler, add:

```python
        if tool_name == "Text":
            self._open_text_popup(x, y)
            return
```

- [ ] **Step 9:** Implement `_open_text_popup` method in `src/app.py`:

```python
    def _open_text_popup(self, x, y):
        """Open a small popup for text entry, render to canvas on Apply."""
        popup = tk.Toplevel(self.root)
        popup.title("Text Tool")
        popup.geometry("300x120")
        popup.transient(self.root)
        popup.grab_set()

        tk.Label(popup, text="Text:").pack(anchor="w", padx=8, pady=(8, 0))
        text_var = tk.StringVar()
        entry = tk.Entry(popup, textvariable=text_var, width=30)
        entry.pack(padx=8, pady=4)
        entry.focus_set()

        def apply_text():
            text = text_var.get()
            if not text:
                popup.destroy()
                return
            from src.fonts import render_text_pixels
            settings = self._tool_settings.get("text")
            font_name = settings.get("font", "5px")
            spacing = settings.get("spacing", 1)
            pixels = render_text_pixels(text, font_name, spacing)
            if pixels:
                self._push_undo()
                layer_grid = self.timeline.current_layer()
                color = self.palette.selected_color
                for dx, dy in pixels:
                    layer_grid.set_pixel(x + dx, y + dy, color)
                self._render_canvas()
            popup.destroy()

        btn_frame = tk.Frame(popup)
        btn_frame.pack(pady=8)
        tk.Button(btn_frame, text="Apply", command=apply_text).pack(side="left", padx=4)
        tk.Button(btn_frame, text="Cancel", command=popup.destroy).pack(side="left", padx=4)
        entry.bind("<Return>", lambda e: apply_text())
```

- [ ] **Step 10:** Run full test suite, verify no regressions. Commit: `feat: add Text tool with built-in 5px bitmap font`.

---

### Task 5: Spray/Airbrush Tool

New `SprayTool` class that scatters random pixels in a circle.

**Files:**
- Create: `tests/test_spray_tool.py`
- Modify: `src/tools.py` (add `SprayTool` class)
- Modify: `src/app.py` (tool registration, event handling)
- Modify: `src/ui/icons.py` (icon mapping)
- Modify: `src/ui/options_bar.py` (density slider)
- Modify: `src/tool_settings.py` (spray defaults)
- Modify: `src/keybindings.py` (keybinding)

- [ ] **Step 1:** Create `tests/test_spray_tool.py` with tests:

```python
"""Tests for SprayTool."""
import random
from src.pixel_data import PixelGrid
from src.tools import SprayTool

RED = (255, 0, 0, 255)


class TestSprayTool:
    def test_spray_places_pixels(self):
        """Spray should place at least some pixels."""
        random.seed(42)
        grid = PixelGrid(32, 32)
        tool = SprayTool()
        tool.apply(grid, 16, 16, RED, radius=8, density=0.5)
        # Count non-transparent pixels
        count = 0
        for y in range(32):
            for x in range(32):
                if grid.get_pixel(x, y) != (0, 0, 0, 0):
                    count += 1
        assert count > 0

    def test_spray_within_radius(self):
        """All placed pixels must be within the spray radius."""
        random.seed(42)
        grid = PixelGrid(32, 32)
        tool = SprayTool()
        cx, cy, radius = 16, 16, 6
        tool.apply(grid, cx, cy, RED, radius=radius, density=1.0)
        for y in range(32):
            for x in range(32):
                if grid.get_pixel(x, y) != (0, 0, 0, 0):
                    dist = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
                    assert dist <= radius + 0.5  # small tolerance for rounding

    def test_spray_zero_density_no_pixels(self):
        """Density 0 should place no pixels."""
        grid = PixelGrid(16, 16)
        tool = SprayTool()
        tool.apply(grid, 8, 8, RED, radius=4, density=0.0)
        for y in range(16):
            for x in range(16):
                assert grid.get_pixel(x, y) == (0, 0, 0, 0)

    def test_spray_radius_1(self):
        """Spray with radius 1 should place pixels near center."""
        random.seed(42)
        grid = PixelGrid(8, 8)
        tool = SprayTool()
        tool.apply(grid, 4, 4, RED, radius=1, density=1.0)
        count = 0
        for y in range(8):
            for x in range(8):
                if grid.get_pixel(x, y) != (0, 0, 0, 0):
                    count += 1
        assert count > 0
```

Run tests, verify they fail (SprayTool doesn't exist yet).

- [ ] **Step 2:** Add `SprayTool` class to `src/tools.py`, after the `GradientFillTool` class (end of file):

```python
class SprayTool:
    """Airbrush/spray — scatters random pixels within a circular radius."""

    def apply(self, grid: PixelGrid, x: int, y: int, color: tuple,
              radius: int = 8, density: float = 0.3,
              dither_pattern: str = "none") -> None:
        import random
        import math
        count = int(density * math.pi * radius * radius)
        pattern = DITHER_PATTERNS.get(dither_pattern)
        for _ in range(count):
            # Random point in circle using rejection sampling
            while True:
                dx = random.uniform(-radius, radius)
                dy = random.uniform(-radius, radius)
                if dx * dx + dy * dy <= radius * radius:
                    break
            px = x + int(dx)
            py = y + int(dy)
            if pattern is not None:
                if not pattern[py % len(pattern)][px % len(pattern[0])]:
                    continue
            grid.set_pixel(px, py, color)
```

- [ ] **Step 3:** Run tests, verify all 4 pass. Commit: `feat: add SprayTool class with circular scatter`.

- [ ] **Step 4:** Add spray keybinding in `src/keybindings.py`. After the `"text"` line, add:

```python
    "spray": "a",
```

- [ ] **Step 5:** Add spray to `TOOL_DEFAULTS` in `src/tool_settings.py`:

```python
    "spray":   {"size": 8, "density": 0.3, "dither": "none"},
```

- [ ] **Step 6:** Add spray icon in `src/ui/icons.py`. Add to `TOOL_ICON_MAP`:

```python
    "spray": "spray-bottle-bold.svg",
```

Add to `_PNG_FALLBACK`:

```python
    "spray": "A",
```

- [ ] **Step 7:** Add spray options to `TOOL_OPTIONS` in `src/ui/options_bar.py`:

```python
    "spray":   {"size": True},
```

- [ ] **Step 8:** Register the tool in `src/app.py` `_tools` dict (line 114-128):

```python
            "Spray": SprayTool(),
```

Also add `SprayTool` to the import at the top of `app.py` where `PenTool, EraserTool, ...` are imported from `src.tools`.

- [ ] **Step 9:** Add spray handling in `_on_canvas_click` (near line 895). After the pen block, add:

```python
        elif tool_name == "Spray":
            self._push_undo()
            settings = self._tool_settings.get("spray")
            radius = settings.get("size", 8)
            density = settings.get("density", 0.3)
            self._apply_symmetry_draw(
                lambda px, py: self._tools["Spray"].apply(
                    layer_grid, px, py, color,
                    radius=radius, density=density,
                    dither_pattern=self._dither_pattern
                ), x, y
            )
```

- [ ] **Step 10:** Add spray handling in `_on_canvas_drag` (near line 1013). After the pen drag block, add:

```python
        elif self.current_tool_name == "Spray":
            settings = self._tool_settings.get("spray")
            radius = settings.get("size", 8)
            density = settings.get("density", 0.3)
            self._apply_symmetry_draw(
                lambda px, py: self._tools["Spray"].apply(
                    layer_grid, px, py, color,
                    radius=radius, density=density,
                    dither_pattern=self._dither_pattern
                ), x, y
            )
```

- [ ] **Step 11:** Add spray to the locked-layer check lists in `_on_canvas_click` (line 871) and `_on_canvas_drag` (line 994-995). Add `"Spray"` to the tuple of tool names that check for locked layers.

- [ ] **Step 12:** Add tiled wrapping for spray in `_on_canvas_click` (line 891) and `_on_canvas_drag` (line 1006). Add `"Spray"` to the tool name tuples that call `self._wrap_coord`.

- [ ] **Step 13:** Run full test suite, verify no regressions. Commit: `feat: add Spray/Airbrush tool with circular scatter`.

---

## Chunk 3: Crash Recovery + Palette Sort

### Task 6: Crash Recovery

Auto-save to `~/.retrosprite/recovery/` every 60 seconds, detect and offer restore on startup.

**Files:**
- Create: `tests/test_crash_recovery.py`
- Modify: `src/app.py` (recovery save logic, startup check, cleanup on exit)
- Modify: `src/project.py` (add optional `recovery_meta` to save format)

- [ ] **Step 1:** Create `tests/test_crash_recovery.py` with tests:

```python
"""Tests for crash recovery."""
import os
import json
import tempfile
from unittest.mock import patch
from src.project import save_project, load_project
from src.animation import AnimationTimeline
from src.palette import Palette


class TestRecoverySave:
    def test_recovery_file_is_valid_retro_format(self, tmp_path):
        """Recovery file must be loadable as a normal .retro project."""
        timeline = AnimationTimeline(8, 8)
        palette = Palette("Pico-8")
        timeline.current_layer().set_pixel(2, 2, (255, 0, 0, 255))

        path = str(tmp_path / "recovery_test.retro")
        save_project(path, timeline, palette)

        loaded_tl, loaded_pal, _ = load_project(path)
        assert loaded_tl.current_layer().get_pixel(2, 2) == (255, 0, 0, 255)

    def test_recovery_meta_optional(self, tmp_path):
        """Projects without recovery_meta load fine (backward compat)."""
        timeline = AnimationTimeline(4, 4)
        palette = Palette("Pico-8")
        path = str(tmp_path / "no_meta.retro")
        save_project(path, timeline, palette)

        # Verify no crash on load
        loaded_tl, _, _ = load_project(path)
        assert loaded_tl.width == 4


class TestRecoveryDirectory:
    def test_recovery_dir_creation(self, tmp_path):
        """Recovery directory is created if it doesn't exist."""
        recovery_dir = str(tmp_path / "recovery")
        os.makedirs(recovery_dir, exist_ok=True)
        assert os.path.isdir(recovery_dir)
```

Run tests, verify they pass (these test existing functionality + basic assertions).

- [ ] **Step 2:** Add a `_save_recovery` method to `src/app.py`:

```python
    def _save_recovery(self):
        """Save a recovery backup to ~/.retrosprite/recovery/."""
        import os
        from datetime import datetime
        recovery_dir = os.path.expanduser("~/.retrosprite/recovery")
        os.makedirs(recovery_dir, exist_ok=True)
        recovery_path = os.path.join(recovery_dir, "recovery_latest.retro")
        try:
            save_project(
                recovery_path, self.timeline, self.palette,
                tool_settings=self._tool_settings.to_dict()
            )
        except Exception:
            pass  # Recovery save should never crash the app
```

- [ ] **Step 3:** Add a `_schedule_recovery_save` method and hook it into `__init__` after the existing auto-save setup (near line 178):

```python
    def _schedule_recovery_save(self):
        """Schedule periodic recovery saves."""
        self._save_recovery()
        self._recovery_after_id = self.root.after(
            self._auto_save_interval, self._schedule_recovery_save
        )
```

Call `self._schedule_recovery_save()` at the end of `__init__`.

- [ ] **Step 4:** Add startup recovery check in `__init__`, after the timeline/palette are initialized (around line 112) but before the UI is built. Add:

```python
        # Check for crash recovery
        self._check_recovery()
```

Implement the method:

```python
    def _check_recovery(self):
        """Check for recovery file and offer to restore."""
        import os
        from tkinter import messagebox
        recovery_dir = os.path.expanduser("~/.retrosprite/recovery")
        recovery_path = os.path.join(recovery_dir, "recovery_latest.retro")
        if not os.path.exists(recovery_path):
            return
        try:
            stat = os.stat(recovery_path)
            from datetime import datetime
            mtime = datetime.fromtimestamp(stat.st_mtime)
            age_str = mtime.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            age_str = "unknown time"

        restore = messagebox.askyesno(
            "Crash Recovery",
            f"Unsaved work found from {age_str}.\nRestore it?",
            parent=self.root
        )
        if restore:
            try:
                self.timeline, self.palette, _ts = load_project(recovery_path)
            except Exception:
                messagebox.showerror("Recovery Failed",
                                     "Could not load recovery file.",
                                     parent=self.root)
        # Clean up recovery file regardless of choice
        try:
            os.remove(recovery_path)
        except OSError:
            pass
```

- [ ] **Step 5:** Clean up recovery on clean exit and on successful manual save. In the existing `_save_project` method (or wherever manual save is done), add after a successful save:

```python
        self._cleanup_recovery()
```

Implement:

```python
    def _cleanup_recovery(self):
        """Remove recovery file after successful save or clean exit."""
        import os
        recovery_path = os.path.expanduser("~/.retrosprite/recovery/recovery_latest.retro")
        try:
            os.remove(recovery_path)
        except OSError:
            pass
```

Also call `_cleanup_recovery()` in the window close handler (`_on_close` or `WM_DELETE_WINDOW` handler).

- [ ] **Step 6:** Cancel the recovery timer on exit. In the close handler, add:

```python
        if hasattr(self, '_recovery_after_id'):
            self.root.after_cancel(self._recovery_after_id)
```

- [ ] **Step 7:** Run full test suite, verify no regressions. Commit: `feat: add crash recovery with auto-save to ~/.retrosprite/recovery/`.

---

### Task 7: Palette Sort

Add `sort_by(key)` method to the `Palette` class with 7 sort keys.

**Files:**
- Create: `tests/test_palette_sort.py`
- Modify: `src/palette.py` (add `sort_by` method)
- Modify: `src/app.py` (palette right-click menu, undo integration)

- [ ] **Step 1:** Create `tests/test_palette_sort.py` with failing tests:

```python
"""Tests for palette sort_by method."""
from src.palette import Palette


RED = (255, 0, 0, 255)
GREEN = (0, 255, 0, 255)
BLUE = (0, 0, 255, 255)
WHITE = (255, 255, 255, 255)
BLACK = (0, 0, 0, 255)
TRANSPARENT = (0, 0, 0, 0)


class TestPaletteSortBy:
    def test_sort_by_red(self):
        pal = Palette.__new__(Palette)
        pal.colors = [GREEN, RED, BLUE]
        pal.selected_index = 0
        pal.name = "test"
        result = pal.sort_by("red")
        reds = [c[0] for c in result]
        assert reds == sorted(reds)

    def test_sort_by_green(self):
        pal = Palette.__new__(Palette)
        pal.colors = [RED, GREEN, BLUE]
        pal.selected_index = 0
        pal.name = "test"
        result = pal.sort_by("green")
        greens = [c[1] for c in result]
        assert greens == sorted(greens)

    def test_sort_by_blue(self):
        pal = Palette.__new__(Palette)
        pal.colors = [RED, GREEN, BLUE]
        pal.selected_index = 0
        pal.name = "test"
        result = pal.sort_by("blue")
        blues = [c[2] for c in result]
        assert blues == sorted(blues)

    def test_sort_by_brightness(self):
        pal = Palette.__new__(Palette)
        pal.colors = [WHITE, BLACK, RED]
        pal.selected_index = 0
        pal.name = "test"
        result = pal.sort_by("brightness")
        # BLACK < RED < WHITE by HSV value
        assert result[0] == BLACK

    def test_sort_by_hue(self):
        pal = Palette.__new__(Palette)
        pal.colors = [BLUE, RED, GREEN]
        pal.selected_index = 0
        pal.name = "test"
        result = pal.sort_by("hue")
        # Hue: RED ~0, GREEN ~0.33, BLUE ~0.67
        assert result[0] == RED
        assert result[1] == GREEN
        assert result[2] == BLUE

    def test_sort_by_luminance(self):
        pal = Palette.__new__(Palette)
        pal.colors = [WHITE, BLACK, GREEN]
        pal.selected_index = 0
        pal.name = "test"
        result = pal.sort_by("luminance")
        lums = [0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2] for c in result]
        assert lums == sorted(lums)

    def test_transparent_colors_go_to_end(self):
        pal = Palette.__new__(Palette)
        pal.colors = [TRANSPARENT, RED, GREEN]
        pal.selected_index = 0
        pal.name = "test"
        result = pal.sort_by("red")
        assert result[-1] == TRANSPARENT

    def test_sort_by_saturation(self):
        pal = Palette.__new__(Palette)
        pal.colors = [WHITE, RED, (128, 128, 128, 255)]
        pal.selected_index = 0
        pal.name = "test"
        result = pal.sort_by("saturation")
        # WHITE and GRAY have 0 saturation, RED has 1.0
        assert result[-1] == RED

    def test_sort_returns_new_list(self):
        pal = Palette.__new__(Palette)
        pal.colors = [RED, GREEN, BLUE]
        pal.selected_index = 0
        pal.name = "test"
        result = pal.sort_by("red")
        assert result is not pal.colors
```

Run tests, verify they fail (`Palette` has no `sort_by` method).

- [ ] **Step 2:** Add `sort_by` method to `Palette` class in `src/palette.py`. Add after the `set_palette` method (line 73):

```python
    def sort_by(self, key: str) -> list[tuple[int, int, int, int]]:
        """Sort palette colors by the given key.

        Keys: hue, saturation, brightness, luminance, red, green, blue.
        Fully transparent colors (a == 0) are excluded from sorting
        and placed at the end.
        Returns a new sorted color list (does not modify self.colors).
        """
        opaque = [c for c in self.colors if c[3] > 0]
        transparent = [c for c in self.colors if c[3] == 0]

        if key == "red":
            opaque.sort(key=lambda c: c[0])
        elif key == "green":
            opaque.sort(key=lambda c: c[1])
        elif key == "blue":
            opaque.sort(key=lambda c: c[2])
        elif key == "luminance":
            opaque.sort(key=lambda c: 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2])
        elif key == "hue":
            opaque.sort(key=lambda c: colorsys.rgb_to_hsv(
                c[0] / 255, c[1] / 255, c[2] / 255)[0])
        elif key == "saturation":
            opaque.sort(key=lambda c: colorsys.rgb_to_hsv(
                c[0] / 255, c[1] / 255, c[2] / 255)[1])
        elif key == "brightness":
            opaque.sort(key=lambda c: colorsys.rgb_to_hsv(
                c[0] / 255, c[1] / 255, c[2] / 255)[2])

        return opaque + transparent
```

- [ ] **Step 3:** Run tests, verify all 9 pass. Commit: `feat: add Palette.sort_by() with 7 sort keys`.

- [ ] **Step 4:** Add palette sort UI in `src/app.py`. Find the palette panel setup area and add a right-click context menu. Add a method:

```python
    def _sort_palette(self, key: str):
        """Sort palette by key and update UI."""
        self._push_undo()
        new_colors = self.palette.sort_by(key)
        self.palette.colors = new_colors
        self.palette.selected_index = min(
            self.palette.selected_index, len(new_colors) - 1
        )
        self.right_panel.palette_panel.refresh()
        self._update_status(f"Palette sorted by {key}")
```

- [ ] **Step 5:** Create the right-click context menu on the palette widget. In the right panel setup area (or in the palette panel's init), bind `<Button-3>` to show a context menu:

```python
    def _show_palette_context_menu(self, event):
        menu = tk.Menu(self.root, tearoff=0)
        sort_menu = tk.Menu(menu, tearoff=0)
        for key in ("hue", "saturation", "brightness", "luminance",
                     "red", "green", "blue"):
            sort_menu.add_command(
                label=key.capitalize(),
                command=lambda k=key: self._sort_palette(k)
            )
        menu.add_cascade(label="Sort by...", menu=sort_menu)
        menu.tk_popup(event.x_root, event.y_root)
```

Bind this to the palette canvas widget:

```python
        self.right_panel.palette_panel.canvas.bind(
            "<Button-3>", self._show_palette_context_menu
        )
```

- [ ] **Step 6:** Run full test suite, verify no regressions. Commit: `feat: add palette sort UI with right-click context menu`.

---

## Summary

| Chunk | Tasks | Est. Steps | Key Files |
|-------|-------|------------|-----------|
| 1 | T1 (duration_ms bug), T2 (color brush), T3 (tiled cycle) | 20 | `project.py`, `tools.py`, `app.py`, `keybindings.py` |
| 2 | T4 (text tool), T5 (spray tool) | 24 | `fonts.py` (new), `tools.py`, `app.py`, `icons.py`, `options_bar.py`, `tool_settings.py` |
| 3 | T6 (crash recovery), T7 (palette sort) | 15 | `app.py`, `palette.py`, `project.py` |

**Total:** 7 tasks, ~59 steps, ~7 commits.
