"""The directive hints (plan step D4): the hover card and the status bar's hint.

The whole front end runs in the test process, as in test_qt_editor.py. The
precedence itself is the core's StatusLine (tests/test_directive_hint_ui.py);
these check that the Qt status bar and the hover card use it as Tk did.
"""

import pytest

from tests.conftest import QT_PROBLEM

if QT_PROBLEM:
    pytest.skip(f"Qt not available: {QT_PROBLEM}", allow_module_level=True)

from PySide6.QtCore import QPointF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from chordnotepad.models.directive import DIRECTIVE_SYNTAX  # noqa: E402
from chordnotepad_desktop.status_bar import HINT_DELAY_MS, HintLine, hint_line  # noqa: E402
from tests.qt.test_qt_editor import Editor, song, start  # noqa: E402

TEXT = "{bpm: 90}\nC   G   Am  F\n{bpm: 999}\n{capo: 2}\n{capo: 3}\nC G\n"


@pytest.fixture
def ed(qapp, qtbot, tmp_path):
    harness = start(qapp, qtbot, tmp_path)
    editor = Editor(harness, qtbot)
    qtbot.waitUntil(lambda: editor.area.hasActiveFocus(), timeout=1000)
    yield editor
    warnings, unexpected = list(harness.app.warnings), list(harness.unexpected)
    harness.shutdown()
    qtbot.wait(1)
    assert warnings == [] and unexpected == []


def card(ed):
    return ed.item("hintCard")


def card_hint(ed):
    return ed.item("editorPane").property("hint")


def status(ed):
    return ed.harness.app.status_bar


def hover(ed, position):
    QTest.mouseMove(ed.window, ed.point_of(position))


def past_line_end(ed, position):
    """A window point right of ``position``, the end of a line."""
    rect = ed.area.positionToRectangle(position)
    return ed.area.mapToScene(QPointF(rect.x() + 40, rect.y() + rect.height() / 2)).toPoint()


# -- the hover card -----------------------------------------------------------------------


def test_the_card_shows_450_ms_after_the_pointer_rests_on_a_directive(ed):
    song(ed, TEXT)
    hover(ed, 3)
    ed.run(250)
    assert not card(ed).isVisible()
    ed.qtbot.waitUntil(lambda: card(ed).isVisible(), timeout=1000)
    hint = card_hint(ed)
    assert (hint["start"], hint["end"]) == (0, len("{bpm: 90}"))
    assert hint["message"] == "" and hint["syntax"] == DIRECTIVE_SYNTAX["bpm"]
    assert card(ed).property("bad") is False
    # Just under the directive's first character, so it doesn't cover it.
    first = ed.area.positionToRectangle(0)
    assert card(ed).property("y") >= first.y() + first.height()
    # Wrapped between the examples only: no break inside "{bpm: 120}".
    assert ed.item("hintCardSyntax").property("text") == DIRECTIVE_SYNTAX["bpm"].replace(
        ": ", ":\u00a0")


def test_an_invalid_directive_gives_its_reason_in_red(ed):
    song(ed, TEXT)
    hover(ed, TEXT.index("{bpm: 999}") + 4)
    ed.qtbot.waitUntil(lambda: card(ed).isVisible(), timeout=1500)
    assert card_hint(ed)["message"] == "Tempo must be 20-400"
    assert card(ed).property("bad") is True
    assert ed.item("hintCardMessage").property("text") == "Tempo must be 20-400"


def test_a_directive_without_effect_explains_it_muted(ed):
    song(ed, TEXT)
    hover(ed, TEXT.index("{capo: 2}") + 2)
    ed.qtbot.waitUntil(lambda: card(ed).isVisible(), timeout=1500)
    hint = card_hint(ed)
    assert hint["redundant"] is True and hint["message"].startswith("Has no effect")
    assert card(ed).property("bad") is False


def test_every_directive_gets_a_card_not_only_bad_ones(ed):
    # Tk explained only red and faded directives; the Qt card is on every one.
    song(ed, TEXT)
    hover(ed, TEXT.index("{capo: 3}") + 2)
    ed.qtbot.waitUntil(lambda: card(ed).isVisible(), timeout=1500)
    assert card_hint(ed)["syntax"] == DIRECTIVE_SYNTAX["capo"]


def test_chords_lyrics_and_past_the_line_end_show_nothing(ed):
    song(ed, TEXT)
    hover(ed, TEXT.index("Am"))
    ed.run(600)
    assert not card(ed).isVisible()
    # Right of "{bpm: 90}": the pointer is past the end of its line.
    QTest.mouseMove(ed.window, past_line_end(ed, len("{bpm: 90}")))
    ed.run(600)
    assert not card(ed).isVisible()
    assert ed.bridge.hintAt(len("{bpm: 90}")) == {}      # the line's end


def test_the_card_hides_on_leaving_on_a_click_and_on_another_directive(ed):
    song(ed, TEXT)
    hover(ed, 3)
    ed.qtbot.waitUntil(lambda: card(ed).isVisible(), timeout=1500)
    hover(ed, TEXT.index("Am"))
    assert not card(ed).isVisible()
    hover(ed, 3)
    ed.qtbot.waitUntil(lambda: card(ed).isVisible(), timeout=1500)
    QTest.mouseClick(ed.window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                     ed.point_of(3))
    assert not card(ed).isVisible()
    hover(ed, 4)
    ed.qtbot.waitUntil(lambda: card(ed).isVisible(), timeout=1500)
    # Another directive: the old card goes at once, the new one after a rest.
    hover(ed, TEXT.index("{bpm: 999}") + 3)
    assert not card(ed).isVisible()
    ed.qtbot.waitUntil(lambda: card(ed).isVisible(), timeout=1500)
    assert card_hint(ed)["message"] == "Tempo must be 20-400"


def test_typing_hides_the_card(ed):
    song(ed, TEXT)
    hover(ed, 3)
    ed.qtbot.waitUntil(lambda: card(ed).isVisible(), timeout=1500)
    ed.set_cursor(len(TEXT))
    ed.type("x")
    assert not card(ed).isVisible()


def test_astral_characters_keep_the_card_on_its_directive(ed):
    text = "\U0001F600 {key: G}\n"
    song(ed, text)
    start16 = 3                              # the emoji is two UTF-16 units, then a space
    hint = ed.bridge.hintAt(start16 + 2)
    assert (hint["start"], hint["end"]) == (start16, start16 + len("{key: G}"))
    assert hint["syntax"] == DIRECTIVE_SYNTAX["key"]


# -- the status bar ---------------------------------------------------------------------


def test_the_status_bar_is_under_the_editor_with_the_sessions_status(ed):
    bar = ed.item("statusBar")
    assert bar.isVisible()
    assert ed.item("statusText").property("text") == "Ready"
    assert status(ed).property("text") == "Ready"


def test_the_caret_in_a_directive_shows_its_hint_150_ms_later(ed):
    song(ed, TEXT)
    ed.set_cursor(3)
    assert status(ed).property("showHint") is False
    ed.qtbot.waitUntil(lambda: status(ed).property("showHint") is True, timeout=1000)
    assert status(ed).property("hintSyntax") == DIRECTIVE_SYNTAX["bpm"]
    assert status(ed).property("hintMessage") == ""
    assert ed.item("hintSyntax").isVisible() and not ed.item("statusText").isVisible()
    # Leaving brings the status back.
    ed.set_cursor(TEXT.index("Am"))
    ed.qtbot.waitUntil(lambda: status(ed).property("showHint") is False, timeout=1000)
    assert ed.item("statusText").isVisible()


def test_an_invalid_directive_puts_the_reason_first(ed):
    song(ed, TEXT)
    ed.set_cursor(TEXT.index("{bpm: 999}") + 3)
    ed.qtbot.waitUntil(lambda: status(ed).property("showHint") is True, timeout=1000)
    assert status(ed).property("hintMessage") == "Tempo must be 20-400"
    assert status(ed).property("hintRedundant") is False
    assert status(ed).property("text") == "Tempo must be 20-400 — " + DIRECTIVE_SYNTAX["bpm"]
    ed.set_cursor(TEXT.index("{capo: 2}") + 3)
    ed.qtbot.waitUntil(lambda: status(ed).property("hintRedundant") is True, timeout=1000)


def test_a_partly_typed_keyword_lists_what_it_could_become(ed):
    ed.type("{t")
    ed.qtbot.waitUntil(lambda: status(ed).property("showHint") is True, timeout=1000)
    assert status(ed).property("hintSyntax") == (
        DIRECTIVE_SYNTAX["tempo"] + " · " + DIRECTIVE_SYNTAX["time"])


def test_keys_are_debounced_into_one_lookup(ed):
    song(ed, "{bpm: 90}\n")
    ed.set_cursor(9)
    ed.run(HINT_DELAY_MS + 100)
    calls = []
    real = ed.store.direct

    def spy(name, *args):
        if name == "directive_hint_at":
            calls.append(args)
        return real(name, *args)

    ed.store.direct = spy
    for _ in range(4):
        ed.key(Qt.Key.Key_Left)
        ed.run(20)
    ed.run(HINT_DELAY_MS + 60)
    assert calls == [(5,)]


def test_a_new_status_covers_the_hint_until_the_caret_moves(ed):
    song(ed, "C G\n")
    ed.set_cursor(4)
    ed.store.submit("insert_snippet", {"offset": 4, "text": "{bpm: 120}"})
    ed.qtbot.waitUntil(lambda: ed.text() == "C G\n{bpm: 120}", timeout=2000)
    ed.qtbot.waitUntil(lambda: status(ed).property("statusText").startswith("Inserted"),
                       timeout=1000)
    ed.run(HINT_DELAY_MS + 100)
    # The caret is in the new directive, but the status stays.
    assert status(ed).property("showHint") is False
    ed.key(Qt.Key.Key_Left)
    ed.qtbot.waitUntil(lambda: status(ed).property("showHint") is True, timeout=1000)


def test_playback_status_wins_over_the_hint(ed):
    ed.harness.player.auto_play = False
    song(ed, TEXT)
    ed.set_cursor(3)
    ed.qtbot.waitUntil(lambda: status(ed).property("showHint") is True, timeout=1000)
    ed.store.submit("play_pause", {"from_offset": None})
    ed.qtbot.waitUntil(lambda: status(ed).property("playing") is True, timeout=3000)
    assert status(ed).property("showHint") is False
    ed.store.submit("stop")
    ed.qtbot.waitUntil(lambda: status(ed).property("playing") is False, timeout=3000)
    # "Stopped playback" is a new status: it shows until the caret moves.
    assert status(ed).property("statusText") == "Stopped playback"
    ed.run(HINT_DELAY_MS + 100)
    assert status(ed).property("showHint") is False
    assert ed.area.property("cursorPosition") == 3       # kept while playing
    ed.key(Qt.Key.Key_Right)
    ed.qtbot.waitUntil(lambda: status(ed).property("showHint") is True, timeout=1000)


def test_a_new_detection_looks_the_hint_up_again(ed):
    # A "has no effect" reason needs the chords: it comes with HighlightState.
    song(ed, "{capo: 2}\n")
    ed.set_cursor(3)
    ed.qtbot.waitUntil(lambda: status(ed).property("showHint") is True, timeout=1000)
    assert status(ed).property("hintRedundant") is False
    ed.set_cursor(len("{capo: 2}\n"))
    ed.type("{capo: 3}\nC")
    ed.set_cursor(3)
    ed.settle()
    ed.qtbot.waitUntil(lambda: status(ed).property("hintRedundant") is True, timeout=2000)


def test_hint_line():
    class Hint:
        message, syntax, redundant = "Not a key", "{key: G}\n{key: Am}", False

    assert hint_line(Hint) == HintLine("Not a key", "{key: G} · {key: Am}", False)
    assert hint_line(Hint).text == "Not a key — {key: G} · {key: Am}"
    Hint.syntax = ""
    assert hint_line(Hint) is None
