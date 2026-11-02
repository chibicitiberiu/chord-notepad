"""Changing the tempo, time signature or key while a song is paused.

Like the voicing (tests/test_session_voicing_playback.py): the song is
rendered up front, so these are refused while it plays. Paused, they are
allowed and Play renders again from the chord the song stopped on, with
the new values.
"""

import pytest

from session.state import PlaybackStatus, SongDefaultsState
from tests.test_session_playback import Env


def _paused_on_second_chord(env):
    env.session.play_pause()
    env.rendered()
    env.player.play(chords=2)
    env.host.run_pending()
    env.session.play_pause()
    assert env.playback().status is PlaybackStatus.PAUSED


def _spy_renders(env):
    """Record the start point and values of each render Play starts."""
    renders = []
    real = env.audio.start_song_playback

    def spy(**kwargs):
        renders.append(kwargs)
        return real(**kwargs)

    env.audio.start_song_playback = spy
    return renders


CHANGES = {
    "tempo": (lambda s: s.set_bpm(90), "initial_bpm", 90),
    "time signature": (lambda s: s.set_time_signature(3, 4), "initial_time_sig", (3, 4)),
    "key": (lambda s: s.set_key("G"), "initial_key", "G"),
}


@pytest.mark.parametrize("what", CHANGES)
def test_a_change_while_paused_renders_again_from_the_paused_chord_on_resume(what):
    change, field, value = CHANGES[what]
    env = Env(auto_play=False)
    _paused_on_second_chord(env)
    paused_at = env.playback().playing_span
    renders = _spy_renders(env)
    change(env.session)
    assert env.playback().status is PlaybackStatus.PAUSED  # nothing restarts yet
    assert env.playback().playing_span == paused_at

    env.session.play_pause()
    env.rendered()
    # A new render from the paused chord (index 1 of the first line), with the new value.
    assert len(renders) == 1
    assert (renders[0]["start_line_index"], renders[0]["start_item_index"]) == (0, 1)
    assert renders[0][field] == value
    assert env.player.calls[-2:] == ["stop", "start"]
    env.player.play(chords=1)
    env.host.run_pending()
    assert env.playback().playing_span == paused_at
    assert env.playback().status is PlaybackStatus.PLAYING
    # The strip's playhead is on that chord again.
    assert env.sheet.pings[-1] == ("G", 1)


@pytest.mark.parametrize("what", CHANGES)
def test_a_change_while_playing_is_refused(what):
    change, field, value = CHANGES[what]
    env = Env(auto_play=False)
    env.session.play_pause()
    env.rendered()
    change(env.session)
    assert (env.main.bpm, env.main.time_signature_beats, env.main.key) == (120, 4, None)
    env.session.play_pause()   # pause
    env.session.play_pause()   # resume: the old render goes on
    assert env.player.calls[-1] == "resume"


def test_the_stale_mark_goes_with_the_paused_song():
    env = Env(auto_play=False)
    _paused_on_second_chord(env)
    env.session.set_bpm(90)
    env.session.stop()
    env.session.play_pause()
    env.rendered()
    env.session.play_pause()
    env.session.play_pause()
    assert env.player.calls[-1] == "resume"


def test_the_unchanged_value_leaves_the_resume_alone():
    env = Env(auto_play=False)
    _paused_on_second_chord(env)
    env.session.set_bpm(120)   # what it already is: no change notified
    env.session.play_pause()
    assert env.player.calls[-1] == "resume"


def test_the_song_defaults_unlock_on_pause_and_lock_on_resume():
    env = Env(auto_play=False)
    env.session.play_pause()
    env.rendered()
    reason = "Pause to change the playback settings"
    assert env.recorder.last(SongDefaultsState).locked_reason == reason
    env.session.play_pause()
    assert env.recorder.last(SongDefaultsState).locked_reason is None
    env.session.play_pause()
    assert env.recorder.last(SongDefaultsState).locked_reason == reason
