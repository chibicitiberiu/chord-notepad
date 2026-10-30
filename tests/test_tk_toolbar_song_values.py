"""The desktop toolbar shows the song's own tempo, time signature and key.

``MainWindow._apply_toolbar`` maps a ``ToolbarState``: a value the song sets
with a directive is shown greyed out and can't be changed, with a tooltip
naming the directive. The window method runs unbound against stand-ins, so
no widget is built.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

from session import toolbar
from session.state import PlayAction, ToolbarState


def _state(**changes):
    values = dict(
        notation="american", bpm=110, bpm_display=110, bpm_editable=True,
        multiplier_pct=100.0, key="C", key_options=toolbar.key_options("american"),
        beats=3, unit=4, metronome=False, play_action=PlayAction.PLAY)
    values.update(changes)
    return ToolbarState(**values)


def _window():
    return SimpleNamespace(
        update_notation_buttons=Mock(), bpm_scrubber=Mock(), multiplier_scrubber=Mock(),
        key_combo=MagicMock(), key_var=Mock(), time_sig_beats_var=Mock(),
        time_sig_unit_var=Mock(), time_sig_beats_spin=Mock(), time_sig_unit_spin=Mock(),
        _refresh_metronome_button=Mock(), play_pause_button=Mock(),
        _play_pause_tooltip=SimpleNamespace(text=""), _icon_play="play", _icon_pause="pause",
        _bpm_tooltip=SimpleNamespace(text=""), _key_tooltip=SimpleNamespace(text=""),
        _beats_tooltip=SimpleNamespace(text=""), _unit_tooltip=SimpleNamespace(text=""))


def _apply(window, state):
    from ui.main_window import MainWindow

    MainWindow._apply_toolbar(window, state)


def test_values_the_song_sets_are_greyed_out_with_the_directive_in_the_tooltip():
    window = _window()
    _apply(window, _state(bpm=70, bpm_display=70, bpm_editable=False, key="D", beats=6, unit=8,
                          bpm_set_by="{bpm: 70}", time_set_by="{time: 6/8}",
                          key_set_by="{key: D}"))
    window.bpm_scrubber.set_readonly.assert_called_with(True)
    window.bpm_scrubber.set_value.assert_called_with(70)
    window.bpm_scrubber.set_display_text.assert_called_with("70")
    window.key_var.set.assert_called_with("D")
    window.key_combo.configure.assert_called_with(state="disabled")
    window.time_sig_beats_var.set.assert_called_with(6)
    window.time_sig_unit_var.set.assert_called_with(8)
    window.time_sig_beats_spin.configure.assert_called_with(state="disabled")
    window.time_sig_unit_spin.configure.assert_called_with(state="disabled")
    assert window._bpm_tooltip.text == "Set by {bpm: 70} in the song"
    assert window._key_tooltip.text == "Set by {key: D} in the song"
    assert window._beats_tooltip.text == "Set by {time: 6/8} in the song"
    assert window._unit_tooltip.text == "Set by {time: 6/8} in the song"


def test_values_the_song_does_not_set_are_editable_again():
    window = _window()
    _apply(window, _state(bpm_set_by="{bpm: 70}", key_set_by="{key: D}",
                          time_set_by="{time: 6/8}", bpm_editable=False))
    _apply(window, _state())
    window.bpm_scrubber.set_readonly.assert_called_with(False)
    window.key_combo.configure.assert_called_with(state="readonly")
    window.time_sig_beats_spin.configure.assert_called_with(state="normal")
    window.time_sig_unit_spin.configure.assert_called_with(state="normal")
    for tooltip in (window._bpm_tooltip, window._key_tooltip, window._beats_tooltip,
                    window._unit_tooltip):
        assert "Set by" not in tooltip.text and tooltip.text


def test_only_the_values_the_song_sets_are_locked():
    window = _window()
    _apply(window, _state(key="G", key_set_by="{key: G}"))
    window.bpm_scrubber.set_readonly.assert_called_with(False)
    window.key_combo.configure.assert_called_with(state="disabled")
    window.time_sig_beats_spin.configure.assert_called_with(state="normal")


def test_while_playing_the_tempo_shows_the_live_value():
    window = _window()
    _apply(window, _state(bpm=90, bpm_display=140, bpm_editable=False,
                          bpm_set_by="{bpm: 90}", play_action=PlayAction.PAUSE))
    window.bpm_scrubber.set_value.assert_called_with(90)
    window.bpm_scrubber.set_display_text.assert_called_with("140")
