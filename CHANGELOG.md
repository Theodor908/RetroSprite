# Changelog

All notable changes to RetroSprite will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-03-26

### Added
- 13 drawing tools: Pen, Eraser, Fill, Line, Rectangle, Ellipse, Polygon, Rounded Rectangle, Blur, Color Picker, Gradient Fill, Shading Ink, Move
- Selection tools: Rectangle Select, Magic Wand, Lasso, Custom Brush
- Layer system with blend modes (Normal, Multiply, Screen, Overlay, Addition, Subtract, Darken, Lighten, Difference)
- Layer groups and clipping masks
- 7 non-destructive layer effects: Outline, Drop Shadow, Inner Shadow, Hue/Sat, Gradient Map, Glow, Pattern Overlay
- Frame-by-frame animation with timeline panel
- Onion skinning (past/future frames)
- Frame tags for organizing animation sections
- Playback modes: Forward, Reverse, Ping-Pong
- Drawing modes: Symmetry (horizontal/vertical/both), Pixel Perfect, Dithering, Tiled Mode
- Ink modes: Normal, Alpha Lock, Behind
- Built-in palettes: Pico-8, DB16, DB32, Commodore 64, NES, and more
- Color ramp generation (RGB/HSV interpolation)
- Indexed color mode with median-cut quantization
- Palette import/export: GPL, PAL, HEX, ASE formats
- Native `.retro` project format preserving layers, frames, and settings
- Export: PNG, animated GIF, WebP, APNG, Sprite Sheet (PNG + JSON metadata), Frame Sequence
- Import: Aseprite (.ase/.aseprite), Photoshop (.psd)
- Krita-style reference image overlay with move, resize, opacity, and project persistence
- Tilemap layers with reusable tile palettes and pixel/tile editing modes
- RotSprite high-quality pixel art rotation
- Plugin system: custom tools, filters, effects, menu items
- Scripting API for programmatic access to project, layers, frames, and export
- CLI batch mode for headless export
- Feature Guide (Help menu) with searchable reference for all tools and APIs
- Per-tool settings persistence
- Auto-save every 60 seconds
- Customizable keyboard shortcuts
- Neon-themed UI with Phosphor icons
