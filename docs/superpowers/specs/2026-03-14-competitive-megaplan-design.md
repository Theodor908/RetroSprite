# RetroSprite Competitive Mega-Plan: 4-Phase Feature Roadmap

> **Scope:** 23 features across 4 plans, ordered by competitive impact.
> Each plan is independently shippable.
> **Tech stack:** Python, Tkinter, NumPy, PIL (existing). New optional dependencies noted per feature.

---

## Plan 1: Core Gaps (Tier 1)

These 6 features close the gaps that 5 out of 6 competitors have over RetroSprite.

### 1.1 Custom Brushes (Capture from Canvas)

**Purpose:** Let users select a region and use it as a brush. Present in Aseprite, Pro Motion, Pixelorama, LibreSprite, GrafX2.

**Design:**

**Existing implementation:** `app.py` already has `self._custom_brush_mask: set | None` (line 148), `_capture_brush()` bound to `Ctrl+B` (line 1339), and `_reset_brush()`. `PenTool.apply()` and `EraserTool.apply()` accept `mask: set` for shape-only brushes. This feature **extends** the existing system, not replaces it.

- **Color brush extension:** Add a parallel field `self._custom_brush_colors: dict[tuple[int,int], tuple] | None` alongside the existing `_custom_brush_mask: set`. Keys are `(dx, dy)` offsets (same as mask), values are RGBA colors captured from the selection.
- `_capture_brush()` is extended to populate both `_custom_brush_mask` (existing, for shape) and `_custom_brush_colors` (new, for per-pixel colors)
- Two modes:
  - **Color brush:** paints with captured per-pixel colors from `_custom_brush_colors` (new default)
  - **Monochrome brush:** paints with current foreground color using `_custom_brush_mask` shape only (existing behavior)
- `PenTool.apply()` gains an optional `color_mask: dict | None` parameter. When provided, each offset uses its own color instead of the single `color` argument. The existing `mask: set` parameter remains unchanged.
- Options bar: shows "Brush: Custom" label + "Clear" button when active. Monochrome toggle.
- Brush library: list of up to 8 recent captures in a small dropdown next to the brush indicator.
- Tool settings: `"brush_mode": "color"` (color or mono)

**Files:**
- Modify: `src/app.py` (capture logic, brush state, drawing integration)
- Modify: `src/tools.py` (PenTool/EraserTool mask handling for color brushes)
- Modify: `src/ui/options_bar.py` (brush indicator, clear button, mono toggle)
- Modify: `src/tool_settings.py` (brush_mode setting)

### 1.2 Tiled/Wrap-Around Preview Enhancement

**Purpose:** Enhance the existing tiled mode with ghost-copy rendering so artists can visually verify seamless tiling. Present in Aseprite, Pixelorama, Pro Motion, Pyxel Edit, LibreSprite.

**Existing implementation:** `app.py` already has `self._tiled_mode = "off"` (line 171) with `"off"`, `"x"`, `"y"`, `"both"` modes. The View menu has radio buttons for these modes (lines 337-345). Coordinate wrapping in draw handlers already exists (lines 891, 1006, 1130). `canvas.py` receives `tiled_mode` for rendering (line 2614).

**Enhancement design:**

- **Ghost-copy rendering:** When any tiled mode is active, render semi-transparent copies of the canvas at adjacent offsets. For `"x"`: draw left/right neighbors. For `"y"`: draw top/bottom. For `"both"`: draw all 8 surrounding copies.
- Ghost copy opacity: 40% by default (distinguishable from real canvas but clearly secondary)
- Modify `src/canvas.py` rendering path to blit composed frame at neighboring offsets when `tiled_mode != "off"`
- Add keyboard toggle shortcut `Ctrl+Shift+T` to cycle through tiled modes (avoids conflict with `Ctrl+T` which is bound to `_enter_rotation_mode()` in keybindings.py line 25)
- No new state fields needed — extends existing `_tiled_mode`

**Files:**
- Modify: `src/canvas.py` (ghost-copy rendering at neighboring offsets)
- Modify: `src/app.py` (keyboard shortcut for cycling tiled modes)
- Modify: `src/keybindings.py` (add `"tiled_cycle": "<Control-Shift-t>"`)

### 1.3 Text Tool

**Purpose:** Place pixel-rendered text on the canvas. Present in Aseprite, Pixelorama, GrafX2.

**Design:**

- New tool `"text"` in toolbar, keybinding `t` (verify against `DEFAULT_BINDINGS` in `keybindings.py` — `t` is not currently bound; `x` is avoided as it conventionally swaps fg/bg colors in pixel art editors)
- Click on canvas opens a small inline popup (Toplevel) with:
  - Text entry field
  - Font selector dropdown: 3-4 built-in pixel fonts at sizes 5px, 7px, 9px, 11px
  - Color: current foreground color (auto-updates)
  - "Apply" and "Cancel" buttons
- Built-in pixel fonts stored as bitmap definitions in `src/fonts.py` — each character is a small 2D array of 0/1 values. No external font file dependencies. Covers ASCII printable range (32-126).
- Font data format: `dict[str, dict[str, list[list[int]]]]` keyed by font name, then character.
- On "Apply": renders text to active layer at click position using `PenTool.apply()` per pixel
- Live preview: overlay on canvas updates as user types
- Anti-aliasing: off (pixel art). No AA toggle needed.

**Files:**
- Create: `src/fonts.py` (bitmap font definitions)
- Modify: `src/tools.py` (no new class — text rendering is a utility function)
- Modify: `src/app.py` (text tool interaction, popup, preview overlay)
- Modify: `src/ui/icons.py`, `src/ui/toolbar.py` (icon registration)
- Modify: `src/ui/options_bar.py` (font selector when text tool active)
- Modify: `src/tool_settings.py` (text tool defaults: font name, size)

### 1.4 Spray/Airbrush Tool

**Purpose:** Random scatter of pixels within a circular radius. Present in Aseprite, Pixelorama, Pro Motion, LibreSprite, GrafX2.

**Design:**

- New `SprayTool` class in `src/tools.py`
- Signature: `apply(grid, x, y, color, radius=8, density=0.3, dither_pattern="none")`
- Each call scatters `int(density * pi * radius^2)` random pixels within a circle of `radius` centered on `(x, y)`. Uses `random.random()` for position selection within the circle.
- During drag: `app.py` calls `spray.apply()` on each motion event (continuous application like pen)
- Dither support: respects the current dither pattern for each scattered pixel
- Toolbar: icon after existing tools, keybinding `a` (verify not bound in `keybindings.py` — `a` is currently unbound)
- Options bar: size (radius, 1-64), density slider (0.1 to 1.0)
- Tool settings: `"spray": {"size": 8, "density": 0.3, "dither": "none"}`

**Important:** Each new tool must have an entry in `TOOL_DEFAULTS` in `src/tool_settings.py`, with the key matching the lowercase tool name exactly as used in `ToolSettingsManager.save()` calls in `app.py`. Without this entry, `save()` silently drops the settings.

**Files:**
- Modify: `src/tools.py` (add SprayTool class)
- Modify: `src/app.py` (tool registration, event handling)
- Modify: `src/ui/icons.py`, `src/ui/toolbar.py` (icon)
- Modify: `src/ui/options_bar.py` (density slider)
- Modify: `src/tool_settings.py` (add `"spray"` and `"text"` to `TOOL_DEFAULTS`)

### 1.5 Crash Recovery

**Purpose:** Protect unsaved work from crashes. Existing autosave only saves to `_project_path` (no help for new/unsaved projects).

**Design:**

- Recovery directory: `~/.retrosprite/recovery/`
- Every 60 seconds (reuse existing `_auto_save_interval`), save a recovery backup regardless of whether `_project_path` is set
- Recovery file: standard `.retro` format with additional metadata: `"recovery_meta": {"original_path": str|null, "timestamp": ISO8601}`
- Recovery file naming: `recovery_<timestamp>.retro` (only keep latest — overwrite previous)
- On startup (`RetroSpriteApp.__init__`): check recovery directory. If a recovery file exists:
  - Compare timestamp to last known save of the original path (if any)
  - Prompt user: "Unsaved work found from [date/time]. Restore it?"
  - Yes: load recovery file, set `_project_path` to original if available
  - No: delete recovery file, continue normally
- On clean exit or successful manual save: delete recovery file
- On crash: recovery file persists for next startup

**Files:**
- Modify: `src/app.py` (recovery save logic, startup check, cleanup on exit)
- Modify: `src/project.py` (add recovery_meta to save format — optional field, no version bump)

### 1.6 Palette Sort

**Purpose:** Sort palette colors by hue, saturation, brightness, etc. Most competitors have this.

**Design:**

- Add `sort_by(key: str) -> list[tuple]` method to `Palette` class
- Sort keys: `"hue"`, `"saturation"`, `"brightness"`, `"luminance"`, `"red"`, `"green"`, `"blue"`
- HSV sorts use `colorsys.rgb_to_hsv()`
- Luminance uses standard formula: `0.299*R + 0.587*G + 0.114*B`
- Fully transparent colors `(a == 0)` are excluded from sorting and placed at the end
- UI: right-click on palette area → "Sort by..." submenu with the 7 options
- Undo integration: `_push_undo()` before sorting so it's reversible
- Returns new sorted color list; caller replaces palette contents

**Files:**
- Modify: `src/palette.py` (add sort_by method)
- Modify: `src/app.py` (palette context menu, undo integration)
- Modify: `src/ui/right_panel.py` (right-click menu on palette widget)

---

## Plan 2: Power Tools (Tier 2)

6 features that add professional-grade capabilities.

### 2.1 Pressure Sensitivity

**Purpose:** Tablet pen pressure maps to brush size and/or opacity. Aseprite and Pro Motion support this.

**Design:**

- **Platform approach:** Use ctypes to query Windows Ink / WinTab API for pressure data, since Tkinter doesn't expose it natively
- Module: `src/pressure.py` — provides `get_pressure() -> float | None` (0.0-1.0, None if no tablet)
- Pressure mapping options:
  - `"size"`: pressure scales brush size from 1 to `base_size * 2`
  - `"opacity"`: pressure scales opacity from 10% to 100%
  - `"both"`: both size and opacity
- Options bar: pressure toggle button (hidden if no tablet detected), mapping dropdown
- Integration: `_on_canvas_drag` reads pressure, adjusts tool parameters before calling tool.apply()
- Graceful degradation: if pressure module fails to initialize, feature is hidden entirely
- Tool settings: `"pressure": {"enabled": false, "map_to": "size"}`

**Files:**
- Create: `src/pressure.py` (platform-specific pressure reading)
- Modify: `src/app.py` (pressure integration in draw events)
- Modify: `src/ui/options_bar.py` (pressure toggle + mapping selector)
- Modify: `src/tool_settings.py` (pressure settings)

### 2.2 Interactive Scale/Skew Transform

**Purpose:** Drag handles to scale/skew selected content interactively.

**Design:**

- Activated when a selection exists and user switches to Move tool (or presses `Ctrl+Shift+S` — `Ctrl+T` is already bound to rotation mode in keybindings.py)
- 8 handles rendered around the selection bounding box:
  - 4 corners: scale (Shift for free/non-proportional)
  - 4 edges: skew/shear along that axis
- Transform computation: build a 2x3 affine matrix from handle positions
- Preview: PIL `Image.transform(Image.AFFINE, ...)` with `NEAREST` resampling, rendered as canvas overlay
- Enter/double-click: commit transform to layer (push undo first)
- Escape: cancel, restore original pixels
- State: `self._transform_handles`, `self._transform_matrix` in `app.py`

**Files:**
- Modify: `src/app.py` (transform mode, handle rendering, matrix computation, commit/cancel)
- Modify: `src/image_processing.py` (affine transform helper if needed)

### 2.3 Sprite Sheet Import

**Purpose:** Slice a sprite sheet image into animation frames.

**Design:**

- `File > Import > Sprite Sheet...` menu item
- Dialog (`src/ui/sheet_import_dialog.py`):
  - File picker for source image (PNG, BMP, etc.)
  - Tile width/height inputs (default: smallest common factor of image width/height that produces a reasonable tile count, e.g., 16px or 32px; user adjusts as needed)
  - Columns/rows display (computed from `image_width / tile_width` and `image_height / tile_height`)
  - Margin and spacing inputs (default 0)
  - Preview: grid overlay on loaded image thumbnail
  - "Import" and "Cancel" buttons
- On import:
  - Slices image into tiles using PIL crop
  - Creates new project with one frame per tile
  - Each frame has a single layer with the tile pixels
  - Palette auto-extracted from imported image
- Implementation: `src/sheet_import.py` for slicing logic

**Files:**
- Create: `src/sheet_import.py` (slice logic)
- Create: `src/ui/sheet_import_dialog.py` (dialog UI)
- Modify: `src/app.py` (menu item, import action)

### 2.4 Right-Click Tool Assignment

**Purpose:** Left mouse = tool A, right mouse = tool B. Pixelorama and GrafX2 have this.

**Design:**

- State: `self._right_tool: str = "eraser"` in `app.py`
- Right-clicking a toolbar icon assigns that tool to the right mouse button (instead of switching the primary tool)
- `<Button-3>` events on canvas activate `_right_tool` for that stroke only — `_on_canvas_click`, `_on_canvas_drag`, `_on_canvas_release` check which button is pressed
- Each mouse button remembers its own tool settings independently. Right-tool settings use a separate `ToolSettingsManager` instance (`self._right_tool_settings`) rather than prefixed keys, since `ToolSettingsManager.save()` silently drops tool names not in `TOOL_DEFAULTS`. The right-tool manager uses the same `TOOL_DEFAULTS` but maintains independent state.
- Status bar shows: `LMB: Pen | RMB: Eraser`
- Toolbar: right-assigned tool icon has a subtle right-side highlight

**Files:**
- Modify: `src/app.py` (right tool state, second ToolSettingsManager instance, event routing, status display)
- Modify: `src/ui/toolbar.py` (right-click assignment, visual indicator)
- Modify: `src/project.py` (serialize/deserialize right-tool settings separately)

### 2.5 Tilemap Data Export (JSON/XML)

**Purpose:** Export tilemap layer data in formats game engines can consume.

**Design:**

- `File > Export > Tilemap Data...` menu item
- Dialog: format picker (JSON / TMX XML), output path
- **JSON format** (Tiled-compatible subset):
  ```json
  {
    "width": 20, "height": 15,
    "tilewidth": 16, "tileheight": 16,
    "tilesets": [{"firstgid": 1, "image": "tileset.png", "tilecount": N}],
    "layers": [{"name": "...", "data": [1, 2, 0, 3, ...]}]
  }
  ```
- **TMX XML format:** same structure in Tiled's XML schema
- Tile index mapping: RetroSprite tileset index + 1 (Tiled uses 1-based, 0 = empty)
- Flip flags encoded in tile GID high bits (Tiled convention: bit 31 = horizontal, bit 30 = vertical)
- Tileset image exported as companion PNG sprite sheet
- Implementation: `src/tilemap_export.py`

**Files:**
- Create: `src/tilemap_export.py` (JSON and TMX export logic)
- Modify: `src/app.py` (menu item)
- Modify: `src/ui/export_dialog.py` (tilemap export dialog, or new dialog)

### 2.6 AnimPainting (Auto-Advance Frame)

**Purpose:** Automatically advance to next frame after each brush stroke. Pro Motion calls this AnimPainting.

**Design:**

- Toggle: shortcut `Ctrl+Shift+A`, or button in timeline panel
- State: `self._anim_painting: bool = False` in `app.py`
- On `_on_canvas_release` (end of stroke), if enabled:
  - Advance to next frame via `self.timeline.set_current((current + 1) % total_frames)` (note: the method is `set_current()`, not `set_frame()`)
  - Update timeline panel display
- Wraps from last frame back to frame 0
- Status bar shows "AnimPaint" indicator when active
- Disabled automatically when animation is playing

**Files:**
- Modify: `src/app.py` (toggle, auto-advance logic in release handler)
- Modify: `src/ui/timeline.py` (AnimPaint toggle button)

---

## Plan 3: Tilemap & Creative Tools (Tier 2-3)

6 features enhancing tilemap workflows and creative drawing capabilities.

### 3.1 Live Tile Editing

**Purpose:** Edit a tile in one location, all instances update automatically.

**Design:**

- When editing in a tilemap layer's "Pixels" mode:
  - Determine which tile the edited pixel belongs to (from tile reference at that grid position)
  - Write the pixel change to the tileset's master tile data (not to a per-instance copy)
  - Since all tile references point to the master tileset, all instances reflect the change immediately on next render
- This may largely work already if tilemap layers store references rather than pixel copies — verify during implementation
- If not: modify the tilemap pixel editing path to write back to `Tileset.tiles[tile_index]` instead of layer pixels
- Undo: snapshot the affected master tile before modification

**Files:**
- Modify: `src/tilemap.py` (ensure edit-back-to-master behavior)
- Modify: `src/app.py` (tilemap pixel editing path)

### 3.2 Isometric & Hexagonal Tilemap Grids

**Purpose:** Support non-rectangular tile grids for iso/hex game development.

**Design:**

- `TilemapLayer` gains `grid_type: str` field: `"orthogonal"` (default), `"isometric"`, `"hexagonal"`
- Coordinate conversion functions in `src/tilemap.py`:
  - `screen_to_tile(sx, sy, grid_type, tw, th) -> (col, row)`
  - `tile_to_screen(col, row, grid_type, tw, th) -> (sx, sy)`
- **Isometric:** staggered diamond layout
  - `tile_to_screen`: `sx = (col - row) * tw/2 + origin_x`, `sy = (col + row) * th/2 + origin_y`
  - `screen_to_tile`: inverse of above
- **Hexagonal:** flat-top hex with alternating row offset
  - Even rows: no offset. Odd rows: offset by `tw/2`
  - `screen_to_tile`: axial coordinate conversion with rounding to nearest hex center
- Grid rendering: draw grid lines according to grid type (diamond lines for iso, hex outlines for hex)
- UI: dropdown in tilemap layer properties to select grid type
- Tilemap export (Plan 2.5): includes `"orientation"` field in JSON/TMX

**Files:**
- Modify: `src/tilemap.py` (grid_type field, coordinate conversion functions)
- Modify: `src/app.py` (grid rendering, coordinate mapping for tilemap tools)
- Modify: `src/ui/tiles_panel.py` (grid type selector)
- Modify: `src/tilemap_export.py` (orientation field in export)

### 3.3 Color Cycling (Animated Palette)

**Purpose:** Amiga-style palette animation — colors shift through defined ranges automatically.

**Design:**

- Data model: `ColorCycle` dataclass with `start_index: int`, `end_index: int`, `speed_ms: int`, `direction: str` (forward/reverse/pingpong)
- `Palette` gains `cycles: list[ColorCycle]` field. `Palette.__init__` must initialize `self.cycles = []` by default.
- **Cycle stepping is integrated into the animation playback loop** — not a separate timer. The existing playback loop in `app.py` tracks elapsed time per frame step; color cycles accumulate elapsed time and rotate indices when their `speed_ms` threshold is reached. This prevents timer drift between animation frames and palette cycles.
- Rendering: in indexed color mode, substitute palette colors per-frame based on cycle state. In RGBA mode, remap pixels that match cycled palette entries.
- UI: right-click palette → "Color Cycling..." dialog to define/edit/remove cycle ranges
- Preview: "Play Cycles" button in dialog runs its own standalone timer (drift acceptable for preview only)
- Serialization: `"color_cycles"` array in project file (backward compatible — missing = no cycles). `load_project()` must call `palette.cycles = [ColorCycle(**c) for c in project.get("color_cycles", [])]` after loading palette colors.

**Files:**
- Modify: `src/palette.py` (ColorCycle dataclass, cycles list, rotation logic)
- Modify: `src/app.py` (cycle timer during playback, rendering integration)
- Modify: `src/project.py` (serialize/deserialize color_cycles)
- Create: `src/ui/color_cycle_dialog.py` (cycle editor dialog)

### 3.4 More Ink Modes

**Purpose:** Smear, halftone, tint, kaleidoscope drawing modes.

**Design:**

- **Smear:** On drag, sample color at new position, blend it with color from previous position. `apply(grid, x, y, prev_x, prev_y, strength=0.5)` — reads pixel at (x,y), blends with pixel at (prev_x, prev_y), writes result.
- **Halftone:** Apply ordered Bayer dither based on pixel brightness. If brightness at position exceeds Bayer threshold, draw foreground color; otherwise skip. Creates classic comic-book dot pattern.
- **Tint:** Blend foreground color with existing pixel at configurable ratio. `result = lerp(existing, foreground, tint_strength)`. Default strength 0.3.
- **Kaleidoscope:** N-fold rotational symmetry (extends existing horizontal/vertical/both symmetry). Rotates draw position around canvas center at `360/N` degree intervals. N configurable 2-12.
- Ink modes added to the existing ink mode cycle in options bar: normal → lighten → darken → smear → halftone → tint
- Kaleidoscope is a symmetry mode, not an ink mode — added to symmetry cycle: off → horizontal → vertical → both → kaleidoscope

**Files:**
- Modify: `src/tools.py` (smear, halftone, tint ink implementations)
- Modify: `src/app.py` (ink mode routing, kaleidoscope symmetry math, prev position tracking for smear)
- Modify: `src/ui/options_bar.py` (new ink modes in cycle, kaleidoscope segment count)
- Modify: `src/tool_settings.py` (new mode defaults)

### 3.5 APNG Import

**Purpose:** Import animated PNG files as animation frames.

**Design:**

- Detect APNG in `File > Open`: if `Image.open(path)` has `is_animated` attribute and it's True, treat as APNG
- For each frame in the APNG:
  - Extract frame image via PIL's `im.seek(n)` + `im.copy()`
  - Read frame duration from `im.info.get("duration", 100)` ms
  - Create a `Frame` with a single `Layer` containing the frame pixels as a `PixelGrid`
- Set up `AnimationTimeline` from the extracted frames
- Auto-extract palette from the combined frame pixels
- Handle disposal modes: PIL handles this internally when copying frames

**Files:**
- Create: `src/apng_import.py` (APNG frame extraction logic)
- Modify: `src/app.py` (detect APNG on open, route to importer)

---

## Plan 4: Advanced & Exotic (Tier 3)

7 features for power users and differentiation.

### 4.1 Animated Brushes

**Purpose:** Brush that cycles through animation frames as you paint. Extends custom brushes from Plan 1.

**Design:**

- Capture: select frames in timeline (e.g., frames 1-4), press `Ctrl+Shift+B` to capture as animated brush
- Storage: `self._animated_brush: list[dict[tuple[int,int], tuple]] | None` — list of custom brush frames
- Cycling modes:
  - **Per-stroke:** each new stroke uses next brush frame
  - **Per-pixel:** each pixel placed advances to next brush frame
  - Configurable via options bar dropdown
- `self._animated_brush_index: int = 0` tracks current frame
- Drawing: on each apply, use `_animated_brush[_animated_brush_index]` as the brush mask
- Options bar: shows "Animated Brush (N frames)" label, cycling mode dropdown, "Clear" button

**Files:**
- Modify: `src/app.py` (animated brush capture, cycling logic, drawing integration)
- Modify: `src/ui/options_bar.py` (animated brush indicator, cycling mode)

### 4.2 3D Mesh Layer (Reference)

**Purpose:** Import .obj mesh as a 2D reference layer for tracing.

**Shared prerequisite with 4.5:** Both 4.2 and 4.5 require adding `is_reference: bool = False` to the `Layer` class and skipping reference layers in `flatten_layers()` and all export functions. This shared change should be implemented once (as part of whichever feature ships first). See 4.5 for the full `is_reference` specification.

**Existing system:** `app.py` already has a reference image overlay (`self._reference_image`, `self._reference_opacity`, `File > Load Reference Image...` at line 261). The layer-based approach in 4.2/4.5 supersedes this overlay system. Migration: keep the overlay system as a lightweight alternative; layer-based references are the full-featured replacement.

**Design:**

- `Layer > Add 3D Reference...` loads an .obj file
- Minimal .obj parser in `src/mesh_import.py`: reads `v` (vertices) and `f` (faces) lines only. No materials/textures.
- Rendering: simple orthographic wireframe projection
  - Project 3D vertices to 2D: `(x, y, z) -> (x * scale + cx, -y * scale + cy)` (ignore z for orthographic)
  - Draw edges between face vertices using Bresenham lines
  - Optional: flat shading with face normals for basic depth cues
- Rendered to a reference layer (uses shared `Layer.is_reference = True` from 4.5)
- User can adjust: rotation (X/Y/Z sliders), scale, position via a small control panel
- Re-renders on parameter change

**Files:**
- Create: `src/mesh_import.py` (.obj parser + wireframe renderer)
- Modify: `src/app.py` (menu item, 3D reference controls)
- Depends on: `is_reference` field from 4.5 (or implement 4.5's Layer changes first)

### 4.3 Audio Sync for Animation

**Purpose:** Play audio in sync with animation for lip-sync, music videos, etc.

**Design:**

- **Prerequisite:** `Frame.duration_ms` is not currently serialized in `save_project()` (line 122-126 of project.py only saves name, layers, active_layer). This must be fixed first — add `"duration_ms"` to frame serialization in `save_project()` and read it back in `load_project()` (default 100ms for old files).
- `Timeline > Load Audio Track...` loads .wav file (simplest format, no codec dependencies)
- Optional dependency: `pygame.mixer` for playback (supports `set_pos()` for seeking; `simpleaudio` and `winsound` do not support mid-stream seeking). Feature hidden if `pygame` is not installed.
- Audio track state: `self._audio_path: str | None`, `self._audio_data` (loaded waveform for visualization)
- Waveform visualization: rendered as a horizontal track below the timeline's frame grid
  - Downsample waveform to match timeline pixel width
  - Draw amplitude bars per-frame column
- Playback sync: when animation plays, start audio from the corresponding time offset using `pygame.mixer.music.play(start=offset_seconds)`
  - `audio_position_ms = sum(frame.duration_ms for frame in frames[:current_index])`
  - On animation loop/restart: re-seek audio to matching position
- Frame markers: click on waveform to place named markers (stored in project file)
- Stop audio when animation stops

**Files:**
- Create: `src/audio.py` (audio loading, playback, waveform extraction)
- Modify: `src/app.py` (audio state, playback sync)
- Modify: `src/ui/timeline.py` (waveform rendering, marker UI)
- Modify: `src/project.py` (serialize audio path + markers)

### 4.4 Pixel-Art Scaling Algorithms

**Purpose:** Scale2x, Scale3x, cleanEdge, OmniScale — purpose-built for pixel art upscaling.

**Design:**

- Added as options in `Image > Resize` dialog alongside existing nearest-neighbor
- **Scale2x:** For each pixel, examine 4 neighbors (N, S, E, W). Output 2x2 block where corners inherit from neighbors if they match specific patterns. Pure lookup table algorithm.
- **Scale3x:** Extension of Scale2x to 3x3 output blocks. Same neighbor-pattern approach.
- **cleanEdge:** Edge-detection pass identifies pixel art edges, then applies bilinear interpolation only in non-edge regions. Edges stay crisp.
- **OmniScale:** Combines EPX (Scale2x) with linear filtering — applies EPX first, then softens non-edge areas. Good for higher scale factors.
- All implementations: pure NumPy, operate on RGBA arrays
- Scale factors: Scale2x = 2x only, Scale3x = 3x only, cleanEdge/OmniScale = arbitrary integer factors (2x-8x)
- UI: dropdown in resize dialog showing algorithm name + brief description

**Files:**
- Modify: `src/image_processing.py` (add scale2x, scale3x, clean_edge, omni_scale functions)
- Modify: `src/app.py` (resize dialog algorithm selector)

### 4.5 Reference Layers (Shared Infrastructure for 4.2)

**Purpose:** Import any image as a non-exportable drawing reference. Also provides the `is_reference` infrastructure used by 4.2 (3D Mesh Layer).

**Existing system:** `app.py` already has a simple reference image overlay (`self._reference_image`, `self._reference_opacity = 0.3`, `File > Load Reference Image...` at line 261, `_load_reference_image()` and `_toggle_reference()` at lines 2529-2550). The layer-based approach here is the full-featured replacement. The existing overlay system is kept as a lightweight alternative for users who don't need layer-stack integration.

**Design:**

- `Layer > Add Reference Layer...` loads an image file (PNG, JPG, BMP, etc.)
- Image loaded via PIL, converted to RGBA, stored in a `Layer` with `is_reference = True`
- **Layer class changes (shared with 4.2):**
  - Add `is_reference: bool = False` to `Layer.__init__`
  - Add `ref_offset: tuple[int, int] = (0, 0)` for positioning
  - Add `ref_scale: float = 1.0` for scaling
- Reference layer properties:
  - Opacity (adjustable, uses existing layer opacity)
  - Position offset (x, y) — reference can be repositioned
  - Scale factor — reference can be scaled to match canvas
  - Visibility toggle (uses existing layer visibility)
- `flatten_layers()` skips layers where `is_reference == True`
- All export functions (`export.py`, `animated_export.py`) skip reference layers
- Timeline: reference layers shown with a distinct icon/color (e.g., blue tint)
- Serialization: `"is_reference": true` in layer data. Reference image stored as base64 PNG in project file. Backward compatible: defaults to `false` when missing.

**Files:**
- Modify: `src/layer.py` (add `is_reference`, `ref_offset`, `ref_scale` fields; skip in `flatten_layers()`)
- Modify: `src/app.py` (menu item, reference layer rendering with offset/scale)
- Modify: `src/export.py`, `src/animated_export.py` (skip reference layers)
- Modify: `src/project.py` (serialize/deserialize reference layer fields)
- Modify: `src/ui/timeline.py` (reference layer visual indicator)

### 4.6 Undo History Panel

**Purpose:** Visual list of undo states for easy navigation.

**Design:**

- New collapsible panel in right panel area (below palette or as a tab)
- Displays undo stack as a scrollable list: each entry shows action label + relative timestamp
- Current position highlighted with accent color
- Click any entry: jumps to that undo state (applies undos or redos as needed to reach it)
- Implementation requires the undo stack to store labels — audit current `_push_undo()` to ensure labels are captured
- Panel auto-scrolls to keep current position visible
- Stack entries: `{"label": str, "timestamp": float, "state": ...}`
- Max visible entries: 50 most recent (scrollable for more)

**Files:**
- Modify: `src/app.py` (expose undo stack for panel, jump-to-state logic, ensure labels on all push_undo calls)
- Create: `src/ui/undo_panel.py` (undo history panel widget)
- Modify: `src/ui/right_panel.py` (integrate undo panel)

### 4.7 Multi-Document Tabs

**Purpose:** Open multiple projects simultaneously in one window.

**Design:**

- Tab bar widget above the canvas area
- Each tab holds a complete document state:
  - `AnimationTimeline`, `Palette`, `ToolSettingsManager`
  - Undo/redo stacks
  - Project path, dirty flag
  - Canvas zoom/scroll position
- Refactor: extract "document state" from `RetroSpriteApp` into a `Document` class
  - `Document` holds: timeline, palette, tool_settings, undo_stack, redo_stack, project_path, dirty, zoom, scroll
  - `RetroSpriteApp` holds: list of `Document`s, active document index, UI shell
- Switching tabs: save current UI state to active document, load new document's state, re-render
- Shortcuts: `Ctrl+N` new tab (extends existing new project), `Ctrl+W` close tab (prompt save if dirty), `Ctrl+Tab` / `Ctrl+Shift+Tab` cycle tabs (note: `Ctrl+T` is already bound to rotation mode — do not use it here)
- Tab display: shows project filename (or "Untitled") + dirty indicator (*)
- Max tabs: 8 (to prevent resource exhaustion)

**Files:**
- Create: `src/document.py` (Document class extracted from app state)
- Modify: `src/app.py` (refactor to use Document, tab management, tab switching)
- Create: `src/ui/tab_bar.py` (tab bar widget)

---

## Cross-Cutting Concerns

### Testing Strategy

Each feature gets unit tests:
- Tools: test `apply()` output on a `PixelGrid`
- Import/export: round-trip tests with known data
- UI interactions: manual verification (Tkinter testing is fragile)
- Algorithm correctness: pixel-level assertions for scaling algos, coordinate conversions

### Serialization

- **Pre-existing bug:** `Frame.duration_ms` is not currently serialized in `save_project()`. Must be fixed before Plan 2 (AnimPainting) or Plan 4 (Audio Sync) — add `"duration_ms"` to frame data in `save_project()` and read it in `load_project()` (default 100ms for old files). Fix this in Plan 1 or early Plan 2.
- New layer fields (`is_reference`, `ref_offset`, `ref_scale`, `grid_type`) use backward-compatible defaults
- New palette fields (`color_cycles`) default to empty list when missing; `Palette.__init__` must set `self.cycles = []`
- No project version bump unless the format change breaks older readers
- Recovery files use standard `.retro` format + optional metadata

### Dependencies

- **No new required dependencies** for Plans 1-3
- Plan 2 optional: pressure sensitivity may require platform-specific ctypes calls (no pip dependency)
- Plan 4 optional dependencies:
  - `pygame` for audio playback with seeking support (feature hidden if not installed)
  - All other features use existing stack (Python, Tkinter, NumPy, PIL)

### Tool Registration Pattern

Every new tool must follow this checklist:
1. Add class to `src/tools.py` (if it has an `apply()` method)
2. Add entry to `TOOL_DEFAULTS` in `src/tool_settings.py` — key must exactly match the lowercase tool name used in `ToolSettingsManager.save()` calls. Without this, settings are silently dropped.
3. Add icon mapping in `src/ui/icons.py` `TOOL_ICON_MAP`
4. Add to `TOOL_OPTIONS` in `src/ui/options_bar.py`
5. Add keybinding to `DEFAULT_BINDINGS` in `src/keybindings.py` (verify no conflicts)
6. Add event handlers in `src/app.py`

### Feature Flags

Features that add optional dependencies (audio sync, pressure sensitivity) should gracefully degrade:
- Try importing the dependency at module level
- If unavailable, hide the UI entry point entirely
- No error dialogs for missing optional features

---

## Implementation Order

| Phase | Plan | Features | Estimated Tasks |
|-------|------|----------|-----------------|
| 1 | Core Gaps | Custom brushes, tiled preview, text tool, spray tool, crash recovery, palette sort | ~18 tasks |
| 2 | Power Tools | Pressure sensitivity, scale/skew transform, sprite sheet import, right-click tools, tilemap export, AnimPainting | ~18 tasks |
| 3 | Tilemap & Creative | Live tile editing, iso/hex grids, color cycling, ink modes, APNG import | ~15 tasks |
| 4 | Advanced | Animated brushes, 3D mesh, audio sync, scaling algos, reference layers, undo panel, multi-doc tabs | ~21 tasks |

Each plan is independently shippable. Plan 1 should be implemented first as it closes the most critical competitive gaps.
