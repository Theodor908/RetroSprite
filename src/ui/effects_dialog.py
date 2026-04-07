"""Non-destructive layer effects dialog for RetroSprite."""
from __future__ import annotations
import copy
import tkinter as tk
from tkinter import colorchooser
from src.effects import LayerEffect
from src.ui.theme import (
    BG_DEEP, BG_PANEL, BG_PANEL_ALT, BORDER, TEXT_PRIMARY, TEXT_SECONDARY,
    ACCENT_CYAN, ACCENT_MAGENTA, ACCENT_PURPLE,
    BUTTON_BG, BUTTON_HOVER,
)


EFFECT_TYPES = [
    ("Outline", "outline", {
        "color": (0, 0, 0, 255), "thickness": 1, "mode": "outer", "connectivity": 4
    }),
    ("Drop Shadow", "drop_shadow", {
        "color": (0, 0, 0, 200), "offset_x": 2, "offset_y": 2, "blur": 0, "opacity": 0.7
    }),
    ("Inner Shadow", "inner_shadow", {
        "color": (0, 0, 0, 200), "offset_x": 1, "offset_y": 1, "blur": 0, "opacity": 0.5
    }),
    ("Hue/Sat/Value", "hue_sat", {
        "hue": 0, "saturation": 1.0, "value": 0
    }),
    ("Gradient Map", "gradient_map", {
        "stops": [(0.0, (0, 0, 0, 255)), (1.0, (255, 255, 255, 255))], "opacity": 1.0
    }),
    ("Glow/Bloom", "glow", {
        "threshold": 200, "radius": 2, "intensity": 1.0, "tint": (255, 255, 255, 255)
    }),
    ("Pattern Overlay", "pattern_overlay", {
        "pattern": "checkerboard", "blend_mode": "multiply", "opacity": 0.5,
        "scale": 1, "offset_x": 0, "offset_y": 0
    }),
]

_TYPE_TO_LABEL = {et[1]: et[0] for et in EFFECT_TYPES}


def get_all_effect_types(api=None):
    """Return built-in effect types plus any plugin-registered effects."""
    all_types = list(EFFECT_TYPES)
    if api:
        for name, info in api._plugin_effects.items():
            all_types.append((name, f"plugin_{name}", info.get("default_params", {})))
    return all_types


def _rgba_to_hex(rgba) -> str:
    r, g, b = int(rgba[0]), int(rgba[1]), int(rgba[2])
    return f"#{r:02x}{g:02x}{b:02x}"


def _hex_to_rgba(hex_color: str, alpha: int = 255) -> tuple:
    h = hex_color.lstrip("#")
    r = int(h[0:2], 16)
    g = int(h[2:4], 16)
    b = int(h[4:6], 16)
    return (r, g, b, alpha)


class EffectsDialog(tk.Toplevel):
    """Modal dialog for configuring non-destructive layer effects."""

    def __init__(self, parent, layer, render_callback, api=None):
        super().__init__(parent)
        self.title("Layer Effects")
        self.resizable(True, True)
        self.geometry("640x480")
        self.configure(bg=BG_DEEP)
        self.transient(parent)
        self.grab_set()

        self.layer = layer
        self.render_callback = render_callback
        self._api = api
        self._all_effect_types = get_all_effect_types(api)

        # Preserve original for cancel
        self._original_effects: list[LayerEffect] = copy.deepcopy(layer.effects)
        # Working copy — applied to layer immediately for live preview
        self.working_effects: list[LayerEffect] = copy.deepcopy(layer.effects)
        self.layer.effects = self.working_effects

        self._selected_idx: int | None = None
        self._param_widgets: list = []

        self._build_ui()
        self._refresh_list()

        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

    # ------------------------------------------------------------------ #
    # UI Construction
    # ------------------------------------------------------------------ #

    def _build_ui(self):
        btn_cfg = dict(font=("Consolas", 9), relief="flat",
                       bg=BUTTON_BG, fg=TEXT_PRIMARY,
                       activebackground=BUTTON_HOVER, activeforeground=ACCENT_CYAN)

        # Top area: effect list (left) + param editor (right)
        top = tk.Frame(self, bg=BG_DEEP)
        top.pack(fill="both", expand=True, padx=6, pady=6)

        # ---------- Left: effect list ----------
        left = tk.Frame(top, bg=BG_PANEL, width=200)
        left.pack(side="left", fill="y", padx=(0, 4))
        left.pack_propagate(False)

        tk.Label(left, text="Effects", font=("Consolas", 9, "bold"),
                 bg=BG_PANEL, fg=ACCENT_CYAN).pack(pady=(6, 2))

        self._listbox = tk.Listbox(
            left, selectmode="single",
            bg=BG_PANEL_ALT, fg=TEXT_PRIMARY,
            selectbackground=ACCENT_CYAN, selectforeground=BG_DEEP,
            font=("Consolas", 9), highlightthickness=1,
            highlightbackground=BORDER, highlightcolor=ACCENT_CYAN,
            activestyle="none", relief="flat",
        )
        self._listbox.pack(fill="both", expand=True, padx=4, pady=2)
        self._listbox.bind("<<ListboxSelect>>", self._on_list_select)

        # Management buttons
        mgmt = tk.Frame(left, bg=BG_PANEL)
        mgmt.pack(fill="x", padx=4, pady=4)

        self._add_menu_btn = tk.Menubutton(
            mgmt, text="Add \u25be", font=("Consolas", 8),
            bg=BUTTON_BG, fg=ACCENT_CYAN, relief="flat",
            activebackground=BUTTON_HOVER, activeforeground=ACCENT_CYAN,
        )
        add_menu = tk.Menu(self._add_menu_btn, tearoff=0,
                           bg=BG_PANEL, fg=TEXT_PRIMARY,
                           activebackground=ACCENT_CYAN, activeforeground=BG_DEEP,
                           font=("Consolas", 9))
        for label, etype, defaults in self._all_effect_types:
            add_menu.add_command(
                label=label,
                command=lambda et=etype, ed=defaults: self._add_effect(et, ed)
            )
        self._add_menu_btn.config(menu=add_menu)
        self._add_menu_btn.pack(side="left", padx=2)

        tk.Button(mgmt, text="Del", command=self._remove_effect,
                  **btn_cfg).pack(side="left", padx=2)
        tk.Button(mgmt, text="\u2191", width=2, command=self._move_up,
                  **btn_cfg).pack(side="left", padx=1)
        tk.Button(mgmt, text="\u2193", width=2, command=self._move_down,
                  **btn_cfg).pack(side="left", padx=1)

        # ---------- Right: parameter editor ----------
        right_outer = tk.Frame(top, bg=BG_PANEL)
        right_outer.pack(side="left", fill="both", expand=True)

        tk.Label(right_outer, text="Parameters", font=("Consolas", 9, "bold"),
                 bg=BG_PANEL, fg=ACCENT_CYAN).pack(pady=(6, 2))

        self._params_frame = tk.Frame(right_outer, bg=BG_PANEL)
        self._params_frame.pack(fill="both", expand=True, padx=6, pady=4)

        # ---------- Bottom: Apply / Cancel ----------
        bottom = tk.Frame(self, bg=BG_DEEP)
        bottom.pack(fill="x", padx=6, pady=(0, 6))

        tk.Button(bottom, text="Apply", command=self._on_apply,
                  font=("Consolas", 9), bg=ACCENT_CYAN, fg=BG_DEEP,
                  relief="flat", activebackground=ACCENT_PURPLE,
                  activeforeground=TEXT_PRIMARY).pack(side="right", padx=4)
        tk.Button(bottom, text="Cancel", command=self._on_cancel,
                  **btn_cfg).pack(side="right", padx=4)

    # ------------------------------------------------------------------ #
    # List management
    # ------------------------------------------------------------------ #

    def _refresh_list(self):
        self._listbox.delete(0, "end")
        type_labels = {et[1]: et[0] for et in self._all_effect_types}
        for fx in self.working_effects:
            label = type_labels.get(fx.type, fx.type)
            prefix = "\u2713 " if fx.enabled else "\u25cb "
            self._listbox.insert("end", prefix + label)
        if self._selected_idx is not None:
            idx = min(self._selected_idx, len(self.working_effects) - 1)
            if idx >= 0:
                self._listbox.selection_set(idx)
                self._listbox.activate(idx)

    def _on_list_select(self, event=None):
        sel = self._listbox.curselection()
        if not sel:
            return
        self._selected_idx = sel[0]
        self._build_params()

    def _add_effect(self, etype: str, defaults: dict):
        fx = LayerEffect(type=etype, enabled=True, params=copy.deepcopy(defaults))
        self.working_effects.append(fx)
        self._selected_idx = len(self.working_effects) - 1
        self._refresh_list()
        self._build_params()
        self._live_preview()

    def _remove_effect(self):
        if self._selected_idx is None or not self.working_effects:
            return
        idx = self._selected_idx
        if 0 <= idx < len(self.working_effects):
            self.working_effects.pop(idx)
            if self.working_effects:
                self._selected_idx = min(idx, len(self.working_effects) - 1)
            else:
                self._selected_idx = None
            self._refresh_list()
            self._clear_params()
            if self._selected_idx is not None and self._selected_idx >= 0:
                self._build_params()
            self._live_preview()

    def _move_up(self):
        idx = self._selected_idx
        if idx is None or idx <= 0:
            return
        self.working_effects[idx - 1], self.working_effects[idx] = \
            self.working_effects[idx], self.working_effects[idx - 1]
        self._selected_idx = idx - 1
        self._refresh_list()
        self._live_preview()

    def _move_down(self):
        idx = self._selected_idx
        if idx is None or idx >= len(self.working_effects) - 1:
            return
        self.working_effects[idx], self.working_effects[idx + 1] = \
            self.working_effects[idx + 1], self.working_effects[idx]
        self._selected_idx = idx + 1
        self._refresh_list()
        self._live_preview()

    # ------------------------------------------------------------------ #
    # Parameter widget building
    # ------------------------------------------------------------------ #

    def _clear_params(self):
        for w in self._params_frame.winfo_children():
            w.destroy()
        self._param_widgets.clear()

    def _build_params(self):
        self._clear_params()
        if self._selected_idx is None or self._selected_idx >= len(self.working_effects):
            return

        fx = self.working_effects[self._selected_idx]
        p = fx.params
        row = 0

        # Enabled checkbox
        enabled_var = tk.BooleanVar(value=fx.enabled)

        def _toggle_enabled(var=enabled_var, effect=fx):
            effect.enabled = var.get()
            self._refresh_list()
            self._live_preview()

        ck = tk.Checkbutton(self._params_frame, text="Enabled",
                            variable=enabled_var, command=_toggle_enabled,
                            bg=BG_PANEL, fg=TEXT_PRIMARY,
                            selectcolor=BG_PANEL_ALT,
                            activebackground=BG_PANEL, activeforeground=ACCENT_CYAN,
                            font=("Consolas", 9))
        ck.grid(row=row, column=0, columnspan=4, sticky="w", pady=(0, 6))
        row += 1

        if fx.type == "outline":
            self._build_color_row(p, "color", row); row += 1
            self._build_int_row(p, "thickness", "Thickness", 1, 10, row); row += 1
            self._build_option_row(p, "mode", "Mode", ["outer", "inner", "both"], row); row += 1
            self._build_option_row(p, "connectivity", "Connectivity",
                                   [4, 8], row, label_map={4: "4-conn", 8: "8-conn"}); row += 1

        elif fx.type == "drop_shadow":
            self._build_color_row(p, "color", row); row += 1
            self._build_int_row(p, "offset_x", "Offset X", -20, 20, row); row += 1
            self._build_int_row(p, "offset_y", "Offset Y", -20, 20, row); row += 1
            self._build_int_row(p, "blur", "Blur", 0, 20, row); row += 1
            self._build_float_row(p, "opacity", "Opacity", 0.0, 1.0, row); row += 1

        elif fx.type == "inner_shadow":
            self._build_color_row(p, "color", row); row += 1
            self._build_int_row(p, "offset_x", "Offset X", -20, 20, row); row += 1
            self._build_int_row(p, "offset_y", "Offset Y", -20, 20, row); row += 1
            self._build_int_row(p, "blur", "Blur", 0, 20, row); row += 1
            self._build_float_row(p, "opacity", "Opacity", 0.0, 1.0, row); row += 1

        elif fx.type == "hue_sat":
            self._build_int_row(p, "hue", "Hue Shift", -180, 180, row); row += 1
            self._build_float_row(p, "saturation", "Saturation", 0.0, 4.0, row); row += 1
            self._build_int_row(p, "value", "Value Shift", -255, 255, row); row += 1

        elif fx.type == "gradient_map":
            self._build_gradient_stops_row(p, row); row += 2

        elif fx.type == "glow":
            self._build_int_row(p, "threshold", "Threshold", 0, 255, row); row += 1
            self._build_int_row(p, "radius", "Radius", 0, 20, row); row += 1
            self._build_float_row(p, "intensity", "Intensity", 0.0, 5.0, row); row += 1
            self._build_color_row(p, "tint", row); row += 1

        elif fx.type == "pattern_overlay":
            patterns = ["checkerboard", "scanlines", "dots", "crosshatch", "diagonal", "noise"]
            blend_modes = ["normal", "multiply", "screen", "overlay"]
            self._build_option_row(p, "pattern", "Pattern", patterns, row); row += 1
            self._build_option_row(p, "blend_mode", "Blend", blend_modes, row); row += 1
            self._build_float_row(p, "opacity", "Opacity", 0.0, 1.0, row); row += 1
            self._build_int_row(p, "scale", "Scale", 1, 8, row); row += 1
            self._build_int_row(p, "offset_x", "Offset X", 0, 32, row); row += 1
            self._build_int_row(p, "offset_y", "Offset Y", 0, 32, row); row += 1

        elif fx.type.startswith("plugin_"):
            # Auto-generate UI for plugin effect params
            for key, val in p.items():
                label = key.replace("_", " ").title()
                if isinstance(val, int):
                    self._build_int_row(p, key, label, 0, max(val * 4, 100), row); row += 1
                elif isinstance(val, float):
                    self._build_float_row(p, key, label, 0.0, max(val * 4, 1.0), row); row += 1
                elif isinstance(val, str):
                    self._build_string_row(p, key, label, row); row += 1

    def _lbl(self, text: str, row: int):
        tk.Label(self._params_frame, text=text, font=("Consolas", 8),
                 bg=BG_PANEL, fg=TEXT_SECONDARY, anchor="w"
                 ).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=2)

    def _build_color_row(self, params: dict, key: str, row: int):
        label = "Color" if key == "color" else "Tint"
        self._lbl(label, row)

        color_val = params.get(key, (0, 0, 0, 255))
        alpha_val = int(color_val[3]) if len(color_val) > 3 else 255
        hex_color = _rgba_to_hex(color_val)

        swatch = tk.Label(self._params_frame, bg=hex_color, width=6,
                          relief="sunken", cursor="hand2")
        swatch.grid(row=row, column=1, sticky="w", pady=2)

        alpha_var = tk.IntVar(value=alpha_val)

        def _pick_color(s=swatch, p=params, k=key, av=alpha_var):
            current_hex = s.cget("bg")
            result = colorchooser.askcolor(color=current_hex, parent=self,
                                           title=f"Choose {label}")
            if result and result[1]:
                picked_hex = result[1]
                s.config(bg=picked_hex)
                new_rgba = _hex_to_rgba(picked_hex, av.get())
                p[k] = new_rgba
                self._live_preview()

        swatch.bind("<Button-1>", lambda e: _pick_color())

        tk.Label(self._params_frame, text="A:", font=("Consolas", 8),
                 bg=BG_PANEL, fg=TEXT_SECONDARY).grid(row=row, column=2, padx=(4, 0))

        def _alpha_changed(*_, s=swatch, p=params, k=key, av=alpha_var):
            try:
                a = max(0, min(255, av.get()))
            except Exception:
                return
            current_hex = s.cget("bg")
            p[k] = _hex_to_rgba(current_hex, a)
            self._live_preview()

        alpha_spin = tk.Spinbox(self._params_frame, from_=0, to=255, width=4,
                                textvariable=alpha_var,
                                font=("Consolas", 8), bg=BG_PANEL_ALT,
                                fg=TEXT_PRIMARY, buttonbackground=BUTTON_BG,
                                command=_alpha_changed)
        alpha_spin.grid(row=row, column=3, sticky="w", pady=2)
        alpha_var.trace_add("write", _alpha_changed)

    def _build_int_row(self, params: dict, key: str, label: str,
                       min_val: int, max_val: int, row: int):
        self._lbl(label, row)
        var = tk.IntVar(value=int(params.get(key, min_val)))

        def _changed(*_, p=params, k=key, v=var):
            try:
                p[k] = max(min_val, min(max_val, v.get()))
            except Exception:
                return
            self._live_preview()

        tk.Scale(self._params_frame, from_=min_val, to=max_val,
                 orient="horizontal", variable=var, command=lambda _: _changed(),
                 length=180, bg=BG_PANEL, fg=TEXT_PRIMARY,
                 troughcolor=BG_PANEL_ALT, highlightthickness=0,
                 activebackground=ACCENT_CYAN, font=("Consolas", 7),
                 showvalue=True).grid(row=row, column=1, columnspan=3, sticky="ew", pady=2)

    def _build_float_row(self, params: dict, key: str, label: str,
                         min_val: float, max_val: float, row: int):
        self._lbl(label, row)
        steps = 1000
        raw_val = float(params.get(key, min_val))
        span = max_val - min_val
        init_int = int((raw_val - min_val) / span * steps) if span > 0 else 0
        var = tk.IntVar(value=max(0, min(steps, init_int)))

        val_lbl = tk.Label(self._params_frame, text=f"{raw_val:.2f}",
                           font=("Consolas", 8), bg=BG_PANEL, fg=ACCENT_CYAN, width=5)
        val_lbl.grid(row=row, column=3, sticky="w", pady=2)

        def _changed(_, p=params, k=key, v=var, lbl=val_lbl):
            try:
                frac = v.get() / steps
                float_val = round(min_val + frac * span, 3)
                float_val = max(min_val, min(max_val, float_val))
                p[k] = float_val
                lbl.config(text=f"{float_val:.2f}")
            except Exception:
                return
            self._live_preview()

        tk.Scale(self._params_frame, from_=0, to=steps,
                 orient="horizontal", variable=var, command=_changed,
                 length=180, bg=BG_PANEL, fg=TEXT_PRIMARY,
                 troughcolor=BG_PANEL_ALT, highlightthickness=0,
                 activebackground=ACCENT_CYAN, font=("Consolas", 7),
                 showvalue=False).grid(row=row, column=1, columnspan=2, sticky="ew", pady=2)

    def _build_option_row(self, params: dict, key: str, label: str,
                          options: list, row: int, label_map: dict | None = None):
        self._lbl(label, row)
        current = params.get(key, options[0])

        if label_map:
            display_options = [label_map.get(o, str(o)) for o in options]
            rev_map = {v: k for k, v in label_map.items()}
            display_val = label_map.get(current, str(current))
        else:
            display_options = [str(o) for o in options]
            rev_map = None
            display_val = str(current)

        var = tk.StringVar(value=display_val)

        def _changed(*_, p=params, k=key, v=var, rm=rev_map, opts=options):
            raw = v.get()
            if rm:
                value = rm.get(raw, raw)
            else:
                value = raw
                for o in opts:
                    if str(o) == raw:
                        value = o
                        break
            p[k] = value
            self._live_preview()

        menu = tk.OptionMenu(self._params_frame, var, *display_options,
                             command=lambda _: _changed())
        menu.config(width=12, font=("Consolas", 8), bg=BG_PANEL,
                    fg=TEXT_PRIMARY, highlightthickness=0,
                    activebackground=BUTTON_HOVER, activeforeground=ACCENT_CYAN)
        menu.grid(row=row, column=1, columnspan=3, sticky="w", pady=2)
        var.trace_add("write", _changed)

    def _build_string_row(self, params: dict, key: str, label: str, row: int):
        self._lbl(label, row)
        var = tk.StringVar(value=str(params.get(key, "")))

        def _changed(*_, p=params, k=key, v=var):
            p[k] = v.get()
            self._live_preview()

        entry = tk.Entry(self._params_frame, textvariable=var, width=20,
                         font=("Consolas", 8), bg=BG_PANEL_ALT, fg=TEXT_PRIMARY,
                         insertbackground=ACCENT_CYAN)
        entry.grid(row=row, column=1, columnspan=3, sticky="w", pady=2)
        var.trace_add("write", _changed)

    def _build_gradient_stops_row(self, params: dict, row: int):
        """Two color pickers for gradient start/end stops + opacity."""
        self._lbl("Gradient", row)

        stops = list(params.get(
            "stops", [(0.0, (0, 0, 0, 255)), (1.0, (255, 255, 255, 255))]
        ))
        while len(stops) < 2:
            stops.append((1.0, (255, 255, 255, 255)))
        params["stops"] = stops

        container = tk.Frame(self._params_frame, bg=BG_PANEL)
        container.grid(row=row, column=1, columnspan=3, sticky="w", pady=2)

        def _make_stop_btn(idx: int):
            color = stops[idx][1]
            hex_c = _rgba_to_hex(color)
            lbl_text = "Start" if idx == 0 else "End"
            tk.Label(container, text=lbl_text, font=("Consolas", 7),
                     bg=BG_PANEL, fg=TEXT_SECONDARY).pack(side="left", padx=(0, 2))
            swatch = tk.Label(container, bg=hex_c, width=5, relief="sunken",
                              cursor="hand2")
            swatch.pack(side="left", padx=(0, 8))

            def _pick(s=swatch, i=idx):
                result = colorchooser.askcolor(color=s.cget("bg"), parent=self,
                                               title=f"Stop {i} color")
                if result and result[1]:
                    s.config(bg=result[1])
                    alpha = stops[i][1][3] if len(stops[i][1]) > 3 else 255
                    new_color = _hex_to_rgba(result[1], alpha)
                    stops[i] = (stops[i][0], new_color)
                    self._live_preview()

            swatch.bind("<Button-1>", lambda e: _pick())

        _make_stop_btn(0)
        _make_stop_btn(1)

        # Opacity on next row
        self._build_float_row(params, "opacity", "Opacity", 0.0, 1.0, row + 1)

    # ------------------------------------------------------------------ #
    # Live preview & apply/cancel
    # ------------------------------------------------------------------ #

    def _live_preview(self):
        """Apply working effects to the layer and trigger a redraw."""
        self.layer.effects = self.working_effects
        self.render_callback()

    def _on_apply(self):
        self.layer.effects = self.working_effects
        self.render_callback()
        self.destroy()

    def _on_cancel(self):
        self.layer.effects = self._original_effects
        self.render_callback()
        self.destroy()
