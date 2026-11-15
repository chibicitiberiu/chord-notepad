"""The song values' and the transport's tooltips (session/toolbar_texts.py):
the desktop's defaults, which the Qt player bar shows, and its own play text."""

from chordnotepad.session import toolbar_texts
from chordnotepad.session.platform import ANDROID, DESKTOP, DESKTOP_QT
from chordnotepad.session.state import PlayAction


def test_the_desktop_texts_are_unchanged():
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

