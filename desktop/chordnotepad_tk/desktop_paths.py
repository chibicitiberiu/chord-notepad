"""Finds the desktop app's files: the one place that knows how it ships.

``main.py`` calls :func:`resolve_desktop_paths` once, before anything else,
and hands the result down (``Application`` -> ``build_core_services``,
``ResourceService``). Every desktop build has the same layout under its
root (``VERSION``, ``resources/``, ``help/build/html``); only the root
differs:

* PyInstaller: ``sys._MEIPASS`` (the spec's ``datas``);
* Flatpak: ``/app/share/chord-notepad`` (the manifest's ``cp`` steps);
* snap: ``$SNAP/share/chord-notepad`` (snapcraft.yaml's ``override-build``);
* running from source: the checkout, two folders above this file's
  package (``desktop/chordnotepad_tk/``).

Stdlib only: ``main.py`` imports it before pyfluidsynth is loaded.
"""

import os
import sys
from pathlib import Path
from typing import Mapping, Optional

from chordnotepad.app_paths import AppPaths

#: The Flatpak app id (``app-id`` in the manifest).
FLATPAK_APP_ID = "io.github.chibicitiberiu.ChordNotepad"
#: The snap's name (``name`` in snap/snapcraft.yaml).
SNAP_NAME = "chord-notepad"
#: Where the Flatpak and the snap install the app, under their prefix.
INSTALL_SUBDIR = Path("share") / "chord-notepad"
#: The Flatpak's install prefix (``FLATPAK_DEST``).
FLATPAK_PREFIX = Path("/app")

#: The checkout: this file is ``<checkout>/desktop/chordnotepad_tk/desktop_paths.py``.
CHECKOUT_ROOT = Path(__file__).resolve().parents[2]

#: The bundled SoundFont, under ``resources/``.
SOUNDFONT = Path("soundfont") / "GeneralUser-GS.sf2"


def paths_under(root: Path, *, dev_dll_dir: bool = False) -> AppPaths:
    """The desktop layout under ``root``.

    Args:
        root: The checkout, the bundle or the install folder.
        dev_dll_dir: Include ``.tools/bin`` (a checkout only).
    """
    resources = root / "resources"
    return AppPaths(
        root=root,
        version_file=root / "VERSION",
        resources=resources,
        help_html=root / "help" / "build" / "html",
        soundfont=resources / SOUNDFONT,
        dev_dll_dir=root / ".tools" / "bin" if dev_dll_dir else None,
    )


def resolve_desktop_paths(*, env: Optional[Mapping[str, str]] = None,
                          meipass: Optional[str] = None,
                          flatpak_prefix: Path = FLATPAK_PREFIX,
                          checkout_root: Path = CHECKOUT_ROOT) -> AppPaths:
    """Where this desktop build's files are.

    Args:
        env: The environment (tests); ``os.environ`` by default.
        meipass: The PyInstaller bundle folder (tests); ``sys._MEIPASS`` by
            default, when frozen.
        flatpak_prefix: The Flatpak's prefix (tests); ``/app`` by default.
        checkout_root: The checkout (tests); this file's checkout by default.
    """
    env = os.environ if env is None else env
    if meipass is None:
        meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return paths_under(Path(meipass))
    if env.get("FLATPAK_ID") == FLATPAK_APP_ID:
        return paths_under(flatpak_prefix / INSTALL_SUBDIR)
    if env.get("SNAP_NAME") == SNAP_NAME and env.get("SNAP"):
        return paths_under(Path(env["SNAP"]) / INSTALL_SUBDIR)
    return paths_under(checkout_root, dev_dll_dir=True)
