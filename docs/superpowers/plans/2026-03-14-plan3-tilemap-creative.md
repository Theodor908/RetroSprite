# Plan 3: Tilemap & Creative Tools Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add five features enhancing tilemap workflows and creative drawing capabilities: Live Tile Editing, Isometric & Hexagonal Tilemap Grids, Color Cycling (Animated Palette), More Ink Modes (Smear/Halftone/Tint + Kaleidoscope symmetry), and APNG Import.

**Architecture:** Chunk 1 (Tasks 1-2) enhances the existing tilemap system — live edit-back-to-master tile data, and non-rectangular grid coordinate systems. Chunk 2 (Tasks 3-4) adds Amiga-style color cycling integrated into animation playback, plus new ink/symmetry modes. Chunk 3 (Task 5) adds APNG import as a new file format handler.

**Tech Stack:** Python, Tkinter, NumPy, PIL (existing stack). No new dependencies required.

**Codebase references:**
- Tilemap system: `src/tilemap.py` — `Tileset` (tiles array, `tile_width`/`tile_height`, `find_matching`), `TilemapLayer` (grid of `TileRef`), `TileRef` (index + flip_x + flip_y packed into uint32)
- Palette: `src/palette.py` line 37 — `class Palette` with `self.colors: list[tuple]`, `self.selected_index`, `self.name`. No `cycles` field yet.
- Animation playback: `src/app.py` — `_play_animation()` and `_animate_step()` methods using `root.after()` timer. Frame duration from `frame_obj.duration_ms`.
- Ink modes: `src/ui/options_bar.py` line 186 — `_INK_MODES = ["Normal", "αLock", "Behind"]`. Cycling via `_cycle_ink_mode()`.
- Symmetry: `src/app.py` line 1428 — `_apply_symmetry_draw()`. Modes: off, horizontal, vertical, both. Cycle at line 1445.
- Serialization: `src/project.py` — JSON `.retro` format. `save_project()` / `load_project()`.
- Tool settings: `src/tool_settings.py` — `TOOL_DEFAULTS` dict, `ToolSettingsManager` class.

---

## Chunk 1: Tilemap Enhancements

### Task 1: Live Tile Editing

**Goal:** When editing pixels in a tilemap layer's "Pixels" mode, writes go back to the master tile in `Tileset.tiles[tile_index]`. All instances sharing the same tile ID auto-update on next render since `TilemapLayer.render_to_pixels()` reads from `self.tileset.tiles`.

**Files:**
- Modify: `src/tilemap.py` (add `write_pixel_to_master()` method on `TilemapLayer`)
- Modify: `src/app.py` (route tilemap pixel edits through `write_pixel_to_master()` instead of direct layer pixel writes)
- Test: `tests/test_live_tile_edit.py` (create)

- [ ] **Step 1: Write failing tests**

Create `tests/test_live_tile_edit.py`:

```python
"""Tests for live tile editing — edits write back to master tileset."""
import numpy as np
from src.tilemap import Tileset, TileRef, TilemapLayer


class TestLiveTileEditing:
    def test_write_pixel_updates_master_tile(self):
        """Editing a pixel in a placed tile updates the master tileset tile."""
        ts = Tileset("Test", 8, 8)
        tile = np.full((8, 8, 4), [100, 100, 100, 255], dtype=np.uint8)
        idx = ts.add_tile(tile)

        tl = TilemapLayer("TM", 16, 16, ts)
        tl.grid[0][0] = TileRef(idx)

        # Write pixel at canvas position (2, 3) — inside tile at grid[0][0]
        tl.write_pixel_to_master(2, 3, (255, 0, 0, 255))

        # Master tile should be updated
        assert tuple(ts.tiles[idx][3, 2]) == (255, 0, 0, 255)

    def test_write_pixel_affects_all_instances(self):
        """Two tile instances sharing the same tile ID both reflect the edit."""
        ts = Tileset("Test", 8, 8)
        tile = np.full((8, 8, 4), [50, 50, 50, 255], dtype=np.uint8)
        idx = ts.add_tile(tile)

        tl = TilemapLayer("TM", 24, 8, ts)
        tl.grid[0][0] = TileRef(idx)
        tl.grid[0][1] = TileRef(idx)
        tl.grid[0][2] = TileRef(idx)

        # Edit pixel in first instance
        tl.write_pixel_to_master(1, 1, (255, 255, 0, 255))

        # Render — all three instances should show the change at local (1,1)
        rendered = tl.render_to_pixels()
        assert tuple(rendered[1, 1]) == (255, 255, 0, 255)
        assert tuple(rendered[1, 9]) == (255, 255, 0, 255)   # second tile
        assert tuple(rendered[1, 17]) == (255, 255, 0, 255)   # third tile

    def test_write_pixel_to_empty_tile_is_noop(self):
        """Writing to an empty tile cell (index 0) does nothing."""
        ts = Tileset("Test", 8, 8)
        tl = TilemapLayer("TM", 16, 16, ts)
        # All cells are index 0 (empty)
        tl.write_pixel_to_master(2, 2, (255, 0, 0, 255))
        # Empty tile should remain unchanged
        assert np.all(ts.tiles[0][:, :, 3] == 0)

    def test_write_pixel_out_of_bounds_is_noop(self):
        """Writing outside the tilemap canvas does nothing."""
        ts = Tileset("Test", 8, 8)
        tl = TilemapLayer("TM", 16, 16, ts)
        tile = np.full((8, 8, 4), [50, 50, 50, 255], dtype=np.uint8)
        idx = ts.add_tile(tile)
        tl.grid[0][0] = TileRef(idx)
        # Should not crash
        tl.write_pixel_to_master(100, 100, (255, 0, 0, 255))

    def test_write_pixel_respects_flip_x(self):
        """When tile is flipped, pixel coordinates are un-flipped before writing to master."""
        ts = Tileset("Test", 4, 4)
        tile = np.zeros((4, 4, 4), dtype=np.uint8)
        tile[:, :, 3] = 255
        idx = ts.add_tile(tile)

        tl = TilemapLayer("TM", 4, 4, ts)
        tl.grid[0][0] = TileRef(idx, flip_x=True)

        # Write to screen position (0, 0) — with flip_x, this maps to
        # local tile position (3, 0)
        tl.write_pixel_to_master(0, 0, (255, 0, 0, 255))
        assert tuple(ts.tiles[idx][0, 3]) == (255, 0, 0, 255)

    def test_write_pixel_respects_flip_y(self):
        """When tile is y-flipped, pixel y is un-flipped before writing to master."""
        ts = Tileset("Test", 4, 4)
        tile = np.zeros((4, 4, 4), dtype=np.uint8)
        tile[:, :, 3] = 255
        idx = ts.add_tile(tile)

        tl = TilemapLayer("TM", 4, 4, ts)
        tl.grid[0][0] = TileRef(idx, flip_y=True)

        # Write to screen position (0, 0) — with flip_y, this maps to
        # local tile position (0, 3)
        tl.write_pixel_to_master(0, 0, (255, 0, 0, 255))
        assert tuple(ts.tiles[idx][3, 0]) == (255, 0, 0, 255)

    def test_undo_snapshot_captures_master_tile(self):
        """snapshot_tile() returns a copy of the master tile before edit."""
        ts = Tileset("Test", 8, 8)
        tile = np.full((8, 8, 4), [42, 42, 42, 255], dtype=np.uint8)
        idx = ts.add_tile(tile)

        tl = TilemapLayer("TM", 8, 8, ts)
        tl.grid[0][0] = TileRef(idx)

        snapshot = tl.snapshot_tile(0, 0)
        assert snapshot is not None
        tile_idx, tile_copy = snapshot
        assert tile_idx == idx
        assert np.array_equal(tile_copy, tile)

        # Edit
        tl.write_pixel_to_master(0, 0, (255, 0, 0, 255))
        # Original snapshot should be unchanged
        assert tuple(tile_copy[0, 0]) == (42, 42, 42, 255)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_live_tile_edit.py -v`
Expected: FAIL — `AttributeError: 'TilemapLayer' object has no attribute 'write_pixel_to_master'`

- [ ] **Step 3: Implement `write_pixel_to_master()` and `snapshot_tile()` on TilemapLayer**

Add to `src/tilemap.py` inside class `TilemapLayer`, after `render_to_pixels()` (~line 154):

```python
def write_pixel_to_master(self, canvas_x: int, canvas_y: int,
                          color: tuple) -> None:
    """Write a pixel edit back to the master tileset tile.

    Translates canvas coordinates to grid cell + local tile coordinates,
    accounts for flip transforms, and writes directly to
    ``self.tileset.tiles[ref.index]``.
    """
    tw, th = self.tileset.tile_width, self.tileset.tile_height
    col = canvas_x // tw
    row = canvas_y // th
    if col < 0 or col >= self.grid_cols or row < 0 or row >= self.grid_rows:
        return
    ref = self.grid[row][col]
    if ref.index == 0 or ref.index >= len(self.tileset.tiles):
        return
    local_x = canvas_x % tw
    local_y = canvas_y % th
    # Un-flip coordinates to write to the master tile's canonical orientation
    if ref.flip_x:
        local_x = tw - 1 - local_x
    if ref.flip_y:
        local_y = th - 1 - local_y
    self.tileset.tiles[ref.index][local_y, local_x] = color

def snapshot_tile(self, canvas_x: int, canvas_y: int) -> tuple[int, np.ndarray] | None:
    """Return (tile_index, copy_of_tile_pixels) for undo before editing.

    Returns None if the cell is empty (index 0) or out of bounds.
    """
    tw, th = self.tileset.tile_width, self.tileset.tile_height
    col = canvas_x // tw
    row = canvas_y // th
    if col < 0 or col >= self.grid_cols or row < 0 or row >= self.grid_rows:
        return None
    ref = self.grid[row][col]
    if ref.index == 0 or ref.index >= len(self.tileset.tiles):
        return None
    return (ref.index, self.tileset.tiles[ref.index].copy())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_live_tile_edit.py -v`
Expected: All 8 tests PASS.

- [ ] **Step 5: Integrate into app.py pixel editing path**

In `src/app.py`, locate the tilemap pixel editing code path (where pen/eraser tools draw on a tilemap layer). Modify the draw function that currently writes to the rendered pixel buffer to instead call `layer.write_pixel_to_master(x, y, color)`.

Find the drawing lambda/function in `_on_canvas_click` and `_on_canvas_drag` that handles tilemap layers. Before the draw call, capture an undo snapshot:

```python
# Before stroke begins (in _on_canvas_click), if active layer is tilemap:
if hasattr(active_layer, 'is_tilemap') and active_layer.is_tilemap():
    snap = active_layer.snapshot_tile(x, y)
    if snap:
        self._tilemap_undo_tiles[snap[0]] = snap[1]  # tile_index -> original pixels
```

Replace direct `grid.set_pixel(x, y, color)` calls with `active_layer.write_pixel_to_master(x, y, color)` when `active_layer.is_tilemap()`.

- [ ] **Step 6: Add undo support for tilemap edits**

In the undo push for tilemap edits, store `self._tilemap_undo_tiles` (dict of `tile_index -> np.ndarray`). On undo, restore each tile: `tileset.tiles[idx] = saved_copy`.

- [ ] **Step 7: Verify full integration manually**

Open the app, create a tilemap layer, place the same tile in multiple cells, edit one instance, confirm all instances update.

---

### Task 2: Isometric & Hexagonal Tilemap Grids

**Goal:** Add `grid_type` field to `TilemapLayer` supporting `"orthogonal"` (default), `"isometric"`, and `"hexagonal"`. Add coordinate conversion functions and grid-type-aware rendering.

**Files:**
- Modify: `src/tilemap.py` (add `grid_type` field, `screen_to_tile()`, `tile_to_screen()` functions, update `render_to_pixels()`)
- Modify: `src/ui/tiles_panel.py` (grid type selector dropdown)
- Modify: `src/app.py` (use coordinate conversion for tilemap mouse events, grid line rendering)
- Modify: `src/project.py` (serialize `grid_type` — backward compatible, default `"orthogonal"`)
- Test: `tests/test_tilemap_grids.py` (create)

- [ ] **Step 1: Write failing tests for coordinate conversion**

Create `tests/test_tilemap_grids.py`:

```python
"""Tests for isometric and hexagonal tilemap grid coordinate conversion."""
import math
import numpy as np
from src.tilemap import (
    screen_to_tile, tile_to_screen,
    Tileset, TilemapLayer,
)


class TestOrthogonalCoords:
    def test_tile_to_screen_origin(self):
        sx, sy = tile_to_screen(0, 0, "orthogonal", 16, 16)
        assert sx == 0
        assert sy == 0

    def test_tile_to_screen_offset(self):
        sx, sy = tile_to_screen(2, 3, "orthogonal", 16, 16)
        assert sx == 32
        assert sy == 48

    def test_screen_to_tile_roundtrip(self):
        for col in range(5):
            for row in range(5):
                sx, sy = tile_to_screen(col, row, "orthogonal", 16, 16)
                c, r = screen_to_tile(sx + 8, sy + 8, "orthogonal", 16, 16)
                assert (c, r) == (col, row)


class TestIsometricCoords:
    def test_tile_to_screen_origin(self):
        sx, sy = tile_to_screen(0, 0, "isometric", 32, 16)
        assert sx == 0
        assert sy == 0

    def test_tile_to_screen_col1(self):
        sx, sy = tile_to_screen(1, 0, "isometric", 32, 16)
        assert sx == 16   # (1-0) * 32/2
        assert sy == 8    # (1+0) * 16/2

    def test_tile_to_screen_row1(self):
        sx, sy = tile_to_screen(0, 1, "isometric", 32, 16)
        assert sx == -16  # (0-1) * 32/2
        assert sy == 8    # (0+1) * 16/2

    def test_screen_to_tile_roundtrip(self):
        for col in range(4):
            for row in range(4):
                sx, sy = tile_to_screen(col, row, "isometric", 32, 16)
                # Hit center of tile
                c, r = screen_to_tile(sx + 16, sy + 8, "isometric", 32, 16)
                assert (c, r) == (col, row), f"Failed for ({col},{row})"


class TestHexagonalCoords:
    def test_tile_to_screen_origin(self):
        sx, sy = tile_to_screen(0, 0, "hexagonal", 32, 28)
        assert sx == 0
        assert sy == 0

    def test_tile_to_screen_odd_row_offset(self):
        """Odd rows are offset by half tile width."""
        sx_even, _ = tile_to_screen(0, 0, "hexagonal", 32, 28)
        sx_odd, _ = tile_to_screen(0, 1, "hexagonal", 32, 28)
        assert sx_odd == sx_even + 16  # half tile width offset

    def test_screen_to_tile_roundtrip_even_rows(self):
        for col in range(4):
            sx, sy = tile_to_screen(col, 0, "hexagonal", 32, 28)
            c, r = screen_to_tile(sx + 16, sy + 14, "hexagonal", 32, 28)
            assert (c, r) == (col, 0)

    def test_screen_to_tile_roundtrip_odd_rows(self):
        for col in range(4):
            sx, sy = tile_to_screen(col, 1, "hexagonal", 32, 28)
            c, r = screen_to_tile(sx + 16, sy + 14, "hexagonal", 32, 28)
            assert (c, r) == (col, 1)


class TestTilemapLayerGridType:
    def test_default_grid_type_is_orthogonal(self):
        ts = Tileset("Test", 8, 8)
        tl = TilemapLayer("TM", 32, 32, ts)
        assert tl.grid_type == "orthogonal"

    def test_set_grid_type_isometric(self):
        ts = Tileset("Test", 8, 8)
        tl = TilemapLayer("TM", 32, 32, ts)
        tl.grid_type = "isometric"
        assert tl.grid_type == "isometric"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_tilemap_grids.py -v`
Expected: FAIL — `ImportError: cannot import name 'screen_to_tile'`

- [ ] **Step 3: Implement coordinate conversion functions**

Add to `src/tilemap.py` as module-level functions (before the classes):

```python
import math


def tile_to_screen(col: int, row: int, grid_type: str,
                   tw: int, th: int) -> tuple[int, int]:
    """Convert tile grid coordinates to screen pixel position (top-left corner)."""
    if grid_type == "isometric":
        sx = (col - row) * tw // 2
        sy = (col + row) * th // 2
        return (sx, sy)
    elif grid_type == "hexagonal":
        # Flat-top hex: odd rows offset by half tile width
        sx = col * tw + (tw // 2 if row % 2 else 0)
        sy = row * (th * 3 // 4)  # 3/4 height stacking for hex
        return (sx, sy)
    else:  # orthogonal
        return (col * tw, row * th)


def screen_to_tile(sx: int, sy: int, grid_type: str,
                   tw: int, th: int) -> tuple[int, int]:
    """Convert screen pixel position to tile grid coordinates."""
    if grid_type == "isometric":
        # Inverse of: sx = (col - row) * tw/2, sy = (col + row) * th/2
        col_f = (sx / (tw / 2) + sy / (th / 2)) / 2
        row_f = (sy / (th / 2) - sx / (tw / 2)) / 2
        return (round(col_f), round(row_f))
    elif grid_type == "hexagonal":
        # Approximate: find row from y, then col accounting for row offset
        row = round(sy / (th * 3 / 4))
        offset = tw // 2 if row % 2 else 0
        col = round((sx - offset) / tw)
        return (col, row)
    else:  # orthogonal
        return (sx // tw, sy // th)
```

- [ ] **Step 4: Add `grid_type` field to `TilemapLayer.__init__`**

In `src/tilemap.py`, in `TilemapLayer.__init__()`, add after `self.pixel_sub_mode = "auto"` (~line 105):

```python
self.grid_type: str = "orthogonal"  # "orthogonal", "isometric", "hexagonal"
```

Also update `TilemapLayer.copy()` to copy `grid_type`:

```python
new.grid_type = self.grid_type
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_tilemap_grids.py -v`
Expected: All tests PASS.

- [ ] **Step 6: Serialize `grid_type` in project.py**

In `src/project.py`, in `save_project()` tilemap layer serialization (~line 43-64), add to `layer_dict`:

```python
"grid_type": getattr(layer, 'grid_type', 'orthogonal'),
```

In `load_project()` tilemap layer loading (~line 210-211), add after setting `pixel_sub_mode`:

```python
layer.grid_type = layer_data.get("grid_type", "orthogonal")
```

- [ ] **Step 7: Write round-trip serialization test**

Add to `tests/test_tilemap_grids.py`:

```python
class TestGridTypeSerialization:
    def test_roundtrip_isometric(self):
        import tempfile, os
        from src.tilemap import Tileset, TilemapLayer, TileRef
        from src.animation import AnimationTimeline, Frame
        from src.palette import Palette
        from src.project import save_project, load_project

        ts = Tileset("Test", 8, 8)
        tile = np.full((8, 8, 4), [100, 100, 100, 255], dtype=np.uint8)
        ts.add_tile(tile)

        timeline = AnimationTimeline(16, 16)
        timeline.tilesets = {"Test": ts}
        frame = timeline.get_frame_obj(0)
        tl = TilemapLayer("TM", 16, 16, ts)
        tl.grid_type = "isometric"
        tl.grid[0][0] = TileRef(1)
        frame.layers = [tl]

        palette = Palette("Pico-8")
        path = os.path.join(tempfile.gettempdir(), "test_grid_type.retro")
        try:
            save_project(path, timeline, palette)
            loaded_tl, _, _ = load_project(path)
            loaded_layer = loaded_tl.get_frame_obj(0).layers[0]
            assert loaded_layer.grid_type == "isometric"
        finally:
            os.unlink(path)
```

- [ ] **Step 8: Run serialization test**

Run: `python -m pytest tests/test_tilemap_grids.py::TestGridTypeSerialization -v`
Expected: PASS.

- [ ] **Step 9: Add grid type selector to tiles panel UI**

In `src/ui/tiles_panel.py`, add a dropdown for grid type selection. When changed, update the active `TilemapLayer.grid_type` and re-render:

```python
# In the tiles panel init, add dropdown:
self._grid_type_var = tk.StringVar(value="orthogonal")
grid_type_menu = tk.OptionMenu(
    self, self._grid_type_var,
    "orthogonal", "isometric", "hexagonal",
    command=self._on_grid_type_change
)
```

- [ ] **Step 10: Update app.py tilemap mouse coordinate mapping**

In `src/app.py`, wherever tilemap mouse events convert screen coordinates to tile coordinates, use `screen_to_tile(sx, sy, layer.grid_type, tw, th)` instead of simple integer division. Similarly use `tile_to_screen()` for grid line rendering.

---

## Chunk 2: Color Cycling & Ink Modes

### Task 3: Color Cycling (Animated Palette)

**Goal:** Amiga-style palette animation. `ColorCycle` dataclass defines a range of palette indices that rotate at a given speed. Cycle stepping is integrated into `_animate_step()` — not a separate timer — to prevent drift.

**Files:**
- Modify: `src/palette.py` (add `ColorCycle` dataclass, `Palette.cycles` field, `step_cycles()` method)
- Modify: `src/app.py` (integrate cycle stepping into `_animate_step()`, rendering substitution)
- Modify: `src/project.py` (serialize/deserialize `"color_cycles"` array)
- Create: `src/ui/color_cycle_dialog.py` (cycle editor dialog)
- Test: `tests/test_color_cycling.py` (create)

- [ ] **Step 1: Write failing tests**

Create `tests/test_color_cycling.py`:

```python
"""Tests for color cycling (animated palette)."""
from src.palette import Palette, ColorCycle


class TestColorCycleDataclass:
    def test_create_cycle(self):
        cycle = ColorCycle(start_index=2, end_index=5, speed_ms=200,
                           direction="forward")
        assert cycle.start_index == 2
        assert cycle.end_index == 5
        assert cycle.speed_ms == 200
        assert cycle.direction == "forward"

    def test_default_direction(self):
        cycle = ColorCycle(start_index=0, end_index=3, speed_ms=100)
        assert cycle.direction == "forward"

    def test_cycle_to_dict(self):
        cycle = ColorCycle(start_index=1, end_index=4, speed_ms=150,
                           direction="reverse")
        d = cycle.to_dict()
        assert d == {"start_index": 1, "end_index": 4,
                     "speed_ms": 150, "direction": "reverse"}

    def test_cycle_from_dict(self):
        d = {"start_index": 2, "end_index": 6, "speed_ms": 300,
             "direction": "pingpong"}
        cycle = ColorCycle.from_dict(d)
        assert cycle.start_index == 2
        assert cycle.end_index == 6
        assert cycle.direction == "pingpong"


class TestPaletteCycles:
    def test_palette_has_empty_cycles_by_default(self):
        pal = Palette("Pico-8")
        assert hasattr(pal, 'cycles')
        assert pal.cycles == []

    def test_add_cycle(self):
        pal = Palette("Pico-8")
        cycle = ColorCycle(start_index=0, end_index=3, speed_ms=100)
        pal.cycles.append(cycle)
        assert len(pal.cycles) == 1

    def test_step_forward_cycle(self):
        pal = Palette("Pico-8")
        original = list(pal.colors)
        cycle = ColorCycle(start_index=0, end_index=3, speed_ms=100,
                           direction="forward")
        pal.cycles.append(cycle)

        # Step once: colors[0:4] should rotate forward by 1
        # forward rotation: last color moves to front
        pal.step_cycles()
        assert pal.colors[0] == original[3]
        assert pal.colors[1] == original[0]
        assert pal.colors[2] == original[1]
        assert pal.colors[3] == original[2]
        # Colors outside range unchanged
        assert pal.colors[4] == original[4]

    def test_step_reverse_cycle(self):
        pal = Palette("Pico-8")
        original = list(pal.colors)
        cycle = ColorCycle(start_index=0, end_index=3, speed_ms=100,
                           direction="reverse")
        pal.cycles.append(cycle)

        # Reverse: first color moves to end
        pal.step_cycles()
        assert pal.colors[0] == original[1]
        assert pal.colors[1] == original[2]
        assert pal.colors[2] == original[3]
        assert pal.colors[3] == original[0]

    def test_step_preserves_colors_outside_range(self):
        pal = Palette("Pico-8")
        original = list(pal.colors)
        cycle = ColorCycle(start_index=4, end_index=7, speed_ms=100)
        pal.cycles.append(cycle)
        pal.step_cycles()
        # Indices 0-3 should be unchanged
        for i in range(4):
            assert pal.colors[i] == original[i]


class TestColorCycleSerialization:
    def test_roundtrip_project_save_load(self):
        """Color cycles survive save/load round-trip."""
        import tempfile, os
        from src.animation import AnimationTimeline
        from src.project import save_project, load_project

        pal = Palette("Pico-8")
        pal.cycles = [
            ColorCycle(start_index=0, end_index=3, speed_ms=100,
                       direction="forward"),
            ColorCycle(start_index=8, end_index=12, speed_ms=200,
                       direction="reverse"),
        ]
        timeline = AnimationTimeline(16, 16)
        path = os.path.join(tempfile.gettempdir(), "test_cycles.retro")
        try:
            save_project(path, timeline, pal)
            _, loaded_pal, _ = load_project(path)
            assert len(loaded_pal.cycles) == 2
            assert loaded_pal.cycles[0].start_index == 0
            assert loaded_pal.cycles[0].direction == "forward"
            assert loaded_pal.cycles[1].speed_ms == 200
        finally:
            os.unlink(path)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_color_cycling.py -v`
Expected: FAIL — `ImportError: cannot import name 'ColorCycle'`

- [ ] **Step 3: Implement `ColorCycle` dataclass**

Add to `src/palette.py` before the `Palette` class (after imports, ~line 3):

```python
from dataclasses import dataclass, field


@dataclass
class ColorCycle:
    """Defines a range of palette indices that rotate during animation."""
    start_index: int
    end_index: int
    speed_ms: int
    direction: str = "forward"  # "forward", "reverse", "pingpong"
    _pingpong_forward: bool = field(default=True, repr=False)
    _elapsed_ms: int = field(default=0, repr=False)

    def to_dict(self) -> dict:
        return {
            "start_index": self.start_index,
            "end_index": self.end_index,
            "speed_ms": self.speed_ms,
            "direction": self.direction,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ColorCycle:
        return cls(
            start_index=d["start_index"],
            end_index=d["end_index"],
            speed_ms=d["speed_ms"],
            direction=d.get("direction", "forward"),
        )
```

- [ ] **Step 4: Add `cycles` field and `step_cycles()` to Palette**

In `src/palette.py`, in `Palette.__init__()`, add after `self.selected_index: int = 0` (~line 43):

```python
self.cycles: list[ColorCycle] = []
```

Add method to `Palette` class:

```python
def step_cycles(self) -> None:
    """Advance all color cycles by one step."""
    for cycle in self.cycles:
        start = cycle.start_index
        end = cycle.end_index
        if start >= len(self.colors) or end >= len(self.colors):
            continue
        sub = self.colors[start:end + 1]
        if len(sub) < 2:
            continue

        if cycle.direction == "forward":
            # Rotate right: last element moves to front
            rotated = [sub[-1]] + sub[:-1]
        elif cycle.direction == "reverse":
            # Rotate left: first element moves to end
            rotated = sub[1:] + [sub[0]]
        elif cycle.direction == "pingpong":
            if cycle._pingpong_forward:
                rotated = [sub[-1]] + sub[:-1]
            else:
                rotated = sub[1:] + [sub[0]]
            # Reverse direction on each step
            cycle._pingpong_forward = not cycle._pingpong_forward
        else:
            continue

        self.colors[start:end + 1] = rotated
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_color_cycling.py -v`
Expected: `TestColorCycleDataclass` and `TestPaletteCycles` PASS. `TestColorCycleSerialization` still FAILS (project.py not updated yet).

- [ ] **Step 6: Add color_cycles serialization to project.py**

In `src/project.py`, in `save_project()`, add to the `project` dict (after `"tool_settings"`, ~line 142):

```python
"color_cycles": [c.to_dict() for c in getattr(palette, 'cycles', [])],
```

In `load_project()`, after palette colors are loaded (~line 178), add:

```python
from src.palette import ColorCycle
palette.cycles = [ColorCycle.from_dict(c) for c in project.get("color_cycles", [])]
```

- [ ] **Step 7: Run full test suite for color cycling**

Run: `python -m pytest tests/test_color_cycling.py -v`
Expected: All tests PASS.

- [ ] **Step 8: Integrate cycle stepping into animation playback**

In `src/app.py`, modify `_animate_step()` (line 2059). After the `self.timeline.set_current(frame_idx)` call (~line 2078), add cycle accumulation and stepping:

```python
# Color cycle stepping (integrated with animation timer, not separate)
if hasattr(self, '_palette') and hasattr(self._palette, 'cycles'):
    for cycle in self._palette.cycles:
        cycle._elapsed_ms += delay
        if cycle._elapsed_ms >= cycle.speed_ms:
            steps = cycle._elapsed_ms // cycle.speed_ms
            cycle._elapsed_ms %= cycle.speed_ms
            for _ in range(steps):
                self._palette.step_cycles()
            self._refresh_palette_display()
```

Note: `delay` is the frame duration computed below. Move the `delay` computation above this block, or use the previous frame's duration.

- [ ] **Step 9: Reset cycle elapsed times on play/stop**

In `_play_animation()`, before starting, reset elapsed accumulators:

```python
for cycle in getattr(self._palette, 'cycles', []):
    cycle._elapsed_ms = 0
```

In `_stop_animation()`, optionally restore original palette colors (or leave cycled state — design choice).

- [ ] **Step 10: Create color cycle editor dialog**

Create `src/ui/color_cycle_dialog.py`:

```python
"""Color Cycle editor dialog for RetroSprite."""
import tkinter as tk
from tkinter import ttk
from src.palette import ColorCycle
from src.ui.theme import (
    BG_PANEL, BG_DEEP, BORDER, ACCENT_CYAN,
    TEXT_PRIMARY, TEXT_SECONDARY, BUTTON_BG,
    style_button, style_label
)


class ColorCycleDialog(tk.Toplevel):
    """Dialog for defining and editing palette color cycles."""

    def __init__(self, parent, palette, on_save=None):
        super().__init__(parent)
        self.title("Color Cycling")
        self.configure(bg=BG_DEEP)
        self.palette = palette
        self._on_save = on_save
        self._preview_after_id = None

        # ... build UI: list of cycles, add/remove buttons,
        # start/end index spinboxes, speed spinbox, direction dropdown,
        # preview button, OK/Cancel
```

Wire the dialog to the palette context menu in `src/app.py` (right-click on palette area → "Color Cycling..." menu item).

- [ ] **Step 11: Run all existing tests for regression**

Run: `python -m pytest tests/ -v --tb=short`
Expected: No regressions.

---

### Task 4: More Ink Modes + Kaleidoscope Symmetry

**Goal:** Add three new ink modes (Smear, Halftone, Tint) and one new symmetry mode (Kaleidoscope — N-fold rotational, 2-12 segments).

**Files:**
- Modify: `src/tools.py` (add `smear_ink()`, `halftone_ink()`, `tint_ink()` helper functions)
- Modify: `src/app.py` (ink mode routing in draw handlers, kaleidoscope symmetry math in `_apply_symmetry_draw()`, `_prev_draw_pos` tracking for smear)
- Modify: `src/ui/options_bar.py` (add new modes to `_INK_MODES`, kaleidoscope segment count control, add kaleidoscope to symmetry cycle)
- Modify: `src/tool_settings.py` (add `"kaleidoscope_segments"` to pen/eraser defaults)
- Test: `tests/test_new_ink_modes.py` (create)

- [ ] **Step 1: Write failing tests for ink mode helpers**

Create `tests/test_new_ink_modes.py`:

```python
"""Tests for Smear, Halftone, and Tint ink modes."""
import numpy as np
from src.pixel_data import PixelGrid
from src.tools import smear_ink, halftone_ink, tint_ink


class TestSmearInk:
    def test_smear_blends_with_previous(self):
        grid = PixelGrid(8, 8)
        grid.set_pixel(0, 0, (200, 0, 0, 255))
        grid.set_pixel(1, 0, (0, 200, 0, 255))
        smear_ink(grid, 1, 0, 0, 0, strength=0.5)
        r, g, b, a = grid.get_pixel(1, 0)
        # Should be blend of (0,200,0) and (200,0,0) at 50%
        assert 80 <= r <= 120  # ~100
        assert 80 <= g <= 120  # ~100
        assert a == 255

    def test_smear_with_no_prev_pixel_is_noop(self):
        grid = PixelGrid(8, 8)
        grid.set_pixel(2, 2, (100, 100, 100, 255))
        # prev position is transparent
        smear_ink(grid, 2, 2, 3, 3, strength=0.5)
        # Should remain unchanged since prev pixel is transparent
        r, g, b, a = grid.get_pixel(2, 2)
        assert (r, g, b, a) == (100, 100, 100, 255)

    def test_smear_strength_zero_is_noop(self):
        grid = PixelGrid(8, 8)
        grid.set_pixel(0, 0, (255, 0, 0, 255))
        grid.set_pixel(1, 0, (0, 255, 0, 255))
        smear_ink(grid, 1, 0, 0, 0, strength=0.0)
        assert grid.get_pixel(1, 0) == (0, 255, 0, 255)


class TestHalftoneInk:
    def test_halftone_draws_based_on_bayer_threshold(self):
        grid = PixelGrid(8, 8)
        fg_color = (255, 0, 0, 255)
        drawn = 0
        for x in range(4):
            for y in range(4):
                halftone_ink(grid, x, y, fg_color, brightness=0.5)
                if grid.get_pixel(x, y) == fg_color:
                    drawn += 1
        # At 50% brightness, roughly half the 4x4 Bayer matrix passes
        assert 4 <= drawn <= 12  # approximately half of 16

    def test_halftone_brightness_1_draws_all(self):
        grid = PixelGrid(8, 8)
        fg_color = (255, 0, 0, 255)
        for x in range(4):
            for y in range(4):
                halftone_ink(grid, x, y, fg_color, brightness=1.0)
        for x in range(4):
            for y in range(4):
                assert grid.get_pixel(x, y) == fg_color

    def test_halftone_brightness_0_draws_none(self):
        grid = PixelGrid(8, 8)
        fg_color = (255, 0, 0, 255)
        for x in range(4):
            for y in range(4):
                halftone_ink(grid, x, y, fg_color, brightness=0.0)
        for x in range(4):
            for y in range(4):
                assert grid.get_pixel(x, y) == (0, 0, 0, 0)


class TestTintInk:
    def test_tint_blends_foreground_with_existing(self):
        grid = PixelGrid(8, 8)
        grid.set_pixel(2, 2, (0, 0, 200, 255))
        tint_ink(grid, 2, 2, (200, 0, 0, 255), strength=0.5)
        r, g, b, a = grid.get_pixel(2, 2)
        # lerp(0, 200, 0.5) = 100; lerp(200, 0, 0.5) = 100
        assert 90 <= r <= 110
        assert 90 <= b <= 110
        assert a == 255

    def test_tint_strength_0_is_noop(self):
        grid = PixelGrid(8, 8)
        grid.set_pixel(1, 1, (100, 100, 100, 255))
        tint_ink(grid, 1, 1, (255, 0, 0, 255), strength=0.0)
        assert grid.get_pixel(1, 1) == (100, 100, 100, 255)

    def test_tint_strength_1_replaces(self):
        grid = PixelGrid(8, 8)
        grid.set_pixel(1, 1, (100, 100, 100, 255))
        tint_ink(grid, 1, 1, (255, 0, 0, 255), strength=1.0)
        assert grid.get_pixel(1, 1) == (255, 0, 0, 255)

    def test_tint_on_transparent_is_noop(self):
        grid = PixelGrid(8, 8)
        tint_ink(grid, 0, 0, (255, 0, 0, 255), strength=0.5)
        # Transparent pixel should remain transparent
        assert grid.get_pixel(0, 0) == (0, 0, 0, 0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_new_ink_modes.py -v`
Expected: FAIL — `ImportError: cannot import name 'smear_ink'`

- [ ] **Step 3: Implement ink mode helper functions in tools.py**

Add to `src/tools.py` after the `DITHER_PATTERNS` dict (~line 13):

```python
# 4x4 Bayer dither matrix for halftone ink mode
BAYER_4X4 = [
    [0,  8,  2,  10],
    [12, 4,  14, 6],
    [3,  11, 1,  9],
    [15, 7,  13, 5],
]


def smear_ink(grid: PixelGrid, x: int, y: int, prev_x: int, prev_y: int,
              strength: float = 0.5) -> None:
    """Smear: blend pixel at (x,y) with pixel from previous position."""
    current = grid.get_pixel(x, y)
    prev = grid.get_pixel(prev_x, prev_y)
    if current is None or prev is None:
        return
    if current[3] == 0 or prev[3] == 0:
        return
    r = int(current[0] + (prev[0] - current[0]) * strength + 0.5)
    g = int(current[1] + (prev[1] - current[1]) * strength + 0.5)
    b = int(current[2] + (prev[2] - current[2]) * strength + 0.5)
    a = int(current[3] + (prev[3] - current[3]) * strength + 0.5)
    grid.set_pixel(x, y, (
        max(0, min(255, r)),
        max(0, min(255, g)),
        max(0, min(255, b)),
        max(0, min(255, a)),
    ))


def halftone_ink(grid: PixelGrid, x: int, y: int,
                 fg_color: tuple, brightness: float = 0.5) -> None:
    """Halftone: apply ordered Bayer dither based on brightness threshold."""
    threshold = BAYER_4X4[y % 4][x % 4] / 16.0
    if brightness > threshold:
        grid.set_pixel(x, y, fg_color)


def tint_ink(grid: PixelGrid, x: int, y: int,
             fg_color: tuple, strength: float = 0.3) -> None:
    """Tint: blend foreground color with existing pixel at configurable ratio."""
    existing = grid.get_pixel(x, y)
    if existing is None or existing[3] == 0:
        return
    r = int(existing[0] + (fg_color[0] - existing[0]) * strength + 0.5)
    g = int(existing[1] + (fg_color[1] - existing[1]) * strength + 0.5)
    b = int(existing[2] + (fg_color[2] - existing[2]) * strength + 0.5)
    a = int(existing[3] + (fg_color[3] - existing[3]) * strength + 0.5)
    grid.set_pixel(x, y, (
        max(0, min(255, r)),
        max(0, min(255, g)),
        max(0, min(255, b)),
        max(0, min(255, a)),
    ))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_new_ink_modes.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Add new ink modes to options_bar.py cycle**

In `src/ui/options_bar.py`, update `_INK_MODES` list (line 186):

```python
_INK_MODES = ["Normal", "αLock", "Behind", "Smear", "Halftone", "Tint"]
```

Update `_cycle_ink_mode()` — extend `mode_map` (line 196):

```python
mode_map = {
    "Normal": "normal", "αLock": "alpha_lock", "Behind": "behind",
    "Smear": "smear", "Halftone": "halftone", "Tint": "tint",
}
```

- [ ] **Step 6: Route new ink modes in app.py draw handlers**

In `src/app.py`, in the draw function inside `_on_canvas_click` / `_on_canvas_drag`, add routing for new ink modes:

```python
ink_mode = self._current_ink_mode  # or from tool settings
if ink_mode == "smear":
    from src.tools import smear_ink
    smear_ink(grid, x, y, self._prev_draw_x, self._prev_draw_y,
              strength=0.5)
elif ink_mode == "halftone":
    from src.tools import halftone_ink
    pixel = grid.get_pixel(x, y)
    brightness = (0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2]) / 255
    halftone_ink(grid, x, y, color, brightness=brightness)
elif ink_mode == "tint":
    from src.tools import tint_ink
    tint_ink(grid, x, y, color, strength=0.3)
```

Track previous draw position for smear:

```python
# In _on_canvas_click:
self._prev_draw_x = x
self._prev_draw_y = y

# In _on_canvas_drag, after drawing:
self._prev_draw_x = x
self._prev_draw_y = y
```

- [ ] **Step 7: Write and run kaleidoscope symmetry tests**

Add to `tests/test_new_ink_modes.py`:

```python
import math


class TestKaleidoscopeSymmetry:
    def test_kaleidoscope_generates_correct_point_count(self):
        """N-fold kaleidoscope generates N draw positions."""
        from src.app_helpers import kaleidoscope_points
        cx, cy = 50, 50
        points = kaleidoscope_points(60, 30, cx, cy, segments=6)
        assert len(points) == 6

    def test_kaleidoscope_2_segments_is_180_rotation(self):
        from src.app_helpers import kaleidoscope_points
        cx, cy = 50, 50
        points = kaleidoscope_points(60, 50, cx, cy, segments=2)
        # Original point + 180-degree rotation
        assert points[0] == (60, 50)
        assert points[1] == (40, 50)  # 2*50-60, 2*50-50

    def test_kaleidoscope_4_segments_includes_90_degree_rotations(self):
        from src.app_helpers import kaleidoscope_points
        cx, cy = 50, 50
        points = kaleidoscope_points(55, 50, cx, cy, segments=4)
        assert len(points) == 4
        # Point is 5px right of center; rotations should be
        # 0°: (55,50), 90°: (50,55), 180°: (45,50), 270°: (50,45)
        assert (55, 50) in points
        assert (50, 55) in points
        assert (45, 50) in points
        assert (50, 45) in points
```

- [ ] **Step 8: Implement kaleidoscope_points helper**

Create or add to a helpers module. Since app.py is large, add a small helper. The simplest approach is to add the function directly in `src/app.py` or create `src/app_helpers.py`:

If creating `src/app_helpers.py`:

```python
"""Helper functions for app.py drawing operations."""
import math


def kaleidoscope_points(x: int, y: int, cx: int, cy: int,
                        segments: int) -> list[tuple[int, int]]:
    """Generate N rotated copies of (x, y) around center (cx, cy).

    Returns list of (x, y) integer coordinates for each segment.
    """
    dx = x - cx
    dy = y - cy
    angle_step = 2 * math.pi / segments
    points = []
    for i in range(segments):
        angle = i * angle_step
        rx = dx * math.cos(angle) - dy * math.sin(angle)
        ry = dx * math.sin(angle) + dy * math.cos(angle)
        points.append((round(cx + rx), round(cy + ry)))
    return points
```

- [ ] **Step 9: Run kaleidoscope tests**

Run: `python -m pytest tests/test_new_ink_modes.py::TestKaleidoscopeSymmetry -v`
Expected: All PASS.

- [ ] **Step 10: Integrate kaleidoscope into symmetry system**

In `src/app.py`, modify `_apply_symmetry_draw()` (line 1428):

```python
def _apply_symmetry_draw(self, fn, x, y):
    """Apply a draw function with symmetry mirroring."""
    fn(x, y)
    cx = self.timeline.width // 2
    cy = self.timeline.height // 2
    if self._symmetry_mode == "kaleidoscope":
        from src.app_helpers import kaleidoscope_points
        segments = getattr(self, '_kaleidoscope_segments', 6)
        points = kaleidoscope_points(x, y, cx, cy, segments)
        for px, py in points[1:]:  # skip index 0 (already drawn above)
            fn(px, py)
        return
    if self._symmetry_mode in ("horizontal", "both"):
        fn(2 * cx - x - 1, y)
    if self._symmetry_mode in ("vertical", "both"):
        fn(x, 2 * cy - y - 1)
    if self._symmetry_mode == "both":
        fn(2 * cx - x - 1, 2 * cy - y - 1)
```

- [ ] **Step 11: Add kaleidoscope to symmetry cycle in options_bar.py**

In `src/ui/options_bar.py`, update `self._sym_options` (line 87):

```python
self._sym_options = ["off", "horizontal", "vertical", "both", "kaleidoscope"]
```

Add a segment count control (shown only when symmetry is "kaleidoscope"):

```python
# Kaleidoscope segment count
self._kal_frame = tk.Frame(self, bg=BG_PANEL)
tk.Label(self._kal_frame, text="Seg:", font=("Consolas", 8),
         bg=BG_PANEL, fg=TEXT_SECONDARY).pack(side="left", padx=(8, 2))
self._kal_var = tk.IntVar(value=6)
tk.Button(self._kal_frame, text="-", width=2, font=("Consolas", 8),
          bg=BUTTON_BG, fg=TEXT_PRIMARY, relief="flat",
          command=lambda: self._change_kal_segments(-1)).pack(side="left")
tk.Label(self._kal_frame, textvariable=self._kal_var,
         font=("Consolas", 9, "bold"), bg=BG_PANEL, fg=TEXT_PRIMARY,
         width=2).pack(side="left")
tk.Button(self._kal_frame, text="+", width=2, font=("Consolas", 8),
          bg=BUTTON_BG, fg=TEXT_PRIMARY, relief="flat",
          command=lambda: self._change_kal_segments(1)).pack(side="left")
```

Show/hide based on current symmetry mode in `_cycle_symmetry()`.

- [ ] **Step 12: Add kaleidoscope_segments to tool_settings.py**

In `src/tool_settings.py`, add `"kaleidoscope_segments": 6` to `"pen"` and `"eraser"` in `TOOL_DEFAULTS`:

```python
"pen":     {"size": 1, "symmetry": "off", "dither": "none",
            "pixel_perfect": False, "ink_mode": "normal",
            "kaleidoscope_segments": 6},
"eraser":  {"size": 3, "symmetry": "off", "pixel_perfect": False,
            "ink_mode": "normal", "kaleidoscope_segments": 6},
```

- [ ] **Step 13: Run all existing tests for regression**

Run: `python -m pytest tests/ -v --tb=short`
Expected: No regressions.

---

## Chunk 3: APNG Import

### Task 5: APNG Import

**Goal:** Detect animated PNG files on `File > Open` and import each frame as a separate animation frame with per-frame duration.

**Files:**
- Create: `src/apng_import.py` (APNG frame extraction logic)
- Modify: `src/app.py` (detect APNG on open, route to importer)
- Test: `tests/test_apng_import.py` (create)

- [ ] **Step 1: Write failing tests**

Create `tests/test_apng_import.py`:

```python
"""Tests for APNG import."""
import tempfile
import os
import numpy as np
from PIL import Image
from src.apng_import import extract_apng_frames, is_apng


class TestIsApng:
    def test_static_png_is_not_apng(self):
        img = Image.new("RGBA", (8, 8), (255, 0, 0, 255))
        path = os.path.join(tempfile.gettempdir(), "test_static.png")
        img.save(path)
        try:
            assert is_apng(path) is False
        finally:
            os.unlink(path)

    def test_apng_is_detected(self):
        """Create a multi-frame PNG and verify detection."""
        frames = [
            Image.new("RGBA", (8, 8), (255, 0, 0, 255)),
            Image.new("RGBA", (8, 8), (0, 255, 0, 255)),
        ]
        path = os.path.join(tempfile.gettempdir(), "test_anim.png")
        frames[0].save(path, save_all=True, append_images=frames[1:],
                       duration=[100, 200], loop=0)
        try:
            assert is_apng(path) is True
        finally:
            os.unlink(path)


class TestExtractApngFrames:
    def _make_apng(self, n_frames=3, size=(8, 8)):
        """Helper: create a temp APNG with n_frames solid-color frames."""
        colors = [
            (255, 0, 0, 255),
            (0, 255, 0, 255),
            (0, 0, 255, 255),
            (255, 255, 0, 255),
        ]
        frames = [Image.new("RGBA", size, colors[i % len(colors)])
                  for i in range(n_frames)]
        durations = [100 + i * 50 for i in range(n_frames)]
        path = os.path.join(tempfile.gettempdir(), "test_extract.png")
        frames[0].save(path, save_all=True, append_images=frames[1:],
                       duration=durations, loop=0)
        return path, durations

    def test_extracts_correct_frame_count(self):
        path, _ = self._make_apng(3)
        try:
            frames = extract_apng_frames(path)
            assert len(frames) == 3
        finally:
            os.unlink(path)

    def test_frames_have_correct_dimensions(self):
        path, _ = self._make_apng(2, size=(16, 12))
        try:
            frames = extract_apng_frames(path)
            for frame_img, duration in frames:
                assert frame_img.size == (16, 12)
                assert frame_img.mode == "RGBA"
        finally:
            os.unlink(path)

    def test_frame_durations_preserved(self):
        path, expected_durations = self._make_apng(3)
        try:
            frames = extract_apng_frames(path)
            actual_durations = [d for _, d in frames]
            assert actual_durations == expected_durations
        finally:
            os.unlink(path)

    def test_frame_pixels_are_correct(self):
        path, _ = self._make_apng(2, size=(4, 4))
        try:
            frames = extract_apng_frames(path)
            # First frame should be red
            img0, _ = frames[0]
            assert img0.getpixel((0, 0)) == (255, 0, 0, 255)
            # Second frame should be green
            img1, _ = frames[1]
            assert img1.getpixel((0, 0)) == (0, 255, 0, 255)
        finally:
            os.unlink(path)

    def test_default_duration_when_missing(self):
        """Frames without explicit duration get 100ms default."""
        img = Image.new("RGBA", (8, 8), (255, 0, 0, 255))
        path = os.path.join(tempfile.gettempdir(), "test_no_dur.png")
        # Save as static PNG — if opened as APNG, should get default duration
        img.save(path)
        try:
            # Static PNGs are handled by is_apng check, but if someone
            # passes a path directly:
            frames = extract_apng_frames(path)
            assert len(frames) == 1
            _, dur = frames[0]
            assert dur == 100
        finally:
            os.unlink(path)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_apng_import.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.apng_import'`

- [ ] **Step 3: Implement `src/apng_import.py`**

Create `src/apng_import.py`:

```python
"""APNG (Animated PNG) import for RetroSprite.

Detects animated PNG files and extracts individual frames with durations.
Uses PIL's built-in APNG support (Pillow >= 8.0).
"""
from __future__ import annotations
from PIL import Image


def is_apng(filepath: str) -> bool:
    """Return True if the file is an animated PNG."""
    try:
        img = Image.open(filepath)
        return getattr(img, 'is_animated', False)
    except Exception:
        return False


def extract_apng_frames(filepath: str) -> list[tuple[Image.Image, int]]:
    """Extract all frames from an APNG file.

    Returns:
        List of (frame_image, duration_ms) tuples.
        Each frame_image is an RGBA PIL Image.
        duration_ms defaults to 100 if not specified.
    """
    img = Image.open(filepath)
    frames: list[tuple[Image.Image, int]] = []

    n_frames = getattr(img, 'n_frames', 1)
    for i in range(n_frames):
        img.seek(i)
        frame = img.copy().convert("RGBA")
        duration = img.info.get("duration", 100)
        if duration <= 0:
            duration = 100
        frames.append((frame, duration))

    return frames


def apng_to_timeline(filepath: str):
    """Import APNG as an AnimationTimeline.

    Returns:
        (AnimationTimeline, Palette) tuple ready to use.
    """
    from src.animation import AnimationTimeline, Frame
    from src.layer import Layer
    from src.pixel_data import PixelGrid
    from src.palette import Palette
    import numpy as np

    frames_data = extract_apng_frames(filepath)
    if not frames_data:
        raise ValueError(f"No frames found in {filepath}")

    first_img, _ = frames_data[0]
    w, h = first_img.size

    timeline = AnimationTimeline(w, h)
    timeline._frames.clear()

    # Collect all unique colors for palette extraction
    all_colors = set()

    for frame_img, duration_ms in frames_data:
        frame = Frame(w, h)
        frame.duration_ms = duration_ms
        layer = frame.layers[0]

        arr = np.array(frame_img, dtype=np.uint8)
        layer.pixels._pixels = arr

        # Collect non-transparent colors
        for y in range(h):
            for x in range(w):
                rgba = tuple(arr[y, x])
                if rgba[3] > 0:
                    all_colors.add(rgba)

        timeline._frames.append(frame)

    timeline.set_current(0)

    # Build palette from extracted colors (up to 256)
    palette = Palette("Imported")
    palette.colors = sorted(list(all_colors))[:256]
    if not palette.colors:
        palette.colors = [(0, 0, 0, 255)]

    return timeline, palette
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_apng_import.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Write integration test for apng_to_timeline**

Add to `tests/test_apng_import.py`:

```python
class TestApngToTimeline:
    def test_creates_timeline_with_correct_frame_count(self):
        from src.apng_import import apng_to_timeline
        # Create temp APNG
        frames = [
            Image.new("RGBA", (8, 8), (255, 0, 0, 255)),
            Image.new("RGBA", (8, 8), (0, 255, 0, 255)),
            Image.new("RGBA", (8, 8), (0, 0, 255, 255)),
        ]
        path = os.path.join(tempfile.gettempdir(), "test_tl.png")
        frames[0].save(path, save_all=True, append_images=frames[1:],
                       duration=[100, 150, 200], loop=0)
        try:
            timeline, palette = apng_to_timeline(path)
            assert timeline.frame_count == 3
            assert timeline.width == 8
            assert timeline.height == 8
        finally:
            os.unlink(path)

    def test_frame_durations_preserved_in_timeline(self):
        from src.apng_import import apng_to_timeline
        frames = [
            Image.new("RGBA", (8, 8), (255, 0, 0, 255)),
            Image.new("RGBA", (8, 8), (0, 255, 0, 255)),
        ]
        path = os.path.join(tempfile.gettempdir(), "test_dur.png")
        frames[0].save(path, save_all=True, append_images=frames[1:],
                       duration=[100, 250], loop=0)
        try:
            timeline, _ = apng_to_timeline(path)
            assert timeline.get_frame_obj(0).duration_ms == 100
            assert timeline.get_frame_obj(1).duration_ms == 250
        finally:
            os.unlink(path)

    def test_palette_extracted_from_frames(self):
        from src.apng_import import apng_to_timeline
        frames = [
            Image.new("RGBA", (4, 4), (255, 0, 0, 255)),
            Image.new("RGBA", (4, 4), (0, 255, 0, 255)),
        ]
        path = os.path.join(tempfile.gettempdir(), "test_pal.png")
        frames[0].save(path, save_all=True, append_images=frames[1:],
                       duration=100, loop=0)
        try:
            _, palette = apng_to_timeline(path)
            assert (255, 0, 0, 255) in palette.colors
            assert (0, 255, 0, 255) in palette.colors
        finally:
            os.unlink(path)
```

- [ ] **Step 6: Run integration tests**

Run: `python -m pytest tests/test_apng_import.py::TestApngToTimeline -v`
Expected: All PASS.

- [ ] **Step 7: Integrate APNG detection into app.py file open**

In `src/app.py`, locate the `_open_file()` or `_open_project()` method. Before the existing file-type handling, add APNG detection:

```python
from src.apng_import import is_apng, apng_to_timeline

# In the open file handler, after getting filepath:
if filepath.lower().endswith('.png') and is_apng(filepath):
    timeline, palette = apng_to_timeline(filepath)
    self.timeline = timeline
    self._palette = palette
    # ... refresh all UI panels
    self._update_status(f"Imported APNG: {os.path.basename(filepath)}")
    return
```

- [ ] **Step 8: Add "Import APNG..." menu item (optional explicit entry)**

In addition to auto-detection on Open, add `File > Import > Animated PNG...` as an explicit menu option for clarity. This reuses `apng_to_timeline()`.

- [ ] **Step 9: Run all existing tests for regression**

Run: `python -m pytest tests/ -v --tb=short`
Expected: No regressions. All new and existing tests PASS.

- [ ] **Step 10: Manual integration testing**

1. Create a test APNG file with multiple frames at different durations
2. Open it in RetroSprite via File > Open
3. Verify correct frame count in timeline
4. Play animation and verify frame durations are respected
5. Verify palette contains colors from the imported frames
