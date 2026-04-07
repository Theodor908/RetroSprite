# Grid Snapping — Design Spec

**Date:** 2026-04-07
**Status:** Approved

## Problem

When working with sprite sheets or tiled assets, users need transforms and placements to align to grid cell boundaries. Currently all operations are pixel-precise with no grid awareness.

## Goals

- Snap transform move/scale, move tool, paste, and text placement to custom grid boundaries
- Active automatically when custom grid is visible — no separate toggle
- Respects grid offset settings

## User Decisions

| Decision | Choice |
|----------|--------|
| When active | Automatically when custom grid is visible |
| What snaps | Transform (move/scale), move tool, paste, text placement |
| Which grid | Custom grid only (1x1 pixel grid snapping is meaningless) |

---

## Snap Function

### `src/grid.py`

```python
def snap_to_grid(x: int, y: int, grid_settings: GridSettings) -> tuple[int, int]:
    """Snap coordinates to nearest custom grid intersection.

    Only snaps when custom grid is visible and has valid dimensions.
    Returns original coordinates unchanged if grid is not active.
    """
    if not grid_settings.custom_grid_visible:
        return x, y
    gw = grid_settings.custom_grid_width
    gh = grid_settings.custom_grid_height
    if gw <= 0 or gh <= 0:
        return x, y
    ox = grid_settings.custom_grid_offset_x
    oy = grid_settings.custom_grid_offset_y
    sx = round((x - ox) / gw) * gw + ox
    sy = round((y - oy) / gh) * gh + oy
    return sx, sy
```

---

## Operations That Snap

### Selection Transform — Move (inside drag)

In `_transform_handle_drag`, when zone is `"inside"`, snap the new position:

```python
new_x = start["position"][0] + dx
new_y = start["position"][1] + dy
t.position = snap_to_grid(new_x, new_y, self._grid_settings)
```

### Selection Transform — Scale (corner/midpoint drag)

When computing the new scale from corner or midpoint drag, snap the mouse position to grid before computing the scale factor. This causes the bounding box edges to align with grid lines.

### Move Tool

When moving a layer or selection, snap the offset delta to grid increments.

### Paste Position

When entering transform mode from paste (`_paste_clipboard`), snap the initial position to grid.

### Text Placement

When clicking with the text tool, snap the click position to grid before opening the dialog.

---

## When Active

Snapping activates when ALL of:
- `self._grid_settings.custom_grid_visible` is True
- `self._grid_settings.custom_grid_width > 0`
- `self._grid_settings.custom_grid_height > 0`

The `snap_to_grid` function handles this check internally — callers just pass coordinates and get them back (possibly snapped, possibly unchanged).

---

## Files Changed

| File | Action | Purpose |
|------|--------|---------|
| `src/grid.py` | **Modify** | Add `snap_to_grid()` function |
| `src/input_handler.py` | **Modify** | Apply snapping in transform drag, move tool, paste, text click |
| `tests/test_grid.py` | **Modify** | Add snap_to_grid tests |

## Dependencies

No new dependencies.

## Testing

### In `tests/test_grid.py`

- `test_snap_basic` — (5, 5) with 8x8 grid snaps to (8, 8)
- `test_snap_exact` — (16, 16) with 8x8 grid stays at (16, 16)
- `test_snap_with_offset` — (5, 5) with 8x8 grid, offset (4, 4) snaps to (4, 4)
- `test_snap_grid_not_visible` — returns original coords when grid hidden
- `test_snap_negative` — handles coordinates near 0 correctly
- `test_snap_rounds_nearest` — (3, 3) with 8x8 grid snaps to (0, 0), (5, 5) snaps to (8, 8)
