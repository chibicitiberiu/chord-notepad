"""The GPU fallback: software rendering by config, environment or necessity (C3)."""

import sys

import pytest

from tests.conftest import QT_PROBLEM

if QT_PROBLEM:
    pytest.skip(f"Qt not available: {QT_PROBLEM}", allow_module_level=True)

from PySide6.QtQuick import QQuickWindow, QSGRendererInterface  # noqa: E402

from chordnotepad_desktop import rendering  # noqa: E402
from chordnotepad_desktop.main import parse_args  # noqa: E402
from chordnotepad_desktop.rendering import (  # noqa: E402
    SOFTWARE_ENV, choose_renderer, relaunch_command, software_reason, watch_scene_graph,
)

SOFTWARE = QSGRendererInterface.GraphicsApi.Software


class FakeWindowApi:
    """Stands in for QQuickWindow's static renderer settings."""

    def __init__(self, api=QSGRendererInterface.GraphicsApi.OpenGL):
        self.api = api
        self.set_to = []

    def graphicsApi(self):  # noqa: N802 (Qt)
        return self.api

    def setGraphicsApi(self, api):  # noqa: N802 (Qt)
        self.set_to.append(api)
        self.api = api


class FakeApp:
    def __init__(self, platform="xcb"):
        self.platform = platform
        self.exits = []

    def platformName(self):  # noqa: N802 (Qt)
        return self.platform

    def exit(self, code):
        self.exits.append(code)


@pytest.fixture
def window_api(monkeypatch):
    fake = FakeWindowApi()
    monkeypatch.setattr(rendering, "QQuickWindow", fake)
    return fake


def test_what_asks_for_software_rendering():
    assert software_reason(False, {}) is None
    assert software_reason(False, {"QT_QUICK_BACKEND": "software"}) == "QT_QUICK_BACKEND=software"
    assert software_reason(False, {SOFTWARE_ENV: "1"}) == f"{SOFTWARE_ENV}=1"
    assert software_reason(False, {SOFTWARE_ENV: "0"}) is None
    assert software_reason(True, {}) == "--software-rendering"
    assert parse_args(["--software-rendering"])[0].software_rendering
    assert not parse_args([])[0].software_rendering


def test_the_flag_or_our_variable_switch_to_software(window_api):
    assert choose_renderer(FakeApp(), flag=True, environ={}, probe=lambda: True) == "software"
    assert window_api.set_to == [SOFTWARE]
    assert choose_renderer(FakeApp(), environ={SOFTWARE_ENV: "yes"}, probe=lambda: True) == "software"


def test_qts_own_variable_is_left_to_qt(window_api):
    assert choose_renderer(FakeApp(), environ={"QT_QUICK_BACKEND": "software"}) == "software"
    assert window_api.set_to == []


def test_without_opengl_on_linux_it_falls_back(window_api):
    assert choose_renderer(FakeApp("wayland"), environ={}, probe=lambda: False,
                           platform="linux") == "software"
    assert window_api.set_to == [SOFTWARE]


def test_with_opengl_it_uses_the_gpu(window_api):
    assert choose_renderer(FakeApp("xcb"), environ={}, probe=lambda: True, platform="linux") == "gpu"
    assert window_api.set_to == []


def test_nothing_is_probed_where_it_isnt_opengl_or_there_is_no_gpu(window_api):
    def probe():
        raise AssertionError("probed")

    assert choose_renderer(FakeApp("windows"), environ={}, probe=probe, platform="win32") == "gpu"
    assert choose_renderer(FakeApp("cocoa"), environ={}, probe=probe, platform="darwin") == "gpu"
    assert choose_renderer(FakeApp("offscreen"), environ={}, probe=probe, platform="linux") == "gpu"


def test_the_opengl_probe_answers(qapp):
    assert rendering.opengl_works() in (True, False)


def test_a_scene_graph_failure_relaunches_in_software_and_quits(qapp, monkeypatch):
    monkeypatch.setattr(rendering, "QQuickWindow", FakeWindowApi())
    window = QQuickWindow()
    app = FakeApp()
    relaunched = []
    watch_scene_graph(window, app, relaunch=lambda: relaunched.append(True) or True)
    window.sceneGraphError.emit(QQuickWindow.SceneGraphError.ContextNotAvailable, "no OpenGL")
    assert relaunched == [True] and app.exits == [0]
    window.deleteLater()


def test_a_failed_relaunch_exits_with_an_error(qapp, monkeypatch):
    monkeypatch.setattr(rendering, "QQuickWindow", FakeWindowApi())
    window = QQuickWindow()
    app = FakeApp()
    watch_scene_graph(window, app, relaunch=lambda: False)
    window.sceneGraphError.emit(QQuickWindow.SceneGraphError.ContextNotAvailable, "no OpenGL")
    assert app.exits == [1]
    window.deleteLater()


def test_a_failure_in_software_has_nothing_left_to_try(qapp, monkeypatch):
    monkeypatch.setattr(rendering, "QQuickWindow", FakeWindowApi(SOFTWARE))
    window = QQuickWindow()
    app = FakeApp()
    relaunched = []
    watch_scene_graph(window, app, relaunch=lambda: relaunched.append(True) or True)
    window.sceneGraphError.emit(QQuickWindow.SceneGraphError.ContextNotAvailable, "?")
    assert relaunched == [] and app.exits == [1]
    window.deleteLater()


def test_the_relaunch_command(monkeypatch):
    monkeypatch.setattr(sys, "orig_argv", ["python3", "-m", "chordnotepad_desktop", "--smoke"])
    assert relaunch_command() == [sys.executable, "-m", "chordnotepad_desktop", "--smoke"]
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "argv", ["/opt/ChordNotepad/ChordNotepad", "--smoke"])
    assert relaunch_command() == [sys.executable, "--smoke"]


def test_the_relaunch_sets_the_variable_for_the_new_process(monkeypatch):
    started = []
    monkeypatch.delenv(SOFTWARE_ENV, raising=False)
    monkeypatch.setattr(rendering.QProcess, "startDetached",
                        staticmethod(lambda program, args: started.append(
                            (program, args, rendering.os.environ.get(SOFTWARE_ENV))) or (True, 1)))
    monkeypatch.setattr(rendering, "relaunch_command", lambda: ["/usr/bin/python3", "-m", "x"])
    assert rendering.relaunch_with_software() is True
    assert started == [("/usr/bin/python3", ["-m", "x"], "1")]
