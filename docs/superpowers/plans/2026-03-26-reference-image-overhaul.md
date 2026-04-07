# Reference Image Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the ephemeral reference image overlay with a Krita-style positionable, persistent reference image saved in `.retro` files.

**Architecture:** New `ReferenceImage` dataclass holds the image + position/scale/opacity. The rendering pipeline composites it at `(x, y)` with scale instead of force-fitting. Project save/load serializes it as base64 PNG. Alt+drag moves, Ctrl+Alt+scroll resizes.

**Tech Stack:** Python, Pillow, NumPy, Tkinter, JSON/base64

**Spec:** `docs/superpowers/specs/2026-03-26-reference-image-overhaul-design.md`

---

### Task 1: ReferenceImage Data Model

**Files:**
- Create: `src/reference_image.py`
- Create: `tests/test_reference_image.py`

- [ ] **Step 1: Write the tests**

```python
# tests/test_reference_image.py
"""Tests for ReferenceImage data model."""
import pytest
from PIL import Image
from src.reference_image import ReferenceImage


class TestReferenceImage:
    def test_default_values(self):
        img = Image.new("RGBA", (10, 10), (255, 0, 0, 255))
        ref = ReferenceImage(image=img)
        assert ref.x == 0
        assert ref.y == 0
        assert ref.scale == 1.0
        assert ref.opacity == 0.3
        assert ref.visible is True
        assert ref.path == ""
        assert ref.image.size == (10, 10)

    def test_custom_values(self):
        img = Image.new("RGBA", (20, 15), (0, 255, 0, 255))
        ref = ReferenceImage(image=img, x=5, y=10, scale=0.5,
                             opacity=0.7, visible=False, path="/tmp/test.png")
        assert ref.x == 5
        assert ref.y == 10
        assert ref.scale == 0.5
        assert ref.opacity == 0.7
        assert ref.visible is False
        assert ref.path == "/tmp/test.png"

    def test_fit_to_canvas(self):
        """fit_to_canvas should calculate scale so image fits within bounds."""
        img = Image.new("RGBA", (100, 50))
        ref = ReferenceImage(image=img)
        ref.fit_to_canvas(50, 50)
        # 100 wide -> needs scale 0.5 to fit in 50 wide
        assert ref.scale == 0.5
        assert ref.x == 0
        assert ref.y == 0

    def test_fit_to_canvas_tall_image(self):
        """Tall image should scale based on height."""
        img = Image.new("RGBA", (20, 100))
        ref = ReferenceImage(image=img)
        ref.fit_to_canvas(40, 40)
        # 100 tall -> needs scale 0.4 to fit in 40 tall
        assert ref.scale == pytest.approx(0.4)

    def test_fit_to_canvas_smaller_image(self):
        """Image smaller than canvas should scale to 1.0 (no upscale)."""
        img = Image.new("RGBA", (10, 10))
        ref = ReferenceImage(image=img)
        ref.fit_to_canvas(50, 50)
        assert ref.scale == 1.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_reference_image.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.reference_image'`

- [ ] **Step 3: Implement ReferenceImage dataclass**

```python
# src/reference_image.py
"""ReferenceImage data model for positionable overlay."""
from __future__ import annotations
from dataclasses import dataclass, field
from PIL import Image


@dataclass
class ReferenceImage:
    """A positionable reference image overlay on the canvas."""
    image: Image.Image
    x: int = 0
    y: int = 0
    scale: float = 1.0
    opacity: float = 0.3
    visible: bool = True
    path: str = ""

    def fit_to_canvas(self, canvas_w: int, canvas_h: int) -> None:
        """Set scale so the image fits within canvas bounds. No upscaling."""
        img_w, img_h = self.image.size
        if img_w <= 0 or img_h <= 0:
            return
        scale_x = canvas_w / img_w
        scale_y = canvas_h / img_h
        self.scale = min(scale_x, scale_y, 1.0)
        self.x = 0
        self.y = 0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_reference_image.py -v`
Expected: All 5 tests PASS

---

### Task 2: Project Persistence — Save/Load

**Files:**
- Modify: `src/project.py:14-15` (save_project signature), `src/project.py:128-145` (project dict), `src/project.py:148` (load_project), `src/project.py:289-290` (return)
- Modify: `tests/test_project.py`
- Read: `src/reference_image.py`

- [ ] **Step 1: Write the tests**

Add to `tests/test_project.py`:

```python
from PIL import Image
from src.reference_image import ReferenceImage


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
        loaded_tl, loaded_pal, _, loaded_ref = load_project(path)

        assert loaded_ref is not None
        assert loaded_ref.x == 3
        assert loaded_ref.y == 5
        assert loaded_ref.scale == 0.5
        assert loaded_ref.opacity == pytest.approx(0.7)
        assert loaded_ref.visible is False
        assert loaded_ref.path == "/tmp/photo.png"
        assert loaded_ref.image.size == (20, 15)
        # Check pixel data survived
        assert loaded_ref.image.getpixel((0, 0)) == (255, 0, 0, 128)

    def test_save_load_without_reference_image(self, tmp_path):
        """No reference image should load as None."""
        path = str(tmp_path / "no_ref.retro")
        timeline = AnimationTimeline(8, 8)
        palette = Palette("Pico-8")

        save_project(path, timeline, palette)
        loaded_tl, loaded_pal, _, loaded_ref = load_project(path)
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
                "name": "Layer 1", "type": "rgba",
                "pixels": "iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAAC0lEQVQYV2NgGPYAAAIIAAEbhpkRAAAAAElFTkSuQmCC",
                "visible": True, "opacity": 1.0, "blend_mode": "normal",
                "locked": False, "depth": 0, "is_group": False,
                "effects": [], "clipping": False
            }], "active_layer": 0}],
            "tags": [], "tool_settings": {}
        }
        with open(path, "w") as f:
            json.dump(old_project, f)

        loaded_tl, loaded_pal, _, loaded_ref = load_project(path)
        assert loaded_ref is None
        assert loaded_tl.width == 8
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_project.py::TestReferenceImagePersistence -v`
Expected: FAIL — `save_project() got an unexpected keyword argument 'reference_image'` and return value unpacking errors

- [ ] **Step 3: Update save_project to accept and serialize reference image**

In `src/project.py`, update the `save_project` function:

Change the signature at line 14:
```python
def save_project(filepath: str, timeline: AnimationTimeline,
                 palette: Palette, tool_settings: dict | None = None,
                 reference_image=None) -> None:
```

Add import at top of file (after existing imports):
```python
from src.reference_image import ReferenceImage
```

After `"tool_settings": tool_settings or {},` (line 141), add reference image serialization and update version logic. Replace lines 128-145:

```python
    # --- Serialize reference image ---
    ref_data = None
    if reference_image is not None:
        buf = io.BytesIO()
        reference_image.image.save(buf, format="PNG")
        ref_data = {
            "data": base64.b64encode(buf.getvalue()).decode("ascii"),
            "x": reference_image.x,
            "y": reference_image.y,
            "scale": reference_image.scale,
            "opacity": reference_image.opacity,
            "visible": reference_image.visible,
            "path": reference_image.path,
        }

    has_ref = ref_data is not None
    if has_ref:
        version = 6
    elif tool_settings:
        version = 5
    elif getattr(timeline, 'color_mode', 'rgba') == 'indexed':
        version = 4
    else:
        version = 3

    project = {
        "version": version,
        "color_mode": getattr(timeline, 'color_mode', 'rgba'),
        "width": timeline.width,
        "height": timeline.height,
        "fps": timeline.fps,
        "current_frame": timeline.current_index,
        "palette_name": palette.name,
        "palette_colors": [list(c) for c in palette.colors],
        "selected_color_index": palette.selected_index,
        "tilesets": tilesets_data,
        "frames": frames_data,
        "tags": timeline.tags,
        "tool_settings": tool_settings or {},
    }
    if ref_data is not None:
        project["reference_image"] = ref_data

    with open(filepath, "w") as f:
        json.dump(project, f)
```

- [ ] **Step 4: Update load_project to return reference image**

Change the return type and add deserialization. At the end of `load_project` (replace lines 289-290):

```python
    # --- Deserialize reference image ---
    ref_data = project.get("reference_image")
    loaded_ref = None
    if ref_data is not None:
        ref_bytes = base64.b64decode(ref_data["data"])
        ref_img = Image.open(io.BytesIO(ref_bytes)).convert("RGBA")
        loaded_ref = ReferenceImage(
            image=ref_img,
            x=ref_data.get("x", 0),
            y=ref_data.get("y", 0),
            scale=ref_data.get("scale", 1.0),
            opacity=ref_data.get("opacity", 0.3),
            visible=ref_data.get("visible", True),
            path=ref_data.get("path", ""),
        )

    tool_settings_data = project.get("tool_settings", {})
    return timeline, palette, tool_settings_data, loaded_ref
```

- [ ] **Step 5: Update all existing callers of load_project to unpack 4 values**

Search for `load_project(` in the codebase. The callers are:

In `src/file_ops.py` line 108:
```python
# Old:
self.timeline, self.palette, tool_settings_data = load_project(path)
# New:
self.timeline, self.palette, tool_settings_data, loaded_ref = load_project(path)
```

In `src/cli.py` — search for `load_project` calls and add `_` for the 4th return value.

In `src/scripting.py` — search for `load_project` calls and add `_` for the 4th return value.

In existing tests `tests/test_project.py` — update existing unpacking lines:
```python
# Old:
loaded_tl, loaded_pal, _ = load_project(path)
# New:
loaded_tl, loaded_pal, _, _ = load_project(path)
```

- [ ] **Step 6: Run all tests to verify they pass**

Run: `pytest tests/test_project.py -v`
Expected: All tests PASS (both new and existing)

---

### Task 3: Rendering Pipeline Update

**Files:**
- Modify: `src/canvas.py:10-19` (build_render_image signature), `src/canvas.py:67-77` (compositing), `src/canvas.py:263-274` (render method)
- Modify: `tests/test_canvas_rendering.py`

- [ ] **Step 1: Write the tests**

Add to `tests/test_canvas_rendering.py`:

```python
from src.reference_image import ReferenceImage


class TestReferenceImageRendering:
    def test_reference_image_composites_at_position(self):
        """Reference image should appear at specified (x, y) position."""
        grid = PixelGrid(8, 8)
        ref_img = Image.new("RGBA", (2, 2), (255, 0, 0, 255))
        ref = ReferenceImage(image=ref_img, x=2, y=3, scale=1.0, opacity=1.0)
        img = build_render_image(grid, pixel_size=1, show_grid=False,
                                 reference=ref)
        # Pixel at (2, 3) should be red (ref composited over checkerboard)
        r, g, b = img.getpixel((2, 3))
        assert r == 255
        assert g == 0
        assert b == 0

    def test_reference_image_with_scale(self):
        """Reference image at scale=2.0 should cover 2x area in canvas pixels."""
        grid = PixelGrid(8, 8)
        ref_img = Image.new("RGBA", (2, 2), (0, 255, 0, 255))
        ref = ReferenceImage(image=ref_img, x=0, y=0, scale=2.0, opacity=1.0)
        img = build_render_image(grid, pixel_size=1, show_grid=False,
                                 reference=ref)
        # Scaled to 4x4, so (3, 3) should be green
        r, g, b = img.getpixel((3, 3))
        assert g == 255
        # (4, 4) should be checkerboard, not green
        r2, g2, b2 = img.getpixel((4, 4))
        assert g2 != 255

    def test_reference_image_with_opacity(self):
        """Reference image at reduced opacity should blend with background."""
        grid = PixelGrid(4, 4)
        ref_img = Image.new("RGBA", (4, 4), (255, 0, 0, 255))
        ref = ReferenceImage(image=ref_img, x=0, y=0, scale=1.0, opacity=0.5)
        img = build_render_image(grid, pixel_size=1, show_grid=False,
                                 reference=ref)
        r, g, b = img.getpixel((0, 0))
        # Red @ 50% over white checkerboard -> ~228 red
        assert 200 < r < 255
        assert g < r
        assert b < r

    def test_reference_none_renders_normally(self):
        """Passing reference=None should render identically to no reference."""
        grid = PixelGrid(4, 4)
        img_none = build_render_image(grid, pixel_size=1, show_grid=False,
                                      reference=None)
        img_default = build_render_image(grid, pixel_size=1, show_grid=False)
        assert list(img_none.getdata()) == list(img_default.getdata())

    def test_old_reference_image_param_still_works(self):
        """Backward compat: old reference_image + reference_opacity params."""
        grid = PixelGrid(4, 4)
        ref_img = Image.new("RGBA", (4, 4), (255, 0, 0, 255))
        img = build_render_image(grid, pixel_size=1, show_grid=False,
                                 reference_image=ref_img,
                                 reference_opacity=1.0)
        r, g, b = img.getpixel((0, 0))
        assert r == 255
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_canvas_rendering.py::TestReferenceImageRendering -v`
Expected: FAIL — `build_render_image() got an unexpected keyword argument 'reference'`

- [ ] **Step 3: Update build_render_image in canvas.py**

Replace the function signature (lines 10-19) with:

```python
def build_render_image(grid: PixelGrid, pixel_size: int,
                       show_grid: bool,
                       onion_grid: PixelGrid | None = None,
                       onion_past_grids: list | None = None,
                       onion_future_grids: list | None = None,
                       onion_past_tint: tuple = (255, 0, 170),
                       onion_future_tint: tuple = (0, 240, 255),
                       reference: 'ReferenceImage | None' = None,
                       reference_image: Image.Image | None = None,
                       reference_opacity: float = 0.3,
                       tiled_mode: str = "off") -> Image.Image:
```

Replace the reference compositing block (lines 67-77) with:

```python
    # Composite reference image between background and pixel data
    # Support new ReferenceImage object or legacy (reference_image, reference_opacity) params
    if reference is not None and reference.visible:
        orig_w, orig_h = reference.image.size
        scaled_w = max(1, int(orig_w * reference.scale))
        scaled_h = max(1, int(orig_h * reference.scale))
        ref_scaled = reference.image.resize((scaled_w, scaled_h), Image.LANCZOS)
        ref_arr = np.array(ref_scaled, dtype=np.uint8)
        ref_arr[:, :, 3] = (ref_arr[:, :, 3].astype(np.float32)
                            * reference.opacity).astype(np.uint8)
        ref_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ref_layer.paste(Image.fromarray(ref_arr, "RGBA"), (reference.x, reference.y))
        bg = Image.alpha_composite(bg, ref_layer)
    elif reference_image is not None:
        ref = reference_image.copy()
        if ref.size != (w, h):
            ref = ref.resize((w, h), Image.LANCZOS)
        ref_arr = np.array(ref, dtype=np.uint8)
        ref_arr[:, :, 3] = (ref_arr[:, :, 3].astype(np.float32)
                            * reference_opacity).astype(np.uint8)
        ref_layer = Image.fromarray(ref_arr, "RGBA")
        bg = Image.alpha_composite(bg, ref_layer)
```

- [ ] **Step 4: Update PixelCanvas.render method**

Replace the render method signature (lines 263-267) with:

```python
    def render(self, onion_grid: PixelGrid | None = None,
               onion_past_grids=None, onion_future_grids=None,
               reference: 'ReferenceImage | None' = None,
               reference_image: Image.Image | None = None,
               reference_opacity: float = 0.3,
               tiled_mode: str = "off") -> None:
```

Update the call to `build_render_image` inside render (lines 268-274):

```python
        img = build_render_image(self.grid, self.pixel_size, self.show_grid,
                                 onion_grid,
                                 onion_past_grids=onion_past_grids,
                                 onion_future_grids=onion_future_grids,
                                 reference=reference,
                                 reference_image=reference_image,
                                 reference_opacity=reference_opacity,
                                 tiled_mode=tiled_mode)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_canvas_rendering.py -v`
Expected: All tests PASS (new and existing)

---

### Task 4: App State & Render Callers

**Files:**
- Modify: `src/app.py:163-166` (init vars), `src/app.py:837-866` (render callers)

- [ ] **Step 1: Update __init__ state variables**

In `src/app.py`, replace lines 163-166:

```python
        # Reference image overlay
        self._reference_image = None  # PIL Image or None
        self._reference_opacity = 0.3
        self._reference_visible = False
```

With:

```python
        # Reference image overlay (Krita-style positionable)
        self._reference = None  # ReferenceImage or None

        # Reference drag state
        self._ref_dragging = False
        self._ref_drag_start = None  # (x, y) screen coords at drag start
        self._ref_drag_origin = None  # (ref.x, ref.y) at drag start
```

- [ ] **Step 2: Update _refresh_canvas**

In `src/app.py`, replace the reference line in `_refresh_canvas` (line 839):

```python
        ref = self._reference_image if self._reference_visible else None
```

With:

```python
        ref = self._reference
```

And update the render call (lines 842-845):

```python
        self.pixel_canvas.render(onion_past_grids=past if past else None,
                                 onion_future_grids=future if future else None,
                                 reference=ref)
```

- [ ] **Step 3: Update _render_canvas**

In `src/app.py`, replace the reference line in `_render_canvas` (line 851):

```python
        ref = self._reference_image if self._reference_visible else None
```

With:

```python
        ref = self._reference
```

And update the render call (lines 862-866):

```python
        self.pixel_canvas.render(onion_past_grids=past if past else None,
                                 onion_future_grids=future if future else None,
                                 reference=ref,
                                 tiled_mode=self._tiled_mode)
```

- [ ] **Step 4: Run full test suite**

Run: `pytest tests/ -x -q`
Expected: All tests pass (the `test_cli_info` pre-existing failure is expected)

---

### Task 5: File Ops — Load, Toggle, Clear, Reset

**Files:**
- Modify: `src/file_ops.py:165-186` (load/toggle reference), `src/file_ops.py:456-463` (reset_state)
- Modify: `src/file_ops.py:108-114` (open_project to use loaded ref)

- [ ] **Step 1: Update _load_reference_image**

In `src/file_ops.py`, replace `_load_reference_image` (lines 165-181):

```python
    def _load_reference_image(self):
        path = ask_open_file(self.root, filetypes=[
            ("Image files", "*.png;*.jpg;*.jpeg;*.bmp;*.gif"),
            ("All files", "*.*")
        ])
        if path:
            try:
                from src.reference_image import ReferenceImage
                img = Image.open(path).convert("RGBA")
                ref = ReferenceImage(image=img, path=path)
                ref.fit_to_canvas(self.timeline.width, self.timeline.height)
                self._reference = ref
                self._render_canvas()
                self._update_status(
                    "Reference image loaded (Alt+drag to move, Ctrl+Alt+scroll to resize)")
            except Exception as e:
                show_error(self.root, "Load Error", str(e))
```

- [ ] **Step 2: Update _toggle_reference**

Replace `_toggle_reference` (lines 183-186):

```python
    def _toggle_reference(self):
        if self._reference is not None:
            self._reference.visible = not self._reference.visible
            self._render_canvas()
```

- [ ] **Step 3: Add _clear_reference method**

Add after `_toggle_reference`:

```python
    def _clear_reference(self):
        self._reference = None
        self._render_canvas()
        self._update_status("Reference image cleared")
```

- [ ] **Step 4: Update _reset_state — stop clearing reference**

In `_reset_state` (lines 462-463), remove these two lines:

```python
        self._reference_image = None
        self._reference_visible = False
```

- [ ] **Step 5: Update _open_project to restore loaded reference**

In `_open_project`, after `self._reset_state()` (around line 114), add:

```python
        self._reference = loaded_ref
```

And update the unpacking at line 108:

```python
                self.timeline, self.palette, tool_settings_data, loaded_ref = load_project(path)
```

For Aseprite/PSD imports (which don't have reference images), add before `self._reset_state()`:

```python
            loaded_ref = None
```

- [ ] **Step 6: Update _new_canvas to clear reference**

In `_new_canvas`, after `self._reset_state()` (line 134), add:

```python
        self._reference = None
```

- [ ] **Step 7: Update _save_project to include reference**

Find the `save_project` call in `file_ops.py` and add the `reference_image` parameter:

```python
save_project(path, self.timeline, self.palette,
             tool_settings=self._tool_settings.to_dict(),
             reference_image=self._reference)
```

- [ ] **Step 8: Run full test suite**

Run: `pytest tests/ -x -q`
Expected: All tests pass

---

### Task 6: Menu & Opacity UI

**Files:**
- Modify: `src/app.py:242-243` (file menu reference section)

- [ ] **Step 1: Update File menu entries**

In `src/app.py`, replace the single reference menu item (lines 242-243):

```python
        file_menu.add_command(label="Load Reference Image...",
                              command=self._load_reference_image)
```

With:

```python
        file_menu.add_separator()
        file_menu.add_command(label="Load Reference Image...",
                              command=self._load_reference_image,
                              accelerator="Ctrl+R")
        file_menu.add_command(label="Toggle Reference Visibility",
                              command=self._toggle_reference)
        file_menu.add_command(label="Clear Reference Image",
                              command=self._clear_reference)

        # Reference opacity submenu
        self._ref_opacity_var = tk.DoubleVar(value=0.3)
        opacity_menu = tk.Menu(file_menu, tearoff=0,
                               bg=BG_PANEL, fg=TEXT_PRIMARY,
                               activebackground=ACCENT_CYAN,
                               activeforeground=BG_DEEP)
        for pct in (10, 20, 30, 50, 75, 100):
            val = pct / 100.0
            opacity_menu.add_radiobutton(
                label=f"{pct}%", variable=self._ref_opacity_var,
                value=val, command=lambda v=val: self._set_ref_opacity(v))
        file_menu.add_cascade(label="Reference Opacity", menu=opacity_menu)
```

- [ ] **Step 2: Add _set_ref_opacity method to file_ops.py**

Add to `src/file_ops.py` after `_clear_reference`:

```python
    def _set_ref_opacity(self, value):
        if self._reference is not None:
            self._reference.opacity = value
            self._ref_opacity_var.set(value)
            self._render_canvas()
```

- [ ] **Step 3: Sync opacity var when loading reference**

At the end of `_load_reference_image` (after `self._reference = ref`), add:

```python
                self._ref_opacity_var.set(ref.opacity)
```

At the end of `_open_project` (after `self._reference = loaded_ref`), add:

```python
        if self._reference is not None:
            self._ref_opacity_var.set(self._reference.opacity)
```

- [ ] **Step 4: Run the app and verify menus appear**

Run: `python main.py`
Expected: File menu shows all 4 reference image entries with opacity submenu. No crashes.

---

### Task 7: Interaction — Alt+Drag Move & Ctrl+Alt+Scroll Resize

**Files:**
- Modify: `src/input_handler.py:41-50` (click handler), add new methods
- Modify: `src/app.py:536-539` (scroll bindings)

- [ ] **Step 1: Add Alt+drag detection in _on_canvas_click**

In `src/input_handler.py`, at the top of `_on_canvas_click` (after line 41, before the rotation check), add:

```python
        # Alt+click starts reference image drag
        alt_held = bool(event_state & 0x20000)
        if alt_held and self._reference is not None:
            self._ref_begin_drag(x, y)
            return
```

- [ ] **Step 2: Add Alt+drag handling in _on_canvas_drag**

In `_on_canvas_drag` (after line 171, before the rotation check), add:

```python
        # Reference image drag
        if self._ref_dragging:
            self._ref_update_drag(x, y)
            return
```

- [ ] **Step 3: Add drag end in _on_canvas_release**

In `_on_canvas_release` (at the top, after line 291), add:

```python
        if self._ref_dragging:
            self._ref_end_drag()
            return
```

- [ ] **Step 4: Implement reference drag methods**

Add to `src/input_handler.py` at the end of the `InputHandlerMixin` class:

```python
    # --- Reference image drag ---

    def _ref_begin_drag(self, x, y):
        """Start dragging the reference image."""
        self._ref_dragging = True
        self._ref_drag_start = (x, y)
        self._ref_drag_origin = (self._reference.x, self._reference.y)

    def _ref_update_drag(self, x, y):
        """Update reference position during drag."""
        if self._ref_drag_start is None:
            return
        dx = x - self._ref_drag_start[0]
        dy = y - self._ref_drag_start[1]
        self._reference.x = self._ref_drag_origin[0] + dx
        self._reference.y = self._ref_drag_origin[1] + dy
        self._render_canvas()

    def _ref_end_drag(self):
        """End reference image drag."""
        self._ref_dragging = False
        self._ref_drag_start = None
        self._ref_drag_origin = None

    def _ref_adjust_scale(self, delta, mx, my):
        """Adjust reference image scale, anchoring around (mx, my)."""
        ref = self._reference
        if ref is None:
            return
        old_scale = ref.scale
        new_scale = max(0.1, min(10.0, old_scale + delta))
        if new_scale == old_scale:
            return
        # Anchor around mouse position: adjust x, y so pixel under cursor stays
        ratio = new_scale / old_scale
        ref.x = int(mx - (mx - ref.x) * ratio)
        ref.y = int(my - (my - ref.y) * ratio)
        ref.scale = new_scale
        self._render_canvas()
```

- [ ] **Step 5: Bind Ctrl+Alt+scroll for reference resize**

In `src/app.py`, after the existing scroll bindings (after line 539), add:

```python
        self.pixel_canvas.bind("<Control-Alt-MouseWheel>",
                               lambda e: self._on_ref_scroll(e))
```

Add the handler method in `src/input_handler.py` (in `InputHandlerMixin`, after `_ref_adjust_scale`):

```python
    def _on_ref_scroll(self, event):
        """Ctrl+Alt+scroll: resize reference image."""
        if self._reference is None:
            return
        delta = 0.1 if event.delta > 0 else -0.1
        # Convert screen coords to canvas pixel coords
        x, y = self.pixel_canvas._to_grid_coords(event)
        self._ref_adjust_scale(delta, x, y)
```

- [ ] **Step 6: Run the app and test interaction**

Run: `python main.py`
Test steps:
1. Load a reference image via File > Load Reference Image
2. Alt+click and drag on canvas — reference should move
3. Ctrl+Alt+scroll — reference should resize around cursor
4. Save project, close, reopen — reference should persist

---

### Task 8: Update Remaining Callers & Final Cleanup

**Files:**
- Modify: `src/cli.py` (load_project unpacking)
- Modify: `src/scripting.py` (load_project unpacking)

- [ ] **Step 1: Find and update all load_project callers**

Search for `load_project(` in `src/cli.py` and `src/scripting.py`. Update each to unpack 4 values:

In `src/cli.py`, find each `load_project` call and change:
```python
# Old:
timeline, palette, _ = load_project(path)
# New:
timeline, palette, _, _ = load_project(path)
```

In `src/scripting.py`, find each `load_project` call and change:
```python
# Old:
self.timeline, self.palette, _ = load_project(path)
# New:
self.timeline, self.palette, _, _ = load_project(path)
```

- [ ] **Step 2: Run full test suite**

Run: `pytest tests/ -x -q`
Expected: All tests pass

- [ ] **Step 3: Manual smoke test**

Run: `python main.py`
Verify:
1. Load reference image — appears on canvas at correct scale
2. Alt+drag — moves reference
3. Ctrl+Alt+scroll — resizes reference around cursor
4. File > Reference Opacity > 75% — reference becomes more visible
5. Toggle Reference Visibility — hides/shows
6. Save project, reopen — reference persists with position/scale/opacity
7. New canvas — reference is cleared
8. Open old .retro file (without reference) — loads fine, no reference
