"""Which parts of the PySide6 wheel the desktop builds ship.

The wheel (PySide6-Essentials) carries all of Qt's essential modules, their
tools and every QML module, some of them GPL-only (Qt Designer, Lottie,
Wayland Compositor, Virtual Keyboard, Quick Timeline, Labs StyleKit and
others). The Qt window needs a small part of it, and only LGPL parts. The
lists below are allow-lists, so a module a later Qt adds stays out until
someone looks at it and its licence:

* :data:`QT_LIBRARIES`: the Qt libraries (``libQt6Core.so.6``,
  ``Qt6Core.dll``, ``QtCore.framework``) by module name;
* :data:`BINDINGS`: PySide6's extension modules for them;
* :data:`PLUGINS`: Qt plugins by type;
* :data:`QML_MODULES`: QML module folders under ``qml/``.

Used by the PyInstaller hooks in hooks/pyinstaller (hook-PySide6.*.py), the
spec's check of what PyInstaller collected, and :func:`trim` for the Flatpak
and the snap, which pip-install the wheel. A new QML import or plugin in the
Qt window means a line here; ``--ui qt --smoke`` in every package fails
until it is there.

Stdlib only: the Flatpak and snap builds run it with their own Python.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path, PurePosixPath
from typing import Iterable, Optional

#: Qt modules, as in their library names (Qt6<name>, libQt6<name>, Qt<name>.framework).
QT_LIBRARIES = frozenset({
    "Core", "Gui", "DBus", "Network", "OpenGL", "Svg",
    "Qml", "QmlMeta", "QmlModels", "QmlWorkerScript",
    "Quick", "QuickLayouts", "QuickTemplates2",
    "QuickControls2", "QuickControls2Impl", "QuickControls2Basic", "QuickControls2BasicStyleImpl",
    # QtQuick.Dialogs (the Settings window's Browse; F3's file dialogs) and
    # the folder model its non-native file dialog lists folders with.
    "QuickDialogs2", "QuickDialogs2QuickImpl", "QuickDialogs2Utils", "LabsFolderListModel",
    # Linux only: the X11 and Wayland platform plugins' libraries.
    "XcbQpa", "WaylandClient",
})

#: PySide6 extension modules: what the Qt window imports, plus the ones
#: PyInstaller adds because those link them.
BINDINGS = frozenset({
    "QtCore", "QtGui", "QtQml", "QtQuick", "QtQuickControls2", "QtSvg",
    "QtNetwork", "QtOpenGL", "QtDBus",
})

#: Plugin type -> plugin names (file names without lib prefix and extension).
PLUGINS = {
    "platforms": {"qxcb", "qwayland", "qwindows", "qcocoa", "qoffscreen", "qminimal"},
    # Compose keys and IBus (fcitx5 and others speak IBus' protocol too).
    "platforminputcontexts": {"composeplatforminputcontextplugin", "ibusplatforminputcontextplugin"},
    "xcbglintegrations": {"qxcb-egl-integration", "qxcb-glx-integration"},
    "wayland-decoration-client": {"adwaita", "bradient"},
    "wayland-graphics-integration-client": {"qt-plugin-wayland-egl", "dmabuf-server", "drm-egl-server",
                                            "shm-emulation-server", "vulkan-server"},
    "wayland-shell-integration": {"xdg-shell"},
    "imageformats": {"qsvg", "qico"},
    "iconengines": {"qsvgicon"},
    # The file chooser and colour scheme through the desktop portal.
    "platformthemes": {"qxdgdesktopportal"},
}

#: QML module folders (relative to qml/), each without its subfolders unless
#: listed too; "" is qml/ itself (builtins.qmltypes, jsroot.qmltypes).
QML_MODULES = frozenset({
    "",
    "QtQml", "QtQml/Models", "QtQml/WorkerScript",
    "QtQuick", "QtQuick/Window", "QtQuick/Layouts", "QtQuick/Templates",
    "QtQuick/Controls", "QtQuick/Controls/impl", "QtQuick/Controls/Basic", "QtQuick/Controls/Basic/impl",
    # FileDialog: the module, its Qt Quick implementation (the Basic look,
    # without the other styles' +Fusion etc. folders) and the folder model.
    "QtQuick/Dialogs", "QtQuick/Dialogs/quickimpl", "QtQuick/Dialogs/quickimpl/qml",
    "Qt/labs/folderlistmodel",
})

_LIBRARY = re.compile(r"^(?:lib)?Qt6?(?P<name>[A-Za-z0-9]+?)(?:\.so(?:\.[0-9.]+)?|\.dll|\.dylib|\.framework(?:/.*)?)$")
_BINDING = re.compile(r"^(?P<name>Qt[A-Za-z0-9]+)\.(?:abi3\.so|pyd|abi3\.pyd|so)$")
_PLUGIN = re.compile(r"^(?:lib)?(?P<name>.+?)\.(?:so|dll|dylib)$")


def _parts(path: str) -> Optional[tuple]:
    """``path`` below the PySide6 folder, without the ``Qt/`` level (Linux, macOS), or None."""
    parts = PurePosixPath(path.replace("\\", "/")).parts
    if not parts or parts[0] != "PySide6":
        return None
    parts = parts[1:]
    if parts[:1] == ("Qt",):
        parts = parts[1:]
    return parts


def wanted(path: str) -> Optional[bool]:
    """Whether a bundle path inside PySide6/ is shipped.

    True or False for the Qt parts the lists above decide (libraries,
    bindings, plugins, QML modules, translations, the Windows software
    OpenGL); None for everything else (PySide6's own Python files and
    libraries, the C++ runtime), which the caller decides.
    """
    parts = _parts(path)
    if parts is None or not parts:
        return None
    if parts[0] == "translations":
        return False  # the window is English only
    if parts[0] == "plugins" and len(parts) >= 3:
        kind = "/".join(parts[1:-1])
        match = _PLUGIN.match(parts[-1])
        return bool(match) and match.group("name") in PLUGINS.get(kind, ())
    if parts[0] == "qml" and len(parts) >= 2:
        folder = "/".join(parts[1:-1])
        return folder in QML_MODULES
    if parts[0] == "lib" and len(parts) >= 2:
        # libQt6Core.so.6 (Linux), QtCore.framework/... (macOS), libicu*.so.73 (Linux, needed by QtCore)
        if parts[1].startswith("libicu"):
            return True
        match = _LIBRARY.match("/".join(parts[1:]) if parts[1].endswith(".framework") else parts[1])
        if match:
            return match.group("name") in QT_LIBRARIES
        return None
    if len(parts) == 1:
        name = parts[0]
        if name.lower() == "opengl32sw.dll":
            return False  # Mesa's software OpenGL: the fallback is Qt Quick's own software renderer
        match = _LIBRARY.match(name)
        if match and name.lower().startswith("qt6"):
            return match.group("name") in QT_LIBRARIES
        match = _BINDING.match(name)
        if match:
            return match.group("name") in BINDINGS
    return None


def is_qt_code(path: str) -> bool:
    """Whether a bundle path is a Qt library or a PySide6 binding (wanted or not).

    Those are linked or imported by other code, so leaving one out breaks
    the app; plugins and QML modules are loaded by name and can go.
    """
    parts = _parts(path)
    if not parts:
        return False
    if parts[0] == "lib" and len(parts) >= 2:
        name = "/".join(parts[1:]) if parts[1].endswith(".framework") else parts[1]
        return bool(_LIBRARY.match(name)) and not parts[1].startswith("libicu")
    if len(parts) == 1:
        name = parts[0]
        return bool(_BINDING.match(name)) or (name.lower().startswith("qt6") and bool(_LIBRARY.match(name)))
    return False


def filter_toc(entries: Iterable[tuple]) -> list:
    """Hook results ``(source, destination folder)`` without the unwanted Qt parts."""
    kept = []
    for src, dest_dir in entries:
        dest = f"{dest_dir}/{os.path.basename(src)}".replace("\\", "/")
        if wanted(dest) is not False:
            kept.append((src, dest_dir))
    return kept


# --- Trimming a pip-installed wheel (the Flatpak and the snap) ---------------

#: Folders of the wheels that only matter for building against Qt or for its tools.
DEV_FOLDERS = ("include", "typesystems", "glue", "scripts", "doc", "lib/cmake",
               "Qt/libexec", "Qt/metatypes", "Qt/lib/cmake", "Qt/lib/metatypes", "Qt/mkspecs")


def trim(site_packages: Path) -> list:
    """Delete what the Qt window doesn't use from PySide6/ and shiboken6/.

    Returns the deleted paths (relative to ``site_packages``). Also drops the
    tools (designer, qmllint and the like: executables at the top of
    PySide6/) and the type stubs.
    """
    site_packages = Path(site_packages)
    removed = []

    def remove(path: Path) -> None:
        removed.append(path.relative_to(site_packages).as_posix())
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()

    for package in ("PySide6", "shiboken6"):
        root = site_packages / package
        if not root.is_dir():
            continue
        for folder in DEV_FOLDERS:
            if (root / folder).exists():
                remove(root / folder)
        for path in sorted(root.rglob("*")):
            if path.is_dir() and not path.is_symlink():
                continue
            rel = path.relative_to(site_packages).as_posix()
            top_level_tool = (path.parent == root and not path.suffix and os.access(path, os.X_OK))
            if path.suffix == ".pyi" or top_level_tool or wanted(rel) is False:
                remove(path)
        # Folders emptied above (deepest first).
        for path in sorted((p for p in root.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
            if not any(path.iterdir()):
                remove(path)
    return removed


def main(argv: list) -> int:
    """``qt_bundle.py trim <site-packages>``: trim an installed wheel and say how much went."""
    if len(argv) != 3 or argv[1] != "trim":
        print("usage: qt_bundle.py trim <site-packages>", file=sys.stderr)
        return 2
    site = Path(argv[2])
    if not (site / "PySide6").is_dir():
        print(f"no PySide6 in {site}", file=sys.stderr)
        return 1
    removed = trim(site)
    print(f"qt_bundle: removed {len(removed)} paths from {site}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
