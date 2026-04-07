# RetroSprite Full Overhaul Design

**Date:** 2026-03-02
**Scope:** Performance backend + new features + visual redesign
**Approach:** Bottom-up rebuild (foundation → tools → animation → QoL → visuals)

---

## Phase 1: Foundation

### 1A. NumPy PixelGrid Migration

Replace `list[list[tuple]]` with `numpy.ndarray` shape `(H, W, 4)` dtype `uint8`.

**Changes to `pixel_data.py`:**
- `_pixels` becomes `np.zeros((height, width, 4), dtype=np.uint8)`
- `to_pil_image()` → `Image.fromarray(self._pixels, 'RGBA')`
- `from_pil_image()` → `np.array(img, dtype=np.uint8)`
- `copy()` → `self._pixels.copy()` (C-level memcpy)
- `clear()` → `self._pixels[:] = 0`
- `get_pixel/set_pixel` — index into ndarray, return/accept tuples for API compat
- `extract_region` / `paste_region` — NumPy slicing

**Impact:** 256x256 frame: ~6.5MB → ~256KB. All operations 10-100x faster.

### 1B. Layer System

**New file: `src/layer.py`**

```
Layer:
  name: str
  pixels: PixelGrid
  visible: bool = True
  opacity: float = 1.0
  blend_mode: str = "normal"  # normal, multiply, screen, overlay
  locked: bool = False
```

**Modified: `src/animation.py`**

Each frame becomes a list of layers instead of a single PixelGrid. The `AnimationTimeline` manages frames, each frame has layers.

```
Frame:
  layers: list[Layer]
  active_layer_index: int = 0

AnimationTimeline:
  _frames: list[Frame]
```

**Compositing:** Flatten layers bottom-to-top with alpha composite + blend modes. Render pipeline: flatten → onion skin → scale → grid overlay.

**UI: Layer Panel** in right sidebar:
- Layer list with visibility toggle (eye icon), selection highlight
- Add / Delete / Duplicate / Merge Down buttons
- Opacity slider for selected layer
- Blend mode dropdown
- Drag to reorder (or up/down buttons)

### 1C. Delta-Based Undo (50+ levels)

```
UndoEntry:
  frame_index: int
  layer_index: int
  changed_coords: np.ndarray  # (N, 2) int16
  old_values: np.ndarray      # (N, 4) uint8
```

- Before operation: snapshot the affected layer region
- After operation: compute diff via `np.any(before != after, axis=2)`
- Store only changed pixel coords + old values
- Undo: restore old values at coords. Redo: store new values similarly.
- Limit: 50 states (configurable)

### 1D. Render Pipeline Optimization

1. **Reuse canvas image:** Store `_image_id`, use `itemconfig()` instead of `delete()`/`create_image()`
2. **Cache grid overlay:** Build once per zoom level, composite on each render
3. **Vectorize onion skin:** `np.where(alpha > 0, ...)` instead of per-pixel Python loop
4. **Generation counter:** `PixelGrid._generation` increments on any change; skip render if unchanged

---

## Phase 2: New Drawing Tools

### 2A. Ellipse Tool (`src/tools.py`)
- Midpoint ellipse algorithm
- Filled/unfilled mode
- Preview during drag (dashed ellipse outline on canvas)
- Shortcut: `O`

### 2B. Symmetry/Mirror Drawing
- Modes: Off, Horizontal, Vertical, Both
- Any draw operation is mirrored relative to canvas center
- Visual center line indicator when active
- Toggle: `M` key or toolbar button
- State stored in `app.py`, applied in draw dispatch

### 2C. Magic Wand Selection
- BFS-based like FillTool but builds selection set instead of painting
- Tolerance parameter (0-255): include pixels within color distance
- Shift+click adds to selection
- Returns set of (x, y) coords → highlight on canvas
- Shortcut: `W`

### 2D. Pixel-Perfect Freehand
- Tracks last 3 drawn points
- If they form an L-shape (90° turn), removes the corner pixel
- Only active for Pen tool at size=1
- Toggle in toolbar options area

### 2E. Dithering Brushes
- 4 patterns: Checkerboard, 25%, 50%, 75%
- Each pattern is a 2x2 or 4x4 bitmask
- Pen tool checks `(x + y) % pattern` before drawing
- Pattern selector in toolbar
- Shortcut: `D` to cycle

### 2F. Shading Ink
- Find closest palette color to target pixel
- Lighten: move one index toward lighter colors in palette
- Darken: move one index toward darker colors
- Palette sorted by luminance for shading order
- Shortcuts: `[` darken, `]` lighten

### 2G. Gradient Fill
- Click-drag defines direction vector
- Fill area (selection or canvas) with gradient between primary and secondary color
- Uses ordered dithering (Bayer 4x4 matrix) for pixel-art-appropriate result
- Accessible via Image menu → "Gradient Fill"

---

## Phase 3: Animation Enhancements

### 3A. Frame Tags
- `Tag(name: str, color: str, start_frame: int, end_frame: int)`
- Stored in `AnimationTimeline.tags: list[Tag]`
- UI: colored bars above frame list, right-click to add/edit/delete
- Export by tag (GIF, sprite sheet)

### 3B. Playback Modes
- Enum: Forward, Reverse, PingPong
- PingPong: plays forward to end, then backward to start, repeat
- Selector in animation controls (dropdown or cycle button)

### 3C. Threaded GIF Export
- `threading.Thread(target=export_worker, daemon=True)`
- Progress updates via `root.after(0, callback)`
- Status bar shows "Exporting GIF... (frame X/N)"
- UI remains interactive during export

---

## Phase 4: Quality of Life

### 4A. Sprite Sheet Export
- Export all frames as single PNG (horizontal strip or NxM grid)
- JSON sidecar file with frame metadata:
  ```json
  {
    "frames": [{"x": 0, "y": 0, "w": 32, "h": 32, "duration": 100}],
    "tags": [{"name": "idle", "from": 0, "to": 3}],
    "size": {"w": 32, "h": 32},
    "scale": 1
  }
  ```
- Scale options: 1x, 2x, 4x, 8x
- Dialog with preview

### 4B. Auto-Save
- Timer: every 60 seconds, if project modified since last save
- Save to `~/.retrosprite/autosave/{project_hash}.retro`
- On startup: check for recovery files, prompt to restore
- Status bar flash: "Auto-saved" for 2 seconds
- Dirty flag tracking (set on any pixel/frame change, clear on save)

### 4C. Customizable Keyboard Shortcuts
- `~/.retrosprite/keybindings.json` mapping action names to key combos
- Default keybindings as fallback
- Settings dialog accessible via Edit menu → "Keyboard Shortcuts..."
- Hot-reload on save

### 4D. Reference Image Overlay
- Import via File menu → "Load Reference Image..."
- Rendered as semi-transparent layer above canvas background, below pixel content
- Adjustable opacity (slider in a floating panel or right panel section)
- Reposition with drag when reference tool active
- Scale: fit-to-canvas or 1:1
- Toggle: `Ctrl+R`
- Not saved in project file, not exported

---

## Phase 5: Neon Retro Visual Theme

### Color System
```
BG_DEEP       = "#0d0d12"   # Main background
BG_PANEL      = "#14141f"   # Panel backgrounds
BG_PANEL_ALT  = "#1a1a2e"   # Alternate/button backgrounds
BORDER        = "#1e1e3a"   # Panel borders (purple tint)
TEXT_PRIMARY   = "#e0e0e8"   # Main text
TEXT_SECONDARY = "#7a7a9a"   # Labels, hints
ACCENT_CYAN   = "#00f0ff"   # Selections, active elements, primary accent
ACCENT_MAGENTA= "#ff00aa"   # Tools, highlights, secondary accent
ACCENT_PURPLE = "#8b5cf6"   # Tertiary accent
SUCCESS       = "#00ff88"   # Success states
WARNING       = "#ffaa00"   # Warnings
BUTTON_BG     = "#1a1a2e"   # Button normal
BUTTON_HOVER  = "#252545"   # Button hover
BUTTON_ACTIVE = "#0d0d12"   # Button pressed (with cyan border)
```

### Component Styling
- **Toolbar:** Compact buttons with Unicode tool symbols, grouped by category (draw/select/navigate) with separators. Active tool: cyan bg + white text.
- **Right panel sections:** Header text with colored accent underline. Collapsible sections.
- **Palette grid:** Rounded-feel swatches with subtle borders. Selected color: cyan border glow.
- **Layer panel:** Eye icon toggles, opacity indicator, active layer cyan left-border.
- **Frame list:** Current frame cyan highlight, frame tags as colored dots.
- **Status bar:** Dark gradient feel, cyan accent for key info (tool, zoom).
- **Scrollbars:** Custom dark theme (troughcolor #14141f, slider #252545).
- **Menu bar:** Dark bg, hover highlight with accent.
- **Startup dialog:** Centered logo area, neon-bordered size cards, accent "Open" button.
- **Dialogs:** Consistent dark theme with accent buttons.

### Tkinter Implementation Notes
- Use `highlightbackground`/`highlightcolor` for glow borders
- Custom `ttk.Style` theme for consistent widget appearance
- Unicode symbols for tool icons: ✏ ◯ ▭ ◇ ▲ ✂ ↔ ✋ 🔍
- `relief="flat"` on all buttons, color changes for states
- Canvas backgrounds match panel theme
