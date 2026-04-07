"""Base classes for plugin tools and effects."""
from __future__ import annotations


class PluginTool:
    """Base class for custom drawing tools registered by plugins.

    Subclass and override on_click/on_drag/on_release to implement behavior.
    Tool receives pixel coordinates (already converted from screen coords).
    """

    name: str = ""
    icon: str | None = None       # path to 16x16 PNG, or None for text label
    cursor: str = "crosshair"     # Tkinter cursor name

    def on_click(self, api, x: int, y: int) -> None:
        """Called on mouse down."""
        pass

    def on_drag(self, api, x: int, y: int) -> None:
        """Called on mouse move while pressed."""
        pass

    def on_release(self, api, x: int, y: int) -> None:
        """Called on mouse up."""
        pass

    def on_options_bar(self, api, frame) -> None:
        """Optional: add widgets to options bar Frame."""
        pass

    def on_preview(self, api, canvas, x: int, y: int) -> None:
        """Optional: draw preview overlay on canvas."""
        pass
