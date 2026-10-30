"""The toolbar through the session: ToolbarState and its commands.

The value logic (key list and spelling, multiplier parsing, snapping) lives in
``session.toolbar`` so every UI shares it; the session publishes one
``ToolbarState`` built from the viewmodel, whoever changed it.
"""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from services.playback_service import PlaybackService
from services.song_parser_service import SongParserService
from session import toolbar
from session.host import HostDispatch
from session.session import AppSession
from session.state import HighlightState, PlayAction, ToolbarState
from session.testing import EventRecorder, FakePlayer, InMemoryDocumentStore, ManualHost
from viewmodels.main_window_viewmodel import MainWindowViewModel
from viewmodels.text_editor_viewmodel import TextEditorViewModel


# -- pure value logic ------------------------------------------------------------


def test_key_options_per_notation():
    assert toolbar.key_options("american")[:3] == ("C", "C#", "Db")
    assert toolbar.key_options("european")[:3] == ("Do", "Do#", "Reb")
    assert len(toolbar.key_options("american")) == len(toolbar.key_options("european")) == 17
    with pytest.raises(ValueError):
        toolbar.key_options("klingon")


@pytest.mark.parametrize("key, notation, expected", [
    ("C", "european", "Do"), ("F#", "european", "Fa#"), ("Bb", "european", "Sib"),
    ("Sol", "american", "G"), ("Mib", "american", "Eb"),
])
def test_convert_key(key, notation, expected):
    assert toolbar.convert_key(key, notation) == expected


def test_shown_key_falls_back_to_the_first_option():
    assert toolbar.shown_key("G", "american") == "G"
    assert toolbar.shown_key(None, "american") == "C"
    assert toolbar.shown_key("", "european") == "Do"


@pytest.mark.parametrize("text, pct", [
    ("150", 150.0), ("150%", 150.0), ("1.5x", 150.0), (" 1.5 X ", 150.0),
    ("87.5", 87.5), ("0.5x", 50.0),
])
def test_parse_multiplier_pct(text, pct):
    assert toolbar.parse_multiplier_pct(text) == pct


@pytest.mark.parametrize("text", ["", "fast", "x", "%"])
def test_parse_multiplier_pct_rejects_garbage(text):
    with pytest.raises(ValueError):
        toolbar.parse_multiplier_pct(text)


def test_bpm_parse_and_format():
    assert toolbar.parse_bpm("119.6") == 120
    assert toolbar.format_bpm(96.0) == "96"
    assert toolbar.format_multiplier_pct(87.5) == "87.5"
    assert toolbar.format_multiplier_pct(150.0) == "150"


@pytest.mark.parametrize("pct", [12.5, 15, 35, 40, 60, 65, 98, 110, 115, 87.5, 33.3, 400])
def test_the_speed_keeps_any_value_in_range(pct):
    # Nothing downstream needs a grid (the scheduler takes any multiplier),
    # so a speed plays as set: the Android slider's 5 % stops included.
    assert toolbar.MULTIPLIER_SCALE.normalize(pct) == pct


def test_the_speed_is_clamped_and_drags_in_whole_percent():
    scale = toolbar.MULTIPLIER_SCALE
    assert scale.normalize(1000) == 400
    assert scale.normalize(0) == 12.5
    assert scale.stepped(100, 2) == 102
    assert scale.stepped(98, 1) == 99
    assert scale.stepped(13, -1) == 12.5


def test_scale_without_tolerance_is_a_strict_grid():
    scale = toolbar.ScrubScale(min_value=0, max_value=10, step=2)
    assert scale.normalize(2.9) == 2
    assert scale.normalize(3.1) == 4
    assert scale.stepped(4, -1) == 2
    assert toolbar.ScrubScale(0, 10, step=0).normalize(3.3) == 3.3


def test_normalize_bpm():
    assert toolbar.normalize_bpm(121) == 120   # magnetic to tens within 1
    assert toolbar.normalize_bpm(125) == 125
    assert toolbar.normalize_bpm(900) == 400
    assert toolbar.normalize_bpm(5) == 20


# -- the session ------------------------------------------------------------------


class FakeConfig:
    """Dict-backed stand-in for ConfigService."""

    def __init__(self, **values):
        self._values = dict(values)

    def get(self, key, default=None):
        return self._values.get(key, default)

    def set(self, key, value):
        self._values[key] = value


class Env:
    """A started session over the real viewmodels and a FakePlayer."""

    def __init__(self, text="", **config):
        self.host = ManualHost()
        dispatch = HostDispatch(self.host)
        self.config = FakeConfig(**config)
        self.player = FakePlayer(auto_play=False)
        self.audio = PlaybackService(self.config, player=self.player, application=dispatch)
        self.store = InMemoryDocumentStore()
        self.main = MainWindowViewModel(
            self.config, self.audio, self.store, SongParserService(), dispatch)
        self.session = AppSession(
            self.host, main_window_viewmodel=self.main,
            text_editor_viewmodel=TextEditorViewModel(SongParserService()))
        self.recorder = EventRecorder()
        self.session.subscribe(self.recorder)
        self.session.start()
        if text:
            self.session.set_text(text)
            self.host.advance(0.5)

    def toolbar(self) -> ToolbarState:
        return self.recorder.last(ToolbarState)

    def play(self):
        self.session.play_pause()
        self.audio._render_thread.join(timeout=10)
        self.host.run_pending()


def test_initial_state_comes_from_the_config():
    env = Env(bpm=96, bpm_multiplier=1.5, key="Sol", notation="european",
              time_signature_beats=3, time_signature_unit=8)
    assert env.toolbar() == ToolbarState(
        notation="european", bpm=96, bpm_display=96, bpm_editable=True,
        multiplier_pct=150.0, key="Sol", key_options=toolbar.key_options("european"),
        beats=3, unit=8, metronome=False, play_action=PlayAction.PLAY)


def test_set_bpm_snaps_like_the_scrubber_and_saves():
    env = Env()
    env.session.set_bpm(131)
    assert env.toolbar().bpm == 130
    assert env.main.bpm == 130
    assert env.config.get("bpm") == 130
    assert env.player.bpm == 130
    env.session.set_bpm(1000)
    assert env.toolbar().bpm == 400


def test_set_bpm_is_ignored_while_playing():
    env = Env("C G")
    env.play()
    env.session.set_bpm(90)
    assert env.main.bpm == 120
    assert env.toolbar().bpm_editable is False


def test_set_multiplier_applies_during_playback():
    env = Env("C G")
    env.play()
    env.recorder.clear()
    env.session.set_multiplier_pct(110)
    assert [t.multiplier_pct for t in env.recorder.of_type(ToolbarState)] == [110.0]
    assert env.player.bpm_multiplier == 1.1
    assert env.config.get("bpm_multiplier") == 1.1


@pytest.mark.parametrize("text, pct", [("35", 35.0), ("115%", 115.0), ("0.375x", 37.5)])
def test_a_typed_speed_plays_as_typed(text, pct):
    env = Env("C G")
    env.session.set_multiplier_text(text)
    assert env.toolbar().multiplier_pct == pct
    assert env.player.bpm_multiplier == pct / 100


def test_set_key():
    env = Env("I IV V")
    env.session.set_key("D")
    assert env.toolbar().key == "D"
    assert env.main.key == "D"
    env.session.set_key("")
    assert env.main.key is None
    assert env.toolbar().key == "C"  # shown as the first option


def test_set_time_signature_and_invalid_values():
    env = Env()
    env.session.set_time_signature(6, 8)
    assert (env.toolbar().beats, env.toolbar().unit) == (6, 8)
    env.recorder.clear()
    env.session.set_time_signature(6, 3)  # not a beat unit: ignored
    assert env.recorder.items == []
    assert env.main.time_signature_unit == 8


def test_toggle_metronome():
    env = Env()
    env.session.toggle_metronome()
    assert env.toolbar().metronome is True
    assert env.player.metronome_enabled is True
    env.session.toggle_metronome()
    assert env.toolbar().metronome is False


def test_set_notation_respells_the_key_and_redetects():
    env = Env("Do Re", key="G")
    assert env.recorder.last(HighlightState).spans == ()
    env.recorder.clear()

    env.session.set_notation("european")

    kinds = [type(item).__name__ for item in env.recorder.items]
    assert kinds == ["HighlightState", "EditorState", "ToolbarState", "SongDefaultsState"]
    assert len(env.recorder.last(HighlightState).spans) == 2
    state = env.toolbar()
    assert (state.notation, state.key) == ("european", "Sol")
    assert state.key_options == toolbar.key_options("european")
    assert env.main.key == "Sol"
    assert env.config.get("notation") == "european"


def test_set_notation_rejects_unknown_ones():
    env = Env()
    with pytest.raises(ValueError):
        env.session.set_notation("klingon")


def test_convert_sends_the_edit_first_then_its_highlight_and_the_toolbar():
    env = Env("C G", key="F")
    env.recorder.clear()
    env.session.convert_notation("european")
    kinds = [type(item).__name__ for item in env.recorder.items]
    assert kinds == ["TextEdited", "HighlightState", "EditorState", "ToolbarState",
                     "SongDefaultsState", "StatusState"]
    assert env.toolbar().key == "Fa"


def test_open_file_directives_reach_the_toolbar():
    env = Env()
    ref = env.store.ref("song.txt")
    env.store.contents[ref.id] = "{bpm: 90} {key: D} {time: 3/4}\nC G"
    env.main.open_file(ref)
    state = env.toolbar()
    assert (state.bpm, state.key, state.beats, state.unit) == (90, "D", 3, 4)


def test_whole_song_transpose_moves_the_toolbar_key():
    env = Env("C G", key="C")
    env.session.transpose(2, None)
    assert env.toolbar().key == "D"


# -- the Tk toolbar maps the state ---------------------------------------------------


def test_tk_toolbar_maps_the_state():
    from ui.main_window import MainWindow

    window = SimpleNamespace(
        update_notation_buttons=Mock(), bpm_scrubber=Mock(), multiplier_scrubber=Mock(),
        key_combo={}, key_var=Mock(), time_sig_beats_var=Mock(), time_sig_unit_var=Mock(),
        _refresh_metronome_button=Mock(), play_pause_button=Mock(),
        _icon_play="play", _icon_pause="pause", _play_pause_tooltip=SimpleNamespace(text=""))
    playing = ToolbarState(
        notation="european", bpm=120, bpm_display=96, bpm_editable=False,
        multiplier_pct=150.0, key="Sol", key_options=toolbar.key_options("european"),
        beats=3, unit=4, metronome=True, play_action=PlayAction.PAUSE)

    MainWindow._apply_toolbar(window, playing)

    assert window._notation == "european"
    window.bpm_scrubber.set_readonly.assert_called_with(True)
    window.bpm_scrubber.set_value.assert_called_with(120)
    window.bpm_scrubber.set_display_text.assert_called_with("96")
    window.multiplier_scrubber.set_value.assert_called_with(150.0)
    assert window.key_combo["values"] == toolbar.key_options("european")
    window.key_var.set.assert_called_with("Sol")
    window.time_sig_beats_var.set.assert_called_with(3)
    window._refresh_metronome_button.assert_called_with(True)
    window.play_pause_button.config.assert_called_with(image="pause")
    assert window._play_pause_tooltip.text == "Pause playback"

    window.bpm_scrubber.reset_mock()
    MainWindow._apply_toolbar(window, ToolbarState(
        notation="american", bpm=120, bpm_display=120, bpm_editable=True,
        multiplier_pct=100.0, key="C", key_options=toolbar.key_options("american"),
        beats=4, unit=4, metronome=False, play_action=PlayAction.RESUME))
    window.bpm_scrubber.set_readonly.assert_called_with(False)
    window.bpm_scrubber.set_display_text.assert_not_called()
    window.play_pause_button.config.assert_called_with(image="play")
    assert window._play_pause_tooltip.text == "Resume playback"


def test_tk_toolbar_sends_commands():
    from ui.main_window import MainWindow

    window = SimpleNamespace(session=Mock(), key_var=Mock(), time_sig_beats_var=Mock(),
                             time_sig_unit_var=Mock())
    window.key_var.get.return_value = "D"
    MainWindow.on_key_change(window)
    window.session.set_key.assert_called_once_with("D")

    window.time_sig_beats_var.get.return_value = 6
    window.time_sig_unit_var.get.return_value = 8
    MainWindow.on_time_signature_change(window)
    window.session.set_time_signature.assert_called_once_with(6, 8)

    MainWindow._on_multiplier_scrubber_change(window, 150.0)
    window.session.set_multiplier_pct.assert_called_once_with(150.0)
    MainWindow._on_bpm_scrubber_change(window, 96.0)
    window.session.set_bpm.assert_called_once_with(96.0)
    MainWindow.set_notation(window, "european")
    window.session.set_notation.assert_called_once_with("european")
