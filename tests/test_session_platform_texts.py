"""Per-platform user-facing texts: the desktop variant is the text it always was.

The host names its platform at bootstrap (``create_session(platform=...)``);
only texts that name a gesture or a menu path differ.
"""

from pathlib import Path

import pytest

from chordnotepad.session import formatting
from chordnotepad.session.platform import ANDROID, DESKTOP, PLATFORMS, check_platform, pick


def test_platforms_and_pick():
    assert PLATFORMS == ("desktop", "android", "desktop_qt", "ios")
    assert check_platform("android") == ANDROID
    with pytest.raises(ValueError):
        check_platform("unknown")
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
    from chordnotepad.services.appdata_service import AppDataService
    from chordnotepad.session.bootstrap import build_core_services, create_session
    from chordnotepad.session.host import HostDispatch
    from chordnotepad.session.testing import FakePlayer, InMemoryDocumentStore, ManualHost

    host = ManualHost()
    services = build_core_services(AppDataService(root=tmp_path), HostDispatch(host),
                                   player=FakePlayer())
    with pytest.raises(ValueError):
        create_session(host, services, InMemoryDocumentStore(), chord_sheet=False,
                       platform="unknown")


# -- Quick Start -------------------------------------------------------------------

FIXTURE = Path(__file__).parent / "fixtures" / "quick_start_desktop.json"


def _as_json(pages):
    import json
    return json.loads(json.dumps(pages, ensure_ascii=False))


def test_desktop_quick_start_is_the_dialogs_text_byte_for_byte():
    """The fixture is the Tk dialog's PAGES from before they moved to the core."""
    import json

    from chordnotepad.session import quick_start

    expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert _as_json(quick_start.pages()) == expected
    assert _as_json(quick_start.pages(DESKTOP)) == expected


def test_android_quick_start_names_taps_and_the_drawer():
    from chordnotepad.session import quick_start

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
        quick_start.pages("unknown")


def test_android_quick_start_says_the_chord_sheet_is_in_play():
    from chordnotepad.session import quick_start

    def sheet_text(platform):
        return next(b[1] for p in quick_start.pages(platform) for b in p["blocks"]
                    if b[0] == "text" and "piano roll" in b[1])

    # Android shows the panel only in the Play tab, not as you write (P9).
    assert sheet_text(ANDROID).startswith(
        "In the Play tab, the panel under the song draws its chords: as a piano roll")
    assert "as you write" not in sheet_text(ANDROID)
    assert sheet_text(DESKTOP).startswith(
        "The panel under the editor draws the song's chords as you write: ")


def test_quick_start_content_carries_snippet_spans(tmp_path):
    from chordnotepad.services.appdata_service import AppDataService
    from chordnotepad.session.bootstrap import build_core_services, create_session
    from chordnotepad.session.events import QuickStartContent
    from chordnotepad.session.host import HostDispatch
    from chordnotepad.session.state import SpanKind
    from chordnotepad.session.testing import EventRecorder, FakePlayer, InMemoryDocumentStore, ManualHost

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


def test_ios_flags_match_android_except_the_picker_note():
    from chordnotepad.session import platform as p

    assert p.IOS in p.PLATFORMS and p.check_platform("ios") == p.IOS
    for table in (p.TRACKS_PLAYHEAD, p.STOP_REWINDS, p.COUNTS_SONG_BARS, p.POSITION_STATUS):
        assert table[p.IOS] == table[p.ANDROID]
    assert p.POSITION_STATUS == {p.DESKTOP: False, p.ANDROID: True, p.DESKTOP_QT: False, p.IOS: True}
    assert p.PICKER_CREATES_FILE == {p.DESKTOP: False, p.ANDROID: True,
                                     p.DESKTOP_QT: False, p.IOS: False}
    for table in (p.TRACKS_PLAYHEAD, p.STOP_REWINDS, p.COUNTS_SONG_BARS,
                  p.POSITION_STATUS, p.PICKER_CREATES_FILE):
        assert set(table) == set(p.PLATFORMS)


def test_pick_falls_back_ios_to_android_to_desktop():
    from chordnotepad.session.platform import IOS

    assert pick({DESKTOP: 1, ANDROID: 2}, IOS) == 2
    assert pick({DESKTOP: 1, ANDROID: 2, IOS: 3}, IOS) == 3
    assert pick({DESKTOP: 1}, IOS) == 1
    assert pick({DESKTOP: 1, ANDROID: 2}, "desktop_qt") == 1  # android never leaks to the desktop


def test_ios_texts_and_tooltips_follow_android():
    from chordnotepad.session import quick_start
    from chordnotepad.session.platform import IOS
    from chordnotepad.settings_forms import voicing_form

    assert quick_start.pages(IOS) == quick_start.pages(ANDROID)
    assert formatting.audio_unavailable_message("x", True, IOS) == (
        formatting.audio_unavailable_message("x", True, ANDROID))
    assert (voicing_form.editor_schema(IOS)["help"] == voicing_form.editor_schema(ANDROID)["help"])


def test_the_export_status_is_the_desktops_on_every_platform():
    """iOS says it once the export picker saved the file (``export_finished``),
    with the place picked; the words are the desktop's."""
    from chordnotepad.session.platform import DESKTOP_QT, IOS

    for platform in (DESKTOP, ANDROID, DESKTOP_QT, IOS):
        assert formatting.exported_midi_status("song.mid", platform) == "Exported MIDI: song.mid"
        assert formatting.exported_audio_status("song.wav", platform) == "Exported audio: song.wav"
        assert formatting.exported_pdf_status("song.pdf", platform) == "Exported PDF: song.pdf"
    assert formatting.exported_midi_status("song.mid") == "Exported MIDI: song.mid"
    assert formatting.exported_audio_status("a {b}.wav") == "Exported audio: a {b}.wav"
