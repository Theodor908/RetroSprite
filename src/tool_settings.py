"""Per-tool settings manager for RetroSprite.

Each drawing tool remembers its own settings independently.
Settings are serialized into the .retro project file.
"""
from __future__ import annotations
from copy import deepcopy


# Default settings per tool. Keys must match TOOL_OPTIONS in options_bar.py.
TOOL_DEFAULTS: dict[str, dict] = {
    "pen":     {"size": 1, "symmetry": "off", "dither": "none", "pixel_perfect": False, "ink_mode": "normal"},
    "eraser":  {"size": 3, "symmetry": "off", "pixel_perfect": False, "ink_mode": "normal"},
    "blur":    {"size": 3},
    "fill":    {"tolerance": 32, "dither": "none", "fill_mode": "normal"},
    "line":    {"size": 1},
    "rect":    {"size": 1},
    "ellipse": {"size": 1},
    "wand":    {"tolerance": 32},
    "pick":    {},
    "select":  {},
    "move":    {},
    "hand":    {},
    "lasso":   {},
    "polygon": {"size": 1},
    "roundrect": {"size": 1, "corner_radius": 2},
    "text": {"font_name": "Standard 5x7", "font_size": 12, "spacing": 1, "line_height": 2, "align": "left"},
}


class ToolSettingsManager:
    """Stores and retrieves per-tool settings."""

    def __init__(self):
        self._settings: dict[str, dict] = deepcopy(TOOL_DEFAULTS)

    def get(self, tool_name: str) -> dict:
        """Return current settings for *tool_name* (lowercase).
        Returns empty dict for unknown tools."""
        return dict(self._settings.get(tool_name, {}))

    def save(self, tool_name: str, values: dict) -> None:
        """Update stored settings for *tool_name*.
        Only keys that exist in that tool's defaults are accepted."""
        if tool_name not in self._settings:
            return
        allowed = self._settings[tool_name]
        for key, value in values.items():
            if key in allowed:
                allowed[key] = value

    def to_dict(self) -> dict:
        """Serialize all tool settings for project save."""
        return deepcopy(self._settings)

    @classmethod
    def from_dict(cls, data: dict) -> ToolSettingsManager:
        """Restore from project file data.
        Missing tools/keys fall back to defaults."""
        mgr = cls()
        for tool_name, saved_values in data.items():
            if tool_name in mgr._settings:
                for key, value in saved_values.items():
                    if key in mgr._settings[tool_name]:
                        mgr._settings[tool_name][key] = value
        return mgr
