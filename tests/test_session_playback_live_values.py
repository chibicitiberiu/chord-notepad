"""PlaybackState's live song values: the key, time signature and tempo
clamp in force at the chord sounding (the Qt status bar shows them).

Idle, they are the values the song starts with (what the toolbar shows,
from the same sources); paused, the paused chord's.
"""

from chordnotepad.session.state import PlaybackState, PlaybackStatus

from tests.test_session_playback import Env

SONG = "{key: D}\nD G\n{time: 3/4}\nA\n{key: G}\nG\n{bpm: 380}\nC\n{bpm: +50}\nEm"


def _sounding(env):
    """(chord text, key, time signature, tempo_clamped) per PlaybackState
    published while a chord sounded."""
    text = env.session.text
    return [(text[p.playing_span.start:p.playing_span.end], p.key, p.time_signature,
             p.tempo_clamped)
            for p in env.recorder.of_type(PlaybackState)
            if p.status is PlaybackStatus.PLAYING and p.playing_span is not None]


def test_each_chord_carries_the_values_in_force():
    env = Env(text=SONG)
    env.session.play_pause()
    env.rendered()
    clamp = "Tempo clamped to 400 BPM at line 9"
    assert _sounding(env) == [
        ("D", "D", (4, 4), None),
        ("G", "D", (4, 4), None),
        ("A", "D", (3, 4), None),
        ("G", "G", (3, 4), None),
        ("C", "G", (3, 4), None),
        ("Em", "G", (3, 4), clamp),
    ]


def test_idle_shows_the_values_the_song_starts_with():
    env = Env(text=SONG)
    state = env.playback() or env.session._playback
    assert (state.status, state.key, state.time_signature, state.tempo_clamped) == (
        PlaybackStatus.IDLE, "D", (4, 4), None)

    # An edit moves them while idle.
    env.session.set_text("{key: Bb}\n{time: 6/8}\nBb F")
    env.host.advance(0.5)
    state = env.playback()
    assert (state.key, state.time_signature) == ("Bb", (6, 8))

    # So does the toolbar, for a song that doesn't set them.
    env.session.set_text("C G")
    env.host.advance(0.5)
    assert (env.playback().key, env.playback().time_signature) == (None, (4, 4))
    env.session.set_key("E")
    env.session.set_time_signature(5, 4)
    assert (env.playback().key, env.playback().time_signature) == ("E", (5, 4))


def test_back_to_the_start_values_when_the_song_ends():
    env = Env(text=SONG)
    env.session.play_pause()
    env.rendered()
    state = env.playback()
    assert state.status is PlaybackStatus.IDLE
    assert (state.key, state.time_signature, state.tempo_clamped) == ("D", (4, 4), None)


def test_paused_keeps_the_paused_chords_values():
    env = Env(auto_play=False, text=SONG)
    env.session.play_pause()
    env.rendered()
    env.player.play(chords=3)
    env.host.run_pending()
    env.session.play_pause()
    state = env.playback()
    assert state.status is PlaybackStatus.PAUSED
    assert (state.key, state.time_signature) == ("D", (3, 4))

    env.session.stop()
    state = env.playback()
    assert state.status is PlaybackStatus.IDLE
    assert (state.key, state.time_signature) == ("D", (4, 4))


def test_the_key_is_in_the_songs_notation():
    env = Env(text="C")
    env.session.set_notation("european")
    env.session.set_text("{key: Sol}\nSol Re\n{key: Fa}\nFa")
    env.host.advance(0.5)
    assert env.playback().key == "Sol"
    env.recorder.clear()
    env.session.play_pause()
    env.rendered()
    assert [key for _, key, _, _ in _sounding(env)] == ["Sol", "Sol", "Fa"]
