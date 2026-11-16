"""windows_dlls: the default DLL search on Windows includes the bundle's folders."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "desktop"))

from chordnotepad_desktop import windows_dlls  # noqa: E402


class FakeKernel32:
    def __init__(self, result=1):
        self.calls = []
        self.result = result

    def SetDefaultDllDirectories(self, flags):  # noqa: N802 (Win32 name)
        self.calls.append(flags)
        return self.result


def test_does_nothing_off_windows():
    kernel32 = FakeKernel32()
    assert windows_dlls.use_bundled_dll_dirs("linux", kernel32, lambda p: None) is False
    assert kernel32.calls == []


def test_on_windows_adds_the_bundle_folders_then_sets_the_default(monkeypatch, tmp_path):
    bundle = tmp_path / "_internal"
    bundle.mkdir()
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    added = []
    kernel32 = FakeKernel32()
    assert windows_dlls.use_bundled_dll_dirs("win32", kernel32, added.append) is True
    assert kernel32.calls == [windows_dlls.LOAD_LIBRARY_SEARCH_DEFAULT_DIRS]
    assert added[0] == str(bundle)
    # PySide6's own folder, where the Qt DLLs are.
    assert any(Path(p).name == "PySide6" for p in added)


def test_a_failed_call_is_reported_not_raised(monkeypatch):
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    assert windows_dlls.use_bundled_dll_dirs("win32", FakeKernel32(result=0), lambda p: None) is False
