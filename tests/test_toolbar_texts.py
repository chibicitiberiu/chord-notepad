"""The song values' and the transport's tooltips, shared by the Tk toolbar
and the Qt player bar (session/toolbar_texts.py)."""

from chordnotepad.session import toolbar_texts
from chordnotepad.session.platform import ANDROID, DESKTOP, DESKTOP_QT
from chordnotepad.session.state import PlayAction


def test_the_tk_texts_are_unchanged():
    assert toolbar_texts.set_by_tooltip("{bpm: 90}") == "Set by {bpm: 90} in the song"
    assert toolbar_texts.play_pause_tooltip(PlayAction.PLAY) == (
        "Play from start (Shift+Click to play from cursor)")
    assert toolbar_texts.play_pause_tooltip(PlayAction.PAUSE, DESKTOP) == "Pause playback"
    assert toolbar_texts.play_pause_tooltip(PlayAction.RESUME) == "Resume playback"
    assert toolbar_texts.STOP_TOOLTIP == "Stop playback"
    assert toolbar_texts.BPM_TOOLTIP.startswith("Beats per minute for this song")


def test_the_qt_play_button_plays_from_the_playhead():
    assert toolbar_texts.play_pause_tooltip(PlayAction.PLAY, DESKTOP_QT) == (
        "Play from the playhead (Shift+Click to play from cursor)")
    assert toolbar_texts.play_pause_tooltip("pause", DESKTOP_QT) == "Pause playback"
    # Other platforms fall back to the desktop's.
    assert toolbar_texts.play_pause_tooltip(PlayAction.PLAY, ANDROID) == (
        toolbar_texts.play_pause_tooltip(PlayAction.PLAY))


def test_the_tk_window_shows_the_shared_texts():
    from chordnotepad_tk import main_window
    assert main_window._BPM_TOOLTIP is toolbar_texts.BPM_TOOLTIP
    assert main_window._PLAY_PAUSE_TOOLTIPS[PlayAction.PLAY] == (
        "Play from start (Shift+Click to play from cursor)")
