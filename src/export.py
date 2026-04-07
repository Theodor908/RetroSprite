"""Export utilities for RetroSprite."""
from __future__ import annotations
import json
import os
from PIL import Image


def build_sprite_sheet(timeline, scale: int = 1, columns: int = 0,
                       frame_start: int | None = None, frame_end: int | None = None):
    """Build a sprite sheet from animation frames.

    Returns (PIL.Image, dict) -- the sheet image and JSON metadata.
    """
    start = frame_start if frame_start is not None else 0
    end = frame_end if frame_end is not None else timeline.frame_count - 1
    fc = end - start + 1
    w, h = timeline.width, timeline.height

    if columns <= 0:
        columns = fc  # horizontal strip by default
    rows = (fc + columns - 1) // columns

    sw = w * scale * columns
    sh = h * scale * rows
    sheet = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))

    frames_meta = []
    for idx, i in enumerate(range(start, end + 1)):
        grid = timeline.get_frame(i)
        img = grid.to_pil_image()
        if scale > 1:
            img = img.resize((w * scale, h * scale), Image.NEAREST)
        col = idx % columns
        row = idx // columns
        px = col * w * scale
        py = row * h * scale
        sheet.paste(img, (px, py))
        frames_meta.append({
            "x": px, "y": py,
            "w": w * scale, "h": h * scale,
            "duration": timeline.get_frame_obj(i).duration_ms,
        })

    tags_meta = []
    for tag in timeline.tags:
        tags_meta.append({
            "name": tag["name"],
            "from": tag["start"],
            "to": tag["end"],
        })

    metadata = {
        "frames": frames_meta,
        "tags": tags_meta,
        "size": {"w": w, "h": h},
        "scale": scale,
    }

    return sheet, metadata


def save_sprite_sheet(timeline, filepath: str, scale: int = 1, columns: int = 0,
                      frame_start: int | None = None, frame_end: int | None = None):
    """Save sprite sheet PNG + JSON sidecar."""
    sheet, metadata = build_sprite_sheet(timeline, scale, columns,
                                         frame_start=frame_start, frame_end=frame_end)
    sheet.save(filepath)
    json_path = filepath.rsplit(".", 1)[0] + ".json"
    with open(json_path, "w") as f:
        json.dump(metadata, f, indent=2)
    return json_path


def export_png_sequence(timeline, output_path: str, scale: int = 1,
                        layer=None, frame_start: int | None = None,
                        frame_end: int | None = None) -> list[str]:
    """Export each frame as a numbered PNG file."""
    base, ext = os.path.splitext(output_path)
    if not ext:
        ext = ".png"
    start = frame_start if frame_start is not None else 0
    end = frame_end if frame_end is not None else timeline.frame_count - 1
    paths = []
    for i in range(start, end + 1):
        if layer is not None:
            frame_obj = timeline.get_frame_obj(i)
            if isinstance(layer, str):
                target = next((l for l in frame_obj.layers if l.name == layer), None)
            else:
                target = frame_obj.layers[layer] if 0 <= layer < len(frame_obj.layers) else None
            if target:
                img = target.pixels.to_pil_image()
            else:
                img = Image.new("RGBA", (timeline.width, timeline.height), (0, 0, 0, 0))
        else:
            grid = timeline.get_frame(i)
            img = grid.to_pil_image()
        if scale > 1:
            img = img.resize((timeline.width * scale, timeline.height * scale), Image.NEAREST)
        frame_path = f"{base}_{i:03d}{ext}"
        img.save(frame_path)
        paths.append(frame_path)
    return paths


def export_png_single(timeline, path: str, frame: int = 0, scale: int = 1,
                      layer: int | str | None = None) -> None:
    """Export a single frame as PNG with user-chosen scale.

    This is the shared backend for PNG export used by both the GUI and CLI.
    """
    frame_obj = timeline.get_frame_obj(frame)
    if layer is not None:
        if isinstance(layer, str):
            target = next((l for l in frame_obj.layers if l.name == layer), None)
            if target is None:
                raise ValueError(f"Layer '{layer}' not found")
        else:
            if 0 <= layer < len(frame_obj.layers):
                target = frame_obj.layers[layer]
            else:
                raise ValueError(f"Layer index {layer} out of range")
        img = target.pixels.to_pil_image()
    else:
        grid = frame_obj.flatten()
        img = grid.to_pil_image()

    if scale > 1:
        img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
    img.save(path)
