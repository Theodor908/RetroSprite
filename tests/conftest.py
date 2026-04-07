import pytest
import tkinter as tk


@pytest.fixture
def root():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk unavailable in this environment")
    root.withdraw()
    yield root
    root.destroy()
