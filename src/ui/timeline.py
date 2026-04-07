"""Bottom Layer x Frame grid timeline panel for RetroSprite."""

import tkinter as tk
import tkinter.font as tkfont
from PIL import ImageTk
from src.ui.theme import (
    BG_DEEP, BG_PANEL, BG_PANEL_ALT, BORDER, ACCENT_CYAN, ACCENT_MAGENTA,
    ACCENT_PURPLE, SUCCESS, WARNING, TEXT_PRIMARY, TEXT_SECONDARY,
    BUTTON_BG, BUTTON_HOVER, blend_color, hex_to_rgb, rgb_to_hex
)
from src.ui.icons import IconPipeline


BLEND_MODES = ["normal", "multiply", "screen", "overlay", "addition",
               "subtract", "darken", "lighten", "difference"]


class TimelinePanel(tk.Frame):
    """Combined layer+frame grid timeline, docked at the bottom of the window."""

    def __init__(self, parent, timeline=None,
                 on_frame_select=None, on_layer_select=None,
                 on_layer_visibility=None, on_layer_lock=None,
                 on_layer_add=None, on_layer_delete=None,
                 on_layer_rename=None, on_layer_duplicate=None,
                 on_layer_merge=None, on_layer_opacity=None,
                 on_frame_add=None, on_frame_delete=None,
                 on_frame_duplicate=None, on_frame_insert=None,
                 on_frame_duration_change=None,
                 on_play=None, on_stop=None,
                 on_onion_toggle=None, on_onion_range_change=None,
                 on_playback_mode=None,
                 on_layer_blend_mode=None,
                 on_layer_fx=None):
        super().__init__(parent, bg=BG_DEEP)

        self._timeline = timeline
        self._callbacks = {
            "frame_select": on_frame_select,
            "layer_select": on_layer_select,
            "layer_visibility": on_layer_visibility,
            "layer_lock": on_layer_lock,
            "layer_add": on_layer_add,
            "layer_delete": on_layer_delete,
            "layer_rename": on_layer_rename,
            "layer_duplicate": on_layer_duplicate,
            "layer_merge": on_layer_merge,
            "layer_opacity": on_layer_opacity,
            "frame_add": on_frame_add,
            "frame_delete": on_frame_delete,
            "frame_duplicate": on_frame_duplicate,
            "frame_insert": on_frame_insert,
            "frame_duration_change": on_frame_duration_change,
            "play": on_play,
            "stop": on_stop,
            "onion_toggle": on_onion_toggle,
            "onion_range_change": on_onion_range_change,
            "playback_mode": on_playback_mode,
            "layer_blend_mode": on_layer_blend_mode,
            "layer_fx": on_layer_fx,
        }

        self._cel_size = 64  # Size of each cel in the grid

        # Load stack icon for blend mode buttons (small, 16px display)
        self._blend_icon_pipeline = IconPipeline(icon_size=16, display_size=16)
        try:
            normal_img, _glow = self._blend_icon_pipeline.get_icon("stack")
            self._blend_icon = ImageTk.PhotoImage(normal_img)
        except Exception:
            self._blend_icon = None
        self._playing = False
        self._copied_frame_idx = None  # For copy/paste frame
        self._tag_drag_edge = None
        self._tag_drag_idx = None
        self._onion_on = False
        self._onion_range = 1
        self._playback_mode = "forward"
        self._collapsed_groups = {}  # {layer_index: bool}
        self._selected_frames = set()  # multi-frame selection (shift-click)
        self._anchor_frame = None  # anchor for shift-click range

        self._build_ui()

    def _build_ui(self):
        # --- Drag handle at the top ---
        self._handle = tk.Frame(self, height=5, bg=BORDER, cursor="sb_v_double_arrow")
        self._handle.pack(fill="x", side="top")
        self._handle.bind("<ButtonPress-1>", self._on_drag_start)
        self._handle.bind("<B1-Motion>", self._on_drag_motion)

        # --- Transport bar (below handle) ---
        self._transport = tk.Frame(self, bg=BG_PANEL, height=32)
        self._transport.pack(fill="x", side="top")
        self._transport.pack_propagate(False)
        self._build_transport()

        # --- Main content area ---
        content = tk.Frame(self, bg=BG_DEEP)
        content.pack(fill="both", expand=True, side="top")

        # --- PanedWindow: layer sidebar (left) | frame grid (right) ---
        self._paned = tk.PanedWindow(content, orient=tk.HORIZONTAL,
                                      bg=BORDER, sashwidth=4,
                                      sashrelief="flat", bd=0,
                                      opaqueresize=True)
        self._paned.pack(fill="both", expand=True)

        # --- Left pane: layer sidebar with vertical scroll ---
        left_pane = tk.Frame(self._paned, bg=BG_PANEL)

        self._layer_canvas = tk.Canvas(left_pane, bg=BG_PANEL,
                                        highlightthickness=0)
        self._layer_canvas.pack(fill="both", expand=True)

        self._layer_inner = tk.Frame(self._layer_canvas, bg=BG_PANEL)
        self._layer_canvas_window = self._layer_canvas.create_window(
            (0, 0), window=self._layer_inner, anchor="nw")

        def _on_layer_canvas_configure(event):
            self._layer_canvas.itemconfig(self._layer_canvas_window,
                                           width=event.width)
        self._layer_canvas.bind("<Configure>", _on_layer_canvas_configure)
        self._layer_inner.bind("<Configure>",
                               lambda e: self._layer_canvas.configure(
                                   scrollregion=self._layer_canvas.bbox("all")))

        # --- Right pane: frame grid with both scrollbars ---
        right_pane = tk.Frame(self._paned, bg=BG_DEEP)

        from tkinter import ttk

        self._v_scrollbar = ttk.Scrollbar(right_pane, orient="vertical",
                                           style="Neon.Vertical.TScrollbar",
                                           command=self._on_v_scroll)
        self._v_scrollbar.pack(side="right", fill="y")

        self._h_scrollbar = ttk.Scrollbar(right_pane, orient="horizontal",
                                           style="Neon.Horizontal.TScrollbar")
        self._h_scrollbar.pack(side="bottom", fill="x")

        self._grid_canvas = tk.Canvas(right_pane, bg=BG_DEEP,
                                      highlightthickness=0,
                                      xscrollcommand=self._h_scrollbar.set,
                                      yscrollcommand=self._on_grid_yscroll)
        self._grid_canvas.pack(fill="both", expand=True)
        self._h_scrollbar.config(command=self._grid_canvas.xview)

        self._grid_inner = tk.Frame(self._grid_canvas, bg=BG_DEEP)
        self._grid_canvas.create_window((0, 0), window=self._grid_inner,
                                         anchor="nw")
        self._grid_inner.bind("<Configure>",
                              lambda e: self._grid_canvas.configure(
                                  scrollregion=self._grid_canvas.bbox("all")))

        for widget in (self._layer_canvas, self._grid_canvas):
            widget.bind("<MouseWheel>", self._on_timeline_mousewheel)

        self._paned.add(left_pane, minsize=120, width=200)
        self._paned.add(right_pane, minsize=100)

    def _on_v_scroll(self, *args):
        """Vertical scrollbar command — sync both canvases."""
        self._grid_canvas.yview(*args)
        self._layer_canvas.yview(*args)

    def _on_grid_yscroll(self, first, last):
        """Called when grid canvas scrolls — sync scrollbar + layer canvas."""
        self._v_scrollbar.set(first, last)
        self._layer_canvas.yview_moveto(first)

    def _on_timeline_mousewheel(self, event):
        """Mousewheel scrolls both panes vertically."""
        self._grid_canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
        self._layer_canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

    @staticmethod
    def _truncate_name(event, lbl, full_text):
        """Truncate label text with '...' to fit available width."""
        font = tkfont.Font(font=lbl.cget("font"))
        avail = event.width
        if avail <= 1:
            return
        if font.measure(full_text) <= avail:
            lbl.config(text=full_text)
        else:
            for i in range(len(full_text), 0, -1):
                if font.measure(full_text[:i] + "...") <= avail:
                    lbl.config(text=full_text[:i] + "...")
                    return
            lbl.config(text="...")

    def _build_transport(self):
        f = self._transport

        # Play controls
        btn_cfg = dict(font=("Consolas", 9), bg=BUTTON_BG, fg=TEXT_PRIMARY,
                       relief="flat", width=3, activebackground=BUTTON_HOVER,
                       activeforeground=ACCENT_CYAN)

        tk.Button(f, text="<<", command=self._step_back, **btn_cfg).pack(side="left", padx=2)
        tk.Button(f, text=">>", command=self._step_forward, **btn_cfg).pack(side="left", padx=2)

        self._play_btn = tk.Button(f, text="\u25B6", command=self._on_play, **btn_cfg)
        self._play_btn.pack(side="left", padx=2)

        self._stop_btn = tk.Button(f, text="\u25A0", command=self._on_stop, **btn_cfg)
        self._stop_btn.pack(side="left", padx=2)

        # Separator
        tk.Frame(f, width=1, bg=ACCENT_CYAN).pack(side="left", fill="y", padx=8, pady=4)

        # Playback mode
        self._mode_var = tk.StringVar(value="fwd")
        self._mode_btn = tk.Button(f, textvariable=self._mode_var,
                                   command=self._cycle_playback_mode,
                                   **{**btn_cfg, "width": 4})
        self._mode_btn.pack(side="left", padx=2)

        # Separator
        tk.Frame(f, width=1, bg=ACCENT_CYAN).pack(side="left", fill="y", padx=8, pady=4)

        # Onion skin
        self._onion_btn = tk.Button(f, text="Onion: Off",
                                    command=self._toggle_onion,
                                    **{**btn_cfg, "width": 9})
        self._onion_btn.pack(side="left", padx=2)

        tk.Label(f, text="Range:", font=("Consolas", 8), bg=BG_PANEL,
                 fg=TEXT_SECONDARY).pack(side="left", padx=(4, 0))
        self._onion_range_var = tk.IntVar(value=1)
        self._onion_spin = tk.Spinbox(f, from_=1, to=5, width=2,
                                      textvariable=self._onion_range_var,
                                      font=("Consolas", 8), bg=BG_PANEL_ALT,
                                      fg=TEXT_PRIMARY, buttonbackground=BUTTON_BG,
                                      command=self._on_onion_range)
        self._onion_spin.pack(side="left", padx=2)

        # Separator
        tk.Frame(f, width=1, bg=ACCENT_CYAN).pack(side="left", fill="y", padx=8, pady=4)

        # Add Frame / Add Layer buttons (left, near onion section)
        tk.Button(f, text="+ Frame", command=self._on_add_frame,
                  font=("Consolas", 8), bg=BUTTON_BG, fg=ACCENT_CYAN,
                  relief="flat", activebackground=BUTTON_HOVER).pack(side="left", padx=4)
        tk.Button(f, text="+ Layer", command=self._on_add_layer,
                  font=("Consolas", 8), bg=BUTTON_BG, fg=ACCENT_PURPLE,
                  relief="flat", activebackground=BUTTON_HOVER).pack(side="left", padx=4)

    def refresh(self):
        """Rebuild the entire grid from the current timeline state."""
        if not self._timeline:
            return

        # Clear existing
        for w in self._layer_inner.winfo_children():
            w.destroy()
        for w in self._grid_inner.winfo_children():
            w.destroy()

        # Ensure all frames have consistent layer counts
        self._timeline.sync_layers()

        frames = self._timeline._frames
        if not frames:
            return

        current_frame_idx = self._timeline._current_index
        current_frame = frames[current_frame_idx]
        num_frames = len(frames)
        num_layers = self._timeline.num_layers  # Global layer count
        active_layer = current_frame.active_layer_index

        # Fix column sizes so they don't resize on click
        for fi in range(num_frames):
            self._grid_inner.grid_columnconfigure(
                fi, minsize=self._cel_size, weight=0)

        # Widget caches for lightweight highlight_frame()
        self._header_widgets = {}
        self._cel_widgets = {}
        self._blend_vars = []  # keep StringVars alive for blend mode dropdowns
        self._layer_rows = {}   # {layer_index: row_widget} for drag-to-reorder
        self._drag_source_idx = None
        self._drag_indicator = None

        # --- Tag strip row in grid_inner ---
        tag_frame = tk.Frame(self._grid_inner, bg=BG_DEEP, height=16)
        tag_frame.grid(row=0, column=0, columnspan=num_frames, sticky="ew")
        self._draw_tags(tag_frame, num_frames)

        # --- Frame header row (clickable to select frame) ---
        for fi in range(num_frames):
            f = frames[fi]
            is_current = (fi == current_frame_idx)
            is_selected = fi in self._selected_frames and not is_current
            if is_current:
                bg = ACCENT_CYAN
                fg = BG_DEEP
            elif is_selected:
                bg = blend_color(BG_PANEL, ACCENT_PURPLE, 0.4)
                fg = ACCENT_PURPLE
            else:
                bg = BG_PANEL
                fg = TEXT_SECONDARY

            header = tk.Frame(self._grid_inner, width=self._cel_size, height=24, bg=bg)
            header.grid(row=1, column=fi, padx=1, pady=(0, 1), sticky="nsew")
            header.grid_propagate(False)

            lbl = tk.Label(header, text=f"{fi+1}", font=("Consolas", 8, "bold"),
                           bg=bg, fg=fg)
            lbl.pack(side="left", padx=(4, 0))

            dur_lbl = tk.Label(header, text=f"{f.duration_ms}ms",
                               font=("Consolas", 7), bg=bg, fg=fg)
            dur_lbl.pack(side="right", padx=(0, 4))

            self._header_widgets[fi] = (header, lbl, dur_lbl)

            # Click anywhere on header to select frame
            for widget in (header, lbl, dur_lbl):
                widget.bind("<Button-1>",
                            lambda e, idx=fi: self._on_frame_click(e, idx))
                widget.bind("<Button-3>",
                            lambda e, idx=fi: self._show_frame_context_menu(e, idx))
            dur_lbl.bind("<Double-Button-1>",
                         lambda e, idx=fi: self._edit_frame_duration(idx))

        # --- Layer sidebar labels ---
        # Spacer for tag + header rows
        spacer = tk.Frame(self._layer_inner, height=36, bg=BG_PANEL)
        spacer.pack(fill="x")

        # Build display order: group headers above their children,
        # overall reversed so top layer appears first visually.
        blocks = []
        i = 0
        while i < num_layers:
            layer = current_frame.layers[i]
            if layer.is_group:
                block = [i]
                j = i + 1
                while (j < num_layers and
                       not current_frame.layers[j].is_group and
                       current_frame.layers[j].depth > layer.depth):
                    block.append(j)
                    j += 1
                blocks.append(block)
                i = j
            else:
                blocks.append([i])
                i += 1
        blocks.reverse()
        display_order = []
        for block in blocks:
            display_order.extend(block)

        for li in display_order:
            layer = current_frame.layers[li]
            layer_depth = layer.depth
            is_group = layer.is_group
            is_active = (li == active_layer)

            # Check if this layer is hidden by a collapsed group
            skip = False
            for gi, is_collapsed in self._collapsed_groups.items():
                if is_collapsed and 0 <= gi < len(current_frame.layers):
                    g_layer = current_frame.layers[gi]
                    if g_layer.is_group:
                        g_depth = g_layer.depth
                        if li > gi and layer_depth > g_depth:
                            skip = True
                            break
            if skip:
                continue

            row = tk.Frame(self._layer_inner, height=self._cel_size, bg=BG_PANEL)
            row.pack(fill="x", pady=1)
            row.pack_propagate(False)
            self._layer_rows[li] = row

            # Left accent bar for child layers
            if layer_depth > 0:
                accent_bar = tk.Frame(row, width=3, bg=ACCENT_MAGENTA)
                accent_bar.pack(side="left", fill="y")

            # Indent based on depth
            indent = layer_depth * 12
            if indent > 0:
                spacer_indent = tk.Frame(row, width=indent, bg=row.cget("bg"))
                spacer_indent.pack(side="left")
                spacer_indent.pack_propagate(False)

            # Collapse/expand toggle for group layers
            if is_group:
                collapsed = self._collapsed_groups.get(li, False)
                toggle_text = "\u25B6" if collapsed else "\u25BC"  # right or down triangle
                toggle_btn = tk.Button(row, text=toggle_text, width=2,
                                       font=("Consolas", 8), bg=BG_PANEL, fg=ACCENT_MAGENTA,
                                       relief="flat",
                                       command=lambda idx=li: self._toggle_group_collapse(idx))
                toggle_btn.pack(side="left", padx=1)

            # Visibility toggle (eye icon)
            vis_text = "\U0001F441" if layer.visible else "\u2014"  # eye vs dash
            vis_fg = ACCENT_CYAN if layer.visible else TEXT_SECONDARY
            vis_btn = tk.Button(row, text=vis_text, width=3,
                                font=("Segoe UI Emoji", 9), bg=BG_PANEL, fg=vis_fg,
                                relief="flat", command=lambda idx=li: self._toggle_visibility(idx))
            vis_btn.pack(side="left", padx=1)

            # Lock toggle (lock icon)
            lock_text = "\U0001F512" if layer.locked else "\U0001F513"  # locked vs unlocked
            lock_color = WARNING if layer.locked else TEXT_SECONDARY
            lock_btn = tk.Button(row, text=lock_text, width=3,
                                 font=("Segoe UI Emoji", 9), bg=BG_PANEL, fg=lock_color,
                                 relief="flat", command=lambda idx=li: self._toggle_lock(idx))
            lock_btn.pack(side="left", padx=1)

            # Layer name — groups get bold magenta styling
            if is_group:
                name_font = ("Consolas", 8, "bold")
                name_fg = ACCENT_CYAN if is_active else ACCENT_MAGENTA
                name_bg = BG_PANEL_ALT if is_active else BG_PANEL
                name_text = f"\U0001F4C1 {layer.name}"
            elif layer_depth > 0:
                name_font = ("Consolas", 8)
                name_fg = ACCENT_CYAN if is_active else TEXT_SECONDARY
                name_bg = BG_PANEL_ALT if is_active else BG_PANEL
                name_text = layer.name
            else:
                name_font = ("Consolas", 8)
                name_fg = ACCENT_CYAN if is_active else TEXT_PRIMARY
                name_bg = BG_PANEL_ALT if is_active else BG_PANEL
                name_text = layer.name
            name_lbl = tk.Label(row, text=name_text, font=name_font,
                                bg=name_bg, fg=name_fg, anchor="w")
            name_lbl.pack(side="left", fill="x", expand=True, padx=2)
            name_lbl.bind("<Button-1>", lambda e, idx=li: self._select_layer(idx))
            name_lbl.bind("<Double-Button-1>", lambda e, idx=li: self._rename_layer(idx))
            name_lbl.bind("<Button-3>", lambda e, idx=li: self._show_layer_context_menu(e, idx))
            name_lbl.bind("<Configure>",
                          lambda e, l=name_lbl, t=name_text: self._truncate_name(e, l, t))

            # Drag-to-reorder bindings
            for drag_widget in (row, name_lbl):
                drag_widget.bind("<B1-Motion>",
                                 lambda e, idx=li: self._on_layer_drag(e, idx))
                drag_widget.bind("<ButtonRelease-1>",
                                 lambda e, idx=li: self._on_layer_drop(e, idx))

            # FX and blend mode — only for non-group layers
            if not is_group:
                # FX button — lit when layer has active effects
                has_fx = bool(getattr(layer, "effects", None))
                fx_bg = ACCENT_MAGENTA if has_fx else BUTTON_BG
                fx_fg = BG_PANEL if has_fx else TEXT_SECONDARY
                fx_btn = tk.Button(row, text="FX", width=3,
                                   font=("Consolas", 7, "bold"),
                                   bg=fx_bg, fg=fx_fg, relief="flat",
                                   activebackground=ACCENT_MAGENTA, activeforeground=BG_PANEL,
                                   command=lambda idx=li: self._on_layer_fx(idx))
                fx_btn.pack(side="right", padx=1)

                # Blend mode dropdown (stack icon + tooltip showing current mode)
                blend_var = tk.StringVar(value=layer.blend_mode)
                self._blend_vars.append(blend_var)
                blend_btn = tk.Menubutton(row, relief="flat", bd=0,
                                           bg=BG_PANEL, activebackground=BUTTON_HOVER,
                                           highlightthickness=0)
                if self._blend_icon:
                    blend_btn.config(image=self._blend_icon)
                else:
                    blend_btn.config(text="\u2630", font=("Consolas", 9),
                                     fg=TEXT_SECONDARY)
                blend_menu = tk.Menu(blend_btn, tearoff=0, bg=BG_PANEL,
                                     fg=TEXT_SECONDARY, font=("Consolas", 8))
                for mode in BLEND_MODES:
                    blend_menu.add_radiobutton(
                        label=mode, variable=blend_var, value=mode,
                        command=lambda val=mode, idx=li: self._on_blend_change(idx, val))
                blend_btn.config(menu=blend_menu)
                blend_btn.pack(side="right", padx=2)
                # Tooltip showing current blend mode on hover
                blend_btn.bind("<Enter>", lambda e, v=blend_var: self._show_blend_tooltip(e, v))
                blend_btn.bind("<Leave>", lambda e: self._hide_blend_tooltip())

            for child in row.winfo_children():
                child.bind("<MouseWheel>", self._on_timeline_mousewheel)
            row.bind("<MouseWheel>", self._on_timeline_mousewheel)

        # --- Cel grid ---
        grid_row_visual = 2  # start after tag + header rows
        for li in display_order:
            # Same skip check as sidebar
            layer = current_frame.layers[li]
            skip = False
            for gi, is_collapsed in self._collapsed_groups.items():
                if is_collapsed and 0 <= gi < len(current_frame.layers):
                    g_layer = current_frame.layers[gi]
                    if g_layer.is_group and li > gi and layer.depth > g_layer.depth:
                        skip = True
                        break
            if skip:
                continue
            grid_row = grid_row_visual
            self._grid_inner.grid_rowconfigure(
                grid_row, minsize=self._cel_size, weight=0)
            for fi in range(num_frames):
                frame = frames[fi]
                is_current_frame = (fi == current_frame_idx)
                is_active_layer = (li == active_layer)

                # Determine cel state
                has_content = False
                if li < len(frame.layers):
                    layer = frame.layers[li]
                    has_content = layer.pixels._pixels.any()

                if is_current_frame and is_active_layer:
                    bg = ACCENT_CYAN
                    fg = BG_DEEP
                elif is_current_frame:
                    bg = blend_color(BG_PANEL_ALT, ACCENT_CYAN, 0.15)
                    fg = ACCENT_CYAN
                elif is_active_layer:
                    bg = BG_PANEL_ALT
                    fg = ACCENT_CYAN
                else:
                    bg = BG_PANEL if has_content else BG_DEEP
                    fg = TEXT_SECONDARY

                cel = tk.Frame(self._grid_inner, width=self._cel_size,
                               height=self._cel_size, bg=bg)
                cel.grid(row=grid_row, column=fi, padx=1, pady=1, sticky="nsew")
                cel.grid_propagate(False)

                # Content indicator
                indicator = "\u25A0" if has_content else ""
                dot = tk.Label(cel, text=indicator, font=("Consolas", 10),
                               bg=bg, fg=fg)
                dot.pack(expand=True, fill="both")

                self._cel_widgets[(fi, li)] = (cel, dot)

                # Bind click and right-click on both cel frame and label
                for widget in (cel, dot):
                    widget.bind("<Button-1>",
                                lambda e, f=fi, l=li: self._select_cel(f, l))
                    widget.bind("<Button-3>",
                                lambda e, f=fi, l=li: self._show_cel_context_menu(e, f, l))

                for child in cel.winfo_children():
                    child.bind("<MouseWheel>", self._on_timeline_mousewheel)
                cel.bind("<MouseWheel>", self._on_timeline_mousewheel)
            grid_row_visual += 1

    def _build_frame_menu(self, menu, frame_idx):
        """Populate a menu with frame operations."""
        menu.add_command(label="Insert Frame Before",
                         command=lambda: self._insert_frame_at(frame_idx - 1))
        menu.add_command(label="Insert Frame After",
                         command=lambda: self._insert_frame_at(frame_idx))
        menu.add_command(label="Duplicate Frame",
                         command=lambda: self._on_duplicate_frame(frame_idx))
        menu.add_command(label="Duplicate Frame (Linked)",
                         command=lambda: self._on_duplicate_frame_linked(frame_idx))
        menu.add_separator()
        menu.add_command(label="Copy Frame",
                         command=lambda: self._copy_frame(frame_idx))
        paste_label = "Paste Frame After"
        menu.add_command(label=paste_label,
                         command=lambda: self._paste_frame(frame_idx),
                         state="normal" if self._copied_frame_idx is not None else "disabled")
        menu.add_separator()
        menu.add_command(label=f"Set Duration ({self._timeline._frames[frame_idx].duration_ms}ms)...",
                         command=lambda: self._edit_frame_duration(frame_idx))
        menu.add_separator()
        menu.add_command(label="Delete Frame",
                         command=lambda: self._on_delete_frame(frame_idx))

        # Multi-frame selection operations
        if len(self._selected_frames) >= 2:
            sel_min = min(self._selected_frames)
            sel_max = max(self._selected_frames)
            count = sel_max - sel_min + 1
            menu.add_separator()
            menu.add_command(
                label=f"Delete Selected ({count} frames)",
                command=self._on_delete_selected_frames)
            menu.add_command(
                label=f"Add Tag on Selection ({sel_min+1}-{sel_max+1})",
                command=lambda: self._add_tag_on_selection(sel_min, sel_max))
        menu.add_separator()
        menu.add_command(label="Add Tag Here...",
                         command=lambda: self._add_tag_at_frame(frame_idx))

    def _add_tag_at_frame(self, frame_idx):
        """Open tag dialog pre-filled with the clicked frame."""
        if not self._timeline:
            return
        from src.ui.tag_dialog import TagDialog
        prefill = {"name": "", "color": "#00ff00",
                   "start": frame_idx, "end": frame_idx}
        dialog = TagDialog(self.winfo_toplevel(), self._timeline.frame_count,
                           tag=prefill)
        self.winfo_toplevel().wait_window(dialog)
        if dialog.result is not None:
            self._timeline.add_tag(
                dialog.result["name"], dialog.result["color"],
                dialog.result["start"], dialog.result["end"])
            self.refresh()

    def _show_frame_context_menu(self, event, frame_idx):
        """Right-click context menu on a frame header."""
        menu = tk.Menu(self, tearoff=0, bg=BG_PANEL, fg=TEXT_PRIMARY,
                       activebackground=ACCENT_CYAN, activeforeground=BG_DEEP,
                       font=("Consolas", 9))
        self._build_frame_menu(menu, frame_idx)
        menu.tk_popup(event.x_root, event.y_root)

    def _show_cel_context_menu(self, event, frame_idx, layer_idx):
        """Right-click context menu on a cel."""
        self._select_cel(frame_idx, layer_idx)
        menu = tk.Menu(self, tearoff=0, bg=BG_PANEL, fg=TEXT_PRIMARY,
                       activebackground=ACCENT_CYAN, activeforeground=BG_DEEP,
                       font=("Consolas", 9))
        self._build_frame_menu(menu, frame_idx)
        menu.add_separator()
        menu.add_command(label="Delete Layer",
                         command=lambda: self._on_delete_layer(layer_idx))
        menu.tk_popup(event.x_root, event.y_root)

    def _show_layer_context_menu(self, event, layer_idx):
        """Right-click context menu on a layer sidebar label."""
        menu = tk.Menu(self, tearoff=0, bg=BG_PANEL, fg=TEXT_PRIMARY,
                       activebackground=ACCENT_CYAN, activeforeground=BG_DEEP,
                       font=("Consolas", 9))
        is_group = False
        if self._timeline:
            frame = self._timeline.current_frame_obj()
            layer = frame.layers[layer_idx]
            is_group = layer.is_group

        if is_group:
            menu.add_command(label="Rename Group",
                             command=lambda: self._rename_layer(layer_idx))
            menu.add_separator()
            num_layers = len(frame.layers)
            menu.add_command(label="Move Up",
                             command=lambda: self._on_move_layer(layer_idx, layer_idx + 1),
                             state="normal" if layer_idx < num_layers - 1 else "disabled")
            menu.add_command(label="Move Down",
                             command=lambda: self._on_move_layer(layer_idx, layer_idx - 1),
                             state="normal" if layer_idx > 0 else "disabled")
            menu.add_separator()
            menu.add_command(label="Delete Group",
                             command=lambda: self._on_delete_layer(layer_idx))
        else:
            menu.add_command(label="Rename Layer",
                             command=lambda: self._rename_layer(layer_idx))
            menu.add_command(label="Duplicate Layer",
                             command=lambda: self._on_duplicate_layer(layer_idx))
            menu.add_separator()
            num_layers = len(frame.layers) if self._timeline else 0
            menu.add_command(label="Move Up",
                             command=lambda: self._on_move_layer(layer_idx, layer_idx + 1),
                             state="normal" if layer_idx < num_layers - 1 else "disabled")
            menu.add_command(label="Move Down",
                             command=lambda: self._on_move_layer(layer_idx, layer_idx - 1),
                             state="normal" if layer_idx > 0 else "disabled")

            # Group operations
            if self._timeline:
                # "Move to Group" submenu
                groups = [(i, l) for i, l in enumerate(frame.layers)
                          if l.is_group]
                if groups:
                    menu.add_separator()
                    group_menu = tk.Menu(menu, tearoff=0, bg=BG_PANEL,
                                         fg=TEXT_PRIMARY,
                                         activebackground=ACCENT_CYAN,
                                         activeforeground=BG_DEEP,
                                         font=("Consolas", 9))
                    for gi, gl in groups:
                        group_menu.add_command(
                            label=gl.name,
                            command=lambda li=layer_idx, gidx=gi: self._move_to_group(li, gidx))
                    menu.add_cascade(label="Move to Group", menu=group_menu)

                # "Remove from Group" if inside a group
                if layer.depth > 0:
                    menu.add_command(label="Remove from Group",
                                     command=lambda: self._remove_from_group(layer_idx))

            menu.add_separator()
            menu.add_command(label="Delete Layer",
                             command=lambda: self._on_delete_layer(layer_idx))
        menu.tk_popup(event.x_root, event.y_root)

    def _copy_frame(self, frame_idx):
        """Store frame index for later paste."""
        self._copied_frame_idx = frame_idx

    def _paste_frame(self, after_idx):
        """Duplicate the copied frame and insert it after after_idx."""
        if self._copied_frame_idx is None or not self._timeline:
            return
        src = self._copied_frame_idx
        if 0 <= src < len(self._timeline._frames):
            self._timeline.duplicate_frame(src)
            # Move the duplicated frame (at src+1) to after after_idx
            dup_pos = src + 1
            target = after_idx + 1 if after_idx >= src else after_idx + 1
            if dup_pos != target:
                self._timeline.move_frame(dup_pos, target)
            self._timeline.set_current(target)
            if self._callbacks["frame_select"]:
                self._callbacks["frame_select"](target)
        self.refresh()

    def _insert_frame_at(self, after_index):
        """Insert a new frame after the given index."""
        if after_index < 0:
            after_index = -1  # Will insert at position 0
        if self._callbacks["frame_insert"]:
            self._callbacks["frame_insert"](after_index)
        self.refresh()

    def _on_delete_frame(self, frame_idx):
        if self._timeline and len(self._timeline._frames) > 1:
            self._timeline.set_current(frame_idx)
            if self._callbacks["frame_delete"]:
                self._callbacks["frame_delete"]()
            self.refresh()

    def _on_delete_selected_frames(self):
        """Delete all frames in the multi-frame selection."""
        if not self._timeline or not self._selected_frames:
            return
        # Delete from highest index to lowest to avoid index shifting
        indices = sorted(self._selected_frames, reverse=True)
        # Must keep at least one frame
        total = len(self._timeline._frames)
        max_delete = total - 1
        for i, idx in enumerate(indices):
            if i >= max_delete:
                break
            self._timeline.remove_frame(idx)
        self._selected_frames.clear()
        self._anchor_frame = None
        if self._callbacks["frame_select"]:
            self._callbacks["frame_select"](self._timeline.current_index)
        self.refresh()

    def _add_tag_on_selection(self, start, end):
        """Open tag dialog pre-filled with the selected frame range."""
        if not self._timeline:
            return
        from src.ui.tag_dialog import TagDialog
        prefill = {"name": "", "color": "#00ff00",
                   "start": start, "end": end}
        dialog = TagDialog(self.winfo_toplevel(), self._timeline.frame_count,
                           tag=prefill)
        self.winfo_toplevel().wait_window(dialog)
        if dialog.result is not None:
            self._timeline.add_tag(
                dialog.result["name"], dialog.result["color"],
                dialog.result["start"], dialog.result["end"])
            self.refresh()

    def _on_duplicate_frame(self, frame_idx):
        if self._callbacks["frame_duplicate"]:
            self._timeline.set_current(frame_idx)
            self._callbacks["frame_duplicate"]()
        self.refresh()

    def _on_duplicate_frame_linked(self, frame_idx):
        if self._timeline:
            self._timeline.set_current(frame_idx)
            self._timeline.duplicate_frame_linked(frame_idx)
            self._timeline.set_current(frame_idx + 1)
        self.refresh()

    def _on_delete_layer(self, layer_idx):
        if self._timeline:
            self._timeline.set_active_layer_all(layer_idx)
            if self._callbacks["layer_delete"]:
                self._callbacks["layer_delete"]()
            self.refresh()

    def _on_duplicate_layer(self, layer_idx):
        if self._timeline:
            self._timeline.set_active_layer_all(layer_idx)
            if self._callbacks["layer_duplicate"]:
                self._callbacks["layer_duplicate"]()
            self.refresh()

    def _on_move_layer(self, from_idx, to_idx):
        if self._timeline:
            self._timeline.move_layer_in_all(from_idx, to_idx)
            if self._callbacks.get("layer_select"):
                self._callbacks["layer_select"](to_idx)
            self.refresh()

    def _move_to_group(self, layer_idx, group_idx):
        """Move a layer into a group via context menu."""
        if self._timeline:
            self._timeline.move_layer_into_group(layer_idx, group_idx)
            if self._callbacks.get("layer_select"):
                frame = self._timeline.current_frame_obj()
                self._callbacks["layer_select"](frame.active_layer_index)
            self.refresh()

    def _remove_from_group(self, layer_idx):
        """Remove a layer from its group via context menu."""
        if self._timeline:
            self._timeline.move_layer_out_of_group(layer_idx)
            if self._callbacks.get("layer_select"):
                frame = self._timeline.current_frame_obj()
                self._callbacks["layer_select"](frame.active_layer_index)
            self.refresh()

    # --- Layer drag-to-reorder ---

    def _on_layer_drag(self, event, source_idx):
        """Handle dragging a layer row to reorder."""
        self._drag_source_idx = source_idx

        # Find which layer row the cursor is over
        target_idx = self._layer_idx_at_y(event)
        if target_idx is None:
            return

        # Draw drop indicator
        self._clear_drag_indicator()
        target_row = self._layer_rows.get(target_idx)
        if target_row and target_idx != source_idx:
            # Highlight the target row
            self._drag_indicator = tk.Frame(self._layer_inner, height=2,
                                             bg=ACCENT_CYAN)
            # Position above or below target depending on direction
            # Layers are displayed top-down (highest index first)
            try:
                target_row.update_idletasks()
                y = target_row.winfo_y()
                if source_idx > target_idx:
                    # Moving up in index = moving down visually
                    y = y + target_row.winfo_height()
                self._drag_indicator.place(x=0, y=y,
                                            relwidth=1.0, height=3)
            except Exception:
                pass

    def _on_layer_drop(self, event, source_idx):
        """Handle dropping a layer after drag."""
        self._clear_drag_indicator()
        if self._drag_source_idx is None:
            return

        target_idx = self._layer_idx_at_y(event)
        if target_idx is not None and target_idx != source_idx and self._timeline:
            frame = self._timeline.current_frame_obj()
            source_layer = frame.layers[source_idx]
            target_layer = frame.layers[target_idx]

            if not source_layer.is_group and target_layer.is_group:
                # Dropping onto a group row — move into group
                self._move_to_group(source_idx, target_idx)
            elif source_layer.depth > 0 and target_layer.depth == 0 and not target_layer.is_group:
                # Dropping a grouped layer onto a root-level layer — remove from group
                self._remove_from_group(source_idx)
            else:
                # Normal reorder
                self._on_move_layer(source_idx, target_idx)

        self._drag_source_idx = None

    def _layer_idx_at_y(self, event):
        """Find which layer index the cursor is over based on y position."""
        # Convert event coords to layer_inner coords
        try:
            widget = event.widget
            y_in_inner = widget.winfo_rooty() + event.y - self._layer_inner.winfo_rooty()
        except Exception:
            return None

        for idx, row in self._layer_rows.items():
            try:
                ry = row.winfo_y()
                rh = row.winfo_height()
                if ry <= y_in_inner <= ry + rh:
                    return idx
            except Exception:
                continue
        return None

    def _clear_drag_indicator(self):
        """Remove the drag drop indicator line."""
        if self._drag_indicator is not None:
            self._drag_indicator.destroy()
            self._drag_indicator = None

    def _draw_tags(self, container, num_frames):
        """Draw colored tag bars above frame columns with stacking, drag, and right-click."""
        if not self._timeline or not self._timeline.tags:
            return

        tags = self._timeline.tags

        # Assign rows for overlapping tags (greedy)
        rows_assigned = []  # list of (tag_index, row)
        occupied = []  # list of list of (start, end) per row

        for ti, tag in enumerate(tags):
            start = tag.get("start", 0)
            end = tag.get("end", 0)
            placed = False
            for row_idx, row_ranges in enumerate(occupied):
                overlap = False
                for rs, re in row_ranges:
                    if start <= re and end >= rs:
                        overlap = True
                        break
                if not overlap:
                    row_ranges.append((start, end))
                    rows_assigned.append((ti, row_idx))
                    placed = True
                    break
            if not placed:
                occupied.append([(start, end)])
                rows_assigned.append((ti, len(occupied) - 1))

        num_rows = len(occupied) if occupied else 0
        if num_rows > 0:
            container.configure(height=num_rows * 16)

        for ti, row_idx in rows_assigned:
            tag = tags[ti]
            color = tag.get("color", ACCENT_CYAN)
            if not (isinstance(color, str) and color.startswith("#") and len(color) >= 7):
                color = ACCENT_CYAN
            start = tag.get("start", 0)
            end = tag.get("end", 0)
            name = tag.get("name", "")

            x_start = start * (self._cel_size + 2)
            width = (end - start + 1) * (self._cel_size + 2)
            y = row_idx * 16

            tag_lbl = tk.Label(container, text=name, font=("Consolas", 7),
                               bg=color, fg=BG_DEEP, anchor="center",
                               cursor="hand2")
            tag_lbl.place(x=x_start, y=y, width=max(width, 10), height=14)

            # Right-click context menu
            tag_lbl.bind("<Button-3>",
                         lambda e, idx=ti: self._show_tag_context_menu(e, idx))
            # Double-click to edit
            tag_lbl.bind("<Double-Button-1>",
                         lambda e, idx=ti: self._edit_tag(idx))

            # Drag to resize edges
            tag_lbl.bind("<Button-1>",
                         lambda e, idx=ti, lbl=tag_lbl: self._tag_drag_start(e, idx, lbl))
            tag_lbl.bind("<B1-Motion>",
                         lambda e, idx=ti: self._tag_drag_motion(e, idx))
            tag_lbl.bind("<ButtonRelease-1>",
                         lambda e, idx=ti: self._tag_drag_end(e, idx))

    def _show_tag_context_menu(self, event, tag_idx):
        """Right-click menu on a tag bar."""
        menu = tk.Menu(self, tearoff=0, bg=BG_PANEL, fg=TEXT_PRIMARY,
                       activebackground=ACCENT_CYAN, activeforeground=BG_DEEP,
                       font=("Consolas", 9))
        menu.add_command(label="Edit Tag...",
                         command=lambda: self._edit_tag(tag_idx))
        menu.add_command(label="Delete Tag",
                         command=lambda: self._delete_tag(tag_idx))
        menu.tk_popup(event.x_root, event.y_root)

    def _edit_tag(self, tag_idx):
        """Open tag dialog to edit an existing tag."""
        if not self._timeline or tag_idx >= len(self._timeline.tags):
            return
        from src.ui.tag_dialog import TagDialog
        tag = self._timeline.tags[tag_idx]
        dialog = TagDialog(self.winfo_toplevel(), self._timeline.frame_count, tag=tag)
        self.winfo_toplevel().wait_window(dialog)
        if dialog.result is not None:
            self._timeline.tags[tag_idx] = dialog.result
            self.refresh()

    def _delete_tag(self, tag_idx):
        """Delete a tag by index."""
        if self._timeline:
            self._timeline.remove_tag(tag_idx)
            self.refresh()

    def _tag_drag_start(self, event, tag_idx, label):
        """Start dragging a tag edge to resize."""
        x_in_label = event.x
        label_width = label.winfo_width()
        if x_in_label <= 8:
            self._tag_drag_edge = "start"
        elif x_in_label >= label_width - 8:
            self._tag_drag_edge = "end"
        else:
            self._tag_drag_edge = None
        self._tag_drag_idx = tag_idx
        self._tag_drag_label = label

    def _tag_drag_motion(self, event, tag_idx):
        """Handle drag motion to resize tag range."""
        if not hasattr(self, '_tag_drag_edge') or self._tag_drag_edge is None:
            return
        if not self._timeline or tag_idx >= len(self._timeline.tags):
            return

        try:
            container_x = event.x_root - self._grid_inner.winfo_rootx()
            frame_idx = int(container_x / (self._cel_size + 2))
            frame_idx = max(0, min(self._timeline.frame_count - 1, frame_idx))
        except Exception:
            return

        tag = self._timeline.tags[tag_idx]
        if self._tag_drag_edge == "start":
            tag["start"] = min(frame_idx, tag["end"])
        elif self._tag_drag_edge == "end":
            tag["end"] = max(frame_idx, tag["start"])

        # Update label position directly (no full refresh — that destroys the label)
        x_start = tag["start"] * (self._cel_size + 2)
        width = (tag["end"] - tag["start"] + 1) * (self._cel_size + 2)
        self._tag_drag_label.place_configure(x=x_start, width=max(width, 10))

    def _tag_drag_end(self, event, tag_idx):
        """End tag edge drag — do a full refresh to fix layout."""
        self._tag_drag_edge = None
        self._tag_drag_idx = None
        self._tag_drag_label = None
        self.refresh()

    def _on_frame_click(self, event, frame_idx):
        """Handle click on frame header — shift-click for range selection."""
        if event.state & 0x1 and self._anchor_frame is not None:
            lo = min(self._anchor_frame, frame_idx)
            hi = max(self._anchor_frame, frame_idx)
            self._selected_frames = set(range(lo, hi + 1))
        else:
            self._anchor_frame = frame_idx
            self._selected_frames.clear()
        if self._callbacks["frame_select"]:
            self._callbacks["frame_select"](frame_idx)
        else:
            self.refresh()

    def _select_cel(self, frame_idx, layer_idx):
        # Clear multi-frame selection on cel click
        self._selected_frames.clear()
        self._anchor_frame = None
        # Set frame and layer atomically to avoid intermediate inconsistent state
        if self._timeline:
            self._timeline.set_current(frame_idx)
            self._timeline.set_active_layer_all(layer_idx)
        # Notify app of the change (frame_select triggers canvas refresh)
        if self._callbacks["frame_select"]:
            self._callbacks["frame_select"](frame_idx)
        self.refresh()

    def _select_layer(self, layer_idx):
        if self._callbacks["layer_select"]:
            self._callbacks["layer_select"](layer_idx)
        self.refresh()

    def _toggle_visibility(self, layer_idx):
        if self._callbacks["layer_visibility"]:
            self._callbacks["layer_visibility"](layer_idx)
        self.refresh()

    def _toggle_lock(self, layer_idx):
        if self._callbacks["layer_lock"]:
            self._callbacks["layer_lock"](layer_idx)
        self.refresh()

    def _toggle_group_collapse(self, group_idx):
        self._collapsed_groups[group_idx] = not self._collapsed_groups.get(group_idx, False)
        self.refresh()

    def _on_blend_change(self, layer_idx, value):
        cb = self._callbacks.get("layer_blend_mode")
        if cb:
            cb(layer_idx, value)

    def _show_blend_tooltip(self, event, blend_var):
        """Show tooltip with current blend mode name."""
        self._hide_blend_tooltip()
        x = event.widget.winfo_rootx() + event.widget.winfo_width() + 4
        y = event.widget.winfo_rooty()
        self._blend_tooltip = tk.Toplevel()
        self._blend_tooltip.wm_overrideredirect(True)
        self._blend_tooltip.wm_geometry(f"+{x}+{y}")
        label = tk.Label(self._blend_tooltip, text=blend_var.get(),
                         bg=BG_PANEL, fg=ACCENT_CYAN,
                         font=("Consolas", 8), padx=6, pady=2,
                         relief="solid", bd=1)
        label.pack()

    def _hide_blend_tooltip(self):
        tip = getattr(self, "_blend_tooltip", None)
        if tip:
            tip.destroy()
            self._blend_tooltip = None

    def _on_layer_fx(self, layer_idx):
        cb = self._callbacks.get("layer_fx")
        if cb:
            cb(layer_idx)

    def _rename_layer(self, layer_idx):
        if self._callbacks["layer_rename"]:
            self._callbacks["layer_rename"](layer_idx)

    def _edit_frame_duration(self, frame_idx):
        """Open inline edit for frame duration."""
        if not self._timeline:
            return
        from tkinter import simpledialog
        frame = self._timeline._frames[frame_idx]
        new_ms = simpledialog.askinteger(
            "Frame Duration", f"Duration for frame {frame_idx + 1} (ms):",
            initialvalue=frame.duration_ms, minvalue=10, maxvalue=5000
        )
        if new_ms is not None:
            frame.duration_ms = new_ms
            if self._callbacks["frame_duration_change"]:
                self._callbacks["frame_duration_change"](frame_idx, new_ms)
            self.refresh()

    def _on_play(self):
        self._playing = True
        self._play_btn.config(fg=ACCENT_CYAN)
        if self._callbacks["play"]:
            self._callbacks["play"]()

    def _on_stop(self):
        self._playing = False
        self._play_btn.config(fg=TEXT_PRIMARY)
        if self._callbacks["stop"]:
            self._callbacks["stop"]()

    def _step_forward(self):
        if self._timeline:
            idx = self._timeline._current_index
            num = len(self._timeline._frames)
            self._select_cel((idx + 1) % num,
                             self._timeline._frames[idx].active_layer_index)

    def _step_back(self):
        if self._timeline:
            idx = self._timeline._current_index
            num = len(self._timeline._frames)
            self._select_cel((idx - 1) % num,
                             self._timeline._frames[idx].active_layer_index)

    def _cycle_playback_mode(self):
        modes = [("fwd", "forward"), ("rev", "reverse"), ("pp", "pingpong")]
        idx = 0
        for i, (label, _) in enumerate(modes):
            if self._mode_var.get() == label:
                idx = i
                break
        next_idx = (idx + 1) % len(modes)
        self._mode_var.set(modes[next_idx][0])
        self._playback_mode = modes[next_idx][1]
        if self._callbacks["playback_mode"]:
            self._callbacks["playback_mode"](self._playback_mode)

    def _toggle_onion(self):
        self._onion_on = not self._onion_on
        self._onion_btn.config(
            text=f"Onion: {'On' if self._onion_on else 'Off'}",
            fg=ACCENT_CYAN if self._onion_on else TEXT_PRIMARY
        )
        if self._callbacks["onion_toggle"]:
            self._callbacks["onion_toggle"](self._onion_on)

    def _on_onion_range(self):
        self._onion_range = self._onion_range_var.get()
        if self._callbacks["onion_range_change"]:
            self._callbacks["onion_range_change"](self._onion_range)

    def _on_add_frame(self):
        if self._callbacks["frame_add"]:
            self._callbacks["frame_add"]()
        self.refresh()

    def _on_add_layer(self):
        if self._callbacks["layer_add"]:
            self._callbacks["layer_add"]()
        self.refresh()

    # --- Drag resize ---
    def _on_drag_start(self, event):
        self._drag_start_y = event.y_root
        self._drag_start_height = self.winfo_height()

    def _on_drag_motion(self, event):
        delta = self._drag_start_y - event.y_root
        new_height = max(100, min(400, self._drag_start_height + delta))
        self.config(height=new_height)


    def highlight_frame(self, frame_idx):
        """Lightweight update: only recolor frame headers and cel column highlights.

        Used during playback to avoid full widget rebuild (which causes flashing).
        """
        if not self._timeline or not hasattr(self, '_header_widgets'):
            return
        frames = self._timeline._frames
        num_frames = len(frames)
        active_layer = frames[frame_idx].active_layer_index if frame_idx < num_frames else 0

        # Update headers
        for fi, (header, lbl, dur_lbl) in self._header_widgets.items():
            is_current = (fi == frame_idx)
            bg = ACCENT_CYAN if is_current else BG_PANEL
            fg = BG_DEEP if is_current else TEXT_SECONDARY
            header.configure(bg=bg)
            lbl.configure(bg=bg, fg=fg)
            dur_lbl.configure(bg=bg, fg=fg)

        # Update cels
        for (fi, li), (cel, dot) in self._cel_widgets.items():
            is_current_frame = (fi == frame_idx)
            is_active_layer = (li == active_layer)
            has_content = False
            if fi < num_frames and li < len(frames[fi].layers):
                has_content = frames[fi].layers[li].pixels._pixels.any()

            if is_current_frame and is_active_layer:
                bg = ACCENT_CYAN
                fg = BG_DEEP
            elif is_current_frame:
                bg = blend_color(BG_PANEL_ALT, ACCENT_CYAN, 0.15)
                fg = ACCENT_CYAN
            elif is_active_layer:
                bg = BG_PANEL_ALT
                fg = ACCENT_CYAN
            else:
                bg = BG_PANEL if has_content else BG_DEEP
                fg = TEXT_SECONDARY
            cel.configure(bg=bg)
            dot.configure(bg=bg, fg=fg)

    def set_timeline(self, timeline):
        self._timeline = timeline
        self.refresh()
