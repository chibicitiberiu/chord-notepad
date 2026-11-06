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


class TestChromaticChordsKeepTheirLetters:
    """C2: a chromatic chord keeps the letters the song wrote it with, moved
    as far as the key moved, so a secondary ii-V still leads where it went.
    Diatonic chords are spelled by the key as before."""

    def test_the_reported_song(self):
        # Bb major with a ii-V-i of E minor: up a tone it's C major with a
        # ii-V-i of F# minor, not C major's Abm7b5 Db7.
        song = "Bb F/A Gm7 Eb\nF#m7b5 B7 Em NC\n"
        assert _moved(song, 2, "american") == "C G/B Am7 F G#m7b5 C#7 F#m NC".split()
        assert _moved(song, -3, "american") == "G D/F# Em7 C D#m7b5 G#7 C#m NC".split()

    def test_the_reported_song_comes_back(self):
        song = "Bb F/A Gm7 Eb\nF#m7b5 B7 Em NC\n"
        for shift in (2, -2, 3, -3, 4, 5, 7, -7):
            back = transpose_text(transpose_text(song, shift, "american"), -shift, "american")
            assert back.split() == song.split(), shift

    def test_a_secondary_ii_v_with_a_key(self):
        song = "{key: Bb}\nBb  G7  Cm7  F7  Bb  F#m7b5  B7  Em\n"
        assert _moved(song, 2, "american") == (
            "{key: C}\nC  A7  Dm7  G7  C  G#m7b5  C#7  F#m\n").split()
        assert _moved(song, -1, "american") == (
            "{key: A}\nA  F#7  Bm7  E7  A  Fm7b5  A#7  D#m\n").split()

    def test_ii_v_i_in_minor_keys(self):
        song = "{key: Am}\nBm7b5  E7  Am\n"
        assert _moved(song, 1, "american") == "{key: Bbm}\nCm7b5  F7  Bbm\n".split()
        assert _moved(song, 2, "american") == "{key: Bm}\nC#m7b5  F#7  Bm\n".split()
        assert _moved(song, -1, "american") == "{key: G#m}\nA#m7b5  D#7  G#m\n".split()
        assert _moved(song, -3, "american") == "{key: F#m}\nG#m7b5  C#7  F#m\n".split()

    def test_a_minor_song_moving_to_its_dominant(self):
        song = "{key: Em}\nEm  C#m7b5  F#7  Bm\n"
        assert _moved(song, 2, "american") == "{key: F#m}\nF#m  D#m7b5  G#7  C#m\n".split()
        assert _moved(song, 1, "american") == "{key: Fm}\nFm  Dm7b5  G7  Cm\n".split()

    def test_secondary_dominants_on_the_key_degrees(self):
        song = "{key: C}\nC  A7  Dm7  G7  C  E7  Am  D7  G\n"
        assert _moved(song, 1, "american") == (
            "{key: Db}\nDb  Bb7  Ebm7  Ab7  Db  F7  Bbm  Eb7  Ab\n").split()
        assert _moved(song, -1, "american") == (
            "{key: B}\nB  G#7  C#m7  F#7  B  D#7  G#m  C#7  F#\n").split()

    def test_a_stand_in_letter_takes_the_key_spelling_and_its_dominant_follows(self):
        # B7 E in Eb: E stands in for Fb (Eb has no degree spelling for it,
        # the letter can't be trusted), so it takes F major's lowered second,
        # Gb, and B7, a fifth above it, follows as Db7.
        song = "{key: Eb}\nEb  B7  E  Eb\n"
        assert _moved(song, 2, "american") == "{key: F}\nF  Db7  Gb  F\n".split()
        back = transpose_text(transpose_text(song, 2, "american"), -2, "american")
        assert back.split() == song.split()

    def test_borrowed_chords_keep_their_flats(self):
        song = "{key: C}\nC  Eb7  Ab  G7  C  Db7  C  Bb  F  C\n"
        assert _moved(song, 2, "american") == (
            "{key: D}\nD  F7  Bb  A7  D  Eb7  D  C  G  D\n").split()
        for shift in range(1, 12):
            for signed in (shift, -shift):
                back = transpose_text(transpose_text(song, signed, "american"), -signed, "american")
                assert back.split() == song.split(), signed

    def test_a_letter_that_would_need_a_double_sharp_keeps_the_fifths(self):
        # Bb up a semitone is B: F# would move to F## and E to E#, so Em takes
        # B major's spelling, F, and the chords before it stay a fifth apart
        # from it: C7, Gm7b5. Back down the fifths bring the letters back.
        song = "{key: Bb}\nBb  F#m7b5  B7  Em\n"
        assert _moved(song, 1, "american") == "{key: B}\nB  Gm7b5  C7  Fm\n".split()
        for shift in range(1, 12):
            for signed in (shift, -shift):
                back = transpose_text(transpose_text(song, signed, "american"), -signed,
                                      "american")
                assert back.split() == song.split(), signed

    def test_a_stand_in_letter_is_not_moved(self):
        # Eb in C up a semitone would be Fb in Db: E stands in for it. Moving
        # that E back as a letter would give D#; it comes back as Eb.
        song = "{key: C}\nC  Eb  C\n"
        assert _moved(song, 1, "american") == "{key: Db}\nDb  E  Db\n".split()
        assert transpose_text(transpose_text(song, 1, "american"), -1, "american").split() == (
            song.split())

    def test_without_a_sure_key_each_chord_keeps_its_own_accidental(self):
        # No {key} and a detection that can't tell: the plain rule, the
        # conservative choice (see TestDetectionFallback).
        assert transpose_chord_token("F#m7b5", 2, "american") == "G#m7b5"
        assert transpose_chord_token("B7", 2, "american") == "C#7"
        assert transpose_chord_token("Bb7", 2, "american") == "C7"

    def test_the_source_key_letters_drive_european_too(self):
        song = "{key: Sib}\nSib  Fa#m7b5  Si7  Mim\n"
        assert _moved(song, 2, "european") == "{key: Do}\nDo  Sol#m7b5  Do#7  Fa#m\n".split()

    def test_a_token_needs_both_keys_for_the_letter_rule(self):
        assert transpose_chord_token("F#7", 2, "american", Key('C', False)) == "Ab7"
        assert transpose_chord_token("F#7", 2, "american", Key('C', False), None,
                                     Key('Bb', False)) == "G#7"
        assert transpose_chord_token("Em/F#", 2, "american", Key('C', False), None,
                                     Key('Bb', False)) == "F#m/G#"

    def test_a_token_a_fifth_above_the_next_root_follows_it(self):
        # B in Bb stands in for Cb: alone it moves by degree (Db7, a tritone
        # substitute in C); before the next chord's F#, a fifth above it.
        assert transpose_chord_token("B7", 2, "american", Key('C', False), None,
                                     Key('Bb', False)) == "Db7"
        assert transpose_chord_token("B7", 2, "american", Key('C', False), "Em",
                                     Key('Bb', False), "F#") == "C#7"


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
        assert {entry.key for entry in plan.values()} == {Key('Db', False)}
        assert {entry.source_key for entry in plan.values()} == {Key('C', False)}

    def test_a_directive_transpose_cant_read_is_skipped(self):
        # In an American song "Sol" isn't a note transpose reads, so the
        # directive stays as written and the chords are detected instead.
        song = "{key: Sol}\nG  D  Em  C\n"
        plan = _plan(song, 4)
        assert {entry.key for entry in plan.values()} == {Key('B', False)}
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
        assert set(_plan("C  G  D\n", 6).values()) == {
            (None, "G", None, None), (None, "D", None, None), (None, None, None, None)}
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
