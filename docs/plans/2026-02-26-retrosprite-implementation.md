# RetroSprite Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a retro pixel art creator with image processing, RLE compression, sprite animation, and GIF export.

**Architecture:** Tkinter-based desktop app with modular components. The pixel canvas is a Tkinter Canvas with a 2D numpy-like list of RGBA tuples as the backing data model. Each module (tools, image processing, compression, animation) operates on this pixel data independently. Pillow handles image I/O and processing filters; imageio handles GIF export.

**Tech Stack:** Python 3.12, Tkinter, Pillow, imageio

---

### Task 1: Project Scaffolding & Dependencies

**Files:**
- Create: `main.py`
- Create: `requirements.txt`
- Create: `src/__init__.py`
- Create: `src/ui/__init__.py`
- Create: `assets/` (directory)
- Create: `tests/__init__.py`

**Step 1: Create requirements.txt**

```
Pillow>=9.0
imageio>=2.20
```

**Step 2: Create package structure**

```bash
mkdir -p src/ui assets tests
```

Create empty `__init__.py` files in `src/`, `src/ui/`, and `tests/`.

**Step 3: Create main.py entry point**

```python
"""RetroSprite - Pixel Art Creator & Animator."""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.app import RetroSpriteApp


def main():
    app = RetroSpriteApp()
    app.run()


if __name__ == "__main__":
    main()
```

**Step 4: Install dependencies**

```bash
pip install -r requirements.txt
```

**Step 5: Commit**

```bash
git add .
git commit -m "chore: scaffold project structure and dependencies"
```

---

### Task 2: Core Pixel Data Model

**Files:**
- Create: `src/pixel_data.py`
- Create: `tests/test_pixel_data.py`

This is the heart of the app — a simple 2D grid of color values that every module reads/writes.

**Step 1: Write failing tests**

```python
"""Tests for pixel data model."""
import pytest
from src.pixel_data import PixelGrid


class TestPixelGrid:
    def test_create_with_dimensions(self):
        grid = PixelGrid(16, 16)
        assert grid.width == 16
        assert grid.height == 16

    def test_default_color_is_transparent(self):
        grid = PixelGrid(8, 8)
        assert grid.get_pixel(0, 0) == (0, 0, 0, 0)

    def test_set_and_get_pixel(self):
        grid = PixelGrid(8, 8)
        grid.set_pixel(3, 4, (255, 0, 0, 255))
        assert grid.get_pixel(3, 4) == (255, 0, 0, 255)

    def test_out_of_bounds_returns_none(self):
        grid = PixelGrid(8, 8)
        assert grid.get_pixel(8, 8) is None
        assert grid.get_pixel(-1, 0) is None

    def test_clear(self):
        grid = PixelGrid(8, 8)
        grid.set_pixel(0, 0, (255, 0, 0, 255))
        grid.clear()
        assert grid.get_pixel(0, 0) == (0, 0, 0, 0)

    def test_to_flat_list(self):
        grid = PixelGrid(2, 2)
        grid.set_pixel(0, 0, (255, 0, 0, 255))
        grid.set_pixel(1, 0, (0, 255, 0, 255))
        flat = grid.to_flat_list()
        assert flat[0] == (255, 0, 0, 255)
        assert flat[1] == (0, 255, 0, 255)

    def test_from_pil_image(self):
        from PIL import Image
        img = Image.new("RGBA", (4, 4), (255, 0, 0, 255))
        grid = PixelGrid.from_pil_image(img)
        assert grid.width == 4
        assert grid.height == 4
        assert grid.get_pixel(0, 0) == (255, 0, 0, 255)

    def test_to_pil_image(self):
        grid = PixelGrid(4, 4)
        grid.set_pixel(0, 0, (0, 128, 255, 255))
        img = grid.to_pil_image()
        assert img.size == (4, 4)
        assert img.getpixel((0, 0)) == (0, 128, 255, 255)

    def test_copy(self):
        grid = PixelGrid(4, 4)
        grid.set_pixel(1, 1, (255, 0, 0, 255))
        copy = grid.copy()
        copy.set_pixel(1, 1, (0, 255, 0, 255))
        assert grid.get_pixel(1, 1) == (255, 0, 0, 255)
        assert copy.get_pixel(1, 1) == (0, 255, 0, 255)
```

**Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_pixel_data.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'src.pixel_data'`

**Step 3: Implement PixelGrid**

```python
"""Core pixel data model for RetroSprite."""
from __future__ import annotations
from PIL import Image


class PixelGrid:
    """A 2D grid of RGBA pixel values."""

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self._pixels: list[list[tuple[int, int, int, int]]] = [
            [(0, 0, 0, 0) for _ in range(width)]
            for _ in range(height)
        ]

    def get_pixel(self, x: int, y: int) -> tuple[int, int, int, int] | None:
        if 0 <= x < self.width and 0 <= y < self.height:
            return self._pixels[y][x]
        return None

    def set_pixel(self, x: int, y: int, color: tuple[int, int, int, int]) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            self._pixels[y][x] = color

    def clear(self) -> None:
        for y in range(self.height):
            for x in range(self.width):
                self._pixels[y][x] = (0, 0, 0, 0)

    def to_flat_list(self) -> list[tuple[int, int, int, int]]:
        return [pixel for row in self._pixels for pixel in row]

    def to_pil_image(self) -> Image.Image:
        img = Image.new("RGBA", (self.width, self.height))
        img.putdata(self.to_flat_list())
        return img

    @classmethod
    def from_pil_image(cls, img: Image.Image) -> PixelGrid:
        img = img.convert("RGBA")
        w, h = img.size
        grid = cls(w, h)
        pixels = list(img.getdata())
        for i, pixel in enumerate(pixels):
            x = i % w
            y = i // w
            grid._pixels[y][x] = pixel
        return grid

    def copy(self) -> PixelGrid:
        new_grid = PixelGrid(self.width, self.height)
        for y in range(self.height):
            for x in range(self.width):
                new_grid._pixels[y][x] = self._pixels[y][x]
        return new_grid
```

**Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_pixel_data.py -v
```

Expected: All PASS

**Step 5: Commit**

```bash
git add src/pixel_data.py tests/test_pixel_data.py
git commit -m "feat: add core PixelGrid data model with PIL conversion"
```

---

### Task 3: RLE Compression

**Files:**
- Create: `src/compression.py`
- Create: `tests/test_compression.py`

**Step 1: Write failing tests**

```python
"""Tests for RLE compression."""
import pytest
from src.compression import rle_encode, rle_decode, compress_grid, decompress_grid
from src.pixel_data import PixelGrid


class TestRLEEncode:
    def test_single_run(self):
        data = [(255, 0, 0, 255)] * 5
        encoded = rle_encode(data)
        assert encoded == [(5, (255, 0, 0, 255))]

    def test_multiple_runs(self):
        data = [(255, 0, 0, 255)] * 3 + [(0, 255, 0, 255)] * 2
        encoded = rle_encode(data)
        assert encoded == [(3, (255, 0, 0, 255)), (2, (0, 255, 0, 255))]

    def test_alternating_pixels(self):
        r = (255, 0, 0, 255)
        b = (0, 0, 255, 255)
        data = [r, b, r, b]
        encoded = rle_encode(data)
        assert encoded == [(1, r), (1, b), (1, r), (1, b)]

    def test_empty_data(self):
        assert rle_encode([]) == []

    def test_single_pixel(self):
        data = [(128, 128, 128, 255)]
        encoded = rle_encode(data)
        assert encoded == [(1, (128, 128, 128, 255))]


class TestRLEDecode:
    def test_decode_single_run(self):
        encoded = [(5, (255, 0, 0, 255))]
        decoded = rle_decode(encoded)
        assert decoded == [(255, 0, 0, 255)] * 5

    def test_decode_multiple_runs(self):
        encoded = [(3, (255, 0, 0, 255)), (2, (0, 255, 0, 255))]
        decoded = rle_decode(encoded)
        assert decoded == [(255, 0, 0, 255)] * 3 + [(0, 255, 0, 255)] * 2

    def test_empty(self):
        assert rle_decode([]) == []

    def test_roundtrip(self):
        r = (255, 0, 0, 255)
        g = (0, 255, 0, 255)
        original = [r, r, r, g, g, r]
        assert rle_decode(rle_encode(original)) == original


class TestGridCompression:
    def test_compress_uniform_grid(self):
        grid = PixelGrid(8, 8)  # All transparent
        encoded, stats = compress_grid(grid)
        assert stats["original_size"] > 0
        assert stats["compressed_size"] > 0
        assert stats["ratio"] > 1.0  # Should compress well

    def test_compress_decompress_roundtrip(self):
        grid = PixelGrid(4, 4)
        grid.set_pixel(0, 0, (255, 0, 0, 255))
        grid.set_pixel(1, 1, (0, 255, 0, 255))
        encoded, stats = compress_grid(grid)
        restored = decompress_grid(encoded, 4, 4)
        assert restored.get_pixel(0, 0) == (255, 0, 0, 255)
        assert restored.get_pixel(1, 1) == (0, 255, 0, 255)
        assert restored.get_pixel(2, 2) == (0, 0, 0, 0)
```

**Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_compression.py -v
```

**Step 3: Implement RLE compression**

```python
"""RLE compression for pixel data."""
from __future__ import annotations
import json
from src.pixel_data import PixelGrid


def rle_encode(data: list[tuple]) -> list[tuple[int, tuple]]:
    if not data:
        return []
    encoded = []
    current = data[0]
    count = 1
    for pixel in data[1:]:
        if pixel == current:
            count += 1
        else:
            encoded.append((count, current))
            current = pixel
            count = 1
    encoded.append((count, current))
    return encoded


def rle_decode(encoded: list[tuple[int, tuple]]) -> list[tuple]:
    result = []
    for count, value in encoded:
        result.extend([value] * count)
    return result


def compress_grid(grid: PixelGrid) -> tuple[list[tuple[int, tuple]], dict]:
    flat = grid.to_flat_list()
    encoded = rle_encode(flat)
    original_size = len(flat) * 4  # 4 bytes per RGBA pixel
    compressed_size = len(encoded) * 5  # count(1) + RGBA(4)
    ratio = original_size / compressed_size if compressed_size > 0 else 0
    stats = {
        "original_size": original_size,
        "compressed_size": compressed_size,
        "ratio": round(ratio, 2),
        "run_count": len(encoded),
        "pixel_count": len(flat),
    }
    return encoded, stats


def decompress_grid(encoded: list[tuple[int, tuple]], width: int, height: int) -> PixelGrid:
    flat = rle_decode(encoded)
    grid = PixelGrid(width, height)
    for i, pixel in enumerate(flat):
        x = i % width
        y = i // width
        if y < height:
            grid.set_pixel(x, y, pixel)
    return grid


def save_rle(encoded: list, width: int, height: int, filepath: str) -> None:
    data = {
        "format": "retrosprite-rle",
        "version": 1,
        "width": width,
        "height": height,
        "runs": [[count, list(color)] for count, color in encoded],
    }
    with open(filepath, "w") as f:
        json.dump(data, f)


def load_rle(filepath: str) -> tuple[list[tuple[int, tuple]], int, int]:
    with open(filepath, "r") as f:
        data = json.load(f)
    encoded = [(run[0], tuple(run[1])) for run in data["runs"]]
    return encoded, data["width"], data["height"]
```

**Step 4: Run tests**

```bash
python -m pytest tests/test_compression.py -v
```

**Step 5: Commit**

```bash
git add src/compression.py tests/test_compression.py
git commit -m "feat: add RLE compression with encode/decode and file I/O"
```

---

### Task 4: Image Processing Operations

**Files:**
- Create: `src/image_processing.py`
- Create: `tests/test_image_processing.py`

**Step 1: Write failing tests**

```python
"""Tests for image processing operations."""
import pytest
from PIL import Image
from src.image_processing import (
    blur, scale, rotate, crop, flip_horizontal, flip_vertical,
    adjust_brightness, adjust_contrast, posterize
)
from src.pixel_data import PixelGrid


@pytest.fixture
def sample_grid():
    grid = PixelGrid(8, 8)
    for x in range(4):
        for y in range(8):
            grid.set_pixel(x, y, (255, 0, 0, 255))
    for x in range(4, 8):
        for y in range(8):
            grid.set_pixel(x, y, (0, 0, 255, 255))
    return grid


class TestBlur:
    def test_blur_returns_same_dimensions(self, sample_grid):
        result = blur(sample_grid, radius=1)
        assert result.width == 8
        assert result.height == 8

    def test_blur_changes_pixels(self, sample_grid):
        result = blur(sample_grid, radius=2)
        # Border pixels should be blended
        assert result.get_pixel(4, 4) != sample_grid.get_pixel(4, 4)


class TestScale:
    def test_scale_up_2x(self, sample_grid):
        result = scale(sample_grid, 2.0)
        assert result.width == 16
        assert result.height == 16

    def test_scale_down_half(self, sample_grid):
        result = scale(sample_grid, 0.5)
        assert result.width == 4
        assert result.height == 4

    def test_scale_preserves_nearest_neighbor(self):
        grid = PixelGrid(2, 2)
        grid.set_pixel(0, 0, (255, 0, 0, 255))
        grid.set_pixel(1, 0, (0, 255, 0, 255))
        grid.set_pixel(0, 1, (0, 0, 255, 255))
        grid.set_pixel(1, 1, (255, 255, 0, 255))
        result = scale(grid, 2.0)
        # Top-left 2x2 block should all be red
        assert result.get_pixel(0, 0) == (255, 0, 0, 255)
        assert result.get_pixel(1, 0) == (255, 0, 0, 255)
        assert result.get_pixel(0, 1) == (255, 0, 0, 255)


class TestRotate:
    def test_rotate_90(self, sample_grid):
        result = rotate(sample_grid, 90)
        assert result.width == 8
        assert result.height == 8

    def test_rotate_180(self):
        grid = PixelGrid(2, 2)
        grid.set_pixel(0, 0, (255, 0, 0, 255))
        result = rotate(grid, 180)
        assert result.get_pixel(1, 1) == (255, 0, 0, 255)


class TestCrop:
    def test_crop_region(self, sample_grid):
        result = crop(sample_grid, x=0, y=0, w=4, h=4)
        assert result.width == 4
        assert result.height == 4
        assert result.get_pixel(0, 0) == (255, 0, 0, 255)


class TestFlip:
    def test_flip_horizontal(self):
        grid = PixelGrid(4, 1)
        grid.set_pixel(0, 0, (255, 0, 0, 255))
        result = flip_horizontal(grid)
        assert result.get_pixel(3, 0) == (255, 0, 0, 255)

    def test_flip_vertical(self):
        grid = PixelGrid(1, 4)
        grid.set_pixel(0, 0, (255, 0, 0, 255))
        result = flip_vertical(grid)
        assert result.get_pixel(0, 3) == (255, 0, 0, 255)


class TestPosterize:
    def test_posterize_reduces_colors(self):
        grid = PixelGrid(1, 1)
        grid.set_pixel(0, 0, (123, 200, 45, 255))
        result = posterize(grid, levels=2)
        pixel = result.get_pixel(0, 0)
        # With 2 levels, values should be either 0 or 255
        assert all(c in (0, 255) for c in pixel[:3])
```

**Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_image_processing.py -v
```

**Step 3: Implement image processing**

```python
"""Image processing operations for pixel art."""
from __future__ import annotations
from PIL import Image, ImageFilter, ImageEnhance
from src.pixel_data import PixelGrid


def blur(grid: PixelGrid, radius: int = 1) -> PixelGrid:
    img = grid.to_pil_image()
    blurred = img.filter(ImageFilter.GaussianBlur(radius=radius))
    return PixelGrid.from_pil_image(blurred)


def scale(grid: PixelGrid, factor: float) -> PixelGrid:
    img = grid.to_pil_image()
    new_w = max(1, int(grid.width * factor))
    new_h = max(1, int(grid.height * factor))
    scaled = img.resize((new_w, new_h), Image.NEAREST)
    return PixelGrid.from_pil_image(scaled)


def rotate(grid: PixelGrid, degrees: int) -> PixelGrid:
    img = grid.to_pil_image()
    rotated = img.rotate(-degrees, resample=Image.NEAREST, expand=False)
    return PixelGrid.from_pil_image(rotated)


def crop(grid: PixelGrid, x: int, y: int, w: int, h: int) -> PixelGrid:
    img = grid.to_pil_image()
    cropped = img.crop((x, y, x + w, y + h))
    return PixelGrid.from_pil_image(cropped)


def flip_horizontal(grid: PixelGrid) -> PixelGrid:
    img = grid.to_pil_image()
    flipped = img.transpose(Image.FLIP_LEFT_RIGHT)
    return PixelGrid.from_pil_image(flipped)


def flip_vertical(grid: PixelGrid) -> PixelGrid:
    img = grid.to_pil_image()
    flipped = img.transpose(Image.FLIP_TOP_BOTTOM)
    return PixelGrid.from_pil_image(flipped)


def adjust_brightness(grid: PixelGrid, factor: float) -> PixelGrid:
    img = grid.to_pil_image()
    enhancer = ImageEnhance.Brightness(img)
    enhanced = enhancer.enhance(factor)
    return PixelGrid.from_pil_image(enhanced)


def adjust_contrast(grid: PixelGrid, factor: float) -> PixelGrid:
    img = grid.to_pil_image()
    enhancer = ImageEnhance.Contrast(img)
    enhanced = enhancer.enhance(factor)
    return PixelGrid.from_pil_image(enhanced)


def posterize(grid: PixelGrid, levels: int = 4) -> PixelGrid:
    img = grid.to_pil_image()
    r, g, b, a = img.split()
    from PIL import ImageOps
    # Posterize works on L or RGB, so handle each channel
    bits = max(1, min(8, levels.bit_length()))
    r = ImageOps.posterize(r, bits)
    g = ImageOps.posterize(g, bits)
    b = ImageOps.posterize(b, bits)
    result = Image.merge("RGBA", (r, g, b, a))
    return PixelGrid.from_pil_image(result)
```

**Step 4: Run tests**

```bash
python -m pytest tests/test_image_processing.py -v
```

**Step 5: Commit**

```bash
git add src/image_processing.py tests/test_image_processing.py
git commit -m "feat: add image processing operations (blur, scale, rotate, crop, flip, posterize)"
```

---

### Task 5: Animation & Frame Management

**Files:**
- Create: `src/animation.py`
- Create: `tests/test_animation.py`

**Step 1: Write failing tests**

```python
"""Tests for animation frame management."""
import os
import pytest
from src.animation import AnimationTimeline
from src.pixel_data import PixelGrid


class TestAnimationTimeline:
    def test_starts_with_one_frame(self):
        timeline = AnimationTimeline(16, 16)
        assert timeline.frame_count == 1

    def test_add_frame(self):
        timeline = AnimationTimeline(16, 16)
        timeline.add_frame()
        assert timeline.frame_count == 2

    def test_current_frame(self):
        timeline = AnimationTimeline(8, 8)
        frame = timeline.current_frame()
        assert isinstance(frame, PixelGrid)
        assert frame.width == 8

    def test_switch_frame(self):
        timeline = AnimationTimeline(8, 8)
        timeline.current_frame().set_pixel(0, 0, (255, 0, 0, 255))
        timeline.add_frame()
        timeline.set_current(1)
        assert timeline.current_frame().get_pixel(0, 0) == (0, 0, 0, 0)
        timeline.set_current(0)
        assert timeline.current_frame().get_pixel(0, 0) == (255, 0, 0, 255)

    def test_duplicate_frame(self):
        timeline = AnimationTimeline(8, 8)
        timeline.current_frame().set_pixel(0, 0, (255, 0, 0, 255))
        timeline.duplicate_frame(0)
        assert timeline.frame_count == 2
        assert timeline.get_frame(1).get_pixel(0, 0) == (255, 0, 0, 255)
        # Should be independent copy
        timeline.get_frame(1).set_pixel(0, 0, (0, 0, 0, 0))
        assert timeline.get_frame(0).get_pixel(0, 0) == (255, 0, 0, 255)

    def test_remove_frame(self):
        timeline = AnimationTimeline(8, 8)
        timeline.add_frame()
        timeline.add_frame()
        timeline.remove_frame(1)
        assert timeline.frame_count == 2

    def test_cannot_remove_last_frame(self):
        timeline = AnimationTimeline(8, 8)
        timeline.remove_frame(0)
        assert timeline.frame_count == 1  # Should not remove

    def test_move_frame(self):
        timeline = AnimationTimeline(8, 8)
        timeline.current_frame().set_pixel(0, 0, (255, 0, 0, 255))
        timeline.add_frame()
        timeline.get_frame(1).set_pixel(0, 0, (0, 255, 0, 255))
        timeline.move_frame(0, 1)
        assert timeline.get_frame(0).get_pixel(0, 0) == (0, 255, 0, 255)
        assert timeline.get_frame(1).get_pixel(0, 0) == (255, 0, 0, 255)

    def test_export_gif(self, tmp_path):
        timeline = AnimationTimeline(8, 8)
        timeline.current_frame().set_pixel(0, 0, (255, 0, 0, 255))
        timeline.add_frame()
        timeline.get_frame(1).set_pixel(0, 0, (0, 255, 0, 255))
        path = str(tmp_path / "test.gif")
        timeline.export_gif(path, fps=10, scale=1)
        assert os.path.exists(path)
        assert os.path.getsize(path) > 0
```

**Step 2: Run tests to verify fail**

```bash
python -m pytest tests/test_animation.py -v
```

**Step 3: Implement animation timeline**

```python
"""Animation timeline and frame management."""
from __future__ import annotations
import imageio
from src.pixel_data import PixelGrid


class AnimationTimeline:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self._frames: list[PixelGrid] = [PixelGrid(width, height)]
        self._current_index: int = 0
        self.fps: int = 10

    @property
    def frame_count(self) -> int:
        return len(self._frames)

    @property
    def current_index(self) -> int:
        return self._current_index

    def current_frame(self) -> PixelGrid:
        return self._frames[self._current_index]

    def get_frame(self, index: int) -> PixelGrid:
        return self._frames[index]

    def set_current(self, index: int) -> None:
        if 0 <= index < len(self._frames):
            self._current_index = index

    def add_frame(self) -> None:
        self._frames.append(PixelGrid(self.width, self.height))

    def duplicate_frame(self, index: int) -> None:
        if 0 <= index < len(self._frames):
            copy = self._frames[index].copy()
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

    def export_gif(self, filepath: str, fps: int = 10, scale: int = 1) -> None:
        from PIL import Image
        images = []
        for frame in self._frames:
            img = frame.to_pil_image()
            if scale > 1:
                new_size = (img.width * scale, img.height * scale)
                img = img.resize(new_size, Image.NEAREST)
            # Convert RGBA to RGB with white background for GIF
            background = Image.new("RGB", img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])
            images.append(background)
        duration = 1.0 / fps
        imageio.mimsave(filepath, images, duration=duration, loop=0)
```

**Step 4: Run tests**

```bash
python -m pytest tests/test_animation.py -v
```

**Step 5: Commit**

```bash
git add src/animation.py tests/test_animation.py
git commit -m "feat: add animation timeline with frame management and GIF export"
```

---

### Task 6: Drawing Tools

**Files:**
- Create: `src/tools.py`
- Create: `tests/test_tools.py`

**Step 1: Write failing tests**

```python
"""Tests for drawing tools."""
import pytest
from src.tools import PenTool, EraserTool, FillTool, LineTool, RectTool
from src.pixel_data import PixelGrid

RED = (255, 0, 0, 255)
GREEN = (0, 255, 0, 255)
TRANSPARENT = (0, 0, 0, 0)


class TestPenTool:
    def test_draw_pixel(self):
        grid = PixelGrid(8, 8)
        tool = PenTool()
        tool.apply(grid, 3, 4, RED)
        assert grid.get_pixel(3, 4) == RED

    def test_draw_out_of_bounds_no_error(self):
        grid = PixelGrid(8, 8)
        tool = PenTool()
        tool.apply(grid, 100, 100, RED)  # Should not crash


class TestEraserTool:
    def test_erase_pixel(self):
        grid = PixelGrid(8, 8)
        grid.set_pixel(3, 3, RED)
        tool = EraserTool()
        tool.apply(grid, 3, 3)
        assert grid.get_pixel(3, 3) == TRANSPARENT


class TestFillTool:
    def test_fill_empty_area(self):
        grid = PixelGrid(4, 4)
        tool = FillTool()
        tool.apply(grid, 0, 0, RED)
        for x in range(4):
            for y in range(4):
                assert grid.get_pixel(x, y) == RED

    def test_fill_bounded_area(self):
        grid = PixelGrid(4, 4)
        # Create a border
        for i in range(4):
            grid.set_pixel(2, i, GREEN)
        tool = FillTool()
        tool.apply(grid, 0, 0, RED)
        assert grid.get_pixel(0, 0) == RED
        assert grid.get_pixel(1, 0) == RED
        assert grid.get_pixel(3, 0) == TRANSPARENT  # Other side of wall

    def test_fill_same_color_noop(self):
        grid = PixelGrid(4, 4)
        grid.set_pixel(0, 0, RED)
        tool = FillTool()
        tool.apply(grid, 0, 0, RED)  # Should not infinite loop


class TestLineTool:
    def test_horizontal_line(self):
        grid = PixelGrid(8, 8)
        tool = LineTool()
        tool.apply(grid, 0, 0, 7, 0, RED)
        for x in range(8):
            assert grid.get_pixel(x, 0) == RED

    def test_vertical_line(self):
        grid = PixelGrid(8, 8)
        tool = LineTool()
        tool.apply(grid, 0, 0, 0, 7, RED)
        for y in range(8):
            assert grid.get_pixel(0, y) == RED


class TestRectTool:
    def test_draw_rectangle_outline(self):
        grid = PixelGrid(8, 8)
        tool = RectTool()
        tool.apply(grid, 1, 1, 4, 4, RED, filled=False)
        assert grid.get_pixel(1, 1) == RED
        assert grid.get_pixel(4, 1) == RED
        assert grid.get_pixel(2, 2) == TRANSPARENT  # Inside

    def test_draw_filled_rectangle(self):
        grid = PixelGrid(8, 8)
        tool = RectTool()
        tool.apply(grid, 1, 1, 3, 3, RED, filled=True)
        assert grid.get_pixel(2, 2) == RED
```

**Step 2: Run tests to verify fail**

```bash
python -m pytest tests/test_tools.py -v
```

**Step 3: Implement drawing tools**

```python
"""Drawing tools for the pixel canvas."""
from __future__ import annotations
from collections import deque
from src.pixel_data import PixelGrid


class PenTool:
    def apply(self, grid: PixelGrid, x: int, y: int, color: tuple) -> None:
        grid.set_pixel(x, y, color)


class EraserTool:
    def apply(self, grid: PixelGrid, x: int, y: int) -> None:
        grid.set_pixel(x, y, (0, 0, 0, 0))


class FillTool:
    def apply(self, grid: PixelGrid, x: int, y: int, color: tuple) -> None:
        target = grid.get_pixel(x, y)
        if target is None or target == color:
            return
        queue = deque([(x, y)])
        visited = set()
        while queue:
            cx, cy = queue.popleft()
            if (cx, cy) in visited:
                continue
            if not (0 <= cx < grid.width and 0 <= cy < grid.height):
                continue
            if grid.get_pixel(cx, cy) != target:
                continue
            visited.add((cx, cy))
            grid.set_pixel(cx, cy, color)
            queue.extend([(cx+1, cy), (cx-1, cy), (cx, cy+1), (cx, cy-1)])


class LineTool:
    def apply(self, grid: PixelGrid, x0: int, y0: int, x1: int, y1: int,
              color: tuple) -> None:
        # Bresenham's line algorithm
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        while True:
            grid.set_pixel(x0, y0, color)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy


class RectTool:
    def apply(self, grid: PixelGrid, x0: int, y0: int, x1: int, y1: int,
              color: tuple, filled: bool = False) -> None:
        min_x, max_x = min(x0, x1), max(x0, x1)
        min_y, max_y = min(y0, y1), max(y0, y1)
        if filled:
            for y in range(min_y, max_y + 1):
                for x in range(min_x, max_x + 1):
                    grid.set_pixel(x, y, color)
        else:
            for x in range(min_x, max_x + 1):
                grid.set_pixel(x, min_y, color)
                grid.set_pixel(x, max_y, color)
            for y in range(min_y, max_y + 1):
                grid.set_pixel(min_x, y, color)
                grid.set_pixel(max_x, y, color)
```

**Step 4: Run tests**

```bash
python -m pytest tests/test_tools.py -v
```

**Step 5: Commit**

```bash
git add src/tools.py tests/test_tools.py
git commit -m "feat: add drawing tools (pen, eraser, fill, line, rectangle)"
```

---

### Task 7: Color Palette Management

**Files:**
- Create: `src/palette.py`

**Step 1: Implement palette**

```python
"""Color palette management."""
from __future__ import annotations

# Classic retro palettes
RETRO_PALETTES = {
    "NES": [
        (0, 0, 0, 255), (255, 255, 255, 255),
        (124, 124, 124, 255), (188, 188, 188, 255),
        (0, 0, 252, 255), (0, 120, 248, 255),
        (104, 136, 252, 255), (152, 120, 248, 255),
        (216, 0, 204, 255), (248, 56, 152, 255),
        (248, 120, 88, 255), (248, 184, 0, 255),
        (172, 124, 0, 255), (0, 184, 0, 255),
        (0, 168, 0, 255), (0, 168, 68, 255),
    ],
    "GameBoy": [
        (15, 56, 15, 255), (48, 98, 48, 255),
        (139, 172, 15, 255), (155, 188, 15, 255),
    ],
    "CGA": [
        (0, 0, 0, 255), (85, 255, 255, 255),
        (255, 85, 255, 255), (255, 255, 255, 255),
    ],
    "Pico-8": [
        (0, 0, 0, 255), (29, 43, 83, 255),
        (126, 37, 83, 255), (0, 135, 81, 255),
        (171, 82, 54, 255), (95, 87, 79, 255),
        (194, 195, 199, 255), (255, 241, 232, 255),
        (255, 0, 77, 255), (255, 163, 0, 255),
        (255, 236, 39, 255), (0, 228, 54, 255),
        (41, 173, 255, 255), (131, 118, 156, 255),
        (255, 119, 168, 255), (255, 204, 170, 255),
    ],
}


class Palette:
    def __init__(self, name: str = "Pico-8"):
        self.name = name
        self.colors: list[tuple[int, int, int, int]] = list(
            RETRO_PALETTES.get(name, RETRO_PALETTES["Pico-8"])
        )
        self.selected_index: int = 0

    @property
    def selected_color(self) -> tuple[int, int, int, int]:
        return self.colors[self.selected_index]

    def select(self, index: int) -> None:
        if 0 <= index < len(self.colors):
            self.selected_index = index

    def add_color(self, color: tuple[int, int, int, int]) -> None:
        if color not in self.colors:
            self.colors.append(color)

    def set_palette(self, name: str) -> None:
        if name in RETRO_PALETTES:
            self.name = name
            self.colors = list(RETRO_PALETTES[name])
            self.selected_index = 0
```

**Step 2: Commit**

```bash
git add src/palette.py
git commit -m "feat: add color palette with retro presets (NES, GameBoy, CGA, Pico-8)"
```

---

### Task 8: Pixel Canvas Widget (UI)

**Files:**
- Create: `src/canvas.py`

This is the main drawing surface — a Tkinter Canvas that renders the pixel grid with zoom, grid lines, and mouse interaction.

**Step 1: Implement pixel canvas**

```python
"""Pixel canvas widget for drawing."""
from __future__ import annotations
import tkinter as tk
from src.pixel_data import PixelGrid


class PixelCanvas(tk.Canvas):
    """Zoomable pixel art canvas with grid overlay."""

    def __init__(self, parent, grid: PixelGrid, pixel_size: int = 20, **kwargs):
        self.grid = grid
        self.pixel_size = pixel_size
        self.show_grid = True
        width = grid.width * pixel_size
        height = grid.height * pixel_size
        super().__init__(parent, width=width, height=height,
                         bg="#2b2b2b", highlightthickness=0, **kwargs)

        self._on_pixel_click = None
        self._on_pixel_drag = None
        self._on_pixel_release = None

        self.bind("<Button-1>", self._handle_click)
        self.bind("<B1-Motion>", self._handle_drag)
        self.bind("<ButtonRelease-1>", self._handle_release)

    def set_grid(self, grid: PixelGrid) -> None:
        self.grid = grid
        self._resize_canvas()
        self.render()

    def _resize_canvas(self) -> None:
        w = self.grid.width * self.pixel_size
        h = self.grid.height * self.pixel_size
        self.config(width=w, height=h)

    def set_pixel_size(self, size: int) -> None:
        self.pixel_size = max(1, min(64, size))
        self._resize_canvas()
        self.render()

    def zoom_in(self) -> None:
        self.set_pixel_size(self.pixel_size + 4)

    def zoom_out(self) -> None:
        self.set_pixel_size(self.pixel_size - 4)

    def _to_grid_coords(self, event) -> tuple[int, int]:
        x = event.x // self.pixel_size
        y = event.y // self.pixel_size
        return x, y

    def _handle_click(self, event):
        x, y = self._to_grid_coords(event)
        if self._on_pixel_click:
            self._on_pixel_click(x, y)

    def _handle_drag(self, event):
        x, y = self._to_grid_coords(event)
        if self._on_pixel_drag:
            self._on_pixel_drag(x, y)

    def _handle_release(self, event):
        x, y = self._to_grid_coords(event)
        if self._on_pixel_release:
            self._on_pixel_release(x, y)

    def on_pixel_click(self, callback) -> None:
        self._on_pixel_click = callback

    def on_pixel_drag(self, callback) -> None:
        self._on_pixel_drag = callback

    def on_pixel_release(self, callback) -> None:
        self._on_pixel_release = callback

    def render(self) -> None:
        self.delete("all")
        ps = self.pixel_size
        for y in range(self.grid.height):
            for x in range(self.grid.width):
                pixel = self.grid.get_pixel(x, y)
                if pixel[3] > 0:  # Not fully transparent
                    color = f"#{pixel[0]:02x}{pixel[1]:02x}{pixel[2]:02x}"
                    self.create_rectangle(
                        x * ps, y * ps, (x + 1) * ps, (y + 1) * ps,
                        fill=color, outline="", tags="pixel"
                    )
        if self.show_grid and ps >= 4:
            self._draw_grid()

    def _draw_grid(self) -> None:
        ps = self.pixel_size
        w = self.grid.width * ps
        h = self.grid.height * ps
        grid_color = "#3a3a3a"
        for x in range(0, w + 1, ps):
            self.create_line(x, 0, x, h, fill=grid_color, tags="grid")
        for y in range(0, h + 1, ps):
            self.create_line(0, y, w, y, fill=grid_color, tags="grid")

    def render_onion_skin(self, prev_grid: PixelGrid) -> None:
        """Render previous frame as translucent overlay."""
        ps = self.pixel_size
        for y in range(prev_grid.height):
            for x in range(prev_grid.width):
                pixel = prev_grid.get_pixel(x, y)
                if pixel[3] > 0:
                    # Blend with background for onion skin effect
                    r = min(255, pixel[0] // 2 + 128)
                    g = min(255, pixel[1] // 2 + 128)
                    b = min(255, pixel[2] // 2 + 128)
                    color = f"#{r:02x}{g:02x}{b:02x}"
                    self.create_rectangle(
                        x * ps, y * ps, (x + 1) * ps, (y + 1) * ps,
                        fill=color, outline="", stipple="gray25",
                        tags="onion"
                    )
```

**Step 2: Commit**

```bash
git add src/canvas.py
git commit -m "feat: add pixel canvas widget with zoom, grid, and onion skinning"
```

---

### Task 9: UI Panels (Toolbar, Right Panel, Dialogs)

**Files:**
- Create: `src/ui/toolbar.py`
- Create: `src/ui/right_panel.py`
- Create: `src/ui/dialogs.py`

**Step 1: Implement toolbar**

```python
# src/ui/toolbar.py
"""Left-side tool bar."""
from __future__ import annotations
import tkinter as tk


TOOLS = [
    ("Pen", "P"),
    ("Eraser", "E"),
    ("Fill", "F"),
    ("Pick", "I"),
    ("Select", "S"),
    ("Line", "L"),
    ("Rect", "R"),
]


class Toolbar(tk.Frame):
    def __init__(self, parent, on_tool_change=None, **kwargs):
        super().__init__(parent, bg="#1e1e1e", **kwargs)
        self.current_tool = "Pen"
        self._on_tool_change = on_tool_change
        self._buttons: dict[str, tk.Button] = {}

        title = tk.Label(self, text="Tools", fg="#aaa", bg="#1e1e1e",
                         font=("Courier", 9, "bold"))
        title.pack(pady=(8, 4))

        for name, shortcut in TOOLS:
            btn = tk.Button(
                self, text=f"{name}\n({shortcut})", width=8, height=2,
                bg="#333", fg="#ddd", activebackground="#555",
                relief="flat", font=("Courier", 8),
                command=lambda n=name: self.select_tool(n)
            )
            btn.pack(padx=4, pady=2)
            self._buttons[name] = btn

        self._highlight("Pen")

    def select_tool(self, name: str) -> None:
        self.current_tool = name
        self._highlight(name)
        if self._on_tool_change:
            self._on_tool_change(name)

    def _highlight(self, name: str) -> None:
        for tool_name, btn in self._buttons.items():
            if tool_name == name:
                btn.config(bg="#0078d4", fg="#fff")
            else:
                btn.config(bg="#333", fg="#ddd")
```

**Step 2: Implement right panel**

```python
# src/ui/right_panel.py
"""Right-side panel with palette, frames, animation preview, compression stats."""
from __future__ import annotations
import tkinter as tk
from src.palette import Palette


class PalettePanel(tk.Frame):
    def __init__(self, parent, palette: Palette, on_color_select=None, **kwargs):
        super().__init__(parent, bg="#1e1e1e", **kwargs)
        self.palette = palette
        self._on_color_select = on_color_select

        tk.Label(self, text="Palette", fg="#aaa", bg="#1e1e1e",
                 font=("Courier", 9, "bold")).pack(pady=(8, 4))

        self.color_frame = tk.Frame(self, bg="#1e1e1e")
        self.color_frame.pack(padx=4)
        self._color_buttons = []
        self._build_colors()

        # Current color display
        self.current_label = tk.Label(self, text="Current:", fg="#aaa",
                                      bg="#1e1e1e", font=("Courier", 8))
        self.current_label.pack(pady=(4, 0))
        self.current_swatch = tk.Canvas(self, width=40, height=40,
                                        bg="#000", highlightthickness=1,
                                        highlightbackground="#555")
        self.current_swatch.pack(pady=4)
        self._update_swatch()

    def _build_colors(self):
        for widget in self._color_buttons:
            widget.destroy()
        self._color_buttons.clear()

        cols = 4
        for i, color in enumerate(self.palette.colors):
            hex_color = f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"
            btn = tk.Button(
                self.color_frame, bg=hex_color, width=2, height=1,
                relief="flat", activebackground=hex_color,
                command=lambda idx=i: self._select(idx)
            )
            btn.grid(row=i // cols, column=i % cols, padx=1, pady=1)
            self._color_buttons.append(btn)

    def _select(self, index: int):
        self.palette.select(index)
        self._update_swatch()
        if self._on_color_select:
            self._on_color_select(self.palette.selected_color)

    def _update_swatch(self):
        c = self.palette.selected_color
        hex_c = f"#{c[0]:02x}{c[1]:02x}{c[2]:02x}"
        self.current_swatch.config(bg=hex_c)

    def refresh(self):
        self._build_colors()
        self._update_swatch()


class FramePanel(tk.Frame):
    def __init__(self, parent, on_frame_select=None, on_add=None,
                 on_duplicate=None, on_delete=None, **kwargs):
        super().__init__(parent, bg="#1e1e1e", **kwargs)
        self._on_frame_select = on_frame_select

        tk.Label(self, text="Frames", fg="#aaa", bg="#1e1e1e",
                 font=("Courier", 9, "bold")).pack(pady=(8, 4))

        self.listbox = tk.Listbox(self, bg="#2b2b2b", fg="#ddd",
                                  selectbackground="#0078d4", height=6,
                                  font=("Courier", 9))
        self.listbox.pack(padx=4, fill="x")
        self.listbox.bind("<<ListboxSelect>>", self._on_select)

        btn_frame = tk.Frame(self, bg="#1e1e1e")
        btn_frame.pack(pady=4)
        for text, cmd in [("+ Add", on_add), ("Copy", on_duplicate),
                          ("- Del", on_delete)]:
            tk.Button(btn_frame, text=text, bg="#333", fg="#ddd",
                      font=("Courier", 8), relief="flat",
                      command=cmd).pack(side="left", padx=2)

    def _on_select(self, event):
        sel = self.listbox.curselection()
        if sel and self._on_frame_select:
            self._on_frame_select(sel[0])

    def update_list(self, count: int, current: int):
        self.listbox.delete(0, tk.END)
        for i in range(count):
            prefix = ">> " if i == current else "   "
            self.listbox.insert(tk.END, f"{prefix}Frame {i + 1}")
        self.listbox.selection_set(current)


class AnimationPreview(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg="#1e1e1e", **kwargs)

        tk.Label(self, text="Preview", fg="#aaa", bg="#1e1e1e",
                 font=("Courier", 9, "bold")).pack(pady=(8, 4))

        self.preview_canvas = tk.Canvas(self, width=80, height=80,
                                        bg="#2b2b2b", highlightthickness=1,
                                        highlightbackground="#555")
        self.preview_canvas.pack(padx=4, pady=4)

        ctrl_frame = tk.Frame(self, bg="#1e1e1e")
        ctrl_frame.pack()
        self.play_btn = None
        self.stop_btn = None
        self._on_play = None
        self._on_stop = None

    def set_callbacks(self, on_play, on_stop):
        self._on_play = on_play
        self._on_stop = on_stop
        ctrl_frame = tk.Frame(self, bg="#1e1e1e")
        ctrl_frame.pack()
        self.play_btn = tk.Button(ctrl_frame, text="Play", bg="#333",
                                  fg="#ddd", font=("Courier", 8),
                                  relief="flat", command=on_play)
        self.play_btn.pack(side="left", padx=2)
        self.stop_btn = tk.Button(ctrl_frame, text="Stop", bg="#333",
                                  fg="#ddd", font=("Courier", 8),
                                  relief="flat", command=on_stop)
        self.stop_btn.pack(side="left", padx=2)

    def render_frame(self, grid, preview_size=80):
        self.preview_canvas.delete("all")
        ps = max(1, preview_size // max(grid.width, grid.height))
        for y in range(grid.height):
            for x in range(grid.width):
                pixel = grid.get_pixel(x, y)
                if pixel[3] > 0:
                    color = f"#{pixel[0]:02x}{pixel[1]:02x}{pixel[2]:02x}"
                    self.preview_canvas.create_rectangle(
                        x * ps, y * ps, (x + 1) * ps, (y + 1) * ps,
                        fill=color, outline=""
                    )


class CompressionPanel(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg="#1e1e1e", **kwargs)

        tk.Label(self, text="RLE Compression", fg="#aaa", bg="#1e1e1e",
                 font=("Courier", 9, "bold")).pack(pady=(8, 4))

        self.stats_text = tk.Text(self, width=22, height=8, bg="#2b2b2b",
                                  fg="#ddd", font=("Courier", 8),
                                  state="disabled")
        self.stats_text.pack(padx=4, pady=4)

    def update_stats(self, stats: dict):
        self.stats_text.config(state="normal")
        self.stats_text.delete("1.0", "end")
        lines = [
            f"Pixels:     {stats.get('pixel_count', 0)}",
            f"Runs:       {stats.get('run_count', 0)}",
            f"Original:   {stats.get('original_size', 0)} B",
            f"Compressed: {stats.get('compressed_size', 0)} B",
            f"Ratio:      {stats.get('ratio', 0)}x",
        ]
        self.stats_text.insert("1.0", "\n".join(lines))
        self.stats_text.config(state="disabled")


class RightPanel(tk.Frame):
    def __init__(self, parent, palette, **kwargs):
        super().__init__(parent, bg="#1e1e1e", **kwargs)
        self.palette_panel = PalettePanel(self, palette)
        self.palette_panel.pack(fill="x")
        self.frame_panel = FramePanel(self)
        self.frame_panel.pack(fill="x")
        self.animation_preview = AnimationPreview(self)
        self.animation_preview.pack(fill="x")
        self.compression_panel = CompressionPanel(self)
        self.compression_panel.pack(fill="x")
```

**Step 3: Implement dialogs**

```python
# src/ui/dialogs.py
"""Dialog windows for RetroSprite."""
from __future__ import annotations
import tkinter as tk
from tkinter import simpledialog, filedialog, messagebox


def ask_canvas_size(parent) -> tuple[int, int] | None:
    """Ask user for canvas dimensions."""
    dialog = tk.Toplevel(parent)
    dialog.title("New Canvas")
    dialog.geometry("250x180")
    dialog.resizable(False, False)
    dialog.configure(bg="#1e1e1e")
    dialog.transient(parent)
    dialog.grab_set()

    result = [None]

    tk.Label(dialog, text="Canvas Size", fg="#ddd", bg="#1e1e1e",
             font=("Courier", 11, "bold")).pack(pady=(12, 8))

    sizes = [(8, 8), (16, 16), (32, 32), (64, 64)]
    for w, h in sizes:
        tk.Button(
            dialog, text=f"{w} x {h}", width=12, bg="#333", fg="#ddd",
            relief="flat", font=("Courier", 9),
            command=lambda ww=w, hh=h: (result.__setitem__(0, (ww, hh)),
                                         dialog.destroy())
        ).pack(pady=2)

    dialog.wait_window()
    return result[0]


def ask_save_file(parent, filetypes=None) -> str | None:
    if filetypes is None:
        filetypes = [("PNG files", "*.png"), ("All files", "*.*")]
    return filedialog.asksaveasfilename(parent=parent, filetypes=filetypes)


def ask_open_file(parent, filetypes=None) -> str | None:
    if filetypes is None:
        filetypes = [("Image files", "*.png;*.jpg;*.bmp"),
                     ("RLE files", "*.rle"), ("All files", "*.*")]
    return filedialog.askopenfilename(parent=parent, filetypes=filetypes)


def ask_export_gif(parent) -> str | None:
    return filedialog.asksaveasfilename(
        parent=parent, filetypes=[("GIF files", "*.gif")],
        defaultextension=".gif"
    )


def show_info(parent, title: str, message: str):
    messagebox.showinfo(title, message, parent=parent)


def show_error(parent, title: str, message: str):
    messagebox.showerror(title, message, parent=parent)
```

**Step 4: Commit**

```bash
git add src/ui/toolbar.py src/ui/right_panel.py src/ui/dialogs.py
git commit -m "feat: add UI panels (toolbar, right panel, dialogs)"
```

---

### Task 10: Main Application Window

**Files:**
- Create: `src/app.py`

This wires everything together — the canvas, tools, panels, menus, and animation playback.

**Step 1: Implement main application**

```python
"""Main application window for RetroSprite."""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from PIL import Image

from src.pixel_data import PixelGrid
from src.canvas import PixelCanvas
from src.tools import PenTool, EraserTool, FillTool, LineTool, RectTool
from src.image_processing import (
    blur, scale, rotate, crop, flip_horizontal, flip_vertical,
    adjust_brightness, adjust_contrast, posterize
)
from src.compression import compress_grid, decompress_grid, save_rle, load_rle
from src.animation import AnimationTimeline
from src.palette import Palette
from src.ui.toolbar import Toolbar
from src.ui.right_panel import RightPanel
from src.ui.dialogs import (
    ask_canvas_size, ask_save_file, ask_open_file,
    ask_export_gif, show_info, show_error
)


class RetroSpriteApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("RetroSprite - Pixel Art Creator")
        self.root.configure(bg="#1e1e1e")
        self.root.geometry("1000x700")

        # Core state
        self.timeline = AnimationTimeline(32, 32)
        self.palette = Palette("Pico-8")
        self.current_tool_name = "Pen"
        self._tools = {
            "Pen": PenTool(),
            "Eraser": EraserTool(),
            "Fill": FillTool(),
            "Line": LineTool(),
            "Rect": RectTool(),
        }
        self._line_start = None
        self._rect_start = None
        self._playing = False
        self._play_after_id = None
        self._onion_skin = False

        self._build_menu()
        self._build_ui()
        self._bind_keys()
        self._refresh_all()

    def run(self):
        self.root.mainloop()

    # --- UI Building ---

    def _build_menu(self):
        menubar = tk.Menu(self.root, bg="#2b2b2b", fg="#ddd",
                          activebackground="#0078d4")

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="New", command=self._new_canvas)
        file_menu.add_command(label="Open Image...", command=self._open_image)
        file_menu.add_command(label="Save as PNG...", command=self._save_png)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)

        # Edit menu
        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="Clear Canvas", command=self._clear_canvas)
        menubar.add_cascade(label="Edit", menu=edit_menu)

        # Image menu
        image_menu = tk.Menu(menubar, tearoff=0)
        image_menu.add_command(label="Blur", command=lambda: self._apply_filter("blur"))
        image_menu.add_command(label="Scale 2x", command=lambda: self._apply_filter("scale_up"))
        image_menu.add_command(label="Scale 0.5x", command=lambda: self._apply_filter("scale_down"))
        image_menu.add_command(label="Rotate 90 CW", command=lambda: self._apply_filter("rotate_90"))
        image_menu.add_command(label="Rotate 180", command=lambda: self._apply_filter("rotate_180"))
        image_menu.add_command(label="Flip Horizontal", command=lambda: self._apply_filter("flip_h"))
        image_menu.add_command(label="Flip Vertical", command=lambda: self._apply_filter("flip_v"))
        image_menu.add_separator()
        image_menu.add_command(label="Brightness +", command=lambda: self._apply_filter("bright_up"))
        image_menu.add_command(label="Brightness -", command=lambda: self._apply_filter("bright_down"))
        image_menu.add_command(label="Contrast +", command=lambda: self._apply_filter("contrast_up"))
        image_menu.add_command(label="Contrast -", command=lambda: self._apply_filter("contrast_down"))
        image_menu.add_command(label="Posterize", command=lambda: self._apply_filter("posterize"))
        menubar.add_cascade(label="Image", menu=image_menu)

        # Animation menu
        anim_menu = tk.Menu(menubar, tearoff=0)
        anim_menu.add_command(label="Play", command=self._play_animation)
        anim_menu.add_command(label="Stop", command=self._stop_animation)
        anim_menu.add_separator()
        anim_menu.add_command(label="Toggle Onion Skin",
                              command=self._toggle_onion_skin)
        anim_menu.add_separator()
        anim_menu.add_command(label="Export GIF...", command=self._export_gif)
        menubar.add_cascade(label="Animation", menu=anim_menu)

        # Compression menu
        comp_menu = tk.Menu(menubar, tearoff=0)
        comp_menu.add_command(label="Compress Current Frame",
                              command=self._compress_frame)
        comp_menu.add_command(label="Save as RLE...", command=self._save_rle)
        comp_menu.add_command(label="Load RLE...", command=self._load_rle)
        menubar.add_cascade(label="Compression", menu=comp_menu)

        self.root.config(menu=menubar)

    def _build_ui(self):
        main_frame = tk.Frame(self.root, bg="#1e1e1e")
        main_frame.pack(fill="both", expand=True)

        # Toolbar (left)
        self.toolbar = Toolbar(main_frame,
                               on_tool_change=self._on_tool_change)
        self.toolbar.pack(side="left", fill="y")

        # Right panel
        self.right_panel = RightPanel(main_frame, self.palette)
        self.right_panel.pack(side="right", fill="y")

        # Wire up right panel callbacks
        self.right_panel.palette_panel._on_color_select = self._on_color_select
        self.right_panel.frame_panel._on_frame_select = self._on_frame_select
        self.right_panel.frame_panel = FramePanelWired(
            self.right_panel, self
        )
        self.right_panel.animation_preview.set_callbacks(
            self._play_animation, self._stop_animation
        )

        # Canvas (center) with scroll
        canvas_frame = tk.Frame(main_frame, bg="#2b2b2b")
        canvas_frame.pack(side="left", fill="both", expand=True)

        self.pixel_canvas = PixelCanvas(
            canvas_frame, self.timeline.current_frame(), pixel_size=16
        )
        self.pixel_canvas.pack(expand=True)

        self.pixel_canvas.on_pixel_click(self._on_canvas_click)
        self.pixel_canvas.on_pixel_drag(self._on_canvas_drag)
        self.pixel_canvas.on_pixel_release(self._on_canvas_release)

        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status = tk.Label(self.root, textvariable=self.status_var,
                          bg="#1a1a1a", fg="#888", anchor="w",
                          font=("Courier", 8), padx=8)
        status.pack(side="bottom", fill="x")

    def _bind_keys(self):
        self.root.bind("p", lambda e: self.toolbar.select_tool("Pen"))
        self.root.bind("e", lambda e: self.toolbar.select_tool("Eraser"))
        self.root.bind("f", lambda e: self.toolbar.select_tool("Fill"))
        self.root.bind("i", lambda e: self.toolbar.select_tool("Pick"))
        self.root.bind("l", lambda e: self.toolbar.select_tool("Line"))
        self.root.bind("r", lambda e: self.toolbar.select_tool("Rect"))
        self.root.bind("+", lambda e: self.pixel_canvas.zoom_in())
        self.root.bind("-", lambda e: self.pixel_canvas.zoom_out())
        self.root.bind("=", lambda e: self.pixel_canvas.zoom_in())

    # --- Tool Handling ---

    def _on_tool_change(self, name: str):
        self.current_tool_name = name
        self._update_status()

    def _on_color_select(self, color):
        self._update_status()

    def _on_canvas_click(self, x, y):
        grid = self.timeline.current_frame()
        color = self.palette.selected_color
        tool_name = self.current_tool_name

        if tool_name == "Pen":
            self._tools["Pen"].apply(grid, x, y, color)
        elif tool_name == "Eraser":
            self._tools["Eraser"].apply(grid, x, y)
        elif tool_name == "Fill":
            self._tools["Fill"].apply(grid, x, y, color)
        elif tool_name == "Pick":
            picked = grid.get_pixel(x, y)
            if picked and picked[3] > 0:
                self.palette.add_color(picked)
                self.palette.select(self.palette.colors.index(picked))
                self.right_panel.palette_panel.refresh()
        elif tool_name == "Line":
            self._line_start = (x, y)
        elif tool_name == "Rect":
            self._rect_start = (x, y)

        self._render_canvas()

    def _on_canvas_drag(self, x, y):
        grid = self.timeline.current_frame()
        color = self.palette.selected_color

        if self.current_tool_name == "Pen":
            self._tools["Pen"].apply(grid, x, y, color)
        elif self.current_tool_name == "Eraser":
            self._tools["Eraser"].apply(grid, x, y)

        self._render_canvas()

    def _on_canvas_release(self, x, y):
        grid = self.timeline.current_frame()
        color = self.palette.selected_color

        if self.current_tool_name == "Line" and self._line_start:
            sx, sy = self._line_start
            self._tools["Line"].apply(grid, sx, sy, x, y, color)
            self._line_start = None
        elif self.current_tool_name == "Rect" and self._rect_start:
            sx, sy = self._rect_start
            self._tools["Rect"].apply(grid, sx, sy, x, y, color, filled=False)
            self._rect_start = None

        self._render_canvas()

    # --- Frame Management ---

    def _on_frame_select(self, index):
        self.timeline.set_current(index)
        self._refresh_canvas()
        self._update_frame_list()

    def _add_frame(self):
        self.timeline.add_frame()
        self.timeline.set_current(self.timeline.frame_count - 1)
        self._refresh_canvas()
        self._update_frame_list()

    def _duplicate_frame(self):
        self.timeline.duplicate_frame(self.timeline.current_index)
        self.timeline.set_current(self.timeline.current_index + 1)
        self._refresh_canvas()
        self._update_frame_list()

    def _delete_frame(self):
        self.timeline.remove_frame(self.timeline.current_index)
        self._refresh_canvas()
        self._update_frame_list()

    # --- Image Processing ---

    def _apply_filter(self, filter_name: str):
        grid = self.timeline.current_frame()
        idx = self.timeline.current_index

        if filter_name == "blur":
            result = blur(grid, radius=1)
        elif filter_name == "scale_up":
            result = scale(grid, 2.0)
        elif filter_name == "scale_down":
            result = scale(grid, 0.5)
        elif filter_name == "rotate_90":
            result = rotate(grid, 90)
        elif filter_name == "rotate_180":
            result = rotate(grid, 180)
        elif filter_name == "flip_h":
            result = flip_horizontal(grid)
        elif filter_name == "flip_v":
            result = flip_vertical(grid)
        elif filter_name == "bright_up":
            result = adjust_brightness(grid, 1.3)
        elif filter_name == "bright_down":
            result = adjust_brightness(grid, 0.7)
        elif filter_name == "contrast_up":
            result = adjust_contrast(grid, 1.5)
        elif filter_name == "contrast_down":
            result = adjust_contrast(grid, 0.7)
        elif filter_name == "posterize":
            result = posterize(grid, levels=4)
        else:
            return

        # Replace frame with result
        self.timeline._frames[idx] = result
        self._refresh_canvas()

    # --- Animation ---

    def _play_animation(self):
        if self._playing:
            return
        self._playing = True
        self._animate_step(0)

    def _animate_step(self, frame_idx):
        if not self._playing:
            return
        if frame_idx >= self.timeline.frame_count:
            frame_idx = 0
        self.timeline.set_current(frame_idx)
        self._refresh_canvas()
        self._update_frame_list()
        # Update preview
        self.right_panel.animation_preview.render_frame(
            self.timeline.current_frame()
        )
        delay = max(30, 1000 // self.timeline.fps)
        self._play_after_id = self.root.after(
            delay, self._animate_step, frame_idx + 1
        )

    def _stop_animation(self):
        self._playing = False
        if self._play_after_id:
            self.root.after_cancel(self._play_after_id)
            self._play_after_id = None

    def _toggle_onion_skin(self):
        self._onion_skin = not self._onion_skin
        self._render_canvas()

    def _export_gif(self):
        path = ask_export_gif(self.root)
        if path:
            try:
                self.timeline.export_gif(path, fps=self.timeline.fps, scale=4)
                show_info(self.root, "Export", f"GIF saved to {path}")
            except Exception as e:
                show_error(self.root, "Export Error", str(e))

    # --- Compression ---

    def _compress_frame(self):
        grid = self.timeline.current_frame()
        encoded, stats = compress_grid(grid)
        self.right_panel.compression_panel.update_stats(stats)
        self._update_status(f"Compressed: {stats['ratio']}x ratio")

    def _save_rle(self):
        path = ask_save_file(self.root,
                             filetypes=[("RLE files", "*.rle")])
        if path:
            grid = self.timeline.current_frame()
            encoded, stats = compress_grid(grid)
            save_rle(encoded, grid.width, grid.height, path)
            show_info(self.root, "Saved", f"RLE saved to {path}")

    def _load_rle(self):
        path = ask_open_file(self.root,
                             filetypes=[("RLE files", "*.rle")])
        if path:
            try:
                encoded, w, h = load_rle(path)
                grid = decompress_grid(encoded, w, h)
                self.timeline._frames[self.timeline.current_index] = grid
                self._refresh_canvas()
                show_info(self.root, "Loaded", f"RLE loaded from {path}")
            except Exception as e:
                show_error(self.root, "Load Error", str(e))

    # --- File Operations ---

    def _new_canvas(self):
        size = ask_canvas_size(self.root)
        if size:
            w, h = size
            self.timeline = AnimationTimeline(w, h)
            self._refresh_all()

    def _open_image(self):
        path = ask_open_file(self.root)
        if path:
            try:
                img = Image.open(path).convert("RGBA")
                grid = PixelGrid.from_pil_image(img)
                self.timeline._frames[self.timeline.current_index] = grid
                self._refresh_canvas()
            except Exception as e:
                show_error(self.root, "Open Error", str(e))

    def _save_png(self):
        path = ask_save_file(self.root,
                             filetypes=[("PNG files", "*.png")])
        if path:
            grid = self.timeline.current_frame()
            img = grid.to_pil_image()
            # Scale up for visibility
            scaled = img.resize(
                (img.width * 8, img.height * 8), Image.NEAREST
            )
            scaled.save(path)
            show_info(self.root, "Saved", f"Saved to {path}")

    def _clear_canvas(self):
        self.timeline.current_frame().clear()
        self._render_canvas()

    # --- Rendering ---

    def _refresh_all(self):
        self._refresh_canvas()
        self._update_frame_list()
        self._update_status()

    def _refresh_canvas(self):
        self.pixel_canvas.set_grid(self.timeline.current_frame())

    def _render_canvas(self):
        self.pixel_canvas.render()
        if self._onion_skin and self.timeline.current_index > 0:
            prev = self.timeline.get_frame(self.timeline.current_index - 1)
            self.pixel_canvas.render_onion_skin(prev)

    def _update_frame_list(self):
        self.right_panel.frame_panel.update_list(
            self.timeline.frame_count, self.timeline.current_index
        )

    def _update_status(self, extra: str = ""):
        grid = self.timeline.current_frame()
        parts = [
            f"{grid.width}x{grid.height}",
            f"Zoom: {self.pixel_canvas.pixel_size}px",
            f"Frame {self.timeline.current_index + 1}/{self.timeline.frame_count}",
            f"Tool: {self.current_tool_name}",
        ]
        if extra:
            parts.append(extra)
        self.status_var.set(" | ".join(parts))


class FramePanelWired(tk.Frame):
    """Frame panel with wired callbacks to the app."""
    def __init__(self, parent, app: RetroSpriteApp):
        super().__init__(parent, bg="#1e1e1e")
        self.app = app

        tk.Label(self, text="Frames", fg="#aaa", bg="#1e1e1e",
                 font=("Courier", 9, "bold")).pack(pady=(8, 4))

        self.listbox = tk.Listbox(self, bg="#2b2b2b", fg="#ddd",
                                  selectbackground="#0078d4", height=6,
                                  font=("Courier", 9))
        self.listbox.pack(padx=4, fill="x")
        self.listbox.bind("<<ListboxSelect>>", self._on_select)

        btn_frame = tk.Frame(self, bg="#1e1e1e")
        btn_frame.pack(pady=4)
        tk.Button(btn_frame, text="+ Add", bg="#333", fg="#ddd",
                  font=("Courier", 8), relief="flat",
                  command=app._add_frame).pack(side="left", padx=2)
        tk.Button(btn_frame, text="Copy", bg="#333", fg="#ddd",
                  font=("Courier", 8), relief="flat",
                  command=app._duplicate_frame).pack(side="left", padx=2)
        tk.Button(btn_frame, text="- Del", bg="#333", fg="#ddd",
                  font=("Courier", 8), relief="flat",
                  command=app._delete_frame).pack(side="left", padx=2)

    def _on_select(self, event):
        sel = self.listbox.curselection()
        if sel:
            self.app._on_frame_select(sel[0])

    def update_list(self, count: int, current: int):
        self.listbox.delete(0, tk.END)
        for i in range(count):
            prefix = ">> " if i == current else "   "
            self.listbox.insert(tk.END, f"{prefix}Frame {i + 1}")
        if current < count:
            self.listbox.selection_set(current)
```

**Step 2: Verify it launches**

```bash
python main.py
```

Expected: Window appears with toolbar, canvas, and right panel. Close the window.

**Step 3: Commit**

```bash
git add src/app.py
git commit -m "feat: add main application window wiring all components together"
```

---

### Task 11: Sample Assets & Final Polish

**Files:**
- Create: `assets/sample_heart.py` (script to generate a sample sprite)

**Step 1: Create sample sprite generator**

```python
"""Generate sample pixel art for testing."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.pixel_data import PixelGrid

# 16x16 heart sprite
HEART = [
    "..XXXX....XXXX..",
    ".XXXXXXXXXXXXXXX",
    "XXXXXXXXXXXXXXXX",
    "XXXXXXXXXXXXXXXX",
    "XXXXXXXXXXXXXXXX",
    "XXXXXXXXXXXXXXXX",
    "XXXXXXXXXXXXXXXX",
    ".XXXXXXXXXXXXXX.",
    "..XXXXXXXXXXXX..",
    "...XXXXXXXXXX...",
    "....XXXXXXXX....",
    ".....XXXXXX.....",
    "......XXXX......",
    ".......XX.......",
    "................",
    "................",
]

RED = (255, 50, 50, 255)
TRANSPARENT = (0, 0, 0, 0)

grid = PixelGrid(16, 16)
for y, row in enumerate(HEART):
    for x, ch in enumerate(row):
        if ch == "X":
            grid.set_pixel(x, y, RED)

img = grid.to_pil_image()
scaled = img.resize((128, 128), resample=0)  # NEAREST
scaled.save(os.path.join(os.path.dirname(__file__), "sample_heart.png"))
print("Saved sample_heart.png")
```

**Step 2: Generate the sample**

```bash
python assets/sample_heart.py
```

**Step 3: Final commit**

```bash
git add assets/ main.py requirements.txt
git commit -m "feat: add sample asset generator and finalize project"
```

---

### Task 12: Run All Tests

**Step 1: Run full test suite**

```bash
python -m pytest tests/ -v
```

Expected: All tests pass.

**Step 2: Launch app for manual verification**

```bash
python main.py
```

Verify:
- Canvas renders with grid
- Drawing tools work (pen, eraser, fill, line, rect)
- Color palette selection works
- Frame add/duplicate/delete works
- Animation playback works
- Image > Blur/Scale/Rotate/Flip works
- Compression > Compress shows stats
- File > Save as PNG works
- Animation > Export GIF works

---

## Summary

| Task | Component | Test File |
|------|-----------|-----------|
| 1 | Project scaffolding | — |
| 2 | PixelGrid data model | test_pixel_data.py |
| 3 | RLE compression | test_compression.py |
| 4 | Image processing | test_image_processing.py |
| 5 | Animation timeline | test_animation.py |
| 6 | Drawing tools | test_tools.py |
| 7 | Color palette | — |
| 8 | Pixel canvas widget | — |
| 9 | UI panels | — |
| 10 | Main app window | — |
| 11 | Sample assets | — |
| 12 | Integration test | — |

**Total: ~12 tasks, building from data layer up through UI.**
