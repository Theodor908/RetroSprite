# RetroSprite — Architecture Guide

## Overview

RetroSprite is a lightweight desktop pixel art editor and animation tool built with:

- **Python 3.8+** — core language
- **NumPy** — pixel data backend (all pixel operations are array-based)
- **Tkinter** — GUI framework (stdlib, no external GUI deps)
- **Pillow (PIL)** — image I/O, compositing, and export
- **imageio** — GIF/WebP/APNG animated export

**Entry point:** `main.py` → `src/app.py:RetroSpriteApp`

## Module Map

### Core (`src/`)

| Module | Purpose |
|--------|---------|
| `app.py` | Main app class — init, UI build, undo/redo, rendering, glue. Inherits from 5 mixins. |
| `input_handler.py` | **InputHandlerMixin** — canvas click/drag/release, tool dispatch, selection, clipboard |
| `file_ops.py` | **FileOpsMixin** — save/load/export/import, auto-save, palette I/O, reference images |
| `rotation_handler.py` | **RotationMixin** — rotation mode state machine, context bar UI |
| `tilemap_editor.py` | **TilemapEditorMixin** — tilemap layer creation, tile editing, auto-sync |
| `layer_animation.py` | **LayerAnimationMixin** — frame/layer management, playback, onion skin, filters, effects, color mode |
| `pixel_data.py` | `PixelGrid` (RGBA) and `IndexedPixelGrid` (palette-indexed) — NumPy array backends |
| `layer.py` | `Layer` model, `apply_blend_mode()`, `flatten_layers()` compositing |
| `animation.py` | `Frame` (layer stack) and `AnimationTimeline` (frame sequence) |
| `tools.py` | Stateless drawing tools: Pen, Eraser, Fill, Line, Rect, Ellipse, Polygon, etc. |
| `effects.py` | 7 non-destructive layer effects + `apply_effects()` pipeline |
| `canvas.py` | `PixelCanvas` Tkinter widget + `build_render_image()` renderer |
| `export.py` | Sprite sheet export + `export_png_single` shared backend |
| `animated_export.py` | WebP and APNG animated export |
| `project.py` | `.retro` project save/load (JSON + base64 PNG) |
| `tilemap.py` | `Tileset`, `TileRef`, `TilemapLayer` (extends Layer) |
| `palette.py` | `Palette` class — color management, ramp generation |
| `palette_io.py` | Palette import/export: GPL, PAL, HEX, ASE formats |
| `image_processing.py` | Filters: blur, scale, rotate, flip, brightness, contrast, posterize |
| `rotsprite.py` | RotSprite algorithm: Scale2x upscale → rotate → mode-downsample |
| `compression.py` | RLE compression for pixel data |
| `quantize.py` | Median cut color quantization |
| `keybindings.py` | Customizable keyboard shortcuts (~/.retrosprite/keybindings.json) |
| `scripting.py` | `RetroSpriteAPI` — plugin/script interface with event system |
| `plugins.py` | Plugin loader (~/.retrosprite/plugins/) |
| `plugin_tools.py` | `PluginTool` base class for custom tools |
| `cli.py` | CLI: export/batch/run/info subcommands, headless mode |
| `tool_settings.py` | Per-tool settings persistence |
| `aseprite_import.py` | Aseprite .ase/.aseprite file parser |
| `psd_import.py` | PSD file import (layer-aware, via psd-tools) |

### UI (`src/ui/`)

| Module | Purpose |
|--------|---------|
| `theme.py` | Neon Retro theme colors + styling functions |
| `toolbar.py` | Left toolbar with tool/symmetry/dither/pixel-perfect controls |
| `right_panel.py` | Palette, color picker, layers, frames, animation preview |
| `timeline.py` | Timeline panel (frames × layers grid, playback, onion skin) |
| `options_bar.py` | Top bar: tool size, tolerance, ink mode, fill mode |
| `dialogs.py` | Startup, canvas size, save/open, color ramp dialogs |
| `export_dialog.py` | Unified export dialog (all formats, scale, settings) |
| `effects_dialog.py` | Layer effects config with live preview |
| `tiles_panel.py` | Tile picker panel for right sidebar |
| `icons.py` | Toolbar icon generation |
| `help_window.py` | Feature guide window |
| `effects.py` | UI effect helpers (scanline texture) |

## Data Flow

```
User Click
  → PixelCanvas (Tkinter widget, converts screen coords to grid coords)
    → InputHandlerMixin._on_canvas_click()
      → Tool.apply(grid, x, y, color, ...) — stateless tool modifies PixelGrid
        → PixelGrid.set_pixel(x, y, color) — writes to NumPy array
  → _render_canvas()
    → flatten_layers() — composites all layers with blend modes, groups, effects
      → build_render_image() — scales to screen, adds checkerboard, onion skin, grid
        → Tkinter Canvas displays PIL PhotoImage
```

## Key Abstractions

### PixelGrid
NumPy `(H, W, 4) uint8` array. Core operations: `get_pixel()`, `set_pixel()`, `copy()`, `to_pil_image()`, `from_pil_image()`.

### IndexedPixelGrid
NumPy `(H, W) uint16` array. Index 0 = transparent, 1+ = palette colors (1-based). Has `to_rgba()` for rendering.

### Layer
Owns a `PixelGrid` (or `IndexedPixelGrid`). Properties: `name`, `visible`, `opacity`, `blend_mode`, `locked`, `depth` (for groups), `effects` (non-destructive), `cel_id` (for linked cels), `clipping`.

### Frame
A stack of `Layer` objects for one animation frame. Has `flatten()` → composited PixelGrid. Each frame has `duration_ms`.

### AnimationTimeline
Ordered list of `Frame` objects. Manages current frame index, frame/layer CRUD. `frame_count` is a `@property`.

### flatten_layers()
Stack-based compositing: iterates layers bottom-to-top, handles groups (push/pop stack), blend modes, opacity, clipping masks, and non-destructive effects. Returns a single `PixelGrid`.

## Patterns

### Mixin Composition
`RetroSpriteApp` inherits from 5 mixin classes. Each mixin is a focused file. Mixins do NOT define `__init__` — all state lives in `app.py`. No two mixins define methods with the same name.

### Stateless Tools
Each tool in `tools.py` is a class with an `apply()` method. Tools operate on `PixelGrid`, never on `Layer` or `Frame`. Tools never import from `app.py`.

### Event System
`RetroSpriteAPI` provides `on(event, callback)`, `off(event, callback)`, `emit(event, payload)`. Plugins subscribe to events like `tool_change`, `palette_change`, `frame_change`.

### Linked Cels
Layers have a `cel_id` (UUID). When frames share a `cel_id`, they share pixel data — editing one updates all. `unlink()` creates an independent copy.

## How to Add a New Tool

1. **Create the tool class** in `src/tools.py`:
   ```python
   class SprayTool:
       def apply(self, grid: PixelGrid, x: int, y: int, color: tuple,
                 size: int = 5, density: float = 0.3) -> None:
           # ... modify grid pixels ...
   ```

2. **Register in `app.py` `__init__`**:
   ```python
   self._tools["Spray"] = SprayTool()
   ```

3. **Add dispatch in `input_handler.py`** — add cases to `_on_canvas_click`, `_on_canvas_drag`, and `_on_canvas_release`.

4. **Add to toolbar** in `src/ui/toolbar.py` — add button and icon.

5. **Write tests** in `tests/test_tools.py`.

## How to Add a New Layer Effect

1. **Implement the effect** in `src/effects.py` as a function that takes `(pixels: np.ndarray, params: dict, original_alpha: np.ndarray)` and returns modified pixels.

2. **Register in the pipeline** — add to the `apply_effects()` function's dispatch.

3. **Add UI config** in `src/ui/effects_dialog.py` — add parameter controls.

4. **Write tests** in `tests/test_effects.py`.

Pipeline order: hue_sat → gradient_map → pattern → glow → inner_shadow → outline → drop_shadow.

## Project File Format (v4)

`.retro` files are JSON with base64-encoded PNG pixel data:

```json
{
  "version": 4,
  "width": 64, "height": 64,
  "color_mode": "rgba",
  "palette": [[r,g,b,a], ...],
  "tilesets": { "name": { "tile_width": 16, "tiles": ["base64..."] } },
  "frames": [
    {
      "name": "Frame 1",
      "duration_ms": 100,
      "layers": [
        {
          "name": "Layer 1",
          "type": "normal",
          "cel_id": "uuid",
          "visible": true,
          "opacity": 1.0,
          "blend_mode": "normal",
          "pixels": "base64-png..."
        }
      ]
    }
  ]
}
```

Linked cels: when a `cel_id` appears in multiple frames, only the first occurrence includes `pixels`; subsequent ones include `"linked_cel_id"` instead.
