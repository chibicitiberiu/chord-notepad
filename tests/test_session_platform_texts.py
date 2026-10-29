"""Per-platform user-facing texts: the desktop variant is the text it always was.

The host names its platform at bootstrap (``create_session(platform=...)``);
only texts that name a gesture or a menu path differ.
"""

import pytest

from session import formatting
from session.platform import ANDROID, DESKTOP, PLATFORMS, check_platform, pick


def test_platforms_and_pick():
    assert PLATFORMS == ("desktop", "android")
    assert check_platform("android") == ANDROID
    with pytest.raises(ValueError):
        check_platform("ios")
    assert pick({DESKTOP: 1, ANDROID: 2}, ANDROID) == 2
    assert pick({DESKTOP: 1}, ANDROID) == 1


def test_audio_unavailable_message_desktop_is_unchanged():
    assert formatting.audio_unavailable_message("no driver", True) == (
        "no driver\n\nClicked chords won't play until this is fixed.")
    assert formatting.audio_unavailable_message("no driver", True, DESKTOP) == (
        "no driver\n\nClicked chords won't play until this is fixed.")
    assert formatting.audio_unavailable_message("", False, ANDROID) == "Audio is not available."
    assert formatting.audio_unavailable_message("no driver", True, ANDROID) == (
        "no driver\n\nTapped chords won't play until this is fixed.")


def test_create_session_refuses_an_unknown_platform(tmp_path):
    from services.appdata_service import AppDataService
    from session.bootstrap import build_core_services, create_session
    from session.host import HostDispatch
    from session.testing import FakePlayer, InMemoryDocumentStore, ManualHost

    host = ManualHost()
    services = build_core_services(AppDataService(root=tmp_path), HostDispatch(host),
                                   player=FakePlayer())
    with pytest.raises(ValueError):
        create_session(host, services, InMemoryDocumentStore(), chord_sheet=False,
                       platform="ios")
