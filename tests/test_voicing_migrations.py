"""The voicing migrations (models.voicing_versions) on files real releases wrote.

The fixtures under tests/fixtures/configs/ were built from old releases'
own output (``git show <tag>``: their presets, their settings form, and
v0.5.4's config migration for the damaged file):

* ``v0.2-legacy.json``: v0.2.0, custom_tunings, European notation;
* ``v0.5.4-copies.json``: v0.5.4, a copy of every built-in as its Tk dialog
  saved it (through the form) and each ensemble as Android stored it (the
  preset raw), with a few values the user changed;
* ``v0.5.4-first-session.json``: the same, as 0.5.4 wrote it in the first
  session (version 1, voicings already signed);
* ``damaged-flipped.json``: such a first session after the next start in
  0.5.4, which flipped the penalties into rewards;
* ``between-builds-copy.json``: a String Quartet copy from a build between
  0.5.4 and 0.6 (c569762), later edited by a build that wrote
  outer_leap_penalty and middle_range_penalty at their added defaults;
* ``tibi-shaped.json``: shaped like Tibi's file as the plan describes it (a
  five-voice quartet copy saved before the version field, three guitars
  that kept the Standard label with other tunings);
* ``v0.4.1-first-session.json``: v0.4.1's first session (version 1): copies
  of SATB, TTBB and the Standard guitar from its Load config sources, and a
  guitar hand-edited in the file with a single weight;
* ``v0.4.1-damaged.json``: the same (without the hand-made guitar) after
  v0.4.1's second start, whose v1 migration flipped the signs; its choirs
  still have the omission order 0.3.0-0.4.1 used.
"""

import copy
import json
import shutil
from pathlib import Path

import pytest

from chordnotepad.audio.picker_factory import build_picker
from chordnotepad.constants import CONFIG_VERSION
from chordnotepad.models import voicing_versions as vv
from chordnotepad.models.ensemble_spec import (
    BUILTIN_ENSEMBLES, DEFAULT_WEIGHTS as ENSEMBLE_DEFAULTS, EnsembleSpec, expand_movement,
)
from chordnotepad.models.voicing_versions import VOICING_VERSION
from chordnotepad.services.appdata_service import AppDataService
from chordnotepad.services.config_service import ConfigService
from chordnotepad.session.bootstrap import build_core_services, create_session
from chordnotepad.session.host import HostDispatch
from chordnotepad.session.platform import ANDROID
from chordnotepad.session.settings_staging import SettingsStaging
from chordnotepad.session.testing import EventRecorder, FakePlayer, InMemoryDocumentStore, ManualHost
from chordnotepad.settings_forms.voicing_form import voicing_error

FIXTURES = Path(__file__).parent / "fixtures" / "configs"
ALL_FIXTURES = sorted(p.name for p in FIXTURES.glob("*.json"))


class _FakeAppData:
    def __init__(self, path: Path) -> None:
        self._path = path

    def get_config_file_path(self) -> Path:
        return self._path


def _install(tmp_path, fixture) -> Path:
    path = tmp_path / "settings.json"
    shutil.copyfile(FIXTURES / fixture, path)
    return path


def _load(tmp_path):
    return ConfigService(_FakeAppData(tmp_path / "settings.json")).load_config()


def _fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _backups(tmp_path):
    return sorted(p.name for p in tmp_path.glob("settings.json.bak-*"))


def _preset_weights(slug):
    return BUILTIN_ENSEMBLES[slug].weights


def _plays(name, entry):
    """The weights an ensemble voicing plays with (saved over the defaults)."""
    return EnsembleSpec.from_dict(name, entry).weights


def test_the_fixtures_are_all_here():
    assert ALL_FIXTURES == sorted([
        "between-builds-copy.json", "damaged-flipped.json", "tibi-shaped.json",
        "v0.2-legacy.json", "v0.4.1-damaged.json", "v0.4.1-first-session.json",
        "v0.5.4-copies.json", "v0.5.4-first-session.json"])


@pytest.mark.parametrize("fixture", ALL_FIXTURES)
def test_each_fixture_loads_migrates_and_builds(tmp_path, fixture):
    path = _install(tmp_path, fixture)
    original = path.read_bytes()
    config = _load(tmp_path)
    assert config.voicings
    for name, entry in config.voicings.items():
        assert entry["version"] == VOICING_VERSION, name
        assert voicing_error(name, entry) is None, name
        build_picker(name, entry)
    saved = json.loads(path.read_text())
    assert saved["version"] == CONFIG_VERSION
    assert saved["voicings"] == config.voicings
    # The file as it was is kept, once.
    [backup] = _backups(tmp_path)
    assert (tmp_path / backup).read_bytes() == original


@pytest.mark.parametrize("fixture", ALL_FIXTURES)
def test_a_second_load_leaves_the_file_byte_identical(tmp_path, fixture):
    path = _install(tmp_path, fixture)
    _load(tmp_path)
    migrated = path.read_bytes()
    second = _load(tmp_path)
    assert path.read_bytes() == migrated
    assert len(_backups(tmp_path)) == 1
    assert json.loads(migrated)["voicings"] == second.voicings


# -- v0.5.4 ------------------------------------------------------------------------------


@pytest.mark.parametrize("fixture", ["v0.5.4-copies.json", "v0.5.4-first-session.json"])
def test_v054_copies_get_their_link_and_the_presets_values(tmp_path, fixture):
    _install(tmp_path, fixture)
    v = _load(tmp_path).voicings
    links = {name: entry.get("based_on") for name, entry in v.items()}
    assert links == {
        "New Guitar (Standard - EADGBE)": "guitar:standard",
        "New Guitar (Drop D)": "guitar:drop_d",
        "New Guitar (DADGAD)": "guitar:dadgad",
        "New Guitar (Open G)": "guitar:open_g",
        "New Ukulele": "guitar:ukulele",
        "New Choir (SATB)": "ensemble:satb",
        "New Male Choir (TTBB)": "ensemble:ttbb",
        "New Treble Choir (SSA)": "ensemble:ssa",
        "New String Quartet": "ensemble:quartet",
        "Android Choir (SATB)": "ensemble:satb",
        "Android Male Choir (TTBB)": "ensemble:ttbb",
        "Android Treble Choir (SSA)": "ensemble:ssa",
        "Android String Quartet": "ensemble:quartet",
        "New Piano (default)": "piano",
    }

    # The quartet copies play the preset now; the user's leap penalty stays.
    for name, own in (("New String Quartet", {"leap_penalty": -3.0}),
                      ("Android String Quartet", {})):
        entry = v[name]
        assert entry["allow_unisons"] is False
        assert "bass_movement" not in entry["weights"]
        assert _plays(name, entry) == dict(copy.deepcopy(_preset_weights("quartet")), **own), name

    # The choirs: the user's leading tone (SATB) and inversion (TTBB) stay.
    satb = v["New Choir (SATB)"]["weights"]
    assert satb["leading_tone_resolution_bonus"] == 2.0
    assert satb["seventh_resolution_bonus"] == _preset_weights("satb")["seventh_resolution_bonus"]
    assert satb["inversion"] == _preset_weights("satb")["inversion"]
    ttbb = v["Android Male Choir (TTBB)"]["weights"]
    assert ttbb["inversion"] == {"root": 0.0, "first": -2.0, "second": -5.0, "third": -3.0}
    assert ttbb["leading_tone_resolution_bonus"] == _preset_weights("ttbb")[
        "leading_tone_resolution_bonus"]
    ssa = v["Android Treble Choir (SSA)"]
    assert _plays("ssa", ssa) == _preset_weights("ssa")
    # Movement: left as 0.5.4 saved it while it plays the preset's, else the
    # preset's per-voice list.
    preset = _preset_weights("ssa")
    voices = len(ssa["voices"])
    wanted = expand_movement(preset["movement"], preset["bass_movement"], voices)
    if wanted == expand_movement(-0.4, -0.15, voices):
        assert (ssa["weights"]["movement"], ssa["weights"]["bass_movement"]) == (-0.4, -0.15)
    else:
        assert ssa["weights"]["movement"] == list(wanted)

    # Fretboard and piano copies keep their values (their presets only gained keys).
    original = _fixture(fixture)["voicings"]
    for name in ("New Guitar (Standard - EADGBE)", "New Ukulele", "New Piano (default)"):
        assert {k: e for k, e in v[name].items() if k not in ("version", "based_on")} \
            == original[name]


def test_v054_round_trip_keeps_the_users_values(tmp_path):
    """0.5.4 editing a 0.6 voicing drops the fields it doesn't know (the
    version, the link and the weights added since); back in 0.6, 0->1 infers
    the link again and 1->2 restores the preset values. Only a value set on
    purpose to the 0.5.4 default would be lost (accepted)."""
    _install(tmp_path, "v0.5.4-copies.json")
    migrated = _load(tmp_path).voicings
    v054_weight_keys = set(vv._quartet_untouched()) - {
        "same_bass_penalty", "upper_spacing_threshold", "outer_leap_penalty",
        "middle_range_penalty", "hidden_perfect_penalty", "low_interval_limit_penalty",
        "allow_unisons"}
    edited = {}
    for name, entry in migrated.items():
        entry = {k: e for k, e in copy.deepcopy(entry).items() if k not in ("version", "based_on")}
        if entry["model"] == "ensemble":
            # 0.5.4's form writes each weight it knows, at the default if missing.
            entry["weights"] = {k: entry["weights"].get(k, copy.deepcopy(ENSEMBLE_DEFAULTS[k]))
                                for k in v054_weight_keys}
        edited[name] = entry
    data = _fixture("v0.5.4-copies.json")
    data["voicings"] = edited
    (tmp_path / "settings.json").write_text(json.dumps(data))
    for backup in tmp_path.glob("settings.json.bak-*"):
        backup.unlink()
    back = _load(tmp_path).voicings
    assert set(back) == set(migrated)
    for name, entry in back.items():
        if entry["model"] == "ensemble":
            assert _plays(name, entry) == _plays(name, migrated[name]), name
            assert (entry["based_on"], entry["allow_unisons"]) == (
                migrated[name]["based_on"], migrated[name]["allow_unisons"])
        else:
            assert entry == migrated[name], name
    assert back["New String Quartet"]["weights"]["leap_penalty"] == -3.0
    assert back["New Choir (SATB)"]["weights"]["leading_tone_resolution_bonus"] == 2.0


# -- damaged, between builds, Tibi-shaped, v0.2 ----------------------------------------


def test_the_damaged_file_gets_its_signs_back(tmp_path):
    _install(tmp_path, "damaged-flipped.json")
    v = _load(tmp_path).voicings
    guitar = v["My Guitar"]["weights"]
    for key in vv.FRETBOARD_NEGATED_KEYS:
        assert guitar[key] < 0, key
    assert guitar["span_penalty"] == -1.5 and guitar["interior_mute_penalty"] == -4.0
    assert v["My Guitar"]["based_on"] == "guitar:standard"
    choir = v["My Choir"]
    assert choir["based_on"] == "ensemble:satb"
    assert all(value < 0 for value in choir["weights"]["omit"].values())
    assert _plays("choir", choir) == _preset_weights("satb")


@pytest.mark.parametrize("fixture", ["v0.4.1-damaged.json", "v0.4.1-first-session.json"])
def test_v041_choirs_end_on_the_presets_omission_order(tmp_path, fixture):
    """0.3.0-0.4.1 choirs had the piano's omission order (root -4, fifth -8,
    extension -7). Flipped by the old v1 migration, then repaired, they come
    back to it, and must take the ensemble order as config v4 gave every
    undamaged one; then 1->2 makes them play the preset."""
    from chordnotepad.models.ensemble_spec import ENSEMBLE_OMIT_WEIGHTS
    _install(tmp_path, fixture)
    v = _load(tmp_path).voicings
    for name, slug in (("My SATB", "satb"), ("My TTBB", "ttbb")):
        assert v[name]["based_on"] == f"ensemble:{slug}"
        assert v[name]["weights"]["omit"] == ENSEMBLE_OMIT_WEIGHTS, name
        assert _plays(name, v[name]) == _preset_weights(slug), name
    guitar = v["My Guitar"]["weights"]
    assert guitar["span_penalty"] == -1.5 and guitar["interior_mute_penalty"] == -4.0
    assert all(guitar[key] < 0 for key in vv.FRETBOARD_NEGATED_KEYS)


def test_v041_first_session_is_not_flipped(tmp_path):
    """The hand-made guitar has one weight, so the 0->1 repair can't tell a
    flip from the user's choice: only the v<3-with-voicings rule (read as v3,
    no sign flip) keeps it right."""
    _install(tmp_path, "v0.4.1-first-session.json")
    v = _load(tmp_path).voicings
    assert v["Hand-made"]["weights"] == {"barre_penalty": -2.5}
    assert "based_on" not in v["Hand-made"]


def test_a_copy_from_a_build_in_between_takes_the_preset(tmp_path):
    _install(tmp_path, "between-builds-copy.json")
    v = _load(tmp_path).voicings
    strings = v["Strings"]
    assert strings["based_on"] == "ensemble:quartet"
    preset = _preset_weights("quartet")
    weights = strings["weights"]
    assert weights["leading_tone_resolution_bonus"] == preset["leading_tone_resolution_bonus"]
    assert weights["outer_leap_penalty"] == preset["outer_leap_penalty"] == -0.5
    assert weights["middle_range_penalty"] == preset["middle_range_penalty"] == -0.5
    assert weights["inversion"] == preset["inversion"]
    assert weights["seventh_resolution_bonus"] == preset["seventh_resolution_bonus"]
    assert weights["movement"] == preset["movement"]
    assert strings["allow_unisons"] is False
    assert v["Choir"]["weights"]["inversion"] == _preset_weights("satb")["inversion"]


def test_tibis_shaped_file(tmp_path):
    _install(tmp_path, "tibi-shaped.json")
    original = _fixture("tibi-shaped.json")["voicings"]
    v = _load(tmp_path).voicings
    quartet = v["New String Quartet"]
    assert quartet["based_on"] == "ensemble:quartet"
    # Its values match the current quartet already: 1->2 changes nothing.
    assert {k: e for k, e in quartet.items() if k not in ("version", "based_on")} \
        == original["New String Quartet"]
    for name in ("7-string", "D tuning", "New voicing"):
        assert "based_on" not in v[name], name
        assert {k: e for k, e in v[name].items() if k != "version"} == original[name]


def test_the_v02_file_becomes_voicings_without_links(tmp_path):
    _install(tmp_path, "v0.2-legacy.json")
    config = _load(tmp_path)
    assert config.voicing == "voicing:Drop D"
    assert config.key == "G" and config.notation == "european"
    assert config.voicings == {
        "Drop D": {"model": "fretboard", "tuning": ["D2", "A2", "D3", "G3", "B3", "E4"],
                   "version": VOICING_VERSION},
        "Mandolin": {"model": "fretboard", "tuning": ["G3", "D4", "A4", "E5"],
                     "version": VOICING_VERSION},
    }


def test_android_writes_nothing_after_a_migrated_load(tmp_path):
    config_dir = tmp_path / "config" / "chord-notepad"
    config_dir.mkdir(parents=True)
    shutil.copyfile(FIXTURES / "v0.5.4-copies.json", config_dir / "settings.json")
    host = ManualHost()
    services = build_core_services(AppDataService(root=tmp_path), HostDispatch(host),
                                   player=FakePlayer())
    path = config_dir / "settings.json"
    migrated = path.read_bytes()
    session = create_session(host, services, InMemoryDocumentStore(), chord_sheet=False,
                             platform=ANDROID)
    session.subscribe(EventRecorder())
    session.start()
    session.begin_settings_edit()
    session.commit_settings(None, invalid_numbers={})
    assert path.read_bytes() == migrated
    assert len(list(config_dir.glob("settings.json.bak-*"))) == 1


def test_a_staged_voicing_from_before_the_change_migrates(tmp_path):
    staging = SettingsStaging(tmp_path / "settings-staged.json")
    quartet = copy.deepcopy(_fixture("v0.5.4-copies.json")["voicings"]["New String Quartet"])
    quartet["weights"]["unison_penalty"] = "abc"   # the wrong value it was staged for
    staging.path.write_text(json.dumps({"version": 1, "voicings": {"Q": quartet},
                                        "numbers": {}}))
    voicings, _ = staging.load()
    entry = voicings["Q"]
    assert entry["version"] == VOICING_VERSION and entry["based_on"] == "ensemble:quartet"
    assert entry["weights"]["unison_penalty"] == "abc"
    assert entry["weights"]["leading_tone_resolution_bonus"] == _preset_weights("quartet")[
        "leading_tone_resolution_bonus"]


# -- each migration on its own ---------------------------------------------------------


def _quartet_v1(**weights):
    """A version-1 copy of the String Quartet, with only ``weights``."""
    entry = {"model": "ensemble", "label": "String Quartet", "based_on": "ensemble:quartet",
             "version": 1, "voices": copy.deepcopy(BUILTIN_ENSEMBLES["quartet"].to_dict()["voices"]),
             "weights": weights}
    return entry


def _quartet_at_preset(**weights):
    """A version-1 copy holding every preset value but ``weights``."""
    preset = copy.deepcopy(BUILTIN_ENSEMBLES["quartet"].to_dict())
    preset["weights"].pop("bass_movement")
    preset["weights"].update(copy.deepcopy(weights))
    return dict(preset, model="ensemble", based_on="ensemble:quartet", version=1)


@pytest.mark.parametrize("key", [k for k in vv.UNTOUCHED_PRESET_VALUES["quartet"]
                                 if k not in ("allow_unisons", "movement", "bass_movement")])
def test_1_to_2_moves_each_untouched_value_and_nothing_else(key):
    target = _preset_weights("quartet")[key]
    for untouched in vv.UNTOUCHED_PRESET_VALUES["quartet"][key]:
        entry = _quartet_at_preset(**{key: copy.deepcopy(untouched)})
        changed = vv._migrate_1_to_2(entry)
        assert entry["weights"][key] == target
        assert changed == (untouched != target)
        once = copy.deepcopy(entry)
        assert vv._migrate_1_to_2(entry) is False and entry == once
    # A value the user set stays.
    own = {r: v - 1.0 for r, v in target.items()} if isinstance(target, dict) else target + 0.25
    entry = _quartet_at_preset(**{key: copy.deepcopy(own)})
    assert vv._migrate_1_to_2(entry) is False and entry["weights"][key] == own


def test_1_to_2_absent_keys_take_the_preset_where_it_differs_from_the_default():
    entry = _quartet_v1()
    del entry["weights"]
    assert vv._migrate_1_to_2(entry) is True
    preset = _preset_weights("quartet")
    assert entry["allow_unisons"] is False
    for key, value in preset.items():
        if key == "bass_movement":
            continue
        if value == ENSEMBLE_DEFAULTS[key]:
            assert key not in entry["weights"], key
        else:
            assert entry["weights"][key] == value, key


def test_1_to_2_movement_shapes():
    preset = _preset_weights("quartet")
    for movement, bass, voices in ((-0.4, -0.15, 4), (-0.4, None, 4),
                                   ([-0.4, -0.4, -0.4, -0.15], None, 4),
                                   (-0.4, -0.15, 5), ([-0.4] * 4 + [-0.15], None, 5)):
        entry = _quartet_v1(movement=movement)
        if bass is not None:
            entry["weights"]["bass_movement"] = bass
        entry["voices"] = (entry["voices"] * 2)[:voices]
        assert vv._migrate_1_to_2(entry) is True
        assert entry["weights"]["movement"] == list(expand_movement(preset["movement"],
                                                                    preset["bass_movement"],
                                                                    voices))
        assert "bass_movement" not in entry["weights"]
    for movement, bass in ((-0.5, -0.15), (-0.4, -0.3), ([-0.8, -0.5, -0.4, -0.15], None)):
        entry = _quartet_v1(movement=movement)
        if bass is not None:
            entry["weights"]["bass_movement"] = bass
        before = copy.deepcopy(entry)
        vv._migrate_1_to_2(entry)
        assert entry["weights"]["movement"] == before["weights"]["movement"]


def test_1_to_2_inversion_is_all_or_nothing():
    entry = _quartet_v1(inversion={"first": -1.5, "second": -5.0})
    vv._migrate_1_to_2(entry)
    assert entry["weights"]["inversion"] == _preset_weights("quartet")["inversion"]
    mixed = {"root": 0.0, "first": -1.5, "second": -6.0, "third": -3.0}
    entry = _quartet_v1(inversion=dict(mixed))
    vv._migrate_1_to_2(entry)
    assert entry["weights"]["inversion"] == mixed


def test_1_to_2_allow_unisons_and_scope():
    entry = _quartet_v1()
    entry["allow_unisons"] = True
    vv._migrate_1_to_2(entry)
    assert entry["allow_unisons"] is False
    for based_on in (None, "guitar:standard", "ensemble:nope", "piano", 3):
        entry = _quartet_v1(leading_tone_resolution_bonus=1.5)
        entry["based_on"] = based_on
        assert vv._migrate_1_to_2(entry) is False
        assert entry["weights"]["leading_tone_resolution_bonus"] == 1.5
    junk = _quartet_v1(leading_tone_resolution_bonus="x", movement="y")
    vv._migrate_1_to_2(junk)
    assert junk["weights"]["leading_tone_resolution_bonus"] == "x"
    assert junk["weights"]["movement"] == "y"


def test_0_to_1_infers_links_only_from_label_and_tuning():
    def link(entry):
        vv._migrate_0_to_1(entry)
        return entry.get("based_on")

    standard = "Guitar (Standard - EADGBE)"
    assert link({"model": "fretboard", "label": standard,
                 "tuning": [40, 45, 50, 55, 59, 64]}) == "guitar:standard"
    assert link({"model": "fretboard", "label": standard,
                 "tuning": ["E2", "A2", "D3", "G3", "B3", "E4"]}) == "guitar:standard"
    assert link({"model": "fretboard", "label": standard,
                 "tuning": [35, 40, 45, 50, 55, 59, 64]}) is None
    assert link({"model": "fretboard", "tuning": [40, 45, 50, 55, 59, 64]}) is None
    assert link({"model": "fretboard", "label": standard, "tuning": "junk"}) is None
    assert link({"model": "ensemble", "label": "String Quartet", "voices": []}) \
        == "ensemble:quartet"
    assert link({"model": "ensemble", "label": "My Quartet"}) is None
    assert link({"model": "ensemble", "voices": BUILTIN_ENSEMBLES["satb"].to_dict()["voices"]}) \
        is None
    assert link({"model": "piano", "label": "Grand Piano"}) == "piano"
    assert link({"model": "piano"}) is None
    assert link({"model": "fretboard", "label": "String Quartet"}) is None
    kept = {"model": "ensemble", "label": "String Quartet", "based_on": "ensemble:satb"}
    vv._migrate_0_to_1(kept)
    assert kept["based_on"] == "ensemble:satb"


def _flipped_guitar(**weights):
    base = {key: 1.0 for key in vv.FRETBOARD_NEGATED_KEYS}
    base.update(weights)
    return {"model": "fretboard", "tuning": [40, 45, 50, 55, 59, 64], "weights": base}


def test_0_to_1_repairs_a_flipped_fretboard_and_leaves_mixed_ones():
    entry = _flipped_guitar(interior_mute_penalty=4.0, bass_note_bonus=8.0)
    assert vv._migrate_0_to_1(entry) is True
    assert entry["weights"]["interior_mute_penalty"] == -4.0
    assert entry["weights"]["bass_note_bonus"] == 8.0
    assert all(entry["weights"][key] < 0 for key in vv.FRETBOARD_NEGATED_KEYS)
    # Twice: a no-op.
    once = copy.deepcopy(entry)
    assert vv._migrate_0_to_1(entry) is False and entry == once
    # Two positive penalties, the rest negative: a user's own, left alone.
    mixed = _flipped_guitar(span_penalty=-1.2, position_penalty=-0.6,
                            fretted_finger_penalty=-0.5, barre_penalty=-1.0)
    before = copy.deepcopy(mixed)
    assert vv._migrate_0_to_1(mixed) is False and mixed == before
    # One missing: left alone.
    partial = _flipped_guitar()
    del partial["weights"]["movement_penalty"]
    before = copy.deepcopy(partial)
    assert vv._migrate_0_to_1(partial) is False and partial == before


def test_0_to_1_repairs_a_flipped_ensemble():
    entry = {"model": "ensemble", "voices": [], "weights": {
        "omit": {"root": 20.0, "third": 40.0}, "movement": [0.4, 0.15], "leap_penalty": 2.0,
        "common_tone_bonus": 1.5, "unison_penalty": -0.5}}
    assert vv._migrate_0_to_1(entry) is True
    w = entry["weights"]
    assert w["omit"] == {"root": -20.0, "third": -40.0}
    assert w["movement"] == [-0.4, -0.15] and w["leap_penalty"] == -2.0
    assert w["common_tone_bonus"] == 1.5 and w["unison_penalty"] == -0.5
    once = copy.deepcopy(entry)
    assert vv._migrate_0_to_1(entry) is False and entry == once
    mixed = {"model": "ensemble", "weights": {"omit": {"root": 20.0, "third": -40.0},
                                               "leap_penalty": 2.0}}
    before = copy.deepcopy(mixed)
    assert vv._migrate_0_to_1(mixed) is False and mixed == before


def test_migrate_voicing_runs_each_step_once():
    entry = _quartet_v1(leading_tone_resolution_bonus=1.5)
    entry["version"] = 0
    del entry["based_on"]
    assert vv.migrate_voicing(entry) is True
    assert entry["based_on"] == "ensemble:quartet" and entry["version"] == VOICING_VERSION
    once = copy.deepcopy(entry)
    assert vv.migrate_voicing(entry) is False and entry == once
    # A newer release's voicing is never touched.
    newer = _quartet_v1(leading_tone_resolution_bonus=1.5)
    newer["version"] = VOICING_VERSION + 1
    before = copy.deepcopy(newer)
    assert vv.migrate_voicing(newer) is False and newer == before


def test_the_negated_keys_are_the_ones_the_old_migration_flipped():
    from chordnotepad.services import config_service
    assert config_service._FRETBOARD_NEGATE_KEYS == vv.FRETBOARD_NEGATED_KEYS
    assert config_service._ENSEMBLE_NEGATE_FLAT_KEYS == vv.ENSEMBLE_NEGATED_FLAT_KEYS


def test_the_untouched_sets_hold_the_v054_defaults():
    """Frozen from ``git show v0.5.4:src/models/ensemble_spec.py``."""
    v054 = {
        'movement': -0.4, 'bass_movement': -0.15, 'leap_penalty': -2.0,
        'octave_leap_penalty': -6.0, 'tritone_leap_penalty': -3.0, 'common_tone_bonus': 1.5,
        'parallel_perfect_penalty': -25.0, 'contrary_motion_bonus': 0.8,
        'seventh_resolution_bonus': 1.5, 'leading_tone_resolution_bonus': 1.5,
        'double_leading_tone_penalty': -8.0,
        'doubling': {'root': 2.0, 'fifth': 0.5, 'third': -2.0, 'seventh': -6.0,
                     'color': -6.0, 'extension': -6.0},
        'omit': {'root': -20.0, 'third': -40.0, 'fifth': -3.0, 'seventh': -40.0,
                 'color': -30.0, 'extension': -6.0},
        'inversion': {'root': 0.0, 'first': -1.5, 'second': -5.0, 'third': -3.0},
        'range_comfort_penalty': -0.5, 'unison_penalty': -0.5, 'upper_spacing_penalty': -0.15,
    }
    for slug, sets in vv.UNTOUCHED_PRESET_VALUES.items():
        assert sets["allow_unisons"][0] is True
        for key, value in v054.items():
            assert sets[key][0] == value, (slug, key)
        # Every weight of the preset has a set (a key added later: its added default).
        assert set(_preset_weights(slug)) <= set(sets), slug


def test_0_to_1_repairs_a_flipped_voicing_with_a_penalty_at_0():
    entry = _flipped_guitar(stretch_penalty=-0.7, barre_penalty=0.0)
    assert vv._migrate_0_to_1(entry) is True
    w = entry["weights"]
    assert w["barre_penalty"] == 0.0 and w["span_penalty"] == -1.0
    assert all(w[key] <= 0 for key in vv.FRETBOARD_NEGATED_KEYS)
    zeros = _flipped_guitar(**{key: 0.0 for key in vv.FRETBOARD_NEGATED_KEYS})
    before = copy.deepcopy(zeros)
    assert vv._migrate_0_to_1(zeros) is False and zeros == before
    choir = {"model": "ensemble", "weights": {"omit": {"root": 20.0, "fifth": 0.0},
                                              "leap_penalty": 2.0}}
    assert vv._migrate_0_to_1(choir) is True
    assert choir["weights"] == {"omit": {"root": -20.0, "fifth": 0.0}, "leap_penalty": -2.0}


def test_0_to_1_moves_a_repaired_old_omission_order_to_the_ensemble_order():
    from chordnotepad.models.ensemble_spec import (
        ENSEMBLE_OMIT_WEIGHTS, PREVIOUS_ENSEMBLE_OMIT_WEIGHTS,
    )
    flipped = {role: -value for role, value in PREVIOUS_ENSEMBLE_OMIT_WEIGHTS.items()}
    entry = {"model": "ensemble", "weights": {"omit": dict(flipped)}}
    assert vv._migrate_0_to_1(entry) is True
    assert entry["weights"]["omit"] == ENSEMBLE_OMIT_WEIGHTS
    # One role changed by the user: repaired, and left in its order.
    tuned = dict(flipped, root=5.0)
    entry = {"model": "ensemble", "weights": {"omit": dict(tuned)}}
    vv._migrate_0_to_1(entry)
    assert entry["weights"]["omit"] == {role: -value for role, value in tuned.items()}


def _failing_1_to_2(entry):
    raise RuntimeError("a migration bug")


def test_a_staged_voicing_whose_migration_fails_is_kept_as_staged(tmp_path):
    from unittest.mock import patch
    staging = SettingsStaging(tmp_path / "settings-staged.json")
    quartet = copy.deepcopy(_fixture("v0.5.4-copies.json")["voicings"]["New String Quartet"])
    staging.path.write_text(json.dumps({"version": 1, "voicings": {"Q": quartet},
                                        "numbers": {}}))
    with patch.object(vv, "MIGRATIONS", (vv._migrate_0_to_1, _failing_1_to_2)):
        voicings, _ = staging.load()
    assert voicings["Q"] == quartet


def test_a_rebuild_from_an_unmigrated_base_migrates_a_copy_first():
    from chordnotepad.settings_forms import voicing_form as vf
    base = copy.deepcopy(_fixture("v0.5.4-copies.json")["voicings"]["New String Quartet"])
    values = vf.values_from_voicing("ensemble", base)
    out = vf.voicing_from_values("ensemble", values, base["label"], base=base)
    assert out["based_on"] == "ensemble:quartet" and out["version"] == VOICING_VERSION
    with __import__("unittest.mock").mock.patch.object(
            vv, "MIGRATIONS", (vv._migrate_0_to_1, _failing_1_to_2)):
        out = vf.voicing_from_values("ensemble", values, base["label"], base=base)
    # Not stamped as current: the next load tries the migration again.
    assert out["version"] == 0 and "based_on" not in out


def test_an_edit_of_a_voicing_whose_migration_failed_keeps_its_version(tmp_path):
    from unittest.mock import patch
    from chordnotepad.session.platform import DESKTOP_QT
    config_dir = tmp_path / "config" / "chord-notepad"
    config_dir.mkdir(parents=True)
    shutil.copyfile(FIXTURES / "v0.5.4-copies.json", config_dir / "settings.json")
    with patch.object(vv, "MIGRATIONS", (vv._migrate_0_to_1, _failing_1_to_2)):
        host = ManualHost()
        services = build_core_services(AppDataService(root=tmp_path), HostDispatch(host),
                                       player=FakePlayer())
        assert "version" not in services.config.config.voicings["New String Quartet"]
        session = create_session(host, services, InMemoryDocumentStore(), chord_sheet=False,
                                 platform=DESKTOP_QT)
        session.subscribe(EventRecorder())
        session.start()
        session.begin_settings_edit()
        session.select_voicing("New String Quartet")
        session.set_voicing_values({"weight:leap_penalty": "-2.75"})
        session.add_voicing_from("custom", "New String Quartet")
        working = session._settings_edit.model.get_voicings()
        for name in ("New String Quartet", "New New String Quartet"):
            assert working[name]["version"] == 0, name
        assert working["New String Quartet"]["weights"]["leap_penalty"] == -2.75
