"""Tests for applying Xft.dpi to Tk 8.6 scaling on X11."""

from unittest.mock import MagicMock

import pytest

from utils import display_scaling


def _root(windowing_system="x11"):
    root = MagicMock()
    root.tk.call.side_effect = lambda *args: windowing_system if args == ("tk", "windowingsystem") else None
    return root


@pytest.fixture
def linux_tk86(monkeypatch):
    monkeypatch.setattr(display_scaling.sys, "platform", "linux")
    monkeypatch.setattr(display_scaling.tk, "TkVersion", 8.6)


def test_sets_scaling_from_xft_dpi(linux_tk86, monkeypatch):
    monkeypatch.setattr(display_scaling, "_read_xft_dpi", lambda: 120.0)
    root = _root()
    display_scaling.apply_xft_dpi(root)
    root.tk.call.assert_any_call("tk", "scaling", 120.0 / 72.0)


def test_leaves_scaling_alone_without_resource(linux_tk86, monkeypatch):
    monkeypatch.setattr(display_scaling, "_read_xft_dpi", lambda: None)
    root = _root()
    display_scaling.apply_xft_dpi(root)
    assert all(call.args[:2] != ("tk", "scaling") for call in root.tk.call.call_args_list)


def test_skips_tk9(monkeypatch):
    monkeypatch.setattr(display_scaling.sys, "platform", "linux")
    monkeypatch.setattr(display_scaling.tk, "TkVersion", 9.0)
    read = MagicMock(return_value=120.0)
    monkeypatch.setattr(display_scaling, "_read_xft_dpi", read)
    root = _root()
    display_scaling.apply_xft_dpi(root)
    read.assert_not_called()
    root.tk.call.assert_not_called()


@pytest.mark.parametrize("platform", ["win32", "darwin"])
def test_skips_other_platforms(monkeypatch, platform):
    monkeypatch.setattr(display_scaling.sys, "platform", platform)
    monkeypatch.setattr(display_scaling.tk, "TkVersion", 8.6)
    root = _root()
    display_scaling.apply_xft_dpi(root)
    root.tk.call.assert_not_called()


def test_skips_non_x11_windowing(linux_tk86, monkeypatch):
    read = MagicMock(return_value=120.0)
    monkeypatch.setattr(display_scaling, "_read_xft_dpi", read)
    display_scaling.apply_xft_dpi(_root(windowing_system="aqua"))
    read.assert_not_called()


def test_tcl_error_is_logged_not_raised(linux_tk86, monkeypatch):
    monkeypatch.setattr(display_scaling, "_read_xft_dpi", lambda: 120.0)
    root = MagicMock()
    root.tk.call.side_effect = display_scaling.tk.TclError("boom")
    display_scaling.apply_xft_dpi(root)  # must not raise


def test_read_xft_dpi_without_libx11(monkeypatch):
    def no_lib(name):
        raise OSError("not found")
    monkeypatch.setattr(display_scaling.ctypes, "CDLL", no_lib)
    assert display_scaling._read_xft_dpi() is None
