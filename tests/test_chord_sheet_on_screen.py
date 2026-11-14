"""The chord sheet on screen, apart from shown (plan step B3).

``chord_sheet_visible`` is the persisted choice: the Tk strip, Android's
sheet, the Qt Edit panel's F9. Whether the sheet is on screen is transient:
the Qt Play workspace always shows its strip, and a minimized window shows
nothing. Rendering follows "on screen", so the Qt timeline gets its
sections in Play with F9 off; with nothing said (the Tk strip), on screen is
shown, exactly as before.
"""

import pytest

from chordnotepad.models.rendered_song import RenderedSong
from chordnotepad.services.playback_service import PlaybackService
from chordnotepad.services.song_parser_service import SongParserService
from chordnotepad.session.host import HostDispatch
from chordnotepad.session.platform import DESKTOP, DESKTOP_QT
from chordnotepad.session.session import AppSession
from chordnotepad.session.state import ChordSheetState, PlaybackState, TimelineSection
from chordnotepad.session.testing import (
    EventRecorder, FakeChordSheet, FakePlayer, InMemoryDocumentStore, ManualHost,
)
from chordnotepad.viewmodels.chord_sheet_viewmodel import ChordSheetViewModel
from chordnotepad.viewmodels.main_window_viewmodel import MainWindowViewModel
from chordnotepad.viewmodels.text_editor_viewmodel import TextEditorViewModel
from tests.test_chord_sheet_playhead import FakeConfig
from tests.test_chord_sheet_viewmodel import make_chord, make_vm
from tests.test_chord_sheet_viewmodel import FakeConfig as SheetConfig


def hidden_vm():
    song = RenderedSong(chords=[make_chord("C")])
    return make_vm(rendered=song, config=SheetConfig(chord_sheet_visible=False))


def test_on_screen_follows_visible_until_told_otherwise():
    vm, _, _ = hidden_vm()
    assert (vm.visible, vm.on_screen) == (False, False)
    vm.set_visible(True)
    assert vm.on_screen is True
    vm.set_on_screen(False)
    assert (vm.visible, vm.on_screen) == (True, False)
    vm.set_on_screen(None)
    assert vm.on_screen is True
    vm.set_visible(False)
    vm.set_on_screen(True)
    assert (vm.visible, vm.on_screen) == (False, True)


def test_on_screen_renders_while_hidden_and_isnt_persisted():
    vm, audio, scheduler = hidden_vm()
    config = vm._config
    vm.set_song([], "A")
    assert scheduler.pending is None and audio.render_calls == []
    vm.set_on_screen(True)              # the Play workspace
    scheduler.flush()
    assert audio.render_calls == [([], "A")]
    assert vm.rendered_song is not None
    vm.set_song([], "B")                # an edit while on screen renders too
    scheduler.flush()
    assert audio.render_calls[-1] == ([], "B")
    assert config.get("chord_sheet_visible") is False
    assert "chord_sheet_on_screen" not in config._values


def test_off_screen_holds_renders_back_even_while_shown():
    vm, audio, scheduler = make_vm(rendered=RenderedSong(chords=[make_chord("C")]))
    vm.set_on_screen(False)             # a minimized window
    vm.set_song([], "A")
    vm.set_song([], "B")
    assert scheduler.pending is None and audio.render_calls == []
    vm.set_on_screen(None)              # back: it is shown, so it renders once
    scheduler.flush()
    assert audio.render_calls == [([], "B")]


def test_going_off_screen_mid_render_drops_the_result():
    holder = {}
    song = RenderedSong(chords=[make_chord("C")])

    class Audio:
        def play_notes_immediate(self, notes):
            pass

        def render_song(self, lines, key, should_abort=None, private_picker=False):
            holder["vm"].set_on_screen(False)
            assert should_abort() is True
            return song

    vm, _, scheduler = make_vm(audio=Audio())
    holder["vm"] = vm
    vm.set_song([], "C")
    scheduler.flush()
    assert vm.rendered_song is None
    vm.set_on_screen(None)              # on screen again: the dropped input renders again
    assert scheduler.pending is not None


def test_saying_the_same_thing_again_does_not_restart_the_debounce():
    vm, audio, scheduler = make_vm(rendered=RenderedSong(chords=[make_chord("C")]))
    vm.set_song([], "A")
    pending = scheduler.pending
    vm.set_on_screen(True)              # was on screen already (shown)
    assert scheduler.pending is pending


# -- through the session ---------------------------------------------------------------


SONG = "{label: verse}\nC   G\n{label: chorus}\nAm  F\n"


class Env:
    """A Qt session with the real sheet, hidden in the config (F9 off)."""

    def __init__(self, platform=DESKTOP_QT):
        self.host = ManualHost()
        dispatch = HostDispatch(self.host)
        self.config = FakeConfig(chord_sheet_visible=False)
        self.audio = PlaybackService(self.config, player=FakePlayer(auto_play=False),
                                     application=dispatch)
        parser = SongParserService()
        main = MainWindowViewModel(self.config, self.audio, InMemoryDocumentStore(), parser,
                                   dispatch)
        self.sheet = ChordSheetViewModel(self.config, self.audio, host=self.host,
                                         executor=lambda fn: fn(), platform=platform)
        self.session = AppSession(self.host, main_window_viewmodel=main,
                                  text_editor_viewmodel=TextEditorViewModel(parser),
                                  chord_sheet_viewmodel=self.sheet, platform=platform)
        self.recorder = EventRecorder()
        self.session.subscribe(self.recorder)
        self.session.start()

    def type(self, text):
        self.session.set_text(text)
        self.host.advance(2.0)


def test_the_play_workspace_gets_its_timeline_sections_with_f9_off():
    env = Env()
    env.type(SONG)
    assert env.sheet.rendered_song is None          # Edit, F9 off: nothing renders
    assert env.recorder.last(PlaybackState).sections == ()
    env.session.set_chord_sheet_on_screen(True)     # the Play tab
    env.host.advance(2.0)
    assert env.recorder.last(PlaybackState).sections == (
        TimelineSection("verse", 1, 2, False), TimelineSection("chorus", 3, 4, False))
    assert env.recorder.last(ChordSheetState).visible is False
    assert env.config.get("chord_sheet_visible") is False
    # Back in Edit with F9 off, edits wait again.
    env.session.set_chord_sheet_on_screen(None)
    revision = env.recorder.last(ChordSheetState).song_revision
    env.type(SONG + "{label: coda}\nD\n")
    assert env.recorder.last(ChordSheetState).song_revision == revision


def test_the_tk_strip_still_renders_only_while_shown():
    env = Env(platform=DESKTOP)
    env.type(SONG)
    assert env.sheet.rendered_song is None
    env.session.set_chord_sheet_visible(True)
    env.host.advance(2.0)
    assert env.sheet.rendered_song is not None
    env.session.set_chord_sheet_visible(False)
    revision = env.recorder.last(ChordSheetState).song_revision
    env.type("D E")
    assert env.recorder.last(ChordSheetState).song_revision == revision
    assert env.config.get("chord_sheet_visible") is False


@pytest.mark.parametrize("value", [True, False, None])
def test_the_session_passes_on_screen_to_the_sheet(value):
    host = ManualHost()
    sheet = FakeChordSheet()
    session = AppSession(host, main_window_viewmodel=MainWindowViewModel(
        FakeConfig(), PlaybackService(FakeConfig(), player=FakePlayer()), InMemoryDocumentStore(),
        SongParserService(), HostDispatch(host)),
        text_editor_viewmodel=TextEditorViewModel(SongParserService()),
        chord_sheet_viewmodel=sheet, platform=DESKTOP_QT)
    session.start()
    session.set_chord_sheet_on_screen(value)
    assert sheet.on_screen_override is value
