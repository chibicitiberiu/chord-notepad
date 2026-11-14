"""Which renderer Qt Quick uses: the GPU, or software when the GPU can't.

Qt Quick draws through the RHI (OpenGL on Linux, Direct3D 11 on Windows,
Metal on macOS). Where that can't start (a VM or remote desktop without
OpenGL, a broken driver, a sandbox missing the GL libraries) the window
would stay black or Qt would exit. The fallback is Qt Quick's software
renderer, which everything in this front end supports (no MultiEffect,
pitfall 15).

Software rendering is chosen, before the first window, when:

* ``QT_QUICK_BACKEND=software`` is set (Qt's own switch; Qt does the rest),
* :data:`SOFTWARE_ENV` is set to ``1`` (ours, e.g. in a launcher), or
  ``--software-rendering`` is on the command line,
* on Linux, an OpenGL context can't be created (:func:`opengl_works`).

And automatically when the RHI fails anyway: :func:`watch_scene_graph`
handles the window's ``sceneGraphError`` (connecting to it also stops Qt
from exiting on its own) by starting the app again with :data:`SOFTWARE_ENV`
set, then quitting this one. The new process can't loop: software rendering
doesn't fail that way.
"""

import logging
import os
import sys
from typing import Callable, List, Mapping, Optional

from PySide6.QtCore import QProcess
from PySide6.QtGui import QGuiApplication, QOffscreenSurface, QOpenGLContext
from PySide6.QtQuick import QQuickWindow, QSGRendererInterface

logger = logging.getLogger(__name__)

#: Set to 1 for software rendering (the relaunch sets it too).
SOFTWARE_ENV = "CHORD_NOTEPAD_SOFTWARE_RENDERING"
#: Qt Quick's own backend switch.
QT_BACKEND_ENV = "QT_QUICK_BACKEND"
#: The command-line switch.
SOFTWARE_FLAG = "--software-rendering"
#: Platform plugins that never draw on a GPU, so there is nothing to probe.
_NO_GPU_PLATFORMS = frozenset({"offscreen", "minimal", "vnc"})


def _is_on(value: Optional[str]) -> bool:
    return (value or "").strip().lower() in ("1", "true", "yes", "on")


def software_reason(flag: bool, environ: Mapping[str, str]) -> Optional[str]:
    """Why software rendering was asked for, or None if it wasn't."""
    if environ.get(QT_BACKEND_ENV, "").strip().lower() == "software":
        return f"{QT_BACKEND_ENV}=software"
    if _is_on(environ.get(SOFTWARE_ENV)):
        return f"{SOFTWARE_ENV}={environ.get(SOFTWARE_ENV)}"
    if flag:
        return SOFTWARE_FLAG
    return None


def opengl_works() -> bool:
    """Whether an OpenGL context can be created and made current offscreen."""
    surface = QOffscreenSurface()
    surface.create()
    context = QOpenGLContext()
    try:
        if not context.create():
            return False
        if not context.makeCurrent(surface):
            return False
        context.doneCurrent()
        return True
    finally:
        surface.destroy()


def choose_renderer(app: QGuiApplication, *, flag: bool = False,
                    environ: Optional[Mapping[str, str]] = None,
                    probe: Callable[[], bool] = opengl_works,
                    platform: str = sys.platform) -> str:
    """Pick software or GPU rendering; call before the first window exists.

    Returns:
        ``"software"`` or ``"gpu"``.
    """
    environ = os.environ if environ is None else environ
    reason = software_reason(flag, environ)
    if reason is None and platform.startswith("linux") \
            and app.platformName() not in _NO_GPU_PLATFORMS and not probe():
        reason = "OpenGL isn't available"
    if reason is None:
        logger.info("Rendering with the GPU (%s)", QQuickWindow.graphicsApi().name)
        return "gpu"
    if not reason.startswith(QT_BACKEND_ENV):
        # (Qt applies its own variable itself, when the scene graph starts.)
        QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.Software)
    logger.info("Rendering in software (%s)", reason)
    return "software"


def relaunch_command(argv: Optional[List[str]] = None) -> List[str]:
    """The command line that starts this app again (program first)."""
    if getattr(sys, "frozen", False):
        return [sys.executable, *(sys.argv[1:] if argv is None else argv)]
    # sys.orig_argv keeps "-m chordnotepad_tk.main" (sys.argv has the file).
    original = list(getattr(sys, "orig_argv", [])) or [sys.executable, *sys.argv]
    return [sys.executable, *original[1:]]


def relaunch_with_software() -> bool:
    """Start this app again with software rendering (detached)."""
    command = relaunch_command()
    os.environ[SOFTWARE_ENV] = "1"
    started = QProcess.startDetached(command[0], command[1:])
    started = started[0] if isinstance(started, tuple) else bool(started)
    logger.warning("Restarting with software rendering: %s (%s)", command,
                   "started" if started else "failed")
    return started


def watch_scene_graph(window: QQuickWindow, app: QGuiApplication,
                      relaunch: Callable[[], bool] = relaunch_with_software) -> None:
    """Handle the window's scene-graph failure: relaunch in software, quit."""
    def failed(error, message: str) -> None:
        logger.error("The scene graph failed (%s): %s", error, message)
        if QQuickWindow.graphicsApi() == QSGRendererInterface.GraphicsApi.Software:
            # Nothing left to fall back to.
            app.exit(1)
            return
        app.exit(0 if relaunch() else 1)

    window.sceneGraphError.connect(failed)
