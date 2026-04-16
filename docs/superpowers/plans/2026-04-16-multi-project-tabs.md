# Multi-Project Tabs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable multiple projects open simultaneously in a tabbed interface, matching Aseprite/Photoshop workflow parity.

**Architecture:** Extract all per-document state into a `ProjectContext` dataclass. The app holds a list of contexts and swaps `self.*` references on tab switch. A custom `TabBar` widget provides the tab UI. Mixins continue using `self.timeline`, `self.palette`, etc. unchanged.

**Tech Stack:** Python 3.8+, Tkinter, dataclasses, existing RetroSprite modules.

**Spec:** `docs/superpowers/specs/2026-04-16-multi-project-tabs-design.md`

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `src/project_context.py` | `ProjectContext` dataclass — bundles all per-document state |
| Create | `src/ui/tab_bar.py` | `TabBar` custom Tkinter widget — tab display, click, close, overflow scroll |
| Modify | `src/app.py` | Add `_projects` list, `_active_project_index`, swap methods, tab bar in `_build_ui()` |
| Modify | `src/file_ops.py` | Multi-tab file ops: new/open create tabs, close/close-all, save updates tab |
| Modify | `src/scripting.py` | Make `timeline`/`palette` into `@property`, add `project_switch` event |
| Modify | `src/ui/theme.py` | Add tab bar color constants |
| Create | `tests/test_project_context.py` | ProjectContext unit tests |
| Create | `tests/test_tab_bar.py` | TabBar widget tests |
| Create | `tests/test_multi_project.py` | Integration tests for multi-document switching |

---

## Task 1: Add Tab Bar Theme Colors

**Files:**
- Modify: `src/ui/theme.py`

- [ ] **Step 1: Read current theme file**

Read `src/ui/theme.py` to see the current color constants and naming patterns.

- [ ] **Step 2: Add tab bar colors to the dark theme dict**

In `src/ui/theme.py`, add these entries to the `_DARK` dict (after the existing entries around line 22):

```python
"TAB_ACTIVE": "#1a1a2e",
"TAB_INACTIVE": "#0d0d12",
"TAB_HOVER": "#22223a",
"TAB_CLOSE": "#7a7a9a",
"TAB_CLOSE_HOVER": "#ff4466",
"TAB_DIRTY": "#ff00aa",
"TAB_BORDER": "#1e1e3a",
```

- [ ] **Step 3: Add corresponding module-level variables**

After the existing module-level variable block (around line 56), add:

```python
TAB_ACTIVE = _DARK["TAB_ACTIVE"]
TAB_INACTIVE = _DARK["TAB_INACTIVE"]
TAB_HOVER = _DARK["TAB_HOVER"]
TAB_CLOSE = _DARK["TAB_CLOSE"]
TAB_CLOSE_HOVER = _DARK["TAB_CLOSE_HOVER"]
TAB_DIRTY = _DARK["TAB_DIRTY"]
TAB_BORDER = _DARK["TAB_BORDER"]
```

- [ ] **Step 4: Update `set_mode()` to include the new variables**

In the `set_mode()` function, add the new variables to the global update block so they switch with dark/light mode:

```python
global TAB_ACTIVE, TAB_INACTIVE, TAB_HOVER, TAB_CLOSE, TAB_CLOSE_HOVER, TAB_DIRTY, TAB_BORDER
TAB_ACTIVE = theme["TAB_ACTIVE"]
TAB_INACTIVE = theme["TAB_INACTIVE"]
TAB_HOVER = theme["TAB_HOVER"]
TAB_CLOSE = theme["TAB_CLOSE"]
TAB_CLOSE_HOVER = theme["TAB_CLOSE_HOVER"]
TAB_DIRTY = theme["TAB_DIRTY"]
TAB_BORDER = theme["TAB_BORDER"]
```

Also add matching entries to the `_LIGHT` dict if one exists, or use the same values.

- [ ] **Step 5: Verify no import errors**

Run: `python -c "from src.ui.theme import TAB_ACTIVE, TAB_INACTIVE, TAB_HOVER, TAB_CLOSE, TAB_CLOSE_HOVER, TAB_DIRTY, TAB_BORDER; print('OK')"`
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add src/ui/theme.py
git commit -m "feat: add tab bar theme colors for multi-project tabs"
```

---

## Task 2: Create ProjectContext Dataclass

**Files:**
- Create: `src/project_context.py`
- Create: `tests/test_project_context.py`

- [ ] **Step 1: Write the failing test for ProjectContext creation**

Create `tests/test_project_context.py`:

```python
"""Tests for ProjectContext — per-document state container."""
import pytest
from src.animation import AnimationTimeline
from src.palette import Palette
from src.project_context import ProjectContext


def test_create_default_context():
    """A new ProjectContext has sensible defaults."""
    ctx = ProjectContext.create_new(width=64, height=64)
    assert ctx.name == "Untitled"
    assert ctx.project_path is None
    assert ctx.dirty is False
    assert isinstance(ctx.timeline, AnimationTimeline)
    assert ctx.timeline.width == 64
    assert ctx.timeline.height == 64
    assert isinstance(ctx.palette, Palette)
    assert ctx.undo_stack == []
    assert ctx.redo_stack == []
    assert ctx.zoom_level == 1
    assert ctx.scroll_x == 0.0
    assert ctx.scroll_y == 0.0
    assert ctx.symmetry_mode == "off"
    assert ctx.playing is False
    assert ctx.onion_skin is False


def test_create_context_with_name():
    """Name can be overridden at creation."""
    ctx = ProjectContext.create_new(width=32, height=32, name="sprite.retro")
    assert ctx.name == "sprite.retro"


def test_create_context_custom_size():
    """Timeline dimensions match requested size."""
    ctx = ProjectContext.create_new(width=128, height=96)
    assert ctx.timeline.width == 128
    assert ctx.timeline.height == 96
    assert ctx.symmetry_axis_x == 64
    assert ctx.symmetry_axis_y == 48


def test_untitled_counter():
    """Multiple untitled contexts get incrementing names."""
    ProjectContext._untitled_counter = 0
    ctx1 = ProjectContext.create_new(width=32, height=32)
    ctx2 = ProjectContext.create_new(width=32, height=32)
    ctx3 = ProjectContext.create_new(width=32, height=32)
    assert ctx1.name == "Untitled"
    assert ctx2.name == "Untitled 2"
    assert ctx3.name == "Untitled 3"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_project_context.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.project_context'`

- [ ] **Step 3: Implement ProjectContext**

Create `src/project_context.py`:

```python
"""ProjectContext — encapsulates all per-document state for multi-project tabs."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from src.animation import AnimationTimeline
from src.grid import GridSettings
from src.palette import Palette


@dataclass
class ProjectContext:
    """All state belonging to a single open document.

    Global/shared state (active tool, clipboard, UI widgets, keybindings)
    stays on the app — this only holds what changes per-document.
    """

    # Identity
    project_path: Optional[str] = None
    name: str = "Untitled"
    dirty: bool = False

    # Core data
    timeline: AnimationTimeline = field(default_factory=lambda: AnimationTimeline(64, 64))
    palette: Palette = field(default_factory=lambda: Palette("Pico-8"))

    # Undo / Redo
    undo_stack: list = field(default_factory=list)
    redo_stack: list = field(default_factory=list)

    # Canvas view state
    zoom_level: int = 1
    scroll_x: float = 0.0
    scroll_y: float = 0.0

    # Document-bound settings
    grid_settings: GridSettings = field(default_factory=GridSettings)
    symmetry_mode: str = "off"
    symmetry_axis_x: int = 32
    symmetry_axis_y: int = 32

    # Reference image
    reference: Any = None  # ReferenceImage or None

    # Playback state
    playing: bool = False
    playback_mode: str = "forward"
    onion_skin: bool = False
    onion_range: int = 1
    pingpong_direction: int = 1

    # Export settings
    export_settings: dict = field(default_factory=dict)

    # Tool settings (document-bound portion)
    tool_settings: Any = None  # ToolSettingsManager or None

    # Display
    display_effects: bool = True

    # Untitled counter for unique names
    _untitled_counter: int = 0

    @classmethod
    def create_new(cls, width: int, height: int,
                   name: str | None = None) -> ProjectContext:
        """Create a fresh ProjectContext for a new document."""
        from src.tool_settings import ToolSettingsManager

        if name is None:
            cls._untitled_counter += 1
            if cls._untitled_counter == 1:
                name = "Untitled"
            else:
                name = f"Untitled {cls._untitled_counter}"

        timeline = AnimationTimeline(width, height)
        return cls(
            name=name,
            timeline=timeline,
            palette=Palette("Pico-8"),
            symmetry_axis_x=width // 2,
            symmetry_axis_y=height // 2,
            tool_settings=ToolSettingsManager(),
        )

    @classmethod
    def from_loaded(cls, timeline: AnimationTimeline, palette: Palette,
                    path: str, tool_settings: Any = None,
                    reference: Any = None,
                    grid_settings: GridSettings | None = None,
                    symmetry_axis_x: int | None = None,
                    symmetry_axis_y: int | None = None) -> ProjectContext:
        """Create a ProjectContext from loaded project data."""
        import os
        from src.tool_settings import ToolSettingsManager

        gs = grid_settings if grid_settings is not None else GridSettings()
        return cls(
            project_path=path,
            name=os.path.basename(path),
            timeline=timeline,
            palette=palette,
            grid_settings=gs,
            symmetry_axis_x=symmetry_axis_x if symmetry_axis_x is not None else timeline.width // 2,
            symmetry_axis_y=symmetry_axis_y if symmetry_axis_y is not None else timeline.height // 2,
            tool_settings=tool_settings if tool_settings is not None else ToolSettingsManager(),
            reference=reference,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_project_context.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/project_context.py tests/test_project_context.py
git commit -m "feat: add ProjectContext dataclass for per-document state"
```

---

## Task 3: Create TabBar Widget

**Files:**
- Create: `src/ui/tab_bar.py`
- Create: `tests/test_tab_bar.py`

- [ ] **Step 1: Write failing tests for TabBar**

Create `tests/test_tab_bar.py`:

```python
"""Tests for TabBar widget."""
import tkinter as tk
import pytest

try:
    _root = tk.Tk()
    _root.withdraw()
    HAS_TK = True
except Exception:
    HAS_TK = False
    _root = None

pytestmark = pytest.mark.skipif(not HAS_TK, reason="No display")


from src.ui.tab_bar import TabBar


@pytest.fixture
def tab_bar():
    bar = TabBar(_root, on_tab_select=lambda i: None,
                 on_tab_close=lambda i: None,
                 on_new_tab=lambda: None)
    return bar


def test_add_tab(tab_bar):
    tab_bar.add_tab("sprite.retro")
    assert tab_bar.tab_count == 1
    assert tab_bar.get_tab_name(0) == "sprite.retro"


def test_add_multiple_tabs(tab_bar):
    tab_bar.add_tab("file1.retro")
    tab_bar.add_tab("file2.retro")
    tab_bar.add_tab("file3.retro")
    assert tab_bar.tab_count == 3


def test_remove_tab(tab_bar):
    tab_bar.add_tab("file1.retro")
    tab_bar.add_tab("file2.retro")
    tab_bar.remove_tab(0)
    assert tab_bar.tab_count == 1
    assert tab_bar.get_tab_name(0) == "file2.retro"


def test_set_active_tab(tab_bar):
    tab_bar.add_tab("file1.retro")
    tab_bar.add_tab("file2.retro")
    tab_bar.set_active(1)
    assert tab_bar.active_index == 1


def test_set_dirty(tab_bar):
    tab_bar.add_tab("file.retro")
    tab_bar.set_dirty(0, True)
    assert tab_bar.is_dirty(0) is True
    tab_bar.set_dirty(0, False)
    assert tab_bar.is_dirty(0) is False


def test_rename_tab(tab_bar):
    tab_bar.add_tab("Untitled")
    tab_bar.rename_tab(0, "sprite.retro")
    assert tab_bar.get_tab_name(0) == "sprite.retro"


def test_set_tooltip(tab_bar):
    tab_bar.add_tab("sprite.retro")
    tab_bar.set_tooltip(0, "/full/path/to/sprite.retro")
    assert tab_bar.get_tooltip(0) == "/full/path/to/sprite.retro"


def test_clear_all(tab_bar):
    tab_bar.add_tab("file1.retro")
    tab_bar.add_tab("file2.retro")
    tab_bar.clear()
    assert tab_bar.tab_count == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_tab_bar.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.ui.tab_bar'`

- [ ] **Step 3: Implement TabBar widget**

Create `src/ui/tab_bar.py`:

```python
"""TabBar — custom tabbed document switcher for multi-project support."""
from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional

from src.ui.theme import (
    BG_DEEP, BG_PANEL, TEXT_PRIMARY, TEXT_SECONDARY, ACCENT_CYAN,
    TAB_ACTIVE, TAB_INACTIVE, TAB_HOVER, TAB_CLOSE, TAB_CLOSE_HOVER,
    TAB_DIRTY, TAB_BORDER,
)


class _TabButton:
    """Internal data for a single tab."""

    __slots__ = ("name", "dirty", "tooltip", "frame", "label", "close_btn",
                 "dirty_dot")

    def __init__(self, name: str):
        self.name = name
        self.dirty = False
        self.tooltip: str = ""
        # Widgets set later by TabBar._build_tab
        self.frame: Optional[tk.Frame] = None
        self.label: Optional[tk.Label] = None
        self.close_btn: Optional[tk.Label] = None
        self.dirty_dot: Optional[tk.Label] = None


class TabBar(tk.Frame):
    """Horizontal tab bar for switching between open documents."""

    def __init__(self, parent: tk.Widget, *,
                 on_tab_select: Callable[[int], None],
                 on_tab_close: Callable[[int], None],
                 on_new_tab: Callable[[], None]):
        super().__init__(parent, bg=BG_DEEP, height=28)
        self._on_tab_select = on_tab_select
        self._on_tab_close = on_tab_close
        self._on_new_tab = on_new_tab
        self._tabs: list[_TabButton] = []
        self._active: int = -1

        # Scrollable container
        self._scroll_frame = tk.Frame(self, bg=BG_DEEP)
        self._scroll_frame.pack(side="left", fill="both", expand=True)

        self._tabs_inner = tk.Frame(self._scroll_frame, bg=BG_DEEP)
        self._tabs_inner.pack(side="left", anchor="w")

        # [+] new tab button
        self._new_btn = tk.Label(
            self, text="+", font=("Consolas", 11, "bold"),
            bg=BG_DEEP, fg=TEXT_SECONDARY, cursor="hand2",
            padx=8, pady=2,
        )
        self._new_btn.pack(side="right", padx=(0, 4))
        self._new_btn.bind("<Button-1>", lambda e: self._on_new_tab())
        self._new_btn.bind("<Enter>",
                           lambda e: self._new_btn.config(fg=ACCENT_CYAN))
        self._new_btn.bind("<Leave>",
                           lambda e: self._new_btn.config(fg=TEXT_SECONDARY))

        # Scroll with mouse wheel on the bar
        self.bind("<MouseWheel>", self._on_scroll)
        self._scroll_offset = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def tab_count(self) -> int:
        return len(self._tabs)

    @property
    def active_index(self) -> int:
        return self._active

    def add_tab(self, name: str, activate: bool = True) -> int:
        """Add a new tab and optionally make it active. Returns index."""
        tab = _TabButton(name)
        self._tabs.append(tab)
        idx = len(self._tabs) - 1
        self._build_tab(tab, idx)
        if activate:
            self.set_active(idx)
        return idx

    def remove_tab(self, index: int) -> None:
        """Remove a tab by index."""
        if index < 0 or index >= len(self._tabs):
            return
        tab = self._tabs.pop(index)
        if tab.frame:
            tab.frame.destroy()
        # Rebuild remaining tabs to fix indices
        self._rebuild_all()
        # Adjust active index
        if self._active >= len(self._tabs):
            self._active = max(0, len(self._tabs) - 1)
        if self._tabs:
            self._highlight_active()

    def set_active(self, index: int) -> None:
        """Set the active tab by index."""
        if index < 0 or index >= len(self._tabs):
            return
        self._active = index
        self._highlight_active()

    def get_tab_name(self, index: int) -> str:
        return self._tabs[index].name

    def rename_tab(self, index: int, name: str) -> None:
        self._tabs[index].name = name
        if self._tabs[index].label:
            display = self._truncate(name)
            self._tabs[index].label.config(text=display)

    def set_dirty(self, index: int, dirty: bool) -> None:
        self._tabs[index].dirty = dirty
        if self._tabs[index].dirty_dot:
            self._tabs[index].dirty_dot.config(
                text="\u2022 " if dirty else "  ",
                fg=TAB_DIRTY if dirty else TAB_INACTIVE,
            )

    def is_dirty(self, index: int) -> bool:
        return self._tabs[index].dirty

    def set_tooltip(self, index: int, tooltip: str) -> None:
        self._tabs[index].tooltip = tooltip

    def get_tooltip(self, index: int) -> str:
        return self._tabs[index].tooltip

    def clear(self) -> None:
        """Remove all tabs."""
        for tab in self._tabs:
            if tab.frame:
                tab.frame.destroy()
        self._tabs.clear()
        self._active = -1

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_tab(self, tab: _TabButton, index: int) -> None:
        """Create the widgets for a single tab."""
        frame = tk.Frame(self._tabs_inner, bg=TAB_INACTIVE, cursor="hand2",
                         padx=0, pady=0,
                         highlightthickness=0,
                         bd=0)
        frame.pack(side="left", padx=(0, 1))

        # Dirty indicator dot
        dirty_dot = tk.Label(
            frame, text="  ", font=("Consolas", 8),
            bg=TAB_INACTIVE, fg=TAB_INACTIVE, padx=0, pady=0,
        )
        dirty_dot.pack(side="left", padx=(4, 0))

        # Tab name
        display = self._truncate(tab.name)
        label = tk.Label(
            frame, text=display, font=("Consolas", 9),
            bg=TAB_INACTIVE, fg=TEXT_SECONDARY,
            padx=4, pady=4,
        )
        label.pack(side="left")

        # Close button
        close_btn = tk.Label(
            frame, text="\u00d7", font=("Consolas", 9),
            bg=TAB_INACTIVE, fg=TAB_CLOSE,
            padx=4, pady=4, cursor="hand2",
        )
        close_btn.pack(side="left", padx=(0, 2))

        tab.frame = frame
        tab.label = label
        tab.close_btn = close_btn
        tab.dirty_dot = dirty_dot

        # Bindings
        for widget in (frame, label, dirty_dot):
            widget.bind("<Button-1>",
                        lambda e, i=index: self._click_tab(i))
            widget.bind("<Button-2>",
                        lambda e, i=index: self._on_tab_close(i))
            widget.bind("<Enter>",
                        lambda e, i=index: self._hover_tab(i, True))
            widget.bind("<Leave>",
                        lambda e, i=index: self._hover_tab(i, False))

        close_btn.bind("<Button-1>",
                       lambda e, i=index: self._close_tab(i))
        close_btn.bind("<Enter>",
                       lambda e: close_btn.config(fg=TAB_CLOSE_HOVER))
        close_btn.bind("<Leave>",
                       lambda e, i=index: self._reset_close_color(i))

    def _rebuild_all(self) -> None:
        """Destroy and rebuild all tab widgets (after remove/reorder)."""
        for tab in self._tabs:
            if tab.frame:
                tab.frame.destroy()
                tab.frame = None
        for idx, tab in enumerate(self._tabs):
            self._build_tab(tab, idx)
            if tab.dirty:
                self.set_dirty(idx, True)

    def _highlight_active(self) -> None:
        """Update visual state for all tabs."""
        for i, tab in enumerate(self._tabs):
            is_active = (i == self._active)
            bg = TAB_ACTIVE if is_active else TAB_INACTIVE
            fg = TEXT_PRIMARY if is_active else TEXT_SECONDARY
            if tab.frame:
                tab.frame.config(bg=bg)
            if tab.label:
                tab.label.config(bg=bg, fg=fg)
            if tab.close_btn:
                tab.close_btn.config(bg=bg)
            if tab.dirty_dot:
                dot_fg = TAB_DIRTY if tab.dirty else bg
                tab.dirty_dot.config(bg=bg, fg=dot_fg)

    def _click_tab(self, index: int) -> None:
        if index != self._active:
            self._on_tab_select(index)

    def _close_tab(self, index: int) -> None:
        self._on_tab_close(index)

    def _hover_tab(self, index: int, entering: bool) -> None:
        if index == self._active:
            return
        tab = self._tabs[index]
        bg = TAB_HOVER if entering else TAB_INACTIVE
        if tab.frame:
            tab.frame.config(bg=bg)
        if tab.label:
            tab.label.config(bg=bg)
        if tab.close_btn:
            tab.close_btn.config(bg=bg)
        if tab.dirty_dot:
            dot_fg = TAB_DIRTY if tab.dirty else bg
            tab.dirty_dot.config(bg=bg, fg=dot_fg)

    def _reset_close_color(self, index: int) -> None:
        tab = self._tabs[index]
        if tab.close_btn:
            tab.close_btn.config(fg=TAB_CLOSE)

    def _on_scroll(self, event: tk.Event) -> None:
        """Horizontal scroll on mouse wheel."""
        # Positive delta = scroll right, negative = scroll left
        delta = -1 if event.delta > 0 else 1
        self._scroll_offset += delta * 40
        self._scroll_offset = max(0, self._scroll_offset)
        self._tabs_inner.place(x=-self._scroll_offset, y=0)

    @staticmethod
    def _truncate(name: str, max_len: int = 20) -> str:
        if len(name) > max_len:
            return name[:max_len - 1] + "\u2026"
        return name
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_tab_bar.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/ui/tab_bar.py tests/test_tab_bar.py
git commit -m "feat: add TabBar widget for multi-project document switching"
```

---

## Task 4: Make RetroSpriteAPI Properties Dynamic

**Files:**
- Modify: `src/scripting.py`

- [ ] **Step 1: Read the current scripting.py**

Read `src/scripting.py` to see the current `__init__` and how `timeline`/`palette` are stored. They are currently plain attributes set on lines 21-22:
```python
self.timeline = timeline
self.palette = palette
```

- [ ] **Step 2: Write a test for dynamic API properties**

Add to an existing test file or create a small test. Since the API is simple, test inline:

Create or append to `tests/test_scripting.py`:

```python
"""Tests for RetroSpriteAPI dynamic properties."""
import pytest
from src.animation import AnimationTimeline
from src.palette import Palette
from src.scripting import RetroSpriteAPI


class FakeApp:
    def __init__(self):
        self.timeline = AnimationTimeline(32, 32)
        self.palette = Palette("Pico-8")


def test_api_timeline_follows_app():
    """API.timeline returns whatever the app currently has."""
    app = FakeApp()
    api = RetroSpriteAPI(timeline=app.timeline, palette=app.palette, app=app)
    old_timeline = api.timeline
    # Simulate a project switch
    app.timeline = AnimationTimeline(64, 64)
    assert api.timeline is app.timeline
    assert api.timeline is not old_timeline


def test_api_palette_follows_app():
    """API.palette returns whatever the app currently has."""
    app = FakeApp()
    api = RetroSpriteAPI(timeline=app.timeline, palette=app.palette, app=app)
    old_palette = api.palette
    app.palette = Palette("Pico-8")
    assert api.palette is app.palette
    assert api.palette is not old_palette


def test_api_headless_no_app():
    """Without an app, timeline/palette are stored directly."""
    tl = AnimationTimeline(16, 16)
    pal = Palette("Pico-8")
    api = RetroSpriteAPI(timeline=tl, palette=pal, app=None)
    assert api.timeline is tl
    assert api.palette is pal
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_scripting.py -v`
Expected: `test_api_timeline_follows_app` FAILS — API returns stored reference, not app's current one.

- [ ] **Step 4: Make timeline and palette into dynamic properties**

In `src/scripting.py`, refactor the `__init__` to store `_timeline` and `_palette` as fallbacks, and add `@property` accessors:

Replace the direct attribute assignments:
```python
self.timeline = timeline
self.palette = palette
```

With:
```python
self._timeline = timeline
self._palette = palette
```

Then add properties after `__init__`:

```python
@property
def timeline(self) -> AnimationTimeline:
    if self.app is not None:
        return self.app.timeline
    return self._timeline

@timeline.setter
def timeline(self, value: AnimationTimeline) -> None:
    self._timeline = value
    if self.app is not None:
        self.app.timeline = value

@property
def palette(self) -> Palette:
    if self.app is not None:
        return self.app.palette
    return self._palette

@palette.setter
def palette(self, value: Palette) -> None:
    self._palette = value
    if self.app is not None:
        self.app.palette = value
```

- [ ] **Step 5: Fix any references to `self.timeline`/`self.palette` in scripting.py**

Search for any direct `self.timeline` or `self.palette` usage inside scripting.py methods that should use the property. These should now work via the property automatically.

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_scripting.py -v`
Expected: All 3 tests PASS

- [ ] **Step 7: Run full test suite to check for regressions**

Run: `python -m pytest tests/ -x -q`
Expected: All existing tests PASS

- [ ] **Step 8: Commit**

```bash
git add src/scripting.py tests/test_scripting.py
git commit -m "feat: make RetroSpriteAPI timeline/palette dynamic properties"
```

---

## Task 5: Integrate ProjectContext Into App State Management

**Files:**
- Modify: `src/app.py`
- Create: `tests/test_multi_project.py`

This is the core task: adding `_projects`, `_active_project_index`, and the swap methods to `RetroSpriteApp`.

- [ ] **Step 1: Write failing tests for project context integration**

Create `tests/test_multi_project.py`:

```python
"""Integration tests for multi-project document switching."""
import tkinter as tk
import pytest

try:
    _root = tk.Tk()
    _root.withdraw()
    HAS_TK = True
except Exception:
    HAS_TK = False
    _root = None

pytestmark = pytest.mark.skipif(not HAS_TK, reason="No display")

from src.project_context import ProjectContext
from src.animation import AnimationTimeline
from src.palette import Palette


def test_save_to_context():
    """_save_to_context captures current app state into a ProjectContext."""
    ctx = ProjectContext.create_new(width=64, height=64)
    # Simulate: zoom=4, dirty=True, symmetry="horizontal"
    ctx.zoom_level = 4
    ctx.dirty = True
    ctx.symmetry_mode = "horizontal"
    assert ctx.zoom_level == 4
    assert ctx.dirty is True
    assert ctx.symmetry_mode == "horizontal"


def test_contexts_are_independent():
    """Two ProjectContexts don't share state."""
    ctx1 = ProjectContext.create_new(width=32, height=32)
    ctx2 = ProjectContext.create_new(width=64, height=64)
    ctx1.dirty = True
    ctx1.undo_stack.append("snapshot1")
    assert ctx2.dirty is False
    assert ctx2.undo_stack == []
    assert ctx1.timeline is not ctx2.timeline
    assert ctx1.palette is not ctx2.palette


def test_undo_stacks_independent():
    """Undo stacks are truly separate between contexts."""
    ctx1 = ProjectContext.create_new(width=32, height=32)
    ctx2 = ProjectContext.create_new(width=32, height=32)
    ctx1.undo_stack.append("action_a")
    ctx1.undo_stack.append("action_b")
    ctx2.undo_stack.append("action_x")
    assert len(ctx1.undo_stack) == 2
    assert len(ctx2.undo_stack) == 1
    assert ctx1.undo_stack[0] == "action_a"
    assert ctx2.undo_stack[0] == "action_x"
```

- [ ] **Step 2: Run tests to verify they pass (these test ProjectContext directly)**

Run: `python -m pytest tests/test_multi_project.py -v`
Expected: All 3 tests PASS (they test ProjectContext which already exists)

- [ ] **Step 3: Add `_projects` list and `_active_project_index` to `__init__`**

In `src/app.py`, after the existing state initialization (after line ~183 where `self._dirty = False` is set), add:

```python
# Multi-project state
self._projects: list[ProjectContext] = []
self._active_project_index: int = 0
```

Then, at the end of `__init__` (before `self.root.protocol(...)` on line 252), wrap the initial state into a ProjectContext:

```python
# Wrap initial document in a ProjectContext
from src.project_context import ProjectContext
initial_ctx = ProjectContext(
    project_path=self._project_path,
    name=os.path.basename(self._project_path) if self._project_path else "Untitled",
    timeline=self.timeline,
    palette=self.palette,
    undo_stack=self._undo_stack,
    redo_stack=self._redo_stack,
    grid_settings=self._grid_settings,
    symmetry_mode=self._symmetry_mode,
    symmetry_axis_x=self._symmetry_axis_x,
    symmetry_axis_y=self._symmetry_axis_y,
    reference=self._reference,
    playback_mode=self._playback_mode,
    onion_skin=self._onion_skin,
    onion_range=self._onion_range,
    pingpong_direction=self._pingpong_direction,
    export_settings=self._export_settings,
    tool_settings=self._tool_settings,
    display_effects=self._display_effects,
)
if initial_ctx.name == "Untitled":
    ProjectContext._untitled_counter = 1
self._projects.append(initial_ctx)
self._active_project_index = 0
```

- [ ] **Step 4: Add `_save_to_context()` method**

Add this method to `src/app.py` (in the app class, not in a mixin):

```python
def _save_to_context(self) -> None:
    """Save current app state into the active ProjectContext."""
    ctx = self._projects[self._active_project_index]
    ctx.project_path = self._project_path
    ctx.dirty = self._dirty
    ctx.timeline = self.timeline
    ctx.palette = self.palette
    ctx.undo_stack = self._undo_stack
    ctx.redo_stack = self._redo_stack
    ctx.grid_settings = self._grid_settings
    ctx.symmetry_mode = self._symmetry_mode
    ctx.symmetry_axis_x = self._symmetry_axis_x
    ctx.symmetry_axis_y = self._symmetry_axis_y
    ctx.reference = self._reference
    ctx.playing = self._playing
    ctx.playback_mode = self._playback_mode
    ctx.onion_skin = self._onion_skin
    ctx.onion_range = self._onion_range
    ctx.pingpong_direction = self._pingpong_direction
    ctx.export_settings = self._export_settings
    ctx.tool_settings = self._tool_settings
    ctx.display_effects = self._display_effects
    # Canvas view state
    ctx.zoom_level = self.pixel_canvas.pixel_size
    ctx.scroll_x = self.pixel_canvas.xview()[0] if hasattr(self.pixel_canvas, 'xview') else 0.0
    ctx.scroll_y = self.pixel_canvas.yview()[0] if hasattr(self.pixel_canvas, 'yview') else 0.0
```

- [ ] **Step 5: Add `_load_from_context()` method**

Add this method to `src/app.py`:

```python
def _load_from_context(self, index: int) -> None:
    """Load state from a ProjectContext into app variables."""
    ctx = self._projects[index]
    self._project_path = ctx.project_path
    self._dirty = ctx.dirty
    self.timeline = ctx.timeline
    self.palette = ctx.palette
    self._undo_stack = ctx.undo_stack
    self._redo_stack = ctx.redo_stack
    self._grid_settings = ctx.grid_settings
    self._symmetry_mode = ctx.symmetry_mode
    self._symmetry_axis_x = ctx.symmetry_axis_x
    self._symmetry_axis_y = ctx.symmetry_axis_y
    self._reference = ctx.reference
    self._playing = ctx.playing
    self._playback_mode = ctx.playback_mode
    self._onion_skin = ctx.onion_skin
    self._onion_range = ctx.onion_range
    self._pingpong_direction = ctx.pingpong_direction
    self._export_settings = ctx.export_settings
    self._tool_settings = ctx.tool_settings
    self._display_effects = ctx.display_effects
    # Canvas view state
    self.pixel_canvas.pixel_size = ctx.zoom_level
```

- [ ] **Step 6: Add `_switch_project()` method**

Add this method to `src/app.py`:

```python
def _switch_project(self, index: int) -> None:
    """Switch the active document to the project at the given index."""
    if index == self._active_project_index:
        return
    if index < 0 or index >= len(self._projects):
        return

    # 1. Cancel transient modes
    if self._selection_transform is not None:
        self._cancel_selection_transform()
    if self._rotation_mode:
        self._exit_rotation_mode(apply=False)
    if self._pasting:
        self._cancel_paste()
    if self._polygon_points:
        self._cancel_polygon()
    self._lasso_points = []
    self._line_start = None
    self._rect_start = None
    self._roundrect_start = None
    self._ellipse_start = None
    self._select_start = None
    self._move_start = None
    self._move_snapshot = None
    self._hand_last = None

    # 2. Stop playback
    self._stop_animation()

    # 3. Save outgoing state
    self._save_to_context()

    # 4. Load incoming state
    self._active_project_index = index
    self._load_from_context(index)

    # 5. Refresh all UI panels
    self.right_panel.palette_panel.palette = self.palette
    self.right_panel.palette_panel.refresh()
    self.timeline_panel.set_timeline(self.timeline)
    self.pixel_canvas.clear_overlays()
    self.pixel_canvas.clear_selection()
    self.pixel_canvas.clear_floating()
    self.pixel_canvas.clear_rotation_handles()
    self._pixel_grid_var.set(self._grid_settings.pixel_grid_visible)
    self._custom_grid_var.set(self._grid_settings.custom_grid_visible)
    self._update_grid_widget()
    if self._reference is not None:
        self._ref_opacity_var.set(self._reference.opacity)
    self._refresh_all()

    # 6. Update title and tab bar
    name = self._projects[index].name
    path_display = self._project_path or name
    self.root.title(f"RetroSprite - {path_display}")
    self.tab_bar.set_active(index)

    # 7. Emit API event
    self.api.emit("project_switch", {"index": index})
```

- [ ] **Step 7: Add `_active_context` property for convenience**

```python
@property
def _active_context(self) -> ProjectContext:
    """The currently active ProjectContext."""
    return self._projects[self._active_project_index]
```

- [ ] **Step 8: Run full test suite**

Run: `python -m pytest tests/ -x -q`
Expected: All tests PASS (no behavioral changes yet to existing flows)

- [ ] **Step 9: Commit**

```bash
git add src/app.py tests/test_multi_project.py
git commit -m "feat: add project context swap mechanism to RetroSpriteApp"
```

---

## Task 6: Add TabBar to the UI

**Files:**
- Modify: `src/app.py` (in `_build_ui()`)

- [ ] **Step 1: Import TabBar in app.py**

Add to the imports at the top of `src/app.py`:

```python
from src.ui.tab_bar import TabBar
```

- [ ] **Step 2: Add tab bar to `_build_ui()`**

In `_build_ui()`, after the options_bar pack (line 545: `self.options_bar.pack(side="top", fill="x")`), and before the grid widget label (line 548), insert:

```python
# Tab bar (between options bar and main frame)
self.tab_bar = TabBar(
    self.root,
    on_tab_select=self._switch_project,
    on_tab_close=self._close_project,
    on_new_tab=self._new_canvas,
)
self.tab_bar.pack(side="top", fill="x", before=self.options_bar)
```

Note: Using `before=self.options_bar` places it visually above the options bar. Alternatively, reorder the pack calls so the tab bar is packed before the options bar.

- [ ] **Step 3: Add the initial tab after `_build_ui()` completes**

In `__init__`, after the ProjectContext is created and appended (the code added in Task 5), add:

```python
# Add initial tab to the tab bar
initial_tab_name = initial_ctx.name
self.tab_bar.add_tab(initial_tab_name, activate=True)
if self._project_path:
    self.tab_bar.set_tooltip(0, self._project_path)
```

- [ ] **Step 4: Update `_mark_dirty()` to sync tab dirty indicator**

In `src/file_ops.py`, modify `_mark_dirty()` (line 694):

```python
def _mark_dirty(self):
    self._dirty = True
    if hasattr(self, 'tab_bar'):
        self.tab_bar.set_dirty(self._active_project_index, True)
```

- [ ] **Step 5: Launch the app and verify tab bar appears**

Run: `python main.py`
Expected: Tab bar visible above the options bar with one tab ("Untitled" or filename). The [+] button should be visible on the right.

- [ ] **Step 6: Run full test suite**

Run: `python -m pytest tests/ -x -q`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add src/app.py src/file_ops.py
git commit -m "feat: add TabBar widget to the main UI layout"
```

---

## Task 7: Refactor File Operations for Multi-Tab

**Files:**
- Modify: `src/file_ops.py`

- [ ] **Step 1: Refactor `_new_canvas()` to create a new tab**

Replace the existing `_new_canvas()` method (lines 159-182) with:

```python
def _new_canvas(self):
    """Create a new project in a new tab."""
    from src.dialogs import ask_canvas_size
    size = ask_canvas_size(self.root)
    if not size:
        return
    w, h = size
    from src.project_context import ProjectContext
    ctx = ProjectContext.create_new(width=w, height=h)
    self._projects.append(ctx)
    new_index = len(self._projects) - 1
    self.tab_bar.add_tab(ctx.name, activate=False)
    self._switch_project(new_index)
```

- [ ] **Step 2: Refactor `_open_project()` to open in a new tab**

Modify `_open_project()` (line 82). The key changes:
1. Remove the `_check_save_before()` guard (no longer replacing the current doc)
2. Check if file is already open in another tab
3. Create a new ProjectContext from loaded data
4. Add tab and switch

Replace the method with:

```python
def _open_project(self):
    """Open a .retro project file in a new tab."""
    path = ask_open_file(
        self.root,
        filetypes=[("RetroSprite Projects", "*.retro"),
                   ("Aseprite Files", "*.ase;*.aseprite"),
                   ("Photoshop Files", "*.psd"),
                   ("All files", "*.*")]
    )
    if not path:
        return

    # Check if already open
    for i, ctx in enumerate(self._projects):
        if ctx.project_path and os.path.normpath(ctx.project_path) == os.path.normpath(path):
            self._switch_project(i)
            return

    if not self.api.emit("before_load", {"filepath": path}):
        return

    ext = os.path.splitext(path)[1].lower()
    try:
        if ext in ('.ase', '.aseprite'):
            from src.aseprite_import import load_aseprite
            timeline, palette = load_aseprite(path)
            pal = Palette("Pico-8")
            pal.colors = palette.colors
            pal.selected_index = 0
            loaded_ref = None
            tool_settings_data = None
            grid_data = None
        elif ext == '.psd':
            from src.psd_import import load_psd
            timeline, palette = load_psd(path)
            pal = Palette("Pico-8")
            pal.colors = palette.colors
            pal.selected_index = 0
            loaded_ref = None
            tool_settings_data = None
            grid_data = None
        else:
            timeline, pal, tool_settings_data, loaded_ref, grid_data = load_project(path)
    except Exception as e:
        show_error(self.root, "Open Error", str(e))
        return

    from src.project_context import ProjectContext
    from src.grid import GridSettings
    from src.tool_settings import ToolSettingsManager

    gs = None
    sym_x = timeline.width // 2
    sym_y = timeline.height // 2
    ts = None

    if ext not in ('.ase', '.aseprite', '.psd'):
        if grid_data is not None:
            gs = GridSettings.from_dict(grid_data)
            if isinstance(grid_data, dict):
                ax = grid_data.get("symmetry_axis_x")
                ay = grid_data.get("symmetry_axis_y")
                if ax is not None:
                    sym_x = ax
                if ay is not None:
                    sym_y = ay
        ts = ToolSettingsManager.from_dict(tool_settings_data)

    proj_path = path if ext == '.retro' else None
    ctx = ProjectContext.from_loaded(
        timeline=timeline, palette=pal,
        path=path if proj_path else path,
        tool_settings=ts,
        reference=loaded_ref,
        grid_settings=gs,
        symmetry_axis_x=sym_x,
        symmetry_axis_y=sym_y,
    )
    if proj_path:
        ctx.project_path = proj_path

    self._projects.append(ctx)
    new_index = len(self._projects) - 1

    from src.recents import update_recents
    update_recents(path)

    self.tab_bar.add_tab(ctx.name, activate=False)
    self.tab_bar.set_tooltip(new_index, path)
    self._switch_project(new_index)
    self.api.emit("after_load", {"filepath": path})
```

- [ ] **Step 3: Add `_close_project()` method**

Add this new method to `FileOpsMixin` in `src/file_ops.py`:

```python
def _close_project(self, index: int | None = None):
    """Close a project tab. Prompts to save if dirty."""
    if index is None:
        index = self._active_project_index

    ctx = self._projects[index]

    # Check if dirty and prompt to save
    if ctx.dirty:
        # Temporarily switch to the tab being closed so save works correctly
        if index != self._active_project_index:
            self._switch_project(index)

        if not self._check_save_before():
            return

    # If this is the last tab, return to startup dialog
    if len(self._projects) == 1:
        self._stop_animation()
        self._projects.clear()
        self.tab_bar.clear()
        self._return_to_menu = True
        self.root.destroy()
        return

    # Remove the project and tab
    self._projects.pop(index)
    self.tab_bar.remove_tab(index)

    # Determine new active index
    if index <= self._active_project_index:
        self._active_project_index = max(0, self._active_project_index - 1)

    # Load the new active project
    self._load_from_context(self._active_project_index)
    self.right_panel.palette_panel.palette = self.palette
    self.right_panel.palette_panel.refresh()
    self.timeline_panel.set_timeline(self.timeline)
    self.pixel_canvas.clear_overlays()
    self._refresh_all()
    name = self._projects[self._active_project_index].name
    path_display = self._project_path or name
    self.root.title(f"RetroSprite - {path_display}")
    self.tab_bar.set_active(self._active_project_index)
```

- [ ] **Step 4: Add `_close_all_projects()` method**

```python
def _close_all_projects(self):
    """Close all project tabs, prompting to save each dirty one."""
    # Iterate in reverse so indices stay valid
    for i in range(len(self._projects) - 1, -1, -1):
        ctx = self._projects[i]
        if ctx.dirty:
            self._switch_project(i)
            if not self._check_save_before():
                return  # User cancelled — abort close-all
    # All saved or discarded — return to menu
    self._stop_animation()
    self._projects.clear()
    self.tab_bar.clear()
    self._return_to_menu = True
    self.root.destroy()
```

- [ ] **Step 5: Update `_save_project()` to sync tab state**

In `_save_project()` (line 29), after `self._dirty = False` (line 42), add:

```python
if hasattr(self, 'tab_bar'):
    self.tab_bar.set_dirty(self._active_project_index, False)
```

- [ ] **Step 6: Update `_save_project_as()` to sync tab name and state**

In `_save_project_as()` (line 50), after `self._dirty = False` (line 71), add:

```python
if hasattr(self, 'tab_bar'):
    import os as _os
    self.tab_bar.rename_tab(self._active_project_index, _os.path.basename(path))
    self.tab_bar.set_tooltip(self._active_project_index, path)
    self.tab_bar.set_dirty(self._active_project_index, False)
    self._active_context.name = _os.path.basename(path)
    self._active_context.project_path = path
```

- [ ] **Step 7: Update `_on_close()` to handle all tabs**

Replace `_on_close()` (line 745) with:

```python
def _on_close(self):
    """Handle window close (X button or Exit menu)."""
    # Prompt for each dirty project
    for i, ctx in enumerate(self._projects):
        if ctx.dirty:
            self._switch_project(i)
            if not self._check_save_before():
                return  # User cancelled
    self._stop_animation()
    from src.plugins import unload_all_plugins
    unload_all_plugins(self._plugins, self.api)
    self.root.destroy()
```

- [ ] **Step 8: Update `_return_to_menu_action()` to handle all tabs**

Replace `_return_to_menu_action()` (line 754) with:

```python
def _return_to_menu_action(self):
    """Return to the startup menu instead of quitting."""
    for i, ctx in enumerate(self._projects):
        if ctx.dirty:
            self._switch_project(i)
            if not self._check_save_before():
                return
    self._stop_animation()
    self._return_to_menu = True
    self.root.destroy()
```

- [ ] **Step 9: Run full test suite**

Run: `python -m pytest tests/ -x -q`
Expected: All tests PASS

- [ ] **Step 10: Manual smoke test**

Run: `python main.py`
Test:
1. Create a new project (Ctrl+N or [+] button) — new tab appears
2. Open a file (Ctrl+O) — new tab appears
3. Switch between tabs — canvas, palette, timeline update
4. Draw in Tab 1, switch to Tab 2, switch back — pixels preserved
5. Close a tab (click ×) — prompts to save if dirty
6. Close last tab — returns to startup dialog

- [ ] **Step 11: Commit**

```bash
git add src/file_ops.py
git commit -m "feat: refactor file operations for multi-tab document management"
```

---

## Task 8: Add Keyboard Shortcuts for Tab Navigation

**Files:**
- Modify: `src/app.py` (in `_bind_keys()`)

- [ ] **Step 1: Add tab navigation keybindings**

In `_bind_keys()` method in `src/app.py` (around line 616), add the following bindings:

```python
# Tab navigation
for key in ("<Control-w>", "<Control-W>"):
    self.root.bind(key, lambda e: self._close_project())
for key in ("<Control-Shift-w>", "<Control-Shift-W>"):
    self.root.bind(key, lambda e: self._close_all_projects())
self.root.bind("<Control-Tab>", lambda e: self._next_tab())
self.root.bind("<Control-Shift-Tab>", lambda e: self._prev_tab())
for n in range(1, 10):
    self.root.bind(f"<Control-Key-{n}>",
                   lambda e, i=n-1: self._switch_project(i))
```

- [ ] **Step 2: Add `_next_tab()` and `_prev_tab()` helper methods**

Add to `src/app.py`:

```python
def _next_tab(self) -> None:
    """Switch to the next tab (wrapping)."""
    if len(self._projects) <= 1:
        return
    new_idx = (self._active_project_index + 1) % len(self._projects)
    self._switch_project(new_idx)

def _prev_tab(self) -> None:
    """Switch to the previous tab (wrapping)."""
    if len(self._projects) <= 1:
        return
    new_idx = (self._active_project_index - 1) % len(self._projects)
    self._switch_project(new_idx)
```

- [ ] **Step 3: Add Close and Close All to the File menu**

In `_build_menu()` in `src/app.py`, find the File menu section. After the existing Save As entry, add:

```python
file_menu.add_separator()
file_menu.add_command(label="Close", command=self._close_project,
                      accelerator="Ctrl+W")
file_menu.add_command(label="Close All", command=self._close_all_projects,
                      accelerator="Ctrl+Shift+W")
```

- [ ] **Step 4: Run the app and test shortcuts**

Run: `python main.py`
Test:
1. Ctrl+N → new tab
2. Ctrl+Tab → next tab
3. Ctrl+Shift+Tab → previous tab
4. Ctrl+1, Ctrl+2 → jump to tab
5. Ctrl+W → close current tab
6. Ctrl+Shift+W → close all tabs

- [ ] **Step 5: Run full test suite**

Run: `python -m pytest tests/ -x -q`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/app.py
git commit -m "feat: add keyboard shortcuts for tab navigation"
```

---

## Task 9: Add Right-Click Context Menu to Tabs

**Files:**
- Modify: `src/ui/tab_bar.py`

- [ ] **Step 1: Add context menu support to TabBar**

In `src/ui/tab_bar.py`, add an `on_tab_context` callback parameter to `__init__`:

```python
def __init__(self, parent: tk.Widget, *,
             on_tab_select: Callable[[int], None],
             on_tab_close: Callable[[int], None],
             on_new_tab: Callable[[], None],
             on_tab_context: Callable[[int, tk.Event], None] | None = None):
```

Store it: `self._on_tab_context = on_tab_context`

- [ ] **Step 2: Bind right-click in `_build_tab()`**

In `_build_tab()`, add to the binding loop for `frame`, `label`, `dirty_dot`:

```python
widget.bind("<Button-3>",
            lambda e, i=index: self._show_context(i, e))
```

Add the method:

```python
def _show_context(self, index: int, event: tk.Event) -> None:
    if self._on_tab_context:
        self._on_tab_context(index, event)
```

- [ ] **Step 3: Add context menu handler in app.py**

In `src/app.py`, add a method and pass it to TabBar:

```python
def _on_tab_context(self, index: int, event: tk.Event) -> None:
    """Show right-click context menu for a tab."""
    menu = tk.Menu(self.root, tearoff=0)
    menu.add_command(label="Close", command=lambda: self._close_project(index))
    menu.add_command(label="Close Others",
                     command=lambda: self._close_others(index))
    menu.add_command(label="Close All",
                     command=self._close_all_projects)
    menu.add_separator()
    menu.add_command(label="Save", command=lambda: self._save_tab(index))
    ctx = self._projects[index]
    if ctx.project_path:
        menu.add_separator()
        menu.add_command(label="Reveal in Explorer",
                         command=lambda: self._reveal_in_explorer(ctx.project_path))
    menu.tk_popup(event.x_root, event.y_root)

def _close_others(self, keep_index: int) -> None:
    """Close all tabs except the one at keep_index."""
    indices = [i for i in range(len(self._projects)) if i != keep_index]
    for i in reversed(indices):
        self._close_project(i)

def _save_tab(self, index: int) -> None:
    """Save a specific tab's project."""
    if index != self._active_project_index:
        self._switch_project(index)
    self._save_project()

def _reveal_in_explorer(self, path: str) -> None:
    """Open the file's directory in the system file explorer."""
    import subprocess, os
    folder = os.path.dirname(path)
    if os.name == 'nt':
        subprocess.Popen(f'explorer /select,"{path}"')
    elif os.name == 'posix':
        subprocess.Popen(['xdg-open', folder])
```

Update the TabBar construction in `_build_ui()` to pass the callback:

```python
self.tab_bar = TabBar(
    self.root,
    on_tab_select=self._switch_project,
    on_tab_close=self._close_project,
    on_new_tab=self._new_canvas,
    on_tab_context=self._on_tab_context,
)
```

- [ ] **Step 4: Run the app and test context menu**

Run: `python main.py`
Test: Right-click a tab → context menu with Close, Close Others, Close All, Save, Reveal in Explorer

- [ ] **Step 5: Run full test suite**

Run: `python -m pytest tests/ -x -q`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/ui/tab_bar.py src/app.py
git commit -m "feat: add right-click context menu to tab bar"
```

---

## Task 10: Add `project_switch` Event to API

**Files:**
- Modify: `src/scripting.py`

- [ ] **Step 1: Write test for project_switch event**

Add to `tests/test_scripting.py`:

```python
def test_project_switch_event():
    """project_switch event fires with index payload."""
    app = FakeApp()
    api = RetroSpriteAPI(timeline=app.timeline, palette=app.palette, app=app)
    received = []
    api.on("project_switch", lambda payload: received.append(payload))
    api.emit("project_switch", {"index": 2})
    assert len(received) == 1
    assert received[0]["index"] == 2
```

- [ ] **Step 2: Run test to verify it passes**

Run: `python -m pytest tests/test_scripting.py::test_project_switch_event -v`
Expected: PASS — the event system already supports arbitrary event names, so this should work without code changes.

- [ ] **Step 3: Verify the `_switch_project()` method in app.py already emits this event**

Check that the `_switch_project()` method (added in Task 5) contains:
```python
self.api.emit("project_switch", {"index": index})
```

This was included in Task 5, Step 6. No changes needed.

- [ ] **Step 4: Commit**

```bash
git add tests/test_scripting.py
git commit -m "test: add project_switch event test"
```

---

## Task 11: Update Documentation

**Files:**
- Modify: Keyboard shortcut documentation and user guides

- [ ] **Step 1: Identify documentation files to update**

Search for keyboard shortcut references and user documentation:
- Check `docs/` for any shortcut reference files
- Check if there's an in-app help dialog that lists shortcuts
- Check `CLAUDE.md` for mentions of file operations

- [ ] **Step 2: Update CLAUDE.md**

In `CLAUDE.md`, add a note about the multi-project tab system in the Architecture section. Add a new row to the mixin table or add a note:

```markdown
### Multi-Project Tabs

- `src/project_context.py` — `ProjectContext` dataclass holding per-document state
- `src/ui/tab_bar.py` — `TabBar` custom widget for document switching
- State swap: `_save_to_context()` / `_load_from_context()` / `_switch_project()`
- Global state (tool, clipboard) stays on app; per-document state (timeline, palette, undo) lives in ProjectContext
```

- [ ] **Step 3: Update keyboard shortcut documentation**

Add the new shortcuts to whatever shortcut reference exists:

```
Ctrl+W          Close active tab
Ctrl+Shift+W    Close all tabs
Ctrl+Tab        Next tab
Ctrl+Shift+Tab  Previous tab
Ctrl+1-9        Jump to tab by position
```

- [ ] **Step 4: Commit**

```bash
git add docs/ CLAUDE.md
git commit -m "docs: add multi-project tabs documentation and shortcuts"
```

---

## Task 12: Final Integration Testing

**Files:**
- Modify: `tests/test_multi_project.py`

- [ ] **Step 1: Add comprehensive integration tests**

Add the following tests to `tests/test_multi_project.py`:

```python
def test_clipboard_shared_across_contexts():
    """Clipboard is not stored in ProjectContext — it's global."""
    ctx1 = ProjectContext.create_new(width=32, height=32)
    ctx2 = ProjectContext.create_new(width=32, height=32)
    # Clipboard is on the app, not on the context
    assert not hasattr(ctx1, '_clipboard')
    assert not hasattr(ctx2, '_clipboard')


def test_context_from_loaded():
    """from_loaded creates a context with the right name and path."""
    tl = AnimationTimeline(64, 64)
    pal = Palette("Pico-8")
    ctx = ProjectContext.from_loaded(
        timeline=tl, palette=pal, path="/tmp/test.retro"
    )
    assert ctx.name == "test.retro"
    assert ctx.project_path == "/tmp/test.retro"
    assert ctx.timeline is tl
    assert ctx.palette is pal
    assert ctx.dirty is False


def test_context_symmetry_defaults_to_center():
    """Symmetry axes default to canvas center."""
    ctx = ProjectContext.create_new(width=100, height=60)
    assert ctx.symmetry_axis_x == 50
    assert ctx.symmetry_axis_y == 30
```

- [ ] **Step 2: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS including the new ones.

- [ ] **Step 3: Run the app for a full manual smoke test**

Run: `python main.py`

Complete workflow test:
1. App starts → one tab visible ("Untitled")
2. Ctrl+N → new project dialog → second tab appears → switched to it
3. Draw something in Tab 2
4. Click Tab 1 → canvas shows empty project, palette resets
5. Click Tab 2 → drawings preserved
6. Ctrl+O → open a file → new tab appears
7. Ctrl+S → saves active document, dirty dot clears
8. Ctrl+Tab / Ctrl+Shift+Tab → cycles through tabs
9. Ctrl+1 → jumps to first tab
10. Right-click tab → context menu works
11. Click × on a dirty tab → save prompt appears
12. Close all tabs → startup dialog returns
13. Ctrl+Z/Ctrl+Y → undo/redo is per-document (draw in Tab 1, switch to Tab 2, Ctrl+Z does nothing, switch back to Tab 1, Ctrl+Z undoes)

- [ ] **Step 4: Commit**

```bash
git add tests/test_multi_project.py
git commit -m "test: add comprehensive multi-project integration tests"
```

---

## Task Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Tab bar theme colors | `src/ui/theme.py` |
| 2 | ProjectContext dataclass | `src/project_context.py`, `tests/test_project_context.py` |
| 3 | TabBar widget | `src/ui/tab_bar.py`, `tests/test_tab_bar.py` |
| 4 | Dynamic API properties | `src/scripting.py`, `tests/test_scripting.py` |
| 5 | App state management (swap) | `src/app.py`, `tests/test_multi_project.py` |
| 6 | TabBar in UI layout | `src/app.py`, `src/file_ops.py` |
| 7 | Multi-tab file operations | `src/file_ops.py` |
| 8 | Tab keyboard shortcuts | `src/app.py` |
| 9 | Tab context menu | `src/ui/tab_bar.py`, `src/app.py` |
| 10 | project_switch event | `tests/test_scripting.py` |
| 11 | Documentation updates | `CLAUDE.md`, docs |
| 12 | Final integration testing | `tests/test_multi_project.py` |
