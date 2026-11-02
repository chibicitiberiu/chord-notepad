"""Saving a voicing field by field while some of its fields are wrong (Android).

Android's Settings screen saves as you type, so a voicing with a mistake in
one field still has its other fields saved: :func:`plan_voicing` replaces
each field that doesn't parse with the value on disk (for a voicing that
isn't on disk yet, the model's default) and keeps the result if it
validates. A rule that spans fields (a relaxed span below the normal span,
too few strings, a voice whose low note is above its high note) blames the
fields that changed and whose old value makes the voicing valid again, so
they count as wrong too and keep their old value on disk.

Each problem is worded for a list the user reads before leaving Settings
(:func:`problem_text`): where it is, what was typed, what's wrong, and the
field's syntax or range, all from the form schema.
"""

import copy
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from settings_forms import voicing_form as form

#: The records field and its cell ids (``voice:<row>:<column>``).
_RECORDS = 'voices'
_CELL = re.compile(r'^voice:(\d+):(\w+)$')

#: A spec message starts with the voicing ("Fretboard 'Bass': ..."); the
#: problem list names the voicing itself.
_SPEC_PREFIX = re.compile(r"^(Fretboard|Ensemble|Piano) '.*?'[:,] *")


@dataclass(frozen=True)
class FieldProblem:
    """One thing wrong with a voicing.

    Attributes:
        field_id: The field (``voice:<row>:<column>`` for a records cell), or
            None for the voicing as a whole (its saved version is broken too).
        typed: What the field holds now.
        message: What's wrong, as a sentence.
    """

    field_id: Optional[str]
    typed: str
    message: str


@dataclass(frozen=True)
class VoicingPlan:
    """What an autosave writes for one voicing.

    Attributes:
        data: The voicing to write: the form's values with every wrong field
            at its old value. None when even that doesn't validate (keep the
            version on disk).
        problems: The wrong fields, in form order.
    """

    data: Optional[Dict[str, Any]]
    problems: Tuple[FieldProblem, ...]


# -- field values by id ------------------------------------------------------------


def _get(values: Mapping[str, Any], field_id: str) -> Any:
    cell = _CELL.match(field_id)
    if cell:
        rows = values.get(_RECORDS) or []
        row = int(cell.group(1))
        return rows[row].get(cell.group(2)) if row < len(rows) else None
    return values.get(field_id)


def _put(values: Dict[str, Any], field_id: str, value: Any) -> None:
    cell = _CELL.match(field_id)
    if cell:
        rows = values.get(_RECORDS) or []
        row = int(cell.group(1))
        if row < len(rows):
            rows[row][cell.group(2)] = value
        return
    values[field_id] = value


def _old_value(model: str, base: Mapping[str, Any], field_id: str) -> Any:
    """The value ``field_id`` had on disk (a new row's cell: the new row's default)."""
    cell = _CELL.match(field_id)
    if not cell:
        return base.get(field_id)
    rows = base.get(_RECORDS) or []
    row, column = int(cell.group(1)), cell.group(2)
    if row < len(rows):
        value = rows[row].get(column)
    else:
        new_item = _records_field(model).get('new_item', {})
        value = new_item.get(column)
        value = value.replace('{n}', str(row + 1)) if isinstance(value, str) else value
    if column == form.GAP_COLUMN and not _text(value).strip():
        # The bottom voice's gap isn't saved; one that moved up or got a
        # voice below falls back to the gap a new one gets.
        return str(form.DEFAULT_GAP)
    return value


def _records_field(model: str) -> Dict[str, Any]:
    for field in form.iter_fields(form.form_schema(model)):
        if field['kind'] == form.KIND_RECORDS:
            return field
    return {}


def _field_ids(model: str, values: Mapping[str, Any]) -> List[str]:
    """Every field id of the form in display order, a records field cell by cell."""
    ids: List[str] = []
    for field in form.iter_fields(form.form_schema(model)):
        if field['kind'] == form.KIND_RECORDS:
            for row in range(len(values.get(field['id']) or [])):
                ids.extend(f'voice:{row}:{column["id"]}' for column in field['columns'])
        else:
            ids.append(field['id'])
    return ids


def _text(value: Any) -> str:
    return '' if value is None else str(value)


# -- the plan -------------------------------------------------------------------------


def plan_voicing(name: str, model: str, values: Mapping[str, Any], label: Optional[str],
                 saved: Optional[Mapping[str, Any]], recent: Sequence[str] = (),
                 notation: str = 'american') -> VoicingPlan:
    """Work out what to save of one voicing whose form holds ``values``.

    Args:
        name: The voicing's name (the spec's messages carry it).
        model: The form's model.
        values: The form values, keyed by field id.
        label: The voicing's display label, if it has one.
        saved: The voicing as it is on disk, or None if it isn't there yet
            (a different model counts as not there: the defaults stand in).
        recent: Top-level field ids, most recently edited last; a rule that
            spans fields blames these first.
        notation: The notation the form shows note names in (old values
            put back into it are spelled the same way).

    Returns:
        The voicing to write and what's wrong with the form.
    """
    model = form.form_model(model)
    if saved is None or form.form_model(saved.get('model')) != model:
        saved = form.default_voicing(model)
    base = form.values_from_voicing(model, saved, notation)
    ids = _field_ids(model, values)
    order = {field_id: i for i, field_id in enumerate(ids)}

    merged = copy.deepcopy(dict(values))
    parse_errors = form.field_errors(model, values)
    problems: Dict[Optional[str], FieldProblem] = {}
    for field_id in parse_errors:
        typed = _text(_get(values, field_id))
        problems[field_id] = FieldProblem(field_id, typed,
                                          _parse_message(_field_of(model, field_id), typed))
        _put(merged, field_id, _old_value(model, base, field_id))

    def error_of(candidate: Mapping[str, Any]) -> Optional[str]:
        return form.voicing_error(name, form.voicing_from_values(model, candidate, label))

    error = error_of(merged)
    if error is None:
        return VoicingPlan(form.voicing_from_values(model, merged, label), _ordered(problems, order))

    # A rule across fields: revert changed fields, the most recent first,
    # until it holds, then give back the ones it didn't need.
    def rank(field_id: str) -> Tuple[int, int]:
        top = _RECORDS if _CELL.match(field_id) else field_id
        if top in recent:
            return (0, -max(i for i, f in enumerate(recent) if f == top))
        return (1, order.get(field_id, 0))

    changed = sorted((f for f in ids if f not in parse_errors
                      and _get(merged, f) != _old_value(model, base, f)), key=rank)
    trial = copy.deepcopy(merged)
    blamed: List[str] = []
    for field_id in changed:
        _put(trial, field_id, _old_value(model, base, field_id))
        blamed.append(field_id)
        if error_of(trial) is None:
            break
    else:
        problems[None] = FieldProblem(None, '', _sentence(error, model))
        return VoicingPlan(None, _ordered(problems, order))
    for field_id in list(blamed):
        candidate = copy.deepcopy(trial)
        _put(candidate, field_id, _get(merged, field_id))
        if error_of(candidate) is None:
            trial = candidate
            blamed.remove(field_id)
    for field_id in blamed:
        # Part of the first rule that fails (putting it back alone changes
        # the error): that rule's message. Otherwise its own rule's.
        alone = copy.deepcopy(merged)
        _put(alone, field_id, _old_value(model, base, field_id))
        if error_of(alone) != error:
            message = error
        else:
            candidate = copy.deepcopy(trial)
            _put(candidate, field_id, _get(merged, field_id))
            message = error_of(candidate) or error
        problems[field_id] = FieldProblem(field_id, _text(_get(values, field_id)),
                                          _sentence(message, model))
    return VoicingPlan(form.voicing_from_values(model, trial, label), _ordered(problems, order))


def _ordered(problems: Mapping[Optional[str], FieldProblem],
             order: Mapping[str, int]) -> Tuple[FieldProblem, ...]:
    return tuple(sorted(problems.values(),
                        key=lambda p: -1 if p.field_id is None else order.get(p.field_id, 0)))


# -- the words ---------------------------------------------------------------------------


def _fields_by_id(model: str) -> Dict[str, Dict[str, Any]]:
    """Each field's schema by id; a records cell's column under ``voice:*:<column>``."""
    out: Dict[str, Dict[str, Any]] = {}
    for field in form.iter_fields(form.form_schema(model)):
        if field['kind'] == form.KIND_RECORDS:
            for column in field['columns']:
                out[f'voice:*:{column["id"]}'] = column
        else:
            out[field['id']] = field
    return out


def _field_of(model: str, field_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if field_id is None:
        return None
    cell = _CELL.match(field_id)
    return _fields_by_id(model).get(f'voice:*:{cell.group(2)}' if cell else field_id)


def field_labels(model: str) -> Dict[str, str]:
    """Each field's name in a problem list: its label, with the row of a
    piano range or the group of a nested weight in front."""
    labels: Dict[str, str] = {}

    def walk(section: Mapping[str, Any], prefix: str = '') -> None:
        for field in section.get('fields', []):
            labels[field['id']] = prefix + field['label']
        for row in section.get('rows', []):
            labels[row['id']] = row['label']
            for field in row['fields']:
                labels[field['id']] = f"{row['label']} {field['label'].lower()}"
        for group in section.get('groups', []):
            walk(group, f"{group.get('title') or ''}, " if group.get('title') else '')

    for section in form.form_schema(model)['sections']:
        walk(section)
    return labels


def _label_of(model: str, field_id: str) -> str:
    cell = _CELL.match(field_id)
    if cell:
        column = _field_of(model, field_id)
        return f"Voice {int(cell.group(1)) + 1}, {column['label'] if column else cell.group(2)}"
    return field_labels(model).get(field_id, field_id)


def _first_bad(text: str, ok: Any, split: str = r'[,\s]+') -> Optional[str]:
    for token in (t for t in re.split(split, text.strip()) if t):
        if not ok(token):
            return token
    return None


def _is_float(token: str) -> bool:
    try:
        float(token)
        return True
    except ValueError:
        return False


def _is_int(token: str) -> bool:
    return re.fullmatch(r'-?\d+', token.strip()) is not None


def _parse_message(field: Optional[Mapping[str, Any]], typed: str) -> str:
    """What's wrong with ``typed`` in a field it doesn't parse in."""
    kind = field['kind'] if field else None
    text = typed.strip()
    if kind == form.KIND_PITCH_LIST:
        bad = _first_bad(text, lambda t: form.parse_pitch_token(t) is not None)
        if bad:
            return f"{bad} isn't a note name."
    elif kind == form.KIND_PITCH:
        return f"{text} isn't a note name." if text else 'A note is needed.'
    elif kind == form.KIND_INT:
        if _is_int(text) and 'min' in field and 'max' in field:
            return f"{text} is out of range."
        return f"{text} isn't a whole number." if text else 'A whole number is needed.'
    elif kind == form.KIND_FLOAT:
        return f"{text} isn't a number." if text else 'A number is needed.'
    elif kind == form.KIND_INT_LIST:
        bad = _first_bad(text, _is_int, r',')
        if bad:
            return f"{bad.strip()} isn't a whole number."
    elif kind == form.KIND_FLOAT_OR_LIST:
        bad = _first_bad(text, _is_float, r',')
        if bad:
            return f"{bad.strip()} isn't a number."
    elif kind == form.KIND_CHOICE:
        return f"{text} isn't one of the choices."
    return "This value can't be read."


def _sentence(message: str, model: str) -> str:
    """A spec message as a sentence: no voicing in front, field labels for keys."""
    labels = field_labels(model)
    text = _SPEC_PREFIX.sub('', message.strip())
    text = re.sub(r"'(\w+)'", lambda m: labels.get(m.group(1), m.group(0)), text)
    text = text[:1].upper() + text[1:]
    return text if text.endswith(('.', '!', '?')) else text + '.'


def _number(value: Any) -> str:
    return f'{value:g}' if isinstance(value, float) else str(value)


def field_syntax(field: Optional[Mapping[str, Any]], values: Mapping[str, Any],
                 notation: str = 'american') -> str:
    """How to write a value of ``field`` (its syntax or range, example notes
    in ``notation``), or "" when it's obvious."""
    if not field:
        return ''
    kind = field['kind']
    if kind in (form.KIND_INT, form.KIND_FLOAT):
        what = 'a whole number' if kind == form.KIND_INT else 'a number'
        if 'min' in field and 'max' in field:
            return f"Enter {what} from {_number(field['min'])} to {_number(field['max'])}."
        return f"Enter {what}."
    if kind == form.KIND_PITCH:
        return f"Use a note name or a MIDI number, e.g. {form.note_name(60, notation)} or 60."
    if kind == form.KIND_PITCH_LIST:
        hint = form.field_hint(field, values, notation).strip('()') or 'note names or MIDI numbers'
        count = ''
        if 'min_items' in field and 'max_items' in field:
            count = f", {field['min_items']} to {field['max_items']} {field['label'].lower()}"
        return f'Use {hint}{count}.'
    if kind == form.KIND_INT_LIST:
        rule = field.get('hint_count')
        if rule:
            count = max(len(values.get(rule['records']) or []) + rule['offset'], 0)
            return f'Use whole numbers separated by commas, {count} of them.'
        return 'Use whole numbers separated by commas.'
    if kind == form.KIND_FLOAT_OR_LIST:
        return 'Use a number, or one number per voice separated by commas.'
    if kind == form.KIND_CHOICE:
        names = [choice['label'] for choice in field.get('choices', [])]
        if len(names) < 2:
            return ''
        return f"Choose {', '.join(names[:-1])} or {names[-1]}."
    return ''


def problem_text(voicing: str, model: str, problem: FieldProblem,
                 values: Mapping[str, Any], notation: str = 'american') -> str:
    """One line of the problem list, e.g. "Voicing 'Bass', Strings: E2 X9. X9
    isn't a note name. Use note names or MIDI numbers, e.g. E2 A2 D3 G3 B3 E4,
    3 to 12 strings." """
    model = form.form_model(model)
    if problem.field_id is None:
        return f"Voicing '{voicing}': {problem.message}"
    syntax = field_syntax(_field_of(model, problem.field_id), values, notation)
    typed = problem.typed.strip() or '(empty)'
    line = f"Voicing '{voicing}', {_label_of(model, problem.field_id)}: {typed}. {problem.message}"
    return f'{line} {syntax}' if syntax else line

