# Startup Dialog Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the intro video from the startup dialog, add a recent projects section, and replace the bare OS custom-size dialogs with a themed custom canvas size window.

**Architecture:** New `src/recents.py` module handles reading/writing `~/.retrosprite/recents.json`. The startup dialog (`src/ui/dialogs.py`) gets video code removed, a new recents section at the bottom, and a new themed `ask_custom_canvas_size()` function. `src/file_ops.py` calls `update_recents()` on save/open.

**Tech Stack:** Python 3.8+, Tkinter, JSON, os/pathlib

---

### Task 1: Create `src/recents.py` — storage module

**Files:**
- Create: `src/recents.py`
- Create: `tests/test_recents.py`

- [ ] **Step 1: Write failing tests for recents module**

Create `tests/test_recents.py`:

```python
"""Tests for recent projects storage."""
import json
import os
import tempfile
import time

import pytest

from src.recents import load_recents, update_recents, RECENTS_FILENAME


@pytest.fixture
def recents_dir(tmp_path, monkeypatch):
    """Redirect recents storage to a temp directory."""
    monkeypatch.setattr("src.recents._get_config_dir", lambda: str(tmp_path))
    return tmp_path


def test_load_recents_empty(recents_dir):
    """Returns empty list when no recents file exists."""
    assert load_recents() == []


def test_update_and_load(recents_dir):
    """Adding a path makes it appear in load_recents."""
    # Create a real file so it passes the exists check
    f = recents_dir / "test.retro"
    f.write_text("")
    update_recents(str(f))
    result = load_recents()
    assert len(result) == 1
    assert result[0]["path"] == str(f)


def test_update_bumps_existing(recents_dir):
    """Re-adding a path moves it to the top."""
    f1 = recents_dir / "a.retro"
    f2 = recents_dir / "b.retro"
    f1.write_text("")
    f2.write_text("")
    update_recents(str(f1))
    update_recents(str(f2))
    update_recents(str(f1))
    result = load_recents()
    assert result[0]["path"] == str(f1)
    assert result[1]["path"] == str(f2)


def test_cap_at_five(recents_dir):
    """List never exceeds 5 entries."""
    files = []
    for i in range(7):
        f = recents_dir / f"{i}.retro"
        f.write_text("")
        files.append(f)
        update_recents(str(f))
    result = load_recents()
    assert len(result) == 5
    # Most recent is first
    assert result[0]["path"] == str(files[6])


def test_filters_dead_paths(recents_dir):
    """Entries whose files no longer exist are filtered out."""
    f = recents_dir / "gone.retro"
    f.write_text("")
    update_recents(str(f))
    f.unlink()
    result = load_recents()
    assert len(result) == 0


def test_corrupted_file_returns_empty(recents_dir):
    """Gracefully handles corrupted JSON."""
    path = recents_dir / RECENTS_FILENAME
    path.write_text("not json {{{")
    assert load_recents() == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_recents.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.recents'`

- [ ] **Step 3: Implement `src/recents.py`**

Create `src/recents.py`:

```python
"""Recent projects storage for RetroSprite.

Stores up to 5 recently opened/saved .retro project paths
in ~/.retrosprite/recents.json.
"""
from __future__ import annotations

import json
import os
import time

RECENTS_FILENAME = "recents.json"
_MAX_RECENTS = 5


def _get_config_dir() -> str:
    return os.path.expanduser("~/.retrosprite")


def load_recents() -> list[dict]:
    """Load recent projects list, filtering out paths that no longer exist.

    Returns list of dicts with keys: path (str), timestamp (float).
    Sorted newest-first, capped at 5.
    """
    config_dir = _get_config_dir()
    filepath = os.path.join(config_dir, RECENTS_FILENAME)
    if not os.path.exists(filepath):
        return []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            entries = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []
    # Filter dead paths and ensure structure
    valid = []
    for entry in entries:
        if isinstance(entry, dict) and "path" in entry and os.path.exists(entry["path"]):
            valid.append(entry)
    valid.sort(key=lambda e: e.get("timestamp", 0), reverse=True)
    return valid[:_MAX_RECENTS]


def update_recents(path: str) -> None:
    """Add or bump a project path to the top of the recents list."""
    config_dir = _get_config_dir()
    os.makedirs(config_dir, exist_ok=True)
    filepath = os.path.join(config_dir, RECENTS_FILENAME)

    # Load existing
    entries: list[dict] = []
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                entries = json.load(f)
        except (json.JSONDecodeError, OSError):
            entries = []

    # Normalize the path for comparison
    norm = os.path.normpath(path)

    # Remove existing entry for this path
    entries = [e for e in entries if os.path.normpath(e.get("path", "")) != norm]

    # Insert at top
    entries.insert(0, {"path": norm, "timestamp": time.time()})

    # Cap
    entries = entries[:_MAX_RECENTS]

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_recents.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/recents.py tests/test_recents.py
git commit -m "feat: add recents module for recent project storage"
```

---

### Task 2: Remove intro video from startup dialog

**Files:**
- Modify: `src/ui/dialogs.py:1-20` (imports), `src/ui/dialogs.py:102-266` (ask_startup)

- [ ] **Step 1: Remove video-related imports and constants**

In `src/ui/dialogs.py`, remove:
- Line 4: `import webbrowser`
- Lines 7-8: `INTRO_VIDEO_URL` constant
- Lines 10-15: `tkinterweb` try/except import block

The imports section should become:

```python
"""Dialog windows for RetroSprite — cyberpunk neon themed."""
from __future__ import annotations
import tkinter as tk
from tkinter import filedialog, messagebox

from src.ui.theme import (
    BG_DEEP, BG_PANEL, BG_PANEL_ALT, BORDER, TEXT_PRIMARY, TEXT_SECONDARY,
    ACCENT_CYAN, ACCENT_MAGENTA, ACCENT_PURPLE, BUTTON_BG, BUTTON_HOVER,
    blend_color,
)
```

Note: `simpledialog` import is also removed — it will no longer be needed after Task 3 replaces the custom size dialogs.

- [ ] **Step 2: Remove video section from `ask_startup`**

In the `ask_startup` function, remove lines 134-171 (everything from `# Embedded video or fallback button` through the end of the else block including `video_btn.bind` lines).

Keep the Feature Guide button (lines 173-183) — it moves up to fill the space left by the video.

- [ ] **Step 3: Reduce dialog height**

Change line 106 from:
```python
dialog.geometry("420x620")
```
to:
```python
dialog.geometry("420x520")
```

- [ ] **Step 4: Run existing tests**

Run: `python -m pytest tests/ -x -q`
Expected: All tests pass (no tests directly test the video feature)

- [ ] **Step 5: Commit**

```bash
git add src/ui/dialogs.py
git commit -m "feat: remove intro video from startup dialog"
```

---

### Task 3: Replace custom size dialogs with themed window

**Files:**
- Modify: `src/ui/dialogs.py` — add `ask_custom_canvas_size()`, update `_custom_new` in `ask_startup`, update `_custom` in `ask_canvas_size`

- [ ] **Step 1: Add `ask_custom_canvas_size` function**

Add this function after `_neon_hover` and before `ask_canvas_size` in `src/ui/dialogs.py`:

```python
def ask_custom_canvas_size(parent) -> tuple[int, int] | None:
    """Show themed custom canvas size dialog with aspect ratio presets.

    Returns (width, height) tuple or None if cancelled.
    The dialog is modal relative to parent but does not destroy parent.
    """
    dialog = tk.Toplevel(parent)
    dialog.title("Custom Canvas Size")
    dialog.geometry("300x320")
    dialog.resizable(False, False)
    dialog.configure(bg=BG_DEEP)
    dialog.transient(parent)
    dialog.grab_set()

    result = [None]

    # Top gradient bar
    top_bar = tk.Canvas(dialog, height=2, bg=BG_DEEP, highlightthickness=0)
    top_bar.pack(fill="x")
    _draw_gradient_bar(top_bar, ACCENT_CYAN, ACCENT_PURPLE)

    tk.Label(dialog, text="Custom Canvas Size", fg=ACCENT_CYAN, bg=BG_DEEP,
             font=("Consolas", 11, "bold")).pack(pady=(12, 8))

    # Width field
    w_frame = tk.Frame(dialog, bg=BG_DEEP)
    w_frame.pack(fill="x", padx=40, pady=4)
    tk.Label(w_frame, text="Width:", font=("Consolas", 9),
             bg=BG_DEEP, fg=TEXT_PRIMARY).pack(side="left")
    w_var = tk.StringVar(value="64")
    w_entry = tk.Entry(w_frame, textvariable=w_var, width=8, bg=BG_PANEL_ALT,
                       fg=TEXT_PRIMARY, insertbackground=ACCENT_CYAN,
                       font=("Consolas", 9), highlightthickness=1,
                       highlightbackground=BORDER, highlightcolor=ACCENT_CYAN)
    w_entry.pack(side="right")

    # Height field
    h_frame = tk.Frame(dialog, bg=BG_DEEP)
    h_frame.pack(fill="x", padx=40, pady=4)
    tk.Label(h_frame, text="Height:", font=("Consolas", 9),
             bg=BG_DEEP, fg=TEXT_PRIMARY).pack(side="left")
    h_var = tk.StringVar(value="64")
    h_entry = tk.Entry(h_frame, textvariable=h_var, width=8, bg=BG_PANEL_ALT,
                       fg=TEXT_PRIMARY, insertbackground=ACCENT_CYAN,
                       font=("Consolas", 9), highlightthickness=1,
                       highlightbackground=BORDER, highlightcolor=ACCENT_CYAN)
    h_entry.pack(side="right")

    # Error label (hidden by default)
    error_var = tk.StringVar(value="")
    error_label = tk.Label(dialog, textvariable=error_var, fg=ACCENT_MAGENTA,
                           bg=BG_DEEP, font=("Consolas", 8))
    error_label.pack(pady=(2, 0))

    # Aspect ratio presets
    tk.Label(dialog, text="Aspect Ratio Presets", fg=TEXT_SECONDARY, bg=BG_DEEP,
             font=("Consolas", 8)).pack(pady=(8, 2))

    preset_frame = tk.Frame(dialog, bg=BG_DEEP)
    preset_frame.pack()

    def _apply_ratio(rw, rh):
        """Set height based on current width and the chosen ratio."""
        try:
            w = int(w_var.get())
        except ValueError:
            w = 64
        h = max(1, round(w * rh / rw))
        h_var.set(str(h))
        error_var.set("")

    ratios = [("1:1", 1, 1), ("4:3", 4, 3), ("3:4", 3, 4),
              ("16:9", 16, 9), ("9:16", 9, 16)]
    for label, rw, rh in ratios:
        btn = tk.Button(
            preset_frame, text=label, width=4, bg=BG_PANEL_ALT, fg=TEXT_PRIMARY,
            activebackground=ACCENT_PURPLE, activeforeground=BG_DEEP,
            relief="flat", font=("Consolas", 8),
            command=lambda rw_=rw, rh_=rh: _apply_ratio(rw_, rh_)
        )
        btn.pack(side="left", padx=2, pady=2)
        _neon_hover(btn, ACCENT_PURPLE, BG_PANEL_ALT)

    # Buttons
    btn_row = tk.Frame(dialog, bg=BG_DEEP)
    btn_row.pack(pady=(16, 8))

    def _create():
        try:
            w = int(w_var.get())
            h = int(h_var.get())
        except ValueError:
            error_var.set("Width and height must be integers")
            return
        if w < 1 or h < 1:
            error_var.set("Values must be at least 1")
            return
        if w > 2048 or h > 2048:
            error_var.set("Maximum size is 2048x2048")
            return
        result[0] = (w, h)
        dialog.destroy()

    create_btn = tk.Button(
        btn_row, text="Create", width=10, bg=ACCENT_CYAN, fg=BG_DEEP,
        activebackground=ACCENT_MAGENTA, activeforeground=BG_DEEP,
        relief="flat", font=("Consolas", 9, "bold"), command=_create
    )
    create_btn.pack(side="left", padx=4)
    _neon_hover(create_btn, ACCENT_MAGENTA, ACCENT_CYAN)

    cancel_btn = tk.Button(
        btn_row, text="Cancel", width=10, bg=BUTTON_BG, fg=TEXT_PRIMARY,
        activebackground=BUTTON_HOVER, activeforeground=TEXT_PRIMARY,
        relief="flat", font=("Consolas", 9), command=dialog.destroy
    )
    cancel_btn.pack(side="left", padx=4)
    _neon_hover(cancel_btn)

    # Bottom gradient bar
    bot_bar = tk.Canvas(dialog, height=2, bg=BG_DEEP, highlightthickness=0)
    bot_bar.pack(side="bottom", fill="x")
    _draw_gradient_bar(bot_bar, ACCENT_PURPLE, ACCENT_CYAN)

    # Select width field on open
    w_entry.focus_set()
    w_entry.select_range(0, "end")

    dialog.wait_window()
    return result[0]
```

- [ ] **Step 2: Update `ask_canvas_size` to use new custom dialog**

Replace the `_custom` inner function (lines 78-88) in `ask_canvas_size` with:

```python
    def _custom():
        size = ask_custom_canvas_size(dialog)
        if size is not None:
            result[0] = size
        dialog.destroy()
```

- [ ] **Step 3: Update `ask_startup._custom_new` to use new custom dialog**

Replace the `_custom_new` inner function (lines 209-219 in the current file — these line numbers will shift after Task 2 edits) with:

```python
    def _custom_new():
        size = ask_custom_canvas_size(dialog)
        if size is not None:
            result[0] = {"action": "new", "size": size}
            dialog.destroy()
```

This is the key behavioral change: clicking "Custom Size..." opens the themed dialog **without** destroying the startup dialog first. The startup dialog only closes when a valid size is confirmed. If the user cancels, they return to the startup dialog.

- [ ] **Step 4: Verify the app launches correctly**

Run: `python main.py`
Manual check: Click "Custom Size...", verify themed dialog appears over startup dialog. Cancel returns to startup. Creating a size closes both.

- [ ] **Step 5: Commit**

```bash
git add src/ui/dialogs.py
git commit -m "feat: themed custom canvas size dialog with aspect ratio presets"
```

---

### Task 4: Add recent projects section to startup dialog

**Files:**
- Modify: `src/ui/dialogs.py` — add recents section to `ask_startup`

- [ ] **Step 1: Add recents import to dialogs.py**

Add to the imports at the top of `src/ui/dialogs.py`:

```python
from src.recents import load_recents
```

- [ ] **Step 2: Add recents section to `ask_startup`**

In the `ask_startup` function, insert the following **after** the Open Project button and its hover bindings, and **before** the bottom gradient bar. This means after the current `open_btn.bind("<Leave>", ...)` line and before the `# Bottom gradient border` comment:

```python
    # Separator
    sep3 = tk.Canvas(dialog, height=1, bg=BG_DEEP, highlightthickness=0)
    sep3.pack(fill="x", padx=30, pady=8)
    _draw_gradient_bar(sep3, ACCENT_PURPLE, ACCENT_CYAN, height=1)

    # Recent projects section
    tk.Label(dialog, text="Recent Projects", fg=ACCENT_PURPLE, bg=BG_DEEP,
             font=("Consolas", 10, "bold")).pack(pady=(4, 4))

    recents = load_recents()
    if recents:
        for entry in recents:
            path = entry["path"]
            filename = os.path.basename(path)
            dirpath = os.path.dirname(path)

            item_frame = tk.Frame(dialog, bg=BG_DEEP, cursor="hand2")
            item_frame.pack(fill="x", padx=30, pady=1)

            name_label = tk.Label(
                item_frame, text=filename, fg=TEXT_PRIMARY, bg=BG_DEEP,
                font=("Consolas", 9), anchor="w"
            )
            name_label.pack(fill="x")

            dir_label = tk.Label(
                item_frame, text=dirpath, fg=TEXT_SECONDARY, bg=BG_DEEP,
                font=("Consolas", 7), anchor="w"
            )
            dir_label.pack(fill="x")

            def _open_recent(p=path):
                result[0] = {"action": "open", "path": p}
                dialog.destroy()

            for widget in (item_frame, name_label, dir_label):
                widget.bind("<Button-1>", lambda e, p=path: _open_recent(p))
                widget.bind("<Enter>", lambda e, f=item_frame, n=name_label, d=dir_label:
                            (f.config(bg=BG_PANEL_ALT),
                             n.config(bg=BG_PANEL_ALT, fg=ACCENT_CYAN),
                             d.config(bg=BG_PANEL_ALT)))
                widget.bind("<Leave>", lambda e, f=item_frame, n=name_label, d=dir_label:
                            (f.config(bg=BG_DEEP),
                             n.config(bg=BG_DEEP, fg=TEXT_PRIMARY),
                             d.config(bg=BG_DEEP)))
    else:
        tk.Label(dialog, text="No recent projects", fg=TEXT_SECONDARY,
                 bg=BG_DEEP, font=("Consolas", 8)).pack(pady=4)
```

- [ ] **Step 3: Add `os` import to dialogs.py**

Add `import os` to the imports at the top of the file (after `import tkinter as tk`).

- [ ] **Step 4: Increase dialog height for recents**

Change the dialog geometry to accommodate the new section:

```python
dialog.geometry("420x580")
```

- [ ] **Step 5: Verify visually**

Run: `python main.py`
Manual check: With no recents file, the startup dialog shows "No recent projects". After opening/saving a project and relaunching, the project appears in the recents section.

- [ ] **Step 6: Commit**

```bash
git add src/ui/dialogs.py
git commit -m "feat: add recent projects section to startup dialog"
```

---

### Task 5: Wire `update_recents` into file_ops.py

**Files:**
- Modify: `src/file_ops.py:1-18` (imports), `src/file_ops.py:62` (save_as), `src/file_ops.py:126` (open)

- [ ] **Step 1: Add recents import to file_ops.py**

Add to the imports at the top of `src/file_ops.py`:

```python
from src.recents import update_recents
```

- [ ] **Step 2: Call `update_recents` in `_save_project_as`**

In `_save_project_as`, after line 62 (`self._project_path = path`), add:

```python
                update_recents(path)
```

This goes inside the `try` block, after the path is confirmed saved.

- [ ] **Step 3: Call `update_recents` in `_open_project`**

In `_open_project`, after line 126 (`self._project_path = path`), add:

```python
        update_recents(path)
```

- [ ] **Step 4: Call `update_recents` on startup open**

In `src/app.py`, the startup path already sets `self._project_path = startup["path"]` at line 90. Add the recents update there. In `src/app.py` after line 90:

```python
            from src.recents import update_recents
            update_recents(startup["path"])
```

- [ ] **Step 5: Run all tests**

Run: `python -m pytest tests/ -x -q`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add src/file_ops.py src/app.py
git commit -m "feat: track recently opened/saved projects"
```

---

### Task 6: Final cleanup and full test run

**Files:**
- Verify: `src/ui/dialogs.py`, `src/recents.py`, `src/file_ops.py`, `src/app.py`

- [ ] **Step 1: Verify no stale imports remain**

Check that `src/ui/dialogs.py` no longer imports `webbrowser`, `simpledialog`, or `tkinterweb`. Check that it does import `os` and `load_recents`.

- [ ] **Step 2: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All tests pass including the new `test_recents.py` tests

- [ ] **Step 3: Manual smoke test**

Run: `python main.py`
Verify:
1. No video button in startup dialog
2. Feature Guide button is present
3. Preset size buttons work (16x16, 32x32, 64x64, 128x128)
4. "Custom Size..." opens themed dialog over startup
5. Aspect ratio presets adjust height correctly
6. Cancel returns to startup dialog
7. Create closes both dialogs and opens canvas
8. "Open .retro Project..." works
9. "Recent Projects" section shows at the bottom
10. After saving a project and relaunching, it appears in recents
11. Clicking a recent project opens it immediately

- [ ] **Step 4: Commit any final fixes**

```bash
git add -A
git commit -m "chore: final cleanup for startup dialog redesign"
```
