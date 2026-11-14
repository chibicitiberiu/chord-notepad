"""The Settings window (plan step G1): the Python side.

The window is QML (``qml/app/SettingsWindow.qml`` and the voicing form's
files); what it decides with is here, in :class:`SettingsModel`, the
desktop's counterpart of Android's ``SettingsController``. It saves as it
goes (parity checklist resolution 6), through the session's settings edit:

* :meth:`SettingsModel.open` sends ``begin_settings_edit`` (and asks for the
  voicing form's schema once); :meth:`SettingsModel.close` saves what is
  still waiting, then ``cancel_settings_edit`` ends the edit (the wrong
  values are dropped; what was valid is saved already).
* **General and Playback** are a draft of ``DesktopSettingsValues``
  (:attr:`SettingsModel.values`), started from the session's
  ``SettingsState``. A change goes out at once with ``commit_settings``; a
  number being typed goes out when the typing rests (:data:`DRAFT_SAVE_DELAY_MS`).
  A number that isn't a whole number in range is never put in the draft
  (Q8): it is kept as typed (:attr:`SettingsModel.numberTexts`), shown with
  its message (:attr:`SettingsModel.numberErrors`) and sent as
  ``invalid_numbers``, so the config keeps its valid value.
* **Voicings**: the session's ``VoicingEditorState`` is the form
  (:attr:`SettingsModel.editor`, a map of the store). A keystroke sends
  ``set_voicing_values`` (the session re-checks it and the marks come back);
  Enter, leaving the field and every other voicing command also save
  (``commit_settings``): the session writes each voicing's valid fields and
  keeps the wrong ones at the value on disk.

The field kinds, labels, help and messages come from the core's schema
(``settings_forms.voicing_form.editor_schema``, :attr:`SettingsModel.schema`);
the window only lays them out.
"""

import copy
import logging
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QFontDatabase

from chordnotepad.constants import LOG_LEVELS, UI_THEMES
from chordnotepad.session.settings import AUDIO_DRIVER_SUGGESTIONS, NUMBER_SETTINGS
from chordnotepad_desktop import editor_font

logger = logging.getLogger(__name__)

#: How long a number's text rests before it is saved (Android's DRAFT_SAVE_DELAY_MS).
DRAFT_SAVE_DELAY_MS = 400

#: A number field's text that isn't a whole number in range (Android's
#: ``settings_number_range``).
NUMBER_RANGE_MESSAGE = "Enter a whole number from {low} to {high}."

#: The default time signature's units (the Tk dialog's; the checklist's "2, 4, 8 or 16").
TIME_UNITS = (2, 4, 8, 16)

#: The theme choices (config ``ui_theme``), with the mockup's labels.
THEME_LABELS = {"system": "Follow the system", "light": "Light", "dark": "Dark"}

#: The default key's "no key" entry (Android's ``settings_key_none``).
NO_KEY_LABEL = "None"


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
    #: Whether something wrong isn't saved changed.
    problemsChanged = Signal()

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
        self._sent_numbers: Dict[str, str] = {}
        self._schema: Any = None
        self._families: List[str] = []
        # Voicing values sent but not echoed by a VoicingEditorState yet.
        self._pending: Dict[str, Any] = {}
        # Voicing values sent with set_voicing_values since the last commit.
        self._unsaved_form = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(DRAFT_SAVE_DELAY_MS)
        self._timer.timeout.connect(self.flush)
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
        self._number_texts, self._sent_numbers = {}, {}
        self._pending = {}
        self._take_settings(self._store.state("SettingsState").value("values"))
        self._open = True
        self.openChanged.emit()
        self.numbersChanged.emit()
        self.problemsChanged.emit()

    @Slot()
    def close(self) -> None:
        """Save what is still waiting, then end the edit (the wrong values go)."""
        if not self._open:
            return
        self.flush()
        self._store.submit("cancel_settings_edit")
        self._open = False
        self._number_texts, self._sent_numbers = {}, {}
        self._pending = {}
        self.openChanged.emit()
        self.numbersChanged.emit()
        self.problemsChanged.emit()

    def _get_has_problems(self) -> bool:
        problems = self._store.state("VoicingEditorState").value("problems") or []
        return bool(self._number_texts) or bool(problems)

    #: Something wrong isn't saved (a number's text or a voicing value):
    #: closing asks first.
    hasProblems = Property(bool, _get_has_problems, notify=problemsChanged)

    @Slot()
    def discardProblems(self) -> None:  # noqa: N802 (Qt)
        """Drop the wrong values and stay (every voicing with one goes back
        to its saved version; the number fields show their saved values)."""
        if not self._open:
            return
        self._timer.stop()
        self._number_texts, self._sent_numbers = {}, {}
        self._pending = {}
        if self._saved is not None:
            self._draft = dict(self._saved)
        self._store.submit("discard_settings_problems")
        self.draftChanged.emit()
        self.numbersChanged.emit()
        self.problemsChanged.emit()

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
            "audioDrivers": list(AUDIO_DRIVER_SUGGESTIONS),
            "logLevels": list(LOG_LEVELS),
            "themes": [{"value": t, "label": THEME_LABELS[t]} for t in UI_THEMES],
            "timeUnits": list(TIME_UNITS),
        }

    #: The fixed choices: ``audioDrivers``, ``logLevels``, ``themes``, ``timeUnits``.
    choices = Property("QVariantMap", _get_choices, constant=True)

    @Slot(str, "QVariant")
    def setValue(self, name: str, value: Any) -> None:  # noqa: N802 (Qt)
        """Set a General/Playback value (not a typed number) and save it."""
        if self._draft is None or name not in self._draft:
            logger.warning("Settings value %r ignored: no such setting or no edit", name)
            return
        if name == "font_family" and value == self._get_font_family():
            return     # the family shown already (TkFixedFont shows as the one it means)
        if name in ("soundfont_path", "audio_driver"):
            value = str(value or "").strip() or None
        if name == "time_signature_unit":
            value = int(value)
        if self._draft.get(name) == value:
            return
        self._draft[name] = value
        if name == "font_family":
            self._refresh_families()
        self.draftChanged.emit()
        self.flush()

    @Slot(str, str)
    @Slot(str, str, bool)
    def setNumber(self, name: str, text: str, now: bool = False) -> None:  # noqa: N802 (Qt)
        """A number field's text: a whole number in range goes into the
        draft; anything else is kept as typed, marked and never saved (Q8).

        Saved when the typing rests, or ``now`` (an arrow, Enter, leaving the field).
        """
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
            # Back to the saved value: a number typed on the way (the 6 of
            # 60, outside 1-50) must not be saved when the typing rests.
            if self._saved is not None:
                self._draft[name] = self._saved[name]
            self._number_texts[name] = str(text)
        self.draftChanged.emit()
        self.numbersChanged.emit()
        self.problemsChanged.emit()
        if now:
            self.flush()
        else:
            self._timer.start()

    @Slot("QVariant", result=str)
    def localFile(self, url: Any) -> str:  # noqa: N802 (Qt)
        """A file dialog's URL as a local path ("" if it isn't a local file)."""
        return QUrl(url).toLocalFile() if not isinstance(url, QUrl) else url.toLocalFile()

    @Slot()
    def flush(self) -> None:
        """Save what waits: the draft and the wrong number texts if they
        changed since the last save, and voicing edits not saved yet."""
        self._timer.stop()
        if not self._open:
            return
        values_changed = self._draft is not None and self._draft != self._saved
        numbers_changed = self._number_texts != self._sent_numbers
        if values_changed or numbers_changed or self._unsaved_form:
            self._commit(values=values_changed)

    def _commit(self, values: bool = None) -> None:
        """``commit_settings`` with the draft (when it changed) and the number
        texts (when they changed)."""
        if values is None:
            values = self._draft is not None and self._draft != self._saved
        numbers = self._number_texts != self._sent_numbers
        args: Dict[str, Any] = {
            "values": dict(self._draft) if values and self._draft is not None else None,
            "invalid_numbers": dict(self._number_texts) if numbers else None,
        }
        if values:
            self._saved = dict(self._draft)
        self._sent_numbers = dict(self._number_texts)
        self._unsaved_form = False
        self._store.submit("commit_settings", args)

    # -- the voicings editor ----------------------------------------------------------

    def _get_editor(self) -> QObject:
        return self._store.state("VoicingEditorState")

    #: The session's ``VoicingEditorState`` (a store map: ``selected``,
    #: ``values``, ``field_errors``, ...).
    editor = Property(QObject, _get_editor, constant=True)

    def _get_schema(self) -> Any:
        return self._schema

    #: ``voicing_form.editor_schema`` for this platform: ``models``,
    #: ``tree_groups``, ``texts``, ``help``, ``forms``.
    schema = Property("QVariant", _get_schema, notify=schemaChanged)

    @Slot(str)
    def selectVoicing(self, name: str) -> None:  # noqa: N802 (Qt)
        """Show voicing ``name`` in the form."""
        self._pending = {}
        self._voicing_command("select_voicing", {"name": name}, commit=False)

    @Slot()
    def addVoicing(self) -> None:  # noqa: N802 (Qt)
        """Add a voicing ("New voicing (n)", a guitar fretboard); the session selects it."""
        self._pending = {}
        self._voicing_command("add_voicing", {})

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

    @Slot(str, str)
    def loadPreset(self, group: str, label: str) -> None:  # noqa: N802 (Qt)
        """Copy a preset's parameters into the selected voicing (the window asked first)."""
        self._pending = {}
        self._voicing_command("load_voicing_preset", {"group": group, "label": label})

    @Slot(str, "QVariant")
    @Slot(str, "QVariant", bool)
    def setField(self, field_id: str, value: Any, commit: bool = False) -> None:  # noqa: N802 (Qt)
        """A form field changed: re-checked by the session at once, saved
        with ``commit`` (Enter, leaving the field, a checkbox or a choice)."""
        if not self._open:
            return
        value = _plain(value)
        if self._form_values().get(field_id) == value:
            if commit:
                self.commitVoicing()
            return
        self._pending[field_id] = value
        self._unsaved_form = True
        self._voicing_command("set_voicing_values", {"values": {field_id: value}}, commit=commit)

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

    @Slot()
    def commitVoicing(self) -> None:  # noqa: N802 (Qt)
        """Save the voicing edits (Enter or leaving a field), if there are any."""
        if self._open and self._unsaved_form:
            self._commit()

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

    def _voicing_command(self, name: str, args: dict, commit: bool = True) -> None:
        if not self._open:
            return
        self._store.submit(name, args)
        if commit:
            self._commit()

    # -- from the session -------------------------------------------------------------

    def _on_event(self, type_name: str, data: Any) -> None:
        if type_name == "VoicingEditorSchema":
            self._schema = data.get("schema")
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
            self.draftChanged.emit()
        elif type_name == "VoicingEditorState":
            values = self._store.state("VoicingEditorState").value("values") or {}
            # An edit the session has applied is no longer pending.
            for key in [k for k, v in self._pending.items() if values.get(k) == v]:
                del self._pending[key]
            self.problemsChanged.emit()

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
