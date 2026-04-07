# Import/Export Parity — Design Spec

**Date:** 2026-04-06
**Status:** Approved
**Approach:** Hybrid — Shared Core + Format-Specific Dialogs

## Problem

RetroSprite exports 5 animated formats (GIF, APNG, WebP, PNG sequence, sprite sheet) but cannot import any of them back. Every competing pixel art editor (Aseprite, Pixelorama, LibreSprite) supports at least GIF and sprite sheet roundtripping. This is the most significant feature gap versus the competition.

## Goals

- Close all 5 import/export parity gaps
- Provide consistent UX across all import formats
- Follow existing codebase patterns (mixin composition, stateless parsers)

## User Decisions (from brainstorming)

| Decision | Choice |
|----------|--------|
| Scope | All 5 formats (GIF, APNG, WebP, PNG sequence, sprite sheet) |
| Project mode | Ask user: "New Project" or "Insert as Frames" |
| Canvas resize (insert mode) | Ask user: "Resize canvas", "Scale import", or "Center and crop" |
| Sprite sheet import | JSON sidecar + manual grid (no smart slice) |
| PNG sequence selection | Both folder scan and multi-file select |
| Frame timing | Ask user: "Keep original" or "Use project FPS" |

---

## Architecture

### Data Model

```python
@dataclass
class ImportedAnimation:
    frames: list[Image.Image]       # RGBA PIL images, one per frame
    durations: list[int]            # ms per frame (same length as frames)
    width: int
    height: int
    palette: list[tuple[int, int, int, int]] | None  # extracted RGBA colors, or None
    source_path: str                # original file path (for dialog display and errors)
```

All parsers produce this common structure. No parser touches the timeline or UI.

**Validation:** Every parser must verify `len(frames) > 0` and raise `ValueError` with a clear message if the source yields no extractable frames (corrupted file, empty sequence, etc.).

**Memory note:** All frames are held in memory as RGBA PIL Images. For typical pixel art sizes (up to 256x256, ~100 frames) this is under 30MB. Very large imports (1024x1024, 200+ frames) could consume ~800MB. No lazy loading is implemented — this is a documented limitation.

### Import Settings

```python
@dataclass
class ImportSettings:
    mode: str          # "new_project" or "insert"
    resize: str        # "match", "scale", "crop" (only used in insert mode)
    timing: str        # "original" or "project_fps"
```

### Pipeline

```
Format-specific input (file dialog / pre-dialog)
        │
        ▼
    Parser function → ImportedAnimation
        │
        ▼
    Shared ImportDialog → ImportSettings
        │
        ▼
    build_timeline_from_import() → AnimationTimeline
        │
        ▼
    file_ops.py applies to app state
```

---

## Parsers

### `src/animated_import.py` — GIF, APNG, WebP + timeline builder

```python
def parse_gif(path: str) -> ImportedAnimation
def parse_apng(path: str) -> ImportedAnimation
def parse_webp(path: str) -> ImportedAnimation
```

All three use the same Pillow pattern:
- `ImageSequence.Iterator(img)` to walk frames
- `img.info['duration']` for per-frame timing (default 100ms if missing)
- Convert each frame to RGBA
- Extract palette from first P-mode frame (GIF) or collect unique colors

**GIF disposal method handling:** GIF frames can use disposal methods (0=unspecified, 1=leave/cumulative, 2=restore to background, 3=restore to previous). Simply iterating with `ImageSequence` does NOT automatically composite cumulative frames. The `parse_gif` implementation must maintain a running canvas and composite each frame onto it according to the disposal method. The recommended approach: after `img.seek(n)`, call `img.convert("RGBA")` and paste onto a persistent background image, respecting `img.disposal_method` and `img.dispose_extent`. This is the single most common bug in GIF import implementations.

**APNG detection:** APNG files may use `.png` extension instead of `.apng`. When a `.png` file is opened, check `getattr(img, 'n_frames', 1) > 1` to detect animated PNGs and route them to `parse_apng()` instead of treating them as static images.

Also contains the shared `ImportedAnimation` dataclass and timeline builder:

```python
def build_timeline_from_import(
    animation: ImportedAnimation,
    settings: ImportSettings,
    existing_timeline: AnimationTimeline | None = None,
    project_fps: int = 10,
) -> tuple[AnimationTimeline, list[tuple[int, int, int, int]] | None]
```

Returns `(timeline, palette_colors)` — matching the `load_aseprite` / `load_psd` convention of returning palette data alongside the timeline.

**New Project mode:**
- Creates fresh `AnimationTimeline(width, height)`
- Clears default frame, builds Frame + Layer per imported frame
- Sets `duration_ms` per frame (original or normalized to `1000 / project_fps`)
- Returns the extracted `animation.palette` for the app to apply

**Insert mode:**
- Operates on `existing_timeline`
- Applies resize strategy to each imported frame:
  - `match`: resizes canvas to imported dimensions. **All existing frames** in the timeline are also resized (padded with transparent pixels or cropped) to match the new canvas size. Updates `timeline.width` and `timeline.height`.
  - `scale`: scales imported frames to current canvas size (NEAREST). Existing frames untouched.
  - `crop`: centers imported frames on current canvas, clips overflow. Existing frames untouched.
- Inserts frames sequentially after `current_index`: frame 1 at `current_index + 1`, frame 2 at `current_index + 2`, etc.
- Calls `sync_layers()` to keep layer structure consistent
- Returns `None` for palette (existing palette preserved in insert mode)

### `src/sequence_import.py` — PNG sequence, sprite sheet

```python
def parse_png_sequence(paths: list[str]) -> ImportedAnimation
def parse_sprite_sheet_json(png_path: str, json_path: str) -> ImportedAnimation
def parse_sprite_sheet_grid(path: str, cols: int, rows: int,
                            frame_w: int, frame_h: int) -> ImportedAnimation
```

- **PNG sequence**: Takes pre-sorted file paths, loads each as RGBA frame, durations default to 100ms
- **Sprite sheet JSON**: Reads RetroSprite's own JSON sidecar, slices PNG using frame rects (`x`, `y`, `w`, `h`), reads durations from metadata. **Note:** The current `save_sprite_sheet()` in `src/export.py` line 38 hardcodes `"duration": 100` instead of using `frame_obj.duration_ms`. This bug must be fixed as part of this feature to enable proper roundtripping of per-frame timing data.
- **Sprite sheet grid**: User-specified grid, crops each cell left-to-right top-to-bottom, durations default to 100ms

---

## UI Dialogs (`src/ui/import_dialog.py`)

### Shared Import Dialog

Shown after a parser produces an `ImportedAnimation`. Styled with cyberpunk neon theme from `src/ui/theme.py`.

```
┌─ Import Animation ──────────────────────────┐
│                                              │
│  Source: explosion.gif (12 frames, 64×48)    │
│                                              │
│  ── Project Mode ──────────────────────────  │
│  ○ New Project (replaces current canvas)     │
│  ○ Insert as Frames (after current frame)    │
│                                              │
│  ── Canvas Size ─────────────── (insert only)│
│  ○ Resize canvas to match (64×48)            │
│  ○ Scale import to fit canvas (32×32)        │
│  ○ Center and crop to canvas                 │
│                                              │
│  ── Timing ────────────────────────────────  │
│  ○ Keep original timing (50-200ms per frame) │
│  ○ Use project FPS (100ms per frame)         │
│                                              │
│         [ Cancel ]  [ Import ]               │
└──────────────────────────────────────────────┘
```

- Canvas Size section disabled when "New Project" selected
- Timing section shows actual duration range from parsed data
- Returns `ImportSettings` or `None` on cancel

### Sprite Sheet Pre-Dialog

```
┌─ Import Sprite Sheet ───────────────────────┐
│                                              │
│  ○ Use JSON metadata (RetroSprite format)    │
│    [ Browse .json ]  spritesheet.json        │
│  ○ Manual grid                               │
│    Columns: [4]   Rows: [3]                  │
│    Frame W: [32]  Frame H: [32]              │
│                                              │
│  Preview: 12 frames detected                 │
│                                              │
│         [ Cancel ]  [ Next → ]               │
└──────────────────────────────────────────────┘
```

### PNG Sequence Pre-Dialog

```
┌─ Import PNG Sequence ───────────────────────┐
│                                              │
│  ○ Scan folder for numbered PNGs             │
│    [ Browse Folder ]  /sprites/walk/         │
│    Found: walk_000.png ... walk_011.png      │
│                                              │
│  ○ Select individual files                   │
│    [ Browse Files ]  12 files selected       │
│                                              │
│         [ Cancel ]  [ Next → ]               │
└──────────────────────────────────────────────┘
```

Folder scan matches `*_NNN.png` or `*NNN.png` patterns with natural sorting.

---

## Menu Wiring

### `src/app.py` — Menu addition

Add "Import Animation..." item to File menu, between "Open Image..." and "Export..." — forming a natural import/export pair.

### `src/file_ops.py` — `_import_animation()` method

1. File dialog with filters: `GIF (*.gif)`, `APNG (*.apng)`, `WebP (*.webp)`, `PNG Sequence (*.png)`, `Sprite Sheet (*.png)`, `All files (*.*)`
2. Detect format from extension
3. For `.png` files: first check `getattr(img, 'n_frames', 1) > 1` — if animated, route to `parse_apng()`. Otherwise show a small chooser dialog with three options — "Single Image", "Sprite Sheet", or "PNG Sequence". Single Image falls through to the existing `_open_image()` behavior. The other two open their respective pre-dialogs.
4. If sprite sheet or PNG sequence → show format-specific pre-dialog
5. Parse file → `ImportedAnimation`
6. Show shared `ImportDialog` → `ImportSettings`
7. Call `build_timeline_from_import()`
8. If "New Project": replace `self.timeline`, apply `palette_colors` to `self.palette.colors`, call `_reset_state()`, update title/panels
9. If "Insert": `_push_undo()`, insert frames, `_refresh_all()`

---

## Testing

### `tests/test_animated_import.py`

Parser tests (headless, no UI):
- `test_parse_gif_frames` — 3-frame GIF with varying durations
- `test_parse_gif_single_frame` — static GIF returns 1 frame
- `test_parse_gif_missing_duration` — defaults to 100ms
- `test_parse_gif_disposal_cumulative` — GIF with disposal=1 (cumulative frames) composites correctly
- `test_parse_gif_empty_raises` — corrupted/0-frame GIF raises ValueError
- `test_parse_apng_frames` — multi-frame APNG
- `test_parse_apng_from_png_extension` — APNG saved as .png is detected and parsed correctly
- `test_parse_webp_frames` — multi-frame WebP
- `test_parse_source_path_preserved` — all parsers populate `source_path` field

Timeline builder tests:
- `test_build_new_project` — correct frame count, dimensions, durations
- `test_build_new_project_palette` — palette colors returned and non-None
- `test_build_insert_frames` — frames inserted after current index in sequential order
- `test_build_insert_resize_match` — canvas and all existing frames resized to imported dimensions
- `test_build_insert_resize_scale` — imported frames scaled to canvas
- `test_build_insert_resize_crop` — crop/center behavior
- `test_build_insert_palette_none` — insert mode returns None for palette
- `test_build_timing_normalize` — all durations set to project FPS
- `test_build_timing_original` — per-frame durations preserved

### `tests/test_sequence_import.py`

- `test_parse_png_sequence` — 4 numbered PNGs, correct order and count
- `test_parse_png_sequence_natural_sort` — `frame_2.png` before `frame_10.png`
- `test_parse_png_sequence_empty_raises` — 0 matching files raises ValueError
- `test_parse_sprite_sheet_json` — sheet + JSON sidecar, frames match metadata
- `test_parse_sprite_sheet_json_durations` — verify per-frame durations from JSON (after export bug fix)
- `test_parse_sprite_sheet_grid` — 4×3 grid produces 12 correct frames
- `test_parse_sprite_sheet_grid_empty_raises` — 0×0 grid raises ValueError

Format disambiguation tests:
- `test_png_apng_detection` — `.png` file with `n_frames > 1` detected as APNG

All test assets created programmatically with Pillow — no fixture files.

---

## Files Changed/Created

| File | Action | Purpose |
|------|--------|---------|
| `src/animated_import.py` | **New** | `ImportedAnimation`, GIF/APNG/WebP parsers, `build_timeline_from_import()` |
| `src/sequence_import.py` | **New** | PNG sequence + sprite sheet parsers |
| `src/ui/import_dialog.py` | **New** | Shared import dialog + sprite sheet config + PNG sequence selection |
| `src/file_ops.py` | **Modified** | Add `_import_animation()` method |
| `src/app.py` | **Modified** | Add "Import Animation..." menu item |
| `tests/test_animated_import.py` | **New** | Parser + builder tests |
| `tests/test_sequence_import.py` | **New** | Sequence + sprite sheet tests |
| `src/export.py` | **Modified** | Fix `build_sprite_sheet()` to use `frame_obj.duration_ms` instead of hardcoded 100 |
| `README.md` | **Modified** | Update import format list |

## Dependencies

No new dependencies. All formats handled by Pillow (already in the project) + standard library.

**Pillow version requirement:** Animated WebP per-frame duration extraction requires Pillow >= 9.0. Verify the project's current Pillow version meets this. The project already exports WebP, so this is expected to be satisfied.
