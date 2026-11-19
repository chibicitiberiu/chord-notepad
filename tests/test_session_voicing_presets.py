"""The voicings editor's presets for a new voicing and the built-ins shown
read-only: ``add_voicing_from``, ``select_builtin``, the ``blank`` group,
``VoicingGroup.builtins`` and ``VoicingEditorState.read_only``."""

import pytest

from chordnotepad.models.voicing_versions import VOICING_VERSION
from chordnotepad.session.platform import ANDROID, DESKTOP_QT
from chordnotepad.session.state import VoicingEditorState
from chordnotepad.settings_forms import voicing_form
from chordnotepad.viewmodels.settings_viewmodel import voicing_error

from tests.test_session_settings_edit import BASS, editor, make


def _make(tmp_path, voicings=None, platform=DESKTOP_QT):
    from chordnotepad.services.appdata_service import AppDataService
    from chordnotepad.session.bootstrap import build_core_services, create_session
    from chordnotepad.session.host import HostDispatch
    from chordnotepad.session.testing import (
        EventRecorder, FakePlayer, InMemoryDocumentStore, ManualHost,
    )
    import json

    if voicings is not None:
        config_dir = tmp_path / "config" / "chord-notepad"
        config_dir.mkdir(parents=True)
        (config_dir / "settings.json").write_text(json.dumps({"voicings": voicings}))
    host = ManualHost()
    services = build_core_services(AppDataService(root=tmp_path), HostDispatch(host),
                                   player=FakePlayer())
    session = create_session(host, services, InMemoryDocumentStore(), chord_sheet=False,
                             platform=platform)
    recorder = EventRecorder()
    session.subscribe(recorder)
    session.start()
    session.begin_settings_edit()
    return session, recorder


def _working(session):
    return session._settings_edit.model.get_voicings()


# -- the presets ---------------------------------------------------------------------


def test_the_blank_group_comes_first_with_each_models_defaults(tmp_path):
    session, recorder = _make(tmp_path)
    presets = editor(recorder).presets
    assert [(p.group, p.label) for p in presets[:3]] == [
        ("blank", "Blank fretboard"), ("blank", "Blank piano"), ("blank", "Blank ensemble")]
    assert all(p.group != "blank" for p in presets[3:])


@pytest.mark.parametrize("label, model, name", [
    ("Blank fretboard", "fretboard", "New fretboard voicing"),
    ("Blank piano", "piano", "New piano voicing"),
    ("Blank ensemble", "ensemble", "New ensemble voicing"),
])
def test_a_blank_is_its_models_valid_defaults(tmp_path, label, model, name):
    session, recorder = _make(tmp_path)
    session.add_voicing_from("blank", label)
    state = editor(recorder)
    assert (state.selected, state.model, state.read_only) == (name, model, False)
    # A blank links to nothing; it has this release's version.
    assert _working(session)[name] == dict(voicing_form.default_voicing(model),
                                           version=VOICING_VERSION)
    assert voicing_error(name, _working(session)[name]) is None
    assert state.form_errors == () and state.field_errors == {}
    assert name not in state.invalid


def test_android_lists_the_blank_group_first_too(tmp_path):
    # Its Add voicing menu offers the blanks, as the Qt desktop's does.
    session, recorder = _make(tmp_path, platform=ANDROID)
    presets = editor(recorder).presets
    assert [(p.group, p.label) for p in presets[:3]] == [
        ("blank", "Blank fretboard"), ("blank", "Blank piano"), ("blank", "Blank ensemble")]
    session.add_voicing_from("blank", "Blank piano")
    assert editor(recorder).selected == "New piano voicing"


# -- add_voicing_from: names ---------------------------------------------------------


def test_names_are_numbered_ignoring_case(tmp_path):
    session, recorder = _make(tmp_path, voicings={"new piano VOICING": BASS})
    session.add_voicing_from("blank", "Blank piano")
    assert editor(recorder).selected == "New piano voicing 2"
    session.add_voicing_from("blank", "Blank piano")
    assert editor(recorder).selected == "New piano voicing 3"
    session.add_voicing_from("ensemble", "String Quartet")
    assert editor(recorder).selected == "New String Quartet"
    session.add_voicing_from("ensemble", "String Quartet")
    assert editor(recorder).selected == "New String Quartet 2"


def test_a_copy_of_a_voicing_of_the_users_also_the_selected_one(tmp_path):
    session, recorder = _make(tmp_path, voicings={"Bass": BASS})
    session.select_voicing("Bass")
    session.add_voicing_from("custom", "Bass")
    state = editor(recorder)
    assert state.selected == "New Bass" and state.model == "fretboard"
    assert _working(session)["New Bass"] == dict(BASS, version=VOICING_VERSION)
    assert _working(session)["New Bass"] is not _working(session)["Bass"]
    assert state.groups[0].names == ("Bass", "New Bass")


def test_a_copy_of_a_built_in_takes_its_data_and_one_state(tmp_path):
    session, recorder = _make(tmp_path)
    satb = next(p for p in editor(recorder).presets if p.group == "ensemble")
    published = len(recorder.of_type(VoicingEditorState))
    session.add_voicing_from(satb.group, satb.label)
    assert len(recorder.of_type(VoicingEditorState)) == published + 1
    state = editor(recorder)
    name = f"New {satb.label}"
    assert (state.selected, state.model, state.dirty) == (name, "ensemble", False)
    assert len(state.values["voices"]) == 4 and state.form_errors == ()
    preset = next(p for p in voicing_form.load_presets() if p["label"] == satb.label)
    assert preset["based_on"] == "ensemble:satb"
    assert _working(session)[name] == dict(preset["data"], version=VOICING_VERSION,
                                           based_on="ensemble:satb")


def test_an_unknown_preset_is_refused(tmp_path):
    session, recorder = _make(tmp_path)
    with pytest.raises(ValueError):
        session.add_voicing_from("ensemble", "Nope")
    assert editor(recorder).selected is None


# -- built-ins in the list, read-only -------------------------------------------------


def test_each_group_lists_its_built_ins_in_preset_order(tmp_path):
    session, recorder = _make(tmp_path)
    groups = {g.model: g.builtins for g in editor(recorder).groups}
    presets = voicing_form.load_presets()
    for model in ("fretboard", "piano", "ensemble"):
        assert groups[model] == tuple(p["label"] for p in presets if p["group"] == model)
    assert groups["piano"] == ("Piano (default)",)
    assert "Ukulele" in groups["fretboard"]


def test_a_built_in_shows_read_only_and_every_edit_is_refused(tmp_path):
    session, recorder = _make(tmp_path, voicings={"Bass": BASS})
    session.select_builtin("fretboard", "Ukulele")
    state = editor(recorder)
    assert (state.selected, state.model, state.read_only, state.dirty) == (
        "Ukulele", "fretboard", True, False)
    assert state.values == voicing_form.values_from_voicing(
        "fretboard", next(p["data"] for p in voicing_form.load_presets()
                          if p["label"] == "Ukulele"))
    working = {name: dict(data) for name, data in _working(session).items()}

    refused = [
        lambda: session.set_voicing_values({"max_fret": "7"}),
        lambda: session.set_voicing_model("piano"),
        lambda: session.add_voicing_record(),
        lambda: session.remove_voicing_record(0),
        lambda: session.move_voicing_record(0, 1),
        lambda: session.load_voicing_preset("ensemble", "String Quartet"),
    ]
    for edit in refused:
        revision = editor(recorder).revision
        with pytest.raises(RuntimeError, match="built-in"):
            edit()
        # The state still comes back (a view resets its fields from it).
        assert editor(recorder).revision == revision + 1
        assert editor(recorder).read_only is True
    assert _working(session) == working
    assert "Ukulele" not in _working(session)

    # Copy to a new voicing: editable again.
    session.add_voicing_from("fretboard", "Ukulele")
    state = editor(recorder)
    assert (state.selected, state.read_only) == ("New Ukulele", False)
    session.set_voicing_values({"max_fret": "7"})
    assert _working(session)["New Ukulele"]["max_fret"] == 7

    # Selecting a voicing of the user's ends read-only too.
    session.select_builtin("piano", "Piano (default)")
    assert editor(recorder).read_only is True
    session.select_voicing("Bass")
    assert editor(recorder).read_only is False


def test_a_built_in_must_exist(tmp_path):
    session, recorder = _make(tmp_path, voicings={"Bass": BASS})
    for group, label in [("fretboard", "Nope"), ("custom", "Bass"), ("blank", "Blank piano")]:
        with pytest.raises(ValueError):
            session.select_builtin(group, label)
    assert editor(recorder).read_only is False


def test_a_users_voicing_named_like_a_built_in_preset_stays_its_own(tmp_path):
    # "Piano (default)" is a preset label, not a built-in name, so a voicing
    # may take it; showing the built-in must not touch that voicing.
    session, recorder = _make(tmp_path, voicings={"Piano (default)": BASS})
    session.select_builtin("piano", "Piano (default)")
    state = editor(recorder)
    assert state.model == "piano" and state.read_only
    assert [p.label for p in state.presets if p.group == "custom"] == ["Piano (default)"]
    session.remove_voicing("Piano (default)")
    state = editor(recorder)
    assert state.read_only and state.selected == "Piano (default)" and state.model == "piano"
    assert "Piano (default)" not in _working(session)


def test_the_notation_respells_a_built_in(tmp_path):
    session, recorder = _make(tmp_path)
    session.select_builtin("ensemble", "Choir (SATB)")
    american = editor(recorder).values
    session.set_settings_notation("european")
    european = editor(recorder).values
    assert editor(recorder).read_only
    assert european != american
    assert european == voicing_form.values_from_voicing(
        "ensemble", next(p["data"] for p in voicing_form.load_presets()
                         if p["label"] == "Choir (SATB)"), "european")


def test_the_desktop_make_helper_still_works(tmp_path):
    # The shared helper (Tk desktop platform) lists the blanks too.
    session, _, recorder = make(tmp_path)
    session.begin_settings_edit()
    assert editor(recorder).presets[0].group == "blank"
