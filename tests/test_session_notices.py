"""One-off notices dismissed for good (the Qt staff view's rhythm notice).

A config list of notice ids, read back as the session's ``dismissed_notices``
(a direct call on the Qt desktop) and added to with the bridge command
``dismiss_notice``, which saves the config. Android sends none.
"""

import json

import pytest

from chordnotepad.models.config import Config
from chordnotepad.session import bridge
from tests.test_volume import make


def test_the_config_key_and_its_default():
    assert Config().dismissed_notices == []
    assert Config().to_dict()["dismissed_notices"] == []
    loaded = Config.from_dict({"dismissed_notices": ["staff_rhythm", "other"]})
    assert loaded.dismissed_notices == ["staff_rhythm", "other"]
    assert loaded.to_dict()["dismissed_notices"] == ["staff_rhythm", "other"]


@pytest.mark.parametrize("raw, expected", [
    (None, []), ("staff_rhythm", []), ({"staff_rhythm": True}, []),
    (["staff_rhythm", 3, "", None, "staff_rhythm", "b"], ["staff_rhythm", "b"]),
])
def test_junk_is_dropped(raw, expected):
    config = Config.from_dict({"dismissed_notices": raw, "bpm": 90})
    assert config.dismissed_notices == expected and config.bpm == 90
    config.validate()


def test_the_session_keeps_a_dismissed_notice(tmp_path):
    session, services, _ = make(tmp_path)
    assert session.dismissed_notices == ()
    session.dismiss_notice("staff_rhythm")
    session.dismiss_notice("staff_rhythm")
    assert session.dismissed_notices == ("staff_rhythm",)
    services.config.save_config()
    saved = json.loads(services.config.config_file_path.read_text())
    assert saved["dismissed_notices"] == ["staff_rhythm"]
    again, _, _ = make(tmp_path / "again", {"dismissed_notices": ["staff_rhythm"]})
    assert again.dismissed_notices == ("staff_rhythm",)


def test_an_empty_id_is_refused(tmp_path):
    session, services, _ = make(tmp_path)
    with pytest.raises(ValueError):
        session.dismiss_notice("")
    assert services.config.config.dismissed_notices == []


def test_the_qt_window_reaches_it_through_the_bridge():
    assert bridge.SESSION_COMMANDS["dismiss_notice"] == {"notice_id": "str"}
    assert "dismiss_notice" in bridge.CONFIG_COMMANDS
