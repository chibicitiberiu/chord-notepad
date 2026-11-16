"""AppSession.open_recovered: the Qt desktop's File > Backups.

A recovery copy opens like Open (the unsaved-changes question first), as a
modified document bound to the file it was a copy of (or untitled), and
leaves the recent list alone. The copies themselves are
tests/test_recovery_store.py; the menu is tests/qt/test_qt_recovery.py.
"""

import json

from chordnotepad.session import bridge, formatting
from chordnotepad.session.events import (
    ConfirmDiscardRequest, DiscardChoice, PickDocumentRequest, TextEdited, UndoPolicy,
)
from chordnotepad.session.state import DocumentState

from tests.test_session_documents import Env, open_song


def test_a_copy_of_a_saved_song_opens_modified_and_bound_to_it():
    env = Env()
    ref = env.ref("song.txt")
    env.session.open_recovered("Am F C G\n", ref)
    assert env.session.text == "Am F C G\n"
    edits = env.recorder.of_type(TextEdited)
    assert edits[-1].undo == UndoPolicy.RESET
    doc = env.document()
    assert (doc.display_name, doc.is_modified, doc.document_id) == ("song.txt", True, ref.id)
    assert doc.title == "song.txt* - Chord Notepad"
    assert env.status() == "Recovered: song.txt"
    assert env.recent() == []


def test_save_writes_the_recovered_text_to_the_original_file():
    env = Env()
    env.session.open_recovered("Em D\n", env.ref("song.txt"))
    env.session.save()
    assert env.store.read_text(env.ref("song.txt")) == "Em D\n"
    assert env.document().is_modified is False


def test_an_untitled_copy_opens_untitled_and_save_asks_for_a_name():
    env = Env()
    env.session.open_recovered("C\n", None)
    doc = env.document()
    assert (doc.display_name, doc.is_modified, doc.document_id) == ("Untitled", True, None)
    assert env.status() == "Recovered: Untitled"
    env.recorder.clear()
    env.session.save()
    assert env.request(PickDocumentRequest).suggested_name == formatting.UNTITLED_FILE_NAME


def test_an_untitled_copy_without_a_name_suggests_its_first_lyric_line():
    env = Env()
    env.session.open_recovered("C G\nHey Jude\n", None)
    assert env.document().display_name == "Untitled"
    assert env.status() == "Recovered: Untitled"
    env.recorder.clear()
    env.session.save()
    assert env.request(PickDocumentRequest).suggested_name == "Hey Jude.txt"


def test_an_untitled_copy_keeps_the_name_it_was_given():
    env = Env()
    env.session.open_recovered("C\n", None, "Set list.txt")
    assert env.document().display_name == "Set list.txt"
    env.recorder.clear()
    env.session.save()
    assert env.request(PickDocumentRequest).suggested_name == "Set list.txt"


def test_unsaved_changes_are_asked_about_first_and_cancel_keeps_them():
    env = Env(text="mine\n")
    env.session.open_recovered("theirs\n", None)
    env.request(ConfirmDiscardRequest)
    env.answer(DiscardChoice.CANCEL)
    assert env.session.text == "mine\n"
    assert env.recorder.of_type(DocumentState) == []


def test_discard_opens_the_copy():
    env = Env(text="mine\n")
    env.session.open_recovered("theirs\n", env.ref("song.txt"))
    env.answer(DiscardChoice.DISCARD)
    assert env.session.text == "theirs\n"
    assert env.document().is_modified is True


def test_the_same_text_as_shown_is_still_a_reset_edit():
    env = Env()
    open_song(env)
    text = env.session.text
    env.session.open_recovered(text, env.ref("song.txt"))
    assert env.recorder.of_type(TextEdited)[-1].undo == UndoPolicy.RESET
    assert env.document().is_modified is True


def test_open_recovered_is_a_bridge_command_android_never_sends():
    assert bridge.SESSION_COMMANDS["open_recovered"] == {
        "text": "str", "document": "DocumentRef|null", "name": "str|null"}
    kwargs = bridge.decode_args("open_recovered", json.dumps(
        {"text": "C", "document": None, "name": None}))
    assert kwargs == {"text": "C", "document": None, "name": None}
