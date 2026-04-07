# Architecture Refactor & Documentation — Design Spec

**Date:** 2026-03-25
**Goal:** Split the 3,022-line `app.py` god class into focused mixin modules, and create documentation (ARCHITECTURE.md, CONTRIBUTING.md, CODING_STANDARDS.md, CLAUDE.md) for open-source contributors and AI agents.

---

## 1. Problem Statement

`RetroSpriteApp` in `src/app.py` is a 3,022-line class with 142 methods handling:
- UI construction
- Input/tool dispatch (massive if/elif chains)
- File I/O (save, load, import, export)
- Rotation mode state machine
- Tilemap editing logic
- Animation playback & frame/layer management
- Selection, clipboard, and drawing mode state
- Undo/redo, auto-save, theme toggling

This makes the codebase intimidating for contributors. There is also no architecture documentation, coding standards, or contributor guide.

## 2. Non-Goals

- **No behavioral changes.** Every feature works identically after the refactor.
- **No new features.** This is purely structural.
- **No undo system rewrite.** The current snapshot-based undo stays as-is.
- **No tool dispatch refactor to polymorphic pattern.** That's a separate future effort. We only move the existing dispatch code into a focused file.

## 3. Approach: Mixin Composition

### Why Mixins Over Delegation

| Approach | Pros | Cons |
|----------|------|------|
| **Mixins** | Zero API change, `self.` access to all state, tests stay green, simple to implement | Implicit coupling via shared `self` |
| **Delegation** | Explicit interfaces, true decoupling | Requires passing 20+ state vars or proxy objects, massive refactor |
| **Facade + sub-controllers** | Clean separation | Breaks all internal `self._foo` references, huge diff |

**Decision: Mixins.** The priority is making the codebase navigable without breaking anything. Mixins give us focused files with zero behavioral change.

## 4. Module Split Plan

### 4.1 `src/input_handler.py` — InputHandlerMixin

Methods to extract from app.py:
- `_on_canvas_click` (line ~850, ~130 lines) — the main tool dispatch
- `_on_canvas_drag` (line ~980, ~120 lines)
- `_on_canvas_release` (line ~1100, ~90 lines)
- `_draw_tool_cursor` (~20 lines)
- `_on_canvas_motion` (~30 lines)
- `_on_canvas_double_click` (~5 lines)
- `_on_escape` (~10 lines)
- `_on_enter_key` (~10 lines)
- `_on_f_key` (~10 lines)
- `_commit_polygon`, `_cancel_polygon` (~40 lines)
- `_apply_selection_op`, `_clear_selection` (~30 lines)
- `_fill_selection`, `_delete_selection` (~30 lines)
- `_capture_brush`, `_reset_brush` (~30 lines)
- `_copy_selection`, `_paste_clipboard`, `_commit_paste`, `_cancel_paste` (~60 lines)
- `_wrap_coord` (~15 lines)
- `_apply_symmetry_draw` (~15 lines)
- `_shade_at_cursor` (~30 lines)
- `_check_ink_mode` (~20 lines)

Also includes the module-level `_shift_grid()` helper function (used only by Move tool drag).

**Estimated size:** ~500 lines

### 4.2 `src/file_ops.py` — FileOpsMixin

Methods to extract:
- `_save_project`, `_save_project_as` (~60 lines)
- `_open_project` (~70 lines)
- `_new_canvas` (~20 lines)
- `_open_image` (~20 lines)
- `_clear_canvas` (~10 lines)
- `_load_reference_image`, `_toggle_reference` (~30 lines)
- `_show_export_dialog` + worker (~80 lines)
- `_compress_frame`, `_save_rle`, `_load_rle` (~40 lines)
- `_import_palette`, `_export_palette` (~60 lines)
- `_show_color_ramp_dialog` (~15 lines)
- `_update_indexed_palette_refs` (~15 lines)
- `_schedule_auto_save`, `_mark_dirty`, `_check_save_before` (~40 lines)
- `_on_close`, `_return_to_menu_action` (~20 lines)
- `_reset_state` (~50 lines)

**Estimated size:** ~400 lines

### 4.3 `src/rotation_handler.py` — RotationMixin

Methods to extract:
- `_enter_rotation_mode` (~50 lines)
- `_exit_rotation_mode` (~50 lines)
- `_rotation_handle_click` (~25 lines)
- `_rotation_handle_drag` (~50 lines)
- `_rotation_handle_release` (~40 lines)
- `_show_rotation_context_bar` (~50 lines)
- `_hide_rotation_context_bar` (~10 lines)
- `_update_rotation_angle_display` (~5 lines)
- `_on_rotation_angle_entry` (~20 lines)
- `_on_rotation_algo_change` (~5 lines)

**Estimated size:** ~300 lines

### 4.4 `src/tilemap_editor.py` — TilemapEditorMixin

Methods to extract:
- `_new_tilemap_layer_dialog` (~120 lines — the biggest single dialog)
- `_toggle_tilemap_mode` (~30 lines)
- `_on_tilemap_click` (~60 lines)
- `_draw_tile_cursor_preview` (~35 lines)
- `_tilemap_auto_sync` (~55 lines)

**Estimated size:** ~300 lines

### 4.5 `src/layer_animation.py` — LayerAnimationMixin

Methods to extract:
- `_on_frame_select` (~15 lines)
- `_add_frame`, `_insert_frame`, `_duplicate_frame`, `_delete_frame` (~50 lines)
- `_on_layer_select` (~15 lines)
- `_add_layer`, `_add_group` (~30 lines)
- `_delete_layer`, `_duplicate_layer`, `_merge_down_layer` (~30 lines)
- `_toggle_layer_visibility`, `_on_layer_visibility_idx`, `_on_layer_lock` (~30 lines)
- `_on_opacity_change`, `_on_blend_mode_change` (~15 lines)
- `_rename_layer`, `_rename_frame` (~30 lines)
- `_update_layer_list`, `_update_frame_list` (~15 lines)
- `_play_animation`, `_animate_step`, `_stop_animation` (~60 lines)
- `_cycle_playback_mode`, `_on_playback_mode_change` (~15 lines)
- `_on_onion_toggle_from_timeline`, `_on_onion_range_change`, `_toggle_onion_skin` (~20 lines)
- `_add_tag_dialog` (~30 lines)
- `_on_layer_fx_click` (~15 lines)
- `_on_display_effects_toggle` (~10 lines)
- `_apply_filter` (~30 lines)
- `_convert_to_indexed`, `_convert_to_rgba` (~30 lines)
- `_apply_gradient_fill` (~20 lines)

**Estimated size:** ~450 lines

### 4.6 `src/app.py` — Remaining Core

What stays in app.py:
- `__init__` (state initialization)
- `run`
- `_set_app_icon`
- `_build_menu`
- `_build_plugins_menu`, `_apply_plugin_filter`
- `_build_ui`
- `_bind_keys`
- `_on_tool_change`, `_capture_current_tool_settings`, `_apply_tool_settings`
- `_on_radius_change`, `_on_fill_mode_change`, `_on_size_change`
- `_on_color_select`, `_on_picker_color`
- `_push_undo`, `_undo`, `_redo`
- `_on_scroll`, `_on_scroll_h`, `_on_zoom`, `_hand_click`, `_hand_drag`
- `_on_symmetry_change`, `_cycle_symmetry`, `_on_tiled_mode_change`, `_cycle_dither`, `_toggle_pixel_perfect`
- `_on_ink_mode_change`, `_on_tolerance_change`
- `_refresh_all`, `_refresh_canvas`, `_render_canvas`, `_get_onion_grids`
- `_draw_status_scanlines`, `_update_status_text`, `_update_status`
- `_toggle_theme_mode`, `_show_feature_guide`, `_show_keybindings_dialog`

**Estimated size:** ~600 lines

### Summary

| File | Lines | Responsibility |
|------|-------|---------------|
| `app.py` | ~700 | Init, UI build, undo, rendering, settings, glue |
| `input_handler.py` | ~500 | Canvas click/drag/release, tool dispatch, selection, clipboard |
| `layer_animation.py` | ~450 | Frames, layers, playback, onion, tags, effects, filters, color mode |
| `file_ops.py` | ~400 | Save/load/export/import, auto-save, reference images, palette I/O |
| `rotation_handler.py` | ~300 | Rotation mode state machine + context bar UI |
| `tilemap_editor.py` | ~250 | Tilemap layer creation, tile editing, auto-sync |

**Total: ~2,600 lines** distributed across 6 files (from 3,022 in one file, plus per-file overhead for imports/class headers)

## 5. Documentation Plan

### 5.1 `docs/ARCHITECTURE.md`

Target: ~200 lines. Sections:

1. **Overview** — RetroSprite is a Python/Tkinter/NumPy pixel art editor. Entry point: `main.py` → `src/app.py`.
2. **Module Map** — Table of every `src/*.py` and `src/ui/*.py` with one-line descriptions.
3. **Data Flow** — User click → InputHandlerMixin → Tool.apply() → PixelGrid.set_pixel() → flatten_layers() → build_render_image() → Tkinter Canvas.
4. **Key Abstractions:**
   - `PixelGrid` — NumPy `(H,W,4) uint8` array with get/set/copy/to_pil
   - `IndexedPixelGrid` — `uint16` indices, 0=transparent, 1-based palette
   - `Layer` — Pixel data + blend mode + opacity + effects + cel_id
   - `Frame` — Layer stack for one animation frame
   - `AnimationTimeline` — Ordered list of Frames
   - `flatten_layers()` — Stack-based compositing with groups, blend modes, clipping, effects
5. **Patterns:**
   - Mixin composition for app controller
   - Stateless tool classes with `apply()` method
   - Stack-based layer group compositing
   - Event system (emit/on/off) for plugin communication
   - Cel deduplication via `cel_id` for linked cels
6. **How to Add a New Tool** — Step-by-step: create class in `tools.py`, register in `app.__init__`, add dispatch case in `input_handler.py`, add to toolbar, add test.
7. **How to Add a New Effect** — Create in `effects.py`, register in effects pipeline, add dialog config.
8. **Project File Format** — v4 JSON with base64 PNG pixel data, linked cel dedup, tileset serialization.

### 5.2 `docs/CONTRIBUTING.md`

Target: ~120 lines. Sections:

1. **Quick Start** — `git clone`, `pip install -r requirements.txt`, `python -m pytest tests/`, `python main.py`.
2. **Project Structure** — Brief directory overview pointing to ARCHITECTURE.md.
3. **Code Style:**
   - PEP 8, 100-char line limit
   - Type hints on function signatures
   - Docstrings on public classes and complex methods
   - `snake_case` for functions/variables, `PascalCase` for classes
   - Tool dict keys are Capitalized strings: `"Pen"`, `"Eraser"`, `"Wand"`
4. **Where Code Goes:**
   - New drawing tools → `src/tools.py`
   - New layer effects → `src/effects.py`
   - New export formats → `src/export.py` or `src/animated_export.py`
   - UI widgets → `src/ui/`
   - **Never add methods to `app.py`** — use the appropriate mixin
5. **Testing:**
   - `pytest tests/` — all tests must pass
   - New features require tests
   - Test files mirror source: `src/tools.py` → `tests/test_tools.py`
6. **Pull Requests:**
   - Branch from `main`, descriptive branch name
   - One feature per PR
   - Tests must pass

### 5.3 `docs/CODING_STANDARDS.md`

Target: ~150 lines. Sections:

1. **Python Style** — PEP 8, type hints, imports (stdlib → third-party → local), no wildcard imports.
2. **NumPy Conventions:**
   - Pixel arrays: `(H, W, 4)` shape, `uint8` dtype
   - Indexed arrays: `(H, W)` shape, `uint16` dtype
   - Use NumPy vectorization over Python loops for pixel operations
   - `astype(np.float32)` for intermediate math, cast back to `uint8`
3. **Tkinter Patterns:**
   - Use theme colors from `src/ui/theme.py` (never hardcode colors)
   - Font: `("Consolas", 8)` for consistency
   - Use `style_menu()`, `style_scrollbar()` helpers
4. **Encapsulation:**
   - Access `PixelGrid` via `get_pixel()`/`set_pixel()`/`copy()`/`to_pil_image()` — avoid direct `_pixels` access in new code
   - Layer properties via attributes, not internal dict manipulation
5. **Error Handling:**
   - Validate at boundaries (file I/O, user input)
   - Internal code can trust invariants (e.g., pixel coords are in-bounds after check)
   - Use `try/except` around plugin calls (error isolation)
6. **Performance Rules:**
   - NumPy operations over Python loops for anything touching pixels
   - Precompute patterns (checkerboard, dither) instead of per-pixel calculation
   - Avoid PIL ↔ NumPy round-trips in hot paths
7. **Tool Implementation:**
   - Tools are stateless classes with `apply()` method
   - Tools operate on `PixelGrid`, not `Layer` or `Frame`
   - Tools never import from `app.py`

### 5.4 `CLAUDE.md` (project root)

Target: ~100 lines. AI-agent-focused summary:

1. **Project** — RetroSprite, Python 3.8+/Tkinter/NumPy pixel art editor
2. **Commands** — `python -m pytest tests/`, `python main.py`
3. **Architecture** — Point to `docs/ARCHITECTURE.md`, list the mixin structure
4. **Key Conventions:**
   - Tool keys are Capitalized: `"Pen"`, `"Eraser"`, `"Wand"`, `"Lasso"`
   - `self.timeline.frame_count` is a `@property` (no parentheses)
   - `self.palette.selected_color` gives current RGBA tuple
   - Pixel arrays: `(H, W, 4) uint8` — use NumPy, not Python loops
   - Effects pipeline order: hue_sat → gradient_map → pattern → glow → inner_shadow → outline → drop_shadow
5. **Rules:**
   - Do NOT add methods to `src/app.py` — use the appropriate mixin module
   - Do NOT access `grid._pixels` directly — use public API methods
   - New tools go in `src/tools.py`, new effects in `src/effects.py`
   - All changes require tests
   - Use theme colors from `src/ui/theme.py`
6. **No commits** — user manages version control manually

## 6. Implementation Order

1. Create the 5 mixin files, moving methods (pure cut-paste + class wrapper)
2. Update `app.py` imports and class definition
3. Run full test suite — must be 485+ passing (same as before)
4. Write `docs/ARCHITECTURE.md`
5. Write `docs/CONTRIBUTING.md`
6. Write `docs/CODING_STANDARDS.md`
7. Write `CLAUDE.md`

## 7. Risk Mitigation

- **Circular imports:** Mixins import from `src/` modules (tools, layer, etc.) but never from `app.py`. App imports mixins. One-way dependency. Free functions like `_shift_grid` move to the mixin file that uses them.
- **No `__init__` in mixins:** Only `app.py` defines `__init__`. Mixin classes must never define `__init__` — all state is initialized in the core class.
- **No overlapping method names:** Each method name exists in exactly one mixin. No two mixins define a method with the same name.
- **IDE navigation:** At runtime, all mixin methods are methods of `RetroSpriteApp`, so "go to definition" works. Static analysis (mypy, IDE autocomplete within a mixin file) may not resolve cross-mixin `self.` references — this is an accepted trade-off.
- **Test breakage:** No behavioral change. If a test imports `RetroSpriteApp`, it still works — the class just inherits from more bases now.
- **`self` references across mixins:** This works naturally with Python MRO. A method in `InputHandlerMixin` can call `self._push_undo()` which lives in `app.py`. Python resolves it at runtime through the combined class.
- **Cross-cutting methods:** `_build_menu` and `_bind_keys` stay in core `app.py` because they reference methods from all mixins. This is accepted — they serve as "wiring" methods.
- **Imports distribution:** Each mixin file gets only the imports it needs (moved from app.py's monolithic import block). This makes per-module dependencies explicit.
