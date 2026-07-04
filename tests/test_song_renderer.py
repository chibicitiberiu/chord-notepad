"""Comprehensive tests for SongRenderer + event compiler.

These port the old EventProducer unit tests onto the pre-render pipeline. Each
test renders a song synchronously with ``SongRenderer`` and flattens it with
``compile_events`` (has_callback=False), then asserts on the resulting event
stream -- exactly the behaviours the streaming producer used to guarantee.
"""
import pytest
from unittest.mock import MagicMock

from services.song_renderer import SongRenderer
from services.event_compiler import compile_events
from audio.chord_picker import ChordNotePicker
from models.line import Line
from models.chord import ChordInfo
from models.directive import Directive, DirectiveType, BPMModifierType
from models.playback_event_internal import MidiEvent, MidiEventType


@pytest.fixture
def note_picker():
    """Create a real note picker."""
    return ChordNotePicker()


@pytest.fixture
def simple_song():
    """Create a simple song with chords."""
    line1 = Line(content="C G Am F", line_number=1)
    chord_c = ChordInfo(chord="C", start=0, end=1, is_relative=False, is_valid=True)
    chord_g = ChordInfo(chord="G", start=2, end=3, is_relative=False, is_valid=True)
    chord_am = ChordInfo(chord="Am", start=4, end=6, is_relative=False, is_valid=True)
    chord_f = ChordInfo(chord="F", start=7, end=8, is_relative=False, is_valid=True)
    line1.items = [chord_c, chord_g, chord_am, chord_f]
    return [line1]


def render_events(
    lines,
    *,
    note_picker=None,
    initial_key="C",
    initial_bpm=120,
    initial_time_sig=(4, 4),
    start_line_index=0,
    start_item_index=0,
):
    """Render lines and return the full MidiEvent stream (incl. END_OF_SONG)."""
    if note_picker is None:
        note_picker = ChordNotePicker()
    note_picker.reset()
    rendered = SongRenderer().render(
        lines=lines,
        initial_key=initial_key,
        initial_bpm=initial_bpm,
        initial_time_sig=initial_time_sig,
        note_picker=note_picker,
        start_line_index=start_line_index,
        start_item_index=start_item_index,
    )
    return compile_events(rendered, has_callback=False)


class TestMetronomeTicks:
    """The pipeline always emits METRONOME_TICK events alongside chord events.

    Whether they sound is decided by the player at consumption time (it
    mutes/unmutes the drum channel via CC 7). ``is_downbeat`` is derived from
    the absolute beat counter modulo the current time signature.
    """

    def test_one_tick_per_beat_in_44(self, simple_song, note_picker):
        events = render_events(simple_song, note_picker=note_picker)
        ticks = [e for e in events if e.event_type == MidiEventType.METRONOME_TICK]
        # 4 chords * 4 beats per chord (default to time-sig beats per measure)
        assert len(ticks) == 16

    def test_downbeat_every_first_beat_of_measure(self, simple_song, note_picker):
        events = render_events(simple_song, note_picker=note_picker)
        ticks = [e for e in events if e.event_type == MidiEventType.METRONOME_TICK]
        downbeats = [t.metadata.get('is_downbeat') for t in ticks]
        assert downbeats == [
            True, False, False, False,
            True, False, False, False,
            True, False, False, False,
            True, False, False, False,
        ]

    def test_ticks_align_with_chord_start(self, simple_song, note_picker):
        events = render_events(simple_song, note_picker=note_picker)
        ticks = [e for e in events if e.event_type == MidiEventType.METRONOME_TICK]
        note_ons = [e for e in events if e.event_type == MidiEventType.NOTE_ON]
        # First tick of each chord coincides with its NOTE_ON.
        first_chord_tick_ts = [ticks[i * 4].timestamp for i in range(len(note_ons))]
        note_on_ts = [e.timestamp for e in note_ons]
        assert first_chord_tick_ts == pytest.approx(note_on_ts)

    def test_time_signature_directive_changes_downbeat_pattern(self, note_picker):
        # 4/4 chord (4 ticks: down, up, up, up), then a time-sig directive
        # switches to 3/4 and another chord (3 ticks).
        chord_a = ChordInfo(chord="C", start=0, end=1, is_relative=False, is_valid=True, duration=4)
        chord_b = ChordInfo(chord="G", start=2, end=3, is_relative=False, is_valid=True, duration=3)
        time_sig_change = Directive(
            type=DirectiveType.TIME_SIGNATURE, start=0, end=0,
            beats=3, unit=4, is_valid=True,
        )
        line = Line(content="", line_number=1)
        line.items = [chord_a, time_sig_change, chord_b]

        events = render_events([line], note_picker=note_picker)
        ticks = [e for e in events if e.event_type == MidiEventType.METRONOME_TICK]
        downs = [t.metadata.get('is_downbeat') for t in ticks]
        # 4/4 measure: down + 3 ups.
        # Absolute beat counter persists across the time-sig switch; downbeat
        # is now (beat % 3 == 0). So beat 4 % 3 == 1 (up), beat 5 (up), beat 6 (down).
        assert downs == [True, False, False, False, False, False, True]


class TestBasics:
    """Basic rendering functionality."""

    def test_generates_events(self, simple_song, note_picker):
        events = render_events(simple_song, note_picker=note_picker)

        note_on_events = [e for e in events if e.event_type == MidiEventType.NOTE_ON]
        note_off_events = [e for e in events if e.event_type == MidiEventType.NOTE_OFF]
        end_events = [e for e in events if e.event_type == MidiEventType.END_OF_SONG]

        assert len(note_on_events) == 4, "Should have 4 NOTE_ON events"
        assert len(note_off_events) == 4, "Should have 4 NOTE_OFF events"
        assert len(end_events) == 1, "Should have 1 END_OF_SONG event"

    def test_events_have_increasing_timestamps(self, simple_song, note_picker):
        events = render_events(simple_song, note_picker=note_picker)
        for i in range(1, len(events)):
            assert events[i].timestamp >= events[i - 1].timestamp, \
                f"Event {i} timestamp should be >= previous event"

    def test_end_of_song_is_last(self, simple_song, note_picker):
        events = render_events(simple_song, note_picker=note_picker)
        assert events[-1].event_type == MidiEventType.END_OF_SONG


class TestLoopAndBarAccounting:
    """Loops must repeat the right number of times AND the bar counter must
    advance through the repeats so status-bar 'Bar X / Y' stays consistent.
    """

    @staticmethod
    def _song_with_loop(loop_count):
        from services.song_parser_service import SongParserService
        text = "{label: a} C*4\n{loop: a " + str(loop_count) + "}"
        return SongParserService().detect_chords_in_text(text)

    def test_loop_count_3_plays_3_times(self, note_picker):
        events = render_events(self._song_with_loop(3), note_picker=note_picker)
        note_ons = [e for e in events if e.event_type == MidiEventType.NOTE_ON]
        assert len(note_ons) == 3

    def test_loop_count_4_plays_4_times(self, note_picker):
        events = render_events(self._song_with_loop(4), note_picker=note_picker)
        note_ons = [e for e in events if e.event_type == MidiEventType.NOTE_ON]
        assert len(note_ons) == 4

    def test_total_bars_reflects_loop_replays(self, note_picker):
        events = render_events(self._song_with_loop(3), note_picker=note_picker)
        note_ons = [e for e in events if e.event_type == MidiEventType.NOTE_ON]
        # Three full-measure plays of a single 4-beat chord in 4/4 = 3 bars.
        assert [e.metadata['total_bars'] for e in note_ons] == [3, 3, 3]

    def test_current_bar_advances_through_loop(self, note_picker):
        events = render_events(self._song_with_loop(4), note_picker=note_picker)
        note_ons = [e for e in events if e.event_type == MidiEventType.NOTE_ON]
        assert [e.metadata['bar'] for e in note_ons] == [1, 2, 3, 4]

    def test_at_start_is_builtin_label(self, note_picker):
        """'@start' loops the whole document without an explicit {label: @start}."""
        from services.song_parser_service import SongParserService
        text = "C*4\nG*4\n{loop: @start 2}"
        lines = SongParserService().detect_chords_in_text(text)
        events = render_events(lines, note_picker=note_picker)
        note_ons = [e for e in events if e.event_type == MidiEventType.NOTE_ON]
        # Two chords, then the whole document repeated once more = 4 plays.
        assert len(note_ons) == 4

    def test_at_start_bar_count_includes_replay(self, note_picker):
        """Bar accounting must include the @start replay."""
        from services.song_parser_service import SongParserService
        text = "C*4\nG*4\n{loop: @start 2}"
        lines = SongParserService().detect_chords_in_text(text)
        events = render_events(lines, note_picker=note_picker)
        note_ons = [e for e in events if e.event_type == MidiEventType.NOTE_ON]
        assert [e.metadata['bar'] for e in note_ons] == [1, 2, 3, 4]
        assert all(e.metadata['total_bars'] == 4 for e in note_ons)

    def test_time_signature_change_flushes_partial_bar(self, note_picker):
        from services.song_parser_service import SongParserService
        text = "C*4\n{time: 3/4}\nG*3 F*3"
        lines = SongParserService().detect_chords_in_text(text)
        events = render_events(lines, note_picker=note_picker)
        note_ons = [e for e in events if e.event_type == MidiEventType.NOTE_ON]
        bars = [e.metadata['bar'] for e in note_ons]
        # 4/4 measure of C, then 3/4 measure of G, then 3/4 measure of F.
        assert bars == [1, 2, 3]


class TestDirectives:
    """Directive handling in the renderer."""

    def test_bpm_directive(self, note_picker):
        """BPM directive changes tempo (verified by event timing + metadata)."""
        line = Line(content="{bpm: 140} C", line_number=1)
        bpm_dir = Directive(type=DirectiveType.BPM, start=0, end=11, is_valid=True)
        bpm_dir.bpm = 140
        bpm_dir.bpm_modifier_type = BPMModifierType.ABSOLUTE
        chord = ChordInfo(chord="C", start=12, end=13, is_relative=False, is_valid=True)
        line.items = [bpm_dir, chord]

        events = render_events([line], note_picker=note_picker)
        note_on_events = [e for e in events if e.event_type == MidiEventType.NOTE_ON]
        note_off_events = [e for e in events if e.event_type == MidiEventType.NOTE_OFF]

        assert len(note_on_events) >= 1
        assert len(note_off_events) >= 1

        # BPM is baked into the event metadata and timing.
        assert note_on_events[0].metadata['bpm'] == 140
        duration = note_off_events[0].timestamp - note_on_events[0].timestamp
        expected_duration = 4.0 * (60.0 / 140.0)  # 4 beats at BPM 140
        assert abs(duration - expected_duration) < 0.1

    def test_key_directive_with_roman_numerals(self, note_picker):
        """Key directive affects roman numeral resolution."""
        line = Line(content="{key: G} I V", line_number=1)
        key_dir = Directive(type=DirectiveType.KEY, start=0, end=8, is_valid=True)
        key_dir.key = "G"
        chord_I = ChordInfo(chord="I", start=9, end=10, is_relative=True, is_valid=True)
        chord_V = ChordInfo(chord="V", start=11, end=12, is_relative=True, is_valid=True)
        line.items = [key_dir, chord_I, chord_V]

        events = render_events([line], note_picker=note_picker)
        note_on_events = [e for e in events if e.event_type == MidiEventType.NOTE_ON]
        assert len(note_on_events) == 2, "Should have events for both chords"
        assert all(e.metadata['key'] == "G" for e in note_on_events)


class TestNoteOnOff:
    """NOTE_ON and NOTE_OFF event generation."""

    def test_note_on_off_pairs(self, simple_song, note_picker):
        events = render_events(simple_song, note_picker=note_picker)
        note_on_events = [e for e in events if e.event_type == MidiEventType.NOTE_ON]
        note_off_events = [e for e in events if e.event_type == MidiEventType.NOTE_OFF]

        assert len(note_on_events) == len(note_off_events)
        for i in range(len(note_on_events)):
            assert note_off_events[i].timestamp > note_on_events[i].timestamp

    def test_note_off_contains_same_notes(self, simple_song, note_picker):
        events = render_events(simple_song, note_picker=note_picker)
        note_on_events = [e for e in events if e.event_type == MidiEventType.NOTE_ON]
        note_off_events = [e for e in events if e.event_type == MidiEventType.NOTE_OFF]
        for i in range(len(note_on_events)):
            assert note_on_events[i].midi_notes == note_off_events[i].midi_notes


class TestEdgeCases:
    """Edge cases for rendering."""

    def test_empty_song(self, note_picker):
        line = Line(content="", line_number=1)
        events = render_events([line], note_picker=note_picker)
        # Only END_OF_SONG for an empty song.
        assert len(events) == 1
        assert events[0].event_type == MidiEventType.END_OF_SONG

    def test_invalid_chord_skipped(self, note_picker):
        line = Line(content="C InvalidChord G", line_number=1)
        chord_c = ChordInfo(chord="C", start=0, end=1, is_relative=False, is_valid=True)
        chord_invalid = ChordInfo(chord="InvalidChord", start=2, end=14, is_relative=False, is_valid=False)
        chord_g = ChordInfo(chord="G", start=15, end=16, is_relative=False, is_valid=True)
        line.items = [chord_c, chord_invalid, chord_g]

        events = render_events([line], note_picker=note_picker)
        note_on_events = [e for e in events if e.event_type == MidiEventType.NOTE_ON]
        assert len(note_on_events) == 2, "Should only have events for valid chords"


class TestStartPosition:
    """Start-position playback: chords before the start are accounted for but
    not voiced and emit nothing; the first played chord starts at t=0."""

    def test_skipped_chords_emit_nothing(self, note_picker):
        line0 = Line(content="C G", line_number=1)
        line0.items = [
            ChordInfo(chord="C", start=0, end=1, is_valid=True),
            ChordInfo(chord="G", start=2, end=3, is_valid=True),
        ]
        line1 = Line(content="Am F", line_number=2)
        line1.items = [
            ChordInfo(chord="Am", start=4, end=6, is_valid=True),
            ChordInfo(chord="F", start=7, end=8, is_valid=True),
        ]
        events = render_events(
            [line0, line1], note_picker=note_picker,
            initial_key=None, start_line_index=1, start_item_index=0,
        )
        note_ons = [e for e in events if e.event_type == MidiEventType.NOTE_ON]
        # Only Am and F play.
        assert [e.metadata['chord_info'].chord for e in note_ons] == ["Am", "F"]
        # First played event starts at t=0.
        assert note_ons[0].timestamp == 0.0
        # Bars rebased from the start position, but total_bars covers whole song.
        assert [e.metadata['bar'] for e in note_ons] == [1, 2]
        assert all(e.metadata['total_bars'] == 4 for e in note_ons)


class TestDeterminism:
    """Rendering the same song twice yields identical voicings."""

    def test_render_twice_identical(self):
        from services.song_parser_service import SongParserService
        text = "C G\nAm F\n{loop: @start 2}"
        lines = SongParserService().detect_chords_in_text(text)

        p1 = ChordNotePicker()
        p1.reset()
        r1 = SongRenderer().render(lines, "C", 120, (4, 4), p1)

        p2 = ChordNotePicker()
        p2.reset()
        r2 = SongRenderer().render(lines, "C", 120, (4, 4), p2)

        assert [c.midi_notes for c in r1.chords] == [c.midi_notes for c in r2.chords]


class TestRenderCancellation:
    """A set cancel_event aborts rendering and returns None."""

    def test_cancel_returns_none(self, note_picker):
        import threading
        from services.song_parser_service import SongParserService
        text = "C G\nAm F\n"
        lines = SongParserService().detect_chords_in_text(text)
        cancel = threading.Event()
        cancel.set()
        note_picker.reset()
        result = SongRenderer().render(
            lines, "C", 120, (4, 4), note_picker, cancel_event=cancel,
        )
        assert result is None
