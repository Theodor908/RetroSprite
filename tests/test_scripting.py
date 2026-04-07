"""Tests for RetroSpriteAPI scripting interface."""
import pytest
import os
from src.animation import AnimationTimeline, Frame
from src.layer import Layer
from src.palette import Palette
from src.pixel_data import PixelGrid
from src.scripting import RetroSpriteAPI
from src.plugins import discover_plugins, load_plugin, load_all_plugins
from src.cli import build_parser


@pytest.fixture
def api():
    timeline = AnimationTimeline(16, 16)
    palette = Palette("Pico-8")
    return RetroSpriteAPI(timeline=timeline, palette=palette, app=None)


class TestEventSystem:
    def test_on_registers_listener(self, api):
        calls = []
        api.on("test_event", lambda e: calls.append(e))
        api.emit("test_event", {"key": "value"})
        assert len(calls) == 1
        assert calls[0]["key"] == "value"

    def test_off_removes_listener(self, api):
        calls = []
        cb = lambda e: calls.append(e)
        api.on("test_event", cb)
        api.off("test_event", cb)
        api.emit("test_event", {})
        assert len(calls) == 0

    def test_off_nonexistent_is_silent(self, api):
        api.off("nonexistent", lambda e: None)

    def test_before_event_cancellable(self, api):
        api.on("before_save", lambda e: False)
        result = api.emit("before_save", {"filepath": "test.retro"})
        assert result is False

    def test_before_event_allows(self, api):
        api.on("before_save", lambda e: True)
        result = api.emit("before_save", {"filepath": "test.retro"})
        assert result is True

    def test_non_before_event_not_cancellable(self, api):
        api.on("after_save", lambda e: False)
        result = api.emit("after_save", {"filepath": "test.retro"})
        assert result is True

    def test_multiple_listeners_fire_in_order(self, api):
        order = []
        api.on("test", lambda e: order.append(1))
        api.on("test", lambda e: order.append(2))
        api.emit("test", {})
        assert order == [1, 2]

    def test_listener_error_does_not_stop_others(self, api):
        calls = []
        api.on("test", lambda e: 1 / 0)
        api.on("test", lambda e: calls.append("ok"))
        api.emit("test", {})
        assert calls == ["ok"]


class TestPluginDiscovery:
    def test_discover_empty_dir(self, tmp_path):
        result = discover_plugins(str(tmp_path))
        assert result == []

    def test_discover_finds_py_files(self, tmp_path):
        (tmp_path / "plugin_a.py").write_text("pass")
        (tmp_path / "plugin_b.py").write_text("pass")
        (tmp_path / "not_a_plugin.txt").write_text("pass")
        result = discover_plugins(str(tmp_path))
        assert len(result) == 2
        assert all(r.endswith(".py") for r in result)

    def test_discover_nonexistent_dir(self):
        result = discover_plugins("/nonexistent/dir/12345")
        assert result == []


class TestPluginLoading:
    def test_load_valid_plugin(self, api, tmp_path):
        plugin_code = '''
PLUGIN_INFO = {"name": "Test Plugin", "version": "1.0"}

def register(api):
    api.register_filter("Test Filter", lambda g: g)
'''
        plugin_file = tmp_path / "test_plugin.py"
        plugin_file.write_text(plugin_code)
        info = load_plugin(str(plugin_file), api)
        assert info is not None
        assert info["name"] == "Test Plugin"
        assert "Test Filter" in api._plugin_filters

    def test_load_plugin_without_register(self, api, tmp_path):
        plugin_file = tmp_path / "bad_plugin.py"
        plugin_file.write_text("x = 1")
        info = load_plugin(str(plugin_file), api)
        assert info is None

    def test_load_plugin_with_error(self, api, tmp_path):
        plugin_file = tmp_path / "crash_plugin.py"
        plugin_file.write_text("def register(api):\n    raise RuntimeError('boom')")
        info = load_plugin(str(plugin_file), api)
        assert info is None

    def test_load_all_respects_disabled(self, api, tmp_path):
        import json
        (tmp_path / "good.py").write_text(
            "PLUGIN_INFO = {'name': 'Good'}\ndef register(api): pass"
        )
        (tmp_path / "bad.py").write_text(
            "PLUGIN_INFO = {'name': 'Bad'}\ndef register(api): pass"
        )
        config = tmp_path / "plugins.json"
        config.write_text(json.dumps({"disabled": ["bad.py"]}))
        result = load_all_plugins(api, plugin_dir=str(tmp_path),
                                  config_path=str(config))
        names = [p["name"] for p in result]
        assert "Good" in names
        assert "Bad" not in names


class TestProjectIO:
    def test_new_project(self, api):
        api.new_project(32, 32, fps=15)
        assert api.timeline.width == 32
        assert api.timeline.height == 32
        assert api.timeline.fps == 15
        assert api.timeline.frame_count == 1

    def test_save_and_load_project(self, api, tmp_path):
        path = str(tmp_path / "test.retro")
        api.save_project(path)
        api.new_project(8, 8)
        api.load_project(path)
        assert api.timeline.width == 16
        assert api.timeline.height == 16


class TestFrameLayerAccess:
    def test_current_frame_pixels_returns_pixelgrid(self, api):
        result = api.current_frame_pixels()
        assert isinstance(result, PixelGrid)
        assert result.width == 16
        assert result.height == 16

    def test_current_layer_returns_layer(self, api):
        layer = api.current_layer()
        assert isinstance(layer, Layer)

    def test_get_frame_returns_frame_obj(self, api):
        frame = api.get_frame(0)
        assert isinstance(frame, Frame)
        assert frame.width == 16

    def test_add_frame_returns_frame(self, api):
        frame = api.add_frame()
        assert isinstance(frame, Frame)
        assert api.timeline.frame_count == 2

    def test_add_layer_returns_layer(self, api):
        layer = api.add_layer("Test Layer")
        assert isinstance(layer, Layer)
        assert layer.name == "Test Layer"

    def test_remove_frame(self, api):
        api.add_frame()
        assert api.timeline.frame_count == 2
        api.remove_frame(1)
        assert api.timeline.frame_count == 1

    def test_remove_layer(self, api):
        api.add_layer("Extra")
        frame = api.timeline.current_frame_obj()
        assert len(frame.layers) == 2
        api.remove_layer(1)
        assert len(frame.layers) == 1


class TestApplyFilter:
    def test_apply_filter_modifies_pixels(self, api):
        layer = api.current_layer()
        layer.pixels.set_pixel(0, 0, (255, 0, 0, 255))

        def invert(grid):
            import numpy as np
            result = grid.copy()
            result._pixels[:, :, :3] = 255 - result._pixels[:, :, :3]
            return result

        api.apply_filter(invert)
        pixel = layer.pixels.get_pixel(0, 0)
        assert pixel[0] == 0
        assert pixel[1] == 255

    def test_apply_filter_to_specific_frame_layer(self, api):
        api.add_frame()
        api.add_layer("Layer 2")

        def clear_filter(grid):
            grid_copy = grid.copy()
            grid_copy.clear()
            return grid_copy

        api.apply_filter(clear_filter, frame=0, layer=0)


class TestExportMethods:
    def test_export_png(self, api, tmp_path):
        path = str(tmp_path / "out.png")
        api.export_png(path)
        assert os.path.exists(path)

    def test_export_gif(self, api, tmp_path):
        path = str(tmp_path / "out.gif")
        api.export_gif(path)
        assert os.path.exists(path)

    def test_export_sheet(self, api, tmp_path):
        path = str(tmp_path / "sheet.png")
        json_path = api.export_sheet(path)
        assert os.path.exists(path)
        assert os.path.exists(json_path)
        assert json_path.endswith(".json")


class TestRegistration:
    def test_register_menu_item_headless_is_noop(self, api):
        api.register_menu_item("Test", lambda: None)

    def test_register_filter(self, api):
        api.register_filter("Test Filter", lambda g: g)
        assert "Test Filter" in api._plugin_filters

    def test_register_tool_headless_warns(self, api):
        from src.plugin_tools import PluginTool
        api.register_tool("Test", PluginTool)
        assert "Test" in api._plugin_tools

    def test_register_effect(self, api):
        api.register_effect("Test FX", lambda p: p, {"size": 4})
        assert "Test FX" in api._plugin_effects

    def test_push_undo_headless_is_noop(self, api):
        api.push_undo("Test")


class TestCLIParser:
    def test_export_png_args(self):
        parser = build_parser()
        args = parser.parse_args(["export", "input.retro", "output.png",
                                  "--scale", "2", "--frame", "3"])
        assert args.command == "export"
        assert args.input == "input.retro"
        assert args.output == "output.png"
        assert args.scale == 2
        assert args.frame == 3

    def test_export_format_override(self):
        parser = build_parser()
        args = parser.parse_args(["export", "in.retro", "out.png",
                                  "--format", "gif"])
        assert args.format == "gif"

    def test_batch_args(self):
        parser = build_parser()
        args = parser.parse_args(["batch", "input_dir", "output_dir",
                                  "--format", "png", "--scale", "4"])
        assert args.command == "batch"
        assert args.input_dir == "input_dir"
        assert args.output_dir == "output_dir"
        assert args.format == "png"
        assert args.scale == 4

    def test_run_args(self):
        parser = build_parser()
        args = parser.parse_args(["run", "script.py", "--", "arg1", "arg2"])
        assert args.command == "run"
        assert args.script == "script.py"
        assert args.script_args == ["arg1", "arg2"]

    def test_info_args(self):
        parser = build_parser()
        args = parser.parse_args(["info", "project.retro"])
        assert args.command == "info"
        assert args.input == "project.retro"


class TestCLIExport:
    def test_cli_export_png(self, tmp_path):
        from src.cli import cmd_export
        from src.animation import AnimationTimeline
        from src.palette import Palette
        from src.project import save_project

        timeline = AnimationTimeline(8, 8)
        palette = Palette("Pico-8")
        proj_path = str(tmp_path / "test.retro")
        save_project(proj_path, timeline, palette)

        out_path = str(tmp_path / "out.png")
        result = cmd_export(proj_path, out_path, format=None, scale=1,
                           frame=0, columns=0, layer=None)
        assert result == 0
        assert os.path.exists(out_path)

    def test_cli_export_gif(self, tmp_path):
        from src.cli import cmd_export
        from src.animation import AnimationTimeline
        from src.palette import Palette
        from src.project import save_project

        timeline = AnimationTimeline(8, 8)
        palette = Palette("Pico-8")
        proj_path = str(tmp_path / "test.retro")
        save_project(proj_path, timeline, palette)

        out_path = str(tmp_path / "out.gif")
        result = cmd_export(proj_path, out_path, format=None, scale=1,
                           frame=0, columns=0, layer=None)
        assert result == 0
        assert os.path.exists(out_path)

    def test_cli_export_sheet(self, tmp_path):
        from src.cli import cmd_export
        from src.animation import AnimationTimeline
        from src.palette import Palette
        from src.project import save_project

        timeline = AnimationTimeline(8, 8)
        palette = Palette("Pico-8")
        proj_path = str(tmp_path / "test.retro")
        save_project(proj_path, timeline, palette)

        out_path = str(tmp_path / "sheet.json")
        result = cmd_export(proj_path, out_path, format="sheet", scale=1,
                           frame=0, columns=0, layer=None)
        assert result == 0

    def test_cli_export_batch(self, tmp_path):
        from src.cli import cmd_batch
        from src.animation import AnimationTimeline
        from src.palette import Palette
        from src.project import save_project

        in_dir = tmp_path / "input"
        in_dir.mkdir()
        out_dir = tmp_path / "output"
        for name in ["a", "b"]:
            timeline = AnimationTimeline(8, 8)
            palette = Palette("Pico-8")
            save_project(str(in_dir / f"{name}.retro"), timeline, palette)

        result = cmd_batch(str(in_dir), str(out_dir), "*.retro",
                          format="png", scale=1)
        assert result == 0
        assert os.path.exists(str(out_dir / "a.png"))
        assert os.path.exists(str(out_dir / "b.png"))

    def test_cli_info(self, tmp_path, capsys):
        from src.cli import cmd_info
        from src.animation import AnimationTimeline
        from src.palette import Palette
        from src.project import save_project

        timeline = AnimationTimeline(32, 32)
        timeline.fps = 12
        palette = Palette("Pico-8")
        proj_path = str(tmp_path / "hero.retro")
        save_project(proj_path, timeline, palette)

        result = cmd_info(proj_path)
        assert result == 0
        captured = capsys.readouterr()
        assert "32x32" in captured.out
        assert "12 fps" in captured.out


class TestMainRouting:
    def test_cli_subcommands_recognized(self):
        expected = {"export", "batch", "run", "info"}
        from src.cli import build_parser
        parser = build_parser()
        choices = next(
            a.choices for a in parser._actions
            if hasattr(a, "choices") and a.choices is not None
        )
        assert expected == set(choices.keys())


class TestCLIRun:
    def test_run_script_with_api(self, tmp_path):
        from src.cli import cmd_run
        from src.animation import AnimationTimeline
        from src.palette import Palette
        from src.project import save_project

        timeline = AnimationTimeline(8, 8)
        palette = Palette("Pico-8")
        proj_path = str(tmp_path / "test.retro")
        save_project(proj_path, timeline, palette)

        script = tmp_path / "test_script.py"
        out_png = str(tmp_path / "script_out.png")
        script.write_text(
            f'api.load_project(r"{proj_path}")\n'
            f'api.export_png(r"{out_png}")\n'
        )

        result = cmd_run(str(script), [])
        assert result == 0
        assert os.path.exists(out_png)

    def test_run_script_error_returns_1(self, tmp_path):
        from src.cli import cmd_run
        script = tmp_path / "bad_script.py"
        script.write_text("raise ValueError('test error')")
        result = cmd_run(str(script), [])
        assert result == 1
