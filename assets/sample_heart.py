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

grid = PixelGrid(16, 16)
for y, row in enumerate(HEART):
    for x, ch in enumerate(row):
        if ch == "X":
            grid.set_pixel(x, y, RED)

img = grid.to_pil_image()
scaled = img.resize((128, 128), resample=0)  # NEAREST
output_path = os.path.join(os.path.dirname(__file__), "sample_heart.png")
scaled.save(output_path)
print(f"Saved {output_path}")
