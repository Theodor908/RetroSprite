# RetroSprite — AI Agent Instructions

## Project

RetroSprite is a lightweight Python pixel art editor and animation tool.
Stack: Python 3.8+, NumPy, Tkinter, Pillow, imageio.

## Commands

```bash
python -m pytest tests/    # Run tests (must pass before any PR)
python main.py             # Launch the app
python -m src.cli --help   # CLI batch mode
```

## Architecture

Entry: `main.py` → `src/app.py:RetroSpriteApp`

`RetroSpriteApp` uses **mixin composition** — 5 focused modules:

| Mixin File | Class | Responsibility |
|------------|-------|---------------|
| `src/input_handler.py` | `InputHandlerMixin` | Canvas click/drag/release, tool dispatch, selection, clipboard |
| `src/file_ops.py` | `FileOpsMixin` | Save/load/export/import, auto-save, palette I/O |
| `src/rotation_handler.py` | `RotationMixin` | Rotation mode state machine + context bar |
| `src/tilemap_editor.py` | `TilemapEditorMixin` | Tilemap layer creation, tile editing |
| `src/layer_animation.py` | `LayerAnimationMixin` | Frames, layers, playback, onion, filters, effects |

See `docs/ARCHITECTURE.md` for full module map and data flow.
See `docs/CODING_STANDARDS.md` for detailed practices.
See `docs/CONTRIBUTING.md` for contributor guide.

## Key Conventions

- Tool dict keys are **Capitalized**: `"Pen"`, `"Eraser"`, `"Wand"`, `"Lasso"`, `"Polygon"`
- `self.timeline.frame_count` is a `@property` (no parentheses)
- `self.palette.selected_color` gives the current RGBA tuple
- Pixel arrays: `(H, W, 4) uint8` — always use NumPy ops, never Python loops
- Indexed arrays: `(H, W) uint16` — index 0 = transparent, 1-based palette
- Effects pipeline order: hue_sat → gradient_map → pattern → glow → inner_shadow → outline → drop_shadow
- Spatial effects use `original_alpha`, not modified pixels
- Blend modes: normal, multiply, screen, overlay, addition, subtract, darken, lighten, difference

## Rules

<important>
- **Do NOT add methods to `src/app.py`** — use the appropriate mixin module
- **Do NOT access `grid._pixels` directly** — use `get_pixel()`, `set_pixel()`, `copy()`, `to_pil_image()`
- **Do NOT define `__init__` in mixin classes** — all state is in `app.py`
- **Do NOT create methods with names that exist in other mixins** — each name is unique across all mixins
- **Do NOT import from `app.py` in mixin files** — one-way dependency only
- New tools → `src/tools.py` (stateless class with `apply()`)
- New effects → `src/effects.py`
- New export formats → `src/export.py` or `src/animated_export.py`
- UI widgets → `src/ui/`
- All changes require passing tests
- Use theme colors from `src/ui/theme.py` — never hardcode colors
- Font: `("Consolas", 8)` or `("Consolas", 9)`
</important>

## Testing

- 485+ tests in `tests/`
- Test files mirror source: `src/tools.py` → `tests/test_tools.py`
- Tools are testable in isolation with just a `PixelGrid`
- UI tests may need `tk.Tk()` — handle with try/except for headless environments

## No Git Commits

The user manages version control manually. Do not create commits unless explicitly asked.
