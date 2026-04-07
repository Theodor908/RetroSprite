# tests/test_right_panel.py
import pytest
from src.ui.right_panel import RightPanel, CollapsibleSection


def test_collapsible_section(root):
    section = CollapsibleSection(root, title="Test")
    section.pack()
    assert section.is_expanded == True
    section.toggle()
    assert section.is_expanded == False
    section.toggle()
    assert section.is_expanded == True


def test_right_panel_has_no_layer_panel(root):
    panel = RightPanel(root)
    assert not hasattr(panel, "layer_panel")


def test_right_panel_has_no_frame_panel(root):
    panel = RightPanel(root)
    assert not hasattr(panel, "frame_panel")


def test_right_panel_has_palette(root):
    panel = RightPanel(root)
    assert hasattr(panel, "palette_section")


def test_right_panel_has_color_picker(root):
    panel = RightPanel(root)
    assert hasattr(panel, "picker_section")
