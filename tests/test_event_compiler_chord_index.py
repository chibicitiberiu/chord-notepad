"""The chord_index that ``compile_events`` carries on NOTE_ON/REST events.

The chord-sheet playhead is driven by this index rather than the chord's char
span so loop passes (which reuse pass-1 spans) advance the highlight forward
instead of jumping backward. The index is the position in the *unrolled*
``RenderedSong.chords`` list, so it also survives play-from-cursor (skipped
chords keep their slot in the list even though they emit no events).

The index lives in event metadata that the characterization golden serialization
deliberately ignores, so it never disturbs those goldens (asserted elsewhere).
"""
from audio.chord_picker import ChordNotePicker
from services.event_compiler import compile_events
from services.song_parser_service import SongParserService
from services.song_renderer import SongRenderer
from models.playback_event_internal import MidiEventType


def _render(text, *, start_line_index=0, start_item_index=0):
    lines = SongParserService().detect_chords_in_text(text)
    return SongRenderer().render(
        lines=lines,
        initial_key="C",
        initial_bpm=120,
        initial_time_sig=(4, 4),
        note_picker=ChordNotePicker(),
        start_line_index=start_line_index,
        start_item_index=start_item_index,
    )


def _note_ons(events):
    return [e for e in events if e.event_type == MidiEventType.NOTE_ON]


def test_chord_index_matches_position_in_unrolled_song():
    rendered = _render("C G\nAm F\n")
    events = compile_events(rendered, has_callback=True)
    note_ons = _note_ons(events)
    # One NOTE_ON per (non-rest, non-skipped) chord; the carried index points at
    # exactly that chord in rendered.chords.
    for ev in note_ons:
        idx = ev.metadata["chord_index"]
        assert rendered.chords[idx].chord_info is ev.metadata["chord_info"]


def test_chord_index_advances_across_loop_seam():
    # Two passes of a two-chord section: the loop replays share char spans but
    # get fresh indices, so the carried index is strictly increasing.
    rendered = _render("{label: verse}\nC G\n{loop: verse 2}\n")
    events = compile_events(rendered, has_callback=True)
    indices = [e.metadata["chord_index"] for e in _note_ons(events)]
    assert indices == sorted(indices)
    assert len(set(indices)) == len(indices)  # no repeats across the seam
    assert len(indices) == 4  # C G played twice


def test_chord_index_survives_play_from_cursor_skip():
    # Start at line 1 (Am): the two skipped chords keep their slots (indices 0,1)
    # in the unrolled list, so the first emitted NOTE_ON carries index 2.
    rendered = _render("C G\nAm F\n", start_line_index=1, start_item_index=0)
    events = compile_events(rendered, has_callback=True)
    note_ons = _note_ons(events)
    first_idx = note_ons[0].metadata["chord_index"]
    assert rendered.chords[first_idx].chord_info.chord == "Am"
    # Skipped chords precede it in the list, so its index is offset past them.
    assert first_idx == 2
