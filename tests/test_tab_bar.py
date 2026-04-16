"""Tests for TabBar widget."""
import pytest

from src.ui.tab_bar import TabBar


@pytest.fixture
def tab_bar(root):
    bar = TabBar(root, on_tab_select=lambda i: None,
                 on_tab_close=lambda i: None,
                 on_new_tab=lambda: None)
    return bar


def test_add_tab(tab_bar):
    tab_bar.add_tab("sprite.retro")
    assert tab_bar.tab_count == 1
    assert tab_bar.get_tab_name(0) == "sprite.retro"


def test_add_multiple_tabs(tab_bar):
    tab_bar.add_tab("file1.retro")
    tab_bar.add_tab("file2.retro")
    tab_bar.add_tab("file3.retro")
    assert tab_bar.tab_count == 3


def test_remove_tab(tab_bar):
    tab_bar.add_tab("file1.retro")
    tab_bar.add_tab("file2.retro")
    tab_bar.remove_tab(0)
    assert tab_bar.tab_count == 1
    assert tab_bar.get_tab_name(0) == "file2.retro"


def test_set_active_tab(tab_bar):
    tab_bar.add_tab("file1.retro")
    tab_bar.add_tab("file2.retro")
    tab_bar.set_active(1)
    assert tab_bar.active_index == 1


def test_set_dirty(tab_bar):
    tab_bar.add_tab("file.retro")
    tab_bar.set_dirty(0, True)
    assert tab_bar.is_dirty(0) is True
    tab_bar.set_dirty(0, False)
    assert tab_bar.is_dirty(0) is False


def test_rename_tab(tab_bar):
    tab_bar.add_tab("Untitled")
    tab_bar.rename_tab(0, "sprite.retro")
    assert tab_bar.get_tab_name(0) == "sprite.retro"


def test_set_tooltip(tab_bar):
    tab_bar.add_tab("sprite.retro")
    tab_bar.set_tooltip(0, "/full/path/to/sprite.retro")
    assert tab_bar.get_tooltip(0) == "/full/path/to/sprite.retro"


def test_clear_all(tab_bar):
    tab_bar.add_tab("file1.retro")
    tab_bar.add_tab("file2.retro")
    tab_bar.clear()
    assert tab_bar.tab_count == 0
