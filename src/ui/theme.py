"""Neon Retro theme for RetroSprite with dark/light mode support."""

# Current mode: "dark" or "light"
_current_mode = "dark"

# --- Dark mode palette ---
_DARK = {
    "BG_DEEP": "#0d0d12",
    "BG_PANEL": "#14141f",
    "BG_PANEL_ALT": "#1a1a2e",
    "BORDER": "#1e1e3a",
    "TEXT_PRIMARY": "#e0e0e8",
    "TEXT_SECONDARY": "#7a7a9a",
    "ACCENT_CYAN": "#00f0ff",
    "ACCENT_MAGENTA": "#ff00aa",
    "ACCENT_PURPLE": "#8b5cf6",
    "SUCCESS": "#00ff88",
    "WARNING": "#ffaa00",
    "BUTTON_BG": "#1a1a2e",
    "BUTTON_HOVER": "#252545",
    "BUTTON_ACTIVE": "#0d0d12",
}

# --- Light mode palette ---
_LIGHT = {
    "BG_DEEP": "#f0f0f5",
    "BG_PANEL": "#e4e4ee",
    "BG_PANEL_ALT": "#d8d8e6",
    "BORDER": "#c0c0d0",
    "TEXT_PRIMARY": "#1a1a2e",
    "TEXT_SECONDARY": "#5a5a7a",
    "ACCENT_CYAN": "#0090aa",
    "ACCENT_MAGENTA": "#cc0088",
    "ACCENT_PURPLE": "#6b3fd6",
    "SUCCESS": "#00aa55",
    "WARNING": "#cc8800",
    "BUTTON_BG": "#d8d8e6",
    "BUTTON_HOVER": "#c8c8dd",
    "BUTTON_ACTIVE": "#f0f0f5",
}

# Color palette (mutable module-level vars, updated by set_mode)
BG_DEEP = _DARK["BG_DEEP"]
BG_PANEL = _DARK["BG_PANEL"]
BG_PANEL_ALT = _DARK["BG_PANEL_ALT"]
BORDER = _DARK["BORDER"]
TEXT_PRIMARY = _DARK["TEXT_PRIMARY"]
TEXT_SECONDARY = _DARK["TEXT_SECONDARY"]
ACCENT_CYAN = _DARK["ACCENT_CYAN"]
ACCENT_MAGENTA = _DARK["ACCENT_MAGENTA"]
ACCENT_PURPLE = _DARK["ACCENT_PURPLE"]
SUCCESS = _DARK["SUCCESS"]
WARNING = _DARK["WARNING"]
BUTTON_BG = _DARK["BUTTON_BG"]
BUTTON_HOVER = _DARK["BUTTON_HOVER"]
BUTTON_ACTIVE = _DARK["BUTTON_ACTIVE"]


def get_mode() -> str:
    return _current_mode


def set_mode(mode: str):
    """Switch between 'dark' and 'light' mode. Updates all module-level color vars."""
    global _current_mode
    global BG_DEEP, BG_PANEL, BG_PANEL_ALT, BORDER
    global TEXT_PRIMARY, TEXT_SECONDARY
    global ACCENT_CYAN, ACCENT_MAGENTA, ACCENT_PURPLE, SUCCESS, WARNING
    global BUTTON_BG, BUTTON_HOVER, BUTTON_ACTIVE
    _current_mode = mode
    palette = _DARK if mode == "dark" else _LIGHT
    BG_DEEP = palette["BG_DEEP"]
    BG_PANEL = palette["BG_PANEL"]
    BG_PANEL_ALT = palette["BG_PANEL_ALT"]
    BORDER = palette["BORDER"]
    TEXT_PRIMARY = palette["TEXT_PRIMARY"]
    TEXT_SECONDARY = palette["TEXT_SECONDARY"]
    ACCENT_CYAN = palette["ACCENT_CYAN"]
    ACCENT_MAGENTA = palette["ACCENT_MAGENTA"]
    ACCENT_PURPLE = palette["ACCENT_PURPLE"]
    SUCCESS = palette["SUCCESS"]
    WARNING = palette["WARNING"]
    BUTTON_BG = palette["BUTTON_BG"]
    BUTTON_HOVER = palette["BUTTON_HOVER"]
    BUTTON_ACTIVE = palette["BUTTON_ACTIVE"]

# Neon glow variants (softer/transparent versions for glow effects)
NEON_GLOW_CYAN = "#00f0ff"      # Same as ACCENT_CYAN, used at reduced opacity in PIL
NEON_GLOW_MAGENTA = "#ff00aa"   # Same as ACCENT_MAGENTA
NEON_GLOW_PURPLE = "#8b5cf6"    # Same as ACCENT_PURPLE

# Scanline effect colors
SCANLINE_DARK = "#0a0a10"
SCANLINE_LIGHT = "#12121c"

# Onion skin tints
ONION_PAST_TINT = "#ff006640"    # Magenta with alpha (as hex for reference)
ONION_FUTURE_TINT = "#00f0ff40"  # Cyan with alpha


def hex_to_rgb(hex_color: str) -> tuple:
    """Convert '#RRGGBB' to (R, G, B) tuple."""
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def rgb_to_hex(r: int, g: int, b: int) -> str:
    """Convert (R, G, B) to '#rrggbb' string."""
    return f"#{r:02x}{g:02x}{b:02x}"


def blend_color(color1: str, color2: str, t: float) -> str:
    """Blend two hex colors. t=0 returns color1, t=1 returns color2."""
    r1, g1, b1 = hex_to_rgb(color1)
    r2, g2, b2 = hex_to_rgb(color2)
    r = int(r1 + (r2 - r1) * t)
    g = int(g1 + (g2 - g1) * t)
    b = int(b1 + (b2 - b1) * t)
    return rgb_to_hex(r, g, b)


def dim_color(color: str, factor: float) -> str:
    """Dim a hex color by a factor (0.0=black, 1.0=unchanged)."""
    r, g, b = hex_to_rgb(color)
    return rgb_to_hex(int(r * factor), int(g * factor), int(b * factor))


def setup_ttk_theme(root):
    """Configure ttk styles for dark neon scrollbars and widgets."""
    from tkinter import ttk
    style = ttk.Style(root)
    style.theme_use("clam")  # clam supports color customization

    # Scrollbar styling
    style.configure("Neon.Vertical.TScrollbar",
                    background=BUTTON_BG,
                    troughcolor=BG_DEEP,
                    bordercolor=BG_DEEP,
                    arrowcolor=ACCENT_CYAN,
                    relief="flat",
                    borderwidth=0)
    style.map("Neon.Vertical.TScrollbar",
              background=[("active", ACCENT_CYAN), ("pressed", ACCENT_PURPLE)])

    style.configure("Neon.Horizontal.TScrollbar",
                    background=BUTTON_BG,
                    troughcolor=BG_DEEP,
                    bordercolor=BG_DEEP,
                    arrowcolor=ACCENT_CYAN,
                    relief="flat",
                    borderwidth=0)
    style.map("Neon.Horizontal.TScrollbar",
              background=[("active", ACCENT_CYAN), ("pressed", ACCENT_PURPLE)])


def style_button(btn, active=False):
    # active=True highlights the currently selected tool
    if active:
        btn.config(bg=ACCENT_CYAN, fg=BG_DEEP,
                   activebackground=ACCENT_CYAN, activeforeground=BG_DEEP,
                   relief="flat")
    else:
        btn.config(bg=BUTTON_BG, fg=TEXT_PRIMARY,
                   activebackground=BUTTON_HOVER, activeforeground=TEXT_PRIMARY,
                   relief="flat")


def style_label(lbl, secondary=False):
    fg = TEXT_SECONDARY if secondary else TEXT_PRIMARY
    lbl.config(fg=fg, bg=BG_PANEL)


def style_frame(frame):
    frame.config(bg=BG_PANEL)


def style_panel_header(lbl, accent_color=ACCENT_CYAN):
    """Style a section header with accent color."""
    lbl.config(fg=accent_color, bg=BG_PANEL, font=("Consolas", 9, "bold"))


def style_listbox(lb):
    lb.config(bg=BG_PANEL_ALT, fg=TEXT_PRIMARY,
              selectbackground=ACCENT_CYAN, selectforeground=BG_DEEP,
              font=("Consolas", 9), highlightthickness=1,
              highlightbackground=BORDER, highlightcolor=ACCENT_CYAN)


def style_entry(entry):
    entry.config(bg=BG_PANEL_ALT, fg=TEXT_PRIMARY,
                 insertbackground=ACCENT_CYAN, font=("Consolas", 9),
                 highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=ACCENT_CYAN)


def style_scale(scale):
    scale.config(bg=BG_PANEL, fg=TEXT_PRIMARY, troughcolor=BG_PANEL_ALT,
                 highlightthickness=0, activebackground=ACCENT_CYAN)


def style_checkbutton(cb):
    cb.config(bg=BG_PANEL, fg=TEXT_PRIMARY, selectcolor=BG_PANEL_ALT,
              activebackground=BG_PANEL, activeforeground=ACCENT_CYAN)


def style_text(text_widget):
    text_widget.config(bg=BG_PANEL_ALT, fg=TEXT_PRIMARY,
                       font=("Consolas", 8),
                       highlightthickness=1, highlightbackground=BORDER)


def style_spinbox(spinbox):
    spinbox.config(bg=BG_PANEL_ALT, fg=TEXT_PRIMARY,
                   buttonbackground=BUTTON_BG, font=("Consolas", 8))


def style_scrollbar(sb):
    sb.config(bg=BUTTON_BG, troughcolor=BG_PANEL,
              activebackground=ACCENT_CYAN, highlightthickness=0)


def style_canvas(canvas, is_main=False):
    bg = BG_DEEP if is_main else BG_PANEL_ALT
    canvas.config(bg=bg, highlightthickness=1, highlightbackground=BORDER)


def style_menu(menu):
    menu.config(bg=BG_PANEL, fg=TEXT_PRIMARY,
                activebackground=ACCENT_CYAN, activeforeground=BG_DEEP,
                font=("Consolas", 9))
