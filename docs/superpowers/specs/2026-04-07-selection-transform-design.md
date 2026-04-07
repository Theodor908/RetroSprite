# Selection Rotation/Scale/Skew — Design Spec

**Date:** 2026-04-07
**Status:** Approved

## Problem

RetroSprite has a full layer rotation system (Ctrl+T, RotSprite, pivot control, 15° snap) but no way to transform a floating selection or paste before committing. Both Aseprite and Pixelorama support rotate, scale, and skew on selections. This is the second most significant feature gap after the grid system.

## Goals

- Full affine transform on floating selections: rotate, scale (uniform + non-uniform), skew
- Photoshop-style handle zones: corners for scale, midpoints for axis scale, outside for rotate, inside for move, Ctrl+drag for skew
- Auto-show handles on paste, Ctrl+T to re-enter or float a selection
- RotSprite quality on commit, fast nearest-neighbor preview while dragging
- Clip to canvas on commit (standard pixel art editor behavior)

## User Decisions

| Decision | Choice |
|----------|--------|
| Transforms | Rotate + scale (uniform/non-uniform) + skew (full affine) |
| Activation | Auto on paste + Ctrl+T to re-enter or float selection |
| Handle style | Photoshop-style zones (corners=scale, midpoints=axis scale, outside=rotate, Ctrl+drag=skew) |
| Rotation quality | RotSprite on commit, nearest-neighbor preview while dragging |
| Canvas overflow | Clip to canvas (pixels outside discarded) |

---

## Data Model

### `src/selection_transform.py`

```python
@dataclass
class SelectionTransform:
    """Active transform state for a floating selection."""
    pixels: Image.Image          # original RGBA pixels (untransformed)
    position: tuple[int, int]    # top-left (x, y) on canvas
    rotation: float              # degrees
    scale_x: float               # horizontal scale factor (default 1.0)
    scale_y: float               # vertical scale factor (default 1.0)
    skew_x: float                # horizontal skew in degrees (default 0.0)
    skew_y: float                # vertical skew in degrees (default 0.0)
    pivot: tuple[float, float]   # rotation center relative to selection center
```

Identity state: `rotation=0, scale_x=1, scale_y=1, skew_x=0, skew_y=0`.

Affine transform chain order: **skew → scale → rotate around pivot** (matches Photoshop Free Transform).

---

## Handle Zones & Interaction

### Handle Layout

```
        [midpoint-top]
  [corner]────────────────[corner]
  |                              |
  [midpoint-left]    [midpoint-right]
  |                              |
  [corner]────────────────[corner]
        [midpoint-bottom]
              (pivot)
```

### Zone Behaviors

| Zone | Visual | Drag | Modifier |
|------|--------|------|----------|
| Corner circles (4) | Filled circles | Uniform scale | Shift = non-uniform |
| Edge midpoint squares (4) | Filled squares | Non-uniform scale (one axis) | — |
| Outside bounding box | No visual | Free rotation around pivot | Shift = 15° snap |
| Inside bounding box | No visual | Move/translate | — |
| Pivot dot | Magenta circle | Reposition rotation center | — |
| Corner circles | — | — | Ctrl+drag = skew along nearest axis (horizontal corners skew X, vertical corners skew Y) |

### Cursor Feedback

- Corners: `sizing` (diagonal resize)
- Midpoints: `sb_h_double_arrow` / `sb_v_double_arrow`
- Outside: `exchange` (rotation)
- Inside: `fleur` (move)
- Pivot: `crosshair`

---

## Activation Flow

### On paste (Ctrl+V)

1. Floating paste pixels extracted (existing behavior)
2. `SelectionTransform` created with identity values
3. Transform handles appear immediately
4. User can interact or click outside to commit

### On Ctrl+T with existing floating paste

1. Re-enter transform mode, handles reappear

### On Ctrl+T with active selection but no floating paste

1. Float the selected pixels (cut from layer into floating paste)
2. Create `SelectionTransform`, show handles

---

## Live Preview

While dragging:
- Compute affine transform: skew → scale → rotate (nearest-neighbor)
- Render transformed pixels as semi-transparent overlay
- Update every mouse motion event for responsive feedback

---

## Commit & Cancel

### Commit (Enter, click outside bounding box, or switch tools)

1. Apply RotSprite for rotation component
2. Scale and skew via `Image.transform(AFFINE)` with nearest-neighbor
3. Paste onto active layer at current position
4. Clip to canvas bounds (discard outside pixels)
5. Push undo state
6. Clear floating paste and transform state

### Cancel (Esc)

1. If floated by Ctrl+T: paste original pixels back untransformed
2. If from Ctrl+V: discard paste entirely
3. Clear transform state

---

## Context Bar

When in selection transform mode, the options bar shows:

```
Transform | Angle: [0.0°] | Scale: [100]% | [ Apply ] [ Cancel ]
```

- Enter = apply
- Esc = cancel

---

## Functions

### `src/selection_transform.py`

```python
def compute_affine_preview(transform: SelectionTransform) -> Image.Image
```
Fast preview using Pillow's `Image.transform(AFFINE)` with nearest-neighbor for all components (skew, scale, rotate).

```python
def compute_affine_final(transform: SelectionTransform) -> Image.Image
```
Final quality render: RotSprite for rotation, `Image.transform(AFFINE)` for scale/skew.

```python
def hit_test_transform_handle(transform: SelectionTransform, 
                               canvas_x: int, canvas_y: int,
                               pixel_size: int) -> str | None
```
Returns zone: `"corner:0"` through `"corner:3"`, `"midpoint:top"` etc., `"outside"`, `"inside"`, `"pivot"`, or `None`.

```python
def get_transform_bounding_box(transform: SelectionTransform) -> list[tuple[float, float]]
```
Returns 4 corners of the transformed bounding box in canvas coordinates.

---

## Files Changed/Created

| File | Action | Purpose |
|------|--------|---------|
| `src/selection_transform.py` | **New** | `SelectionTransform` dataclass, affine math, hit testing, preview/final render |
| `src/input_handler.py` | **Modified** | Transform mode mouse handling, enter/exit, zone-specific drag |
| `src/canvas.py` | **Modified** | `draw_transform_handles()` for bounding box + corner circles + midpoint squares + pivot |
| `src/app.py` | **Modified** | `self._selection_transform` state, Ctrl+T binding, context bar update |
| `tests/test_selection_transform.py` | **New** | Transform math, hit testing, affine computation, commit/cancel |
| `README.md` | **Modified** | Add selection transform features |

## Dependencies

No new dependencies. Uses:
- Pillow `Image.transform(AFFINE)` for skew/scale
- Existing `src/rotsprite.py` for RotSprite rotation quality
- Existing canvas overlay system for handles

## Testing

### `tests/test_selection_transform.py`

- `test_identity_transform` — no-op transform returns original pixels
- `test_rotation_90` — 90° rotation produces correct dimensions
- `test_scale_2x` — 2x scale doubles dimensions
- `test_scale_non_uniform` — scale_x=2, scale_y=1 doubles width only
- `test_skew_horizontal` — non-zero skew_x produces sheared output
- `test_affine_preview_fast` — preview uses nearest-neighbor (quick, no RotSprite)
- `test_affine_final_rotsprite` — final commit uses RotSprite for rotation
- `test_hit_test_corner` — click on corner returns "corner:N"
- `test_hit_test_midpoint` — click on midpoint returns "midpoint:side"
- `test_hit_test_outside` — click outside box returns "outside"
- `test_hit_test_inside` — click inside box returns "inside"
- `test_hit_test_pivot` — click on pivot returns "pivot"
- `test_clip_to_canvas` — transformed pixels outside canvas bounds are discarded
- `test_commit_pushes_undo` — verify undo state is saved on commit
