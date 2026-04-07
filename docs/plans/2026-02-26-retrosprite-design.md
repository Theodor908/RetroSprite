# RetroSprite - Pixel Art Creator & Animator

## Design Document

**Date:** 2026-02-26
**Platform:** Python Desktop (Tkinter + Pillow)
**Theme:** Retro Pixel Art

## Core Concept

A desktop pixel art editor where users can:
- Draw pixel art on a grid canvas (configurable: 16x16, 32x32, 64x64)
- Process images with blur, scale, rotate, crop, and pixel-art-specific filters
- Compress artwork using a custom RLE implementation with visual stats
- Animate by creating multiple frames with sprite animation playback
- Export as PNG, animated GIF, or RLE-compressed custom format

## Tech Stack

- **GUI:** Tkinter (standard library)
- **Imaging:** Pillow (PIL)
- **GIF Export:** imageio
- **Compression:** Custom RLE implementation

## UI Layout

```
+-------------------------------------------------------------+
|  Menu Bar: File | Edit | Image | Animation | Compression    |
+------+----------------------------------+-------------------+
|      |                                  |                   |
| Tool |     Pixel Canvas                 |  Right Panel      |
| Bar  |     (zoomable grid)              |  - Color Picker   |
|      |                                  |  - Palette        |
| Pen  |                                  |  - Frame List     |
| Fill |                                  |  - Animation      |
| Erase|                                  |    Preview        |
| Pick |                                  |  - Compression    |
| Select                                  |    Stats          |
| Line |                                  |                   |
| Rect |                                  |                   |
+------+----------------------------------+-------------------+
|  Status Bar: Canvas size | Zoom | Frame | Tool              |
+-------------------------------------------------------------+
```

## Image Processing Operations

| Operation | Method | Notes |
|-----------|--------|-------|
| Blur | GaussianBlur / box blur | Optional "pixel blur" (block averaging) |
| Scale | Nearest-neighbor resize | 2x/4x/8x with crisp edges |
| Rotate | 90/180/270 + free rotation | Nearest-neighbor interpolation |
| Crop | Selection-based | Snap to pixel grid |
| Flip | Horizontal/vertical | One-click sprite mirroring |
| Brightness/Contrast | ImageEnhance | Slider controls |
| Posterize | Reduce color depth | Retro palette creation |

## RLE Compression

- Row-by-row encoding of pixel color data
- Visual display of encoded run-length pairs
- Stats panel showing original vs compressed size and ratio
- Custom `.rle` file format for save/load
- Decode capability to restore editable pixel art

Format: `[R,R,R,R,B,B,G,G,G,G,G,G]` -> `[(4,R), (2,B), (6,G)]`

## Animation System

- Frame list with add/remove/duplicate/reorder
- Onion skinning (translucent overlay of previous frame)
- Playback controls with adjustable FPS (1-30)
- Preview panel in right sidebar
- Animated GIF export via imageio

## File Structure

```
MSProject/
├── main.py                  # Entry point
├── requirements.txt         # pillow, imageio
├── assets/                  # Sample sprites, palettes
├── src/
│   ├── app.py              # Main application window
│   ├── canvas.py           # Pixel canvas widget
│   ├── tools.py            # Drawing tools
│   ├── image_processing.py # Blur, scale, rotate, crop
│   ├── compression.py      # RLE encode/decode
│   ├── animation.py        # Frame management, playback, GIF export
│   ├── palette.py          # Color picker and palette management
│   └── ui/
│       ├── toolbar.py      # Left tool bar
│       ├── right_panel.py  # Right panel widgets
│       └── dialogs.py      # File dialogs, settings
└── docs/
    └── plans/
```

## Dependencies

- Python 3.8+
- Pillow >= 9.0
- imageio >= 2.20

## Decisions

- Tkinter chosen for minimal dependencies and retro aesthetic fit
- RLE chosen as compression algorithm due to natural fit with pixel art
- Nearest-neighbor interpolation used throughout for pixel-perfect rendering
