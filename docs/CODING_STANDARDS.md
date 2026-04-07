# RetroSprite — Coding Standards

## Python Style

### General
- **PEP 8** compliance with 100-character line limit
- **Type hints** on all function signatures (parameters and return types)
- **Docstrings** on public classes and methods with non-obvious behavior
- Use `from __future__ import annotations` at the top of every module

### Naming
```python
# Functions and variables
def apply_blend_mode(base, blend, mode): ...
pixel_size = 16

# Classes
class PixelGrid: ...
class LayerEffect: ...

# Constants
DITHER_PATTERNS = { ... }
BG_DEEP = "#0a0a14"

# Tool dictionary keys — always Capitalized
self._tools["Pen"] = PenTool()
self._tools["Wand"] = MagicWandTool()
```

### Imports
Order: stdlib → third-party → local. One blank line between groups.
```python
from __future__ import annotations
import os
import math

import numpy as np
from PIL import Image

from src.pixel_data import PixelGrid
from src.layer import Layer
```

Never use wildcard imports (`from module import *`).

## NumPy Conventions

### Array Shapes
```python
# RGBA pixels — always (H, W, 4) uint8
pixels = np.zeros((height, width, 4), dtype=np.uint8)

# Indexed pixels — always (H, W) uint16
indices = np.zeros((height, width), dtype=np.uint16)

# Alpha channel extraction
alpha = pixels[:, :, 3].astype(np.float32) / 255.0
```

### Performance Rules
- **Use NumPy vectorization** for anything touching pixels. Never iterate pixels in Python:
  ```python
  # BAD — Python loop over pixels
  for y in range(h):
      for x in range(w):
          pixels[y, x, 3] = int(pixels[y, x, 3] * opacity)

  # GOOD — NumPy vectorized
  pixels[:, :, 3] = (pixels[:, :, 3] * opacity).astype(np.uint8)
  ```

- **Use `np.float32` for intermediate math**, cast back to `uint8`:
  ```python
  result = (base.astype(np.float32) * factor).clip(0, 255).astype(np.uint8)
  ```

- **Avoid PIL ↔ NumPy round-trips** in hot paths. If you already have a NumPy array, operate on it directly instead of converting to PIL Image and back.

- **Precompute patterns** (checkerboard, dither matrices) instead of calculating per-pixel.

## Tkinter Patterns

### Theme Colors
Always use theme constants from `src/ui/theme.py`:
```python
from src.ui.theme import (
    BG_DEEP, BG_PANEL, BG_PANEL_ALT, BORDER,
    TEXT_PRIMARY, TEXT_SECONDARY,
    ACCENT_CYAN, ACCENT_MAGENTA,
    BUTTON_BG, BUTTON_HOVER,
)

# Never hardcode colors
tk.Label(parent, text="Hello", fg=TEXT_PRIMARY, bg=BG_PANEL)  # GOOD
tk.Label(parent, text="Hello", fg="#ffffff", bg="#1a1a2e")     # BAD
```

### Font
Use `("Consolas", 8)` or `("Consolas", 9)` consistently. Use `("Consolas", 11, "bold")` for headings.

### Widget Styling
Use the helper functions:
```python
from src.ui.theme import style_menu, style_scrollbar, style_checkbutton
style_menu(my_menu)
```

### Dialogs
- Use `tk.Toplevel` with `transient(parent)` and `grab_set()` for modal dialogs
- Configure with theme colors
- Always provide a way to close (button or Escape key)

## Encapsulation

### PixelGrid Access
In new code, use the public API:
```python
# GOOD — public API
color = grid.get_pixel(x, y)
grid.set_pixel(x, y, (255, 0, 0, 255))
new_grid = grid.copy()
img = grid.to_pil_image()

# AVOID in new code — direct internal access
pixels = grid._pixels[y, x]  # Only acceptable in performance-critical paths
```

### Layer Properties
Access via attributes, not dict manipulation:
```python
layer.opacity = 0.5
layer.blend_mode = "multiply"
layer.visible = False
```

## Error Handling

### Boundaries (validate)
- File I/O: wrap in try/except, show user-friendly error messages
- User input: validate before processing (canvas size, palette index, etc.)
- Plugin calls: always wrap in try/except (error isolation)

### Internals (trust)
- Pixel coordinates: trust that bounds-checking happens at the entry point (`get_pixel`/`set_pixel` already bounds-check)
- Layer indices: trust internal code maintains valid indices
- Don't add defensive checks inside hot paths

## Tool Implementation

### Structure
Tools are **stateless classes** with an `apply()` method:
```python
class MyTool:
    def apply(self, grid: PixelGrid, x: int, y: int, color: tuple,
              size: int = 1, **kwargs) -> None:
        """Modify grid pixels at/around (x, y)."""
        ...
```

### Rules
- Tools operate on `PixelGrid`, never on `Layer`, `Frame`, or the app
- Tools never import from `app.py` or any mixin
- Tools should be testable in isolation with just a `PixelGrid`
- Tool dict keys in the app are Capitalized: `"Pen"`, `"Eraser"`, `"Spray"`

## Mixin Rules

### Do
- Keep methods focused on the mixin's responsibility
- Import only what the mixin's methods need
- Reference `self.*` freely — resolved at runtime via `RetroSpriteApp`

### Don't
- Never define `__init__` in a mixin
- Never define a method name that exists in another mixin
- Never import from `app.py` in a mixin (circular dependency)
- Never add new methods to `app.py` — use the appropriate mixin
