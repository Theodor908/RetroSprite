# tests/test_toolbar.py
import pytest
import tkinter as tk
from src.ui.toolbar import Toolbar


def test_toolbar_creation(root):
    selected = []
    toolbar = Toolbar(root, on_tool_change=lambda t: selected.append(t))
    assert toolbar is not None
    assert toolbar.winfo_exists()


def test_toolbar_has_all_tools(root):
    toolbar = Toolbar(root, on_tool_change=lambda t: None)
    expected_tools = ["pen", "eraser", "blur", "fill", "ellipse",
                      "pick", "select", "wand", "line", "rect", "move", "hand", "lasso",
                      "polygon", "roundrect", "text"]
    assert set(toolbar.tool_names) == set(expected_tools)


def test_toolbar_select_tool(root):
    selected = []
    toolbar = Toolbar(root, on_tool_change=lambda t: selected.append(t))
    toolbar.select_tool("eraser")
    assert toolbar.active_tool == "eraser"


def test_toolbar_width_is_narrow(root):
    toolbar = Toolbar(root, on_tool_change=lambda t: None)
    toolbar.update_idletasks()
    # Should be narrow (~48px) since we removed all text controls
    assert toolbar.winfo_reqwidth() <= 80


def test_toolbar_has_scroll_canvas(root):
    """Toolbar should contain an internal Canvas for scrolling."""
    toolbar = Toolbar(root, on_tool_change=lambda t: None)
    assert hasattr(toolbar, '_scroll_canvas')
    assert isinstance(toolbar._scroll_canvas, tk.Canvas)


def test_toolbar_buttons_in_inner_frame(root):
    """All tool buttons should be children of the inner frame, not the toolbar itself."""
    toolbar = Toolbar(root, on_tool_change=lambda t: None)
    assert hasattr(toolbar, '_inner_frame')
    for tool_name, btn in toolbar._buttons.items():
        assert btn.master == toolbar._inner_frame, f"{tool_name} button not in inner frame"


def test_toolbar_scroll_region_updates(root):
    """Scroll region should cover all buttons after layout."""
    toolbar = Toolbar(root, on_tool_change=lambda t: None)
    toolbar.update_idletasks()
    sr = toolbar._scroll_canvas.cget("scrollregion")
    assert sr != "" and sr != "0 0 0 0"
