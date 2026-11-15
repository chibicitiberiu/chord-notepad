"""The chord identifier sidebar (plan step F5): identifier.py and IdentifierPanel.qml.

Identification, the notes parser, the spelling and the sounding notes are
the core's (tests/test_chord_identifier*.py, the session's identifier
tests); these check the panel over ``IdentifierState``: the piano's
geometry and hit test (black keys first), its colours, the bass dot and the
labels, clicks that select or only play, the notes field in either
notation, the candidates (resolution 1: a click plays, a double click inserts, ▶ auditions,
Shift+▶ plays rolled), the 3 s of amber keys and the markers, Clear, Play,
the read-only lock and the insert error.
"""

import inspect

import pytest

from tests.conftest import QT_PROBLEM

if QT_PROBLEM:
    pytest.skip(f"Qt not available: {QT_PROBLEM}", allow_module_level=True)

from PySide6.QtCore import QPointF, Qt  # noqa: E402
from PySide6.QtGui import QColor  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from chordnotepad.viewmodels.chord_identifier_viewmodel import (  # noqa: E402
    PIANO_HIGHEST_MIDI, PIANO_LOWEST_MIDI,
)
from chordnotepad_desktop import identifier  # noqa: E402
from chordnotepad_desktop.identifier import BLACK_HEIGHT, PianoLayout  # noqa: E402
from chordnotepad_desktop.sidebars import LOCKED_REASON  # noqa: E402
from tests.qt.test_qt_editor import NO_MODIFIER, song  # noqa: E402
from tests.qt.test_qt_sidebars import Window, finish, started  # noqa: E402
from tests.qt.test_qt_value_picker import texts_shown  # noqa: E402

LEFT = Qt.MouseButton.LeftButton
RIGHT = Qt.MouseButton.RightButton
SHIFT = Qt.KeyboardModifier.ShiftModifier
C4, E4, G4 = 60, 64, 67
AMBER = QColor("#f5a623")


class Panel(Window):
    @property
    def model(self):
        return self.harness.app.identifier

    @property
    def player(self):
        return self.harness.player

    def key_item(self, midi):
        return self.find(f"key:{midi}")

    def click_key(self, midi, button=LEFT, modifier=NO_MODIFIER, where=0.85):
        """Click on key ``midi``: low on a white key (below the black keys), in
        the middle of a black one."""
        key = self.key_item(midi)
        y = key.height() * (0.5 if midi % 12 in (1, 3, 6, 8, 10) else where)
        point = key.mapToScene(QPointF(key.width() / 2, y)).toPoint()
        QTest.mouseClick(self.window, button, modifier, point)
        self.run()

    def state(self):
        mapping = self.store.state("IdentifierState")
        return {k: mapping.value(k) for k in mapping.keys()}

    def selected(self):
        return [n["midi"] for n in self.state()["notes"]]

    def type_notes(self, text):
        field = self.find("notesField")
        field.forceActiveFocus()
        field.setProperty("text", "")
        self.model.type("")
        for ch in text:
            QTest.keyClick(self.window, ch)
        self.run(60)

    def candidate(self, chord):
        return self.find("candidate:" + chord)


@pytest.fixture
def panel(qapp, qtbot, tmp_path):
    w = started(qapp, qtbot, tmp_path, sidebar="identifier")
    p = Panel(w.harness, qtbot)
    qtbot.waitUntil(lambda: p.find("identifierPanel").isVisible(), timeout=1000)
    yield p
    finish(p)


# -- the piano's geometry -------------------------------------------------------------------


def test_the_keyboard_is_two_octaves_from_the_cores_lowest_key():
    piano = PianoLayout()
    assert piano.lowest == PIANO_LOWEST_MIDI == 60 and piano.highest == PIANO_HIGHEST_MIDI == 83
    whites = [k for k in piano.keys if not k.black]
    blacks = [k for k in piano.keys if k.black]
    assert len(whites) == 14 and len(blacks) == 10
    assert [k.name for k in whites[:7]] == ["C", "D", "E", "F", "G", "A", "B"]
    assert [k.name for k in blacks[:5]] == ["C#", "D#", "F#", "G#", "A#"]
    assert (whites[0].octave, whites[7].octave, whites[7].midi) == (4, 5, 72)
    # Black keys centred on the gap after C, D, F, G, A (the mockup's).
    assert blacks[0].left == pytest.approx(1 - 0.31) and blacks[0].width == pytest.approx(0.62)
    assert blacks[2].left == pytest.approx(4 - 0.31)


def test_black_keys_are_hit_first():
    piano = PianoLayout()
    # Just right of the C|D gap: C# at the top, D below the black key.
    assert piano.key_at(1.1, 0.2).name == "C#"
    assert piano.key_at(1.1, BLACK_HEIGHT + 0.05).name == "D"
    # Just left of it: C# at the top too, C below.
    assert piano.key_at(0.9, 0.2).name == "C#" and piano.key_at(0.9, 0.9).name == "C"
    # Between E and F there is no black key.
    assert piano.key_at(3.05, 0.1).name == "F" and piano.key_at(2.95, 0.1).name == "E"
    assert piano.key_at(13.9, 0.5).midi == 83
    assert piano.key_at(-0.1, 0.5) is None and piano.key_at(14, 0.5) is None
    assert piano.key_at(5, 1.0) is None


def test_the_drawn_keys_are_where_the_hit_test_finds_them(panel):
    model = panel.model
    piano = panel.find("piano")
    ww = piano.width() / 14
    for key in model.property("keys"):
        item = panel.key_item(key["midi"])
        assert item.x() == pytest.approx(key["left"] * ww, abs=0.01)
        centre = item.mapToItem(piano, QPointF(item.width() / 2, item.height() * (0.5 if key["black"] else 0.85)))
        assert model.keyAt(centre.x() / ww, centre.y() / piano.height()) == key["midi"]


# -- clicks on keys -------------------------------------------------------------------------


def test_a_click_selects_and_sounds_a_key_and_the_field_follows(panel):
    panel.click_key(C4)
    panel.qtbot.waitUntil(lambda: panel.selected() == [C4], timeout=1000)
    assert panel.player.immediate[-1] == [C4]
    panel.click_key(E4)
    panel.click_key(G4)
    panel.qtbot.waitUntil(lambda: panel.selected() == [C4, E4, G4], timeout=1000)
    assert panel.find("notesField").property("text") == "C E G"
    # A second click deselects; nothing sounds then.
    sounded = len(panel.player.immediate)
    panel.click_key(G4)
    panel.qtbot.waitUntil(lambda: panel.selected() == [C4, E4], timeout=1000)
    assert len(panel.player.immediate) == sounded
    assert panel.find("notesField").property("text") == "C E"


def test_a_black_key_click_doesnt_reach_the_white_key_under_it(panel):
    panel.click_key(61)
    panel.qtbot.waitUntil(lambda: panel.selected() == [61], timeout=1000)
    assert panel.find("notesField").property("text") == "C#"


def test_right_click_and_shift_click_only_play_the_key(panel):
    panel.click_key(E4, RIGHT)
    panel.click_key(G4, LEFT, SHIFT)
    panel.qtbot.waitUntil(lambda: len(panel.player.immediate) >= 2, timeout=1000)
    assert panel.player.immediate[-2:] == [[E4], [G4]]
    assert panel.selected() == []
    assert ("play_note", {"note": "E", "octave": 4}) in panel.submitted


def test_selected_keys_are_tinted_and_the_lowest_has_the_bass_dot(panel):
    panel.click_key(E4)
    panel.click_key(61)
    panel.qtbot.waitUntil(lambda: panel.selected() == [61, E4], timeout=1000)
    white, black, plain = panel.key_item(E4), panel.key_item(61), panel.key_item(G4)
    theme = panel.harness.app._engine.singletonInstance("CNTheme", "Theme")
    accent = QColor(theme.property("accentFill"))
    tint = white.property("color")
    assert tint != plain.property("color") and tint.lightness() > 150     # a light tint
    assert tint.blue() > tint.red()                                       # of the accent
    deep = black.property("color")
    assert deep.lightness() < accent.lightness() and deep != QColor("#1a1c21")
    # The bass dot: on C# (the lowest), not on E.
    assert panel.model.property("bass") == 61
    dots = [c for c in black.childItems() if c.isVisible() and c.width() == c.height() and c.width() > 0]
    assert dots and not [c for c in white.childItems() if c.isVisible() and c.width() == c.height()]


def test_labels_are_in_the_songs_notation_with_the_octave_on_c(panel):
    labels = {k["midi"]: k["label"] for k in panel.model.property("keys")}
    assert labels[60] == "C4" and labels[72] == "C5" and labels[67] == "G" and labels[61] == "C#"
    panel.store.submit("set_notation", {"notation": "european"})
    panel.qtbot.waitUntil(lambda: panel.model.property("notation") == "european", timeout=1000)
    labels = {k["midi"]: k["label"] for k in panel.model.property("keys")}
    assert labels[60] == "Do4" and labels[67] == "Sol"
    # At the default width only the C's are labelled (no room for the rest).
    shown = [t for t in texts_shown(panel.find("piano"))]
    assert "Do4" in shown and "Do5" in shown and "Sol" not in shown


# -- the notes field ------------------------------------------------------------------------


def test_the_field_takes_either_notation_and_commas_on_every_keystroke(panel):
    panel.type_notes("Do, Mi, Sol")
    panel.qtbot.waitUntil(lambda: panel.selected() == [C4, E4, G4], timeout=1000)
    sets = [a["text"] for n, a in panel.submitted if n == "identifier_set_notes_text"]
    assert sets[-1] == "Do, Mi, Sol" and len(sets) >= len("Do, Mi, Sol")
    assert "C" in panel.model.property("candidates")
    # The field keeps what was typed (not the session's "C E G").
    assert panel.find("notesField").property("text") == "Do, Mi, Sol"
    panel.type_notes("C E G")
    panel.qtbot.waitUntil(lambda: panel.model.property("candidates")[:1] == ["C"], timeout=1000)
    # A key click rewrites it.
    panel.click_key(71)
    panel.qtbot.waitUntil(lambda: panel.find("notesField").property("text") == "C E G B", timeout=1000)


def test_something_that_isnt_a_note_is_named_and_lists_no_candidates(panel):
    panel.type_notes("C E H")
    panel.qtbot.waitUntil(lambda: panel.model.property("typedError") != "", timeout=1000)
    assert panel.find("typedError").isVisible()
    assert "H" in panel.find("typedError").property("text")
    assert panel.model.property("candidates") == [] and panel.model.property("message") == ""


def test_a_notation_change_respells_the_field_only_if_it_showed_the_keys(panel):
    for midi in (C4, E4, G4):
        panel.click_key(midi)
    panel.qtbot.waitUntil(lambda: panel.find("notesField").property("text") == "C E G", timeout=1000)
    panel.store.submit("set_notation", {"notation": "european"})
    panel.qtbot.waitUntil(lambda: panel.find("notesField").property("text") == "Do Mi Sol", timeout=1000)
    assert "Do" in panel.model.property("candidates")
    assert "Do Mi Sol" in panel.model.property("instructions")
    assert panel.find("notesField").property("placeholderText") == "Do Mi Sol"
    panel.type_notes("Do, Mi, Sol")
    panel.store.submit("set_notation", {"notation": "american"})
    panel.qtbot.waitUntil(lambda: panel.model.property("notation") == "american", timeout=1000)
    assert panel.find("notesField").property("text") == "Do, Mi, Sol"


def test_the_instructions_are_tks():
    from chordnotepad_tk.chord_identifier import ChordIdentifierWindow
    for notation in ("american", "european"):
        assert identifier.instructions(notation) == ChordIdentifierWindow._instructions(notation)


def test_clear_empties_the_keys_and_the_field(panel):
    panel.type_notes("C E G")
    panel.qtbot.waitUntil(lambda: panel.selected() == [C4, E4, G4], timeout=1000)
    panel.click_item(panel.find("identifierClear"))
    panel.qtbot.waitUntil(lambda: panel.selected() == [], timeout=1000)
    assert panel.find("notesField").property("text") == ""
    assert panel.find("identifierMessage").property("text") == "Select notes to identify chords..."


# -- Play -------------------------------------------------------------------------------------


def test_play_needs_notes_and_plays_them_rolled_with_shift_or_a_right_click(panel):
    play = panel.find("identifierPlay")
    assert play.property("enabled") is False
    panel.type_notes("C E G")
    panel.qtbot.waitUntil(lambda: play.property("enabled") is True, timeout=1000)
    panel.click_item(play)
    panel.click_item(play, LEFT, SHIFT)
    panel.click_item(play, RIGHT)
    plays = [a["rolled"] for n, a in panel.submitted if n == "identifier_play_selection"]
    assert plays == [False, True, True]
    panel.qtbot.waitUntil(lambda: len(panel.player.rolled) == 2, timeout=1000)
    assert panel.player.rolled[-1][0] == [C4, E4, G4]
    assert "Shift+click or right-click plays them rolled" in play.property("tip")


# -- candidates -------------------------------------------------------------------------------


def double_click(panel, item):
    QTest.mouseDClick(panel.window, LEFT, NO_MODIFIER, panel.centre(item))
    panel.run()


def test_a_candidate_click_plays_it_without_inserting(panel):
    song(panel, "F\n")
    panel.set_cursor(1)
    panel.type_notes("C E G")
    panel.qtbot.waitUntil(lambda: panel.model.property("candidates")[:1] == ["C"], timeout=1000)
    assert [t for t in texts_shown(panel.candidate("C")) if t == "best"]
    panel.click_item(panel.candidate("C"))
    panel.click_item(panel.candidate("C"), LEFT, SHIFT)               # rolled
    auditions = [a for n, a in panel.submitted if n == "play_identified_chord"]
    assert auditions == [{"chord": "C", "rolled": False}, {"chord": "C", "rolled": True}]
    assert panel.text() == "F\n"
    assert not [n for n, _ in panel.submitted if n == "insert_chord"]
    # The row is the current one, so Enter inserts and Space plays from here.
    assert panel.find("candidates").property("currentIndex") == 0


def test_a_candidate_double_click_inserts_it_once_and_the_editor_gets_the_focus(panel):
    song(panel, "F\n")
    panel.set_cursor(1)
    panel.type_notes("C E G")
    panel.qtbot.waitUntil(lambda: panel.model.property("candidates")[:1] == ["C"], timeout=1000)
    double_click(panel, panel.candidate("C"))
    panel.qtbot.waitUntil(lambda: panel.text() == "F C \n", timeout=2000)
    assert [a for n, a in panel.submitted if n == "insert_chord"] == [{"at": 1, "chord": "C"}]
    # The first click played; the release that ends the double click didn't play again.
    assert [a for n, a in panel.submitted if n == "play_identified_chord"] == [{"chord": "C", "rolled": False}]
    panel.qtbot.waitUntil(lambda: panel.area.hasActiveFocus(), timeout=1000)
    panel.qtbot.waitUntil(
        lambda: panel.harness.app.status_bar.property("statusText") == "Inserted chord: C", timeout=1000)


def test_a_candidate_row_says_what_a_click_and_a_double_click_do(panel):
    song(panel, "F\n")
    panel.type_notes("C E G")
    panel.qtbot.waitUntil(lambda: panel.model.property("candidates")[:1] == ["C"], timeout=1000)
    panel.hover(panel.candidate("C"), 1200)
    assert "Click to play, double-click to insert at the caret, or drag into the text." in \
        texts_shown(panel.window.contentItem())


def test_play_on_a_candidate_auditions_it_and_shift_plays_it_rolled(panel):
    song(panel, "F\n")
    panel.type_notes("C E G")
    panel.qtbot.waitUntil(lambda: panel.model.property("candidates")[:1] == ["C"], timeout=1000)
    row = panel.candidate("C")
    panel.hover(row, 50)
    hear = panel.find("hear:C")
    assert hear.isVisible()
    panel.click_item(hear)
    panel.click_item(hear, LEFT, SHIFT)
    auditions = [a for n, a in panel.submitted if n == "play_identified_chord"]
    assert auditions == [{"chord": "C", "rolled": False}, {"chord": "C", "rolled": True}]
    # Neither inserted anything.
    assert panel.text() == "F\n"
    assert not [n for n, _ in panel.submitted if n == "insert_chord"]


def test_the_sounding_keys_are_amber_for_three_seconds_and_markers_name_the_rest(panel):
    panel.type_notes("C E G")
    panel.qtbot.waitUntil(lambda: panel.model.property("candidates")[:1] == ["C"], timeout=1000)
    panel.model.audition("C", False)
    panel.qtbot.waitUntil(lambda: panel.model.property("sounding") != [], timeout=1000)
    sounding = panel.model.property("sounding")
    on_keys = [m for m in sounding if PIANO_LOWEST_MIDI <= m <= PIANO_HIGHEST_MIDI]
    assert on_keys and all(panel.key_item(m).property("color") == AMBER for m in on_keys)
    below, above = panel.model.property("soundingBelow"), panel.model.property("soundingAbove")
    if any(m < PIANO_LOWEST_MIDI for m in sounding):
        assert below.startswith("◂") and panel.find("soundingBelow").property("text") == below
    # Typed notes in octave 3 sound under the keyboard: a marker.
    panel.type_notes("C3 E3 G3")
    panel.qtbot.waitUntil(lambda: panel.selected() == [48, 52, 55], timeout=1000)
    panel.model.play(False)
    panel.qtbot.waitUntil(lambda: panel.model.property("soundingBelow") != "", timeout=1000)
    assert panel.model.property("soundingBelow").startswith("◂ ")
    assert panel.find("soundingBelow").property("text") == panel.model.property("soundingBelow")
    # Gone after the state's seconds (3), by themselves.
    assert panel.state()["sounding_seconds"] == 3.0
    panel.qtbot.waitUntil(lambda: panel.model.property("sounding") == [], timeout=4000)
    assert panel.model.property("soundingBelow") == ""
    assert panel.key_item(C4).property("color") != AMBER


def test_the_keyboard_reaches_the_candidates(panel):
    song(panel, "F\n")
    panel.set_cursor(1)
    panel.type_notes("C E G")
    panel.qtbot.waitUntil(lambda: panel.model.property("candidates")[:1] == ["C"], timeout=1000)
    QTest.keyClick(panel.window, Qt.Key.Key_Down)
    panel.run()
    assert panel.find("candidates").hasActiveFocus()
    QTest.keyClick(panel.window, Qt.Key.Key_Space, SHIFT)
    panel.run()
    assert ("play_identified_chord", {"chord": "C", "rolled": True}) in panel.submitted
    QTest.keyClick(panel.window, Qt.Key.Key_Return)
    panel.qtbot.waitUntil(lambda: panel.text() == "F C \n", timeout=2000)
    assert panel.area.hasActiveFocus()


def test_inserting_is_locked_while_playing_but_play_still_works(panel):
    panel.harness.player.auto_play = False
    song(panel, "F G\n")
    panel.type_notes("C E G")
    panel.qtbot.waitUntil(lambda: panel.model.property("candidates")[:1] == ["C"], timeout=1000)
    panel.store.submit("play_pause", {"from_offset": None})
    panel.qtbot.waitUntil(lambda: panel.area.property("readOnly") is True, timeout=3000)
    row = panel.candidate("C")
    double_click(panel, row)                          # plays, but doesn't insert
    assert not [n for n, _ in panel.submitted if n == "insert_chord"]
    assert ("play_identified_chord", {"chord": "C", "rolled": False}) in panel.submitted
    panel.hover(row, 1000)
    assert any(LOCKED_REASON in t for t in texts_shown(panel.window.contentItem()))
    panel.click_item(panel.find("hear:C"))
    assert ("play_identified_chord", {"chord": "C", "rolled": False}) in panel.submitted
    panel.store.submit("stop")
    panel.qtbot.waitUntil(lambda: panel.area.property("readOnly") is False, timeout=3000)


def test_an_insert_that_fails_says_so_in_tks_words(panel, monkeypatch):
    song(panel, "F\n")
    panel.type_notes("C E G")
    panel.qtbot.waitUntil(lambda: panel.model.property("candidates")[:1] == ["C"], timeout=1000)

    def broken(at, chord):
        raise ValueError(f"insert offset {at} outside the text (length 2)")

    monkeypatch.setattr(panel.session, "insert_chord", broken)
    panel.set_cursor(0)
    presenter = panel.harness.app.presenter
    double_click(panel, panel.candidate("C"))
    panel.qtbot.waitUntil(lambda: presenter.showing is not None, timeout=2000)
    assert presenter.showing == ("Error", "Could not insert the chord C.\n\n"
                                          "insert offset 0 outside the text (length 2)")
    assert panel.harness.unexpected == []      # not the generic "Something went wrong"
    presenter.dismissed()
    # Any other failure is still the generic one.
    assert panel.model.insert_failure("ValueError: x", "transpose") is None


def test_the_insert_error_is_tks_text():
    from chordnotepad_tk import main_window
    source = inspect.getsource(main_window.MainWindow._on_insert_chord_from_identifier)
    assert 'messagebox.showerror("Error", f"Could not insert the chord {chord_name}.\\n\\n{e}"' in source
    assert identifier.INSERT_FAILED_TITLE == "Error"
    assert identifier.insert_failed_message("Am7", "boom") == "Could not insert the chord Am7.\n\nboom"
