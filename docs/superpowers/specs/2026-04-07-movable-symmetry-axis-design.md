# Movable Symmetry Axis — Design Spec

**Date:** 2026-04-07
**Status:** Approved

## Problem

RetroSprite's symmetry system mirrors around the fixed canvas center with no visual feedback. Users can't see or move the axis. Both Aseprite and Pixelorama show a visible, draggable symmetry axis.

## Goals

- Visible dashed guide line on canvas when symmetry is active
- Drag the line to reposition the axis
- Right-click for precise numeric axis positioning
- Axis position saved per-project in .retro files
- "Both" mode uses a shared center point (not independent axes)

## User Decisions

| Decision | Choice |
|----------|--------|
| Visual guide | Always show axis line when symmetry is on |
| Repositioning | Drag directly + right-click for numeric entry |
| Persistence | Per-project (saved in .retro files) |
| Both mode | Shared center point for both axes |

---

## Visual Guide

When `_symmetry_mode != "off"`:

- **Horizontal symmetry:** A vertical dashed line drawn at `_symmetry_axis_x` spanning the full canvas height
- **Vertical symmetry:** A horizontal dashed line drawn at `_symmetry_axis_y` spanning the full canvas width
- **Both:** Both lines drawn, crossing at `(_symmetry_axis_x, _symmetry_axis_y)`

Line style: magenta (`#ff00ff`), dash pattern `(4, 4)`, width 1, drawn as a canvas overlay (on top of pixels, below tool cursors). Uses the `"symmetry_axis"` tag for easy clearing.

---

## Repositioning

### Drag

- When hovering within 6 screen pixels of the axis line, cursor changes:
  - Vertical axis line → `sb_h_double_arrow`
  - Horizontal axis line → `sb_v_double_arrow`
- Click and drag to move the axis
- Axis snaps to integer pixel boundaries
- Canvas re-renders the guide line on each drag motion
- The mirroring updates live as the axis moves

### Precise Entry (Right-Click)

- Right-click on the axis line opens a small `tk.Toplevel` popup
- Contains a spinbox with the current axis position (pixel value)
- For "both" mode: shows both X and Y spinboxes
- OK applies, Cancel dismisses
- Range: 0 to canvas width/height

---

## Data Model

### App State (in `src/app.py`)

```python
self._symmetry_axis_x = self.timeline.width // 2
self._symmetry_axis_y = self.timeline.height // 2
self._symmetry_axis_dragging = None  # "x", "y", or None
```

Default: canvas center. Reset to center when canvas is resized.

---

## Mirroring Formula

Current (`input_handler.py:_apply_symmetry_draw`):

```python
cx = self.timeline.width // 2
cy = self.timeline.height // 2
```

New:

```python
cx = self._symmetry_axis_x
cy = self._symmetry_axis_y
```

The mirror formulas are unchanged: `2 * cx - x - 1` for horizontal, `2 * cy - y - 1` for vertical.

---

## Axis Guide Rendering

### `src/canvas.py`

```python
def draw_symmetry_axis(self, axis_x: int | None, axis_y: int | None,
                        canvas_w: int, canvas_h: int, zoom: int) -> None
```

Draws dashed magenta lines at the axis positions. Called after `_render_canvas()` whenever symmetry is active.

```python
def clear_symmetry_axis(self) -> None
```

Removes the axis overlay (deletes tag `"symmetry_axis"`).

---

## Axis Interaction

### Hit Testing

```python
def _hit_test_symmetry_axis(self, x: int, y: int) -> str | None
```

In `InputHandlerMixin`. Returns `"x"` if near the vertical axis line, `"y"` if near the horizontal axis line, or `None`. Threshold: 6 screen pixels (adjusted by zoom).

### Mouse Routing

In `_on_canvas_motion`: when symmetry is active and not in another mode, check axis hover and set cursor.

In `_on_canvas_click`: if click hits the axis, start axis drag instead of tool dispatch.

In `_on_canvas_drag`: if `_symmetry_axis_dragging` is set, update the axis position.

In `_on_canvas_release`: clear drag state, re-render.

Right-click on axis: open position popup.

---

## Project Save/Load

### `src/project.py`

Add to the project data dict:

```python
"symmetry_axis_x": self._symmetry_axis_x,
"symmetry_axis_y": self._symmetry_axis_y,
```

On load, read these values if present, otherwise default to canvas center.

---

## Canvas Resize

When canvas dimensions change (via resize dialog), reset axis to new center:

```python
self._symmetry_axis_x = new_width // 2
self._symmetry_axis_y = new_height // 2
```

---

## Functions

### `src/canvas.py`

```python
def draw_symmetry_axis(self, axis_x: int | None, axis_y: int | None,
                        canvas_w: int, canvas_h: int, zoom: int) -> None
```
Draw dashed magenta axis guide lines.

```python
def clear_symmetry_axis(self) -> None
```
Remove axis overlay.

### `src/input_handler.py`

```python
def _hit_test_symmetry_axis(self, x: int, y: int) -> str | None
```
Returns "x", "y", or None based on proximity to axis lines.

```python
def _show_axis_position_popup(self, axis: str) -> None
```
Opens a small dialog for precise axis positioning.

---

## Files Changed/Created

| File | Action | Purpose |
|------|--------|---------|
| `src/app.py` | **Modify** | Add axis state vars, reset on resize, render axis after canvas |
| `src/input_handler.py` | **Modify** | Update `_apply_symmetry_draw`, add axis drag/hit-test, right-click popup |
| `src/canvas.py` | **Modify** | `draw_symmetry_axis()`, `clear_symmetry_axis()` |
| `src/project.py` | **Modify** | Save/load axis position |
| `tests/test_symmetry_axis.py` | **New** | Mirroring with custom axis, hit testing, save/load |

## Dependencies

No new dependencies.

## Testing

### `tests/test_symmetry_axis.py`

- `test_mirror_horizontal_default_center` — default axis mirrors same as before
- `test_mirror_horizontal_custom_axis` — axis at x=3 on 10-wide canvas mirrors correctly
- `test_mirror_vertical_custom_axis` — axis at y=4 mirrors correctly
- `test_mirror_both_custom_axis` — both mode with custom center
- `test_axis_defaults_to_center` — new canvas has axis at width//2, height//2
- `test_axis_reset_on_resize` — resizing canvas resets axis to new center
- `test_project_save_load_axis` — save and reload preserves axis position
- `test_hit_test_near_vertical_axis` — returns "x" when near vertical line
- `test_hit_test_near_horizontal_axis` — returns "y" when near horizontal line
- `test_hit_test_miss` — returns None when not near either axis
