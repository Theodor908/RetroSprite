# Frame Tags Overhaul — Design Spec

**Date:** 2026-04-07
**Status:** Approved

## Problem

The current tag system uses four sequential `simpledialog` prompts to create a tag, tag bars can't be edited or resized, and exports always include all frames with no tag filtering.

## Goals

- Single modal dialog for creating and editing tags (name, color, start, end)
- Colored tag bars above timeline frames with right-click edit/delete
- Drag tag bar edges to resize the frame range
- Overlapping tags stack vertically
- Export dialog tag dropdown to export only tagged frame ranges

## User Decisions

| Decision | Choice |
|----------|--------|
| Overlapping tags | Allowed, stack vertically |
| Tag interaction | Right-click to edit/delete, double-click to edit, drag edges to resize |
| Export filtering | Tag dropdown in export dialog |

---

## Tag Dialog

### `src/ui/tag_dialog.py`

Single modal dialog used for both Add and Edit:

- **Name**: text entry (required)
- **Color**: color swatch button — click opens `RGBAColorPicker` (uses RGB, ignores alpha)
- **Start Frame**: spinbox (1-based, range 1 to frame_count)
- **End Frame**: spinbox (1-based, range start to frame_count)
- **OK / Cancel** buttons

For Edit mode, fields are pre-populated with the existing tag's values.

Returns a result dict `{"name": str, "color": str, "start": int, "end": int}` (0-based frame indices) or None if cancelled.

---

## Tag Bar Rendering

### In `src/ui/timeline.py` `_draw_tags()`

- Tag container height grows to accommodate stacking: `14px * num_stacked_rows`
- Each tag is a `tk.Label` with `bg=tag_color`, `fg=BG_DEEP`, `text=tag_name`
- Positioned with `place()`:
  - `x = start * (cel_size + 2)`
  - `width = (end - start + 1) * (cel_size + 2)`
  - `y = row * 14` (row determined by overlap stacking)
- Stacking: for each tag, find the lowest row where it doesn't overlap with already-placed tags

### Overlap Resolution

Simple greedy row assignment:
```
for each tag:
    for row 0, 1, 2...:
        if no existing tag in this row overlaps:
            place tag in this row
            break
```

---

## Tag Interaction

### Bindings on each tag label:

- `<Button-3>`: right-click context menu with "Edit Tag..." and "Delete Tag"
- `<Double-Button-1>`: open edit dialog
- `<Button-1>`: start edge drag detection (check if click is within 6px of left or right edge)
- `<B1-Motion>`: drag the edge, updating start or end frame in real-time
- `<ButtonRelease-1>`: commit the new range, refresh timeline

### Edge Drag

On `<Button-1>`, check cursor x position relative to tag label:
- Within 6px of left edge → dragging `start`
- Within 6px of right edge → dragging `end`
- Otherwise → no drag (just a click)

During drag:
- Convert mouse x to frame index
- Clamp: start can't exceed end, end can't be less than start
- Clamp: both within 0 to frame_count - 1
- Update tag dict in place
- Redraw tags

### Right-Click Context Menu

```
Edit Tag...    → opens tag dialog pre-populated
Delete Tag     → removes tag, refreshes timeline
```

---

## Export by Tag

### In `src/ui/export_dialog.py`

Add a **Tag** dropdown at the top of the dialog:
- First option: "All Frames" (default)
- Then one entry per tag: "{tag_name} (frames {start+1}-{end+1})"
- When a tag is selected, store the frame range (start, end)

### Frame Range Propagation

The export dialog passes `frame_start` and `frame_end` (or None for all) to the export functions.

### In `src/export.py`

`build_sprite_sheet()` — accept optional `frame_start`/`frame_end` params. Only include frames in range.

### In `src/animated_export.py`

`export_gif()`, `export_webp()`, `export_apng()` — accept optional `frame_start`/`frame_end`. Only include frames in range.

### Frame Sequence Export

Export only the frames in the tag range, numbered sequentially.

---

## Files Changed/Created

| File | Action | Purpose |
|------|--------|---------|
| `src/ui/tag_dialog.py` | **New** | Tag add/edit dialog with name, color, start, end |
| `src/ui/timeline.py` | **Modify** | Tag bar rendering with stacking, drag resize, right-click menu |
| `src/layer_animation.py` | **Modify** | Replace `_add_tag_dialog` to use new dialog |
| `src/ui/export_dialog.py` | **Modify** | Add tag dropdown, pass frame range |
| `src/export.py` | **Modify** | Accept frame range in `build_sprite_sheet` |
| `src/animated_export.py` | **Modify** | Accept frame range in GIF/WebP/APNG exports |

## Dependencies

No new dependencies.

## Testing

- `test_tag_stacking` — overlapping tags get assigned different rows
- `test_tag_edge_drag_clamp` — start can't exceed end, end can't be less than start
- `test_export_frame_range` — exporting with frame range only includes those frames
- `test_tag_dialog_roundtrip` — create tag via dialog, verify data stored correctly
