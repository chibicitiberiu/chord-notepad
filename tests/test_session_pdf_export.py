"""AppSession.export_pdf: the picker, the pages it asks a front end to paint,
and what the answer says.

The session runs on a ManualHost over the real parser and viewmodels; the
front end is the test, answering PickDocumentRequest and PaintPdfRequest.
"""

import pytest

from chordnotepad.services.playback_service import PlaybackService
from chordnotepad.services.song_parser_service import SongParserService
from chordnotepad.session import formatting, print_layout
from chordnotepad.session.events import PaintPdfRequest, PickDocumentRequest, PickMode, UserError
from chordnotepad.session.host import HostDispatch
from chordnotepad.session.session import AppSession
from chordnotepad.session.state import StatusState
from chordnotepad.session.testing import EventRecorder, FakePlayer, InMemoryDocumentStore, ManualHost
from chordnotepad.session.workers import BackgroundWorker
from chordnotepad.viewmodels.main_window_viewmodel import MainWindowViewModel
from chordnotepad.viewmodels.text_editor_viewmodel import TextEditorViewModel

SONG = "{key: A} {time: 4/4} {bpm: 200}\nA D E\nHello there\n"


class FakeConfig:
    def __init__(self, **values):
        self._values = dict(values)

    def get(self, key, default=None):
        return self._values.get(key, default)

    def set(self, key, value):
        self._values[key] = value


class Env:
    def __init__(self, tmp_path, text=SONG, platform="desktop"):
        self.host = ManualHost()
        dispatch = HostDispatch(self.host)
        self.config = FakeConfig()
        self.audio = PlaybackService(self.config, player=FakePlayer(auto_play=False),
                                     application=dispatch)
        self.store = InMemoryDocumentStore({"song.txt": SONG})
        self.main = MainWindowViewModel(
            self.config, self.audio, self.store, SongParserService(), dispatch)
        self.session = AppSession(
            self.host, main_window_viewmodel=self.main,
            text_editor_viewmodel=TextEditorViewModel(SongParserService()),
            worker=BackgroundWorker(self.host),
            audio_export_worker=BackgroundWorker(self.host, name="AudioExport"),
            export_temp_dir=str(tmp_path), platform=platform)
        self.recorder = EventRecorder()
        self.session.subscribe(self.recorder)
        self.session.start()
        if text:
            self.session.set_text(text)
            self.host.advance(0.5)
        self.recorder.clear()

    def pending(self, request_type):
        pending = self.session._flows.pending_request_id
        found = [r for r in self.recorder.of_type(request_type) if r.request_id == pending]
        assert found, f"no pending {request_type.__name__} (recorded: {self.recorder.compact()})"
        return found[0]

    def pick(self, name="out.pdf"):
        """Answer the picker with ``name``; the paint request that follows."""
        request = self.pending(PickDocumentRequest)
        self.session.respond(request.request_id, self.store.ref(name))
        return self.pending(PaintPdfRequest)

    def status(self):
        return self.session._emitter.state(StatusState).text

    def errors(self):
        return [(e.title, e.message) for e in self.recorder.of_type(UserError)]


@pytest.fixture
def env(tmp_path):
    env = Env(tmp_path)
    yield env
    env.session.shutdown()


def test_export_asks_for_a_pdf_named_after_the_song(tmp_path):
    env = Env(tmp_path, text="")
    env.session.open_document(env.store.ref("song.txt"))
    env.recorder.clear()
    env.session.export_pdf("a4")
    request = env.pending(PickDocumentRequest)
    assert (request.mode, request.suggested_name) == (PickMode.EXPORT_PDF, "song.pdf")
    env.session.shutdown()


def test_an_untitled_song_suggests_its_first_lyric_line(tmp_path):
    env = Env(tmp_path, text="C G\nAmazing grace\n")
    env.session.export_pdf("a4")
    assert env.pending(PickDocumentRequest).suggested_name == "Amazing grace.pdf"
    env.session.shutdown()


def test_the_picked_file_gets_the_pages_of_the_song(env):
    env.session.export_pdf("letter")
    request = env.pick()
    assert request.ref == env.store.ref("out.pdf")
    layout = request.layout
    assert layout == print_layout.layout_song(SONG, "american", "Hello there", "letter")
    assert (layout.page_width, layout.page_height) == (612.0, 792.0)
    first = layout.pages[0].lines[0].runs[0]
    assert (first.text, first.dim) == ("Key: A | Time: 4/4 | BPM: 200", True)
    # Nothing written by the session: the front end writes the file.
    assert "memory:out.pdf" not in env.store.contents


def test_the_title_is_the_document_name(tmp_path):
    env = Env(tmp_path, text="")
    env.session.open_document(env.store.ref("song.txt"))
    env.session.export_pdf("a4")
    assert env.pick().layout.title == "song"
    env.session.shutdown()


def test_written_says_where(env):
    env.session.export_pdf("a4")
    request = env.pick()
    env.session.respond(request.request_id, "")
    assert env.status() == formatting.exported_pdf_status(env.store.ref("out.pdf").location)
    assert env.errors() == []
    assert env.session.pending_request is None


def test_a_reason_is_shown(env):
    env.session.export_pdf("a4")
    request = env.pick()
    env.session.respond(request.request_id, "Permission denied")
    location = env.store.ref("out.pdf").location
    assert env.errors() == [(formatting.FILE_ERROR_TITLE, formatting.file_error_message(
        formatting.PDF_EXPORT_FAILED, location, "Permission denied"))]
    assert not env.status().startswith("Exported")


def test_no_answer_is_a_failure_without_a_reason(env):
    env.session.export_pdf("a4")
    request = env.pick()
    env.session.respond(request.request_id, None)
    location = env.store.ref("out.pdf").location
    assert env.errors() == [(formatting.FILE_ERROR_TITLE, f"{formatting.PDF_EXPORT_FAILED}:\n{location}")]


def test_on_android_a_failure_says_the_picked_file_is_left(tmp_path):
    env = Env(tmp_path, platform="android")
    env.session.export_pdf("a4")
    request = env.pick()
    env.session.respond(request.request_id, "Disk full")
    [(_title, message)] = env.errors()
    assert message.endswith(formatting.export_left_file_note("out.pdf"))
    assert "Disk full" in message
    env.session.shutdown()


def test_a_cancelled_picker_paints_nothing(env):
    env.session.export_pdf("a4")
    request = env.pending(PickDocumentRequest)
    env.session.respond(request.request_id, None)
    assert env.recorder.of_type(PaintPdfRequest) == []
    assert env.errors() == []


def test_lyrics_without_chords_export(tmp_path):
    env = Env(tmp_path, text="Amazing grace\nhow sweet the sound\n")
    env.session.export_pdf("a4")
    layout = env.pick().layout
    assert [line.runs[0].text for line in layout.pages[0].lines] == [
        "Amazing grace", "how sweet the sound"]
    env.session.shutdown()


def test_an_empty_song_is_one_page_with_the_header(tmp_path):
    env = Env(tmp_path, text="")
    env.session.export_pdf("a4")
    request = env.pending(PickDocumentRequest)
    assert request.suggested_name == "Untitled.pdf"
    env.session.respond(request.request_id, env.store.ref("out.pdf"))
    layout = env.pending(PaintPdfRequest).layout
    assert (layout.page_count, layout.pages[0].lines, layout.title) == (1, (), "Untitled")
    env.session.shutdown()


def test_the_pages_are_the_text_when_the_file_is_picked(env):
    env.session.export_pdf("a4")
    env.session.set_text("Changed\n")
    layout = env.pick().layout
    assert [line.runs[0].text for line in layout.pages[0].lines] == ["Changed"]


def test_an_unknown_page_size_is_refused(env):
    with pytest.raises(ValueError):
        env.session.export_pdf("a5")
    assert env.session.pending_request is None
