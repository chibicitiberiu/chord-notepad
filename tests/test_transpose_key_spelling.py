"""Transpose spells chords by the key they land in.

A chord's key is the last ``{key:}`` before it (moved with the song); before
the first one, the key detected from those chords. See
services.key_spelling and the "Enharmonic policy" in transpose_service.
"""

import time

from services.key_spelling import Key
from services.song_parser_service import SongParserService
from services.transpose_service import (
    _spelling_plan, transpose_chord_token, transpose_key, transpose_text,
)

G_SONG = """\
{key: G}
G           D/F#        Em          C
Morning comes and takes the dark away
G           B7          Em          A7
Every window opens up to day
C           Cm          G/D         E7
Hold the line, hold the line, my dear
Am7         D7          G
Sunday's almost here
"""

G_SONG_IN_B = """\
{key: B}
B           F#/A#       G#m         E
Morning comes and takes the dark away
B           D#7         G#m         C#7
Every window opens up to day
E           Em          B/F#        G#7
Hold the line, hold the line, my dear
C#m7        F#7         B
Sunday's almost here
"""

F_SONG = """\
{key: F}
F       Bb      F       C7
F       Bb      F       C7      F
Bb      F       G7      C7
"""

F_SONG_IN_DB = """\
{key: Db}
Db      Gb      Db      Ab7
Db      Gb      Db      Ab7     Db
Gb      Db      Eb7     Ab7
"""


def _moved(text, semitones, notation, region=None):
    """The transposed text's words: these tests are about spelling, the
    spacing is test_transpose_service's."""
    return transpose_text(text, semitones, notation, region).split()


def _plan(text, semitones, notation="american"):
    lines = SongParserService().detect_chords_in_text(text, notation)
    return _spelling_plan(lines, semitones, notation)


def _without_key(text):
    return text.split('\n', 1)[1]


class TestShowcaseSongs:
    def test_g_song_up_to_b_uses_sharps(self):
        assert transpose_text(G_SONG, 4, "american") == G_SONG_IN_B

    def test_the_same_song_without_its_key_is_detected_as_g(self):
        assert transpose_text(_without_key(G_SONG), 4, "american") == _without_key(G_SONG_IN_B)

    def test_f_song_down_to_d_flat(self):
        assert transpose_text(F_SONG, -4, "american") == F_SONG_IN_DB

    def test_european_sol_to_si(self):
        song = "{key: Sol}\nSol      Re       Mim      Do\nLam      Do       Re       Sol\n"
        assert _moved(song, 4, "european") == (
            "{key: Si}\nSi       Fa#      Sol#m    Mi\nDo#m     Mi       Fa#      Si\n").split()

    def test_slash_basses_follow_the_key(self):
        song = "{key: D}\nD  D/C#  Bm  Bm/A  G  D/F#  Em  A7\n"
        assert _moved(song, 4, "american") == (
            "{key: F#}\nF#  F#/F  D#m  D#m/C#  B  F#/A#  G#m  C#7\n").split()

    def test_borrowed_flat_seven_is_a_flat(self):
        song = "{key: D}\nD  C  G  D  G  A  D\n"
        assert _moved(song, 1, "american") == "{key: Eb}\nEb  Db  Ab  Eb  Ab  Bb  Eb\n".split()


class TestKeySections:
    def test_a_directive_spells_the_chords_after_it(self):
        song = "{key: F}\nF  Bb  C  Dm\n{key: F#}\nF#  B  C#  D#m\n"
        assert _moved(song, 2, "american") == (
            "{key: G}\nG  C  D  Em\n{key: Ab}\nAb  Db  Eb  Fm\n").split()

    def test_chords_before_the_first_directive_are_detected(self):
        # The first line is in E (detected, so up 4 it's in Ab, not G#);
        # the {key: Bb} then takes over.
        song = "E  B  C#m  A  E\n{key: Bb}\nBb  Eb  F  Gm\n"
        assert _moved(song, 1, "american") == "F  C  Dm  Bb  F\n{key: B}\nB  E  F#  G#m\n".split()
        assert _moved(song, -2, "american") == "D  A  Bm  G  D\n{key: Ab}\nAb  Db  Eb  Fm\n".split()
        assert _moved(song, 4, "american") == "Ab  Eb  Fm  Db  Ab\n{key: D}\nD  G  A  Bm\n".split()

    def test_a_directive_on_a_chord_line_starts_at_its_position(self):
        song = "Bb  F  {key: E}  E  B\n"
        assert _moved(song, 2, "american") == ["C", "G", "{key:", "F#}", "F#", "C#"]

    def test_the_directive_key_moves_with_the_song(self):
        plan = _plan("{key: C}\nC  G\n", 1)
        assert {key for key, _ in plan.values()} == {Key('Db', False)}

    def test_a_directive_transpose_cant_read_is_skipped(self):
        # In an American song "Sol" isn't a note transpose reads, so the
        # directive stays as written and the chords are detected instead.
        song = "{key: Sol}\nG  D  Em  C\n"
        plan = _plan(song, 4)
        assert {key for key, _ in plan.values()} == {Key('B', False)}
        assert _moved(song, 4, "american") == "{key: Sol}\nB  F#  G#m  E\n".split()

    def test_the_toolbar_key_is_never_used(self):
        # A wrong toolbar key can't change the spelling: only the text counts.
        from tests.test_transpose_viewmodel import _make_vm
        vm = _make_vm(key="Eb")
        vm.on_text_changed("G  D  Em  C\n")
        vm.transpose(4, None)
        assert vm.current_text.split() == ["B", "F#", "G#m", "E"]
        assert vm.key == "G"


class TestDetectionFallback:
    def test_an_unsure_key_falls_back_to_the_plain_rule(self):
        # G, D and C major are too close to call and spell this differently.
        assert set(_plan("C  G  D\n", 6).values()) == {(None, "G"), (None, "D"), (None, None)}
        assert _moved("C  G  D\n", 6, "american") == "F#  C#  Ab\n".split()

    def test_roman_numerals_and_rests_are_not_read_for_the_key(self):
        assert _moved("G  V  NC  D  Em  C  G\n", 4, "american") == (
            "B  V  NC  F#  G#m  E  B\n").split()


class TestTonic:
    def test_natural_keys_land_on_the_key_with_fewer_accidentals(self):
        assert transpose_key("C", 1, "american") == "Db"
        assert transpose_key("Am", -1, "american") == "G#m"
        assert transpose_key("Do", 1, "european") == "Reb"
        assert transpose_key("Lam", -1, "european") == "Sol#m"

    def test_pop_song_up_a_semitone_is_in_d_flat(self):
        song = "{key: C}\nC  G  Am  F\n"
        assert _moved(song, 1, "american") == "{key: Db}\nDb  Ab  Bbm  Gb\n".split()

    def test_minor_song_down_a_semitone_is_in_g_sharp_minor(self):
        song = "{key: Am}\nAm  Dm  E7  Am\nF  G  C  E\n"
        assert _moved(song, -1, "american") == (
            "{key: G#m}\nG#m  C#m  D#7  G#m\nE  F#  B  D#\n").split()

    def test_the_toolbar_key_follows(self):
        from tests.test_transpose_viewmodel import _make_vm
        vm = _make_vm(key="C")
        vm.on_text_changed("I  IV  V\n")
        vm.transpose(1, None)
        assert vm.key == "Db"


class TestDiminishedLeadingTone:
    def test_a_diminished_chord_leading_up_is_sharp(self):
        song = "{key: C}\nC  C#dim7  Dm7  G7\nC  G#dim  Am  Ebdim7\nDm7  G7  C\n"
        assert _moved(song, 2, "american") == (
            "{key: D}\nD  D#dim7  Em7  A7\nD  A#dim  Bm  Fdim7\nEm7  A7  D\n").split()

    def test_the_next_chords_bass_counts(self):
        song = "{key: C}\nC  C#dim7  G7/D  C\n"
        assert _moved(song, 2, "american") == "{key: D}\nD  D#dim7  A7/E  D\n".split()

    def test_half_diminished_too(self):
        song = "{key: C}\nC  C#m7b5  Dm7  C  C#ø  Dm\n"
        assert _moved(song, 2, "american") == "{key: D}\nD  D#m7b5  Em7  D  D#ø  Em\n".split()

    def test_a_diminished_chord_not_leading_up_keeps_its_degree(self):
        song = "{key: C}\nC  Abdim7  G7  C\n"
        assert _moved(song, 2, "american") == "{key: D}\nD  Bbdim7  A7  D\n".split()

    def test_the_rule_needs_a_key(self):
        assert transpose_chord_token("C#dim7", 2, "american", None, "Dm7") == "D#dim7"
        assert transpose_chord_token("Dbdim7", 2, "american", None, "Dm7") == "Ebdim7"
        assert transpose_chord_token("Dbdim7", 2, "american", Key('D', False), "Dm7") == "D#dim7"


class TestBannedSpellings:
    def test_no_e_sharp_in_f_sharp_major(self):
        assert _moved("{key: C}\nC  Bdim  C\n", 6, "american") == "{key: F#}\nF#  Fdim  F#\n".split()

    def test_no_c_flat_in_g_flat_major(self):
        song = "{key: Db}\nDb  Gb  Ab  Gb\n"
        assert _moved(song, 5, "american") == "{key: Gb}\nGb  B  Db  B\n".split()


class TestRegions:
    def test_a_selection_is_spelled_in_the_key_of_its_section(self):
        song = "{key: G}\nG  D  Em  C\nG  B7  Em  C\n"
        start = song.index("B7")
        assert _moved(song, 4, "american", (start, start + 2)) == (
            "{key: G}\nG  D  Em  C\nG  D#7  Em  C\n").split()

    def test_a_selection_without_a_directive_is_detected_from_the_whole_section(self):
        song = "G  D  Em  C\nG  B7  Em  C  G\n"
        start = song.index("B7")
        assert _moved(song, 4, "american", (start, start + 2)) == "G  D  Em  C\nG  D#7  Em  C  G\n".split()


class TestUnchangedCallers:
    def test_token_without_a_key_keeps_the_plain_rule(self):
        assert transpose_chord_token("G", 4, "american") == "B"
        assert transpose_chord_token("Em", 4, "american") == "Abm"
        assert transpose_chord_token("C#", 2, "american") == "D#"

    def test_token_with_a_key(self):
        assert transpose_chord_token("Em", 4, "american", Key('B', False)) == "G#m"
        assert transpose_chord_token("Mim/Si", 4, "european", Key('B', False)) == "Sol#m/Re#"
        assert transpose_chord_token("em", 4, "american", Key('B', False)) == "g#m"


def test_a_normal_song_plans_its_keys_in_milliseconds():
    """The plan runs on Android's session thread with every transpose; a
    230-line song with no {key} (the detection path) takes about a
    millisecond. The bound is generous for a loaded, shared machine."""
    song = ("G           D/F#        Em          C\nMorning comes and takes the dark away\n"
            "G           B7          Em          A7\nEvery window opens up to day\n"
            "C           Cm          G/D         E7\nHold the line, hold the line, my dear\n"
            "Am7         D7          G\nSunday's almost here\n") * 29
    lines = SongParserService().detect_chords_in_text(song, "american")
    start = time.perf_counter()
    for shift in range(1, 12):
        _spelling_plan(lines, shift, "american")
    per_plan = (time.perf_counter() - start) / 11
    assert per_plan < 0.1, f"{per_plan * 1000:.1f} ms per plan"
