# Batch 3: Drawing Modes — Tiled Mode, Ink Modes, Color Ramps

**Date:** 2026-03-11

## 1. Tiled/Seamless Drawing Mode

### Behavior
- Toggle via View menu: Tiled Off / Tiled X / Tiled Y / Tiled Both
- **Visual preview:** Canvas renders the tile repeated (3x3 grid — center is the actual canvas, 8 surrounding copies show how it tiles)
- **Wrap drawing:** Pen/eraser strokes that go past an edge continue on the opposite side
- Affects: Pen, Eraser, Fill, Line tools

### Implementation
- State: `self._tiled_mode` — "off", "x", "y", "both"
- Render: In `build_render_image()`, after compositing the main image, tile it 3x3 around the center for the preview. Only the center tile is the actual editable canvas.
- Drawing: In tool apply calls, when position is outside canvas bounds, wrap coordinates: `x % width`, `y % height` (respecting axis mode)
- Fill tool: flood fill must also consider wrapped neighbors

### UI
- View menu: "Tiled Mode" submenu with Off/X/Y/Both radio items
- Status bar shows tiled mode indicator

## 2. Ink Modes (Alpha Lock, Behind)

### Modes
- **Normal** (default) — paint anywhere
- **Alpha Lock** — only modify pixels that already have alpha > 0. Transparent pixels are untouched.
- **Behind** — only paint on fully transparent pixels (alpha == 0). Existing content preserved.

### Implementation
- State: `self._ink_mode` — "normal", "alpha_lock", "behind"
- Applied at draw time: before `set_pixel`, check current pixel alpha
  - Alpha Lock: skip if current alpha == 0
  - Behind: skip if current alpha > 0
- Affects: Pen and Eraser tools only
- Add ink mode check in `_on_canvas_click` and `_on_canvas_drag` pen/eraser code paths

### UI
- Options bar: Add ink mode cycle button for pen/eraser tools
- Shows current mode: "Ink: Normal" / "Ink: αLock" / "Ink: Behind"

## 3. Color Ramp Generator

### Dialog
- Opens via palette right-click or Edit menu → "Generate Color Ramp..."
- Controls:
  - Start color (color picker or current foreground)
  - End color (color picker or current background)
  - Number of steps (2-32, spinner)
  - Interpolation mode: RGB or HSV radio buttons
- Preview strip showing the generated ramp
- "Add to Palette" button — appends colors to current palette

### Implementation
- `src/palette.py`: Add `generate_ramp(color1, color2, steps, mode)` function
- RGB interpolation: linear lerp per channel
- HSV interpolation: convert to HSV, lerp H/S/V, convert back. Use shortest hue path.
- Dialog in `src/ui/dialogs.py`

## Out of Scope
- Tiled mode for selection/transform operations
- Custom ink modes beyond Normal/Alpha Lock/Behind
- Color ramp from multiple control points (just 2-point for now)
