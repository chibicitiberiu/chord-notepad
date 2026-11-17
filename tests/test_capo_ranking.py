"""Suggest Capo's ranked list: the order, the words and the shapes.

``rank_capos`` scores every capo and puts the recommended one first,
``ease_of`` puts each against capo 0 in words, ``capo_shapes`` names the
shapes a capo turns the chords into (as Transpose would write them), and the viewmodel's ``capo_job`` puts
them together from a rendered song (roman numerals resolved, the key in
force at each chord). ``current_capo`` is the capo in force where Suggest
Capo would put one.
"""

import pytest

from chordnotepad.audio.guitar_chord_picker import GuitarChordPicker
from chordnotepad.exceptions import RenderAborted
from chordnotepad.models.chord_notes import ChordNotes
from chordnotepad.models.fretboard_spec import BUILTIN_FRETBOARDS
from chordnotepad.services import capo_advisor
from chordnotepad.services.capo_advisor import (
    CapoOption, _capo_spec, ease_of, rank_capos, suggest_capo)
from chordnotepad.services.playback_service import PlaybackService
from chordnotepad.services.song_parser_service import SongParserService
from chordnotepad.services.transpose_service import transpose_text
from chordnotepad.session.host import HostDispatch
from chordnotepad.session.testing import FakePlayer, InMemoryDocumentStore, ManualHost
from chordnotepad.viewmodels.main_window_viewmodel import MainWindowViewModel

STANDARD = BUILTIN_FRETBOARDS["standard"]


def _cn(notes, root):
    return ChordNotes(notes=notes, bass_note=root, root=root)


FSHARP = [_cn(["F#", "A#", "C#"], "F#"), _cn(["B", "D#", "F#"], "B"),
          _cn(["C#", "F", "G#"], "C#"), _cn(["D#", "F#", "A#"], "D#")]
CMAJOR = [_cn(["C", "E", "G"], "C"), _cn(["G", "B", "D"], "G"),
          _cn(["A", "C", "E"], "A"), _cn(["F", "A", "C"], "F")]


# -- rank_capos ---------------------------------------------------------------------------


def test_every_capo_is_ranked_with_the_recommended_one_first():
    options = rank_capos(STANDARD, FSHARP)
    assert sorted(o.capo for o in options) == list(range(0, 8))
    assert options[0].capo == suggest_capo(STANDARD, FSHARP)
    rest = options[1:]
    assert [o.score for o in rest] == sorted((o.score for o in rest), reverse=True)


def test_the_scores_are_the_pickers():
    options = {o.capo: o for o in rank_capos(STANDARD, FSHARP)}
    base = GuitarChordPicker(STANDARD).voice_sequence_score(FSHARP)
    at_two = GuitarChordPicker(_capo_spec(STANDARD, 2)).voice_sequence_score(FSHARP)
    assert options[0].score == base and options[0].gain_per_chord == 0.0
    assert options[2].score == at_two
    assert options[2].gain_per_chord == pytest.approx((at_two - base) / 4)


def test_capo_0_is_recommended_when_no_capo_passes_the_gate():
    # C G Am F scores a little better at capo 5, by less than the margin.
    options = rank_capos(STANDARD, CMAJOR)
    assert options[0].capo == 0
    assert suggest_capo(STANDARD, CMAJOR) is None
    assert max(options, key=lambda o: (o.score, -o.capo)).capo != 0


def test_equal_scores_go_to_the_lower_capo(monkeypatch):
    class Flat:
        def __init__(self, spec):
            self.spec = spec

        def voice_sequence_score(self, sequence, should_abort=None):
            # Capos 0, 3 and 5 tie at the top; the rest score lower.
            raised = self.spec.tuning[0] - STANDARD.tuning[0]
            return 100.0 if raised in (0, 3, 5) else 10.0 * raised

    monkeypatch.setattr(capo_advisor, "GuitarChordPicker", Flat)
    options = rank_capos(STANDARD, FSHARP, min_total_gain=0.0, min_gain=0.0)
    # Nothing beats capo 0, so it is recommended; the ties follow, lowest first.
    assert [o.capo for o in options] == [0, 3, 5, 7, 6, 4, 2, 1]


def test_no_chords_ranks_nothing():
    assert rank_capos(STANDARD, []) == []
    assert rank_capos(STANDARD, [_cn([], "C")]) == []


def test_an_abort_stops_the_scoring():
    with pytest.raises(RenderAborted):
        rank_capos(STANDARD, FSHARP, should_abort=lambda: True)
    calls = []

    def after_two():
        calls.append(1)
        return len(calls) > 2
    with pytest.raises(RenderAborted):
        rank_capos(STANDARD, FSHARP, should_abort=after_two)


# -- ease_of ------------------------------------------------------------------------------


def test_ease_against_capo_0():
    base = CapoOption(0, 0.0, 0.0)
    # Four chords: the margin is max(1.5 * 4, 6.0) = 6.0.
    assert ease_of(base, base, 4) == "No capo"
    assert ease_of(CapoOption(2, 6.0, 1.5), base, 4) == "Easier"
    assert ease_of(CapoOption(2, 5.9, 1.475), base, 4) == "About the same"
    assert ease_of(CapoOption(2, -5.9, -1.475), base, 4) == "About the same"
    assert ease_of(CapoOption(2, -6.0, -1.5), base, 4) == "Harder"
    # Ten chords: 15.0.
    assert ease_of(CapoOption(3, 14.0, 1.4), base, 10) == "About the same"
    assert ease_of(CapoOption(3, -15.0, -1.5), base, 10) == "Harder"


def test_the_recommended_capo_is_easier():
    options = rank_capos(STANDARD, FSHARP)
    base = next(o for o in options if o.capo == 0)
    assert ease_of(options[0], base, len(FSHARP)) == "Easier"


# -- capo_shapes ----------------------------------------------------------------------


def _shapes(text, capo, notation="american"):
    """The shapes of ``text`` under ``capo``, as the dialog's row names them."""
    rows = {c.capo: c for c in _viewmodel(text, notation=notation)
            .capo_job("guitar:standard")(lambda: False)}
    return rows[capo].shapes


def _transposed(text, capo, notation):
    """Transpose's oracle: the distinct chords of the song moved down ``capo``."""
    out = []
    moved = transpose_text(text, -capo, notation)
    for line in SongParserService().detect_chords_in_text(moved, notation):
        for chord in line.chords:
            if chord.is_valid and not chord.is_rest and chord.chord not in out:
                out.append(chord.chord)
    return tuple(out)


ORACLE_SONGS = [
    ("C G Am F", "american"),
    ("D A Bm G", "american"),
    ("Bb F Gm Eb Cm", "american"),
    ("Eb Ab Bb Cm Fm", "american"),
    ("F#m D A E C#7", "american"),
    ("C E7 Am F G7", "american"),
    ("C(add9) G/B Am7 Fmaj7", "american"),
    ("{key: C}\nDm C#dim Dm G", "american"),
    ("{key: F}\nGm F#dim7 Gm C7", "american"),
    ("{key: Bb}\nBb B7 Em Bb", "american"),
    ("{key: G}\nG F#7 Bm E7 Am D7", "american"),
    ("{key: Eb}\nEb D7 Gm C7 Fm Bb7", "american"),
    ("{key: Ebm}\nEbm Cb Gb Db", "american"),
    ("{key: E}\nE B C#m A G#7", "american"),
    ("{key: G}\nG Bm C D7 G/B", "american"),
    ("{key: Db}\nDb Gb\n{key: E}\nC#m A", "american"),
    ("Do Sol Lam Fa", "european"),
    ("Sib Fa Solm Mib", "european"),
    ("{key: La}\nLa Mi/Sol# Fa#m Re", "european"),
]


@pytest.mark.parametrize("text, notation", ORACLE_SONGS)
def test_the_shapes_are_what_transpose_would_write(text, notation):
    # Every capo, with and without {key}: the key detected from the chords,
    # flat keys, slash chords, secondary dominants, dim leading tones.
    for capo in range(0, 8):
        assert _shapes(text, capo, notation) == _transposed(text, capo, notation), capo


def test_shapes_without_a_key_use_the_detected_key():
    assert _shapes("C G Am F", 1) == ("B", "F#", "G#m", "E")
    assert _shapes("C G Am F", 4) == ("Ab", "Eb", "Fm", "Db")
    assert _shapes("D A Bm G", 1) == ("Db", "Ab", "Bbm", "Gb")
    assert _shapes("Do Sol Lam Fa", 4, "european") == ("Lab", "Mib", "Fam", "Reb")


def test_a_secondary_dominant_keeps_its_letter():
    # B7 in Bb is V/iii: capo 1 makes it A#7 before D#m, not Bb7.
    assert _shapes("{key: Bb}\nBb B7 Em Bb", 1) == ("A", "A#7", "D#m")
    # A diminished chord leading up to the next chord takes a sharp.
    assert _shapes("{key: C}\nDm C#dim Dm G", 2) == ("Cm", "Bdim", "F")


def test_no_capo_names_the_chords_as_written():
    assert _shapes("{key: Ebm}\nEbm Cb Gb Db", 0) == ("Ebm", "Cb", "Gb", "Db")
    assert _shapes("{key: Sib}\nSib Fa Solm", 0, "european") == ("Sib", "Fa", "Solm")


def test_each_shape_is_named_once_and_long_lists_stop_after_eight():
    assert _shapes("{key: C}\nC G C Am F G C", 0) == ("C", "G", "Am", "F")
    assert _shapes("C D E F G A B Cm Dm Em", 0) == tuple("C D E F G A B Cm".split()) + ("\u2026",)


# -- the viewmodel's job ------------------------------------------------------------------


class FakeConfig:
    def __init__(self, **values):
        self._values = dict(values)

    def get(self, key, default=None):
        return self._values.get(key, default)

    def set(self, key, value):
        self._values[key] = value


def _viewmodel(text, **config):
    dispatch = HostDispatch(ManualHost())
    cfg = FakeConfig(**config)
    audio = PlaybackService(cfg, player=FakePlayer(auto_play=False), application=dispatch)
    vm = MainWindowViewModel(cfg, audio, InMemoryDocumentStore(), SongParserService(), dispatch)
    vm.set_and_notify("current_text", text)
    return vm


def _rows(vm, region=None):
    return {c.capo: c for c in vm.capo_job("guitar:standard", region)(lambda: False)}


def test_the_job_ranks_with_words_and_shapes():
    vm = _viewmodel("{key: F#}\nF#  B  C#  D#m  F#  B")
    choices = vm.capo_job("guitar:standard")(lambda: False)
    assert choices[0].recommended and choices[0].ease == "Easier"
    assert [c.recommended for c in choices[1:]] == [False] * 7
    rows = {c.capo: c for c in choices}
    assert rows[0].ease == "No capo" and rows[0].shapes == ("F#", "B", "C#", "D#m")
    assert rows[2].shapes == ("E", "A", "B", "C#m")
    assert vm.suggest_capo_for("guitar:standard") == choices[0].capo


def test_roman_numerals_are_named_by_the_chords_they_resolve_to():
    vm = _viewmodel("{key: Bb}\nI V vi IV")
    rows = _rows(vm)
    assert rows[0].shapes == ("Bb", "F", "Gm", "Eb")
    assert rows[3].shapes == ("G", "D", "Em", "C")


def test_european_roman_numerals_and_chords():
    vm = _viewmodel("{key: Sib}\nI V Solm Mib", notation="european")
    rows = _rows(vm)
    assert rows[0].shapes == ("Sib", "Fa", "Solm", "Mib")
    assert rows[3].shapes == ("Sol", "Re", "Mim", "Do")


def test_a_mid_song_key_change_respells_the_shapes_after_it():
    vm = _viewmodel("{key: Db}\nDb Gb\n{key: E}\nC#m A")
    assert _rows(vm)[2].shapes == ("B", "E", "Bm", "G")


def test_a_selection_names_only_its_chords():
    text = "{key: C}\nC G\nAm F"
    vm = _viewmodel(text)
    start = text.index("Am")
    assert _rows(vm, (start, len(text)))[0].shapes == ("Am", "F")


def test_the_job_has_nothing_for_no_chords_and_aborts():
    vm = _viewmodel("{key: C}\nwords only\nC")
    assert vm.capo_job("guitar:standard", (0, 12))(lambda: False) is None
    with pytest.raises(RenderAborted):
        vm.capo_job("guitar:standard")(lambda: True)
    assert vm.capo_job("piano") is None


def test_an_abort_stops_the_render_before_the_scoring(monkeypatch):
    vm = _viewmodel("{key: F#}\nF#  B  C#  D#m")
    ranked = []
    monkeypatch.setattr(capo_advisor, "rank_capos",
                        lambda *a, **k: ranked.append(1) or [])
    with pytest.raises(RenderAborted):
        vm.capo_job("guitar:standard")(lambda: True)
    assert ranked == []


# -- current_capo ---------------------------------------------------------------------


@pytest.mark.parametrize("text, region, current", [
    ("C G", None, 0),
    ("{capo: 3}\nC G", None, 3),
    ("{capo: 3} {capo: 5}\nC G", None, 5),        # the first one has no effect
    ("{capo: 3}\nC G\n{capo: 5}\nAm", None, 3),    # 5 starts later
    ("{capo: 3}\nC G\nAm F", (14, 18), 3),         # in force above the selection
    ("{capo: 3}\nC G\n{capo: 5}\nAm", (24, 26), 5),
    ("{capo: 99}\nC", None, 0),                    # invalid
    ("{capo: 2}\nwords", None, 2),                 # no chord after it
])
def test_the_capo_in_force_where_one_would_go(text, region, current):
    assert _viewmodel(text).current_capo(region) == current
