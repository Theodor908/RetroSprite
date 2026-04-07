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

    entries: list[dict] = []
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                entries = json.load(f)
        except (json.JSONDecodeError, OSError):
            entries = []

    norm = os.path.normpath(path)
    entries = [e for e in entries if os.path.normpath(e.get("path", "")) != norm]
    entries.insert(0, {"path": norm, "timestamp": time.time()})
    entries = entries[:_MAX_RECENTS]

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)
