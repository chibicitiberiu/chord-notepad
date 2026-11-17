"""Settings safety: a load never costs the user their settings file.

* A new config is saved at the current version (a v1 file was migrated at the
  next start, which flipped the signs of voicings made in between).
* An unusable value reads as its own default; the other settings stay.
* A migrated or repaired file is backed up before it is first replaced.
* A file that can't be read is renamed aside and the app starts on the
  defaults, with a notice; a failed save never resets or renames.
* Keys a newer release wrote survive, and so does its higher version.
"""

import json
import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from chordnotepad.constants import CONFIG_VERSION
from chordnotepad.exceptions import ConfigurationError
from chordnotepad.models.config import Config
from chordnotepad.models.voicing_versions import VOICING_VERSION
from chordnotepad.services import config_service as config_service_module
from chordnotepad.services.appdata_service import AppDataService
from chordnotepad.services.config_service import ConfigService, effective_version
from chordnotepad.session import formatting
from chordnotepad.session.bootstrap import build_core_services, create_session
from chordnotepad.session.events import UserError
from chordnotepad.session.host import HostDispatch
from chordnotepad.session.testing import EventRecorder, FakePlayer, InMemoryDocumentStore, ManualHost


class _FakeAppData:
    def __init__(self, path: Path) -> None:
        self._path = path

    def get_config_file_path(self) -> Path:
        return self._path


def _path(tmp_path) -> Path:
    return tmp_path / "settings.json"


def _service(tmp_path) -> ConfigService:
    return ConfigService(_FakeAppData(_path(tmp_path)))


def _write(tmp_path, data) -> Path:
    path = _path(tmp_path)
    path.write_text(data if isinstance(data, str) else json.dumps(data, indent=2),
                    encoding="utf-8")
    return path


def _backups(tmp_path, label="bak"):
    return sorted(p for p in tmp_path.iterdir() if p.name.startswith(f"settings.json.{label}-"))


#: A guitar a user made, with signed weights as every release since 0.3 saves
#: them, at this release's voicing version (so no voicing migration touches it).
_GUITAR = {"model": "fretboard", "tuning": [40, 45, 50, 55, 59, 64], "label": "Mine",
           "weights": {"span_penalty": -1.5, "barre_penalty": -1.0, "bass_note_bonus": 8.0},
           "version": VOICING_VERSION}


# -- the version a config is saved at -----------------------------------------------


def test_a_new_config_is_saved_at_the_current_version(tmp_path):
    service = _service(tmp_path)
    service.load_config()
    assert json.loads(_path(tmp_path).read_text())["version"] == CONFIG_VERSION
    assert Config().version == CONFIG_VERSION
    assert Config().to_dict()["version"] == CONFIG_VERSION


def test_reset_to_defaults_saves_the_current_version_after_a_backup(tmp_path):
    original = _write(tmp_path, {"version": CONFIG_VERSION, "bpm": 99,
                                 "voicings": {"Mine": _GUITAR}}).read_bytes()
    service = _service(tmp_path)
    service.load_config()
    service.reset_to_defaults()
    saved = json.loads(_path(tmp_path).read_text())
    assert saved["version"] == CONFIG_VERSION and saved["voicings"] == {}
    [backup] = _backups(tmp_path)
    assert backup.name.startswith(f"settings.json.bak-v{CONFIG_VERSION}-")
    assert backup.read_bytes() == original


def test_a_new_voicing_keeps_its_weights_across_two_restarts(tmp_path):
    """The first start used to save version 1, so the second start negated
    the penalties of a voicing made in the first session."""
    first = _service(tmp_path)
    first.load_config()
    first.config.voicings["Mine"] = json.loads(json.dumps(_GUITAR))
    first.save_config()
    for _ in range(2):
        service = _service(tmp_path)
        assert service.load_config().voicings["Mine"] == _GUITAR
    assert json.loads(_path(tmp_path).read_text())["voicings"]["Mine"] == _GUITAR


def test_a_file_saved_as_v1_with_voicings_is_not_flipped(tmp_path):
    """A 0.3-0.5.4 file still at version 1 has signed voicings: it is read as
    version 3, so no sign flip, and backed up before it is rewritten."""
    original = _write(tmp_path, {"version": 1, "voicings": {"Mine": _GUITAR}}).read_bytes()
    service = _service(tmp_path)
    assert service.load_config().voicings["Mine"] == _GUITAR
    saved = json.loads(_path(tmp_path).read_text())
    assert saved["version"] == CONFIG_VERSION and saved["voicings"]["Mine"] == _GUITAR
    [backup] = _backups(tmp_path)
    assert backup.name.startswith("settings.json.bak-v1-") and backup.read_bytes() == original


def test_effective_version():
    assert effective_version({"voicings": {}}, 1) == 3
    assert effective_version({"voicings": {}}, 2) == 3
    assert effective_version({"voicings": {}}, 3) == 3
    assert effective_version({"custom_tunings": {}}, 1) == 1
    assert effective_version({"voicings": []}, 1) == 1
    assert effective_version({"voicings": {}}, 4) == 4


def test_a_v02_file_with_custom_tunings_still_migrates(tmp_path):
    _write(tmp_path, {"version": 1, "voicing": "guitar:Drop D",
                      "custom_tunings": {"Drop D": ["D2", "A2", "D3", "G3", "B3", "E4"]}})
    config = _service(tmp_path).load_config()
    assert config.voicings == {"Drop D": {"model": "fretboard",
                                          "tuning": ["D2", "A2", "D3", "G3", "B3", "E4"],
                                          "version": VOICING_VERSION}}
    assert config.voicing == "voicing:Drop D"
    saved = json.loads(_path(tmp_path).read_text())
    assert "custom_tunings" not in saved and saved["version"] == CONFIG_VERSION
    assert len(_backups(tmp_path)) == 1


@pytest.mark.parametrize("raw", ["3", 4.0, True, [4], {"v": 4}])
def test_a_version_that_isnt_an_int_reads_as_1(tmp_path, raw, caplog):
    _write(tmp_path, {"version": raw, "bpm": 99, "voicings": {"Mine": _GUITAR}})
    with caplog.at_level(logging.WARNING):
        config = _service(tmp_path).load_config()
    assert "not a whole number" in caplog.text
    assert config.bpm == 99
    # Read as 1, and having voicings, as 3: no sign flip.
    assert config.voicings["Mine"] == _GUITAR
    assert json.loads(_path(tmp_path).read_text())["version"] == CONFIG_VERSION


def test_a_newer_version_is_kept_and_not_migrated(tmp_path):
    data = {"version": CONFIG_VERSION + 1, "bpm": 99, "voicings": {"Mine": _GUITAR},
            "a_new_setting": {"x": [1, 2]}}
    original = _write(tmp_path, data).read_bytes()
    service = _service(tmp_path)
    config = service.load_config()
    assert config.version == CONFIG_VERSION + 1
    assert _path(tmp_path).read_bytes() == original  # nothing to migrate: not rewritten
    service.set("bpm", 100)
    service.save_config()
    saved = json.loads(_path(tmp_path).read_text())
    assert saved["version"] == CONFIG_VERSION + 1
    assert saved["a_new_setting"] == {"x": [1, 2]}
    assert saved["voicings"]["Mine"] == _GUITAR
    assert _backups(tmp_path) == []


# -- unknown keys -------------------------------------------------------------------


def test_unknown_top_level_keys_survive_a_save(tmp_path):
    _write(tmp_path, {"version": CONFIG_VERSION, "future_key": 7, "other": [None, "x"]})
    service = _service(tmp_path)
    service.load_config()
    assert service.config.extra == {"future_key": 7, "other": [None, "x"]}
    service.set("bpm", 130)
    service.save_config()
    saved = json.loads(_path(tmp_path).read_text())
    assert saved["future_key"] == 7 and saved["other"] == [None, "x"]
    # They come after the keys this release writes.
    assert list(saved)[-2:] == ["future_key", "other"]
    assert list(saved)[:-2] == list(Config().to_dict())


def test_the_legacy_keys_are_consumed_not_kept(tmp_path):
    config = Config.from_dict({"custom_tunings": {"T": ["E2"]},
                               "custom_ensembles": {"E": {"voices": [{"name": "S",
                                                                      "range": [60, 72]}]}}})
    assert config.extra == {}
    assert set(config.voicings) == {"T", "E"}


# -- values that can't be used ------------------------------------------------------


_DEFAULTS = Config()


@pytest.mark.parametrize("key, bad", [
    ("bpm", 500), ("bpm", "fast"), ("bpm", True), ("bpm", None),
    ("bpm_multiplier", 9.0), ("bpm_multiplier", "x"),
    ("font_size", 200), ("font_size", "11"),
    ("notation", "german"), ("notation", ["american"]),
    ("log_level", "LOUD"), ("log_level", 10),
    ("instrument", 128), ("instrument", -1), ("instrument", 1.5),
    ("default_octave", "4"), ("default_octave", 12),
    ("bass_octave", None),
    ("time_signature_beats", 0), ("time_signature_beats", 17), ("time_signature_beats", 4.0),
    ("time_signature_unit", 3), ("time_signature_unit", True),
    ("max_recent_files", 0), ("max_recent_files", 51), ("max_recent_files", "10"),
    ("key", 5),
])
def test_an_unusable_value_reads_as_its_default_and_keeps_the_rest(key, bad):
    data = {"version": CONFIG_VERSION, "bpm": 99, "font_size": 14, "notation": "european",
            "instrument": 24, "time_signature_beats": 3, "max_recent_files": 20,
            "voicings": {"Mine": _GUITAR}, "voicing": "voicing:Mine"}
    kept = dict(data)
    data[key] = bad
    config = Config.from_dict(data)
    assert getattr(config, key) == getattr(_DEFAULTS, key)
    assert config.needs_backup
    for other, value in kept.items():
        if other not in (key, "version"):
            assert getattr(config, other) == value, other
    config.validate()


def test_usable_values_are_kept_without_a_backup():
    data = {"bpm": 20, "bpm_multiplier": 0.125, "font_size": 72, "notation": "european",
            "log_level": "DEBUG", "instrument": 127, "default_octave": 0, "bass_octave": 2,
            "time_signature_beats": 16, "time_signature_unit": 8, "max_recent_files": 50,
            "key": "Sol", "bpm_float": None}
    config = Config.from_dict(data)
    assert not config.needs_backup
    assert (config.bpm, config.time_signature_unit, config.key) == (20, 8, "G")
    assert Config.from_dict({"bpm": 97.5}).bpm == 97.5  # validate() always took a float


def test_voicing_registry_junk_is_dropped_entry_by_entry():
    config = Config.from_dict({"voicing": 3, "voicings": {"Mine": _GUITAR, "Bad": "x",
                                                          "Worse": [1]}})
    assert config.voicing == "piano"
    assert config.voicings == {"Mine": _GUITAR}
    assert config.needs_backup
    config = Config.from_dict({"voicings": ["not", "a", "mapping"]})
    assert config.voicings == {} and config.needs_backup
    config = Config.from_dict({"custom_tunings": "x", "custom_ensembles": {"E": 1}})
    assert config.voicings == {} and config.needs_backup


def test_recent_files_junk_is_dropped():
    config = Config.from_dict({"recent_files": ["a.txt", 3, None, "b.txt"]})
    assert config.recent_files == ["a.txt", "b.txt"] and config.needs_backup
    config = Config.from_dict({"recent_files": 7})
    assert config.recent_files == [] and config.needs_backup
    config.validate()


def test_bpm_500_keeps_every_other_setting_and_backs_the_file_up(tmp_path):
    data = {"version": CONFIG_VERSION, "bpm": 500, "font_size": 15, "notation": "european",
            "voicing": "voicing:Mine", "voicings": {"Mine": _GUITAR},
            "recent_files": ["/songs/a.txt"]}
    original = _write(tmp_path, data).read_bytes()
    service = _service(tmp_path)
    config = service.load_config()
    assert config.bpm == 120
    assert (config.font_size, config.notation, config.voicing) == (15, "european", "voicing:Mine")
    assert config.voicings == {"Mine": _GUITAR} and config.recent_files == ["/songs/a.txt"]
    # Nothing migrated, so nothing is written at load; the next save backs up first.
    assert _path(tmp_path).read_bytes() == original and _backups(tmp_path) == []
    service.save_config()
    [backup] = _backups(tmp_path)
    assert backup.name.startswith(f"settings.json.bak-v{CONFIG_VERSION}-")
    assert backup.read_bytes() == original
    assert json.loads(_path(tmp_path).read_text())["voicings"] == {"Mine": _GUITAR}
    # Once per run.
    service.save_config()
    assert len(_backups(tmp_path)) == 1


# -- files that can't be read -------------------------------------------------------


@pytest.mark.parametrize("text", ['{"version": 4, "bpm": 9', "[1, 2]", '"settings"', "",
                                  b"\xff\xfe{".decode("latin-1")])
def test_an_unreadable_file_is_renamed_and_the_defaults_are_used(tmp_path, text):
    path = _path(tmp_path)
    path.write_bytes(text.encode("latin-1"))
    service = _service(tmp_path)
    config = service.load_config()
    assert config == Config()
    [kept] = _backups(tmp_path, "corrupt")
    assert kept.read_bytes() == text.encode("latin-1")
    assert service.load_notice == (
        "Settings couldn't be read. The app started with default settings; "
        f"the old file was kept as {kept.name}.")
    assert service.take_load_notice() and service.load_notice is None
    service.save_config()
    assert kept.read_bytes() == text.encode("latin-1")
    assert json.loads(path.read_text())["version"] == CONFIG_VERSION


def test_a_failure_inside_from_dict_sets_the_file_aside(tmp_path):
    original = _write(tmp_path, {"version": CONFIG_VERSION, "bpm": 99}).read_bytes()
    with patch.object(Config, "from_dict", side_effect=RuntimeError("boom")):
        service = _service(tmp_path)
        assert service.load_config() == Config()
    [kept] = _backups(tmp_path, "corrupt")
    assert kept.read_bytes() == original and service.load_notice


def test_an_unreadable_file_that_cant_be_moved_is_never_overwritten(tmp_path):
    path = _path(tmp_path)
    path.write_text("{broken")
    with patch.object(config_service_module.os, "replace", side_effect=OSError("busy")), \
            patch.object(config_service_module.shutil, "copyfile", side_effect=OSError("full")):
        service = _service(tmp_path)
        service.load_config()
        assert service.load_notice
        with patch.object(config_service_module.shutil, "copyfileobj",
                          side_effect=OSError("full")):
            with pytest.raises(ConfigurationError, match="back up"):
                service.save_config()
    assert path.read_text() == "{broken"


def test_the_session_shows_the_notice_once_at_startup(tmp_path):
    config_dir = tmp_path / "config" / "chord-notepad"
    config_dir.mkdir(parents=True)
    (config_dir / "settings.json").write_text('{"bpm": 1')
    host = ManualHost()
    services = build_core_services(AppDataService(root=tmp_path), HostDispatch(host),
                                   player=FakePlayer())
    session = create_session(host, services, InMemoryDocumentStore(), chord_sheet=False)
    recorder = EventRecorder()
    session.subscribe(recorder)
    session.start()
    [error] = [e for e in recorder.of_type(UserError) if e.title == formatting.SETTINGS_TITLE]
    [kept] = list(config_dir.glob("settings.json.corrupt-*"))
    assert error.message == ("Settings couldn't be read. The app started with default "
                             f"settings; the old file was kept as {kept.name}.")
    assert services.config.load_notice is None


def test_a_readable_file_gives_no_notice(tmp_path):
    _write(tmp_path, {"version": CONFIG_VERSION})
    service = _service(tmp_path)
    service.load_config()
    assert service.load_notice is None and service.take_load_notice() is None


# -- saves that fail ----------------------------------------------------------------


def _fail_json_dump(*_args, **_kwargs):
    raise OSError("disk full")


def test_a_failed_save_during_migration_neither_resets_nor_renames(tmp_path):
    data = {"version": 1, "bpm": 99, "voicings": {"Mine": _GUITAR}}
    original = _write(tmp_path, data).read_bytes()
    with patch.object(config_service_module.json, "dump", side_effect=_fail_json_dump):
        service = _service(tmp_path)
        config = service.load_config()
    assert config.bpm == 99 and config.voicings == {"Mine": _GUITAR}
    assert _path(tmp_path).read_bytes() == original
    assert _backups(tmp_path, "corrupt") == [] and service.load_notice is None
    # The backup was made before the write failed.
    [backup] = _backups(tmp_path)
    assert backup.read_bytes() == original


def test_the_exit_save_makes_the_backup_when_the_load_save_failed(tmp_path):
    data = {"version": 2, "bpm": 99, "voicings": {"Mine": _GUITAR}}
    original = _write(tmp_path, data).read_bytes()
    with patch.object(config_service_module.shutil, "copyfileobj",
                      side_effect=OSError("disk full")):
        service = _service(tmp_path)
        service.load_config()
    # The backup failed, so the migrated file wasn't written.
    assert _path(tmp_path).read_bytes() == original and _backups(tmp_path) == []
    service.save_config()  # the exit save
    [backup] = _backups(tmp_path)
    assert backup.name.startswith("settings.json.bak-v2-") and backup.read_bytes() == original
    saved = json.loads(_path(tmp_path).read_text())
    assert saved["version"] == CONFIG_VERSION and saved["bpm"] == 99


def test_a_backup_never_replaces_a_file_already_there(tmp_path):
    original = _write(tmp_path, {"version": 3, "voicings": {}}).read_bytes()
    foreign = tmp_path / "settings.json.bak-v3-20260101-000000"
    foreign.write_text("mine, not the app's")
    other = tmp_path / "settings.json.bak-before-upgrade"
    other.write_text("also mine")
    with patch.object(config_service_module, "backup_name",
                      return_value="settings.json.bak-v3-20260101-000000"):
        _service(tmp_path).load_config()
    assert foreign.read_text() == "mine, not the app's"
    assert other.read_text() == "also mine"
    assert (tmp_path / "settings.json.bak-v3-20260101-000000-1").read_bytes() == original


def test_a_second_load_of_a_migrated_file_changes_nothing(tmp_path):
    _write(tmp_path, {"version": 1, "voicings": {"Mine": _GUITAR}})
    _service(tmp_path).load_config()
    migrated = _path(tmp_path).read_bytes()
    _service(tmp_path).load_config()
    assert _path(tmp_path).read_bytes() == migrated
    assert len(_backups(tmp_path)) == 1
