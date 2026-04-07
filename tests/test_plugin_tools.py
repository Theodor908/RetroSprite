"""Tests for plugin tool and effect base classes."""
import pytest
from src.plugin_tools import PluginTool


class TestPluginTool:
    def test_default_attributes(self):
        tool = PluginTool()
        assert tool.name == ""
        assert tool.icon is None
        assert tool.cursor == "crosshair"

    def test_on_click_is_noop(self):
        tool = PluginTool()
        tool.on_click(None, 0, 0)

    def test_on_drag_is_noop(self):
        tool = PluginTool()
        tool.on_drag(None, 0, 0)

    def test_on_release_is_noop(self):
        tool = PluginTool()
        tool.on_release(None, 0, 0)

    def test_subclass_override(self):
        class StampTool(PluginTool):
            name = "Stamp"
            icon = "stamp.png"
            cursor = "hand2"

            def on_click(self, api, x, y):
                return (x, y)

        stamp = StampTool()
        assert stamp.name == "Stamp"
        assert stamp.icon == "stamp.png"
        assert stamp.on_click(None, 5, 10) == (5, 10)
