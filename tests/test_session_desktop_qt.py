"""The Qt desktop's platform variant (``DESKTOP_QT``, plan step B1).

It has Android's playhead (a clicked chord takes it, playback moves it, ▶
plays from it, Shift+▶ from the cursor) with the desktop's status texts, and
its own wording only where the Tk desktop's texts name Tk menus or controls.
The Tk desktop's texts and behaviour are unchanged (``test_session_player``,
``test_session_platform_texts``).
"""

from pathlib import Path

import pytest

from chordnotepad.session import quick_start
from chordnotepad.session.platform import (
    ANDROID, DESKTOP, DESKTOP_QT, PLATFORMS, TRACKS_PLAYHEAD, check_platform, pick,
)
from chordnotepad.session.state import PlaybackStatus
from tests.test_session_player import Env, named_strip_song


def test_desktop_qt_is_a_platform_of_its_own():
    assert DESKTOP_QT == "desktop_qt" and DESKTOP_QT in PLATFORMS
    assert check_platform(DESKTOP_QT) == DESKTOP_QT
    # Texts without a Qt variant are the desktop's.
    assert pick({DESKTOP: 1, ANDROID: 2}, DESKTOP_QT) == 1
    assert TRACKS_PLAYHEAD == {DESKTOP: False, ANDROID: True, DESKTOP_QT: True}


# -- the playhead -------------------------------------------------------------------


def test_the_playhead_defaults_to_the_first_chord():
    env = Env(DESKTOP_QT)
    assert env.playhead() == 0


def test_a_click_on_a_chord_sounds_it_and_moves_the_playhead():
    env = Env(DESKTOP_QT)
    env.session.tap_chord_at(13)
    assert env.playhead() == 12
    assert env.player.immediate  # auditioned
    # The desktop's status, not Android's position line.
    assert env.status() == "Playing: Am"
    # Not on a chord: nothing moves.
    env.session.tap_chord_at(8)
    assert env.playhead() == 12


def test_play_starts_at_the_playhead_and_playback_moves_it():
    env = Env(DESKTOP_QT, auto_play=False)
    env.session.tap_chord_at(4)
    env.session.play_pause()
    # From the playhead, which isn't "from cursor".
    assert env.status() == "Playing 4 chords..."
    env.rendered()
    env.player.play(2)
    env.host.run_pending()
    assert env.first_played_chord() == "G"
    assert env.playhead() == 12
    assert env.status().startswith("Bar ") and env.status().endswith("Playing: Am")
    env.player.play()
    env.host.run_pending()
    # The end of the song brings it back to the first chord.
    assert env.playback().status is PlaybackStatus.IDLE
    assert env.playhead() == 0
    assert env.status() == "Ready"


def test_shift_play_starts_at_the_cursor():
    env = Env(DESKTOP_QT, auto_play=False)
    env.session.tap_chord_at(4)
    env.session.play_pause(from_offset=15)
    assert env.status() == "Playing from cursor (4 chords)..."
    env.rendered()
    env.player.play(1)
    env.host.run_pending()
    assert env.first_played_chord() == "F"   # the first chord ending after 15
    assert env.playhead() == 16


def test_stop_and_pause_keep_the_playhead_and_rewind_resets_it():
    env = Env(DESKTOP_QT, auto_play=False)
    env.session.play_pause()
    env.rendered()
    env.player.play(2)
    env.host.run_pending()
    env.session.play_pause()
    assert env.status() == "Paused playback"
    assert env.playhead() == 4
    env.session.stop()
    assert env.status() == "Stopped playback"
    assert env.playhead() == 4
    env.session.rewind()
    assert env.playhead() == 0
    assert env.status() == "Ready"


def test_a_click_while_playing_seeks_there():
    env = Env(DESKTOP_QT, auto_play=False)
    env.session.play_pause()
    env.rendered()
    env.player.play(1)
    env.host.run_pending()
    env.session.tap_chord_at(16)
    assert env.player.immediate == []   # a jump, not an audition over the song
    assert env.playback().status is PlaybackStatus.PLAYING
    assert env.status() == "Playing 4 chords..."
    env.rendered()
    env.player.play(1)
    env.host.run_pending()
    assert env.playback().playing_span.start == 16


def test_set_playhead_while_paused_drops_the_paused_song():
    env = Env(DESKTOP_QT, auto_play=False)
    env.session.play_pause()
    env.rendered()
    env.player.play(1)
    env.host.run_pending()
    env.session.play_pause()
    env.session.set_playhead(16)
    assert env.playback().status is PlaybackStatus.IDLE
    assert env.playhead() == 16
    assert env.status() == "Ready"
    env.session.play_pause()
    env.rendered()
    env.player.play(1)
    env.host.run_pending()
    assert env.playback().playing_span.start == 16


def test_a_click_on_a_sheet_chord_moves_the_playhead():
    env = Env(DESKTOP_QT)
    named_strip_song(env)
    env.session.audition(2)
    assert env.sheet.auditioned == [2]
    assert env.playhead() == 12


def test_the_tk_desktop_still_plays_from_the_top_with_its_texts():
    env = Env(DESKTOP, auto_play=False)
    env.session.tap_chord_at(4)
    assert env.playhead() is None
    env.session.play_pause()
    assert env.status() == "Playing 4 chords..."
    env.session.stop()
    env.session.play_pause(from_offset=13)
    assert env.status() == "Playing from cursor (4 chords)..."


# -- texts ----------------------------------------------------------------------------


TK_MENUS = ("Playback →", "View →", "Tools →", "Help →", "Help menu", "Key box",
            "toolbar's Speed")


def _texts(platform):
    return [b[1] for p in quick_start.pages(platform) for b in p["blocks"] if b[0] == "text"]


def test_qt_quick_start_names_the_qt_controls_not_the_tk_menus():
    desktop, qt = quick_start.pages(DESKTOP), quick_start.pages(DESKTOP_QT)
    assert [p["title"] for p in qt] == [p["title"] for p in desktop]
    text = " ".join(_texts(DESKTOP_QT))
    for tk_only in TK_MENUS:
        assert tk_only not in text.replace("☰ → Help →", "☰ ›"), tk_only
    for qt_name in ("Directives palette (Ctrl+Shift+D)", "Chord identifier (Ctrl+Shift+I)",
                    "☰ → Help → Quick start", "Voicing button", "F9", "player bar",
                    "playhead"):
        assert qt_name in text, qt_name
    # Same snippets, the same picture slot; the picture is the Qt window's own.
    blocks = lambda pages, kind: [b for p in pages for b in p["blocks"] if b[0] == kind]
    assert blocks(qt, "snippet") == blocks(desktop, "snippet")
    assert blocks(desktop, "image") == [("image", "resources/quickstart/chord_sheet.png")]
    assert blocks(qt, "image") == [("image", "resources/quickstart/chord_sheet_qt.png")]
    root = Path(__file__).resolve().parents[1]
    for _, path in blocks(qt, "image") + blocks(desktop, "image"):
        assert (root / path).is_file(), path


def test_qt_quick_start_keeps_the_desktop_texts_that_name_no_tk_control():
    desktop, qt = _texts(DESKTOP), _texts(DESKTOP_QT)
    shared = [t for t in desktop if t in qt]
    # The intro, detection, rich chords, directives, structure, sign-off...
    assert len(shared) == len(desktop) - 7
    assert any(t.startswith("Prefer solfège? Switch to European notation with the Do button")
               for t in shared)


@pytest.mark.parametrize("platform", [DESKTOP, ANDROID])
def test_the_other_platforms_quick_start_is_unchanged_by_the_qt_variant(platform):
    # Every Qt text is new: none replaced a Tk or Android one.
    qt_only = set(_texts(DESKTOP_QT)) - set(_texts(DESKTOP))
    assert not qt_only & set(_texts(platform))


def test_create_session_accepts_desktop_qt(tmp_path):
    from chordnotepad.services.appdata_service import AppDataService
    from chordnotepad.session.bootstrap import build_core_services, create_session
    from chordnotepad.session.host import HostDispatch
    from chordnotepad.session.testing import FakePlayer, InMemoryDocumentStore, ManualHost

    host = ManualHost()
    services = build_core_services(AppDataService(root=tmp_path), HostDispatch(host),
                                   player=FakePlayer())
    session = create_session(host, services, InMemoryDocumentStore(), chord_sheet=True,
                             platform=DESKTOP_QT)
    assert session._tracks_playhead
    session.shutdown()
