# Batch 2: Layer Enhancements — Blend Modes & Layer Groups

**Date:** 2026-03-11

## Overview

Add 9 blend modes to the compositing pipeline and implement layer groups using a flat-list-with-depth approach (Aseprite-style).

## 1. Blend Modes

### Supported Modes (9 total)
- **normal** (existing)
- **multiply** — darkens: `result = base * blend / 255`
- **screen** — lightens: `result = 255 - (255-base) * (255-blend) / 255`
- **overlay** — contrast: multiply if base < 128, screen if base >= 128
- **addition** — `result = min(255, base + blend)`
- **subtract** — `result = max(0, base - blend)`
- **darken** — `result = min(base, blend)`
- **lighten** — `result = max(base, blend)`
- **difference** — `result = abs(base - blend)`

### Implementation
- Add `apply_blend_mode(base_arr, blend_arr, mode)` function to `src/layer.py`
- Operates on NumPy arrays (H,W,4 uint8) for performance
- All blend math on RGB channels only; alpha compositing uses standard formula
- Update `flatten_layers()` to call blend function instead of `Image.alpha_composite`
- Formula: for each pixel, blend RGB via mode formula, then composite using blend layer's alpha

### UI
- Add dropdown (OptionMenu) per layer row in `src/ui/timeline.py`
- Fires `on_layer_blend_mode` callback → app sets `layer.blend_mode` across all frames
- Compact: shows abbreviated mode name (e.g., "Mul", "Scr", "Ovr")

## 2. Layer Groups (Flat List + Depth)

### Data Model
- Add `depth: int = 0` to Layer class (nesting level)
- Add `is_group: bool = False` to Layer class
- A group layer has `is_group=True`, its `pixels` are unused (empty)
- Children are consecutive layers after the group with `depth > group.depth`
- Children end when a layer at `depth <= group.depth` is encountered

Example flat list:
```
[0] Layer "BG"           depth=0, is_group=False
[1] Group "Character"    depth=0, is_group=True
[2] Layer "Outline"      depth=1, is_group=False   ← child of Character
[3] Layer "Color"        depth=1, is_group=False   ← child of Character
[4] Group "Effects"      depth=1, is_group=True    ← child of Character (nested group)
[5] Layer "Shadow"       depth=2, is_group=False   ← child of Effects
[6] Layer "Top"          depth=0, is_group=False   ← back to root level
```

### Compositing
- Walk layers bottom-to-top
- When entering a group: push current composite onto stack
- Composite children within the group
- When exiting a group: pop stack, blend group result onto parent using group's blend_mode/opacity

### UI
- Indent layer rows based on `depth` (8px per level)
- Group rows show expand/collapse toggle (▶/▼)
- Collapsed groups hide child layers in timeline
- "Add Group" button/menu item

### Serialization
- Add `depth` and `is_group` fields to layer JSON
- Backward compat: missing fields default to `depth=0, is_group=False`

## Out of Scope
- Drag-and-drop layer reordering between groups
- Clipping masks
- Layer effects (separate batch)
