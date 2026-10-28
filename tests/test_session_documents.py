"""AppSession's document flows: new, open, save, save as, export MIDI, close.

Each flow is a generator (session.flows): the unsaved-changes question is a
``ConfirmDiscardRequest``, every file picker a ``PickDocumentRequest`` the
test answers with a ``DocumentRef`` from an ``InMemoryDocumentStore``. The
session runs on a ManualHost over the real parser, viewmodels and
PlaybackService (with a silent FakePlayer). The Tk side, which only presents
these requests, is tested at the bottom with a Mock standing in for the window.
"""

from unittest.mock import Mock, patch

import pytest

from services.playback_service import PlaybackService
from services.song_parser_service import SongParserService
from session import formatting
from session.documents import DocumentRef
from session.events import (
    CloseApproved, ConfirmDiscardRequest, DiscardChoice, PickDocumentRequest, PickMode,
    TextEdited, UndoPolicy, UserError,
)
from session.host import HostDispatch
from session.session import AppSession
from session.state import (
    DocumentState, HighlightState, RecentDocumentsState, StatusState, ToolbarState,
)
from session.testing import EventRecorder, FakePlayer, InMemoryDocumentStore, ManualHost
from viewmodels.main_window_viewmodel import MainWindowViewModel
from viewmodels.text_editor_viewmodel import TextEditorViewModel

SONG = "{bpm: 90}\n{time: 3/4}\n{key: G}\nG D Em C\n"


class FakeConfig:
    """Dict-backed stand-in for ConfigService."""

    def __init__(self, **values):
        self._values = dict(values)

    def get(self, key, default=None):
        return self._values.get(key, default)

    def set(self, key, value):
        self._values[key] = value


class Env:
    """A started session over an in-memory store holding ``song.txt``."""

    def __init__(self, text="", documents=None, max_recent=10):
        self.host = ManualHost()
        dispatch = HostDispatch(self.host)
        self.config = FakeConfig()
        self.audio = PlaybackService(self.config, player=FakePlayer(auto_play=False),
                                     application=dispatch)
        self.store = InMemoryDocumentStore(
            {"song.txt": SONG} if documents is None else documents, max_recent=max_recent)
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
        self.recorder.clear()

    def type(self, text):
        self.session.set_text(text)
        self.host.advance(0.5)

    def ref(self, name):
        return self.store.ref(name)

    def request(self, request_type=object):
        """The one request the last command left pending."""
        pending = self.session._flows.pending_request_id
        found = [r for r in self.recorder.items
                 if isinstance(r, (ConfirmDiscardRequest, PickDocumentRequest))
                 and r.request_id == pending]
        assert found, f"no pending request (recorded: {self.recorder.compact()})"
        assert isinstance(found[0], request_type)
        return found[0]

    def answer(self, value):
        request = self.request()
        self.recorder.clear()
        self.session.respond(request.request_id, value)

    def document(self):
        return self.recorder.last(DocumentState) or self.session._emitter.state(DocumentState)

    def recent(self):
        state = self.session._emitter.state(RecentDocumentsState)
        return [r.display_name for r in state.items]

    def status(self):
        return self.session._emitter.state(StatusState).text

    def errors(self):
        return [(e.title, e.message) for e in self.recorder.of_type(UserError)]


def open_song(env, name="song.txt"):
    """Open ``name`` with nothing unsaved, and forget the output."""
    env.session.open_document(env.ref(name))
    env.recorder.clear()


# -- states ------------------------------------------------------------------------


def test_initial_document_state_is_an_unmodified_untitled_document():
    env = Env()
    state = env.document()
    assert state == DocumentState("Untitled", None, False, "Untitled - Chord Notepad")
    assert env.recent() == []


def test_typing_marks_the_document_modified():
    env = Env()
    env.session.set_text("C")
    assert env.recorder.last(DocumentState).title == "Untitled* - Chord Notepad"
    assert env.recorder.last(DocumentState).is_modified is True


def test_window_title_formatting():
    assert formatting.window_title("song.txt", False) == "song.txt - Chord Notepad"
    assert formatting.window_title("song.txt", True) == "song.txt* - Chord Notepad"
    assert formatting.window_title(None, False) == "Untitled - Chord Notepad"


def test_recent_list_is_replayed_from_the_store():
    store = InMemoryDocumentStore({"a.txt": "C\n", "b.txt": "G\n"})
    store.add_recent(store.ref("a.txt"))
    store.add_recent(store.ref("b.txt"))
    host = ManualHost()
    main = MainWindowViewModel(FakeConfig(), PlaybackService(FakeConfig(), player=None),
                               store, SongParserService(), HostDispatch(host))
    session = AppSession(host, main_window_viewmodel=main,
                         text_editor_viewmodel=TextEditorViewModel(SongParserService()))
    recorder = EventRecorder()
    session.subscribe(recorder)
    state = recorder.last(RecentDocumentsState)
    assert state.items == (store.ref("b.txt"), store.ref("a.txt"))
    # Plain values only: the refs are frozen dataclasses of strings.
    assert all(isinstance(getattr(r, f), str) for r in state.items
               for f in ("id", "display_name", "location"))


# -- open --------------------------------------------------------------------------


def test_open_unmodified_asks_for_a_document_then_loads_it():
    env = Env()
    env.session.open_document()
    request = env.request(PickDocumentRequest)
    assert (request.mode, request.suggested_name) == (PickMode.OPEN, "")

    env.answer(env.ref("song.txt"))
    edits = env.recorder.of_type(TextEdited)
    assert len(edits) == 1
    assert (edits[0].start, edits[0].end, edits[0].replacement, edits[0].undo) == (
        0, 0, SONG, UndoPolicy.RESET)
    # Highlighted in the same delivery, no debounce.
    highlight = env.recorder.last(HighlightState)
    assert highlight.text_revision == edits[0].text_revision
    assert len(highlight.spans) > 0
    assert env.session._detect_timer is None

    toolbar = env.recorder.last(ToolbarState)
    assert (toolbar.bpm, toolbar.beats, toolbar.unit, toolbar.key) == (90, 3, 4, "G")
    assert env.document() == DocumentState(
        "song.txt", "song.txt", False, "song.txt - Chord Notepad")
    assert env.recent() == ["song.txt"]
    assert env.status() == "Opened: song.txt"
    assert env.session.text == SONG


def test_modified_open_save_then_cancelled_save_as_aborts():
    env = Env("C G")
    env.session.open_document()
    assert isinstance(env.request(), ConfirmDiscardRequest)

    env.answer("save")
    request = env.request(PickDocumentRequest)
    # The document was never saved: Save As, suggesting a name.
    assert (request.mode, request.suggested_name) == (PickMode.SAVE, "Untitled.txt")

    env.answer(None)
    assert env.session._flows.pending_request_id is None
    assert env.recorder.items == []          # no open picker, nothing changed
    assert env.session.text == "C G"
    assert env.main.is_modified is True


def test_modified_open_discard_then_pick_loads_the_document():
    env = Env("C G")
    env.session.open_document()
    env.answer("discard")
    assert env.request(PickDocumentRequest).mode is PickMode.OPEN
    env.answer(env.ref("song.txt"))

    edit = env.recorder.last(TextEdited)
    assert (edit.start, edit.end, edit.replacement, edit.undo) == (0, 3, SONG, UndoPolicy.RESET)
    assert env.recorder.last(ToolbarState).bpm == 90
    assert env.document().title == "song.txt - Chord Notepad"
    assert env.recent() == ["song.txt"]
    assert env.store.contents == {env.ref("song.txt").id: SONG}   # nothing saved


def test_modified_open_save_with_a_name_saves_then_opens():
    env = Env(documents={"song.txt": SONG, "draft.txt": "x"})
    open_song(env, "draft.txt")
    env.type("Am")
    env.session.open_document(env.ref("song.txt"))
    env.answer(DiscardChoice.SAVE.value)       # saves to draft.txt, no picker
    assert env.store.contents[env.ref("draft.txt").id] == "Am"
    assert env.session.text == SONG
    assert env.recent() == ["song.txt", "draft.txt"]


@pytest.mark.parametrize("answer", ["cancel", None])
def test_cancelling_the_question_aborts_open(answer):
    env = Env("C G")
    env.session.open_document()
    env.answer(answer)
    assert env.recorder.items == []
    assert env.session._flows.pending_request_id is None


def test_cancelling_the_open_picker_changes_nothing():
    env = Env()
    env.session.open_document()
    env.answer(None)
    assert env.recorder.items == []


def test_open_failure_is_a_user_error_and_keeps_the_document():
    env = Env()
    open_song(env)
    env.session.open_document(env.ref("nope.txt"))
    assert env.errors() == [(
        "Error", "Failed to open file:\nnope.txt\n\nFile not found: nope.txt")]
    assert env.recorder.of_type(TextEdited) == []
    assert env.document().display_name == "song.txt"
    assert env.recent() == ["song.txt"]


def test_open_recent_opens_without_a_picker():
    env = Env("C G")
    env.session.open_recent(env.ref("song.txt"))
    env.answer("discard")
    assert env.recorder.of_type(PickDocumentRequest) == []
    assert env.session.text == SONG


def test_reopening_the_same_text_still_resets_the_undo_history():
    env = Env()
    open_song(env)
    env.session.open_document(env.ref("song.txt"))
    edits = env.recorder.of_type(TextEdited)
    assert [(e.replacement, e.undo) for e in edits] == [(SONG, UndoPolicy.RESET)]
    assert env.recorder.last(HighlightState).text_revision == edits[0].text_revision


def test_a_picker_answer_must_be_a_document_ref():
    env = Env()
    env.session.open_document()
    request = env.request(PickDocumentRequest)
    with pytest.raises(TypeError):
        env.session.respond(request.request_id, "/some/path.txt")
    assert env.session._flows.pending_request_id is None


def test_open_recent_needs_a_ref():
    env = Env()
    with pytest.raises(TypeError):
        env.session.open_recent("song.txt")


def test_a_new_flow_closes_the_pending_one():
    env = Env("C G")
    env.session.open_document()
    stale = env.request().request_id
    env.session.new_document()
    current = env.request(ConfirmDiscardRequest).request_id
    assert current != stale
    env.session.respond(stale, "discard")      # ignored
    assert env.session.text == "C G"
    env.session.respond(current, "discard")
    assert env.session.text == ""


# -- new ---------------------------------------------------------------------------


def test_new_discarding_changes_clears_the_text_as_a_plain_edit():
    env = Env()
    open_song(env)
    env.type("C G")
    env.session.new_document()
    env.answer("discard")
    edit = env.recorder.last(TextEdited)
    assert (edit.start, edit.end, edit.replacement, edit.undo) == (0, 3, "", UndoPolicy.PLAIN)
    assert env.document() == DocumentState("Untitled", None, False, "Untitled - Chord Notepad")
    assert env.status() == "New file created"
    assert env.recent() == ["song.txt"]


def test_new_without_changes_asks_nothing():
    env = Env()
    env.session.new_document()
    assert env.recorder.of_type(ConfirmDiscardRequest) == []
    assert env.status() == "New file created"


# -- save / save as ----------------------------------------------------------------


def test_save_writes_the_open_document():
    env = Env()
    open_song(env)
    env.type("C G")
    assert env.document().title == "song.txt* - Chord Notepad"
    env.session.save()
    assert env.store.contents[env.ref("song.txt").id] == "C G"
    assert env.recorder.of_type(PickDocumentRequest) == []
    assert env.document().title == "song.txt - Chord Notepad"
    assert env.status() == "Saved: song.txt"


def test_save_without_a_name_asks_for_one():
    env = Env("C G", documents={})
    env.session.save()
    request = env.request(PickDocumentRequest)
    assert (request.mode, request.suggested_name) == (PickMode.SAVE, "Untitled.txt")
    env.answer(env.ref("new.txt"))
    assert env.store.contents[env.ref("new.txt").id] == "C G"
    assert env.document() == DocumentState("new.txt", "new.txt", False, "new.txt - Chord Notepad")
    assert env.recent() == ["new.txt"]
    assert env.errors() == []


def test_save_failure_is_reported_instead_of_asking_for_a_name():
    env = Env()
    open_song(env)
    env.type("C G")
    env.store.write_error = "Permission denied: song.txt"
    env.session.save()
    assert env.recorder.of_type(PickDocumentRequest) == []
    assert env.errors() == [(
        "Error", "Failed to save file:\nsong.txt\n\nPermission denied: song.txt")]
    assert env.document().is_modified is True


def test_save_as_switches_the_document_and_the_recent_list():
    env = Env()
    open_song(env)
    env.session.save_as()
    request = env.request(PickDocumentRequest)
    assert (request.mode, request.suggested_name) == (PickMode.SAVE, "song.txt")
    env.answer(env.ref("copy.txt"))
    assert env.store.contents[env.ref("copy.txt").id] == SONG
    assert env.document().title == "copy.txt - Chord Notepad"
    assert env.recent() == ["copy.txt", "song.txt"]
    assert env.status() == "Saved: copy.txt"


def test_cancelled_save_as_changes_nothing():
    env = Env()
    open_song(env)
    env.session.save_as()
    env.answer(None)
    assert env.recorder.items == []


# -- recent list -------------------------------------------------------------------


def test_recent_list_prunes_unavailable_documents_and_is_capped():
    env = Env(documents={"a.txt": "A", "b.txt": "B", "c.txt": "C"}, max_recent=2)
    for name in ("a.txt", "b.txt", "c.txt"):
        open_song(env, name)
    assert env.recent() == ["c.txt", "b.txt"]

    del env.store.contents[env.ref("b.txt").id]
    env.session.save()
    assert env.recent() == ["c.txt"]


def test_each_open_and_save_adds_to_the_recent_list_once():
    env = Env()
    calls = []
    real = env.store.add_recent
    env.store.add_recent = lambda ref: (calls.append(ref.display_name), real(ref))
    open_song(env)
    env.session.save()
    assert calls == ["song.txt", "song.txt"]


# -- export MIDI -------------------------------------------------------------------


def test_export_writes_midi_bytes_and_is_not_recent():
    env = Env()
    open_song(env)
    env.session.export_midi()
    request = env.request(PickDocumentRequest)
    assert (request.mode, request.suggested_name) == (PickMode.EXPORT_MIDI, "song.mid")
    env.answer(env.ref("song.mid"))
    data = env.store.contents[env.ref("song.mid").id]
    assert isinstance(data, bytes) and data.startswith(b"MThd")
    assert env.recent() == ["song.txt"]
    assert env.document().display_name == "song.txt"
    assert env.status() == "Exported MIDI: song.mid"
    assert env.errors() == []


def test_export_titles_the_midi_after_the_document():
    env = Env()
    open_song(env)
    env.session.export_midi()
    with patch("services.midi_file_writer.render_midi_bytes", return_value=b"MIDI") as render:
        env.answer(env.ref("out.mid"))
    assert render.call_args.kwargs["title"] == "song"


def test_export_untitled_suggests_untitled_mid():
    env = Env("C G")
    env.session.export_midi()
    assert env.request(PickDocumentRequest).suggested_name == "Untitled.mid"


def test_export_without_chords_is_a_user_error():
    env = Env("just lyrics", documents={})
    env.session.export_midi()
    env.answer(env.ref("out.mid"))
    assert env.errors() == [(
        "Error", "Failed to export MIDI file:\nout.mid\n\nThere are no chords to export.")]
    assert env.store.contents == {}


def test_export_write_failure_is_a_user_error():
    env = Env("C G", documents={})
    env.store.write_error = "disk full"
    env.session.export_midi()
    env.answer(env.ref("out.mid"))
    assert env.errors() == [("Error", "Failed to export MIDI file:\nout.mid\n\ndisk full")]


def test_cancelled_export_writes_nothing():
    env = Env("C G", documents={})
    env.session.export_midi()
    env.answer(None)
    assert env.store.contents == {}
    assert env.recorder.items == []


# -- close -------------------------------------------------------------------------


def test_close_without_changes_is_approved_at_once():
    env = Env()
    env.session.request_close()
    assert env.recorder.compact() == [("CloseApproved",)]


def test_close_discarding_changes_is_approved():
    env = Env("C G")
    env.session.request_close()
    env.answer("discard")
    assert env.recorder.of_type(CloseApproved) == [CloseApproved()]


def test_close_cancelled_is_not_approved():
    env = Env("C G")
    env.session.request_close()
    env.answer("cancel")
    assert env.recorder.items == []


def test_close_saving_an_untitled_document_asks_for_a_name_first():
    env = Env("C G", documents={})
    env.session.request_close()
    env.answer("save")
    env.answer(env.ref("song.txt"))
    assert env.store.contents[env.ref("song.txt").id] == "C G"
    assert env.recorder.of_type(CloseApproved) == [CloseApproved()]


def test_a_failed_save_stops_the_close():
    env = Env()
    open_song(env)
    env.type("C G")
    env.store.write_error = "Permission denied: song.txt"
    env.session.request_close()
    env.answer("save")
    assert len(env.errors()) == 1
    assert env.recorder.of_type(CloseApproved) == []


def test_a_failed_save_stops_new_and_open():
    env = Env()
    open_song(env)
    env.type("C G")
    env.store.write_error = "disk full"
    env.session.new_document()
    env.answer("save")
    assert env.session.text == "C G"
    env.session.open_document()
    env.answer("save")
    assert env.recorder.of_type(PickDocumentRequest) == []
    assert env.session.text == "C G"


# -- the Tk window only presents the requests --------------------------------------


def _window():
    from ui.main_window import MainWindow

    window = Mock()
    window.text_editor.get_text.return_value = "C G"
    return MainWindow, window


@pytest.mark.parametrize("response, choice", [
    (True, "save"), (False, "discard"), (None, "cancel"),
])
def test_tk_confirm_discard_maps_yes_no_cancel(response, choice):
    MainWindow, window = _window()
    with patch("ui.main_window.messagebox.askyesnocancel", return_value=response) as ask:
        MainWindow._present_confirm_discard(window, ConfirmDiscardRequest(4))
    assert ask.call_args.args == ("Unsaved Changes", "Do you want to save your changes?")
    assert ask.call_args.kwargs["parent"] is window
    window.session.respond.assert_called_once_with(4, choice)


def test_tk_open_picker_answers_with_a_ref():
    MainWindow, window = _window()
    with patch("ui.main_window.ask_open_filename", return_value="/a/song.txt") as ask:
        MainWindow._present_pick_document(window, PickDocumentRequest(2, PickMode.OPEN, ""))
    assert ask.call_args.kwargs["title"] == "Open File"
    window.application.documents.ref_for_path.assert_called_once_with("/a/song.txt")
    window.session.respond.assert_called_once_with(
        2, window.application.documents.ref_for_path.return_value)


@pytest.mark.parametrize("mode, title, extension", [
    (PickMode.SAVE, "Save File As", ".txt"),
    (PickMode.EXPORT_MIDI, "Export MIDI", ".mid"),
])
def test_tk_save_pickers_prefill_the_suggested_name(mode, title, extension):
    MainWindow, window = _window()
    with patch("ui.main_window.ask_save_as_filename", return_value="") as ask:
        MainWindow._present_pick_document(window, PickDocumentRequest(3, mode, "song.x"))
    kwargs = ask.call_args.kwargs
    assert (kwargs["title"], kwargs["defaultextension"], kwargs["initialfile"]) == (
        title, extension, "song.x")
    window.session.respond.assert_called_once_with(3, None)   # cancelled


def test_tk_requests_are_presented_after_delivery():
    MainWindow, window = _window()
    confirm = ConfirmDiscardRequest(1)
    pick = PickDocumentRequest(2, PickMode.OPEN, "")
    MainWindow._on_session_output(window, confirm)
    MainWindow._on_session_output(window, pick)
    MainWindow._on_session_output(window, CloseApproved())
    assert window.after_idle.call_args_list == [
        ((window._present_confirm_discard, confirm),),
        ((window._present_pick_document, pick),),
        ((window._close_window,),),
    ]
    window.session.respond.assert_not_called()
    window.destroy.assert_not_called()


def test_tk_title_and_recent_menu_follow_the_states():
    MainWindow, window = _window()
    MainWindow._on_session_output(
        window, DocumentState("song.txt", "/a/song.txt", True, "song.txt* - Chord Notepad"))
    window.title.assert_called_once_with("song.txt* - Chord Notepad")

    ref = DocumentRef(id="/a/song.txt", display_name="song.txt", location="/a/song.txt")
    MainWindow._apply_recent_documents(window, RecentDocumentsState((ref,)))
    kwargs = window.recent_menu.add_command.call_args.kwargs
    assert kwargs["label"] == "song.txt"
    window._open_recent = lambda r: MainWindow._open_recent(window, r)
    window._send_text = lambda: MainWindow._send_text(window)
    kwargs["command"]()
    window.session.set_text.assert_called_once_with("C G")
    window.session.open_recent.assert_called_once_with(ref)


def test_tk_empty_recent_menu_says_so():
    MainWindow, window = _window()
    MainWindow._apply_recent_documents(window, RecentDocumentsState(()))
    assert window.recent_menu.add_command.call_args.kwargs["label"] == "(No recent files)"


@pytest.mark.parametrize("method, command", [
    ("new_file", "new_document"), ("open_file", "open_document"), ("save_file", "save"),
    ("save_file_as", "save_as"), ("export_midi", "export_midi"), ("on_close", "request_close"),
])
def test_tk_file_commands_send_the_text_then_run_the_flow(method, command):
    MainWindow, window = _window()
    window._send_text = lambda: MainWindow._send_text(window)
    getattr(MainWindow, method)(window)
    assert [c[0] for c in window.session.method_calls] == ["set_text", command]
    window.session.set_text.assert_called_once_with("C G")


def test_tk_close_window_shuts_down_and_destroys():
    MainWindow, window = _window()
    window._closing = False
    window.geometry.return_value = "900x600+0+0"
    MainWindow._close_window(window)
    MainWindow._close_window(window)       # a second approval does nothing
    window.viewmodel.set_window_geometry.assert_called_once_with("900x600+0+0")
    window.session.stop.assert_called_once()
    window.application.on_shutdown.assert_called_once()
    window.destroy.assert_called_once()
