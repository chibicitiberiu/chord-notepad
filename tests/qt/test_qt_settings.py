"""The Settings window (plan step G1): SettingsModel and SettingsWindow.qml.

Like most desktop settings windows it has Save and Discard (Tibi,
2026-11-15): nothing is written before Save.

The whole front end runs in the test process (``tests/qt/conftest.py``); the
window is opened the way F1's menu will (``AppDialogs.openSettings``).
Repeater and Loader delegates aren't in the QObject tree (pitfall 25), so
the form's fields are found by walking the visual tree (:func:`find`).
"""

import json
import re

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


def range_line(tip):
    """The muted range line of a field's tooltip ("Range 5–24"), or None."""
    found = re.search(r"<br><font color='#[0-9a-f]{6}'>(Range [^<]*)</font>", tip or "")
    return found.group(1) if found else None


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


CLICK_SETTING = "setting:click_plays_chart_voicing"


def test_the_clicked_chords_switch_is_on_the_playback_page_and_saves(settings):
    settings.open("playback")
    settings.qtbot.waitUntil(lambda: settings.window.property("page") == "playback", timeout=1000)
    switch = settings.item(CLICK_SETTING)
    # The page lays out once it is shown.
    settings.qtbot.waitUntil(lambda: switch.mapToScene(QPointF(0, 0)).y() > 0, timeout=2000)
    assert switch.property("title") == "Clicked chords sound as in the chord sheet"
    assert switch.property("help") == "Off: each click is voiced from the chord you clicked before it."
    assert switch.property("checked") is True and settings.config("click_plays_chart_voicing") is True
    settings.click(CLICK_SETTING)
    settings.qtbot.waitUntil(lambda: settings.model.hasChanges, timeout=2000)
    assert settings.config("click_plays_chart_voicing") is True
    settings.save()
    assert settings.config("click_plays_chart_voicing") is False
    assert settings.saved()["click_plays_chart_voicing"] is False
    # Opened again: off.
    settings.open("playback")
    assert settings.model.values["click_plays_chart_voicing"] is False
    assert settings.item(CLICK_SETTING).property("checked") is False


def test_a_saved_off_shows_off_after_a_restart(qapp, qtbot, tmp_path):
    write_config(tmp_path, show_quick_start_on_startup=False, click_plays_chart_voicing=False)
    harness = QtAppHarness(qapp, tmp_path).start()
    qtbot.waitUntil(lambda: harness.window.property("contentReady") is True, timeout=3000)
    s = Settings(harness, qtbot).open("playback")
    try:
        assert s.model.values["click_plays_chart_voicing"] is False
        assert s.item(CLICK_SETTING).property("checked") is False
        assert harness.app.core.config.get("click_plays_chart_voicing") is False
    finally:
        harness.shutdown()
        qtbot.wait(1)


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


def pick(settings, label):
    """Open Add voicing's menu and pick ``label``; wait for the menu to close."""
    menu, items, labels = add_menu_items(settings)
    QMetaObject.invokeMethod(items[labels.index(label)], "triggered")
    settings.qtbot.waitUntil(lambda: not menu.property("visible"), timeout=2000)


def test_add_voicing_offers_blanks_then_the_presets_and_the_core_names_the_new_one(settings):
    # Tibi, 2026-11-15: Copy from existing went into Add voicing's menu, and
    # a blank of each model comes first.
    settings.click("page:voicings")
    assert settings.item("removeVoicing").property("enabled") is False
    menu, items, labels = add_menu_items(settings)
    presets = settings.model.addPresets()
    assert [label for label in labels if label] == [p["label"] for p in presets]
    # The blanks, a separator, then the presets (a separator between groups).
    assert labels[:4] == ["Blank fretboard", "Blank piano", "Blank ensemble", ""]
    assert [p["group"] for p in presets[:3]] == ["blank"] * 3
    groups = [p["group"] for p in presets]
    assert labels.count("") == len(set(groups)) - 1
    assert groups[3:] == sorted(groups[3:], key=groups[3:].index)     # each group in one run
    QMetaObject.invokeMethod(items[0], "triggered")
    settings.qtbot.waitUntil(lambda: settings.editor("selected") == "New fretboard voicing", timeout=2000)
    assert settings.editor("model") == "fretboard"
    assert settings.editor("values")["tuning"] == "E2 A2 D3 G3 B3 E4"
    assert settings.editor("dirty") is False
    assert settings.item("removeVoicing").property("enabled") is True
    assert not settings.item("voicingPlaceholder").isVisible()
    # No question: a new voicing has nothing to lose.
    assert settings.popup("settingsConfirm").property("visible") is False
    settings.qtbot.waitUntil(lambda: not menu.property("visible"), timeout=2000)
    # A built-in preset, another blank, the same blank again.
    pick(settings, "Piano (default)")
    settings.qtbot.waitUntil(lambda: settings.editor("selected") == "New Piano (default)", timeout=2000)
    assert settings.editor("model") == "piano"
    pick(settings, "Blank ensemble")
    settings.qtbot.waitUntil(lambda: settings.editor("selected") == "New ensemble voicing", timeout=2000)
    pick(settings, "Blank fretboard")
    settings.qtbot.waitUntil(lambda: settings.editor("selected") == "New fretboard voicing 2", timeout=2000)
    groups = {g["model"]: g["names"] for g in settings.editor("groups")}
    assert groups == {"fretboard": ["New fretboard voicing", "New fretboard voicing 2"],
                      "piano": ["New Piano (default)"], "ensemble": ["New ensemble voicing"]}
    # The user's voicings are offered, the selected one too: a new one may copy it.
    menu, items, labels = add_menu_items(settings)
    assert labels[labels.index("Piano (default)") + 1] == ""
    assert labels[-4:] == sorted(["New ensemble voicing", "New fretboard voicing",
                                  "New fretboard voicing 2", "New Piano (default)"])   # as the core sorts
    QMetaObject.invokeMethod(items[labels.index("New ensemble voicing")], "triggered")
    settings.qtbot.waitUntil(lambda: settings.editor("selected") == "New New ensemble voicing", timeout=2000)
    assert settings.editor("model") == "ensemble"
    settings.wait(100)
    assert "New fretboard voicing" not in (settings.config("voicings") or {})
    settings.save()
    saved = settings.config("voicings")
    assert {name: saved[name]["model"] for name in saved} == {
        "New fretboard voicing": "fretboard", "New fretboard voicing 2": "fretboard",
        "New Piano (default)": "piano", "New ensemble voicing": "ensemble",
        "New New ensemble voicing": "ensemble"}


def test_add_voicing_from_sends_one_command(settings, monkeypatch):
    sent = []
    submit = settings.harness.store.submit
    monkeypatch.setattr(settings.harness.store, "submit",
                        lambda name, args=None: (sent.append(name), submit(name, args)))
    settings.model.addVoicingFrom("blank", "Blank piano")
    assert sent == ["add_voicing_from"]
    settings.qtbot.waitUntil(lambda: settings.editor("selected") == "New piano voicing", timeout=2000)


# -- the built-ins, read-only ------------------------------------------------------------


def list_entries(settings):
    """The voicing list's rows, top to bottom: (objectName, item)."""
    page = settings.item("voicingsPage")
    rows = []

    def walk(item):
        name = item.objectName()
        if (name.startswith("builtin:") or name.startswith("voicing:")) and item.isVisible():
            rows.append((name, item))
        for child in item.childItems():
            walk(child)

    walk(page)
    return sorted(rows, key=lambda row: row[1].mapToScene(QPointF(0, 0)).y())


def test_each_group_lists_its_built_ins_first_muted_with_a_lock(settings):
    settings.add_voicing()
    settings.window.setProperty("page", "voicings")
    settings.wait(50)
    names = [name for name, _ in list_entries(settings)]
    groups = {g["model"]: g for g in settings.editor("groups")}
    expected = []
    for model in ("fretboard", "piano", "ensemble"):
        expected += [f"builtin:{label}" for label in groups[model]["builtins"]]
        expected += [f"voicing:{name}" for name in groups[model]["names"]]
    assert names == expected
    assert names[:2] == ["builtin:Guitar (Standard - EADGBE)", "builtin:Guitar (Drop D)"]
    assert "builtin:Piano (default)" in names and "builtin:String Quartet" in names
    builtin = settings.item("builtin:Ukulele")
    label = next(c for c in builtin.property("contentItem").childItems()
                 if c.metaObject().className().startswith("Label"))
    own = settings.item("voicing:New voicing").property("contentItem")
    assert label.property("color") != own.property("color")          # muted
    lock = find(builtin, "builtinLock")
    assert lock is not None and lock.isVisible()
    assert "lock-outline" in lock.property("source").toString()
    assert find(settings.item("voicing:New voicing"), "builtinLock") is None


def test_a_built_in_shows_read_only_and_a_copy_is_the_way_to_change_it(settings):
    settings.add_voicing()
    settings.wait(50)
    assert settings.model.hasChanges is True       # the added voicing
    settings.click("builtin:Ukulele")
    settings.qtbot.waitUntil(lambda: settings.editor("read_only") is True, timeout=2000)
    assert (settings.editor("selected"), settings.editor("model")) == ("Ukulele", "fretboard")
    settings.wait(50)
    # Selected, and the user's voicing isn't.
    assert settings.item("builtin:Ukulele").property("highlighted") is True
    assert settings.item("voicing:New voicing").property("highlighted") is False
    # The name is a label, the model box, the trash button and every field disabled.
    assert not settings.item("voicingName").isVisible()
    assert settings.item("builtinName").property("text") == "Ukulele"
    assert settings.item("builtinName").isVisible()
    assert settings.item("voicingModel").property("enabled") is False
    assert settings.item("removeVoicing").property("enabled") is False
    for name in ("field:tuning", "field:max_fret", "field:allow_barres", "field:weight:barre_penalty"):
        assert settings.item(name).property("enabled") is False, name
    assert settings.item("field:tuning").property("text") == settings.editor("values")["tuning"]
    # An edit that gets through anyway is not sent (the session would refuse it).
    before = settings.editor("values")
    revision = settings.editor("revision")
    settings.model.setField("max_fret", "20", True)
    settings.model.setModel("piano")
    settings.model.addRecord("voices")
    settings.wait(100)
    assert settings.editor("values") == before and settings.editor("revision") == revision
    # A built-in of another model: its form.
    settings.click("builtin:Choir (SATB)")
    settings.qtbot.waitUntil(lambda: settings.editor("model") == "ensemble", timeout=2000)
    settings.wait(50)
    assert settings.item("addRecord").property("enabled") is False
    assert settings.item("cell:voice:0:low").property("enabled") is False
    assert settings.item("builtin:Ukulele").property("highlighted") is False
    # Copy: a voicing of the user's, named by the session, editable.
    settings.click("copyBuiltin")
    settings.qtbot.waitUntil(lambda: settings.editor("selected") == "New Choir (SATB)", timeout=2000)
    assert settings.editor("read_only") is False and settings.editor("model") == "ensemble"
    settings.wait(50)
    assert settings.item("voicingName").isVisible() and not settings.item("builtinName").isVisible()
    assert settings.item("voicingModel").property("enabled") is True
    assert settings.item("removeVoicing").property("enabled") is True
    assert settings.item("cell:voice:0:low").property("enabled") is True
    assert settings.item("voicing:New Choir (SATB)").property("highlighted") is True
    assert settings.item("builtin:Choir (SATB)").property("highlighted") is False
    settings.save()
    saved = settings.config("voicings")["New Choir (SATB)"]
    assert saved["model"] == "ensemble" and len(saved["voices"]) == 4


def test_viewing_a_built_in_is_not_a_change(settings):
    settings.window.setProperty("page", "voicings")
    settings.click("builtin:Piano (default)")
    settings.qtbot.waitUntil(lambda: settings.editor("read_only") is True, timeout=2000)
    settings.wait(50)
    assert settings.model.hasChanges is False
    # Add voicing's menu doesn't offer the built-in as one of the user's voicings.
    assert [p for p in settings.model.addPresets() if p["group"] == "custom"] == []
    # Escape closes without asking.
    settings.activate()
    settings.key(Qt.Key.Key_Escape)
    settings.qtbot.waitUntil(lambda: not settings.window.isVisible(), timeout=2000)
    assert settings.popup("settingsUnsavedDialog").property("visible") is False


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
    assert tooltip(field).startswith(escaped(TOOLTIPS["max_span"]) + "<br><font")
    assert tooltip(field).endswith("</font><br><br>⚠ Must be a whole number")
    assert range_line(tooltip(field)) == "Range 1–8"
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


def test_a_number_out_of_range_is_marked_like_one_that_does_not_parse(settings):
    settings.add_voicing()
    settings.activate()
    field = settings.item("field:max_span")
    field.forceActiveFocus()
    QMetaObject.invokeMethod(field, "selectAll")
    settings.type("20")
    settings.qtbot.waitUntil(lambda: field.property("error") == "Must be from 1 to 8", timeout=2000)
    assert tooltip(field).endswith("</font><br><br>\u26a0 Must be from 1 to 8")
    settings.key(Qt.Key.Key_Return)
    assert "New voicing" in settings.editor("invalid")
    settings.click("page:general")
    settings.click("settingsSave")
    error = settings.popup("settingsErrorDialog")
    settings.qtbot.waitUntil(lambda: error.property("visible") is True, timeout=2000)
    assert "New voicing" in error.property("message")
    assert settings.editor("selected") == "New voicing"
    assert "New voicing" not in (settings.config("voicings") or {})


def test_captions_share_their_fields_help(settings):
    settings.add_voicing()
    field = settings.item("field:max_fret")
    assert tooltip(field).startswith(escaped(TOOLTIPS["max_fret"]) + "<br>")
    assert tooltip(settings.item("caption:max_fret")) == tooltip(field)
    # A switch's label is a caption, as the number fields have.
    assert settings.item("caption:allow_barres").property("text") == "Allow barre chords"
    assert settings.item("field:allow_barres").property("text") == ""
    assert tooltip(settings.item("caption:allow_barres")) == escaped(TOOLTIPS["allow_barres"])


def test_number_fields_show_their_range_weights_dont(settings):
    settings.add_voicing()
    for name, expected in [("max_fret", "Range 5–24"), ("fingers", "Range 1–5"),
                           ("max_span", "Range 1–8"), ("relaxed_span", "Range 1–10")]:
        assert range_line(tooltip(settings.item(f"field:{name}"))) == expected, name
        assert range_line(tooltip(settings.item(f"caption:{name}"))) == expected, name
    for name in ("field:weight:barre_penalty", "field:tuning", "caption:weight:barre_penalty"):
        assert range_line(tooltip(settings.item(name))) is None, name
    settings.model.setModel("piano")
    settings.qtbot.waitUntil(lambda: settings.editor("model") == "piano", timeout=2000)
    settings.wait(50)
    assert range_line(tooltip(settings.item("field:hand_span"))) == "Range 1–24"
    assert range_line(tooltip(settings.item("field:rh_center"))) == "Range 0–127"
    assert range_line(tooltip(settings.item("field:nested:omit:root"))) is None
    settings.model.setModel("ensemble")
    settings.qtbot.waitUntil(lambda: settings.editor("model") == "ensemble", timeout=2000)
    settings.wait(50)
    assert range_line(tooltip(settings.item("cell:voice:0:gap"))) == "Range 1–127"
    assert range_line(tooltip(settings.item("cell:voice:0:movement"))) is None


def test_range_text_comes_from_the_schema_limits():
    assert settings_window.range_text({"id": "max_fret", "min": 5, "max": 24}) == "Range 5–24"
    assert settings_window.range_text({"id": "rh_center", "min": 0, "max": 127.0}) == "Range 0–127"
    assert settings_window.range_text({"id": "weight:barre_penalty", "min": -100, "max": 100}) == ""
    assert settings_window.range_text({"id": "nested:omit:root", "min": -100, "max": 100}) == ""
    assert settings_window.range_text({"id": "tuning", "min_items": 3, "max_items": 12}) == ""


def scene_box(item):
    """(left, right) of an item in the window."""
    left = item.mapToScene(QPointF(0, 0)).x()
    return round(left, 2), round(left + item.width(), 2)


def test_switches_and_weights_line_up_with_the_number_fields(settings):
    """A switch's label sits where the captions do and the switch ends where
    the number fields end (it used to be the switch's own text, inset by its
    padding); the ensemble's weights are as wide as the number fields."""
    settings.add_voicing()
    settings.window.setProperty("page", "voicings")
    for model, switch, number in [("fretboard", "allow_barres", "max_fret"),
                                  ("piano", "add_bass", "rh_center"),
                                  ("ensemble", "allow_unisons", "weight:leap_penalty")]:
        if model != "fretboard":
            settings.model.setModel(model)
            settings.qtbot.waitUntil(lambda: settings.editor("model") == model, timeout=2000)
        settings.wait(80)
        caption, other = settings.item(f"caption:{switch}"), settings.item(f"caption:{number}")
        assert caption.isVisible()
        assert scene_box(caption)[0] == scene_box(other)[0], model
        assert scene_box(settings.item(f"field:{switch}"))[1] == scene_box(settings.item(f"field:{number}"))[1], model
        # The switch is alone at the right of its row, not stretched.
        assert settings.item(f"field:{switch}").width() < settings.item(f"field:{number}").width()


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
                                        "cell:voice:0:movement", "field:nested:doubling:root",
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
    assert settings.item("dragRow:0").isVisible() and settings.item(f"dragRow:{rows - 1}").isVisible()
    assert settings.item("duplicateRow:0").isEnabled() and settings.item("cell:voice:0:movement").isEnabled()
    # The last row's gap is off.
    assert not settings.item(f"cell:voice:{rows - 1}:gap").isEnabled()
    assert settings.item("cell:voice:0:gap").isEnabled()
    first = settings.editor("values")["voices"][0]["name"]
    settings.model.moveRecord(0, 1, "voices")
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


def _names(settings):
    return [row["name"] for row in settings.editor("values")["voices"]]


def _ensemble_with_four_voices(settings):
    settings.add_voicing()
    settings.model.setModel("ensemble")
    settings.qtbot.waitUntil(lambda: settings.editor("model") == "ensemble", timeout=2000)
    for _ in range(2):
        settings.click("addRecord")
    settings.qtbot.waitUntil(lambda: len(settings.editor("values")["voices"]) == 4, timeout=2000)
    settings.wait(50)


def test_dragging_a_handle_moves_the_voice(settings):
    _ensemble_with_four_voices(settings)
    before = _names(settings)
    handle = settings.item("dragRow:0")
    start = handle.mapToScene(QPointF(handle.width() / 2, handle.height() / 2)).toPoint()
    step = settings.item("dragRow:1").mapToScene(QPointF(0, 0)).y() - handle.mapToScene(QPointF(0, 0)).y()
    QTest.mousePress(settings.window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
    for fraction in (0.3, 0.6, 1.0):
        QTest.mouseMove(settings.window, start + QPoint(0, int(2 * step * fraction)))
        settings.wait(30)
    QTest.mouseRelease(settings.window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                       start + QPoint(0, int(2 * step)))
    settings.qtbot.waitUntil(lambda: _names(settings) != before, timeout=2000)
    assert _names(settings) == [before[1], before[2], before[0], before[3]]


def test_alt_up_and_down_move_the_row_holding_the_focus(settings):
    _ensemble_with_four_voices(settings)
    before = _names(settings)
    settings.click("cell:voice:2:name")
    settings.key(Qt.Key.Key_Up, Qt.KeyboardModifier.AltModifier)
    settings.qtbot.waitUntil(lambda: _names(settings) != before, timeout=2000)
    assert _names(settings) == [before[0], before[2], before[1], before[3]]
    settings.wait(100)
    settings.click("cell:voice:1:name")
    settings.key(Qt.Key.Key_Down, Qt.KeyboardModifier.AltModifier)
    settings.qtbot.waitUntil(lambda: _names(settings) == before, timeout=2000)


def test_duplicate_inserts_a_copy_of_the_voice_below_it(settings):
    _ensemble_with_four_voices(settings)
    before = settings.editor("values")["voices"]
    settings.click("duplicateRow:1")
    settings.qtbot.waitUntil(lambda: len(settings.editor("values")["voices"]) == 5, timeout=2000)
    after = settings.editor("values")["voices"]
    assert after[2]["name"] == f"{before[1]['name']} 2"
    assert {k: v for k, v in after[2].items() if k != "name"} == \
        {k: v for k, v in before[1].items() if k != "name"}
    assert [r["movement"] for r in after] == [before[0]["movement"], before[1]["movement"],
                                              before[1]["movement"], before[2]["movement"],
                                              before[3]["movement"]]
