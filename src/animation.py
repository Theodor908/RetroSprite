"""Animation timeline and frame management."""
from __future__ import annotations
from src.pixel_data import PixelGrid
from src.layer import Layer, flatten_layers


class Frame:
    """A single animation frame containing one or more layers."""

    def __init__(self, width: int, height: int, name: str = "",
                 color_mode: str = "rgba", palette: list[tuple] | None = None):
        self.width = width
        self.height = height
        self.name = name
        self.color_mode = color_mode
        self._palette = palette
        self.layers: list[Layer] = [Layer("Layer 1", width, height,
                                          color_mode=color_mode, palette=palette)]
        self.active_layer_index: int = 0
        self.duration_ms: int = 100

    @property
    def active_layer(self) -> Layer:
        return self.layers[self.active_layer_index]

    def flatten(self) -> PixelGrid:
        return flatten_layers(self.layers, self.width, self.height)

    def add_layer(self, name: str | None = None) -> Layer:
        if name is None:
            name = f"Layer {len(self.layers) + 1}"
        layer = Layer(name, self.width, self.height,
                      color_mode=self.color_mode, palette=self._palette)
        self.layers.append(layer)
        self.active_layer_index = len(self.layers) - 1
        return layer

    def remove_layer(self, index: int) -> None:
        if len(self.layers) > 1 and 0 <= index < len(self.layers):
            self.layers.pop(index)
            if self.active_layer_index >= len(self.layers):
                self.active_layer_index = len(self.layers) - 1

    def duplicate_layer(self, index: int) -> Layer:
        if 0 <= index < len(self.layers):
            copy = self.layers[index].copy()
            self.layers.insert(index + 1, copy)
            self.active_layer_index = index + 1
            return copy
        return self.layers[self.active_layer_index]

    def merge_down(self, index: int) -> None:
        if index > 0 and index < len(self.layers):
            above = self.layers[index]
            below = self.layers[index - 1]
            # Auto-unlink the below layer to prevent cross-frame propagation
            if hasattr(below, 'unlink'):
                below.unlink()
            # Rasterize tilemap layers before merging
            if hasattr(above, 'is_tilemap') and above.is_tilemap():
                from src.tilemap import TilemapLayer
                above_layer = Layer(above.name, self.width, self.height)
                above_layer.pixels._pixels = above.render_to_pixels()
                above_layer.visible = above.visible
                above_layer.opacity = above.opacity
                above_layer.blend_mode = above.blend_mode
            elif getattr(above, 'color_mode', 'rgba') == "indexed":
                above_layer = Layer(above.name, self.width, self.height)
                above_layer.pixels._pixels = above.pixels.to_rgba()
                above_layer.visible = above.visible
                above_layer.opacity = above.opacity
                above_layer.blend_mode = above.blend_mode
            else:
                above_layer = above
            if hasattr(below, 'is_tilemap') and below.is_tilemap():
                from src.tilemap import TilemapLayer
                below_layer = Layer(below.name, self.width, self.height)
                below_layer.pixels._pixels = below.render_to_pixels()
                below_layer.visible = below.visible
                below_layer.opacity = below.opacity
                below_layer.blend_mode = below.blend_mode
            elif getattr(below, 'color_mode', 'rgba') == "indexed":
                below_layer = Layer(below.name, self.width, self.height)
                below_layer.pixels._pixels = below.pixels.to_rgba()
                below_layer.visible = below.visible
                below_layer.opacity = below.opacity
                below_layer.blend_mode = below.blend_mode
            else:
                below_layer = below
            merged = flatten_layers([below_layer, above_layer], self.width, self.height)
            if hasattr(below, 'is_tilemap') and below.is_tilemap():
                plain = Layer(below.name, self.width, self.height)
                plain.pixels._pixels = merged._pixels.copy()
                plain.visible = below.visible
                plain.opacity = below.opacity
                plain.blend_mode = below.blend_mode
                self.layers[index - 1] = plain
            elif getattr(below, 'color_mode', 'rgba') == "indexed":
                for y in range(self.height):
                    for x in range(self.width):
                        color = merged.get_pixel(x, y)
                        if color:
                            below.pixels.set_pixel(x, y, color)
            else:
                below.pixels._pixels = merged._pixels.copy()
            self.layers.pop(index)
            self.active_layer_index = index - 1

    def move_layer(self, from_idx: int, to_idx: int) -> None:
        if (0 <= from_idx < len(self.layers) and
                0 <= to_idx < len(self.layers)):
            layer = self.layers.pop(from_idx)
            self.layers.insert(to_idx, layer)

    def copy(self, linked: bool = False) -> Frame:
        copy_name = f"copy_00_{self.name}" if self.name else ""
        new_frame = Frame(self.width, self.height, name=copy_name,
                          color_mode=self.color_mode, palette=self._palette)
        new_layer_list = []
        for layer in self.layers:
            if linked:
                new_layer = layer.copy()  # deep copy handles indexed/rgba
                new_layer.pixels = layer.pixels  # Override with shared reference
                new_layer.cel_id = layer.cel_id  # Same ID = linked
            else:
                new_layer = layer.copy()  # independent copy with new cel_id
            new_layer_list.append(new_layer)
        new_frame.layers = new_layer_list
        new_frame.active_layer_index = self.active_layer_index
        new_frame.duration_ms = self.duration_ms
        return new_frame


class AnimationTimeline:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self._frames: list[Frame] = [Frame(width, height, name="frame_000")]
        self._current_index: int = 0
        self.fps: int = 10
        self.tags: list[dict] = []
        self.tilesets: dict = {}  # name -> Tileset (project-scoped)
        self.color_mode: str = "rgba"
        self.palette_ref: list[tuple] | None = None

    @property
    def frame_count(self) -> int:
        return len(self._frames)

    @property
    def num_layers(self) -> int:
        """Global layer count (max across all frames)."""
        if not self._frames:
            return 0
        return max(len(f.layers) for f in self._frames)

    @property
    def current_index(self) -> int:
        return self._current_index

    def sync_layers(self) -> None:
        """Pad shorter frames so all frames have the same layer count.
        Copies layer names/settings from the frame with the most layers."""
        if not self._frames:
            return
        max_layers = max(len(f.layers) for f in self._frames)
        # Find the reference frame (the one with the most layers)
        ref = max(self._frames, key=lambda f: len(f.layers))
        for frame in self._frames:
            while len(frame.layers) < max_layers:
                idx = len(frame.layers)
                ref_layer = ref.layers[idx]
                if hasattr(ref_layer, 'is_tilemap') and ref_layer.is_tilemap():
                    from src.tilemap import TilemapLayer
                    new_layer = TilemapLayer(ref_layer.name, self.width, self.height, ref_layer.tileset)
                else:
                    new_layer = Layer(ref_layer.name, self.width, self.height,
                                      color_mode=self.color_mode, palette=self.palette_ref)
                new_layer.visible = ref_layer.visible
                new_layer.locked = ref_layer.locked
                new_layer.opacity = ref_layer.opacity
                new_layer.depth = ref_layer.depth
                new_layer.is_group = ref_layer.is_group
                frame.layers.append(new_layer)

    def current_frame_obj(self) -> Frame:
        return self._frames[self._current_index]

    def current_frame(self) -> PixelGrid:
        return self._frames[self._current_index].flatten()

    def current_layer(self) -> PixelGrid:
        return self._frames[self._current_index].active_layer.pixels

    def get_frame(self, index: int) -> PixelGrid:
        return self._frames[index].flatten()

    def get_frame_obj(self, index: int) -> Frame:
        return self._frames[index]

    def set_current(self, index: int) -> None:
        if 0 <= index < len(self._frames):
            self._current_index = index

    def add_frame(self) -> None:
        new_frame = Frame(self.width, self.height,
                          name=f"frame_{len(self._frames):03d}",
                          color_mode=self.color_mode, palette=self.palette_ref)
        # Match layer count from first existing frame (global layer structure)
        if self._frames:
            ref = self._frames[0]
            while len(new_frame.layers) < len(ref.layers):
                new_frame.add_layer(f"Layer {len(new_frame.layers) + 1}")
            # Copy layer names and properties from reference
            for i, ref_layer in enumerate(ref.layers):
                new_frame.layers[i].name = ref_layer.name
                new_frame.layers[i].visible = ref_layer.visible
                new_frame.layers[i].locked = ref_layer.locked
                new_frame.layers[i].opacity = ref_layer.opacity
                new_frame.layers[i].depth = ref_layer.depth
                new_frame.layers[i].is_group = ref_layer.is_group
                if hasattr(ref_layer, 'is_tilemap') and ref_layer.is_tilemap():
                    from src.tilemap import TilemapLayer
                    tl = TilemapLayer(ref_layer.name, self.width, self.height, ref_layer.tileset)
                    tl.visible = ref_layer.visible
                    tl.locked = ref_layer.locked
                    tl.opacity = ref_layer.opacity
                    new_frame.layers[i] = tl
            new_frame.active_layer_index = ref.active_layer_index
        self._frames.append(new_frame)

    def insert_frame(self, after_index: int) -> None:
        """Insert a new empty frame after the given index."""
        new_frame = Frame(self.width, self.height,
                          name=f"frame_{len(self._frames):03d}",
                          color_mode=self.color_mode, palette=self.palette_ref)
        if self._frames:
            ref = self._frames[0]
            while len(new_frame.layers) < len(ref.layers):
                new_frame.add_layer(f"Layer {len(new_frame.layers) + 1}")
            for i, ref_layer in enumerate(ref.layers):
                new_frame.layers[i].name = ref_layer.name
                new_frame.layers[i].visible = ref_layer.visible
                new_frame.layers[i].locked = ref_layer.locked
                new_frame.layers[i].opacity = ref_layer.opacity
                new_frame.layers[i].depth = ref_layer.depth
                new_frame.layers[i].is_group = ref_layer.is_group
                if hasattr(ref_layer, 'is_tilemap') and ref_layer.is_tilemap():
                    from src.tilemap import TilemapLayer
                    tl = TilemapLayer(ref_layer.name, self.width, self.height, ref_layer.tileset)
                    tl.visible = ref_layer.visible
                    tl.locked = ref_layer.locked
                    tl.opacity = ref_layer.opacity
                    new_frame.layers[i] = tl
            new_frame.active_layer_index = ref.active_layer_index
        self._frames.insert(after_index + 1, new_frame)

    def duplicate_frame(self, index: int) -> None:
        if 0 <= index < len(self._frames):
            copy = self._frames[index].copy(linked=False)
            self._frames.insert(index + 1, copy)

    def duplicate_frame_linked(self, index: int) -> None:
        if 0 <= index < len(self._frames):
            copy = self._frames[index].copy(linked=True)
            self._frames.insert(index + 1, copy)

    def remove_frame(self, index: int) -> None:
        if len(self._frames) > 1 and 0 <= index < len(self._frames):
            self._frames.pop(index)
            if self._current_index >= len(self._frames):
                self._current_index = len(self._frames) - 1

    def move_frame(self, from_idx: int, to_idx: int) -> None:
        if (0 <= from_idx < len(self._frames) and
                0 <= to_idx < len(self._frames)):
            frame = self._frames.pop(from_idx)
            self._frames.insert(to_idx, frame)

    def is_linked(self, frame_idx: int, layer_idx: int) -> bool:
        """Check if a cel is linked (shared) with any other frame."""
        target_id = self._frames[frame_idx].layers[layer_idx].cel_id
        for i, frame in enumerate(self._frames):
            if i == frame_idx:
                continue
            if layer_idx < len(frame.layers):
                if frame.layers[layer_idx].cel_id == target_id:
                    return True
        return False

    def add_layer_to_all(self, name: str | None = None) -> None:
        """Add a new layer to ALL frames (global layer structure)."""
        if not self._frames:
            return
        if name is None:
            name = f"Layer {len(self._frames[0].layers) + 1}"
        for frame in self._frames:
            layer = Layer(name, self.width, self.height,
                          color_mode=self.color_mode, palette=self.palette_ref)
            frame.layers.append(layer)
            frame.active_layer_index = len(frame.layers) - 1

    def add_group_to_all(self, name: str, depth: int = 0):
        """Add a group layer to all frames."""
        for frame in self._frames:
            group = Layer(name, self.width, self.height)
            group.is_group = True
            group.depth = depth
            frame.layers.append(group)
            frame.active_layer_index = len(frame.layers) - 1

    def set_layer_depth_all(self, idx: int, depth: int) -> None:
        """Set layer depth at given index in ALL frames."""
        self.sync_layers()
        for frame in self._frames:
            if 0 <= idx < len(frame.layers):
                frame.layers[idx].depth = depth

    def move_layer_into_group(self, layer_idx: int, group_idx: int) -> bool:
        """Move a layer into a group across all frames.

        Positions the layer at the end of the group's existing children.
        Sets depth=1. Returns False if the operation is invalid.
        """
        if not self._frames:
            return False
        self.sync_layers()
        ref = self._frames[0]
        if not (0 <= layer_idx < len(ref.layers) and
                0 <= group_idx < len(ref.layers)):
            return False
        if ref.layers[layer_idx].is_group:
            return False
        if not ref.layers[group_idx].is_group:
            return False

        for frame in self._frames:
            layer = frame.layers.pop(layer_idx)
            layer.depth = 1
            # Find where the group ended up after pop
            actual_group = group_idx if layer_idx > group_idx else group_idx - 1
            # Find insertion point: right after group's last existing child
            insert_at = actual_group + 1
            while (insert_at < len(frame.layers) and
                   not frame.layers[insert_at].is_group and
                   frame.layers[insert_at].depth > 0):
                insert_at += 1
            frame.layers.insert(insert_at, layer)
            frame.active_layer_index = insert_at
        return True

    def move_layer_out_of_group(self, layer_idx: int) -> bool:
        """Remove a layer from its group across all frames.

        Sets depth=0 and moves the layer above the parent group.
        Returns False if the layer is already at root level.
        """
        if not self._frames:
            return False
        self.sync_layers()
        ref = self._frames[0]
        if not (0 <= layer_idx < len(ref.layers)):
            return False
        if ref.layers[layer_idx].depth == 0:
            return False
        has_parent = any(ref.layers[j].is_group for j in range(layer_idx))
        if not has_parent:
            return False

        for frame in self._frames:
            layer = frame.layers.pop(layer_idx)
            layer.depth = 0
            # Find the parent group: scan backwards for the nearest group
            parent_idx = layer_idx - 1
            while parent_idx >= 0 and not frame.layers[parent_idx].is_group:
                parent_idx -= 1
            if parent_idx < 0:
                frame.layers.append(layer)
                frame.active_layer_index = len(frame.layers) - 1
                continue
            # Place above the group: find the end of the group's children
            insert_at = parent_idx + 1
            while (insert_at < len(frame.layers) and
                   not frame.layers[insert_at].is_group and
                   frame.layers[insert_at].depth > frame.layers[parent_idx].depth):
                insert_at += 1
            frame.layers.insert(insert_at, layer)
            frame.active_layer_index = insert_at
        return True

    def move_layer_in_all(self, from_idx: int, to_idx: int) -> None:
        """Move a layer from one index to another in ALL frames."""
        for frame in self._frames:
            if (0 <= from_idx < len(frame.layers) and
                    0 <= to_idx < len(frame.layers)):
                frame.move_layer(from_idx, to_idx)
                frame.active_layer_index = to_idx

    def remove_layer_from_all(self, index: int) -> None:
        """Remove a layer at given index from ALL frames."""
        for frame in self._frames:
            if len(frame.layers) > 1 and 0 <= index < len(frame.layers):
                frame.layers.pop(index)
                if frame.active_layer_index >= len(frame.layers):
                    frame.active_layer_index = len(frame.layers) - 1

    def duplicate_layer_in_all(self, index: int) -> None:
        """Duplicate a layer at given index in ALL frames."""
        for frame in self._frames:
            if 0 <= index < len(frame.layers):
                copy = frame.layers[index].copy()
                frame.layers.insert(index + 1, copy)
                frame.active_layer_index = index + 1

    def merge_down_in_all(self, index: int) -> None:
        """Merge layer down in ALL frames."""
        for frame in self._frames:
            if index > 0 and index < len(frame.layers):
                above = frame.layers[index]
                below = frame.layers[index - 1]
                # Auto-unlink the below layer to prevent cross-frame propagation
                if hasattr(below, 'unlink'):
                    below.unlink()
                # Rasterize tilemap layers before merging
                if hasattr(above, 'is_tilemap') and above.is_tilemap():
                    from src.tilemap import TilemapLayer
                    above_layer = Layer(above.name, self.width, self.height)
                    above_layer.pixels._pixels = above.render_to_pixels()
                    above_layer.visible = above.visible
                    above_layer.opacity = above.opacity
                    above_layer.blend_mode = above.blend_mode
                elif getattr(above, 'color_mode', 'rgba') == "indexed":
                    above_layer = Layer(above.name, self.width, self.height)
                    above_layer.pixels._pixels = above.pixels.to_rgba()
                    above_layer.visible = above.visible
                    above_layer.opacity = above.opacity
                    above_layer.blend_mode = above.blend_mode
                else:
                    above_layer = above
                if hasattr(below, 'is_tilemap') and below.is_tilemap():
                    from src.tilemap import TilemapLayer
                    below_layer = Layer(below.name, self.width, self.height)
                    below_layer.pixels._pixels = below.render_to_pixels()
                    below_layer.visible = below.visible
                    below_layer.opacity = below.opacity
                    below_layer.blend_mode = below.blend_mode
                elif getattr(below, 'color_mode', 'rgba') == "indexed":
                    below_layer = Layer(below.name, self.width, self.height)
                    below_layer.pixels._pixels = below.pixels.to_rgba()
                    below_layer.visible = below.visible
                    below_layer.opacity = below.opacity
                    below_layer.blend_mode = below.blend_mode
                else:
                    below_layer = below
                merged = flatten_layers([below_layer, above_layer], self.width, self.height)
                if hasattr(below, 'is_tilemap') and below.is_tilemap():
                    plain = Layer(below.name, self.width, self.height)
                    plain.pixels._pixels = merged._pixels.copy()
                    plain.visible = below.visible
                    plain.opacity = below.opacity
                    plain.blend_mode = below.blend_mode
                    frame.layers[index - 1] = plain
                elif getattr(below, 'color_mode', 'rgba') == "indexed":
                    for y in range(self.height):
                        for x in range(self.width):
                            color = merged.get_pixel(x, y)
                            if color:
                                below.pixels.set_pixel(x, y, color)
                else:
                    below.pixels._pixels = merged._pixels.copy()
                frame.layers.pop(index)
                frame.active_layer_index = index - 1

    def set_active_layer_all(self, index: int) -> None:
        """Set active layer index in ALL frames."""
        for frame in self._frames:
            if 0 <= index < len(frame.layers):
                frame.active_layer_index = index

    def add_tag(self, name: str, color: str, start: int, end: int) -> None:
        self.tags.append({"name": name, "color": color, "start": start, "end": end})

    def remove_tag(self, index: int) -> None:
        if 0 <= index < len(self.tags):
            self.tags.pop(index)

    def get_tags_for_frame(self, frame_index: int) -> list[dict]:
        return [t for t in self.tags if t["start"] <= frame_index <= t["end"]]

    def export_gif(self, filepath: str, fps: int = 10, scale: int = 1,
                   duration_ms: int | None = None,
                   frame_start: int | None = None,
                   frame_end: int | None = None) -> None:
        from PIL import Image
        start = frame_start if frame_start is not None else 0
        end = frame_end if frame_end is not None else len(self._frames) - 1
        frames: list[Image.Image] = []
        for i in range(start, end + 1):
            frame_obj = self._frames[i]
            grid = frame_obj.flatten()
            img = grid.to_pil_image()
            if scale > 1:
                new_size = (img.width * scale, img.height * scale)
                img = img.resize(new_size, Image.NEAREST)
            alpha = img.split()[3]
            p_img = img.convert("RGB").convert("P", palette=Image.ADAPTIVE,
                                                colors=255)
            lut = [255] * 129 + [0] * 127
            transparency_mask = alpha.point(lut, "L")
            p_img.paste(255, transparency_mask)
            frames.append(p_img)

        if not frames:
            return
        if duration_ms is not None:
            durations = duration_ms
        else:
            durations = [self._frames[i].duration_ms for i in range(start, end + 1)]
        frames[0].save(
            filepath, save_all=True, append_images=frames[1:],
            duration=durations, loop=0, transparency=255, disposal=2
        )
