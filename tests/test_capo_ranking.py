"""Suggest Capo's ranked list: the order, the words and the shapes.

``rank_capos`` scores every capo and puts the recommended one first,
``ease_of`` puts each against capo 0 in words, ``capo_shapes`` names the
shapes a capo turns the chords into, and the viewmodel's ``capo_job`` puts
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
    CapoOption, _capo_spec, capo_shapes, ease_of, rank_capos, suggest_capo)
from chordnotepad.services.playback_service import PlaybackService
from chordnotepad.services.song_parser_service import SongParserService
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


def test_shapes_move_down_by_the_capo_in_the_key():
    chords = [("Bb", "Bb"), ("F", "Bb"), ("Gm", "Bb"), ("Eb", "Bb"), ("F", "Bb")]
    assert capo_shapes(chords, 3, "american") == ("G", "D", "Em", "C")
    assert capo_shapes(chords, 0, "american") == ("Bb", "F", "Gm", "Eb")
    # Sharps in a sharp key: F# major, capo 2, is E major.
    assert capo_shapes([("F#", "F#"), ("D#m", "F#"), ("C#/E#", "F#")], 2, "american") == (
        "E", "C#m", "B/D#")


def test_a_chromatic_chord_keeps_its_letter():
    # E7 in C (V/vi) under capo 2: D7 in Bb, not Ebb7 or a flat spelling.
    assert capo_shapes([("C", "C"), ("E7", "C"), ("Am", "C")], 2, "american") == (
        "Bb", "D7", "Gm")


def test_shapes_follow_the_key_at_each_chord():
    # A key change halfway: Db in Db is B under capo 2; the same pitch as
    # C# in A (capo 2: B in G) is the same shape, named once.
    chords = [("Db", "Db"), ("Gb", "Db"), ("C#m", "E"), ("A", "E")]
    assert capo_shapes(chords, 2, "american") == ("B", "E", "Bm", "G")


def test_european_shapes_read_the_key_and_write_the_chords_in_european():
    chords = [("A", "La"), ("E/G#", "La"), ("F#m", "La"), ("D", "La")]
    assert capo_shapes(chords, 2, "european") == ("Sol", "Re/Fa#", "Mim", "Do")


def test_without_a_key_the_plain_spelling_is_used():
    assert capo_shapes([("Bb", None), ("Eb", None), ("F#", None)], 1, "american") == (
        "A", "D", "F")


def test_each_shape_is_named_once_and_long_lists_stop_after_eight():
    chords = [(c, "C") for c in "C G C Am F G C".split()]
    assert capo_shapes(chords, 0, "american") == ("C", "G", "Am", "F")
    many = [(c, None) for c in "C D E F G A B Cm Dm Em".split()]
    assert capo_shapes(many, 0, "american") == tuple("C D E F G A B Cm".split()) + ("…",)


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
