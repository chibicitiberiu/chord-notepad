"""Out-of-range tempo and time-signature directives.

``{bpm}`` and ``{time}`` values outside what the app supports are invalid
directives: highlighted as invalid and ignored by playback. Relative tempo
changes (+N, -N, N%, Nx) clamp the resulting tempo to the app's range.
"""
import threading

import pytest

from audio.chord_picker import ChordNotePicker
from constants import MAX_BPM, MIN_BPM
from models.directive import DirectiveType
from services.song_parser_service import SongParserService
from services.song_renderer import SongRenderer
from session.highlighting import compute_spans
from session.song_defaults import song_defaults
from session.state import SpanKind


@pytest.fixture
def parser():
    return SongParserService()


def _only(parser, text):
    directives = parser.parse_directives(text)
    assert len(directives) == 1
    return directives[0]


def _render(text, initial_bpm=120, initial_time_sig=(4, 4), timeout=10.0):
    """Render ``text`` on a worker thread; fail instead of hanging forever."""
    lines = SongParserService().detect_chords_in_text(text)
    result = {}

    def work():
        try:
            result['song'] = SongRenderer().render(
                lines=lines, initial_key="C", initial_bpm=initial_bpm,
                initial_time_sig=initial_time_sig, note_picker=ChordNotePicker())
        except BaseException as exc:  # surfaced below
            result['error'] = exc

    worker = threading.Thread(target=work, daemon=True)
    worker.start()
    worker.join(timeout)
    assert not worker.is_alive(), f"rendering {text!r} did not finish"
    if 'error' in result:
        raise result['error']
    return result['song']


def test_bounds_are_the_toolbar_range():
    from session.toolbar import BPM_SCALE
    assert (MIN_BPM, MAX_BPM) == (BPM_SCALE.min_value, BPM_SCALE.max_value) == (20, 400)


class TestTempoParsing:
    @pytest.mark.parametrize("value", ["0", "19", "401", "1000", "0%", "-50%", "0x",
                                       "-2x", "nan%", "infx", "nanx"])
    def test_out_of_range_is_invalid(self, parser, value):
        directive = _only(parser, f"{{bpm: {value}}}")
        assert directive.type == DirectiveType.BPM
        assert not directive.is_valid

    @pytest.mark.parametrize("value", ["20", "400", "+500", "-500", "1%", "0.01x", "reset"])
    def test_in_range_and_relative_values_are_valid(self, parser, value):
        assert _only(parser, f"{{bpm: {value}}}").is_valid

    def test_out_of_range_tempo_is_highlighted_invalid(self, parser):
        text = "{bpm: 0}\nC G"
        lines = parser.detect_chords_in_text(text)
        kinds = [span.kind for span in compute_spans(lines, text)
                 if span.start == 0]
        assert kinds == [SpanKind.DIRECTIVE_INVALID]


class TestTimeSignatureParsing:
    @pytest.mark.parametrize("value", ["0/4", "4/0", "4/3", "-3/4", "17/4", "4/32", "3/-4"])
    def test_out_of_range_is_invalid(self, parser, value):
        assert not _only(parser, f"{{time: {value}}}").is_valid

    @pytest.mark.parametrize("value", ["1/1", "16/16", "6/8", "3/4", "2/2"])
    def test_supported_values_are_valid(self, parser, value):
        assert _only(parser, f"{{time: {value}}}").is_valid


class TestRendering:
    def test_zero_tempo_is_ignored(self):
        song = _render("{bpm: 0}\nC")
        assert [rc.bpm for rc in song.chords] == [120]

    def test_zero_beat_time_signature_is_ignored(self):
        song = _render("{time: 0/4}\nC")
        assert [rc.time_sig for rc in song.chords] == [(4, 4)]

    @pytest.mark.parametrize("text, expected", [
        ("{bpm: 30}\n{bpm: -200}\nC", MIN_BPM),
        ("{bpm: 390}\n{bpm: +50}\nC", MAX_BPM),
        ("{bpm: 300}\n{bpm: 1000%}\nC", MAX_BPM),
        ("{bpm: 30}\n{bpm: 1%}\nC", MIN_BPM),
        ("{bpm: 30}\n{bpm: 0.1x}\nC", MIN_BPM),
        ("{bpm: 300}\n{bpm: 4x}\nC", MAX_BPM),
    ])
    def test_relative_changes_clamp(self, text, expected):
        song = _render(text)
        assert [rc.bpm for rc in song.chords] == [expected]
        assert all(MIN_BPM <= bpm <= MAX_BPM for _beat, bpm in song.tempo_map)

    def test_song_defaults_clamp_like_the_renderer(self, parser):
        lines = parser.detect_chords_in_text("{bpm: 30}\n{bpm: -200}\nC")
        assert song_defaults(lines, 120, (4, 4), "C").tempo.value == str(MIN_BPM)
