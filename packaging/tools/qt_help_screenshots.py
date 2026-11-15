#!/usr/bin/env python3
"""Capture the desktop edition's screenshots from the Qt Quick window.

The desktop user guide, the Quick Start image, the AppStream metainfo and the
store listings use the images this tool makes. Run it again whenever the UI
changes; don't edit the PNGs by hand.

How it works (the Qt counterpart of ``android/tools/help_screenshots.py``):

1. Every shot starts the whole front end, ``QtApplication``, inside this
   process: offscreen, on Qt Quick's software renderer, with a silent
   ``FakePlayer`` (a song can be frozen mid-playback), a throwaway profile
   (settings, logs and files in a temporary folder) and a fixed date. It
   never opens a window on a screen, never touches your own settings and
   never plays a sound. No display or Xvfb is needed.
2. The shot's *scene* sets the state: it loads a song, switches Edit/Play,
   opens a sidebar or the chord sheet, advances the playhead, opens a menu.
3. The window is a fixed size and scale (``--size``, ``--scale``), in the
   light theme unless the shot asks for dark, so a run gives the same
   pixels every time on the same machine.
4. ``window.grabWindow()`` is saved as a palette PNG (optimised) in
   ``help/images/desktop/``, or, for the store shots, in
   ``packaging/store/screenshots/``; numbered callouts are drawn at the
   centres of named QML items.

Usage (from the repository root, nothing needs installing)::

    pipenv run python packaging/tools/qt_help_screenshots.py --list
    pipenv run python packaging/tools/qt_help_screenshots.py            # every shot
    pipenv run python packaging/tools/qt_help_screenshots.py --only main-window,player
    pipenv run python packaging/tools/qt_help_screenshots.py --out /tmp/shots --scale 2

Needs PySide6 and Pillow (with libimagequant for the palette step; it falls
back to plain RGB PNGs without it).
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

REPO = Path(__file__).resolve().parents[2]
SONGS = REPO / "android" / "tools" / "help_shot_songs"
HELP_OUT = REPO / "help" / "images" / "desktop"
STORE_OUT = REPO / "packaging" / "store" / "screenshots" / "desktop"
QUICK_START_OUT = REPO / "resources" / "quickstart"

#: The window's logical size: wide enough for the whole player bar, the rail
#: and a sidebar, small enough to read in the guide at its column width.
DEFAULT_SIZE = (1280, 800)
#: Today, for anything that shows a date (the unsaved-changes dot never does).
TODAY = datetime.date(2026, 11, 15)

#: Callout colours (the Qt window's primary, light theme).
PRIMARY = (0x3F, 0x51, 0xB5)
ON_PRIMARY = (0xFF, 0xFF, 0xFF)
HALO = (0xFF, 0xFF, 0xFF)


def isolate_environment(root: Path) -> None:
    """Throwaway XDG folders, no sound server, no session bus, offscreen Qt.

    Done before Qt or the app is imported, so nothing reads the real ones.
    """
    for name in ("config", "data", "cache", "runtime"):
        (root / name).mkdir(parents=True, exist_ok=True)
    (root / "runtime").chmod(0o700)
    env = {
        "XDG_CONFIG_HOME": str(root / "config"),
        "XDG_DATA_HOME": str(root / "data"),
        "XDG_CACHE_HOME": str(root / "cache"),
        "XDG_RUNTIME_DIR": str(root / "runtime"),
        "HOME": str(root / "home"),
        "PULSE_SERVER": "unix:/nonexistent",
        "PIPEWIRE_REMOTE": "/nonexistent",
        "DBUS_SESSION_BUS_ADDRESS": "unix:path=/nonexistent",
        "QT_QPA_PLATFORM": "offscreen",
        "QT_QUICK_BACKEND": "software",
        "QML_DISABLE_DISK_CACHE": "1",
        "QT_QPA_FONTDIR": str(REPO / "resources" / "fonts"),
    }
    (root / "home").mkdir(exist_ok=True)
    os.environ.update(env)
    os.environ.pop("DISPLAY", None)
    os.environ.pop("WAYLAND_DISPLAY", None)


def soundfont_presets(path: Path) -> List[Tuple[int, str]]:
    """(program, name) of the bank 0 presets of a .sf2 (its ``phdr`` chunk), by program."""
    import struct

    data = path.read_bytes()

    def chunks(offset: int, end: int):
        while offset + 8 <= end:
            size = struct.unpack("<I", data[offset + 4:offset + 8])[0]
            yield data[offset:offset + 4], offset + 8, size
            offset += 8 + size + (size & 1)

    presets = []
    for cid, start, size in chunks(12, len(data)):
        if cid == b"LIST" and data[start:start + 4] == b"pdta":
            for cid2, start2, size2 in chunks(start + 4, start + size):
                if cid2 == b"phdr":
                    for i in range(size2 // 38 - 1):  # the last record is the terminator
                        rec = data[start2 + i * 38:start2 + (i + 1) * 38]
                        program, bank = struct.unpack("<HH", rec[20:24])
                        if bank == 0:
                            presets.append((program, rec[:20].split(b"\0")[0].decode("latin-1")))
    return sorted(presets)


def _walk(item, name: str):
    """The first visual descendant of ``item`` named ``name`` (depth first)."""
    for child in item.childItems():
        if child.objectName() == name:
            return child
        found = _walk(child, name)
        if found is not None:
            return found
    return None


def _walk_text(item, text: str):
    """The first visible descendant whose ``text`` property is ``text``."""
    for child in item.childItems():
        if child.isVisible() and child.property("text") == text:
            return child
        found = _walk_text(child, text)
        if found is not None:
            return found
    return None


# -- shots --------------------------------------------------------------------------------


@dataclass
class Shot:
    """One image: where it goes, which page it is for, and how to set it up."""

    name: str
    page: str
    what: str
    scene: Callable[["Scene"], Optional[object]]
    #: Where the PNG goes: ``help``, ``store`` or ``quickstart``.
    dest: str = "help"
    dark: bool = False
    #: Numbered callouts: (number, objectName[, fx, fy]): the disc sits at
    #: that fraction of the item's rectangle (the middle by default).
    callouts: List[tuple] = field(default_factory=list)
    #: Crop to this item's (or popup's) rectangle (objectName) plus ``pad``
    #: logical px, or to a fixed rectangle (x, y, right, bottom) in logical px.
    crop: Optional[str] = None
    crop_rect: Optional[Tuple[int, int, int, int]] = None
    pad: int = 8
    #: Keep only this much (width, height, logical px) of the crop's top left.
    crop_size: Optional[Tuple[int, int]] = None
    #: Resize the grabbed window (the Settings window) to this logical size.
    size_window: Optional[Tuple[int, int]] = None
    #: The device pixel ratio this image needs (None: the run's ``--scale``).
    scale: Optional[float] = None
    #: Scale the finished image to this size (Lanczos).
    final_size: Optional[Tuple[int, int]] = None
    #: Palette PNG (small); False keeps every colour (the store images).
    quantize: bool = True
    #: A window of its own (objectName under the main window) to grab
    #: instead of the main one (the Settings window, a dialog).
    window: Optional[str] = None
    size: Optional[Tuple[int, int]] = None
    config: Dict[str, object] = field(default_factory=dict)
    #: The scene leaves the pointer where it wants it (a tooltip shot).
    keep_pointer: bool = False


SHOTS: Dict[str, Shot] = {}


def shot(name: str, page: str, what: str, **kw):
    """Register ``fn(scene)`` as the setup of the shot ``name``."""

    def register(fn):
        SHOTS[name] = Shot(name=name, page=page, what=what, scene=fn, **kw)
        return fn

    return register


class Scene:
    """What a shot's setup can do: the running app and a few helpers."""

    def __init__(self, qt, window, app, tmp: Path):
        from PySide6.QtQuick import QQuickItem

        self.qt = qt
        self.window = window
        self.app = app
        self.tmp = tmp
        self._item_type = QQuickItem

    # -- time -----------------------------------------------------------------------
    def wait(self, ms: int = 100) -> None:
        from PySide6.QtTest import QTest

        QTest.qWait(ms)

    def until(self, condition, timeout: int = 4000, what: str = "") -> None:
        from PySide6.QtTest import QTest

        waited = 0
        while not condition():
            QTest.qWait(25)
            waited += 25
            if waited > timeout:
                raise RuntimeError(f"Timed out waiting for {what or condition}")

    def settle(self, ms: int = 250) -> None:
        """Let queued session events, layout and the first paint finish."""
        self.wait(ms)
        self.wait(ms)

    # -- finding things -------------------------------------------------------------
    def item(self, name: str):
        """A QML item by objectName: the visual tree first (popup contents sit
        in the overlay; Repeater delegates aren't QObject children), then any
        QObject child (a Menu or a Popup isn't an Item)."""
        from PySide6.QtCore import QObject

        found = _walk(self.window.contentItem(), name) or self.window.findChild(QObject, name)
        if found is None:
            raise KeyError(f"No QML item named {name!r}")
        return found

    def has(self, name: str) -> bool:
        try:
            self.item(name)
            return True
        except KeyError:
            return False

    def centre(self, name_or_item):
        item = self.item(name_or_item) if isinstance(name_or_item, str) else name_or_item
        from PySide6.QtCore import QPointF

        point = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
        return point.toPoint()

    # -- the pointer and the keys -----------------------------------------------------
    def click(self, name_or_item, button=None) -> None:
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest

        QTest.mouseClick(self.window, button or Qt.MouseButton.LeftButton,
                         Qt.KeyboardModifier.NoModifier, self.centre(name_or_item))
        self.wait(120)

    def hover(self, name_or_item, ms: int = 900) -> None:
        """Rest the pointer on an item long enough for its tooltip."""
        from PySide6.QtCore import QPoint
        from PySide6.QtTest import QTest

        QTest.mouseMove(self.window, QPoint(1, self.window.height() - 2))
        self.wait(20)
        QTest.mouseMove(self.window, self.centre(name_or_item))
        self.wait(ms)

    def park_pointer(self) -> None:
        """Somewhere quiet, so no tooltip or hover state is in the shot."""
        from PySide6.QtCore import QPoint
        from PySide6.QtTest import QTest

        QTest.mouseMove(self.window, QPoint(self.window.width() // 2, 16))
        self.wait(20)
        QTest.mouseMove(self.window, QPoint(self.window.width() // 2 + 1, 16))
        self.wait(60)

    def call(self, object_name: str, function: str, *args) -> None:
        """Call a QML function of the object named ``object_name``."""
        from PySide6.QtCore import QMetaObject, QObject, Q_ARG, Qt

        target = self.window.findChild(QObject, object_name)
        if target is None:
            raise KeyError(f"No object named {object_name!r}")
        ok = QMetaObject.invokeMethod(target, function, Qt.ConnectionType.DirectConnection,
                                      *[Q_ARG("QVariant", a) for a in args])
        if not ok:
            raise RuntimeError(f"{object_name}.{function} could not be called")
        self.settle()

    def dialogs(self, function: str, *args) -> None:
        """Call one of AppDialogs.qml's functions (``openSettings("voicings")``)."""
        self.call("appDialogs", function, *args)

    def click_text(self, text: str) -> None:
        """Click the visible item whose ``text`` is ``text`` (a menu entry)."""
        found = _walk_text(self.window.contentItem(), text)
        if found is None:
            raise KeyError(f"No visible item with the text {text!r}")
        self.click(found)

    def instruments(self) -> None:
        """Give the silent player the bundled soundfont's 128 preset names."""
        player = self.qt.core.playback._player
        names = soundfont_presets(REPO / "resources" / "soundfont" / "GeneralUser-GS.sf2")
        player.get_available_instruments = lambda: names
        self.submit("set_instrument", program=0)
        self.settle()

    def fretted(self, voicing: str = "guitar:standard") -> None:
        """Voice the song for a guitar and wait until Fret cards and Tab exist."""
        self.submit("set_voicing", voicing=voicing)
        self.until(lambda: all(v["available"] for v in self.state("ChordSheetState", "views")),
                   timeout=15000, what="the fretted views")
        self.settle()

    def key(self, key, modifier=None) -> None:
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest

        QTest.keyClick(self.window, key, modifier or Qt.KeyboardModifier.NoModifier)
        self.wait(120)

    # -- commands -------------------------------------------------------------------
    def submit(self, command: str, **args) -> None:
        self.qt.store.submit(command, args)
        self.wait(60)

    def state(self, type_name: str, key: str):
        return self.qt.store.state(type_name).value(key)

    def song(self, filename: str, name: Optional[str] = None) -> None:
        """Open one of the guide's example songs as a saved document.

        The text goes in as a restored draft of a document that lives in a
        made-up folder: nothing is written, and the status bar has no
        "Opened: <temporary path>" in it.
        """
        name = name or filename
        text = (SONGS / filename).read_text(encoding="utf-8")
        ref = {"id": f"/home/musician/Songs/{name}", "display_name": name,
               "location": "/home/musician/Songs"}
        self.qt.store.submit("restore_draft", {"text": text, "document": ref,
                                               "modified": False, "read_only": False})
        self.until(lambda: self.window.title().startswith(name), what="the song")
        self.settle()

    def text(self, text: str, name: str) -> None:
        """Open ``text`` as a song called ``name`` (see :meth:`song`)."""
        ref = {"id": f"/home/musician/Songs/{name}", "display_name": name,
               "location": "/home/musician/Songs"}
        self.qt.store.submit("restore_draft", {"text": text, "document": ref,
                                               "modified": False, "read_only": False})
        self.until(lambda: self.window.title().startswith(name), what="the song")
        self.settle()

    def mode(self, mode: str) -> None:
        self.window.setProperty("mode", mode)
        self.settle()

    def playing(self, chords: int) -> None:
        """Start playback and freeze it after ``chords`` chord pings."""
        self.qt.store.submit("play_pause", {"from_offset": None})
        player = self.qt.core.playback._player
        self.until(lambda: player.event_buffer is not None, what="the player's buffer")
        thread = self.qt.core.playback._render_thread
        if thread is not None:
            thread.join(5)
        player.play(chords)
        self.settle()


# -- the images ---------------------------------------------------------------------------
#
# Songs: the two the Android guide uses (public domain), so both editions show
# the same music. The window is 1280x800 logical px unless a shot says
# otherwise.

GRACE = ("amazing_grace.txt", "Amazing Grace.txt")
FAIR = ("scarborough_fair.txt", "Scarborough Fair.txt")
TWINKLE = ("C        C/E      F      C\n"
           "Twinkle, twinkle, little star,\n"
           "Dm    Am     G        C\n"
           "How I wonder what you are!\n")


@shot("editor-main-window", "introduction", "Play mode with Amazing Grace playing: the hero shot.")
def _main_window(sc: Scene):
    sc.song(*GRACE)
    sc.mode("play")
    sc.playing(5)


@shot("main-window-labeled", "getting started", "Edit mode, the Directives sidebar open, numbered.",
      callouts=[(1, "playTab", 1.35, 0.5), (2, "appMenuButton"), (3, "iconRail", 0.5, 0.45),
                (4, "editToolbar", 0.62, 0.5), (5, "editor", 0.78, 0.5), (6, "statusBar", 0.5, 0.5)])
def _edit_window(sc: Scene):
    sc.song(*FAIR)
    sc.mode("edit")


@shot("play-window-labeled", "getting started", "Play mode while a song plays, numbered.",
      callouts=[(1, "titleBlock", 0.5, 1.0, "playerBar"), (2, "prevButton", 0.5, 1.0, "playerBar"),
                (3, "playButton", 0.5, 1.0, "playerBar"), (4, "stopButton", 0.5, 1.0, "playerBar"),
                (5, "timeline", 0.5, 1.0, "playerBar"), (6, "position", 0.5, 1.0, "playerBar"),
                (7, "voicingTip", 0.5, 1.0, "playerBar"), (8, "instrumentButton", 0.5, 1.0, "playerBar"),
                (9, "speedButton", 0.5, 1.0, "playerBar"), (10, "metronomeButton", 0.5, 1.0, "playerBar"),
                (11, "volumeButton", 0.5, 1.0, "playerBar"), (12, "sheetTabs", 0.5, 1.0)])
def _play_window(sc: Scene):
    sc.song(*GRACE)
    sc.mode("play")
    sc.playing(5)


@shot("app-menu", "interface", "The ☰ menu.", crop_rect=(940, 30, 1280, 420))
def _app_menu(sc: Scene):
    sc.song(*FAIR)
    sc.click("appMenuButton")


@shot("menu-bar", "interface", "The menu bar shown, with the View menu open.", crop_rect=(0, 0, 480, 600))
def _menu_bar(sc: Scene):
    sc.song(*FAIR)
    sc.qt.chrome.menuBar = True
    sc.settle()
    sc.call("appMenuBar", "openMenu", 2)


@shot("directives-palette", "interface", "The Directives sidebar.", crop_rect=(0, 36, 520, 440))
def _palette(sc: Scene):
    sc.song(*FAIR)
    sc.click("rail:directives")


@shot("chord-identifier", "interface", "The Chord identifier with C E G entered.",
      crop_rect=(0, 36, 520, 560))
def _identifier(sc: Scene):
    sc.song(*FAIR)
    sc.click("rail:identifier")
    sc.qt.identifier.type("C E G")


@shot("chord-sheet-piano-roll", "chord sheet", "The piano roll while Amazing Grace plays.",
      crop="chordSheetPane", pad=0)
def _sheet_roll(sc: Scene):
    sc.song(*GRACE)
    sc.mode("play")
    sc.playing(5)


@shot("chord-sheet-staff", "chord sheet", "The staff view.", crop="chordSheetPane", pad=0)
def _sheet_staff(sc: Scene):
    sc.song(*GRACE)
    sc.mode("play")
    sc.click("sheetTab:staff")
    sc.playing(5)


@shot("chord-sheet-fret-cards", "chord sheet", "Fret cards with a guitar voicing.",
      crop="chordSheetPane", pad=0)
def _sheet_cards(sc: Scene):
    sc.song(*GRACE)
    sc.mode("play")
    sc.fretted()
    sc.click("sheetTab:fret")
    sc.playing(5)


@shot("chord-sheet-tab", "chord sheet", "Tab with a guitar voicing.", crop="chordSheetPane", pad=0)
def _sheet_tab(sc: Scene):
    sc.song(*GRACE)
    sc.mode("play")
    sc.fretted()
    sc.click("sheetTab:tab")
    sc.playing(5)


@shot("settings-general", "settings", "Settings, General.", window="settingsWindow",
      size_window=(900, 720))
def _settings_general(sc: Scene):
    sc.song(*FAIR)
    sc.dialogs("openSettings", "general")


@shot("settings-playback", "settings", "Settings, Playback and audio.", window="settingsWindow",
      size_window=(900, 560))
def _settings_playback(sc: Scene):
    sc.song(*FAIR)
    sc.dialogs("openSettings", "playback")


@shot("settings-voicings", "settings", "Settings, Voicings.", window="settingsWindow",
      size_window=(900, 720))
def _settings_voicings(sc: Scene):
    sc.song(*FAIR)
    sc.dialogs("openSettings", "voicings")


@shot("settings-voicing-form", "settings", "Settings, Voicings, a new fretboard voicing.",
      window="settingsWindow", size_window=(900, 720))
def _settings_voicing_form(sc: Scene):
    sc.song(*FAIR)
    sc.dialogs("openSettings", "voicings")
    sc.submit("add_voicing")
    sc.wait(400)


@shot("transpose", "transpose", "The Transpose dialog.", crop="transposeDialog", pad=14)
def _transpose(sc: Scene):
    sc.song(*GRACE)
    sc.click("transposeButton")


@shot("capo-suggest", "directives", "The Suggest Capo dialog.", crop="capoDialog", pad=14)
def _capo(sc: Scene):
    sc.song(*GRACE)
    sc.dialogs("openSuggestCapo")


@shot("quick-start", "getting started", "The Quick Start tour, page 1.", crop="quickStartDialog",
      pad=14, config={"show_quick_start_on_startup": True})
def _quick_start(sc: Scene):
    sc.until(lambda: sc.has("quickStartDialog") and sc.item("quickStartDialog").property("opened"),
             what="Quick Start")


@shot("speed-controls", "getting started", "The speed popup.", crop_rect=(780, 36, 1280, 330))
def _speed(sc: Scene):
    sc.song(*GRACE)
    sc.mode("play")
    sc.click("speedButton")


@shot("instrument-menu", "getting started", "The instrument menu, Guitar family open.",
      crop_rect=(780, 36, 1280, 520))
def _instrument(sc: Scene):
    sc.song(*GRACE)
    sc.instruments()
    sc.mode("play")
    sc.click("instrumentButton")
    sc.click_text("Guitar")


@shot("voicing-menu", "playback", "The Voicing menu.", crop_rect=(780, 36, 1280, 520))
def _voicing(sc: Scene):
    sc.song(*GRACE)
    sc.mode("play")
    sc.click("voicingTip")


@shot("key-picker", "interface", "The key picker opened from the song values.",
      crop_rect=(0, 36, 640, 330))
def _key_picker(sc: Scene):
    # A song with no {key}, so the value isn't a link to a directive.
    sc.text(TWINKLE, "Twinkle.txt")
    sc.mode("play")
    sc.click("keyValue")


@shot("chord_sheet_qt", "Quick Start, page 6", "The chord sheet's fret cards, for the Quick Start.",
      dest="quickstart", crop="chordSheetPane", pad=0, crop_size=(702, 300),
      size=(1000, 700))
def _quick_start_image(sc: Scene):
    sc.text(TWINKLE, "Twinkle.txt")
    sc.mode("play")
    sc.fretted()
    sc.click("sheetTab:fret")


# The store listings (Microsoft Store, AppStream, the Snap Store): 1920x1080, the
# window 1920x1080 at scale 1 (at 2x the icons come out cropped offscreen, see notes). Songs are the same public-domain two.
STORE = dict(dest="store", size=(1920, 1080), quantize=False)


@shot("01-play-piano-roll", "store", "Amazing Grace playing, on the piano roll.", **STORE)
def _store_play(sc: Scene):
    sc.song(*GRACE)
    sc.mode("play")
    sc.playing(5)


@shot("02-edit", "store", "Scarborough Fair in Edit mode with the Directives sidebar.", **STORE)
def _store_edit(sc: Scene):
    sc.song(*FAIR)
    sc.mode("edit")


@shot("03-play-fret-cards", "store", "Scarborough Fair playing, guitar fret cards.", **STORE)
def _store_cards(sc: Scene):
    sc.song(*FAIR)
    sc.mode("play")
    sc.fretted()
    sc.click("sheetTab:fret")
    sc.playing(6)


@shot("04-play-staff-dark", "store", "Amazing Grace playing on the staff, dark theme.", dark=True,
      **STORE)
def _store_staff_dark(sc: Scene):
    sc.song(*GRACE)
    sc.mode("play")
    sc.click("sheetTab:staff")
    sc.playing(5)


@shot("05-identifier", "store", "The chord identifier next to the song.", **STORE)
def _store_identifier(sc: Scene):
    sc.song(*FAIR)
    sc.click("rail:identifier")
    sc.qt.identifier.type("A C E G")


@shot("06-voicings", "store", "Settings, a fretboard voicing.", window="settingsWindow",
      size_window=(1920, 1080), **STORE)
def _store_voicings(sc: Scene):
    sc.song(*FAIR)
    sc.dialogs("openSettings", "voicings")
    sc.submit("add_voicing")
    sc.wait(400)


@shot("notation-toggle", "writing chords", "The AB | Do switch.", crop="notationToggle", pad=6)
def _notation(sc: Scene):
    sc.song(*FAIR)
    sc.mode("edit")


# -- the runner ---------------------------------------------------------------------------


def rect_of(obj) -> Tuple[float, float, float, float]:
    """The scene rectangle (x, y, width, height, logical px) of an item or a Popup."""
    from PySide6.QtCore import QPointF

    if hasattr(obj, "mapToScene"):
        top_left = obj.mapToScene(QPointF(0, 0))
        return top_left.x(), top_left.y(), obj.width(), obj.height()
    return (obj.property("x"), obj.property("y"), obj.property("width"), obj.property("height"))


def destination(shot: Shot, out_dir: Path) -> Path:
    """The folder of ``shot``'s PNG. By default each kind goes where the repository
    uses it; ``--out`` puts the help images there and the others in subfolders."""
    if shot.dest == "help":
        return out_dir
    if out_dir == HELP_OUT:
        return {"store": STORE_OUT, "quickstart": QUICK_START_OUT}[shot.dest]
    return out_dir / shot.dest


def to_pil(image):
    """A QImage as a Pillow RGBA image."""
    from PIL import Image
    from PySide6.QtGui import QImage

    image = image.convertToFormat(QImage.Format.Format_RGBA8888)
    return Image.frombytes("RGBA", (image.width(), image.height()), bytes(image.constBits()))


def save_png(img, path: Path, quantize: bool = True) -> None:
    """Palette PNG (libimagequant when present), optimised, deterministic."""
    from PIL import features

    path.parent.mkdir(parents=True, exist_ok=True)
    rgb = img.convert("RGB")
    if quantize and features.check("libimagequant"):
        rgb = rgb.quantize(colors=256, method=3, dither=0)
    rgb.save(path, optimize=True)


def draw_callouts(img, points: List[Tuple[int, float, float]], scale: float):
    """Numbered discs at ``points`` (number, x, y in logical px)."""
    from PIL import ImageDraw, ImageFont

    draw = ImageDraw.Draw(img)
    r = round(11 * scale)
    font = None
    for candidate in ("/usr/share/fonts/google-roboto/Roboto-Bold.ttf",
                      "/usr/share/fonts/google-noto/NotoSans-Bold.ttf",
                      "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf",
                      "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        if Path(candidate).exists():
            font = ImageFont.truetype(candidate, round(13 * scale))
            break
    for number, x, y in points:
        cx, cy = round(x * scale), round(y * scale)
        draw.ellipse((cx - r - 2, cy - r - 2, cx + r + 2, cy + r + 2), fill=HALO)
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=PRIMARY)
        draw.text((cx, cy), str(number), fill=ON_PRIMARY, font=font, anchor="mm")
    return img


def run_shot(shot: Shot, out_dir: Path, scale: float, size: Tuple[int, int],
             base: Path, keep: bool) -> Path:
    """Start the app, set the scene, grab and save one image."""
    import json as _json

    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQuick import QQuickItem, QQuickWindow

    from chordnotepad.app_paths import AppPaths
    from chordnotepad.services.appdata_service import AppDataService
    from chordnotepad.session.testing import FakePlayer
    from chordnotepad_desktop.application import QtApplication

    tmp = Path(tempfile.mkdtemp(prefix=f"{shot.name}-", dir=base))
    config_dir = tmp / "appdata" / "config" / "chord-notepad"
    config_dir.mkdir(parents=True)
    config = {"version": 4, "show_quick_start_on_startup": False,
              "ui_theme": "dark" if shot.dark else "light", "audio_driver": "file",
              **shot.config}
    (config_dir / "settings.json").write_text(_json.dumps(config), encoding="utf-8")

    app = QGuiApplication.instance()
    paths = AppPaths(resources=REPO / "resources")
    qt = QtApplication(paths, appdata=AppDataService(root=tmp / "appdata"),
                       player=FakePlayer(auto_play=False), configure_logging=False,
                       today=lambda: TODAY)
    main = qt.start(app)
    window = main.window
    sc = Scene(qt, window, app, tmp)
    try:
        sc.until(lambda: window.property("contentReady") is True, what="the window")
        w, h = shot.size or size
        window.resize(w, h)
        sc.settle()
        shot.scene(sc)
        sc.settle()
        if not shot.keep_pointer:
            sc.park_pointer()
        target = window
        if shot.window:
            target = window.findChild(QQuickWindow, shot.window) or sc.item(shot.window).window()
            if shot.size_window:
                target.resize(*shot.size_window)
                sc.settle()
        image = to_pil(target.grabWindow())
        ratio = image.width / max(1, target.width())
        points = []
        for number, name, *more in shot.callouts:
            fx, fy, *yref = more or (0.5, 0.5)
            x, y, w, h = rect_of(sc.item(name))
            if yref:  # the row of another item: this item's x, that item's y
                _, y, _, h = rect_of(sc.item(yref[0]))
            points.append((number, x + w * fx, y + h * fy))
        image = draw_callouts(image, points, ratio)
        box = None
        if shot.crop:
            x, y, w, h = rect_of(sc.item(shot.crop))
            box = (x - shot.pad, y - shot.pad, x + w + shot.pad, y + h + shot.pad)
        elif shot.crop_rect:
            box = shot.crop_rect
        if box and shot.crop_size:
            box = (box[0], box[1], box[0] + shot.crop_size[0], box[1] + shot.crop_size[1])
        if box:
            box = (max(0, box[0]), max(0, box[1]),
                   min(target.width(), box[2]), min(target.height(), box[3]))
            image = image.crop(tuple(round(v * ratio) for v in box))
        if shot.final_size:
            from PIL import Image

            image = image.resize(shot.final_size, Image.Resampling.LANCZOS)
        path = destination(shot, out_dir) / f"{shot.name}.png"
        save_png(image, path, shot.quantize)
        return path
    finally:
        qt.shutdown()
        QGuiApplication.processEvents()
        if not keep:
            shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--list", action="store_true", help="list the shots and exit")
    parser.add_argument("--only", help="comma-separated shot names")
    parser.add_argument("--out", type=Path, default=HELP_OUT,
                        help="folder for the help images (default help/images/desktop)")
    parser.add_argument("--scale", type=float, default=1.0,
                        help="device pixel ratio (QT_SCALE_FACTOR); 1 gives logical-size PNGs")
    parser.add_argument("--size", default=f"{DEFAULT_SIZE[0]}x{DEFAULT_SIZE[1]}",
                        help="window size in logical px")
    parser.add_argument("--keep", action="store_true", help="keep each shot's temporary profile")
    args = parser.parse_args(argv)

    if args.list:
        for s in SHOTS.values():
            print(f"{s.name:28} {s.dest:10} {s.page}: {s.what}")
        return 0
    names = args.only.split(",") if args.only else list(SHOTS)
    unknown = [n for n in names if n not in SHOTS]
    if unknown:
        sys.exit(f"Unknown shot(s): {', '.join(unknown)} (see --list)")
    width, height = (int(v) for v in args.size.lower().split("x"))

    scales = sorted({SHOTS[n].scale or args.scale for n in names})
    if len(scales) > 1:
        # QT_SCALE_FACTOR is read once at start-up: one process per scale.
        import subprocess

        status = 0
        for scale in scales:
            group = [n for n in names if (SHOTS[n].scale or args.scale) == scale]
            command = [sys.executable, __file__, "--only", ",".join(group), "--out", str(args.out),
                       "--size", args.size, "--scale", repr(args.scale)]
            command += ["--keep"] * args.keep
            status |= subprocess.call(command)
        return status
    args.scale = scales[0]

    base = Path(tempfile.mkdtemp(prefix="cn-qt-shots-"))
    isolate_environment(base)
    os.environ["QT_SCALE_FACTOR"] = repr(args.scale)
    sys.path[:0] = [str(REPO / "core"), str(REPO / "desktop")]

    from PySide6.QtGui import QGuiApplication

    from chordnotepad_desktop.main import prepare_application
    from chordnotepad.app_paths import AppPaths

    app = QGuiApplication([sys.argv[0]])
    prepare_application(app, AppPaths(resources=REPO / "resources"))
    status = 0
    try:
        for name in names:
            try:
                path = run_shot(SHOTS[name], args.out, args.scale, (width, height), base, args.keep)
                print(f"{name}: {path.relative_to(REPO) if path.is_relative_to(REPO) else path}")
            except Exception as e:  # keep going: one bad scene shouldn't lose the rest
                status = 1
                print(f"{name}: FAILED: {e!r}", file=sys.stderr)
    finally:
        shutil.rmtree(base, ignore_errors=True)
    return status


if __name__ == "__main__":
    sys.exit(main())
