"""A chord clicked in the text sounds as the chord sheet shows it.

Tibi, 2026-11-16: "When people practice and want to hear a chord, and they
play the chart and it sounds different, it's not really ok." With the
``click_plays_chart_voicing`` setting on (the default) a click or tap on a
chord in the text plays the notes the chord sheet's render has for it, which
are the ones Play sounds. A chord a loop repeats sounds as in the pass a
paused song is in, else as in its first pass. Without a render of the text as
it is now, or with the setting off, clicks go back to click-to-hear's own
picker, which voice-leads from the chord clicked before.

The real session, ChordSheetViewModel and PlaybackService over a FakePlayer
(``tests.test_chord_sheet_playhead.Env``), plus FakeChordSheet where a test
needs to control the render.
"""

from types import SimpleNamespace

import pytest

from chordnotepad.models.config import Config
from chordnotepad.session.platform import ANDROID, DESKTOP, DESKTOP_QT
from chordnotepad.session.settings import SettingsValues
from chordnotepad.session.state import ChordSheetState, PlaybackStatus, SettingsState
from tests.test_chord_sheet_playhead import Env as SheetEnv
from tests.test_session_player import Env as FakeSheetEnv

GUITAR = "guitar:standard"
# G C G Am: the sheet voices C x32013, keeping the pinky on the G's top
# note, the click picker x32010.
TEXT = "G  C  G  Am"
FIRST, C, G = 0, TEXT.index("C"), TEXT.index("G", 1)

# A loop whose second pass voices C lower (piano): it follows G, not B.
# The strip: F# B C G C G (indices 0-5).
LOOPED = "{label: verse}\nF#  B\n{label: chorus}\nC  G\n{loop: chorus 2}"
L_B, L_C, L_G = LOOPED.index("B"), LOOPED.index("C "), LOOPED.index("G")


def sheet_notes(env, index):
    return env.sheet.rendered_song.chords[index].midi_notes


def picker_notes(voicing, taps, text=TEXT):
    """What the click picker plays for ``taps`` (the setting off)."""
    env = SheetEnv(DESKTOP_QT, text, voicing=voicing, click_plays_chart_voicing=False)
    for offset in taps:
        env.session.tap_chord_at(offset)
    return env.player.immediate


@pytest.mark.parametrize("platform", [DESKTOP_QT, ANDROID, DESKTOP])
def test_a_clicked_chord_sounds_the_notes_the_chord_sheet_shows(platform):
    env = SheetEnv(platform, TEXT, voicing=GUITAR)
    env.session.tap_chord_at(FIRST)
    env.session.tap_chord_at(C)
    assert env.player.immediate == [sheet_notes(env, 0), sheet_notes(env, 1)]
    # The click picker would have voiced that C from the G before it.
    assert picker_notes(GUITAR, [FIRST, C])[-1] != sheet_notes(env, 1)


def test_the_same_chord_sounds_the_same_however_often_and_after_whatever():
    env = SheetEnv(DESKTOP_QT, TEXT, voicing=GUITAR)
    for offset in (C, FIRST, C, G, C, C):
        env.session.tap_chord_at(offset)
    c_taps = [notes for notes, offset in zip(env.player.immediate, (C, FIRST, C, G, C, C))
              if offset == C]
    assert c_taps == [sheet_notes(env, 1)] * 4


def test_shift_click_rolls_the_same_notes():
    env = SheetEnv(DESKTOP_QT, TEXT, voicing=GUITAR)
    env.session.tap_chord_at(FIRST, rolled=True)
    env.session.tap_chord_at(C, rolled=True)
    assert [notes for notes, _gap in env.player.rolled] == [
        sorted(sheet_notes(env, 0)), sorted(sheet_notes(env, 1))]
    assert env.player.immediate == []


def test_a_sheet_card_tap_still_sounds_its_own_notes():
    env = SheetEnv(DESKTOP_QT, LOOPED)
    env.session.audition(4)
    assert env.player.immediate == [sheet_notes(env, 4)]


# -- loops ---------------------------------------------------------------------------------


def _played(env, n):
    thread = env.audio._render_thread
    if thread is not None:
        thread.join(timeout=10)
    env.host.run_pending()
    env.player.play(n)
    env.host.run_pending()


def _paused_in_the_second_pass(env):
    env.session.play_pause()
    _played(env, 5)                     # F# B C G C
    env.session.play_pause()
    assert env.session._playback.status is PlaybackStatus.PAUSED
    assert env.session._playback.chord_index == 4


def test_the_loop_voices_its_passes_differently():
    env = SheetEnv(DESKTOP_QT, LOOPED)
    assert [c.chord_info.chord for c in env.sheet.rendered_song.chords] == [
        "F#", "B", "C", "G", "C", "G"]
    assert sheet_notes(env, 2) != sheet_notes(env, 4)


@pytest.mark.parametrize("platform", [DESKTOP_QT, ANDROID])
def test_idle_a_looped_chord_sounds_as_in_its_first_pass(platform):
    env = SheetEnv(platform, LOOPED)
    env.session.tap_chord_at(L_C)
    assert env.player.immediate == [sheet_notes(env, 2)]
    assert env.recorder.last(ChordSheetState).cursor_index == 2


@pytest.mark.parametrize("platform", [DESKTOP_QT, ANDROID])
def test_paused_in_the_second_pass_a_chord_of_that_pass_sounds_as_there(platform):
    env = SheetEnv(platform, LOOPED)
    _paused_in_the_second_pass(env)
    env.session.tap_chord_at(L_C)
    assert env.player.immediate == [sheet_notes(env, 4)]
    # The tap drops the paused song and puts the playhead on that pass's card.
    assert env.session._playback.status is PlaybackStatus.IDLE
    assert env.recorder.last(ChordSheetState).cursor_index == 4
    assert env.session.timeline_position().bar == 5


def test_paused_in_the_second_pass_a_chord_before_the_loop_sounds_as_it_is():
    env = SheetEnv(DESKTOP_QT, LOOPED)
    _paused_in_the_second_pass(env)
    env.session.tap_chord_at(L_B)
    assert env.player.immediate == [sheet_notes(env, 1)]
    assert env.recorder.last(ChordSheetState).cursor_index == 1


def test_paused_in_the_first_pass_a_chord_of_the_loop_sounds_as_in_the_first_pass():
    env = SheetEnv(DESKTOP_QT, LOOPED)
    env.session.play_pause()
    _played(env, 4)                     # F# B C G
    env.session.play_pause()
    assert env.session._playback.chord_index == 3
    env.session.tap_chord_at(L_C)
    assert env.player.immediate == [sheet_notes(env, 2)]


def test_the_tk_desktop_playing_in_the_second_pass_sounds_that_pass():
    # The Tk desktop's taps don't seek: they sound over the song.
    env = SheetEnv(DESKTOP, LOOPED)
    env.session.play_pause()
    _played(env, 5)
    assert env.session._playback.status is PlaybackStatus.PLAYING
    env.session.tap_chord_at(L_G)
    assert env.player.immediate == [sheet_notes(env, 5)]
    assert env.session._playback.status is PlaybackStatus.PLAYING


def test_playing_on_the_qt_desktop_a_tap_still_only_jumps():
    env = SheetEnv(DESKTOP_QT, LOOPED)
    env.session.play_pause()
    _played(env, 5)
    env.session.tap_chord_at(L_G)
    assert env.player.immediate == []


# -- falling back to the click picker -------------------------------------------------------


def test_an_edited_text_falls_back_until_the_sheet_renders_it():
    env = SheetEnv(DESKTOP_QT, TEXT, voicing=GUITAR)
    rendered = env.sheet.rendered_song
    env.session.set_text("G  C  G  Am  C")        # detection still pending
    env.session.tap_chord_at(FIRST)
    env.session.tap_chord_at(C)
    assert env.player.immediate == picker_notes(GUITAR, [FIRST, C])
    # Detected, but the sheet's render is still the old text's (debounced).
    env.host.advance(0.6)                          # detection: 0.5 s, the sheet: 0.5 s more
    assert env.session._detected_text == env.session.text
    assert env.sheet.rendered_song is rendered and not env.sheet.render_is_current
    env.session.tap_chord_at(C)
    assert env.player.immediate[-1] == picker_notes(GUITAR, [FIRST, C, C])[-1] != sheet_notes(env, 1)
    # Rendered: the sheet's notes again.
    env.host.advance(2.0)
    assert env.sheet.render_is_current
    env.session.tap_chord_at(C)
    assert env.player.immediate[-1] == sheet_notes(env, 1)


def test_a_new_voicing_falls_back_until_the_sheet_renders_it():
    env = SheetEnv(DESKTOP_QT, TEXT)
    env.session.set_voicing(GUITAR)
    assert not env.sheet.render_is_current
    env.session.tap_chord_at(C)
    assert env.player.immediate == picker_notes(GUITAR, [C])
    env.host.advance(2.0)
    env.session.tap_chord_at(C)
    assert env.player.immediate[-1] == sheet_notes(env, 1) != env.player.immediate[0]


def test_a_hidden_sheet_that_never_rendered_falls_back():
    env = SheetEnv(DESKTOP_QT, voicing=GUITAR)
    env.session.set_chord_sheet_visible(False)
    env.session.set_text(TEXT)
    env.host.advance(2.0)
    assert env.sheet.rendered_song is None
    env.session.tap_chord_at(FIRST)
    env.session.tap_chord_at(C)
    assert env.player.immediate == picker_notes(GUITAR, [FIRST, C])


def _fake_chord(chord, start, notes):
    return SimpleNamespace(chord_info=SimpleNamespace(chord=chord, start=start,
                                                      end=start + len(chord)),
                           midi_notes=notes, skipped=False, bar=1, song_bar=1)


def test_a_render_without_the_chord_falls_back():
    env = FakeSheetEnv(DESKTOP_QT, text="C   G")
    # A render that has C but not G (e.g. a chord the song doesn't play).
    env.sheet.finish_render(SimpleNamespace(chords=[_fake_chord("C", 0, [1, 2, 3])],
                                            total_bars=1))
    env.session.tap_chord_at(0)
    assert env.sheet.auditioned == [0] and env.player.immediate == []
    env.session.tap_chord_at(4)
    assert env.sheet.auditioned == [0] and len(env.player.immediate) == 1


def test_a_render_of_another_chord_at_the_same_place_falls_back():
    env = FakeSheetEnv(DESKTOP_QT, text="C   G")
    env.sheet.finish_render(SimpleNamespace(
        chords=[_fake_chord("Cm", 0, [1, 2, 3]), _fake_chord("G", 4, [4, 5, 6])],
        total_bars=2))
    env.session.tap_chord_at(0)                     # "C" in the text, "Cm" rendered
    assert env.sheet.auditioned == [] and len(env.player.immediate) == 1
    env.session.tap_chord_at(4)
    assert env.sheet.auditioned == [1]


def test_a_render_from_before_the_last_feed_falls_back():
    env = FakeSheetEnv(DESKTOP_QT, text="C   G")
    env.sheet.finish_render(SimpleNamespace(
        chords=[_fake_chord("C", 0, [1, 2, 3]), _fake_chord("G", 4, [4, 5, 6])],
        total_bars=2))
    env.session.set_key("D")                        # fed again, not rendered yet
    env.session.tap_chord_at(0)
    assert env.sheet.auditioned == [] and len(env.player.immediate) == 1


def test_audio_that_fails_is_reported_like_any_tap():
    env = FakeSheetEnv(DESKTOP_QT, text="C   G")
    env.sheet.finish_render(SimpleNamespace(chords=[_fake_chord("C", 0, [1, 2, 3])],
                                            total_bars=1))
    env.sheet.audition_error = "no driver"
    env.session.tap_chord_at(0)
    assert env.status() == "Audio is not available"


# -- the setting off -------------------------------------------------------------------------


def test_off_clicks_voice_lead_from_the_chord_clicked_before():
    env = SheetEnv(DESKTOP_QT, TEXT, voicing=GUITAR, click_plays_chart_voicing=False)
    env.session.tap_chord_at(FIRST)
    env.session.tap_chord_at(C)
    assert env.player.immediate[-1] != sheet_notes(env, 1)
    # The PlaybackService's click picker, from the chord before.
    picker = env.audio._click_picker
    assert picker is not None
    assert env.player.immediate == picker_notes(GUITAR, [FIRST, C])


def test_the_setting_is_read_at_each_click():
    env = SheetEnv(DESKTOP_QT, TEXT, voicing=GUITAR)
    env.session.tap_chord_at(FIRST)
    env.config.set("click_plays_chart_voicing", False)
    env.session.tap_chord_at(C)
    assert env.player.immediate[-1] == picker_notes(GUITAR, [C])[-1] != sheet_notes(env, 1)
    env.config.set("click_plays_chart_voicing", True)
    env.session.tap_chord_at(C)
    assert env.player.immediate[-1] == sheet_notes(env, 1)


# -- the config and the settings ---------------------------------------------------------------


def test_the_config_keeps_the_setting():
    assert Config().click_plays_chart_voicing is True
    off = Config(click_plays_chart_voicing=False)
    assert off.to_dict()["click_plays_chart_voicing"] is False
    assert Config.from_dict(off.to_dict()).click_plays_chart_voicing is False
    assert Config.from_dict(Config().to_dict()).click_plays_chart_voicing is True


def test_an_older_config_without_the_key_has_it_on():
    data = Config().to_dict()
    del data["click_plays_chart_voicing"]
    assert Config.from_dict(data).click_plays_chart_voicing is True
    assert Config.from_dict({}).click_plays_chart_voicing is True


def test_the_settings_values_carry_it():
    assert SettingsValues.read(Config()).click_plays_chart_voicing is True
    values = SettingsValues.read(Config(click_plays_chart_voicing=False))
    assert values.click_plays_chart_voicing is False
    assert values.as_dict()["click_plays_chart_voicing"] is False


def test_a_settings_commit_saves_it_and_the_next_click_follows(tmp_path):
    from tests.test_word_wrap_setting import make, saved

    session, services, recorder = make(tmp_path)
    assert recorder.last(SettingsState).values.click_plays_chart_voicing is True
    session.begin_settings_edit()
    values = session.settings_values()
    session.commit_settings(SettingsValues(**{**values.as_dict(),
                                              "click_plays_chart_voicing": False}))
    assert saved(tmp_path)["click_plays_chart_voicing"] is False
    assert services.config.config.click_plays_chart_voicing is False
    assert recorder.last(SettingsState).values.click_plays_chart_voicing is False
    assert session._main.click_plays_chart_voicing is False


def test_a_saved_off_reads_back_off(tmp_path):
    from tests.test_word_wrap_setting import make

    session, _, recorder = make(tmp_path, config={"click_plays_chart_voicing": False})
    assert recorder.last(SettingsState).values.click_plays_chart_voicing is False
    assert session._main.click_plays_chart_voicing is False


def test_the_bridge_carries_it():
    from chordnotepad.session import bridge

    assert bridge.schema()["types"]["SettingsValues"]["fields"][
        "click_plays_chart_voicing"] == "bool"
