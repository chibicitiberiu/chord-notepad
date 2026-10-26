"""Tests for :func:`utils.ui_helpers.resolve_font_family`.

The editor's default font is the Tk named font ``TkFixedFont``; used directly
in a ``(family, size)`` tuple, Tk fell back to a proportional font.
"""

import os

import pytest

tk = pytest.importorskip('tkinter')
from tkinter import font as tkfont  # noqa: E402

from utils.ui_helpers import resolve_font_family  # noqa: E402


def _has_display() -> bool:
    return bool(os.environ.get('DISPLAY')) or os.name == 'nt'


@pytest.fixture
def root():
    """A hidden Tk root, skipping the test if no display is available."""
    if not _has_display():
        pytest.skip("No display available for tkinter tests")
    try:
        instance = tk.Tk()
    except tk.TclError:
        pytest.skip("No display available for tkinter tests")
    instance.withdraw()
    yield instance
    instance.destroy()


def test_named_fixed_font_resolves_to_monospace_family(root):
    family = resolve_font_family(root, 'TkFixedFont')
    assert family != 'TkFixedFont'
    assert tkfont.Font(root=root, font=(family, 11)).metrics('fixed') == 1


def test_real_family_is_unchanged(root):
    assert resolve_font_family(root, 'Courier') == 'Courier'
