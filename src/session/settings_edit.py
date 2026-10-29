"""A Settings screen's working copy, for views across the bridge (Android).

The desktop Settings dialog holds a live ``SettingsViewModel`` and its
Voicings page keeps the form in Tk widgets. A bridge view can hold neither,
so the session keeps them here: :class:`SettingsEdit` wraps the same
``SettingsViewModel`` working copy (``AppSession.begin_settings_edit``) plus
the voicing loaded in the form, and every edit goes through the viewmodel
exactly as the desktop page does (``add_voicing``, ``remove_voicing``,
``rename_voicing``, ``set_voicing_data(name, voicing_from_values(...))``).
``save`` runs ``validate_all`` as the gate and then ``commit``.

What the view draws comes out as :class:`~session.state.VoicingEditorState`
(:meth:`SettingsEdit.state`); the form schema it draws with is static
(``settings_forms.voicing_form.editor_schema``).
"""

import copy
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional, Tuple

from settings_forms import voicing_form as form
from session.state import VoicingEditorState, VoicingGroup, VoicingPreset
from settings_forms.voicing_texts import MODEL_LABELS

if TYPE_CHECKING:
    from viewmodels.settings_viewmodel import SettingsViewModel


class SettingsEdit:
    """The working copy of one Settings screen and its voicing form."""

    def __init__(self, model: "SettingsViewModel") -> None:
        """Start editing ``model`` (a fresh ``SettingsViewModel``); nothing selected."""
        self.model = model
        self._selected: Optional[str] = None
        self._form_model: Optional[str] = None
        self._values: Dict[str, Any] = {}
        self._label: Optional[str] = None
        self._dirty = False
        self._revision = 0

    # -- the voicings list -----------------------------------------------------

    @property
    def selected(self) -> Optional[str]:
        """The voicing in the form, or None."""
        return self._selected

    def select(self, name: str) -> None:
        """Load ``name`` into the form (not edited yet).

        Raises:
            ValueError: If there is no such voicing.
        """
        voicings = self.model.get_voicings()
        if name not in voicings:
            raise ValueError(f"No voicing named '{name}'.")
        data = voicings[name]
        self._selected = name
        self._load(data)
        self._dirty = False

    def add(self) -> str:
        """Add a voicing (a guitar fretboard, uniquely named) and select it."""
        name = self.model.add_voicing()
        self.select(name)
        return name

    def remove(self, name: str) -> None:
        """Remove ``name``; the form empties if it was the one shown."""
        self.model.remove_voicing(name)
        if self._selected == name:
            self._clear()

    def rename(self, old: str, new: str) -> None:
        """Rename a voicing (the form follows it).

        Raises:
            ValueError: For an empty or taken name, or no voicing ``old``.
        """
        self.model.rename_voicing(old, new)
        if self._selected == old:
            self._selected = (new or "").strip()

    # -- the form ----------------------------------------------------------------

    def set_values(self, values: Mapping[str, Any]) -> None:
        """Take edited form values (all of them, or just the changed ones).

        The merged values are parsed forgivingly into the voicing (a value
        that doesn't parse stays a raw string and shows as a field error).

        Raises:
            RuntimeError: If no voicing is selected.
            TypeError: If ``values`` isn't an object.
        """
        self._require_selected()
        if not isinstance(values, Mapping):
            raise TypeError(f"voicing values must be an object, got {values!r}")
        merged = dict(self._values)
        merged.update(copy.deepcopy(dict(values)))
        self._values = merged
        self._store(form.voicing_from_values(self._form_model, merged, self._label))

    def set_model(self, model: str) -> None:
        """Switch the selected voicing to ``model`` with that model's defaults.

        Raises:
            RuntimeError: If no voicing is selected.
            ValueError: For an unknown model.
        """
        self._require_selected()
        if model not in form.MODELS:
            raise ValueError(f"unknown voicing model {model!r}")
        if model == self._form_model:
            return
        self._label = None
        data = form.default_voicing(model)
        self._store(data)
        self._load(data, keep_label=True)

    def add_record(self, field_id: str = "voices") -> None:
        """Append a row to a records field (the ensemble's voices)."""
        self._require_selected()
        self._replace_values(form.add_record(self._form_model, self._values, field_id))

    def remove_record(self, index: int, field_id: str = "voices") -> None:
        """Remove row ``index`` of a records field (nothing if out of range)."""
        self._require_selected()
        self._replace_values(form.remove_record(self._form_model, self._values, index, field_id))

    def presets(self) -> List[Dict[str, Any]]:
        """The "Load config" entries (built-ins, then the working voicings)."""
        return self.model.get_load_presets()

    def load_preset(self, group: str, label: str) -> None:
        """Replace the selected voicing's parameters with a "Load config" entry.

        Raises:
            RuntimeError: If no voicing is selected.
            ValueError: If there is no such entry.
        """
        self._require_selected()
        for preset in self.presets():
            if preset["group"] == group and preset["label"] == label:
                data = copy.deepcopy(preset["data"])
                self._label = data.get("label")
                self._store(data)
                self._load(data, keep_label=True)
                return
        raise ValueError(f"no preset {label!r} in group {group!r}")

    # -- saving ------------------------------------------------------------------

    def first_invalid(self) -> Optional[Tuple[str, str]]:
        """The first voicing Save would refuse, as ``(name, message)``, or None."""
        errors = self.model.validate_all()
        return errors[0] if errors else None

    # -- output ------------------------------------------------------------------

    def bump(self) -> None:
        """Count one more command (the state's ``revision``)."""
        self._revision += 1

    def state(self) -> VoicingEditorState:
        """What the voicings editor shows now."""
        voicings = self.model.get_voicings()
        by_group: Dict[str, List[str]] = {group: [] for group in form.TREE_GROUPS}
        for name in sorted(voicings):
            model = voicings[name].get("model", "piano")
            by_group[model if model in form.TREE_GROUPS else "piano"].append(name)
        groups = tuple(VoicingGroup(group, MODEL_LABELS[group], tuple(by_group[group]))
                       for group in form.TREE_GROUPS)
        invalid = tuple(name for name, _ in self.model.validate_all())
        presets = tuple(VoicingPreset(p["label"], p["group"]) for p in self.presets())
        if self._selected is None:
            return VoicingEditorState(
                active=True, revision=self._revision, groups=groups, invalid=invalid,
                presets=presets, selected=None, model=None, values={}, field_errors={},
                form_errors=(), hints={}, dirty=False)
        checked = form.validate_form(self._selected, self._form_model, self._values, self._label)
        schema = form.form_schema(self._form_model)
        hints = {f["id"]: form.field_hint(f, self._values)
                 for f in form.iter_fields(schema) if f.get("hint")}
        return VoicingEditorState(
            active=True, revision=self._revision, groups=groups, invalid=invalid,
            presets=presets, selected=self._selected, model=self._form_model,
            values=copy.deepcopy(self._values), field_errors=checked["fields"],
            form_errors=tuple(checked["form"]), hints=hints, dirty=self._dirty)

    # -- internals ---------------------------------------------------------------

    def _require_selected(self) -> None:
        if self._selected is None:
            raise RuntimeError("no voicing is selected in the voicings editor")

    def _load(self, data: Mapping[str, Any], keep_label: bool = False) -> None:
        self._form_model = form.form_model(data.get("model", "piano"))
        self._values = form.values_from_voicing(self._form_model, data)
        if not keep_label:
            self._label = data.get("label")

    def _store(self, data: Dict[str, Any]) -> None:
        self.model.set_voicing_data(self._selected, data)
        self._dirty = True

    def _replace_values(self, values: Dict[str, Any]) -> None:
        self._values = values
        self._store(form.voicing_from_values(self._form_model, values, self._label))

    def _clear(self) -> None:
        self._selected = None
        self._form_model = None
        self._values = {}
        self._label = None
        self._dirty = False
