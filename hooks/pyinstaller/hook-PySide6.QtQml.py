"""PyInstaller build hook for PySide6.QtQml (overrides PyInstaller's own).

PyInstaller's hook collects every QML module of the wheel, GPL-only ones
included (Wayland Compositor, Lottie, Virtual Keyboard, Quick Timeline).
This one collects the folders packaging/qt_bundle.py lists and leaves out
the QML debugging plugins.
"""

import os
import sys

from PyInstaller.utils.hooks.qt import add_qt6_dependencies, pyside6_library_info

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, os.pardir, "packaging"))
import qt_bundle  # noqa: E402

hiddenimports, binaries, datas = add_qt6_dependencies(__file__)
qml_binaries, qml_datas = pyside6_library_info.collect_qtqml_files()
binaries = qt_bundle.filter_toc(binaries + qml_binaries)
datas = qt_bundle.filter_toc(datas + qml_datas)
