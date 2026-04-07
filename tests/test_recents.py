"""Tests for recent projects storage."""
import json
import os
import tempfile
import time

import pytest

from src.recents import load_recents, update_recents, RECENTS_FILENAME


@pytest.fixture
def recents_dir(tmp_path, monkeypatch):
    """Redirect recents storage to a temp directory."""
    monkeypatch.setattr("src.recents._get_config_dir", lambda: str(tmp_path))
    return tmp_path


def test_load_recents_empty(recents_dir):
    """Returns empty list when no recents file exists."""
    assert load_recents() == []


def test_update_and_load(recents_dir):
    """Adding a path makes it appear in load_recents."""
    f = recents_dir / "test.retro"
    f.write_text("")
    update_recents(str(f))
    result = load_recents()
    assert len(result) == 1
    assert result[0]["path"] == str(f)


def test_update_bumps_existing(recents_dir):
    """Re-adding a path moves it to the top."""
    f1 = recents_dir / "a.retro"
    f2 = recents_dir / "b.retro"
    f1.write_text("")
    f2.write_text("")
    update_recents(str(f1))
    update_recents(str(f2))
    update_recents(str(f1))
    result = load_recents()
    assert result[0]["path"] == str(f1)
    assert result[1]["path"] == str(f2)


def test_cap_at_five(recents_dir):
    """List never exceeds 5 entries."""
    files = []
    for i in range(7):
        f = recents_dir / f"{i}.retro"
        f.write_text("")
        files.append(f)
        update_recents(str(f))
    result = load_recents()
    assert len(result) == 5
    assert result[0]["path"] == str(files[6])


def test_filters_dead_paths(recents_dir):
    """Entries whose files no longer exist are filtered out."""
    f = recents_dir / "gone.retro"
    f.write_text("")
    update_recents(str(f))
    f.unlink()
    result = load_recents()
    assert len(result) == 0


def test_corrupted_file_returns_empty(recents_dir):
    """Gracefully handles corrupted JSON."""
    path = recents_dir / RECENTS_FILENAME
    path.write_text("not json {{{")
    assert load_recents() == []
