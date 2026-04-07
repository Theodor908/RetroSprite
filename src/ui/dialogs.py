"""Dialog windows for RetroSprite — cyberpunk neon themed."""
from __future__ import annotations
import os
import tkinter as tk
from tkinter import filedialog, messagebox

from src.recents import load_recents

from src.ui.theme import (
    BG_DEEP, BG_PANEL, BG_PANEL_ALT, BORDER, TEXT_PRIMARY, TEXT_SECONDARY,
    ACCENT_CYAN, ACCENT_MAGENTA, ACCENT_PURPLE, BUTTON_BG, BUTTON_HOVER,
    blend_color,
)


def _draw_gradient_bar(canvas, color1, color2, height=2):
    """Draw a horizontal gradient bar on a canvas widget."""
    def _redraw(event=None):
        canvas.delete("all")
        w = canvas.winfo_width()
        if w < 2:
            return
        steps = min(w, 80)
        seg = w / steps
        for i in range(steps):
            c = blend_color(color1, color2, i / max(1, steps - 1))
            x1 = int(i * seg)
            x2 = int((i + 1) * seg)
            canvas.create_rectangle(x1, 0, x2, height, fill=c, outline="")
    canvas.bind("<Configure>", _redraw)
    canvas.after(10, _redraw)


def _neon_hover(btn, hover_color=ACCENT_CYAN, normal_bg=BUTTON_BG):
    """Add neon hover effect to a button."""
    btn.bind("<Enter>", lambda e: btn.config(bg=hover_color, fg=BG_DEEP))
    btn.bind("<Leave>", lambda e: btn.config(bg=normal_bg, fg=TEXT_PRIMARY))


def ask_custom_canvas_size(parent) -> tuple[int, int] | None:
    """Show themed custom canvas size dialog with aspect ratio presets.

    Returns (width, height) tuple or None if cancelled.
    The dialog is modal relative to parent but does not destroy parent.
    """
    dialog = tk.Toplevel(parent)
    dialog.title("Custom Canvas Size")
    dialog.geometry("300x320")
    dialog.resizable(False, False)
    dialog.configure(bg=BG_DEEP)
    dialog.transient(parent)
    dialog.grab_set()

    result = [None]

    # Top gradient bar
    top_bar = tk.Canvas(dialog, height=2, bg=BG_DEEP, highlightthickness=0)
    top_bar.pack(fill="x")
    _draw_gradient_bar(top_bar, ACCENT_CYAN, ACCENT_PURPLE)

    tk.Label(dialog, text="Custom Canvas Size", fg=ACCENT_CYAN, bg=BG_DEEP,
             font=("Consolas", 11, "bold")).pack(pady=(12, 8))

    # Width field
    w_frame = tk.Frame(dialog, bg=BG_DEEP)
    w_frame.pack(fill="x", padx=40, pady=4)
    tk.Label(w_frame, text="Width:", font=("Consolas", 9),
             bg=BG_DEEP, fg=TEXT_PRIMARY).pack(side="left")
    w_var = tk.StringVar(value="64")
    w_entry = tk.Entry(w_frame, textvariable=w_var, width=8, bg=BG_PANEL_ALT,
                       fg=TEXT_PRIMARY, insertbackground=ACCENT_CYAN,
                       font=("Consolas", 9), highlightthickness=1,
                       highlightbackground=BORDER, highlightcolor=ACCENT_CYAN)
    w_entry.pack(side="right")

    # Height field
    h_frame = tk.Frame(dialog, bg=BG_DEEP)
    h_frame.pack(fill="x", padx=40, pady=4)
    tk.Label(h_frame, text="Height:", font=("Consolas", 9),
             bg=BG_DEEP, fg=TEXT_PRIMARY).pack(side="left")
    h_var = tk.StringVar(value="64")
    h_entry = tk.Entry(h_frame, textvariable=h_var, width=8, bg=BG_PANEL_ALT,
                       fg=TEXT_PRIMARY, insertbackground=ACCENT_CYAN,
                       font=("Consolas", 9), highlightthickness=1,
                       highlightbackground=BORDER, highlightcolor=ACCENT_CYAN)
    h_entry.pack(side="right")

    # Error label (hidden by default)
    error_var = tk.StringVar(value="")
    error_label = tk.Label(dialog, textvariable=error_var, fg=ACCENT_MAGENTA,
                           bg=BG_DEEP, font=("Consolas", 8))
    error_label.pack(pady=(2, 0))

    # Aspect ratio presets
    tk.Label(dialog, text="Aspect Ratio Presets", fg=TEXT_SECONDARY, bg=BG_DEEP,
             font=("Consolas", 8)).pack(pady=(8, 2))

    preset_frame = tk.Frame(dialog, bg=BG_DEEP)
    preset_frame.pack()

    def _apply_ratio(rw, rh):
        """Set height based on current width and the chosen ratio."""
        try:
            w = int(w_var.get())
        except ValueError:
            w = 64
        h = max(1, round(w * rh / rw))
        h_var.set(str(h))
        error_var.set("")

    ratios = [("1:1", 1, 1), ("4:3", 4, 3), ("3:4", 3, 4),
              ("16:9", 16, 9), ("9:16", 9, 16)]
    for label, rw, rh in ratios:
        btn = tk.Button(
            preset_frame, text=label, width=4, bg=BG_PANEL_ALT, fg=TEXT_PRIMARY,
            activebackground=ACCENT_PURPLE, activeforeground=BG_DEEP,
            relief="flat", font=("Consolas", 8),
            command=lambda rw_=rw, rh_=rh: _apply_ratio(rw_, rh_)
        )
        btn.pack(side="left", padx=2, pady=2)
        _neon_hover(btn, ACCENT_PURPLE, BG_PANEL_ALT)

    # Buttons
    btn_row = tk.Frame(dialog, bg=BG_DEEP)
    btn_row.pack(pady=(16, 8))

    def _create():
        try:
            w = int(w_var.get())
            h = int(h_var.get())
        except ValueError:
            error_var.set("Width and height must be integers")
            return
        if w < 1 or h < 1:
            error_var.set("Values must be at least 1")
            return
        if w > 2048 or h > 2048:
            error_var.set("Maximum size is 2048x2048")
            return
        result[0] = (w, h)
        dialog.destroy()

    create_btn = tk.Button(
        btn_row, text="Create", width=10, bg=ACCENT_CYAN, fg=BG_DEEP,
        activebackground=ACCENT_MAGENTA, activeforeground=BG_DEEP,
        relief="flat", font=("Consolas", 9, "bold"), command=_create
    )
    create_btn.pack(side="left", padx=4)
    _neon_hover(create_btn, ACCENT_MAGENTA, ACCENT_CYAN)

    cancel_btn = tk.Button(
        btn_row, text="Cancel", width=10, bg=BUTTON_BG, fg=TEXT_PRIMARY,
        activebackground=BUTTON_HOVER, activeforeground=TEXT_PRIMARY,
        relief="flat", font=("Consolas", 9), command=dialog.destroy
    )
    cancel_btn.pack(side="left", padx=4)
    _neon_hover(cancel_btn)

    # Bottom gradient bar
    bot_bar = tk.Canvas(dialog, height=2, bg=BG_DEEP, highlightthickness=0)
    bot_bar.pack(side="bottom", fill="x")
    _draw_gradient_bar(bot_bar, ACCENT_PURPLE, ACCENT_CYAN)

    # Select width field on open
    w_entry.focus_set()
    w_entry.select_range(0, "end")

    dialog.wait_window()
    return result[0]


def ask_canvas_size(parent) -> tuple[int, int] | None:
    dialog = tk.Toplevel(parent)
    dialog.title("New Canvas")
    dialog.geometry("260x260")
    dialog.resizable(False, False)
    dialog.configure(bg=BG_DEEP)
    dialog.transient(parent)
    dialog.grab_set()

    result = [None]

    # Top gradient border
    top_bar = tk.Canvas(dialog, height=2, bg=BG_DEEP, highlightthickness=0)
    top_bar.pack(fill="x")
    _draw_gradient_bar(top_bar, ACCENT_CYAN, ACCENT_PURPLE)

    tk.Label(dialog, text="Canvas Size", fg=ACCENT_CYAN, bg=BG_DEEP,
             font=("Consolas", 12, "bold")).pack(pady=(12, 8))

    sizes = [(8, 8), (16, 16), (32, 32), (64, 64), (128, 128)]
    for w, h in sizes:
        btn = tk.Button(
            dialog, text=f"{w} x {h}", width=14, bg=BUTTON_BG, fg=TEXT_PRIMARY,
            activebackground=ACCENT_CYAN, activeforeground=BG_DEEP,
            relief="flat", font=("Consolas", 9),
            command=lambda ww=w, hh=h: (result.__setitem__(0, (ww, hh)),
                                         dialog.destroy())
        )
        btn.pack(pady=2)
        _neon_hover(btn)

    def _custom():
        size = ask_custom_canvas_size(dialog)
        if size is not None:
            result[0] = size
        dialog.destroy()

    custom_btn = tk.Button(
        dialog, text="Custom...", width=14, bg=BG_PANEL_ALT, fg=TEXT_PRIMARY,
        activebackground=ACCENT_MAGENTA, activeforeground=BG_DEEP,
        relief="flat", font=("Consolas", 9), command=_custom
    )
    custom_btn.pack(pady=2)
    _neon_hover(custom_btn, ACCENT_MAGENTA, BG_PANEL_ALT)

    dialog.wait_window()
    return result[0]


def ask_startup(parent) -> dict | None:
    """Show startup dialog with cyberpunk neon theme."""
    dialog = tk.Toplevel(parent)
    dialog.title("RetroSprite")
    dialog.geometry("420x580")
    dialog.resizable(False, False)
    dialog.configure(bg=BG_DEEP)
    dialog.grab_set()
    dialog.focus_force()

    result = [None]

    # Top gradient border
    top_bar = tk.Canvas(dialog, height=3, bg=BG_DEEP, highlightthickness=0)
    top_bar.pack(fill="x")
    _draw_gradient_bar(top_bar, ACCENT_CYAN, ACCENT_MAGENTA, height=3)

    # Glow title using a canvas
    title_canvas = tk.Canvas(dialog, width=300, height=50, bg=BG_DEEP,
                             highlightthickness=0)
    title_canvas.pack(pady=(16, 0))

    # Shadow/glow layers
    for offset, color in [(2, ACCENT_PURPLE), (1, ACCENT_MAGENTA)]:
        title_canvas.create_text(150 + offset, 25 + offset, text="RetroSprite",
                                 font=("Consolas", 18, "bold"), fill=color)
    title_canvas.create_text(150, 25, text="RetroSprite",
                             font=("Consolas", 18, "bold"), fill=ACCENT_CYAN)

    tk.Label(dialog, text="Pixel Art Creator", fg=TEXT_SECONDARY, bg=BG_DEEP,
             font=("Consolas", 9)).pack(pady=(0, 12))

    # Feature Guide button
    from src.ui.help_window import show_feature_guide
    guide_btn = tk.Button(
        dialog, text="\u2630  Feature Guide", width=24,
        bg=BUTTON_BG, fg=TEXT_PRIMARY, relief="flat",
        activebackground=ACCENT_CYAN, activeforeground=BG_DEEP,
        font=("Consolas", 9, "bold"),
        command=lambda: show_feature_guide(dialog)
    )
    guide_btn.pack(pady=(4, 8))
    _neon_hover(guide_btn)

    # Separator
    sep1 = tk.Canvas(dialog, height=1, bg=BG_DEEP, highlightthickness=0)
    sep1.pack(fill="x", padx=30)
    _draw_gradient_bar(sep1, ACCENT_CYAN, ACCENT_PURPLE, height=1)

    # New canvas section
    tk.Label(dialog, text="New Canvas", fg=ACCENT_CYAN, bg=BG_DEEP,
             font=("Consolas", 10, "bold")).pack(pady=(10, 4))

    sizes = [(16, 16), (32, 32), (64, 64), (128, 128)]
    btn_frame = tk.Frame(dialog, bg=BG_DEEP)
    btn_frame.pack()
    for w, h in sizes:
        btn = tk.Button(
            btn_frame, text=f"{w}x{h}", width=6, bg=BUTTON_BG, fg=TEXT_PRIMARY,
            activebackground=ACCENT_CYAN, activeforeground=BG_DEEP,
            relief="flat", font=("Consolas", 9),
            command=lambda ww=w, hh=h: (
                result.__setitem__(0, {"action": "new", "size": (ww, hh)}),
                dialog.destroy())
        )
        btn.pack(side="left", padx=3, pady=2)
        _neon_hover(btn)

    def _custom_new():
        size = ask_custom_canvas_size(dialog)
        if size is not None:
            result[0] = {"action": "new", "size": size}
            dialog.destroy()

    custom_btn = tk.Button(
        dialog, text="Custom Size...", width=18, bg=BG_PANEL_ALT, fg=TEXT_PRIMARY,
        activebackground=ACCENT_MAGENTA, activeforeground=BG_DEEP,
        relief="flat", font=("Consolas", 9), command=_custom_new
    )
    custom_btn.pack(pady=6)
    _neon_hover(custom_btn, ACCENT_MAGENTA, BG_PANEL_ALT)

    # Separator
    sep2 = tk.Canvas(dialog, height=1, bg=BG_DEEP, highlightthickness=0)
    sep2.pack(fill="x", padx=30, pady=8)
    _draw_gradient_bar(sep2, ACCENT_MAGENTA, ACCENT_PURPLE, height=1)

    # Open project section
    tk.Label(dialog, text="Open Project", fg=ACCENT_MAGENTA, bg=BG_DEEP,
             font=("Consolas", 10, "bold")).pack(pady=(4, 4))

    def _open_project():
        path = filedialog.askopenfilename(
            parent=dialog,
            filetypes=[("RetroSprite Projects", "*.retro"),
                       ("All files", "*.*")]
        )
        if path:
            result[0] = {"action": "open", "path": path}
            dialog.destroy()

    open_btn = tk.Button(
        dialog, text="Open .retro Project...", width=24,
        bg=ACCENT_MAGENTA, fg="#fff", relief="flat",
        activebackground=ACCENT_CYAN, activeforeground=BG_DEEP,
        font=("Consolas", 10, "bold"),
        command=_open_project
    )
    open_btn.pack(pady=6)
    open_btn.bind("<Enter>", lambda e: open_btn.config(bg=ACCENT_CYAN, fg=BG_DEEP))
    open_btn.bind("<Leave>", lambda e: open_btn.config(bg=ACCENT_MAGENTA, fg="#fff"))

    # Separator
    sep3 = tk.Canvas(dialog, height=1, bg=BG_DEEP, highlightthickness=0)
    sep3.pack(fill="x", padx=30, pady=8)
    _draw_gradient_bar(sep3, ACCENT_PURPLE, ACCENT_CYAN, height=1)

    # Recent projects section
    tk.Label(dialog, text="Recent Projects", fg=ACCENT_PURPLE, bg=BG_DEEP,
             font=("Consolas", 10, "bold")).pack(pady=(4, 4))

    recents = load_recents()
    if recents:
        for entry in recents:
            path = entry["path"]
            filename = os.path.basename(path)
            dirpath = os.path.dirname(path)

            item_frame = tk.Frame(dialog, bg=BG_DEEP, cursor="hand2")
            item_frame.pack(fill="x", padx=30, pady=1)

            name_label = tk.Label(
                item_frame, text=filename, fg=TEXT_PRIMARY, bg=BG_DEEP,
                font=("Consolas", 9), anchor="w"
            )
            name_label.pack(fill="x")

            dir_label = tk.Label(
                item_frame, text=dirpath, fg=TEXT_SECONDARY, bg=BG_DEEP,
                font=("Consolas", 7), anchor="w"
            )
            dir_label.pack(fill="x")

            def _open_recent(p=path):
                result[0] = {"action": "open", "path": p}
                dialog.destroy()

            for widget in (item_frame, name_label, dir_label):
                widget.bind("<Button-1>", lambda e, p=path: _open_recent(p))
                widget.bind("<Enter>", lambda e, f=item_frame, n=name_label, d=dir_label:
                            (f.config(bg=BG_PANEL_ALT),
                             n.config(bg=BG_PANEL_ALT, fg=ACCENT_CYAN),
                             d.config(bg=BG_PANEL_ALT)))
                widget.bind("<Leave>", lambda e, f=item_frame, n=name_label, d=dir_label:
                            (f.config(bg=BG_DEEP),
                             n.config(bg=BG_DEEP, fg=TEXT_PRIMARY),
                             d.config(bg=BG_DEEP)))
    else:
        tk.Label(dialog, text="No recent projects", fg=TEXT_SECONDARY,
                 bg=BG_DEEP, font=("Consolas", 8)).pack(pady=4)

    # Bottom gradient border
    bot_bar = tk.Canvas(dialog, height=3, bg=BG_DEEP, highlightthickness=0)
    bot_bar.pack(side="bottom", fill="x")
    _draw_gradient_bar(bot_bar, ACCENT_PURPLE, ACCENT_CYAN, height=3)

    dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
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


def ask_save_before(parent) -> bool | None:
    """Ask user to save before discarding current project.
    Returns: True=save, False=discard, None=cancel."""
    return messagebox.askyesnocancel(
        "Save Project",
        "Do you want to save the current project before continuing?",
        parent=parent
    )


def ask_color_ramp(parent, fg_color, bg_color) -> dict | None:
    """Show color ramp generator dialog.
    Returns dict with keys: start, end, steps, mode — or None if cancelled."""
    dialog = tk.Toplevel(parent)
    dialog.title("Generate Color Ramp")
    dialog.geometry("320x280")
    dialog.resizable(False, False)
    dialog.configure(bg=BG_DEEP)
    dialog.transient(parent)
    dialog.grab_set()

    result = [None]

    top_bar = tk.Canvas(dialog, height=2, bg=BG_DEEP, highlightthickness=0)
    top_bar.pack(fill="x")
    _draw_gradient_bar(top_bar, ACCENT_CYAN, ACCENT_PURPLE)

    tk.Label(dialog, text="Color Ramp Generator", fg=ACCENT_CYAN, bg=BG_DEEP,
             font=("Consolas", 11, "bold")).pack(pady=(10, 8))

    # Start color display
    start_frame = tk.Frame(dialog, bg=BG_DEEP)
    start_frame.pack(fill="x", padx=20, pady=2)
    tk.Label(start_frame, text="Start:", font=("Consolas", 9),
             bg=BG_DEEP, fg=TEXT_PRIMARY).pack(side="left")
    start_swatch = tk.Canvas(start_frame, width=24, height=16, bg=BG_DEEP,
                             highlightthickness=1, highlightbackground=BORDER)
    start_swatch.pack(side="left", padx=4)
    sc = f"#{fg_color[0]:02x}{fg_color[1]:02x}{fg_color[2]:02x}"
    start_swatch.create_rectangle(0, 0, 24, 16, fill=sc, outline="")
    tk.Label(start_frame, text=f"({fg_color[0]},{fg_color[1]},{fg_color[2]})",
             font=("Consolas", 8), bg=BG_DEEP, fg=TEXT_SECONDARY).pack(side="left", padx=4)

    # End color display
    end_frame = tk.Frame(dialog, bg=BG_DEEP)
    end_frame.pack(fill="x", padx=20, pady=2)
    tk.Label(end_frame, text="End:  ", font=("Consolas", 9),
             bg=BG_DEEP, fg=TEXT_PRIMARY).pack(side="left")
    end_swatch = tk.Canvas(end_frame, width=24, height=16, bg=BG_DEEP,
                           highlightthickness=1, highlightbackground=BORDER)
    end_swatch.pack(side="left", padx=4)
    ec = f"#{bg_color[0]:02x}{bg_color[1]:02x}{bg_color[2]:02x}"
    end_swatch.create_rectangle(0, 0, 24, 16, fill=ec, outline="")
    tk.Label(end_frame, text=f"({bg_color[0]},{bg_color[1]},{bg_color[2]})",
             font=("Consolas", 8), bg=BG_DEEP, fg=TEXT_SECONDARY).pack(side="left", padx=4)

    # Steps spinner
    steps_frame = tk.Frame(dialog, bg=BG_DEEP)
    steps_frame.pack(fill="x", padx=20, pady=6)
    tk.Label(steps_frame, text="Steps:", font=("Consolas", 9),
             bg=BG_DEEP, fg=TEXT_PRIMARY).pack(side="left")
    steps_var = tk.IntVar(value=8)
    tk.Button(steps_frame, text="-", width=2, font=("Consolas", 8),
              bg=BUTTON_BG, fg=TEXT_PRIMARY, relief="flat",
              command=lambda: steps_var.set(max(2, steps_var.get() - 1))
              ).pack(side="left", padx=2)
    tk.Label(steps_frame, textvariable=steps_var, font=("Consolas", 9, "bold"),
             bg=BG_DEEP, fg=TEXT_PRIMARY, width=3).pack(side="left")
    tk.Button(steps_frame, text="+", width=2, font=("Consolas", 8),
              bg=BUTTON_BG, fg=TEXT_PRIMARY, relief="flat",
              command=lambda: steps_var.set(min(32, steps_var.get() + 1))
              ).pack(side="left", padx=2)

    # Interpolation mode
    mode_frame = tk.Frame(dialog, bg=BG_DEEP)
    mode_frame.pack(fill="x", padx=20, pady=4)
    tk.Label(mode_frame, text="Mode:", font=("Consolas", 9),
             bg=BG_DEEP, fg=TEXT_PRIMARY).pack(side="left")
    mode_var = tk.StringVar(value="rgb")
    tk.Radiobutton(mode_frame, text="RGB", variable=mode_var, value="rgb",
                   bg=BG_DEEP, fg=TEXT_PRIMARY, selectcolor=BG_PANEL,
                   activebackground=BG_DEEP, activeforeground=ACCENT_CYAN,
                   font=("Consolas", 9)).pack(side="left", padx=8)
    tk.Radiobutton(mode_frame, text="HSV", variable=mode_var, value="hsv",
                   bg=BG_DEEP, fg=TEXT_PRIMARY, selectcolor=BG_PANEL,
                   activebackground=BG_DEEP, activeforeground=ACCENT_CYAN,
                   font=("Consolas", 9)).pack(side="left", padx=8)

    # Preview strip
    preview_canvas = tk.Canvas(dialog, height=24, bg=BG_PANEL_ALT,
                               highlightthickness=1, highlightbackground=BORDER)
    preview_canvas.pack(fill="x", padx=20, pady=8)

    def _update_preview(*_args):
        preview_canvas.delete("all")
        from src.palette import generate_ramp
        steps = steps_var.get()
        mode = mode_var.get()
        ramp = generate_ramp(fg_color, bg_color, steps, mode)
        pw = preview_canvas.winfo_width()
        if pw < 2:
            pw = 280
        seg = pw / max(1, len(ramp))
        for i, c in enumerate(ramp):
            x1 = int(i * seg)
            x2 = int((i + 1) * seg)
            hex_c = f"#{c[0]:02x}{c[1]:02x}{c[2]:02x}"
            preview_canvas.create_rectangle(x1, 0, x2, 24, fill=hex_c, outline="")

    steps_var.trace_add("write", _update_preview)
    mode_var.trace_add("write", _update_preview)
    dialog.after(50, _update_preview)

    # Buttons
    btn_frame = tk.Frame(dialog, bg=BG_DEEP)
    btn_frame.pack(fill="x", padx=20, pady=8)

    def _add():
        result[0] = {
            "start": fg_color,
            "end": bg_color,
            "steps": steps_var.get(),
            "mode": mode_var.get(),
        }
        dialog.destroy()

    add_btn = tk.Button(btn_frame, text="Add to Palette", width=14,
                        bg=ACCENT_CYAN, fg=BG_DEEP, relief="flat",
                        font=("Consolas", 9, "bold"), command=_add)
    add_btn.pack(side="left", padx=4)
    _neon_hover(add_btn, ACCENT_MAGENTA, ACCENT_CYAN)

    cancel_btn = tk.Button(btn_frame, text="Cancel", width=10,
                           bg=BUTTON_BG, fg=TEXT_PRIMARY, relief="flat",
                           font=("Consolas", 9), command=dialog.destroy)
    cancel_btn.pack(side="left", padx=4)
    _neon_hover(cancel_btn)

    dialog.wait_window()
    return result[0]
