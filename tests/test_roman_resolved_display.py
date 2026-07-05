"""Tests for showing the resolved chord next to roman numerals.

``ChordNotes.resolved_symbol`` carries the absolute chord a roman numeral
resolved to (display-only), and the chord-sheet renderers label such chords
as ``V7 (G7)`` via ``chord_symbol_label``.
"""

from chord.helper import ChordHelper
from services.song_parser_service import SongParserService
from services.song_renderer import SongRenderer
from audio.chord_picker import ChordNotePicker
from ui.chord_sheet.piano_roll import PianoRollRenderer
from ui.chord_sheet.ops import DrawOps, TextOp
from ui.chord_sheet.renderer_interface import SheetContext, chord_symbol_label


# ---------------------------------------------------------------------------
# ChordNotes.resolved_symbol
# ---------------------------------------------------------------------------

class TestResolvedSymbol:
    def setup_method(self):
        self.helper = ChordHelper()

    def _resolve(self, symbol, key):
        return self.helper.compute_chord_notes(symbol, key=key, is_relative=True)

    def test_dominant_seventh(self):
        assert self._resolve('V7', 'C').resolved_symbol == 'G7'

    def test_minor_degree(self):
        assert self._resolve('ii', 'C').resolved_symbol == 'Dm'

    def test_slash_roman(self):
        assert self._resolve('vi/I', 'C').resolved_symbol == 'Am/C'

    def test_diminished_keeps_natural_spelling(self):
        assert self._resolve('viio', 'Am').resolved_symbol == 'G#dim'

    def test_flat_degree(self):
        assert self._resolve('bIII', 'C').resolved_symbol == 'Eb'

    def test_absolute_chord_has_no_resolved_symbol(self):
        assert self.helper.compute_chord_notes('C').resolved_symbol is None

    def test_european_chord_has_no_resolved_symbol(self):
        cn = self.helper.compute_chord_notes('Do')
        assert cn.notes == ['C', 'E', 'G']
        assert cn.resolved_symbol is None


# ---------------------------------------------------------------------------
# chord_symbol_label + renderer integration
# ---------------------------------------------------------------------------

def _render(text, key):
    lines = SongParserService().detect_chords_in_text(text)
    return SongRenderer().render(
        lines=lines,
        initial_key=key,
        initial_bpm=120,
        initial_time_sig=(4, 4),
        note_picker=ChordNotePicker(),
        start_line_index=0,
        start_item_index=0,
    )


class TestChordSymbolLabel:
    def test_roman_chord_gets_parenthesized_resolution(self):
        song = _render('I  V7\n', 'C')
        labels = [chord_symbol_label(c) for c in song.chords]
        assert labels == ['I (C)', 'V7 (G7)']

    def test_absolute_chord_shown_as_written(self):
        song = _render('C  Am7\n', 'C')
        labels = [chord_symbol_label(c) for c in song.chords]
        assert labels == ['C', 'Am7']

    def test_key_change_mid_song_resolves_per_chord(self):
        song = _render('V\n{key: G}\nV\n', 'C')
        labels = [chord_symbol_label(c) for c in song.chords]
        assert labels == ['V (G)', 'V (D)']

    def test_renderer_draws_the_resolved_label(self):
        song = _render('V7\n', 'C')
        renderer = PianoRollRenderer()
        ctx = SheetContext(song=song)
        layout = renderer.layout(ctx, 160.0)
        ops = DrawOps()
        renderer.paint(ops, ctx, layout)
        texts = [op.s for op in ops.ops if isinstance(op, TextOp)]
        assert 'V7 (G7)' in texts
