# Multi-Project Tabs — Design Spec

**Date:** 2026-04-16
**Status:** Approved
**Goal:** Allow multiple projects open simultaneously in tabbed interface, matching Aseprite/Photoshop workflow parity.

---

## Overview

RetroSprite currently supports a single document per session. This spec adds tabbed multi-document support: a custom tab bar, a `ProjectContext` data model to encapsulate per-document state, and a context-switching mechanism that swaps document data while reusing a single set of UI widgets.

---

## Architecture: ProjectContext Extract & Swap

### Approach

Rather than refactoring all mixin `self.*` references (Approach B) or duplicating entire app instances (Approach C), we extract per-document state into a `ProjectContext` object. The app holds a `list[ProjectContext]` and an `_active_project_index`. On tab switch, current state is saved into the outgoing context, incoming context is loaded into `self.*` variables, and UI panels refresh. Mixins continue using `self.timeline`, `self.palette`, etc. unchanged.

### Why This Approach

- Minimal disruption to existing mixin architecture (mixins keep reading `self.*`)
- No mass renaming (`self.timeline` → `self.document.timeline`) across 5 mixins + app.py
- Existing 485+ tests remain valid
- Swap function is the single point of responsibility

---

## 1. ProjectContext Data Model

**New file:** `src/project_context.py`

```python
@dataclass
class ProjectContext:
    # Identity
    project_path: Optional[str]      # .retro file path (None if unsaved)
    name: str                        # Display name for tab
    dirty: bool                      # Unsaved changes flag

    # Core data
    timeline: AnimationTimeline      # Frames, layers, pixel data
    palette: Palette                 # Document palette

    # Undo/Redo
    undo_stack: list                 # Per-document undo history
    redo_stack: list                 # Per-document redo history

    # Canvas view state
    zoom_level: int                  # pixel_size
    scroll_x: float                  # Canvas scroll position
    scroll_y: float

    # Document-bound settings
    grid_settings: dict
    symmetry_mode: str
    symmetry_axis_x: int
    symmetry_axis_y: int

    # Reference image
    reference: Optional[ReferenceImage]

    # Playback state
    playing: bool
    playback_mode: str
    onion_skin: bool
    onion_range: int

    # Export settings
    export_settings: dict

    # Tool settings that are spatial/document-bound
    tool_settings: dict
```

### State Partitioning

**Per-document (in ProjectContext):**
- `timeline`, `palette`, `project_path`, `dirty`
- `undo_stack`, `redo_stack`
- `zoom_level`, `scroll_x`, `scroll_y`
- `grid_settings`, `symmetry_mode`, `symmetry_axis_x`, `symmetry_axis_y`
- `reference` (ReferenceImage)
- `playing`, `playback_mode`, `onion_skin`, `onion_range`
- `export_settings`, `tool_settings`

**Global (stays on app):**
- `current_tool_name`, `_tools` dict, `_tool_size`, `_dither_pattern`, `_ink_mode`, `_fill_mode` — "hand" state
- `_clipboard`, `_paste_origin` — global clipboard for cross-document paste
- All UI widget references (`pixel_canvas`, `toolbar`, `right_panel`, `timeline_panel`, `options_bar`)
- `keybindings`, `_plugins`, `api`

**Transient state (cancelled/cleared on switch, not stored):**
- `_line_start`, `_rect_start`, `_ellipse_start`, `_roundrect_start`
- `_lasso_points`, `_polygon_points`, `_polygon_closing`
- `_selection_pixels`, `_selection_transform`, `_transform_*` fields
- `_rotation_mode`, `_rotation_*` fields
- `_text_mode`, `_text_*` fields
- `_move_start`, `_move_snapshot`, `_hand_last`
- `_pasting`, `_paste_pos` (paste is committed or cancelled)

---

## 2. Tab Bar Widget

**New file:** `src/ui/tab_bar.py`

### Layout

```
┌──────────────────────────────────────────────────────────┐
│ Menubar                                                  │
├──────────────────────────────────────────────────────────┤
│ [● sprite.retro ×] [Untitled ×] [tileset.retro ×]  [+]  │  ← Tab Bar
├──────────────────────────────────────────────────────────┤
│ Options Bar                                              │
│ ... rest of existing UI ...                              │
```

Position: above the options bar, below the menu bar. Always visible (even with one tab).

### Tab Appearance

- Document name (filename or "Untitled", "Untitled 2", etc.)
- Dirty indicator: dot/asterisk before name when unsaved
- Close button (×) on each tab
- Active tab visually distinct (highlight color from theme)
- Long names truncated with ellipsis; full path in tooltip
- Styling: theme colors from `src/ui/theme.py`, font `("Consolas", 9)`

### Tab Interactions

| Action | Behavior |
|--------|----------|
| Click tab | Switch to that document |
| Click × | Close tab (save prompt if dirty) |
| Click [+] | New document (same as File > New) |
| Middle-click tab | Close tab |
| Right-click tab | Context menu: Close, Close Others, Close All, Save, Reveal in Explorer |
| Scroll wheel on bar | Scroll tabs when overflowing |
| Drag tabs | Reorder (stretch goal, not v1) |

### Overflow

When tabs exceed the bar width, scroll arrows appear at the edges. Scroll wheel on the tab bar scrolls horizontally. No tab count limit.

---

## 3. Document Switching Flow

Method: `_switch_project(index)` on the app.

### Steps (switching from Document A → Document B):

1. **Cancel transient modes** — Cancel (discard, not commit) rotation mode, text mode, and selection transform to avoid applying unintended partial work. Clear line/lasso/polygon points. Cancel active paste.
2. **Stop playback** — Stop animation if playing. Cancel all `after()` callbacks related to playback.
3. **Save outgoing state** — Write current zoom, scroll position, and document-bound settings back into Document A's `ProjectContext`.
4. **Swap references** — Bulk-assign Document B's `ProjectContext` fields into `self.*` variables:
   ```
   self.timeline = project_b.timeline
   self.palette = project_b.palette
   self._project_path = project_b.project_path
   self._dirty = project_b.dirty
   self._undo_stack = project_b.undo_stack
   self._redo_stack = project_b.redo_stack
   self._grid_settings = project_b.grid_settings
   ... etc for all ProjectContext fields
   ```
5. **Restore canvas view** — Set `pixel_canvas.pixel_size` to saved zoom, restore scroll position.
6. **Refresh all UI panels:**
   - `pixel_canvas` re-renders with new timeline/frame
   - `right_panel` refreshes palette, layers, animation preview
   - `timeline_panel` rebuilds frame/layer grid
   - `options_bar` updates symmetry indicators
   - Title bar updates with document name
   - Status bar updates dimensions
7. **Emit API event** — `self.api.emit("project_switch", {"index": index})`

### Auto-Save

Applies to the active document only. Timer resets on tab switch.

### Dirty Tracking

`_mark_dirty()` sets `dirty=True` on the active `ProjectContext` and updates the tab's visual indicator.

---

## 4. File Operations Changes

### File > New
- Creates a new `ProjectContext` with fresh `AnimationTimeline` and default `Palette`
- Appends to project list, adds tab labeled "Untitled" (incrementing: "Untitled 2", "Untitled 3")
- Switches to the new tab

### File > Open
- If the file is already open in another tab → switch to that tab (no duplicate)
- Otherwise → create new `ProjectContext`, load data, add tab, switch to it

### File > Save / Save As
- Operates on active document only
- Save As updates tab label to new filename
- Clears dirty flag on active `ProjectContext`

### File > Close (new menu item)
- Closes the active tab
- Prompts to save if dirty
- If last tab is closed → return to startup dialog

### File > Close All (new menu item)
- Closes all tabs, prompting per dirty document (one by one)
- Returns to startup dialog

### Startup Flow
- Unchanged. Startup dialog creates the first `ProjectContext`. Tab bar visible with one tab.

### Duplicate File Detection
- On File > Open, check `project.project_path` across all open `ProjectContext` instances. If match found, switch to existing tab.

---

## 5. Keyboard Shortcuts

### New Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+W` | Close active tab |
| `Ctrl+Shift+W` | Close all tabs |
| `Ctrl+Tab` | Next tab |
| `Ctrl+Shift+Tab` | Previous tab |
| `Ctrl+1` through `Ctrl+9` | Jump to tab by position |

### Unchanged Shortcuts (new behavior)

| Shortcut | New Behavior |
|----------|-------------|
| `Ctrl+N` | Opens new document in new tab (was: replace current) |
| `Ctrl+O` | Opens document in new tab (was: replace current) |
| `Ctrl+S` | Saves active document (unchanged) |
| `Ctrl+Shift+S` | Save As active document (unchanged) |

### Documentation Requirement

All new shortcuts must be added to:
- User-facing keyboard shortcut documentation
- Any in-app help or shortcut reference panels
- `docs/CONTRIBUTING.md` if it lists shortcuts

---

## 6. Palette Behavior

**Per-project with copy option (Option C from brainstorming).**

- Each document has its own `Palette` instance in its `ProjectContext`
- Switching tabs swaps the palette panel contents
- New documents start with the default palette
- Future enhancement: copy/paste palettes between documents, or "start new document with current palette"

---

## 7. Clipboard Behavior

**Global clipboard (Option A from brainstorming).**

- `_clipboard` and `_paste_origin` remain on the app, not in `ProjectContext`
- Copy pixels in Document A → switch to Document B → paste works
- Enables core cross-document workflow (copying sprites/elements between sheets)

---

## 8. API & Plugin Impact

### New API Event

- `project_switch` — emitted on active document change, payload: `{"index": int}`

### Dynamic API Properties

`RetroSpriteAPI` properties `timeline` and `palette` become `@property` decorators that read from `self.app.timeline` and `self.app.palette` dynamically. This ensures plugins always access the active document's data without caching stale references.

```python
class RetroSpriteAPI:
    @property
    def timeline(self):
        return self.app.timeline

    @property
    def palette(self):
        return self.app.palette
```

---

## 9. Testing Strategy

### New Test Files

| Test File | Covers |
|-----------|--------|
| `tests/test_project_context.py` | ProjectContext creation, state save/restore round-trips |
| `tests/test_tab_bar.py` | Tab widget: add, remove, click, overflow, dirty indicator, context menu |
| `tests/test_multi_project.py` | Switch flow: state isolation, transient mode cancellation, undo/redo independence, clipboard sharing |

### Key Test Scenarios

- Open two documents, draw in A, switch to B, switch back — A's pixels unchanged
- Undo stack is independent per document
- Copy in A, paste in B works (global clipboard)
- Close dirty document triggers save prompt
- Opening an already-open file switches to its tab (no duplicate)
- Symmetry axes are per-document and restored on switch
- Rotation/selection/text mode cancelled on switch without corruption
- Closing last tab returns to startup dialog
- `api.timeline` returns active document's timeline after switch
- `project_switch` event fires with correct index

### Existing Tests

485+ existing tests should not break. The initial document created in `__init__` is wrapped in a `ProjectContext`, but `self.timeline`, `self.palette`, etc. continue to work identically for single-document usage.

---

## 10. New Files Summary

| File | Purpose |
|------|---------|
| `src/project_context.py` | `ProjectContext` dataclass |
| `src/ui/tab_bar.py` | `TabBar` custom widget |
| `tests/test_project_context.py` | ProjectContext unit tests |
| `tests/test_tab_bar.py` | TabBar widget tests |
| `tests/test_multi_project.py` | Integration tests for multi-document switching |

## 11. Modified Files Summary

| File | Changes |
|------|---------|
| `src/app.py` | Add `_projects` list, `_active_project_index`, `_switch_project()`, `_save_to_context()`, `_load_from_context()`. Modify `__init__` to wrap initial state in ProjectContext. Add tab bar to `_build_ui()`. |
| `src/file_ops.py` | Modify `_new_project()`, `_open_project()` to create new tabs. Add `_close_project()`, `_close_all_projects()`. Modify save to update tab label/dirty. |
| `src/scripting.py` | Make `timeline` and `palette` into `@property`. Add `project_switch` event. |
| `src/ui/theme.py` | Add tab bar color constants (active, inactive, hover, close button). |
| Keyboard shortcut config | Register `Ctrl+W`, `Ctrl+Shift+W`, `Ctrl+Tab`, `Ctrl+Shift+Tab`, `Ctrl+1-9`. |
| User documentation | Document new shortcuts and tab behavior. |

---

## Out of Scope (Future Work)

- Drag-and-drop tab reordering
- Layer/frame transfer between documents (pixel clipboard covers core workflow)
- Session restoration (reopen last session's tabs)
- Copy/paste palette between documents (architecture supports it, UI not in v1)
- Multiple views of the same document
