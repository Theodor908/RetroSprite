# Reference Image Overhaul — Krita-Style Positionable Overlay

**Date:** 2026-03-26
**Status:** Approved
**Scope:** Persistence, positioning, opacity control for reference images

## Problem

The reference image feature has three bugs/limitations:
1. **Not persistent** — reference image is wiped on new project, open project, or import (via `_reset_state()`)
2. **No positioning** — force-resized to canvas dimensions, no move/resize
3. **No opacity control** — hardcoded at 0.3, no UI to change it

## Solution: Krita-Style Reference Image

Model the reference image as a positionable canvas object with persistence in the `.retro` file format.

---

## 1. Data Model

New file: `src/reference_image.py`

```python
@dataclass
class ReferenceImage:
    image: Image.Image    # Original RGBA PIL image (full resolution)
    x: int = 0            # Position in canvas pixel coordinates
    y: int = 0
    scale: float = 1.0    # 1.0 = one ref pixel per one canvas pixel
    opacity: float = 0.3  # 0.0–1.0
    visible: bool = True
    path: str = ""        # Original file path (informational only)
```

**App state change** (`app.py`):
- Replace `self._reference_image`, `self._reference_opacity`, `self._reference_visible` with a single `self._reference: ReferenceImage | None = None`

**Auto-fit on load:** Calculate `scale` so the image fits within canvas bounds. Keep the original full-resolution image for later rescaling.

## 2. Persistence (.retro Format)

**Version bump:** 5 → 6

**New top-level key in project JSON:**

```json
"reference_image": {
    "data": "<base64-encoded PNG>",
    "x": 0,
    "y": 0,
    "scale": 1.0,
    "opacity": 0.3,
    "visible": true,
    "path": "C:/original/photo.png"
}
```

**Save** (`project.py:save_project`): Accept optional `ReferenceImage`. If present, encode PIL image as base64 PNG and include the dict. Bump version to 6.

**Load** (`project.py:load_project`): Return `ReferenceImage` if key exists. Older files (version ≤5) return `None` — full backward compatibility.

**`_reset_state()` change:** Stop clearing the reference image. Reference is only replaced when:
- A project is loaded (replaced by file contents or `None`)
- A new canvas is created (set to `None`)
- User explicitly clears it (new menu item)

## 3. Rendering Pipeline

**File:** `src/canvas.py:build_render_image()`

**Signature change:** Replace `reference_image: Image.Image | None` + `reference_opacity: float` with `reference: ReferenceImage | None`.

**Compositing logic:** Instead of force-resizing to canvas, place at `(x, y)` with `scale`:

```python
if reference is not None:
    ref_scaled = reference.image.resize(
        (int(orig_w * reference.scale),
         int(orig_h * reference.scale)), Image.LANCZOS)
    ref_arr = np.array(ref_scaled)
    ref_arr[:,:,3] = (ref_arr[:,:,3] * reference.opacity).astype(np.uint8)
    ref_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ref_layer.paste(Image.fromarray(ref_arr), (reference.x, reference.y))
    bg = Image.alpha_composite(bg, ref_layer)
```

**Callers updated:** `_render_canvas()` and `_refresh_canvas()` in `app.py` pass `self._reference` directly.

## 4. Interaction — Move & Resize

**Move:** Alt + left-click drag moves the reference image on the canvas. Coordinates are in canvas pixels (zoom-independent).

**Resize:** Ctrl+Alt + mouse wheel adjusts `scale` in ±0.1 increments (clamped 0.1–10.0). Scales around cursor position. (Alt+scroll alone is already bound to horizontal canvas scroll.)

**Implementation location:** New methods in `InputHandlerMixin`:
- `_ref_begin_drag(x, y)` — store start position
- `_ref_update_drag(x, y)` — update reference x/y, re-render
- `_ref_end_drag()` — clear drag state
- `_ref_adjust_scale(delta, mx, my)` — adjust scale around cursor

**Drag state** (initialized in `app.py.__init__`):
```python
self._ref_dragging: bool = False
self._ref_drag_start: tuple[int, int] | None = None
self._ref_drag_origin: tuple[int, int] | None = None
```

**No undo for reference moves** — workspace concern, not drawing operation.

## 5. UI — Menu & Opacity Control

**File menu additions:**

```
Load Reference Image...       Ctrl+R
Toggle Reference Visibility
Clear Reference Image
Reference Opacity >           (submenu: 10%, 20%, 30%, 50%, 75%, 100%)
```

- **Toggle Reference Visibility**: Toggles `ReferenceImage.visible`
- **Clear Reference Image**: Sets `self._reference = None`
- **Reference Opacity submenu**: Presets with checkmark on active value

**Keyboard shortcuts:**
- `Ctrl+R` — Load reference (existing binding preserved)
- Second `Ctrl+R` when loaded — toggle visibility (existing behavior preserved)

**Status bar messages:**
- Load: `"Reference image loaded (Alt+drag to move, Ctrl+Alt+scroll to resize)"`
- Clear: `"Reference image cleared"`

## Files Changed

| File | Change |
|------|--------|
| `src/reference_image.py` | **New** — `ReferenceImage` dataclass |
| `src/app.py` | Replace 3 reference vars with `self._reference`, add drag state vars, update `__init__`, update `_render_canvas`/`_refresh_canvas` calls |
| `src/canvas.py` | Update `build_render_image()` signature and compositing logic |
| `src/file_ops.py` | Update `_load_reference_image()`, `_toggle_reference()`, `_reset_state()`; add `_clear_reference()`, opacity submenu methods |
| `src/input_handler.py` | Add `_ref_begin_drag`, `_ref_update_drag`, `_ref_end_drag`, `_ref_adjust_scale`; hook Alt+click/drag and Ctrl+Alt+scroll |
| `src/project.py` | Update `save_project()` and `load_project()` for reference image serialization, version 6 |
| `tests/test_project.py` | Add tests for save/load with reference image, backward compat |
| `tests/test_canvas_rendering.py` | Update rendering tests for new reference parameter |

## Backward Compatibility

- Version ≤5 `.retro` files load normally with `reference = None`
- Version 6 files opened in older RetroSprite versions will ignore the unknown `reference_image` key (JSON is lenient)
