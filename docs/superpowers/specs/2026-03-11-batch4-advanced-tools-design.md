# Batch 4: Advanced Tools — Design Spec

**Date:** 2026-03-11
**Status:** Approved
**Features:** RotSprite Rotation, Non-Destructive Layer Effects, Tilemap Layers

---

## 1. RotSprite Rotation

### Algorithm

**RotSprite** — pixel-art-aware rotation via upscale → rotate → downscale:

1. **Scale2x Upscale (×8):** Apply modified Scale2x 3 times (2³ = 8×). For each pixel E with neighbors A-I, produce 2×2 block:
   - E0 = (D≈B && D≉H && B≉F) ? D : E
   - E1 = (B≈F && B≉D && F≉H) ? F : E
   - E2 = (D≈H && D≉B && H≉F) ? D : E
   - E3 = (H≈F && H≉D && F≉B) ? F : E
   - RotSprite modification: use `similar(a,b) = color_distance(a,b) < threshold` instead of `==`

2. **Rotate at 8× resolution:** Nearest-neighbor rotation around pivot×8. Clean results because Scale2x already created smooth sub-pixel edges.

3. **Downscale to 1×:** Mode-based downsample (most common color in 8×8 block) to avoid introducing new colors.

**Fast Rotation** alternative: simple nearest-neighbor at native resolution. For 90°/180°/270°, both algorithms produce identical results.

### Canvas Interaction (Aseprite-style)

- **Activation:** Select content → Edit > Rotate (Ctrl+T)
- **Handles:** Corner handles for drag-to-rotate, cursor changes to ↻
- **Shift+drag:** Snap to 15° increments
- **Pivot point:** Visible dot at center, draggable to reposition
- **Live preview:** Updates as you drag
- **Context bar:** Angle input field, algorithm dropdown (RotSprite | Fast), pivot X/Y fields
- **Enter:** Bake rotation into layer pixels (destructive). Undo state saved before entering rotation mode. Escape also uses this saved state to restore.
- **Escape:** Cancel, restore original from saved undo state.
- **Bounding box:** Rotated pixels that extend outside the canvas are **clipped** to canvas bounds (same as Aseprite's default behavior with expand=False). Content is not lost from undo perspective — user can Ctrl+Z and try a different angle.

### Performance

- Only rotate the selection bounding box, not full canvas
- Large selections: show Fast preview during drag, compute RotSprite on mouse release
- Cache RotSprite result until angle changes
- 64×64 → 512×512 intermediate (fine). 256×256 → 2048×2048 intermediate (~16MB, manageable).

### New File: `src/rotsprite.py`

```
scale2x(pixels, threshold=48) -> ndarray          # Modified Scale2x
rotsprite_rotate(pixels, angle, pivot) -> ndarray  # Full pipeline
fast_rotate(pixels, angle, pivot) -> ndarray       # Nearest-neighbor
color_distance(a, b) -> int                        # Manhattan RGBA distance (scalar, per pixel pair)
```

Note: `color_distance` is a scalar function comparing two RGBA tuples. Inside the vectorized `scale2x()`, neighbor comparisons are done with NumPy broadcasting — `similar()` operates on padded arrays and produces boolean masks. Each Scale2x pass operates on its own input (not the original image); the threshold is calibrated for 8-bit channels and works correctly at all pass levels since Scale2x never introduces new colors.

---

## 2. Non-Destructive Layer Effects

### Data Model

```python
class LayerEffect:
    type: str       # effect type identifier
    enabled: bool   # toggle without removing
    params: dict    # effect-specific parameters
```

`Layer` gains: `self.effects: list[LayerEffect] = []`

### Effects (7 total)

#### Core

**Outline:**
- Algorithm: For transparent pixels adjacent to opaque, fill with outline color. Binary dilation (outer) / erosion (inner).
- Params: `color` (RGBA), `thickness` (1-4px), `mode` ("outer"|"inner"|"both"), `connectivity` (4|8)

**Drop Shadow:**
- Algorithm: Copy alpha mask, offset by (dx,dy), fill with shadow color, optional Gaussian blur, composite behind layer.
- Params: `color` (RGBA), `offset_x/y` (-16 to +16), `blur` (0-3), `opacity` (0.0-1.0)

**Inner Shadow:**
- Algorithm: Invert alpha mask, offset, optional blur, clip to original alpha. Shadow visible only inside opaque areas.
- Params: `color` (RGBA), `offset_x/y` (-16 to +16), `blur` (0-3), `opacity` (0.0-1.0)

#### Color

**Hue/Saturation/Value Shift:**
- Algorithm: Vectorized RGB→HSV, shift H, scale S, offset V, HSV→RGB. Preserve alpha.
- Params: `hue` (-180 to +180°), `saturation` (0.0-2.0), `value` (-100 to +100, maps to V channel offset in 0-255 range)

**Gradient Map:**
- Algorithm: Compute luminance (0.299R + 0.587G + 0.114B), map to color stops, interpolate.
- Params: `stops` (list of (position, RGBA)), `opacity` (0.0-1.0)

#### Advanced

**Glow/Bloom:**
- Algorithm: Extract bright pixels above threshold → Gaussian blur → Screen-blend onto original.
- Params: `threshold` (0-255), `radius` (1-8), `intensity` (0.0-2.0), `tint` (RGBA)

**Pattern Overlay:**
- Algorithm: Tile small pattern across layer bounds, blend with chosen mode, clip to layer alpha.
- Params: `pattern` ("scanlines"|"crosshatch"|"dots"|"diagonal"|"noise"|"checkerboard"), `blend_mode` (any of 9), `opacity` (0.0-1.0), `scale` (1-4), `offset_x/y`
- Built-in patterns are small NumPy arrays (4×4 to 8×8), generated procedurally.

### Effect Application Order

During `flatten_layers()`, for each layer with effects. Effects operate on a **copy** of the layer's original pixels. Outline and Drop Shadow are computed from the **original alpha mask** (before other spatial effects modify it), not from each other's output:

1. Color effects (hue/sat, gradient map) — modify pixel colors in-place
2. Pattern overlay — blend pattern onto pixels
3. Glow/bloom — add glow composite
4. Inner shadow — computed from original alpha, clipped inside
5. Outline — computed from **original** alpha mask, added to result
6. Drop shadow — computed from **original** alpha mask, composited behind result

This ensures drop shadow is cast from the sprite silhouette, not from the outline (matching Photoshop/Aseprite behavior).

### UI

**FX Button:** Per-layer button in timeline row. Magenta when effects active, dim when empty. Click opens Effects Dialog.

**Effects Dialog:**
- Left panel: effect list with checkboxes (enable/disable), reorder (▲▼), add (+), remove (✕)
- Right panel: params for selected effect (sliders, dropdowns, color pickers)
- Live preview on canvas as you adjust
- Apply / Cancel buttons

**View Menu:** "Display Layer Effects" toggle (default ON). When OFF, flatten skips effects for faster editing. Effects always applied on export.

### New Files

- `src/effects.py` — Effect classes, apply pipeline, all 7 effect functions
- `src/ui/effects_dialog.py` — FX config dialog with live preview

---

## 3. Tilemap Layers

### Data Model

```python
class Tileset:
    name: str
    tile_width: int
    tile_height: int
    tiles: list[np.ndarray]  # index 0 = empty/transparent (always)

    add_tile(pixels) -> int
    remove_tile(index)
    update_tile(index, pixels)       # live update all instances
    find_matching(pixels) -> int|None
    import_from_image(path, tw, th)  # auto-slice + dedup

class TileRef:
    index: int       # tile index (0 = empty)
    flip_x: bool
    flip_y: bool
    # Packed as uint32: [flip_y:1][flip_x:1][unused:14][index:16]

class TilemapLayer(Layer):
    tileset: Tileset
    grid: list[list[TileRef]]    # 2D grid of tile references
    grid_cols: int               # canvas_width // tile_width
    grid_rows: int               # canvas_height // tile_height
    edit_mode: str               # "pixels" | "tiles"
    pixel_sub_mode: str          # "auto" | "manual"

    def render_to_pixels(self) -> np.ndarray:
        # Resolve all tile refs → blit into pixel buffer

    @property
    def pixels(self) -> PixelGrid:
        # Override Layer.pixels — returns rendered tile grid as PixelGrid
        # This is the SOLE dispatch mechanism: flatten_layers() calls
        # layer.pixels uniformly for ALL layer types. No isinstance checks,
        # no circular imports. TilemapLayer.pixels computes on access.
        return PixelGrid.from_array(self.render_to_pixels())

    def copy(self) -> 'TilemapLayer':
        # MUST override Layer.copy() to preserve tilemap data:
        # - Deep-copy grid (list of TileRef lists)
        # - Share tileset reference (tilesets are project-scoped, not copied)
        # - Copy all base Layer fields (visible, opacity, blend_mode, etc.)
        # - Copy effects list

    def is_tilemap(self) -> bool:
        return True  # duck-typing flag for guards (see below)
```

### Tileset Ownership

Tilesets are **project-scoped**, not per-layer. Stored in `AnimationTimeline.tilesets: dict[str, Tileset]` (keyed by name). Multiple TilemapLayers can reference the same tileset. On serialization, tilesets are saved once at project level; layers store tileset name as reference.

### Tile Size

- Custom width × height input with preset dropdown (8×8, 16×16, 24×24, 32×32)
- Locked after creation (cannot change) — because grid dimensions (grid_cols, grid_rows) depend on tile size; changing it would invalidate the entire grid

### Critical Integration: Layer Operations

Several existing operations must be guarded for TilemapLayer:

**sync_layers() / add_frame() (animation.py):** When creating layers for new frames, check the layer type in the reference frame. If it's a TilemapLayer, create a TilemapLayer (sharing the same tileset, with an empty grid) instead of a plain Layer. Use duck-typing: `if hasattr(layer, 'is_tilemap') and layer.is_tilemap()`.

**merge_down() / merge_down_in_all():** Merging a TilemapLayer down must first rasterize it via `render_to_pixels()`, then merge the pixel result. The target becomes a regular pixel layer. This is intentional — merging is destructive by nature. If the target is also a TilemapLayer, warn the user that tile data will be lost.

**duplicate_layer():** Must call `layer.copy()` which TilemapLayer overrides to preserve grid + tileset reference.

### Two Editing Modes

**Draw Pixels (default):**
- Edit tile content directly, drawing tools work on pixels
- **Auto sub-mode (default):** Draw normally. Modified tile cells auto-matched to existing tiles or new tile created. Unused tiles auto-cleaned.
- **Manual sub-mode:** Draw modifies tile definition. ALL instances update live (Pyxel Edit style). No new tiles created.

**Draw Tiles:**
- Place tiles from tileset onto grid
- Tool mapping: Pen=place, Eraser=clear to empty, Fill=flood-fill, Pick=select tile from canvas, Rect=fill rect, Line=place line
- Tile transforms: flip horizontal / flip vertical (default shortcuts: Shift+X / Shift+Y, customizable via keybindings). Stored per-cell in TileRef.

**Mode toggle:** Keyboard shortcut (default: Tab when tilemap layer active) or button in context bar. Status bar shows: "PIXELS (Auto)" / "PIXELS (Manual)" / "TILES". All tilemap shortcuts registered through `src/keybindings.py` for user customization.

### UI

**Tiles Panel (right sidebar):**
- Grid of tile thumbnails from active tileset
- Index 0 = empty (∅ icon). Selected tile has green border.
- Click to select tile for placement
- Flip X / Flip Y toggle buttons
- Import button: load tileset from image file (auto-slice + dedup)

**New Tilemap Layer Dialog:**
- Radio: Create New tileset / Use Existing (dropdown)
- Tile size: width × height fields + presets dropdown
- Tileset name field
- Create / Cancel buttons

**Canvas Overlay:**
- Tile grid lines (dashed, semi-transparent cyan) when tilemap layer active
- Only visible at sufficient zoom (tile ≥ 8px on screen)
- Hover highlight on current cell
- In Tiles mode: cursor shows ghost preview of selected tile
- Toggle in View menu

### Tileset Import

```python
def import_tileset_from_image(image_path, tile_w, tile_h) -> Tileset:
    # Open image, iterate tile-sized blocks left→right top→bottom
    # Skip fully transparent tiles
    # Dedup: check if identical tile already exists
    # Return populated Tileset
```

---

## Architecture

### New Files (8)

| File | Purpose |
|------|---------|
| `src/rotsprite.py` | RotSprite algorithm (Scale2x + rotate + downscale) |
| `src/effects.py` | Effect classes + apply pipeline (7 effects) |
| `src/tilemap.py` | Tileset, TileRef, TilemapLayer classes |
| `src/ui/effects_dialog.py` | FX config dialog with live preview |
| `src/ui/tiles_panel.py` | Tile picker panel for right sidebar |
| `tests/test_rotsprite.py` | RotSprite algorithm tests |
| `tests/test_effects.py` | Layer effects tests |
| `tests/test_tilemap.py` | Tilemap layer tests |

### Modified Files (9)

| File | Changes |
|------|---------|
| `src/layer.py` | Add `effects` field to Layer |
| `src/canvas.py` | Rotation handles overlay, tile grid overlay |
| `src/app.py` | Rotation tool mode, tilemap mode toggle, FX wiring |
| `src/tools.py` | Tile placement tools (pen/eraser/fill in tile mode) |
| `src/ui/timeline.py` | FX button per layer row, tilemap layer icon |
| `src/ui/right_panel.py` | Mount tiles panel |
| `src/image_processing.py` | RotSprite integration |
| `src/animation.py` | sync_layers/add_frame guard for TilemapLayer; merge_down rasterize guard |
| `src/project.py` | v3 format: effects + tilemap serialization |

### Rendering Pipeline (Updated)

```
flatten_layers():
  for each layer (bottom → top):
    pixels = layer.pixels  # uniform access — TilemapLayer.pixels property
                           # auto-renders tile grid; no isinstance needed

    if layer.effects:
      original_alpha = pixels[:,:,3].copy()  # save for outline/shadow
      pixels = apply_effects(pixels, layer.effects, original_alpha)

    composite onto frame (blend mode + opacity)
```

No circular imports: `flatten_layers()` in `layer.py` never references `TilemapLayer`. The `pixels` property override handles dispatch via polymorphism.

### Project Format v3

- Backward compatible: v3 reader handles v2/v1 files
- v2/v1 readers cannot load tilemap layers or effects (graceful skip)
- Effects serialized as JSON list in layer data
- Tilesets serialized as tile images (PNG-encoded) + metadata
- Tilemap grids as 2D arrays of packed uint32 tile refs
