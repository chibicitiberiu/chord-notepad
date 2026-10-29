"""Per-platform user-facing texts: the desktop variant is the text it always was.

The host names its platform at bootstrap (``create_session(platform=...)``);
only texts that name a gesture or a menu path differ.
"""

from pathlib import Path

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


# -- Quick Start -------------------------------------------------------------------

FIXTURE = Path(__file__).parent / "fixtures" / "quick_start_desktop.json"


def _as_json(pages):
    import json
    return json.loads(json.dumps(pages, ensure_ascii=False))


def test_desktop_quick_start_is_the_dialogs_text_byte_for_byte():
    """The fixture is the Tk dialog's PAGES from before they moved to the core."""
    import json

    from session import quick_start
    from ui.dialogs.quick_start import QuickStartDialog

    expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert _as_json(quick_start.pages()) == expected
    assert _as_json(quick_start.pages(DESKTOP)) == expected
    assert QuickStartDialog.PAGES == quick_start.pages(DESKTOP)


def test_android_quick_start_names_taps_and_the_drawer():
    from session import quick_start

    desktop, android = quick_start.pages(DESKTOP), quick_start.pages(ANDROID)
    assert [p["title"] for p in android] == [p["title"] for p in desktop]
    text = " ".join(b[1] for p in android for b in p["blocks"] if b[0] == "text")
    for desktop_only in ("Click", "F1", "Help menu", "⋮", "toolbar"):
        assert desktop_only not in text
    assert "tap any chord" in text and "＋ Insert" in text
    assert "☰ → User guide" in text and "☰ → Quick start" in text
    assert "Voicing button in the Play tab" in text
    assert "Edit ribbon" in text and "song pill" in text
    assert not any(b[0] == "image" for p in android for b in p["blocks"])
    # Snippets are the same on both.
    snippets = lambda pages: [b for p in pages for b in p["blocks"] if b[0] == "snippet"]
    assert snippets(android) == snippets(desktop)
    with pytest.raises(ValueError):
        quick_start.pages("ios")


def test_quick_start_content_carries_snippet_spans(tmp_path):
    from services.appdata_service import AppDataService
    from session.bootstrap import build_core_services, create_session
    from session.events import QuickStartContent
    from session.host import HostDispatch
    from session.state import SpanKind
    from session.testing import EventRecorder, FakePlayer, InMemoryDocumentStore, ManualHost

    host = ManualHost()
    services = build_core_services(AppDataService(root=tmp_path), HostDispatch(host),
                                   player=FakePlayer())
    session = create_session(host, services, InMemoryDocumentStore(), chord_sheet=False,
                             platform=ANDROID)
    recorder = EventRecorder()
    session.subscribe(recorder)
    session.set_show_quick_start_on_startup(False)
    session.request_quick_start()
    content = recorder.last(QuickStartContent)
    assert content.show_on_startup is False
    assert len(content.pages) == 7
    first = content.pages[0].blocks[1]
    assert first.kind == "snippet" and first.notation == "american"
    chords = [first.text[s.start:s.end] for s in first.spans if s.kind is SpanKind.CHORD]
    assert chords == ["C", "C/E", "F", "C", "Dm", "Am", "G", "C"]
    assert content.pages[0].blocks[2].text.startswith("The app recognizes")
    assert "tap any chord" in content.pages[0].blocks[2].text
