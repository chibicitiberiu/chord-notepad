"""Tests for the {capo: N} directive and capo-relative whole-song voicing.

A ``{capo: N}`` directive raises the fretboard tuning by N semitones from that
point forward, so the fret/tab views can draw capo-relative shapes. The
sounding pitches are unchanged -- a capo picks easier shapes for the same
chords, it does not transpose. Non-fretboard models ignore it.
"""

import pytest

from audio.chord_picker import ChordNotePicker
from audio.guitar_chord_picker import GuitarChordPicker
from models.directive import DirectiveType
from services.song_parser_service import SongParserService
from services.song_renderer import SongRenderer


@pytest.fixture(scope="module")
def parser():
    return SongParserService()


def _render(parser, text, picker=None, key="F#"):
    lines = parser.detect_chords_in_text(text)
    return SongRenderer().render(
        lines=lines, initial_key=key, initial_bpm=120, initial_time_sig=(4, 4),
        note_picker=picker or GuitarChordPicker('standard'),
        start_line_index=0, start_item_index=0,
    )


def _played(song):
    return [rc for rc in song.chords if not rc.is_rest and not rc.skipped]


class TestCapoParsing:
    def test_capo_directive_parsed(self, parser):
        directives = parser.parse_directives("{capo: 5}\n")
        assert len(directives) == 1
        assert directives[0].type == DirectiveType.CAPO
        assert directives[0].capo == 5

    def test_capo_zero_is_valid(self, parser):
        directives = parser.parse_directives("{capo: 0}\n")
        assert directives[0].type == DirectiveType.CAPO
        assert directives[0].capo == 0

    def test_capo_out_of_range_is_invalid(self, parser):
        for value in ("13", "-1", "99"):
            directives = parser.parse_directives("{capo: %s}\n" % value)
            assert directives[0].type == DirectiveType.UNKNOWN
            assert not directives[0].is_valid

    def test_capo_non_integer_is_invalid(self, parser):
        directives = parser.parse_directives("{capo: high}\n")
        assert directives[0].type == DirectiveType.UNKNOWN
        assert not directives[0].is_valid


class TestCapoStamping:
    def test_no_directive_leaves_capo_zero(self, parser):
        song = _render(parser, "F#  B  C#\n")
        assert all(rc.capo == 0 for rc in _played(song))

    def test_directive_scopes_forward(self, parser):
        song = _render(parser, "F#\n{capo: 4}\nB  C#\n")
        played = _played(song)
        assert played[0].capo == 0     # before the directive
        assert played[1].capo == 4
        assert played[2].capo == 4

    def test_mid_song_capo_change(self, parser):
        song = _render(parser, "{capo: 2}\nF#\n{capo: 0}\nB\n")
        played = _played(song)
        assert played[0].capo == 2
        assert played[1].capo == 0

    def test_capo_restored_after_loop(self, parser):
        # A loop back to a label restores the capo in effect there, like key.
        text = (
            "{capo: 3}\n{label: verse}\nF#  B\n"
            "{capo: 5}\nC#\n{loop: verse 2}\n"
        )
        song = _render(parser, text)
        played = _played(song)
        # First pass: F#,B at capo 3, then {capo:5}, C# at capo 5. The loop
        # restores the capo saved at the label (3), then re-walks the body, so
        # the {capo:5} directive fires again -- exactly like tempo/key restores.
        assert [rc.capo for rc in played] == [3, 3, 5, 3, 3, 5]


class TestCapoVoicing:
    def test_capo_produces_capo_relative_and_easier_shape(self, parser):
        # F# in F# needs a full barre with no capo; capo 2 lets an open E-shape
        # (capo-relative frets, all low) voice it.
        no_capo = _played(_render(parser, "F#\n"))[0]
        capo2 = _played(_render(parser, "{capo: 2}\nF#\n"))[0]
        assert max(no_capo.fingering) >= 4          # barre high on the neck
        assert max(capo2.fingering) <= 2            # capo-relative, near the nut

    def test_capo_keeps_pitch_classes(self, parser):
        # The capo changes the shape, not the chord: same pitch classes sound.
        no_capo = _played(_render(parser, "B\n"))[0]
        capo2 = _played(_render(parser, "{capo: 2}\nB\n"))[0]
        assert {n % 12 for n in no_capo.midi_notes} == {n % 12 for n in capo2.midi_notes}

    def test_capo_zero_everywhere_matches_no_directive(self, parser):
        # An explicit {capo: 0} must voice identically to no directive at all
        # (the fast path is taken in both cases).
        plain = _played(_render(parser, "F#  B  C#  D#m\n"))
        zeroed = _played(_render(parser, "{capo: 0}\nF#  B  C#  D#m\n"))
        assert [rc.fingering for rc in plain] == [rc.fingering for rc in zeroed]
        assert [rc.midi_notes for rc in plain] == [rc.midi_notes for rc in zeroed]


class TestNonFretboardIgnoresCapo:
    def test_piano_model_ignores_capo(self, parser):
        # The piano model does not support a capo; a {capo} directive must not
        # change its voicing at all.
        picker_a = ChordNotePicker()
        picker_b = ChordNotePicker()
        plain = _played(_render(parser, "F#  B  C#\n", picker=picker_a))
        capoed = _played(_render(parser, "{capo: 4}\nF#  B  C#\n", picker=picker_b))
        assert [rc.midi_notes for rc in plain] == [rc.midi_notes for rc in capoed]

    def test_piano_model_has_no_capo_support(self):
        assert ChordNotePicker().supports_capo is False
        assert GuitarChordPicker('standard').supports_capo is True

    def test_with_capo_zero_returns_self(self):
        picker = GuitarChordPicker('standard')
        assert picker.with_capo(0) is picker

    def test_with_capo_raises_tuning(self):
        picker = GuitarChordPicker('standard')
        capoed = picker.with_capo(3)
        assert list(capoed.tuning_midi) == [p + 3 for p in picker.tuning_midi]
