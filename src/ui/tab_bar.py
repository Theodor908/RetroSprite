"""TabBar widget — horizontal row of closeable document tabs."""
from __future__ import annotations
import tkinter as tk
from typing import Callable, List, Optional

try:
    from src.ui.theme import (
        BG_DEEP, BG_PANEL, TEXT_PRIMARY, TEXT_SECONDARY, ACCENT_CYAN,
        TAB_ACTIVE, TAB_INACTIVE, TAB_HOVER, TAB_CLOSE, TAB_CLOSE_HOVER,
        TAB_DIRTY, TAB_BORDER,
    )
except ImportError:
    # Fallbacks until theme.py is updated
    BG_DEEP = "#0d0d12"
    BG_PANEL = "#14141f"
    TEXT_PRIMARY = "#e0e0e8"
    TEXT_SECONDARY = "#7a7a9a"
    ACCENT_CYAN = "#00f0ff"
    TAB_ACTIVE = "#1a1a2e"
    TAB_INACTIVE = "#0d0d12"
    TAB_HOVER = "#22223a"
    TAB_CLOSE = "#7a7a9a"
    TAB_CLOSE_HOVER = "#ff4466"
    TAB_DIRTY = "#ff00aa"
    TAB_BORDER = "#1e1e3a"

_FONT = ("Consolas", 9)
_BAR_HEIGHT = 28
_MAX_NAME_LEN = 20


def _truncate(name: str) -> str:
    """Truncate name to _MAX_NAME_LEN chars with ellipsis."""
    if len(name) > _MAX_NAME_LEN:
        return name[:_MAX_NAME_LEN - 1] + "\u2026"
    return name


class _TabButton:
    """Holds per-tab data and widget references."""

    def __init__(self, name: str):
        self.name: str = name
        self.dirty: bool = False
        self.tooltip: str = ""
        # Widget references set after construction
        self.frame: Optional[tk.Frame] = None
        self.dirty_lbl: Optional[tk.Label] = None
        self.name_lbl: Optional[tk.Label] = None
        self.close_btn: Optional[tk.Label] = None


class TabBar(tk.Frame):
    """Custom tab bar widget — fires callbacks, does NOT manage document state."""

    def __init__(
        self,
        parent,
        *,
        on_tab_select: Callable[[int], None],
        on_tab_close: Callable[[int], None],
        on_new_tab: Callable[[], None],
        on_tab_context: Callable[[int, tk.Event], None] | None = None,
        **kwargs,
    ):
        super().__init__(parent, bg=BG_DEEP, height=_BAR_HEIGHT, **kwargs)
        self.pack_propagate(False)

        self._on_tab_select = on_tab_select
        self._on_tab_close = on_tab_close
        self._on_new_tab = on_new_tab
        self._on_tab_context = on_tab_context

        self._tabs: List[_TabButton] = []
        self._active: int = -1

        # Scrollable inner canvas
        self._canvas = tk.Canvas(
            self, bg=BG_DEEP, height=_BAR_HEIGHT,
            highlightthickness=0, bd=0,
        )
        self._canvas.pack(side="left", fill="both", expand=True)

        # Inner frame placed inside canvas window
        self._inner = tk.Frame(self._canvas, bg=BG_DEEP)
        self._win_id = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")

        self._inner.bind("<Configure>", self._on_inner_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)
        self._canvas.bind("<MouseWheel>", self._on_mousewheel)
        self._inner.bind("<MouseWheel>", self._on_mousewheel)

        # [+] new-tab button on the far right
        self._new_btn = tk.Label(
            self, text=" + ", bg=BG_DEEP, fg=TEXT_SECONDARY,
            font=_FONT, cursor="hand2", padx=4,
        )
        self._new_btn.pack(side="right", fill="y")
        self._new_btn.bind("<Button-1>", lambda _e: self._on_new_tab())
        self._new_btn.bind("<Enter>", lambda _e: self._new_btn.config(fg=ACCENT_CYAN))
        self._new_btn.bind("<Leave>", lambda _e: self._new_btn.config(fg=TEXT_SECONDARY))

        # Bottom border line
        tk.Frame(self, bg=TAB_BORDER, height=1).pack(side="bottom", fill="x")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _on_inner_configure(self, _event=None):
        bbox = self._canvas.bbox("all")
        if bbox:
            self._canvas.configure(scrollregion=bbox)

    def _on_canvas_configure(self, event):
        # Keep inner frame height matched to canvas
        self._canvas.itemconfigure(self._win_id, height=event.height)

    def _on_mousewheel(self, event):
        self._canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")

    def _build_tab_widget(self, tab: _TabButton, index: int) -> tk.Frame:
        """Create and return the Frame widget for a tab entry."""
        is_active = (index == self._active)
        bg = TAB_ACTIVE if is_active else TAB_INACTIVE
        fg = TEXT_PRIMARY if is_active else TEXT_SECONDARY

        frame = tk.Frame(
            self._inner, bg=bg, padx=4, pady=0,
            highlightthickness=1,
            highlightbackground=TAB_BORDER if is_active else BG_DEEP,
        )
        frame.pack(side="left", fill="y", padx=(0, 1))

        # Dirty dot
        dirty_lbl = tk.Label(
            frame, text="\u25cf" if tab.dirty else " ",
            bg=bg, fg=TAB_DIRTY if tab.dirty else bg,
            font=_FONT, padx=0,
        )
        dirty_lbl.pack(side="left")

        # Name label
        name_lbl = tk.Label(
            frame, text=_truncate(tab.name),
            bg=bg, fg=fg, font=_FONT, padx=2, cursor="hand2",
        )
        name_lbl.pack(side="left")

        # Close button
        close_btn = tk.Label(
            frame, text="\u00d7",
            bg=bg, fg=TAB_CLOSE, font=_FONT, padx=2, cursor="hand2",
        )
        close_btn.pack(side="left")

        # --- bind events ---
        def _select(_e, i=index):
            self._on_tab_select(i)

        def _close(_e, i=index):
            self._on_tab_close(i)

        def _enter_tab(_e, f=frame, nl=name_lbl, dl=dirty_lbl, cb=close_btn, i=index):
            if i != self._active:
                f.config(bg=TAB_HOVER)
                nl.config(bg=TAB_HOVER)
                dl.config(bg=TAB_HOVER)
                cb.config(bg=TAB_HOVER)

        def _leave_tab(_e, f=frame, nl=name_lbl, dl=dirty_lbl, cb=close_btn, i=index):
            if i != self._active:
                f.config(bg=TAB_INACTIVE)
                nl.config(bg=TAB_INACTIVE)
                dl.config(bg=TAB_INACTIVE)
                cb.config(bg=TAB_INACTIVE)

        def _enter_close(_e, cb=close_btn):
            cb.config(fg=TAB_CLOSE_HOVER)

        def _leave_close(_e, cb=close_btn, i=index):
            cb.config(fg=TAB_CLOSE)

        for widget in (frame, name_lbl, dirty_lbl):
            widget.bind("<Button-1>", _select)
            widget.bind("<Button-2>", _close)   # middle-click
            widget.bind("<Button-3>",
                        lambda e, i=index: self._show_context(i, e))
            widget.bind("<Enter>", _enter_tab)
            widget.bind("<Leave>", _leave_tab)

        close_btn.bind("<Button-1>", _close)
        close_btn.bind("<Button-2>", _close)
        close_btn.bind("<Enter>", _enter_close)
        close_btn.bind("<Leave>", _leave_close)

        tab.frame = frame
        tab.dirty_lbl = dirty_lbl
        tab.name_lbl = name_lbl
        tab.close_btn = close_btn

        return frame

    def _show_context(self, index: int, event: tk.Event) -> None:
        if self._on_tab_context:
            self._on_tab_context(index, event)

    def _rebuild_all(self):
        """Destroy all tab widgets and recreate them from scratch."""
        for widget in self._inner.winfo_children():
            widget.destroy()
        for i, tab in enumerate(self._tabs):
            self._build_tab_widget(tab, i)

    def _refresh_tab_appearance(self, index: int):
        """Update visual styling of a single tab (active vs inactive)."""
        tab = self._tabs[index]
        if tab.frame is None:
            return
        is_active = (index == self._active)
        bg = TAB_ACTIVE if is_active else TAB_INACTIVE
        fg = TEXT_PRIMARY if is_active else TEXT_SECONDARY
        tab.frame.config(
            bg=bg,
            highlightbackground=TAB_BORDER if is_active else BG_DEEP,
        )
        tab.name_lbl.config(bg=bg, fg=fg)
        dirty_fg = TAB_DIRTY if tab.dirty else bg
        tab.dirty_lbl.config(bg=bg, fg=dirty_fg)
        tab.close_btn.config(bg=bg)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def tab_count(self) -> int:
        return len(self._tabs)

    @property
    def active_index(self) -> int:
        return self._active

    def add_tab(self, name: str, activate: bool = True) -> int:
        """Append a new tab and return its index."""
        tab = _TabButton(name)
        prev_active = self._active
        index = len(self._tabs)
        self._tabs.append(tab)
        if activate or self._active == -1:
            self._active = index
        self._build_tab_widget(tab, index)
        # Refresh previous active tab to remove its highlight
        if activate and prev_active >= 0 and prev_active != index:
            self._refresh_tab_appearance(prev_active)
        return index

    def remove_tab(self, index: int):
        """Remove tab at *index*, rebuild indices."""
        if index < 0 or index >= len(self._tabs):
            return
        tab = self._tabs.pop(index)
        if tab.frame is not None:
            tab.frame.destroy()
        # Adjust active index
        if self._active >= len(self._tabs):
            self._active = len(self._tabs) - 1
        elif self._active > index:
            self._active -= 1
        # Full rebuild because closures capture stale indices after removal
        self._rebuild_all()

    def set_active(self, index: int):
        """Highlight *index* as the active tab."""
        if index < 0 or index >= len(self._tabs):
            return
        old = self._active
        self._active = index
        if old != index and 0 <= old < len(self._tabs):
            self._refresh_tab_appearance(old)
        self._refresh_tab_appearance(index)

    def get_tab_name(self, index: int) -> str:
        return self._tabs[index].name

    def rename_tab(self, index: int, name: str):
        self._tabs[index].name = name
        tab = self._tabs[index]
        if tab.name_lbl is not None:
            tab.name_lbl.config(text=_truncate(name))

    def set_dirty(self, index: int, dirty: bool):
        self._tabs[index].dirty = dirty
        tab = self._tabs[index]
        if tab.dirty_lbl is not None:
            is_active = (index == self._active)
            bg = TAB_ACTIVE if is_active else TAB_INACTIVE
            tab.dirty_lbl.config(
                text="\u25cf" if dirty else " ",
                fg=TAB_DIRTY if dirty else bg,
            )

    def is_dirty(self, index: int) -> bool:
        return self._tabs[index].dirty

    def set_tooltip(self, index: int, tooltip: str):
        self._tabs[index].tooltip = tooltip

    def get_tooltip(self, index: int) -> str:
        return self._tabs[index].tooltip

    def clear(self):
        """Remove all tabs."""
        for widget in self._inner.winfo_children():
            widget.destroy()
        self._tabs.clear()
        self._active = -1
