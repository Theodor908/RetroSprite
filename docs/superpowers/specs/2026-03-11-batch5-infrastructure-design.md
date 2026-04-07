# Batch 5: Infrastructure — Design Spec

**Date:** 2026-03-11
**Status:** Approved
**Features:** Scripting API, CLI/Batch Export, Plugin System

---

## 1. Scripting API

### RetroSpriteAPI Class (`src/scripting.py`)

The central API object passed to plugins and scripts. Provides both direct access to internals and high-level convenience methods.

```python
class RetroSpriteAPI:
    # Direct access (power users)
    timeline: AnimationTimeline
    palette: Palette
    app: RetroSpriteApp | None  # None in headless/CLI mode

    # --- Convenience: Project I/O ---
    def load_project(path: str) -> None
    def save_project(path: str) -> None
    def new_project(width: int, height: int, fps: int = 12) -> None

    # --- Convenience: Export ---
    def export_png(path: str, frame: int = 0, scale: int = 1,
                   layer: int | str | None = None) -> None
        # layer: index or name. None = flattened composite.
    def export_gif(path: str, scale: int = 1) -> None
    def export_sheet(path: str, scale: int = 1, columns: int = 0) -> str
        # path should be .png — JSON sidecar is auto-named (path with .json extension)
        # Returns path to JSON metadata sidecar

    # --- Convenience: Frame/Layer Access ---
    # NOTE: These wrap timeline methods with correct types:
    #   get_frame() calls timeline.get_frame_obj() → returns Frame (not PixelGrid)
    #   current_frame_pixels() calls timeline.current_frame() → returns PixelGrid (flattened)
    #   add_frame() calls timeline.add_frame() then returns the new Frame object
    def current_frame_pixels() -> PixelGrid  # flattened composite
    def current_layer() -> Layer
    def get_frame(index: int) -> Frame       # uses get_frame_obj() internally
    def add_frame() -> Frame                 # returns timeline.frames[-1] after add
    def add_layer(name: str) -> Layer
    def remove_frame(index: int) -> None
    def remove_layer(index: int) -> None

    # --- Convenience: Image Processing ---
    def apply_filter(func: Callable[[PixelGrid], PixelGrid],
                     frame: int | None = None,
                     layer: int | None = None) -> None
        # If frame/layer None, applies to current. func receives PixelGrid, returns modified.
        # In GUI mode: automatically pushes undo state before applying.
        # Selection-aware: if a selection exists, only the selected region is passed
        # to func and the result is masked back into the layer.

    def apply_effect(layer_index: int, effect_type: str, params: dict) -> None
        # Adds a LayerEffect to the specified layer
        # In GUI mode: automatically pushes undo state before applying.

    # --- Undo (GUI mode only, no-op in headless) ---
    def push_undo(label: str = "Script Action") -> None
        # Explicitly push undo state. apply_filter/apply_effect auto-call this,
        # but plugins doing manual pixel edits should call it first.

    # --- Plugin Registration (UI mode only, no-op in headless) ---
    def register_menu_item(label: str, callback: Callable,
                           submenu: str = "Plugins") -> None
    def register_filter(name: str, func: Callable[[PixelGrid], PixelGrid]) -> None
        # Appears in Filters > Plugins submenu
    def register_tool(name: str, tool_class: type) -> None
        # tool_class must implement PluginTool interface
    def register_effect(name: str, apply_func: Callable,
                        default_params: dict) -> None
        # Appears in Effects Dialog "Add" dropdown
    def on(event_name: str, callback: Callable[[dict], Any]) -> None
        # Subscribe to events
    def off(event_name: str, callback: Callable) -> None
        # Unsubscribe

    # --- Internal ---
    def emit(event_name: str, payload: dict) -> bool
        # Fire event. Returns False if any before_* listener returned False.
    _listeners: dict[str, list[Callable]]
```

### Headless Mode

When `api.app is None` (CLI/script mode):
- `register_menu_item`, `register_tool` are no-ops (log warning)
- `register_filter`, `register_effect` still work (available to scripts)
- All data manipulation and export methods work identically
- No Tkinter dependency — `scripting.py` imports only data modules

### API Initialization

**GUI mode:** `app.py` creates the API in `__init__()`:
```python
self.api = RetroSpriteAPI(timeline=self.timeline, palette=self.palette, app=self)
```

**CLI mode:** `cli.py` creates headless API:
```python
api = RetroSpriteAPI(timeline=timeline, palette=palette, app=None)
```

---

## 2. CLI Interface

### Entry Point

`src/cli.py` with `argparse`. Invoked when `sys.argv[1]` is a known subcommand.

**main.py integration** (at module level, in `if __name__ == "__main__"`, BEFORE calling `main()`):
```python
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] in ("export", "batch", "run", "info"):
        from src.cli import main as cli_main
        sys.exit(cli_main())
    else:
        main()  # existing GUI launch
```
This ensures Tkinter is never imported in CLI mode.

### Commands

**`export`** — Export a single project:
```
python main.py export <input.retro> <output> [options]
    --format    png|gif|sheet|frames   (auto-detect from extension if omitted)
    --scale     1-8                    (nearest-neighbor upscale, default 1)
    --frame     N                      (specific frame index, for png)
    --columns   N                      (sheet columns, 0=auto-square)
    --layer     name|index             (export specific layer only)
```

Format auto-detection: `.png` → single frame, `.gif` → animated GIF, `.json` → sprite sheet (PNG+JSON pair). `frames` format exports every frame as `output_000.png`, `output_001.png`, etc.

**`batch`** — Batch process a directory:
```
python main.py batch <input_dir> <output_dir> [options]
    --pattern   "*.retro"              (glob filter, default "*.retro")
    --format    png|gif|sheet          (required)
    --scale     1-8
```

Iterates matching files, exports each. Prints progress: `[1/12] Exporting hero.retro → hero.png`

**`run`** — Execute a script:
```
python main.py run <script.py> [-- script_args...]
```

Creates headless `RetroSpriteAPI`, injects as `api` in script globals. Script receives `sys.argv` from args after `--`. Example:

```python
# batch_resize.py
import sys
api.load_project(sys.argv[1])
for i in range(api.timeline.frame_count):
    frame = api.get_frame(i)
    # manipulate...
api.export_gif("output.gif", scale=2)
```

**`info`** — Print project metadata:
```
python main.py info <input.retro>
```

Output:
```
Project: hero.retro (v3)
Size: 32x32, 12 fps
Frames: 8
Layers: 3 (Background, Character, FX)
Effects: Character has Outline, Drop Shadow
Tilesets: none
Palette: "Endesga 32" (32 colors)
```

### Headless Architecture

CLI never imports Tkinter. Creates `AnimationTimeline` and `Palette` directly using `load_project()` from `src/project.py`. The `RetroSpriteAPI` wraps these with `app=None`.

---

## 3. Plugin System

### Discovery & Loading (`src/plugins.py`)

**Plugin directory:** `~/.retrosprite/plugins/`

**Loader:**
```python
def discover_plugins(plugin_dir: str) -> list[str]
    # Returns list of .py file paths

def load_plugin(path: str, api: RetroSpriteAPI) -> dict | None
    # Imports module, calls register(api), returns plugin info dict
    # On error: logs warning, returns None

def load_all_plugins(api: RetroSpriteAPI) -> list[dict]
    # Discovers and loads all plugins, respecting disabled list
```

**Plugin contract:**
```python
# Required:
def register(api: RetroSpriteAPI) -> None:
    """Called on startup. Use api.register_* to set up."""

# Optional:
def unregister(api: RetroSpriteAPI) -> None:
    """Called on shutdown. Clean up resources."""
```

**Enable/disable:** `~/.retrosprite/plugins.json`:
```json
{"disabled": ["experimental.py"]}
```

**Error isolation:** Each plugin loads in a try/except. Failures are logged to stderr and optionally shown in a startup warning, but never prevent the app from launching.

### Plugin Capabilities

#### Menu Items
```python
api.register_menu_item("Apply CRT Filter", my_callback)
api.register_menu_item("Export to Itch", export_itch, submenu="Export Tools")
```
Creates entries under Edit > Plugins menu (or custom submenu). Callback receives no arguments — plugin uses `api` closure.

#### Custom Filters
```python
def sepia(grid: PixelGrid) -> PixelGrid:
    pixels = grid._pixels.copy()
    # ... transform ...
    result = PixelGrid(grid.width, grid.height)
    result._pixels = pixels
    return result

api.register_filter("Sepia Tone", sepia)
```
Appears under Filters > Plugins. When selected, applies to current layer/selection.

#### Custom Tools
```python
from src.plugin_tools import PluginTool

class StampTool(PluginTool):
    name = "Stamp"
    icon = None  # optional: path to 16x16 PNG

    def on_click(self, api, x, y):
        """Called on mouse down."""
        pass

    def on_drag(self, api, x, y):
        """Called on mouse move while pressed."""
        pass

    def on_release(self, api, x, y):
        """Called on mouse up."""
        pass

api.register_tool("Stamp", StampTool)
```
Appears in toolbar under a separator. Tool receives pixel coordinates (not screen coordinates — already converted).

**Tool dispatch integration:** In `app.py`, the mouse handlers (`_on_canvas_click`, `_on_canvas_drag`, `_on_canvas_release`) check `self.current_tool_name` against `self.api._plugin_tools` dict before the existing tool dispatch. If matched, delegate to the `PluginTool` instance's `on_click/on_drag/on_release` methods. Plugin tools also receive `api.palette.selected_color` and can access tool size via `api.app.tool_size` if needed.

**PluginTool extended interface** (optional overrides):
```python
class PluginTool:
    name: str
    icon: str | None = None       # path to 16x16 PNG, or None for text label
    cursor: str = "crosshair"     # Tkinter cursor name

    def on_click(self, api, x, y): ...
    def on_drag(self, api, x, y): ...
    def on_release(self, api, x, y): ...
    def on_options_bar(self, api, frame): ...  # optional: add widgets to options bar Frame
    def on_preview(self, api, canvas, x, y): ...  # optional: draw preview overlay
```

#### Custom Effects
```python
def apply_pixelate(pixels, block_size=4, **kwargs):
    import numpy as np
    h, w = pixels.shape[:2]
    result = pixels.copy()
    for y in range(0, h, block_size):
        for x in range(0, w, block_size):
            block = result[y:y+block_size, x:x+block_size]
            avg = block.mean(axis=(0, 1)).astype(np.uint8)
            result[y:y+block_size, x:x+block_size] = avg
    return result

api.register_effect("Pixelate", apply_pixelate, {"block_size": 4})
```
Appears in Effects Dialog "Add" dropdown alongside built-in effects. Params exposed via auto-generated UI (numeric → Spinbox, string → Entry).

#### Event Hooks
```python
def on_save(event):
    print(f"Saved to {event['filepath']}")

def before_export(event):
    if event['format'] == 'gif' and api.timeline.frame_count > 100:
        print("Warning: large GIF!")
        return False  # cancel export

api.on("after_save", on_save)
api.on("before_export", before_export)
```

---

## 4. Event System

### Events

| Event | When | Payload | Cancellable |
|-------|------|---------|-------------|
| `frame_change` | Active frame changes | `{frame_index, frame}` | No |
| `layer_change` | Active layer changes | `{layer_index, layer}` | No |
| `tool_change` | Tool switched | `{tool_name}` | No |
| `before_save` | About to save | `{filepath}` | Yes |
| `after_save` | Save complete | `{filepath}` | No |
| `before_export` | About to export | `{filepath, format}` | Yes |
| `after_export` | Export complete | `{filepath, format}` | No |
| `before_load` | About to load | `{filepath}` | Yes |
| `after_load` | Project loaded | `{filepath}` | No |
| `canvas_paint` | Stroke completed | `{layer, tool, bounds}` | No |
| `palette_change` | Color/palette changed | `{color, index}` | No |
| `frame_added` | Frame created | `{frame_index}` | No |
| `frame_removed` | Frame deleted | `{frame_index}` | No |
| `layer_added` | Layer created | `{layer_index, layer}` | No |
| `layer_removed` | Layer deleted | `{layer_index}` | No |
| `layer_merged` | Layers merged down | `{layer_index}` | No |

### Implementation

Simple observer pattern in `RetroSpriteAPI`:

```python
def on(self, event_name: str, callback: Callable) -> None:
    self._listeners.setdefault(event_name, []).append(callback)

def off(self, event_name: str, callback: Callable) -> None:
    if event_name in self._listeners:
        try:
            self._listeners[event_name].remove(callback)
        except ValueError:
            pass  # silently ignore if callback not registered

def emit(self, event_name: str, payload: dict) -> bool:
    for cb in self._listeners.get(event_name, []):
        try:
            result = cb(payload)
            if event_name.startswith("before_") and result is False:
                return False
        except Exception as e:
            import traceback
            traceback.print_exc()
    return True
```

Event emission points: `app.py` calls `self.api.emit(...)` at each relevant location. Plugin errors are caught per-callback — one bad plugin doesn't prevent other listeners from firing.

---

## 5. Architecture

### New Files (5)

| File | Purpose |
|------|---------|
| `src/scripting.py` | RetroSpriteAPI class + event system |
| `src/cli.py` | CLI entry point, argparse subcommands |
| `src/plugins.py` | Plugin discovery, loading, error isolation |
| `src/plugin_tools.py` | PluginTool base class + PluginEffect interface |
| `tests/test_scripting.py` | Tests for API, CLI, plugin loading, events |

### Modified Files (4)

| File | Changes |
|------|---------|
| `main.py` | Route to CLI when subcommand detected |
| `src/app.py` | Create API, load plugins, emit events, Plugins menu |
| `src/ui/toolbar.py` | Render plugin tools after separator |
| `src/ui/effects_dialog.py` | Include plugin effects in Add dropdown |

### Dependency Flow

```
main.py ─→ cli.py ─→ scripting.py ─→ (animation, layer, export, image_processing, effects, project)
main.py ─→ app.py ─→ plugins.py ─→ scripting.py
                                      ↓
                                plugin_tools.py
```

`scripting.py` depends only on data modules (animation, layer, pixel_data, export, project, image_processing, effects). Never imports app.py or Tkinter. The `app` reference is injected at construction time.

`plugins.py` imports only `scripting.py` and stdlib (`importlib`, `os`, `json`).

`plugin_tools.py` defines abstract base classes only — no heavy dependencies.
