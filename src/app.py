"""Main application window for RetroSprite."""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, simpledialog
import os
import sys
from PIL import Image, ImageTk

from src.pixel_data import PixelGrid
from src.canvas import PixelCanvas
from src.tools import (
    PenTool, EraserTool, FillTool, LineTool, RectTool, BlurTool,
    EllipseTool, MagicWandTool, ShadingInkTool, GradientFillTool,
    LassoTool, PolygonTool, RoundedRectTool, DITHER_PATTERNS,
    TextTool,
)
import numpy as np
from src.animation import AnimationTimeline
from src.grid import GridSettings
from src.palette import Palette
from src.project import save_project, load_project
from src.keybindings import KeybindingsManager
from src.scripting import RetroSpriteAPI
from src.plugins import load_all_plugins
from src.ui.toolbar import Toolbar
from src.ui.right_panel import RightPanel
from src.ui.options_bar import OptionsBar
from src.tool_settings import ToolSettingsManager
from src.ui.timeline import TimelinePanel
from src.ui.dialogs import (
    ask_canvas_size, ask_save_file, ask_open_file,
    ask_export_gif, ask_startup, ask_save_before, show_info, show_error,
    ask_color_ramp
)
from src.ui.theme import (
    BG_DEEP, BG_PANEL, BG_PANEL_ALT, BORDER, TEXT_PRIMARY, TEXT_SECONDARY,
    ACCENT_CYAN, ACCENT_MAGENTA, BUTTON_BG, BUTTON_HOVER,
    style_menu, style_scrollbar, style_checkbutton, setup_ttk_theme,
    get_mode, set_mode,
)

# Mixin imports
from src.input_handler import InputHandlerMixin
from src.file_ops import FileOpsMixin
from src.rotation_handler import RotationMixin
from src.tilemap_editor import TilemapEditorMixin
from src.layer_animation import LayerAnimationMixin


class RetroSpriteApp(InputHandlerMixin, FileOpsMixin, RotationMixin,
                     TilemapEditorMixin, LayerAnimationMixin):
    """Main application class for RetroSprite pixel art editor.

    Uses mixin composition to keep focused modules:
    - InputHandlerMixin: canvas click/drag/release, tool dispatch, selection
    - FileOpsMixin: save/load/export/import, auto-save, palette I/O
    - RotationMixin: rotation mode state machine + context bar
    - TilemapEditorMixin: tilemap layer creation, tile editing
    - LayerAnimationMixin: frames, layers, playback, filters, effects
    """

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("RetroSprite - Pixel Art Creator")
        self._set_app_icon()
        self.root.configure(bg=BG_DEEP)
        setup_ttk_theme(self.root)
        default_w, default_h = 1200, 800
        self.root.update_idletasks()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        win_w = min(default_w, int(screen_w * 0.9))
        win_h = min(default_h, int(screen_h * 0.9))
        x = (screen_w - win_w) // 2
        y = (screen_h - win_h) // 2
        self.root.geometry(f"{win_w}x{win_h}+{x}+{y}")
        self.root.minsize(900, 650)

        # Show startup dialog
        self.root.withdraw()
        self.root.update_idletasks()  # Process the withdraw before dialog
        startup = ask_startup(self.root)
        if startup is None:
            self.root.destroy()
            raise SystemExit
        self.root.deiconify()

        # Core state
        self._project_path = None  # path to current .retro file
        if startup["action"] == "open":
            ext = os.path.splitext(startup["path"])[1].lower()
            if ext in ('.ase', '.aseprite'):
                from src.aseprite_import import load_aseprite
                self.timeline, palette = load_aseprite(startup["path"])
                self.palette = Palette("Pico-8")
                self.palette.colors = palette.colors
                self.palette.selected_index = 0
            elif ext == '.psd':
                from src.psd_import import load_psd
                self.timeline, palette = load_psd(startup["path"])
                self.palette = Palette("Pico-8")
                self.palette.colors = palette.colors
                self.palette.selected_index = 0
            else:
                self.timeline, self.palette, _tool_settings_data, _, _ = load_project(startup["path"])
            self._project_path = startup["path"] if ext == '.retro' else None
            from src.recents import update_recents
            update_recents(startup["path"])
        else:
            w, h = startup["size"]
            self.timeline = AnimationTimeline(w, h)
            self.palette = Palette("Pico-8")
        self.current_tool_name = "Pen"
        self._tools = {
            "Pen": PenTool(),
            "Eraser": EraserTool(),
            "Fill": FillTool(),
            "Line": LineTool(),
            "Rect": RectTool(),
            "Blur": BlurTool(),
            "Ellipse": EllipseTool(),
            "Wand": MagicWandTool(),
            "ShadingInk": ShadingInkTool(),
            "GradientFill": GradientFillTool(),
            "Lasso": LassoTool(),
            "Polygon": PolygonTool(),
            "RoundedRect": RoundedRectTool(),
            "Text": TextTool(),
        }
        # Scripting API
        self.api = RetroSpriteAPI(
            timeline=self.timeline, palette=self.palette, app=self
        )
        self._tool_size = 1
        if startup["action"] == "open" and ext == '.retro':
            self._tool_settings = ToolSettingsManager.from_dict(_tool_settings_data)
        else:
            self._tool_settings = ToolSettingsManager()
        self._line_start = None
        self._rect_start = None
        self._roundrect_start = None
        self._corner_radius = 2
        self._ellipse_start = None
        self._hand_last = None  # last mouse position for Hand panning
        self._move_start = None
        self._move_snapshot = None
        self._select_start = None
        self._selection_pixels = None   # set[tuple[int,int]] or None — unified for all tools
        self._custom_brush_mask = None   # set[tuple[int,int]] relative offsets or None
        self._paste_origin = (0, 0)     # origin for pasting copied selection
        self._wand_tolerance = 32  # 0-255 color distance threshold
        self._clipboard = None  # PixelGrid or None
        self._lasso_points = []    # list of (x, y) during lasso drag
        self._polygon_points = []  # list of (x, y) for polygon vertices
        self._polygon_closing = False  # prevents re-entry during close
        self._pasting = False   # floating paste mode active
        self._paste_pos = (0, 0)  # current floating paste position
        self._playing = False
        self._play_after_id = None
        self._playback_mode = "forward"  # forward, reverse, pingpong
        self._pingpong_direction = 1
        self._onion_skin = False
        self._undo_stack: list[PixelGrid] = []  # max 10
        self._redo_stack: list[PixelGrid] = []
        self._UNDO_LIMIT = 10

        # Phase 2: New drawing mode state
        self._symmetry_mode = "off"  # off, horizontal, vertical, both
        self._symmetry_axis_x = self.timeline.width // 2
        self._symmetry_axis_y = self.timeline.height // 2
        self._symmetry_axis_dragging = None  # "x", "y", or None
        self._pixel_perfect = False
        self._pp_last_points = []
        self._dither_pattern = "none"
        self._tiled_mode = "off"  # off, x, y, both
        self._ink_mode = "normal"  # normal, alpha_lock, behind
        self._grid_settings = GridSettings()
        self._fill_mode = "normal"  # normal, contour

        self._return_to_menu = False

        # Auto-save
        self._dirty = False
        self._auto_save_interval = 60000  # 60 seconds

        # Reference image overlay (Krita-style positionable)
        self._reference = None  # ReferenceImage or None

        # Reference drag state
        self._ref_dragging = False
        self._ref_drag_start = None  # (x, y) at drag start
        self._ref_drag_origin = None  # (ref.x, ref.y) at drag start

        # Layer effects display toggle
        self._display_effects = True
        # Export dialog last-used settings
        self._export_settings = {}

        # Rotation mode state
        self._rotation_mode = False
        self._rotation_angle = 0.0
        self._rotation_pivot = None       # (x, y) grid coords
        self._rotation_algorithm = "rotsprite"
        self._rotation_original = None    # saved pixel array for cancel
        self._rotation_bounds = None      # (x, y, w, h) grid coords
        self._rotation_dragging = None    # "corner" or "pivot" or None
        self._rotation_drag_start_angle = 0.0  # angle at drag start
        self._rotation_mouse_start_angle = 0.0  # mouse angle at drag start
        self._rotation_context_frame = None  # tk.Frame for context bar

        # Selection transform state
        self._selection_transform = None   # SelectionTransform or None
        self._transform_context_frame = None
        self._transform_drag_zone = None
        self._transform_drag_start = None
        self._transform_start_state = None
        self._transform_mouse_start_angle = 0.0
        self._transform_ctrl_held = False
        self._transform_shift_held = False

        # Text tool state
        self._text_mode = False
        self._text_string = ""
        self._text_pos = (0, 0)
        self._text_cursor_pos = 0
        self._text_cursor_visible = True
        self._text_cursor_after_id = None
        self._text_loaded_fonts = {}
        self._text_context_frame = None
        self._text_spacing = 1
        self._text_line_height = 2
        self._text_align = "left"
        self._text_font_size = 12
        self._text_dragging = False

        # Keybindings
        self.keybindings = KeybindingsManager()

        self._build_menu()
        self._build_ui()
        self._bind_keys()
        self._refresh_all()
        # Load plugins
        self._plugins = load_all_plugins(self.api)
        self._build_plugins_menu()
        if self.api._plugin_tools:
            self.toolbar.add_plugin_tools(self.api._plugin_tools)
        self._schedule_auto_save()
        if self._project_path:
            self.root.title(f"RetroSprite - {self._project_path}")

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def run(self):
        self.root.mainloop()
        return self._return_to_menu

    def _set_app_icon(self):
        """Set the window/taskbar icon from assets/icon.png."""
        if getattr(sys, 'frozen', False):
            base = sys._MEIPASS
        else:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        icon_path = os.path.join(base, 'assets', 'icon.png')
        if os.path.exists(icon_path):
            icon_img = Image.open(icon_path)
            self._app_icon = ImageTk.PhotoImage(icon_img)
            self.root.iconphoto(True, self._app_icon)

    # --- UI Building ---

    def _build_menu(self):
        menubar = tk.Menu(self.root, bg=BG_PANEL, fg=TEXT_PRIMARY,
                          activebackground=ACCENT_CYAN,
                          activeforeground=BG_DEEP,
                          font=("Consolas", 9))

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="New", command=self._new_canvas)
        file_menu.add_separator()
        file_menu.add_command(label="Save Project", command=self._save_project,
                              accelerator="Ctrl+S")
        file_menu.add_command(label="Save Project As...",
                              command=self._save_project_as)
        file_menu.add_command(label="Open Project...",
                              command=self._open_project, accelerator="Ctrl+O")
        file_menu.add_separator()
        file_menu.add_command(label="Open Image...", command=self._open_image)
        file_menu.add_command(label="Import Animation...",
                              command=self._import_animation)
        file_menu.add_command(label="Export...", command=self._show_export_dialog,
                              accelerator="Ctrl+Shift+E")
        file_menu.add_separator()
        file_menu.add_command(label="Load Reference Image...",
                              command=self._load_reference_image,
                              accelerator="Ctrl+R")
        file_menu.add_command(label="Toggle Reference Visibility",
                              command=self._toggle_reference)
        file_menu.add_command(label="Clear Reference Image",
                              command=self._clear_reference)

        # Reference opacity submenu
        self._ref_opacity_var = tk.DoubleVar(value=0.3)
        opacity_menu = tk.Menu(file_menu, tearoff=0,
                               bg=BG_PANEL, fg=TEXT_PRIMARY,
                               activebackground=ACCENT_CYAN,
                               activeforeground=BG_DEEP)
        for pct in (10, 20, 30, 50, 75, 100):
            val = pct / 100.0
            opacity_menu.add_radiobutton(
                label=f"{pct}%", variable=self._ref_opacity_var,
                value=val, command=lambda v=val: self._set_ref_opacity(v))
        file_menu.add_cascade(label="Reference Opacity", menu=opacity_menu)
        file_menu.add_command(label="Return to Menu",
                              command=self._return_to_menu_action)
        file_menu.add_command(label="Exit", command=self._on_close)
        menubar.add_cascade(label="File", menu=file_menu)

        # Edit menu
        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="Undo", command=self._undo,
                              accelerator="Ctrl+Z")
        edit_menu.add_command(label="Redo", command=self._redo,
                              accelerator="Ctrl+Y")
        edit_menu.add_separator()
        edit_menu.add_command(label="Copy", command=self._copy_selection,
                              accelerator="Ctrl+C")
        edit_menu.add_command(label="Paste", command=self._paste_clipboard,
                              accelerator="Ctrl+V")
        edit_menu.add_separator()
        edit_menu.add_command(label="Capture Brush", command=self._capture_brush,
                              accelerator="Ctrl+B")
        edit_menu.add_command(label="Reset Brush", command=self._reset_brush)
        edit_menu.add_separator()
        edit_menu.add_command(label="Clear Canvas", command=self._clear_canvas)
        edit_menu.add_separator()
        edit_menu.add_command(label="Add Group", command=self._add_group)
        edit_menu.add_command(label="New Tilemap Layer...",
                              command=self._new_tilemap_layer_dialog)
        edit_menu.add_separator()
        edit_menu.add_command(label="Generate Color Ramp...",
                              command=self._show_color_ramp_dialog)
        from src.palette import RETRO_PALETTES
        palette_submenu = tk.Menu(edit_menu, tearoff=0)
        for pname in RETRO_PALETTES:
            palette_submenu.add_command(
                label=pname,
                command=lambda n=pname: self._load_builtin_palette(n))
        edit_menu.add_cascade(label="Load Built-in Palette", menu=palette_submenu)
        edit_menu.add_command(label="Import Palette...",
                              command=self._import_palette)
        edit_menu.add_command(label="Export Palette...",
                              command=self._export_palette)
        edit_menu.add_separator()
        edit_menu.add_command(label="Keyboard Shortcuts...",
                              command=self._show_keybindings_dialog)
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
        image_menu.add_separator()
        image_menu.add_command(label="Gradient Fill", command=self._apply_gradient_fill)
        image_menu.add_separator()
        image_menu.add_command(label="Convert to Indexed...", command=self._convert_to_indexed)
        image_menu.add_command(label="Convert to RGBA", command=self._convert_to_rgba)
        menubar.add_cascade(label="Image", menu=image_menu)

        # Animation menu
        anim_menu = tk.Menu(menubar, tearoff=0)
        anim_menu.add_command(label="Play", command=self._play_animation)
        anim_menu.add_command(label="Stop", command=self._stop_animation)
        anim_menu.add_separator()
        anim_menu.add_command(label="Toggle Onion Skin",
                              command=self._toggle_onion_skin)
        anim_menu.add_separator()
        anim_menu.add_command(label="Add Tag...", command=self._add_tag_dialog)
        anim_menu.add_separator()
        # Export GIF removed — use unified Export dialog (Ctrl+Shift+E)
        menubar.add_cascade(label="Animation", menu=anim_menu)

        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        self._pixel_grid_var = tk.BooleanVar(value=True)
        self._custom_grid_var = tk.BooleanVar(value=False)
        view_menu.add_checkbutton(label="Show Pixel Grid",
                                  variable=self._pixel_grid_var,
                                  command=self._toggle_pixel_grid,
                                  accelerator="Ctrl+H")
        view_menu.add_checkbutton(label="Show Custom Grid",
                                  variable=self._custom_grid_var,
                                  command=self._toggle_custom_grid,
                                  accelerator="Ctrl+G")
        view_menu.add_command(label="Grid Settings...",
                              command=self._show_grid_settings,
                              accelerator="Ctrl+Shift+G")
        view_menu.add_separator()
        self._tiled_var = tk.StringVar(value="off")
        view_menu.add_radiobutton(label="Tiled Off", variable=self._tiled_var,
                                  value="off", command=self._on_tiled_mode_change)
        view_menu.add_radiobutton(label="Tiled X", variable=self._tiled_var,
                                  value="x", command=self._on_tiled_mode_change)
        view_menu.add_radiobutton(label="Tiled Y", variable=self._tiled_var,
                                  value="y", command=self._on_tiled_mode_change)
        view_menu.add_radiobutton(label="Tiled Both", variable=self._tiled_var,
                                  value="both", command=self._on_tiled_mode_change)
        view_menu.add_separator()
        self._display_effects_var = tk.BooleanVar(value=True)
        view_menu.add_checkbutton(label="Display Layer Effects",
                                  variable=self._display_effects_var,
                                  command=self._on_display_effects_toggle)
        menubar.add_cascade(label="View", menu=view_menu)

        # Compression menu
        comp_menu = tk.Menu(menubar, tearoff=0)
        comp_menu.add_command(label="Compress Current Frame",
                              command=self._compress_frame)
        comp_menu.add_command(label="Save as RLE...", command=self._save_rle)
        comp_menu.add_command(label="Load RLE...", command=self._load_rle)
        menubar.add_cascade(label="Compression", menu=comp_menu)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0, bg=BG_PANEL, fg=TEXT_PRIMARY,
                            activebackground=ACCENT_CYAN,
                            activeforeground=BG_DEEP)
        help_menu.add_command(label="Feature Guide",
                              command=self._show_feature_guide)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.root.config(menu=menubar)

    def _build_plugins_menu(self):
        """Create Plugins submenu with registered plugin menu items."""
        if (not self._plugins and not self.api._plugin_filters
                and not self.api._menu_items):
            return
        menubar = self.root.nametowidget(self.root.cget("menu"))
        plugins_menu = tk.Menu(menubar, tearoff=0,
                               bg=BG_PANEL, fg=TEXT_PRIMARY,
                               activebackground=ACCENT_CYAN,
                               activeforeground=BG_DEEP)

        # Plugin-registered menu items
        if self.api._menu_items:
            for item in self.api._menu_items:
                plugins_menu.add_command(
                    label=item["label"],
                    command=item["callback"]
                )
            plugins_menu.add_separator()

        # Plugin-registered filters
        if self.api._plugin_filters:
            for name, func in self.api._plugin_filters.items():
                plugins_menu.add_command(
                    label=f"Filter: {name}",
                    command=lambda f=func: self._apply_plugin_filter(f)
                )
            plugins_menu.add_separator()

        # Plugin info
        for plugin in self._plugins:
            plugins_menu.add_command(
                label=f"  {plugin['name']}",
                state="disabled"
            )

        if plugins_menu.index("end") is not None:
            menubar.add_cascade(label="Plugins", menu=plugins_menu)

    def _apply_plugin_filter(self, func):
        """Apply a plugin-registered filter to current layer."""
        self._push_undo()
        layer = self.timeline.current_frame_obj().active_layer
        result = func(layer.pixels)
        layer.pixels._pixels = result._pixels.copy()
        self._refresh_canvas()

    def _build_ui(self):
        # Status bar with CRT scanline effect (pack first so it stays at bottom)
        self.status_var = tk.StringVar(value="Ready")
        self._status_canvas = tk.Canvas(self.root, height=22, bg=BG_PANEL,
                                        highlightthickness=0)
        self._status_canvas.pack(side="bottom", fill="x")
        self._status_canvas.bind("<Configure>", self._draw_status_scanlines)
        self._status_text_id = None
        self._scanline_photo = None
        self.status_var.trace_add("write", lambda *_: self._update_status_text())

        # Timeline panel (bottom, above status bar)
        self._onion_range = 1
        self.timeline_panel = TimelinePanel(
            self.root, timeline=self.timeline,
            on_frame_select=self._on_frame_select,
            on_layer_select=self._on_layer_select,
            on_layer_visibility=self._on_layer_visibility_idx,
            on_layer_lock=self._on_layer_lock,
            on_layer_add=self._add_layer,
            on_layer_delete=self._delete_layer,
            on_layer_rename=self._rename_layer,
            on_layer_duplicate=self._duplicate_layer,
            on_layer_merge=self._merge_down_layer,
            on_layer_opacity=self._on_opacity_change,
            on_frame_add=self._add_frame,
            on_frame_delete=self._delete_frame,
            on_frame_duplicate=self._duplicate_frame,
            on_frame_insert=self._insert_frame,
            on_play=self._play_animation,
            on_stop=self._stop_animation,
            on_onion_toggle=self._on_onion_toggle_from_timeline,
            on_onion_range_change=self._on_onion_range_change,
            on_playback_mode=self._on_playback_mode_change,
            on_layer_blend_mode=self._on_blend_mode_change,
            on_layer_fx=self._on_layer_fx_click,
        )
        self.timeline_panel.config(height=180)
        self.timeline_panel.pack(side="bottom", fill="x")
        self.timeline_panel.pack_propagate(False)

        # Options bar (top, below menu)
        self.options_bar = OptionsBar(
            self.root,
            on_size_change=self._on_size_change,
            on_symmetry_change=self._on_symmetry_change,
            on_dither_change=self._cycle_dither,
            on_pixel_perfect_toggle=self._toggle_pixel_perfect,
            on_tolerance_change=self._on_tolerance_change,
            on_ink_mode_change=self._on_ink_mode_change,
            on_radius_change=self._on_radius_change,
            on_fill_mode_change=self._on_fill_mode_change,
        )
        self.options_bar.pack(side="top", fill="x")

        # Grid widget (right side of options bar)
        self._grid_widget_label = tk.Label(
            self.options_bar, text="Grid: Off",
            font=("Consolas", 8), bg=BG_PANEL, fg=TEXT_SECONDARY,
            cursor="hand2", padx=8)
        self._grid_widget_label.pack(side="right", padx=(0, 8))
        self._grid_widget_label.bind("<Button-1>",
            lambda e: self._quick_toggle_custom_grid())
        self._grid_widget_label.bind("<Button-3>",
            lambda e: self._show_grid_settings())

        # Main frame (center: toolbar + canvas + right panel)
        main_frame = tk.Frame(self.root, bg=BG_DEEP)
        main_frame.pack(fill="both", expand=True)

        # Toolbar (left)
        self.toolbar = Toolbar(main_frame,
                               on_tool_change=self._on_tool_change,
                               keybindings=self.keybindings)
        self.toolbar.pack(side="left", fill="y")

        # Right panel
        self.right_panel = RightPanel(main_frame, self.palette)
        self.right_panel.pack(side="right", fill="y")
        # Inject app so TilesPanel can access the timeline
        self.right_panel.wire_app(self)

        # Wire palette callback
        self.right_panel.palette_panel._on_color_select = self._on_color_select

        # Wire color picker callback
        self.right_panel.color_picker._on_color_pick = self._on_picker_color

        # Wire animation preview callbacks
        self.right_panel.animation_preview.set_callbacks(
            self._play_animation, self._stop_animation,
            self._cycle_playback_mode
        )

        # Canvas (center) — scrollable container
        canvas_outer = tk.Frame(main_frame, bg=BG_PANEL_ALT)
        canvas_outer.pack(side="left", fill="both", expand=True)

        self.pixel_canvas = PixelCanvas(
            canvas_outer, self.timeline.current_frame(), pixel_size=16
        )

        h_scroll = ttk.Scrollbar(canvas_outer, orient="horizontal",
                                 command=self.pixel_canvas.xview,
                                 style="Neon.Horizontal.TScrollbar")
        v_scroll = ttk.Scrollbar(canvas_outer, orient="vertical",
                                 command=self.pixel_canvas.yview,
                                 style="Neon.Vertical.TScrollbar")
        self.pixel_canvas.config(xscrollcommand=h_scroll.set,
                                 yscrollcommand=v_scroll.set)

        v_scroll.pack(side="right", fill="y")
        h_scroll.pack(side="bottom", fill="x")
        self.pixel_canvas.pack(side="left", fill="both", expand=True)

        self.pixel_canvas.on_pixel_click(self._on_canvas_click)
        self.pixel_canvas.on_pixel_drag(self._on_canvas_drag)
        self.pixel_canvas.on_pixel_release(self._on_canvas_release)
        self.pixel_canvas.on_pixel_motion(self._on_canvas_motion)
        self.pixel_canvas.bind("<Double-Button-1>", self._on_canvas_double_click)
        self.pixel_canvas.bind("<Button-3>", lambda e: self._on_canvas_right_click(
            int(e.x // self.pixel_canvas.pixel_size),
            int(e.y // self.pixel_canvas.pixel_size)))

    def _bind_keys(self):
        kb = self.keybindings
        self.root.bind(kb.get("pen"), lambda e: self.toolbar.select_tool("Pen"))
        self.root.bind(kb.get("eraser"), lambda e: self.toolbar.select_tool("Eraser"))
        self.root.bind(kb.get("blur"), lambda e: self.toolbar.select_tool("Blur"))
        self.root.bind(kb.get("fill"), lambda e: self._on_f_key())
        self.root.bind(kb.get("pick"), lambda e: self.toolbar.select_tool("Pick"))
        self.root.bind(kb.get("select"), lambda e: self.toolbar.select_tool("Select"))
        self.root.bind(kb.get("line"), lambda e: self.toolbar.select_tool("Line"))
        self.root.bind(kb.get("rect"), lambda e: self.toolbar.select_tool("Rect"))
        self.root.bind(kb.get("hand"), lambda e: self.toolbar.select_tool("Hand"))
        self.root.bind(kb.get("ellipse"), lambda e: self.toolbar.select_tool("Ellipse"))
        self.root.bind(kb.get("wand"), lambda e: self.toolbar.select_tool("Wand"))
        self.root.bind(kb.get("move"), lambda e: self.toolbar.select_tool("Move"))
        self.root.bind(kb.get("lasso"), lambda e: self.toolbar.select_tool("Lasso"))
        self.root.bind(kb.get("polygon"), lambda e: self.toolbar.select_tool("Polygon"))
        self.root.bind(kb.get("text"), lambda e: self.toolbar.select_tool("Text"))
        self.root.bind(kb.get("roundrect"), lambda e: self.toolbar.select_tool("Roundrect"))
        self.root.bind(kb.get("symmetry"), lambda e: self._cycle_symmetry())
        self.root.bind(kb.get("dither"), lambda e: self._cycle_dither())
        self.root.bind(kb.get("pixel_perfect"), lambda e: self._toggle_pixel_perfect())
        self.root.bind("[", lambda e: self._shade_at_cursor("darken"))
        self.root.bind("]", lambda e: self._shade_at_cursor("lighten"))
        self.root.bind("+", lambda e: self.pixel_canvas.zoom_in())
        self.root.bind("-", lambda e: self.pixel_canvas.zoom_out())
        self.root.bind("=", lambda e: self.pixel_canvas.zoom_in())
        self.root.bind("<Delete>", lambda e: self._delete_selection())
        self.root.bind("<Control-Delete>", lambda e: self._delete_layer())
        # Scroll: plain wheel = vertical, Alt+wheel = horizontal, Ctrl+wheel = zoom
        self.pixel_canvas.bind("<MouseWheel>",
                               lambda e: self._on_scroll(e))
        self.pixel_canvas.bind("<Alt-MouseWheel>",
                               lambda e: self._on_scroll_h(e))
        self.pixel_canvas.bind("<Control-MouseWheel>",
                               lambda e: self._on_zoom(e))
        self.pixel_canvas.bind("<Control-Alt-MouseWheel>",
                               lambda e: self._on_ref_scroll(e))
        # Bind both lowercase and uppercase for Windows compatibility
        for key in ("<Control-c>", "<Control-C>"):
            self.root.bind(key, lambda e: self._copy_selection())
        for key in ("<Control-v>", "<Control-V>"):
            self.root.bind(key, lambda e: self._paste_clipboard())
        for key in ("<Control-b>", "<Control-B>"):
            self.root.bind(key, lambda e: self._capture_brush())
        for key in ("<Control-s>", "<Control-S>"):
            self.root.bind(key, lambda e: self._save_project())
        for key in ("<Control-o>", "<Control-O>"):
            self.root.bind(key, lambda e: self._open_project())
        self.root.bind("<Escape>", lambda e: self._on_escape())
        for key in ("<Control-z>", "<Control-Z>"):
            self.root.bind(key, lambda e: self._undo())
        for key in ("<Control-y>", "<Control-Y>"):
            self.root.bind(key, lambda e: self._redo())
        for key in ("<Control-r>", "<Control-R>"):
            self.root.bind(key, lambda e: self._load_reference_image() if self._reference is None else self._toggle_reference())
        for key in ("<Control-t>", "<Control-T>"):
            self.root.bind(key, lambda e: self._enter_selection_transform())
        for key in ("<Control-Shift-e>", "<Control-Shift-E>"):
            self.root.bind(key, lambda e: self._show_export_dialog())
        self.root.bind("<Control-g>", lambda e: self._toggle_custom_grid())
        self.root.bind("<Control-h>", lambda e: self._toggle_pixel_grid())
        self.root.bind("<Control-Shift-G>", lambda e: self._show_grid_settings())
        self.root.bind("<Return>", lambda e: self._on_enter_key())
        # Tab cycles tilemap edit mode only when the active layer is a TilemapLayer
        self.root.bind("<Tab>", lambda e: self._toggle_tilemap_mode())
        self.root.bind("<Key>", lambda e: self._on_key_press(e))

    # --- Tool Handling ---

    def _on_tool_change(self, name: str):
        # Commit any active selection transform before switching tools
        if self._selection_transform is not None:
            self._commit_selection_transform()
        if self._text_mode:
            self._exit_text_mode(commit=True)
        # Save outgoing tool's settings
        old_tool = self.current_tool_name.lower()
        self._tool_settings.save(old_tool, self._capture_current_tool_settings())

        self.current_tool_name = name
        self.api.emit("tool_change", {"tool_name": name})
        self._cancel_paste()
        self._line_start = None
        self._rect_start = None
        self._roundrect_start = None
        self._ellipse_start = None
        self._select_start = None
        self._hand_last = None
        self._move_start = None
        self._move_snapshot = None
        self._pp_last_points = []
        self._lasso_points = []
        self._polygon_points = []
        # Update options bar visibility for the new tool
        self.options_bar.set_tool(name.lower())
        # Restore incoming tool's settings
        new_settings = self._tool_settings.get(name.lower())
        self._apply_tool_settings(new_settings)
        # Set Hand tool raw callbacks or clear them
        if name == "Hand":
            self.pixel_canvas._on_raw_click = self._hand_click
            self.pixel_canvas._on_raw_drag = self._hand_drag
        else:
            self.pixel_canvas._on_raw_click = None
            self.pixel_canvas._on_raw_drag = None
        self.pixel_canvas.clear_overlays()
        self._update_status()
        # Keep tiles panel visible when switching tools on a tilemap layer
        try:
            frame_obj = self.timeline.current_frame_obj()
            self.right_panel.update_tiles_visibility(frame_obj.active_layer)
        except Exception:
            pass

    def _capture_current_tool_settings(self) -> dict:
        """Capture the current app state as a settings dict for the active tool."""
        return {
            "size": self._tool_size,
            "symmetry": self._symmetry_mode,
            "dither": self._dither_pattern,
            "pixel_perfect": self._pixel_perfect,
            "ink_mode": self._ink_mode,
            "tolerance": self._wand_tolerance,
            "corner_radius": self._corner_radius,
            "fill_mode": self._fill_mode,
        }

    def _apply_tool_settings(self, settings: dict) -> None:
        """Apply a settings dict to the app state and sync the OptionsBar."""
        if "size" in settings:
            self._tool_size = settings["size"]
        if "symmetry" in settings:
            self._symmetry_mode = settings["symmetry"]
        if "dither" in settings:
            self._dither_pattern = settings["dither"]
        if "pixel_perfect" in settings:
            self._pixel_perfect = settings["pixel_perfect"]
        if "ink_mode" in settings:
            self._ink_mode = settings["ink_mode"]
        if "tolerance" in settings:
            self._wand_tolerance = settings["tolerance"]
        if "corner_radius" in settings:
            self._corner_radius = settings["corner_radius"]
        if "fill_mode" in settings:
            self._fill_mode = settings["fill_mode"]
        self.options_bar.restore_settings(settings)

    def _on_radius_change(self, radius: int):
        self._corner_radius = radius

    def _on_fill_mode_change(self, mode: str):
        self._fill_mode = mode

    def _on_size_change(self, size: int):
        self._tool_size = size
        self._custom_brush_mask = None
        self._update_status()

    def _on_color_select(self, color):
        idx = self.palette.colors.index(color) if color in self.palette.colors else -1
        self.api.emit("palette_change", {"color": color, "index": idx})
        self._update_status()

    def _on_picker_color(self, color, add_to_palette=False):
        """Handle color picked from the color picker gradient."""
        self.palette.add_color(color)
        idx = self.palette.colors.index(color)
        self.palette.select(idx)
        self.right_panel.palette_panel.refresh()
        self.api.emit("palette_change", {"color": color, "index": idx})
        if add_to_palette:
            self._update_status("Added to palette")
        else:
            self._update_status()

    # --- Undo / Redo ---

    def _push_undo(self):
        """Snapshot current active layer before a modification."""
        frame_obj = self.timeline.current_frame_obj()
        layer_idx = frame_obj.active_layer_index
        snapshot = frame_obj.active_layer.pixels.copy()
        self._undo_stack.append((self.timeline.current_index, layer_idx, snapshot))
        if len(self._undo_stack) > self._UNDO_LIMIT:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        self._mark_dirty()

    def _undo(self):
        if not self._undo_stack:
            return
        frame_obj = self.timeline.current_frame_obj()
        layer_idx = frame_obj.active_layer_index
        self._redo_stack.append((self.timeline.current_index, layer_idx,
                                 frame_obj.active_layer.pixels.copy()))
        frame_idx, saved_layer_idx, prev = self._undo_stack.pop()
        target_frame = self.timeline.get_frame_obj(frame_idx)
        target_frame.layers[saved_layer_idx].pixels = prev
        self._refresh_canvas()
        self._update_status("Undo")

    def _redo(self):
        if not self._redo_stack:
            return
        frame_obj = self.timeline.current_frame_obj()
        layer_idx = frame_obj.active_layer_index
        self._undo_stack.append((self.timeline.current_index, layer_idx,
                                 frame_obj.active_layer.pixels.copy()))
        frame_idx, saved_layer_idx, next_state = self._redo_stack.pop()
        target_frame = self.timeline.get_frame_obj(frame_idx)
        target_frame.layers[saved_layer_idx].pixels = next_state
        self._refresh_canvas()
        self._update_status("Redo")

    # --- Scroll / Pan / Zoom ---

    def _on_scroll(self, event):
        """Vertical scroll (plain wheel)."""
        direction = -1 if event.delta > 0 else 1
        self.pixel_canvas.yview_scroll(direction * 3, "units")

    def _on_scroll_h(self, event):
        """Horizontal scroll (Alt+wheel)."""
        direction = -1 if event.delta > 0 else 1
        self.pixel_canvas.xview_scroll(direction * 3, "units")

    def _on_zoom(self, event):
        """Zoom in/out (Ctrl+wheel), relative to cursor position."""
        if event.delta > 0:
            self.pixel_canvas.zoom_in(event)
        else:
            self.pixel_canvas.zoom_out(event)
        self._render_canvas()
        self._update_status()

    def _hand_click(self, event):
        """Start Hand tool panning."""
        self.pixel_canvas.scan_mark(event.x, event.y)

    def _hand_drag(self, event):
        """Hand tool drag to pan."""
        self.pixel_canvas.scan_dragto(event.x, event.y, gain=1)

    # --- Drawing Mode Toggles ---

    def _on_symmetry_change(self, mode: str):
        """Called when symmetry is changed from the options bar."""
        self._symmetry_mode = mode
        self._update_status()

    def _cycle_symmetry(self):
        """Cycle Off -> H -> V -> Both -> Off."""
        modes = ["off", "horizontal", "vertical", "both"]
        idx = modes.index(self._symmetry_mode)
        self._symmetry_mode = modes[(idx + 1) % len(modes)]
        self.options_bar.update_symmetry_label(self._symmetry_mode)
        self._update_status()

    def _on_tiled_mode_change(self):
        self._tiled_mode = self._tiled_var.get()
        self.pixel_canvas.set_tiled_mode(self._tiled_mode)
        self._render_canvas()
        self._update_status(f"Tiled: {self._tiled_mode}")

    def _cycle_dither(self):
        """Cycle through dither patterns."""
        patterns = list(DITHER_PATTERNS.keys())
        idx = patterns.index(self._dither_pattern)
        self._dither_pattern = patterns[(idx + 1) % len(patterns)]
        self.options_bar.update_dither_label(self._dither_pattern)
        self._update_status()

    def _toggle_pixel_perfect(self):
        """Toggle pixel-perfect freehand mode."""
        self._pixel_perfect = not self._pixel_perfect
        self.options_bar.update_pixel_perfect_label(self._pixel_perfect)
        self._update_status()

    def _on_tolerance_change(self, value: int) -> None:
        self._wand_tolerance = value

    def _on_ink_mode_change(self, mode):
        self._ink_mode = mode
        self._update_status(f"Ink: {mode}")

    # --- Keybindings Dialog ---

    def _show_keybindings_dialog(self):
        """Show a dialog listing all keyboard shortcuts."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Keyboard Shortcuts")
        dialog.geometry("300x400")
        dialog.resizable(False, False)
        dialog.configure(bg=BG_DEEP)
        dialog.transient(self.root)
        dialog.grab_set()

        tk.Label(dialog, text="Keyboard Shortcuts", fg=ACCENT_CYAN, bg=BG_DEEP,
                 font=("Consolas", 11, "bold")).pack(pady=(12, 8))

        frame = tk.Frame(dialog, bg=BG_DEEP)
        frame.pack(fill="both", expand=True, padx=12, pady=4)

        bindings = self.keybindings.get_all()
        for action, key in sorted(bindings.items()):
            row = tk.Frame(frame, bg=BG_DEEP)
            row.pack(fill="x", pady=1)
            tk.Label(row, text=action, fg=TEXT_SECONDARY, bg=BG_DEEP,
                     font=("Consolas", 9), width=16, anchor="w").pack(side="left")
            tk.Label(row, text=key, fg=TEXT_PRIMARY, bg=BG_PANEL_ALT,
                     font=("Consolas", 9), width=12, anchor="w").pack(side="left")

        tk.Button(dialog, text="Close", bg=BUTTON_BG, fg=TEXT_PRIMARY,
                  activebackground=BUTTON_HOVER, activeforeground=TEXT_PRIMARY,
                  font=("Consolas", 9), relief="flat",
                  command=dialog.destroy).pack(pady=8)

    # --- Rendering ---

    def _refresh_all(self):
        self._refresh_canvas()
        self._update_frame_list()
        self._update_layer_list()
        self.timeline_panel.refresh()
        self._update_status()
        # Keep tiles panel visibility in sync
        try:
            frame_obj = self.timeline.current_frame_obj()
            self.right_panel.update_tiles_visibility(frame_obj.active_layer)
        except Exception:
            pass

    def _get_onion_grids(self):
        """Collect past and future onion skin grids based on range."""
        past = []
        future = []
        if not self._onion_skin:
            return past, future
        cur = self.timeline.current_index
        r = getattr(self, '_onion_range', 1)
        for i in range(1, r + 1):
            idx = cur - i
            if 0 <= idx < self.timeline.frame_count:
                past.append(self.timeline.get_frame(idx))
        for i in range(1, r + 1):
            idx = cur + i
            if 0 <= idx < self.timeline.frame_count:
                future.append(self.timeline.get_frame(idx))
        return past, future

    def _refresh_canvas(self):
        past, future = self._get_onion_grids()
        ref = self._reference
        self.pixel_canvas.grid = self.timeline.current_frame()
        self.pixel_canvas._resize_canvas()
        self.pixel_canvas.grid_settings = self._grid_settings
        self.pixel_canvas.render(onion_past_grids=past if past else None,
                                 onion_future_grids=future if future else None,
                                 reference=ref)
        if self._selection_pixels:
            self.pixel_canvas.draw_wand_selection(self._selection_pixels)
        self._draw_symmetry_axis_overlay()
        if self._selection_transform is not None:
            self._draw_transform_overlay()

    def _render_canvas(self):
        past, future = self._get_onion_grids()
        ref = self._reference
        self.pixel_canvas.grid = self.timeline.current_frame()

        # Temporarily suppress effects if Display Layer Effects is off
        saved_effects = None
        if not self._display_effects:
            frame_obj = self.timeline.current_frame_obj()
            saved_effects = [layer.effects for layer in frame_obj.layers]
            for layer in frame_obj.layers:
                layer.effects = []

        self.pixel_canvas.grid_settings = self._grid_settings
        self.pixel_canvas.render(onion_past_grids=past if past else None,
                                 onion_future_grids=future if future else None,
                                 reference=ref,
                                 tiled_mode=self._tiled_mode)

        # Restore effects after render
        if saved_effects is not None:
            frame_obj = self.timeline.current_frame_obj()
            for layer, fx in zip(frame_obj.layers, saved_effects):
                layer.effects = fx

        # Re-draw persistent selection if active
        if self._selection_pixels:
            self.pixel_canvas.draw_wand_selection(self._selection_pixels)

        # Draw tile grid overlay when active layer is a TilemapLayer
        frame_obj_tg = self.timeline.current_frame_obj()
        active_layer_tg = frame_obj_tg.active_layer
        if (hasattr(active_layer_tg, 'is_tilemap') and active_layer_tg.is_tilemap()):
            tw = active_layer_tg.tileset.tile_width
            th = active_layer_tg.tileset.tile_height
            cw = active_layer_tg.grid_cols * tw
            ch = active_layer_tg.grid_rows * th
            zoom = self.pixel_canvas.pixel_size
            self.pixel_canvas.draw_tile_grid(tw, th, cw, ch, zoom)
        else:
            self.pixel_canvas.clear_tile_grid()
        self.pixel_canvas.delete("tile_highlight")
        self._draw_symmetry_axis_overlay()

        # Redraw transform overlay at current zoom if active
        if self._selection_transform is not None:
            self._draw_transform_overlay()

    # --- Theme ---

    def _toggle_theme_mode(self):
        current = get_mode()
        new_mode = "light" if current == "dark" else "dark"
        set_mode(new_mode)

    # --- Help ---

    def _show_feature_guide(self):
        from src.ui.help_window import show_feature_guide
        show_feature_guide(self.root)

    # --- Status Bar ---

    def _draw_status_scanlines(self, event=None):
        """Redraw the status bar scanline texture on resize."""
        c = self._status_canvas
        w = c.winfo_width()
        h = c.winfo_height()
        if w < 2 or h < 2:
            return
        from src.ui.effects import create_scanline_texture
        from src.ui.theme import SCANLINE_DARK, SCANLINE_LIGHT
        texture = create_scanline_texture(w, h, SCANLINE_DARK, SCANLINE_LIGHT)
        self._scanline_photo = ImageTk.PhotoImage(texture)
        c.delete("scanline")
        c.create_image(0, 0, image=self._scanline_photo, anchor="nw",
                        tags="scanline")
        self._update_status_text()

    def _update_status_text(self):
        """Redraw the status text on top of the scanline texture."""
        c = self._status_canvas
        c.delete("status_text")
        text = self.status_var.get()
        c.create_text(8, 11, text=text, anchor="w",
                       font=("Consolas", 8), fill=TEXT_SECONDARY,
                       tags="status_text")

    def _update_status(self, extra: str = ""):
        grid = self.timeline.current_frame()
        tool_info = self.current_tool_name
        if self.current_tool_name in ("Pen", "Eraser", "Blur"):
            tool_info += f" [{self._tool_size}px]"
        parts = [
            f"{grid.width}x{grid.height}",
            f"Zoom: {self.pixel_canvas.pixel_size}px",
            f"Frame {self.timeline.current_index + 1}/{self.timeline.frame_count}",
            f"Tool: {tool_info}",
            f"Onion: {'ON' if self._onion_skin else 'OFF'}",
        ]
        if self._symmetry_mode != "off":
            sym_labels = {"horizontal": "H", "vertical": "V", "both": "Both"}
            parts.append(f"Sym: {sym_labels[self._symmetry_mode]}")
        if self._dither_pattern != "none":
            parts.append(f"Dither: {self._dither_pattern}")
        if self._pixel_perfect:
            parts.append("PxPerf")
        if extra:
            parts.append(extra)
        self.status_var.set(" | ".join(parts))
