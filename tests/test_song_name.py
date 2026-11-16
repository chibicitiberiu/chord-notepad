"""session.song_name: an untitled song's name, from its first lyric line.

Where it is used: the Backups row of an untitled song
(tests/qt/test_qt_recovery.py) and the name Save and Export MIDI suggest
(tests/test_session_documents.py).
"""

from pathlib import Path

import pytest

from chordnotepad.session import song_name
from chordnotepad.session.song_name import lyric_name, song_file_name

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


@pytest.mark.parametrize("example, notation, name", [
    ("01_quick_start.txt", "american", "Twinkle, twinkle, little star"),
    ("02_american_complete.txt", "american", "I know a bank where the wild thyme blows"),
    # Its chords are European: in that notation the chord lines are skipped.
    ("03_european.txt", "european", "In a village of La Mancha, the name of which"),
    ("04_roman_numerals.txt", "american", "Once upon a midnight dreary, while I pondered"),
])
def test_the_bundled_examples_are_named_by_their_first_lyric(example, notation, name):
    text = (EXAMPLES / example).read_text(encoding="utf-8")
    assert lyric_name(text, notation) == name


def test_the_quick_start_example_suggests_its_first_line_as_the_file_name():
    text = (EXAMPLES / "01_quick_start.txt").read_text(encoding="utf-8")
    assert song_file_name(text) == "Twinkle, twinkle, little star.txt"


def test_chord_lines_directives_comments_and_blank_lines_are_skipped():
    text = ("{bpm: 90} {key: G}\n"
            "\n"
            "   \n"
            "// A comment, not lyrics\n"
            "{label: verse}\n"
            "G   D   Em  C\n"
            "  Amazing grace,   how sweet  \n")
    assert lyric_name(text) == "Amazing grace, how sweet"


def test_a_directive_or_comment_on_a_lyric_line_is_left_out():
    assert lyric_name("{capo: 2} Here comes the sun // intro\n") == "Here comes the sun"


def test_a_song_without_lyrics_has_no_name():
    for text in ("", "\n\n", "C G Am F\nAm*2 G*2\n", "{bpm: 90}\n// notes\n",
                 "---\n| | | |\n***\n"):
        assert lyric_name(text) is None
        assert song_name.song_name(text) == "Untitled"
        assert song_file_name(text) == "Untitled.txt"


def test_a_line_of_punctuation_isnt_a_lyric():
    assert lyric_name("C G\n-- -- --\nla la la\n") == "la la la"


def test_the_plain_text_marker_isnt_part_of_the_name():
    # "Am I" would be a chord line without the dot.
    assert lyric_name(".Am I wrong\n") == "Am I wrong"


def test_the_notation_decides_what_is_a_chord_line():
    text = "Do Re Mi Fa\nSing along\n"
    assert lyric_name(text, "american") == "Do Re Mi Fa"
    assert lyric_name(text, "european") == "Sing along"


def test_characters_no_file_system_takes_are_replaced():
    name = lyric_name('He said: "stop/go" <now> | a*b\\c? \x07ok\n')
    assert name == "He said stop go now a b c ok"
    assert not set(name) & set('\\/:*?"<>|')


def test_trailing_punctuation_and_leading_dots_go():
    assert lyric_name("Twinkle, twinkle, little star,\n") == "Twinkle, twinkle, little star"
    assert lyric_name("And so it ends...\n") == "And so it ends"
    assert lyric_name("Wait for me -\n") == "Wait for me"
    assert lyric_name("Hallelujah!\n") == "Hallelujah!"
    assert lyric_name(". ..hidden\n") == "hidden"


def test_a_long_line_is_cut_at_a_word_boundary():
    line = "Oh what a beautiful morning, oh what a beautiful day, I've got a feeling"
    name = lyric_name(line)
    assert name == "Oh what a beautiful morning, oh what a beautiful"
    assert len(name) <= song_name.MAX_LENGTH
    assert line.startswith(name)


def test_a_long_word_is_cut_where_the_limit_is():
    name = lyric_name("x" * 100)
    assert name == "x" * song_name.MAX_LENGTH


def test_a_name_windows_reserves_for_a_device_isnt_used():
    assert lyric_name("Con\n") is None
    assert lyric_name("Con\nCon te partirò\n") == "Con te partirò"


def test_the_name_is_valid_for_rename_and_save():
    # The session refuses names with separators or control characters, and
    # over its byte limit.
    from chordnotepad.session import formatting

    name = lyric_name("Ünïcödé ✓ " * 20)
    assert name and len(name.encode("utf-8")) <= formatting.MAX_NAME_BYTES
    assert "/" not in name and "\\" not in name
