"""The Voicings page of the Settings window.

A two-pane editor for the ``voicings`` registry: a grouped tree of voicings on
the left (with add/remove buttons), and a model-specific parameter form on the
right. All state lives in the injected
:class:`~viewmodels.settings_viewmodel.SettingsViewModel`; this widget renders
it and forwards edits.

The forms are drawn from the declarative schemas in
:mod:`settings_forms.voicing_form`, which also owns every label, help text,
default, parse rule and validation message, so Android renders the same
editor. This module only lays the schema out as Tk widgets.

The form stays deliberately forgiving while the user types: an unparseable
field keeps its raw string in the working copy rather than being rejected
mid-edit. Two error classes surface:

* **Parse errors** -- a value that stayed a raw string where a number, note
  name or list was expected, marked red on the offending control as you type.
* **Semantic / cross-field errors** (relaxed span < span, voice low >= high, a
  wrong ``max_spacing`` length, an out-of-range value, ...) are left to the
  spec: after each edit ``viewmodel.validate_voicing`` runs and its message is
  shown in a red banner at the top of the form.

The dialog's Save button is still the hard gate (it runs
``viewmodel.validate_all`` and jumps to the first bad voicing); the inline
feedback here is additive.
"""

import copy
import logging
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Any, Callable, Dict, List, Mapping, Optional

from settings_forms.voicing_form import (
    KIND_BOOL,
    KIND_CHOICE,
    KIND_FLOAT,
    KIND_INT,
    KIND_TEXT,
    MODELS,
    SECTION_GRID,
    SECTION_GROUPS,
    SECTION_RANGE_TABLE,
    SECTION_STACK,
    SECTION_TABLE,
    TREE_GROUPS,
    choice_label,
    choice_value,
    collected_field_errors,
    default_voicing,
    field_hint,
    form_model,
    form_schema,
    values_from_voicing,
    voicing_from_values,
    voicing_with_record_added,
    voicing_with_record_removed,
)
from settings_forms.voicing_texts import EDITOR_TEXTS, MODEL_LABELS, TOOLTIPS
from ui.base.tooltip import add_tooltip, ensure_field_error_styles, mark_field
from ui.menu_style import style_menu
from viewmodels.settings_viewmodel import SettingsViewModel

logger = logging.getLogger(__name__)

#: Model selector label -> model key.
_DISPLAY_MODEL = {display: model for model, display in MODEL_LABELS.items()}

#: Grey used for hints and section blurbs.
_HINT_COLOR = '#666666'
_HEADER_FONT = ('TkDefaultFont', 9, 'bold')

# Desktop-only spacing that differs between otherwise alike sections/fields.
_SECTION_PADY = {('fretboard', 'physical'): (6, 0), ('piano', 'physical'): (8, 0)}
_STACK_FIELD_PADY = {'max_spacing': (8, 2), 'allow_unisons': 2}
_STACK_TEXT_PADY = 2
_STACK_CHECK_PADY = (4, 2)


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
        # Form state, populated by _build_form from the model's schema.
        self._collect: Optional[Callable[[], dict]] = None
        # field-id -> reader of its current value; records field-id -> per-row readers.
        self._value_getters: Dict[str, Callable[[], Any]] = {}
        self._record_getters: Dict[str, List[Dict[str, Callable[[], Any]]]] = {}
        # field-id -> control, tooltip, and base tooltip text (for inline marks).
        self._field_widgets: Dict[str, tk.Widget] = {}
        self._field_tooltips: Dict[str, Any] = {}
        self._field_base_tips: Dict[str, str] = {}

        ensure_field_error_styles()

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
        add_btn = ttk.Button(buttons, text='+', width=3, command=self._on_add)
        add_btn.pack(side=tk.LEFT)
        remove_btn = ttk.Button(buttons, text='−', width=3, command=self._on_remove)
        remove_btn.pack(side=tk.LEFT, padx=(4, 0))
        add_tooltip(add_btn, TOOLTIPS['tree_add'])
        add_tooltip(remove_btn, TOOLTIPS['tree_remove'])

    def refresh(self) -> None:
        """Re-read the view model and rebuild the voicings tree."""
        for item in self._tree.get_children():
            self._tree.delete(item)

        for model in TREE_GROUPS:
            self._tree.insert('', 'end', iid=f'g:{model}', text=MODEL_LABELS[model],
                              open=True, tags=('group',))

        voicings = self._vm.get_voicings()
        for name in sorted(voicings):
            model = voicings[name].get('model', 'piano')
            group = model if model in TREE_GROUPS else 'piano'
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
        if not messagebox.askyesno(EDITOR_TEXTS['remove_confirm_title'],
                                   EDITOR_TEXTS['remove_confirm'].format(name=name),
                                   parent=self):
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
        right.rowconfigure(5, weight=1)
        self._right = right

        # Row 0: Load config menubutton (the Menubutton draws its own indicator,
        # so the text is plain 'Load config' with no manual arrow glyph).
        self._load_button = ttk.Menubutton(right, text=EDITOR_TEXTS['load_button'])
        self._load_menu = tk.Menu(self._load_button, tearoff=0)
        style_menu(self._load_menu)
        self._load_button['menu'] = self._load_menu
        self._load_button.grid(row=0, column=0, sticky='w', pady=(0, 6))
        add_tooltip(self._load_button, TOOLTIPS['load'])

        # Row 1: Name.
        name_frame = ttk.Frame(right)
        name_frame.grid(row=1, column=0, sticky='ew', pady=(0, 4))
        name_frame.columnconfigure(1, weight=1)
        self._tip_label(name_frame, EDITOR_TEXTS['name_label'], TOOLTIPS['name'],
                        row=0, column=0, sticky='w', padx=(0, 6))
        self._name_var = tk.StringVar()
        self._name_entry = ttk.Entry(name_frame, textvariable=self._name_var)
        self._name_entry.grid(row=0, column=1, sticky='ew')
        self._name_entry.bind('<FocusOut>', self._on_name_commit)
        self._name_entry.bind('<Return>', self._on_name_commit)
        add_tooltip(self._name_entry, TOOLTIPS['name'])

        # Row 2: Model.
        model_frame = ttk.Frame(right)
        model_frame.grid(row=2, column=0, sticky='ew', pady=(0, 4))
        model_label = ttk.Label(model_frame, text=EDITOR_TEXTS['model_label'])
        model_label.pack(side=tk.LEFT, padx=(0, 6))
        add_tooltip(model_label, TOOLTIPS['model'])
        self._model_var = tk.StringVar()
        self._model_combo = ttk.Combobox(
            model_frame, textvariable=self._model_var, state='readonly',
            values=[MODEL_LABELS[m] for m in MODELS],
            width=14,
        )
        self._model_combo.pack(side=tk.LEFT)
        self._model_combo.bind('<<ComboboxSelected>>', self._on_model_changed)
        add_tooltip(self._model_combo, TOOLTIPS['model'])

        ttk.Separator(right, orient='horizontal').grid(row=3, column=0, sticky='ew', pady=6)

        # Row 4: the semantic/cross-field error banner (hidden until needed).
        self._banner = tk.Label(
            right, anchor='w', justify=tk.LEFT, wraplength=420,
            background='#ffdddd', foreground='#8b0000', padx=8, pady=5,
        )
        self._banner.grid(row=4, column=0, sticky='ew', pady=(0, 6))
        self._banner.grid_remove()

        # Row 5: the model parameter form host (scrollable content per model).
        self._form_host = ttk.Frame(right)
        self._form_host.grid(row=5, column=0, sticky='nsew')
        self._form_host.columnconfigure(0, weight=1)
        self._form_host.rowconfigure(0, weight=1)

    def _rebuild_load_menu(self) -> None:
        self._load_menu.delete(0, 'end')
        previous_group = None
        for preset in self._vm.get_load_presets():
            if previous_group is not None and preset['group'] != previous_group:
                self._load_menu.add_separator()
            previous_group = preset['group']
            self._load_menu.add_command(
                label=preset['label'],
                command=lambda p=preset['data']: self._on_load_source(p),
            )

    def _on_load_source(self, params: dict) -> None:
        if self._current_name is None:
            return
        if not messagebox.askyesno(
            EDITOR_TEXTS['load_confirm_title'],
            EDITOR_TEXTS['load_confirm'],
            parent=self,
        ):
            return
        data = copy.deepcopy(params)
        self._current_label = data.get('label')
        self._vm.set_voicing_data(self._current_name, data)
        self._model_var.set(MODEL_LABELS.get(data.get('model', 'piano'), 'Piano'))
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
            messagebox.showerror(EDITOR_TEXTS['rename_error_title'], str(exc), parent=self)
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
            EDITOR_TEXTS['model_confirm_title'],
            EDITOR_TEXTS['model_confirm'],
            parent=self,
        ):
            self._model_var.set(MODEL_LABELS.get(current.get('model', 'piano'), 'Piano'))
            return
        data = default_voicing(new_model)
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
        self._model_var.set(MODEL_LABELS.get(data.get('model', 'piano'), 'Piano'))
        self._build_form(data)

    def _clear_editor(self) -> None:
        self._current_name = None
        self._current_label = None
        self._collect = None
        self._reset_fields()
        self._hide_banner()
        self._name_var.set('')
        self._model_var.set('')
        for child in self._form_host.winfo_children():
            child.destroy()
        placeholder = ttk.Label(
            self._form_host, text=EDITOR_TEXTS['placeholder'],
            foreground='#666666',
        )
        placeholder.grid(row=0, column=0, sticky='nw')
        self._set_editor_enabled(False)

    def _set_editor_enabled(self, enabled: bool) -> None:
        state = 'normal' if enabled else 'disabled'
        self._name_entry.configure(state=state)
        self._load_button.configure(state=state)
        self._model_combo.configure(state='readonly' if enabled else 'disabled')

    # -- Inline validation plumbing -----------------------------------------

    def _reset_fields(self) -> None:
        """Forget the previous form's registered controls (they were destroyed)."""
        self._field_widgets = {}
        self._field_tooltips = {}
        self._field_base_tips = {}

    def _register_field(self, field_id: str, widget: tk.Widget, tip_text: str) -> None:
        """Track a validatable control: tooltip it, and re-mark it live as it's typed."""
        self._field_base_tips[field_id] = tip_text
        self._field_tooltips[field_id] = add_tooltip(widget, tip_text)
        self._field_widgets[field_id] = widget
        widget.bind('<KeyRelease>',
                    lambda _e, fid=field_id: self._live_mark(fid), add='+')

    @staticmethod
    def _tip_label(parent, text: str, tip: str, **grid_kwargs) -> ttk.Label:
        """Create a form label, grid it, and give it its control's tooltip.

        Mirroring the tooltip onto the label (not just the input) means hovering
        the caption also reveals the help, which aids discoverability.
        """
        label = ttk.Label(parent, text=text)
        label.grid(**grid_kwargs)
        if tip:
            add_tooltip(label, tip)
        return label

    def _apply_field_mark(self, field_id: str, message: Optional[str]) -> None:
        """Red-mark (or clear) one control and fold ``message`` into its tooltip."""
        widget = self._field_widgets.get(field_id)
        if widget is None:
            return
        mark_field(widget, message is not None)
        tooltip = self._field_tooltips.get(field_id)
        if tooltip is not None:
            base = self._field_base_tips.get(field_id, '')
            tooltip.set_text(f"{base}\n\n⚠ {message}" if message else base)

    def _live_mark(self, field_id: str) -> None:
        """Lightweight per-keystroke re-mark of a single field (no vm/banner touch)."""
        if self._collect is None:
            return
        errors = collected_field_errors(self._collect())
        self._apply_field_mark(field_id, errors.get(field_id))

    def _refresh_validation(self) -> None:
        """Re-mark every field from its parse error and refresh the banner."""
        if self._current_name is None or self._collect is None:
            self._hide_banner()
            return
        errors = collected_field_errors(self._collect())
        for field_id in self._field_widgets:
            self._apply_field_mark(field_id, errors.get(field_id))
        message = self._vm.validate_voicing(self._current_name)
        if message:
            self._show_banner(message)
        else:
            self._hide_banner()

    def _show_banner(self, message: str) -> None:
        self._banner.configure(text=message)
        self._banner.grid()

    def _hide_banner(self) -> None:
        self._banner.grid_remove()

    # -- Scrollable form scaffolding ----------------------------------------

    def _new_scroll_area(self) -> ttk.Frame:
        """Clear the form host and return a fresh scrollable inner frame.

        The inner frame carries a right padding so its controls never sit
        underneath the vertical scrollbar.
        """
        for child in self._form_host.winfo_children():
            child.destroy()

        canvas = tk.Canvas(self._form_host, highlightthickness=0, borderwidth=0)
        canvas.grid(row=0, column=0, sticky='nsew')
        scrollbar = ttk.Scrollbar(self._form_host, orient='vertical', command=canvas.yview)
        scrollbar.grid(row=0, column=1, sticky='ns')
        canvas.configure(yscrollcommand=scrollbar.set)

        # padding right = 16 keeps content clear of the scrollbar gutter.
        inner = ttk.Frame(canvas, padding=(2, 2, 16, 2))
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
        self._reset_fields()
        self._loading_form = True
        try:
            model = form_model(data.get('model', 'piano'))
            values = values_from_voicing(model, data)
            inner = self._new_scroll_area()
            self._value_getters = {}
            self._record_getters = {}
            row = 0
            for section in form_schema(model)['sections']:
                row = self._render_section(inner, model, section, values, row)
            self._collect = lambda: voicing_from_values(model, self._form_values())
        finally:
            self._loading_form = False
        # Reflect the freshly-built form's current error state immediately.
        self._refresh_validation()

    def _form_values(self) -> Dict[str, Any]:
        """Read the form's current values (keyed by schema field id)."""
        values: Dict[str, Any] = {fid: get() for fid, get in self._value_getters.items()}
        for fid, rows in self._record_getters.items():
            values[fid] = [{cid: get() for cid, get in row.items()} for row in rows]
        return values

    def _commit_form(self, event=None) -> None:
        if self._loading_form or self._current_name is None or self._collect is None:
            return
        data = self._collect()
        if self._current_label:
            data['label'] = self._current_label
        self._vm.set_voicing_data(self._current_name, data)
        self._dirty = True
        self._refresh_validation()

    def _bind_commit(self, widget, *, is_entry=False) -> None:
        """Wire a widget so leaving/changing it commits the form."""
        if is_entry:
            widget.bind('<FocusOut>', self._commit_form)
            widget.bind('<Return>', self._commit_form)

    # -- Schema rendering ----------------------------------------------------

    def _render_section(self, inner: ttk.Frame, model: str, section: Mapping[str, Any],
                        values: Mapping[str, Any], row: int) -> int:
        """Lay one schema section out at ``row`` of ``inner``; return the next free row."""
        kind = section['kind']
        if kind == SECTION_STACK:
            return self._render_stack(inner, section, values, row)
        if kind == SECTION_TABLE:
            self._render_records_table(inner, section, values, row)
        elif kind == SECTION_RANGE_TABLE:
            self._render_range_table(inner, section, values, row)
        elif kind == SECTION_GROUPS:
            container = ttk.Frame(inner)
            container.grid(row=row, column=0, columnspan=2, sticky='ew', pady=(8, 0))
            container.columnconfigure(0, weight=1, uniform='nested')
            container.columnconfigure(1, weight=1, uniform='nested')
            for idx, group in enumerate(section['groups']):
                gr, gc = divmod(idx, 2)
                sub_frame = ttk.LabelFrame(container, text=group['title'], padding=6)
                sub_frame.grid(row=gr, column=gc, sticky='new', padx=(0, 8), pady=(0, 8))
                self._build_field_grid(sub_frame, group['fields'], values, colon=False)
        elif kind == SECTION_GRID and section.get('title'):
            frame = ttk.LabelFrame(inner, text=section['title'], padding=8)
            frame.grid(row=row, column=0, columnspan=2, sticky='ew', pady=(8, 0))
            if section.get('blurb'):
                ttk.Label(frame, text=section['blurb'], foreground=_HINT_COLOR,
                          wraplength=440, justify=tk.LEFT).grid(
                    row=0, column=0, columnspan=4, sticky='w', pady=(0, 6))
            grid_frame = ttk.Frame(frame)
            grid_frame.grid(row=1, column=0, columnspan=4, sticky='ew')
            self._build_field_grid(grid_frame, section['fields'], values, colon=False)
            for idx, group in enumerate(section.get('groups', [])):
                sub_frame = ttk.LabelFrame(frame, text=group['title'], padding=6)
                sub_frame.grid(row=2 + idx, column=0, columnspan=4, sticky='ew', pady=(8, 0))
                self._build_field_grid(sub_frame, group['fields'], values, colon=False)
        elif kind == SECTION_GRID:
            frame = ttk.Frame(inner)
            frame.grid(row=row, column=0, columnspan=2, sticky='ew',
                       pady=_SECTION_PADY.get((model, section['id']), (8, 0)))
            self._build_field_grid(frame, section['fields'], values, colon=True)
        else:
            logger.warning("Unknown voicing form section kind: %r", kind)
            return row
        return row + 1

    def _render_stack(self, inner: ttk.Frame, section: Mapping[str, Any],
                      values: Mapping[str, Any], row: int) -> int:
        """Fields one under another: a labelled entry (plus hint), or a checkbox."""
        for field in section['fields']:
            fid = field['id']
            if field['kind'] == KIND_BOOL:
                var = tk.BooleanVar(value=bool(values[fid]))
                check = ttk.Checkbutton(inner, text=field['label'], variable=var,
                                        command=self._commit_form)
                check.grid(row=row, column=0, columnspan=2, sticky='w',
                           pady=_STACK_FIELD_PADY.get(fid, _STACK_CHECK_PADY))
                add_tooltip(check, field['help'])
                self._value_getters[fid] = lambda v=var: bool(v.get())
                row += 1
                continue
            pady = _STACK_FIELD_PADY.get(fid, _STACK_TEXT_PADY)
            self._tip_label(inner, field['label'] + ':', field['help'],
                            row=row, column=0, sticky='w', pady=pady)
            var = tk.StringVar(value=values[fid])
            entry = ttk.Entry(inner, textvariable=var)
            entry.grid(row=row, column=1, sticky='ew', pady=pady)
            self._bind_commit(entry, is_entry=True)
            self._register_field(fid, entry, field['help'])
            self._value_getters[fid] = var.get
            row += 1
            hint = field_hint(field, values)
            if hint:
                ttk.Label(inner, text=hint, foreground=_HINT_COLOR).grid(
                    row=row, column=1, sticky='w')
                row += 1
        return row

    def _build_field_grid(self, frame: ttk.Frame, fields: List[Mapping[str, Any]],
                          values: Mapping[str, Any], *, colon: bool) -> None:
        """Lay fields out in a 2-column (label, input) grid.

        Number fields get a spinbox over the schema's ``min``/``max``/``step``;
        other text fields (the ensemble's movement weight) a plain entry.
        Columns 0/2 hold labels, 1/3 hold inputs.
        """
        for idx, field in enumerate(fields):
            fid = field['id']
            r, c = divmod(idx, 2)
            c *= 2
            label = field['label'] + (':' if colon else '')
            self._tip_label(frame, label, field['help'], row=r, column=c, sticky='w',
                            padx=(0, 6), pady=2)
            var = tk.StringVar(value=values[fid])
            if field['kind'] in (KIND_INT, KIND_FLOAT):
                widget = ttk.Spinbox(frame, from_=field['min'], to=field['max'],
                                     increment=field['step'], textvariable=var, width=8,
                                     command=self._commit_form)
            else:
                widget = ttk.Entry(frame, textvariable=var, width=field.get('width', 8))
            widget.grid(row=r, column=c + 1, sticky='w', padx=(0, 18), pady=2)
            self._bind_commit(widget, is_entry=True)
            self._register_field(fid, widget, field['help'])
            self._value_getters[fid] = var.get

    def _render_records_table(self, inner: ttk.Frame, section: Mapping[str, Any],
                              values: Mapping[str, Any], row: int) -> None:
        """A records field (the voices) as an editable table with add/remove buttons.

        All columns are fixed-width and left-aligned (no expanding middle
        column), so the last cell and the remove button stay snug against the
        name instead of being shoved to the right edge.
        """
        field = section['fields'][0]
        fid, columns = field['id'], field['columns']
        frame = ttk.LabelFrame(inner, text=section['title'], padding=8)
        frame.grid(row=row, column=0, columnspan=2, sticky='ew')

        for col, column in enumerate(columns):
            header = ttk.Label(frame, text=column['label'], font=_HEADER_FONT)
            header.grid(row=0, column=col, sticky='w', padx=(0, 6))
            add_tooltip(header, column['help'])
        ttk.Separator(frame, orient='horizontal').grid(
            row=1, column=0, columnspan=len(columns), sticky='ew', pady=(2, 4))

        records = values.get(fid) or []
        row_getters: List[Dict[str, Callable[[], Any]]] = []
        for i, record in enumerate(records):
            grid_row = i + 2
            getters: Dict[str, Callable[[], Any]] = {}
            for col, column in enumerate(columns):
                cid = column['id']
                if column['kind'] == KIND_CHOICE:
                    var = tk.StringVar(value=choice_label(column, record.get(cid)))
                    widget = ttk.Combobox(frame, textvariable=var, width=column['width'],
                                          state='readonly',
                                          values=[c['label'] for c in column['choices']])
                    widget.grid(row=grid_row, column=col, sticky='w', padx=(0, 6), pady=1)
                    widget.bind('<<ComboboxSelected>>', self._commit_form)
                    getters[cid] = lambda v=var, c=column: choice_value(c, v.get())
                else:
                    var = tk.StringVar(value=record.get(cid, ''))
                    widget = ttk.Entry(frame, textvariable=var, width=column['width'])
                    widget.grid(row=grid_row, column=col, sticky='w', padx=(0, 6), pady=1)
                    self._bind_commit(widget, is_entry=True)
                    getters[cid] = var.get
                if column['kind'] == KIND_TEXT:
                    add_tooltip(widget, column['help'])  # free text: never invalid
                else:
                    path = field['error_path'].format(index=i, column=cid)
                    self._register_field(path, widget, column['help'])

            remove_btn = ttk.Button(frame, text=field['remove_label'], width=3,
                                    command=lambda idx=i: self._remove_voice(idx))
            remove_btn.grid(row=grid_row, column=len(columns), sticky='w', padx=(2, 0), pady=1)
            add_tooltip(remove_btn, field['remove_help'])
            row_getters.append(getters)
        self._record_getters[fid] = row_getters

        add_btn = ttk.Button(frame, text=field['add_label'], command=self._add_voice)
        add_btn.grid(row=len(records) + 2, column=0, columnspan=2, sticky='w', pady=(6, 0))
        add_tooltip(add_btn, field['add_help'])

    def _render_range_table(self, inner: ttk.Frame, section: Mapping[str, Any],
                            values: Mapping[str, Any], row: int) -> None:
        """Labelled rows of (low, high) pitch entries (the piano's hands & range)."""
        frame = ttk.LabelFrame(inner, text=section['title'], padding=8)
        frame.grid(row=row, column=0, columnspan=2, sticky='ew')

        for col, htext in enumerate(section['columns'], start=1):
            header = ttk.Label(frame, text=htext, font=_HEADER_FONT)
            header.grid(row=0, column=col, sticky='w', padx=(0, 6))
        ttk.Separator(frame, orient='horizontal').grid(
            row=1, column=0, columnspan=len(section['columns']) + 1, sticky='ew', pady=(2, 4))

        for i, range_row in enumerate(section['rows']):
            grid_row = i + 2
            row_label = ttk.Label(frame, text=range_row['label'])
            row_label.grid(row=grid_row, column=0, sticky='w', padx=(0, 6), pady=1)
            add_tooltip(row_label, range_row['help'])
            last = len(range_row['fields']) - 1
            for j, field in enumerate(range_row['fields']):
                fid = field['id']
                var = tk.StringVar(value=values[fid])
                entry = ttk.Entry(frame, textvariable=var, width=field['width'])
                entry.grid(row=grid_row, column=j + 1, sticky='w',
                           padx=(0, 6) if j < last else 0, pady=1)
                self._bind_commit(entry, is_entry=True)
                self._register_field(fid, entry, field['help'])
                self._value_getters[fid] = var.get

    # -- Records (voices) ----------------------------------------------------

    def _add_voice(self) -> None:
        if self._current_name is None or self._collect is None:
            return
        data = voicing_with_record_added(self._collect())
        if self._current_label:
            data['label'] = self._current_label
        self._vm.set_voicing_data(self._current_name, data)
        self._dirty = True
        self._build_form(data)

    def _remove_voice(self, index: int) -> None:
        if self._current_name is None or self._collect is None:
            return
        data = voicing_with_record_removed(self._collect(), index)
        if self._current_label:
            data['label'] = self._current_label
        self._vm.set_voicing_data(self._current_name, data)
        self._dirty = True
        self._build_form(data)
