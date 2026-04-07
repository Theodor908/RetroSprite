# Timeline Layout Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the fixed-width timeline sidebar with a resizable PanedWindow, add synchronized vertical scrolling, and truncate layer names so buttons never clip.

**Architecture:** Single-file change to `src/ui/timeline.py`. The `_build_ui` method is restructured to use `tk.PanedWindow` with two panes (layer sidebar and frame grid). Both panes share a synchronized vertical scroll. Layer name labels use a `<Configure>` callback for ellipsis truncation.

**Tech Stack:** Python, Tkinter (PanedWindow, Canvas, Scrollbar), tkinter.font

**Spec:** `docs/superpowers/specs/2026-03-27-timeline-layout-overhaul-design.md`

---

### Task 1: Replace Fixed Sidebar with PanedWindow

**Files:**
- Modify: `src/ui/timeline.py:81-127` (`_build_ui` method)

- [ ] **Step 1: Add tkinter.font import**

At the top of `src/ui/timeline.py`, after the existing imports (line 4), add:

```python
import tkinter.font as tkfont
```

- [ ] **Step 2: Replace `_build_ui` layout section**

In `_build_ui`, replace lines 94-127 (everything from `# --- Main content area ---` to end of method) with:

```python
        # --- Main content area ---
        content = tk.Frame(self, bg=BG_DEEP)
        content.pack(fill="both", expand=True, side="top")

        # --- PanedWindow: layer sidebar (left) | frame grid (right) ---
        self._paned = tk.PanedWindow(content, orient=tk.HORIZONTAL,
                                      bg=BORDER, sashwidth=4,
                                      sashrelief="flat", bd=0,
                                      opaqueresize=True)
        self._paned.pack(fill="both", expand=True)

        # --- Left pane: layer sidebar with vertical scroll ---
        left_pane = tk.Frame(self._paned, bg=BG_PANEL)

        self._layer_canvas = tk.Canvas(left_pane, bg=BG_PANEL,
                                        highlightthickness=0)
        self._layer_canvas.pack(fill="both", expand=True)

        self._layer_inner = tk.Frame(self._layer_canvas, bg=BG_PANEL)
        self._layer_canvas_window = self._layer_canvas.create_window(
            (0, 0), window=self._layer_inner, anchor="nw")

        # Resize inner frame width to match canvas width
        def _on_layer_canvas_configure(event):
            self._layer_canvas.itemconfig(self._layer_canvas_window,
                                           width=event.width)
        self._layer_canvas.bind("<Configure>", _on_layer_canvas_configure)
        self._layer_inner.bind("<Configure>",
                               lambda e: self._layer_canvas.configure(
                                   scrollregion=self._layer_canvas.bbox("all")))

        # --- Right pane: frame grid with both scrollbars ---
        right_pane = tk.Frame(self._paned, bg=BG_DEEP)

        from tkinter import ttk

        # Vertical scrollbar (syncs both panes)
        self._v_scrollbar = ttk.Scrollbar(right_pane, orient="vertical",
                                           style="Neon.Vertical.TScrollbar",
                                           command=self._on_v_scroll)
        self._v_scrollbar.pack(side="right", fill="y")

        # Horizontal scrollbar (grid only)
        self._h_scrollbar = ttk.Scrollbar(right_pane, orient="horizontal",
                                           style="Neon.Horizontal.TScrollbar")
        self._h_scrollbar.pack(side="bottom", fill="x")

        self._grid_canvas = tk.Canvas(right_pane, bg=BG_DEEP,
                                      highlightthickness=0,
                                      xscrollcommand=self._h_scrollbar.set,
                                      yscrollcommand=self._on_grid_yscroll)
        self._grid_canvas.pack(fill="both", expand=True)
        self._h_scrollbar.config(command=self._grid_canvas.xview)

        self._grid_inner = tk.Frame(self._grid_canvas, bg=BG_DEEP)
        self._grid_canvas.create_window((0, 0), window=self._grid_inner,
                                         anchor="nw")
        self._grid_inner.bind("<Configure>",
                              lambda e: self._grid_canvas.configure(
                                  scrollregion=self._grid_canvas.bbox("all")))

        # Mousewheel scrolling on both panes
        for widget in (self._layer_canvas, self._grid_canvas):
            widget.bind("<MouseWheel>", self._on_timeline_mousewheel)

        # Add panes with min size
        self._paned.add(left_pane, minsize=120, width=200)
        self._paned.add(right_pane, minsize=100)
```

- [ ] **Step 3: Add vertical scroll sync methods**

Add these methods to the `TimelinePanel` class (after `_build_ui`, before `_build_transport`):

```python
    def _on_v_scroll(self, *args):
        """Vertical scrollbar command — sync both canvases."""
        self._grid_canvas.yview(*args)
        self._layer_canvas.yview(*args)

    def _on_grid_yscroll(self, first, last):
        """Called when grid canvas scrolls — sync scrollbar + layer canvas."""
        self._v_scrollbar.set(first, last)
        self._layer_canvas.yview_moveto(first)

    def _on_timeline_mousewheel(self, event):
        """Mousewheel scrolls both panes vertically."""
        self._grid_canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
        self._layer_canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
```

- [ ] **Step 4: Update `refresh()` to use `_layer_inner` instead of `_layer_sidebar`**

In the `refresh()` method (around line 185), replace the clear logic:

```python
        # Clear existing
        for w in self._layer_sidebar.winfo_children():
            w.destroy()
```

With:

```python
        # Clear existing
        for w in self._layer_inner.winfo_children():
            w.destroy()
```

- [ ] **Step 5: Update all `self._layer_sidebar` references in `refresh()` to `self._layer_inner`**

In the `refresh()` method, find every occurrence of `self._layer_sidebar` and replace with `self._layer_inner`. These are:

- Line ~256: `spacer = tk.Frame(self._layer_sidebar, ...)` → `spacer = tk.Frame(self._layer_inner, ...)`
- Line ~279: `row = tk.Frame(self._layer_sidebar, ...)` → `row = tk.Frame(self._layer_inner, ...)`

Search for all `self._layer_sidebar` in the file and replace any that create child widgets with `self._layer_inner`. Keep `self._layer_sidebar` only if it refers to the old variable name — but since we removed it, all references must point to `self._layer_inner`.

- [ ] **Step 6: Remove old `_layer_header_width` usage**

The `self._layer_header_width = 180` (line 63) is no longer needed for the sidebar frame width. However, it may still be used elsewhere. Search for `_layer_header_width` in the file. If it's only used at line 63 and line 103 (old sidebar width), remove line 63. If used elsewhere (e.g., for row height calculations), keep it.

- [ ] **Step 7: Bind mousewheel on layer row children**

In `refresh()`, after creating each layer row's child widgets (buttons, labels), bind mousewheel to them so scrolling works when hovering over buttons/labels inside the layer sidebar:

After line ~358 (end of the layer row creation loop, after blend_btn tooltip bindings), add:

```python
            # Bind mousewheel on all children for scroll support
            for child in row.winfo_children():
                child.bind("<MouseWheel>", self._on_timeline_mousewheel)
            row.bind("<MouseWheel>", self._on_timeline_mousewheel)
```

Similarly, in the cel grid section, bind mousewheel on cel frames:

After creating each cel frame in the grid loop, add:

```python
                cel_frame.bind("<MouseWheel>", self._on_timeline_mousewheel)
                for child in cel_frame.winfo_children():
                    child.bind("<MouseWheel>", self._on_timeline_mousewheel)
```

- [ ] **Step 8: Run the app and test PanedWindow + scroll**

Run: `python main.py`
Test steps:
1. The timeline should show a draggable sash between layer names and frame grid
2. Drag the sash left/right — layer sidebar should resize
3. Add 5+ layers — vertical scrollbar should appear on the right
4. Scroll with mousewheel — both layer sidebar and frame grid scroll together
5. Horizontal scroll on frame grid still works

---

### Task 2: Layer Name Truncation

**Files:**
- Modify: `src/ui/timeline.py` (layer name label creation in `refresh()`)

- [ ] **Step 1: Add the `_truncate_name` static method**

Add to `TimelinePanel` class (near the scroll methods):

```python
    @staticmethod
    def _truncate_name(event, lbl, full_text):
        """Truncate label text with '...' to fit available width."""
        font = tkfont.Font(font=lbl.cget("font"))
        avail = event.width
        if avail <= 1:
            return
        if font.measure(full_text) <= avail:
            lbl.config(text=full_text)
        else:
            for i in range(len(full_text), 0, -1):
                if font.measure(full_text[:i] + "...") <= avail:
                    lbl.config(text=full_text[:i] + "...")
                    return
            lbl.config(text="...")
```

- [ ] **Step 2: Bind truncation on layer name labels**

In `refresh()`, find where the layer name label is created (the `name_lbl = tk.Label(row, text=layer.name, ...)` block). After the existing bindings (Button-1, Double-Button-1, Button-3), add:

```python
            name_lbl.bind("<Configure>",
                          lambda e, l=name_lbl, t=layer.name: self._truncate_name(e, l, t))
```

- [ ] **Step 3: Run the app and test truncation**

Run: `python main.py`
Test steps:
1. Create a layer with a long name (e.g., "This is a very long layer name that should truncate")
2. The name should show with "..." truncation in the sidebar
3. Drag the sash wider — more of the name should appear
4. Drag the sash narrower — the name truncates further
5. Buttons (eye, lock, FX, blend) should never be clipped

---

### Task 3: Run Tests and Final Verification

**Files:**
- Read: `tests/test_timeline.py`

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/ -q --ignore=tests/test_options_bar.py --ignore=tests/test_right_panel.py --ignore=tests/test_tiled_mode.py`
Expected: All tests pass (pre-existing Tkinter headless errors are expected)

- [ ] **Step 2: Manual smoke test**

Run: `python main.py`
Verify:
1. PanedWindow sash is visible and draggable between layer list and frame grid
2. Sash starts at ~200px from left
3. Layer names truncate with "..." when sidebar is narrow
4. Dragging sash wider reveals full layer names
5. Buttons (eye, lock, FX, blend dropdown) are always fully visible
6. Adding 5+ layers shows vertical scrollbar on right side
7. Mousewheel scrolls both layer sidebar and frame grid in sync
8. Horizontal scroll on frame grid still works independently
9. All existing timeline functionality works: frame selection, layer selection, visibility toggle, lock toggle, FX button, blend mode dropdown, transport controls, drag-to-resize panel height
