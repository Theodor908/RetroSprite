# Batch 1: Selection System & Custom Brushes

**Date:** 2026-03-11
**Scope:** Freehand lasso tool, unified selection model with set operations, custom brush capture

## Overview

Batch 1 upgrades RetroSprite's selection system from two disconnected representations (rect tuple + pixel set) into a unified pixel-set model, adds a freehand lasso tool, and enables custom brush capture from selections.

## 1. Unified Selection Model

### Problem
Currently `self._selection` stores `(x0, y0, x1, y1)` for rect select and `self._wand_selection` stores `set[tuple[int,int]]` for magic wand. These are separate code paths with separate rendering, copy, fill, and delete logic. Adding selection operations (add/subtract/intersect) across tools requires unification.

### Design
- Replace both with a single `self._selection_pixels: set[tuple[int,int]]`
- Rect select produces a pixel set: `{(x,y) for x in range(x0,x1+1) for y in range(y0,y1+1)}`
- Wand already produces a pixel set — no change needed
- Lasso will produce a pixel set via scanline fill

### Selection Operations
Modifier keys (consistent across rect, wand, lasso):
- **No modifier:** Replace — `selection = new_pixels`
- **Shift:** Add — `selection = selection | new_pixels`
- **Ctrl:** Subtract — `selection = selection - new_pixels`
- **Shift+Ctrl:** Intersect — `selection = selection & new_pixels`

### Migration
- Remove `self._selection` (rect tuple) and `self._wand_selection` (pixel set)
- Update `_copy_selection`, `_fill_selection`, `_delete_selection` to work with `_selection_pixels` only
- Remove `draw_selection()` (rect marching ants) — all selections rendered via `draw_wand_selection()` (pixel boundary outlines)
- Update `clear_selection()` to clear `_selection_pixels`

### Files Changed
- `src/app.py` — selection state, mouse handlers, copy/fill/delete, modifier detection
- `src/canvas.py` — remove `draw_selection()` if unused after migration

## 2. Freehand Lasso Tool

### Interaction
1. User selects lasso tool from toolbar
2. Click + drag draws a freeform boundary (tracked as `list[tuple[int,int]]` of pixel coordinates)
3. On mouse release, auto-close the path (connect last point to first)
4. Fill interior using scanline algorithm to produce `set[tuple[int,int]]`
5. Apply selection operation based on modifiers (replace/add/subtract/intersect)

### Implementation
- New `LassoTool` class in `src/tools.py` with a `fill_interior(points) -> set` static method
- Scanline fill: for each row in bounding box, count edge crossings to determine inside/outside
- App-level: track points during drag, draw preview path as overlay, finalize on release

### Visual Feedback
- During drag: draw the lasso path as connected line segments on canvas overlay
- After release: render selection boundary via `draw_wand_selection()` (existing)

### Options Bar
- No size/dither/pixel-perfect — lasso only needs symmetry (debatable) and selection mode indicator
- Config: `"lasso": {}` in `TOOL_OPTIONS`

### Files Changed
- `src/tools.py` — new `LassoTool` class
- `src/app.py` — mouse handlers for lasso (click/drag/release), tool routing
- `src/canvas.py` — `draw_lasso_preview()` for in-progress path overlay
- `src/ui/toolbar.py` — add lasso icon/button
- `src/ui/options_bar.py` — add lasso entry
- `src/ui/icons.py` — lasso icon

## 3. Custom Brushes (Capture from Selection)

### Workflow
1. User creates a selection (any tool: rect, wand, lasso)
2. User triggers Edit → Capture Brush (shortcut: Ctrl+B)
3. Pixels within selection bounding box are read from active layer
4. Stored as `self._custom_brush_mask: set[tuple[int,int]]` (relative offsets from center)
5. Pen and eraser use the mask instead of the square footprint

### Shape-Only Mode
- Captured brush preserves only the **shape** (which pixels are non-transparent)
- Drawing uses current foreground color with the brush shape's alpha values
- No color stamping in this iteration

### Drawing Integration
- `PenTool.apply()` and `EraserTool.apply()` accept an optional `mask: set[tuple[int,int]]` parameter
- When mask is provided, iterate over mask offsets instead of the square `range(-half, -half+size)` loop
- Symmetry and pixel-perfect still apply normally

### Reset
- Changing brush size clears custom brush
- Menu item: Edit → Reset Brush
- Status bar shows "Custom Brush" indicator when active

### Files Changed
- `src/app.py` — capture logic, brush state, draw routing, menu entries
- `src/tools.py` — PenTool and EraserTool accept optional mask parameter

## Data Flow

```
Selection Tools (Rect, Wand, Lasso)
        │
        ▼
  set[tuple[int,int]]  ← unified pixel set
        │
   ┌────┼────────────┐
   ▼    ▼            ▼
 Copy  Fill    Capture Brush
 Paste Delete       │
                    ▼
          mask: set[tuple[int,int]]
                    │
                    ▼
          Pen / Eraser apply
          (iterate mask offsets)
```

## Testing Strategy
- Unit tests for `LassoTool.fill_interior()` with known polygons
- Unit tests for selection set operations (add/subtract/intersect)
- Unit tests for PenTool/EraserTool with custom mask
- Integration tests for capture brush workflow
- Verify backward compat: existing rect select and wand behavior unchanged in user-facing results

## Out of Scope (Deferred)
- Polygonal lasso (click-by-click point placement)
- Brush palette UI (save/load multiple custom brushes)
- Color stamp mode (brush retains original colors)
- Selection transform (move, scale, rotate selection content)
