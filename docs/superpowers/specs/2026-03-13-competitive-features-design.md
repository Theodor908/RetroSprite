# Competitive Features: Drawing Tools & Layer Workflow

> **Batch A:** Polygon tool, Rounded Rectangle tool, Contour Fill mode, Move tool
> **Batch B:** Linked Cels, Clipping Masks

These features close the highest-impact gaps identified in a competitive analysis against Aseprite, Pixelorama, Pro Motion NG, and Pyxel Edit.

---

## Batch A: Drawing Tools

### A1: Polygon Tool

**Purpose:** Draw arbitrary polygons with straight edges — a fundamental shape tool missing from the current toolset.

**Implementation:**

- New `PolygonTool` class in `src/tools.py`
- Signature: `apply(grid, points: list[tuple[int,int]], color, filled=False, width=1)`
- Outline mode: Bresenham line between consecutive vertices (reuses `LineTool` internals)
- Filled mode: scanline fill algorithm over the polygon interior (even-odd rule)
- Canvas interaction:
  - Each left-click adds a vertex
  - Live preview line drawn from last vertex to cursor
  - Enter closes the polygon and applies
  - Escape cancels without drawing
  - **Double-click handling:** use a `_polygon_closing` flag — set on `<Double-Button-1>`, checked in `<Button-1>` handler to skip adding the duplicate vertex. The double-click handler closes the polygon.
- State: `self._polygon_points: list[tuple[int,int]] = []` in `app.py`
- Toolbar: icon after Ellipse, keybinding `N`
- Options bar: size (stroke width)
- `ToolSettingsManager` defaults: `"polygon": {"size": 1}`

**Algorithm (filled):**
```
1. For each scanline y in bounding box:
2.   Find all x-intersections with polygon edges
3.   Sort intersections
4.   Fill between pairs (even-odd rule)
```

### A2: Rounded Rectangle Tool

**Purpose:** Draw rectangles with rounded corners — common in UI pixel art and game assets.

**Implementation:**

- New `RoundedRectTool` class in `src/tools.py`
- Signature: `apply(grid, x0, y0, x1, y1, color, radius=2, filled=False, width=1)`
- Corner rendering: quarter-circle arcs using midpoint circle algorithm, connected by straight lines
- Radius clamped to `min(radius, (min(w, h) - 1) // 2)` to guarantee at least one straight pixel per side. For very small rects where this yields 0, falls back to regular rectangle.
- Canvas interaction: identical to `RectTool` (click-drag for opposite corners)
- Toolbar: icon after Rect, keybinding `Shift+R`
- Options bar: size (stroke width) + corner radius control (1-16px, default 2)
- `ToolSettingsManager` defaults: `"roundrect": {"size": 1, "corner_radius": 2}`
- Options bar gains a `_radius_var` and radius +/- buttons, shown only for roundrect tool

### A3: Contour Fill (Fill Tool Mode)

**Purpose:** Fill only the border pixels of a region — useful for drawing outlines around shapes quickly.

**Implementation:**

- Add `fill_mode` field to Fill tool settings: `"normal"` (default) or `"contour"`
- Algorithm:
  1. Flood-select the clicked region using exact color match (same as FillTool's existing flood fill logic, **not** tolerance-based wand). This ensures contour fill selects the same region that normal fill would fill.
  2. Find border pixels: pixels in the region that have at least one 4-connected neighbor outside the region
  3. Fill only border pixels with the selected color
- UI: toggle button in Fill tool's options bar row ("Fill: Normal" / "Fill: Contour")
- `ToolSettingsManager` defaults for fill: add `"fill_mode": "normal"`
- `FillTool.apply()` gains an optional `contour=False` parameter. When `contour=True`, it performs the border detection step instead of filling the entire region.

### A4: Move Tool

**Purpose:** Directly move layer content or active selection by dragging — a standard tool in every image editor.

**Implementation:**

- New toolbar entry, keybinding `V`
- No `src/tools.py` class — handled entirely in `app.py` event handlers (like Hand tool pattern)
- Behavior:
  - If `_selection_pixels` is set: cut selection to floating paste, move with drag
  - If no selection: move entire layer content by drag delta
- Layer move algorithm:
  1. On click: push undo (full frame snapshot via existing `_push_undo()` mechanism), record start position
  2. On drag: compute delta (dx, dy), shift layer pixels by delta from original snapshot, render live
  3. On release: finalize the shift (pixels already committed during drag)
- Pixels that move outside canvas bounds are clipped. Status bar shows "Move: (dx, dy)" during drag and warns "pixels clipped" when content goes off-canvas.
- `ToolSettingsManager` defaults: `"move": {}`
- Toolbar icon: four-directional arrow, placed before the Hand tool

**Undo integration:** Uses the existing `_push_undo()` which snapshots the full frame state. Undo restores the entire frame, which correctly handles layer pixel data. This is consistent with how other destructive tools (pen, eraser, fill) integrate with undo.

---

## Batch B: Layer Workflow

### B1: Linked Cels

**Purpose:** Allow multiple frames to share the same layer pixel data. Editing a linked cel in one frame updates all frames that reference it. Essential for animation workflows where parts of a sprite (e.g., body, background) stay constant across frames.

**Design: Shared-Reference Approach (Option B)**

Instead of a centralized cel_store with timeline backrefs (which would require modifying every Layer construction site), use Python's object reference semantics directly:

1. **`Layer` class** — add `cel_id: str` field (UUID string, generated on creation). This is a plain data field, not a property. `pixels` remains a direct attribute.
2. **Linking mechanism** — two Layer objects are linked when they hold the **same `PixelGrid` object reference** AND the same `cel_id`. Any mutation to the PixelGrid (e.g., `set_pixel()`) is immediately visible through all references.
3. **Frame duplication** — `Frame.copy(linked=False)` gains a `linked` parameter:
   - When `linked=True` (used by `duplicate_frame()`): creates new Layer shell objects with `new_layer.pixels = original_layer.pixels` (same reference) and `new_layer.cel_id = original_layer.cel_id`. Does NOT call `Layer.copy()`.
   - When `linked=False` (default, preserves existing behavior): calls `Layer.copy()` for each layer, producing deep-copied independent pixel data with new cel_ids. Existing tests (`test_duplicate_frame`) continue to pass.
   - `AnimationTimeline.duplicate_frame()` calls `Frame.copy(linked=True)`.
4. **Unlink operation** — `Layer.unlink()`:
   - Deep-copies the PixelGrid: `self.pixels = self.pixels.deep_copy()`
   - Assigns new cel_id: `self.cel_id = str(uuid4())`
   - Now this layer has independent pixel data
5. **`Layer.copy()`** — updated to handle new fields:
   - Deep-copies pixels (existing behavior)
   - Generates new `cel_id` (independent copy)
   - Copies `clipping` value from source
6. **Link detection** — `timeline.is_linked(frame_idx, layer_idx)` checks if any other frame's same-index layer shares the same `cel_id`

**Merge-down safety:**
- Before `merge_down`, automatically unlink the target layer if it's linked. This prevents merge results from propagating to unrelated frames.
- Add check in `Frame.merge_down()` and `AnimationTimeline.merge_down_in_all()`.

**Existing construction sites (unchanged):**
- `Layer.__init__()` — generates a new `cel_id`, creates its own PixelGrid. No changes needed.
- `Layer.from_grid()` — same, generates unique cel_id. No changes needed.
- `AnimationTimeline.add_frame()`, `insert_frame()`, `add_layer_to_all()`, `sync_layers()` — all create new Layers with new PixelGrids and unique cel_ids. These always produce **independent (unlinked) cels**. Only `duplicate_frame()` produces linked cels.

**No GC needed:** Since PixelGrid objects are held directly by Layer instances (not in a central store), Python's garbage collector handles cleanup automatically when frames/layers are removed.

**UI:**
- Timeline panel: linked cels show a small link indicator (e.g., colored dot or chain icon)
- Right-click on timeline cel → "Unlink Cel" (grayed out if not linked)
- Status bar shows "Linked" when editing a linked cel

**Serialization (project file):**
- Each layer in frame data stores `"cel_id"` alongside its pixel data
- On save: layers with the same `cel_id` write pixel data only once (first occurrence); subsequent occurrences store `"cel_ref": "<cel_id>"` instead of inline pixels
- On load: when `"cel_ref"` is encountered, look up the already-loaded PixelGrid from the first occurrence and share the reference
- Backward compatibility: old files without `cel_id` → generate unique IDs on load (all layers independent)
- Version bump to 6

### B2: Clipping Masks

**Purpose:** A clipped layer is only visible within the opaque pixels of the nearest non-clipped layer below it. Essential for shading and detail work without spilling outside shape boundaries.

**Data Model Changes:**

1. **`Layer` class** — add `clipping: bool = False` field
2. **`flatten_layers()`** in `layer.py` — modify compositing logic

**Compositing algorithm:**
```
base_alpha = None  # alpha of the clip-base layer's OWN pixels (pre-composite)

for layer in layers (bottom to top):
    if not layer.visible:
        continue

    # Resolve layer image (apply opacity, effects)
    layer_img = resolve_layer(layer)

    if not layer.clipping or base_alpha is None:
        # Normal layer — composite normally, becomes new clip base
        base_alpha = layer_img alpha channel (the layer's OWN pixels * opacity,
                     BEFORE compositing with the canvas below)
        composite layer_img onto result
    else:
        # Clipped layer — multiply alpha by base_alpha before compositing
        clipped_img = copy of layer_img
        clipped_img.alpha *= base_alpha
        composite clipped_img onto result
```

**Key distinction:** `base_alpha` comes from the clip-base layer's **own** pixels scaled by its opacity, **not** from the accumulated composite. This matches Aseprite's behavior: a 50% opacity base layer clips to its own shape, not to the combined shape of everything below.

**Edge cases:**
- Bottom-most layer set to clipping: `base_alpha` is None, so treated as normal layer
- Multiple consecutive clipped layers: all clip to the same base's alpha
- Clipped layer in a group: clips to nearest non-clipped layer within the same group depth level. The existing group stack in `flatten_layers` carries `base_alpha` per stack frame.

**Group + clipping integration:**
The existing `flatten_layers` uses a stack for group compositing. Each stack entry gains a `base_alpha` field:
```python
stack_entry = {
    "canvas": group_canvas,
    "base_alpha": None  # NEW: tracks clip base within this group
}
```
When entering a group, `base_alpha` resets to None. When leaving a group, the group's composite becomes a layer that may itself set `base_alpha` in the parent scope.

**UI:**
- Right-click layer in timeline panel → "Clip to Below" toggle
- Clipped layers show visually indented with a small downward arrow/bracket indicator
- Attempting to clip the bottom layer: show brief status message "Cannot clip bottom layer"

**Serialization:**
- Add `"clipping": true/false` to each layer in project file
- Backward compatible: defaults to `false` when missing
- No version bump needed (additive field)

---

## Files Modified

| File | Changes |
|------|---------|
| `src/tools.py` | Add `PolygonTool`, `RoundedRectTool`, update `FillTool` with contour mode |
| `src/app.py` | Move tool handlers, polygon interaction state, new tool registration, contour fill wiring |
| `src/ui/toolbar.py` | Add Polygon, RoundedRect, Move tool icons |
| `src/ui/icons.py` | New tool icons |
| `src/ui/options_bar.py` | Corner radius control, fill mode toggle |
| `src/tool_settings.py` | Add defaults for polygon, roundrect, move; add fill_mode and corner_radius |
| `src/layer.py` | Add `clipping` and `cel_id` fields, `unlink()` method, update `flatten_layers()` for clipping |
| `src/animation.py` | Update `Frame.copy()` for linked cels (shared reference), auto-unlink in merge_down, add `is_linked()` |
| `src/project.py` | Serialize/deserialize cel_id/cel_ref and clipping field, version 6 |
| `src/ui/timeline.py` | Link indicators, unlink context menu, clip-to-below context menu |
| `tests/` | New test files for each feature |

## Testing Strategy

- Unit tests for `PolygonTool.apply()` — outline and filled modes, various vertex counts
- Unit tests for `RoundedRectTool.apply()` — various sizes and radii, edge cases (square, tiny rect)
- Unit tests for contour fill — border detection, single-pixel regions, large regions
- Unit tests for linked cels — shared edit propagation, unlink creates independent copy, Frame.copy() produces linked layers, merge_down auto-unlinks
- Unit tests for clipping mask compositing — `flatten_layers` with `clipping=True`, base_alpha from own pixels, group interaction, bottom-layer-clip edge case
- Unit tests for serialization round-trip — cel_id/cel_ref deduplication, clipping field persistence
- Integration: manual verification of tool interaction, undo/redo, and project save/load
