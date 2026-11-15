"""The playhead in a later pass of a loop (Tibi, 2026-11-15: "clicking on
the second segment in the seek bar makes the click register in the first").

A loop plays the same chords of the text again, so a text offset can't say
which pass the playhead is on. The session keeps the pass beside the offset
(the n-th occurrence of the chord in the chord sheet's loop-unrolled song):
a seek on the timeline (``seek_to_bar``) or on a chord-sheet slot
(``audition``) and the playback pings set it; the position, the sheet's
cursor and Play follow it (the renderer's ``start_pass``). A seek from the
text, rewind, the Qt Stop and every edit put it back on the first pass. The
Tk desktop has no playhead and keeps its behaviour.
"""

import pytest

from chordnotepad.audio.chord_picker import ChordNotePicker
from chordnotepad.services.song_parser_service import SongParserService
from chordnotepad.services.song_renderer import SongRenderer
from chordnotepad.session.platform import ANDROID, DESKTOP, DESKTOP_QT
from chordnotepad.session.state import ChordSheetState, PlaybackStatus
from tests.test_session_player import Env
from tests.test_timeline import SONG, strip_render

# SONG: verse C G (bars 1-2), chorus Am F (3-4), the chorus again (5-6).
# The strip's chords: C G Am F Am F, indices 0-5.
C, AM, F = SONG.index("C "), SONG.index("Am"), SONG.index("F")
NEW_VOICING = "guitar:standard"


def render(text, start, start_pass):
    lines = SongParserService().detect_chords_in_text(text, "american")
    return SongRenderer().render(
        lines=lines, initial_key="C", initial_bpm=120, initial_time_sig=(4, 4),
        note_picker=ChordNotePicker(), start_line_index=start[0],
        start_item_index=start[1], start_pass=start_pass)


def played(song):
    return [(c.chord_info.chord, c.song_bar) for c in song.chords if not c.skipped]


def qt_env(platform=DESKTOP_QT):
    env = Env(platform, text=SONG, auto_play=False)
    strip_render(env)
    return env


def bar(env):
    return env.session.timeline_position().bar


def cursor(env):
    return env.recorder.last(ChordSheetState).cursor_index


def play_chords(env, n):
    env.rendered()
    env.player.play(n)
    env.host.run_pending()


# -- the renderer --------------------------------------------------------------------------


def test_the_renderer_starts_in_the_pass_it_is_asked_for():
    am = (3, 0)     # line 3, item 0
    assert played(render(SONG, am, 0)) == [("Am", 3), ("F", 4), ("Am", 5), ("F", 6)]
    second = render(SONG, am, 1)
    assert played(second) == [("Am", 5), ("F", 6)]
    # The skipped chords before it keep the strip's indices.
    assert len(second.chords) == 6
    # A pass the song doesn't have plays nothing.
    assert played(render(SONG, am, 2)) == []
    # At the top of the song too (the first chord, offset 0).
    looped = "C G\n{loop: @start 2}"
    assert played(render(looped, (0, 0), 1)) == [("C", 3), ("G", 4)]


# -- seeking into a later pass -------------------------------------------------------------


def test_a_timeline_seek_into_the_second_pass_puts_the_playhead_there():
    env = qt_env()
    env.session.seek_to_bar(5)
    # The editor's marker is on the chord in the text, the same for both passes.
    assert env.playhead() == AM
    assert bar(env) == 5
    assert cursor(env) == 4
    env.session.play_pause()
    play_chords(env, 1)
    assert (env.playback().chord_index, env.playback().bar) == (4, 5)


def test_a_click_on_a_second_pass_slot_of_the_sheet_puts_the_playhead_there():
    env = qt_env()
    env.session.audition(5)            # F, second pass
    assert env.playhead() == F
    assert (bar(env), cursor(env)) == (6, 5)
    env.session.play_pause()
    play_chords(env, 1)
    assert env.playback().chord_index == 5


@pytest.mark.parametrize("seek", ["timeline", "sheet"])
def test_a_seek_into_the_second_pass_while_playing_jumps_there(seek):
    env = qt_env()
    env.session.play_pause()
    play_chords(env, 1)
    assert env.playback().chord_index == 0
    if seek == "timeline":
        env.session.seek_to_bar(5)
    else:
        env.session.audition(4)
    play_chords(env, 1)
    assert env.playback().status is PlaybackStatus.PLAYING
    assert (env.playback().chord_index, env.playback().bar) == (4, 5)


def test_a_seek_while_paused_drops_the_paused_song_and_plays_from_the_pass():
    env = qt_env()
    env.session.play_pause()
    play_chords(env, 1)
    env.session.play_pause()
    assert env.playback().status is PlaybackStatus.PAUSED
    env.session.seek_to_bar(6)
    assert env.playback().status is PlaybackStatus.IDLE
    assert (env.playhead(), bar(env)) == (F, 6)
    env.session.play_pause()
    play_chords(env, 1)
    assert env.playback().chord_index == 5


def test_the_android_sheet_tap_gets_the_pass_too():
    env = qt_env(ANDROID)
    env.session.audition(4)
    assert (env.playhead(), cursor(env)) == (AM, 4)
    env.session.play_pause()
    play_chords(env, 1)
    assert env.playback().chord_index == 4


# -- following playback ----------------------------------------------------------------------


def _paused_in_the_second_pass(env):
    env.session.play_pause()
    play_chords(env, 5)                 # C G Am F Am
    env.session.play_pause()
    assert env.playback().status is PlaybackStatus.PAUSED
    assert env.playback().chord_index == 4


def test_paused_in_the_second_pass_the_position_and_resume_stay_in_it():
    env = qt_env()
    _paused_in_the_second_pass(env)
    assert bar(env) == 5
    assert env.playhead() == AM
    env.session.play_pause()
    play_chords(env, 1)
    assert env.playback().chord_index == 5


def test_a_re_rendered_resume_starts_in_the_pass_it_was_paused_in():
    env = qt_env()
    _paused_in_the_second_pass(env)
    env.session.set_voicing(NEW_VOICING)
    env.session.play_pause()            # renders again, from the paused chord
    play_chords(env, 1)
    assert (env.playback().chord_index, env.playback().bar) == (4, 5)


def test_android_stop_leaves_the_playhead_on_the_chords_first_pass_as_before():
    # Android's Stop is unchanged by the loop passes: the playhead rests on
    # the chord that sounded, in its first pass (test_chord_sheet_playhead).
    env = qt_env(ANDROID)
    _paused_in_the_second_pass(env)
    env.session.stop()
    assert (env.playhead(), bar(env), cursor(env)) == (AM, 3, 2)
    env.session.play_pause()
    play_chords(env, 1)
    assert env.playback().chord_index == 2


def test_the_tk_desktop_resumes_a_re_render_at_the_chords_first_pass_as_before():
    env = qt_env(DESKTOP)
    _paused_in_the_second_pass(env)
    env.session.set_voicing(NEW_VOICING)
    env.session.play_pause()
    play_chords(env, 1)
    assert env.playback().chord_index == 2
    # And a sheet click only sounds the chord.
    env.session.stop()
    env.session.audition(4)
    assert env.playhead() is None


# -- what goes back to the first pass ---------------------------------------------------------


def _in_the_second_pass(env):
    env.session.seek_to_bar(5)
    assert (env.playhead(), bar(env)) == (AM, 5)


def test_a_seek_from_the_text_goes_to_the_first_pass():
    env = qt_env()
    _in_the_second_pass(env)
    env.session.set_playhead(AM)
    assert (bar(env), cursor(env)) == (3, 2)
    _in_the_second_pass(env)
    env.session.tap_chord_at(AM)        # the Qt desktop's playhead follows taps
    assert bar(env) == 3


def test_rewind_and_the_qt_stop_go_to_the_first_chord():
    env = qt_env()
    _in_the_second_pass(env)
    env.session.rewind()
    assert (env.playhead(), bar(env)) == (C, 1)
    _in_the_second_pass(env)
    env.session.stop()
    assert (env.playhead(), bar(env)) == (C, 1)


def test_an_edit_puts_the_playhead_back_on_its_chords_first_pass():
    env = qt_env()
    _in_the_second_pass(env)
    env.session.insert_text(len(SONG), "\nla la")
    env.host.advance(0.5)
    strip_render(env)
    assert env.playhead() == AM
    assert (bar(env), cursor(env)) == (3, 2)
    env.session.play_pause()
    play_chords(env, 1)
    assert env.playback().chord_index == 2


def test_a_strip_without_the_pass_falls_back_to_the_first():
    env = qt_env()
    _in_the_second_pass(env)
    # The strip's song loses the second pass (a render of other text).
    env.sheet.finish_render(render("{label: chorus}\nAm  F", (0, 0), 0))
    env.session.play_pause()
    play_chords(env, 1)
    assert env.playback().chord_index == 2


def test_a_detection_that_keeps_the_chord_keeps_the_pass():
    env = qt_env()
    _in_the_second_pass(env)
    # A detection of the same text (a notation change detects again).
    env.session._entry(env.session._detect_now)()
    assert (env.playhead(), bar(env)) == (AM, 5)


_EXAMPLES = __import__("pathlib").Path(__file__).parent.parent / "examples"
#: Songs with loops for the start-in-pass check: the examples, nested loops,
#: a loop back to the top, and roman numerals whose key changes per pass.
LOOPED_SONGS = [(p.name, p.read_text(encoding="utf-8")) for p in sorted(_EXAMPLES.glob("*.txt"))] + [
    ("nested", "{label: a}\nC G\n{label: b}\nAm F*2 NC\n{loop: b 2}\n{loop: a 2}\nE"),
    ("top", "C G*2\n{loop: @start 3}\nF"),
    ("roman", "{key: C}\n{label: v}\nI IV*2 V\n{key: G}\n{loop: v 3}\nvi"),
]


@pytest.mark.parametrize("name, text", LOOPED_SONGS, ids=[n for n, _ in LOOPED_SONGS])
def test_every_repeated_chord_can_be_started_from_in_each_of_its_passes(name, text):
    """For each chord a loop repeats, a render from its line and item in
    each of its passes starts exactly there: the index and bar the strip
    shows."""
    lines = SongParserService().detect_chords_in_text(text, "american")

    def run(start=(0, 0), start_pass=0):
        return SongRenderer().render(
            lines=lines, initial_key="C", initial_bpm=120, initial_time_sig=(4, 4),
            note_picker=ChordNotePicker(), start_line_index=start[0],
            start_item_index=start[1], start_pass=start_pass)

    whole = run()
    keys = [(c.line_index, c.item_index) for c in whole.chords]
    seen = {}
    for index, chord in enumerate(whole.chords):
        key = keys[index]
        start_pass = seen.get(key, 0)
        seen[key] = start_pass + 1
        if keys.count(key) < 2:
            continue        # not in a loop: the first-pass start, as always
        song = run(key, start_pass)
        first = next(i for i, c in enumerate(song.chords) if not c.skipped)
        assert first == index, (name, index, start_pass)
        assert len(song.chords) == len(whole.chords)
        assert song.chords[first].song_bar == chord.song_bar
