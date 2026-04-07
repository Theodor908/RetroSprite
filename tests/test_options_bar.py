# tests/test_options_bar.py
import pytest
from src.ui.options_bar import OptionsBar


def test_options_bar_creation(root):
    bar = OptionsBar(root)
    assert bar is not None
    assert bar.winfo_exists()


def test_options_bar_update_tool(root):
    bar = OptionsBar(root)
    bar.set_tool("pen")
    assert bar.current_tool == "pen"
    # Pen should show size, symmetry, dither, pixel perfect
    assert bar._size_frame.winfo_ismapped() or bar._size_frame.winfo_manager() != ""


def test_options_bar_update_tool_hand(root):
    bar = OptionsBar(root)
    bar.set_tool("hand")
    assert bar.current_tool == "hand"
    # Hand should hide size controls


def test_options_bar_get_size(root):
    bar = OptionsBar(root)
    bar.set_tool("pen")
    bar.set_size(5)
    assert bar.get_size() == 5


def test_options_bar_get_symmetry(root):
    bar = OptionsBar(root)
    assert bar.get_symmetry() == "off"
