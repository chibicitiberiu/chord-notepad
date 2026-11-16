"""Let Qt's plugins find the Qt DLLs beside them on Windows, also in the MSIX.

The Qt DLLs live in ``PySide6\\`` (``_internal\\PySide6\\`` in a build) and a
QML plugin such as ``qml\\QtQuick\\Controls\\Basic\\qtquickcontrols2basicstyleplugin.dll``
needs some that nothing has loaded yet (``Qt6QuickControls2Basic.dll``). Qt
loads plugins with a plain ``LoadLibrary``. Outside a package that search
includes PATH and PyInstaller's ``SetDllDirectory`` folder; inside an MSIX it
doesn't (packaged apps search the package root, the exe's folder and
System32), so the plugin failed with "The specified module could not be
found" and the window never loaded. Python's own extension modules were fine:
they load with explicit ``LOAD_LIBRARY_SEARCH_*`` flags.

:func:`use_bundled_dll_dirs` makes those flags the process default
(``SetDefaultDllDirectories``) and adds the bundle's folders with
``os.add_dll_directory``, so every later ``LoadLibrary`` searches the exe's
folder, those folders and System32, inside a package or not.
"""

import importlib.util
import logging
import os
import sys
from pathlib import Path
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

#: LOAD_LIBRARY_SEARCH_DEFAULT_DIRS: the exe's folder, AddDllDirectory folders, System32.
LOAD_LIBRARY_SEARCH_DEFAULT_DIRS = 0x00001000

#: The os.add_dll_directory handles, kept so the folders stay added.
_ADDED: List[Any] = []


def dll_dirs() -> List[Path]:
    """The folders the bundled DLLs are in: the bundle's root and PySide6's."""
    dirs: List[Path] = []
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        dirs.append(Path(bundle))
    spec = importlib.util.find_spec("PySide6")
    if spec is not None and spec.submodule_search_locations:
        dirs.append(Path(list(spec.submodule_search_locations)[0]))
    shiboken = importlib.util.find_spec("shiboken6")
    if shiboken is not None and shiboken.submodule_search_locations:
        dirs.append(Path(list(shiboken.submodule_search_locations)[0]))
    return [d for d in dirs if d.is_dir()]


def use_bundled_dll_dirs(platform: str = sys.platform, kernel32: Optional[Any] = None,
                         add_dll_directory: Optional[Any] = None) -> bool:
    """On Windows, make the default DLL search include the bundle's folders.

    Args:
        platform: ``sys.platform`` (a parameter for the tests).
        kernel32: ``ctypes.windll.kernel32`` (a stand-in in the tests).
        add_dll_directory: ``os.add_dll_directory`` (a stand-in in the tests).

    Returns:
        True when the default was changed; False elsewhere or when it failed
        (logged: the app still tries to start).
    """
    if platform != "win32":
        return False
    try:
        if kernel32 is None:
            import ctypes
            kernel32 = ctypes.windll.kernel32
        add = add_dll_directory or os.add_dll_directory
        for folder in dll_dirs():
            _ADDED.append(add(str(folder)))
        if not kernel32.SetDefaultDllDirectories(LOAD_LIBRARY_SEARCH_DEFAULT_DIRS):
            logger.warning("SetDefaultDllDirectories failed; Qt plugins may not load")
            return False
    except (AttributeError, OSError):
        logger.warning("Couldn't set the DLL search folders", exc_info=True)
        return False
    return True
