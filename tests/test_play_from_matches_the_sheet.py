"""Play from the cursor sounds every chord as the chord sheet shows it.

Tibi, 2026-11-17: after switching from Treble Choir to String Quartet, a
chord clicked in the piano roll sounded an octave above what Play sounded.
The note log showed it: Play started from the playhead, and a render from the
cursor voiced its first chord fresh, while the sheet (and so a click) voices
from the top of the song. Each voicing follows from the one before, so the
two settled an octave apart for the rest of the song. Now a render from the
cursor voices the chords before it too, for context, and drops them.

The real session, ChordSheetViewModel and PlaybackService over a FakePlayer
(``tests.test_chord_sheet_playhead.Env``).
"""

from pathlib import Path

import pytest

from chordnotepad.models.playback_event_internal import MidiEventType
from chordnotepad.session.platform import DESKTOP_QT
from tests.test_chord_sheet_playhead import Env

QUICK_START = (Path(__file__).resolve().parents[1] / "examples" / "01_quick_start.txt").read_text(
    encoding="utf-8")

# Small enough to run every start; a loop and a mid-song key change, so the
# lead-in crosses both.
LOOPED = ("{key: C}\nC  Am  F  G\n{label: chorus}\nC/E  F  Dm7  G7\n{loop: chorus 2}\n"
          "{key: D}\nD  Bm  G  A\n")


def _first_played(env):
    env.player.play(1)
    env.host.run_pending()
    ons = [e for e in env.player.played if e.event_type == MidiEventType.NOTE_ON]
    return sorted(ons[0].midi_notes)


@pytest.mark.parametrize("voicing", ["piano", "guitar:standard", "ensemble:quartet",
                                     "ensemble:ssa"])
def test_playing_from_any_chord_sounds_it_as_the_sheet_shows_it(voicing):
    top = Env(DESKTOP_QT, LOOPED, voicing=voicing)
    chords = top.sheet.rendered_song.chords
    starts = sorted({c.chord_info.start for c in chords if c.midi_notes})
    expected = {}
    for c in chords:                       # a looped chord starts in its first pass
        if c.midi_notes and c.chord_info.start not in expected:
            expected[c.chord_info.start] = sorted(c.midi_notes)
    for start in starts:
        env = Env(DESKTOP_QT, LOOPED, voicing=voicing)
        env.play_from(start)
        assert _first_played(env) == expected[start], (voicing, LOOPED[start:start + 5])


@pytest.mark.parametrize("voicing", ["ensemble:quartet", "piano"])
def test_the_quick_start_from_its_duration_verse_sounds_as_the_sheet(voicing):
    # Tibi's case: Play from the Duration verse (C C/B Am Em/G ...) on a String Quartet.
    top = Env(DESKTOP_QT, QUICK_START, voicing=voicing)
    chords = top.sheet.rendered_song.chords
    verse = QUICK_START.index("C*2   C/B*2")
    index = next(i for i, c in enumerate(chords) if c.chord_info.start == verse)
    sheet = [sorted(c.midi_notes) for c in chords[index:] if c.midi_notes]
    env = Env(DESKTOP_QT, QUICK_START, voicing=voicing)
    env.play_from(verse)
    env.player.play(len(sheet))
    env.host.run_pending()
    played = [sorted(e.midi_notes) for e in env.player.played
              if e.event_type == MidiEventType.NOTE_ON]
    assert played == sheet[:len(played)] and len(played) >= 8
