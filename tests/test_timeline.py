"""The player's timeline (plan step B2): the beat in the bar and the song's sections.

The renderer gives every chord the beat it starts on (``RenderedChord.beat``
in the rebased bar, ``song_beat`` in the song's bar), the pings carry them,
and ``PlaybackState.beat`` pairs with ``bar``. ``timeline.song_sections``
turns the chord sheet's song into bar ranges for a scrubber, which the
session publishes as ``PlaybackState.sections``.
"""

from types import SimpleNamespace

import pytest

from chordnotepad.audio.chord_picker import ChordNotePicker
from chordnotepad.models.rendered_song import SongMarker
from chordnotepad.services.event_compiler import compile_events
from chordnotepad.services.song_parser_service import SongParserService
from chordnotepad.services.song_renderer import SongRenderer
from chordnotepad.session.platform import (
    ANDROID, COUNTS_SONG_BARS, DESKTOP, DESKTOP_QT,
)
from chordnotepad.session.state import PlaybackState, PlaybackStatus, TimelineSection
from chordnotepad.session.timeline import song_sections
from tests.test_session_player import Env


def render(text, start=(0, 0), time_sig=(4, 4)):
    lines = SongParserService().detect_chords_in_text(text, "american")
    return SongRenderer().render(
        lines=lines, initial_key="C", initial_bpm=120, initial_time_sig=time_sig,
        note_picker=ChordNotePicker(), start_line_index=start[0], start_item_index=start[1])


def played(song):
    return [c for c in song.chords if not c.skipped]


# -- the beat each chord starts on ----------------------------------------------------


def test_each_chord_knows_the_beat_it_starts_on():
    song = render("C*2 G*1.5 Am*0.5 F D*3 E")
    got = [(c.chord_info.chord, c.song_bar, c.song_beat, c.bar, c.beat) for c in song.chords]
    assert got == [
        ("C", 1, 1.0, 1, 1.0),
        ("G", 1, 3.0, 1, 3.0),
        ("Am", 1, 4.5, 1, 4.5),
        ("F", 2, 1.0, 2, 1.0),
        ("D", 3, 1.0, 3, 1.0),
        ("E", 3, 4.0, 3, 4.0),
    ]


def test_a_meter_change_starts_a_new_bar_on_beat_one():
    song = render("C*2 {time: 3/4} G A")
    assert [(c.song_bar, c.song_beat) for c in song.chords] == [(1, 1.0), (2, 1.0), (3, 1.0)]


def test_from_the_cursor_the_song_beat_stays_and_the_rebased_beat_restarts():
    # Start at G, halfway through bar 1.
    song = render("C*2 G*2 Am", start=(0, 1))
    first = played(song)[0]
    assert first.chord_info.chord == "G"
    assert (first.song_bar, first.song_beat) == (1, 3.0)
    assert (first.bar, first.beat) == (1, 1.0)
    assert [(c.song_bar, c.song_beat, c.bar, c.beat) for c in played(song)[1:]] == [
        (2, 1.0, 1, 3.0)]


def test_the_events_carry_both_beats():
    song = render("C*2 G*2 NC")
    metas = [e.metadata for e in compile_events(song, has_callback=True)
             if e.metadata and e.metadata.get("chord_info") is not None
             and "has_callback" in e.metadata]
    assert [(m["song_beat"], m["beat"]) for m in metas] == [(1.0, 1.0), (3.0, 3.0), (1.0, 1.0)]


def test_the_renderer_labels_section_and_loop_markers():
    song = render("{label: verse}\nC G\n{loop: verse 2}\n{bpm: 90}\nAm")
    got = [(m.kind, m.text, m.label) for m in song.markers]
    assert got == [("section", "verse", "verse"), ("loop", "verse (2/2)", "verse"),
                   ("tempo", "90 bpm", "")]


# -- sections ----------------------------------------------------------------------------


def sections(text, **kw):
    return list(song_sections(render(text, **kw)))


def S(label, first, last, repeat=False):
    return TimelineSection(label, first, last, repeat)


def test_a_song_without_labels_is_one_section():
    assert sections("C G Am F") == [S("", 1, 4)]


def test_no_song_or_no_chords_has_no_sections():
    assert song_sections(None) == ()
    assert song_sections(render("la la la")) == ()
    assert song_sections(SimpleNamespace(chords=[], markers=[], total_bars=1)) == ()


def test_labels_split_the_song_and_bars_before_the_first_label_have_no_label():
    text = "C G\n{label: verse}\nAm F\nC\n{label: chorus}\nF G C"
    assert sections(text) == [S("", 1, 2), S("verse", 3, 5), S("chorus", 6, 8)]


def test_a_label_at_the_top_starts_the_first_section():
    assert sections("{label: intro}\nC G\n{label: verse}\nAm") == [
        S("intro", 1, 2), S("verse", 3, 3)]


def test_loop_passes_are_repeats_in_playing_order():
    text = "{label: chorus}\nF C\n{loop: chorus 3}\n{label: outro}\nG"
    assert sections(text) == [
        S("chorus", 1, 2), S("chorus", 3, 4, True), S("chorus", 5, 6, True), S("outro", 7, 7)]


def test_a_label_in_the_middle_of_a_bar_starts_at_that_bar():
    # C*6 fills bar 1 and half of bar 2, where chorus's G*2 starts; Am is bar 3.
    assert sections("{label: verse}\nC*6\n{label: chorus}\nG*2 Am") == [
        S("verse", 1, 1), S("chorus", 2, 3)]


def test_two_labels_in_one_bar_keep_the_later():
    assert sections("{label: a}\nC*2\n{label: b}\nG*2 Am") == [S("b", 1, 2)]


def test_a_label_after_the_last_chord_starts_nothing():
    assert sections("C G\n{label: coda}") == [S("", 1, 2)]


def test_the_sections_tile_every_bar():
    text = ("C*3\n{label: verse}\nG*1.5 Am*2.5\n{time: 3/4}\nF\n{label: chorus}\nC*6\n"
            "{loop: chorus 2}\nD")
    song = render(text)
    found = song_sections(song)
    assert found[0].first_bar == 1 and found[-1].last_bar == song.total_bars
    for before, after in zip(found, found[1:]):
        assert after.first_bar == before.last_bar + 1
        assert before.first_bar <= before.last_bar


def test_other_markers_dont_start_sections():
    marker = SongMarker(beat=4.0, time=2.0, kind="tempo", text="90 bpm")
    song = render("C G")
    song.markers = [marker]
    assert song_sections(song) == (S("", 1, 2),)


# -- the session ---------------------------------------------------------------------------


SONG = "{label: verse}\nC   G\n{label: chorus}\nAm  F\n{loop: chorus 2}"
# Chords: C 15-16, G 19-20, Am 37-39, F 41-42 (one bar each in 4/4).


def test_only_the_tk_desktop_counts_bars_from_where_playback_started():
    assert COUNTS_SONG_BARS == {DESKTOP: False, ANDROID: True, DESKTOP_QT: True}


def strip_render(env):
    env.sheet.finish_render(render(env.session.text))


def last_playback(env):
    return env.recorder.last(PlaybackState)


@pytest.mark.parametrize("platform", [DESKTOP, ANDROID, DESKTOP_QT])
def test_the_session_publishes_the_strips_sections_and_keeps_them(platform):
    env = Env(platform, text=SONG, auto_play=False)
    assert env.playback().sections == ()
    strip_render(env)
    expected = (S("verse", 1, 2), S("chorus", 3, 4), S("chorus", 5, 6, True))
    assert last_playback(env).sections == expected
    env.session.play_pause()
    env.rendered()
    env.player.play(1)
    env.host.run_pending()
    assert last_playback(env).sections == expected
    env.session.stop()
    assert last_playback(env).status is PlaybackStatus.IDLE
    assert last_playback(env).sections == expected
    # An edit doesn't touch them until the strip renders the new text.
    env.session.set_text(SONG.replace("{loop: chorus 2}", ""))
    env.host.advance(0.5)
    assert env.playback().sections == expected
    strip_render(env)
    assert env.playback().sections == (S("verse", 1, 2), S("chorus", 3, 4))


def test_a_strip_render_with_the_same_sections_publishes_nothing():
    env = Env(DESKTOP_QT, text=SONG)
    strip_render(env)
    env.recorder.clear()
    strip_render(env)
    assert env.recorder.of_type(PlaybackState) == []


def bars_and_beats(env):
    return [(s.bar, s.beat) for s in env.recorder.of_type(PlaybackState)
            if s.playing_span is not None]


@pytest.mark.parametrize("platform", [ANDROID, DESKTOP_QT])
def test_android_and_qt_bar_and_beat_count_from_the_top_of_the_song(platform):
    env = Env(platform, text="C*2 G*2 Am F", auto_play=False)
    env.session.play_pause(from_offset=4)   # from G, the middle of bar 1
    env.rendered()
    env.player.play()
    env.host.run_pending()
    assert bars_and_beats(env) == [(1, 3), (2, 1), (3, 1)]
    assert last_playback(env).beat == 0   # idle again


def test_the_tk_desktop_bar_and_beat_restart_where_playback_started():
    env = Env(DESKTOP, text="C*2 G*2 Am F", auto_play=False)
    env.session.play_pause(from_offset=4)
    env.rendered()
    env.player.play()
    env.host.run_pending()
    assert bars_and_beats(env) == [(1, 1), (1, 3), (2, 3)]


def test_an_off_beat_chord_is_on_the_beat_it_starts_in():
    env = Env(DESKTOP_QT, text="C*1.5 G*2.5 Am", auto_play=False)
    env.session.play_pause()
    env.rendered()
    env.player.play()
    env.host.run_pending()
    assert bars_and_beats(env) == [(1, 1), (1, 2), (2, 1)]


def test_the_qt_status_names_the_song_bar_and_the_tk_status_the_rebased_one():
    for platform, bar in ((DESKTOP_QT, "Bar 2/3"), (DESKTOP, "Bar 1/3")):
        env = Env(platform, text="C G Am", auto_play=False)
        env.session.play_pause(from_offset=2)
        env.rendered()
        env.player.play(1)
        env.host.run_pending()
        assert env.status().startswith(bar + " | 120 BPM"), (platform, env.status())
