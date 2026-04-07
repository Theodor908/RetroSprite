"""Feature guide window for RetroSprite — neon themed scrollable help."""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from src.ui.theme import (
    BG_DEEP, BG_PANEL, BG_PANEL_ALT, BORDER, TEXT_PRIMARY, TEXT_SECONDARY,
    ACCENT_CYAN, ACCENT_MAGENTA, ACCENT_PURPLE, BUTTON_BG,
)

# Feature guide content: (category, [(feature, description), ...])
GUIDE_SECTIONS = [
    ("Drawing Tools", [
        ("Pen (P)", "Draw pixels with the current color. Hold and drag for freehand strokes. Supports symmetry, dithering, and pixel-perfect modes."),
        ("Eraser (E)", "Remove pixels (set to transparent). Works like Pen but clears instead. Supports symmetry and pixel-perfect modes."),
        ("Fill (F)", "Flood-fill a contiguous area with the current color. Tolerance-based. Press F with an active selection to fill just the selection."),
        ("Line (L)", "Click start point, drag to end point to draw a straight pixel line. Adjustable width."),
        ("Rectangle (R)", "Click and drag to draw a filled rectangle. Adjustable border width."),
        ("Ellipse (O)", "Click and drag to draw a filled ellipse/circle."),
        ("Polygon (N)", "Click to place vertices. Double-click or press Enter to close the shape. Supports filled or outline mode."),
        ("Rounded Rectangle (U)", "Click and drag to draw a rectangle with rounded corners. Adjustable corner radius via options bar."),
        ("Blur (B)", "Soften pixels by averaging neighboring colors. Drag over areas to blur. Adjustable size."),
        ("Color Picker (I)", "Click any pixel to set it as the current drawing color."),
        ("Gradient Fill", "Fill a region with a dithered gradient between two colors (Bayer pattern)."),
        ("Shading Ink ([ / ])", "Lighten or darken existing pixels. Use [ for darken, ] for lighten at cursor position."),
        ("Move (V)", "Move the current layer content. Click and drag to reposition all pixels. With a selection active, floats and moves only the selected pixels. Ctrl+drag snaps to grid when custom grid is visible."),
        ("Text (T)", "Click on canvas to open the text dialog. Type text, choose font (built-in bitmap or loaded TTF), adjust spacing. Live preview on canvas. Press OK to stamp text as pixels."),
    ]),
    ("Text Tool", [
        ("Built-in Fonts", "Two pixel-perfect bitmap fonts: Tiny (3x5) for HUD labels and Standard (5x7) for general text. Both cover full ASCII printable range."),
        ("TTF Font Loading", "Select 'Load Font...' in the font dropdown to load any .ttf or .otf file. TTF fonts are rendered with crisp 1-bit pixels (no anti-aliasing) for pixel art."),
        ("Letter Spacing", "Adjustable extra pixels between characters. Default 1px for bitmap fonts."),
        ("Multiline Text", "Type multiple lines in the dialog. All lines are rendered and stamped together."),
        ("Text + Transform", "After placing text, select it and press Ctrl+T to rotate, scale, or skew the stamped text."),
    ]),
    ("Selection Tools", [
        ("Select (S)", "Click and drag a rectangular selection. Shift=Add, Ctrl=Subtract, Shift+Ctrl=Intersect."),
        ("Magic Wand (W)", "Click to select all connected pixels of the same color. Adjustable tolerance in options bar."),
        ("Lasso (A)", "Freehand selection — draw a loop around pixels to select them."),
        ("Polygon Select (N)", "Click to place vertices for a polygonal selection area."),
        ("Custom Brush (Ctrl+B)", "Capture the current selection as a reusable brush shape."),
        ("Copy/Paste (Ctrl+C/V)", "Copy selection to clipboard, paste as floating transform. Ctrl+X cuts."),
        ("Delete Selection", "Press Delete to clear selected pixels to transparent."),
    ]),
    ("Selection Transform", [
        ("Enter Transform (Ctrl+T)", "Enter transform mode on the current selection, paste, or entire layer. Shows 8 handles: 4 corners + 4 midpoints."),
        ("Move (drag inside)", "Drag inside the bounding box to reposition. Ctrl+drag snaps to custom grid."),
        ("Scale — Uniform (drag corner)", "Drag a corner handle to scale uniformly (maintain aspect ratio)."),
        ("Scale — Non-uniform (Shift+corner)", "Hold Shift while dragging a corner to scale X and Y independently."),
        ("Scale — Axis (drag midpoint)", "Drag a midpoint handle to scale along one axis only."),
        ("Rotate (drag outside)", "Drag outside the bounding box to rotate freely around the pivot point."),
        ("Rotate — Snap (Shift+outside)", "Hold Shift while rotating to snap to 15-degree increments."),
        ("Skew (Ctrl+drag corner)", "Hold Ctrl and drag a corner to skew/shear. Top/bottom corners adjust horizontal skew, left/right corners adjust vertical skew."),
        ("Pivot (drag magenta dot)", "Drag the magenta pivot dot to reposition the center of rotation."),
        ("Context Bar", "Angle and Scale fields for precise numeric entry. Type a value and press Enter to apply."),
        ("Apply / Cancel", "Press Enter or click Apply to commit. Press Esc or click Cancel to discard. Switching tools auto-commits."),
        ("Auto on Paste", "Pasting (Ctrl+V) automatically enters transform mode with handles shown."),
    ]),
    ("Grid & Snapping", [
        ("Pixel Grid (Ctrl+H)", "Toggle the 1x1 pixel grid overlay. Visible at higher zoom levels. Color and min-zoom configurable in Grid Settings."),
        ("Custom Grid (Ctrl+G)", "Toggle an NxM tile grid overlay. Configurable width, height, offset, and RGBA color."),
        ("Grid Settings (Ctrl+Shift+G)", "Open the Grid Settings dialog to configure both grids. Settings are saved per-project."),
        ("Grid Toolbar Widget", "Click the grid indicator in the status bar to toggle custom grid. Right-click to open Grid Settings."),
        ("Grid Snapping (Ctrl+drag)", "Hold Ctrl while dragging in transform mode or with the Move tool to snap positions to custom grid boundaries. Paste and text placement auto-snap when the custom grid is visible."),
    ]),
    ("Symmetry", [
        ("Symmetry Modes (M)", "Cycle through: Off, Horizontal, Vertical, Both. Mirrors drawing across the symmetry axis. Works with Pen, Eraser, and Blur tools."),
        ("Movable Axis", "When symmetry is on, a dashed magenta guide line shows the axis position. Drag the line to reposition it."),
        ("Precise Axis Position", "Right-click on the symmetry axis line to open a popup for exact pixel coordinates."),
        ("Axis Persistence", "Symmetry axis position is saved per-project in .retro files. Resets to center when canvas is resized."),
    ]),
    ("Navigation", [
        ("Hand (H)", "Click and drag to pan/scroll the canvas."),
        ("Zoom (Ctrl+Scroll)", "Scroll while holding Ctrl to zoom in/out. Zooms toward cursor position."),
        ("Zoom (+/-)", "Press + or = to zoom in, - to zoom out."),
        ("Scroll", "Mouse wheel scrolls vertically. Alt+wheel scrolls horizontally."),
    ]),
    ("Drawing Modes", [
        ("Pixel Perfect (G)", "Automatically removes L-shaped corners for clean 1px lines. Toggle with G key."),
        ("Dithering (D)", "Apply checkerboard or ordered dither patterns while drawing. Cycle patterns with D key."),
        ("Tiled Mode (View menu)", "Preview how your sprite tiles seamlessly. Draw across tile edges. Supports X, Y, or Both directions."),
        ("Ink Modes", "Normal draws normally. Alpha Lock only paints on existing pixels. Behind draws under existing pixels. Cycle via options bar."),
    ]),
    ("Layers", [
        ("Add/Delete Layers", "Use the timeline panel buttons or Edit menu. + Layer button adds a new layer."),
        ("Blend Modes", "Each layer can use: Normal, Multiply, Screen, Overlay, Addition, Subtract, Darken, Lighten, Difference."),
        ("Layer Groups", "Edit > Add Group creates a folder. Drag layers into groups for organization."),
        ("Opacity", "Adjust layer transparency with the opacity slider in the timeline."),
        ("Visibility/Lock", "Eye icon toggles visibility. Lock icon prevents accidental edits."),
        ("Layer Effects (FX)", "Click FX button per layer: Outline, Drop Shadow, Inner Shadow, Hue/Sat, Gradient Map, Glow, Pattern Overlay."),
    ]),
    ("Animation", [
        ("Frames", "Add, delete, duplicate frames in the timeline. Click frame headers to navigate."),
        ("Playback", "Animation > Play/Stop or use the transport bar. Forward, Reverse, Ping-Pong modes."),
        ("Onion Skin", "Ghost previous/next frames to aid animation. Toggle in Animation menu. Adjustable range."),
        ("Frame Tags", "Label frame ranges (e.g., 'walk', 'idle') for organization and selective export."),
        ("Frame Duration", "Set per-frame timing (ms) for variable-speed animations. Click duration in timeline to edit."),
    ]),
    ("Image Processing", [
        ("Scale 2x / 0.5x", "Double or halve the canvas resolution."),
        ("Rotate 90/180", "Rotate the entire canvas."),
        ("Flip H / V", "Mirror the canvas horizontally or vertically."),
        ("Brightness/Contrast", "Adjust image brightness and contrast (+/-)."),
        ("Posterize", "Reduce color levels for a stylized look."),
    ]),
    ("Color & Palette", [
        ("Palette Panel", "Click colors to select. Right-click to edit. Drag to reorder."),
        ("Color Ramp", "Edit > Generate Color Ramp — interpolate between two colors (RGB/HSV)."),
        ("Indexed Mode", "Image > Convert to Indexed for palette-constrained editing with median-cut quantization."),
        ("Import/Export Palette", "Edit menu: GPL, PAL, HEX, ASE palette formats."),
    ]),
    ("File & Export", [
        ("Save/Open Project (.retro)", "File > Save/Open (Ctrl+S/Ctrl+O) preserves layers, frames, effects, grid settings, symmetry axis, and tool settings."),
        ("Export (Ctrl+Shift+E)", "Unified export dialog: PNG, GIF, WebP, APNG, Sprite Sheet (PNG + JSON), Frame Sequence. Scalable 1-16x."),
        ("Import Animated", "Import GIF, APNG, WebP (animated), PNG sequence, or Sprite Sheet (JSON or manual grid) as frames."),
        ("Import Aseprite", "Open .ase/.aseprite files with layers, cels, and palette preserved."),
        ("Import PSD", "Open Photoshop files with layer structure and blend modes."),
        ("Reference Image (Ctrl+R)", "Load a semi-transparent guide image overlay. Positionable, scalable, persistent across sessions."),
    ]),
    ("Tilemap", [
        ("Tilemap Layers", "Edit > New Tilemap Layer — paint with reusable tiles on a grid."),
        ("Tile Editing", "Pixel mode edits individual pixels. Tile mode stamps whole tiles. Toggle with Tab."),
        ("Tile Mode Tools", "Pen (B) — stamp selected tile. Eraser (E) — clear cell. Fill (F) — flood-fill connected cells with same tile. Pick (I) — sample tile from canvas."),
        ("Tiles Panel", "Browse and select tiles from the tileset in the right sidebar."),
    ]),
    ("Other", [
        ("Undo/Redo (Ctrl+Z / Ctrl+Y)", "Undo history (up to 10 steps) for the current session."),
        ("Auto-Save", "Project auto-saves every 60 seconds to prevent data loss."),
        ("Keyboard Shortcuts", "Edit > Keyboard Shortcuts to customize all keybindings. Stored in ~/.retrosprite/keybindings.json."),
    ]),
    ("Plugin Development", [
        ("Getting Started",
         "Create a .py file in ~/.retrosprite/plugins/. "
         "Define register(api) to set up your plugin and optionally unregister(api) for cleanup. "
         "Add PLUGIN_INFO = {'name': 'My Plugin'} for display."),
        ("api.register_tool(name, cls)",
         "Register a custom drawing tool. Subclass PluginTool and override "
         "on_click(api, x, y), on_drag(api, x, y), on_release(api, x, y). "
         "Optional: on_preview() for overlays, on_options_bar() for settings UI."),
        ("api.register_filter(name, func)",
         "Register an image filter. func receives a PixelGrid and must return a new PixelGrid. "
         "Appears under Plugins menu as 'Filter: name'."),
        ("api.register_effect(name, func, params)",
         "Register a non-destructive layer effect. func(pixels, params) -> pixels. "
         "params dict defines defaults (e.g., {'radius': 3})."),
        ("api.register_menu_item(label, callback)",
         "Add a custom entry to the Plugins menu. callback() is called on click."),
        ("api.on(event, callback)",
         "Subscribe to events. Events: before_draw, after_draw, before_save, after_save, "
         "frame_change, layer_change, tool_change, color_change, and more. "
         "Return False from before_* events to cancel the action."),
        ("api.off(event, callback)",
         "Unsubscribe a previously registered event listener."),
        ("api.emit(event, payload)",
         "Fire a custom event. payload is a dict passed to all listeners."),
    ]),
    ("Scripting API — Project", [
        ("api.new_project(w, h, fps=12)",
         "Create a new blank project with given dimensions."),
        ("api.load_project(path)",
         "Load a .retro project file."),
        ("api.save_project(path)",
         "Save current project to a .retro file."),
        ("api.current_frame_pixels()",
         "Get the flattened PixelGrid of the current frame."),
        ("api.current_layer()",
         "Get the active Layer object of the current frame."),
        ("api.get_frame(index)",
         "Get a Frame object by index."),
        ("api.add_frame() / api.remove_frame(i)",
         "Add a new frame at the end, or remove frame at index."),
        ("api.add_layer(name) / api.remove_layer(i)",
         "Add a named layer to all frames, or remove layer at index from all frames."),
    ]),
    ("Scripting API — Export", [
        ("api.export_png(path, frame=0, scale=1)",
         "Export a single frame as PNG. Optional layer param to export one layer."),
        ("api.export_gif(path, scale=1)",
         "Export all frames as animated GIF with per-frame durations."),
        ("api.export_webp(path, scale=1)",
         "Export as lossless animated WebP."),
        ("api.export_apng(path, scale=1)",
         "Export as animated PNG (APNG)."),
        ("api.export_sheet(path, scale=1, columns=0)",
         "Export sprite sheet PNG + JSON metadata. columns=0 auto-calculates layout."),
        ("api.export_frames(path, scale=1)",
         "Export each frame as numbered PNG files."),
    ]),
    ("Scripting API — Processing", [
        ("api.apply_filter(func, frame, layer)",
         "Apply a pixel transform function to a layer. func(PixelGrid) -> PixelGrid. "
         "Respects active selection if in GUI mode."),
        ("api.apply_effect(layer_idx, type, params)",
         "Add a non-destructive effect to a layer. Types: outline, drop_shadow, "
         "inner_shadow, hue_sat, gradient_map, glow, pattern."),
        ("api.push_undo(label)",
         "Save undo checkpoint before making changes (GUI mode only)."),
        ("api.convert_to_indexed(num_colors)",
         "Convert project to indexed color mode with median-cut quantization."),
        ("api.convert_to_rgba()",
         "Convert project back from indexed to full RGBA mode."),
    ]),
]


def show_feature_guide(parent=None):
    """Open the feature guide window."""
    win = tk.Toplevel(parent)
    win.title("RetroSprite — Feature Guide")
    win.geometry("640x600")
    win.configure(bg=BG_DEEP)
    win.resizable(True, True)

    # Title
    title = tk.Label(win, text="Feature Guide", font=("Consolas", 14, "bold"),
                     fg=ACCENT_CYAN, bg=BG_DEEP)
    title.pack(pady=(12, 4))
    subtitle = tk.Label(win, text="Quick reference for all tools and features",
                        font=("Consolas", 9), fg=TEXT_SECONDARY, bg=BG_DEEP)
    subtitle.pack(pady=(0, 8))

    # Search bar
    search_frame = tk.Frame(win, bg=BG_DEEP)
    search_frame.pack(fill="x", padx=16, pady=(0, 8))
    search_lbl = tk.Label(search_frame, text="Search:", font=("Consolas", 9),
                          fg=TEXT_SECONDARY, bg=BG_DEEP)
    search_lbl.pack(side="left", padx=(0, 6))
    search_var = tk.StringVar()
    search_entry = tk.Entry(search_frame, textvariable=search_var,
                            font=("Consolas", 9), bg=BG_PANEL, fg=TEXT_PRIMARY,
                            insertbackground=ACCENT_CYAN, relief="flat",
                            highlightthickness=1, highlightcolor=ACCENT_CYAN,
                            highlightbackground=BORDER)
    search_entry.pack(side="left", fill="x", expand=True)
    match_lbl = tk.Label(search_frame, text="", font=("Consolas", 8),
                         fg=TEXT_SECONDARY, bg=BG_DEEP)
    match_lbl.pack(side="left", padx=(6, 0))

    # Scrollable content
    container = tk.Frame(win, bg=BG_DEEP)
    container.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    canvas = tk.Canvas(container, bg=BG_DEEP, highlightthickness=0)
    scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview,
                               style="Neon.Vertical.TScrollbar")
    inner = tk.Frame(canvas, bg=BG_DEEP)

    inner.bind("<Configure>",
               lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas_window = canvas.create_window((0, 0), window=inner, anchor="nw")
    canvas.bind("<Configure>",
                lambda e: canvas.itemconfig(canvas_window, width=e.width))
    canvas.configure(yscrollcommand=scrollbar.set)

    scrollbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)

    # Mousewheel scrolling
    def _on_mousewheel(event):
        canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

    canvas.bind("<MouseWheel>", _on_mousewheel)
    inner.bind("<MouseWheel>", _on_mousewheel)

    # Track all widgets for search filtering
    _all_widgets = []  # [(section_header, separator, [(row, name_lbl, desc_lbl)])]

    def _build_content():
        """Build all section/feature widgets."""
        for section_name, features in GUIDE_SECTIONS:
            header = tk.Label(inner, text=section_name,
                              font=("Consolas", 11, "bold"),
                              fg=ACCENT_MAGENTA, bg=BG_DEEP, anchor="w")
            header.pack(fill="x", padx=8, pady=(12, 4))
            header.bind("<MouseWheel>", _on_mousewheel)

            sep = tk.Frame(inner, height=1, bg=ACCENT_PURPLE)
            sep.pack(fill="x", padx=8, pady=(0, 4))

            rows = []
            for feat_name, feat_desc in features:
                row = tk.Frame(inner, bg=BG_PANEL, bd=0)
                row.pack(fill="x", padx=12, pady=2)
                row.bind("<MouseWheel>", _on_mousewheel)
                row.columnconfigure(1, weight=1)

                name_lbl = tk.Label(row, text=feat_name,
                                    font=("Consolas", 9, "bold"),
                                    fg=ACCENT_CYAN, bg=BG_PANEL, anchor="nw")
                name_lbl.grid(row=0, column=0, padx=(6, 4), pady=3, sticky="nw")
                name_lbl.bind("<MouseWheel>", _on_mousewheel)

                desc_lbl = tk.Label(row, text=feat_desc,
                                    font=("Consolas", 8),
                                    fg=TEXT_PRIMARY, bg=BG_PANEL, anchor="nw",
                                    justify="left")
                desc_lbl.grid(row=0, column=1, padx=(0, 6), pady=3, sticky="nwe")
                desc_lbl.bind("<MouseWheel>", _on_mousewheel)

                def _update_wrap(event, r=row, nl=name_lbl, dl=desc_lbl):
                    nl.update_idletasks()
                    avail = event.width - nl.winfo_width() - 16
                    dl.configure(wraplength=max(avail, 100))
                row.bind("<Configure>", _update_wrap)

                rows.append((row, feat_name, feat_desc))

            _all_widgets.append((header, sep, rows))

    def _apply_filter(*_args):
        """Show/hide features based on search query."""
        query = search_var.get().strip().lower()
        total_matches = 0

        for header, sep, rows in _all_widgets:
            section_has_match = False
            for row_frame, feat_name, feat_desc in rows:
                if not query or query in feat_name.lower() or query in feat_desc.lower():
                    row_frame.pack(fill="x", padx=12, pady=2)
                    section_has_match = True
                    total_matches += 1
                else:
                    row_frame.pack_forget()

            if section_has_match or not query:
                header.pack(fill="x", padx=8, pady=(12, 4))
                sep.pack(fill="x", padx=8, pady=(0, 4))
            else:
                header.pack_forget()
                sep.pack_forget()

        if query:
            match_lbl.config(text=f"{total_matches} found")
        else:
            match_lbl.config(text="")

        # Reset scroll to top on search
        canvas.yview_moveto(0)

    _build_content()
    search_var.trace_add("write", _apply_filter)

    # Close button
    close_btn = tk.Button(win, text="Close", width=10,
                          font=("Consolas", 9), bg=BUTTON_BG, fg=TEXT_PRIMARY,
                          relief="flat", command=win.destroy)
    close_btn.pack(pady=(0, 8))

    # Focus search on open
    search_entry.focus_set()
    win.lift()
    win.focus_force()
