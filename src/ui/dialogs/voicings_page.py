"""The Voicings page of the Settings window.

A two-pane editor for the ``voicings`` registry: a grouped tree of voicings on
the left (with add/remove buttons), and a model-specific parameter form on the
right. All state lives in the injected
:class:`~viewmodels.settings_viewmodel.SettingsViewModel`; this widget only
renders it and forwards edits. Nothing here is validated inline -- the form is
deliberately forgiving while the user types (an unparseable field keeps its raw
string in the working copy), and the dialog's Save button is the gate that runs
``viewmodel.validate_all()``.
"""

import logging
import re
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Any, Callable, Dict, List, Optional

from models.ensemble_spec import (
    BUILTIN_ENSEMBLES,
    DEFAULT_WEIGHTS as ENSEMBLE_DEFAULT_WEIGHTS,
    _NESTED_WEIGHT_KEYS,
    midi_to_note_name,
    parse_note_name,
)
from models.fretboard_spec import (
    BUILTIN_FRETBOARDS,
    DEFAULT_WEIGHTS as FRETBOARD_DEFAULT_WEIGHTS,
)
from viewmodels.settings_viewmodel import SettingsViewModel

logger = logging.getLogger(__name__)


# Human-readable labels, taken verbatim from help/fretted.rst and
# help/ensembles.rst, keyed by the weight's config key.
FRETBOARD_WEIGHT_LABELS: Dict[str, str] = {
    'sounding_string_bonus': 'Sounding-string bonus',
    'open_string_bonus': 'Open-string bonus',
    'bass_note_bonus': 'Bass-note bonus',
    'slash_bass_bonus': 'Slash-bass bonus',
    'span_penalty': 'Stretch penalty',
    'position_penalty': 'Neck-position penalty',
    'fretted_finger_penalty': 'Finger-use penalty',
    'barre_penalty': 'Barre penalty',
    'interior_mute_penalty': 'Interior-mute penalty',
    'movement_penalty': 'Hand-movement penalty',
    'kept_finger_bonus': 'Held-finger bonus',
}

ENSEMBLE_WEIGHT_LABELS: Dict[str, str] = {
    'movement': 'Voice movement cost',
    'bass_movement': 'Bass movement cost',
    'leap_penalty': 'Large leap penalty',
    'octave_leap_penalty': 'Octave leap penalty',
    'tritone_leap_penalty': 'Tritone leap penalty',
    'common_tone_bonus': 'Common-tone bonus',
    'parallel_perfect_penalty': 'Parallel fifths/octaves penalty',
    'contrary_motion_bonus': 'Contrary motion bonus',
    'seventh_resolution_bonus': 'Seventh resolution bonus',
    'leading_tone_resolution_bonus': 'Leading-tone resolution bonus',
    'double_leading_tone_penalty': 'Doubled leading-tone penalty',
    'range_comfort_penalty': 'Range comfort margin',
    'unison_penalty': 'Unison penalty',
    'upper_spacing_penalty': 'Upper-voice spacing',
}

# Titles for the three nested-weight sub-frames.
NESTED_WEIGHT_TITLES: Dict[str, str] = {
    'doubling': 'Doubling preferences',
    'omit': 'Omission costs',
    'inversion': 'Inversion preferences',
}

# Human labels for the per-role sub-keys of the nested weights.
ROLE_LABELS: Dict[str, str] = {
    'root': 'Root',
    'third': 'Third',
    'fifth': 'Fifth',
    'seventh': 'Seventh',
    'color': 'Color',
    'extension': 'Extension',
    'first': 'First',
    'second': 'Second',
}

# Display names for the model combobox, and the mapping back to model keys.
_MODEL_DISPLAY = {'fretboard': 'Fretboard', 'ensemble': 'Ensemble', 'piano': 'Piano'}
_DISPLAY_MODEL = {display: model for model, display in _MODEL_DISPLAY.items()}
# Group node order in the tree.
_GROUP_ORDER = ('fretboard', 'piano', 'ensemble')
_GROUP_LABEL = {'fretboard': 'Fretboard', 'piano': 'Piano', 'ensemble': 'Ensemble'}


def _default_fretboard_data() -> dict:
    """Parameters for a brand-new fretboard voicing (standard guitar)."""
    return {'model': 'fretboard', 'tuning': [40, 45, 50, 55, 59, 64]}


def _default_ensemble_data() -> dict:
    """Parameters for a brand-new ensemble voicing (a minimal two-voice pair)."""
    return {
        'model': 'ensemble',
        'voices': [
            {'name': 'Voice 1', 'range': ['C4', 'C5']},
            {'name': 'Voice 2', 'range': ['C3', 'C4']},
        ],
    }


def _default_piano_data() -> dict:
    return {'model': 'piano'}


def _default_data_for_model(model: str) -> dict:
    if model == 'fretboard':
        return _default_fretboard_data()
    if model == 'ensemble':
        return _default_ensemble_data()
    return _default_piano_data()


def _pitch_to_text(value: Any) -> str:
    """Render a single pitch (MIDI int or already-a-string) as a note name."""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return midi_to_note_name(value)
    return str(value)


def _tuning_to_text(tuning: Any) -> str:
    """Render a tuning (list of pitches, or a raw in-progress string) for the entry."""
    if isinstance(tuning, str):
        return tuning
    if isinstance(tuning, (list, tuple)):
        return ' '.join(_pitch_to_text(p) for p in tuning)
    return ''


def _parse_pitch_token(token: str):
    """Parse one pitch token to a MIDI int, or return None if unparseable."""
    token = token.strip()
    if re.fullmatch(r'-?\d+', token):
        return int(token)
    return parse_note_name(token)


def _parse_pitch_list(text: str):
    """Parse a whitespace/comma separated pitch list; return a list or the raw text."""
    tokens = [t for t in re.split(r'[,\s]+', text.strip()) if t]
    if not tokens:
        return []
    parsed = []
    for token in tokens:
        midi = _parse_pitch_token(token)
        if midi is None:
            return text  # keep raw string for validation to pinpoint later
        parsed.append(midi)
    return parsed


def _parse_pitch_or_raw(text: str):
    """Parse a single pitch endpoint; return an int or the raw string."""
    midi = _parse_pitch_token(text)
    return midi if midi is not None else text


def _parse_int_or_raw(text: str):
    text = text.strip()
    try:
        return int(text)
    except ValueError:
        return text


def _parse_float_or_raw(text: str):
    text = text.strip()
    try:
        return float(text)
    except ValueError:
        return text


class VoicingsPage(ttk.Frame):
    """Left tree + right parameter-form editor for the voicings registry."""

    def __init__(self, parent, viewmodel: SettingsViewModel) -> None:
        """Build the page.

        Args:
            parent: The parent widget (the Settings dialog's page container).
            viewmodel: The shared settings view model to read from and edit.
        """
        super().__init__(parent, padding=10)

        self._vm = viewmodel
        self._current_name: Optional[str] = None
        self._current_label: Optional[str] = None
        self._dirty = False
        self._suppress_tree_event = False
        self._loading_form = False
        # Per-model form state, populated by _build_*_form.
        self._collect: Optional[Callable[[], dict]] = None

        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        self._build_left_pane()
        self._build_right_pane()

        self.refresh()
        self._clear_editor()

    # -- Left pane -----------------------------------------------------------

    def _build_left_pane(self) -> None:
        left = ttk.Frame(self)
        left.grid(row=0, column=0, sticky='ns', padx=(0, 10))
        left.rowconfigure(0, weight=1)

        self._tree = ttk.Treeview(left, show='tree', height=10, selectmode='browse')
        self._tree.grid(row=0, column=0, sticky='ns')
        scroll = ttk.Scrollbar(left, orient='vertical', command=self._tree.yview)
        scroll.grid(row=0, column=1, sticky='ns')
        self._tree.configure(yscrollcommand=scroll.set)
        self._tree.tag_configure('group', font=('TkDefaultFont', 9, 'bold'))
        self._tree.bind('<<TreeviewSelect>>', self._on_tree_select)

        buttons = ttk.Frame(left)
        buttons.grid(row=1, column=0, columnspan=2, sticky='w', pady=(6, 0))
        ttk.Button(buttons, text='+', width=3, command=self._on_add).pack(side=tk.LEFT)
        ttk.Button(buttons, text='−', width=3, command=self._on_remove).pack(
            side=tk.LEFT, padx=(4, 0)
        )

    def refresh(self) -> None:
        """Re-read the view model and rebuild the voicings tree."""
        for item in self._tree.get_children():
            self._tree.delete(item)

        for model in _GROUP_ORDER:
            self._tree.insert('', 'end', iid=f'g:{model}', text=_GROUP_LABEL[model],
                              open=True, tags=('group',))

        voicings = self._vm.get_voicings()
        for name in sorted(voicings):
            model = voicings[name].get('model', 'piano')
            group = model if model in _GROUP_ORDER else 'piano'
            self._tree.insert(f'g:{group}', 'end', iid=f'v:{name}', text=name)

    def _select_in_tree(self, name: str) -> None:
        """Highlight ``name`` in the tree without triggering a form reload."""
        iid = f'v:{name}'
        if not self._tree.exists(iid):
            return
        self._suppress_tree_event = True
        try:
            self._tree.selection_set(iid)
            self._tree.see(iid)
            self._tree.focus(iid)
        finally:
            self._suppress_tree_event = False

    def _on_tree_select(self, event=None) -> None:
        if self._suppress_tree_event:
            return
        selection = self._tree.selection()
        if not selection:
            return
        iid = selection[0]
        if iid.startswith('g:'):
            return  # selecting a group is a no-op
        name = iid[2:]
        if name in self._vm.get_voicings():
            self._load_editor(name)

    def _on_add(self) -> None:
        name = self._vm.add_voicing()
        self.refresh()
        self._load_editor(name)
        self._select_in_tree(name)

    def _on_remove(self) -> None:
        selection = self._tree.selection()
        if not selection or selection[0].startswith('g:'):
            return
        name = selection[0][2:]
        if not messagebox.askyesno('Remove Voicing', f"Remove voicing '{name}'?", parent=self):
            return
        self._vm.remove_voicing(name)
        if self._current_name == name:
            self._current_name = None
        self.refresh()
        if self._current_name is None:
            self._clear_editor()

    # -- Right pane ----------------------------------------------------------

    def _build_right_pane(self) -> None:
        right = ttk.Frame(self)
        right.grid(row=0, column=1, sticky='nsew')
        right.columnconfigure(0, weight=1)
        right.rowconfigure(4, weight=1)
        self._right = right

        # Row 1: Load config menubutton.
        self._load_button = ttk.Menubutton(right, text='Load config ▾')
        self._load_menu = tk.Menu(self._load_button, tearoff=0)
        self._load_button['menu'] = self._load_menu
        self._load_button.grid(row=0, column=0, sticky='w', pady=(0, 6))

        # Row 2: Name.
        name_frame = ttk.Frame(right)
        name_frame.grid(row=1, column=0, sticky='ew', pady=(0, 4))
        ttk.Label(name_frame, text='Name:').pack(side=tk.LEFT, padx=(0, 6))
        self._name_var = tk.StringVar()
        self._name_entry = ttk.Entry(name_frame, textvariable=self._name_var)
        self._name_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._name_entry.bind('<FocusOut>', self._on_name_commit)
        self._name_entry.bind('<Return>', self._on_name_commit)

        # Row 3: Model.
        model_frame = ttk.Frame(right)
        model_frame.grid(row=2, column=0, sticky='ew', pady=(0, 4))
        ttk.Label(model_frame, text='Model:').pack(side=tk.LEFT, padx=(0, 6))
        self._model_var = tk.StringVar()
        self._model_combo = ttk.Combobox(
            model_frame, textvariable=self._model_var, state='readonly',
            values=[_MODEL_DISPLAY[m] for m in ('fretboard', 'ensemble', 'piano')],
            width=14,
        )
        self._model_combo.pack(side=tk.LEFT)
        self._model_combo.bind('<<ComboboxSelected>>', self._on_model_changed)

        ttk.Separator(right, orient='horizontal').grid(row=3, column=0, sticky='ew', pady=6)

        # Row 4: the model parameter form host (scrollable content added per model).
        self._form_host = ttk.Frame(right)
        self._form_host.grid(row=4, column=0, sticky='nsew')
        self._form_host.columnconfigure(0, weight=1)
        self._form_host.rowconfigure(0, weight=1)

    def _rebuild_load_menu(self) -> None:
        self._load_menu.delete(0, 'end')
        sources = self._vm.get_load_sources()
        n_fret = len(BUILTIN_FRETBOARDS)
        n_ens = len(BUILTIN_ENSEMBLES)
        groups = [
            sources[0:n_fret],
            sources[n_fret:n_fret + n_ens],
            sources[n_fret + n_ens:n_fret + n_ens + 1],
            sources[n_fret + n_ens + 1:],
        ]
        first = True
        for group in groups:
            if not group:
                continue
            if not first:
                self._load_menu.add_separator()
            first = False
            for label, params in group:
                self._load_menu.add_command(
                    label=label,
                    command=lambda p=params: self._on_load_source(p),
                )

    def _on_load_source(self, params: dict) -> None:
        if self._current_name is None:
            return
        import copy
        data = copy.deepcopy(params)
        self._current_label = data.get('label')
        self._vm.set_voicing_data(self._current_name, data)
        self._model_var.set(_MODEL_DISPLAY.get(data.get('model', 'piano'), 'Piano'))
        self._build_form(data)
        self._dirty = True

    def _on_name_commit(self, event=None) -> None:
        if self._current_name is None:
            return
        new = self._name_var.get().strip()
        if new == self._current_name:
            return
        try:
            self._vm.rename_voicing(self._current_name, new)
        except ValueError as exc:
            messagebox.showerror('Rename Voicing', str(exc), parent=self)
            self._name_var.set(self._current_name)
            return
        self._current_name = new
        self.refresh()
        self._select_in_tree(new)

    def _on_model_changed(self, event=None) -> None:
        if self._current_name is None:
            return
        new_model = _DISPLAY_MODEL.get(self._model_var.get())
        current = self._vm.get_voicings().get(self._current_name, {})
        if new_model == current.get('model'):
            return
        if self._dirty and not messagebox.askyesno(
            'Change Model',
            'Switching model will replace the current parameters with defaults. Continue?',
            parent=self,
        ):
            self._model_var.set(_MODEL_DISPLAY.get(current.get('model', 'piano'), 'Piano'))
            return
        data = _default_data_for_model(new_model)
        self._current_label = None
        self._vm.set_voicing_data(self._current_name, data)
        self._build_form(data)
        self._dirty = True

    # -- Editor load / clear -------------------------------------------------

    def select_voicing(self, name: str) -> None:
        """Select ``name`` in the tree and load it into the editor."""
        if name in self._vm.get_voicings():
            self._load_editor(name)
            self._select_in_tree(name)

    def _load_editor(self, name: str) -> None:
        self._current_name = name
        data = self._vm.get_voicings()[name]
        self._current_label = data.get('label')
        self._dirty = False

        self._set_editor_enabled(True)
        self._rebuild_load_menu()
        self._name_var.set(name)
        self._model_var.set(_MODEL_DISPLAY.get(data.get('model', 'piano'), 'Piano'))
        self._build_form(data)

    def _clear_editor(self) -> None:
        self._current_name = None
        self._current_label = None
        self._collect = None
        self._name_var.set('')
        self._model_var.set('')
        for child in self._form_host.winfo_children():
            child.destroy()
        placeholder = ttk.Label(
            self._form_host, text='Select a voicing to edit, or add one with "+".',
            foreground='#666666',
        )
        placeholder.grid(row=0, column=0, sticky='nw')
        self._set_editor_enabled(False)

    def _set_editor_enabled(self, enabled: bool) -> None:
        state = 'normal' if enabled else 'disabled'
        self._name_entry.configure(state=state)
        self._load_button.configure(state=state)
        self._model_combo.configure(state='readonly' if enabled else 'disabled')

    # -- Scrollable form scaffolding ----------------------------------------

    def _new_scroll_area(self) -> ttk.Frame:
        """Clear the form host and return a fresh scrollable inner frame."""
        for child in self._form_host.winfo_children():
            child.destroy()

        canvas = tk.Canvas(self._form_host, highlightthickness=0, borderwidth=0)
        canvas.grid(row=0, column=0, sticky='nsew')
        scrollbar = ttk.Scrollbar(self._form_host, orient='vertical', command=canvas.yview)
        scrollbar.grid(row=0, column=1, sticky='ns')
        canvas.configure(yscrollcommand=scrollbar.set)

        inner = ttk.Frame(canvas)
        window = canvas.create_window((0, 0), window=inner, anchor='nw')

        def _on_configure(event):
            canvas.configure(scrollregion=canvas.bbox('all'))
        inner.bind('<Configure>', _on_configure)

        def _on_canvas_configure(event):
            canvas.itemconfigure(window, width=event.width)
        canvas.bind('<Configure>', _on_canvas_configure)

        def _on_mousewheel(event):
            if event.num == 4:
                canvas.yview_scroll(-1, 'units')
            elif event.num == 5:
                canvas.yview_scroll(1, 'units')
            else:
                canvas.yview_scroll(-1 if event.delta > 0 else 1, 'units')

        for widget in (canvas, inner):
            widget.bind('<MouseWheel>', _on_mousewheel)
            widget.bind('<Button-4>', _on_mousewheel)
            widget.bind('<Button-5>', _on_mousewheel)

        inner.columnconfigure(1, weight=1)
        return inner

    def _build_form(self, data: dict) -> None:
        self._loading_form = True
        try:
            model = data.get('model', 'piano')
            if model == 'fretboard':
                self._build_fretboard_form(data)
            elif model == 'ensemble':
                self._build_ensemble_form(data)
            else:
                self._build_piano_form(data)
        finally:
            self._loading_form = False

    def _commit_form(self, event=None) -> None:
        if self._loading_form or self._current_name is None or self._collect is None:
            return
        data = self._collect()
        if self._current_label:
            data['label'] = self._current_label
        self._vm.set_voicing_data(self._current_name, data)
        self._dirty = True

    def _bind_commit(self, widget, *, is_entry=False) -> None:
        """Wire a widget so leaving/changing it commits the form."""
        if is_entry:
            widget.bind('<FocusOut>', self._commit_form)
            widget.bind('<Return>', self._commit_form)

    # -- Fretboard form ------------------------------------------------------

    def _build_fretboard_form(self, data: dict) -> None:
        inner = self._new_scroll_area()
        weights = dict(FRETBOARD_DEFAULT_WEIGHTS)
        weights.update(data.get('weights', {}) or {})
        row = 0

        ttk.Label(inner, text='Strings:').grid(row=row, column=0, sticky='w', pady=2)
        strings_var = tk.StringVar(value=_tuning_to_text(data.get('tuning', [])))
        strings_entry = ttk.Entry(inner, textvariable=strings_var)
        strings_entry.grid(row=row, column=1, sticky='ew', pady=2)
        self._bind_commit(strings_entry, is_entry=True)
        row += 1
        ttk.Label(inner, text='(note names or MIDI numbers, e.g. E2 A2 D3 G3 B3 E4)',
                  foreground='#666666').grid(row=row, column=1, sticky='w')
        row += 1

        spin_vars: Dict[str, tk.StringVar] = {}
        for key, text, lo, hi, default in (
            ('max_fret', 'Max fret:', 5, 24, 12),
            ('fingers', 'Fingers:', 1, 5, 4),
            ('max_span', 'Max span:', 1, 8, 4),
            ('relaxed_span', 'Relaxed span:', 1, 10, 5),
        ):
            ttk.Label(inner, text=text).grid(row=row, column=0, sticky='w', pady=2)
            var = tk.StringVar(value=str(data.get(key, default)))
            spin = ttk.Spinbox(inner, from_=lo, to=hi, textvariable=var, width=8,
                               command=self._commit_form)
            spin.grid(row=row, column=1, sticky='w', pady=2)
            self._bind_commit(spin, is_entry=True)
            spin_vars[key] = var
            row += 1

        barre_var = tk.BooleanVar(value=bool(data.get('allow_barres', True)))
        ttk.Checkbutton(inner, text='Allow barre chords', variable=barre_var,
                        command=self._commit_form).grid(
            row=row, column=1, sticky='w', pady=2)
        row += 1

        weights_frame = ttk.LabelFrame(inner, text='Weights', padding=6)
        weights_frame.grid(row=row, column=0, columnspan=2, sticky='ew', pady=(8, 0))
        weights_frame.columnconfigure(1, weight=1)
        weight_vars: Dict[str, tk.StringVar] = {}
        for wrow, key in enumerate(FRETBOARD_DEFAULT_WEIGHTS):
            ttk.Label(weights_frame, text=FRETBOARD_WEIGHT_LABELS.get(key, key)).grid(
                row=wrow, column=0, sticky='w', pady=1)
            var = tk.StringVar(value=str(weights.get(key)))
            spin = ttk.Spinbox(weights_frame, from_=0.0, to=100.0, increment=0.1,
                               textvariable=var, width=8, command=self._commit_form)
            spin.grid(row=wrow, column=1, sticky='w', pady=1)
            self._bind_commit(spin, is_entry=True)
            weight_vars[key] = var

        def collect() -> dict:
            out: dict = {'model': 'fretboard'}
            out['tuning'] = _parse_pitch_list(strings_var.get())
            for key, var in spin_vars.items():
                out[key] = _parse_int_or_raw(var.get())
            out['allow_barres'] = bool(barre_var.get())
            out['weights'] = {k: _parse_float_or_raw(v.get()) for k, v in weight_vars.items()}
            return out

        self._collect = collect

    # -- Ensemble form -------------------------------------------------------

    def _build_ensemble_form(self, data: dict) -> None:
        inner = self._new_scroll_area()
        voices = list(data.get('voices', []) or [])
        row = 0

        voices_frame = ttk.LabelFrame(inner, text='Voices', padding=6)
        voices_frame.grid(row=row, column=0, columnspan=2, sticky='ew')
        voices_frame.columnconfigure(1, weight=1)
        row += 1

        ttk.Label(voices_frame, text='Name').grid(row=0, column=0, sticky='w')
        ttk.Label(voices_frame, text='Low').grid(row=0, column=1, sticky='w')
        ttk.Label(voices_frame, text='High').grid(row=0, column=2, sticky='w')

        voice_rows: List[Dict[str, tk.StringVar]] = []
        for i, voice in enumerate(voices):
            vrange = voice.get('range', [None, None]) if isinstance(voice, dict) else [None, None]
            low = vrange[0] if len(vrange) > 0 else None
            high = vrange[1] if len(vrange) > 1 else None
            name_var = tk.StringVar(value=str(voice.get('name', '')) if isinstance(voice, dict) else '')
            low_var = tk.StringVar(value=_pitch_to_text(low) if low is not None else '')
            high_var = tk.StringVar(value=_pitch_to_text(high) if high is not None else '')
            name_e = ttk.Entry(voices_frame, textvariable=name_var, width=12)
            name_e.grid(row=i + 1, column=0, sticky='w', pady=1)
            low_e = ttk.Entry(voices_frame, textvariable=low_var, width=8)
            low_e.grid(row=i + 1, column=1, sticky='w', pady=1, padx=2)
            high_e = ttk.Entry(voices_frame, textvariable=high_var, width=8)
            high_e.grid(row=i + 1, column=2, sticky='w', pady=1, padx=2)
            for entry in (name_e, low_e, high_e):
                self._bind_commit(entry, is_entry=True)
            ttk.Button(voices_frame, text='✕', width=3,
                       command=lambda idx=i: self._remove_voice(idx)).grid(
                row=i + 1, column=3, padx=2)
            voice_rows.append({'name': name_var, 'low': low_var, 'high': high_var})

        ttk.Button(voices_frame, text='Add voice', command=self._add_voice).grid(
            row=len(voices) + 1, column=0, sticky='w', pady=(4, 0))

        ttk.Label(inner, text='Max spacing:').grid(row=row, column=0, sticky='w', pady=(8, 2))
        spacing_val = data.get('max_spacing')
        spacing_text = (
            ', '.join(str(s) for s in spacing_val)
            if isinstance(spacing_val, (list, tuple)) else (spacing_val or '')
        )
        spacing_var = tk.StringVar(value=str(spacing_text))
        spacing_entry = ttk.Entry(inner, textvariable=spacing_var)
        spacing_entry.grid(row=row, column=1, sticky='ew', pady=(8, 2))
        self._bind_commit(spacing_entry, is_entry=True)
        row += 1
        ttk.Label(inner, text=f'(comma-separated, {max(len(voices) - 1, 0)} values expected)',
                  foreground='#666666').grid(row=row, column=1, sticky='w')
        row += 1

        unison_var = tk.BooleanVar(value=bool(data.get('allow_unisons', True)))
        ttk.Checkbutton(inner, text='Allow unisons', variable=unison_var,
                        command=self._commit_form).grid(row=row, column=1, sticky='w', pady=2)
        row += 1

        weights = data.get('weights', {}) or {}
        weight_vars: Dict[str, tk.StringVar] = {}
        movement_var = tk.StringVar()
        nested_vars: Dict[str, Dict[str, tk.StringVar]] = {}

        weights_frame = ttk.LabelFrame(inner, text='Weights', padding=6)
        weights_frame.grid(row=row, column=0, columnspan=2, sticky='ew', pady=(8, 0))
        weights_frame.columnconfigure(1, weight=1)
        wrow = 0
        for key, default in ENSEMBLE_DEFAULT_WEIGHTS.items():
            if key == 'movement':
                ttk.Label(weights_frame, text=ENSEMBLE_WEIGHT_LABELS[key]).grid(
                    row=wrow, column=0, sticky='w', pady=1)
                mv = weights.get('movement', default)
                movement_var.set(
                    ', '.join(str(x) for x in mv) if isinstance(mv, (list, tuple)) else str(mv)
                )
                mv_entry = ttk.Entry(weights_frame, textvariable=movement_var, width=14)
                mv_entry.grid(row=wrow, column=1, sticky='w', pady=1)
                self._bind_commit(mv_entry, is_entry=True)
                wrow += 1
            elif key in _NESTED_WEIGHT_KEYS:
                continue
            else:
                ttk.Label(weights_frame, text=ENSEMBLE_WEIGHT_LABELS.get(key, key)).grid(
                    row=wrow, column=0, sticky='w', pady=1)
                var = tk.StringVar(value=str(weights.get(key, default)))
                spin = ttk.Spinbox(weights_frame, from_=-100.0, to=100.0, increment=0.1,
                                   textvariable=var, width=8, command=self._commit_form)
                spin.grid(row=wrow, column=1, sticky='w', pady=1)
                self._bind_commit(spin, is_entry=True)
                weight_vars[key] = var
                wrow += 1

        for nested_key in _NESTED_WEIGHT_KEYS:
            sub_default = ENSEMBLE_DEFAULT_WEIGHTS[nested_key]
            sub_current = weights.get(nested_key, {}) or {}
            sub_frame = ttk.LabelFrame(inner, text=NESTED_WEIGHT_TITLES[nested_key], padding=6)
            sub_frame.grid(row=row + 1 + list(_NESTED_WEIGHT_KEYS).index(nested_key),
                           column=0, columnspan=2, sticky='ew', pady=(8, 0))
            sub_frame.columnconfigure(1, weight=1)
            nested_vars[nested_key] = {}
            for srow, (subkey, subdefault) in enumerate(sub_default.items()):
                ttk.Label(sub_frame, text=ROLE_LABELS.get(subkey, subkey)).grid(
                    row=srow, column=0, sticky='w', pady=1)
                var = tk.StringVar(value=str(sub_current.get(subkey, subdefault)))
                spin = ttk.Spinbox(sub_frame, from_=-100.0, to=100.0, increment=0.1,
                                   textvariable=var, width=8, command=self._commit_form)
                spin.grid(row=srow, column=1, sticky='w', pady=1)
                self._bind_commit(spin, is_entry=True)
                nested_vars[nested_key][subkey] = var

        def collect() -> dict:
            out: dict = {'model': 'ensemble'}
            out_voices = []
            for vr in voice_rows:
                out_voices.append({
                    'name': vr['name'].get().strip(),
                    'range': [_parse_pitch_or_raw(vr['low'].get()),
                              _parse_pitch_or_raw(vr['high'].get())],
                })
            out['voices'] = out_voices
            spacing_raw = spacing_var.get().strip()
            if spacing_raw:
                out['max_spacing'] = _parse_int_list_or_raw(spacing_raw)
            out['allow_unisons'] = bool(unison_var.get())
            weights_out: dict = {k: _parse_float_or_raw(v.get()) for k, v in weight_vars.items()}
            weights_out['movement'] = _parse_scalar_or_list(movement_var.get())
            for nested_key, sub in nested_vars.items():
                weights_out[nested_key] = {sk: _parse_float_or_raw(sv.get())
                                           for sk, sv in sub.items()}
            out['weights'] = weights_out
            return out

        self._collect = collect

    def _add_voice(self) -> None:
        if self._current_name is None or self._collect is None:
            return
        data = self._collect()
        data.setdefault('voices', [])
        data['voices'].append({'name': f"Voice {len(data['voices']) + 1}", 'range': ['C3', 'C4']})
        if self._current_label:
            data['label'] = self._current_label
        self._vm.set_voicing_data(self._current_name, data)
        self._dirty = True
        self._build_form(data)

    def _remove_voice(self, index: int) -> None:
        if self._current_name is None or self._collect is None:
            return
        data = self._collect()
        voices = data.get('voices', [])
        if 0 <= index < len(voices):
            del voices[index]
        if self._current_label:
            data['label'] = self._current_label
        self._vm.set_voicing_data(self._current_name, data)
        self._dirty = True
        self._build_form(data)

    # -- Piano form ----------------------------------------------------------

    def _build_piano_form(self, data: dict) -> None:
        inner = self._new_scroll_area()
        ttk.Label(
            inner,
            text='The piano model has no configurable parameters yet.',
            foreground='#666666', wraplength=360, justify=tk.LEFT,
        ).grid(row=0, column=0, columnspan=2, sticky='nw')
        self._collect = lambda: {'model': 'piano'}


def _parse_int_list_or_raw(text: str):
    """Parse a comma-separated int list; return a list or the raw string."""
    tokens = [t.strip() for t in text.split(',') if t.strip()]
    parsed = []
    for token in tokens:
        try:
            parsed.append(int(token))
        except ValueError:
            return text
    return parsed


def _parse_scalar_or_list(text: str):
    """Parse ``movement`` as a single float or a comma-separated list of floats."""
    text = text.strip()
    if ',' in text:
        tokens = [t.strip() for t in text.split(',') if t.strip()]
        parsed = []
        for token in tokens:
            try:
                parsed.append(float(token))
            except ValueError:
                return text
        return parsed
    try:
        return float(text)
    except ValueError:
        return text
