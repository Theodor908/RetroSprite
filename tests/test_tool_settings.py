"""Tests for ToolSettingsManager."""
from src.tool_settings import ToolSettingsManager


def test_defaults_exist_for_all_tools():
    mgr = ToolSettingsManager()
    for tool in ["pen", "eraser", "blur", "fill", "line", "rect", "ellipse", "wand",
                 "pick", "select", "hand", "lasso"]:
        settings = mgr.get(tool)
        assert isinstance(settings, dict)


def test_pen_defaults():
    mgr = ToolSettingsManager()
    s = mgr.get("pen")
    assert s["size"] == 1
    assert s["symmetry"] == "off"
    assert s["dither"] == "none"
    assert s["pixel_perfect"] is False
    assert s["ink_mode"] == "normal"


def test_eraser_defaults():
    mgr = ToolSettingsManager()
    s = mgr.get("eraser")
    assert s["size"] == 3
    assert s["ink_mode"] == "normal"


def test_save_and_get():
    mgr = ToolSettingsManager()
    mgr.save("pen", {"size": 5, "symmetry": "horizontal"})
    s = mgr.get("pen")
    assert s["size"] == 5
    assert s["symmetry"] == "horizontal"
    # Other defaults preserved
    assert s["dither"] == "none"


def test_save_ignores_unknown_keys():
    mgr = ToolSettingsManager()
    mgr.save("pen", {"size": 5, "bogus_key": 999})
    s = mgr.get("pen")
    assert s["size"] == 5
    assert "bogus_key" not in s


def test_to_dict_round_trip():
    mgr = ToolSettingsManager()
    mgr.save("pen", {"size": 7, "dither": "checker"})
    mgr.save("eraser", {"size": 10})
    data = mgr.to_dict()
    mgr2 = ToolSettingsManager.from_dict(data)
    assert mgr2.get("pen")["size"] == 7
    assert mgr2.get("pen")["dither"] == "checker"
    assert mgr2.get("eraser")["size"] == 10


def test_from_dict_fills_missing_with_defaults():
    mgr = ToolSettingsManager.from_dict({"pen": {"size": 3}})
    s = mgr.get("pen")
    assert s["size"] == 3
    assert s["symmetry"] == "off"  # default filled in
    # Other tools get full defaults
    assert mgr.get("eraser")["size"] == 3  # eraser default


def test_get_unknown_tool_returns_empty():
    mgr = ToolSettingsManager()
    s = mgr.get("nonexistent_tool")
    assert s == {}


def test_project_round_trip(tmp_path):
    """Verify tool settings survive save/load cycle."""
    from src.tool_settings import ToolSettingsManager
    import json
    mgr = ToolSettingsManager()
    mgr.save("pen", {"size": 7, "symmetry": "both", "dither": "checker"})
    mgr.save("eraser", {"size": 12})
    data = mgr.to_dict()
    # Simulate what save_project would write
    path = tmp_path / "test.json"
    path.write_text(json.dumps({"tool_settings": data}))
    # Simulate what load_project would read
    loaded = json.loads(path.read_text())
    mgr2 = ToolSettingsManager.from_dict(loaded.get("tool_settings", {}))
    assert mgr2.get("pen")["size"] == 7
    assert mgr2.get("pen")["symmetry"] == "both"
    assert mgr2.get("eraser")["size"] == 12
