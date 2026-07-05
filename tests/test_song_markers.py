"""Tests for the timeline markers ``SongRenderer`` emits onto ``RenderedSong``.

Markers annotate the unrolled beat/time domain (the same one ``RenderedChord``
lives in) for an upcoming chord-sheet strip view: section starts, loop repeats,
tempo changes, meter changes, and key changes. They are a purely additive side
effect of the
single render walk -- playback, MIDI export, and voicing never read them.

Each test builds a song from ChordPro-ish text via ``SongParserService`` (so the
directive/loop machinery is exercised exactly as in production) and asserts on
``RenderedSong.markers``.
"""
from audio.chord_picker import ChordNotePicker
from services.song_parser_service import SongParserService
from services.song_renderer import SongRenderer


def _render(text, *, initial_bpm=120, initial_time_sig=(4, 4), initial_key="C"):
    lines = SongParserService().detect_chords_in_text(text)
    rendered = SongRenderer().render(
        lines=lines,
        initial_key=initial_key,
        initial_bpm=initial_bpm,
        initial_time_sig=initial_time_sig,
        note_picker=ChordNotePicker(),
    )
    assert rendered is not None
    return rendered


def _tuples(rendered):
    """Markers as (kind, text) pairs, in walk order."""
    return [(m.kind, m.text) for m in rendered.markers]


class TestNoMarkers:
    def test_plain_song_has_no_markers(self):
        rendered = _render("C G Am F\n")
        assert rendered.markers == []

    def test_only_initial_tempo_and_meter_emit_nothing(self):
        # The seeded (0.0, bpm)/(0.0, time_sig) map entries must not surface as
        # markers -- markers are for CHANGES, not the starting values.
        rendered = _render("C G\n", initial_bpm=100, initial_time_sig=(3, 4))
        assert rendered.markers == []


class TestSectionMarkers:
    def test_single_label_emits_one_section_marker(self):
        rendered = _render("{label: verse}\nC G\n")
        assert _tuples(rendered) == [("section", "verse")]
        assert rendered.markers[0].beat == 0.0
        assert rendered.markers[0].time == 0.0

    def test_label_after_chords_positioned_at_its_beat(self):
        # C is a full 4/4 bar -> the label sits at beat 4.0.
        rendered = _render("C\n{label: chorus}\nG\n")
        assert _tuples(rendered) == [("section", "chorus")]
        marker = rendered.markers[0]
        assert marker.beat == 4.0
        # Beat/time agree with the chord that starts there.
        g = next(rc for rc in rendered.chords if rc.chord_info.chord == "G")
        assert marker.beat == g.start_beat
        assert marker.time == g.start_time

    def test_start_builtin_label_never_emits(self):
        # A song that never names a label produces no 'section' marker, proving
        # the synthetic '@start' snapshot doesn't leak a marker.
        rendered = _render("C\n{bpm: 130}\nG\n")
        assert not any(m.kind == "section" for m in rendered.markers)


class TestTempoMarkers:
    def test_tempo_change_marker_text_and_beat(self):
        rendered = _render("C\n{bpm: 140}\nD\n")
        tempo = [m for m in rendered.markers if m.kind == "tempo"]
        assert len(tempo) == 1
        assert tempo[0].text == "140 bpm"
        assert tempo[0].beat == 4.0
        # No marker for the initial bpm at beat 0.
        assert all(m.beat > 0 for m in rendered.markers if m.kind == "tempo")

    def test_no_tempo_marker_when_bpm_directive_at_beat_zero(self):
        # A {bpm} before any chord overwrites the seeded beat-0 entry; still no
        # marker, because beat-0 tempo is the starting value, not a change.
        rendered = _render("{bpm: 90}\nC G\n")
        assert [m for m in rendered.markers if m.kind == "tempo"] == []
        assert rendered.tempo_map == [(0.0, 90)]


class TestMeterMarkers:
    def test_meter_change_marker_text_and_beat(self):
        rendered = _render("C\n{time: 3/4}\nD\n")
        meter = [m for m in rendered.markers if m.kind == "meter"]
        assert len(meter) == 1
        assert meter[0].text == "3/4"
        assert meter[0].beat == 4.0

    def test_no_meter_marker_when_time_directive_at_beat_zero(self):
        rendered = _render("{time: 3/4}\nC D\n")
        assert [m for m in rendered.markers if m.kind == "meter"] == []
        assert rendered.meter_map == [(0.0, (3, 4))]


class TestKeyMarkers:
    def test_key_change_marker_text_and_beat(self):
        rendered = _render("C\n{key: G}\nD\n")
        keys = [m for m in rendered.markers if m.kind == "key"]
        assert len(keys) == 1
        assert keys[0].text == "Key G"
        assert keys[0].beat == 4.0

    def test_initial_key_emits_no_marker(self):
        rendered = _render("C G\n", initial_key="F#")
        assert [m for m in rendered.markers if m.kind == "key"] == []

    def test_no_key_marker_when_key_directive_at_beat_zero(self):
        # A {key} before any chord is the starting key, not a change.
        rendered = _render("{key: G}\nC D\n")
        assert [m for m in rendered.markers if m.kind == "key"] == []

    def test_duplicate_same_key_directive_emits_nothing(self):
        rendered = _render("C\n{key: G}\nD\n{key: G}\nE\n")
        keys = [m for m in rendered.markers if m.kind == "key"]
        assert [(m.text, m.beat) for m in keys] == [("Key G", 4.0)]

    def test_redundant_key_directive_matching_current_key_emits_nothing(self):
        # {key: C} while already in C (the initial key) is not a change.
        rendered = _render("C\n{key: C}\nD\n", initial_key="C")
        assert [m for m in rendered.markers if m.kind == "key"] == []


class TestLoopRestoringKey:
    """Pin the key behavior across a loop seam when a {key} lives in the body.

    Mirrors TestLoopRestoringTempo: the loop restores the label's saved key at
    the jump beat, then the re-walked {key} directive re-sets it at that same
    beat. Markers mirror both effective changes, so two 'key' markers land at
    the jump beat -- the honest picture of the key across the seam.
    """

    def test_restore_then_reset_emits_both_key_markers(self):
        # The label snapshot (key C) is taken BEFORE {key: G}, and the first
        # {key: G} sits at beat 0 (the starting key of the walk), so it emits
        # no marker. At the seam the restore emits 'Key C', then the re-walked
        # {key: G} emits 'Key G' -- both at the jump beat.
        rendered = _render(
            "{label: chorus}\n{key: G}\nC\n{loop: chorus 2}\nD\n",
            initial_key="C")
        assert _tuples(rendered) == [
            ("section", "chorus"),
            ("loop", "chorus (2/2)"),
            ("key", "Key C"),       # loop restores the label's saved C
            ("key", "Key G"),       # re-walked {key: G} re-sets it
        ]
        seam = [m for m in rendered.markers if m.kind in ("loop", "key")]
        assert all(m.beat == 4.0 for m in seam)

    def test_loop_restore_to_different_key_emits_one_marker(self):
        # No {key} inside the body after the jump target's snapshot point --
        # the key changes mid-body AFTER the chord, so the restore back to the
        # saved key is the only effective change at each seam.
        rendered = _render(
            "{label: chorus}\nC\n{key: G}\n{loop: chorus 2}\nD\n",
            initial_key="C")
        keys = [m for m in rendered.markers if m.kind == "key"]
        assert [(m.text, m.beat) for m in keys] == [
            ("Key G", 4.0),   # {key: G} after the first pass's chord
            ("Key C", 4.0),   # loop restore back to the label's saved C
            ("Key G", 8.0),   # re-walked {key: G} on the second pass
        ]


class TestLoopMarkers:
    def test_loop_count_one_or_less_emits_no_loop_marker(self):
        rendered = _render("{label: chorus}\nC\n{loop: chorus 1}\n")
        assert [m for m in rendered.markers if m.kind == "loop"] == []

    def test_loop_emits_one_marker_per_repeat_pass_no_dup_section(self):
        rendered = _render("{label: chorus}\nC G\n{loop: chorus 3}\n")
        assert _tuples(rendered) == [
            ("section", "chorus"),
            ("loop", "chorus (2/3)"),
            ("loop", "chorus (3/3)"),
        ]
        # Exactly one section marker (the first pass), none re-emitted at the
        # loop-jump beats where the target label is re-walked.
        sections = [m for m in rendered.markers if m.kind == "section"]
        assert len(sections) == 1

    def test_loop_marker_beats_match_jump_positions(self):
        # Two chords per pass = 8 beats; loop back at beat 8, then beat 16.
        rendered = _render("{label: chorus}\nC G\n{loop: chorus 3}\n")
        loops = [m for m in rendered.markers if m.kind == "loop"]
        assert [m.beat for m in loops] == [8.0, 16.0]

    def test_loop_marker_beat_time_agree_with_chord_replay(self):
        rendered = _render("{label: chorus}\nC G\n{loop: chorus 2}\n")
        loop = next(m for m in rendered.markers if m.kind == "loop")
        # The first replayed chord starts exactly at the loop marker.
        replays = [rc for rc in rendered.chords
                   if rc.chord_info.chord == "C" and not rc.skipped]
        assert len(replays) == 2
        assert loop.beat == replays[1].start_beat
        assert loop.time == replays[1].start_time


class TestLoopRestoringTempo:
    """Pin the tempo behavior across a loop seam when a {bpm} lives in the body.

    The loop restores the label's saved tempo (appending it to tempo_map at the
    jump beat), then the re-walked {bpm} directive re-sets the tempo at that same
    beat (a same-beat overwrite of tempo_map). Markers mirror both writes, so two
    'tempo' markers land at the jump beat -- the honest picture of the tempo
    across the seam. The final tempo_map keeps only the surviving value.
    """

    def test_restore_then_reset_emits_both_tempo_markers(self):
        rendered = _render(
            "{label: chorus}\n{bpm: 200}\nC\n{loop: chorus 2}\nD\n")
        kinds = _tuples(rendered)
        assert kinds == [
            ("section", "chorus"),
            ("loop", "chorus (2/2)"),
            ("tempo", "120 bpm"),   # loop restores the label's saved 120 bpm
            ("tempo", "200 bpm"),   # re-walked {bpm: 200} re-sets it
        ]
        # All three post-seam markers share the jump beat.
        seam = [m for m in rendered.markers if m.kind in ("loop", "tempo")]
        assert all(m.beat == 4.0 for m in seam)
        # tempo_map's final surviving state at that beat is the re-set value.
        assert rendered.tempo_map[-1] == (4.0, 200)


class TestMarkerInvariants:
    def test_markers_non_decreasing_in_beat(self):
        rendered = _render(
            "{label: a}\nC G\n{bpm: 140}\nD\n{time: 3/4}\nE\n{loop: a 2}\nF\n")
        beats = [m.beat for m in rendered.markers]
        assert beats == sorted(beats)

    def test_marker_beat_time_agree_with_chords_generally(self):
        rendered = _render("C\n{bpm: 150}\nD\n{time: 6/8}\nE\n")
        # Every marker should coincide with some rendered chord's start.
        starts = {(round(rc.start_beat, 6), round(rc.start_time, 6))
                  for rc in rendered.chords}
        for m in rendered.markers:
            assert (round(m.beat, 6), round(m.time, 6)) in starts


class TestPlayFromCursorPrefix:
    """Markers cover the whole walk, including the skipped play-from-cursor
    prefix, where time stays 0.0 (matching the skipped chords there)."""

    def test_markers_emitted_in_skipped_prefix_with_zero_time(self):
        lines = SongParserService().detect_chords_in_text(
            "{label: intro}\nC\n{bpm: 140}\nD\nE\n")
        # Start playback from the 3rd line (item index into line 3 = the 'D').
        rendered = SongRenderer().render(
            lines=lines,
            initial_key="C",
            initial_bpm=120,
            initial_time_sig=(4, 4),
            note_picker=ChordNotePicker(),
            start_line_index=3,
            start_item_index=0,
        )
        assert rendered is not None
        # The section + tempo markers in the skipped prefix still emit, with
        # advancing beat but time pinned at 0.0.
        section = next(m for m in rendered.markers if m.kind == "section")
        tempo = next(m for m in rendered.markers if m.kind == "tempo")
        assert section.beat == 0.0 and section.time == 0.0
        assert tempo.beat == 4.0 and tempo.time == 0.0
