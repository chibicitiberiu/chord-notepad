"""The Settings window (plan step G1): the Python side.

The window is QML (``qml/app/SettingsWindow.qml`` and the voicing form's
files); what it decides with is here, in :class:`SettingsModel`. Like most
desktop settings windows it has Save and Discard (Tibi, 2026-11-15; the
parity checklist's resolution 6 had it save as it went, as Android does),
through the session's settings edit:

* :meth:`SettingsModel.open` sends ``begin_settings_edit`` (and asks for the
  voicing form's schema once). :meth:`SettingsModel.save` sends
  ``save_settings``: every voicing is validated, and the first wrong one is
  the session's ``UserError`` (the edit stays open); otherwise everything is
  written and applied in one go and the edit ends. :meth:`SettingsModel.discard`
  sends ``cancel_settings_edit``: nothing is written.
* **General and Playback** are a draft of ``DesktopSettingsValues``
  (:attr:`SettingsModel.values`), started from the session's
  ``SettingsState``. A number that isn't a whole number in range is never
  put in the draft (Q8): it is kept as typed (:attr:`SettingsModel.numberTexts`)
  and shown with its message (:attr:`SettingsModel.numberErrors`); Save is
  refused until it is fixed.
  The window isn't modal, so some of these values change elsewhere while it
  is open (the ☰ Dark theme, text zoom, View › Word wrap). Each state change
  reads the config again (``settings_values``) and takes what changed there
  into the draft, unless the window changed that value itself: Save sends
  the whole draft, and an old value in it would undo the change made
  elsewhere.
* **Voicings**: the session's ``VoicingEditorState`` is the form
  (:attr:`SettingsModel.editor`, a map of the store). A keystroke sends
  ``set_voicing_values`` (the session re-checks it and the marks come back)
  into the session's working copy; Save writes it.

The field kinds, labels, help and messages come from the core's schema
(``settings_forms.voicing_form.editor_schema``, :attr:`SettingsModel.schema`);
the window only lays them out.
"""

import copy
import dataclasses
import logging
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot
from PySide6.QtGui import QFontDatabase

from chordnotepad.constants import LOG_LEVELS, UI_THEMES
from chordnotepad.session.settings import AUDIO_DRIVER_SUGGESTIONS, NUMBER_SETTINGS
from chordnotepad_desktop import editor_font

logger = logging.getLogger(__name__)

#: A number field's text that isn't a whole number in range (Android's
#: ``settings_number_range``).
NUMBER_RANGE_MESSAGE = "Enter a whole number from {low} to {high}."

#: The default time signature's units (the Tk dialog's; the checklist's "2, 4, 8 or 16").
TIME_UNITS = (2, 4, 8, 16)

#: The theme choices (config ``ui_theme``), with the mockup's labels.
THEME_LABELS = {"system": "Follow the system", "light": "Light", "dark": "Dark"}

#: The default key's "no key" entry (Android's ``settings_key_none``).
NO_KEY_LABEL = "None"

#: The voicing commands the session refuses while the form shows a built-in
#: (``VoicingEditorState.read_only``); the window doesn't send them then.
READ_ONLY_REFUSED = frozenset((
    "set_voicing_values", "set_voicing_model", "rename_voicing", "load_voicing_preset",
    "add_voicing_record", "remove_voicing_record", "move_voicing_record"))

#: The audio driver entry that saves no driver: FluidSynth's default, then
#: the platform's list (``PlaybackService``).
AUTO_DRIVER_LABEL = "Auto"


#: A number field's range, the muted second line of its tooltip.
RANGE_TEXT = "Range {low}\u2013{high}"

#: Field id prefixes of the weights (``settings_forms.voicing_form``): their
#: min and max only bound the spinner, so their tooltips show no range.
WEIGHT_PREFIXES = ("weight:", "nested:")


def range_text(field: Dict[str, Any]) -> str:
    """The range line of a voicing form field's tooltip ("Range 5\u201324"):
    a field with the schema's ``min`` and ``max``, weights left out; ""
    for any other."""
    if field.get("min") is None or field.get("max") is None:
        return ""
    if str(field.get("id", "")).startswith(WEIGHT_PREFIXES):
        return ""
    return RANGE_TEXT.format(low=f"{field['min']:g}", high=f"{field['max']:g}")


def with_ranges(schema: Any) -> Any:
    """The editor schema with each field's :func:`range_text` as ``range``
    (records columns too), for the tooltips."""
    if not isinstance(schema, dict):
        return schema
    schema = copy.deepcopy(schema)

    def mark(field: Dict[str, Any]) -> None:
        field["range"] = range_text(field)
        for column in field.get("columns") or []:
            mark(column)

    def walk(section: Dict[str, Any]) -> None:
        for field in section.get("fields") or []:
            mark(field)
        for row in section.get("rows") or []:
            for field in row.get("fields") or []:
                mark(field)
        for group in section.get("groups") or []:
            walk(group)

    for form in (schema.get("forms") or {}).values():
        for section in form.get("sections") or []:
            walk(section)
    return schema


def font_families(current: str) -> List[str]:
    """The font families to offer, sorted without regard to case.

    As Tk's dialog: blank names and Windows' vertical-writing names
    (starting with "@") are left out, and the family the editor shows now
    is always in the list (the config's Tk name ``TkFixedFont`` is shown as
    the family it stands for).
    """
    families = {f for f in QFontDatabase.families() if f.strip() and not f.startswith("@")}
    if current:
        families.add(current)
    return sorted(families, key=str.lower)


class SettingsModel(QObject):
    """The Settings window's state holder (see the module docstring).

    Args:
        store: The window's :class:`~chordnotepad_desktop.session_store.SessionStore`.
    """

    #: The window should be shown (an edit is open) or not.
    openChanged = Signal()
    #: values, keyChoices or fontFamilies changed.
    draftChanged = Signal()
    #: numberTexts / numberErrors changed.
    numbersChanged = Signal()
    #: The voicing form's schema arrived.
    schemaChanged = Signal()
    #: hasChanges changed.
    changesChanged = Signal()
    #: Save or Discard ended the edit: the window closes.
    finished = Signal()
    #: Save was refused for a wrong voicing (the session selected it and
    #: said why); the window shows the Voicings page.
    saveRefused = Signal()

    def __init__(self, store: Any, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._store = store
        self._open = False
        self._limits: Dict[str, Any] = {}
        self._keys: Dict[str, List[str]] = {"american": [], "european": []}
        #: What the window shows, and what the config has (the last values sent).
        self._draft: Optional[Dict[str, Any]] = None
        self._saved: Optional[Dict[str, Any]] = None
        self._number_texts: Dict[str, str] = {}
        self._schema: Any = None
        self._families: List[str] = []
        # Voicing values sent but not echoed by a VoicingEditorState yet.
        self._pending: Dict[str, Any] = {}
        # A voicing command other than a selection went out since the edit began.
        self._voicings_changed = False
        # save_settings sent but not run by the session yet.
        self._saving = False
        store.event.connect(self._on_event)
        store.stateChanged.connect(self._on_state)
        self._on_state("SettingsState")

    # -- life ------------------------------------------------------------------------

    def _get_open(self) -> bool:
        return self._open

    #: An edit is open: the window shows.
    isOpen = Property(bool, _get_open, notify=openChanged)

    @Slot()
    def open(self) -> None:
        """Open the window's edit (nothing if one is open already)."""
        if self._open:
            return
        if self._schema is None:
            self._store.submit("request_voicing_editor_schema")
        self._store.submit("begin_settings_edit")
        self._draft = self._saved = None
        self._number_texts = {}
        self._pending = {}
        self._voicings_changed = False
        self._take_settings(self._store.state("SettingsState").value("values"))
        self._open = True
        self.openChanged.emit()
        self.numbersChanged.emit()
        self.changesChanged.emit()

    @Slot(result=bool)
    def save(self) -> bool:
        """Save everything (``save_settings``) and end the edit.

        False, with nothing sent, while a number's text is wrong. A wrong
        voicing is the session's to refuse: it selects the voicing, says why
        (``UserError``) and keeps the edit open (:attr:`saveRefused`).
        Otherwise :attr:`finished` follows.
        """
        if not self._open:
            return True
        if self._number_texts:
            return False
        if self._saving:
            return True
        self._saving = True
        self._store.submit("save_settings", {"values": dict(self._draft) if self._draft else None})
        self._store.after_commands(self._save_ran)
        return True

    def _save_ran(self) -> None:
        self._saving = False
        if not self._open:
            return
        if self._store.state("VoicingEditorState").value("active"):
            self.saveRefused.emit()
            return
        self._end()
        self.finished.emit()

    @Slot()
    def discard(self) -> None:
        """Drop every change and end the edit (``cancel_settings_edit``):
        nothing is written."""
        if not self._open:
            return
        self._store.submit("cancel_settings_edit")
        self._end()
        self.finished.emit()

    @Slot()
    def close(self) -> None:
        """End the edit without saving (the main window is closing)."""
        self.discard()

    def _end(self) -> None:
        self._open = False
        self._number_texts = {}
        self._pending = {}
        self._voicings_changed = False
        self.openChanged.emit()
        self.numbersChanged.emit()
        self.changesChanged.emit()

    def _get_has_changes(self) -> bool:
        if not self._open:
            return False
        editor = self._store.state("VoicingEditorState")
        return (self._voicings_changed or bool(self._number_texts)
                or bool(editor.value("restored"))
                or (self._draft is not None and self._draft != self._saved))

    #: Something isn't saved: Save and Discard are enabled, closing asks.
    hasChanges = Property(bool, _get_has_changes, notify=changesChanged)

    @Slot()
    def discardProblems(self) -> None:  # noqa: N802 (Qt)
        """Drop the wrong values kept from last time (the restored banner's
        Discard): every voicing with one goes back to its saved version."""
        if not self._open:
            return
        self._store.submit("discard_settings_problems")
        self.changesChanged.emit()

    # -- General and Playback ---------------------------------------------------------

    def _get_values(self) -> dict:
        return dict(self._draft or {})

    #: The General and Playback values shown (``DesktopSettingsValues``' fields;
    #: ``key`` American).
    values = Property("QVariantMap", _get_values, notify=draftChanged)

    def _get_number_texts(self) -> dict:
        return dict(self._number_texts)

    #: ``{setting: text}`` for the number fields whose text isn't valid.
    numberTexts = Property("QVariantMap", _get_number_texts, notify=numbersChanged)

    def _get_number_errors(self) -> dict:
        out = {}
        for name in self._number_texts:
            low, high = self.number_range(name)
            out[name] = NUMBER_RANGE_MESSAGE.format(low=low, high=high)
        return out

    #: ``{setting: message}`` for the same fields.
    numberErrors = Property("QVariantMap", _get_number_errors, notify=numbersChanged)

    def _get_limits(self) -> dict:
        return {name: list(self.number_range(name)) for name in NUMBER_SETTINGS}

    #: ``{setting: [low, high]}`` of the number fields.
    limits = Property("QVariantMap", _get_limits, notify=draftChanged)

    def number_range(self, name: str) -> tuple:
        """The accepted range of number setting ``name`` (``SettingsState``'s limits)."""
        limits = self._limits
        if name == "font_size":
            return limits.get("font_size_min", 6), limits.get("font_size_max", 72)
        if name == "max_recent_files":
            return 1, limits.get("max_recent_files_max", 50)
        if name == "bpm":
            return limits.get("bpm_min", 20), limits.get("bpm_max", 400)
        if name == "time_signature_beats":
            return 1, 16
        raise ValueError(f"{name!r} is not a number setting")

    def _get_key_choices(self) -> list:
        notation = (self._draft or {}).get("notation", "american")
        shown = self._keys.get(notation) or self._keys["american"]
        return ([{"value": "", "label": NO_KEY_LABEL}]
                + [{"value": american, "label": label}
                   for american, label in zip(self._keys["american"], shown)])

    #: The default key's choices in the draft's notation: ``{value, label}``,
    #: the value American ("" for none).
    keyChoices = Property("QVariantList", _get_key_choices, notify=draftChanged)

    def _get_font_families(self) -> list:
        return list(self._families)

    #: The font families to choose from (see :func:`font_families`).
    fontFamilies = Property("QVariantList", _get_font_families, notify=draftChanged)

    def _get_font_family(self) -> str:
        return editor_font.resolve_family((self._draft or {}).get("font_family"))

    #: The family the font box shows (the config's Tk name as the family it means).
    fontFamily = Property(str, _get_font_family, notify=draftChanged)

    def _get_choices(self) -> dict:
        return {
            # "Auto" stands for no driver (the suggestions' "").
            "audioDrivers": [AUTO_DRIVER_LABEL] + [d for d in AUDIO_DRIVER_SUGGESTIONS if d],
            "audioDriverAuto": AUTO_DRIVER_LABEL,
            "logLevels": list(LOG_LEVELS),
            "themes": [{"value": t, "label": THEME_LABELS[t]} for t in UI_THEMES],
            "timeUnits": list(TIME_UNITS),
        }

    #: The fixed choices: ``audioDrivers`` (with ``audioDriverAuto`` for none),
    #: ``logLevels``, ``themes``, ``timeUnits``.
    choices = Property("QVariantMap", _get_choices, constant=True)

    @Slot(str, "QVariant")
    def setValue(self, name: str, value: Any) -> None:  # noqa: N802 (Qt)
        """Set a General/Playback value (not a typed number) in the draft."""
        if self._draft is None or name not in self._draft:
            logger.warning("Settings value %r ignored: no such setting or no edit", name)
            return
        if name == "font_family" and value == self._get_font_family():
            return     # the family shown already (TkFixedFont shows as the one it means)
        if name in ("soundfont_path", "audio_driver"):
            value = str(value or "").strip() or None
        if name == "audio_driver" and value is not None and value.lower() == AUTO_DRIVER_LABEL.lower():
            value = None
        if name == "time_signature_unit":
            value = int(value)
        if self._draft.get(name) == value:
            return
        self._draft[name] = value
        if name == "font_family":
            self._refresh_families()
        if name == "notation":
            # The voicing form shows note names in the notation being edited.
            self._store.submit("set_settings_notation", {"notation": value})
        self.draftChanged.emit()
        self.changesChanged.emit()

    @Slot(str, str)
    @Slot(str, str, bool)
    def setNumber(self, name: str, text: str, now: bool = False) -> None:  # noqa: N802 (Qt)
        """A number field's text: a whole number in range goes into the
        draft; anything else is kept as typed and marked, and Save waits
        for it (Q8). ``now`` (an arrow, Enter, leaving the field) is kept
        for the field's callers; the draft takes every text the same way."""
        if self._draft is None or name not in NUMBER_SETTINGS:
            return
        low, high = self.number_range(name)
        try:
            value = int(str(text).strip())
        except ValueError:
            value = None
        if value is not None and low <= value <= high:
            self._number_texts.pop(name, None)
            self._draft[name] = value
        else:
            # Back to the saved value while the text is wrong.
            if self._saved is not None:
                self._draft[name] = self._saved[name]
            self._number_texts[name] = str(text)
        self.draftChanged.emit()
        self.numbersChanged.emit()
        self.changesChanged.emit()

    @Slot("QVariant", result=str)
    def localFile(self, url: Any) -> str:  # noqa: N802 (Qt)
        """A file dialog's URL as a local path ("" if it isn't a local file)."""
        return QUrl(url).toLocalFile() if not isinstance(url, QUrl) else url.toLocalFile()

    def _follow_config(self) -> None:
        """Take into the draft what changed in the config from elsewhere
        while the window is open (the ☰ Dark theme, text zoom, Word wrap),
        so Save doesn't write the old value back. A value the window
        changed itself stays as the window has it; a number being typed
        keeps its text."""
        if not self._open or self._saved is None or self._saving:
            return
        try:
            now = self._store.direct("settings_values")
        except RuntimeError:          # no services (some tests)
            return
        now = dataclasses.asdict(now) if dataclasses.is_dataclass(now) else dict(now or {})
        changed = {k: v for k, v in now.items() if k in self._saved and self._saved[k] != v}
        if not changed:
            return
        if self._draft is not None:
            for key, value in changed.items():
                if self._draft.get(key) == self._saved[key]:
                    self._draft[key] = value
        self._saved.update(changed)
        if "font_family" in changed:
            self._refresh_families()
        self.draftChanged.emit()
        self.changesChanged.emit()

    # -- the voicings editor ----------------------------------------------------------

    def _get_editor(self) -> QObject:
        return self._store.state("VoicingEditorState")

    #: The session's ``VoicingEditorState`` (a store map: ``selected``,
    #: ``values``, ``field_errors``, ...).
    editor = Property(QObject, _get_editor, constant=True)

    def _get_schema(self) -> Any:
        return self._schema

    #: ``voicing_form.editor_schema`` for this platform: ``models``,
    #: ``tree_groups``, ``texts``, ``help``, ``forms`` (each field with its
    #: tooltip's ``range`` line, :func:`range_text`).
    schema = Property("QVariant", _get_schema, notify=schemaChanged)

    @Slot(str)
    def selectVoicing(self, name: str) -> None:  # noqa: N802 (Qt)
        """Show voicing ``name`` in the form."""
        self._pending = {}
        self._voicing_command("select_voicing", {"name": name}, change=False)

    @Slot()
    def addVoicing(self) -> None:  # noqa: N802 (Qt)
        """Add a voicing ("New voicing (n)", a guitar fretboard); the session selects it."""
        self._pending = {}
        self._voicing_command("add_voicing", {})

    @Slot(result="QVariantList")
    def addPresets(self) -> list:  # noqa: N802 (Qt)
        """Add voicing's menu: ``{label, group}`` for every preset and every
        working voicing, in the session's order: the blanks (group
        ``blank``), the built-ins by model, then the user's voicings sorted
        by name. The state's ``presets`` leave out the selected voicing (it
        can't copy itself); a new one may copy it. A built-in being viewed
        (``read_only``) is in its own group already."""
        editor = self._store.state("VoicingEditorState")
        presets = [dict(p) for p in (editor.value("presets") or [])]
        selected = editor.value("selected")
        if (selected and not editor.value("read_only")
                and not any(p["group"] == "custom" and p["label"] == selected for p in presets)):
            others = [p for p in presets if p["group"] != "custom"]
            custom = sorted([p["label"] for p in presets if p["group"] == "custom"] + [selected])
            presets = others + [{"label": name, "group": "custom"} for name in custom]
        return presets

    @Slot(str, str)
    def addVoicingFrom(self, group: str, label: str) -> None:  # noqa: N802 (Qt)
        """Add a voicing that starts as preset ``label`` of ``group`` (one of
        :meth:`addPresets`, or a built-in of the list: group = its model);
        the session names it ("New fretboard voicing", "New <label>", ...)
        and selects it, in one state (``add_voicing_from``)."""
        self._pending = {}
        self._voicing_command("add_voicing_from", {"group": group, "label": label})

    @Slot(str, str)
    def selectBuiltin(self, group: str, label: str) -> None:  # noqa: N802 (Qt)
        """Show built-in ``label`` of model ``group`` in the form, read-only
        (``select_builtin``). Viewing one changes nothing."""
        self._pending = {}
        self._voicing_command("select_builtin", {"group": group, "label": label}, change=False)

    @Slot(str)
    def removeVoicing(self, name: str) -> None:  # noqa: N802 (Qt)
        """Remove voicing ``name`` (the window has asked)."""
        self._pending = {}
        self._voicing_command("remove_voicing", {"name": name})

    @Slot(str, str)
    def renameVoicing(self, old: str, new: str) -> None:  # noqa: N802 (Qt)
        """Rename a voicing; a refused name is the session's ``UserError``."""
        if new.strip() == old:
            return
        self._voicing_command("rename_voicing", {"old": old, "new": new})

    @Slot(str)
    def setModel(self, model: str) -> None:  # noqa: N802 (Qt)
        """Switch the selected voicing to ``model``'s defaults (the window asked first if dirty)."""
        self._pending = {}
        self._voicing_command("set_voicing_model", {"model": model})

    @Slot(str, "QVariant")
    @Slot(str, "QVariant", bool)
    def setField(self, field_id: str, value: Any, commit: bool = False) -> None:  # noqa: N802 (Qt)
        """A form field changed: re-checked by the session at once (``commit``,
        Enter or leaving the field, changes nothing more: Save writes it)."""
        if not self._open:
            return
        value = _plain(value)
        if self._form_values().get(field_id) == value:
            return
        self._pending[field_id] = value
        self._voicing_command("set_voicing_values", {"values": {field_id: value}})

    @Slot(str, int, str, "QVariant")
    @Slot(str, int, str, "QVariant", bool)
    def setCell(self, field_id: str, index: int, column: str, value: Any,  # noqa: N802 (Qt)
                commit: bool = False) -> None:
        """A records cell changed: the whole list goes out, built on the rows
        shown now (with edits not echoed yet), so quick edits of two cells both stay."""
        rows = copy.deepcopy(self._form_values().get(field_id) or [])
        if not 0 <= index < len(rows):
            return
        rows[index] = dict(rows[index])
        rows[index][column] = _plain(value)
        self.setField(field_id, rows, commit)

    @Slot(str)
    def addRecord(self, field_id: str) -> None:  # noqa: N802 (Qt)
        """Add a row to records field ``field_id`` (the ensemble's voices)."""
        self._pending.pop(field_id, None)
        self._voicing_command("add_voicing_record", {"field_id": field_id})

    @Slot(int, str)
    def removeRecord(self, index: int, field_id: str) -> None:  # noqa: N802 (Qt)
        """Remove row ``index`` of records field ``field_id``."""
        self._pending.pop(field_id, None)
        self._voicing_command("remove_voicing_record", {"index": index, "field_id": field_id})

    @Slot(int, int, str)
    def moveRecord(self, index: int, offset: int, field_id: str) -> None:  # noqa: N802 (Qt)
        """Move row ``index`` of records field ``field_id`` by ``offset`` (-1 up, +1 down)."""
        self._pending.pop(field_id, None)
        self._voicing_command("move_voicing_record",
                              {"index": index, "offset": offset, "field_id": field_id})

    @Slot(str, result="QVariant")
    def fieldValue(self, field_id: str) -> Any:  # noqa: N802 (Qt)
        """A form field's value, with the edits the session hasn't echoed yet."""
        return self._form_values().get(field_id)

    def _form_values(self) -> Dict[str, Any]:
        values = dict(self._store.state("VoicingEditorState").value("values") or {})
        values.update(self._pending)
        return values

    def _voicing_command(self, name: str, args: dict, change: bool = True) -> None:
        if not self._open:
            return
        if name in READ_ONLY_REFUSED and self._store.state("VoicingEditorState").value("read_only"):
            # A built-in is shown: its controls are disabled, and the session
            # would refuse the edit (RuntimeError).
            logger.debug("%s ignored: the form shows a built-in voicing", name)
            return
        self._store.submit(name, args)
        if change and not self._voicings_changed:
            self._voicings_changed = True
            self.changesChanged.emit()

    # -- from the session -------------------------------------------------------------

    def _on_event(self, type_name: str, data: Any) -> None:
        if type_name == "VoicingEditorSchema":
            self._schema = with_ranges(data.get("schema"))
            self.schemaChanged.emit()

    def _on_state(self, type_name: str) -> None:
        if type_name == "SettingsState":
            state = self._store.state("SettingsState")
            self._limits = {key: state.value(key) for key in (
                "font_size_min", "font_size_max", "bpm_min", "bpm_max", "max_recent_files_max")
                if state.value(key) is not None}
            self._keys = {"american": list(state.value("american_keys") or []),
                          "european": list(state.value("european_keys") or [])}
            if self._open and self._draft is None:
                self._take_settings(state.value("values"))
            self._follow_config()
            self.draftChanged.emit()
        elif type_name == "EditorState":
            # Text zoom and Word wrap write the config without a SettingsState.
            self._follow_config()
        elif type_name == "VoicingEditorState":
            values = self._store.state("VoicingEditorState").value("values") or {}
            # An edit the session has applied is no longer pending.
            for key in [k for k, v in self._pending.items() if values.get(k) == v]:
                del self._pending[key]
            self.changesChanged.emit()

    def _take_settings(self, values: Optional[dict]) -> None:
        if not values:
            return
        self._draft = dict(values)
        self._saved = dict(values)
        self._refresh_families()
        self.draftChanged.emit()

    def _refresh_families(self) -> None:
        self._families = font_families(self._get_font_family())


def _plain(value: Any) -> Any:
    """A value from QML as plain JSON data (QJSValue lists and maps arrive converted)."""
    if hasattr(value, "toVariant"):
        value = value.toVariant()
    if isinstance(value, list):
        return [_plain(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    return value
