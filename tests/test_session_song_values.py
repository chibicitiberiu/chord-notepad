"""The Settings defaults vs. the open song's own tempo, time signature and key.

The defaults (Settings: default tempo, time signature, key) live in the
config and only Settings changes them. The toolbar (desktop) and Song
defaults (Android) show what the song starts with: a value the song sets
with a directive before its first chord is shown as the song's and can't be
changed from the UI; any other value can be changed for the current document
only, and New/Open start again from the defaults.
"""

import pytest

from services.playback_service import PlaybackService
from services.song_parser_service import SongParserService
from session.events import ConfirmDiscardRequest, DiscardChoice
from session.host import HostDispatch
from session.session import AppSession
from session.state import PlaybackStatus, SongDefaultsState, ToolbarState
from session.testing import EventRecorder, FakePlayer, InMemoryDocumentStore, ManualHost
from viewmodels.main_window_viewmodel import MainWindowViewModel
from viewmodels.settings_viewmodel import SettingsChanges
from viewmodels.text_editor_viewmodel import TextEditorViewModel

SONG = "{bpm: 70} {time: 6/8} {key: D}\nD G A\n"
DEFAULTS = dict(bpm=110, time_signature_beats=3, time_signature_unit=4, key="C")


class FakeConfig:
    """Dict-backed stand-in for ConfigService that counts writes."""

    def __init__(self, **values):
        self.values = dict(values)
        self.writes = []

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.writes.append(key)
        self.values[key] = value


class Env:
    """A started session over an in-memory store and a silent FakePlayer."""

    def __init__(self, text="", documents=None, auto_play=False, **config):
        self.host = ManualHost()
        dispatch = HostDispatch(self.host)
        self.config = FakeConfig(**{**DEFAULTS, **config})
        self.player = FakePlayer(auto_play=auto_play)
        self.audio = PlaybackService(self.config, player=self.player, application=dispatch)
        self.store = InMemoryDocumentStore({"song.txt": SONG} if documents is None else documents)
        self.main = MainWindowViewModel(
            self.config, self.audio, self.store, SongParserService(), dispatch)
        self.session = AppSession(
            self.host, main_window_viewmodel=self.main,
            text_editor_viewmodel=TextEditorViewModel(SongParserService()))
        self.recorder = EventRecorder()
        self.session.subscribe(self.recorder)
        self.session.start()
        if text:
            self.type(text)

    def type(self, text):
        self.session.set_text(text)
        self.host.advance(0.5)

    def discard(self):
        """Answer "discard" if the session asks about unsaved changes."""
        request = self.session.pending_request
        if isinstance(request, ConfirmDiscardRequest):
            self.session.respond(request.request_id, DiscardChoice.DISCARD.value)

    def new(self):
        self.session.new_document()
        self.discard()

    def open(self, name="song.txt"):
        self.session.open_document(self.store.ref(name))
        self.discard()

    def toolbar(self) -> ToolbarState:
        return self.recorder.last(ToolbarState)

    def defaults(self) -> SongDefaultsState:
        return self.recorder.last(SongDefaultsState)

    def saved_defaults(self):
        c = self.config.values
        return (c["bpm"], c["time_signature_beats"], c["time_signature_unit"], c["key"])

    def shown(self):
        t = self.toolbar()
        return (t.bpm, t.beats, t.unit, t.key)

    def play(self):
        self.session.play_pause()
        self.audio._render_thread.join(timeout=10)
        self.host.run_pending()


# -- opening a song leaves the defaults alone -----------------------------------------


def test_opening_a_song_does_not_change_the_defaults():
    env = Env()
    env.open()
    assert env.saved_defaults() == (110, 3, 4, "C")
    assert not {"bpm", "time_signature_beats", "time_signature_unit", "key"} & set(env.config.writes)
    # The toolbar shows what the song starts with.
    assert env.shown() == (70, 6, 8, "D")


def test_new_after_opening_starts_from_the_defaults():
    env = Env()
    env.open()
    env.new()
    assert env.shown() == (110, 3, 4, "C")
    t = env.toolbar()
    assert (t.bpm_set_by, t.time_set_by, t.key_set_by) == (None, None, None)
    assert t.bpm_editable is True
    assert env.defaults().summary == "110 · 3/4 · C"


def test_the_first_directive_anywhere_no_longer_sets_the_toolbar():
    # A tempo set after the first chord doesn't set the starting tempo: the
    # song starts at the default.
    env = Env(documents={"late.txt": "C G\n{bpm: 140}\nF C\n"})
    env.open("late.txt")
    assert env.main.bpm == 110
    assert env.toolbar().bpm == 110
    assert env.toolbar().bpm_set_by is None
    assert env.config.values["bpm"] == 110


# -- a temporary change is for the current document only ----------------------------------


def test_a_temporary_change_is_not_saved_to_the_defaults():
    env = Env("C G")
    env.session.set_bpm(90)
    env.session.set_time_signature(6, 8)
    env.session.set_key("G")
    assert env.shown() == (90, 6, 8, "G")
    assert env.saved_defaults() == (110, 3, 4, "C")
    assert not {"bpm", "time_signature_beats", "time_signature_unit", "key"} & set(env.config.writes)


def test_new_and_open_drop_a_temporary_change():
    env = Env("C G", documents={"song.txt": SONG, "plain.txt": "Am F\n"})
    env.session.set_bpm(90)
    env.session.set_key("G")
    env.new()
    assert env.shown() == (110, 3, 4, "C")

    env.session.set_bpm(150)
    env.session.set_time_signature(2, 4)
    env.open("plain.txt")
    assert env.shown() == (110, 3, 4, "C")


def test_a_temporary_change_plays():
    env = Env("C G")
    env.session.set_bpm(90)
    env.play()
    assert env.toolbar().bpm_display == 90


def test_the_defaults_are_in_the_current_notation():
    env = Env(notation="european", key="G")
    env.new()
    assert env.main.key == "Sol"
    assert env.toolbar().key == "Sol"


# -- values the song sets are the song's ---------------------------------------------------


def test_values_the_song_sets_are_locked():
    env = Env()
    env.open()
    t = env.toolbar()
    assert (t.bpm_set_by, t.time_set_by, t.key_set_by) == ("{bpm: 70}", "{time: 6/8}", "{key: D}")
    assert t.bpm_editable is False
    env.session.set_bpm(100)
    env.session.set_bpm_text("100")
    env.session.reset_bpm()
    env.session.set_time_signature(4, 4)
    env.session.set_key("G")
    assert env.shown() == (70, 6, 8, "D")
    assert (env.main.bpm, env.main.key) == (110, "C")


def test_a_value_the_song_does_not_set_stays_editable():
    env = Env("{key: G}\nG D")
    t = env.toolbar()
    assert (t.bpm_set_by, t.time_set_by, t.key_set_by) == (None, None, "{key: G}")
    assert t.bpm_editable is True
    env.session.set_bpm(90)
    env.session.set_time_signature(6, 8)
    assert env.shown() == (90, 6, 8, "G")


def test_the_lock_follows_the_text():
    env = Env("C G")
    env.session.set_bpm(90)
    env.type("{bpm: 75}\nC G")
    assert (env.toolbar().bpm, env.toolbar().bpm_set_by) == (75, "{bpm: 75}")
    env.type("C G")
    # The temporary value comes back once the song stops setting it.
    assert (env.toolbar().bpm, env.toolbar().bpm_set_by) == (90, None)


def test_a_mid_song_change_shows_the_starting_value():
    env = Env("{bpm: 90} {time: 3/4}\nC G\n{bpm: 140} {time: 4/4} {key: A}\nD A")
    t = env.toolbar()
    assert (t.bpm, t.beats, t.unit) == (90, 3, 4)
    assert (t.bpm_set_by, t.time_set_by) == ("{bpm: 90}", "{time: 3/4}")
    # The key changes only later: the song starts in the default key.
    assert (t.key, t.key_set_by) == ("C", None)


def test_a_relative_starting_tempo_shows_its_result():
    env = Env("{bpm: +20}\nC G")
    assert (env.toolbar().bpm, env.toolbar().bpm_set_by) == (130, "{bpm: +20}")


def test_toolbar_and_song_defaults_agree():
    env = Env("{bpm: 90} {time: 3/4}\nC G\n{bpm: 140}\nD A")
    d, t = env.defaults(), env.toolbar()
    assert d.tempo.value == str(t.bpm) and d.tempo.from_directive == (t.bpm_set_by is not None)
    assert d.time.value == f"{t.beats}/{t.unit}"
    assert d.key.from_directive == (t.key_set_by is not None)


# -- playback ---------------------------------------------------------------------------


def test_while_playing_the_tempo_follows_the_song_then_returns_to_its_start():
    env = Env("{bpm: 90}\nC G\n{bpm: 140}\nD A", auto_play=True)
    env.session.play_pause()
    env.audio._render_thread.join(timeout=10)
    env.host.run_pending()
    displays = [t.bpm_display for t in env.recorder.of_type(ToolbarState)]
    assert 140 in displays
    assert env.session._playback.status is PlaybackStatus.IDLE
    assert (env.toolbar().bpm, env.toolbar().bpm_display) == (90, 90)


def test_write_into_song_uses_the_current_values():
    env = Env("{key: G}\nG D")
    env.session.set_bpm(90)
    env.session.write_song_defaults()
    assert env.session.text == "{bpm: 90} {time: 3/4}\n{key: G}\nG D"
    t = env.toolbar()
    assert (t.bpm_set_by, t.time_set_by, t.key_set_by) == ("{bpm: 90}", "{time: 3/4}", "{key: G}")
    assert env.saved_defaults() == (110, 3, 4, "C")


# -- Settings is what changes the defaults --------------------------------------------------


def test_settings_change_the_defaults_for_the_next_new_document():
    env = Env("C G")
    env.config.values.update(bpm=95, key="E")
    env.session.apply_settings(SettingsChanges(general_changed=True))
    env.new()
    assert (env.toolbar().bpm, env.toolbar().key) == (95, "E")


@pytest.mark.parametrize("command, args", [
    ("set_bpm", (90,)), ("set_time_signature", (6, 8)), ("set_key", ("G",)),
])
def test_toolbar_commands_do_not_write_the_defaults_even_after_playing(command, args):
    env = Env("C G")
    getattr(env.session, command)(*args)
    env.play()
    assert env.saved_defaults() == (110, 3, 4, "C")
