"""The ``version`` and ``based_on`` of saved voicings (models.voicing_versions).

Every path that stores a voicing stamps it with this release's version; a
copy of a built-in links to it; a rebuild from the form carries the stored
dict's link, the keys it doesn't know (a newer release's) and a higher
version.
"""

import copy
import json

import pytest

from chordnotepad.constants import CONFIG_VERSION
from chordnotepad.models import voicing_versions as vv
from chordnotepad.models.voicing_versions import VOICING_VERSION
from chordnotepad.services.appdata_service import AppDataService
from chordnotepad.session.bootstrap import build_core_services, create_session
from chordnotepad.session.host import HostDispatch
from chordnotepad.session.platform import ANDROID, DESKTOP_QT
from chordnotepad.session.testing import EventRecorder, FakePlayer, InMemoryDocumentStore, ManualHost
from chordnotepad.settings_forms import voicing_form as vf
from chordnotepad.settings_forms.voicing_autosave import plan_voicing


def _make(tmp_path, voicings=None, platform=DESKTOP_QT):
    if voicings is not None:
        config_dir = tmp_path / "config" / "chord-notepad"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "settings.json").write_text(json.dumps(
            {"version": CONFIG_VERSION, "voicings": voicings}))
    host = ManualHost()
    services = build_core_services(AppDataService(root=tmp_path), HostDispatch(host),
                                   player=FakePlayer())
    session = create_session(host, services, InMemoryDocumentStore(), chord_sheet=False,
                             platform=platform)
    session.subscribe(EventRecorder())
    session.start()
    session.begin_settings_edit()
    return session, services


def _working(session):
    return session._settings_edit.model.get_voicings()


def _disk(services):
    return json.loads(services.appdata.get_config_file_path().read_text())["voicings"]


def _preset(label):
    return next(p for p in vf.load_presets() if p["label"] == label)


QUARTET = _preset("String Quartet")
STANDARD = next(p for p in vf.load_presets() if p["group"] == "fretboard")


# -- ids ------------------------------------------------------------------------------


def test_every_built_in_preset_has_its_link():
    from chordnotepad.models.ensemble_spec import BUILTIN_ENSEMBLES
    from chordnotepad.models.fretboard_spec import BUILTIN_FRETBOARDS
    links = {p["label"]: p.get("based_on") for p in vf.load_presets({"mine": {"model": "piano"}})}
    for slug, spec in BUILTIN_FRETBOARDS.items():
        assert links[spec.label] == f"guitar:{slug}"
    for slug, spec in BUILTIN_ENSEMBLES.items():
        assert links[spec.label] == f"ensemble:{slug}"
    assert links["Piano (default)"] == "piano"
    assert links["mine"] is None
    assert QUARTET["based_on"] == "ensemble:quartet"


def test_stamp_keeps_a_higher_version_and_replaces_junk():
    assert vv.stamp({}) == {"version": VOICING_VERSION}
    assert vv.stamp({"version": VOICING_VERSION + 3}) == {"version": VOICING_VERSION + 3}
    for junk in ("2", 1.0, True, -1, None):
        assert vv.stamp({"version": junk}) == {"version": VOICING_VERSION}
    assert vv.stamp({}, "piano") == {"version": VOICING_VERSION, "based_on": "piano"}


def test_migrate_voicing_leaves_a_current_voicing_alone():
    entry = {"model": "piano", "version": VOICING_VERSION}
    assert vv.migrate_voicing(entry) is False and entry == {"model": "piano",
                                                             "version": VOICING_VERSION}
    newer = {"model": "piano", "version": VOICING_VERSION + 1, "x": 1}
    assert vv.migrate_voicing(newer) is False and newer["version"] == VOICING_VERSION + 1
    unstamped = {"model": "piano"}
    assert vv.migrate_voicing(unstamped) is True and unstamped["version"] == VOICING_VERSION
    floated = {"model": "piano", "version": float(VOICING_VERSION)}
    assert vv.migrate_voicing(floated) is True and type(floated["version"]) is int


# -- every store path stamps ----------------------------------------------------------


def _assert_stamped(entry, based_on):
    assert entry["version"] == VOICING_VERSION
    assert entry.get("based_on") == based_on


def test_each_store_path_ends_with_a_version_and_the_link(tmp_path):
    session, services = _make(tmp_path)
    session.add_voicing()
    _assert_stamped(_working(session)["New voicing"], None)

    session.add_voicing_from("blank", "Blank ensemble")
    _assert_stamped(_working(session)["New ensemble voicing"], None)

    session.add_voicing_from("ensemble", "String Quartet")
    name = "New String Quartet"
    _assert_stamped(_working(session)[name], "ensemble:quartet")
    session.set_voicing_values({"weight:leap_penalty": "-2.5"})
    _assert_stamped(_working(session)[name], "ensemble:quartet")
    assert _working(session)[name]["weights"]["leap_penalty"] == -2.5
    session.add_voicing_record("voices")
    session.duplicate_voicing_record(0, "voices")
    session.move_voicing_record(0, 1, "voices")
    session.remove_voicing_record(5, "voices")
    _assert_stamped(_working(session)[name], "ensemble:quartet")
    assert len(_working(session)[name]["voices"]) == 5

    session.add_voicing_from("custom", name)
    _assert_stamped(_working(session)[f"New {name}"], "ensemble:quartet")

    session.select_voicing("New voicing")
    session.load_voicing_preset("ensemble", "String Quartet")
    _assert_stamped(_working(session)["New voicing"], "ensemble:quartet")
    session.load_voicing_preset("fretboard", STANDARD["label"])
    _assert_stamped(_working(session)["New voicing"], "guitar:standard")
    session.load_voicing_preset("custom", "New ensemble voicing")
    _assert_stamped(_working(session)["New voicing"], None)
    session.load_voicing_preset("ensemble", "String Quartet")
    session.set_voicing_model("piano")
    _assert_stamped(_working(session)["New voicing"], None)
    session.set_voicing_model("ensemble")
    _assert_stamped(_working(session)["New voicing"], None)

    # The Qt desktop's Save writes the working copy as it is.
    session.save_settings()
    disk = _disk(services)
    _assert_stamped(disk[name], "ensemble:quartet")
    _assert_stamped(disk[f"New {name}"], "ensemble:quartet")
    _assert_stamped(disk["New voicing"], None)
    _assert_stamped(disk["New ensemble voicing"], None)


def test_android_autosave_writes_the_version_and_the_link(tmp_path):
    session, services = _make(tmp_path, platform=ANDROID)
    session.add_voicing_from("ensemble", "String Quartet")
    session.commit_settings(None, invalid_numbers={})
    _assert_stamped(_disk(services)["New String Quartet"], "ensemble:quartet")
    session.set_voicing_values({"weight:leap_penalty": "-3"})
    session.commit_settings(None, invalid_numbers={})
    saved = _disk(services)["New String Quartet"]
    _assert_stamped(saved, "ensemble:quartet")
    assert saved["weights"]["leap_penalty"] == -3.0
    # A wrong field keeps its value on disk; the rest, the link included, is written.
    session.set_voicing_values({"weight:leap_penalty": "x", "weight:unison_penalty": "-1"})
    session.commit_settings(None, invalid_numbers={})
    saved = _disk(services)["New String Quartet"]
    _assert_stamped(saved, "ensemble:quartet")
    assert (saved["weights"]["leap_penalty"], saved["weights"]["unison_penalty"]) == (-3.0, -1.0)


# -- the carry-over -------------------------------------------------------------------


def _newer(data):
    """``data`` as a newer release might have saved it."""
    entry = copy.deepcopy(data)
    entry.update(version=VOICING_VERSION + 2, based_on="ensemble:quartet", future_key=[1, 2])
    entry["weights"] = dict(entry.get("weights", {}), future_weight=-1.5)
    entry["weights"]["omit"] = dict(entry["weights"]["omit"], future_role=-9.0)
    return entry


def test_a_rebuild_carries_unknown_keys_the_link_and_a_higher_version():
    base = _newer(QUARTET["data"])
    values = vf.values_from_voicing("ensemble", base)
    out = vf.voicing_from_values("ensemble", values, base.get("label"), base=base)
    assert out["version"] == VOICING_VERSION + 2
    assert out["based_on"] == "ensemble:quartet"
    assert out["future_key"] == [1, 2]
    assert out["weights"]["future_weight"] == -1.5
    assert out["weights"]["omit"]["future_role"] == -9.0
    assert out["voices"] == base["voices"]


def test_a_rebuild_without_a_base_adds_nothing():
    values = vf.values_from_voicing("ensemble", QUARTET["data"])
    out = vf.voicing_from_values("ensemble", values, "String Quartet")
    assert "version" not in out and "based_on" not in out


def test_keys_the_form_builds_are_never_carried_over():
    base = dict(copy.deepcopy(QUARTET["data"]), upper_clef="bass")
    base["weights"]["bass_movement"] = -0.15
    values = dict(vf.values_from_voicing("ensemble", base), upper_clef="treble")
    out = vf.voicing_from_values("ensemble", values, None, base=base)
    assert "upper_clef" not in out  # set back to treble, which isn't saved
    assert "bass_movement" not in out["weights"]  # the movement list replaces it
    assert "label" not in out  # the label is the caller's
    assert out["version"] == VOICING_VERSION


def test_a_model_switch_carries_nothing():
    base = _newer(QUARTET["data"])
    out = vf.voicing_from_values("piano", vf.default_values("piano"), None, base=base)
    assert "based_on" not in out and "future_key" not in out
    assert "future_weight" not in out["weights"]
    assert out["version"] == VOICING_VERSION


@pytest.mark.parametrize("model", ["fretboard", "piano"])
def test_other_models_carry_their_unknown_keys(model):
    base = dict(vf.default_voicing(model), based_on="piano" if model == "piano" else
                "guitar:standard", version=VOICING_VERSION, capo_default=2,
                weights={"future_weight": 1.0})
    if model == "piano":
        base["weights"]["omit"] = {"future_role": -2.0}
    out = vf.voicing_from_values(model, vf.values_from_voicing(model, base), None, base=base)
    assert out["based_on"] == base["based_on"] and out["capo_default"] == 2
    assert out["weights"]["future_weight"] == 1.0
    if model == "piano":
        assert out["weights"]["omit"]["future_role"] == -2.0


def test_the_autosave_plan_carries_the_working_data():
    base = _newer(QUARTET["data"])
    values = dict(vf.values_from_voicing("ensemble", base), **{"weight:leap_penalty": "x"})
    plan = plan_voicing("Q", "ensemble", values, base.get("label"), saved=base, stored=base)
    assert plan.problems and plan.data is not None
    assert plan.data["future_key"] == [1, 2] and plan.data["based_on"] == "ensemble:quartet"
    assert plan.data["version"] == VOICING_VERSION + 2


def test_an_edit_on_either_platform_keeps_a_newer_releases_keys(tmp_path):
    for platform in (DESKTOP_QT, ANDROID):
        root = tmp_path / platform
        session, services = _make(root, voicings={"Q": _newer(QUARTET["data"])},
                                  platform=platform)
        session.select_voicing("Q")
        session.set_voicing_values({"weight:leap_penalty": "-2.5"})
        if platform == ANDROID:
            session.commit_settings(None, invalid_numbers={})
        else:
            session.save_settings()
        saved = _disk(services)["Q"]
        assert saved["weights"]["leap_penalty"] == -2.5
        assert saved["future_key"] == [1, 2] and saved["weights"]["future_weight"] == -1.5
        assert saved["version"] == VOICING_VERSION + 2
        assert saved["based_on"] == "ensemble:quartet"


# -- a newer release's model ------------------------------------------------------------


HARP = {"model": "harp", "strings": 47, "pedals": {"C": "natural"},
        "weights": {"glissando_bonus": 1.0}, "version": VOICING_VERSION + 1}
GUITAR = {"model": "fretboard", "tuning": [40, 45, 50, 55, 59, 64], "label": "Mine",
          "version": VOICING_VERSION}


def _editor(session):
    from chordnotepad.session.state import VoicingEditorState
    return session._settings_edit.state(session._services.config.config.voicings)


@pytest.mark.parametrize("platform", [DESKTOP_QT, ANDROID])
def test_a_newer_releases_model_is_read_only_and_never_rewritten(tmp_path, platform):
    from chordnotepad.session.settings_edit import NEWER_VERSION_NOTE
    session, services = _make(tmp_path, voicings={"Harp": copy.deepcopy(HARP),
                                                   "Mine": copy.deepcopy(GUITAR)},
                              platform=platform)
    session.select_voicing("Harp")
    state = _editor(session)
    assert (state.selected, state.model, state.read_only) == ("Harp", None, True)
    assert state.values == {} and state.form_errors == (NEWER_VERSION_NOTE,)
    assert "Harp" not in state.invalid
    for edit in (lambda: session.set_voicing_values({"weight:x": "1"}),
                 lambda: session.set_voicing_model("piano"),
                 lambda: session.load_voicing_preset("ensemble", "String Quartet"),
                 lambda: session.add_voicing_record("voices")):
        with pytest.raises(RuntimeError, match="newer version"):
            edit()
    assert _working(session)["Harp"] == HARP

    # Editing another voicing and saving writes the harp as it was.
    session.select_voicing("Mine")
    assert not _editor(session).read_only
    session.set_voicing_values({"max_fret": "15"})
    session.rename_voicing("Harp", "Concert harp")
    if platform == ANDROID:
        session.commit_settings(None, invalid_numbers={})
    else:
        session.save_settings()
    disk = _disk(services)
    assert disk["Concert harp"] == HARP and "Harp" not in disk
    assert disk["Mine"]["max_fret"] == 15


def test_loading_a_newer_releases_voicing_over_one_makes_it_read_only(tmp_path):
    session, services = _make(tmp_path, voicings={"Harp": copy.deepcopy(HARP),
                                                   "Mine": copy.deepcopy(GUITAR)})
    session.select_voicing("Mine")
    session.load_voicing_preset("custom", "Harp")
    assert _editor(session).read_only and _working(session)["Mine"] == HARP
    with pytest.raises(RuntimeError):
        session.set_voicing_values({"max_fret": "15"})
