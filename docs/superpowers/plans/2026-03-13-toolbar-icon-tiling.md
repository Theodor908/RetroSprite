# Toolbar, Icon & Tiling Fixes — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the toolbar scrollable on small windows, add the missing lasso icon, and fix canvas panning when tiled mode is active.

**Architecture:** Three independent changes: (1) toolbar.py gets a Canvas+Frame scroll wrapper, (2) a Phosphor SVG file is added to icons/, (3) canvas.py tracks tiled mode to expand scrollregion and fix zoom math.

**Tech Stack:** Python 3.8+, Tkinter, Pillow, pytest

---

## Chunk 1: Scrollable Toolbar

### Task 1: Add scrollable canvas wrapper to Toolbar

**Files:**
- Modify: `src/ui/toolbar.py` (full file — restructure `__init__` and `add_plugin_tools`)
- Test: `tests/test_toolbar.py`

- [ ] **Step 1: Write failing tests for scrollable toolbar**

Add tests to `tests/test_toolbar.py`:

```python
def test_toolbar_has_scroll_canvas(root):
    """Toolbar should contain an internal Canvas for scrolling."""
    toolbar = Toolbar(root, on_tool_change=lambda t: None)
    # The toolbar should have a _scroll_canvas attribute
    assert hasattr(toolbar, '_scroll_canvas')
    assert isinstance(toolbar._scroll_canvas, tk.Canvas)


def test_toolbar_buttons_in_inner_frame(root):
    """All tool buttons should be children of the inner frame, not the toolbar itself."""
    toolbar = Toolbar(root, on_tool_change=lambda t: None)
    assert hasattr(toolbar, '_inner_frame')
    for tool_name, btn in toolbar._buttons.items():
        assert btn.master == toolbar._inner_frame, f"{tool_name} button not in inner frame"


def test_toolbar_scroll_region_updates(root):
    """Scroll region should cover all buttons after layout."""
    toolbar = Toolbar(root, on_tool_change=lambda t: None)
    toolbar.update_idletasks()
    sr = toolbar._scroll_canvas.cget("scrollregion")
    # scrollregion should be non-empty when buttons exist
    assert sr != "" and sr != "0 0 0 0"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_toolbar.py -v`
Expected: FAIL — `_scroll_canvas` and `_inner_frame` don't exist yet

- [ ] **Step 3: Implement scrollable toolbar**

In `src/ui/toolbar.py`, restructure `__init__` to use a Canvas+Frame pattern:

```python
class Toolbar(tk.Frame):
    def __init__(self, parent, on_tool_change=None, keybindings=None, **kwargs):
        super().__init__(parent, bg=BG_DEEP, width=48, **kwargs)
        self.pack_propagate(False)

        self._on_tool_change = on_tool_change
        self._active_tool = "pen"
        self._keybindings = keybindings
        self._buttons: dict[str, tk.Button] = {}
        self._photos: dict[str, ImageTk.PhotoImage] = {}
        self._photos_glow: dict[str, ImageTk.PhotoImage] = {}

        self._pipeline = IconPipeline(icon_size=16, display_size=32)

        # Scrollable container: Canvas + inner Frame
        self._scroll_canvas = tk.Canvas(self, bg=BG_DEEP, highlightthickness=0,
                                         width=48, bd=0)
        self._scroll_canvas.pack(fill="both", expand=True)

        self._inner_frame = tk.Frame(self._scroll_canvas, bg=BG_DEEP)
        self._canvas_window = self._scroll_canvas.create_window(
            (0, 0), window=self._inner_frame, anchor="nw"
        )

        # Update scroll region when inner frame resizes
        self._inner_frame.bind("<Configure>", self._on_inner_configure)
        # Match canvas width to toolbar width
        self._scroll_canvas.bind("<Configure>", self._on_canvas_configure)
        # Mousewheel scrolling
        self._scroll_canvas.bind("<MouseWheel>", self._on_mousewheel)
        self._inner_frame.bind("<MouseWheel>", self._on_mousewheel)

        # Build icon buttons (into _inner_frame)
        for tool_name in TOOL_LIST:
            normal_img, glow_img = self._pipeline.get_icon(tool_name)
            photo_normal = ImageTk.PhotoImage(normal_img)
            photo_glow = ImageTk.PhotoImage(glow_img)
            self._photos[tool_name] = photo_normal
            self._photos_glow[tool_name] = photo_glow

            btn = tk.Button(
                self._inner_frame, image=photo_normal, width=36, height=36,
                bg=BUTTON_BG, activebackground=BUTTON_HOVER,
                relief="flat", bd=0,
                command=lambda n=tool_name: self.select_tool(n)
            )
            btn.pack(padx=4, pady=2)
            self._buttons[tool_name] = btn

            # Tooltip on hover
            btn.bind("<Enter>", lambda e, n=tool_name: self._show_tooltip(e, n))
            btn.bind("<Leave>", lambda e: self._hide_tooltip())
            # Forward mousewheel from buttons to canvas
            btn.bind("<MouseWheel>", self._on_mousewheel)

        self._tooltip = None
        self._highlight("pen")

    def _on_inner_configure(self, event=None):
        """Update scroll region when inner frame content changes."""
        self._scroll_canvas.configure(
            scrollregion=self._scroll_canvas.bbox("all")
        )

    def _on_canvas_configure(self, event=None):
        """Keep inner frame width matched to canvas width."""
        if event:
            self._scroll_canvas.itemconfig(self._canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        """Scroll toolbar on mousewheel."""
        self._scroll_canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
```

Also update `add_plugin_tools` to pack into `self._inner_frame`:

```python
    def add_plugin_tools(self, plugin_tools: dict) -> None:
        """Add plugin tools to the toolbar after a separator."""
        if not plugin_tools:
            return
        sep = tk.Frame(self._inner_frame, bg=BORDER, height=2)
        sep.pack(fill="x", padx=4, pady=4)
        for name, tool in plugin_tools.items():
            btn = tk.Button(
                self._inner_frame, text=name[:3], width=4, height=2,
                bg=BUTTON_BG, activebackground=BUTTON_HOVER,
                fg=TEXT_PRIMARY, font=("Consolas", 8, "bold"),
                relief="flat", bd=0,
                command=lambda n=name: self.select_tool(n)
            )
            btn.pack(padx=4, pady=2)
            self._buttons[name.lower()] = btn
            btn.bind("<Enter>", lambda e, n=name: self._show_tooltip(e, n.lower()))
            btn.bind("<Leave>", lambda e: self._hide_tooltip())
            btn.bind("<MouseWheel>", self._on_mousewheel)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_toolbar.py -v`
Expected: All PASS

- [ ] **Step 5: Run full test suite to check for regressions**

Run: `python -m pytest tests/ -x -q`
Expected: All 430+ tests pass

---

## Chunk 2: Lasso Icon

### Task 2: Download and add lasso-bold.svg

**Files:**
- Add: `icons/lasso-bold.svg`
- Test: `tests/test_icons.py` (existing)

- [ ] **Step 1: Download lasso-bold.svg from Phosphor Icons**

Use the Phosphor Icons GitHub raw URL to fetch the bold lasso SVG:

```bash
curl -o icons/lasso-bold.svg "https://raw.githubusercontent.com/phosphor-icons/core/main/assets/bold/lasso-bold.svg"
```

If the URL doesn't work (Phosphor may not have "lasso"), check the Phosphor core repo for the correct filename. Alternative search:

```bash
# Search for lasso in the Phosphor repo
curl -s "https://api.github.com/search/code?q=lasso+repo:phosphor-icons/core" | python -c "import sys,json; [print(i['name']) for i in json.load(sys.stdin).get('items',[])]"
```

If Phosphor doesn't have a lasso icon, create a minimal SVG that represents a lasso shape (a loop with a trailing line), styled to match the other bold icons (24x24 viewbox, stroke-width ~1.5, stroke="currentColor").

- [ ] **Step 2: Verify icon loads in the pipeline**

Run: `python -m pytest tests/test_icons.py -v`
Expected: All PASS

- [ ] **Step 3: Visual verification**

Run: `python main.py`
Verify: The lasso tool in the toolbar shows a proper icon instead of a fallback letter "L".

---

## Chunk 3: Tiled Mode Panning Fix

### Task 3: Add tiled_mode tracking to PixelCanvas

**Files:**
- Modify: `src/canvas.py:120-200` (PixelCanvas class)
- Test: `tests/test_tiled_mode.py`

- [ ] **Step 1: Write failing tests for tiled scrollregion**

Add to `tests/test_tiled_mode.py`:

```python
import tkinter as tk
from src.canvas import PixelCanvas
from src.pixel_data import PixelGrid


class TestTiledScrollRegion:
    @pytest.fixture
    def canvas_setup(self):
        root = tk.Tk()
        root.withdraw()
        grid = PixelGrid(8, 8)
        canvas = PixelCanvas(root, grid, pixel_size=4)
        yield canvas, grid
        root.destroy()

    def test_scrollregion_default_no_tiling(self, canvas_setup):
        canvas, grid = canvas_setup
        sr = canvas.cget("scrollregion").split()
        w, h = int(float(sr[2])), int(float(sr[3]))
        assert w == 8 * 4  # 32
        assert h == 8 * 4  # 32

    def test_scrollregion_expands_with_tiling(self, canvas_setup):
        canvas, grid = canvas_setup
        canvas.set_tiled_mode("both")
        sr = canvas.cget("scrollregion").split()
        w, h = int(float(sr[2])), int(float(sr[3]))
        assert w == 8 * 4 * 3  # 96
        assert h == 8 * 4 * 3  # 96

    def test_scrollregion_resets_when_tiling_off(self, canvas_setup):
        canvas, grid = canvas_setup
        canvas.set_tiled_mode("both")
        canvas.set_tiled_mode("off")
        sr = canvas.cget("scrollregion").split()
        w, h = int(float(sr[2])), int(float(sr[3]))
        assert w == 8 * 4  # 32
        assert h == 8 * 4  # 32

    def test_scrollregion_x_mode(self, canvas_setup):
        canvas, grid = canvas_setup
        canvas.set_tiled_mode("x")
        sr = canvas.cget("scrollregion").split()
        w, h = int(float(sr[2])), int(float(sr[3]))
        # Rendering always produces 3x3, so scroll region is 3x3
        assert w == 8 * 4 * 3
        assert h == 8 * 4 * 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_tiled_mode.py::TestTiledScrollRegion -v`
Expected: FAIL — `set_tiled_mode` doesn't exist yet

- [ ] **Step 3: Implement set_tiled_mode and update _update_scrollregion**

In `src/canvas.py`, add `_tiled_mode` attribute and `set_tiled_mode()` method to `PixelCanvas`:

In `__init__`, after `self._on_raw_click = None`:
```python
        self._tiled_mode = "off"
```

Add new method after `_update_scrollregion`:
```python
    def set_tiled_mode(self, mode: str) -> None:
        """Set tiled mode and update scroll region accordingly."""
        self._tiled_mode = mode
        self._update_scrollregion()
        if mode != "off":
            # Center viewport on the middle tile (the real sprite)
            self.xview_moveto(1 / 3)
            self.yview_moveto(1 / 3)
```

Update `_update_scrollregion`:
```python
    def _update_scrollregion(self) -> None:
        w = self.grid.width * self.pixel_size
        h = self.grid.height * self.pixel_size
        if self._tiled_mode != "off":
            w *= 3
            h *= 3
        self.config(scrollregion=(0, 0, w, h))
```

Also update `_resize_canvas` to preserve tiled state:
```python
    def _resize_canvas(self) -> None:
        w = self.grid.width * self.pixel_size
        h = self.grid.height * self.pixel_size
        self.config(width=w, height=h)
        self._update_scrollregion()
```
(This stays the same — `_update_scrollregion` now handles the multiplier.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_tiled_mode.py::TestTiledScrollRegion -v`
Expected: All PASS

### Task 4: Fix zoom_at for tiled mode

**Files:**
- Modify: `src/canvas.py:175-199` (`zoom_at` method)
- Test: `tests/test_tiled_mode.py`

- [ ] **Step 1: Write failing test for zoom under tiled mode**

Add to `tests/test_tiled_mode.py`:

```python
    def test_scroll_region_correct_after_zoom_with_tiling(self, canvas_setup):
        canvas, grid = canvas_setup
        canvas.set_tiled_mode("both")
        canvas.pixel_size = 8
        canvas._resize_canvas()
        sr = canvas.cget("scrollregion").split()
        w, h = int(float(sr[2])), int(float(sr[3]))
        # After zoom to ps=8: 8*8*3 = 192
        assert w == 8 * 8 * 3
        assert h == 8 * 8 * 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tiled_mode.py::TestTiledScrollRegion::test_scroll_region_correct_after_zoom_with_tiling -v`
Expected: This should actually PASS since `_update_scrollregion` already handles the multiplier. If it passes, proceed.

- [ ] **Step 3: Fix zoom_at scroll fraction denominator**

In `src/canvas.py`, update `zoom_at` lines 194-195:

Replace:
```python
            self.xview_moveto((new_cx - event.x) / (self.grid.width * new_size))
            self.yview_moveto((new_cy - event.y) / (self.grid.height * new_size))
```

With:
```python
            mult = 3 if self._tiled_mode != "off" else 1
            self.xview_moveto((new_cx - event.x) / (self.grid.width * new_size * mult))
            self.yview_moveto((new_cy - event.y) / (self.grid.height * new_size * mult))
```

- [ ] **Step 4: Run all tiled mode tests**

Run: `python -m pytest tests/test_tiled_mode.py -v`
Expected: All PASS

### Task 5: Fix _to_grid_coords for tiled mode offset

**Files:**
- Modify: `src/canvas.py:201-207` (`_to_grid_coords` method)
- Test: `tests/test_tiled_mode.py`

When the scroll region is 3× and the viewport is centered on the middle tile, `canvasx`/`canvasy` return coordinates offset by the tile padding. Grid coordinates must be mod-wrapped into `[0, grid.width)` and `[0, grid.height)` so drawing tools hit the correct pixel.

- [ ] **Step 1: Write failing test for grid coord wrapping**

Add to `TestTiledScrollRegion` in `tests/test_tiled_mode.py`:

```python
    def test_to_grid_coords_wraps_in_tiled_mode(self, canvas_setup):
        canvas, grid = canvas_setup  # 8x8 grid, ps=4
        canvas.set_tiled_mode("both")
        # Simulate a click at canvas position (36, 36) — that's pixel (9, 9)
        # which should wrap to (1, 1) on an 8x8 grid
        class FakeEvent:
            x = 36
            y = 36
        gx, gy = canvas._to_grid_coords(FakeEvent())
        assert 0 <= gx < 8
        assert 0 <= gy < 8
        assert gx == 9 % 8  # 1
        assert gy == 9 % 8  # 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tiled_mode.py::TestTiledScrollRegion::test_to_grid_coords_wraps_in_tiled_mode -v`
Expected: FAIL — coordinates not wrapped yet

- [ ] **Step 3: Update _to_grid_coords to wrap in tiled mode**

In `src/canvas.py`, replace `_to_grid_coords`:

```python
    def _to_grid_coords(self, event) -> tuple[int, int]:
        # Account for scroll offset
        cx = self.canvasx(event.x)
        cy = self.canvasy(event.y)
        x = int(cx) // self.pixel_size
        y = int(cy) // self.pixel_size
        if self._tiled_mode != "off":
            x = x % self.grid.width
            y = y % self.grid.height
        return x, y
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_tiled_mode.py::TestTiledScrollRegion -v`
Expected: All PASS

### Task 6: Wire set_tiled_mode into app.py

**Files:**
- Modify: `src/app.py:1257-1260` (`_on_tiled_mode_change` method)

- [ ] **Step 1: Update `_on_tiled_mode_change` to call `set_tiled_mode`**

In `src/app.py`, modify `_on_tiled_mode_change`:

Replace:
```python
    def _on_tiled_mode_change(self):
        self._tiled_mode = self._tiled_var.get()
        self._render_canvas()
        self._update_status(f"Tiled: {self._tiled_mode}")
```

With:
```python
    def _on_tiled_mode_change(self):
        self._tiled_mode = self._tiled_var.get()
        self.pixel_canvas.set_tiled_mode(self._tiled_mode)
        self._render_canvas()
        self._update_status(f"Tiled: {self._tiled_mode}")
```

- [ ] **Step 2: Run full test suite**

Run: `python -m pytest tests/ -x -q`
Expected: All 430+ tests pass

- [ ] **Step 3: Manual verification**

Run: `python main.py`
Test:
1. View > Tiled Both — verify you can pan with Hand tool to see neighboring dimmed copies
2. View > Tiled X — same behavior
3. Ctrl+scroll to zoom while tiled — viewport should not jump
4. View > Tiled Off — verify normal behavior restored
