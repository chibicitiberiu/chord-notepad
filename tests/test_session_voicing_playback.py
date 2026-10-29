"""Changing the voicing or the instrument while a song is paused or playing.

The song is pre-rendered, so a voicing change can't reach a song that plays:
it is refused (and the menu says why). While paused it is allowed, and Play
then renders again from the chord the song stopped on. The instrument is a
synth setting: it changes at any time.
"""

from session.state import PlaybackStatus, VoicingMenuState
from tests.test_session_playback import Env

NEW_VOICING = "guitar:standard"


def _paused_on_second_chord(env):
    env.session.play_pause()
    env.rendered()
    env.player.play(chords=2)
    env.host.run_pending()
    env.session.play_pause()
    assert env.playback().status is PlaybackStatus.PAUSED


def _menu(env):
    return env.recorder.last(VoicingMenuState)


def test_voicing_change_while_paused_renders_again_from_the_paused_chord_on_resume():
    env = Env(auto_play=False)
    _paused_on_second_chord(env)
    paused_at = env.playback().playing_span
    renders = []
    real = env.audio.start_song_playback

    def spy(**kwargs):
        renders.append((kwargs["start_line_index"], kwargs["start_item_index"],
                        env.audio._note_picker))
        return real(**kwargs)

    env.audio.start_song_playback = spy
    old_picker = env.audio._note_picker
    env.session.set_voicing(NEW_VOICING)
    assert env.audio._config.get("voicing", "piano") == NEW_VOICING
    assert env.playback().status is PlaybackStatus.PAUSED  # nothing restarts yet

    env.session.play_pause()
    env.rendered()
    # A new render, from the paused chord (index 1 of the first line), with the new picker.
    assert len(renders) == 1
    assert renders[0][:2] == (0, 1)
    assert renders[0][2] is not old_picker
    assert env.player.calls[-2:] == ["stop", "start"]
    env.player.play(chords=1)
    env.host.run_pending()
    assert env.playback().playing_span == paused_at
    assert env.playback().status is PlaybackStatus.PLAYING


def test_without_a_voicing_change_resume_does_not_render_again():
    env = Env(auto_play=False)
    _paused_on_second_chord(env)
    env.session.play_pause()
    assert env.player.calls[-1] == "resume"
    assert env.player.calls.count("start") == 1


def test_a_voicing_change_before_the_pause_leaves_the_resume_alone():
    env = Env(auto_play=False)
    env.session.set_voicing(NEW_VOICING)
    _paused_on_second_chord(env)
    env.session.play_pause()
    assert env.player.calls[-1] == "resume"


def test_voicing_change_is_refused_while_playing_and_the_menu_says_why():
    env = Env(auto_play=False)
    env.session.play_pause()
    env.rendered()
    before = env.audio._config.get("voicing", "piano")
    assert _menu(env).locked_reason == "Pause to change the voicing"
    env.session.set_voicing(NEW_VOICING)
    assert env.audio._config.get("voicing", "piano") == before
    assert env.audio._note_picker is not None
    assert env.status() == "Pause to change the voicing"


def test_the_voicing_menu_unlocks_when_paused_and_when_idle():
    env = Env(auto_play=False)
    env.session.play_pause()
    env.rendered()
    env.session.play_pause()
    assert _menu(env).locked_reason is None
    env.session.play_pause()
    assert _menu(env).locked_reason is not None
    env.session.rewind()
    assert _menu(env).locked_reason is None
    env.session.set_voicing(NEW_VOICING)
    assert env.audio._config.get("voicing", "piano") == NEW_VOICING


def test_instrument_change_while_paused_reaches_the_synth_and_resume_keeps_it():
    env = Env(auto_play=False)
    _paused_on_second_chord(env)
    env.session.set_instrument(24)
    assert env.player.instrument == 24
    env.session.play_pause()
    assert env.player.calls[-1] == "resume"
    assert env.player.instrument == 24


def test_instrument_change_while_playing_reaches_the_synth_at_once():
    env = Env(auto_play=False)
    env.session.play_pause()
    env.rendered()
    env.session.set_instrument(40)
    assert env.player.instrument == 40
    assert env.playback().status is PlaybackStatus.PLAYING
