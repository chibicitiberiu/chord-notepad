"""Android's startup screen: the support prompt policy, app_started and its dismissal.

Design: docs/ANDROID.md, "Startup screen and support prompt". The desktop never
sends ``app_started``, so it never gets a StartupState.
"""

import dataclasses
import json

import pytest

from models.config import Config
from services.appdata_service import AppDataService
from session.bootstrap import build_core_services, create_session
from session.events import PickDocumentRequest, PickMode, UserError
from session.host import HostDispatch
from session.state import DocumentState, StartupScreen, StartupState
from session.support import NAG_DELAY_DAYS, LaunchKind, should_show_support_prompt
from session.testing import EventRecorder, FakePlayer, InMemoryDocumentStore, ManualHost

INSTALLED = "2026-10-01"
DAY_6 = "2026-10-07"
DAY_7 = "2026-10-08"


# -- the policy ------------------------------------------------------------------


@pytest.mark.parametrize("today,last_shown,can_ask,expected", [
    (INSTALLED, None, True, False),          # install day
    ("2026-10-02", None, True, False),       # day 1
    (DAY_6, None, True, False),              # day 6
    (DAY_7, None, True, True),               # day 7: the first prompt
    ("2027-03-01", None, True, True),        # months later
    (DAY_7, DAY_7, True, False),             # already shown today
    ("2026-10-09", DAY_7, True, True),       # the next day
    (DAY_7, "2026-10-20", True, True),       # last shown "in the future": clock moved back
    (DAY_7, None, False, False),             # billing can't sell it, or a supporter
    ("2026-09-20", None, True, False),       # today before the install day (clock back)
    ("not a date", None, True, False),
    (DAY_7, "garbage", True, True),          # a bad last-shown date doesn't block it
])
def test_should_show_support_prompt(today, last_shown, can_ask, expected):
    assert should_show_support_prompt(today, INSTALLED, last_shown, can_ask) is expected


def test_the_delay_is_a_week():
    assert NAG_DELAY_DAYS == 7
    assert should_show_support_prompt(DAY_7, "bad", None, True) is False


# -- the session -------------------------------------------------------------------


def make(tmp_path, config=None, documents=None):
    if config is not None:
        config_dir = tmp_path / "config" / "chord-notepad"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "settings.json").write_text(json.dumps(config))
    host = ManualHost()
    services = build_core_services(AppDataService(root=tmp_path), HostDispatch(host),
                                   player=FakePlayer())
    store = InMemoryDocumentStore(documents or {})
    session = create_session(host, services, store, chord_sheet=False, platform="android")
    recorder = EventRecorder()
    session.subscribe(recorder)
    session.start()
    return session, services, recorder, store


def saved_config(services) -> dict:
    return json.loads(services.appdata.get_config_file_path().read_text())


def started(session, kind="direct", today=DAY_7, can_ask=True):
    session.app_started(kind, today, INSTALLED, can_ask)


def test_no_startup_state_until_app_started(tmp_path):
    session, _, recorder, _ = make(tmp_path)
    assert recorder.of_type(StartupState) == []
    session.dismiss_startup_screen()            # nothing to dismiss yet
    assert recorder.of_type(StartupState) == []


@pytest.mark.parametrize("kind,can_ask,quick_start,screen", [
    ("direct", True, True, StartupScreen.SUPPORT_PROMPT),   # the prompt replaces Quick Start
    ("direct", True, False, StartupScreen.SUPPORT_PROMPT),
    ("direct", False, True, StartupScreen.QUICK_START),
    ("direct", False, False, StartupScreen.NONE),
    ("document", True, True, StartupScreen.NONE),
    ("restore", True, True, StartupScreen.NONE),
])
def test_app_started_picks_the_screen(tmp_path, kind, can_ask, quick_start, screen):
    session, _, recorder, _ = make(tmp_path, config={"show_quick_start_on_startup": quick_start})
    started(session, kind, can_ask=can_ask)
    assert recorder.of_type(StartupState) == [StartupState(screen)]


def test_quick_start_before_day_seven(tmp_path):
    session, _, recorder, _ = make(tmp_path)
    started(session, today=DAY_6)
    assert recorder.of_type(StartupState) == [StartupState(StartupScreen.QUICK_START)]


def test_only_the_first_app_started_counts(tmp_path):
    session, _, recorder, _ = make(tmp_path)
    started(session, "restore")
    started(session, "direct")                  # e.g. a second activity: ignored
    assert recorder.of_type(StartupState) == [StartupState(StartupScreen.NONE)]

    session2, _, recorder2, _ = make(tmp_path / "two")
    started(session2, "direct")
    started(session2, "restore")                # a rotation keeps the prompt
    assert recorder2.of_type(StartupState) == [StartupState(StartupScreen.SUPPORT_PROMPT)]


def test_unknown_launch_kind_raises(tmp_path):
    session, _, recorder, _ = make(tmp_path)
    with pytest.raises(ValueError):
        started(session, "sideways")
    assert recorder.of_type(StartupState) == []
    assert [k.value for k in LaunchKind] == ["direct", "document", "restore"]


def test_dismissing_the_prompt_records_today_and_saves(tmp_path):
    session, services, recorder, _ = make(tmp_path)
    started(session)
    session.dismiss_startup_screen()
    assert recorder.last(StartupState) == StartupState(StartupScreen.NONE)
    assert services.config.config.support_prompt_last_shown == DAY_7
    assert saved_config(services)["support_prompt_last_shown"] == DAY_7

    # The next start the same day: Quick Start instead; the day after: the prompt.
    session2, _, recorder2, _ = make(tmp_path)
    started(session2)
    assert recorder2.last(StartupState) == StartupState(StartupScreen.QUICK_START)
    session3, _, recorder3, _ = make(tmp_path)
    started(session3, today="2026-10-09")
    assert recorder3.last(StartupState) == StartupState(StartupScreen.SUPPORT_PROMPT)


def test_dismissing_quick_start_records_nothing(tmp_path):
    session, services, recorder, _ = make(tmp_path)
    started(session, can_ask=False)
    session.dismiss_startup_screen()
    assert recorder.last(StartupState) == StartupState(StartupScreen.NONE)
    assert services.config.config.support_prompt_last_shown is None


def test_saving_settings_keeps_the_last_shown_date(tmp_path):
    session, services, _, _ = make(tmp_path)
    started(session)
    session.dismiss_startup_screen()
    values = session.settings_values()
    session.apply_settings(dataclasses.replace(values, bpm=100))
    session.begin_settings_edit()
    session.save_settings(dataclasses.replace(values, font_size=19))
    assert services.config.config.support_prompt_last_shown == DAY_7
    assert saved_config(services)["support_prompt_last_shown"] == DAY_7


def test_config_round_trip_and_bad_values():
    config = Config(support_prompt_last_shown="2026-10-30")
    assert Config.from_dict(config.to_dict()).support_prompt_last_shown == "2026-10-30"
    assert Config.from_dict({}).support_prompt_last_shown is None
    for bad in (5, "yesterday", ["2026-10-30"]):
        assert Config.from_dict({"support_prompt_last_shown": bad}).support_prompt_last_shown is None


# -- read-only documents -------------------------------------------------------------


def test_save_on_a_read_only_document_runs_save_as(tmp_path):
    session, _, recorder, store = make(tmp_path, documents={"song.txt": "C G\n"})
    ref = store.ref("song.txt")
    session.open_document(ref, read_only=True)
    assert recorder.last(DocumentState).read_only is True
    session.set_text("C G Am\n")
    recorder.clear()
    session.save()
    request = recorder.last(PickDocumentRequest)
    assert request is not None and request.mode == PickMode.SAVE
    assert request.suggested_name == "song.txt"
    assert store.contents[ref.id] == "C G\n"          # not written
    copy = store.ref("copy.txt")
    session.respond(request.request_id, copy)
    assert store.contents[copy.id] == "C G Am\n"
    state = recorder.last(DocumentState)
    assert state.document_id == copy.id and state.read_only is False
    assert recorder.of_type(UserError) == []


def test_read_only_follows_the_open_document(tmp_path):
    session, _, recorder, store = make(tmp_path, documents={"a.txt": "C\n", "b.txt": "G\n"})
    session.open_document(store.ref("a.txt"), read_only=True)
    session.open_document(store.ref("b.txt"))
    assert recorder.last(DocumentState).read_only is False
    session.save()                                    # writable: no picker
    assert recorder.last(PickDocumentRequest) is None
    # A failed read-only open keeps the open document as it was.
    session.open_document(store.ref("missing.txt"), read_only=True)
    assert recorder.last(DocumentState).read_only is False
    # read_only without a ref (the picker) is ignored.
    session.open_document(None, read_only=True)
    request = recorder.last(PickDocumentRequest)
    session.respond(request.request_id, store.ref("a.txt"))
    assert recorder.last(DocumentState).read_only is False


def test_restored_draft_keeps_read_only(tmp_path):
    session, _, recorder, store = make(tmp_path, documents={"a.txt": "C\n"})
    session.restore_draft("C D\n", store.ref("a.txt"), True, read_only=True)
    assert recorder.last(DocumentState).read_only is True
    recorder.clear()
    session.save()
    assert recorder.last(PickDocumentRequest).mode == PickMode.SAVE
