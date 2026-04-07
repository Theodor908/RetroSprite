# Timeline Layout Overhaul — Resizable Panes, Vertical Scroll, Name Truncation

**Date:** 2026-03-27
**Status:** Approved
**Scope:** Timeline panel layout improvements

## Problems

1. **Layer name clipping**: Layer names overflow into the FX/blend buttons because the sidebar is fixed at 180px and names have no truncation
2. **No resizable divider**: Users cannot adjust the width split between the layer list and frame grid
3. **No vertical scrolling**: When there are more layers than fit vertically, there's no way to scroll

## Solution

### 1. PanedWindow Split

Replace the current fixed `Frame` side-by-side layout with a horizontal `tk.PanedWindow`:

**Current** (timeline.py lines 99-109):
```
grid_area (Frame)
├── _layer_sidebar (Frame, width=180, pack_propagate=False)
└── _grid_scroll_frame (Frame, fill="both", expand=True)
```

**New**:
```
grid_area (PanedWindow, orient=HORIZONTAL)
├── left_pane (Frame, min_width=120)
│   ├── _layer_canvas (Canvas, yscrollcommand synced)
│   │   └── _layer_inner (Frame — layer rows go here)
│   └── (no separate scrollbar — synced with right pane's)
└── right_pane (Frame)
    ├── _grid_canvas (Canvas, xscroll + yscroll)
    │   └── _grid_inner (Frame — cel grid)
    ├── _h_scrollbar (horizontal, bottom)
    └── _v_scrollbar (vertical, right)
```

- Default sash position: 200px
- Minimum left pane width: 120px (enough for buttons even without names)
- Sash styled with theme colors (`BORDER` background, 4px wide)
- On sash drag: layer name labels recalculate truncation

### 2. Synchronized Vertical Scrolling

- The frame grid (`_grid_canvas`) gets a vertical `Scrollbar` on the right
- The layer sidebar (`_layer_canvas`) shares the same vertical scroll position
- Scrolling either pane (or the scrollbar, or mousewheel) scrolls both in sync
- Mousewheel works when hovering over either the layer sidebar or the frame grid
- Horizontal scroll remains on the frame grid only (layers don't scroll horizontally)

**Sync mechanism**: Both canvases call `yview_moveto` with the same fraction. The vertical scrollbar controls the grid canvas, and a `<Configure>` / scroll callback mirrors the position to the layer canvas.

### 3. Layer Row Layout — Buttons Fixed, Names Truncate

**New pack order** (left to right):

```
[Eye][Lock] Layer name...                [FX][Blend▼]
 side=left   side=left, fill=x, expand    side=right
```

This is already the current order (Eye, Lock on left → name in middle → Blend, FX on right). The fix is:

- **Buttons**: packed with fixed width, `side="left"` for eye/lock, `side="right"` for FX/blend — these never clip
- **Name label**: packed `side="left", fill="x", expand=True` (already is), but now gets a `<Configure>` callback that truncates the text with "..." when the label width is smaller than the text width

**Truncation logic**:
```python
def _truncate_name(event, lbl, full_text):
    font = tkfont.Font(font=lbl.cget("font"))
    avail = event.width
    if font.measure(full_text) <= avail:
        lbl.config(text=full_text)
    else:
        for i in range(len(full_text), 0, -1):
            if font.measure(full_text[:i] + "...") <= avail:
                lbl.config(text=full_text[:i] + "...")
                return
        lbl.config(text="...")
```

Bind on the name label's `<Configure>` event, storing the full name separately.

### 4. No Persistence

Sash position resets to 200px default each time the app starts. No save/load.

## Files Changed

| File | Change |
|------|--------|
| `src/ui/timeline.py` | Replace fixed sidebar with PanedWindow, add vertical scroll sync, add name truncation |

No other files need changes — this is entirely within the timeline widget.

## Backward Compatibility

No data model changes. Pure UI layout change within a single file.
