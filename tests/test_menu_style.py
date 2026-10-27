"""Tests for the X11 menu outline."""

import pytest

tk = pytest.importorskip('tkinter')
from tkinter import ttk

from constants import UI_BG, UI_BORDER
from ui.menu_style import iter_menus, style_menu


@pytest.fixture
def root():
    """A hidden Tk root using clam, skipping if no display is available."""
    try:
        instance = tk.Tk()
    except tk.TclError:
        pytest.skip("No display available for tkinter tests")
    instance.withdraw()
    ttk.Style(instance).theme_use('clam')
    yield instance
    instance.destroy()


@pytest.fixture
def x11(root):
    if root.tk.call('tk', 'windowingsystem') != 'x11':
        pytest.skip("Menus are only restyled on X11")


def _menu(root):
    menu = tk.Menu(root, tearoff=0)
    menu.add_command(label="New")
    menu.add_separator()
    menu.add_command(label="Recent")
    menu.add_separator()
    menu.add_command(label="Exit")
    return menu


def _types(menu):
    return [menu.type(i) for i in range(menu.index('end') + 1)]


def _background(menu, index):
    return str(menu.entrycget(index, 'background'))


def test_outline_is_the_menu_background_behind_a_flat_border(root, x11):
    menu = _menu(root)
    style_menu(menu)

    assert str(menu.cget('background')) == UI_BORDER
    assert str(menu.cget('relief')) == 'flat'
    assert int(menu.cget('borderwidth')) == 1
    for index in range(menu.index('end') + 1):
        assert _background(menu, index) == UI_BG
    # Separators are Tk's own
    assert _types(menu).count('separator') == 2


def test_entries_added_later_are_painted_when_the_menu_opens(root, x11):
    menu = tk.Menu(root, tearoff=0)
    style_menu(menu)
    menu.add_command(label="Song.txt")
    menu.add_separator()
    menu.add_command(label="Clear")

    menu.tk.eval(menu.cget('postcommand'))

    for index in range(3):
        assert _background(menu, index) == UI_BG


def test_keeps_an_existing_postcommand(root, x11):
    calls = []
    menu = tk.Menu(root, tearoff=0, postcommand=lambda: calls.append(1))
    style_menu(menu)
    menu.tk.eval(menu.cget('postcommand'))
    assert calls == [1]


def test_leaves_other_themes_alone(root):
    ttk.Style(root).theme_use('alt')
    menu = _menu(root)
    background = str(menu.cget('background'))
    style_menu(menu)
    assert str(menu.cget('background')) == background
    assert _background(menu, 0) == ''


class _Win32Interp:
    """Tk interpreter stand-in that reports the win32 windowing system."""

    def __init__(self, real):
        self._real = real

    def call(self, *args):
        if args == ('tk', 'windowingsystem'):
            return 'win32'
        return self._real.call(*args)

    def __getattr__(self, name):
        return getattr(self._real, name)


def test_leaves_other_windowing_systems_alone(root):
    menu = _menu(root)
    real = menu.tk
    menu.tk = _Win32Interp(real)
    try:
        style_menu(menu)
    finally:
        menu.tk = real
    assert _background(menu, 0) == ''


def test_empty_menu_is_fine(root, x11):
    menu = tk.Menu(root, tearoff=0)
    style_menu(menu)
    assert menu.index('end') is None


def test_iter_menus_finds_nested_menus(root):
    menubar = tk.Menu(root)
    file_menu = tk.Menu(menubar, tearoff=0)
    recent = tk.Menu(file_menu, tearoff=0)
    frame = tk.Frame(root)
    popup = tk.Menu(frame, tearoff=0)
    found = list(iter_menus(root))
    for menu in (menubar, file_menu, recent, popup):
        assert menu in found
