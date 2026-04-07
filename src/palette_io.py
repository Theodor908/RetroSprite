"""Palette file import/export — GPL, PAL, HEX, ASE formats."""
from __future__ import annotations
import struct
import os


def load_palette(path: str) -> list[tuple[int, int, int, int]]:
    """Auto-detect format from extension and load palette colors."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".gpl":
        return _load_gpl(path)
    elif ext == ".pal":
        return _load_pal(path)
    elif ext == ".hex":
        return _load_hex(path)
    elif ext == ".ase":
        return _load_ase(path)
    else:
        raise ValueError(f"Unsupported palette format: {ext}")


def save_palette(path: str, colors: list[tuple[int, int, int, int]],
                 name: str = "Untitled") -> None:
    """Save palette in format matching extension."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".gpl":
        _save_gpl(path, colors, name)
    elif ext == ".pal":
        _save_pal(path, colors)
    elif ext == ".hex":
        _save_hex(path, colors)
    elif ext == ".ase":
        _save_ase(path, colors, name)
    else:
        raise ValueError(f"Unsupported palette format: {ext}")


# --- GPL (GIMP Palette) ---

def _load_gpl(path: str) -> list[tuple[int, int, int, int]]:
    colors = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("GIMP") or line.startswith("Name:") or line.startswith("Columns:"):
                continue
            parts = line.split()
            if len(parts) >= 3:
                try:
                    r, g, b = int(parts[0]), int(parts[1]), int(parts[2])
                    colors.append((r, g, b, 255))
                except ValueError:
                    continue
    return colors


def _save_gpl(path: str, colors: list[tuple], name: str) -> None:
    with open(path, "w") as f:
        f.write(f"GIMP Palette\nName: {name}\n#\n")
        for i, c in enumerate(colors):
            f.write(f"{c[0]:3d} {c[1]:3d} {c[2]:3d}\tcolor_{i}\n")


# --- PAL (JASC-PAL) ---

def _load_pal(path: str) -> list[tuple[int, int, int, int]]:
    colors = []
    with open(path, "r") as f:
        lines = f.read().strip().split("\n")
    if len(lines) < 3:
        return colors
    for line in lines[3:]:
        parts = line.strip().split()
        if len(parts) >= 3:
            try:
                r, g, b = int(parts[0]), int(parts[1]), int(parts[2])
                colors.append((r, g, b, 255))
            except ValueError:
                continue
    return colors


def _save_pal(path: str, colors: list[tuple]) -> None:
    with open(path, "w") as f:
        f.write("JASC-PAL\n0100\n")
        f.write(f"{len(colors)}\n")
        for c in colors:
            f.write(f"{c[0]} {c[1]} {c[2]}\n")


# --- HEX (Lospec) ---

def _load_hex(path: str) -> list[tuple[int, int, int, int]]:
    colors = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip().lstrip("#")
            if len(line) >= 6:
                try:
                    r = int(line[0:2], 16)
                    g = int(line[2:4], 16)
                    b = int(line[4:6], 16)
                    colors.append((r, g, b, 255))
                except ValueError:
                    continue
    return colors


def _save_hex(path: str, colors: list[tuple]) -> None:
    with open(path, "w") as f:
        for c in colors:
            f.write(f"{c[0]:02x}{c[1]:02x}{c[2]:02x}\n")


# --- ASE (Adobe Swatch Exchange) ---

def _load_ase(path: str) -> list[tuple[int, int, int, int]]:
    colors = []
    with open(path, "rb") as f:
        magic = f.read(4)
        if magic != b"ASEF":
            raise ValueError("Not a valid ASE file")
        _version = struct.unpack(">HH", f.read(4))
        block_count = struct.unpack(">I", f.read(4))[0]
        for _ in range(block_count):
            block_type = struct.unpack(">H", f.read(2))[0]
            block_size = struct.unpack(">I", f.read(4))[0]
            block_data = f.read(block_size)
            if block_type == 0x0001:  # Color entry
                offset = 0
                name_len = struct.unpack(">H", block_data[offset:offset+2])[0]
                offset += 2 + name_len * 2  # UTF-16 chars
                model = block_data[offset:offset+4]
                offset += 4
                if model == b"RGB ":
                    rf, gf, bf = struct.unpack(">fff", block_data[offset:offset+12])
                    r = max(0, min(255, round(rf * 255)))
                    g = max(0, min(255, round(gf * 255)))
                    b = max(0, min(255, round(bf * 255)))
                    colors.append((r, g, b, 255))
    return colors


def _save_ase(path: str, colors: list[tuple], name: str) -> None:
    blocks = []
    for i, c in enumerate(colors):
        color_name = f"color_{i}"
        name_encoded = color_name.encode("utf-16-be") + b"\x00\x00"
        name_len = len(color_name) + 1
        rf = c[0] / 255.0
        gf = c[1] / 255.0
        bf = c[2] / 255.0
        block_data = struct.pack(">H", name_len)
        block_data += name_encoded
        block_data += b"RGB "
        block_data += struct.pack(">fff", rf, gf, bf)
        block_data += struct.pack(">H", 0)  # color type: global
        blocks.append(block_data)

    with open(path, "wb") as f:
        f.write(b"ASEF")
        f.write(struct.pack(">HH", 1, 0))
        f.write(struct.pack(">I", len(blocks)))
        for block_data in blocks:
            f.write(struct.pack(">H", 0x0001))
            f.write(struct.pack(">I", len(block_data)))
            f.write(block_data)
