"""Grid overlay settings for RetroSprite."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class GridSettings:
    """Dual grid configuration: pixel grid (1x1) + custom grid (NxM)."""

    # Pixel grid (1x1)
    pixel_grid_visible: bool = True
    pixel_grid_color: tuple[int, int, int, int] = (180, 180, 180, 80)
    pixel_grid_min_zoom: int = 4

    # Custom grid (NxM)
    custom_grid_visible: bool = False
    custom_grid_width: int = 16
    custom_grid_height: int = 16
    custom_grid_offset_x: int = 0
    custom_grid_offset_y: int = 0
    custom_grid_color: tuple[int, int, int, int] = (0, 240, 255, 120)

    def __post_init__(self):
        self.custom_grid_width = max(1, self.custom_grid_width)
        self.custom_grid_height = max(1, self.custom_grid_height)

    def to_dict(self) -> dict:
        return {
            "pixel_visible": self.pixel_grid_visible,
            "pixel_color": list(self.pixel_grid_color),
            "pixel_min_zoom": self.pixel_grid_min_zoom,
            "custom_visible": self.custom_grid_visible,
            "custom_width": self.custom_grid_width,
            "custom_height": self.custom_grid_height,
            "custom_offset_x": self.custom_grid_offset_x,
            "custom_offset_y": self.custom_grid_offset_y,
            "custom_color": list(self.custom_grid_color),
        }

    def snap(self, x: int, y: int) -> tuple[int, int]:
        """Snap coordinates to nearest custom grid intersection.

        Only snaps when custom grid is visible with valid dimensions.
        Returns original coordinates unchanged if grid is not active.
        """
        if not self.custom_grid_visible:
            return x, y
        gw = self.custom_grid_width
        gh = self.custom_grid_height
        if gw <= 0 or gh <= 0:
            return x, y
        ox = self.custom_grid_offset_x
        oy = self.custom_grid_offset_y
        sx = round((x - ox) / gw) * gw + ox
        sy = round((y - oy) / gh) * gh + oy
        return sx, sy

    @classmethod
    def from_dict(cls, data: dict) -> GridSettings:
        defaults = cls()
        return cls(
            pixel_grid_visible=data.get("pixel_visible", defaults.pixel_grid_visible),
            pixel_grid_color=tuple(data.get("pixel_color", list(defaults.pixel_grid_color))),
            pixel_grid_min_zoom=data.get("pixel_min_zoom", defaults.pixel_grid_min_zoom),
            custom_grid_visible=data.get("custom_visible", defaults.custom_grid_visible),
            custom_grid_width=data.get("custom_width", defaults.custom_grid_width),
            custom_grid_height=data.get("custom_height", defaults.custom_grid_height),
            custom_grid_offset_x=data.get("custom_offset_x", defaults.custom_grid_offset_x),
            custom_grid_offset_y=data.get("custom_offset_y", defaults.custom_grid_offset_y),
            custom_grid_color=tuple(data.get("custom_color", list(defaults.custom_grid_color))),
        )
