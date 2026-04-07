# Layer Groups — Design Spec

**Date:** 2026-04-07
**Status:** Approved

## Problem

Layer groups are scaffolded but non-functional. The `Layer` class has `depth` and `is_group` attributes, `flatten_layers()` handles group compositing correctly, and the timeline renders collapse arrows — but there is no way to assign layers to groups. All layers remain at `depth=0`, so indentation never shows, collapse does nothing, and groups are purely decorative.

## Design Decisions

- **One level of nesting only** (matching Aseprite/Pixelorama). Groups are always at depth 0, children at depth 1. No groups inside groups.
- **Both context menu and drag** for assigning layers to groups. Context menu for discoverability, drag for speed.
- **Empty group creation** — "Add Group" creates an empty group folder. Layers are moved in manually.

## Architecture

### Data Layer (`src/animation.py`)

Three new methods on `AnimationTimeline`:

1. **`set_layer_depth_all(idx, depth)`** — Sets `layer.depth` on the layer at `idx` in every frame.
2. **`move_layer_into_group(layer_idx, group_idx)`** — Moves the layer to the position right after the group (above existing children), sets `depth=1`. Applied across all frames.
3. **`move_layer_out_of_group(layer_idx)`** — Sets `depth=0` and moves the layer above its parent group. Applied across all frames.

Constraints:
- `move_layer_into_group` rejects if `layer_idx` points to a group, or if `group_idx` does not point to a group.
- `move_layer_out_of_group` is a no-op if layer is already at depth 0.
- Both methods maintain active_layer_index consistency.

### UI Layer (`src/ui/timeline.py`)

**Context menu additions** (in `_show_layer_context_menu`):
- For non-group layers: "Move to Group >" submenu listing all groups by name. Clicking a group calls `move_layer_into_group`.
- For layers with `depth > 0`: "Remove from Group" item. Calls `move_layer_out_of_group`.

**Drag-into-group detection** (in `_on_layer_drop`):
- If the drop target is a group row and the source is a non-group layer, call `move_layer_into_group` instead of `_on_move_layer`.
- If the drop target is outside any group and the source has `depth > 0`, call `move_layer_out_of_group`.

**Visual indicators:**
- Group rows: bold name label, magenta text color (using `ACCENT_MAGENTA` from theme).
- Child layers: 12px indent (already coded at line 349, will activate once depth=1).
- A subtle left border or background tint on child rows to reinforce grouping.

### Group Creation Fix (`src/layer_animation.py`)

`_add_group()` currently sets `depth = active.depth`, which could create nested groups. Fix: always set `depth=0`.

### Collapse/Expand

Already functional in the code — the skip logic at lines 330-341 checks `layer.depth > g_layer.depth`. Once children actually have `depth=1`, collapse will hide them. No changes needed.

### Save/Load

Already handled — `project.py` saves and loads `layer.depth` at lines 56 and 80. No changes needed.

## Files to Modify

| File | Change |
|------|--------|
| `src/animation.py` | Add `set_layer_depth_all`, `move_layer_into_group`, `move_layer_out_of_group` |
| `src/layer_animation.py` | Fix `_add_group` to always use `depth=0` |
| `src/ui/timeline.py` | Context menu items, drag-into-group logic, group visual styling |

## Testing

- Test `move_layer_into_group` moves layer to correct position and sets depth=1 across all frames
- Test `move_layer_out_of_group` resets depth=0 and repositions above group
- Test that moving a group into a group is rejected (one-level constraint)
- Test collapse hides children and expand shows them
- Test that `_add_group` always creates at depth=0
