"""Customizable keyboard shortcuts manager."""
from __future__ import annotations
import json
import os

DEFAULT_BINDINGS = {
    "pen": "p",
    "eraser": "e",
    "blur": "b",
    "fill": "f",
    "pick": "i",
    "select": "s",
    "line": "l",
    "rect": "r",
    "hand": "h",
    "ellipse": "o",
    "wand": "w",
    "move": "v",
    "lasso": "a",
    "polygon": "n",
    "text": "t",
    "roundrect": "u",
    "symmetry": "m",
    "dither": "d",
    "pixel_perfect": "g",
    "darken": "bracketleft",
    "lighten": "bracketright",
    "zoom_in": "plus",
    "zoom_out": "minus",
    "transform": "<Control-t>",
}

CONFIG_DIR = os.path.expanduser("~/.retrosprite")
CONFIG_FILE = os.path.join(CONFIG_DIR, "keybindings.json")


class KeybindingsManager:
    def __init__(self):
        self.bindings = dict(DEFAULT_BINDINGS)
        self._load()

    def _load(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE) as f:
                    custom = json.load(f)
                self.bindings.update(custom)
            except (json.JSONDecodeError, IOError):
                pass

    def save(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(self.bindings, f, indent=2)

    def get(self, action: str) -> str:
        return self.bindings.get(action, "")

    def set(self, action: str, key: str):
        self.bindings[action] = key

    def get_all(self) -> dict:
        return dict(self.bindings)
