# Startup Dialog Redesign — Design Spec

**Date:** 2026-04-03
**Scope:** Remove intro video, redesign custom canvas size dialog, add recent projects section

---

## 1. Startup Dialog Changes

### Removed
- `INTRO_VIDEO_URL` constant and all video/embed/fallback logic
- `webbrowser` import (only used for video)
- `tkinterweb` optional import (only used for video embed)

### New Layout (top to bottom)
1. Glow title ("RetroSprite") + "Pixel Art Creator" subtitle
2. Feature Guide button
3. Gradient separator
4. **New Canvas** — preset buttons (16x16, 32x32, 64x64, 128x128) + "Custom Size..." button
5. Gradient separator
6. **Open Project** — "Open .retro Project..." browse button
7. Gradient separator
8. **Recent Projects** — up to 5 entries, or "No recent projects" placeholder

Dialog height reduced from 620px to ~520px (video section removed).

---

## 2. Recent Projects

### Storage
File: `~/.retrosprite/recents.json`

```json
[
  {"path": "C:/Users/vasil/art/character.retro", "timestamp": 1743638400},
  {"path": "C:/Users/vasil/art/tileset.retro", "timestamp": 1743552000}
]
```

- Sorted by timestamp descending (newest first)
- Capped at 5 entries
- On load/save of any `.retro` file, the list is updated (add or bump to top)
- On startup, entries whose files no longer exist on disk are filtered out

### Display
- Section header "Recent Projects" in accent color
- Each entry is a clickable button showing filename (e.g. `character.retro`) with the full directory path as smaller secondary text below
- Single click loads immediately (closes startup dialog)
- If no recents exist (or all files have been deleted), show "No recent projects" in `TEXT_SECONDARY`

### Module: `src/recents.py`
Two functions:
- `load_recents() -> list[dict]` — read file, filter dead paths, return up to 5
- `update_recents(path: str)` — add/bump path to top, cap at 5, write file

Storage logic stays out of dialog UI and out of mixins. `file_ops.py` calls `update_recents()` when saving or opening projects.

---

## 3. Custom Canvas Size Dialog

### Behavior
Clicking "Custom Size..." opens a new `Toplevel` window **without closing** the startup dialog. The startup dialog remains visible but blocked (`transient` + `grab_set` makes the custom dialog modal relative to startup).

### Layout (~300x320px)
1. Gradient top bar
2. Title: "Custom Canvas Size" in `ACCENT_CYAN`
3. Width field — label + themed entry, default value 64
4. Height field — label + themed entry, default value 64
5. Aspect ratio presets — row of small buttons:
   - `1:1` — sets height equal to width
   - `4:3` — e.g. 64x48
   - `3:4` — e.g. 48x64
   - `16:9` — e.g. 64x36
   - `9:16` — e.g. 36x64
   - Presets adjust height based on current width value
6. "Create" button (`ACCENT_CYAN`) — validates, sets result, closes custom dialog then startup dialog
7. "Cancel" button (`BUTTON_BG`) — closes only the custom dialog, returns to startup
8. Gradient bottom bar

### Validation
- Width and height must be integers, >= 1, <= 2048
- Invalid input shows an inline error label in `WARNING` color (no messagebox)

### Replaces
The current `simpledialog.askinteger` approach in both `ask_startup._custom_new()` and `ask_canvas_size._custom()`.

---

## 4. File Changes

| File | Change |
|------|--------|
| `src/recents.py` | **New** — `load_recents()`, `update_recents(path)` |
| `src/ui/dialogs.py` | Remove video code, add recents section to `ask_startup`, new `ask_custom_canvas_size()` function, update `ask_canvas_size` to use new custom dialog too |
| `src/file_ops.py` | Call `update_recents(path)` in save/open project methods |
| `tests/test_recents.py` | **New** — test load/save/cap/dead-path-filtering |

No changes to `app.py`. No new mixin methods. No new dependencies.
