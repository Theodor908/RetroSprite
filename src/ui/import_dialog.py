"""Import dialogs for RetroSprite — animated, sprite sheet, PNG sequence."""
from __future__ import annotations
import os
import tkinter as tk
from tkinter import filedialog
from src.animated_import import ImportSettings
from src.ui.theme import (
    BG_DEEP, BG_PANEL, TEXT_PRIMARY, TEXT_SECONDARY,
    ACCENT_CYAN, ACCENT_MAGENTA, BUTTON_BG, BUTTON_HOVER,
)


class ImportDialog(tk.Toplevel):
    """Shared import options dialog shown after parsing an animated file.

    Collects: project mode, canvas resize strategy, timing preference.

    Usage:
        dialog = ImportDialog(parent, n_frames=12, src_w=64, src_h=48,
                              duration_range=(50, 200), source_name="explosion.gif",
                              canvas_w=32, canvas_h=32, project_fps=10)
        parent.wait_window(dialog)
        settings = dialog.result  # ImportSettings or None
    """

    def __init__(self, parent, *, n_frames: int, src_w: int, src_h: int,
                 duration_range: tuple[int, int], source_name: str,
                 canvas_w: int, canvas_h: int, project_fps: int):
        super().__init__(parent)
        self.title("Import Animation")
        self.configure(bg=BG_DEEP)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._src_w = src_w
        self._src_h = src_h
        self._canvas_w = canvas_w
        self._canvas_h = canvas_h
        self._project_fps = project_fps
        self.result: ImportSettings | None = None

        self._build_ui(n_frames, source_name, duration_range)

        # Center on parent
        self.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        w = self.winfo_width()
        h = self.winfo_height()
        self.geometry(f"+{px + (pw - w) // 2}+{py + (ph - h) // 2}")

    def _build_ui(self, n_frames, source_name, duration_range):
        font = ("Consolas", 9)
        pad = {"padx": 10, "pady": 4}

        # Source info
        info = f"{source_name}  ({n_frames} frames, {self._src_w}\u00d7{self._src_h})"
        tk.Label(self, text=info, bg=BG_DEEP, fg=ACCENT_CYAN,
                 font=("Consolas", 9, "bold")).pack(**pad, anchor="w")

        # --- Project Mode ---
        tk.Label(self, text="Project Mode", bg=BG_DEEP, fg=TEXT_SECONDARY,
                 font=font).pack(**pad, anchor="w")
        self._mode_var = tk.StringVar(value="new_project")
        for val, label in [("new_project", "New Project (replaces current canvas)"),
                           ("insert", "Insert as Frames (after current frame)")]:
            tk.Radiobutton(
                self, text=label, variable=self._mode_var, value=val,
                bg=BG_DEEP, fg=TEXT_PRIMARY, selectcolor=BG_PANEL,
                activebackground=BG_DEEP, activeforeground=ACCENT_CYAN,
                font=font, command=self._on_mode_change,
            ).pack(padx=20, anchor="w")

        # --- Canvas Size (insert mode only) ---
        self._resize_frame = tk.Frame(self, bg=BG_DEEP)
        self._resize_frame.pack(fill="x", **pad)
        tk.Label(self._resize_frame, text="Canvas Size", bg=BG_DEEP,
                 fg=TEXT_SECONDARY, font=font).pack(anchor="w")
        self._resize_var = tk.StringVar(value="scale")
        for val, label in [
            ("match", f"Resize canvas to match ({self._src_w}\u00d7{self._src_h})"),
            ("scale", f"Scale import to fit canvas ({self._canvas_w}\u00d7{self._canvas_h})"),
            ("crop", "Center and crop to canvas"),
        ]:
            tk.Radiobutton(
                self._resize_frame, text=label, variable=self._resize_var,
                value=val, bg=BG_DEEP, fg=TEXT_PRIMARY, selectcolor=BG_PANEL,
                activebackground=BG_DEEP, activeforeground=ACCENT_CYAN,
                font=font,
            ).pack(padx=20, anchor="w")

        # --- Timing ---
        tk.Label(self, text="Timing", bg=BG_DEEP, fg=TEXT_SECONDARY,
                 font=font).pack(**pad, anchor="w")
        self._timing_var = tk.StringVar(value="original")
        min_d, max_d = duration_range
        fps_ms = max(1, 1000 // self._project_fps)
        for val, label in [
            ("original", f"Keep original timing ({min_d}\u2013{max_d}ms per frame)"),
            ("project_fps", f"Use project FPS ({fps_ms}ms per frame)"),
        ]:
            tk.Radiobutton(
                self, text=label, variable=self._timing_var, value=val,
                bg=BG_DEEP, fg=TEXT_PRIMARY, selectcolor=BG_PANEL,
                activebackground=BG_DEEP, activeforeground=ACCENT_CYAN,
                font=font,
            ).pack(padx=20, anchor="w")

        # --- Buttons ---
        btn_row = tk.Frame(self, bg=BG_DEEP)
        btn_row.pack(fill="x", pady=(12, 8), padx=10)
        cancel_btn = tk.Button(
            btn_row, text="Cancel", bg=BUTTON_BG, fg=TEXT_PRIMARY,
            font=font, relief="flat", padx=16, pady=4,
            command=self._on_cancel)
        cancel_btn.pack(side="right", padx=4)
        import_btn = tk.Button(
            btn_row, text="Import", bg=ACCENT_CYAN, fg=BG_DEEP,
            font=("Consolas", 9, "bold"), relief="flat", padx=16, pady=4,
            command=self._on_import)
        import_btn.pack(side="right", padx=4)

        self._on_mode_change()

    def _on_mode_change(self):
        if self._mode_var.get() == "new_project":
            for child in self._resize_frame.winfo_children():
                child.configure(state="disabled")
        else:
            for child in self._resize_frame.winfo_children():
                child.configure(state="normal")

    def _on_cancel(self):
        self.result = None
        self.destroy()

    def _on_import(self):
        self.result = ImportSettings(
            mode=self._mode_var.get(),
            resize=self._resize_var.get(),
            timing=self._timing_var.get(),
        )
        self.destroy()


class SpriteSheetDialog(tk.Toplevel):
    """Pre-dialog for sprite sheet import — JSON or manual grid config.

    Usage:
        dialog = SpriteSheetDialog(parent, png_path)
        parent.wait_window(dialog)
        result = dialog.result
        # result is ("json", json_path) or ("grid", cols, rows, fw, fh) or None
    """

    def __init__(self, parent, png_path: str):
        super().__init__(parent)
        self.title("Import Sprite Sheet")
        self.configure(bg=BG_DEEP)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._png_path = png_path
        self.result = None

        self._build_ui()

        self.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        w = self.winfo_width()
        h = self.winfo_height()
        self.geometry(f"+{px + (pw - w) // 2}+{py + (ph - h) // 2}")

    def _build_ui(self):
        font = ("Consolas", 9)
        pad = {"padx": 10, "pady": 4}

        self._mode_var = tk.StringVar(value="json")

        # JSON mode
        tk.Radiobutton(
            self, text="Use JSON metadata (RetroSprite format)",
            variable=self._mode_var, value="json",
            bg=BG_DEEP, fg=TEXT_PRIMARY, selectcolor=BG_PANEL,
            activebackground=BG_DEEP, activeforeground=ACCENT_CYAN,
            font=font, command=self._on_mode_change,
        ).pack(**pad, anchor="w")

        json_row = tk.Frame(self, bg=BG_DEEP)
        json_row.pack(fill="x", padx=20, pady=2)
        self._json_path_var = tk.StringVar(value="")
        self._json_browse_btn = tk.Button(
            json_row, text="Browse .json", bg=BUTTON_BG, fg=TEXT_PRIMARY,
            font=font, relief="flat", command=self._browse_json)
        self._json_browse_btn.pack(side="left")
        self._json_label = tk.Label(
            json_row, textvariable=self._json_path_var,
            bg=BG_DEEP, fg=TEXT_SECONDARY, font=font)
        self._json_label.pack(side="left", padx=8)

        # Grid mode
        tk.Radiobutton(
            self, text="Manual grid",
            variable=self._mode_var, value="grid",
            bg=BG_DEEP, fg=TEXT_PRIMARY, selectcolor=BG_PANEL,
            activebackground=BG_DEEP, activeforeground=ACCENT_CYAN,
            font=font, command=self._on_mode_change,
        ).pack(**pad, anchor="w")

        grid_frame = tk.Frame(self, bg=BG_DEEP)
        grid_frame.pack(fill="x", padx=20, pady=2)
        self._grid_widgets = []
        self._cols_var = tk.IntVar(value=4)
        self._rows_var = tk.IntVar(value=3)
        self._fw_var = tk.IntVar(value=32)
        self._fh_var = tk.IntVar(value=32)
        for label_text, var in [("Columns:", self._cols_var),
                                ("Rows:", self._rows_var),
                                ("Frame W:", self._fw_var),
                                ("Frame H:", self._fh_var)]:
            lbl = tk.Label(grid_frame, text=label_text, bg=BG_DEEP,
                           fg=TEXT_PRIMARY, font=font)
            lbl.pack(side="left", padx=(4, 0))
            spin = tk.Spinbox(grid_frame, from_=1, to=999, width=4,
                              textvariable=var, font=font,
                              bg=BG_PANEL, fg=TEXT_PRIMARY,
                              buttonbackground=BUTTON_BG)
            spin.pack(side="left", padx=(0, 4))
            self._grid_widgets.extend([lbl, spin])

        # Buttons
        btn_row = tk.Frame(self, bg=BG_DEEP)
        btn_row.pack(fill="x", pady=(12, 8), padx=10)
        tk.Button(
            btn_row, text="Cancel", bg=BUTTON_BG, fg=TEXT_PRIMARY,
            font=font, relief="flat", padx=16, pady=4,
            command=self._on_cancel).pack(side="right", padx=4)
        tk.Button(
            btn_row, text="Next \u2192", bg=ACCENT_CYAN, fg=BG_DEEP,
            font=("Consolas", 9, "bold"), relief="flat", padx=16, pady=4,
            command=self._on_next).pack(side="right", padx=4)

        self._on_mode_change()

    def _on_mode_change(self):
        is_json = self._mode_var.get() == "json"
        state_json = "normal" if is_json else "disabled"
        state_grid = "disabled" if is_json else "normal"
        self._json_browse_btn.configure(state=state_json)
        for w in self._grid_widgets:
            w.configure(state=state_grid)

    def _browse_json(self):
        path = filedialog.askopenfilename(
            parent=self, filetypes=[("JSON files", "*.json")],
            initialdir=os.path.dirname(self._png_path))
        if path:
            self._json_path_var.set(os.path.basename(path))
            self._json_full_path = path

    def _on_cancel(self):
        self.result = None
        self.destroy()

    def _on_next(self):
        if self._mode_var.get() == "json":
            json_path = getattr(self, "_json_full_path", "")
            if not json_path:
                return
            self.result = ("json", json_path)
        else:
            self.result = ("grid", self._cols_var.get(), self._rows_var.get(),
                           self._fw_var.get(), self._fh_var.get())
        self.destroy()


class PngSequenceDialog(tk.Toplevel):
    """Pre-dialog for PNG sequence import — folder scan or multi-select.

    Usage:
        dialog = PngSequenceDialog(parent)
        parent.wait_window(dialog)
        result = dialog.result  # list[str] of PNG paths, or None
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Import PNG Sequence")
        self.configure(bg=BG_DEEP)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.result: list[str] | None = None
        self._paths: list[str] = []

        self._build_ui()

        self.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        w = self.winfo_width()
        h = self.winfo_height()
        self.geometry(f"+{px + (pw - w) // 2}+{py + (ph - h) // 2}")

    def _build_ui(self):
        font = ("Consolas", 9)
        pad = {"padx": 10, "pady": 4}

        self._mode_var = tk.StringVar(value="folder")

        # Folder scan mode
        tk.Radiobutton(
            self, text="Scan folder for numbered PNGs",
            variable=self._mode_var, value="folder",
            bg=BG_DEEP, fg=TEXT_PRIMARY, selectcolor=BG_PANEL,
            activebackground=BG_DEEP, activeforeground=ACCENT_CYAN,
            font=font,
        ).pack(**pad, anchor="w")

        folder_row = tk.Frame(self, bg=BG_DEEP)
        folder_row.pack(fill="x", padx=20, pady=2)
        self._folder_btn = tk.Button(
            folder_row, text="Browse Folder", bg=BUTTON_BG, fg=TEXT_PRIMARY,
            font=font, relief="flat", command=self._browse_folder)
        self._folder_btn.pack(side="left")
        self._folder_info = tk.StringVar(value="")
        tk.Label(folder_row, textvariable=self._folder_info,
                 bg=BG_DEEP, fg=TEXT_SECONDARY, font=font).pack(side="left", padx=8)

        # Multi-select mode
        tk.Radiobutton(
            self, text="Select individual files",
            variable=self._mode_var, value="files",
            bg=BG_DEEP, fg=TEXT_PRIMARY, selectcolor=BG_PANEL,
            activebackground=BG_DEEP, activeforeground=ACCENT_CYAN,
            font=font,
        ).pack(**pad, anchor="w")

        files_row = tk.Frame(self, bg=BG_DEEP)
        files_row.pack(fill="x", padx=20, pady=2)
        self._files_btn = tk.Button(
            files_row, text="Browse Files", bg=BUTTON_BG, fg=TEXT_PRIMARY,
            font=font, relief="flat", command=self._browse_files)
        self._files_btn.pack(side="left")
        self._files_info = tk.StringVar(value="")
        tk.Label(files_row, textvariable=self._files_info,
                 bg=BG_DEEP, fg=TEXT_SECONDARY, font=font).pack(side="left", padx=8)

        # Buttons
        btn_row = tk.Frame(self, bg=BG_DEEP)
        btn_row.pack(fill="x", pady=(12, 8), padx=10)
        tk.Button(
            btn_row, text="Cancel", bg=BUTTON_BG, fg=TEXT_PRIMARY,
            font=font, relief="flat", padx=16, pady=4,
            command=self._on_cancel).pack(side="right", padx=4)
        tk.Button(
            btn_row, text="Next \u2192", bg=ACCENT_CYAN, fg=BG_DEEP,
            font=("Consolas", 9, "bold"), relief="flat", padx=16, pady=4,
            command=self._on_next).pack(side="right", padx=4)

    def _browse_folder(self):
        from src.sequence_import import scan_folder_for_pngs
        folder = filedialog.askdirectory(parent=self)
        if folder:
            self._paths = scan_folder_for_pngs(folder)
            if self._paths:
                first = os.path.basename(self._paths[0])
                last = os.path.basename(self._paths[-1])
                self._folder_info.set(
                    f"Found: {first} ... {last} ({len(self._paths)} files)")
            else:
                self._folder_info.set("No PNG files found")

    def _browse_files(self):
        from src.sequence_import import _natural_sort_key
        files = filedialog.askopenfilenames(
            parent=self, filetypes=[("PNG files", "*.png")])
        if files:
            self._paths = sorted(files, key=_natural_sort_key)
            self._files_info.set(f"{len(self._paths)} files selected")

    def _on_cancel(self):
        self.result = None
        self.destroy()

    def _on_next(self):
        if self._paths:
            self.result = self._paths
        self.destroy()
