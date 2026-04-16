"""ProjectContext — encapsulates all per-document state for multi-project tabs."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Optional

from src.animation import AnimationTimeline
from src.grid import GridSettings
from src.palette import Palette


@dataclass
class ProjectContext:
    """All state belonging to a single open document."""

    # Class-level counter for untitled documents — ClassVar excluded from dataclass fields
    _untitled_counter: ClassVar[int] = 0

    # Identity
    project_path: Optional[str] = None
    name: str = "Untitled"
    dirty: bool = False

    # Core data
    timeline: AnimationTimeline = field(default_factory=lambda: AnimationTimeline(64, 64))
    palette: Palette = field(default_factory=lambda: Palette("Pico-8"))

    # Undo / Redo
    undo_stack: list = field(default_factory=list)
    redo_stack: list = field(default_factory=list)

    # Canvas view state
    zoom_level: int = 1
    scroll_x: float = 0.0
    scroll_y: float = 0.0

    # Document-bound settings
    grid_settings: GridSettings = field(default_factory=GridSettings)
    symmetry_mode: str = "off"
    symmetry_axis_x: int = 32
    symmetry_axis_y: int = 32

    # Reference image
    reference: Any = None

    # Playback state
    playing: bool = False
    playback_mode: str = "forward"
    onion_skin: bool = False
    onion_range: int = 1
    pingpong_direction: int = 1

    # Export settings
    export_settings: dict = field(default_factory=dict)

    # Tool settings (document-bound portion)
    tool_settings: Any = None

    # Drawing mode settings (per-document)
    tiled_mode: str = "off"
    dither_pattern: str = "none"
    pixel_perfect: bool = False
    ink_mode: str = "normal"
    fill_mode: str = "normal"

    # Display
    display_effects: bool = True

    @classmethod
    def create_new(cls, width: int, height: int,
                   name: str | None = None) -> ProjectContext:
        """Create a fresh ProjectContext for a new document."""
        from src.tool_settings import ToolSettingsManager

        if name is None:
            cls._untitled_counter += 1
            if cls._untitled_counter == 1:
                name = "Untitled"
            else:
                name = f"Untitled {cls._untitled_counter}"

        timeline = AnimationTimeline(width, height)
        return cls(
            name=name,
            timeline=timeline,
            palette=Palette("Pico-8"),
            symmetry_axis_x=width // 2,
            symmetry_axis_y=height // 2,
            tool_settings=ToolSettingsManager(),
        )

    @classmethod
    def from_loaded(cls, timeline: AnimationTimeline, palette: Palette,
                    path: str, tool_settings: Any = None,
                    reference: Any = None,
                    grid_settings: GridSettings | None = None,
                    symmetry_axis_x: int | None = None,
                    symmetry_axis_y: int | None = None) -> ProjectContext:
        """Create a ProjectContext from loaded project data."""
        import os
        from src.tool_settings import ToolSettingsManager

        gs = grid_settings if grid_settings is not None else GridSettings()
        return cls(
            project_path=path,
            name=os.path.basename(path),
            timeline=timeline,
            palette=palette,
            grid_settings=gs,
            symmetry_axis_x=symmetry_axis_x if symmetry_axis_x is not None else timeline.width // 2,
            symmetry_axis_y=symmetry_axis_y if symmetry_axis_y is not None else timeline.height // 2,
            tool_settings=tool_settings if tool_settings is not None else ToolSettingsManager(),
            reference=reference,
        )
