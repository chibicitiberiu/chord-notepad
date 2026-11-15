# Contributing to Chord Notepad

Thanks for helping. Bug reports, fixes, translations of the help and new
features are all welcome. For anything bigger than a small fix, open an issue
first so we can agree on the approach before you spend time on it.

## Licence of your contribution

Chord Notepad is licensed under the [GNU AGPL-3.0](LICENSE) together with the
additional permissions and terms in [ADDITIONAL-TERMS.txt](ADDITIONAL-TERMS.txt).
They let the app use app stores' purchase libraries and be distributed through
app stores, and they keep the "Chord Notepad" name for the original project.
The logo and store material are covered separately by
[ARTWORK-TERMS.txt](ARTWORK-TERMS.txt).

By submitting a contribution (a pull request, a patch or code in an issue),
you agree that:

- code anywhere in the repository, including `help/conf.py`, `help/_ext/`
  and `help/_static/`, is licensed under the GNU AGPL-3.0 together with the
  additional permissions and terms in ADDITIONAL-TERMS.txt;
- text and images in the user guide (`help/`) and the developer docs
  (`docs/`) are licensed under
  [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/), and code
  samples in `docs/` under both licences;
- your contribution may be distributed together with the logo and store
  material under [ARTWORK-TERMS.txt](ARTWORK-TERMS.txt), including in builds
  that embed them; they aren't part of the Corresponding Source; and
- you wrote it, or otherwise have the right to submit it under those terms.

The logo and store material aren't open for contributions; please don't send
changes to them.

You keep the copyright in your contribution. You don't need to sign anything.
Signing off your commits (`git commit -s`) is welcome but not required.

If your contribution includes code from somewhere else, say where it came from
and what licence it's under, so it can be checked and credited.

## Before you send a pull request

- Run the tests: `make test`. If you changed how chords are read, transposed
  or converted, also run `make fuzz` (the long fuzz and exhaustive tests,
  about 10 minutes; they don't run in CI).
- The Qt front end's tests (`tests/qt/`) run offscreen on Qt's software
  renderer and need no display; they skip when PySide6 or pytest-qt can't be
  imported. A QML warning fails the test. If you touched QML, also run
  `qmllint` on it (it ships with PySide6).
- The Tk tests need a display and skip without one. CI runs the suite under
  `xvfb-run`; on a headless machine, start an Xvfb (`Xvfb :97 -screen 0
  1280x800x24 &`) and run with `DISPLAY=:97`. They go when the Tk window does.
- Add or update tests for what you changed.
- If you changed what users see, update the user guide in `help/`
  (see [docs/HELP_AUTHORING.md](docs/HELP_AUTHORING.md)) and check that
  `make docs-check` passes. If a desktop window changed, redo its screenshots
  with `packaging/tools/qt_help_screenshots.py`.
- Follow the conventions below. The architecture is described in
  [docs/architecture/session.md](docs/architecture/session.md), and the
  Android app in [docs/ANDROID.md](docs/ANDROID.md).

## Conventions

- Python naming: classes `PascalCase`, functions `snake_case`, constants
  `UPPER_SNAKE_CASE`, private names with a leading underscore.
- Public functions have type hints and docstrings.
- One `logger = logging.getLogger(__name__)` per module.
- Python packages, imported by name, nothing installed: the shared core
  `chordnotepad` (`core/chordnotepad/`), the Qt Quick desktop app
  `chordnotepad_desktop` (`desktop/chordnotepad_desktop/`) and the old Tk
  desktop app `chordnotepad_tk` (`desktop/chordnotepad_tk/`, which stays for
  one release as `--ui tk` and is then deleted; don't add features to it).
  Imports are absolute (`from chordnotepad.session.state import ...`). The
  core never imports tkinter, Pillow, jeepney or PySide6
  (`tests/test_core_import_guard.py`); desktop-only code goes in
  `chordnotepad_desktop`.
- Logic lives in the shared Python core. The front ends (Qt, and the Android
  Kotlin/Compose app) stay thin: app flows and cross-view wiring belong in
  `core/chordnotepad/session/`, not in `desktop/chordnotepad_desktop/`,
  QML or Kotlin.
- Don't change the editor's text typography or colours (font, text colours,
  chord highlighting). The chrome around it is fair game.
- Errors use the exceptions in `core/chordnotepad/exceptions.py`.

## Running and testing the desktop app

You need Python 3.14 and `pipenv install --dev` (PySide6 and pytest-qt come
with it). Nothing is installed, so the folders go on `PYTHONPATH`. Don't run a
bare `make`: its default target starts the app.

```bash
# The Qt window (it becomes the default in 0.6.0); --ui tk is the old Tk one.
PYTHONPATH=core:desktop pipenv run python -m chordnotepad_tk.main --ui qt

# The Qt tests, offscreen (no display needed)
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software pipenv run python -m pytest tests/qt -q

# Everything
pipenv run python -m pytest tests/ -q
```

The Qt front end lives in `desktop/chordnotepad_desktop/`: Python models that
wrap the session (`session_store.py` is the bridge to QML) and the QML in
`qml/` (`app/` for the window, `CNStyle/` for the controls, `CNTheme/` for the
tokens). QML only shows what the session publishes and sends commands, as the
Android UI does. The architecture is in
[docs/architecture/session.md](docs/architecture/session.md). To try the
window without touching your own settings, point `XDG_CONFIG_HOME`,
`XDG_DATA_HOME` and `XDG_CACHE_HOME` at an empty folder.

`packaging/tools/qt_help_screenshots.py` starts the whole window offscreen with
a throwaway profile and makes the desktop guide's screenshots (see
[docs/HELP_AUTHORING.md](docs/HELP_AUTHORING.md)).
