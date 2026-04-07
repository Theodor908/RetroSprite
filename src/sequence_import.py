"""PNG sequence and sprite sheet import parsers."""
from __future__ import annotations
import json
import os
import re
from PIL import Image
from src.animated_import import ImportedAnimation


def _natural_sort_key(path: str):
    """Sort key that handles embedded numbers naturally.

    'frame_2.png' sorts before 'frame_10.png'.
    """
    name = os.path.basename(path)
    return [int(c) if c.isdigit() else c.lower()
            for c in re.split(r'(\d+)', name)]


def scan_folder_for_pngs(folder: str) -> list[str]:
    """Scan a folder for numbered PNG files, return naturally sorted paths."""
    paths = []
    for name in os.listdir(folder):
        if name.lower().endswith(".png"):
            paths.append(os.path.join(folder, name))
    paths.sort(key=_natural_sort_key)
    return paths


def parse_png_sequence(paths: list[str]) -> ImportedAnimation:
    """Parse a list of PNG file paths into ImportedAnimation.

    Args:
        paths: Pre-sorted list of PNG file paths.

    Returns:
        ImportedAnimation with all frames loaded, durations defaulting to 100ms.
    """
    if not paths:
        raise ValueError("No frames provided for PNG sequence import")

    frames: list[Image.Image] = []
    for p in paths:
        img = Image.open(p).convert("RGBA")
        frames.append(img)

    width, height = frames[0].size
    durations = [100] * len(frames)
    source = os.path.dirname(paths[0]) if paths else ""

    return ImportedAnimation(
        frames=frames,
        durations=durations,
        width=width,
        height=height,
        palette=None,
        source_path=source,
    )


def parse_sprite_sheet_json(png_path: str, json_path: str) -> ImportedAnimation:
    """Parse a sprite sheet using RetroSprite's JSON sidecar metadata.

    The JSON contains a "frames" array with {x, y, w, h, duration} per frame
    and a "size" object with {w, h} for the original frame dimensions.
    """
    with open(json_path, "r") as f:
        meta = json.load(f)

    sheet = Image.open(png_path).convert("RGBA")
    frame_defs = meta["frames"]
    if not frame_defs:
        raise ValueError(f"No frames defined in JSON: {json_path}")

    scale = meta.get("scale", 1)
    orig_w = meta["size"]["w"]
    orig_h = meta["size"]["h"]

    frames: list[Image.Image] = []
    durations: list[int] = []

    for fd in frame_defs:
        region = sheet.crop((fd["x"], fd["y"],
                             fd["x"] + fd["w"], fd["y"] + fd["h"]))
        if scale > 1:
            region = region.resize((orig_w, orig_h), Image.NEAREST)
        frames.append(region)
        durations.append(fd.get("duration", 100))

    return ImportedAnimation(
        frames=frames,
        durations=durations,
        width=orig_w,
        height=orig_h,
        palette=None,
        source_path=png_path,
    )


def parse_sprite_sheet_grid(path: str, cols: int, rows: int,
                            frame_w: int, frame_h: int) -> ImportedAnimation:
    """Parse a sprite sheet by slicing it into a uniform grid.

    Frames are read left-to-right, top-to-bottom.
    """
    if cols <= 0 or rows <= 0:
        raise ValueError("No frames: cols and rows must be > 0")

    sheet = Image.open(path).convert("RGBA")
    frames: list[Image.Image] = []

    for row in range(rows):
        for col in range(cols):
            x = col * frame_w
            y = row * frame_h
            if x + frame_w > sheet.width or y + frame_h > sheet.height:
                continue
            region = sheet.crop((x, y, x + frame_w, y + frame_h))
            frames.append(region)

    if not frames:
        raise ValueError(f"No frames extracted from sprite sheet: {path}")

    durations = [100] * len(frames)

    return ImportedAnimation(
        frames=frames,
        durations=durations,
        width=frame_w,
        height=frame_h,
        palette=None,
        source_path=path,
    )
