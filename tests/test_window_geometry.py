"""The window's geometry and the chord sheet's height, kept for both desktops.

The Qt window saves a neutral form in logical pixels (``window_bounds``,
``window_maximized``, ``chord_sheet_logical_height``) and Tk's values next to
it; Tk saves only its own and drops the neutral ones. Each front end must
open where the other closed, at any scale, without drifting a pixel when
the user switches back and forth (the 0.6.0 ``--ui tk`` fallback).
"""

import json
import math
import random

import pytest

from chordnotepad.constants import DEFAULT_CHORD_SHEET_HEIGHT
from chordnotepad.models import window_geometry as wg
from chordnotepad.models.config import Config
from chordnotepad.models.window_geometry import WindowGeometry
from chordnotepad.services.appdata_service import AppDataService
from chordnotepad.services.config_service import ConfigService
from chordnotepad.session.bootstrap import build_core_services, create_session
from chordnotepad.session.host import HostDispatch
from chordnotepad.session.platform import DESKTOP, DESKTOP_QT
from chordnotepad.session.testing import EventRecorder, FakePlayer, InMemoryDocumentStore, ManualHost

SCALES = (1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 3.0)


# -- Tk's string -----------------------------------------------------------------


@pytest.mark.parametrize("text, expected", [
    ("900x600", WindowGeometry(900, 600)),
    ("1200x800+100+50", WindowGeometry(1200, 800, 100, 50)),
    ("1200x800+-8+-8", WindowGeometry(1200, 800, -8, -8)),     # maximized on Windows
    (" 640x480+0+0 ", WindowGeometry(640, 480, 0, 0)),
    ("=640x480+3+4", WindowGeometry(640, 480, 3, 4)),
    ("640x480-10-10", WindowGeometry(640, 480)),               # from the right: size only
    ("640x480+10-10", WindowGeometry(640, 480)),
])
def test_tk_geometry_strings(text, expected):
    assert wg.parse_tk_geometry(text) == expected


@pytest.mark.parametrize("text", ["", "900", "900x", "0x600", "900x0", "axb", "900x600+1",
                                  None, 900, "900x600+1+2+3"])
def test_what_isnt_a_tk_geometry(text):
    assert wg.parse_tk_geometry(text) is None


def test_format_like_tk():
    assert wg.format_tk_geometry(WindowGeometry(900, 600)) == "900x600"
    assert wg.format_tk_geometry(WindowGeometry(900, 600, 10, 20)) == "900x600+10+20"
    assert wg.format_tk_geometry(WindowGeometry(900, 600, -8, -8)) == "900x600+-8+-8"
    assert wg.parse_tk_geometry("900x600+-8+-8") == WindowGeometry(900, 600, -8, -8)


@pytest.mark.parametrize("scale", [0, -1, math.nan, math.inf, True, "1.25", None])
def test_a_scale_must_be_a_number_above_zero(scale):
    with pytest.raises(ValueError):
        wg.check_scale(scale)
    with pytest.raises(ValueError):
        wg.saved_geometry(None, "900x600", False, scale)


# -- migration and the neutral form --------------------------------------------------


def test_tk_physical_pixels_become_logical_ones():
    assert wg.saved_geometry(None, "1200x800+100+50", False, 1.25) == WindowGeometry(960, 640, 80, 40)
    assert wg.saved_geometry(None, "1200x800+100+50", False, 1.0) == WindowGeometry(1200, 800, 100, 50)
    assert wg.saved_geometry(None, "1200x800+-10+-10", True, 2.0) == WindowGeometry(
        600, 400, -5, -5, True)
    # Half a pixel rounds up, for a place left of the screen too.
    assert wg.to_logical(5, 2.0) == 3 and wg.to_logical(-5, 2.0) == -2


def test_junk_gives_the_logical_default():
    for tk in ("nonsense", None, ""):
        assert wg.saved_geometry(None, tk, False, 1.5) == WindowGeometry(900, 600)
    # Tk's default size is what Tk showed: converted like any other.
    assert wg.saved_geometry(None, "900x600", False, 1.5) == WindowGeometry(600, 400)
    assert wg.saved_sheet_height(None, 160, 1.25) == 128
    assert wg.saved_sheet_height(None, "junk", 1.25) == DEFAULT_CHORD_SHEET_HEIGHT


def test_a_first_start_has_the_neutral_defaults_and_a_tk_config_has_none():
    fresh = Config.from_dict({})
    assert fresh.window_bounds == {"width": 900, "height": 600, "x": None, "y": None}
    assert fresh.chord_sheet_logical_height == DEFAULT_CHORD_SHEET_HEIGHT
    assert Config().window_bounds == fresh.window_bounds
    tk_written = Config.from_dict({"window_geometry": "900x600+0+0", "chord_sheet_height": 160})
    assert tk_written.window_bounds is None and tk_written.chord_sheet_logical_height is None
    tk_dropped = Config.from_dict({"window_geometry": "900x600+0+0", "window_bounds": None,
                                   "chord_sheet_height": 160, "chord_sheet_logical_height": None})
    assert tk_dropped.window_bounds is None and tk_dropped.chord_sheet_logical_height is None


def test_the_neutral_bounds_win_over_tk():
    bounds = {"width": 1000, "height": 700, "x": 5, "y": 6}
    assert wg.saved_geometry(bounds, "100x100+0+0", True, 2.0) == WindowGeometry(1000, 700, 5, 6, True)
    unplaced = {"width": 1000, "height": 700, "x": None, "y": None}
    assert wg.saved_geometry(unplaced, "100x100+0+0", False, 2.0) == WindowGeometry(1000, 700)


@pytest.mark.parametrize("raw", [
    None, "1000x700", [], {"width": 0, "height": 700}, {"width": 1000},
    {"width": 10.5, "height": 7}, {"width": True, "height": 7}, {"width": "10", "height": 7},
])
def test_junk_bounds_are_ignored(raw):
    assert wg.bounds_from_config(raw) is None
    assert Config.from_dict({"window_bounds": raw}).window_bounds is None


def test_half_a_place_is_no_place():
    assert wg.bounds_from_config({"width": 10, "height": 7, "x": 1}) == WindowGeometry(10, 7)
    assert Config.from_dict({"window_bounds": {"width": 10, "height": 7, "x": 1, "y": "2"}}
                            ).window_bounds == {"width": 10, "height": 7, "x": None, "y": None}


def test_the_config_keeps_the_new_keys():
    config = Config.from_dict({"window_bounds": {"width": 10, "height": 7, "x": -3, "y": 4},
                               "chord_sheet_logical_height": 200})
    data = config.to_dict()
    assert data["window_bounds"] == {"width": 10, "height": 7, "x": -3, "y": 4}
    assert data["chord_sheet_logical_height"] == 200
    assert Config().to_dict()["window_bounds"] == wg.DEFAULT_BOUNDS
    for junk in (0, -4, 1.5, "200", True):
        assert Config.from_dict({"chord_sheet_logical_height": junk}).chord_sheet_logical_height is None


def test_tk_string_is_kept_when_it_already_converts_to_the_bounds():
    # 1201 / 1.25 = 960.8 -> 961: a Qt window at 961 logical keeps Tk's 1201.
    assert wg.tk_geometry_for(WindowGeometry(961, 640, 80, 40), 1.25, "1201x800+100+50") == (
        "1201x800+100+50")
    assert wg.tk_geometry_for(WindowGeometry(962, 640, 80, 40), 1.25, "1201x800+100+50") == (
        "1203x800+100+50")
    assert wg.tk_geometry_for(WindowGeometry(962, 640), 1.25, "junk") == "1203x800"


# -- round trips between the front ends ----------------------------------------------


def _geometries(seed):
    rng = random.Random(seed)
    for _ in range(300):
        placed = rng.random() < 0.8
        yield WindowGeometry(rng.randint(200, 4000), rng.randint(150, 2500),
                             rng.randint(-50, 5000) if placed else None,
                             rng.randint(-50, 3000) if placed else None,
                             rng.random() < 0.3)


class Desktop:
    """The two front ends over one config file, as the app uses them."""

    def __init__(self, path):
        self.path = path

    def _session(self, platform):
        host = ManualHost()
        services = build_core_services(AppDataService(root=self.path), HostDispatch(host),
                                       player=FakePlayer())
        session = create_session(host, services, InMemoryDocumentStore(), chord_sheet=True,
                                 platform=platform)
        session.subscribe(EventRecorder())
        session.start()
        return session, services

    def qt_close(self, geometry, sheet_height, scale):
        session, services = self._session(DESKTOP_QT)
        session.set_logical_window_geometry(geometry, scale)
        session.set_logical_chord_sheet_height(sheet_height, scale)
        services.config.save_config()

    def qt_open(self, scale):
        session, _ = self._session(DESKTOP_QT)
        return session.logical_window_geometry(scale), session.logical_chord_sheet_height(scale)

    def tk_open(self):
        session, services = self._session(DESKTOP)
        return session.window_geometry, services.config.config.chord_sheet_height

    def tk_close(self, geometry, sheet_height):
        session, services = self._session(DESKTOP)
        session.set_window_geometry(geometry)
        session.set_chord_sheet_height(sheet_height)
        services.config.save_config()

    def saved(self):
        return json.loads((self.path / "config" / "chord-notepad" / "settings.json").read_text())


@pytest.mark.parametrize("scale", SCALES)
def test_qt_then_tk_then_qt_comes_back_exactly(scale):
    """Logical -> Tk's pixels -> logical is exact for any scale of 1 or more."""
    for geometry in _geometries(int(scale * 100)):
        tk = wg.tk_geometry_for(geometry, scale, None)
        back = wg.saved_geometry(None, tk, geometry.maximized, scale)
        assert back == geometry, (geometry, tk)


@pytest.mark.parametrize("scale", SCALES)
def test_tk_then_qt_then_tk_leaves_tks_string_alone(scale):
    rng = random.Random(int(scale * 1000))
    for _ in range(300):
        tk = f"{rng.randint(200, 5000)}x{rng.randint(150, 3000)}+{rng.randint(-50, 6000)}+{rng.randint(-50, 4000)}"
        logical = wg.saved_geometry(None, tk, False, scale)
        assert wg.tk_geometry_for(logical, scale, tk) == tk
        height = rng.randint(1, 2000)
        assert wg.tk_sheet_height_for(wg.saved_sheet_height(None, height, scale), scale,
                                      height) == height


@pytest.mark.parametrize("scale", SCALES)
def test_sheet_heights_round_trip(scale):
    for height in range(1, 1500, 7):
        tk = wg.tk_sheet_height_for(height, scale, None)
        assert wg.saved_sheet_height(None, tk, scale) == height


def test_both_front_ends_over_one_config_file(tmp_path):
    desktop = Desktop(tmp_path)
    # A config from before Qt: Tk's values at 125%, migrated.
    desktop.tk_close("1200x800+100+50", 250)
    assert desktop.qt_open(1.25) == (WindowGeometry(960, 640, 80, 40), 200)

    # Qt closes maximized, with a taller sheet; Tk opens at Qt's normal geometry.
    desktop.qt_close(WindowGeometry(1000, 700, 40, 30, maximized=True), 300, 1.25)
    saved = desktop.saved()
    assert saved["window_bounds"] == {"width": 1000, "height": 700, "x": 40, "y": 30}
    assert saved["window_maximized"] is True
    assert saved["chord_sheet_logical_height"] == 300
    assert desktop.tk_open() == ("1250x875+50+38", 375)
    assert desktop.qt_open(1.25) == (WindowGeometry(1000, 700, 40, 30, True), 300)

    # Tk saves the same place back: nothing moves on either side.
    desktop.tk_close("1250x875+50+38", 375)
    saved = desktop.saved()
    assert saved["window_bounds"] is None and saved["chord_sheet_logical_height"] is None
    assert saved["window_maximized"] is False      # Tk never restores maximized
    assert desktop.qt_open(1.25) == (WindowGeometry(1000, 700, 40, 30), 300)

    # Tk moved it; Qt follows.
    desktop.tk_close("1500x1000+0+0", 125)
    assert desktop.qt_open(1.25) == (WindowGeometry(1200, 800, 0, 0), 100)

    # Qt reopened without moving: Tk's own string and height are kept as they were.
    geometry, height = desktop.qt_open(1.25)
    desktop.qt_close(geometry, height, 1.25)
    assert desktop.tk_open() == ("1500x1000+0+0", 125)


def test_a_fresh_config_opens_at_the_logical_defaults(tmp_path):
    desktop = Desktop(tmp_path)
    assert desktop.qt_open(1.5) == (WindowGeometry(900, 600), DEFAULT_CHORD_SHEET_HEIGHT)


def test_an_unplaced_qt_window_gives_tk_a_size_only(tmp_path):
    desktop = Desktop(tmp_path)
    desktop.qt_close(WindowGeometry(800, 500), 120, 2.0)
    assert desktop.tk_open() == ("1600x1000", 240)


@pytest.mark.parametrize("geometry", [
    WindowGeometry(0, 600), WindowGeometry(800, -1), WindowGeometry(800, 600, 5, None),
    "800x600", None,
])
def test_a_bad_geometry_is_refused_and_nothing_is_written(tmp_path, geometry):
    desktop = Desktop(tmp_path)
    session, services = desktop._session(DESKTOP_QT)
    before = services.config.config.to_dict()
    with pytest.raises(ValueError):
        session.set_logical_window_geometry(geometry, 1.25)
    with pytest.raises(ValueError):
        session.set_logical_window_geometry(WindowGeometry(800, 600), 0)
    assert services.config.config.to_dict() == before


def test_the_config_service_reads_back_what_qt_wrote(tmp_path):
    desktop = Desktop(tmp_path)
    desktop.qt_close(WindowGeometry(1000, 700, -20, 30, True), 222, 1.5)
    service = ConfigService(AppDataService(root=tmp_path))
    config = service.load_config()
    assert config.window_bounds == {"width": 1000, "height": 700, "x": -20, "y": 30}
    assert config.window_geometry == "1500x1050+-30+45"
    assert (config.window_maximized, config.chord_sheet_logical_height,
            config.chord_sheet_height) == (True, 222, 333)
