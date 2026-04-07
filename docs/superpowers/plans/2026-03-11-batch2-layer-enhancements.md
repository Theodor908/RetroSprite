# Batch 2: Layer Enhancements — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Add 9 blend modes to compositing and implement layer groups using flat-list-with-depth.

**Architecture:** Blend mode math via NumPy array operations in layer.py. Layer groups use existing flat list with `depth`/`is_group` properties — no tree restructuring.

**Tech Stack:** Python 3.8+, NumPy, PIL, Tkinter, pytest

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `src/layer.py` | Modify | Add blend mode functions, update flatten_layers, add depth/is_group to Layer |
| `src/app.py` | Modify | Add group operations, blend mode change callback |
| `src/ui/timeline.py` | Modify | Blend mode dropdown, group indent, collapse toggle |
| `src/animation.py` | Modify | Add group-aware layer operations |
| `src/project.py` | Modify | Serialize/deserialize depth and is_group |
| `tests/test_layer.py` | Modify | Blend mode tests, group compositing tests |
| `tests/test_tools.py` | None | No changes needed |

---

## Chunk 1: Blend Modes

### Task 1: Implement blend mode math

**Files:**
- Modify: `src/layer.py`
- Modify: `tests/test_layer.py`

- [ ] **Step 1: Write failing tests for blend modes**

Add to `tests/test_layer.py`:

```python
from src.layer import Layer, flatten_layers, apply_blend_mode
import numpy as np

class TestBlendModes:
    def _make_arrays(self, base_rgb, blend_rgb):
        """Create 1x1 RGBA arrays for testing."""
        base = np.array([[list(base_rgb) + [255]]], dtype=np.uint8)
        blend = np.array([[list(blend_rgb) + [255]]], dtype=np.uint8)
        return base, blend

    def test_normal_mode(self):
        base, blend = self._make_arrays((100, 100, 100), (200, 200, 200))
        result = apply_blend_mode(base, blend, "normal")
        assert tuple(result[0, 0, :3]) == (200, 200, 200)

    def test_multiply(self):
        base, blend = self._make_arrays((200, 100, 50), (128, 255, 0))
        result = apply_blend_mode(base, blend, "multiply")
        # 200*128//255=100, 100*255//255=100, 50*0//255=0
        assert tuple(result[0, 0, :3]) == (100, 100, 0)

    def test_screen(self):
        base, blend = self._make_arrays((100, 100, 100), (100, 100, 100))
        result = apply_blend_mode(base, blend, "screen")
        # 255 - (155*155)//255 = 255 - 94 = 161
        expected = 255 - (155 * 155) // 255
        assert tuple(result[0, 0, :3]) == (expected, expected, expected)

    def test_addition(self):
        base, blend = self._make_arrays((200, 100, 50), (100, 200, 250))
        result = apply_blend_mode(base, blend, "addition")
        assert tuple(result[0, 0, :3]) == (255, 255, 255)  # clamped

    def test_subtract(self):
        base, blend = self._make_arrays((200, 100, 50), (50, 150, 100))
        result = apply_blend_mode(base, blend, "subtract")
        assert tuple(result[0, 0, :3]) == (150, 0, 0)  # clamped at 0

    def test_darken(self):
        base, blend = self._make_arrays((200, 50, 100), (100, 100, 100))
        result = apply_blend_mode(base, blend, "darken")
        assert tuple(result[0, 0, :3]) == (100, 50, 100)

    def test_lighten(self):
        base, blend = self._make_arrays((200, 50, 100), (100, 100, 100))
        result = apply_blend_mode(base, blend, "lighten")
        assert tuple(result[0, 0, :3]) == (200, 100, 100)

    def test_difference(self):
        base, blend = self._make_arrays((200, 50, 100), (100, 100, 100))
        result = apply_blend_mode(base, blend, "difference")
        assert tuple(result[0, 0, :3]) == (100, 50, 0)

    def test_overlay_dark(self):
        """Overlay on dark base (< 128) uses multiply-like formula."""
        base, blend = self._make_arrays((50, 50, 50), (100, 100, 100))
        result = apply_blend_mode(base, blend, "overlay")
        # For base < 128: 2 * base * blend / 255
        expected = 2 * 50 * 100 // 255
        assert tuple(result[0, 0, :3]) == (expected, expected, expected)

    def test_overlay_light(self):
        """Overlay on light base (>= 128) uses screen-like formula."""
        base, blend = self._make_arrays((200, 200, 200), (100, 100, 100))
        result = apply_blend_mode(base, blend, "overlay")
        # For base >= 128: 255 - 2*(255-base)*(255-blend)/255
        expected = 255 - 2 * 55 * 155 // 255
        assert tuple(result[0, 0, :3]) == (expected, expected, expected)

    def test_unknown_mode_falls_back_to_normal(self):
        base, blend = self._make_arrays((100, 100, 100), (200, 200, 200))
        result = apply_blend_mode(base, blend, "nonexistent")
        assert tuple(result[0, 0, :3]) == (200, 200, 200)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_layer.py::TestBlendModes -v`

- [ ] **Step 3: Implement `apply_blend_mode` in `src/layer.py`**

Add before `flatten_layers`:

```python
def apply_blend_mode(base: np.ndarray, blend: np.ndarray, mode: str) -> np.ndarray:
    """Apply blend mode to RGB channels. Both arrays are (H,W,4) uint8.

    Returns a new array with blended RGB and blend's original alpha.
    """
    b = base[:, :, :3].astype(np.int32)
    l = blend[:, :, :3].astype(np.int32)

    if mode == "multiply":
        rgb = (b * l) // 255
    elif mode == "screen":
        rgb = 255 - ((255 - b) * (255 - l)) // 255
    elif mode == "overlay":
        mask = b < 128
        rgb = np.where(mask, (2 * b * l) // 255, 255 - (2 * (255 - b) * (255 - l)) // 255)
    elif mode == "addition":
        rgb = np.minimum(b + l, 255)
    elif mode == "subtract":
        rgb = np.maximum(b - l, 0)
    elif mode == "darken":
        rgb = np.minimum(b, l)
    elif mode == "lighten":
        rgb = np.maximum(b, l)
    elif mode == "difference":
        rgb = np.abs(b - l)
    else:
        # normal or unknown — just use blend layer's colors
        rgb = l

    result = blend.copy()
    result[:, :, :3] = rgb.astype(np.uint8)
    return result
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_layer.py::TestBlendModes -v`

---

### Task 2: Update `flatten_layers` to use blend modes

**Files:**
- Modify: `src/layer.py:35-52`
- Modify: `tests/test_layer.py`

- [ ] **Step 1: Write failing test**

```python
class TestBlendModeFlatten:
    def test_multiply_layer_compositing(self):
        """A multiply layer should darken the layer below."""
        bottom = Layer("bottom", 2, 2)
        bottom.pixels.set_pixel(0, 0, (200, 200, 200, 255))
        bottom.pixels.set_pixel(1, 0, (100, 100, 100, 255))

        top = Layer("top", 2, 2)
        top.blend_mode = "multiply"
        top.pixels.set_pixel(0, 0, (128, 128, 128, 255))
        top.pixels.set_pixel(1, 0, (255, 255, 255, 255))

        result = flatten_layers([bottom, top], 2, 2)
        # (0,0): 200*128//255 = 100
        assert result.get_pixel(0, 0)[0] == 200 * 128 // 255
        # (1,0): 100*255//255 = 100 (multiply by white = no change)
        assert result.get_pixel(1, 0)[0] == 100

    def test_normal_mode_unchanged(self):
        """Normal mode should work exactly as before."""
        bottom = Layer("bottom", 1, 1)
        bottom.pixels.set_pixel(0, 0, (100, 0, 0, 255))

        top = Layer("top", 1, 1)
        top.pixels.set_pixel(0, 0, (0, 200, 0, 128))

        result = flatten_layers([bottom, top], 1, 1)
        # Standard alpha composite — not pure replacement
        r, g, b, a = result.get_pixel(0, 0)
        assert a == 255
        assert g > 0  # green from top layer blended in
```

- [ ] **Step 2: Update `flatten_layers`**

Replace the function in `src/layer.py`:

```python
def flatten_layers(layers: list[Layer], width: int, height: int) -> PixelGrid:
    """Composite all visible layers into a single PixelGrid.

    Layers are composited bottom-to-top (index 0 = bottom).
    Supports blend modes and layer groups with depth.
    """
    base = Image.new("RGBA", (width, height), (0, 0, 0, 0))

    for layer in layers:
        if not layer.visible:
            continue
        if getattr(layer, 'is_group', False):
            continue  # groups don't have pixel data to composite

        layer_img = layer.pixels.to_pil_image()
        if layer.opacity < 1.0:
            arr = np.array(layer_img, dtype=np.uint8)
            arr[:, :, 3] = (arr[:, :, 3] * layer.opacity).astype(np.uint8)
            layer_img = Image.fromarray(arr, "RGBA")

        if layer.blend_mode == "normal":
            base = Image.alpha_composite(base, layer_img)
        else:
            base_arr = np.array(base, dtype=np.uint8)
            blend_arr = np.array(layer_img, dtype=np.uint8)
            # Apply blend mode to get blended RGB
            blended = apply_blend_mode(base_arr, blend_arr, layer.blend_mode)
            # Use blend layer alpha for compositing
            blend_alpha = blend_arr[:, :, 3].astype(np.float32) / 255.0
            # Lerp: result = base * (1 - alpha) + blended * alpha
            for c in range(3):
                base_arr[:, :, c] = (
                    base_arr[:, :, c] * (1.0 - blend_alpha) +
                    blended[:, :, c] * blend_alpha
                ).astype(np.uint8)
            # Alpha channel: standard union
            base_a = base_arr[:, :, 3].astype(np.float32) / 255.0
            out_a = base_a + blend_alpha * (1.0 - base_a)
            base_arr[:, :, 3] = (out_a * 255).astype(np.uint8)
            base = Image.fromarray(base_arr, "RGBA")

    return PixelGrid.from_pil_image(base)
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_layer.py -v`

---

### Task 3: Add blend mode dropdown to timeline UI

**Files:**
- Modify: `src/ui/timeline.py` (layer sidebar rendering)
- Modify: `src/app.py` (callback)

- [ ] **Step 1: Add callback to TimelinePanel**

In `src/ui/timeline.py` `__init__`, the constructor accepts callbacks. Add `on_layer_blend_mode` parameter. Store as `self._callbacks["layer_blend_mode"]`.

- [ ] **Step 2: Add blend mode dropdown in layer sidebar**

In the layer sidebar loop (where visibility/lock/name are created), add a compact OptionMenu after the name label:

```python
BLEND_MODES = ["normal", "multiply", "screen", "overlay", "addition",
               "subtract", "darken", "lighten", "difference"]
BLEND_ABBREV = {"normal": "Norm", "multiply": "Mul", "screen": "Scr",
                "overlay": "Ovr", "addition": "Add", "subtract": "Sub",
                "darken": "Drk", "lighten": "Ltn", "difference": "Dif"}

# Inside the layer sidebar loop, after name_lbl:
blend_var = tk.StringVar(value=layer.blend_mode)
blend_menu = tk.OptionMenu(row, blend_var, *BLEND_MODES,
                           command=lambda val, idx=li: self._on_blend_change(idx, val))
blend_menu.config(width=4, font=("Consolas", 7), bg=BG_PANEL,
                  fg=TEXT_SECONDARY, highlightthickness=0)
blend_menu.pack(side="right", padx=2)
```

- [ ] **Step 3: Add blend mode change handler in timeline**

```python
def _on_blend_change(self, layer_idx, value):
    cb = self._callbacks.get("layer_blend_mode")
    if cb:
        cb(layer_idx, value)
```

- [ ] **Step 4: Add callback in app.py**

In `src/app.py`, where TimelinePanel is created, add the callback:
```python
on_layer_blend_mode=self._on_blend_mode_change,
```

Implement:
```python
def _on_blend_mode_change(self, index, mode):
    """Set blend mode for layer at index across all frames."""
    for frame in self.timeline._frames:
        if index < len(frame.layers):
            frame.layers[index].blend_mode = mode
    self._render_canvas()
```

- [ ] **Step 5: Run full test suite**

Run: `python -m pytest tests/ -q`

---

## Chunk 2: Layer Groups

### Task 4: Add depth and is_group to Layer model

**Files:**
- Modify: `src/layer.py` (Layer class)
- Modify: `src/project.py` (serialization)
- Modify: `tests/test_layer.py`

- [ ] **Step 1: Add properties to Layer**

In `src/layer.py` Layer.__init__, add:
```python
self.depth: int = 0
self.is_group: bool = False
```

In `copy()`, add:
```python
new_layer.depth = self.depth
new_layer.is_group = self.is_group
```

- [ ] **Step 2: Update serialization**

In `src/project.py` save_project, add to layer dict:
```python
"depth": layer.depth,
"is_group": getattr(layer, 'is_group', False),
```

In load_project, add after blend_mode loading:
```python
layer.depth = layer_data.get("depth", 0)
layer.is_group = layer_data.get("is_group", False)
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/ -q`

---

### Task 5: Implement group-aware compositing

**Files:**
- Modify: `src/layer.py` (`flatten_layers`)
- Modify: `tests/test_layer.py`

- [ ] **Step 1: Write failing test**

```python
class TestLayerGroups:
    def test_group_compositing(self):
        """Children of a group should composite together first, then blend onto base."""
        bg = Layer("bg", 2, 1)
        bg.pixels.set_pixel(0, 0, (200, 200, 200, 255))
        bg.pixels.set_pixel(1, 0, (200, 200, 200, 255))

        group = Layer("group", 2, 1)
        group.is_group = True
        group.blend_mode = "multiply"
        group.depth = 0

        child1 = Layer("child1", 2, 1)
        child1.depth = 1
        child1.pixels.set_pixel(0, 0, (128, 128, 128, 255))

        child2 = Layer("child2", 2, 1)
        child2.depth = 1
        child2.pixels.set_pixel(1, 0, (128, 128, 128, 255))

        result = flatten_layers([bg, group, child1, child2], 2, 1)
        # Children composite normally within group, then group multiplies onto bg
        # child1+child2 produce (128,128,128) at each pixel
        # multiply: 200*128/255 = 100
        r0 = result.get_pixel(0, 0)[0]
        r1 = result.get_pixel(1, 0)[0]
        assert r0 == 200 * 128 // 255
        assert r1 == 200 * 128 // 255

    def test_group_opacity(self):
        """Group opacity should affect entire group result."""
        bg = Layer("bg", 1, 1)
        bg.pixels.set_pixel(0, 0, (0, 0, 0, 255))

        group = Layer("group", 1, 1)
        group.is_group = True
        group.opacity = 0.5
        group.depth = 0

        child = Layer("child", 1, 1)
        child.depth = 1
        child.pixels.set_pixel(0, 0, (200, 200, 200, 255))

        result = flatten_layers([bg, group, child], 1, 1)
        # Group result is (200,200,200) at 50% opacity over (0,0,0)
        r = result.get_pixel(0, 0)[0]
        assert 95 <= r <= 105  # approximately 100

    def test_hidden_group_hides_children(self):
        """Invisible group should hide all children."""
        bg = Layer("bg", 1, 1)
        bg.pixels.set_pixel(0, 0, (100, 100, 100, 255))

        group = Layer("group", 1, 1)
        group.is_group = True
        group.visible = False
        group.depth = 0

        child = Layer("child", 1, 1)
        child.depth = 1
        child.pixels.set_pixel(0, 0, (255, 0, 0, 255))

        result = flatten_layers([bg, group, child], 1, 1)
        assert result.get_pixel(0, 0) == (100, 100, 100, 255)

    def test_nested_groups(self):
        """Nested groups should composite correctly."""
        bg = Layer("bg", 1, 1)
        bg.pixels.set_pixel(0, 0, (200, 200, 200, 255))

        outer = Layer("outer", 1, 1)
        outer.is_group = True
        outer.depth = 0

        inner = Layer("inner", 1, 1)
        inner.is_group = True
        inner.blend_mode = "multiply"
        inner.depth = 1

        leaf = Layer("leaf", 1, 1)
        leaf.depth = 2
        leaf.pixels.set_pixel(0, 0, (128, 128, 128, 255))

        result = flatten_layers([bg, outer, inner, leaf], 1, 1)
        # leaf composites in inner group (multiply onto transparent = just leaf)
        # inner result multiplies... but inner composites onto outer's empty base
        # outer composites normally onto bg
        # Net: leaf alpha-composites onto bg
        r = result.get_pixel(0, 0)[0]
        assert r == 128  # multiply with empty base = just the pixels

    def test_flat_layers_still_work(self):
        """Layers without groups (depth=0) should composite normally."""
        l1 = Layer("l1", 1, 1)
        l1.pixels.set_pixel(0, 0, (100, 0, 0, 255))
        l2 = Layer("l2", 1, 1)
        l2.pixels.set_pixel(0, 0, (0, 200, 0, 255))
        result = flatten_layers([l1, l2], 1, 1)
        assert result.get_pixel(0, 0) == (0, 200, 0, 255)
```

- [ ] **Step 2: Rewrite `flatten_layers` with group support**

```python
def flatten_layers(layers: list[Layer], width: int, height: int) -> PixelGrid:
    """Composite all visible layers into a single PixelGrid.

    Layers are composited bottom-to-top (index 0 = bottom).
    Supports blend modes and layer groups (flat list with depth).
    """
    def _composite_one(base_img, layer_img, blend_mode):
        """Composite a single layer onto base using its blend mode."""
        if blend_mode == "normal":
            return Image.alpha_composite(base_img, layer_img)
        base_arr = np.array(base_img, dtype=np.uint8)
        blend_arr = np.array(layer_img, dtype=np.uint8)
        blended = apply_blend_mode(base_arr, blend_arr, blend_mode)
        blend_alpha = blend_arr[:, :, 3].astype(np.float32) / 255.0
        for c in range(3):
            base_arr[:, :, c] = (
                base_arr[:, :, c] * (1.0 - blend_alpha) +
                blended[:, :, c] * blend_alpha
            ).astype(np.uint8)
        base_a = base_arr[:, :, 3].astype(np.float32) / 255.0
        out_a = base_a + blend_alpha * (1.0 - base_a)
        base_arr[:, :, 3] = (out_a * 255).astype(np.uint8)
        return Image.fromarray(base_arr, "RGBA")

    # Stack-based group compositing
    # Each stack entry: (group_base_image, group_blend_mode, group_opacity, group_visible)
    stack = []
    current = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    skip_depth = -1  # if >= 0, skip layers deeper than this

    i = 0
    while i < len(layers):
        layer = layers[i]
        depth = getattr(layer, 'depth', 0)
        is_group = getattr(layer, 'is_group', False)

        # Check if we're exiting groups (depth decreased)
        while stack and depth <= stack[-1][4]:
            group_base, group_mode, group_opacity, group_visible, group_depth = stack.pop()
            if group_visible:
                if group_opacity < 1.0:
                    arr = np.array(current, dtype=np.uint8)
                    arr[:, :, 3] = (arr[:, :, 3] * group_opacity).astype(np.uint8)
                    current = Image.fromarray(arr, "RGBA")
                current = _composite_one(group_base, current, group_mode)
            else:
                current = group_base
            skip_depth = -1

        # Skip hidden group children
        if skip_depth >= 0 and depth > skip_depth:
            i += 1
            continue

        if is_group:
            if not layer.visible:
                skip_depth = depth
            else:
                skip_depth = -1
            stack.append((current, layer.blend_mode, layer.opacity, layer.visible, depth))
            current = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            i += 1
            continue

        skip_depth = -1
        if not layer.visible:
            i += 1
            continue

        layer_img = layer.pixels.to_pil_image()
        if layer.opacity < 1.0:
            arr = np.array(layer_img, dtype=np.uint8)
            arr[:, :, 3] = (arr[:, :, 3] * layer.opacity).astype(np.uint8)
            layer_img = Image.fromarray(arr, "RGBA")

        current = _composite_one(current, layer_img, layer.blend_mode)
        i += 1

    # Pop remaining groups
    while stack:
        group_base, group_mode, group_opacity, group_visible, group_depth = stack.pop()
        if group_visible:
            if group_opacity < 1.0:
                arr = np.array(current, dtype=np.uint8)
                arr[:, :, 3] = (arr[:, :, 3] * group_opacity).astype(np.uint8)
                current = Image.fromarray(arr, "RGBA")
            current = _composite_one(group_base, current, group_mode)
        else:
            current = group_base

    return PixelGrid.from_pil_image(current)
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_layer.py -v`

---

### Task 6: Add group UI and operations

**Files:**
- Modify: `src/app.py` (add group, collapse state)
- Modify: `src/animation.py` (add_group_to_all)
- Modify: `src/ui/timeline.py` (indent, collapse toggle)

- [ ] **Step 1: Add `add_group_to_all` to AnimationTimeline**

In `src/animation.py`, add method:

```python
def add_group_to_all(self, name: str, depth: int = 0):
    """Add a group layer to all frames."""
    for frame in self._frames:
        group = Layer(name, self._width, self._height)
        group.is_group = True
        group.depth = depth
        frame.layers.append(group)
        frame.active_layer_index = len(frame.layers) - 1
```

- [ ] **Step 2: Add group menu item in app.py**

In the Edit or Layer menu, add:
```python
layer_menu.add_command(label="Add Group", command=self._add_group)
```

Implement:
```python
def _add_group(self):
    """Add a new layer group."""
    # Determine depth from current active layer
    frame_obj = self.timeline.current_frame_obj()
    active = frame_obj.active_layer
    depth = getattr(active, 'depth', 0)
    self.timeline.add_group_to_all(f"Group {len(frame_obj.layers)}", depth=depth)
    self._refresh_timeline()
    self._render_canvas()
```

- [ ] **Step 3: Add indent and collapse to timeline UI**

In `src/ui/timeline.py`, in the layer sidebar loop:

```python
# Before creating the row widgets:
layer_depth = getattr(layer, 'depth', 0)
is_group = getattr(layer, 'is_group', False)
indent = layer_depth * 12  # pixels per depth level

# Add padding to row
row_inner = tk.Frame(row, bg=row.cget("bg"))
row_inner.pack(fill="both", expand=True, padx=(indent, 0))

# For groups: show collapse toggle
if is_group:
    collapsed = self._collapsed_groups.get(li, False)
    toggle_text = "\u25B6" if collapsed else "\u25BC"  # ▶ or ▼
    toggle_btn = tk.Button(row_inner, text=toggle_text, width=2,
                           font=("Consolas", 8), bg=BG_PANEL, fg=ACCENT_MAGENTA,
                           relief="flat",
                           command=lambda idx=li: self._toggle_group_collapse(idx))
    toggle_btn.pack(side="left", padx=1)
```

Add to `__init__`:
```python
self._collapsed_groups = {}  # {layer_index: bool}
```

Add collapse handler:
```python
def _toggle_group_collapse(self, group_idx):
    self._collapsed_groups[group_idx] = not self._collapsed_groups.get(group_idx, False)
    self.refresh()
```

Skip rendering children of collapsed groups:
```python
# In the layer sidebar loop, before creating row:
# Check if this layer is a child of a collapsed group
skip = False
for gi, is_collapsed in self._collapsed_groups.items():
    if is_collapsed and gi < num_layers:
        g_layer = current_frame.layers[gi]
        if getattr(g_layer, 'is_group', False):
            g_depth = getattr(g_layer, 'depth', 0)
            if li > gi and getattr(layer, 'depth', 0) > g_depth:
                skip = True
                break
if skip:
    continue
```

Apply the same skip logic to the cel grid loop.

- [ ] **Step 4: Run full test suite**

Run: `python -m pytest tests/ -q`

- [ ] **Step 5: Manual smoke test**

Launch app → Add Group → add layers inside → set group blend mode to Multiply → verify compositing → collapse/expand group in timeline.

---
