"""The ▾ value pickers (plan step D5): the chip, the ValuePicker, the pick.

The whole front end runs in the test process, as in test_qt_editor.py. The
data the pickers show and the commands they send are the core's (B4:
tests/test_pickers.py, tests/test_snippets.py); these check the chip's rules,
the popup's choices and keys, and that a pick is one validated undo step.
Also insert_snippet end to end (the palette's insert, B4), since the editor
is what selects its value.
"""

import pytest

from tests.conftest import QT_PROBLEM

if QT_PROBLEM:
    pytest.skip(f"Qt not available: {QT_PROBLEM}", allow_module_level=True)

from PySide6.QtCore import QPointF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from chordnotepad.session import pickers  # noqa: E402
from chordnotepad.session.directives import check_directive  # noqa: E402
from chordnotepad.session.toolbar import insert_key_options  # noqa: E402
from chordnotepad_desktop.value_picker import compose_value, initial_values  # noqa: E402
from tests.qt.test_qt_editor import CTRL, NO_MODIFIER, Editor, song, start  # noqa: E402

ALT = Qt.KeyboardModifier.AltModifier
TEXT = ("{label: verse}\nC G\n{label: chorus}\nF C\n{loop: verse}\n{key: G}\n"
        "{time: 3/4}\n{bpm: 120}\n{capo: 2}\n// {key: D}\n")


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


def find(root, name):
    """An item by objectName in the visual tree (the popup's content is
    under the overlay, and Repeater delegates aren't in the QObject tree:
    pitfall 25)."""
    if root.objectName() == name:
        return root
    for child in root.childItems():
        found = find(child, name)
        if found is not None:
            return found
    return None


def item(ed, name):
    found = find(ed.window.contentItem(), name)
    assert found is not None, name
    return found


def chip(ed):
    return ed.item("pickChip")


def picker(ed):
    return ed.item("valuePicker")


def is_open(ed):
    return picker(ed).property("visible") is True


def click_item(ed, it):
    centre = it.mapToScene(QPointF(it.width() / 2, it.height() / 2)).toPoint()
    QTest.mouseClick(ed.window, Qt.MouseButton.LeftButton, NO_MODIFIER, centre)


def at(text, directive, inside=2):
    return text.index(directive) + inside


def caret_in(ed, text, directive, inside=2):
    ed.set_cursor(at(text, directive, inside))
    ed.qtbot.waitUntil(lambda: ed.harness.app.pickers.property("caretPicker").get("start")
                       == text.index(directive), timeout=1000)


def open_at_caret(ed, text, directive):
    caret_in(ed, text, directive)
    ed.key(Qt.Key.Key_Down, ALT)
    ed.qtbot.waitUntil(lambda: is_open(ed), timeout=1000)
    ed.run(30)


def focused(ed):
    return ed.window.activeFocusItem()


def plain(value):
    """A QML var property as Python data (a QJSValue, or already converted)."""
    return value.toVariant() if hasattr(value, "toVariant") else value


def texts_shown(root):
    """Every text in the visual tree (a tooltip's too)."""
    found = []
    text = root.property("text")
    if isinstance(text, str) and root.isVisible():
        found.append(text)
    for child in root.childItems():
        found.extend(texts_shown(child))
    return found


# -- the chip -------------------------------------------------------------------------------


def test_the_chip_sits_after_the_caret_directives_brace(ed):
    song(ed, TEXT)
    assert not chip(ed).isVisible()
    caret_in(ed, TEXT, "{key: G}")
    ed.qtbot.waitUntil(lambda: chip(ed).isVisible(), timeout=1000)
    end = ed.area.positionToRectangle(TEXT.index("{key: G}") + len("{key: G}"))
    assert chip(ed).property("x") >= end.x() and chip(ed).property("y") == end.y()
    # Just after the } counts too (picker_at).
    caret_in(ed, TEXT, "{key: G}", inside=len("{key: G}"))
    assert chip(ed).isVisible()


def test_no_chip_on_labels_comments_chords_or_while_read_only(ed):
    ed.harness.player.auto_play = False
    song(ed, TEXT)
    for place in (at(TEXT, "{label: verse}"), at(TEXT, "// {key: D}", 5), TEXT.index("F C")):
        ed.set_cursor(place)
        ed.run(60)
        assert not chip(ed).isVisible(), place
    caret_in(ed, TEXT, "{capo: 2}")
    ed.qtbot.waitUntil(lambda: chip(ed).isVisible(), timeout=1000)
    ed.window.setProperty("mode", "play")
    ed.qtbot.waitUntil(lambda: not chip(ed).isVisible(), timeout=1000)
    ed.window.setProperty("mode", "edit")
    ed.qtbot.waitUntil(lambda: chip(ed).isVisible(), timeout=1000)
    ed.store.submit("play_pause", {"from_offset": None})
    ed.qtbot.waitUntil(lambda: ed.area.property("readOnly") is True, timeout=3000)
    assert not chip(ed).isVisible()
    ed.key(Qt.Key.Key_Down, ALT)
    ed.run(60)
    assert not is_open(ed)
    ed.store.submit("stop")
    ed.qtbot.waitUntil(lambda: chip(ed).isVisible(), timeout=3000)


def test_hovering_a_directive_shows_its_chip_with_a_grace_period(ed):
    song(ed, TEXT)
    ed.set_cursor(TEXT.index("C G"))
    ed.run(60)
    key = TEXT.index("{key: G}")
    QTest.mouseMove(ed.window, ed.point_of(key + 3))
    ed.qtbot.waitUntil(lambda: chip(ed).isVisible(), timeout=1000)
    pane = ed.item("editorPane")
    assert plain(pane.property("pickDir"))["start"] == key
    # Off the directive: the chip stays 300 ms, then goes.
    QTest.mouseMove(ed.window, ed.point_of(TEXT.index("F C")))
    ed.run(150)
    assert chip(ed).isVisible()
    ed.qtbot.waitUntil(lambda: not chip(ed).isVisible(), timeout=1000)


def test_the_strip_between_the_directive_and_the_chip_is_sticky(ed):
    # "{key: G}{time: 3/4}" on one line: the chip of the first overlaps the
    # second's brace, and the pointer crossing it keeps the first's target.
    text = "{key: G}{time: 3/4}\n"
    song(ed, text)
    QTest.mouseMove(ed.window, ed.point_of(3))
    ed.qtbot.waitUntil(lambda: chip(ed).isVisible(), timeout=1000)
    pane = ed.item("editorPane")
    centre = chip(ed).mapToScene(QPointF(chip(ed).width() / 2, chip(ed).height() / 2)).toPoint()
    QTest.mouseMove(ed.window, centre)
    ed.run(400)
    assert chip(ed).isVisible() and plain(pane.property("pickDir"))["start"] == 0
    click_item(ed, chip(ed))
    ed.qtbot.waitUntil(lambda: is_open(ed), timeout=1000)
    assert picker(ed).property("kind") == "key"


def test_the_chips_tooltip_names_alt_down(ed):
    song(ed, TEXT)
    caret_in(ed, TEXT, "{key: G}")
    ed.qtbot.waitUntil(lambda: chip(ed).isVisible(), timeout=1000)
    centre = chip(ed).mapToScene(QPointF(chip(ed).width() / 2, chip(ed).height() / 2)).toPoint()
    QTest.mouseMove(ed.window, centre)
    ed.qtbot.waitUntil(lambda: any("Pick a value" in t and "Alt+Down" in t
                                   for t in texts_shown(ed.window.contentItem())), timeout=2000)


# -- the picker -----------------------------------------------------------------------------


def test_alt_down_opens_the_key_picker_on_the_current_key(ed):
    song(ed, TEXT)
    open_at_caret(ed, TEXT, "{key: G}")
    assert picker(ed).property("kind") == "key"
    assert focused(ed).objectName() == "key:G"
    # Every key of the Tk Insert Key dialog, no more.
    names = {"key:" + k for k in insert_key_options("american")}
    found = {n for n in names if find(ed.window.contentItem(), n) is not None}
    assert found == names
    assert find(ed.window.contentItem(), "key:H") is None


def test_enter_on_a_key_chip_replaces_the_value_as_one_undo_step(ed):
    song(ed, TEXT)
    open_at_caret(ed, TEXT, "{key: G}")
    ed.key(Qt.Key.Key_Right)            # G -> A♭ (pitch order, twins side by side)
    assert focused(ed).objectName() == "key:Ab"
    ed.key(Qt.Key.Key_Left)
    ed.key(Qt.Key.Key_Left)
    assert focused(ed).objectName() == "key:F#"
    ed.key(Qt.Key.Key_Return)
    after = TEXT.replace("{key: G}", "{key: F#}")
    ed.qtbot.waitUntil(lambda: ed.text() == after, timeout=2000)
    assert not is_open(ed)
    assert ed.area.hasActiveFocus()
    assert ed.area.property("cursorPosition") == after.index("{key: F#}") + len("{key: F#}")
    ed.key(Qt.Key.Key_Z, CTRL)
    assert ed.text() == TEXT


def test_escape_closes_without_a_change(ed):
    song(ed, TEXT)
    open_at_caret(ed, TEXT, "{key: G}")
    ed.key(Qt.Key.Key_Escape)
    ed.qtbot.waitUntil(lambda: not is_open(ed), timeout=1000)
    ed.run(60)
    assert ed.text() == TEXT and ed.area.hasActiveFocus()


def test_the_picker_closes_when_the_editor_locks(ed):
    song(ed, TEXT)
    open_at_caret(ed, TEXT, "{key: G}")
    ed.window.setProperty("mode", "play")
    ed.qtbot.waitUntil(lambda: not is_open(ed), timeout=1000)
    assert ed.text() == TEXT


def test_clicking_a_chip_with_the_mouse(ed):
    song(ed, TEXT)
    caret_in(ed, TEXT, "{key: G}")
    click_item(ed, chip(ed))
    ed.qtbot.waitUntil(lambda: is_open(ed), timeout=1000)
    ed.run(30)
    click_item(ed, item(ed, "key:Em"))
    ed.qtbot.waitUntil(lambda: ed.text() == TEXT.replace("{key: G}", "{key: Em}"), timeout=2000)


def test_european_songs_get_european_keys(ed):
    text = "{key: Sol}\nDo Re\n"
    song(ed, text)
    ed.store.submit("set_notation", {"notation": "european"})
    ed.run(60)
    open_at_caret(ed, text, "{key: Sol}")
    assert focused(ed).objectName() == "key:Sol"
    assert item(ed, "key:Reb").property("text") == "Re♭"
    ed.key(Qt.Key.Key_Escape)


def test_time_presets_and_beats_over_a_unit(ed):
    song(ed, TEXT)
    open_at_caret(ed, TEXT, "{time: 3/4}")
    assert focused(ed).objectName() == "time:3/4"
    click_item(ed, item(ed, "time:6/8"))
    after = TEXT.replace("{time: 3/4}", "{time: 6/8}")
    ed.qtbot.waitUntil(lambda: ed.text() == after, timeout=2000)
    # Beats and a unit, as the Tk Insert Time dialog: 5 / 16.
    open_at_caret(ed, after, "{time: 6/8}")
    box = item(ed, "pickerBox")
    assert box.property("value") == 6
    box.forceActiveFocus()
    ed.key(Qt.Key.Key_Up)
    ed.key(Qt.Key.Key_Down)
    ed.key(Qt.Key.Key_Down)
    click_item(ed, item(ed, "unit:16"))
    click_item(ed, item(ed, "pickerApply"))
    ed.qtbot.waitUntil(lambda: ed.text() == after.replace("{time: 6/8}", "{time: 5/16}"),
                       timeout=2000)


def test_tempo_forms_and_the_number_box(ed):
    song(ed, TEXT)
    open_at_caret(ed, TEXT, "{bpm: 120}")
    box = item(ed, "pickerBox")
    assert focused(ed) is not None and box.property("value") == 120
    click_item(ed, item(ed, "tempo:-10"))
    box = item(ed, "pickerBox")
    assert box.property("value") == -10
    box.forceActiveFocus()
    ed.key(Qt.Key.Key_A, CTRL)
    for k in (Qt.Key.Key_Minus, Qt.Key.Key_2, Qt.Key.Key_5):
        ed.key(k)
    ed.key(Qt.Key.Key_Return)
    after = TEXT.replace("{bpm: 120}", "{bpm: -25}")
    ed.qtbot.waitUntil(lambda: ed.text() == after, timeout=2000)
    # reset applies at once.
    open_at_caret(ed, after, "{bpm: -25}")
    click_item(ed, item(ed, "tempo:reset"))
    ed.qtbot.waitUntil(lambda: ed.text() == after.replace("{bpm: -25}", "{bpm: reset}"),
                       timeout=2000)


class FakeClock:
    """The Tap button's clock: each call is the next time in ``times``."""

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def tap_at(ed, clock, *times):
    for t in times:
        clock.now = t
        click_item(ed, item(ed, "pickerTap"))
        ed.run(5)


def test_tap_finds_the_tempo_and_apply_writes_it(ed):
    clock = FakeClock()
    ed.harness.app.pickers._clock = clock
    song(ed, TEXT)
    open_at_caret(ed, TEXT, "{bpm: 120}")
    count = item(ed, "pickerTapCount")
    assert count.property("text") == "tap the beat"
    tap_at(ed, clock, 10.0)
    # One tap: no tempo yet, the box keeps 120.
    assert item(ed, "pickerBox").property("value") == 120
    assert count.property("text") == "1 tap"
    tap_at(ed, clock, 10.6, 11.2, 11.8)
    assert item(ed, "pickerBox").property("value") == 100
    assert count.property("text") == "4 taps"
    assert ed.text() == TEXT                        # nothing written before Apply
    # The box kept the focus: the keyboard still works on it.
    assert focused(ed) is not None and "pickerBox" in (
        focused(ed).objectName() + str(focused(ed).parentItem().objectName()))
    click_item(ed, item(ed, "pickerApply"))
    after = TEXT.replace("{bpm: 120}", "{bpm: 100}")
    ed.qtbot.waitUntil(lambda: ed.text() == after, timeout=2000)


def test_tap_after_typing_or_from_another_form_gives_a_bpm(ed):
    clock = FakeClock()
    ed.harness.app.pickers._clock = clock
    text = "{bpm: +10}\nC\n"
    song(ed, text)
    open_at_caret(ed, text, "{bpm: +10}")
    box = item(ed, "pickerBox")
    box.forceActiveFocus()
    ed.key(Qt.Key.Key_Up)                           # the box was used: its binding is gone
    tap_at(ed, clock, 1.0, 1.5, 2.0)
    assert item(ed, "tempo:120").property("current") is True   # now an absolute bpm
    assert item(ed, "pickerBox").property("value") == 120
    box = item(ed, "pickerBox")
    box.forceActiveFocus()
    ed.key(Qt.Key.Key_Return)
    ed.qtbot.waitUntil(lambda: ed.text() == "{bpm: 120}\nC\n", timeout=2000)


def test_a_pause_or_a_reopened_picker_starts_a_new_count(ed):
    clock = FakeClock()
    ed.harness.app.pickers._clock = clock
    song(ed, TEXT)
    open_at_caret(ed, TEXT, "{bpm: 120}")
    tap_at(ed, clock, 1.0, 1.5, 2.0)
    assert item(ed, "pickerTapCount").property("text") == "3 taps"
    tap_at(ed, clock, 6.0)                          # a pause: a new count
    assert item(ed, "pickerTapCount").property("text") == "1 tap"
    assert item(ed, "pickerBox").property("value") == 120
    ed.key(Qt.Key.Key_Escape)
    ed.qtbot.waitUntil(lambda: not is_open(ed), timeout=1000)
    open_at_caret(ed, TEXT, "{bpm: 120}")
    assert item(ed, "pickerTapCount").property("text") == "tap the beat"
    assert ed.text() == TEXT


def test_a_multiplier_takes_quarter_steps(ed):
    text = "{bpm: 1.5x}\nC\n"
    song(ed, text)
    open_at_caret(ed, text, "{bpm: 1.5x}")
    box = item(ed, "pickerBox")
    assert box.property("displayText") == "1.5"
    box.forceActiveFocus()
    ed.key(Qt.Key.Key_Up)
    ed.key(Qt.Key.Key_Return)
    ed.qtbot.waitUntil(lambda: ed.text() == "{bpm: 1.75x}\nC\n", timeout=2000)


def test_capo_box_with_enter(ed):
    song(ed, TEXT)
    open_at_caret(ed, TEXT, "{capo: 2}")
    assert focused(ed).objectName() == "pickerBox" or "pickerBox" in str(focused(ed).parentItem())
    for k in (Qt.Key.Key_Up, Qt.Key.Key_Up, Qt.Key.Key_Up):
        ed.key(k)
    ed.key(Qt.Key.Key_Return)
    ed.qtbot.waitUntil(lambda: ed.text() == TEXT.replace("{capo: 2}", "{capo: 5}"), timeout=2000)


def test_loop_offers_the_labels_above_and_writes_the_count(ed):
    song(ed, TEXT)
    open_at_caret(ed, TEXT, "{loop: verse}")
    # Labels above the loop, in song order, then @start.
    for name in ("loop:verse", "loop:chorus", "loop:@start"):
        assert find(ed.window.contentItem(), name) is not None, name
    assert item(ed, "loop:verse").property("current") is True
    box = item(ed, "pickerBox")
    assert box.property("value") == 2          # {loop: verse} plays twice
    click_item(ed, item(ed, "loop:chorus"))
    box.forceActiveFocus()
    ed.key(Qt.Key.Key_Up)
    ed.key(Qt.Key.Key_Return)
    ed.qtbot.waitUntil(lambda: ed.text() == TEXT.replace("{loop: verse}", "{loop: chorus 3}"),
                       timeout=2000)


def test_a_loop_whose_label_isnt_offered_waits_for_one(ed):
    text = "{loop: nowhere}\n{label: later}\nC\n"
    song(ed, text)
    open_at_caret(ed, text, "{loop: nowhere}")
    assert item(ed, "pickerApply").property("enabled") is False
    assert find(ed.window.contentItem(), "loop:later") is None     # below the loop
    click_item(ed, item(ed, "loop:@start"))
    assert item(ed, "pickerApply").property("enabled") is True
    click_item(ed, item(ed, "pickerApply"))
    ed.qtbot.waitUntil(lambda: ed.text() == text.replace("nowhere", "@start 2"), timeout=2000)


def test_a_pick_of_the_same_value_changes_nothing(ed):
    song(ed, TEXT)
    open_at_caret(ed, TEXT, "{key: G}")
    ed.key(Qt.Key.Key_Return)
    ed.qtbot.waitUntil(lambda: not is_open(ed), timeout=1000)
    ed.run(60)
    assert ed.text() == TEXT
    assert not any(name == "replace_directive_value" for name, _ in ed.submitted)


def test_a_directive_that_changed_while_the_picker_was_open_isnt_touched(ed):
    song(ed, TEXT)
    model = ed.harness.app.pickers
    caret_in(ed, TEXT, "{key: G}")
    stale = dict(model.property("caretPicker"))
    stale["cpEnd"] += 1
    assert model.apply(stale, "D") is False
    assert model.apply(model.property("caretPicker"), "") is False
    ed.run(60)
    assert ed.text() == TEXT


# -- insert_snippet end to end (B4's palette insert) -------------------------------------------


def test_insert_snippet_selects_the_value_so_typing_replaces_it(ed):
    song(ed, "C G\n")
    ed.set_cursor(3)
    ed.store.submit("insert_snippet", {"offset": 3, "text": "{bpm: 120}"})
    ed.qtbot.waitUntil(lambda: ed.text() == "C G {bpm: 120}\n", timeout=2000)
    assert ed.area.property("selectedText") == "120"
    ed.type("90")
    ed.qtbot.waitUntil(lambda: ed.session.text == "C G {bpm: 90}\n", timeout=2000)
    # The chip is there for the new directive; its picker sees the typed value.
    ed.qtbot.waitUntil(lambda: ed.harness.app.pickers.property("caretPicker").get("current")
                       == "90", timeout=1000)
    # One undo step each: the typing, then the insert.
    ed.key(Qt.Key.Key_Z, CTRL)
    assert ed.text() == "C G {bpm: 120}\n"
    ed.key(Qt.Key.Key_Z, CTRL)
    assert ed.text() == "C G\n"


def test_insert_snippet_fills_the_template_for_the_song(ed):
    text = "{label: verse}\nDo Re\n"
    song(ed, text)
    ed.store.submit("set_notation", {"notation": "european"})
    ed.run(60)
    ed.store.submit("insert_snippet", {"offset": len(text), "text": "{key: G}"})
    ed.qtbot.waitUntil(lambda: ed.text() == text + "{key: Sol}", timeout=2000)
    assert ed.area.property("selectedText") == "Sol"
    # A loop to a label the song hasn't: the nearest one above instead.
    ed.store.submit("insert_snippet", {"offset": len(ed.text()), "text": "{loop: chorus}"})
    ed.qtbot.waitUntil(lambda: ed.text().endswith("{loop: verse}"), timeout=2000)


# -- the values (Python) -------------------------------------------------------------------


def picker_for(kind, current, labels=()):
    ctx = pickers.PickerContext("american", tuple(labels), current)
    return pickers.DirectivePicker(kind, 0, 1, 0, 1, pickers.picker_options(kind, ctx))


def test_initial_values_read_the_value_as_typed():
    assert initial_values(picker_for("time", "7/8")) == {"beats": 7, "unit": 8}
    assert initial_values(picker_for("time", "3/5")) == {"beats": 4, "unit": 4}
    assert initial_values(picker_for("tempo", "50%")) == {"form": "pct", "number": 50}
    assert initial_values(picker_for("tempo", "999")) == {"form": "abs", "number": 400}
    assert initial_values(picker_for("tempo", "1.3x")) == {"form": "mul", "number": 1.25}
    assert initial_values(picker_for("tempo", "reset")) == {"form": "reset", "number": 0}
    assert initial_values(picker_for("capo", "x")) == {"fret": 0}
    assert initial_values(picker_for("capo", "30")) == {"fret": 12}
    assert initial_values(picker_for("loop", "verse", ["verse"])) == {"label": "verse", "count": 2}
    assert initial_values(picker_for("loop", "intro 40", ["verse"])) == {"label": "", "count": 16}
    # An existing count of 1 (valid by hand, plays once) opens showing the minimum, 2.
    assert initial_values(picker_for("loop", "verse 1", ["verse"])) == {"label": "verse", "count": 2}
    assert initial_values(picker_for("key", "G")) == {}


def test_compose_value_gives_only_values_the_insert_dialogs_took():
    composed = [
        ("key", {"value": "Db"}), ("time", {"value": "6/8"}), ("time", {"beats": 5, "unit": 16}),
        ("tempo", {"form": "abs", "number": 90}), ("tempo", {"form": "rel", "number": -10}),
        ("tempo", {"form": "pct", "number": 50}), ("tempo", {"form": "mul", "number": 0.25}),
        ("tempo", {"form": "reset"}), ("capo", {"fret": 7}),
        ("loop", {"label": "verse", "count": 3}),
    ]
    values = [compose_value(kind, parts) for kind, parts in composed]
    assert values == ["Db", "6/8", "5/16", "90", "-10", "50%", "0.25x", "reset", "7", "verse 3"]
    fields = {"key": "key", "tempo": "value", "capo": "capo"}
    for (kind, _), value in zip(composed, values):
        if kind == "loop":
            problem = check_directive("loop", {"label": "verse", "count": "3"},
                                      existing_labels={"verse"})
        elif kind == "time":
            beats, unit = value.split("/")
            problem = check_directive("time", {"beats": beats, "unit": unit})
        else:
            problem = check_directive("bpm" if kind == "tempo" else kind, {fields[kind]: value})
        assert problem is None, (kind, value, problem)


def test_compose_value_refuses_what_isnt_a_value():
    assert compose_value("time", {"beats": 17, "unit": 4}) == ""
    assert compose_value("time", {"beats": 4, "unit": 3}) == ""
    assert compose_value("tempo", {"form": "abs", "number": 401}) == ""
    assert compose_value("tempo", {"form": "mul", "number": 0.3}) == ""
    assert compose_value("capo", {"fret": 13}) == ""
    assert compose_value("loop", {"label": "", "count": 2}) == ""
    assert compose_value("loop", {"label": "verse", "count": 0}) == ""
    assert compose_value("loop", {"label": "verse", "count": 1}) == ""
    assert compose_value("key", {}) == ""
    assert compose_value("nope", {"value": "x"}) == ""


# -- Edit › Change value… -------------------------------------------------------------------


def test_the_edit_menus_change_value_opens_the_caret_picker(ed):
    # Tibi (2026-11-15): every edit command in the Edit menu, Alt+Down's too.
    from PySide6.QtCore import QMetaObject
    song(ed, TEXT)
    action, row = ed.item("pickerAction"), ed.item("barPicker")
    assert row.property("text") == action.property("text")
    assert row.property("text").replace("&", "") == "Change value…"
    assert row.property("shortcutText") == "Alt+Down"
    ed.set_cursor(TEXT.index("C G") + 1)                 # a chord line: no picker
    ed.run(30)
    assert action.property("enabled") is False and row.property("enabled") is False
    caret_in(ed, TEXT, "{key: G}")
    ed.qtbot.waitUntil(lambda: action.property("enabled") is True, timeout=1000)
    QMetaObject.invokeMethod(row, "click")              # as a click on the menu row
    ed.qtbot.waitUntil(lambda: is_open(ed), timeout=1000)
    assert action.property("enabled") is False           # not again while it shows


def test_change_value_is_off_while_playing(ed):
    song(ed, TEXT)
    caret_in(ed, TEXT, "{key: G}")
    action = ed.item("pickerAction")
    ed.qtbot.waitUntil(lambda: action.property("enabled") is True, timeout=1000)
    ed.harness.player.auto_play = False
    ed.store.submit("play_pause", {"from_offset": None})
    ed.qtbot.waitUntil(lambda: ed.area.property("readOnly") is True, timeout=3000)
    assert action.property("enabled") is False
    ed.store.submit("stop")
