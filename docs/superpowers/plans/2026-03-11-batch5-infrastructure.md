# Batch 5: Infrastructure — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a scripting API, CLI/batch export interface, and plugin system to RetroSprite.

**Architecture:** Four new modules (`scripting.py`, `cli.py`, `plugins.py`, `plugin_tools.py`) with clean dependency flow. The scripting API wraps existing data modules without importing Tkinter. CLI routes from `main.py` before GUI launch. Plugins load from `~/.retrosprite/plugins/` with error isolation. Event system uses simple observer pattern.

**Tech Stack:** Python stdlib (`argparse`, `importlib`, `os`, `json`, `glob`), existing project modules (animation, layer, pixel_data, export, project, effects, image_processing).

**Spec:** `docs/superpowers/specs/2026-03-11-batch5-infrastructure-design.md`

---

## Chunk 1: Core Scripting API & Plugin Foundations

### Task 1: PluginTool Base Class (`src/plugin_tools.py`)

**Files:**
- Create: `src/plugin_tools.py`
- Create: `tests/test_plugin_tools.py`

- [ ] **Step 1: Write the failing test**

In `tests/test_plugin_tools.py`:

```python
"""Tests for plugin tool and effect base classes."""
import pytest
from src.plugin_tools import PluginTool


class TestPluginTool:
    def test_default_attributes(self):
        tool = PluginTool()
        assert tool.name == ""
        assert tool.icon is None
        assert tool.cursor == "crosshair"

    def test_on_click_is_noop(self):
        tool = PluginTool()
        # Should not raise
        tool.on_click(None, 0, 0)

    def test_on_drag_is_noop(self):
        tool = PluginTool()
        tool.on_drag(None, 0, 0)

    def test_on_release_is_noop(self):
        tool = PluginTool()
        tool.on_release(None, 0, 0)

    def test_subclass_override(self):
        class StampTool(PluginTool):
            name = "Stamp"
            icon = "stamp.png"
            cursor = "hand2"

            def on_click(self, api, x, y):
                return (x, y)

        stamp = StampTool()
        assert stamp.name == "Stamp"
        assert stamp.icon == "stamp.png"
        assert stamp.on_click(None, 5, 10) == (5, 10)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_plugin_tools.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.plugin_tools'`

- [ ] **Step 3: Write minimal implementation**

In `src/plugin_tools.py`:

```python
"""Base classes for plugin tools and effects."""
from __future__ import annotations


class PluginTool:
    """Base class for custom drawing tools registered by plugins.

    Subclass and override on_click/on_drag/on_release to implement behavior.
    Tool receives pixel coordinates (already converted from screen coords).
    """

    name: str = ""
    icon: str | None = None       # path to 16x16 PNG, or None for text label
    cursor: str = "crosshair"     # Tkinter cursor name

    def on_click(self, api, x: int, y: int) -> None:
        """Called on mouse down."""
        pass

    def on_drag(self, api, x: int, y: int) -> None:
        """Called on mouse move while pressed."""
        pass

    def on_release(self, api, x: int, y: int) -> None:
        """Called on mouse up."""
        pass

    def on_options_bar(self, api, frame) -> None:
        """Optional: add widgets to options bar Frame."""
        pass

    def on_preview(self, api, canvas, x: int, y: int) -> None:
        """Optional: draw preview overlay on canvas."""
        pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_plugin_tools.py -v`
Expected: 5 passed

---

### Task 2: RetroSpriteAPI — Event System Core (`src/scripting.py`)

**Files:**
- Create: `src/scripting.py`
- Create: `tests/test_scripting.py`

- [ ] **Step 1: Write failing tests for event system**

In `tests/test_scripting.py`:

```python
"""Tests for RetroSpriteAPI scripting interface."""
import pytest
from src.animation import AnimationTimeline
from src.palette import Palette
from src.scripting import RetroSpriteAPI


@pytest.fixture
def api():
    timeline = AnimationTimeline(16, 16)
    palette = Palette("Pico-8")
    return RetroSpriteAPI(timeline=timeline, palette=palette, app=None)


class TestEventSystem:
    def test_on_registers_listener(self, api):
        calls = []
        api.on("test_event", lambda e: calls.append(e))
        api.emit("test_event", {"key": "value"})
        assert len(calls) == 1
        assert calls[0]["key"] == "value"

    def test_off_removes_listener(self, api):
        calls = []
        cb = lambda e: calls.append(e)
        api.on("test_event", cb)
        api.off("test_event", cb)
        api.emit("test_event", {})
        assert len(calls) == 0

    def test_off_nonexistent_is_silent(self, api):
        api.off("nonexistent", lambda e: None)  # should not raise

    def test_before_event_cancellable(self, api):
        api.on("before_save", lambda e: False)
        result = api.emit("before_save", {"filepath": "test.retro"})
        assert result is False

    def test_before_event_allows(self, api):
        api.on("before_save", lambda e: True)
        result = api.emit("before_save", {"filepath": "test.retro"})
        assert result is True

    def test_non_before_event_not_cancellable(self, api):
        api.on("after_save", lambda e: False)
        result = api.emit("after_save", {"filepath": "test.retro"})
        assert result is True  # False return ignored for non-before events

    def test_multiple_listeners_fire_in_order(self, api):
        order = []
        api.on("test", lambda e: order.append(1))
        api.on("test", lambda e: order.append(2))
        api.emit("test", {})
        assert order == [1, 2]

    def test_listener_error_does_not_stop_others(self, api):
        calls = []
        api.on("test", lambda e: 1 / 0)  # will raise
        api.on("test", lambda e: calls.append("ok"))
        api.emit("test", {})
        assert calls == ["ok"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_scripting.py::TestEventSystem -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write RetroSpriteAPI with event system**

In `src/scripting.py`:

```python
"""Scripting API for RetroSprite — plugin and CLI interface."""
from __future__ import annotations
import traceback
from typing import Any, Callable

from src.animation import AnimationTimeline, Frame
from src.layer import Layer
from src.palette import Palette
from src.pixel_data import PixelGrid


class RetroSpriteAPI:
    """Central API object for plugins and scripts.

    Provides direct access to internals and high-level convenience methods.
    When app is None (CLI/headless mode), UI registration methods are no-ops.
    """

    def __init__(self, timeline: AnimationTimeline, palette: Palette,
                 app: Any | None = None):
        self.timeline = timeline
        self.palette = palette
        self.app = app
        self._listeners: dict[str, list[Callable]] = {}
        self._plugin_tools: dict[str, Any] = {}
        self._plugin_filters: dict[str, Callable] = {}
        self._plugin_effects: dict[str, dict] = {}
        self._menu_items: list[dict] = []

    # --- Event System ---

    def on(self, event_name: str, callback: Callable) -> None:
        """Subscribe to an event."""
        self._listeners.setdefault(event_name, []).append(callback)

    def off(self, event_name: str, callback: Callable) -> None:
        """Unsubscribe from an event."""
        if event_name in self._listeners:
            try:
                self._listeners[event_name].remove(callback)
            except ValueError:
                pass

    def emit(self, event_name: str, payload: dict) -> bool:
        """Fire event. Returns False if any before_* listener returned False."""
        for cb in self._listeners.get(event_name, []):
            try:
                result = cb(payload)
                if event_name.startswith("before_") and result is False:
                    return False
            except Exception:
                traceback.print_exc()
        return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_scripting.py::TestEventSystem -v`
Expected: 8 passed

---

### Task 3: RetroSpriteAPI — Convenience Methods

**Files:**
- Modify: `src/scripting.py`
- Modify: `tests/test_scripting.py`

- [ ] **Step 1: Write failing tests for convenience methods**

Add to `tests/test_scripting.py`:

```python
class TestProjectIO:
    def test_new_project(self, api):
        api.new_project(32, 32, fps=15)
        assert api.timeline.width == 32
        assert api.timeline.height == 32
        assert api.timeline.fps == 15
        assert api.timeline.frame_count == 1

    def test_save_and_load_project(self, api, tmp_path):
        path = str(tmp_path / "test.retro")
        api.save_project(path)
        api.new_project(8, 8)
        api.load_project(path)
        assert api.timeline.width == 16
        assert api.timeline.height == 16


class TestFrameLayerAccess:
    def test_current_frame_pixels_returns_pixelgrid(self, api):
        result = api.current_frame_pixels()
        assert isinstance(result, PixelGrid)
        assert result.width == 16
        assert result.height == 16

    def test_current_layer_returns_layer(self, api):
        layer = api.current_layer()
        assert isinstance(layer, Layer)

    def test_get_frame_returns_frame_obj(self, api):
        frame = api.get_frame(0)
        assert isinstance(frame, Frame)
        assert frame.width == 16

    def test_add_frame_returns_frame(self, api):
        frame = api.add_frame()
        assert isinstance(frame, Frame)
        assert api.timeline.frame_count == 2

    def test_add_layer_returns_layer(self, api):
        layer = api.add_layer("Test Layer")
        assert isinstance(layer, Layer)
        assert layer.name == "Test Layer"

    def test_remove_frame(self, api):
        api.add_frame()
        assert api.timeline.frame_count == 2
        api.remove_frame(1)
        assert api.timeline.frame_count == 1

    def test_remove_layer(self, api):
        api.add_layer("Extra")
        frame = api.timeline.current_frame_obj()
        assert len(frame.layers) == 2
        api.remove_layer(1)
        assert len(frame.layers) == 1


class TestApplyFilter:
    def test_apply_filter_modifies_pixels(self, api):
        # Set a pixel, apply identity filter
        layer = api.current_layer()
        layer.pixels.set_pixel(0, 0, (255, 0, 0, 255))

        def invert(grid):
            import numpy as np
            result = grid.copy()
            result._pixels[:, :, :3] = 255 - result._pixels[:, :, :3]
            return result

        api.apply_filter(invert)
        pixel = layer.pixels.get_pixel(0, 0)
        assert pixel[0] == 0  # red inverted to 0
        assert pixel[1] == 255  # green inverted to 255

    def test_apply_filter_to_specific_frame_layer(self, api):
        api.add_frame()
        api.add_layer("Layer 2")

        def clear_filter(grid):
            grid_copy = grid.copy()
            grid_copy.clear()
            return grid_copy

        api.apply_filter(clear_filter, frame=0, layer=0)
        # Should not raise


class TestExportMethods:
    def test_export_png(self, api, tmp_path):
        path = str(tmp_path / "out.png")
        api.export_png(path)
        import os
        assert os.path.exists(path)

    def test_export_gif(self, api, tmp_path):
        path = str(tmp_path / "out.gif")
        api.export_gif(path)
        import os
        assert os.path.exists(path)

    def test_export_sheet(self, api, tmp_path):
        path = str(tmp_path / "sheet.png")
        json_path = api.export_sheet(path)
        import os
        assert os.path.exists(path)
        assert os.path.exists(json_path)
        assert json_path.endswith(".json")


class TestRegistration:
    def test_register_menu_item_headless_is_noop(self, api):
        # Should not raise in headless mode
        api.register_menu_item("Test", lambda: None)

    def test_register_filter(self, api):
        api.register_filter("Test Filter", lambda g: g)
        assert "Test Filter" in api._plugin_filters

    def test_register_tool_headless_warns(self, api):
        from src.plugin_tools import PluginTool
        api.register_tool("Test", PluginTool)
        # In headless mode, stored but not displayed
        assert "Test" in api._plugin_tools

    def test_register_effect(self, api):
        api.register_effect("Test FX", lambda p: p, {"size": 4})
        assert "Test FX" in api._plugin_effects

    def test_push_undo_headless_is_noop(self, api):
        # Should not raise
        api.push_undo("Test")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_scripting.py -v`
Expected: FAIL — `AttributeError: 'RetroSpriteAPI' object has no attribute 'new_project'`

- [ ] **Step 3: Add convenience methods to RetroSpriteAPI**

Append to `RetroSpriteAPI` class in `src/scripting.py` (after the `emit` method — do NOT duplicate `on`/`off`/`emit`):

```python
    # --- Convenience: Project I/O ---

    def load_project(self, path: str) -> None:
        """Load a .retro project file."""
        from src.project import load_project as _load
        timeline, palette = _load(path)
        self.timeline = timeline
        self.palette = palette

    def save_project(self, path: str) -> None:
        """Save current project to a .retro file."""
        from src.project import save_project as _save
        _save(path, self.timeline, self.palette)

    def new_project(self, width: int, height: int, fps: int = 12) -> None:
        """Create a new empty project."""
        self.timeline = AnimationTimeline(width, height)
        self.timeline.fps = fps
        self.palette = Palette("Pico-8")

    # --- Convenience: Export ---

    def export_png(self, path: str, frame: int = 0, scale: int = 1,
                   layer: int | str | None = None) -> None:
        """Export a single frame as PNG."""
        if layer is not None:
            frame_obj = self.timeline.get_frame_obj(frame)
            if isinstance(layer, str):
                for i, l in enumerate(frame_obj.layers):
                    if l.name == layer:
                        layer = i
                        break
                else:
                    raise ValueError(f"Layer '{layer}' not found")
            img = frame_obj.layers[layer].pixels.to_pil_image()
        else:
            grid = self.timeline.get_frame(frame)
            img = grid.to_pil_image()
        if scale > 1:
            from PIL import Image
            img = img.resize((img.width * scale, img.height * scale),
                             Image.NEAREST)
        img.save(path)

    def export_gif(self, path: str, scale: int = 1) -> None:
        """Export animation as GIF."""
        self.timeline.export_gif(path, fps=self.timeline.fps, scale=scale)

    def export_sheet(self, path: str, scale: int = 1,
                     columns: int = 0) -> str:
        """Export sprite sheet PNG + JSON sidecar. Returns JSON path."""
        from src.export import save_sprite_sheet
        return save_sprite_sheet(self.timeline, path, scale=scale,
                                 columns=columns)

    # --- Convenience: Frame/Layer Access ---

    def current_frame_pixels(self) -> PixelGrid:
        """Get flattened composite of current frame."""
        return self.timeline.current_frame()

    def current_layer(self) -> Layer:
        """Get the active layer object."""
        return self.timeline.current_frame_obj().active_layer

    def get_frame(self, index: int) -> Frame:
        """Get Frame object by index."""
        return self.timeline.get_frame_obj(index)

    def add_frame(self) -> Frame:
        """Add a new frame and return it."""
        self.timeline.add_frame()
        return self.timeline.get_frame_obj(self.timeline.frame_count - 1)

    def add_layer(self, name: str) -> Layer:
        """Add a new layer to all frames."""
        self.timeline.add_layer_to_all(name)
        return self.timeline.current_frame_obj().active_layer

    def remove_frame(self, index: int) -> None:
        """Remove a frame by index."""
        self.timeline.remove_frame(index)

    def remove_layer(self, index: int) -> None:
        """Remove a layer from all frames."""
        self.timeline.remove_layer_from_all(index)

    # --- Convenience: Image Processing ---

    def apply_filter(self, func: Callable[[PixelGrid], PixelGrid],
                     frame: int | None = None,
                     layer: int | None = None) -> None:
        """Apply a filter function to a layer's pixels.

        If frame/layer are None, applies to current.
        In GUI mode: automatically pushes undo state before applying.
        Selection-aware: if a selection exists in GUI mode, only the selected
        region is passed to func and the result is masked back.
        """
        self.push_undo("Apply Filter")
        f_idx = frame if frame is not None else self.timeline.current_index
        frame_obj = self.timeline.get_frame_obj(f_idx)
        l_idx = layer if layer is not None else frame_obj.active_layer_index
        target_layer = frame_obj.layers[l_idx]

        # Selection-aware: if GUI has a selection, apply only to selected pixels
        selection = None
        if self.app is not None:
            selection = getattr(self.app, '_selection_pixels', None)

        if selection:
            import numpy as np
            pixels = target_layer.pixels
            # Extract bounding box of selection
            xs = [p[0] for p in selection]
            ys = [p[1] for p in selection]
            x0, x1 = min(xs), max(xs) + 1
            y0, y1 = min(ys), max(ys) + 1
            # Create sub-grid from bounding box
            sub = PixelGrid(x1 - x0, y1 - y0)
            sub._pixels = pixels._pixels[y0:y1, x0:x1].copy()
            # Apply filter to sub-grid
            result_sub = func(sub)
            # Mask back only selected pixels
            for sx, sy in selection:
                lx, ly = sx - x0, sy - y0
                if 0 <= lx < result_sub.width and 0 <= ly < result_sub.height:
                    pixels._pixels[sy, sx] = result_sub._pixels[ly, lx]
        else:
            result = func(target_layer.pixels)
            target_layer.pixels._pixels = result._pixels.copy()

    def apply_effect(self, layer_index: int, effect_type: str,
                     params: dict) -> None:
        """Add a LayerEffect to the specified layer."""
        self.push_undo("Apply Effect")
        from src.effects import LayerEffect
        frame_obj = self.timeline.current_frame_obj()
        layer = frame_obj.layers[layer_index]
        effect = LayerEffect(effect_type, params)
        layer.effects.append(effect)

    # --- Undo (GUI mode only, no-op in headless) ---

    def push_undo(self, label: str = "Script Action") -> None:
        """Push undo state. No-op in headless mode."""
        if self.app is not None and hasattr(self.app, '_push_undo'):
            self.app._push_undo()

    # --- Plugin Registration ---

    def register_menu_item(self, label: str, callback: Callable,
                           submenu: str = "Plugins") -> None:
        """Register a menu item. No-op in headless mode."""
        if self.app is None:
            import warnings
            warnings.warn("register_menu_item is a no-op in headless mode")
            return
        self._menu_items.append({
            "label": label, "callback": callback, "submenu": submenu
        })

    def register_filter(self, name: str,
                        func: Callable[[PixelGrid], PixelGrid]) -> None:
        """Register a custom filter. Available in both GUI and headless."""
        self._plugin_filters[name] = func

    def register_tool(self, name: str, tool_class: type) -> None:
        """Register a custom drawing tool."""
        self._plugin_tools[name] = tool_class
        if self.app is None:
            import warnings
            warnings.warn("register_tool: tool UI unavailable in headless mode")

    def register_effect(self, name: str, apply_func: Callable,
                        default_params: dict) -> None:
        """Register a custom effect for the Effects Dialog."""
        self._plugin_effects[name] = {
            "apply_func": apply_func,
            "default_params": default_params,
        }
```

- [ ] **Step 4: Run all scripting tests**

Run: `python -m pytest tests/test_scripting.py -v`
Expected: All tests pass (8 event + 17 convenience = 25 tests)

---

### Task 4: Plugin Loader (`src/plugins.py`)

**Files:**
- Create: `src/plugins.py`
- Add to: `tests/test_scripting.py`

- [ ] **Step 1: Write failing tests for plugin loading**

Add to `tests/test_scripting.py`:

```python
import os
import tempfile
from src.plugins import discover_plugins, load_plugin, load_all_plugins


class TestPluginDiscovery:
    def test_discover_empty_dir(self, tmp_path):
        result = discover_plugins(str(tmp_path))
        assert result == []

    def test_discover_finds_py_files(self, tmp_path):
        (tmp_path / "plugin_a.py").write_text("pass")
        (tmp_path / "plugin_b.py").write_text("pass")
        (tmp_path / "not_a_plugin.txt").write_text("pass")
        result = discover_plugins(str(tmp_path))
        assert len(result) == 2
        assert all(r.endswith(".py") for r in result)

    def test_discover_nonexistent_dir(self):
        result = discover_plugins("/nonexistent/dir/12345")
        assert result == []


class TestPluginLoading:
    def test_load_valid_plugin(self, api, tmp_path):
        plugin_code = '''
PLUGIN_INFO = {"name": "Test Plugin", "version": "1.0"}

def register(api):
    api.register_filter("Test Filter", lambda g: g)
'''
        plugin_file = tmp_path / "test_plugin.py"
        plugin_file.write_text(plugin_code)
        info = load_plugin(str(plugin_file), api)
        assert info is not None
        assert info["name"] == "Test Plugin"
        assert "Test Filter" in api._plugin_filters

    def test_load_plugin_without_register(self, api, tmp_path):
        plugin_file = tmp_path / "bad_plugin.py"
        plugin_file.write_text("x = 1")
        info = load_plugin(str(plugin_file), api)
        assert info is None  # no register function

    def test_load_plugin_with_error(self, api, tmp_path):
        plugin_file = tmp_path / "crash_plugin.py"
        plugin_file.write_text("def register(api):\n    raise RuntimeError('boom')")
        info = load_plugin(str(plugin_file), api)
        assert info is None  # error isolated

    def test_load_all_respects_disabled(self, api, tmp_path):
        import json
        (tmp_path / "good.py").write_text(
            "PLUGIN_INFO = {'name': 'Good'}\ndef register(api): pass"
        )
        (tmp_path / "bad.py").write_text(
            "PLUGIN_INFO = {'name': 'Bad'}\ndef register(api): pass"
        )
        config = tmp_path / "plugins.json"
        config.write_text(json.dumps({"disabled": ["bad.py"]}))
        result = load_all_plugins(api, plugin_dir=str(tmp_path),
                                  config_path=str(config))
        names = [p["name"] for p in result]
        assert "Good" in names
        assert "Bad" not in names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_scripting.py::TestPluginDiscovery tests/test_scripting.py::TestPluginLoading -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.plugins'`

- [ ] **Step 3: Implement plugin loader**

In `src/plugins.py`:

```python
"""Plugin discovery and loading for RetroSprite."""
from __future__ import annotations
import importlib.util
import json
import os
import sys
import traceback


DEFAULT_PLUGIN_DIR = os.path.join(os.path.expanduser("~"), ".retrosprite", "plugins")
DEFAULT_CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".retrosprite", "plugins.json")


def discover_plugins(plugin_dir: str = DEFAULT_PLUGIN_DIR) -> list[str]:
    """Return list of .py file paths in plugin directory."""
    if not os.path.isdir(plugin_dir):
        return []
    return sorted(
        os.path.join(plugin_dir, f)
        for f in os.listdir(plugin_dir)
        if f.endswith(".py") and not f.startswith("_")
    )


def load_plugin(path: str, api) -> dict | None:
    """Import a plugin module, call register(api), return plugin info.

    Returns None if the plugin has no register() function or raises an error.
    """
    module_name = os.path.splitext(os.path.basename(path))[0]
    spec = importlib.util.spec_from_file_location(
        f"retrosprite_plugin_{module_name}", path
    )
    if spec is None or spec.loader is None:
        return None
    try:
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    except Exception:
        traceback.print_exc()
        return None

    register_fn = getattr(module, "register", None)
    if register_fn is None:
        return None

    try:
        register_fn(api)
    except Exception:
        traceback.print_exc()
        return None

    info = getattr(module, "PLUGIN_INFO", {"name": module_name})
    info.setdefault("name", module_name)
    info["_module"] = module
    info["_path"] = path
    return info


def load_all_plugins(api, plugin_dir: str = DEFAULT_PLUGIN_DIR,
                     config_path: str = DEFAULT_CONFIG_PATH) -> list[dict]:
    """Discover and load all plugins, respecting disabled list."""
    disabled = set()
    if os.path.exists(config_path):
        try:
            with open(config_path) as f:
                config = json.load(f)
            disabled = set(config.get("disabled", []))
        except (json.JSONDecodeError, IOError):
            pass

    results = []
    for path in discover_plugins(plugin_dir):
        filename = os.path.basename(path)
        if filename in disabled:
            continue
        info = load_plugin(path, api)
        if info is not None:
            results.append(info)
    return results


def unload_all_plugins(plugins: list[dict], api) -> None:
    """Call unregister() on all loaded plugins that support it."""
    for info in plugins:
        module = info.get("_module")
        if module is None:
            continue
        unregister_fn = getattr(module, "unregister", None)
        if unregister_fn is not None:
            try:
                unregister_fn(api)
            except Exception:
                traceback.print_exc()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_scripting.py -v`
Expected: All tests pass

---

### Task 5: CLI Entry Point (`src/cli.py`)

**Files:**
- Create: `src/cli.py`
- Add to: `tests/test_scripting.py`

- [ ] **Step 1: Write failing tests for CLI**

Add to `tests/test_scripting.py`:

```python
from src.cli import build_parser


class TestCLIParser:
    def test_export_png_args(self):
        parser = build_parser()
        args = parser.parse_args(["export", "input.retro", "output.png",
                                  "--scale", "2", "--frame", "3"])
        assert args.command == "export"
        assert args.input == "input.retro"
        assert args.output == "output.png"
        assert args.scale == 2
        assert args.frame == 3

    def test_export_format_override(self):
        parser = build_parser()
        args = parser.parse_args(["export", "in.retro", "out.png",
                                  "--format", "gif"])
        assert args.format == "gif"

    def test_batch_args(self):
        parser = build_parser()
        args = parser.parse_args(["batch", "input_dir", "output_dir",
                                  "--format", "png", "--scale", "4"])
        assert args.command == "batch"
        assert args.input_dir == "input_dir"
        assert args.output_dir == "output_dir"
        assert args.format == "png"
        assert args.scale == 4

    def test_run_args(self):
        parser = build_parser()
        args = parser.parse_args(["run", "script.py", "--", "arg1", "arg2"])
        assert args.command == "run"
        assert args.script == "script.py"
        assert args.script_args == ["arg1", "arg2"]

    def test_info_args(self):
        parser = build_parser()
        args = parser.parse_args(["info", "project.retro"])
        assert args.command == "info"
        assert args.input == "project.retro"


class TestCLIExport:
    def test_cli_export_png(self, tmp_path):
        from src.cli import cmd_export
        from src.animation import AnimationTimeline
        from src.palette import Palette

        timeline = AnimationTimeline(8, 8)
        palette = Palette("Pico-8")
        from src.project import save_project
        proj_path = str(tmp_path / "test.retro")
        save_project(proj_path, timeline, palette)

        out_path = str(tmp_path / "out.png")
        result = cmd_export(proj_path, out_path, format=None, scale=1,
                           frame=0, columns=0, layer=None)
        assert result == 0
        assert os.path.exists(out_path)

    def test_cli_export_gif(self, tmp_path):
        from src.cli import cmd_export
        from src.animation import AnimationTimeline
        from src.palette import Palette
        from src.project import save_project

        timeline = AnimationTimeline(8, 8)
        palette = Palette("Pico-8")
        proj_path = str(tmp_path / "test.retro")
        save_project(proj_path, timeline, palette)

        out_path = str(tmp_path / "out.gif")
        result = cmd_export(proj_path, out_path, format=None, scale=1,
                           frame=0, columns=0, layer=None)
        assert result == 0
        assert os.path.exists(out_path)

    def test_cli_export_sheet(self, tmp_path):
        from src.cli import cmd_export
        from src.animation import AnimationTimeline
        from src.palette import Palette
        from src.project import save_project

        timeline = AnimationTimeline(8, 8)
        palette = Palette("Pico-8")
        proj_path = str(tmp_path / "test.retro")
        save_project(proj_path, timeline, palette)

        out_path = str(tmp_path / "sheet.json")
        result = cmd_export(proj_path, out_path, format="sheet", scale=1,
                           frame=0, columns=0, layer=None)
        assert result == 0

    def test_cli_export_batch(self, tmp_path):
        from src.cli import cmd_batch
        from src.animation import AnimationTimeline
        from src.palette import Palette
        from src.project import save_project

        # Create two project files
        in_dir = tmp_path / "input"
        in_dir.mkdir()
        out_dir = tmp_path / "output"
        for name in ["a", "b"]:
            timeline = AnimationTimeline(8, 8)
            palette = Palette("Pico-8")
            save_project(str(in_dir / f"{name}.retro"), timeline, palette)

        result = cmd_batch(str(in_dir), str(out_dir), "*.retro",
                          format="png", scale=1)
        assert result == 0
        assert os.path.exists(str(out_dir / "a.png"))
        assert os.path.exists(str(out_dir / "b.png"))

    def test_cli_info(self, tmp_path, capsys):
        from src.cli import cmd_info
        from src.animation import AnimationTimeline
        from src.palette import Palette
        from src.project import save_project

        timeline = AnimationTimeline(32, 32)
        timeline.fps = 12
        palette = Palette("Pico-8")
        proj_path = str(tmp_path / "hero.retro")
        save_project(proj_path, timeline, palette)

        result = cmd_info(proj_path)
        assert result == 0
        captured = capsys.readouterr()
        assert "32x32" in captured.out
        assert "12 fps" in captured.out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_scripting.py::TestCLIParser tests/test_scripting.py::TestCLIExport -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.cli'`

- [ ] **Step 3: Implement CLI**

In `src/cli.py`:

```python
"""CLI entry point for RetroSprite headless operations."""
from __future__ import annotations
import argparse
import glob
import os
import sys


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for CLI subcommands."""
    parser = argparse.ArgumentParser(
        prog="retrosprite",
        description="RetroSprite CLI — export, batch process, and script"
    )
    sub = parser.add_subparsers(dest="command")

    # export
    exp = sub.add_parser("export", help="Export a single project")
    exp.add_argument("input", help="Input .retro file")
    exp.add_argument("output", help="Output file path")
    exp.add_argument("--format", choices=["png", "gif", "sheet", "frames"],
                     default=None, help="Output format (auto-detect if omitted)")
    exp.add_argument("--scale", type=int, default=1, help="Scale factor (1-8)")
    exp.add_argument("--frame", type=int, default=0, help="Frame index (for png)")
    exp.add_argument("--columns", type=int, default=0,
                     help="Sheet columns (0=auto)")
    exp.add_argument("--layer", default=None, help="Layer name or index")

    # batch
    bat = sub.add_parser("batch", help="Batch process a directory")
    bat.add_argument("input_dir", help="Input directory")
    bat.add_argument("output_dir", help="Output directory")
    bat.add_argument("--pattern", default="*.retro", help="Glob pattern")
    bat.add_argument("--format", choices=["png", "gif", "sheet"],
                     required=True, help="Output format")
    bat.add_argument("--scale", type=int, default=1, help="Scale factor")

    # run
    run = sub.add_parser("run", help="Execute a script")
    run.add_argument("script", help="Script file path")
    run.add_argument("script_args", nargs="*", help="Script arguments")

    # info
    inf = sub.add_parser("info", help="Print project metadata")
    inf.add_argument("input", help="Input .retro file")

    return parser


def _detect_format(output_path: str) -> str:
    """Auto-detect format from file extension."""
    ext = os.path.splitext(output_path)[1].lower()
    if ext == ".gif":
        return "gif"
    elif ext == ".json":
        return "sheet"
    elif ext == ".png":
        return "png"
    return "png"


def _parse_layer(layer_arg: str | None) -> int | str | None:
    """Parse --layer argument as int index or string name."""
    if layer_arg is None:
        return None
    try:
        return int(layer_arg)
    except ValueError:
        return layer_arg


def cmd_export(input_path: str, output_path: str, format: str | None,
               scale: int, frame: int, columns: int,
               layer: str | None) -> int:
    """Export a single project. Returns 0 on success, 1 on error."""
    from src.scripting import RetroSpriteAPI
    from src.animation import AnimationTimeline
    from src.palette import Palette
    from src.project import load_project

    try:
        timeline, palette = load_project(input_path)
    except Exception as e:
        print(f"Error loading {input_path}: {e}", file=sys.stderr)
        return 1

    api = RetroSpriteAPI(timeline=timeline, palette=palette, app=None)
    fmt = format or _detect_format(output_path)
    parsed_layer = _parse_layer(layer)

    try:
        if fmt == "png":
            api.export_png(output_path, frame=frame, scale=scale,
                           layer=parsed_layer)
        elif fmt == "gif":
            api.export_gif(output_path, scale=scale)
        elif fmt == "sheet":
            # save_sprite_sheet expects a .png path, derives .json sidecar
            sheet_path = output_path
            if sheet_path.lower().endswith(".json"):
                sheet_path = sheet_path[:-5] + ".png"
            api.export_sheet(sheet_path, scale=scale, columns=columns)
        elif fmt == "frames":
            base, ext = os.path.splitext(output_path)
            if not ext:
                ext = ".png"
            for i in range(timeline.frame_count):
                frame_path = f"{base}_{i:03d}{ext}"
                api.export_png(frame_path, frame=i, scale=scale,
                               layer=parsed_layer)
        print(f"Exported: {output_path}")
        return 0
    except Exception as e:
        print(f"Export error: {e}", file=sys.stderr)
        return 1


def cmd_batch(input_dir: str, output_dir: str, pattern: str,
              format: str, scale: int) -> int:
    """Batch export all matching files. Returns 0 on success."""
    files = sorted(glob.glob(os.path.join(input_dir, pattern)))
    if not files:
        print(f"No files matching '{pattern}' in {input_dir}")
        return 1

    os.makedirs(output_dir, exist_ok=True)
    total = len(files)
    errors = 0

    for idx, filepath in enumerate(files, 1):
        basename = os.path.splitext(os.path.basename(filepath))[0]
        ext = {"png": ".png", "gif": ".gif", "sheet": ".png"}[format]
        output_path = os.path.join(output_dir, basename + ext)
        print(f"[{idx}/{total}] Exporting {os.path.basename(filepath)} -> "
              f"{os.path.basename(output_path)}")
        result = cmd_export(filepath, output_path, format=format,
                           scale=scale, frame=0, columns=0, layer=None)
        if result != 0:
            errors += 1

    if errors:
        print(f"\n{errors}/{total} exports failed")
        return 1
    print(f"\nAll {total} exports succeeded")
    return 0


def cmd_run(script_path: str, script_args: list[str]) -> int:
    """Execute a script with headless API. Returns 0 on success."""
    from src.scripting import RetroSpriteAPI
    from src.animation import AnimationTimeline
    from src.palette import Palette

    timeline = AnimationTimeline(32, 32)
    palette = Palette("Pico-8")
    api = RetroSpriteAPI(timeline=timeline, palette=palette, app=None)

    # Set up sys.argv for the script
    old_argv = sys.argv
    sys.argv = [script_path] + script_args

    try:
        with open(script_path) as f:
            code = f.read()
        exec(code, {"api": api, "__name__": "__main__",
                     "__file__": script_path})
        return 0
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 1
    except Exception as e:
        print(f"Script error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1
    finally:
        sys.argv = old_argv


def cmd_info(input_path: str) -> int:
    """Print project metadata. Returns 0 on success."""
    from src.project import load_project

    try:
        timeline, palette = load_project(input_path)
    except Exception as e:
        print(f"Error loading {input_path}: {e}", file=sys.stderr)
        return 1

    basename = os.path.basename(input_path)
    frame_obj = timeline.get_frame_obj(0)
    layer_names = [l.name for l in frame_obj.layers]

    # Check for effects
    effects_info = []
    for layer in frame_obj.layers:
        if hasattr(layer, 'effects') and layer.effects:
            fx_names = [e.effect_type for e in layer.effects]
            effects_info.append(f"{layer.name} has {', '.join(fx_names)}")

    # Check for tilesets
    ts_names = list(getattr(timeline, 'tilesets', {}).keys())

    print(f"Project: {basename} (v3)")
    print(f"Size: {timeline.width}x{timeline.height}, {timeline.fps} fps")
    print(f"Frames: {timeline.frame_count}")
    print(f"Layers: {len(layer_names)} ({', '.join(layer_names)})")
    if effects_info:
        print(f"Effects: {'; '.join(effects_info)}")
    else:
        print("Effects: none")
    if ts_names:
        print(f"Tilesets: {', '.join(ts_names)}")
    else:
        print("Tilesets: none")
    print(f"Palette: \"{palette.name}\" ({len(palette.colors)} colors)")
    return 0


def main() -> int:
    """CLI main entry point."""
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 1

    if args.command == "export":
        return cmd_export(args.input, args.output, args.format, args.scale,
                         args.frame, args.columns, args.layer)
    elif args.command == "batch":
        return cmd_batch(args.input_dir, args.output_dir, args.pattern,
                        args.format, args.scale)
    elif args.command == "run":
        return cmd_run(args.script, args.script_args)
    elif args.command == "info":
        return cmd_info(args.input)

    return 1
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_scripting.py -v`
Expected: All tests pass

---

### Task 6: main.py CLI Routing

**Files:**
- Modify: `main.py` (lines 22-23)

- [ ] **Step 1: Write failing test for CLI routing**

Add to `tests/test_scripting.py`:

```python
class TestMainRouting:
    def test_cli_subcommands_recognized(self):
        """Verify the subcommand list matches CLI parser."""
        expected = {"export", "batch", "run", "info"}
        from src.cli import build_parser
        parser = build_parser()
        # Subcommands are the choices of the 'command' dest
        assert expected == set(parser._subparsers._actions[1].choices.keys())
```

- [ ] **Step 2: Run test to verify it passes (sanity check)**

Run: `python -m pytest tests/test_scripting.py::TestMainRouting -v`
Expected: PASS

- [ ] **Step 3: Modify main.py to route CLI subcommands**

Change `main.py` lines 22-23 from:

```python
if __name__ == "__main__":
    main()
```

To:

```python
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] in ("export", "batch", "run", "info"):
        from src.cli import main as cli_main
        sys.exit(cli_main())
    else:
        main()
```

- [ ] **Step 4: Verify existing tests still pass**

Run: `python -m pytest tests/ -v --tb=short`
Expected: All tests pass (293 existing + new tests)

---

## Chunk 2: GUI Integration

### Task 7: App.py — Create API & Load Plugins

**Files:**
- Modify: `src/app.py` (lines 26-28, ~96, ~159)

- [ ] **Step 1: Add imports to app.py**

At `src/app.py` line 28 (after `from src.keybindings import KeybindingsManager`), add:

```python
from src.scripting import RetroSpriteAPI
from src.plugins import load_all_plugins
```

- [ ] **Step 2: Create API instance after timeline/palette init**

After the `_tools` dict closing `}` (around line 95, after `"Lasso": LassoTool(),`), add:

```python
        # Scripting API
        self.api = RetroSpriteAPI(
            timeline=self.timeline, palette=self.palette, app=self
        )
```

- [ ] **Step 3: Load plugins after UI is built**

After line 159 (`self._refresh_all()`), add:

```python
        # Load plugins
        self._plugins = load_all_plugins(self.api)
        self._build_plugins_menu()
```

- [ ] **Step 4: Add _build_plugins_menu method**

Add to `RetroSpriteApp` class (after `_build_menu`, around line 265):

```python
    def _build_plugins_menu(self):
        """Create Plugins submenu with registered plugin menu items."""
        if (not self._plugins and not self.api._plugin_filters
                and not self.api._menu_items):
            return
        menubar = self.root.nametowidget(self.root.cget("menu"))
        plugins_menu = tk.Menu(menubar, tearoff=0,
                               bg=BG_PANEL, fg=TEXT_PRIMARY,
                               activebackground=ACCENT_CYAN,
                               activeforeground=BG_DEEP)

        # Plugin-registered menu items
        if self.api._menu_items:
            for item in self.api._menu_items:
                plugins_menu.add_command(
                    label=item["label"],
                    command=item["callback"]
                )
            plugins_menu.add_separator()

        # Plugin-registered filters
        if self.api._plugin_filters:
            for name, func in self.api._plugin_filters.items():
                plugins_menu.add_command(
                    label=f"Filter: {name}",
                    command=lambda f=func: self._apply_plugin_filter(f)
                )
            plugins_menu.add_separator()

        # Plugin info
        for plugin in self._plugins:
            plugins_menu.add_command(
                label=f"  {plugin['name']}",
                state="disabled"
            )

        if plugins_menu.index("end") is not None:
            menubar.add_cascade(label="Plugins", menu=plugins_menu)

    def _apply_plugin_filter(self, func):
        """Apply a plugin-registered filter to current layer."""
        self._push_undo()
        layer = self.timeline.current_frame_obj().active_layer
        result = func(layer.pixels)
        layer.pixels._pixels = result._pixels.copy()
        self._refresh_canvas()
```

- [ ] **Step 5: Verify all tests still pass**

Run: `python -m pytest tests/ -v --tb=short`
Expected: All tests pass

---

### Task 8: Event Emissions in App.py

**Files:**
- Modify: `src/app.py` (multiple methods)

- [ ] **Step 1: Add event emissions to _save_project**

Replace `_save_project` method (line 1949) with:

```python
    def _save_project(self):
        """Save to current project path, or prompt for path."""
        if self._project_path:
            if not self.api.emit("before_save", {"filepath": self._project_path}):
                return
            try:
                save_project(self._project_path, self.timeline, self.palette)
                self._dirty = False
                self._update_status("Project saved")
                self.api.emit("after_save", {"filepath": self._project_path})
            except Exception as e:
                show_error(self.root, "Save Error", str(e))
        else:
            self._save_project_as()
```

- [ ] **Step 2: Add event emissions to _export_gif**

Replace `_export_gif` method (line 1751) with:

```python
    def _export_gif(self):
        path = ask_export_gif(self.root)
        if not path:
            return
        if not self.api.emit("before_export", {"filepath": path, "format": "gif"}):
            return
        self._update_status("Exporting GIF...")

        def worker():
            try:
                duration = self.right_panel.animation_preview.frame_duration_ms
                self.timeline.export_gif(path, fps=self.timeline.fps, scale=4,
                                         duration_ms=duration)
                self.root.after(0, lambda: self.api.emit(
                    "after_export", {"filepath": path, "format": "gif"}))
                self.root.after(0, lambda: show_info(self.root, "Export",
                                                      f"GIF saved to {path}"))
            except Exception as e:
                self.root.after(0, lambda: show_error(self.root, "Export Error",
                                                       str(e)))
            finally:
                self.root.after(0, lambda: self._update_status(""))

        import threading
        threading.Thread(target=worker, daemon=True).start()
```

- [ ] **Step 3: Add event emissions for frame/layer/tool changes**

Find each of these methods in `app.py` and add the appropriate `self.api.emit(...)` call:

**Frame change** — wherever `self.timeline.set_current(...)` is called (search for `set_current`), add after the call:
```python
        self.api.emit("frame_change", {
            "frame_index": <new_index>,
            "frame": self.timeline.current_frame_obj()
        })
```

**Layer change** — wherever `frame.active_layer_index = ...` is set for user-driven layer switches, add:
```python
        self.api.emit("layer_change", {
            "layer_index": <new_index>,
            "layer": self.timeline.current_frame_obj().active_layer
        })
```

**Tool change** — in the tool selection callback (where `self.current_tool_name` is set), add:
```python
        self.api.emit("tool_change", {"tool_name": self.current_tool_name})
```

**Frame add/remove** — in add/duplicate/remove frame methods, add:
```python
        self.api.emit("frame_added", {"frame_index": <index>})
        # or
        self.api.emit("frame_removed", {"frame_index": <index>})
```

**Layer add/remove/merge** — in layer operations, add:
```python
        self.api.emit("layer_added", {"layer_index": <index>, "layer": <layer>})
        # or
        self.api.emit("layer_removed", {"layer_index": <index>})
        # or
        self.api.emit("layer_merged", {"layer_index": <index>})
```

**Load project** — in `_open_project`, wrap with before/after:
```python
        if not self.api.emit("before_load", {"filepath": path}):
            return
        # ... existing load code ...
        self.api.emit("after_load", {"filepath": path})
```

**Palette change** — where `self.palette.select(...)` is called for user color picks, add:
```python
        self.api.emit("palette_change", {
            "color": self.palette.selected_color,
            "index": self.palette.selected_index
        })
```

- [ ] **Step 4: Add plugin unload on close**

In `_on_close` method (line 1934), add before `self.root.destroy()`:
```python
        from src.plugins import unload_all_plugins
        unload_all_plugins(self._plugins, self.api)
```

- [ ] **Step 5: Verify all tests pass**

Run: `python -m pytest tests/ -v --tb=short`
Expected: All tests pass

---

### Task 9: Plugin Tool Dispatch in App.py

**Files:**
- Modify: `src/app.py` (lines 616, 721, 821)

- [ ] **Step 1: Add plugin tool dispatch to _on_canvas_click**

At `_on_canvas_click` (line 616), after the rotation mode check (line 620) and before the pasting check (line 622), add:

```python
        # Plugin tool dispatch
        if self.current_tool_name in self.api._plugin_tools:
            tool_cls = self.api._plugin_tools[self.current_tool_name]
            if not hasattr(self, '_active_plugin_tool') or \
               not isinstance(self._active_plugin_tool, tool_cls):
                self._active_plugin_tool = tool_cls()
            self._active_plugin_tool.on_click(self.api, x, y)
            self._refresh_canvas()
            return
```

- [ ] **Step 2: Add plugin tool dispatch to _on_canvas_drag**

At the top of `_on_canvas_drag` (line 721), add:

```python
        if self.current_tool_name in self.api._plugin_tools:
            if hasattr(self, '_active_plugin_tool') and self._active_plugin_tool:
                self._active_plugin_tool.on_drag(self.api, x, y)
                self._refresh_canvas()
            return
```

- [ ] **Step 3: Add plugin tool dispatch to _on_canvas_release**

At the top of `_on_canvas_release` (line 821), add:

```python
        if self.current_tool_name in self.api._plugin_tools:
            if hasattr(self, '_active_plugin_tool') and self._active_plugin_tool:
                self._active_plugin_tool.on_release(self.api, x, y)
                self._refresh_canvas()
            return
```

- [ ] **Step 4: Verify all tests pass**

Run: `python -m pytest tests/ -v --tb=short`
Expected: All tests pass

---

### Task 10: Plugin Tools in Toolbar

**Files:**
- Modify: `src/ui/toolbar.py` (after line 56)

- [ ] **Step 1: Add method to render plugin tools**

Add to `Toolbar` class (after the `__init__` method):

```python
    def add_plugin_tools(self, plugin_tools: dict):
        """Add plugin tools to toolbar after a separator."""
        if not plugin_tools:
            return
        # Add separator
        sep = tk.Frame(self, height=2, bg=BORDER)
        sep.pack(fill="x", padx=6, pady=4)

        for tool_name, tool_cls in plugin_tools.items():
            btn = tk.Button(
                self, text=tool_name[:3], width=4, height=2,
                bg=BUTTON_BG, activebackground=BUTTON_HOVER,
                fg=TEXT_PRIMARY, font=("Consolas", 8),
                relief="flat", bd=0,
                command=lambda n=tool_name: self.select_tool(n)
            )
            btn.pack(padx=4, pady=2)
            self._buttons[tool_name] = btn
            btn.bind("<Enter>", lambda e, n=tool_name: self._show_tooltip(e, n))
            btn.bind("<Leave>", lambda e: self._hide_tooltip())
```

- [ ] **Step 2: Wire from app.py after plugin load**

In app.py, after `self._build_plugins_menu()` (added in Task 7), add:

```python
        if self.api._plugin_tools:
            self.toolbar.add_plugin_tools(self.api._plugin_tools)
```

- [ ] **Step 3: Verify all tests pass**

Run: `python -m pytest tests/ -v --tb=short`
Expected: All tests pass

---

### Task 11: Plugin Effects in Effects Dialog

**Files:**
- Modify: `src/ui/effects_dialog.py` (lines 39, 58, 129)

- [ ] **Step 1: Add function to include plugin effects**

In `effects_dialog.py`, after `_TYPE_TO_LABEL` (line 39), add:

```python
def get_all_effect_types(api=None):
    """Return EFFECT_TYPES + plugin-registered effects."""
    all_types = list(EFFECT_TYPES)
    if api and hasattr(api, '_plugin_effects'):
        for name, info in api._plugin_effects.items():
            all_types.append((name, f"plugin_{name}", dict(info["default_params"])))
    return all_types
```

- [ ] **Step 2: Update EffectsDialog.__init__ to accept api parameter**

Change `src/ui/effects_dialog.py` line 58 from:

```python
    def __init__(self, parent, layer, render_callback):
```

To:

```python
    def __init__(self, parent, layer, render_callback, api=None):
```

Add after line 68 (`self.render_callback = render_callback`):

```python
        self._api = api
```

- [ ] **Step 3: Use get_all_effect_types in dropdown builder**

Change `src/ui/effects_dialog.py` line 129 from:

```python
        for label, etype, defaults in EFFECT_TYPES:
```

To:

```python
        for label, etype, defaults in get_all_effect_types(self._api):
```

- [ ] **Step 4: Update app.py to pass API to effects dialog**

Find where `EffectsDialog` is instantiated in app.py (search for `EffectsDialog(`) and add `api=self.api` as the last argument. For example, change:

```python
EffectsDialog(self.root, layer, self._refresh_canvas)
```

To:

```python
EffectsDialog(self.root, layer, self._refresh_canvas, api=self.api)
```

- [ ] **Step 5: Verify all tests pass**

Run: `python -m pytest tests/ -v --tb=short`
Expected: All tests pass

---

### Task 12: CLI Script Runner Integration Test

**Files:**
- Add to: `tests/test_scripting.py`

- [ ] **Step 1: Write integration tests for script execution**

Add to `tests/test_scripting.py`:

```python
class TestCLIRun:
    def test_run_script_with_api(self, tmp_path):
        from src.cli import cmd_run
        from src.animation import AnimationTimeline
        from src.palette import Palette
        from src.project import save_project

        # Create a project
        timeline = AnimationTimeline(8, 8)
        palette = Palette("Pico-8")
        proj_path = str(tmp_path / "test.retro")
        save_project(proj_path, timeline, palette)

        # Write a script that loads and exports
        script = tmp_path / "test_script.py"
        out_png = str(tmp_path / "script_out.png")
        script.write_text(
            f'api.load_project(r"{proj_path}")\n'
            f'api.export_png(r"{out_png}")\n'
        )

        result = cmd_run(str(script), [])
        assert result == 0
        assert os.path.exists(out_png)

    def test_run_script_error_returns_1(self, tmp_path):
        from src.cli import cmd_run
        script = tmp_path / "bad_script.py"
        script.write_text("raise ValueError('test error')")
        result = cmd_run(str(script), [])
        assert result == 1
```

- [ ] **Step 2: Run test to verify it passes**

Run: `python -m pytest tests/test_scripting.py::TestCLIRun -v`
Expected: 2 passed

---

### Task 13: Full Test Suite Verification

**Files:**
- All files

- [ ] **Step 1: Run full test suite**

Run: `python -m pytest tests/ -v --tb=short`
Expected: All tests pass (293 existing + ~40 new = 333+ tests)

- [ ] **Step 2: Verify CLI works end-to-end**

Test the CLI help output:
```
python main.py export --help
```

- [ ] **Step 3: Manual smoke test of GUI**

Launch `python main.py` and verify:
1. App launches without errors
2. Plugins menu appears (may be empty if no plugins installed)
3. Effects dialog still works
4. All tools still work

---

## Summary

| File | Type | Purpose |
|------|------|---------|
| `src/plugin_tools.py` | New | PluginTool base class |
| `src/scripting.py` | New | RetroSpriteAPI + event system |
| `src/plugins.py` | New | Plugin discovery & loading |
| `src/cli.py` | New | CLI with argparse subcommands |
| `tests/test_plugin_tools.py` | New | 5 tests for PluginTool |
| `tests/test_scripting.py` | New | ~40 tests for API, CLI, plugins, events |
| `main.py` | Modified | CLI routing before GUI |
| `src/app.py` | Modified | Create API, load plugins, emit events, plugin dispatch |
| `src/ui/toolbar.py` | Modified | Plugin tool buttons |
| `src/ui/effects_dialog.py` | Modified | Plugin effects in dropdown |

**Total:** 4 new source files, 2 new test files, 4 modified files, ~45 new tests.
