"""CHORD_NOTEPAD_LIBFLUIDSYNTH lets packages point pyfluidsynth at a library."""

import ctypes.util
import glob
import importlib
import sys

import pytest

import audio.fluidsynth_import as loader


def _real_library_path():
    soname = ctypes.util.find_library("fluidsynth")
    if not soname:
        return None
    for folder in ("/usr/lib64", "/usr/lib", "/usr/lib/x86_64-linux-gnu", "/usr/local/lib"):
        matches = glob.glob(f"{folder}/{soname}")
        if matches:
            return matches[0]
    return None


@pytest.fixture
def fresh_import(monkeypatch):
    """Reload the loader with pyfluidsynth not yet imported."""
    saved = sys.modules.pop("fluidsynth", None)

    def reload():
        sys.modules.pop("fluidsynth", None)
        return importlib.reload(loader)

    yield reload
    sys.modules.pop("fluidsynth", None)
    if saved is not None:
        sys.modules["fluidsynth"] = saved
    importlib.reload(loader)


def test_env_path_is_used_when_the_linker_cache_has_no_fluidsynth(monkeypatch, fresh_import):
    path = _real_library_path()
    if path is None:
        pytest.skip("libfluidsynth not installed in a standard folder")
    # A snap: the system cache knows nothing about the bundled library
    nothing = lambda name: None
    monkeypatch.setattr(ctypes.util, "find_library", nothing)
    monkeypatch.setenv(loader.LIBRARY_ENV, path)

    module = fresh_import()

    assert module.fluidsynth.lib == path
    assert ctypes.util.find_library is nothing  # restored after the import


def test_without_env_it_is_a_plain_import(monkeypatch, fresh_import):
    monkeypatch.delenv(loader.LIBRARY_ENV, raising=False)
    module = fresh_import()
    assert module.fluidsynth.lib == ctypes.util.find_library("fluidsynth")


def test_missing_env_path_falls_back_to_plain_import(monkeypatch, fresh_import, caplog):
    monkeypatch.setenv(loader.LIBRARY_ENV, "/nonexistent/libfluidsynth.so.3")
    module = fresh_import()
    assert module.fluidsynth.lib == ctypes.util.find_library("fluidsynth")
    assert "missing file" in caplog.text
