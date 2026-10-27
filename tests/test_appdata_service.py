"""Tests for AppDataService directory resolution."""

import sys
from pathlib import Path

import pytest

from services.appdata_service import AppDataService

linux_only = pytest.mark.skipif(
    sys.platform in ("win32", "darwin"), reason="XDG paths apply on Linux only"
)


@linux_only
def test_xdg_variables_are_honoured(monkeypatch, tmp_path):
    # Flatpak points these at ~/.var/app/<id>/...; the home folder itself is
    # not writable from the sandbox.
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    service = AppDataService()
    assert service.get_config_dir() == tmp_path / "config" / "chord-notepad"
    assert service.get_app_data_dir() == tmp_path / "data" / "chord-notepad"
    assert service.get_logs_dir() == tmp_path / "data" / "chord-notepad" / "logs"


@linux_only
@pytest.mark.parametrize("value", ["", "relative/path"])
def test_unset_or_relative_xdg_falls_back_to_home(monkeypatch, value):
    monkeypatch.setenv("XDG_CONFIG_HOME", value)
    monkeypatch.setenv("XDG_DATA_HOME", value)
    service = AppDataService()
    assert service.get_config_dir() == Path.home() / ".config" / "chord-notepad"
    assert service.get_app_data_dir() == Path.home() / ".local" / "share" / "chord-notepad"
