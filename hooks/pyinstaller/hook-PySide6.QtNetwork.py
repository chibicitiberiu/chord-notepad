"""PyInstaller build hook for PySide6.QtNetwork (overrides PyInstaller's own).

QtQml links QtNetwork, so the library comes along, but the app makes no
network connections of its own: no TLS or network-information plugins
(packaging/qt_bundle.py) and so no OpenSSL.
"""

import os
import sys

from PyInstaller.utils.hooks.qt import add_qt6_dependencies

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, os.pardir, "packaging"))
import qt_bundle  # noqa: E402

hiddenimports, binaries, datas = add_qt6_dependencies(__file__)
binaries = qt_bundle.filter_toc(binaries)
datas = qt_bundle.filter_toc(datas)
