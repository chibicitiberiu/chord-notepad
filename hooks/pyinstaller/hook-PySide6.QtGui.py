"""PyInstaller build hook for PySide6.QtGui (overrides PyInstaller's own).

The same collection, keeping only the plugins packaging/qt_bundle.py lists:
the plugins left out (GTK platform theme, virtual keyboard, EGLFS, ...) are
never analysed, so the libraries they would pull in stay out too.
"""

import os
import sys

from PyInstaller.utils.hooks.qt import add_qt6_dependencies

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, os.pardir, "packaging"))
import qt_bundle  # noqa: E402

hiddenimports, binaries, datas = add_qt6_dependencies(__file__)
binaries = qt_bundle.filter_toc(binaries)
datas = qt_bundle.filter_toc(datas)
