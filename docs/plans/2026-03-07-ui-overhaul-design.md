# RetroSprite UI Overhaul & Animation Timeline — Design Document

**Date:** 2026-03-07
**Scope:** Full cyberpunk UI overhaul + bottom Layer x Frame grid timeline + top options bar

---

## 1. Layout Architecture

Transform from 3-column (toolbar | canvas | right panel) to professional 4-zone layout:

```
+--------------------------------------------------------------------------+
| Menu Bar                                                                  |
+--------------------------------------------------------------------------+
| Top Options Bar (context-sensitive: tool name, size, sym, dither, etc.)   |
+------+---------------------------------------------------+---------------+
|      |                                                   |               |
| Tool |                                                   | Right Panel   |
| bar  |                Canvas                             | - Palette     |
| (48px|                                                   | - Color Picker|
| icons|                                                   | - Preview     |
| only)|                                                   | - Compression |
|      |                                                   |               |
+------+--------------------------+------------------------+---------------+
| drag handle (resizable)         |                                        |
+------------+--------------------+----------------------------------------+
|            | Tag bars | Frame#s + per-frame duration (ms)                |
| Layer      +-------------------------------------------------------------+
| sidebar    | Cel Grid (layer rows x frame columns)                       |
| (name,     | Playhead = glowing cyan column on current frame              |
|  lock,     |                                                              |
|  eye)      |                                                              |
+------------+-------------------------------------------------------------+
| [<<][>>][>][stop] Mode:[fwd] | Onion:[ON] Range:[2] | +Frame | +Layer   |
+-------------------------------------------------------------------------- +
```

## 2. Bottom Timeline Panel (src/ui/timeline.py — NEW)

### Tag Strip
- Colored neon bars above frame numbers, one per tag spanning its frame range
- Double-click to edit tag, right-click to delete
- Colors use ACCENT_CYAN, ACCENT_MAGENTA, ACCENT_PURPLE, SUCCESS, WARNING

### Frame Header Row
- Frame numbers + per-frame duration in ms
- Double-click duration to edit inline
- Current frame number glows cyan

### Layer Sidebar (left of grid)
- Layer name + lock toggle + visibility toggle per row
- Double-click name to rename
- Right-click context menu: delete, duplicate, merge down

### Cel Grid
- Each cell = one layer's content in one frame
- States: filled (colored dot or mini thumbnail), empty (dark), linked (future)
- Click to select frame + layer simultaneously
- Current cel: cyan border
- Current frame column: soft cyan glow (playhead)

### Transport Bar (bottom of timeline)
- Play/stop/step-forward/step-back buttons
- Playback mode dropdown (forward/reverse/pingpong)
- Onion skin toggle + range spinbox
- +Frame and +Layer buttons

### Resizing
- Drag handle at top edge of timeline panel
- Default height: fits all layers + controls comfortably (~150-180px)

### Per-Frame Timing
- Each Frame gets a `duration_ms` attribute (default 100)
- Playback reads per-frame duration instead of global delay
- GIF export uses per-frame durations

### Layer Locking
- Layer model already has `locked` field — wire to UI toggle
- When locked: drawing tools skip that layer, show lock indicator on cursor

### Frame Reordering
- Drag frame columns left/right to reorder
- Uses existing AnimationTimeline.move_frame()

## 3. Top Options Bar (src/ui/options_bar.py — NEW)

Horizontal bar between menu and canvas. BG_PANEL background with bottom border gradient (cyan to purple).

### Contents
- Tool indicator: current tool name + 12x12 pixelated icon
- Context-sensitive controls per active tool:

| Tool              | Controls Shown                              |
|-------------------|---------------------------------------------|
| Pen, Eraser, Blur | Size, Symmetry, Dither, Pixel Perfect       |
| Fill              | Tolerance, Dither                           |
| Line, Rect, Ellipse | Size (stroke width), Symmetry            |
| Magic Wand        | Tolerance                                   |
| Pick, Hand, Select | Tool name only                             |

### Removed from Toolbar
Brush size section, symmetry section, dither section, pixel perfect section, wand tolerance section all move here.

## 4. Toolbar Redesign (src/ui/toolbar.py — REWRITE)

- Narrow vertical strip (~48px wide) of icon-only buttons
- Each button: 32x32 pixelated icon from Phosphor icon pipeline
- Active tool: neon glow halo (soft cyan shadow) + bright cyan tint
- Inactive: muted icon on dark background, subtle hover glow
- Tooltip on hover: tool name + shortcut key

### Icon Mapping (Phosphor icons)
- Pen -> pen
- Eraser -> eraser
- Blur -> drop
- Fill -> paint-bucket
- Ellipse -> circle
- Pick -> eyedropper
- Select -> selection
- Wand -> magic-wand
- Line -> line-segment
- Rect -> rectangle
- Hand -> hand

## 5. Icon Pipeline (src/ui/icons.py — NEW)

1. Load Phosphor PNG from icons/ directory
2. Resize to 16x16 with LANCZOS
3. Threshold to binary (line vs background)
4. Colorize: lines -> ACCENT_CYAN, background -> transparent
5. Optional secondary color (ACCENT_PURPLE) for fill areas
6. Scale up to 32x32 with NEAREST for crisp pixel look
7. Cache as PhotoImage

Active glow variant: generate second version with 1-2px soft cyan bloom around icon edges.

## 6. Right Panel Redesign (src/ui/right_panel.py — REWRITE)

### Removed
LayerPanel, FramePanel (moved to timeline)

### Collapsible Sections
Each section has:
- Header bar with section name + collapse/expand chevron
- Left-edge gradient accent line (2px, cyan to purple)

### Palette Panel
- Color grid with better spacing
- Current color swatch with neon border glow
- Recent colors row (last 10 picked colors) below swatch

### Color Picker Panel
- HSV gradient canvas (bug-fixed: no palette flooding on drag)
- Value slider
- Alpha slider (NEW: 0-255)
- Hex entry with preview swatch (checkerboard behind for transparency)
- "+ Palette" button

### Animation Preview
- Dynamic sizing: scales to fit panel width (no more fixed 80x80)
- Neon glow border when animation is playing

### Compression Panel
- Same stats display, themed consistently

## 7. Cyberpunk Visual Effects (src/ui/effects.py — NEW)

### Glow System
- `create_glow(image, color, radius)` — Adds soft colored bloom around non-transparent pixels
- `gradient_border(canvas, x1, y1, x2, y2, color1, color2)` — Gradient line between two neon colors

### Specific Effects
- Active tool glow: soft cyan halo behind selected tool icon
- Playhead pulse: current frame column pulses subtly during playback
- Hover states: buttons brighten with color shift toward cyan
- Panel border gradients: cyan to purple gradient lines as separators
- Status bar scanlines: subtle CRT-style horizontal line texture
- Section header underline: thin glowing line in accent color
- Active color swatch glow: current color preview emits glow of its own color
- Selection highlight: neon border rather than solid fill for selected items

### Color Usage Expansion
- ACCENT_CYAN (#00f0ff) — Primary: active states, playhead, selection, headers
- ACCENT_MAGENTA (#ff00aa) — Secondary: hover accents, alternate tags, destructive actions
- ACCENT_PURPLE (#8b5cf6) — Tertiary: gradient endpoints, linked cels
- SUCCESS (#00ff88) — Onion skin future frames, save confirmations
- WARNING (#ffaa00) — Locked layer indicators, unsaved changes

## 8. Multi-Frame Onion Skinning Enhancement

- Range control: configurable frames before/after (1-5)
- Color tinting: past frames magenta/red, future frames cyan/green
- Per-direction opacity: past frames fade more than future
- Toggle in timeline transport bar: quick on/off + range spinner

## 9. Dialog Redesign (src/ui/dialogs.py — UPDATE)

- Startup dialog: neon cyan title with glow, purple subtitle, neon-bordered size buttons
- All dialogs: BG_DEEP background, neon-accented buttons, gradient separators
- Replace simpledialog calls (tag creation etc.) with custom themed dialogs

## 10. Bug Fixes Bundled In

1. Color picker drag flooding — only add to palette on explicit "+ Palette" click
2. Preview clipping — dynamic sizing instead of fixed 80x80
3. Panel double-construction — clean initialization, no destroy-rebuild
4. Unused theme constants — all five unused colors get purposeful roles
5. style_canvas dead branch — fix identical if/else
6. Onion skin auto-enable — remove surprise auto-enable on frame add

## 11. File Structure

```
src/ui/
  timeline.py      — NEW: Bottom Layer x Frame grid timeline panel
  options_bar.py   — NEW: Top context-sensitive tool options bar
  icons.py         — NEW: Phosphor -> pixel icon pipeline + glow generation
  effects.py       — NEW: Neon glow, gradient borders, scanline effects
  toolbar.py       — REWRITE: Icon-only vertical strip
  right_panel.py   — REWRITE: Collapsible sections, no layers/frames
  theme.py         — UPDATE: Use all accent colors, add effect helpers
  dialogs.py       — UPDATE: Cyberpunk-themed custom dialogs
src/
  animation.py     — UPDATE: Per-frame duration, enhanced onion skinning
  canvas.py        — UPDATE: Multi-frame onion skin rendering
  app.py           — UPDATE: New layout assembly, wire new components
icons/             — NEW: Phosphor icon source PNGs
```

## 12. Out of Scope (YAGNI)

- Linked cels
- Layer groups/folders
- Custom brushes
- Tiled/seamless mode
- Scripting API
- Indexed color mode
- Dockable/rearrangeable panels
