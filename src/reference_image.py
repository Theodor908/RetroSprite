"""ReferenceImage data model for positionable overlay."""
from __future__ import annotations
from dataclasses import dataclass
from PIL import Image


@dataclass
class ReferenceImage:
    """A positionable reference image overlay on the canvas."""
    image: Image.Image
    x: int = 0
    y: int = 0
    scale: float = 1.0
    opacity: float = 0.3
    visible: bool = True
    path: str = ""

    def fit_to_canvas(self, canvas_w: int, canvas_h: int) -> None:
        """Set scale so the image fits within canvas bounds. No upscaling."""
        img_w, img_h = self.image.size
        if img_w <= 0 or img_h <= 0:
            return
        scale_x = canvas_w / img_w
        scale_y = canvas_h / img_h
        self.scale = min(scale_x, scale_y, 1.0)
        self.x = 0
        self.y = 0
