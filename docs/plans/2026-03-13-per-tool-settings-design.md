# Per-Tool Settings Design

**Date:** 2026-03-13
**Goal:** Each drawing tool remembers its own settings independently. Switching tools restores the settings last used for that tool. Settings persist in the `.retro` project file.

## Data Model

A `ToolSettingsManager` class holds a `dict[str, dict[str, Any]]` mapping lowercase tool names to their settings.

### Settings per tool

| Tool | size | symmetry | dither | pixel_perfect | ink_mode | tolerance |
|------|------|----------|--------|---------------|----------|-----------|
| pen | 1 | off | none | False | normal | - |
| eraser | 3 | off | - | False | normal | - |
| blur | 3 | - | - | - | - | - |
| fill | - | - | none | - | - | 32 |
| line | 1 | - | - | - | - | - |
| rect | 1 | - | - | - | - | - |
| ellipse | 1 | - | - | - | - | - |
| wand | - | - | - | - | - | 32 |
| pick | (none) | | | | | |
| select | (none) | | | | | |
| hand | (none) | | | | | |
| lasso | (none) | | | | | |

Dash means the tool does not use that setting. The defaults map is derived from `TOOL_OPTIONS` in `options_bar.py`.

## ToolSettingsManager API

```python
class ToolSettingsManager:
    def __init__(self):
        self._settings: dict[str, dict[str, Any]] = { ...DEFAULTS... }

    def get(self, tool_name: str) -> dict[str, Any]:
        """Return the current settings dict for a tool."""

    def save(self, tool_name: str, values: dict[str, Any]) -> None:
        """Save current values for a tool (only keys that tool supports)."""

    def to_dict(self) -> dict:
        """Serialize all tool settings for project save."""

    @classmethod
    def from_dict(cls, data: dict) -> ToolSettingsManager:
        """Restore from project file data, falling back to defaults for missing keys."""
```

## Tool Switch Flow

1. User clicks Tool B while Tool A is active.
2. `_on_tool_change(name)` fires:
   a. **Save** current app state into manager for Tool A.
   b. **Load** settings for Tool B from manager.
   c. **Apply** loaded settings to `_tool_size`, `_symmetry_mode`, `_dither_pattern`, `_pixel_perfect`, `_ink_mode`, `_wand_tolerance`.
   d. **UI sync** — call `options_bar.restore_settings(settings)` to update all controls.
3. OptionsBar shows/hides controls as before via `TOOL_OPTIONS`.

## Project File Integration

### Save (`project.py:save_project`)
Add `"tool_settings": manager.to_dict()` to the project JSON. Bump version to 5.

### Load (`project.py:load_project`)
Read `"tool_settings"` key (default to `{}` for older projects). Return it as a third element from `load_project`, or attach it to the timeline. The app initializes `ToolSettingsManager.from_dict(data)`.

## Files Changed

| File | Change |
|------|--------|
| `src/tool_settings.py` (NEW) | `ToolSettingsManager` class |
| `src/app.py` | Wire manager into `__init__`, `_on_tool_change`, callbacks, save/load |
| `src/ui/options_bar.py` | Add `restore_settings()` method for batch UI updates |
| `src/project.py` | Serialize/deserialize `tool_settings` in save/load |

## Backward Compatibility

- Projects saved with version < 5 load normally; `ToolSettingsManager` initializes with defaults.
- Version 5 projects opened in older RetroSprite versions ignore the `tool_settings` key (JSON is additive).
