# Toolbar, Icon & Tiling Fixes — Design Spec

**Date:** 2026-03-13
**Scope:** 3 independent improvements — scrollable toolbar, lasso icon, tiled mode panning fix

---

## 1. Scrollable Toolbar

### Problem
When the application window is resized smaller (or screen resolution is limited), toolbar buttons at the bottom get clipped with no way to access them.

### Solution
Wrap toolbar buttons in a Tkinter `Canvas` widget with an inner `Frame`, enabling mousewheel scrolling when content overflows.

### Design

**Structure change in `src/ui/toolbar.py`:**
- Current: `Toolbar(tk.Frame)` → buttons packed directly via `btn.pack()`
- New: `Toolbar(tk.Frame)` → contains a `tk.Canvas` → contains an inner `tk.Frame` → buttons packed into inner frame
- The Canvas acts as the scroll viewport; the inner frame holds all buttons

**Scroll behavior:**
- Bind `<MouseWheel>` on the canvas to scroll vertically
- No visible scrollbar — scroll is mousewheel-only
- Scroll region updates dynamically via `<Configure>` event on the inner frame
- When all buttons fit, scrolling has no effect (natural behavior)

**Important details:**
- `add_plugin_tools()` must also pack its separator and buttons into the inner scrollable frame (not `self`)
- The Canvas must be packed with `fill="both", expand=True` inside the `pack_propagate(False)` frame
- Platform note: Linux uses `<Button-4>`/`<Button-5>` for mousewheel; current target is Windows so `<MouseWheel>` suffices

**Files modified:** `src/ui/toolbar.py`

---

## 2. Lasso Tool Icon

### Problem
The lasso tool maps to `lasso-bold.svg` in `TOOL_ICON_MAP`, but no such file exists in `icons/`. The tool currently falls back to a letter "L" icon.

### Solution
Download the Phosphor Icons `lasso-bold.svg` and place it in the `icons/` directory. The existing icon pipeline will pick it up automatically — no code changes needed beyond adding the file.

**Files added:** `icons/lasso-bold.svg`

---

## 3. Tiled Mode Panning Fix

### Problem
When tiled mode is active (`x`, `y`, or `both`), `canvas.py` renders a 3x3 grid of the sprite (center = original, surrounding 8 = dimmed copies). However, `_update_scrollregion()` always sets the scroll region to the original sprite size. Combined with Tkinter's default `confine=True`, this prevents panning to see the surrounding tile copies.

### Root Cause
`_update_scrollregion()` in `src/canvas.py` (line ~148):
```python
def _update_scrollregion(self):
    w = self.grid.width * self.pixel_size
    h = self.grid.height * self.pixel_size
    self.config(scrollregion=(0, 0, w, h))
```
This doesn't account for the 3x tiled image size.

### Solution
Make `_update_scrollregion()` aware of the current tiled mode. When tiling is active, expand the scroll region to cover the full 3x3 (or 3x1 / 1x3) rendered image.

**Scroll region sizing:**
The rendering code (`build_render_image`) always produces a 3×3 grid regardless of whether the mode is `x`, `y`, or `both`. Therefore the scroll region must always be `3w × 3h` when tiling is active:

| Tiled Mode | Width | Height |
|------------|-------|--------|
| `off` | `w` | `h` |
| `x` / `y` / `both` | `3 * w` | `3 * h` |

Where `w = grid.width * pixel_size` and `h = grid.height * pixel_size`.

**Implementation:**
- Add a `_tiled_mode` attribute to `PixelCanvas` (default `"off"`) with a `set_tiled_mode(mode)` method
- `set_tiled_mode()` stores the mode, calls `_update_scrollregion()`, and centers the viewport on the middle tile
- Update `_update_scrollregion()` to use 3× multiplier when `_tiled_mode != "off"`
- Call `set_tiled_mode()` from `app.py`'s `_on_tiled_mode_change`
- Keep `confine=True` so panning stays bounded to the padded region

**Viewport centering after mode change:**
When tiled mode activates, the viewport must scroll to center on the middle tile (the real sprite). Call `xview_moveto(1/3)` and `yview_moveto(1/3)` after expanding the scroll region. When tiled mode is disabled, reset to normal scroll position.

**Zoom fix (`zoom_at`):**
`zoom_at()` computes scroll fractions using `self.grid.width * new_size`. In tiled mode the scrollable area is 3× that. The denominator must use the actual scroll region width/height (i.e., multiply by 3 when tiled mode is active) to prevent viewport jumps during zoom.

**Industry precedent:** Aseprite and Pixelorama both keep the viewport focused on the original tile with surrounding copies as visual aids. This fix matches that pattern — you can see the neighbors but can't scroll infinitely.

**Files modified:** `src/canvas.py`, `src/app.py`

---

## Testing

- **Scrollable toolbar:** Manual test — resize window vertically until buttons clip, verify mousewheel scrolls to reveal them
- **Lasso icon:** Visual verification — lasso tool shows Phosphor icon instead of letter fallback
- **Tiled panning:** Manual test — enable tiling (X/Y/Both), verify Hand tool and scroll can reach neighboring tile copies

---

## Summary of Changes

| Change | Files | Type |
|--------|-------|------|
| Scrollable toolbar | `src/ui/toolbar.py` | UI enhancement |
| Lasso icon | `icons/lasso-bold.svg` | Asset addition |
| Tiled scroll fix | `src/canvas.py`, `src/app.py` | Bug fix |
