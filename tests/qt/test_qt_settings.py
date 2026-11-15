"""The Settings window (plan step G1): SettingsModel and SettingsWindow.qml.

The whole front end runs in the test process (``tests/qt/conftest.py``); the
window is opened the way F1's menu will (``AppDialogs.openSettings``).
Repeater and Loader delegates aren't in the QObject tree (pitfall 25), so
the form's fields are found by walking the visual tree (:func:`find`).
"""

import json

import pytest

from tests.conftest import QT_PROBLEM

if QT_PROBLEM:
    pytest.skip(f"Qt not available: {QT_PROBLEM}", allow_module_level=True)

from PySide6.QtCore import QMetaObject, QObject, QPoint, QPointF, Qt, Q_ARG, Q_RETURN_ARG  # noqa: E402
from PySide6.QtGui import QGuiApplication, QWheelEvent  # noqa: E402
from PySide6.QtQuick import QQuickItem, QQuickWindow  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from chordnotepad.settings_forms.voicing_texts import EDITOR_TEXTS, TOOLTIPS  # noqa: E402
from chordnotepad_desktop import settings_window  # noqa: E402
from tests.qt.conftest import QtAppHarness, write_config  # noqa: E402


def find(root, name):
    """The item named ``name`` under ``root`` (an item or a window), through
    Repeater and Loader delegates too; None if there is none."""
    if isinstance(root, QQuickWindow):
        root = root.contentItem()
    if root.objectName() == name:
        return root
    for child in root.childItems():
        hit = find(child, name)
        if hit is not None:
            return hit
    return None


def tooltip(quick_item):
    """The text of an item's attached ToolTip."""
    for child in quick_item.findChildren(QObject):
        if child.metaObject().className() == "QQuickToolTipAttached":
            return child.property("text")
    return None


def escaped(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")


def click(window, quick_item):
    centre = quick_item.mapToScene(QPointF(quick_item.width() / 2, quick_item.height() / 2))
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                     centre.toPoint())


class Settings:
    """The started app with its Settings window open."""

    def __init__(self, harness, qtbot):
        self.harness, self.qtbot = harness, qtbot
        self.model = harness.app.dialogs.settings
        self.hub = harness.window.findChild(QObject, "appDialogs")
        self.window = harness.window.findChild(QQuickWindow, "settingsWindow")

    def open(self, page="general"):
        QMetaObject.invokeMethod(self.hub, "openSettings", Q_ARG("QVariant", page))
        self.qtbot.waitUntil(lambda: self.window.isVisible(), timeout=2000)
        self.qtbot.waitUntil(lambda: self.editor("active") is True, timeout=2000)
        self.qtbot.waitUntil(lambda: self.model.schema is not None, timeout=2000)
        return self

    def activate(self):
        self.window.requestActivate()
        self.qtbot.waitUntil(lambda: QGuiApplication.focusWindow() is self.window, timeout=1000)

    def editor(self, key):
        return self.harness.store.state("VoicingEditorState").value(key)

    def config(self, key):
        return self.harness.app.core.config.get(key)

    def saved(self):
        return json.loads(self.harness.config_file().read_text(encoding="utf-8"))

    def item(self, name):
        found = find(self.window, name)
        assert found is not None, name
        return found

    def popup(self, name):
        found = self.window.findChild(QObject, name)
        assert found is not None, name
        return found

    def click(self, name):
        click(self.window, self.item(name))

    def key(self, key, modifier=Qt.KeyboardModifier.NoModifier):
        QTest.keyClick(self.window, key, modifier)

    def type(self, text):
        for ch in text:
            QTest.keyClick(self.window, ch)

    def wait(self, ms=50):
        self.qtbot.wait(ms)

    def add_voicing(self):
        self.window.setProperty("page", "voicings")
        self.model.addVoicing()
        self.qtbot.waitUntil(lambda: self.editor("selected") == "New voicing", timeout=2000)


@pytest.fixture
def settings(qapp, qtbot, tmp_path):
    write_config(tmp_path, show_quick_start_on_startup=False)
    harness = QtAppHarness(qapp, tmp_path).start()
    qtbot.waitUntil(lambda: harness.window.property("contentReady") is True, timeout=3000)
    s = Settings(harness, qtbot).open()
    yield s
    warnings, unexpected = list(harness.app.warnings), list(harness.unexpected)
    harness.shutdown()
    qtbot.wait(1)
    assert warnings == [] and unexpected == []


# -- opening and closing -----------------------------------------------------------------


def test_opening_starts_a_settings_edit_and_closing_ends_it(settings):
    assert settings.window.isVisible()
    assert settings.model.isOpen
    settings.click("settingsClose")
    settings.qtbot.waitUntil(lambda: not settings.window.isVisible(), timeout=2000)
    settings.qtbot.waitUntil(lambda: settings.editor("active") is False, timeout=2000)
    assert not settings.model.isOpen


def test_escape_closes_the_settings_window(settings):
    settings.activate()
    settings.key(Qt.Key.Key_Escape)
    settings.qtbot.waitUntil(lambda: not settings.window.isVisible(), timeout=2000)
    assert settings.editor("active") is False


def test_the_pages(settings):
    for page in ("general", "playback", "voicings"):
        settings.click("page:" + page)
        settings.qtbot.waitUntil(lambda: settings.window.property("page") == page, timeout=1000)
    assert settings.item("voicingPlaceholder").isVisible()
    assert settings.item("voicingPlaceholder").property("text") == EDITOR_TEXTS["placeholder"]


# -- General and Playback ----------------------------------------------------------------------


def test_a_change_is_saved_and_applied_at_once(settings):
    settings.click("setting:word_wrap")
    settings.qtbot.waitUntil(lambda: settings.config("word_wrap") is True, timeout=2000)
    assert settings.saved()["word_wrap"] is True
    # Applied to the editor at once (the session's apply_settings).
    settings.qtbot.waitUntil(lambda: settings.harness.app.editor.wordWrap is True, timeout=2000)


def test_q8_a_typed_number_out_of_range_is_marked_and_never_saved(settings):
    assert settings.config("max_recent_files") == 10
    settings.model.setNumber("max_recent_files", "60", True)
    settings.wait(100)
    assert settings.config("max_recent_files") == 10
    assert settings.model.numberErrors == {"max_recent_files": "Enter a whole number from 1 to 50."}
    # Kept for next time as invalid_numbers, not as a value.
    settings.qtbot.waitUntil(lambda: settings.editor("staged_numbers") == {"max_recent_files": "60"},
                             timeout=2000)
    field = settings.item("setting:max_recent_files")
    assert field.property("error") == "Enter a whole number from 1 to 50."
    settings.model.setNumber("max_recent_files", "20", True)
    settings.qtbot.waitUntil(lambda: settings.config("max_recent_files") == 20, timeout=2000)
    assert settings.model.numberErrors == {}
    assert settings.editor("staged_numbers") == {}


def test_a_number_typed_in_the_field_is_saved_when_the_typing_rests(settings):
    settings.activate()
    field = settings.item("setting:font_size")
    field.forceActiveFocus()
    QMetaObject.invokeMethod(field, "selectAll")
    settings.type("14")
    settings.wait(settings_window.DRAFT_SAVE_DELAY_MS + 200)
    settings.qtbot.waitUntil(lambda: settings.config("font_size") == 14, timeout=2000)
    # The arrows step it and save at once.
    settings.key(Qt.Key.Key_Up)
    settings.qtbot.waitUntil(lambda: settings.config("font_size") == 15, timeout=2000)
    # Not a number: marked, the saved size stays.
    QMetaObject.invokeMethod(field, "selectAll")
    settings.type("x")
    settings.key(Qt.Key.Key_Return)
    settings.qtbot.waitUntil(lambda: field.property("error") != "", timeout=1000)
    assert settings.config("font_size") == 15


def test_the_bpm_and_time_signature_ranges(settings):
    assert settings.model.limits["bpm"] == [20, 400]
    assert settings.model.limits["time_signature_beats"] == [1, 16]
    settings.model.setNumber("bpm", "19", True)
    settings.model.setNumber("time_signature_beats", "17", True)
    settings.wait(100)
    assert settings.config("bpm") == 120 and settings.config("time_signature_beats") == 4
    assert settings.model.numberErrors["bpm"] == "Enter a whole number from 20 to 400."
    settings.model.setNumber("bpm", "96", True)
    settings.model.setValue("time_signature_unit", 8)
    settings.qtbot.waitUntil(lambda: settings.config("bpm") == 96, timeout=2000)
    settings.qtbot.waitUntil(lambda: settings.config("time_signature_unit") == 8, timeout=2000)
    assert settings.model.choices["timeUnits"] == [2, 4, 8, 16]


def test_the_notation_respells_the_default_key_which_stays_american(settings):
    settings.model.setValue("key", "G")
    settings.qtbot.waitUntil(lambda: settings.config("key") == "G", timeout=2000)
    settings.click("setting:notation:european")
    settings.qtbot.waitUntil(lambda: settings.config("notation") == "european", timeout=2000)
    labels = [k["label"] for k in settings.model.keyChoices]
    assert labels[0] == "None" and "Sol" in labels and "G" not in labels
    assert settings.item("setting:key").property("currentText") == "Sol"
    assert settings.config("key") == "G"


def test_the_notation_respells_the_voicing_note_names(settings):
    settings.add_voicing()
    assert settings.editor("values")["tuning"] == "E2 A2 D3 G3 B3 E4"
    settings.model.setValue("notation", "european")
    settings.qtbot.waitUntil(lambda: settings.editor("values")["tuning"] == "Mi2 La2 Re3 Sol3 Si3 Mi4",
                             timeout=2000)
    # Stored as MIDI numbers either way.
    assert settings.config("voicings")["New voicing"]["tuning"] == [40, 45, 50, 55, 59, 64]


def test_the_font_list_is_filtered_and_shows_the_editors_font(settings):
    families = settings.model.fontFamilies
    assert families and not any(f.startswith("@") or not f.strip() for f in families)
    assert families == sorted(families, key=str.lower)
    # The config's TkFixedFont shows as the font it stands for.
    assert settings.config("font_family") == "TkFixedFont"
    assert settings.model.fontFamily == "Noto Sans Mono"
    assert settings.item("setting:font_family").property("currentText") == "Noto Sans Mono"
    other = next(f for f in families if f != "Noto Sans Mono")
    settings.model.setValue("font_family", other)
    settings.qtbot.waitUntil(lambda: settings.config("font_family") == other, timeout=2000)


def test_log_level_quick_start_soundfont_and_driver(settings):
    settings.model.setValue("log_level", "DEBUG")
    settings.model.setValue("show_quick_start_on_startup", True)
    settings.model.setValue("soundfont_path", "/music/My Font.sf2")
    settings.model.setValue("audio_driver", "jack")
    settings.qtbot.waitUntil(lambda: settings.config("audio_driver") == "jack", timeout=2000)
    assert settings.config("log_level") == "DEBUG"
    assert settings.config("show_quick_start_on_startup") is True
    assert settings.config("soundfont_path") == "/music/My Font.sf2"
    # Empty means the bundled soundfont / auto-detect.
    settings.model.setValue("soundfont_path", "  ")
    settings.model.setValue("audio_driver", "")
    settings.qtbot.waitUntil(lambda: settings.config("audio_driver") is None, timeout=2000)
    assert settings.config("soundfont_path") is None
    assert "" in settings.model.choices["audioDrivers"]
    assert settings.model.choices["logLevels"] == ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def test_the_soundfont_file_dialog_takes_sf2_files(settings):
    dialog = settings.window.findChild(QObject, "soundfontDialog") or next(
        o for o in settings.window.findChildren(QObject) if o.property("title") == "Select SoundFont")
    assert dialog.property("title") == "Select SoundFont"
    assert dialog.property("nameFilters")[0] == "SoundFont files (*.sf2)"


def test_the_theme_switches_live(settings):
    pane = settings.harness.window.findChild(QQuickItem, "editorPane")
    light = pane.property("color").name()
    settings.model.setValue("ui_theme", "dark")
    settings.qtbot.waitUntil(lambda: settings.config("ui_theme") == "dark", timeout=2000)
    settings.qtbot.waitUntil(lambda: pane.property("color").name() == "#1e1f22", timeout=2000)
    settings.model.setValue("ui_theme", "light")
    settings.qtbot.waitUntil(lambda: pane.property("color").name() == light, timeout=2000)
    # "Follow the system": offscreen has no dark scheme.
    settings.model.setValue("ui_theme", "system")
    settings.qtbot.waitUntil(lambda: settings.config("ui_theme") == "system", timeout=2000)
    assert pane.property("color").name() == light


def test_values_changed_elsewhere_while_open_are_shown_and_not_undone(settings):
    """The window isn't modal: the ☰ Dark theme, text zoom and View › Word
    wrap change the config while it is open. The window shows the new values,
    and its next save (it sends every General/Playback value) keeps them."""
    store = settings.harness.store
    size = settings.config("font_size")
    store.submit("set_ui_theme", {"theme": "dark"})
    store.submit("step_font_size", {"delta": 2})
    store.submit("set_word_wrap", {"on": True})
    settings.qtbot.waitUntil(lambda: (settings.model.values["ui_theme"],
                                      settings.model.values["font_size"],
                                      settings.model.values["word_wrap"]) == ("dark", size + 2, True),
                             timeout=2000)
    # A change in the window now writes the whole draft: the others stay.
    settings.model.setValue("show_quick_start_on_startup", True)
    settings.qtbot.waitUntil(lambda: settings.config("show_quick_start_on_startup") is True,
                             timeout=2000)
    settings.wait(100)
    assert (settings.config("ui_theme"), settings.config("font_size"),
            settings.config("word_wrap")) == ("dark", size + 2, True)
    assert settings.harness.app.editor.wordWrap is True


# -- Voicings --------------------------------------------------------------------------------


def test_plus_adds_a_guitar_voicing_and_selects_it(settings):
    settings.click("page:voicings")
    settings.click("addVoicing")
    settings.qtbot.waitUntil(lambda: settings.editor("selected") == "New voicing", timeout=2000)
    assert settings.editor("model") == "fretboard"
    assert settings.editor("values")["tuning"] == "E2 A2 D3 G3 B3 E4"
    groups = {g["model"]: g["names"] for g in settings.editor("groups")}
    assert groups["fretboard"] == ["New voicing"]
    assert [g["model"] for g in settings.editor("groups")] == ["fretboard", "piano", "ensemble"]
    settings.qtbot.waitUntil(lambda: "New voicing" in settings.config("voicings"), timeout=2000)
    assert not settings.item("voicingPlaceholder").isVisible()


def test_minus_asks_first(settings):
    settings.add_voicing()
    settings.click("removeVoicing")
    dialog = settings.popup("settingsConfirm")
    settings.qtbot.waitUntil(lambda: dialog.property("opened") is True, timeout=2000)
    assert dialog.property("title") == "Remove Voicing"
    assert dialog.property("message") == "Remove voicing 'New voicing'?"
    settings.click("settingsConfirmCancel")
    settings.qtbot.waitUntil(lambda: dialog.property("visible") is False, timeout=2000)
    assert settings.editor("selected") == "New voicing"
    settings.click("removeVoicing")
    settings.qtbot.waitUntil(lambda: dialog.property("opened") is True, timeout=2000)
    settings.click("settingsConfirmYes")
    settings.qtbot.waitUntil(lambda: settings.editor("selected") is None, timeout=2000)
    settings.qtbot.waitUntil(lambda: "New voicing" not in (settings.config("voicings") or {}),
                             timeout=2000)


@pytest.mark.parametrize("name, message", [
    ("", "Voicing name cannot be empty."),
    ("guitar (drop d)", "'Guitar (Drop D)' is a built-in voicing. Choose another name."),
    ("new VOICING 2", "A voicing named 'New voicing 2' already exists."),
])
def test_the_name_rules_and_their_messages(settings, name, message):
    settings.add_voicing()
    settings.model.addVoicing()
    settings.qtbot.waitUntil(lambda: settings.editor("selected") == "New voicing 2", timeout=2000)
    settings.model.selectVoicing("New voicing")
    settings.qtbot.waitUntil(lambda: settings.editor("selected") == "New voicing", timeout=2000)
    settings.activate()
    field = settings.item("voicingName")
    field.forceActiveFocus()
    QMetaObject.invokeMethod(field, "selectAll")
    if name:
        settings.type(name)
    else:
        settings.key(Qt.Key.Key_Delete)
    settings.key(Qt.Key.Key_Return)
    # Shown over the Settings window (it is the one in use).
    error = settings.popup("settingsErrorDialog")
    settings.qtbot.waitUntil(lambda: error.property("visible") is True, timeout=2000)
    assert error.property("title") == EDITOR_TEXTS["rename_error_title"]
    assert message in error.property("message")
    # The name goes back to the voicing's.
    settings.qtbot.waitUntil(lambda: field.property("text") == "New voicing", timeout=1000)
    settings.key(Qt.Key.Key_Escape)
    settings.qtbot.waitUntil(lambda: error.property("visible") is False, timeout=1000)
    # Once: not again when the field lost the focus to the dialog.
    settings.wait(100)
    assert error.property("visible") is False and settings.harness.app.presenter.showing is None
    assert settings.window.isVisible()


def test_a_rename_commits_on_enter(settings):
    settings.add_voicing()
    settings.activate()
    field = settings.item("voicingName")
    field.forceActiveFocus()
    QMetaObject.invokeMethod(field, "selectAll")
    settings.type("Baritone")
    settings.key(Qt.Key.Key_Return)
    settings.qtbot.waitUntil(lambda: settings.editor("selected") == "Baritone", timeout=2000)
    settings.qtbot.waitUntil(lambda: "Baritone" in settings.config("voicings"), timeout=2000)


def test_the_name_help_names_the_qt_voicing_menus(settings):
    assert settings.model.schema["help"]["name"] == "The name of this voicing, shown in the Voicing menus."
    settings.add_voicing()
    assert settings.item("voicingName").property("tip") == settings.model.schema["help"]["name"]


def test_a_wrong_field_is_marked_with_its_message_and_never_saved(settings):
    settings.add_voicing()
    settings.qtbot.waitUntil(lambda: "New voicing" in settings.config("voicings"), timeout=2000)
    saved_span = settings.config("voicings")["New voicing"].get("max_span")
    settings.activate()
    field = settings.item("field:max_span")
    field.forceActiveFocus()
    QMetaObject.invokeMethod(field, "selectAll")
    settings.type("x")
    # Re-checked on every keystroke: marked before Enter.
    settings.qtbot.waitUntil(lambda: field.property("error") == "Must be a whole number", timeout=2000)
    banner = settings.item("voicingErrors")
    assert banner.isVisible()
    assert settings.item("voicingErrorsText").property("text").startswith(EDITOR_TEXTS["errors_banner"])
    # Tk's mark: the field's help, then "⚠ message".
    assert tooltip(field) == escaped(TOOLTIPS["max_span"]) + "<br><br>⚠ Must be a whole number"
    settings.key(Qt.Key.Key_Return)
    settings.wait(100)
    assert settings.config("voicings")["New voicing"].get("max_span") == saved_span
    assert "New voicing" in settings.editor("invalid")
    assert any(p["field_id"] == "max_span" for p in settings.editor("problems"))


def test_captions_share_their_fields_help(settings):
    settings.add_voicing()
    field = settings.item("field:max_fret")
    assert tooltip(field) == escaped(TOOLTIPS["max_fret"])
    assert settings.item("field:allow_barres").property("text") == "Allow barre chords"


def test_switching_the_model_asks_first_when_edited(settings):
    settings.add_voicing()
    box = settings.item("voicingModel")
    # Not edited yet: no question.
    settings.window.findChild(QObject, "voicingsPage")
    QMetaObject.invokeMethod(box, "activated", Q_ARG(int, 2))
    settings.qtbot.waitUntil(lambda: settings.editor("model") == "piano", timeout=2000)
    settings.model.setField("hand_span", "12", True)
    settings.qtbot.waitUntil(lambda: settings.editor("dirty") is True, timeout=2000)
    QMetaObject.invokeMethod(box, "activated", Q_ARG(int, 1))
    dialog = settings.popup("settingsConfirm")
    settings.qtbot.waitUntil(lambda: dialog.property("opened") is True, timeout=2000)
    assert dialog.property("title") == EDITOR_TEXTS["model_confirm_title"]
    assert dialog.property("message") == EDITOR_TEXTS["model_confirm"]
    # The box shows the voicing's model until the answer.
    assert box.property("currentText") == "Piano"
    settings.click("settingsConfirmYes")
    settings.qtbot.waitUntil(lambda: settings.editor("model") == "ensemble", timeout=2000)
    assert box.property("currentText") == "Ensemble"


def test_copy_from_existing_lists_the_presets_and_asks(settings):
    settings.add_voicing()
    settings.click("copyFromExisting")
    menu = settings.popup("presetMenu")
    settings.qtbot.waitUntil(lambda: menu.property("opened") is True, timeout=2000)
    items = [QMetaObject.invokeMethod(menu, "itemAt", Q_RETURN_ARG("QQuickItem*"), Q_ARG(int, i))
             for i in range(menu.property("count"))]
    labels = [item.property("text") or "" for item in items]
    presets = [p["label"] for p in settings.editor("presets")]
    assert [label for label in labels if label] == presets
    assert "New voicing" not in presets      # not the voicing being edited
    piano = next(p for p in settings.editor("presets") if p["group"] == "piano")
    index = labels.index(piano["label"])
    QMetaObject.invokeMethod(items[index], "triggered")
    dialog = settings.popup("settingsConfirm")
    settings.qtbot.waitUntil(lambda: dialog.property("opened") is True, timeout=2000)
    assert dialog.property("title") == EDITOR_TEXTS["load_confirm_title"]
    assert dialog.property("message") == EDITOR_TEXTS["load_confirm"]
    settings.click("settingsConfirmYes")
    settings.qtbot.waitUntil(lambda: settings.editor("model") == "piano", timeout=2000)
    assert settings.editor("selected") == "New voicing"


def test_every_section_kind_is_drawn(settings):
    settings.add_voicing()
    for model, fields in [("fretboard", ["field:tuning", "field:max_fret", "field:allow_barres",
                                         "field:weight:barre_penalty"]),
                          ("piano", ["field:range:lh_range:low", "field:range:rh_range:high",
                                     "field:rh_center", "field:add_bass", "field:nested:omit:root"]),
                          ("ensemble", ["recordsTable", "field:upper_clef", "field:allow_unisons",
                                        "field:movement", "field:nested:doubling:root",
                                        "field:nested:inversion:first"])]:
        settings.model.setModel(model)
        settings.qtbot.waitUntil(lambda: settings.editor("model") == model, timeout=2000)
        settings.wait(50)
        for name in fields:
            assert settings.item(name).isVisible(), name


def test_the_voices_table(settings):
    settings.add_voicing()
    settings.model.setModel("ensemble")
    settings.qtbot.waitUntil(lambda: settings.editor("model") == "ensemble", timeout=2000)
    settings.wait(50)
    rows = len(settings.editor("values")["voices"])
    assert not settings.item("moveUp:0").isEnabled() and settings.item("moveDown:0").isEnabled()
    assert settings.item(f"moveUp:{rows - 1}").isEnabled()
    assert not settings.item(f"moveDown:{rows - 1}").isEnabled()
    # The last row's gap is off.
    assert not settings.item(f"cell:voice:{rows - 1}:gap").isEnabled()
    assert settings.item("cell:voice:0:gap").isEnabled()
    first = settings.editor("values")["voices"][0]["name"]
    settings.click("moveDown:0")
    settings.qtbot.waitUntil(lambda: settings.editor("values")["voices"][1]["name"] == first, timeout=2000)
    settings.click("addRecord")
    settings.qtbot.waitUntil(lambda: len(settings.editor("values")["voices"]) == rows + 1, timeout=2000)
    settings.wait(50)
    settings.click(f"removeRow:{rows}")
    settings.qtbot.waitUntil(lambda: len(settings.editor("values")["voices"]) == rows, timeout=2000)
    # A cell: re-checked as typed, its message in the tooltip.
    settings.model.setCell("voices", 0, "low", "H9", False)
    settings.qtbot.waitUntil(lambda: "voice:0:low" in (settings.editor("field_errors") or {}), timeout=2000)
    settings.wait(50)
    cell = settings.item("cell:voice:0:low")
    assert cell.property("error") == "Not a valid note name"
    assert tooltip(cell).endswith("⚠ Not a valid note name")


def test_a_rule_across_fields_marks_the_field_and_shows_the_banner(settings):
    settings.add_voicing()
    settings.model.setField("relaxed_span", "2", True)      # below Max span (4)
    settings.qtbot.waitUntil(lambda: "relaxed_span" in (settings.editor("field_errors") or {}), timeout=2000)
    settings.wait(50)
    message = settings.editor("field_errors")["relaxed_span"]
    assert "Max span" in message
    assert settings.item("field:relaxed_span").property("error") == message
    text = settings.item("voicingErrorsText").property("text")
    # The spec's message is the form's only while no field is blamed for it.
    assert text.splitlines() == [EDITOR_TEXTS["errors_banner"], *settings.editor("form_errors")]
    assert settings.item("voicingErrors").isVisible()


def test_closing_with_wrong_values_asks_and_discard_drops_them(settings):
    settings.add_voicing()
    settings.model.setField("max_span", "x", True)
    settings.model.setNumber("bpm", "5", True)
    settings.qtbot.waitUntil(lambda: settings.model.hasProblems, timeout=2000)
    settings.click("settingsClose")
    dialog = settings.popup("settingsProblems")
    settings.qtbot.waitUntil(lambda: dialog.property("opened") is True, timeout=2000)
    listed = settings.item("settingsProblemsList").property("text") if find(settings.window, "settingsProblemsList") \
        else dialog.findChild(QQuickItem, "settingsProblemsList").property("text")
    assert "Enter a whole number from 20 to 400. (5)" in listed and "New voicing" in listed
    # Edit stays, on the first wrong value.
    settings.click("settingsProblemsEdit") if find(settings.window, "settingsProblemsEdit") else \
        click(settings.window, dialog.findChild(QQuickItem, "settingsProblemsEdit"))
    settings.qtbot.waitUntil(lambda: dialog.property("visible") is False, timeout=2000)
    assert settings.window.isVisible() and settings.window.property("page") == "playback"
    settings.model.close() if False else None
    settings.click("settingsClose")
    settings.qtbot.waitUntil(lambda: dialog.property("opened") is True, timeout=2000)
    click(settings.window, dialog.findChild(QQuickItem, "settingsProblemsDiscard"))
    settings.qtbot.waitUntil(lambda: not settings.window.isVisible(), timeout=2000)
    settings.qtbot.waitUntil(lambda: settings.editor("active") is False, timeout=2000)
    assert settings.config("bpm") == 120


def test_the_voicing_form_scrolls_with_the_wheel_also_over_its_fields(settings):
    settings.add_voicing()
    form = settings.item("voicingForm")
    flick = form.parentItem()
    while flick is not None and flick.property("contentY") is None:
        flick = flick.parentItem()
    assert flick is not None
    settings.window.setHeight(420)          # shorter than the form
    settings.qtbot.waitUntil(lambda: flick.property("contentHeight") > flick.height() + 50, timeout=2000)
    with settings.qtbot.waitSignal(settings.window.frameSwapped, timeout=1000):   # laid out
        settings.window.update()
    # Over a number field that hasn't the focus: the form scrolls, the value stays.
    def spins(item):
        if item.objectName().startswith("field:") and "FormSpin" in item.metaObject().className():
            yield item
        for child in item.childItems():
            yield from spins(child)

    field = next(f for f in spins(form) if f.isVisible()
                 and 0 < f.mapToItem(flick, QPointF(0, 0)).y() < flick.height() - f.height())
    before = settings.editor("values")
    pos = field.mapToScene(QPointF(field.width() / 2, field.height() / 2))
    for _ in range(3):
        event = QWheelEvent(pos, QPointF(settings.window.mapToGlobal(pos.toPoint())), QPoint(0, 0),
                            QPoint(0, -120), Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                            Qt.ScrollPhase.NoScrollPhase, False)
        QGuiApplication.sendEvent(settings.window, event)
        settings.wait(20)
    settings.qtbot.waitUntil(lambda: flick.property("contentY") > 0, timeout=1000)
    assert settings.editor("values") == before
