"""Tests for the Standard MIDI File writer.

Each test builds a ``RenderedSong`` (by hand, or via the real render pipeline for
the integration checks), writes it with ``write_midi_file``, reads the file back
with ``mido``, and asserts on the absolute-tick reconstruction of each track.
"""
import pytest
import mido

from services.midi_file_writer import write_midi_file, PPQ
from services.song_renderer import SongRenderer
from audio.chord_picker import ChordNotePicker
from models.rendered_song import RenderedSong, RenderedChord
from models.chord import ChordInfo
from exceptions import FileOperationError


def make_chord(
    symbol="C",
    *,
    midi_notes=(48, 60, 64, 67),
    voice_notes=None,
    start_beat=0.0,
    duration_beats=4.0,
    bpm=120,
    time_sig=(4, 4),
    key=None,
    is_rest=False,
    skipped=False,
):
    """Build a RenderedChord with sensible defaults for writer tests."""
    return RenderedChord(
        chord_info=ChordInfo(chord=symbol, start=0, end=len(symbol), is_valid=True),
        chord_notes=None,
        midi_notes=None if (is_rest or skipped) else list(midi_notes),
        line_index=0,
        item_index=0,
        start_beat=start_beat,
        duration_beats=duration_beats,
        start_time=0.0,
        duration_seconds=0.0,
        bpm=bpm,
        time_sig=time_sig,
        key=key,
        bar=1,
        is_rest=is_rest,
        skipped=skipped,
        voice_notes=list(voice_notes) if voice_notes is not None else None,
    )


def abs_messages(track):
    """Return (absolute_tick, message) pairs for a mido track."""
    out = []
    t = 0
    for msg in track:
        t += msg.time
        out.append((t, msg))
    return out


def messages_of_type(track, msg_type):
    """Return (absolute_tick, message) pairs of a given message type."""
    return [(t, m) for t, m in abs_messages(track) if m.type == msg_type]


def read_back(rendered, tmp_path, name="out.mid", **kwargs):
    """Write a RenderedSong to a temp file and read it back with mido."""
    path = tmp_path / name
    write_midi_file(rendered, path, **kwargs)
    return mido.MidiFile(str(path))


def test_header_format_and_ppq(tmp_path):
    rendered = RenderedSong(chords=[make_chord()], total_beats=4.0)
    midi = read_back(rendered, tmp_path)
    assert midi.type == 1
    assert midi.ticks_per_beat == PPQ
    assert len(midi.tracks) == 2


def test_simple_44_song(tmp_path):
    """C then G, 4 beats each, at bpm 120."""
    rendered = RenderedSong(
        chords=[
            make_chord("C", midi_notes=[48, 60, 64, 67], start_beat=0.0, duration_beats=4.0),
            make_chord("G", midi_notes=[43, 59, 62, 67], start_beat=4.0, duration_beats=4.0),
        ],
        total_beats=8.0,
        tempo_map=[(0.0, 120)],
        meter_map=[(0.0, (4, 4))],
    )
    midi = read_back(rendered, tmp_path, title="My Song")
    conductor, chords = midi.tracks

    # Single tempo of 500000 us/quarter.
    tempos = messages_of_type(conductor, "set_tempo")
    assert [(t, m.tempo) for t, m in tempos] == [(0, 500000)]

    # 4/4 time signature at tick 0.
    sigs = messages_of_type(conductor, "time_signature")
    assert len(sigs) == 1
    assert (sigs[0][1].numerator, sigs[0][1].denominator) == (4, 4)

    # Track name honours the title.
    names = messages_of_type(conductor, "track_name")
    assert names[0][1].name == "My Song"

    # program_change present at tick 0 on the chord track.
    progs = messages_of_type(chords, "program_change")
    assert progs and progs[0][0] == 0

    # note_on at ticks 0 and 1920; note_off at 1920 and 3840.
    on_ticks = sorted({t for t, m in messages_of_type(chords, "note_on")})
    off_ticks = sorted({t for t, m in messages_of_type(chords, "note_off")})
    assert on_ticks == [0, 1920]
    assert off_ticks == [1920, 3840]

    # velocity 100 on every note_on.
    assert all(m.velocity == 100 for _, m in messages_of_type(chords, "note_on"))


def test_default_title(tmp_path):
    rendered = RenderedSong(chords=[make_chord()], total_beats=4.0)
    midi = read_back(rendered, tmp_path)
    names = messages_of_type(midi.tracks[0], "track_name")
    assert names[0][1].name == "Chord Notepad export"


def test_program_number_respected(tmp_path):
    rendered = RenderedSong(chords=[make_chord()], total_beats=4.0)
    midi = read_back(rendered, tmp_path, program=24)
    progs = messages_of_type(midi.tracks[1], "program_change")
    assert progs[0][1].program == 24


def test_tempo_change_mid_song(tmp_path):
    rendered = RenderedSong(
        chords=[
            make_chord("C", start_beat=0.0, duration_beats=4.0, bpm=120),
            make_chord("G", start_beat=4.0, duration_beats=4.0, bpm=240),
        ],
        total_beats=8.0,
        tempo_map=[(0.0, 120), (4.0, 240)],
        meter_map=[(0.0, (4, 4))],
    )
    midi = read_back(rendered, tmp_path)
    tempos = messages_of_type(midi.tracks[0], "set_tempo")
    assert [(t, m.tempo) for t, m in tempos] == [(0, 500000), (1920, 250000)]


def test_meter_change_alters_tempo_and_ticks(tmp_path):
    """6/8 at constant bpm: unit=8 makes set_tempo 1_000_000 us/quarter, and
    ticks after the change accrue at 240 per beat."""
    rendered = RenderedSong(
        chords=[
            make_chord("C", start_beat=0.0, duration_beats=4.0, time_sig=(4, 4)),
            make_chord("G", start_beat=4.0, duration_beats=6.0, time_sig=(6, 8)),
        ],
        total_beats=10.0,
        tempo_map=[(0.0, 120)],
        meter_map=[(0.0, (4, 4)), (4.0, (6, 8))],
    )
    midi = read_back(rendered, tmp_path)
    conductor, chords = midi.tracks

    tempos = messages_of_type(conductor, "set_tempo")
    assert [(t, m.tempo) for t, m in tempos] == [(0, 500000), (1920, 1_000_000)]

    sigs = messages_of_type(conductor, "time_signature")
    assert [(t, m.numerator, m.denominator) for t, m in sigs] == [
        (0, 4, 4), (1920, 6, 8),
    ]

    # G note_on at tick 1920; note_off at 1920 + 6*240 = 3360.
    on_ticks = sorted({t for t, m in messages_of_type(chords, "note_on")})
    off_ticks = sorted({t for t, m in messages_of_type(chords, "note_off")})
    assert 1920 in on_ticks
    assert 3360 in off_ticks


def test_rest_gap_leaves_silence(tmp_path):
    """chord, rest, chord: the second chord starts after the rest's beats and no
    events are emitted during the rest."""
    rendered = RenderedSong(
        chords=[
            make_chord("C", start_beat=0.0, duration_beats=4.0),
            make_chord("NC", start_beat=4.0, duration_beats=4.0, is_rest=True),
            make_chord("G", start_beat=8.0, duration_beats=4.0),
        ],
        total_beats=12.0,
        tempo_map=[(0.0, 120)],
        meter_map=[(0.0, (4, 4))],
    )
    midi = read_back(rendered, tmp_path)
    on_ticks = sorted({t for t, m in messages_of_type(midi.tracks[1], "note_on")})
    # C at 0, G at 8 beats = 3840 tick. Nothing at 1920 (the rest).
    assert on_ticks == [0, 3840]


def test_skipped_chords_emit_nothing(tmp_path):
    rendered = RenderedSong(
        chords=[
            make_chord("C", start_beat=0.0, duration_beats=4.0, skipped=True),
            make_chord("G", start_beat=4.0, duration_beats=4.0),
        ],
        total_beats=8.0,
        tempo_map=[(0.0, 120)],
        meter_map=[(0.0, (4, 4))],
    )
    midi = read_back(rendered, tmp_path)
    on_ticks = sorted({t for t, m in messages_of_type(midi.tracks[1], "note_on")})
    # Only the G chord (at tick 1920) sounds.
    assert on_ticks == [1920]


def test_fractional_duration_rounds(tmp_path):
    """A 4.5-beat chord rounds its note_off tick correctly."""
    rendered = RenderedSong(
        chords=[make_chord("C", start_beat=0.0, duration_beats=4.5)],
        total_beats=4.5,
        tempo_map=[(0.0, 120)],
        meter_map=[(0.0, (4, 4))],
    )
    midi = read_back(rendered, tmp_path)
    off_ticks = sorted({t for t, m in messages_of_type(midi.tracks[1], "note_off")})
    # 4.5 beats * 480 ticks/beat = 2160.
    assert off_ticks == [2160]


def test_key_change_emits_two_key_signatures(tmp_path):
    rendered = RenderedSong(
        chords=[
            make_chord("C", start_beat=0.0, duration_beats=4.0, key="C"),
            make_chord("G", start_beat=4.0, duration_beats=4.0, key="G"),
        ],
        total_beats=8.0,
        tempo_map=[(0.0, 120)],
        meter_map=[(0.0, (4, 4))],
    )
    midi = read_back(rendered, tmp_path)
    keys = messages_of_type(midi.tracks[0], "key_signature")
    assert [(t, m.key) for t, m in keys] == [(0, "C"), (1920, "G")]


def test_repeated_key_not_re_emitted(tmp_path):
    rendered = RenderedSong(
        chords=[
            make_chord("C", start_beat=0.0, duration_beats=4.0, key="C"),
            make_chord("G", start_beat=4.0, duration_beats=4.0, key="C"),
        ],
        total_beats=8.0,
    )
    midi = read_back(rendered, tmp_path)
    keys = messages_of_type(midi.tracks[0], "key_signature")
    assert [(t, m.key) for t, m in keys] == [(0, "C")]


def test_non_power_of_two_denominator_skips_time_signature(tmp_path):
    rendered = RenderedSong(
        chords=[make_chord("C", start_beat=0.0, duration_beats=3.0, time_sig=(3, 5))],
        total_beats=3.0,
        tempo_map=[(0.0, 120)],
        meter_map=[(0.0, (3, 5))],
    )
    midi = read_back(rendered, tmp_path)
    conductor, chords = midi.tracks
    # No time_signature meta was written.
    assert messages_of_type(conductor, "time_signature") == []
    # Notes are still placed.
    assert messages_of_type(chords, "note_on")


def test_out_of_range_notes_skipped(tmp_path):
    rendered = RenderedSong(
        chords=[make_chord("C", midi_notes=[-5, 60, 200, 64], start_beat=0.0, duration_beats=4.0)],
        total_beats=4.0,
    )
    midi = read_back(rendered, tmp_path)
    notes = {m.note for _, m in messages_of_type(midi.tracks[1], "note_on")}
    assert notes == {60, 64}


def test_io_failure_raises_file_operation_error(tmp_path):
    rendered = RenderedSong(chords=[make_chord()], total_beats=4.0)
    bad_path = tmp_path / "does_not_exist" / "out.mid"
    with pytest.raises(FileOperationError):
        write_midi_file(rendered, bad_path)


def test_end_of_track_covers_total_beats(tmp_path):
    rendered = RenderedSong(
        chords=[make_chord("C", start_beat=0.0, duration_beats=4.0)],
        total_beats=8.0,  # song longer than the last note
        tempo_map=[(0.0, 120)],
        meter_map=[(0.0, (4, 4))],
    )
    midi = read_back(rendered, tmp_path)
    for track in midi.tracks:
        end = messages_of_type(track, "end_of_track")
        assert end and end[0][0] >= 3840  # tick(total_beats=8) == 3840


def test_integration_render_pipeline_deterministic(song_parser, tmp_path):
    """Build a RenderedSong via the real pipeline and confirm two writes are
    byte-identical."""
    text = "C G\nAm F\n{loop: @start 2}"
    lines = song_parser.detect_chords_in_text(text)

    picker = ChordNotePicker()
    picker.reset()
    rendered = SongRenderer().render(lines, "C", 120, (4, 4), picker)
    assert rendered is not None

    path_a = tmp_path / "a.mid"
    path_b = tmp_path / "b.mid"
    write_midi_file(rendered, path_a, title="Song")
    write_midi_file(rendered, path_b, title="Song")

    assert path_a.read_bytes() == path_b.read_bytes()

    # Sanity: the file is a readable format-1 SMF with note content.
    midi = mido.MidiFile(str(path_a))
    assert midi.type == 1
    assert messages_of_type(midi.tracks[1], "note_on")


# ---------------------------------------------------------------------------
# Per-voice export (RenderedSong.voice_labels / RenderedChord.voice_notes)
# ---------------------------------------------------------------------------

SATB_LABELS = ["Bass", "Tenor", "Alto", "Soprano"]  # low to high


def test_no_voice_labels_uses_single_chords_track(tmp_path):
    """Baseline (no voice_labels): unchanged from before per-voice support."""
    rendered = RenderedSong(
        chords=[
            make_chord("C", start_beat=0.0, duration_beats=4.0),
            make_chord("G", start_beat=4.0, duration_beats=4.0),
        ],
        total_beats=8.0,
        tempo_map=[(0.0, 120)],
        meter_map=[(0.0, (4, 4))],
    )
    assert rendered.voice_labels is None
    midi = read_back(rendered, tmp_path)
    assert len(midi.tracks) == 2
    names = messages_of_type(midi.tracks[1], "track_name")
    assert names[0][1].name == "Chords"


def test_per_voice_tracks_order_names_and_pitches(tmp_path):
    """SATB voice_labels (low->high) produce 5 tracks, top-voice-first after
    the conductor, each carrying only that voice's note per chord."""
    rendered = RenderedSong(
        chords=[
            make_chord(
                "C", midi_notes=[48, 60, 64, 67],
                voice_notes=[48, 60, 64, 67],  # Bass, Tenor, Alto, Soprano
                start_beat=0.0, duration_beats=4.0,
            ),
            make_chord(
                "G", midi_notes=[43, 59, 62, 67],
                voice_notes=[43, 59, 62, 67],
                start_beat=4.0, duration_beats=4.0,
            ),
        ],
        total_beats=8.0,
        tempo_map=[(0.0, 120)],
        meter_map=[(0.0, (4, 4))],
        voice_labels=list(SATB_LABELS),
    )
    midi = read_back(rendered, tmp_path)

    assert len(midi.tracks) == 5

    names = [messages_of_type(t, "track_name")[0][1].name for t in midi.tracks]
    assert names == ["Chord Notepad export", "Soprano", "Alto", "Tenor", "Bass"]

    conductor, soprano, alto, tenor, bass = midi.tracks

    def notes_on(track):
        return sorted({m.note for _, m in messages_of_type(track, "note_on")})

    assert notes_on(soprano) == [67]
    assert notes_on(alto) == [62, 64]
    assert notes_on(tenor) == [59, 60]
    assert notes_on(bass) == [43, 48]

    # Each voice track still has its own program_change and end_of_track.
    for track in (soprano, alto, tenor, bass):
        assert messages_of_type(track, "program_change")
        assert messages_of_type(track, "end_of_track")


def test_per_voice_tracks_preserve_unison(tmp_path):
    """A unison (two adjacent voices sharing a pitch) is duplicated across
    both voice tracks, not collapsed."""
    rendered = RenderedSong(
        chords=[
            make_chord(
                "C", midi_notes=[48, 60, 64, 67],
                voice_notes=[48, 48, 64, 67],  # Bass and Tenor unison at 48
                start_beat=0.0, duration_beats=4.0,
            ),
        ],
        total_beats=4.0,
        tempo_map=[(0.0, 120)],
        meter_map=[(0.0, (4, 4))],
        voice_labels=list(SATB_LABELS),
    )
    midi = read_back(rendered, tmp_path)
    conductor, soprano, alto, tenor, bass = midi.tracks

    assert {m.note for _, m in messages_of_type(tenor, "note_on")} == {48}
    assert {m.note for _, m in messages_of_type(bass, "note_on")} == {48}


def test_per_voice_track_program_number_respected(tmp_path):
    rendered = RenderedSong(
        chords=[
            make_chord(
                "C", midi_notes=[48, 60, 64, 67],
                voice_notes=[48, 60, 64, 67],
                start_beat=0.0, duration_beats=4.0,
            ),
        ],
        total_beats=4.0,
        voice_labels=list(SATB_LABELS),
    )
    midi = read_back(rendered, tmp_path, program=52)
    for track in midi.tracks[1:]:
        progs = messages_of_type(track, "program_change")
        assert progs[0][1].program == 52


def test_missing_voice_notes_falls_back_to_single_track(tmp_path):
    """If any played chord lacks voice_notes (or has a mismatched length),
    the whole export falls back to the single 'Chords' track."""
    rendered = RenderedSong(
        chords=[
            make_chord(
                "C", midi_notes=[48, 60, 64, 67],
                voice_notes=[48, 60, 64, 67],
                start_beat=0.0, duration_beats=4.0,
            ),
            make_chord(
                "G", midi_notes=[43, 59, 62, 67],
                voice_notes=None,  # missing
                start_beat=4.0, duration_beats=4.0,
            ),
        ],
        total_beats=8.0,
        tempo_map=[(0.0, 120)],
        meter_map=[(0.0, (4, 4))],
        voice_labels=list(SATB_LABELS),
    )
    midi = read_back(rendered, tmp_path)
    assert len(midi.tracks) == 2
    names = messages_of_type(midi.tracks[1], "track_name")
    assert names[0][1].name == "Chords"
    # Both chords' full midi_notes are present on the combined track.
    on_notes = {m.note for _, m in messages_of_type(midi.tracks[1], "note_on")}
    assert on_notes == {48, 60, 64, 67, 43, 59, 62}


def test_mismatched_voice_notes_length_falls_back_to_single_track(tmp_path):
    rendered = RenderedSong(
        chords=[
            make_chord(
                "C", midi_notes=[48, 60, 64, 67],
                voice_notes=[48, 60, 64],  # only 3 entries for 4 voice_labels
                start_beat=0.0, duration_beats=4.0,
            ),
        ],
        total_beats=4.0,
        voice_labels=list(SATB_LABELS),
    )
    midi = read_back(rendered, tmp_path)
    assert len(midi.tracks) == 2
    assert messages_of_type(midi.tracks[1], "track_name")[0][1].name == "Chords"


def test_skipped_and_rest_chords_ignored_by_voice_notes_guard(tmp_path):
    """A skipped chord or a rest with no voice_notes must not block per-voice
    export -- only *played* chords (not skipped, not rest) need voice_notes."""
    rendered = RenderedSong(
        chords=[
            make_chord(
                "C", midi_notes=[48, 60, 64, 67], voice_notes=None,
                start_beat=0.0, duration_beats=4.0, skipped=True,
            ),
            make_chord(
                "NC", is_rest=True, voice_notes=None,
                start_beat=4.0, duration_beats=4.0,
            ),
            make_chord(
                "G", midi_notes=[43, 59, 62, 67],
                voice_notes=[43, 59, 62, 67],
                start_beat=8.0, duration_beats=4.0,
            ),
        ],
        total_beats=12.0,
        voice_labels=list(SATB_LABELS),
    )
    midi = read_back(rendered, tmp_path)
    assert len(midi.tracks) == 5
    names = [messages_of_type(t, "track_name")[0][1].name for t in midi.tracks]
    assert names == ["Chord Notepad export", "Soprano", "Alto", "Tenor", "Bass"]
