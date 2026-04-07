"""WebP and APNG animated export for RetroSprite."""
from __future__ import annotations
from PIL import Image


def export_webp(timeline, path: str, scale: int = 1, loop: int = 0,
                frame_start: int | None = None, frame_end: int | None = None) -> None:
    """Export animation as lossless WebP.

    Uses Pillow save_all with per-frame durations from timeline frames.
    """
    frames: list[Image.Image] = []
    durations: list[int] = []

    start = frame_start if frame_start is not None else 0
    end = frame_end if frame_end is not None else len(timeline._frames) - 1

    for i in range(start, end + 1):
        frame_obj = timeline._frames[i]
        grid = frame_obj.flatten()
        img = grid.to_pil_image()
        if scale > 1:
            img = img.resize((img.width * scale, img.height * scale),
                             Image.NEAREST)
        frames.append(img)
        durations.append(frame_obj.duration_ms)

    if not frames:
        return
    frames[0].save(
        path, save_all=True, append_images=frames[1:],
        duration=durations, loop=loop, lossless=True, format="WEBP"
    )


def export_apng(timeline, path: str, scale: int = 1, loop: int = 0,
                frame_start: int | None = None, frame_end: int | None = None) -> None:
    """Export animation as APNG.

    Uses Pillow save_all with disposal=2 (clear) and per-frame durations.
    """
    frames: list[Image.Image] = []
    durations: list[int] = []

    start = frame_start if frame_start is not None else 0
    end = frame_end if frame_end is not None else len(timeline._frames) - 1

    for i in range(start, end + 1):
        frame_obj = timeline._frames[i]
        grid = frame_obj.flatten()
        img = grid.to_pil_image()
        if scale > 1:
            img = img.resize((img.width * scale, img.height * scale),
                             Image.NEAREST)
        frames.append(img)
        durations.append(frame_obj.duration_ms)

    if not frames:
        return
    frames[0].save(
        path, save_all=True, append_images=frames[1:],
        duration=durations, loop=loop, disposal=2, format="PNG"
    )
