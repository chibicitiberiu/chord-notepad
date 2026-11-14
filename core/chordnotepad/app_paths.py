"""Where the app's own files are: VERSION, resources, the built help.

The core never works these out itself. Each front end knows how it ships
and builds an :class:`AppPaths` at its entry point:

* the desktop: ``chordnotepad_tk.desktop_paths.resolve_desktop_paths`` (a
  checkout, a PyInstaller bundle, the Flatpak or the snap);
* Android: ``chordnotepad_android.host`` (the SoundFont Kotlin copied to
  ``filesDir``, the native library folder).

It then passes it to ``session.bootstrap.build_core_services``. A module
that walked up from its own ``__file__`` instead would find nothing, without
an error, once the code moves to another folder
(tests/test_app_paths.py guards against that).

Stdlib only.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

#: What :meth:`AppPaths.read_version` returns when there is no VERSION file.
UNKNOWN_VERSION = "0.0"


@dataclass(frozen=True)
class AppPaths:
    """The folders and files the app ships, as the front end found them.

    A field is None when this front end doesn't ship that file (Android has
    no VERSION file and no ``resources/`` folder, for example).

    Attributes:
        root: The folder the app's files sit in: the checkout, the
            PyInstaller bundle or the install prefix.
        version_file: The ``VERSION`` file (one line, e.g. ``0.5.4``).
        resources: ``resources/``: icons, the SoundFont, licences, Quick
            Start images.
        help_html: The built help (``help/build/html``).
        soundfont: The bundled SoundFont, used when Settings names none.
        dev_dll_dir: ``.tools/bin`` in a Windows checkout: the FluidSynth DLLs
            for running from source. None in a bundle.
        native_lib_dir: Android's ``nativeLibraryDir`` (only logged:
            FluidSynth is loaded by soname).
    """

    root: Optional[Path] = None
    version_file: Optional[Path] = None
    resources: Optional[Path] = None
    help_html: Optional[Path] = None
    soundfont: Optional[Path] = None
    dev_dll_dir: Optional[Path] = None
    native_lib_dir: Optional[Path] = None

    @property
    def licenses(self) -> Optional[Path]:
        """``resources/licenses``: the data of Help > Open Source Licences."""
        return self.resources / "licenses" if self.resources is not None else None

    @property
    def quickstart(self) -> Optional[Path]:
        """``resources/quickstart``: the Quick Start images."""
        return self.resources / "quickstart" if self.resources is not None else None

    def read_version(self) -> str:
        """The VERSION file's contents, or ``"0.0"`` if there is none."""
        if self.version_file is None:
            return UNKNOWN_VERSION
        try:
            return self.version_file.read_text(encoding="utf-8").strip()
        except OSError:
            return UNKNOWN_VERSION


#: No bundled files at all: the default for tests and tools that build the
#: core with their own player. A front end always passes the paths it
#: resolved (tests/test_app_paths.py checks both entry points do).
NO_BUNDLED_FILES = AppPaths()
