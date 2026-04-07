# Batch 7: File Formats & Export — Design Spec

**Date:** 2026-03-12
**Status:** Approved

## Goal

Fix hardcoded export scales, add WebP/APNG animated export, add PSD layer-aware import, and unify all exports behind a single dialog.

## Scope

1. **Fix export scale** — replace hardcoded 8x (PNG), 4x (GIF/sheet) with user-chosen scale, remembered per format
2. **WebP animated export** — lossless RGBA, Pillow native
3. **APNG animated export** — RGBA, Pillow native
4. **PSD import** — layer-aware via `psd-tools`, blend modes, groups, opacity
5. **Unified Export Dialog** — single dialog for all formats with format-specific options

## Architecture

### New Files

- `src/animated_export.py` — WebP and APNG export functions
- `src/psd_import.py` — PSD file import using `psd-tools`
- `src/ui/export_dialog.py` — Unified export dialog (Tkinter Toplevel)
- `tests/test_file_formats.py` — Tests for all new functionality

### Modified Files

- `src/export.py` — add `export_png_single()` function (shared backend for PNG export)
- `src/scripting.py` — refactor `export_png` to delegate to `export_png_single`, add `export_webp`/`export_apng` methods
- `src/animation.py` — fix `export_gif` to use per-frame `duration_ms` (currently uses single global duration)
- `src/cli.py` — add `webp`, `apng` format choices to both `export` and `batch` subcommands, add `.psd` input detection, update `_detect_format` for `.webp`/`.apng`
- `src/app.py` — replace 3 export menu items (File + Animation menus) with unified "Export..." dialog, add PSD to Open dialog, use threaded export for animated formats
- `requirements.txt` — add `psd-tools>=1.9`

## Design Details

### 1. Export Modules (Backend)

#### `src/animated_export.py`

```python
def export_webp(timeline, path, scale=1, loop=0) -> None:
    """Export animation as WebP. Lossless RGBA, Pillow save_all."""

def export_apng(timeline, path, scale=1, loop=0) -> None:
    """Export animation as APNG. RGBA, disposal mode 2."""
```

Both follow the same pattern as `AnimationTimeline.export_gif`:
- Flatten each frame via `timeline.get_frame(i).to_pil_image()`
- Scale with `Image.NEAREST`
- Collect PIL images
- Save first image with `save_all=True`, append rest
- **Per-frame durations:** use `[frame.duration_ms for frame in timeline._frames]` as the `duration` parameter (Pillow accepts a list)

WebP uses `format="WEBP"`, `lossless=True`.

APNG uses `format="PNG"`, `disposal=2` (clear).

**Note:** `AnimationTimeline.export_gif` currently uses a single global duration for all frames. This batch also fixes `export_gif` to use per-frame `duration_ms` for consistency across all animated formats.

#### `src/export.py` — `export_png_single`

```python
def export_png_single(timeline, path, frame=0, scale=1, layer=None) -> None:
    """Export a single frame as PNG with user-chosen scale."""
```

Replaces the hardcoded 8x logic currently in `app.py:_save_png`. Reuses the same flatten + scale + save pattern.

`RetroSpriteAPI.export_png` in `src/scripting.py` will be refactored to delegate to this function, avoiding duplicate logic. This is the single source of truth for PNG single-frame export.

### 2. PSD Import

#### `src/psd_import.py`

```python
def load_psd(path) -> tuple[AnimationTimeline, Palette]:
    """Import PSD file with layer-aware parsing."""
```

**Layer mapping:**
- PSD `Layer` → RetroSprite `Layer` with pixel data from `layer.topil().convert("RGBA")` then `numpy.array(...)` (more reliable than `layer.numpy()` across psd-tools versions)
- PSD groups → layers with `is_group=True`, `depth` from nesting level
- Blend modes: direct map for 9 supported modes (normal, multiply, screen, overlay, darken, lighten, difference, addition, subtract), fallback "normal" for unsupported
- Opacity: PSD 0-255 → RetroSprite 0.0-1.0
- Visibility: `layer.is_visible()` → `layer.visible`

**Color handling:**
- RGB → add alpha=255
- RGBA → direct copy
- CMYK/Lab/Grayscale/Indexed → composite to RGBA via Pillow `.convert("RGBA")`

**Palette extraction:**
- Scan unique opaque colors across all layers (cap at 256)
- If PSD has embedded color table, use that
- Return `Palette("Imported")` with `.colors` replaced by extracted colors (Palette constructor defaults to Pico-8; must explicitly set `.colors` after construction)

**Limitations (by design):**
- Text layers rasterized
- Adjustment layers applied via composite
- Smart objects rasterized
- Layer effects baked into pixels via `psd-tools` composite

**PSD blend mode mapping:**

| PSD Mode | RetroSprite Mode |
|----------|-----------------|
| normal | normal |
| multiply | multiply |
| screen | screen |
| overlay | overlay |
| darken | darken |
| lighten | lighten |
| difference | difference |
| linear dodge (add) | addition |
| subtract | subtract |
| All others | normal (fallback) |

### 3. Unified Export Dialog

#### `src/ui/export_dialog.py`

`ExportDialog(parent, timeline, palette, last_settings=None)` — Tkinter Toplevel.

**Layout:**
- Format dropdown: PNG | GIF | WebP | APNG | Sprite Sheet | PNG Sequence
- Scale picker: radio buttons [1x] [2x] [4x] [8x] + custom Spinbox (1-16)
- Frame selector: "Current frame" / "All frames" (PNG single only)
- Layer selector: "All (flattened)" / layer name dropdown (PNG/Frames only)
- Sheet columns: Spinbox (Sheet only)
- Output size preview: live-updating label (e.g. "Output: 256x256 px")
- [Export] [Cancel] buttons

**Returns:** `ExportSettings` dataclass or `None` on cancel:
```python
@dataclass
class ExportSettings:
    format: str       # "png", "gif", "webp", "apng", "sheet", "frames"
    scale: int        # 1-16
    frame: int        # frame index (for png single)
    layer: str | None # layer name or None for flattened
    columns: int      # sheet columns (0=auto)
    output_path: str  # file path from save dialog
```

**Behavior:**
- Format change shows/hides relevant options
- Scale defaults to last-used (stored on app instance as `self._export_settings` dict)
- [Export] triggers file dialog with format-appropriate extension filter
- Output size preview updates live

**File extension filters per format:**
- PNG: `*.png`
- GIF: `*.gif`
- WebP: `*.webp`
- APNG: `*.apng;*.png`
- Sheet: `*.png`
- Frames: `*.png` (base name, generates numbered files)

### 4. App Integration

**Menu changes in `_build_menu()`:**
- Remove `_save_png` and `_export_sprite_sheet` from the File menu
- Remove `_export_gif` from the Animation menu
- Add single "Export..." (`Ctrl+Shift+E`) to the File menu
- Keep "Save Project" and "Save As..." unchanged

**New `_show_export_dialog()` method:**
- Opens `ExportDialog`, gets `ExportSettings`
- Dispatches to backend:
  - `"png"` → `export_png_single()`
  - `"gif"` → `timeline.export_gif()`
  - `"webp"` → `export_webp()`
  - `"apng"` → `export_apng()`
  - `"sheet"` → `save_sprite_sheet()`
  - `"frames"` → `export_png_sequence()`
- Stores settings for next time
- Fires before/after export events (event emissions are the responsibility of this dispatcher, not the backend functions)
- Animated formats (GIF, WebP, APNG) run in a background thread to avoid blocking the UI (same pattern as existing `_export_gif` thread worker)

**Open dialog:**
- Add `("Photoshop Files", "*.psd")` to filetypes
- Extension detection routes to `load_psd()`

### 5. CLI Updates

In `src/cli.py`:
- Add `"webp"` and `"apng"` to `--format` choices in both `cmd_export` and `cmd_batch` subparsers
- Update `_detect_format` to handle `.webp` → "webp", `.apng` → "apng"
- Update `cmd_batch` extension map to include webp/apng
- Add format dispatch in `cmd_export`:
  ```
  elif fmt == "webp": export_webp(...)
  elif fmt == "apng": export_apng(...)
  ```
- Add `.psd` to input file detection (alongside `.ase`)

**Note:** The canonical blend mode names in the codebase are full words: "addition" and "subtract" (not "add"/"sub" as MEMORY.md shorthand suggests).

### 6. Dependencies

Add to `requirements.txt`:
```
psd-tools>=1.9
```

## Testing

**`tests/test_file_formats.py`:**

- `TestExportPNGSingle` — export at 1x, 2x, 4x, verify output dimensions
- `TestWebPExport` — export 2-frame animation, read back, verify frame count and dimensions
- `TestAPNGExport` — export 2-frame animation, read back, verify frame count and dimensions
- `TestPSDImport` — create minimal PSD with psd-tools, import, verify layers/blend modes/opacity
- `TestPSDColorModes` — test RGB and RGBA PSD modes
- `TestCLINewFormats` — test `cmd_export` with webp and apng formats
- `TestExportSettings` — test ExportSettings dataclass

No GUI tests for ExportDialog (Tkinter tests are fragile — consistent with existing test patterns).

Expected: ~15-20 new tests.

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `src/animated_export.py` | Create | WebP + APNG export |
| `src/psd_import.py` | Create | PSD layer-aware import |
| `src/ui/export_dialog.py` | Create | Unified export dialog + ExportSettings |
| `tests/test_file_formats.py` | Create | All new tests |
| `src/export.py` | Modify | Add `export_png_single` (shared backend) |
| `src/scripting.py` | Modify | Refactor `export_png` → delegate to `export_png_single`, add `export_webp`/`export_apng` |
| `src/animation.py` | Modify | Fix `export_gif` per-frame `duration_ms` |
| `src/cli.py` | Modify | Add webp/apng/psd to export+batch, update `_detect_format` |
| `src/app.py` | Modify | Unified export menu (File+Animation), PSD in Open, threaded animated export |
| `requirements.txt` | Modify | Add psd-tools>=1.9 |
