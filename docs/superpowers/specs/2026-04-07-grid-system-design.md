# Grid System Overhaul — Design Spec

**Date:** 2026-04-07
**Status:** Approved

## Problem

RetroSprite's grid overlay is hardcoded: always on at zoom >= 4px, fixed gray color, 1px spacing only, no user control. Every competing pixel art editor (Aseprite, Pixelorama) offers toggleable grids with custom sizes, colors, and offsets. Users working with tile-based assets need to see tile boundaries (8x8, 16x16, 32x32) overlaid on the canvas.

## Goals

- Dual grid system: pixel grid (1x1) + custom grid (NxM)
- Each grid independently toggleable with configurable RGBA color
- Custom grid supports arbitrary width, height, and X/Y offset
- Settings accessible via toolbar widget, View menu, and keyboard shortcuts
- Grid settings persist per-project in `.retro` files

## User Decisions

| Decision | Choice |
|----------|--------|
| Grid sizes | Fully custom NxM with offset |
| Access method | Toolbar widget + View menu + keyboard shortcuts |
| Grid count | Dual: pixel grid (1x1) + custom grid (NxM) |
| Color control | Full RGBA color picker per grid |
| Persistence | Per-project (saved in `.retro` files) |

---

## Data Model

### `src/grid.py`

```python
@dataclass
class GridSettings:
    # Pixel grid (1x1)
    pixel_grid_visible: bool = True
    pixel_grid_color: tuple[int, int, int, int] = (180, 180, 180, 80)
    pixel_grid_min_zoom: int = 4  # minimum pixel_size to show

    # Custom grid (NxM)
    custom_grid_visible: bool = False
    custom_grid_width: int = 16
    custom_grid_height: int = 16
    custom_grid_offset_x: int = 0
    custom_grid_offset_y: int = 0
    custom_grid_color: tuple[int, int, int, int] = (0, 240, 255, 120)
```

Stored on `RetroSpriteApp` as `self._grid_settings`.

### Serialization

```python
def to_dict(self) -> dict
def from_dict(cls, data: dict) -> GridSettings
```

If a field is missing from the dict (backward compatibility), use the default value.

---

## Rendering (`src/canvas.py`)

Replace the existing hardcoded grid rendering (`canvas.py:97-104`) with two configurable methods.

### Pixel Grid

- Draws lines at every pixel boundary (same as current behavior)
- Uses `grid_settings.pixel_grid_color` RGBA
- Only draws when `pixel_grid_visible` is True AND `pixel_size >= pixel_grid_min_zoom`

### Custom Grid

- Draws lines at every `custom_grid_width` / `custom_grid_height` pixel intervals
- Offset by `custom_grid_offset_x` / `custom_grid_offset_y` pixels
- Uses 2px thick lines to visually distinguish from pixel grid
- Only draws when `custom_grid_visible` is True

### Render Order

Canvas pixels → pixel grid → custom grid → overlays (selection, cursor, etc.)

### Color Handling

Tkinter canvas lines don't support true alpha. Grid line colors are computed by blending the RGBA value against a dark background assumption (`BG_DEEP`), producing an opaque hex color. This matches the existing approach — the alpha channel controls perceived brightness/subtlety of the grid lines.

---

## UI Controls

### Toolbar Widget (options bar)

A small clickable widget in the top options bar:

- Displays current state: `Grid: 16x16` when visible, `Grid: Off` when hidden (dimmed)
- **Left-click**: toggles custom grid visibility
- **Right-click**: opens Grid Settings dialog
- Updates dynamically when settings change

### View Menu

```
View
  ├── Show Pixel Grid          Ctrl+H
  ├── Show Custom Grid         Ctrl+G
  ├── Grid Settings...         Ctrl+Shift+G
  ├── ─────────────
  ├── Tiled Off
  ...
```

Inserted before the existing Tiled mode options in the View menu.

### Keyboard Shortcuts

- **Ctrl+G** — toggle custom grid visibility
- **Ctrl+H** — toggle pixel grid visibility
- **Ctrl+Shift+G** — open Grid Settings dialog

### Grid Settings Dialog (`src/ui/grid_dialog.py`)

```
┌─ Grid Settings ─────────────────────────────┐
│                                              │
│  ── Pixel Grid ────────────────────────────  │
│  [✓] Visible                                 │
│  Color: [■ ████████]                         │
│  Min Zoom: [4] px                            │
│                                              │
│  ── Custom Grid ───────────────────────────  │
│  [✓] Visible                                 │
│  Width:  [16]  Height: [16]                  │
│  Offset X: [0]  Offset Y: [0]               │
│  Color: [■ ████████]                         │
│                                              │
│         [ Cancel ]  [ Apply ]                │
└──────────────────────────────────────────────┘
```

- Color button shows a swatch of the current color
- Clicking color button opens an RGBA picker (4 sliders: R 0-255, G 0-255, B 0-255, A 0-255)
- Styled with cyberpunk neon theme, `("Consolas", 9)` font
- Apply updates `self._grid_settings` and re-renders canvas
- Cancel discards changes

---

## Persistence

### `.retro` Project Files

Grid settings serialize under a `"grid"` key in the project JSON:

```json
{
  "version": 7,
  "grid": {
    "pixel_visible": true,
    "pixel_color": [180, 180, 180, 80],
    "pixel_min_zoom": 4,
    "custom_visible": false,
    "custom_width": 16,
    "custom_height": 16,
    "custom_offset_x": 0,
    "custom_offset_y": 0,
    "custom_color": [0, 240, 255, 120]
  }
}
```

**Backward compatibility:** If `"grid"` key is missing (files saved before this feature), use `GridSettings()` defaults. Version bump from 6 to 7.

### State Lifecycle

- `app.py.__init__`: initialize `self._grid_settings = GridSettings()`
- `_save_project`: include `grid_settings.to_dict()` in project data
- `load_project`: restore from `"grid"` key or use defaults
- `_open_project`: apply loaded grid settings
- `_new_canvas`: reset to defaults

---

## Files Changed/Created

| File | Action | Purpose |
|------|--------|---------|
| `src/grid.py` | **New** | `GridSettings` dataclass, `to_dict()`, `from_dict()` |
| `src/canvas.py` | **Modified** | Replace hardcoded grid with dual-grid rendering using `GridSettings` |
| `src/ui/grid_dialog.py` | **New** | Grid Settings dialog with RGBA color picker widget |
| `src/app.py` | **Modified** | Init `_grid_settings`, View menu items, toolbar widget, Ctrl+G/H/Shift+G bindings |
| `src/file_ops.py` | **Modified** | Pass grid settings to save/load |
| `src/project.py` | **Modified** | Version bump 6→7, serialize/deserialize grid settings |
| `tests/test_grid.py` | **New** | `GridSettings` serialization, defaults, backward compat |
| `README.md` | **Modified** | Add grid features to feature list |

## Dependencies

No new dependencies. Uses Tkinter (existing) for dialog and canvas rendering.

## Testing

### `tests/test_grid.py`

- `test_defaults` — GridSettings() produces expected default values
- `test_to_dict_roundtrip` — to_dict → from_dict preserves all fields
- `test_from_dict_missing_fields` — missing keys fall back to defaults (backward compat)
- `test_from_dict_empty` — empty dict produces all defaults
- `test_pixel_grid_color_rgba` — color tuple has 4 components
- `test_custom_grid_dimensions_positive` — width/height must be >= 1
