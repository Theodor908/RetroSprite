"""File operations mixin for RetroSprite (save, load, export, import, auto-save)."""
from __future__ import annotations

import os
import threading

from PIL import Image

from src.pixel_data import PixelGrid
from src.compression import compress_grid, decompress_grid, save_rle, load_rle
from src.animation import AnimationTimeline
from src.palette import Palette
from src.project import save_project, load_project
from src.tool_settings import ToolSettingsManager
from src.recents import update_recents
from src.ui.dialogs import (
    ask_canvas_size, ask_save_file, ask_open_file,
    ask_save_before, show_info, show_error, ask_color_ramp,
)


class FileOpsMixin:
    """Save, load, export, import, auto-save, palette I/O, and project lifecycle."""

    # ------------------------------------------------------------------
    # Save / Save-As
    # ------------------------------------------------------------------

    def _save_project(self):
        """Save to current project path, or prompt for path."""
        self._tool_settings.save(self.current_tool_name.lower(), self._capture_current_tool_settings())
        if self._project_path:
            if not self.api.emit("before_save", {"filepath": self._project_path}):
                return
            try:
                save_project(self._project_path, self.timeline, self.palette,
                             tool_settings=self._tool_settings.to_dict(),
                             reference_image=self._reference,
                             grid_settings=self._grid_settings.to_dict(),
                             symmetry_axis_x=self._symmetry_axis_x,
                             symmetry_axis_y=self._symmetry_axis_y)
                self._dirty = False
                self._update_status("Project saved")
                self.api.emit("after_save", {"filepath": self._project_path})
            except Exception as e:
                show_error(self.root, "Save Error", str(e))
        else:
            self._save_project_as()

    def _save_project_as(self):
        """Save project to a new .retro file."""
        path = ask_save_file(
            self.root,
            filetypes=[("RetroSprite Projects", "*.retro")]
        )
        if path:
            if not path.endswith(".retro"):
                path += ".retro"
            if not self.api.emit("before_save", {"filepath": path}):
                return
            try:
                self._tool_settings.save(self.current_tool_name.lower(), self._capture_current_tool_settings())
                save_project(path, self.timeline, self.palette,
                             tool_settings=self._tool_settings.to_dict(),
                             reference_image=self._reference,
                             grid_settings=self._grid_settings.to_dict(),
                             symmetry_axis_x=self._symmetry_axis_x,
                             symmetry_axis_y=self._symmetry_axis_y)
                self._project_path = path
                update_recents(path)
                self._dirty = False
                self.root.title(f"RetroSprite - {path}")
                self._update_status("Project saved")
                self.api.emit("after_save", {"filepath": path})
            except Exception as e:
                show_error(self.root, "Save Error", str(e))

    # ------------------------------------------------------------------
    # Open / New / Image import
    # ------------------------------------------------------------------

    def _open_project(self):
        """Open a .retro project file."""
        if not self._check_save_before():
            return
        path = ask_open_file(
            self.root,
            filetypes=[("RetroSprite Projects", "*.retro"),
                       ("Aseprite Files", "*.ase;*.aseprite"),
                       ("Photoshop Files", "*.psd"),
                       ("All files", "*.*")]
        )
        if not path:
            return
        if not self.api.emit("before_load", {"filepath": path}):
            return
        ext = os.path.splitext(path)[1].lower()
        if ext in ('.ase', '.aseprite'):
            from src.aseprite_import import load_aseprite
            try:
                self.timeline, palette = load_aseprite(path)
                self.palette.colors = palette.colors
                self.palette.selected_index = 0
            except Exception as e:
                show_error(self.root, "Import Error", str(e))
                return
            loaded_ref = None
        elif ext == '.psd':
            from src.psd_import import load_psd
            try:
                self.timeline, palette = load_psd(path)
                self.palette.colors = palette.colors
                self.palette.selected_index = 0
            except Exception as e:
                show_error(self.root, "Import Error", str(e))
                return
            loaded_ref = None
        else:
            try:
                self.timeline, self.palette, tool_settings_data, loaded_ref, grid_data = load_project(path)
            except Exception as e:
                show_error(self.root, "Open Error", str(e))
                return
        self.api.timeline = self.timeline
        self.api.palette = self.palette
        self._reset_state()
        self._reference = loaded_ref
        if self._reference is not None:
            self._ref_opacity_var.set(self._reference.opacity)
        if ext not in ('.ase', '.aseprite', '.psd'):
            if grid_data is not None:
                from src.grid import GridSettings
                self._grid_settings = GridSettings.from_dict(grid_data)
            else:
                from src.grid import GridSettings
                self._grid_settings = GridSettings()
            self._pixel_grid_var.set(self._grid_settings.pixel_grid_visible)
            self._custom_grid_var.set(self._grid_settings.custom_grid_visible)
            self._update_grid_widget()
            if grid_data:
                ax = grid_data.get("symmetry_axis_x") if isinstance(grid_data, dict) else None
                ay = grid_data.get("symmetry_axis_y") if isinstance(grid_data, dict) else None
                if ax is not None:
                    self._symmetry_axis_x = ax
                if ay is not None:
                    self._symmetry_axis_y = ay
            self._tool_settings = ToolSettingsManager.from_dict(tool_settings_data)
            pen_settings = self._tool_settings.get("pen")
            self._apply_tool_settings(pen_settings)
        self._project_path = path
        update_recents(path)
        self.root.title(f"RetroSprite - {path}")
        self.right_panel.palette_panel.palette = self.palette
        self.right_panel.palette_panel.refresh()
        self.timeline_panel.set_timeline(self.timeline)
        self._refresh_all()
        self.api.emit("after_load", {"filepath": path})

    def _new_canvas(self):
        if not self._check_save_before():
            return
        size = ask_canvas_size(self.root)
        if not size:
            return
        w, h = size
        self._reset_state()
        from src.grid import GridSettings
        self._grid_settings = GridSettings()
        self._pixel_grid_var.set(True)
        self._custom_grid_var.set(False)
        self._update_grid_widget()
        self._reference = None
        self.timeline = AnimationTimeline(w, h)
        self._symmetry_axis_x = self.timeline.width // 2
        self._symmetry_axis_y = self.timeline.height // 2
        self.palette = Palette("Pico-8")
        self._project_path = None
        self.root.title("RetroSprite - Pixel Art Creator")
        self.right_panel.palette_panel.palette = self.palette
        self.right_panel.palette_panel.refresh()
        self.timeline_panel.set_timeline(self.timeline)
        self._refresh_all()

    def _open_image(self):
        path = ask_open_file(self.root)
        if path:
            try:
                img = Image.open(path).convert("RGBA")
                w, h = self.timeline.width, self.timeline.height
                if img.size != (w, h):
                    img = img.resize((w, h), Image.NEAREST)
                grid = PixelGrid.from_pil_image(img)
                frame_obj = self.timeline.current_frame_obj()
                frame_obj.active_layer.pixels = grid
                self._refresh_canvas()
            except Exception as e:
                show_error(self.root, "Open Error", str(e))

    def _import_animation(self):
        """Import animated files (GIF, APNG, WebP, sprite sheet, PNG sequence)."""
        path = ask_open_file(
            self.root,
            filetypes=[
                ("Animated files", "*.gif;*.apng;*.webp"),
                ("PNG / Sprite Sheet", "*.png"),
                ("All files", "*.*"),
            ]
        )
        if not path:
            return

        ext = os.path.splitext(path)[1].lower()
        try:
            animation = self._parse_import_file(path, ext)
        except Exception as e:
            show_error(self.root, "Import Error", str(e))
            return

        if animation is None:
            return  # user cancelled a sub-dialog

        # Show shared import dialog
        from src.ui.import_dialog import ImportDialog
        dur_min = min(animation.durations)
        dur_max = max(animation.durations)
        dialog = ImportDialog(
            self.root,
            n_frames=len(animation.frames),
            src_w=animation.width,
            src_h=animation.height,
            duration_range=(dur_min, dur_max),
            source_name=os.path.basename(animation.source_path),
            canvas_w=self.timeline.width,
            canvas_h=self.timeline.height,
            project_fps=self.timeline.fps,
        )
        self.root.wait_window(dialog)
        settings = dialog.result
        if settings is None:
            return

        # Build timeline
        from src.animated_import import build_timeline_from_import
        try:
            if settings.mode == "new_project":
                if not self._check_save_before():
                    return
                timeline, palette_colors = build_timeline_from_import(
                    animation, settings, project_fps=self.timeline.fps)
                self.timeline = timeline
                self.api.timeline = self.timeline
                if palette_colors:
                    self.palette.colors = palette_colors
                    self.palette.selected_index = 0
                self._reset_state()
                self.root.title(
                    f"RetroSprite - {os.path.basename(path)}")
                self.right_panel.palette_panel.palette = self.palette
                self.right_panel.palette_panel.refresh()
                self.timeline_panel.set_timeline(self.timeline)
                self._refresh_all()
            else:
                self._push_undo()
                build_timeline_from_import(
                    animation, settings,
                    existing_timeline=self.timeline,
                    project_fps=self.timeline.fps)
                self.timeline_panel.set_timeline(self.timeline)
                self._refresh_all()
        except Exception as e:
            show_error(self.root, "Import Error", str(e))

    def _parse_import_file(self, path, ext):
        """Parse a file into ImportedAnimation based on extension.

        Returns ImportedAnimation or None if user cancels a sub-dialog.
        """
        import tkinter as tk

        if ext == ".gif":
            from src.animated_import import parse_gif
            return parse_gif(path)
        elif ext == ".apng":
            from src.animated_import import parse_apng
            return parse_apng(path)
        elif ext == ".webp":
            from src.animated_import import parse_webp
            return parse_webp(path)
        elif ext == ".png":
            return self._handle_png_import(path)
        else:
            raise ValueError(f"Unsupported format: {ext}")

    def _handle_png_import(self, path):
        """Handle .png files — detect APNG or show format chooser."""
        import tkinter as tk
        from PIL import Image as PILImage

        img = PILImage.open(path)
        n_frames = getattr(img, "n_frames", 1)
        img.close()

        if n_frames > 1:
            from src.animated_import import parse_apng
            return parse_apng(path)

        # Ambiguous .png — ask user
        chooser = tk.Toplevel(self.root)
        chooser.title("PNG Import Type")
        chooser.configure(bg="#0d0d12")
        chooser.resizable(False, False)
        chooser.transient(self.root)
        chooser.grab_set()

        result = {"choice": None}
        font = ("Consolas", 9)

        tk.Label(chooser, text="How should this PNG be imported?",
                 bg="#0d0d12", fg="#e0e0e8", font=font).pack(padx=16, pady=(12, 8))

        for val, label in [("image", "Single Image"),
                           ("sheet", "Sprite Sheet"),
                           ("sequence", "PNG Sequence")]:
            tk.Button(
                chooser, text=label, bg="#1a1a2e", fg="#e0e0e8",
                font=font, relief="flat", width=20, pady=4,
                command=lambda v=val: (result.update(choice=v),
                                       chooser.destroy()),
            ).pack(padx=16, pady=2)

        tk.Button(
            chooser, text="Cancel", bg="#1a1a2e", fg="#7a7a9a",
            font=font, relief="flat", width=20, pady=4,
            command=chooser.destroy,
        ).pack(padx=16, pady=(2, 12))

        self.root.wait_window(chooser)

        choice = result["choice"]
        if choice is None:
            return None
        elif choice == "image":
            self._open_image_from_path(path)
            return None
        elif choice == "sheet":
            from src.ui.import_dialog import SpriteSheetDialog
            dialog = SpriteSheetDialog(self.root, path)
            self.root.wait_window(dialog)
            if dialog.result is None:
                return None
            if dialog.result[0] == "json":
                from src.sequence_import import parse_sprite_sheet_json
                return parse_sprite_sheet_json(path, dialog.result[1])
            else:
                _, cols, rows, fw, fh = dialog.result
                from src.sequence_import import parse_sprite_sheet_grid
                return parse_sprite_sheet_grid(path, cols, rows, fw, fh)
        elif choice == "sequence":
            from src.ui.import_dialog import PngSequenceDialog
            dialog = PngSequenceDialog(self.root)
            self.root.wait_window(dialog)
            if dialog.result is None:
                return None
            from src.sequence_import import parse_png_sequence
            return parse_png_sequence(dialog.result)
        return None

    def _open_image_from_path(self, path):
        """Import a single image into the current layer (no file dialog)."""
        try:
            img = Image.open(path).convert("RGBA")
            w, h = self.timeline.width, self.timeline.height
            if img.size != (w, h):
                img = img.resize((w, h), Image.NEAREST)
            grid = PixelGrid.from_pil_image(img)
            frame_obj = self.timeline.current_frame_obj()
            frame_obj.active_layer.pixels = grid
            self._refresh_canvas()
        except Exception as e:
            show_error(self.root, "Open Error", str(e))

    def _clear_canvas(self):
        self._push_undo()
        self.timeline.current_layer().clear()
        self._render_canvas()

    # ------------------------------------------------------------------
    # Reference image
    # ------------------------------------------------------------------

    def _load_reference_image(self):
        path = ask_open_file(self.root, filetypes=[
            ("Image files", "*.png;*.jpg;*.jpeg;*.bmp;*.gif"),
            ("All files", "*.*")
        ])
        if path:
            try:
                from src.reference_image import ReferenceImage
                img = Image.open(path).convert("RGBA")
                ref = ReferenceImage(image=img, path=path)
                ref.fit_to_canvas(self.timeline.width, self.timeline.height)
                self._reference = ref
                self._ref_opacity_var.set(ref.opacity)
                self._render_canvas()
                self._update_status(
                    "Reference image loaded (Alt+drag to move, Ctrl+Alt+scroll to resize)")
            except Exception as e:
                show_error(self.root, "Load Error", str(e))

    def _toggle_reference(self):
        if self._reference is not None:
            self._reference.visible = not self._reference.visible
            self._render_canvas()

    def _clear_reference(self):
        self._reference = None
        self._render_canvas()
        self._update_status("Reference image cleared")

    def _set_ref_opacity(self, value):
        if self._reference is not None:
            self._reference.opacity = value
            self._ref_opacity_var.set(value)
            self._render_canvas()

    # ------------------------------------------------------------------
    # Grid settings
    # ------------------------------------------------------------------

    def _toggle_pixel_grid(self):
        self._grid_settings.pixel_grid_visible = self._pixel_grid_var.get()
        self._render_canvas()

    def _toggle_custom_grid(self):
        self._grid_settings.custom_grid_visible = self._custom_grid_var.get()
        self._update_grid_widget()
        self._render_canvas()

    def _quick_toggle_custom_grid(self):
        self._grid_settings.custom_grid_visible = not self._grid_settings.custom_grid_visible
        self._custom_grid_var.set(self._grid_settings.custom_grid_visible)
        self._update_grid_widget()
        self._render_canvas()

    def _show_grid_settings(self):
        from src.ui.grid_dialog import GridSettingsDialog
        dialog = GridSettingsDialog(self.root, self._grid_settings)
        self.root.wait_window(dialog)
        if dialog.result is not None:
            self._grid_settings = dialog.result
            self._pixel_grid_var.set(self._grid_settings.pixel_grid_visible)
            self._custom_grid_var.set(self._grid_settings.custom_grid_visible)
            self._update_grid_widget()
            self._render_canvas()

    def _update_grid_widget(self):
        gs = self._grid_settings
        if gs.custom_grid_visible:
            text = f"Grid: {gs.custom_grid_width}\u00d7{gs.custom_grid_height}"
        else:
            text = "Grid: Off"
        if hasattr(self, '_grid_widget_label'):
            self._grid_widget_label.config(text=text)

    # ------------------------------------------------------------------
    # Export dialog
    # ------------------------------------------------------------------

    def _show_export_dialog(self):
        """Open the unified export dialog and dispatch to backend."""
        from src.ui.export_dialog import ExportDialog
        dialog = ExportDialog(self.root, self.timeline, self.palette,
                              self._export_settings)
        self.root.wait_window(dialog)
        settings = dialog.result
        if settings is None:
            return

        # Remember settings for next time
        self._export_settings = {
            "format": settings.format,
            "scale": settings.scale,
        }

        path = settings.output_path
        fmt = settings.format

        if not self.api.emit("before_export", {"filepath": path, "format": fmt}):
            return

        # Animated formats run in background thread
        if fmt in ("gif", "webp", "apng"):
            self._update_status(f"Exporting {fmt.upper()}...")

            def worker():
                try:
                    if fmt == "gif":
                        self.timeline.export_gif(path, fps=self.timeline.fps,
                                                 scale=settings.scale,
                                                 frame_start=settings.tag_start,
                                                 frame_end=settings.tag_end)
                    elif fmt == "webp":
                        from src.animated_export import export_webp
                        export_webp(self.timeline, path, scale=settings.scale,
                                    frame_start=settings.tag_start,
                                    frame_end=settings.tag_end)
                    elif fmt == "apng":
                        from src.animated_export import export_apng
                        export_apng(self.timeline, path, scale=settings.scale,
                                    frame_start=settings.tag_start,
                                    frame_end=settings.tag_end)
                    self.root.after(0, lambda: self.api.emit(
                        "after_export", {"filepath": path, "format": fmt}))
                    self.root.after(0, lambda: show_info(
                        self.root, "Export", f"Exported to {path}"))
                except Exception as e:
                    self.root.after(0, lambda: show_error(
                        self.root, "Export Error", str(e)))
                finally:
                    self.root.after(0, lambda: self._update_status(""))

            threading.Thread(target=worker, daemon=True).start()
        else:
            # Synchronous formats
            try:
                if fmt == "png":
                    from src.export import export_png_single
                    export_png_single(self.timeline, path,
                                      frame=settings.frame, scale=settings.scale,
                                      layer=settings.layer)
                elif fmt == "sheet":
                    from src.export import save_sprite_sheet
                    save_sprite_sheet(self.timeline, path,
                                     scale=settings.scale,
                                     columns=settings.columns,
                                     frame_start=settings.tag_start,
                                     frame_end=settings.tag_end)
                elif fmt == "frames":
                    from src.export import export_png_sequence
                    export_png_sequence(self.timeline, path,
                                       scale=settings.scale,
                                       layer=settings.layer,
                                       frame_start=settings.tag_start,
                                       frame_end=settings.tag_end)
                self.api.emit("after_export", {"filepath": path, "format": fmt})
                show_info(self.root, "Export", f"Exported to {path}")
            except Exception as e:
                show_error(self.root, "Export Error", str(e))

    # ------------------------------------------------------------------
    # Compression (RLE)
    # ------------------------------------------------------------------

    def _compress_frame(self):
        grid = self.timeline.current_frame()
        encoded, stats = compress_grid(grid)
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
                frame_obj = self.timeline.current_frame_obj()
                frame_obj.active_layer.pixels = grid
                self._refresh_canvas()
                show_info(self.root, "Loaded", f"RLE loaded from {path}")
            except Exception as e:
                show_error(self.root, "Load Error", str(e))

    # ------------------------------------------------------------------
    # Palette import / export
    # ------------------------------------------------------------------

    def _import_palette(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            parent=self.root,
            title="Import Palette",
            filetypes=[
                ("All Palettes", "*.gpl;*.pal;*.hex;*.ase"),
                ("GIMP Palette", "*.gpl"), ("JASC PAL", "*.pal"),
                ("HEX", "*.hex"), ("Adobe ASE", "*.ase"),
            ]
        )
        if not path:
            return
        from src.palette_io import load_palette
        try:
            colors = load_palette(path)
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Import Error", str(e))
            return
        self.palette.colors.clear()
        self.palette.colors.extend(colors)
        self.palette.selected_index = 0
        self.right_panel.palette_panel.palette = self.palette
        self.right_panel.palette_panel.refresh()
        if getattr(self.timeline, 'color_mode', 'rgba') == "indexed":
            self.timeline.palette_ref = self.palette.colors
            self._update_indexed_palette_refs()
        self._update_status(f"Imported palette: {os.path.basename(path)}")

    def _export_palette(self):
        from tkinter import filedialog
        filetypes = [
            ("GIMP Palette", "*.gpl"), ("JASC PAL", "*.pal"),
            ("HEX", "*.hex"), ("Adobe ASE", "*.ase"),
        ]
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Export Palette",
            filetypes=filetypes,
            defaultextension=".gpl",
        )
        if not path:
            return
        from src.palette_io import save_palette
        try:
            save_palette(path, self.palette.colors, name=self.palette.name)
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Export Error", str(e))
            return
        self._update_status(f"Exported palette: {os.path.basename(path)}")

    def _load_builtin_palette(self, name: str):
        self.palette.set_palette(name)
        self.right_panel.palette_panel.refresh()
        self._update_status(f"Loaded palette: {name}")

    # ------------------------------------------------------------------
    # Color ramp
    # ------------------------------------------------------------------

    def _show_color_ramp_dialog(self):
        fg = self.palette.selected_color
        bg = self.palette.colors[-1] if len(self.palette.colors) > 1 else (255, 255, 255, 255)
        result = ask_color_ramp(self.root, fg, bg)
        if result:
            from src.palette import generate_ramp
            ramp = generate_ramp(result["start"], result["end"],
                                 result["steps"], result["mode"])
            for color in ramp:
                self.palette.add_color(color)
            self.right_panel.palette_panel.refresh()
            self._update_status(f"Added {len(ramp)} colors to palette")

    # ------------------------------------------------------------------
    # Indexed palette helpers
    # ------------------------------------------------------------------

    def _update_indexed_palette_refs(self):
        """Update _palette ref on all IndexedPixelGrid layers."""
        for i in range(self.timeline.frame_count):
            frame = self.timeline.get_frame_obj(i)
            for layer in frame.layers:
                if getattr(layer, 'color_mode', 'rgba') == "indexed" and hasattr(layer.pixels, '_palette'):
                    layer.pixels._palette = self.palette.colors

    # ------------------------------------------------------------------
    # Auto-save
    # ------------------------------------------------------------------

    def _schedule_auto_save(self):
        if self._dirty and self._project_path:
            try:
                self._tool_settings.save(self.current_tool_name.lower(), self._capture_current_tool_settings())
                save_project(self._project_path, self.timeline, self.palette,
                             tool_settings=self._tool_settings.to_dict(),
                             reference_image=self._reference,
                             grid_settings=self._grid_settings.to_dict(),
                             symmetry_axis_x=self._symmetry_axis_x,
                             symmetry_axis_y=self._symmetry_axis_y)
                self._update_status("Auto-saved")
                self.root.after(2000, lambda: self._update_status(""))
                self._dirty = False
            except Exception:
                pass
        self.root.after(self._auto_save_interval, self._schedule_auto_save)

    def _mark_dirty(self):
        self._dirty = True

    # ------------------------------------------------------------------
    # Save-before guard / close / reset
    # ------------------------------------------------------------------

    def _check_save_before(self) -> bool:
        """Ask user to save before a destructive action.
        Returns True if we can proceed, False to abort."""
        answer = ask_save_before(self.root)
        if answer is None:
            # Cancel — abort the operation
            return False
        if answer:
            # Yes — save first
            self._tool_settings.save(self.current_tool_name.lower(), self._capture_current_tool_settings())
            if self._project_path:
                try:
                    save_project(self._project_path, self.timeline, self.palette,
                                 tool_settings=self._tool_settings.to_dict(),
                                 reference_image=self._reference,
                                 grid_settings=self._grid_settings.to_dict(),
                                 symmetry_axis_x=self._symmetry_axis_x,
                                 symmetry_axis_y=self._symmetry_axis_y)
                except Exception as e:
                    show_error(self.root, "Save Error", str(e))
                    return False
            else:
                path = ask_save_file(
                    self.root,
                    filetypes=[("RetroSprite Projects", "*.retro")]
                )
                if not path:
                    return False
                if not path.endswith(".retro"):
                    path += ".retro"
                try:
                    save_project(path, self.timeline, self.palette,
                                 tool_settings=self._tool_settings.to_dict(),
                                 reference_image=self._reference,
                                 grid_settings=self._grid_settings.to_dict(),
                                 symmetry_axis_x=self._symmetry_axis_x,
                                 symmetry_axis_y=self._symmetry_axis_y)
                    self._project_path = path
                except Exception as e:
                    show_error(self.root, "Save Error", str(e))
                    return False
        # No or successful save — proceed
        return True

    def _on_close(self):
        """Handle window close (X button or Exit menu)."""
        if not self._check_save_before():
            return
        self._stop_animation()
        from src.plugins import unload_all_plugins
        unload_all_plugins(self._plugins, self.api)
        self.root.destroy()

    def _return_to_menu_action(self):
        """Return to the startup menu instead of quitting."""
        if not self._check_save_before():
            return
        self._stop_animation()
        self._return_to_menu = True
        self.root.destroy()

    def _reset_state(self):
        """Reset all transient state for a fresh project."""
        self._stop_animation()
        self._playback_mode = "forward"
        self._pingpong_direction = 1
        self._dirty = False
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._selection_pixels = None
        self._select_start = None
        self._clipboard = None
        self._custom_brush_mask = None
        self._pasting = False
        self._paste_pos = (0, 0)
        self._line_start = None
        self._rect_start = None
        self._roundrect_start = None
        self._ellipse_start = None
        self._hand_last = None
        self._onion_skin = False
        self._onion_range = 1
        self._pp_last_points = []
        self.current_tool_name = "Pen"
        self._tool_settings = ToolSettingsManager()
        self.toolbar.select_tool("Pen")
        self.options_bar.set_tool("pen")
        pen_settings = self._tool_settings.get("pen")
        self._apply_tool_settings(pen_settings)
        self._rotation_mode = False
        self._rotation_angle = 0.0
        self._rotation_pivot = None
        self._rotation_original = None
        self._rotation_bounds = None
        self._rotation_dragging = None
        self._rotation_context_frame = None
        self.pixel_canvas.clear_overlays()
        self.pixel_canvas.clear_selection()
        self.pixel_canvas.clear_floating()
        self.pixel_canvas.clear_rotation_handles()
