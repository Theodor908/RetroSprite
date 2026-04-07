# Per-Tool Settings Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Each drawing tool independently remembers its own settings (size, symmetry, dither, pixel_perfect, ink_mode, tolerance), persisted in the `.retro` project file.

**Architecture:** A new `ToolSettingsManager` class stores per-tool settings as a `dict[str, dict]`. On tool switch, the app saves the outgoing tool's settings and restores the incoming tool's settings, syncing both the app state variables and the OptionsBar UI. The manager serializes to/from the project file.

**Tech Stack:** Python, Tkinter (existing stack). No new dependencies.

---

### Task 1: Create `ToolSettingsManager` class

**Files:**
- Create: `src/tool_settings.py`
- Test: `tests/test_tool_settings.py`

**Step 1: Write the failing tests**

Create `tests/test_tool_settings.py`:

```python
"""Tests for ToolSettingsManager."""
from src.tool_settings import ToolSettingsManager


def test_defaults_exist_for_all_tools():
    mgr = ToolSettingsManager()
    for tool in ["pen", "eraser", "blur", "fill", "line", "rect", "ellipse", "wand",
                 "pick", "select", "hand", "lasso"]:
        settings = mgr.get(tool)
        assert isinstance(settings, dict)


def test_pen_defaults():
    mgr = ToolSettingsManager()
    s = mgr.get("pen")
    assert s["size"] == 1
    assert s["symmetry"] == "off"
    assert s["dither"] == "none"
    assert s["pixel_perfect"] is False
    assert s["ink_mode"] == "normal"


def test_eraser_defaults():
    mgr = ToolSettingsManager()
    s = mgr.get("eraser")
    assert s["size"] == 3
    assert s["ink_mode"] == "normal"


def test_save_and_get():
    mgr = ToolSettingsManager()
    mgr.save("pen", {"size": 5, "symmetry": "horizontal"})
    s = mgr.get("pen")
    assert s["size"] == 5
    assert s["symmetry"] == "horizontal"
    # Other defaults preserved
    assert s["dither"] == "none"


def test_save_ignores_unknown_keys():
    mgr = ToolSettingsManager()
    mgr.save("pen", {"size": 5, "bogus_key": 999})
    s = mgr.get("pen")
    assert s["size"] == 5
    assert "bogus_key" not in s


def test_to_dict_round_trip():
    mgr = ToolSettingsManager()
    mgr.save("pen", {"size": 7, "dither": "checker"})
    mgr.save("eraser", {"size": 10})
    data = mgr.to_dict()
    mgr2 = ToolSettingsManager.from_dict(data)
    assert mgr2.get("pen")["size"] == 7
    assert mgr2.get("pen")["dither"] == "checker"
    assert mgr2.get("eraser")["size"] == 10


def test_from_dict_fills_missing_with_defaults():
    mgr = ToolSettingsManager.from_dict({"pen": {"size": 3}})
    s = mgr.get("pen")
    assert s["size"] == 3
    assert s["symmetry"] == "off"  # default filled in
    # Other tools get full defaults
    assert mgr.get("eraser")["size"] == 3  # eraser default


def test_get_unknown_tool_returns_empty():
    mgr = ToolSettingsManager()
    s = mgr.get("nonexistent_tool")
    assert s == {}
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_tool_settings.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.tool_settings'`

**Step 3: Write the implementation**

Create `src/tool_settings.py`:

```python
"""Per-tool settings manager for RetroSprite.

Each drawing tool remembers its own settings independently.
Settings are serialized into the .retro project file.
"""
from __future__ import annotations
from copy import deepcopy


# Default settings per tool. Keys must match TOOL_OPTIONS in options_bar.py.
TOOL_DEFAULTS: dict[str, dict] = {
    "pen":     {"size": 1, "symmetry": "off", "dither": "none", "pixel_perfect": False, "ink_mode": "normal"},
    "eraser":  {"size": 3, "symmetry": "off", "pixel_perfect": False, "ink_mode": "normal"},
    "blur":    {"size": 3},
    "fill":    {"tolerance": 32, "dither": "none"},
    "line":    {"size": 1},
    "rect":    {"size": 1},
    "ellipse": {"size": 1},
    "wand":    {"tolerance": 32},
    "pick":    {},
    "select":  {},
    "hand":    {},
    "lasso":   {},
}


class ToolSettingsManager:
    """Stores and retrieves per-tool settings."""

    def __init__(self):
        self._settings: dict[str, dict] = deepcopy(TOOL_DEFAULTS)

    def get(self, tool_name: str) -> dict:
        """Return current settings for *tool_name* (lowercase).
        Returns empty dict for unknown tools."""
        return dict(self._settings.get(tool_name, {}))

    def save(self, tool_name: str, values: dict) -> None:
        """Update stored settings for *tool_name*.
        Only keys that exist in that tool's defaults are accepted."""
        if tool_name not in self._settings:
            return
        allowed = self._settings[tool_name]
        for key, value in values.items():
            if key in allowed:
                allowed[key] = value

    def to_dict(self) -> dict:
        """Serialize all tool settings for project save."""
        return deepcopy(self._settings)

    @classmethod
    def from_dict(cls, data: dict) -> ToolSettingsManager:
        """Restore from project file data.
        Missing tools/keys fall back to defaults."""
        mgr = cls()
        for tool_name, saved_values in data.items():
            if tool_name in mgr._settings:
                for key, value in saved_values.items():
                    if key in mgr._settings[tool_name]:
                        mgr._settings[tool_name][key] = value
        return mgr
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_tool_settings.py -v`
Expected: All 8 tests PASS

**Step 5: Commit**

```bash
git add src/tool_settings.py tests/test_tool_settings.py
git commit -m "feat: add ToolSettingsManager for per-tool settings"
```

---

### Task 2: Add `restore_settings()` to OptionsBar

**Files:**
- Modify: `src/ui/options_bar.py` (add method after line 249)

**Step 1: Write the implementation**

Add this method to the `OptionsBar` class at the end of the file (after `update_pixel_perfect_label`):

```python
def restore_settings(self, settings: dict) -> None:
    """Batch-update all UI controls from a settings dict.
    Called on tool switch to reflect the new tool's stored values."""
    if "size" in settings:
        self._size_var.set(settings["size"])
    if "symmetry" in settings:
        self._sym_var.set(settings["symmetry"])
    if "dither" in settings:
        self._dither_var.set(settings["dither"])
    if "pixel_perfect" in settings:
        self._pp_var.set(settings["pixel_perfect"])
        self._pp_btn.config(text=f"PP: {'On' if settings['pixel_perfect'] else 'Off'}")
    if "ink_mode" in settings:
        mode_display = {"normal": "Normal", "alpha_lock": "\u03b1Lock", "behind": "Behind"}
        display = mode_display.get(settings["ink_mode"], "Normal")
        self._ink_var.set(display)
        self._ink_btn.config(text=f"Ink: {display}")
    if "tolerance" in settings:
        self._tol_var.set(settings["tolerance"])
```

**Step 2: Verify app still launches**

Run: `python main.py` — confirm it opens without errors, close the app.

**Step 3: Commit**

```bash
git add src/ui/options_bar.py
git commit -m "feat: add restore_settings method to OptionsBar"
```

---

### Task 3: Wire `ToolSettingsManager` into `RetroSpriteApp`

This is the core integration task. It modifies `src/app.py` in several places.

**Files:**
- Modify: `src/app.py`

**Step 1: Add import (line ~29, after `from src.ui.options_bar import OptionsBar`)**

Add:
```python
from src.tool_settings import ToolSettingsManager
```

**Step 2: Initialize manager in `__init__` (after line 102, near `self._tool_size = 1`)**

Add after `self._tool_size = 1` (line 102):
```python
self._tool_settings = ToolSettingsManager()
```

**Step 3: Create helper methods to capture and apply tool settings**

Add two new methods near the tool handling section (after `_on_tool_change`, around line 665):

```python
def _capture_current_tool_settings(self) -> dict:
    """Capture the current app state as a settings dict for the active tool."""
    return {
        "size": self._tool_size,
        "symmetry": self._symmetry_mode,
        "dither": self._dither_pattern,
        "pixel_perfect": self._pixel_perfect,
        "ink_mode": self._ink_mode,
        "tolerance": self._wand_tolerance,
    }

def _apply_tool_settings(self, settings: dict) -> None:
    """Apply a settings dict to the app state and sync the OptionsBar."""
    if "size" in settings:
        self._tool_size = settings["size"]
    if "symmetry" in settings:
        self._symmetry_mode = settings["symmetry"]
    if "dither" in settings:
        self._dither_pattern = settings["dither"]
    if "pixel_perfect" in settings:
        self._pixel_perfect = settings["pixel_perfect"]
    if "ink_mode" in settings:
        self._ink_mode = settings["ink_mode"]
    if "tolerance" in settings:
        self._wand_tolerance = settings["tolerance"]
    self.options_bar.restore_settings(settings)
```

**Step 4: Update `_on_tool_change` (line 643-664)**

Replace the current `_on_tool_change` method body. The key changes are: save outgoing tool settings, load incoming tool settings, apply them.

Current (line 643-664):
```python
def _on_tool_change(self, name: str):
    self.current_tool_name = name
    self.api.emit("tool_change", {"tool_name": name})
    self._cancel_paste()
    self._line_start = None
    self._rect_start = None
    self._ellipse_start = None
    self._select_start = None
    self._hand_last = None
    self._pp_last_points = []
    self._lasso_points = []
    # Update options bar for the new tool
    self.options_bar.set_tool(name.lower())
    # Set Hand tool raw callbacks or clear them
    if name == "Hand":
        self.pixel_canvas._on_raw_click = self._hand_click
        self.pixel_canvas._on_raw_drag = self._hand_drag
    else:
        self.pixel_canvas._on_raw_click = None
        self.pixel_canvas._on_raw_drag = None
    self.pixel_canvas.clear_overlays()
    self._update_status()
```

New version:
```python
def _on_tool_change(self, name: str):
    # Save outgoing tool's settings
    old_tool = self.current_tool_name.lower()
    self._tool_settings.save(old_tool, self._capture_current_tool_settings())

    self.current_tool_name = name
    self.api.emit("tool_change", {"tool_name": name})
    self._cancel_paste()
    self._line_start = None
    self._rect_start = None
    self._ellipse_start = None
    self._select_start = None
    self._hand_last = None
    self._pp_last_points = []
    self._lasso_points = []
    # Update options bar visibility for the new tool
    self.options_bar.set_tool(name.lower())
    # Restore incoming tool's settings
    new_settings = self._tool_settings.get(name.lower())
    self._apply_tool_settings(new_settings)
    # Set Hand tool raw callbacks or clear them
    if name == "Hand":
        self.pixel_canvas._on_raw_click = self._hand_click
        self.pixel_canvas._on_raw_drag = self._hand_drag
    else:
        self.pixel_canvas._on_raw_click = None
        self.pixel_canvas._on_raw_drag = None
    self.pixel_canvas.clear_overlays()
    self._update_status()
```

**Step 5: Update `_reset_state` (line 2128-2171)**

In `_reset_state`, replace the manual setting resets with a fresh `ToolSettingsManager` and apply the Pen defaults.

Replace lines 2150-2160:
```python
        self._symmetry_mode = "off"
        self._pixel_perfect = False
        self._pp_last_points = []
        self._dither_pattern = "none"
        self.current_tool_name = "Pen"
        self._tool_size = 1
        self.toolbar.select_tool("Pen")
        self.options_bar.set_size(1)
        self.options_bar.update_symmetry_label("off")
        self.options_bar.update_dither_label("none")
        self.options_bar.update_pixel_perfect_label(False)
```

With:
```python
        self._pp_last_points = []
        self.current_tool_name = "Pen"
        self._tool_settings = ToolSettingsManager()
        self.toolbar.select_tool("Pen")
        self.options_bar.set_tool("pen")
        pen_settings = self._tool_settings.get("pen")
        self._apply_tool_settings(pen_settings)
```

**Step 6: Verify app still launches and tool switching works**

Run: `python main.py`
- Select Pen, set size to 5
- Switch to Eraser, confirm size shows 3 (eraser default)
- Switch back to Pen, confirm size shows 5 (remembered)
- Close the app

**Step 7: Commit**

```bash
git add src/app.py
git commit -m "feat: wire ToolSettingsManager into app for per-tool settings"
```

---

### Task 4: Persist tool settings in project file

**Files:**
- Modify: `src/project.py` (lines 14 and 91-107 for save, lines 110-218 for load)
- Modify: `src/app.py` (save/load integration points)

**Step 1: Update `save_project` signature and serialization**

In `src/project.py`, change the `save_project` function signature (line 14) to accept an optional `tool_settings` parameter:

```python
def save_project(filepath: str, timeline: AnimationTimeline,
                 palette: Palette, tool_settings: dict | None = None) -> None:
```

In the project dict (around line 91), add the tool_settings key. Also update the version logic:

Replace line 92:
```python
        "version": 4 if getattr(timeline, 'color_mode', 'rgba') == 'indexed' else 3,
```
With:
```python
        "version": 5 if tool_settings else (4 if getattr(timeline, 'color_mode', 'rgba') == 'indexed' else 3),
```

Add after the `"tags"` line (line 103, before the closing `}`):
```python
        "tool_settings": tool_settings or {},
```

**Step 2: Update `load_project` to return tool settings**

Change the return type (line 110):
```python
def load_project(filepath: str) -> tuple[AnimationTimeline, Palette, dict]:
```

Before the final return (line 218), extract tool_settings:
```python
    tool_settings_data = project.get("tool_settings", {})
    return timeline, palette, tool_settings_data
```

**Step 3: Update all `save_project` calls in `app.py`**

There are 6 calls to `save_project` in `app.py` (lines 2082, 2106, 2120, 2212, 2233). Each needs `tool_settings=self._tool_settings.to_dict()` added as the 4th argument.

Before saving, capture the current tool's settings so they're included:

For each `save_project(...)` call, add a preceding line:
```python
self._tool_settings.save(self.current_tool_name.lower(), self._capture_current_tool_settings())
```

Then change the call, e.g.:
```python
save_project(self._project_path, self.timeline, self.palette,
             tool_settings=self._tool_settings.to_dict())
```

**Step 4: Update all `load_project` calls in `app.py`**

Line 78 (in `__init__`):
```python
self.timeline, self.palette, tool_settings_data = load_project(startup["path"])
self._tool_settings = ToolSettingsManager.from_dict(tool_settings_data)
```

Line 2278 (in `_open_project`):
```python
self.timeline, self.palette, tool_settings_data = load_project(path)
```

Then in `_reset_state` called after load, or directly after line 2278, initialize the manager:

After `_reset_state()` on line 2284, add:
```python
if ext not in ('.ase', '.aseprite', '.psd'):
    self._tool_settings = ToolSettingsManager.from_dict(tool_settings_data)
    pen_settings = self._tool_settings.get("pen")
    self._apply_tool_settings(pen_settings)
```

Note: For `.ase` and `.psd` imports, `load_project` isn't called so `tool_settings_data` won't exist. The `_reset_state` already creates a fresh `ToolSettingsManager`.

**Step 5: Add a round-trip test**

Add to `tests/test_tool_settings.py`:

```python
def test_project_round_trip(tmp_path):
    """Verify tool settings survive save/load cycle."""
    from src.tool_settings import ToolSettingsManager
    mgr = ToolSettingsManager()
    mgr.save("pen", {"size": 7, "symmetry": "both", "dither": "checker"})
    mgr.save("eraser", {"size": 12})
    data = mgr.to_dict()
    # Simulate what save_project would write
    import json
    path = tmp_path / "test.json"
    path.write_text(json.dumps({"tool_settings": data}))
    # Simulate what load_project would read
    loaded = json.loads(path.read_text())
    mgr2 = ToolSettingsManager.from_dict(loaded.get("tool_settings", {}))
    assert mgr2.get("pen")["size"] == 7
    assert mgr2.get("pen")["symmetry"] == "both"
    assert mgr2.get("eraser")["size"] == 12
```

**Step 6: Run all tests**

Run: `python -m pytest tests/test_tool_settings.py -v`
Expected: All tests PASS

**Step 7: Verify full round-trip manually**

Run: `python main.py`
1. Set Pen size to 5, symmetry to horizontal
2. Switch to Eraser, set size to 8
3. Save project as `test.retro`
4. Close and reopen the project
5. Select Pen — should show size 5, symmetry horizontal
6. Select Eraser — should show size 8

**Step 8: Commit**

```bash
git add src/project.py src/app.py tests/test_tool_settings.py
git commit -m "feat: persist per-tool settings in .retro project file"
```

---

### Task 5: Handle callback updates saving to manager

**Files:**
- Modify: `src/app.py`

The existing callbacks (`_on_size_change`, `_on_symmetry_change`, `_cycle_dither`, `_toggle_pixel_perfect`, `_on_ink_mode_change`, `_on_tolerance_change`) update the flat app variables. These still work correctly because:

1. When the user changes a setting via the OptionsBar, it updates the app variable (e.g., `_tool_size = size`).
2. When the user switches tools, `_on_tool_change` captures the current values (which include any OptionsBar changes) into the manager.

No changes needed to these callbacks — the save-on-switch pattern handles it. This task is verification only.

**Step 1: Verify settings are captured on switch**

Run: `python main.py`
1. Pen → set size 5
2. Switch to Rect (Pen size 5 should be saved)
3. Rect → set size 3
4. Switch back to Pen → size should be 5
5. Switch to Rect → size should be 3

**Step 2: Commit (if any fixes needed)**

```bash
git add src/app.py
git commit -m "fix: ensure callback-driven changes saved on tool switch"
```

---

### Task 6: Final cleanup and edge case handling

**Files:**
- Modify: `src/app.py`
- Modify: `src/tool_settings.py`

**Step 1: Handle plugin tools**

Plugin tools loaded via `plugin_tools.py` won't have defaults in `TOOL_DEFAULTS`. The `ToolSettingsManager.get()` already returns `{}` for unknown tools, so they'll behave as they do today (using whatever the current app state is). No code change needed.

**Step 2: Ensure `_change_size` keyboard shortcut (`[` and `]`) updates correctly**

Check that keyboard shortcuts for size change still work and are captured on tool switch. These already modify `_tool_size` via `_on_size_change`, so they're fine.

**Step 3: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat: per-tool settings complete — each tool remembers its own size, symmetry, dither, pixel_perfect, ink_mode, tolerance"
```
