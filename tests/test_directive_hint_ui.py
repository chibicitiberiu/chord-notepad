"""The desktop's directive hints: the status-bar hint and the hover tooltip.

``StatusLine`` (what the status bar shows) is plain core logic, which the
Qt status bar uses; tests/qt/test_qt_hints.py covers the window's side.
"""

from chordnotepad.models.directive import DIRECTIVE_SYNTAX
from chordnotepad.session import formatting
from chordnotepad.session.status_line import StatusLine


# -- the texts --------------------------------------------------------------

def test_the_status_hint_puts_the_reason_first():
    assert (formatting.directive_hint_status("Tempo must be 20-400", "{bpm: 120} · {bpm: +10}")
            == "Tempo must be 20-400 — {bpm: 120} · {bpm: +10}")


def test_a_valid_directive_shows_only_its_syntax():
    assert formatting.directive_hint_status("", DIRECTIVE_SYNTAX["capo"]) == "{capo: 3} · {capo: 0}"


def test_several_candidates_go_on_one_line():
    syntax = DIRECTIVE_SYNTAX["label"] + "\n" + DIRECTIVE_SYNTAX["loop"]
    assert formatting.directive_hint_status("", syntax) == (
        "{label: verse} · {loop: verse} · {loop: verse 3} · {loop: @start 2}")


def test_no_directive_no_hint():
    assert formatting.directive_hint_status("", "") == ""


def test_the_tooltip_has_the_reason_then_the_syntax():
    assert (formatting.directive_hint_tooltip("Capo must be a fret from 0 to 12", "{capo: 3} · {capo: 0}")
            == "Capo must be a fret from 0 to 12\n{capo: 3} · {capo: 0}")


# -- what the status bar shows ----------------------------------------------

class TestStatusLine:
    def _line(self):
        shown = []
        return StatusLine(shown.append), shown

    def test_the_hint_shows_over_the_status_and_leaving_brings_it_back(self):
        line, shown = self._line()
        line.set_status("Opened song.txt", cursor=0)
        line.set_hint("{bpm: 120} · {bpm: +10}", cursor=5)
        assert shown[-1] == "{bpm: 120} · {bpm: +10}"
        line.set_hint("", cursor=20)
        assert shown[-1] == "Opened song.txt"

    def test_playback_status_wins(self):
        line, shown = self._line()
        line.set_hint("{key: G} · {key: Am}", cursor=3)
        line.set_playing(True)
        line.set_status("Bar 1/8 · Playing C", cursor=3)
        assert shown[-1] == "Bar 1/8 · Playing C"
        line.set_hint("{key: G} · {key: Am}", cursor=4)
        assert line.text == "Bar 1/8 · Playing C"
        line.set_playing(False)
        assert shown[-1] == "{key: G} · {key: Am}"

    def test_a_new_status_shows_until_the_cursor_moves(self):
        line, shown = self._line()
        line.set_hint("{bpm: 120}", cursor=4)
        line.set_status("Saved song.txt", cursor=4)
        line.set_hint("{bpm: 120}", cursor=4)        # the cursor hasn't moved
        assert shown[-1] == "Saved song.txt"
        line.set_hint("{bpm: 120}", cursor=5)
        assert shown[-1] == "{bpm: 120}"

    def test_an_unchanged_hint_is_not_shown_again(self):
        line, shown = self._line()
        line.set_hint("{bpm: 120}", cursor=4)
        line.set_hint("{bpm: 120}", cursor=5)
        assert shown == ["{bpm: 120}"]

    def test_any_hint_value_works_and_false_is_none(self):
        # Qt hands over the reason and the syntax apart.
        line, shown = self._line()
        line.set_status("Ready", cursor=0)
        line.set_hint(("Not a key", "{key: G}"), cursor=2)
        assert line.showing_hint and shown[-1] == ("Not a key", "{key: G}")
        line.set_hint(None, cursor=9)
        assert not line.showing_hint and shown[-1] == "Ready"


# -- the session answers without detecting again ---------------------------

def test_the_session_hint_reuses_the_last_detection(monkeypatch):
    from tests.test_session_playback import Env
    from chordnotepad.services.song_parser_service import SongParserService

    env = Env(text="{capo: 2}\n{capo: 3}\nC G")

    def no_detection(*_a, **_k):
        raise AssertionError("detected again")

    monkeypatch.setattr(SongParserService, "detect_chords_in_text", no_detection)
    hint = env.session.directive_hint_at(2)
    assert hint.redundant and hint.message.startswith("Has no effect")
    # Typed, not detected yet: the directives alone are parsed (cheap).
    env.session.set_text("{capo: 2}\n{capo: 30}\nC G", client_token=1)
    hint = env.session.directive_hint_at(len("{capo: 2}\n{ca"))
    assert (hint.message, hint.redundant) == ("Capo must be a fret from 0 to 12", False)

