"""The Settings window (plan step G1): SettingsModel and SettingsWindow.qml.

Like most desktop settings windows it has Save and Discard (Tibi,
2026-11-15): nothing is written before Save.

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

    def save(self):
        """Save, and wait for the window to close and the edit to end."""
        self.click("settingsSave")
        self.qtbot.waitUntil(lambda: not self.window.isVisible(), timeout=2000)
        self.qtbot.waitUntil(lambda: self.editor("active") is False, timeout=2000)

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


def test_opening_starts_a_settings_edit_and_discard_ends_it(settings):
    assert settings.window.isVisible()
    assert settings.model.isOpen
    assert not settings.model.hasChanges
    assert settings.item("settingsUnsaved").property("text") == ""
    settings.click("settingsDiscard")
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


def test_a_change_waits_for_save_then_is_saved_and_applied(settings):
    settings.click("setting:word_wrap")
    settings.qtbot.waitUntil(lambda: settings.model.hasChanges, timeout=2000)
    assert settings.item("settingsUnsaved").property("text") == "Unsaved changes"
    settings.wait(100)
    assert settings.config("word_wrap") is False
    assert settings.harness.app.editor.wordWrap is False
    settings.save()
    assert settings.config("word_wrap") is True
    assert settings.saved()["word_wrap"] is True
    # Applied to the editor (the session's apply_settings).
    settings.qtbot.waitUntil(lambda: settings.harness.app.editor.wordWrap is True, timeout=2000)


def test_discard_drops_every_change(settings):
    settings.click("setting:word_wrap")
    settings.model.setNumber("bpm", "96", True)
    settings.add_voicing()
    settings.qtbot.waitUntil(lambda: settings.model.hasChanges, timeout=2000)
    settings.click("settingsDiscard")
    settings.qtbot.waitUntil(lambda: settings.editor("active") is False, timeout=2000)
    settings.wait(100)
    assert settings.config("word_wrap") is False and settings.config("bpm") == 120
    assert "New voicing" not in (settings.config("voicings") or {})
    # Opened again: the saved values.
    settings.open()
    assert settings.model.values["word_wrap"] is False and not settings.model.hasChanges


def test_q8_a_typed_number_out_of_range_is_marked_and_save_waits_for_it(settings):
    assert settings.config("max_recent_files") == 10
    settings.model.setNumber("max_recent_files", "60", True)
    assert settings.model.numberErrors == {"max_recent_files": "Enter a whole number from 1 to 50."}
    field = settings.item("setting:max_recent_files")
    assert field.property("error") == "Enter a whole number from 1 to 50."
    assert settings.model.hasChanges
    # Save refuses, says why and shows the page with the field.
    settings.click("page:playback")
    settings.click("settingsSave")
    refused = settings.popup("settingsNotSaved")
    settings.qtbot.waitUntil(lambda: refused.property("opened") is True, timeout=2000)
    assert refused.property("title") == "Settings Not Saved"
    assert settings.window.isVisible() and settings.window.property("page") == "general"
    settings.wait(100)
    assert settings.config("max_recent_files") == 10
    settings.key(Qt.Key.Key_Escape)
    settings.qtbot.waitUntil(lambda: refused.property("visible") is False, timeout=1000)
    settings.model.setNumber("max_recent_files", "20", True)
    assert settings.model.numberErrors == {}
    settings.save()
    assert settings.config("max_recent_files") == 20


def test_a_number_typed_in_the_field_goes_into_the_draft(settings):
    settings.activate()
    field = settings.item("setting:font_size")
    field.forceActiveFocus()
    QMetaObject.invokeMethod(field, "selectAll")
    settings.type("14")
    settings.qtbot.waitUntil(lambda: settings.model.values["font_size"] == 14, timeout=2000)
    # The arrows step it.
    settings.key(Qt.Key.Key_Up)
    settings.qtbot.waitUntil(lambda: settings.model.values["font_size"] == 15, timeout=2000)
    # Not a number: marked, the draft keeps the saved size.
    QMetaObject.invokeMethod(field, "selectAll")
    settings.type("x")
    settings.key(Qt.Key.Key_Return)
    settings.qtbot.waitUntil(lambda: field.property("error") != "", timeout=1000)
    assert settings.model.values["font_size"] == settings.config("font_size")
    QMetaObject.invokeMethod(field, "selectAll")
    settings.type("15")
    settings.qtbot.waitUntil(lambda: field.property("error") == "", timeout=1000)
    settings.save()
    assert settings.config("font_size") == 15


def test_the_bpm_and_time_signature_ranges(settings):
    assert settings.model.limits["bpm"] == [20, 400]
    assert settings.model.limits["time_signature_beats"] == [1, 16]
    settings.model.setNumber("bpm", "19", True)
    settings.model.setNumber("time_signature_beats", "17", True)
    assert settings.model.numberErrors["bpm"] == "Enter a whole number from 20 to 400."
    assert settings.model.save() is False
    settings.model.setNumber("bpm", "96", True)
    settings.model.setNumber("time_signature_beats", "3", True)
    settings.model.setValue("time_signature_unit", 8)
    settings.save()
    assert (settings.config("bpm"), settings.config("time_signature_beats"),
            settings.config("time_signature_unit")) == (96, 3, 8)
    assert settings.model.choices["timeUnits"] == [2, 4, 8, 16]


def test_the_notation_respells_the_default_key_which_stays_american(settings):
    settings.model.setValue("key", "G")
    settings.click("setting:notation:european")
    settings.qtbot.waitUntil(lambda: settings.model.values["notation"] == "european", timeout=2000)
    labels = [k["label"] for k in settings.model.keyChoices]
    assert labels[0] == "None" and "Sol" in labels and "G" not in labels
    assert settings.item("setting:key").property("currentText") == "Sol"
    settings.save()
    assert settings.config("notation") == "european" and settings.config("key") == "G"


def test_the_notation_respells_the_voicing_note_names(settings):
    settings.add_voicing()
    assert settings.editor("values")["tuning"] == "E2 A2 D3 G3 B3 E4"
    settings.model.setValue("notation", "european")
    settings.qtbot.waitUntil(lambda: settings.editor("values")["tuning"] == "Mi2 La2 Re3 Sol3 Si3 Mi4",
                             timeout=2000)
    settings.save()
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
    settings.save()
    assert settings.config("font_family") == other


def test_log_level_quick_start_soundfont_and_driver(settings):
    settings.model.setValue("log_level", "DEBUG")
    settings.model.setValue("show_quick_start_on_startup", True)
    settings.model.setValue("soundfont_path", "/music/My Font.sf2")
    settings.model.setValue("audio_driver", "jack")
    settings.save()
    assert settings.config("audio_driver") == "jack"
    assert settings.config("log_level") == "DEBUG"
    assert settings.config("show_quick_start_on_startup") is True
    assert settings.config("soundfont_path") == "/music/My Font.sf2"
    # Empty is the bundled soundfont; "Auto" (or nothing) is no driver.
    settings.open()
    assert settings.item("setting:audio_driver").property("editText") == "jack"
    settings.model.setValue("soundfont_path", "  ")
    settings.model.setValue("audio_driver", "Auto")
    settings.save()
    assert settings.config("audio_driver") is None
    assert settings.config("soundfont_path") is None
    settings.open()
    assert settings.item("setting:audio_driver").property("editText") == "Auto"
    assert settings.model.choices["audioDrivers"][0] == "Auto"
    assert "" not in settings.model.choices["audioDrivers"]
    assert "pulseaudio" in settings.model.choices["audioDrivers"]
    settings.model.setValue("audio_driver", "")
    assert settings.model.values["audio_driver"] is None
    assert settings.model.choices["logLevels"] == ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def test_the_soundfont_file_dialog_takes_sf2_files(settings):
    dialog = settings.window.findChild(QObject, "soundfontDialog") or next(
        o for o in settings.window.findChildren(QObject) if o.property("title") == "Select SoundFont")
    assert dialog.property("title") == "Select SoundFont"
    assert dialog.property("nameFilters")[0] == "SoundFont files (*.sf2)"


def test_the_theme_switches_on_save(settings):
    pane = settings.harness.window.findChild(QQuickItem, "editorPane")
    light = pane.property("color").name()
    settings.model.setValue("ui_theme", "dark")
    settings.wait(100)
    assert pane.property("color").name() == light
    settings.save()
    assert settings.config("ui_theme") == "dark"
    settings.qtbot.waitUntil(lambda: pane.property("color").name() == "#1e1f22", timeout=2000)
    settings.open()
    settings.model.setValue("ui_theme", "light")
    settings.save()
    settings.qtbot.waitUntil(lambda: pane.property("color").name() == light, timeout=2000)
    # "Follow the system": offscreen has no dark scheme.
    settings.open()
    settings.model.setValue("ui_theme", "system")
    settings.save()
    assert settings.config("ui_theme") == "system"
    assert pane.property("color").name() == light


def test_values_changed_elsewhere_while_open_are_shown_and_not_undone(settings):
    """The window isn't modal: the ☰ Dark theme, text zoom and View › Word
    wrap change the config while it is open. The window shows the new values,
    and its Save (it sends every General/Playback value) keeps them; a value
    the window changed itself stays as the window has it."""
    store = settings.harness.store
    size = settings.config("font_size")
    settings.model.setValue("key", "D")
    store.submit("set_ui_theme", {"theme": "dark"})
    store.submit("step_font_size", {"delta": 2})
    store.submit("set_word_wrap", {"on": True})
    settings.qtbot.waitUntil(lambda: (settings.model.values["ui_theme"],
                                      settings.model.values["font_size"],
                                      settings.model.values["word_wrap"]) == ("dark", size + 2, True),
                             timeout=2000)
    # Save writes the whole draft: the others stay.
    settings.model.setValue("show_quick_start_on_startup", True)
    settings.save()
    assert settings.config("show_quick_start_on_startup") is True
    assert settings.config("key") == "D"
    assert (settings.config("ui_theme"), settings.config("font_size"),
            settings.config("word_wrap")) == ("dark", size + 2, True)
    assert settings.harness.app.editor.wordWrap is True


# -- Voicings --------------------------------------------------------------------------------


def add_menu_items(settings):
    """Open Add voicing's menu: (the menu, its items, their labels)."""
    settings.click("addVoicing")
    menu = settings.popup("addVoicingMenu")
    settings.qtbot.waitUntil(lambda: menu.property("opened") is True, timeout=2000)
    items = [QMetaObject.invokeMethod(menu, "itemAt", Q_RETURN_ARG("QQuickItem*"), Q_ARG(int, i))
             for i in range(menu.property("count"))]
    return menu, items, [item.property("text") or "" for item in items]


def test_add_voicing_offers_the_presets_and_the_pick_is_what_it_starts_as(settings):
    # Tibi, 2026-11-15: Copy from existing went into Add voicing's menu.
    settings.click("page:voicings")
    assert settings.item("removeVoicing").property("enabled") is False
    menu, items, labels = add_menu_items(settings)
    presets = [p["label"] for p in settings.editor("presets")]
    assert [label for label in labels if label] == presets
    groups = [p["group"] for p in settings.editor("presets")]
    assert labels.count("") == len(set(groups)) - 1          # a separator between groups
    # Not the last row (each row keeps its own preset).
    # (The blank fretboard first: a guitar's defaults.)
    first = settings.editor("presets")[0]
    assert first["group"] == "blank" and labels[0] == first["label"] == "Blank fretboard"
    QMetaObject.invokeMethod(items[0], "triggered")
    settings.qtbot.waitUntil(lambda: settings.editor("selected") == "New voicing", timeout=2000)
    settings.qtbot.waitUntil(lambda: settings.editor("model") == "fretboard", timeout=2000)
    assert settings.editor("values")["tuning"] == "E2 A2 D3 G3 B3 E4"
    assert settings.item("removeVoicing").property("enabled") is True
    assert not settings.item("voicingPlaceholder").isVisible()
    # No question: a new voicing has nothing to lose.
    assert settings.popup("settingsConfirm").property("visible") is False
    settings.qtbot.waitUntil(lambda: not menu.property("visible"), timeout=2000)
    for group, model in (("piano", "piano"), ("ensemble", "ensemble")):
        menu, items, labels = add_menu_items(settings)
        preset = next(p for p in settings.editor("presets") if p["group"] == group)
        QMetaObject.invokeMethod(items[labels.index(preset["label"])], "triggered")
        settings.qtbot.waitUntil(lambda: settings.editor("model") == model, timeout=2000)
        settings.qtbot.waitUntil(lambda: not menu.property("visible"), timeout=2000)
    groups = {g["model"]: g["names"] for g in settings.editor("groups")}
    assert groups == {"fretboard": ["New voicing"], "piano": ["New voicing 2"],
                      "ensemble": ["New voicing 3"]}
    # The selected voicing is offered too: a new one may copy it.
    menu, items, labels = add_menu_items(settings)
    assert "New voicing 3" in labels and "New voicing" in labels
    QMetaObject.invokeMethod(items[labels.index("New voicing 3")], "triggered")
    settings.qtbot.waitUntil(lambda: settings.editor("selected") == "New voicing 4", timeout=2000)
    settings.qtbot.waitUntil(lambda: settings.editor("model") == "ensemble", timeout=2000)
    settings.wait(100)
    assert "New voicing" not in (settings.config("voicings") or {})
    settings.save()
    saved = settings.config("voicings")
    assert [saved[f"New voicing{n}"]["model"] for n in ("", " 2", " 3", " 4")] == [
        "fretboard", "piano", "ensemble", "ensemble"]


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
    assert settings.item("removeVoicing").property("enabled") is False
    settings.save()
    assert "New voicing" not in (settings.config("voicings") or {})


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
    settings.save()
    assert "Baritone" in settings.config("voicings")


def test_the_name_help_names_the_qt_voicing_menus(settings):
    assert settings.model.schema["help"]["name"] == "The name of this voicing, shown in the Voicing menus."
    settings.add_voicing()
    assert settings.item("voicingName").property("tip") == settings.model.schema["help"]["name"]


def test_a_wrong_field_is_marked_with_its_message_and_save_refuses_it(settings):
    settings.add_voicing()
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
    assert "New voicing" in settings.editor("invalid")
    # Save: the session refuses, names it and selects it; the window stays.
    settings.click("page:general")
    settings.click("settingsSave")
    error = settings.popup("settingsErrorDialog")
    settings.qtbot.waitUntil(lambda: error.property("visible") is True, timeout=2000)
    assert "New voicing" in error.property("message")
    assert settings.window.isVisible() and settings.window.property("page") == "voicings"
    assert settings.editor("active") is True and settings.editor("selected") == "New voicing"
    assert "New voicing" not in (settings.config("voicings") or {})


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


def unsaved_button(settings, dialog, name):
    click(settings.window, dialog.findChild(QQuickItem, name))


def test_closing_with_unsaved_changes_asks_save_discard_or_cancel(settings):
    settings.activate()
    settings.click("setting:word_wrap")
    settings.qtbot.waitUntil(lambda: settings.model.hasChanges, timeout=2000)
    settings.key(Qt.Key.Key_Escape)
    dialog = settings.popup("settingsUnsavedDialog")
    settings.qtbot.waitUntil(lambda: dialog.property("opened") is True, timeout=2000)
    # Cancel stays, with the change.
    unsaved_button(settings, dialog, "settingsUnsavedCancel")
    settings.qtbot.waitUntil(lambda: dialog.property("visible") is False, timeout=2000)
    assert settings.window.isVisible() and settings.model.values["word_wrap"] is True
    # The title bar's close asks too; Discard drops it.
    settings.window.close()
    settings.qtbot.waitUntil(lambda: dialog.property("opened") is True, timeout=2000)
    unsaved_button(settings, dialog, "settingsUnsavedDiscard")
    settings.qtbot.waitUntil(lambda: not settings.window.isVisible(), timeout=2000)
    settings.qtbot.waitUntil(lambda: settings.editor("active") is False, timeout=2000)
    assert settings.config("word_wrap") is False
    # Save saves.
    settings.open()
    settings.activate()
    settings.click("setting:word_wrap")
    settings.key(Qt.Key.Key_Escape)
    settings.qtbot.waitUntil(lambda: dialog.property("opened") is True, timeout=2000)
    unsaved_button(settings, dialog, "settingsUnsavedSave")
    settings.qtbot.waitUntil(lambda: not settings.window.isVisible(), timeout=2000)
    settings.qtbot.waitUntil(lambda: settings.config("word_wrap") is True, timeout=2000)


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
