"""Rotation mode state machine for RetroSprite."""

import math
import tkinter as tk

import numpy as np

from src.pixel_data import PixelGrid
from src.rotsprite import fast_rotate, rotsprite_rotate
from src.ui.theme import (
    ACCENT_CYAN, BG_DEEP, BG_PANEL, BG_PANEL_ALT,
    BUTTON_BG, BUTTON_HOVER, TEXT_PRIMARY, TEXT_SECONDARY,
)


class RotationMixin:
    """Interactive rotation: enter/exit mode, drag corners to rotate,
    Shift-snap to 15 deg, context bar with angle entry and algorithm picker."""

    def _enter_rotation_mode(self):
        """Enter interactive rotation mode for the current layer."""
        if self._rotation_mode:
            return
        layer_grid = self.timeline.current_layer()
        pixels = layer_grid._pixels

        # Check if there's any content
        if pixels[:, :, 3].max() == 0:
            self._update_status("Nothing to rotate")
            return

        # Determine bounds from selection or non-transparent pixels
        if self._selection_pixels and len(self._selection_pixels) > 0:
            xs = [p[0] for p in self._selection_pixels]
            ys = [p[1] for p in self._selection_pixels]
            bx, by = min(xs), min(ys)
            bw = max(xs) - bx + 1
            bh = max(ys) - by + 1
        else:
            # Use full layer bounds (non-transparent)
            mask = pixels[:, :, 3] > 0
            rows = np.any(mask, axis=1)
            cols = np.any(mask, axis=0)
            if not rows.any():
                self._update_status("Nothing to rotate")
                return
            by = int(np.argmax(rows))
            bh = int(len(rows) - np.argmax(rows[::-1])) - by
            bx = int(np.argmax(cols))
            bw = int(len(cols) - np.argmax(cols[::-1])) - bx

        self._push_undo()
        self._rotation_mode = True
        self._rotation_angle = 0.0
        self._rotation_bounds = (bx, by, bw, bh)
        self._rotation_pivot = (bx + bw / 2.0, by + bh / 2.0)
        self._rotation_original = pixels.copy()
        self._rotation_algorithm = "rotsprite"
        self._rotation_dragging = None

        # Draw handles
        self.pixel_canvas.draw_rotation_handles(
            self._rotation_bounds, self._rotation_angle,
            self._rotation_pivot, self.pixel_canvas.pixel_size
        )

        # Show context bar
        self._show_rotation_context_bar()
        self._update_status("Rotation mode: drag corners to rotate, Enter=apply, Esc=cancel")

    def _exit_rotation_mode(self, apply=False):
        """Exit rotation mode, optionally applying the rotation."""
        if not self._rotation_mode:
            return

        if apply and self._rotation_angle % 360 != 0:
            # Apply final rotation with selected algorithm
            pixels = self._rotation_original
            pivot = (int(self._rotation_pivot[0]),
                     int(self._rotation_pivot[1]))
            if self._rotation_algorithm == "rotsprite":
                result = rotsprite_rotate(pixels, self._rotation_angle,
                                          pivot=pivot)
            else:
                result = fast_rotate(pixels, self._rotation_angle,
                                     pivot=pivot)
            frame_obj = self.timeline.current_frame_obj()
            frame_obj.active_layer.pixels = PixelGrid(
                result.shape[1], result.shape[0])
            frame_obj.active_layer.pixels._pixels = result
        elif not apply:
            # Cancel: restore original pixels
            if self._rotation_original is not None:
                frame_obj = self.timeline.current_frame_obj()
                h, w = self._rotation_original.shape[:2]
                frame_obj.active_layer.pixels = PixelGrid(w, h)
                frame_obj.active_layer.pixels._pixels = self._rotation_original

        self._rotation_mode = False
        self._rotation_original = None
        self._rotation_bounds = None
        self._rotation_pivot = None
        self._rotation_dragging = None

        self.pixel_canvas.clear_rotation_handles()
        self._hide_rotation_context_bar()
        self._refresh_canvas()

        if apply and self._rotation_angle % 360 != 0:
            self._update_status(
                f"Rotation applied: {self._rotation_angle:.1f} deg "
                f"({self._rotation_algorithm})")
        else:
            self._update_status("Rotation cancelled")
        self._rotation_angle = 0.0

    def _rotation_handle_click(self, x, y, event_state=0):
        """Handle mouse click during rotation mode."""
        ps = self.pixel_canvas.pixel_size
        # Use screen coords for hit testing
        sx = x * ps + ps // 2
        sy = y * ps + ps // 2

        hit = self.pixel_canvas.hit_test_rotation_handle(
            sx, sy, self._rotation_bounds, self._rotation_angle,
            self._rotation_pivot, ps
        )

        if hit == "pivot":
            self._rotation_dragging = "pivot"
        elif hit and hit.startswith("corner:"):
            self._rotation_dragging = "corner"
            # Record starting angle from mouse to pivot
            pvx = self._rotation_pivot[0]
            pvy = self._rotation_pivot[1]
            self._rotation_mouse_start_angle = math.degrees(
                math.atan2(y - pvy, x - pvx))
            self._rotation_drag_start_angle = self._rotation_angle
        else:
            self._rotation_dragging = None

    def _rotation_handle_drag(self, x, y):
        """Handle mouse drag during rotation mode."""
        if self._rotation_dragging == "corner":
            pvx = self._rotation_pivot[0]
            pvy = self._rotation_pivot[1]
            current_mouse_angle = math.degrees(
                math.atan2(y - pvy, x - pvx))
            delta = current_mouse_angle - self._rotation_mouse_start_angle
            new_angle = self._rotation_drag_start_angle + delta

            # Normalize to -180..180
            new_angle = ((new_angle + 180) % 360) - 180

            self._rotation_angle = new_angle

            # Live preview using fast_rotate
            pixels = self._rotation_original
            pivot = (int(self._rotation_pivot[0]),
                     int(self._rotation_pivot[1]))
            preview = fast_rotate(pixels, self._rotation_angle, pivot=pivot)
            frame_obj = self.timeline.current_frame_obj()
            frame_obj.active_layer.pixels._pixels = preview

            self._render_canvas()
            self.pixel_canvas.draw_rotation_handles(
                self._rotation_bounds, self._rotation_angle,
                self._rotation_pivot, self.pixel_canvas.pixel_size
            )
            self._update_rotation_angle_display()

        elif self._rotation_dragging == "pivot":
            self._rotation_pivot = (float(x), float(y))
            # Re-apply preview with new pivot
            if self._rotation_angle % 360 != 0:
                pixels = self._rotation_original
                pivot = (int(self._rotation_pivot[0]),
                         int(self._rotation_pivot[1]))
                preview = fast_rotate(pixels, self._rotation_angle,
                                      pivot=pivot)
                frame_obj = self.timeline.current_frame_obj()
                frame_obj.active_layer.pixels._pixels = preview
                self._render_canvas()
            self.pixel_canvas.draw_rotation_handles(
                self._rotation_bounds, self._rotation_angle,
                self._rotation_pivot, self.pixel_canvas.pixel_size
            )

    def _rotation_handle_release(self, x, y, event_state=0):
        """Handle mouse release during rotation mode."""
        shift_held = bool(event_state & 0x0001)

        if self._rotation_dragging == "corner" and shift_held:
            # Snap to 15 degree increments
            self._rotation_angle = round(self._rotation_angle / 15) * 15
            # Re-apply with snapped angle
            pixels = self._rotation_original
            pivot = (int(self._rotation_pivot[0]),
                     int(self._rotation_pivot[1]))
            preview = fast_rotate(pixels, self._rotation_angle, pivot=pivot)
            frame_obj = self.timeline.current_frame_obj()
            frame_obj.active_layer.pixels._pixels = preview
            self._render_canvas()
            self.pixel_canvas.draw_rotation_handles(
                self._rotation_bounds, self._rotation_angle,
                self._rotation_pivot, self.pixel_canvas.pixel_size
            )
            self._update_rotation_angle_display()

        # If algorithm is rotsprite and we just finished a corner drag,
        # re-render with full quality
        if (self._rotation_dragging == "corner" and
                self._rotation_algorithm == "rotsprite" and
                self._rotation_angle % 360 != 0):
            pixels = self._rotation_original
            pivot = (int(self._rotation_pivot[0]),
                     int(self._rotation_pivot[1]))
            result = rotsprite_rotate(pixels, self._rotation_angle,
                                      pivot=pivot)
            frame_obj = self.timeline.current_frame_obj()
            frame_obj.active_layer.pixels._pixels = result
            self._render_canvas()
            self.pixel_canvas.draw_rotation_handles(
                self._rotation_bounds, self._rotation_angle,
                self._rotation_pivot, self.pixel_canvas.pixel_size
            )

        self._rotation_dragging = None

    def _show_rotation_context_bar(self):
        """Show a context bar for rotation mode in the options area."""
        self._hide_rotation_context_bar()

        frame = tk.Frame(self.options_bar, bg=BG_PANEL)
        frame.pack(side="right", padx=4)
        self._rotation_context_frame = frame

        # Angle label + entry
        tk.Label(frame, text="Angle:", fg=TEXT_SECONDARY, bg=BG_PANEL,
                 font=("Consolas", 8)).pack(side="left", padx=(4, 2))
        self._rotation_angle_var = tk.StringVar(value="0.0")
        angle_entry = tk.Entry(frame, textvariable=self._rotation_angle_var,
                               width=6, bg=BG_PANEL_ALT, fg=TEXT_PRIMARY,
                               font=("Consolas", 8), insertbackground=TEXT_PRIMARY)
        angle_entry.pack(side="left", padx=2)
        angle_entry.bind("<Return>", self._on_rotation_angle_entry)
        tk.Label(frame, text="\u00b0", fg=TEXT_SECONDARY, bg=BG_PANEL,
                 font=("Consolas", 8)).pack(side="left")

        # Algorithm dropdown
        tk.Label(frame, text="Algo:", fg=TEXT_SECONDARY, bg=BG_PANEL,
                 font=("Consolas", 8)).pack(side="left", padx=(8, 2))
        self._rotation_algo_var = tk.StringVar(value="RotSprite")
        algo_menu = tk.OptionMenu(
            frame, self._rotation_algo_var,
            "RotSprite", "Fast",
            command=self._on_rotation_algo_change
        )
        algo_menu.config(bg=BUTTON_BG, fg=TEXT_PRIMARY, font=("Consolas", 8),
                         highlightthickness=0, relief="flat",
                         activebackground=BUTTON_HOVER)
        algo_menu.pack(side="left", padx=2)

        # Apply button
        tk.Button(frame, text="Apply", bg=ACCENT_CYAN, fg=BG_DEEP,
                  font=("Consolas", 8, "bold"), relief="flat",
                  activebackground=BUTTON_HOVER,
                  command=lambda: self._exit_rotation_mode(apply=True)
                  ).pack(side="left", padx=(8, 2))

        # Cancel button
        tk.Button(frame, text="Cancel", bg=BUTTON_BG, fg=TEXT_PRIMARY,
                  font=("Consolas", 8), relief="flat",
                  activebackground=BUTTON_HOVER,
                  command=lambda: self._exit_rotation_mode(apply=False)
                  ).pack(side="left", padx=2)

    def _hide_rotation_context_bar(self):
        """Remove the rotation context bar."""
        if self._rotation_context_frame is not None:
            self._rotation_context_frame.destroy()
            self._rotation_context_frame = None

    def _update_rotation_angle_display(self):
        """Update the angle display in the context bar."""
        if hasattr(self, '_rotation_angle_var'):
            self._rotation_angle_var.set(f"{self._rotation_angle:.1f}")

    def _on_rotation_angle_entry(self, event=None):
        """Handle manual angle entry."""
        try:
            angle = float(self._rotation_angle_var.get())
            self._rotation_angle = angle
            # Apply preview
            pixels = self._rotation_original
            pivot = (int(self._rotation_pivot[0]),
                     int(self._rotation_pivot[1]))
            preview = fast_rotate(pixels, self._rotation_angle, pivot=pivot)
            frame_obj = self.timeline.current_frame_obj()
            frame_obj.active_layer.pixels._pixels = preview
            self._render_canvas()
            self.pixel_canvas.draw_rotation_handles(
                self._rotation_bounds, self._rotation_angle,
                self._rotation_pivot, self.pixel_canvas.pixel_size
            )
        except ValueError:
            pass

    def _on_rotation_algo_change(self, value):
        """Handle algorithm selection change."""
        self._rotation_algorithm = value.lower()
