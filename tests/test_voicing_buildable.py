"""What Settings accepts, playback can build.

``voicing_form.voicing_error`` builds the picker with the same function
PlaybackService does (``audio.picker_factory.build_picker``), so a voicing the
form lets through never falls back to Piano; and one that can't be built is
refused with its reason and reported once when it is chosen.
"""

import copy
import dataclasses
from unittest.mock import Mock

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from chordnotepad.audio.chord_picker import ChordNotePicker
from chordnotepad.audio.ensemble_voicer import EnsembleVoicer
from chordnotepad.audio.guitar_chord_picker import GuitarChordPicker
from chordnotepad.audio.picker_factory import build_picker
from chordnotepad.exceptions import ConfigurationError
from chordnotepad.services.config_service import ConfigService
from chordnotepad.services.playback_service import PlaybackService
from chordnotepad.session.events import UserError
from chordnotepad.session.formatting import UNUSABLE_VOICING_TITLE
from chordnotepad.settings_forms import voicing_form as vf

from tests.test_session_settings_edit import editor, make

PICKERS = {'fretboard': GuitarChordPicker, 'ensemble': EnsembleVoicer, 'piano': ChordNotePicker}


def _service(voicings, voicing='voicing:V'):
    """A PlaybackService over a config holding ``voicings``."""
    config = Mock(spec=ConfigService)
    config.get.side_effect = lambda key, default=None: {
        'voicings': voicings, 'voicing': voicing}.get(key, default)
    return PlaybackService(config, player=Mock())


def _accepted(model, values, label=None):
    """The voicing dict of ``values`` when the form accepts it, else None."""
    checked = vf.validate_form('V', model, values, label)
    if checked['fields'] or checked['form']:
        return None
    return vf.voicing_from_values(model, values, label)


def _plays_as_its_model(data):
    service = _service({'V': data})
    assert service.voicing_failure is None
    assert isinstance(service._note_picker, PICKERS[data['model']])
    assert isinstance(build_picker('V', data), PICKERS[data['model']])


def test_every_preset_and_blank_builds():
    for preset in vf.load_presets():
        data = preset['data']
        assert vf.voicing_error(preset['label'], data) is None, preset['label']
        _plays_as_its_model(data)
    for model in vf.MODELS:
        data = vf.default_voicing(model)
        assert vf.voicing_error('Blank', data) is None
        _plays_as_its_model(data)


def test_the_form_refuses_what_the_engine_cannot_build():
    # Whatever build_picker raises is the form's error, in its words.
    bad = {'model': 'ensemble', 'voices': [{'name': 'A', 'range': ['C3', 'C4']},
                                           {'name': 'B', 'range': ['C4', 'C5']}]}
    message = vf.voicing_error('V', bad)
    assert message and 'lower than voice' in message
    with pytest.raises(ConfigurationError):
        build_picker('V', bad)
    assert vf.cross_field_errors('V', 'ensemble', vf.values_from_voicing('ensemble', bad))
    # A build failure that isn't a spec message is refused too.
    unbuildable = {'model': 'ensemble', **vf.default_voicing('ensemble'),
                   'weights': {'movement': []}}
    assert vf.voicing_error('V', unbuildable)


CELLS = st.sampled_from(['C2', 'C4', 'G5', 'zz', '', 'E1', 'B3'])
NUMBERS = st.sampled_from(['-0.4', '0', '1.5', 'x', '', '-0.15'])
OPS = st.one_of(
    st.tuples(st.just('add')),
    st.tuples(st.just('remove'), st.integers(0, 8)),
    st.tuples(st.just('move'), st.integers(0, 8), st.integers(-3, 3)),
    st.tuples(st.just('duplicate'), st.integers(0, 8)),
    st.tuples(st.just('cell'), st.integers(0, 8),
              st.sampled_from(['low', 'high', 'gap', 'movement', 'name']), CELLS),
    st.tuples(st.just('cell'), st.integers(0, 8), st.just('movement'), NUMBERS),
    st.tuples(st.just('field'), st.sampled_from(['allow_unisons', 'upper_clef']), st.booleans()),
)


@settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(preset=st.sampled_from([p['data'] for p in vf.load_presets() if p['data']['model'] == 'ensemble']),
       ops=st.lists(OPS, max_size=8))
def test_anything_the_form_accepts_after_edits_builds(preset, ops):
    values = vf.values_from_voicing('ensemble', preset)
    for op in ops:
        kind = op[0]
        if kind == 'add':
            values = vf.add_record('ensemble', values)
        elif kind == 'remove':
            values = vf.remove_record('ensemble', values, op[1])
        elif kind == 'move':
            values = vf.move_record('ensemble', values, op[1], op[2])
        elif kind == 'duplicate':
            values = vf.duplicate_record('ensemble', values, op[1])
        elif kind == 'cell':
            rows = copy.deepcopy(values['voices'])
            if op[1] < len(rows):
                rows[op[1]][op[2]] = op[3]
            values = {**values, 'voices': rows}
        else:
            values = {**values, op[1]: 'treble' if op[1] == 'upper_clef' else op[2]}
        data = _accepted('ensemble', values)
        if data is not None:
            _plays_as_its_model(data)
        else:
            # Refused: the form says so on a field or for the whole form.
            checked = vf.validate_form('V', 'ensemble', values)
            assert checked['fields'] or checked['form']


def test_quartet_copy_with_two_added_voices_commits_and_plays_as_the_ensemble(tmp_path):
    """Tibi's case through the session: copy the String Quartet, add a Solo and a
    Double Bass, save; playback builds the ensemble, not Piano."""
    session, services, recorder = make(tmp_path)
    session.begin_settings_edit()
    session.add_voicing_from("ensemble", "String Quartet")
    name = editor(recorder).selected
    for voice_name, low, high in (("Solo", "B1", "D4"), ("Double Bass", "E1", "G2")):
        session.add_voicing_record()
        voices = [dict(v) for v in editor(recorder).values["voices"]]
        voices[-1].update(name=voice_name, low=low, high=high)
        session.set_voicing_values({"voices": voices})
    state = editor(recorder)
    assert [r["movement"] for r in state.values["voices"]] == \
        ["-0.8", "-0.4", "-0.4", "-0.4", "-0.4", "-0.15"]
    assert state.field_errors == {} and name not in state.invalid

    session.save_settings(None)
    saved = services.config.config.voicings[name]
    assert saved["weights"]["movement"] == [-0.8, -0.4, -0.4, -0.4, -0.4, -0.15]
    session.set_voicing(f"voicing:{name}")
    assert services.playback.voicing_failure is None
    assert isinstance(services.playback.create_note_picker(), EnsembleVoicer)
    assert isinstance(services.playback._note_picker, EnsembleVoicer)
    assert not any(isinstance(e, UserError) and e.title == UNUSABLE_VOICING_TITLE
                   for e in recorder.items)


def test_a_saved_quartet_with_the_old_four_entry_list_opens_and_plays_as_the_ensemble(tmp_path):
    quartet = next(p["data"] for p in vf.load_presets() if p["label"] == "String Quartet")
    old = copy.deepcopy(quartet)
    old["voices"] += [{"name": "Solo", "range": ["B1", "D4"]},
                      {"name": "Double Bass", "range": ["E1", "G2"]}]
    old["max_spacing"] += [12, 12]
    session, services, recorder = make(tmp_path, voicings={"Copy": old}, current=True)
    session.begin_settings_edit()
    session.select_voicing("Copy")
    state = editor(recorder)
    assert [r["movement"] for r in state.values["voices"]] == \
        ["-0.8", "-0.4", "-0.4", "-0.4", "-0.4", "-0.15"]
    assert state.field_errors == {}
    assert isinstance(_service({"Copy": old}, "voicing:Copy")._note_picker, EnsembleVoicer)


def _unbuildable():
    """A voicing from an old or hand-edited config that can't be built."""
    return {"model": "ensemble", "voices": [{"name": "A", "range": ["C3", "C4"]},
                                            {"name": "B", "range": ["C4", "C5"]}]}


def test_playback_says_why_a_voicing_fell_back_to_piano():
    service = _service({"V": _unbuildable()})
    assert isinstance(service._note_picker, ChordNotePicker)
    assert service.voicing_failure.startswith("Voicing 'V' can't be used: ")
    assert service.voicing_failure.endswith("Playing with Piano until it's fixed in Settings.")
    service.set_voicing("voicing:Nope")
    assert "no such voicing" in service.voicing_failure
    service.set_voicing("piano")
    assert service.voicing_failure is None


def test_the_session_reports_an_unusable_voicing_once_per_choice(tmp_path):
    session, services, recorder = make(tmp_path, voicings={"Bad": _unbuildable()}, current=True)
    notices = lambda: [e for e in recorder.items
                       if isinstance(e, UserError) and e.title == UNUSABLE_VOICING_TITLE]
    assert notices() == []
    session.set_voicing("voicing:Bad")
    assert len(notices()) == 1
    assert notices()[0].message.startswith("Voicing 'Bad' can't be used: ")
    assert "Playing with Piano until it's fixed in Settings." in notices()[0].message
    session.set_voicing("piano")
    assert len(notices()) == 1
    session.set_voicing("voicing:Bad")
    assert len(notices()) == 2


FIELD_TEXT = st.sampled_from(['0', '1', '4', '5', '12', '99', '-3', 'x', '', '2.5', 'C3', 'E2 A2 D3 G3'])


@pytest.mark.parametrize('model', ['fretboard', 'piano'])
@settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.too_slow,
                                                                  HealthCheck.function_scoped_fixture])
@given(data=st.data())
def test_fretboard_and_piano_edits_the_form_accepts_build(model, data):
    values = vf.default_values(model)
    ids = [k for k, v in values.items() if isinstance(v, str)]
    for key in data.draw(st.lists(st.sampled_from(ids), max_size=4)):
        values = {**values, key: data.draw(FIELD_TEXT)}
    accepted = _accepted(model, values)
    if accepted is not None:
        _plays_as_its_model(accepted)
