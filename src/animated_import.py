"""Animated format import (GIF, APNG, WebP) and timeline builder."""
from __future__ import annotations
from dataclasses import dataclass
from PIL import Image, ImageSequence
from src.animation import AnimationTimeline, Frame
from src.layer import Layer
from src.pixel_data import PixelGrid


@dataclass
class ImportedAnimation:
    """Common structure produced by all format parsers."""
    frames: list[Image.Image]
    durations: list[int]
    width: int
    height: int
    palette: list[tuple[int, int, int, int]] | None
    source_path: str


@dataclass
class ImportSettings:
    """User choices from the import dialog."""
    mode: str       # "new_project" or "insert"
    resize: str     # "match", "scale", "crop"
    timing: str     # "original" or "project_fps"


def _extract_palette(img: Image.Image) -> list[tuple[int, int, int, int]] | None:
    """Extract palette colors from a P-mode image, or None."""
    if img.mode != "P":
        return None
    raw = img.getpalette()
    if raw is None:
        return None
    colors = []
    for i in range(0, min(len(raw), 768), 3):
        colors.append((raw[i], raw[i + 1], raw[i + 2], 255))
    return colors if colors else None


def parse_gif(path: str) -> ImportedAnimation:
    """Parse an animated GIF into ImportedAnimation.

    Handles GIF disposal methods by maintaining a running canvas
    and compositing each frame according to its disposal method.
    """
    img = Image.open(path)
    if img.format != "GIF":
        raise ValueError(f"Not a GIF file: {path}")

    palette = _extract_palette(img)
    width, height = img.size
    frames: list[Image.Image] = []
    durations: list[int] = []

    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))

    for frame_idx, frame in enumerate(ImageSequence.Iterator(img)):
        disposal = getattr(img, "disposal_method", 0)
        prev_canvas = canvas.copy()

        rgba_frame = frame.convert("RGBA")
        canvas.paste(rgba_frame, (0, 0), rgba_frame)
        frames.append(canvas.copy())

        dur = frame.info.get("duration", 100)
        if dur <= 0:
            dur = 100
        durations.append(dur)

        if disposal == 2:
            canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        elif disposal == 3:
            canvas = prev_canvas

    if not frames:
        raise ValueError(f"No frames found in GIF: {path}")

    return ImportedAnimation(
        frames=frames,
        durations=durations,
        width=width,
        height=height,
        palette=palette,
        source_path=path,
    )


def _parse_animated_image(path: str, format_name: str) -> ImportedAnimation:
    """Shared parser for APNG and WebP animated images.

    Both formats are handled identically by Pillow's ImageSequence.
    """
    img = Image.open(path)
    width, height = img.size

    frames: list[Image.Image] = []
    durations: list[int] = []

    for frame in ImageSequence.Iterator(img):
        frames.append(frame.convert("RGBA").copy())
        dur = frame.info.get("duration", 100)
        if dur <= 0:
            dur = 100
        durations.append(dur)

    if not frames:
        raise ValueError(f"No frames found in {format_name} file: {path}")

    return ImportedAnimation(
        frames=frames,
        durations=durations,
        width=width,
        height=height,
        palette=None,
        source_path=path,
    )


def parse_apng(path: str) -> ImportedAnimation:
    """Parse an animated PNG (APNG) into ImportedAnimation."""
    return _parse_animated_image(path, "APNG")


def parse_webp(path: str) -> ImportedAnimation:
    """Parse an animated WebP into ImportedAnimation."""
    return _parse_animated_image(path, "WebP")


def build_timeline_from_import(
    animation: ImportedAnimation,
    settings: ImportSettings,
    existing_timeline: AnimationTimeline | None = None,
    project_fps: int = 10,
) -> tuple[AnimationTimeline, list[tuple[int, int, int, int]] | None]:
    """Build or modify a timeline from imported animation data.

    Returns:
        (timeline, palette_colors) — palette_colors is None in insert mode.
    """
    if settings.mode == "new_project":
        return _build_new_project(animation, settings, project_fps)
    else:
        return _build_insert(animation, settings, existing_timeline, project_fps)


def _compute_duration(settings: ImportSettings, original_ms: int,
                      project_fps: int) -> int:
    if settings.timing == "project_fps":
        return max(1, 1000 // project_fps)
    return original_ms


def _build_new_project(
    animation: ImportedAnimation,
    settings: ImportSettings,
    project_fps: int,
) -> tuple[AnimationTimeline, list[tuple[int, int, int, int]] | None]:
    timeline = AnimationTimeline(animation.width, animation.height)
    timeline._frames.clear()

    for i, (pil_img, dur) in enumerate(zip(animation.frames, animation.durations)):
        frame = Frame(animation.width, animation.height,
                      name=f"Frame {i + 1}")
        frame.layers.clear()
        layer = Layer("Layer 1", animation.width, animation.height)
        layer.pixels = PixelGrid.from_pil_image(pil_img)
        frame.layers.append(layer)
        frame.active_layer_index = 0
        frame.duration_ms = _compute_duration(settings, dur, project_fps)
        timeline._frames.append(frame)

    return timeline, animation.palette


def _resize_frame_pixels(frame: Frame, new_w: int, new_h: int) -> None:
    """Resize all layers in a frame to new dimensions (pad with transparent)."""
    for layer in frame.layers:
        old_img = layer.pixels.to_pil_image()
        new_img = Image.new("RGBA", (new_w, new_h), (0, 0, 0, 0))
        new_img.paste(old_img, (0, 0))
        layer.pixels = PixelGrid.from_pil_image(new_img)
    frame.width = new_w
    frame.height = new_h


def _build_insert(
    animation: ImportedAnimation,
    settings: ImportSettings,
    existing_timeline: AnimationTimeline,
    project_fps: int,
) -> tuple[AnimationTimeline, None]:
    canvas_w = existing_timeline.width
    canvas_h = existing_timeline.height

    # Handle resize strategy
    if settings.resize == "match":
        new_w, new_h = animation.width, animation.height
        if new_w != canvas_w or new_h != canvas_h:
            for frame_obj in existing_timeline._frames:
                _resize_frame_pixels(frame_obj, new_w, new_h)
            existing_timeline.width = new_w
            existing_timeline.height = new_h
            canvas_w, canvas_h = new_w, new_h

    insert_after = existing_timeline.current_index

    for i, (pil_img, dur) in enumerate(zip(animation.frames, animation.durations)):
        # Apply resize to imported frame
        if settings.resize == "scale" and (pil_img.size != (canvas_w, canvas_h)):
            pil_img = pil_img.resize((canvas_w, canvas_h), Image.NEAREST)
        elif settings.resize == "crop":
            cropped = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
            offset_x = (canvas_w - animation.width) // 2
            offset_y = (canvas_h - animation.height) // 2
            cropped.paste(pil_img, (offset_x, offset_y))
            pil_img = cropped

        frame = Frame(canvas_w, canvas_h, name=f"Imported {i + 1}")
        frame.layers.clear()
        layer = Layer("Layer 1", canvas_w, canvas_h)
        layer.pixels = PixelGrid.from_pil_image(pil_img)
        frame.layers.append(layer)
        frame.active_layer_index = 0
        frame.duration_ms = _compute_duration(settings, dur, project_fps)

        idx = insert_after + 1 + i
        existing_timeline._frames.insert(idx, frame)

    existing_timeline.sync_layers()
    return existing_timeline, None
