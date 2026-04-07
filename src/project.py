"""Project save/load for RetroSprite (.retro JSON format)."""
from __future__ import annotations
import json
import base64
import io
import numpy as np
from PIL import Image
from src.pixel_data import PixelGrid, IndexedPixelGrid
from src.animation import AnimationTimeline, Frame
from src.layer import Layer
from src.palette import Palette
from src.reference_image import ReferenceImage


def save_project(filepath: str, timeline: AnimationTimeline,
                 palette: Palette, tool_settings: dict | None = None,
                 reference_image=None, grid_settings=None,
                 symmetry_axis_x: int | None = None,
                 symmetry_axis_y: int | None = None) -> None:
    # --- Serialize tilesets ---
    tilesets_data = {}
    for name, ts in getattr(timeline, 'tilesets', {}).items():
        tiles_encoded = []
        for tile in ts.tiles:
            img = Image.fromarray(tile, "RGBA")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            tiles_encoded.append(base64.b64encode(buf.getvalue()).decode("ascii"))
        tilesets_data[name] = {
            "tile_width": ts.tile_width,
            "tile_height": ts.tile_height,
            "tiles": tiles_encoded,
        }

    frames_data = []
    # Track cel_ids already serialized for deduplication (linked cels)
    serialized_cel_ids = set()
    for i in range(timeline.frame_count):
        frame_obj = timeline.get_frame_obj(i)
        layers_data = []
        for layer in frame_obj.layers:
            cel_id = getattr(layer, 'cel_id', None)

            # --- Tilemap layer serialization ---
            if hasattr(layer, 'is_tilemap') and layer.is_tilemap():
                grid_data = [[ref.pack() for ref in row] for row in layer.grid]
                layer_dict = {
                    "name": layer.name,
                    "type": "tilemap",
                    "tileset_name": layer.tileset.name,
                    "grid": grid_data,
                    "visible": layer.visible,
                    "opacity": layer.opacity,
                    "blend_mode": layer.blend_mode,
                    "locked": layer.locked,
                    "depth": layer.depth,
                    "is_group": False,
                    "effects": [fx.to_dict() for fx in getattr(layer, 'effects', [])],
                    "edit_mode": layer.edit_mode,
                    "pixel_sub_mode": layer.pixel_sub_mode,
                    "clipping": getattr(layer, 'clipping', False),
                }
                if cel_id:
                    layer_dict["cel_id"] = cel_id
                layers_data.append(layer_dict)
                if cel_id:
                    serialized_cel_ids.add(cel_id)
                continue  # skip normal pixel serialization

            # Check if this cel_id was already serialized (linked cel)
            if cel_id and cel_id in serialized_cel_ids:
                layers_data.append({
                    "name": layer.name,
                    "cel_id": cel_id,
                    "cel_ref": cel_id,
                    "visible": layer.visible,
                    "opacity": layer.opacity,
                    "blend_mode": layer.blend_mode,
                    "locked": layer.locked,
                    "depth": layer.depth,
                    "is_group": getattr(layer, 'is_group', False),
                    "effects": [fx.to_dict() for fx in getattr(layer, 'effects', [])],
                    "clipping": getattr(layer, 'clipping', False),
                })
                continue

            # --- Indexed layer serialization ---
            if getattr(layer, 'color_mode', 'rgba') == "indexed":
                layer_dict = {
                    "name": layer.name,
                    "color_mode": "indexed",
                    "indices": layer.pixels.to_flat_indices(),
                    "visible": layer.visible,
                    "opacity": layer.opacity,
                    "blend_mode": layer.blend_mode,
                    "locked": layer.locked,
                    "depth": layer.depth,
                    "is_group": getattr(layer, 'is_group', False),
                    "effects": [fx.to_dict() for fx in getattr(layer, 'effects', [])],
                    "clipping": getattr(layer, 'clipping', False),
                }
                if cel_id:
                    layer_dict["cel_id"] = cel_id
                    serialized_cel_ids.add(cel_id)
                layers_data.append(layer_dict)
                continue  # skip normal pixel serialization

            # --- Normal pixel layer serialization ---
            pixels = layer.pixels.to_flat_list()
            layer_dict = {
                "name": layer.name,
                "visible": layer.visible,
                "opacity": layer.opacity,
                "blend_mode": layer.blend_mode,
                "locked": layer.locked,
                "depth": layer.depth,
                "is_group": getattr(layer, 'is_group', False),
                "effects": [fx.to_dict() for fx in getattr(layer, 'effects', [])],
                "pixels": [list(p) for p in pixels],
                "clipping": getattr(layer, 'clipping', False),
            }
            if cel_id:
                layer_dict["cel_id"] = cel_id
                serialized_cel_ids.add(cel_id)
            layers_data.append(layer_dict)
        frames_data.append({
            "name": frame_obj.name,
            "layers": layers_data,
            "active_layer": frame_obj.active_layer_index,
        })

    # --- Serialize reference image ---
    ref_data = None
    if reference_image is not None:
        buf = io.BytesIO()
        reference_image.image.save(buf, format="PNG")
        ref_data = {
            "data": base64.b64encode(buf.getvalue()).decode("ascii"),
            "x": reference_image.x,
            "y": reference_image.y,
            "scale": reference_image.scale,
            "opacity": reference_image.opacity,
            "visible": reference_image.visible,
            "path": reference_image.path,
        }

    has_ref = ref_data is not None
    has_grid = grid_settings is not None
    if has_grid:
        version = 7
    elif has_ref:
        version = 6
    elif tool_settings:
        version = 5
    elif getattr(timeline, 'color_mode', 'rgba') == 'indexed':
        version = 4
    else:
        version = 3

    project = {
        "version": version,
        "color_mode": getattr(timeline, 'color_mode', 'rgba'),
        "width": timeline.width,
        "height": timeline.height,
        "fps": timeline.fps,
        "current_frame": timeline.current_index,
        "palette_name": palette.name,
        "palette_colors": [list(c) for c in palette.colors],
        "selected_color_index": palette.selected_index,
        "tilesets": tilesets_data,
        "frames": frames_data,
        "tags": timeline.tags,
        "tool_settings": tool_settings or {},
    }
    if ref_data is not None:
        project["reference_image"] = ref_data
    if grid_settings is not None:
        project["grid"] = grid_settings
    if symmetry_axis_x is not None:
        project["symmetry_axis_x"] = symmetry_axis_x
    if symmetry_axis_y is not None:
        project["symmetry_axis_y"] = symmetry_axis_y

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(project, f, ensure_ascii=True)


def load_project(filepath: str) -> tuple[AnimationTimeline, Palette, dict, 'ReferenceImage | None', dict | None]:
    with open(filepath, "rb") as f:
        project = json.loads(f.read())

    w = project["width"]
    h = project["height"]
    version = project.get("version", 1)

    timeline = AnimationTimeline(w, h)
    timeline.fps = project.get("fps", 10)

    # --- Load tilesets first ---
    tilesets_loaded = {}
    for name, ts_data in project.get("tilesets", {}).items():
        from src.tilemap import Tileset
        ts = Tileset(name, ts_data["tile_width"], ts_data["tile_height"])
        ts.tiles = []  # clear default empty tile, we'll load all tiles
        for encoded in ts_data["tiles"]:
            tile_bytes = base64.b64decode(encoded)
            tile_img = Image.open(io.BytesIO(tile_bytes)).convert("RGBA")
            ts.tiles.append(np.array(tile_img, dtype=np.uint8))
        tilesets_loaded[name] = ts
    timeline.tilesets = tilesets_loaded

    # --- Load palette BEFORE frames (indexed layers need it) ---
    palette_name = project.get("palette_name", "Pico-8")
    palette = Palette(palette_name)
    if "palette_colors" in project:
        palette.colors = [tuple(c) for c in project["palette_colors"]]
    if "selected_color_index" in project:
        palette.select(project["selected_color_index"])

    # --- Set timeline color mode ---
    timeline.color_mode = project.get("color_mode", "rgba")
    if timeline.color_mode == "indexed":
        timeline.palette_ref = palette.colors

    frames_data = project["frames"]
    timeline._frames.clear()

    # Map cel_id -> PixelGrid for linked cel reconstruction
    cel_pixel_map: dict[str, object] = {}

    if version >= 2:
        for frame_data in frames_data:
            frame = Frame(w, h, name=frame_data.get("name", ""))
            frame.layers.clear()
            for layer_data in frame_data["layers"]:
                cel_id = layer_data.get("cel_id", None)
                cel_ref = layer_data.get("cel_ref", None)

                # --- Tilemap layer loading ---
                if layer_data.get("type") == "tilemap":
                    from src.tilemap import TilemapLayer, TileRef
                    ts_name = layer_data["tileset_name"]
                    ts = timeline.tilesets.get(ts_name)
                    if ts:
                        layer = TilemapLayer(layer_data["name"], w, h, ts)
                        layer.grid = [
                            [TileRef.unpack(v) for v in row]
                            for row in layer_data["grid"]
                        ]
                        layer.edit_mode = layer_data.get("edit_mode", "pixels")
                        layer.pixel_sub_mode = layer_data.get("pixel_sub_mode", "auto")
                    else:
                        layer = Layer(layer_data["name"], w, h)  # fallback
                    layer.visible = layer_data.get("visible", True)
                    layer.opacity = layer_data.get("opacity", 1.0)
                    layer.blend_mode = layer_data.get("blend_mode", "normal")
                    layer.locked = layer_data.get("locked", False)
                    layer.depth = layer_data.get("depth", 0)
                    layer.is_group = layer_data.get("is_group", False)
                    from src.effects import LayerEffect
                    layer.effects = [LayerEffect.from_dict(e) for e in layer_data.get("effects", [])]
                    layer.clipping = layer_data.get("clipping", False)
                    if cel_id:
                        layer.cel_id = cel_id
                        if cel_id not in cel_pixel_map:
                            cel_pixel_map[cel_id] = layer.pixels

                # --- Linked cel reference (reuse pixel data) ---
                elif cel_ref and cel_ref in cel_pixel_map:
                    layer = Layer(layer_data["name"], w, h)
                    layer.pixels = cel_pixel_map[cel_ref]
                    layer.cel_id = cel_ref
                    layer.visible = layer_data.get("visible", True)
                    layer.opacity = layer_data.get("opacity", 1.0)
                    layer.blend_mode = layer_data.get("blend_mode", "normal")
                    layer.locked = layer_data.get("locked", False)
                    layer.depth = layer_data.get("depth", 0)
                    layer.is_group = layer_data.get("is_group", False)
                    from src.effects import LayerEffect
                    layer.effects = [LayerEffect.from_dict(e) for e in layer_data.get("effects", [])]
                    layer.clipping = layer_data.get("clipping", False)

                else:
                    # Check if indexed layer
                    if layer_data.get("color_mode") == "indexed":
                        layer = Layer(layer_data["name"], w, h, color_mode="indexed",
                                      palette=palette.colors)
                        layer.pixels = IndexedPixelGrid.from_flat_indices(
                            w, h, layer_data["indices"], palette.colors)
                    else:
                        # --- Normal pixel layer loading ---
                        layer = Layer(layer_data["name"], w, h)
                        if "pixels" in layer_data:
                            for i, rgba in enumerate(layer_data["pixels"]):
                                x = i % w
                                y = i // w
                                layer.pixels.set_pixel(x, y, tuple(rgba))
                    # Common attributes for both indexed and rgba:
                    layer.visible = layer_data.get("visible", True)
                    layer.opacity = layer_data.get("opacity", 1.0)
                    layer.blend_mode = layer_data.get("blend_mode", "normal")
                    layer.locked = layer_data.get("locked", False)
                    layer.depth = layer_data.get("depth", 0)
                    layer.is_group = layer_data.get("is_group", False)
                    from src.effects import LayerEffect
                    layer.effects = [LayerEffect.from_dict(e) for e in layer_data.get("effects", [])]
                    layer.clipping = layer_data.get("clipping", False)
                    # Assign cel_id if present, otherwise layer keeps its auto-generated one
                    if cel_id:
                        layer.cel_id = cel_id
                        cel_pixel_map[cel_id] = layer.pixels
                frame.layers.append(layer)
            frame.active_layer_index = frame_data.get("active_layer", 0)
            timeline._frames.append(frame)
        timeline.tags = project.get("tags", [])
    else:
        # v1 format: flat pixel lists per frame
        for flat_pixels in frames_data:
            frame = Frame(w, h)
            for i, rgba in enumerate(flat_pixels):
                x = i % w
                y = i // w
                frame.layers[0].pixels.set_pixel(x, y, tuple(rgba))
            timeline._frames.append(frame)

    current = project.get("current_frame", 0)
    timeline.set_current(current)

    # --- Deserialize reference image ---
    ref_data = project.get("reference_image")
    loaded_ref = None
    if ref_data is not None:
        ref_bytes = base64.b64decode(ref_data["data"])
        ref_img = Image.open(io.BytesIO(ref_bytes)).convert("RGBA")
        loaded_ref = ReferenceImage(
            image=ref_img,
            x=ref_data.get("x", 0),
            y=ref_data.get("y", 0),
            scale=ref_data.get("scale", 1.0),
            opacity=ref_data.get("opacity", 0.3),
            visible=ref_data.get("visible", True),
            path=ref_data.get("path", ""),
        )

    tool_settings_data = project.get("tool_settings", {})
    grid_data = project.get("grid", None)
    if grid_data is None:
        sax = project.get("symmetry_axis_x")
        say = project.get("symmetry_axis_y")
        if sax is not None or say is not None:
            grid_data = {"symmetry_axis_x": sax, "symmetry_axis_y": say}
    elif isinstance(grid_data, dict):
        grid_data["symmetry_axis_x"] = project.get("symmetry_axis_x")
        grid_data["symmetry_axis_y"] = project.get("symmetry_axis_y")
    return timeline, palette, tool_settings_data, loaded_ref, grid_data
