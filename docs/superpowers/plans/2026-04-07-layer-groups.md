# Layer Groups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make layer groups functional — layers can be assigned to groups, visually nested, and collapsed/expanded.

**Architecture:** Add three methods to `AnimationTimeline` for group operations (`set_layer_depth_all`, `move_layer_into_group`, `move_layer_out_of_group`). Fix `_add_group` to always use depth=0. Extend `TimelinePanel` with context menu items and drag-into-group detection. All rendering/compositing already works via `flatten_layers()`.

**Tech Stack:** Python, Tkinter, NumPy (existing stack)

---

### Task 1: Data Layer — Group Operations in AnimationTimeline

**Files:**
- Modify: `src/animation.py:296-311` (after `add_group_to_all`, before `move_layer_in_all`)
- Test: `tests/test_layer_groups.py` (create)

- [ ] **Step 1: Write failing test for `set_layer_depth_all`**

Create `tests/test_layer_groups.py`:

```python
"""Tests for layer group operations."""
from src.animation import AnimationTimeline


def test_set_layer_depth_all():
    tl = AnimationTimeline(8, 8)
    tl.add_group_to_all("Group 1")
    tl.add_layer_to_all("Child")
    tl.set_layer_depth_all(1, 1)
    for frame in tl._frames:
        assert frame.layers[1].depth == 1


def test_set_layer_depth_all_multiple_frames():
    tl = AnimationTimeline(8, 8)
    tl.add_frame()
    tl.add_group_to_all("Group 1")
    tl.add_layer_to_all("Child")
    tl.set_layer_depth_all(1, 1)
    for frame in tl._frames:
        assert frame.layers[1].depth == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_layer_groups.py -v`
Expected: FAIL with `AttributeError: 'AnimationTimeline' object has no attribute 'set_layer_depth_all'`

- [ ] **Step 3: Implement `set_layer_depth_all`**

In `src/animation.py`, add after `add_group_to_all` (after line 303):

```python
def set_layer_depth_all(self, idx: int, depth: int) -> None:
    """Set layer depth at given index in ALL frames."""
    for frame in self._frames:
        if 0 <= idx < len(frame.layers):
            frame.layers[idx].depth = depth
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_layer_groups.py -v`
Expected: PASS

- [ ] **Step 5: Write failing test for `move_layer_into_group`**

Append to `tests/test_layer_groups.py`:

```python
def test_move_layer_into_group():
    """Layer moves to position right after group and gets depth=1."""
    tl = AnimationTimeline(8, 8)
    # layers: [Layer 1(idx=0), Group(idx=1), Layer 2(idx=2)]
    tl.add_group_to_all("Group 1")
    tl.add_layer_to_all("Layer 2")
    # Move Layer 2 (idx=2) into Group 1 (idx=1)
    tl.move_layer_into_group(2, 1)
    frame = tl._frames[0]
    # Group stays at idx=1, Layer 2 should now be at idx=2 with depth=1
    # But it was already at idx=2, so position unchanged — depth should be set
    # Actually: group is at 1, layer moves to group_idx+1=2
    # layers: [Layer 1(0), Group(1), Layer 2(2,depth=1)]
    assert frame.layers[1].is_group
    assert frame.layers[1].name == "Group 1"
    assert frame.layers[2].name == "Layer 2"
    assert frame.layers[2].depth == 1


def test_move_layer_into_group_repositions():
    """Layer below group moves up to be right after group."""
    tl = AnimationTimeline(8, 8)
    # layers: [Layer 1(0), Layer 2(1), Group(2)]
    tl.add_layer_to_all("Layer 2")
    tl.add_group_to_all("Group 1")
    # Move Layer 1 (idx=0) into Group 1 (idx=2)
    tl.move_layer_into_group(0, 2)
    frame = tl._frames[0]
    # After pop(0): [Layer 2(0), Group(1)]
    # Group is now at idx=1, insert at 2: [Layer 2(0), Group(1), Layer 1(2)]
    assert frame.layers[1].is_group
    assert frame.layers[1].name == "Group 1"
    assert frame.layers[2].name == "Layer 1"
    assert frame.layers[2].depth == 1


def test_move_layer_into_group_rejects_group():
    """Cannot move a group into another group (one-level constraint)."""
    tl = AnimationTimeline(8, 8)
    tl.add_group_to_all("Group 1")
    tl.add_group_to_all("Group 2")
    result = tl.move_layer_into_group(2, 1)
    assert result is False
    # Groups stay at depth 0
    frame = tl._frames[0]
    assert frame.layers[1].depth == 0
    assert frame.layers[2].depth == 0


def test_move_layer_into_group_rejects_nongroup_target():
    """Cannot move a layer into a non-group layer."""
    tl = AnimationTimeline(8, 8)
    tl.add_layer_to_all("Layer 2")
    result = tl.move_layer_into_group(0, 1)
    assert result is False
```

- [ ] **Step 6: Run test to verify it fails**

Run: `python -m pytest tests/test_layer_groups.py -v`
Expected: FAIL with `AttributeError: 'AnimationTimeline' object has no attribute 'move_layer_into_group'`

- [ ] **Step 7: Implement `move_layer_into_group`**

In `src/animation.py`, add after `set_layer_depth_all`:

```python
def move_layer_into_group(self, layer_idx: int, group_idx: int) -> bool:
    """Move a layer into a group across all frames.

    Positions the layer right after the group (above existing children).
    Sets depth=1. Returns False if the operation is invalid.
    """
    if not self._frames:
        return False
    ref = self._frames[0]
    if not (0 <= layer_idx < len(ref.layers) and
            0 <= group_idx < len(ref.layers)):
        return False
    if ref.layers[layer_idx].is_group:
        return False
    if not ref.layers[group_idx].is_group:
        return False

    for frame in self._frames:
        layer = frame.layers.pop(layer_idx)
        layer.depth = 1
        # Find where the group ended up after pop
        # If layer_idx < group_idx, group shifted down by 1
        actual_group = group_idx if layer_idx > group_idx else group_idx - 1
        # Find insertion point: right after group's last existing child
        insert_at = actual_group + 1
        while (insert_at < len(frame.layers) and
               not frame.layers[insert_at].is_group and
               frame.layers[insert_at].depth > 0):
            insert_at += 1
        frame.layers.insert(insert_at, layer)
        frame.active_layer_index = insert_at
    return True
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `python -m pytest tests/test_layer_groups.py -v`
Expected: ALL PASS

- [ ] **Step 9: Write failing test for `move_layer_out_of_group`**

Append to `tests/test_layer_groups.py`:

```python
def test_move_layer_out_of_group():
    """Layer at depth=1 moves above its group and gets depth=0."""
    tl = AnimationTimeline(8, 8)
    tl.add_group_to_all("Group 1")
    tl.add_layer_to_all("Child")
    tl.set_layer_depth_all(2, 1)  # Make "Child" a child of Group 1
    tl.move_layer_out_of_group(2)
    frame = tl._frames[0]
    # Child should be above the group now (higher index = above)
    assert frame.layers[2].name == "Child"
    assert frame.layers[2].depth == 0


def test_move_layer_out_of_group_noop_at_root():
    """No-op if layer is already at depth 0."""
    tl = AnimationTimeline(8, 8)
    tl.add_layer_to_all("Layer 2")
    result = tl.move_layer_out_of_group(1)
    assert result is False
    frame = tl._frames[0]
    assert frame.layers[1].depth == 0


def test_move_layer_out_finds_parent_group():
    """Layer removed from group is placed above the parent group."""
    tl = AnimationTimeline(8, 8)
    # layers: [Layer 1(0), Group(1), Child A(2,d=1), Child B(3,d=1)]
    tl.add_group_to_all("Group 1")
    tl.add_layer_to_all("Child A")
    tl.set_layer_depth_all(2, 1)
    tl.add_layer_to_all("Child B")
    tl.set_layer_depth_all(3, 1)
    # Move Child A (idx=2) out
    tl.move_layer_out_of_group(2)
    frame = tl._frames[0]
    # Child A should be above the group (at the end or after group+children)
    # After pop(2): [Layer 1(0), Group(1), Child B(2,d=1)]
    # Insert above group = after last child = idx 3
    # Result: [Layer 1(0), Group(1), Child B(2,d=1), Child A(3,d=0)]
    assert frame.layers[3].name == "Child A"
    assert frame.layers[3].depth == 0
```

- [ ] **Step 10: Run test to verify it fails**

Run: `python -m pytest tests/test_layer_groups.py -v`
Expected: FAIL with `AttributeError: 'AnimationTimeline' object has no attribute 'move_layer_out_of_group'`

- [ ] **Step 11: Implement `move_layer_out_of_group`**

In `src/animation.py`, add after `move_layer_into_group`:

```python
def move_layer_out_of_group(self, layer_idx: int) -> bool:
    """Remove a layer from its group across all frames.

    Sets depth=0 and moves the layer above the parent group.
    Returns False if the layer is already at root level.
    """
    if not self._frames:
        return False
    ref = self._frames[0]
    if not (0 <= layer_idx < len(ref.layers)):
        return False
    if ref.layers[layer_idx].depth == 0:
        return False

    for frame in self._frames:
        layer = frame.layers.pop(layer_idx)
        layer.depth = 0
        # Find the parent group: scan backwards for the nearest group with depth < original
        parent_idx = layer_idx - 1
        while parent_idx >= 0 and not frame.layers[parent_idx].is_group:
            parent_idx -= 1
        if parent_idx < 0:
            # No parent found, just put it back at the end
            frame.layers.append(layer)
            frame.active_layer_index = len(frame.layers) - 1
            continue
        # Place above the group: find the end of the group's children
        insert_at = parent_idx + 1
        while (insert_at < len(frame.layers) and
               not frame.layers[insert_at].is_group and
               frame.layers[insert_at].depth > frame.layers[parent_idx].depth):
            insert_at += 1
        frame.layers.insert(insert_at, layer)
        frame.active_layer_index = insert_at
    return True
```

- [ ] **Step 12: Run all tests to verify they pass**

Run: `python -m pytest tests/test_layer_groups.py -v`
Expected: ALL PASS

- [ ] **Step 13: Commit**

```bash
git add tests/test_layer_groups.py src/animation.py
git commit -m "feat: add group operations — move_layer_into_group, move_layer_out_of_group, set_layer_depth_all"
```

---

### Task 2: Fix Group Creation to Always Use Depth 0

**Files:**
- Modify: `src/layer_animation.py:124-133`
- Test: `tests/test_layer_groups.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_layer_groups.py`:

```python
def test_add_group_always_depth_zero():
    """New groups are always created at depth 0, regardless of active layer depth."""
    tl = AnimationTimeline(8, 8)
    tl.add_group_to_all("Group 1")
    tl.add_layer_to_all("Child")
    tl.set_layer_depth_all(2, 1)
    # Simulate active layer being a child (depth=1)
    for frame in tl._frames:
        frame.active_layer_index = 2
    # Add another group — should be depth 0
    tl.add_group_to_all("Group 2", depth=0)
    for frame in tl._frames:
        assert frame.layers[3].is_group
        assert frame.layers[3].depth == 0
```

- [ ] **Step 2: Run test to verify it passes** (this tests the data layer which already defaults to 0)

Run: `python -m pytest tests/test_layer_groups.py::test_add_group_always_depth_zero -v`
Expected: PASS (the bug is in the mixin, not the data layer)

- [ ] **Step 3: Fix `_add_group` in the mixin**

In `src/layer_animation.py`, change lines 124-133:

Replace:
```python
def _add_group(self):
    """Add a new layer group."""
    frame_obj = self.timeline.current_frame_obj()
    active = frame_obj.active_layer
    depth = active.depth
    name = f"Group {len(frame_obj.layers)}"
    self.timeline.add_group_to_all(name, depth=depth)
```

With:
```python
def _add_group(self):
    """Add a new layer group."""
    frame_obj = self.timeline.current_frame_obj()
    name = f"Group {len(frame_obj.layers)}"
    self.timeline.add_group_to_all(name, depth=0)
```

- [ ] **Step 4: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/layer_animation.py tests/test_layer_groups.py
git commit -m "fix: _add_group always creates groups at depth=0"
```

---

### Task 3: Context Menu — Move to Group / Remove from Group

**Files:**
- Modify: `src/ui/timeline.py:548-568` (`_show_layer_context_menu`)

- [ ] **Step 1: Add "Move to Group" submenu and "Remove from Group" item**

In `src/ui/timeline.py`, replace `_show_layer_context_menu` (lines 548-568):

```python
def _show_layer_context_menu(self, event, layer_idx):
    """Right-click context menu on a layer sidebar label."""
    menu = tk.Menu(self, tearoff=0, bg=BG_PANEL, fg=TEXT_PRIMARY,
                   activebackground=ACCENT_CYAN, activeforeground=BG_DEEP,
                   font=("Consolas", 9))
    menu.add_command(label="Rename Layer",
                     command=lambda: self._rename_layer(layer_idx))
    menu.add_command(label="Duplicate Layer",
                     command=lambda: self._on_duplicate_layer(layer_idx))
    menu.add_separator()
    num_layers = len(self._timeline.current_frame_obj().layers) if self._timeline else 0
    menu.add_command(label="Move Up",
                     command=lambda: self._on_move_layer(layer_idx, layer_idx + 1),
                     state="normal" if layer_idx < num_layers - 1 else "disabled")
    menu.add_command(label="Move Down",
                     command=lambda: self._on_move_layer(layer_idx, layer_idx - 1),
                     state="normal" if layer_idx > 0 else "disabled")

    # Group operations
    if self._timeline:
        frame = self._timeline.current_frame_obj()
        layer = frame.layers[layer_idx]

        if not layer.is_group:
            # "Move to Group" submenu
            groups = [(i, l) for i, l in enumerate(frame.layers)
                      if l.is_group]
            if groups:
                menu.add_separator()
                group_menu = tk.Menu(menu, tearoff=0, bg=BG_PANEL,
                                     fg=TEXT_PRIMARY,
                                     activebackground=ACCENT_CYAN,
                                     activeforeground=BG_DEEP,
                                     font=("Consolas", 9))
                for gi, gl in groups:
                    group_menu.add_command(
                        label=gl.name,
                        command=lambda li=layer_idx, gidx=gi: self._move_to_group(li, gidx))
                menu.add_cascade(label="Move to Group", menu=group_menu)

            # "Remove from Group" if inside a group
            if layer.depth > 0:
                menu.add_command(label="Remove from Group",
                                 command=lambda: self._remove_from_group(layer_idx))

    menu.add_separator()
    menu.add_command(label="Delete Layer",
                     command=lambda: self._on_delete_layer(layer_idx))
    menu.tk_popup(event.x_root, event.y_root)
```

- [ ] **Step 2: Add `_move_to_group` and `_remove_from_group` methods**

Add these methods right after `_on_move_layer` (after line 638):

```python
def _move_to_group(self, layer_idx, group_idx):
    """Move a layer into a group via context menu."""
    if self._timeline:
        self._timeline.move_layer_into_group(layer_idx, group_idx)
        if self._callbacks.get("layer_select"):
            # Find where the layer ended up
            frame = self._timeline.current_frame_obj()
            self._callbacks["layer_select"](frame.active_layer_index)
        self.refresh()

def _remove_from_group(self, layer_idx):
    """Remove a layer from its group via context menu."""
    if self._timeline:
        self._timeline.move_layer_out_of_group(layer_idx)
        if self._callbacks.get("layer_select"):
            frame = self._timeline.current_frame_obj()
            self._callbacks["layer_select"](frame.active_layer_index)
        self.refresh()
```

- [ ] **Step 3: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add src/ui/timeline.py
git commit -m "feat: add 'Move to Group' and 'Remove from Group' context menu items"
```

---

### Task 4: Drag-Into-Group Detection

**Files:**
- Modify: `src/ui/timeline.py:671-681` (`_on_layer_drop`)

- [ ] **Step 1: Update `_on_layer_drop` for group-aware drops**

Replace `_on_layer_drop` (lines 671-681):

```python
def _on_layer_drop(self, event, source_idx):
    """Handle dropping a layer after drag."""
    self._clear_drag_indicator()
    if self._drag_source_idx is None:
        return

    target_idx = self._layer_idx_at_y(event)
    if target_idx is not None and target_idx != source_idx and self._timeline:
        frame = self._timeline.current_frame_obj()
        source_layer = frame.layers[source_idx]
        target_layer = frame.layers[target_idx]

        if not source_layer.is_group and target_layer.is_group:
            # Dropping onto a group row — move into group
            self._move_to_group(source_idx, target_idx)
        elif source_layer.depth > 0 and target_layer.depth == 0 and not target_layer.is_group:
            # Dropping a grouped layer onto a root-level layer — remove from group
            self._remove_from_group(source_idx)
        else:
            # Normal reorder
            self._on_move_layer(source_idx, target_idx)

    self._drag_source_idx = None
```

- [ ] **Step 2: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 3: Commit**

```bash
git add src/ui/timeline.py
git commit -m "feat: drag layer onto group row to add it to group"
```

---

### Task 5: Visual Styling for Group Rows and Children

**Files:**
- Modify: `src/ui/timeline.py:323-436` (layer sidebar rendering in `refresh`)

- [ ] **Step 1: Update group row styling**

In the layer sidebar rendering section of `refresh()` (around line 382-386), update the name label creation. Replace the existing name label block:

```python
# Layer name
name_fg = ACCENT_CYAN if is_active else TEXT_PRIMARY
name_bg = BG_PANEL_ALT if is_active else BG_PANEL
name_lbl = tk.Label(row, text=layer.name, font=("Consolas", 8),
                    bg=name_bg, fg=name_fg, anchor="w")
```

With:

```python
# Layer name — groups get bold magenta styling
if is_group:
    name_font = ("Consolas", 8, "bold")
    name_fg = ACCENT_CYAN if is_active else ACCENT_MAGENTA
    name_bg = BG_PANEL_ALT if is_active else BG_PANEL
    name_text = f"\U0001F4C1 {layer.name}"  # folder icon
elif layer_depth > 0:
    name_font = ("Consolas", 8)
    name_fg = ACCENT_CYAN if is_active else TEXT_SECONDARY
    name_bg = BG_PANEL_ALT if is_active else BG_PANEL
    name_text = layer.name
else:
    name_font = ("Consolas", 8)
    name_fg = ACCENT_CYAN if is_active else TEXT_PRIMARY
    name_bg = BG_PANEL_ALT if is_active else BG_PANEL
    name_text = layer.name
name_lbl = tk.Label(row, text=name_text, font=name_font,
                    bg=name_bg, fg=name_fg, anchor="w")
```

- [ ] **Step 2: Add left border accent on child rows**

Right after creating the `row` frame (line 343-345), add a visual left-border for children:

After:
```python
row = tk.Frame(self._layer_inner, height=self._cel_size, bg=BG_PANEL)
row.pack(fill="x", pady=1)
row.pack_propagate(False)
```

Add:
```python
# Left accent bar for child layers
if layer_depth > 0:
    accent_bar = tk.Frame(row, width=3, bg=ACCENT_MAGENTA)
    accent_bar.pack(side="left", fill="y")
```

- [ ] **Step 3: Update truncation to handle folder icon prefix**

In the `_truncate_name` binding (line 390-391), update to use the display text:

Replace:
```python
name_lbl.bind("<Configure>",
              lambda e, l=name_lbl, t=layer.name: self._truncate_name(e, l, t))
```

With:
```python
name_lbl.bind("<Configure>",
              lambda e, l=name_lbl, t=name_text: self._truncate_name(e, l, t))
```

- [ ] **Step 4: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 5: Manual test**

Run: `python main.py`
- Create a group ("+ Layer" then right-click > context or use existing Add Group button)
- Add layers and right-click > Move to Group > [group name]
- Verify: child layers show indented with magenta left bar
- Verify: group row shows folder icon and bold magenta text
- Verify: collapse arrow hides/shows children
- Verify: drag a layer onto the group row to add it
- Verify: right-click child > "Remove from Group" works

- [ ] **Step 6: Commit**

```bash
git add src/ui/timeline.py
git commit -m "feat: visual styling for group rows (folder icon, bold) and child layers (indent, accent bar)"
```
