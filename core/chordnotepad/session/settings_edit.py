"""A Settings screen's working copy, for views across the bridge (Android).

The desktop Settings dialog holds a live ``SettingsViewModel`` and its
Voicings page keeps the form in Tk widgets. A bridge view can hold neither,
so the session keeps them here: :class:`SettingsEdit` wraps the same
``SettingsViewModel`` working copy (``AppSession.begin_settings_edit``) plus
the voicing loaded in the form, and every edit goes through the viewmodel
exactly as the desktop page does (``add_voicing``, ``remove_voicing``,
``rename_voicing``, ``set_voicing_data(name, voicing_from_values(...))``).
``save`` runs ``validate_all`` as the gate and then ``commit``.

Android saves as it goes instead (``AppSession.commit_settings``): every
voicing that differs from the config gets a plan
(``settings_forms.voicing_autosave``), which writes its valid fields and
keeps its wrong ones at the value on disk; :meth:`SettingsEdit.registry`
is what gets written. The edit then :meth:`SettingsEdit.rebase` s onto a
fresh working copy of the config, carrying over the voicings that still have
wrong values (:meth:`SettingsEdit.staged_voicings`, which the session also
keeps in a staging file for when the app goes away before they are fixed).

What the view draws comes out as :class:`~session.state.VoicingEditorState`
(:meth:`SettingsEdit.state`); the form schema it draws with is static
(``settings_forms.voicing_form.editor_schema``).
"""

import copy
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Mapping, Optional, Tuple

from chordnotepad.settings_forms import voicing_form as form
from chordnotepad.settings_forms.voicing_autosave import VoicingPlan, plan_voicing, problem_text
from chordnotepad.session.state import SettingsProblem, VoicingEditorState, VoicingGroup, VoicingPreset
from chordnotepad.settings_forms.voicing_texts import (
    BLANK_PRESET_LABELS, BLANK_VOICING_NAMES, COPY_NAME, MODEL_LABELS,
)

#: The group of the presets that are a model's defaults (listed first).
BLANK_GROUP = "blank"

if TYPE_CHECKING:
    from chordnotepad.viewmodels.settings_viewmodel import SettingsViewModel


class SettingsEdit:
    """The working copy of one Settings screen and its voicing form."""

    def __init__(self, model: "SettingsViewModel", blank_presets: bool = True) -> None:
        """Start editing ``model`` (a fresh ``SettingsViewModel``); nothing selected.

        Args:
            model: The working copy.
            blank_presets: Whether :meth:`presets` lists the ``blank`` group
                first (a model's defaults; not on Android, whose "Load
                config" menu has no heading for it).
        """
        self.model = model
        self._blank_presets = blank_presets
        self._selected: Optional[str] = None
        #: ``(group, label)`` of the built-in shown read-only, or None.
        self._builtin: Optional[Tuple[str, str]] = None
        self._form_model: Optional[str] = None
        self._values: Dict[str, Any] = {}
        self._label: Optional[str] = None
        self._dirty = False
        self._revision = 0
        self._recent: List[str] = []
        #: General/Playback number fields whose text isn't valid, ``{setting: text}``.
        self.staged_numbers: Dict[str, str] = {}
        #: Whether the edit opened with wrong values kept from last time.
        self.restored = False

    def rebase(self, model: "SettingsViewModel", keep: Iterable[str] = ()) -> None:
        """Carry on with ``model``, a fresh working copy of what was just
        committed; the working data of the voicings in ``keep`` (those with
        wrong values) carries over, and the form stays as it is."""
        old = self.model.get_voicings()
        self.model = model
        for name in keep:
            if name in old:
                model.set_voicing_data(name, copy.deepcopy(old[name]))

    @property
    def notation(self) -> str:
        """The notation the form shows note names in: the Settings notation
        being edited (``model.notation``), not the open song's."""
        return "european" if self.model.notation == "european" else "american"

    def respell(self) -> None:
        """Show the form's note names in :attr:`notation` again (it changed).

        The form is rebuilt from the voicing, so a value being typed that
        doesn't parse stays as it is."""
        if self._builtin is not None:
            self._values = form.values_from_voicing(
                self._form_model, self._builtin_data(*self._builtin), self.notation)
        elif self._selected is not None:
            self._values = form.values_from_voicing(
                self._form_model, self.model.get_voicings()[self._selected], self.notation)

    # -- the voicings list -----------------------------------------------------

    @property
    def selected(self) -> Optional[str]:
        """The voicing in the form, or None."""
        return self._selected

    @property
    def read_only(self) -> bool:
        """Whether the form shows a built-in (:meth:`select_builtin`): every
        edit is refused until a voicing of the user's is selected."""
        return self._builtin is not None

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
        self._builtin = None
        self._load(data)
        self._dirty = False
        self._recent = []

    def select_builtin(self, group: str, label: str) -> None:
        """Show built-in ``label`` of model ``group`` (a ``VoicingGroup.builtins``
        entry) in the form, read-only.

        Raises:
            ValueError: If there is no such built-in.
        """
        data = self._builtin_data(group, label)
        self._selected = label
        self._builtin = (group, label)
        self._load(data)
        self._dirty = False
        self._recent = []

    def add(self) -> str:
        """Add a voicing (a guitar fretboard, uniquely named) and select it."""
        name = self.model.add_voicing()
        self.select(name)
        return name

    def add_from(self, group: str, label: str) -> str:
        """Add a voicing that starts as preset ``label`` of ``group`` and select it.

        ``group`` is ``blank`` (a model's defaults), a model (a built-in) or
        ``custom`` (a voicing of the working copy, also the selected one).
        A blank is named "New fretboard voicing" (and so on), a copy "New
        <label>"; either is numbered ("New Piano (default) 2") when the
        name is taken, ignoring case, or a built-in's.

        Raises:
            ValueError: If there is no such preset.
        """
        for preset in self._all_presets():
            if preset["group"] == group and preset["label"] == label:
                break
        else:
            raise ValueError(f"no preset {label!r} in group {group!r}")
        data = copy.deepcopy(preset["data"])
        if group == BLANK_GROUP:
            base = BLANK_VOICING_NAMES[data["model"]]
        else:
            base = COPY_NAME.format(label=label)
        name = self.model.add_voicing_data(base, data)
        self.select(name)
        return name

    def remove(self, name: str) -> None:
        """Remove ``name``; the form empties if it was the one shown."""
        self.model.remove_voicing(name)
        if self._selected == name and self._builtin is None:
            self._clear()

    def rename(self, old: str, new: str) -> None:
        """Rename a voicing (the form follows it).

        Raises:
            ValueError: For an empty or taken name, or no voicing ``old``.
        """
        self.model.rename_voicing(old, new)
        if self._selected == old and self._builtin is None:
            self._selected = (new or "").strip()

    # -- the form ----------------------------------------------------------------

    def set_values(self, values: Mapping[str, Any]) -> None:
        """Take edited form values (all of them, or just the changed ones).

        The merged values are parsed forgivingly into the voicing (a value
        that doesn't parse stays a raw string and shows as a field error).

        Raises:
            RuntimeError: If no voicing is selected, or a built-in is.
            TypeError: If ``values`` isn't an object.
        """
        self._require_editable()
        if not isinstance(values, Mapping):
            raise TypeError(f"voicing values must be an object, got {values!r}")
        merged = dict(self._values)
        merged.update(copy.deepcopy(dict(values)))
        self._values = merged
        for key in values:
            if key in self._recent:
                self._recent.remove(key)
            self._recent.append(key)
        self._store(form.voicing_from_values(self._form_model, merged, self._label))

    def set_model(self, model: str) -> None:
        """Switch the selected voicing to ``model`` with that model's defaults.

        Raises:
            RuntimeError: If no voicing is selected, or a built-in is.
            ValueError: For an unknown model.
        """
        self._require_editable()
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
        self._require_editable()
        self._replace_values(form.add_record(self._form_model, self._values, field_id,
                                             self.notation))

    def remove_record(self, index: int, field_id: str = "voices") -> None:
        """Remove row ``index`` of a records field (nothing if out of range)."""
        self._require_editable()
        self._replace_values(form.remove_record(self._form_model, self._values, index, field_id,
                                                self.notation))

    def duplicate_record(self, index: int, field_id: str = "voices") -> None:
        """Copy row ``index`` of a records field right below it (nothing if
        out of range): the same cells, the name with " 2" added."""
        self._require_editable()
        self._replace_values(form.duplicate_record(self._form_model, self._values, index,
                                                   field_id, self.notation))

    def move_record(self, index: int, offset: int, field_id: str = "voices") -> None:
        """Move row ``index`` of a records field by ``offset`` rows (-1 up, +1
        down; nothing if it would leave the list)."""
        self._require_editable()
        self._replace_values(form.move_record(self._form_model, self._values, index, offset,
                                              field_id, self.notation))

    def presets(self) -> List[Dict[str, Any]]:
        """The "Load config" entries: the blanks (unless left out for the
        platform), the built-ins, then the working voicings but the selected
        one."""
        exclude = self._selected if self._builtin is None else None
        blanks = self._blanks() if self._blank_presets else []
        return blanks + self.model.get_load_presets(exclude=exclude)

    def builtins(self, model: str) -> Tuple[str, ...]:
        """The built-in presets of ``model``, in preset order (their labels)."""
        return tuple(p["label"] for p in self.model.get_load_presets() if p["group"] == model)

    def load_preset(self, group: str, label: str) -> None:
        """Replace the selected voicing's parameters with a "Load config" entry.

        Raises:
            RuntimeError: If no voicing is selected, or a built-in is.
            ValueError: If there is no such entry.
        """
        self._require_editable()
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

    def saved_voicing(self, name: str, disk: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
        """Working voicing ``name`` as the config ``disk`` has it (through a
        rename), or None if it isn't there."""
        original = self.model.original_name(name)
        return disk.get(original) if original is not None else None

    def plans(self, disk: Mapping[str, Any]) -> Dict[str, VoicingPlan]:
        """An autosave plan for every working voicing that differs from ``disk``."""
        out: Dict[str, VoicingPlan] = {}
        for name, data in self.model.get_voicings().items():
            saved = self.saved_voicing(name, disk)
            if saved is not None and data == saved:
                continue
            if name == self._selected and self._builtin is None:
                model, values, label, recent = self._form_model, self._values, self._label, self._recent
            else:
                model = form.form_model(data.get('model', 'piano'))
                values = form.values_from_voicing(model, data, self.notation)
                label, recent = data.get('label'), []
            out[name] = plan_voicing(name, model, values, label, saved, recent, self.notation)
        return out

    def registry(self, plans: Mapping[str, VoicingPlan],
                 disk: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
        """The voicings an autosave writes: each planned one's valid version
        (or what's on disk, when even that won't validate), the rest as they are."""
        out: Dict[str, Dict[str, Any]] = {}
        for name, data in self.model.get_voicings().items():
            plan = plans.get(name)
            if plan is None:
                out[name] = copy.deepcopy(data)
            elif plan.data is not None:
                out[name] = plan.data
            else:
                saved = self.saved_voicing(name, disk)
                if saved is not None:
                    out[name] = copy.deepcopy(saved)
        return out

    def staged_voicings(self, plans: Mapping[str, VoicingPlan]) -> Dict[str, Dict[str, Any]]:
        """The working data of the voicings with wrong values (what isn't saved)."""
        voicings = self.model.get_voicings()
        return {name: copy.deepcopy(voicings[name]) for name, plan in plans.items()
                if plan.problems and name in voicings}

    def discard_problems(self, disk: Mapping[str, Any]) -> None:
        """Put every voicing with wrong values back as ``disk`` has it, and
        forget the number texts."""
        for name, plan in self.plans(disk).items():
            if not plan.problems:
                continue
            saved = self.saved_voicing(name, disk)
            if saved is None:
                self.remove(name)
            else:
                self.model.set_voicing_data(name, copy.deepcopy(saved))
                if name == self._selected and self._builtin is None:
                    self.select(name)
        self.staged_numbers = {}
        self.restored = False

    # -- output ------------------------------------------------------------------

    def bump(self) -> None:
        """Count one more command (the state's ``revision``)."""
        self._revision += 1

    def state(self, disk: Mapping[str, Any]) -> VoicingEditorState:
        """What the voicings editor shows now (``disk``: the config's voicings)."""
        voicings = self.model.get_voicings()
        by_group: Dict[str, List[str]] = {group: [] for group in form.TREE_GROUPS}
        for name in sorted(voicings):
            model = voicings[name].get("model", "piano")
            by_group[model if model in form.TREE_GROUPS else "piano"].append(name)
        groups = tuple(VoicingGroup(group, MODEL_LABELS[group], tuple(by_group[group]),
                                    self.builtins(group))
                       for group in form.TREE_GROUPS)
        plans = self.plans(disk)
        listed = [name for group in groups for name in group.names]
        broken = {name for name, _ in self.model.validate_all()}
        invalid = tuple(name for name in listed
                        if name in broken or (name in plans and plans[name].problems))
        problems = tuple(self._problems(name, plans[name]) for name in listed if name in plans)
        presets = tuple(VoicingPreset(p["label"], p["group"]) for p in self.presets())
        common = dict(active=True, revision=self._revision, groups=groups, invalid=invalid,
                      presets=presets, problems=tuple(p for ps in problems for p in ps),
                      staged_numbers=dict(self.staged_numbers), restored=self.restored,
                      read_only=self.read_only)
        if self._selected is None:
            return VoicingEditorState(
                selected=None, model=None, values={}, field_errors={},
                form_errors=(), hints={}, dirty=False, **common)
        checked = form.validate_form(self._selected, self._form_model, self._values, self._label)
        field_errors = dict(checked["fields"])
        # (A built-in has no plan; a voicing of the user's may share its label.)
        own = self._builtin is None and self._selected in plans
        for problem in plans[self._selected].problems if own else ():
            if problem.field_id is not None:
                field_errors.setdefault(problem.field_id, problem.message)
        # The spec's message is the form's only while no field is blamed for
        # it: otherwise it repeats what the field says.
        form_errors = () if field_errors else tuple(checked["form"])
        schema = form.form_schema(self._form_model)
        hints = {f["id"]: form.field_hint(f, self._values, self.notation)
                 for f in form.iter_fields(schema) if f.get("hint")}
        return VoicingEditorState(
            selected=self._selected, model=self._form_model,
            values=copy.deepcopy(self._values), field_errors=field_errors,
            form_errors=form_errors, hints=hints, dirty=self._dirty, **common)

    def _problems(self, name: str, plan: VoicingPlan) -> Tuple[SettingsProblem, ...]:
        if name == self._selected and self._builtin is None:
            model, values = self._form_model, self._values
        else:
            data = self.model.get_voicings()[name]
            model = form.form_model(data.get("model", "piano"))
            values = form.values_from_voicing(model, data, self.notation)
        return tuple(SettingsProblem(name, p.field_id,
                                     problem_text(name, model, p, values, self.notation))
                     for p in plan.problems)

    # -- internals ---------------------------------------------------------------

    def _require_selected(self) -> None:
        if self._selected is None:
            raise RuntimeError("no voicing is selected in the voicings editor")

    def _require_editable(self) -> None:
        self._require_selected()
        if self._builtin is not None:
            raise RuntimeError(
                f"the voicing in the form is the built-in {self._selected!r}, "
                "which can't be edited (add_voicing_from copies it)")

    def _blanks(self) -> List[Dict[str, Any]]:
        """The ``blank`` presets: each model's defaults, in list order."""
        return [{"label": BLANK_PRESET_LABELS[model], "group": BLANK_GROUP,
                 "data": form.default_voicing(model)} for model in form.TREE_GROUPS]

    def _all_presets(self) -> List[Dict[str, Any]]:
        """Every preset :meth:`add_from` copies: the blanks, the built-ins
        and every working voicing (the selected one too)."""
        return self._blanks() + self.model.get_load_presets()

    def _builtin_data(self, group: str, label: str) -> Dict[str, Any]:
        for preset in self.model.get_load_presets():
            if preset["group"] == group and preset["label"] == label and group in form.MODELS:
                return copy.deepcopy(preset["data"])
        raise ValueError(f"no built-in voicing {label!r} of model {group!r}")

    def _load(self, data: Mapping[str, Any], keep_label: bool = False) -> None:
        self._form_model = form.form_model(data.get("model", "piano"))
        self._values = form.values_from_voicing(self._form_model, data, self.notation)
        if not keep_label:
            self._label = data.get("label")

    def _store(self, data: Dict[str, Any]) -> None:
        self.model.set_voicing_data(self._selected, data)
        self._dirty = True

    def _replace_values(self, values: Dict[str, Any]) -> None:
        self._values = values
        self._store(form.voicing_from_values(self._form_model, values, self._label))

    def _clear(self) -> None:
        self._recent = []
        self._selected = None
        self._builtin = None
        self._form_model = None
        self._values = {}
        self._label = None
        self._dirty = False
