"""Aseprite (.ase/.aseprite) file import."""
from __future__ import annotations
import struct
import zlib
import numpy as np
from src.pixel_data import PixelGrid
from src.animation import AnimationTimeline, Frame
from src.layer import Layer
from src.palette import Palette


ASE_BLEND_MAP = {
    0: "normal", 1: "multiply", 2: "screen", 3: "overlay",
    4: "darken", 5: "lighten", 10: "difference",
    16: "addition", 17: "subtract",
}


def load_aseprite(path: str) -> tuple[AnimationTimeline, Palette]:
    """Parse .ase/.aseprite file and return (timeline, palette)."""
    with open(path, "rb") as f:
        data = f.read()

    pos = 0

    def read(fmt, offset=None):
        nonlocal pos
        if offset is not None:
            pos = offset
        size = struct.calcsize(fmt)
        val = struct.unpack_from(fmt, data, pos)
        pos += size
        return val if len(val) > 1 else val[0]

    _file_size = read("<I")
    magic = read("<H")
    if magic != 0xA5E0:
        raise ValueError("Not a valid Aseprite file")
    num_frames = read("<H")
    width = read("<H")
    height = read("<H")
    color_depth = read("<H")
    _flags = read("<I")
    _speed = read("<H")
    pos = 28
    _palette_entry = read("<I")
    pos = 128

    bpp = color_depth // 8

    layer_infos = []
    palette_colors = []
    frames_data = []
    cel_cache = {}

    for frame_idx in range(num_frames):
        frame_start = pos
        frame_size = read("<I")
        _frame_magic = read("<H")
        old_chunks = read("<H")
        duration_ms = read("<H")
        pos += 2
        new_chunks = read("<I")
        chunk_count = new_chunks if new_chunks != 0 else old_chunks

        cels = []

        for _ in range(chunk_count):
            chunk_size = read("<I")
            chunk_type = read("<H")
            chunk_data_start = pos
            chunk_data_size = chunk_size - 6

            if chunk_type == 0x2004:  # Layer
                flags = struct.unpack_from("<H", data, pos)[0]
                layer_type = struct.unpack_from("<H", data, pos + 2)[0]
                blend_mode = struct.unpack_from("<H", data, pos + 10)[0]
                opacity = struct.unpack_from("<B", data, pos + 12)[0]
                name_pos = pos + 16
                name_len = struct.unpack_from("<H", data, name_pos)[0]
                name = data[name_pos + 2:name_pos + 2 + name_len].decode("utf-8", errors="replace")
                layer_infos.append({
                    "name": name,
                    "flags": flags,
                    "blend": ASE_BLEND_MAP.get(blend_mode, "normal"),
                    "opacity": opacity / 255.0,
                    "visible": bool(flags & 1),
                    "type": layer_type,
                })

            elif chunk_type == 0x2005:  # Cel
                layer_index = struct.unpack_from("<H", data, pos)[0]
                x_pos = struct.unpack_from("<h", data, pos + 2)[0]
                y_pos = struct.unpack_from("<h", data, pos + 4)[0]
                cel_opacity = struct.unpack_from("<B", data, pos + 6)[0]
                cel_type = struct.unpack_from("<H", data, pos + 7)[0]
                cel_header_size = 16

                if cel_type == 0:  # Raw
                    cel_w = struct.unpack_from("<H", data, pos + cel_header_size)[0]
                    cel_h = struct.unpack_from("<H", data, pos + cel_header_size + 2)[0]
                    pixel_start = pos + cel_header_size + 4
                    raw = data[pixel_start:pixel_start + cel_w * cel_h * bpp]
                    pixels = _decode_pixels(raw, cel_w, cel_h, color_depth, palette_colors)
                    canvas = _place_cel(pixels, x_pos, y_pos, cel_w, cel_h, width, height)
                    cels.append((layer_index, canvas))
                    cel_cache[(frame_idx, layer_index)] = canvas

                elif cel_type == 1:  # Linked
                    linked_frame = struct.unpack_from("<H", data, pos + cel_header_size)[0]
                    cached = cel_cache.get((linked_frame, layer_index))
                    if cached is not None:
                        cels.append((layer_index, cached.copy()))

                elif cel_type == 2:  # Compressed
                    cel_w = struct.unpack_from("<H", data, pos + cel_header_size)[0]
                    cel_h = struct.unpack_from("<H", data, pos + cel_header_size + 2)[0]
                    compressed_start = pos + cel_header_size + 4
                    compressed_data = data[compressed_start:chunk_data_start + chunk_data_size]
                    raw = zlib.decompress(compressed_data)
                    pixels = _decode_pixels(raw, cel_w, cel_h, color_depth, palette_colors)
                    canvas = _place_cel(pixels, x_pos, y_pos, cel_w, cel_h, width, height)
                    cels.append((layer_index, canvas))
                    cel_cache[(frame_idx, layer_index)] = canvas

            elif chunk_type == 0x2019:  # Palette (new)
                pal_size = struct.unpack_from("<I", data, pos)[0]
                first_idx = struct.unpack_from("<I", data, pos + 4)[0]
                last_idx = struct.unpack_from("<I", data, pos + 8)[0]
                p = pos + 20
                while len(palette_colors) <= last_idx:
                    palette_colors.append((0, 0, 0, 255))
                for idx in range(first_idx, last_idx + 1):
                    entry_flags = struct.unpack_from("<H", data, p)[0]
                    r = data[p + 2]
                    g = data[p + 3]
                    b = data[p + 4]
                    a = data[p + 5]
                    palette_colors[idx] = (r, g, b, a)
                    p += 6
                    if entry_flags & 1:
                        name_len = struct.unpack_from("<H", data, p)[0]
                        p += 2 + name_len

            elif chunk_type == 0x0004:  # Old palette
                packets = struct.unpack_from("<H", data, pos)[0]
                p = pos + 2
                idx = 0
                for _ in range(packets):
                    skip = data[p]
                    count = data[p + 1]
                    if count == 0:
                        count = 256
                    p += 2
                    idx += skip
                    for _ in range(count):
                        r, g, b = data[p], data[p + 1], data[p + 2]
                        while len(palette_colors) <= idx:
                            palette_colors.append((0, 0, 0, 255))
                        palette_colors[idx] = (r, g, b, 255)
                        p += 3
                        idx += 1

            pos = chunk_data_start + chunk_data_size

        frames_data.append((cels, duration_ms))
        pos = frame_start + frame_size

    # Build timeline
    timeline = AnimationTimeline(width, height)
    timeline._frames.clear()

    normal_layer_indices = [i for i, info in enumerate(layer_infos)
                           if info["type"] == 0]

    if not normal_layer_indices:
        normal_layer_indices = [0]
        layer_infos = [{"name": "Layer 1", "flags": 1, "blend": "normal",
                        "opacity": 1.0, "visible": True, "type": 0}]

    for frame_idx, (cels, duration_ms) in enumerate(frames_data):
        frame = Frame(width, height, name=f"Frame {frame_idx + 1}")
        frame.layers.clear()
        frame.duration_ms = duration_ms

        cel_map = {layer_idx: pixels for layer_idx, pixels in cels}

        for li in normal_layer_indices:
            info = layer_infos[li] if li < len(layer_infos) else {
                "name": f"Layer {li}", "blend": "normal", "opacity": 1.0, "visible": True}
            layer = Layer(info["name"], width, height)
            layer.blend_mode = info["blend"]
            layer.opacity = info["opacity"]
            layer.visible = info["visible"]

            if li in cel_map:
                layer.pixels._pixels = cel_map[li]

            frame.layers.append(layer)

        if not frame.layers:
            frame.layers.append(Layer("Layer 1", width, height))
        frame.active_layer_index = 0
        timeline._frames.append(frame)

    palette = Palette("Imported")
    if palette_colors:
        palette.colors = list(palette_colors)
    palette.selected_index = 0

    timeline.tags = _parse_tags(data)

    return timeline, palette


def _decode_pixels(raw: bytes, w: int, h: int, depth: int,
                   palette: list) -> np.ndarray:
    if depth == 32:
        arr = np.frombuffer(raw, dtype=np.uint8).reshape(h, w, 4).copy()
    elif depth == 16:
        arr = np.frombuffer(raw, dtype=np.uint8).reshape(h, w, 2)
        rgba = np.zeros((h, w, 4), dtype=np.uint8)
        rgba[:, :, 0] = arr[:, :, 0]
        rgba[:, :, 1] = arr[:, :, 0]
        rgba[:, :, 2] = arr[:, :, 0]
        rgba[:, :, 3] = arr[:, :, 1]
        arr = rgba
    elif depth == 8:
        indices = np.frombuffer(raw, dtype=np.uint8).reshape(h, w)
        rgba = np.zeros((h, w, 4), dtype=np.uint8)
        for i, color in enumerate(palette):
            mask = indices == i
            rgba[mask] = color
        arr = rgba
    else:
        arr = np.zeros((h, w, 4), dtype=np.uint8)
    return arr


def _place_cel(pixels: np.ndarray, x: int, y: int, cel_w: int, cel_h: int,
               canvas_w: int, canvas_h: int) -> np.ndarray:
    canvas = np.zeros((canvas_h, canvas_w, 4), dtype=np.uint8)
    src_x0 = max(0, -x)
    src_y0 = max(0, -y)
    dst_x0 = max(0, x)
    dst_y0 = max(0, y)
    copy_w = min(cel_w - src_x0, canvas_w - dst_x0)
    copy_h = min(cel_h - src_y0, canvas_h - dst_y0)
    if copy_w > 0 and copy_h > 0:
        canvas[dst_y0:dst_y0 + copy_h, dst_x0:dst_x0 + copy_w] = \
            pixels[src_y0:src_y0 + copy_h, src_x0:src_x0 + copy_w]
    return canvas


def _parse_tags(data: bytes) -> list[dict]:
    tags = []
    pos = 128
    file_size = len(data)
    while pos < file_size - 16:
        try:
            frame_size = struct.unpack_from("<I", data, pos)[0]
            magic = struct.unpack_from("<H", data, pos + 4)[0]
            if magic != 0xF1FA:
                break
            old_chunks = struct.unpack_from("<H", data, pos + 6)[0]
            new_chunks = struct.unpack_from("<I", data, pos + 12)[0]
            chunk_count = new_chunks if new_chunks != 0 else old_chunks
            cp = pos + 16
            for _ in range(chunk_count):
                if cp + 6 > file_size:
                    break
                chunk_size = struct.unpack_from("<I", data, cp)[0]
                chunk_type = struct.unpack_from("<H", data, cp + 4)[0]
                if chunk_type == 0x2018:
                    tp = cp + 6
                    num_tags = struct.unpack_from("<H", data, tp)[0]
                    tp += 10
                    for _ in range(num_tags):
                        from_frame = struct.unpack_from("<H", data, tp)[0]
                        to_frame = struct.unpack_from("<H", data, tp + 2)[0]
                        _loop_dir = struct.unpack_from("<B", data, tp + 4)[0]
                        _repeat = struct.unpack_from("<H", data, tp + 5)[0]
                        tp += 17
                        name_len = struct.unpack_from("<H", data, tp)[0]
                        name = data[tp + 2:tp + 2 + name_len].decode("utf-8", errors="replace")
                        tp += 2 + name_len
                        tags.append({"name": name, "start": from_frame, "end": to_frame})
                cp += chunk_size
            pos += frame_size
        except (struct.error, IndexError):
            break
    return tags
