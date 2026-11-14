"""The Qt window's Edit sidebars (plan step F5): which one is open and its width.

Desktop only, like the volume: two config keys, read back as the session's
``sidebar`` / ``sidebar_width`` (direct calls) and written with the bridge
commands ``set_sidebar`` / ``set_sidebar_width``. Android sends neither.
"""

import json
import math

import pytest

from chordnotepad.constants import (
    DEFAULT_SIDEBAR, DEFAULT_SIDEBAR_WIDTH, SIDEBAR_WIDTH_MAX, SIDEBAR_WIDTH_MIN, SIDEBARS,
)
from chordnotepad.models.config import Config
from chordnotepad.session import bridge
from tests.test_volume import make


def test_the_config_keys_and_their_defaults():
    assert SIDEBARS == ("directives", "identifier") and DEFAULT_SIDEBAR == "directives"
    assert (SIDEBAR_WIDTH_MIN, DEFAULT_SIDEBAR_WIDTH, SIDEBAR_WIDTH_MAX) == (56, 76, 150)
    config = Config()
    assert (config.sidebar, config.sidebar_width) == ("directives", 76)
    assert config.to_dict()["sidebar"] == "directives" and config.to_dict()["sidebar_width"] == 76
    loaded = Config.from_dict({"sidebar": "identifier", "sidebar_width": 90.25})
    assert (loaded.sidebar, loaded.sidebar_width) == ("identifier", 90.2)
    assert Config.from_dict({"sidebar": ""}).sidebar == ""


@pytest.mark.parametrize("raw, expected", [
    ("tools", "directives"), (None, "directives"), (3, "directives"), (["identifier"], "directives"),
])
def test_a_junk_sidebar_reads_as_the_default(raw, expected):
    config = Config.from_dict({"sidebar": raw, "bpm": 90})
    assert config.sidebar == expected and config.bpm == 90
    config.validate()


@pytest.mark.parametrize("raw, expected", [
    (10, 56), (500, 150), ("wide", 76), (True, 76), (None, 76), (math.nan, 76), (100, 100),
])
def test_a_saved_width_is_clamped_and_junk_is_the_default(raw, expected):
    config = Config.from_dict({"sidebar_width": raw})
    assert config.sidebar_width == expected
    config.validate()


def test_validate_refuses_what_from_dict_never_makes():
    config = Config()
    config.sidebar = "tools"
    with pytest.raises(ValueError):
        config.validate()
    config = Config()
    config.sidebar_width = 20
    with pytest.raises(ValueError):
        config.validate()


def test_the_session_reads_and_keeps_them(tmp_path):
    session, services, _ = make(tmp_path, {"sidebar": "identifier", "sidebar_width": 100})
    assert (session.sidebar, session.sidebar_width) == ("identifier", 100.0)
    session.set_sidebar("")
    session.set_sidebar_width(120.04)
    assert (session.sidebar, session.sidebar_width) == ("", 120.0)
    session.set_sidebar_width(999)
    assert session.sidebar_width == SIDEBAR_WIDTH_MAX
    session.set_sidebar_width(1)
    assert session.sidebar_width == SIDEBAR_WIDTH_MIN
    session.set_sidebar("directives")
    services.config.save_config()
    saved = json.loads(services.config.config_file_path.read_text())
    assert (saved["sidebar"], saved["sidebar_width"]) == ("directives", SIDEBAR_WIDTH_MIN)


def test_a_first_start_has_the_palette_open(tmp_path):
    session, _, _ = make(tmp_path)
    assert (session.sidebar, session.sidebar_width) == ("directives", 76.0)


@pytest.mark.parametrize("bad", ["tools", "Directives", None])
def test_set_sidebar_refuses_other_names(tmp_path, bad):
    session, services, _ = make(tmp_path)
    with pytest.raises(ValueError):
        session.set_sidebar(bad)
    assert services.config.config.sidebar == "directives"


@pytest.mark.parametrize("bad", [math.nan, math.inf])
def test_set_sidebar_width_refuses_what_isnt_a_number(tmp_path, bad):
    session, services, _ = make(tmp_path)
    with pytest.raises(ValueError):
        session.set_sidebar_width(bad)
    assert services.config.config.sidebar_width == 76


def test_the_qt_window_reaches_them_through_the_bridge():
    assert bridge.SESSION_COMMANDS["set_sidebar"] == {"sidebar": "str"}
    assert bridge.SESSION_COMMANDS["set_sidebar_width"] == {"width": "float"}
    assert {"set_sidebar", "set_sidebar_width"} <= bridge.CONFIG_COMMANDS
