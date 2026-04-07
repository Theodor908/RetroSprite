# Batch 6: Interop & Color — Design Spec

**Date:** 2026-03-11
**Status:** Approved
**Features:** Indexed Color Mode, Color Reduction, Palette Import/Export, Aseprite Import, PNG Sequence Export

---

## 1. Indexed Color Mode

### IndexedPixelGrid (`src/pixel_data.py`)

New class alongside existing `PixelGrid`. Stores palette indices instead of RGBA.

**Why uint16:** Index 0 is reserved for transparent. With 1-based palette indices, 256 colors requires indices 1-256, which exceeds uint8 range. uint16 supports up to 65535 palette entries.

```python
class IndexedPixelGrid:
    """A 2D grid of palette indices backed by a NumPy uint16 array.

    Holds a reference to the project palette so that get_pixel/set_pixel
    have the same signature as PixelGrid — tools work transparently.
    """

    def __init__(self, width: int, height: int, palette: list[tuple] | None = None):
        self.width = width
        self.height = height
        self._palette = palette or []  # Reference to project palette (Palette.colors)
        # Index 0 = transparent. Palette indices are 1-based (palette[0] → index 1).
        self._indices = np.zeros((height, width), dtype=np.uint16)

    # --- PixelGrid-compatible interface (tools use these) ---

    def get_pixel(self, x: int, y: int) -> tuple[int,int,int,int] | None:
        """Resolve index to RGBA using stored palette reference.
        Same signature as PixelGrid.get_pixel — tools work transparently.
        """
        if 0 <= x < self.width and 0 <= y < self.height:
            idx = int(self._indices[y, x])
            if idx == 0:
                return (0, 0, 0, 0)
            if idx - 1 < len(self._palette):
                return self._palette[idx - 1]
            return (0, 0, 0, 0)
        return None

    def set_pixel(self, x: int, y: int, color: tuple[int,int,int,int]) -> None:
        """Snap color to nearest palette entry and store index.
        Same signature as PixelGrid.set_pixel — tools work transparently.
        """
        if 0 <= x < self.width and 0 <= y < self.height:
            if color[3] == 0:
                self._indices[y, x] = 0
                return
            idx = nearest_palette_index(color, self._palette)
            self._indices[y, x] = idx + 1  # 1-based

    # --- Index-level access ---

    def get_index(self, x: int, y: int) -> int | None:
        if 0 <= x < self.width and 0 <= y < self.height:
            return int(self._indices[y, x])
        return None

    def set_index(self, x: int, y: int, index: int) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            self._indices[y, x] = index

    # --- Conversion ---

    def to_rgba(self, palette: list[tuple] | None = None) -> np.ndarray:
        """Convert to (H, W, 4) uint8 RGBA array for compositing/display.
        Uses LUT-based vectorized lookup for performance.
        """
        pal = palette or self._palette
        max_idx = len(pal)
        # Build lookup table: index 0 = transparent, 1..N = palette colors
        lut = np.zeros((max_idx + 1, 4), dtype=np.uint8)
        for i, color in enumerate(pal):
            lut[i + 1] = color
        # Clamp indices to valid range
        safe_indices = np.clip(self._indices, 0, max_idx)
        return lut[safe_indices]

    def to_pil_image(self, palette: list[tuple] | None = None) -> 'Image.Image':
        """Convert to PIL Image. Needed for export paths."""
        from PIL import Image
        return Image.fromarray(self.to_rgba(palette), "RGBA")

    def to_pixelgrid(self, palette: list[tuple] | None = None) -> PixelGrid:
        """Convert to a standard PixelGrid."""
        grid = PixelGrid(self.width, self.height)
        grid._pixels = self.to_rgba(palette)
        return grid

    # --- Standard operations ---

    def copy(self) -> IndexedPixelGrid:
        new = IndexedPixelGrid(self.width, self.height, self._palette)
        new._indices = self._indices.copy()
        return new

    def clear(self) -> None:
        self._indices[:] = 0

    def extract_region(self, x: int, y: int, w: int, h: int) -> IndexedPixelGrid:
        """Extract a rectangular sub-region."""
        region = IndexedPixelGrid(w, h, self._palette)
        for ry in range(h):
            for rx in range(w):
                sx, sy = x + rx, y + ry
                if 0 <= sx < self.width and 0 <= sy < self.height:
                    region._indices[ry, rx] = self._indices[sy, sx]
        return region

    def paste_region(self, source, x: int, y: int) -> None:
        """Paste another IndexedPixelGrid onto this grid, skipping index 0."""
        for sy in range(source.height):
            for sx in range(source.width):
                if source._indices[sy, sx] > 0:
                    tx, ty = x + sx, y + sy
                    if 0 <= tx < self.width and 0 <= ty < self.height:
                        self._indices[ty, tx] = source._indices[sy, sx]

    # --- Serialization ---

    def to_flat_indices(self) -> list[int]:
        return self._indices.flatten().tolist()

    def to_flat_list(self) -> list[tuple[int,int,int,int]]:
        """PixelGrid-compatible serialization (resolves to RGBA)."""
        rgba = self.to_rgba()
        flat = rgba.reshape(-1, 4)
        return [tuple(int(v) for v in row) for row in flat]

    @classmethod
    def from_flat_indices(cls, width: int, height: int, indices: list[int],
                          palette: list[tuple] | None = None) -> IndexedPixelGrid:
        grid = cls(width, height, palette)
        grid._indices = np.array(indices, dtype=np.uint16).reshape(height, width)
        return grid
```

### Helper Function

```python
def nearest_palette_index(color: tuple, palette: list[tuple]) -> int:
    """Find the palette index with minimum Euclidean RGB distance."""
    r, g, b = color[0], color[1], color[2]
    best_idx = 0
    best_dist = float('inf')
    for i, pc in enumerate(palette):
        dr = r - pc[0]
        dg = g - pc[1]
        db = b - pc[2]
        dist = dr*dr + dg*dg + db*db
        if dist < best_dist:
            best_dist = dist
            best_idx = i
    return best_idx
```

### Layer Integration

`Layer` class changes in `src/layer.py`:
- Add `color_mode` property: `"rgba"` or `"indexed"`.
- In indexed mode, `self.pixels` is an `IndexedPixelGrid` instead of `PixelGrid`.
- `Layer.__init__` accepts optional `color_mode="rgba"` and `palette` parameters.
- `Layer.copy()` preserves color mode.
- `Layer.from_grid()` detects grid type and sets color_mode accordingly.

```python
class Layer:
    def __init__(self, name: str, width: int, height: int,
                 color_mode: str = "rgba", palette: list[tuple] | None = None):
        self.name = name
        self.color_mode = color_mode
        if color_mode == "indexed":
            self.pixels = IndexedPixelGrid(width, height, palette)
        else:
            self.pixels = PixelGrid(width, height)
        # ... rest unchanged

    def copy(self) -> Layer:
        palette = self.pixels._palette if self.color_mode == "indexed" else None
        new_layer = Layer(f"{self.name} Copy", self.pixels.width, self.pixels.height,
                          color_mode=self.color_mode, palette=palette)
        if self.color_mode == "indexed":
            new_layer.pixels = self.pixels.copy()  # IndexedPixelGrid.copy() preserves palette ref
        else:
            new_layer.pixels._pixels = self.pixels._pixels.copy()
        new_layer.visible = self.visible
        new_layer.opacity = self.opacity
        new_layer.blend_mode = self.blend_mode
        new_layer.locked = self.locked
        new_layer.depth = self.depth
        new_layer.is_group = self.is_group
        import copy as copy_mod
        new_layer.effects = copy_mod.deepcopy(self.effects)
        return new_layer
```

### Compositing (`flatten_layers`)

In `flatten_layers()`, when encountering an indexed layer:
- Call `layer.pixels.to_rgba()` to get an RGBA ndarray, wrap in a temporary PixelGrid.
- Continue compositing as normal (RGBA blend modes, opacity, effects).
- The flattened output is always RGBA — indexed mode constrains **drawing**, not compositing.

The key change is in the layer pixel resolution path (around line 144-152 of current `layer.py`):

Replace the current pixel resolution + effects block (lines ~144-156 of `layer.py`) with:

```python
# Resolve pixel data to RGBA ndarray
if hasattr(layer.pixels, '_indices'):
    layer_rgba = layer.pixels.to_rgba()
else:
    layer_rgba = layer.pixels._pixels

# Apply effects (always operates on RGBA arrays)
if hasattr(layer, 'effects') and layer.effects:
    from src.effects import apply_effects
    raw = layer_rgba.copy()  # was: layer_pixels._pixels.copy() — now uses resolved RGBA
    original_alpha = raw[:, :, 3].copy()
    processed = apply_effects(raw, layer.effects, original_alpha)
    layer_img = Image.fromarray(processed, "RGBA")
else:
    layer_img = Image.fromarray(layer_rgba, "RGBA")
```

The key change: `layer_pixels._pixels.copy()` on the old line 147 is replaced by `layer_rgba.copy()`, using the already-resolved RGBA array. This ensures indexed layers with effects don't crash on `._pixels` access.

No changes needed to `flatten_layers` signature — `IndexedPixelGrid` holds its own palette reference.

### Tool Integration

**Tools don't change at all.** `IndexedPixelGrid` implements the same `get_pixel(x, y)` and `set_pixel(x, y, color)` signatures as `PixelGrid`. Internally:
- `get_pixel` resolves the stored index to RGBA using the palette reference.
- `set_pixel` snaps the RGBA color to the nearest palette entry and stores the index.
- The eraser passes `(0,0,0,0)` which maps to index 0 (transparent).

Since `IndexedPixelGrid` holds a `_palette` reference (set at construction from `Palette.colors`), no palette argument is needed in the tool call path. Tools in `src/tools.py` call `grid.set_pixel(x, y, color)` and `grid.get_pixel(x, y)` exactly as before.

**Palette reference lifecycle:** When the palette is loaded or changed, `IndexedPixelGrid._palette` must point to the current `Palette.colors` list. Since Python lists are mutable references, assigning `grid._palette = palette.colors` at layer creation is sufficient — palette color edits (in-place mutations) are automatically visible. When the palette is fully replaced (e.g., import), all indexed layers must have their `_palette` reference updated. This is handled in `convert_project_to_indexed()` and palette import code.

### AnimationTimeline & Frame

`AnimationTimeline` gains:
- `color_mode` property: `"rgba"` or `"indexed"` (stored, serialized).
- `palette_ref` property: reference to `Palette.colors` list (set by app.py or CLI on creation).
- When `color_mode == "indexed"`, ALL layer creation paths pass `color_mode="indexed"` and `palette=self.palette_ref`:
  - `Frame.__init__` — the default "Layer 1" layer. `Frame` gains optional `color_mode`/`palette` params, forwarded from timeline.
  - `add_frame()` — creates Frame with timeline's color_mode/palette.
  - `insert_frame()` — same.
  - `add_layer_to_all()` — creates Layer with timeline's color_mode/palette.
  - `sync_layers()` — creates Layer with timeline's color_mode/palette.

`Frame.flatten()` uses `flatten_layers()` which now handles indexed layers transparently (each `IndexedPixelGrid` holds its own palette reference, resolves to RGBA during compositing).

**Undo/Redo:** No changes needed. The existing `_push_undo` in app.py uses `layer.pixels.copy()` which calls the polymorphic `.copy()` method — `PixelGrid.copy()` for RGBA, `IndexedPixelGrid.copy()` for indexed. Restore replaces `layer.pixels = prev` with the snapshotted object. Both grid types support this pattern correctly.

### Project Format v4

```json
{
    "version": 4,
    "color_mode": "indexed",  // or "rgba" (default if absent)
    // ... existing fields ...
    "frames": [{
        "layers": [{
            "color_mode": "indexed",
            "indices": [0, 1, 1, 2, ...],  // flat uint16 list
            // OR for rgba layers:
            "pixels": [[r,g,b,a], ...],
        }]
    }]
}
```

Backward compat: v1-v3 files load as `color_mode: "rgba"` (existing behavior unchanged). v4 files with `color_mode: "indexed"` load indexed layers.

### Palette Color Editing in Indexed Mode

When the user changes a palette color in indexed mode:
- All pixels using that index automatically display the new color (they store indices, not RGBA).
- No pixel data needs to change.

When the user removes a palette color at index `R` (1-based):
1. Build new palette (remove color at position R-1 from palette list).
2. Find nearest color in the NEW palette for the removed color → replacement index `N`.
3. For every pixel in every layer in every frame:
   - If index == R: set to N+1 (remap to nearest)
   - If index > R: decrement by 1 (shift down)
   - If index < R: no change
This order (remap then shift in one pass) is safe because remapped pixels get their final index directly.

---

## 2. Color Reduction / Quantization

### `src/quantize.py`

```python
def median_cut(pixels: np.ndarray, num_colors: int) -> list[tuple[int,int,int,int]]:
    """Reduce colors using median cut algorithm.

    Args:
        pixels: (N, 4) uint8 array of RGBA pixels. Transparent pixels (a==0) are skipped.
        num_colors: Target palette size (2-256).
    Returns:
        List of RGBA color tuples.
    """
    # Filter out transparent pixels
    # Recursively split color boxes along channel with largest range
    # Return centroid of each box as palette color

def quantize_to_palette(grid: PixelGrid, palette: list[tuple]) -> IndexedPixelGrid:
    """Map each pixel to nearest palette color, return IndexedPixelGrid."""
    # Uses nearest_palette_index for each non-transparent pixel
```

### Conversion Functions (`src/scripting.py` / standalone)

```python
def convert_project_to_indexed(timeline: AnimationTimeline, palette: Palette,
                                num_colors: int | None = None) -> None:
    """Convert all frames/layers from RGBA to indexed.

    If num_colors is provided, run median_cut first to generate optimal palette.
    If None, use existing palette colors for quantization.
    """
    # 1. Optionally generate palette via median_cut from all pixel data
    # 2. For each frame, each layer: quantize_to_palette → replace with IndexedPixelGrid
    # 3. Set timeline.color_mode = "indexed"

def convert_project_to_rgba(timeline: AnimationTimeline, palette: Palette) -> None:
    """Expand indexed layers back to RGBA."""
    # For each indexed layer: to_pixelgrid(palette) → replace pixels
    # Set timeline.color_mode = "rgba"
```

### UI Integration

- **Menu:** Image > Convert to Indexed...
- **Dialog:** Spinbox for color count (2-256, default: current palette size), preview swatch row, "Convert" / "Cancel"
- **Reverse:** Image > Convert to RGBA
- **API:** `api.convert_to_indexed(num_colors=None)`, `api.convert_to_rgba()`

---

## 3. Palette Import/Export

### `src/palette_io.py`

```python
def load_palette(path: str) -> list[tuple[int,int,int,int]]:
    """Auto-detect format from extension and load palette colors."""

def save_palette(path: str, colors: list[tuple[int,int,int,int]], name: str = "Untitled") -> None:
    """Save palette in format matching extension."""

# Internal format handlers:
def _load_gpl(path: str) -> list[tuple]: ...
def _save_gpl(path: str, colors: list[tuple], name: str) -> None: ...

def _load_pal(path: str) -> list[tuple]: ...
def _save_pal(path: str, colors: list[tuple]) -> None: ...

def _load_hex(path: str) -> list[tuple]: ...
def _save_hex(path: str, colors: list[tuple]) -> None: ...

def _load_ase(path: str) -> list[tuple]: ...
def _save_ase(path: str, colors: list[tuple], name: str) -> None: ...
```

### Format Details

**GPL (GIMP Palette):**
```
GIMP Palette
Name: My Palette
#
  0   0   0	Black
255 255 255	White
```
- Parse: skip lines starting with `#` or `GIMP` or `Name:`, split remaining lines on whitespace, take first 3 as R G B. Alpha defaults to 255.
- Write: header + `R G B\tcolor_N` per line.

**PAL (JASC-PAL):**
```
JASC-PAL
0100
16
0 0 0
255 255 255
```
- Parse: skip first 2 lines, line 3 = count, remaining = `R G B` space-separated.
- Write: header lines + count + `R G B` per line.

**HEX (Lospec):**
```
000000
ffffff
ff0077
```
- Parse: one hex color per line, 6 chars, no `#`. Alpha = 255.
- Write: lowercase hex per line, no `#`.

**ASE (Adobe Swatch Exchange):**
- Binary, big-endian.
- Header: `ASEF` magic, version (1.0), block count.
- Color entry block: type `0x0001`, name (UTF-16), color model (`RGB `), 3 floats (0.0-1.0), type word.
- Group blocks: type `0xC001` (start) / `0xC002` (end). We ignore groups.
- Parse: read color entry blocks, convert RGB floats to 0-255, alpha = 255.
- Write: header + one color entry block per color, RGB model, floats.

### UI Integration

- Palette panel: Add "Import" / "Export" buttons (or gear menu dropdown).
- **Import dialog:** File open with filter `*.gpl;*.pal;*.hex;*.ase`. On load, ask user: "Replace current palette" or "Append to palette".
- **Export dialog:** File save with type dropdown for format selection.
- **API:** `api.palette.load_file(path)`, `api.palette.save_file(path)`
  - These are convenience methods added to `Palette` (or top-level in `palette_io.py` used by scripting API).

---

## 4. Aseprite (.ase/.aseprite) Import

### `src/aseprite_import.py`

Read-only import of Aseprite's binary format.

```python
def load_aseprite(path: str) -> tuple[AnimationTimeline, Palette]:
    """Parse .ase/.aseprite file and return (timeline, palette)."""
```

### Aseprite Binary Format Summary

**File structure:**
- **Header** (128 bytes): magic `0xA5E0`, frame count, width, height, color depth (8=indexed, 16=grayscale, 32=RGBA), flags, palette entry count, pixel ratio, etc.
- **Frames:** Each has a header (size, magic `0xF1FA`, chunk count, duration_ms) followed by chunks.

**Key chunk types:**
| Chunk | Type | What it contains |
|-------|------|-----------------|
| Old palette | `0x0004` | 256-color palette (legacy) |
| Old palette2 | `0x0011` | Legacy palette |
| Layer | `0x2004` | Layer flags, type, blend mode, opacity, name |
| Cel | `0x2005` | Layer index, x/y offset, opacity, cel type (raw/linked/compressed) |
| Frame tags | `0x2018` | Tag name, from/to frame, color |
| Palette | `0x2019` | New palette format with per-entry name |
| Color profile | `0x2007` | ICC profile (skip) |
| Slice | `0x2022` | Nine-slice data (skip) |

**Cel types:**
- `0` = Raw: uncompressed RGBA/indexed pixel data
- `1` = Linked: references another frame's cel (we expand to raw)
- `2` = Compressed: zlib-compressed pixel data

**Color depth handling:**
- 32bpp (RGBA): direct import as PixelGrid
- 8bpp (Indexed): import as IndexedPixelGrid if project is indexed mode, otherwise expand to RGBA using the file's palette
- 16bpp (Grayscale): convert to RGBA (R=G=B=value, A=alpha)

### Import Mapping

```python
# Blend mode mapping: Aseprite → RetroSprite
ASE_BLEND_MAP = {
    0: "normal",
    1: "multiply",
    2: "screen",
    3: "overlay",
    4: "darken",
    5: "lighten",
    # 6: color_dodge → fallback "normal"
    # 7: color_burn → fallback "normal"
    # 8: hard_light → fallback "normal"
    # 9: soft_light → fallback "normal"
    10: "difference",
    # 11: exclusion → fallback "normal"
    # 12: hue → fallback "normal"
    # 13: saturation → fallback "normal"
    # 14: color → fallback "normal"
    # 15: luminosity → fallback "normal"
    16: "addition",
    17: "subtract",
    # 18: divide → fallback "normal"
}
```

### Import Details

- **Cel offsets:** Aseprite cels have x/y position offsets from canvas origin. Pixel data must be pasted at that offset into a full-canvas-sized layer, not at (0,0).
- **Layer opacity:** Aseprite stores as byte (0-255). Convert to float: `opacity = ase_opacity / 255.0`.
- **Linked cels (type 1):** Reference a cel from another frame. Expand by copying the referenced cel's pixel data into the current frame.
- **Compressed cels (type 2):** zlib-decompress before reading pixel data.
- **Color depth:** Aseprite indexed files (8bpp) import as indexed mode. RGBA (32bpp) as RGBA. Grayscale (16bpp) as RGBA with R=G=B=value.

### What We Skip (with warning to stderr)

- Linked cels: expanded to full pixel data (no warning needed, transparent to user)
- Tilemap layers: skipped with warning
- Group layers: children imported as top-level layers with warning
- Slices, user data, color profiles: silently ignored
- External files: not supported

### UI Integration

- **File > Open:** Accept `.ase` and `.aseprite` extensions alongside `.retro`
- **CLI:** `python main.py export input.ase output.png` loads via `load_aseprite`
- Detection: check file extension in `_open_project()` and `cli.py`'s `cmd_export`

---

## 5. PNG Sequence Export

### `src/export.py` Addition

```python
def export_png_sequence(timeline, output_path: str, scale: int = 1,
                        layer: int | str | None = None) -> list[str]:
    """Export each frame as a numbered PNG file.

    Args:
        timeline: AnimationTimeline
        output_path: Base path like "sprites/hero.png"
                     Frames become "sprites/hero_000.png", "sprites/hero_001.png", etc.
        scale: Nearest-neighbor upscale factor (1-8)
        layer: Optional layer index or name. None = flattened composite.

    Returns:
        List of exported file paths.
    """
    base, ext = os.path.splitext(output_path)
    paths = []
    for i in range(timeline.frame_count):
        if layer is not None:
            # Export specific layer
            frame_obj = timeline.get_frame_obj(i)
            if isinstance(layer, str):
                target = next((l for l in frame_obj.layers if l.name == layer), None)
            else:
                target = frame_obj.layers[layer] if 0 <= layer < len(frame_obj.layers) else None
            if target:
                img = target.pixels.to_pil_image()  # Works for both PixelGrid and IndexedPixelGrid
            else:
                img = Image.new("RGBA", (timeline.width, timeline.height), (0,0,0,0))
        else:
            grid = timeline.get_frame(i)
            img = grid.to_pil_image()

        if scale > 1:
            img = img.resize((timeline.width * scale, timeline.height * scale), Image.NEAREST)

        frame_path = f"{base}_{i:03d}{ext}"
        img.save(frame_path)
        paths.append(frame_path)
    return paths
```

### Integration Points

- **File > Export > PNG Sequence...**: Dialog with output folder + base name, scale spinbox, optional layer dropdown
- **CLI:** `python main.py export input.retro output.png --format frames --scale 2`
  - The `frames` format is already anticipated in `cli.py` — implement the handler in `cmd_export`
- **API:** `api.export_frames(path, scale=1, layer=None)` convenience method on RetroSpriteAPI

---

## 6. Architecture

### New Files (4)

| File | Purpose |
|------|---------|
| `src/quantize.py` | Median cut algorithm + quantize_to_palette |
| `src/palette_io.py` | GPL/PAL/HEX/ASE palette import/export |
| `src/aseprite_import.py` | .ase/.aseprite binary format parser |
| `tests/test_interop_color.py` | Tests for all Batch 6 features |

### Modified Files (8)

| File | Changes |
|------|---------|
| `src/pixel_data.py` | Add `IndexedPixelGrid` class + `nearest_palette_index` helper |
| `src/layer.py` | Add `color_mode` param, handle IndexedPixelGrid in `flatten_layers` |
| `src/palette.py` | Add `remove_color()`, `replace_color()` methods |
| `src/export.py` | Add `export_png_sequence()` |
| `src/project.py` | v4 format: serialize/deserialize indexed layers + color_mode |
| `src/app.py` | Indexed mode UI (menu items, convert dialogs, palette import/export), .ase in Open dialog |
| `src/cli.py` | Handle `frames` format, .ase input files |
| `src/scripting.py` | Add `convert_to_indexed`, `convert_to_rgba`, `export_frames` to API |

### Dependency Flow

```
aseprite_import.py → animation.py, layer.py, pixel_data.py, palette.py
quantize.py → pixel_data.py (IndexedPixelGrid, nearest_palette_index)
palette_io.py → (standalone, no project deps — only stdlib + struct)
export.py (png sequence) → animation.py, pixel_data.py, PIL
project.py (v4) → pixel_data.py (IndexedPixelGrid)
```

No circular dependencies. `palette_io.py` is fully standalone. `aseprite_import.py` depends only on data modules.

### Color Mode Scope

`color_mode` is a **project-wide** setting on `AnimationTimeline`. All normal layers share the same mode. Per-layer `color_mode` exists only for serialization/deserialization convenience — the conversion functions convert all layers at once.

**Tilemap layers in indexed mode:** Tileset tiles remain RGBA arrays (they are pre-rendered bitmaps). `TilemapLayer` is unaffected by indexed mode — it already composites via RGBA. The conversion functions (`convert_project_to_indexed/rgba`) skip tilemap layers.

### CLI `info` Command

Update `cmd_info` to read the actual project version from the loaded data instead of hardcoding `(v3)`. Display `color_mode` when it is indexed.
