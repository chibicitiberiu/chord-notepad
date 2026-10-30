"""The desktop's directive hints: the status-bar hint and the hover tooltip.

``StatusLine`` (what the status bar shows) is plain logic. ``DirectiveHints``
runs against a real ``ChordTextEditor`` and a real session in a hidden Tk
root; those tests skip without a display.
"""

import os

import pytest

from models.directive import DIRECTIVE_SYNTAX
from session import formatting
from ui.directive_hints import StatusLine


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


# -- the session answers without detecting again ---------------------------

def test_the_session_hint_reuses_the_last_detection(monkeypatch):
    from tests.test_session_playback import Env
    from services.song_parser_service import SongParserService

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


# -- the Tk wiring -----------------------------------------------------------

tk = pytest.importorskip('tkinter')


@pytest.fixture
def root():
    if not (os.environ.get('DISPLAY') or os.name == 'nt'):
        pytest.skip("No display available for tkinter tests")
    try:
        instance = tk.Tk()
    except tk.TclError:
        pytest.skip("No display available for tkinter tests")
    # Mapped (bbox needs it) but off-screen and past the window manager.
    instance.overrideredirect(True)
    instance.geometry("+-4000+-4000")
    yield instance
    instance.destroy()


@pytest.fixture
def ui(root):
    """A session, an editor painting its highlight and the hints over them."""
    from tests.test_session_playback import Env
    from ui.directive_hints import DirectiveHints
    from ui.text_editor import ChordTextEditor

    text = "{bpm: 0}\n{capo: 2}\n{capo: 3}\nC G\n{key: G}"
    env = Env(text=text)
    editor = ChordTextEditor(root, session=env.session, width=40, height=8)
    editor.pack()
    editor.insert('1.0', text)
    editor.paint_spans(env.session._spans)
    label = tk.Label(root, text="Ready")
    hints = DirectiveHints(editor, label, env.session, delay_ms=0)
    hints.set_status("Ready")
    root.update()
    return editor, label, hints, text


def _put_cursor(editor, offset):
    editor.mark_set(tk.INSERT, f"1.0 + {offset} chars")


class TestDirectiveHintsTk:
    def test_the_cursor_in_a_directive_shows_its_hint(self, ui):
        editor, label, hints, text = ui
        _put_cursor(editor, text.index("{key") + 3)
        hints.refresh()
        assert label.cget("text") == "{key: G} · {key: Am} · {key: F#m} · {key: Sol}"

    def test_an_invalid_directive_gives_its_reason_first(self, ui):
        editor, label, hints, _text = ui
        _put_cursor(editor, 3)
        hints.refresh()
        assert label.cget("text") == "Tempo must be 20-400 — " + " · ".join(
            DIRECTIVE_SYNTAX["bpm"].split(" · "))

    def test_leaving_the_directive_restores_the_status(self, ui):
        editor, label, hints, text = ui
        _put_cursor(editor, 3)
        hints.refresh()
        _put_cursor(editor, text.index("C G") + 1)
        hints.refresh()
        assert label.cget("text") == "Ready"

    def test_while_playing_the_hint_waits(self, ui):
        editor, label, hints, _text = ui
        hints.set_playing(True)
        hints.set_status("Bar 1/2 · Playing C")
        _put_cursor(editor, 3)
        hints.refresh()
        assert label.cget("text") == "Bar 1/2 · Playing C"

    def test_typing_schedules_one_lookup(self, ui, root):
        editor, label, hints, _text = ui
        _put_cursor(editor, 3)
        hints.schedule()
        hints.schedule()
        root.update()
        root.after(5)
        root.update()
        assert label.cget("text").startswith("Tempo must be 20-400")

    def _xy(self, editor, offset):
        x, y, _w, h = editor.bbox(f"1.0 + {offset} chars")
        return x + 1, y + h // 2

    def test_hovering_a_red_directive_explains_it(self, ui):
        editor, _label, hints, _text = ui
        region = hints.region_at(*self._xy(editor, 2))
        assert region == (0, len("{bpm: 0}"))
        assert hints.tooltip_text(region) == "Tempo must be 20-400\n" + DIRECTIVE_SYNTAX["bpm"]

    def test_hovering_a_faded_directive_explains_it(self, ui):
        editor, _label, hints, text = ui
        start = text.index("{capo: 2}")
        region = hints.region_at(*self._xy(editor, start + 1))
        assert region == (start, start + len("{capo: 2}"))
        assert hints.tooltip_text(region).startswith("Has no effect: replaced by {capo: 3}")

    def test_valid_directives_and_chords_have_no_tooltip(self, ui):
        editor, _label, hints, text = ui
        assert hints.region_at(*self._xy(editor, text.index("{key") + 1)) is None
        assert hints.region_at(*self._xy(editor, text.index("C G"))) is None

    def test_the_tooltip_shows_after_hovering(self, ui, root):
        editor, _label, hints, _text = ui
        hints.tooltip.delay_ms = 0
        x, y = self._xy(editor, 2)
        hints.tooltip._on_motion(type("E", (), {"x": x, "y": y})())
        root.update()
        root.after(5)
        root.update()
        window = hints.tooltip._tip_window
        assert window is not None
        # Under the directive, not over it.
        _x, line_y, _w, line_h = editor.bbox("1.0")
        assert window.winfo_y() >= editor.winfo_rooty() + line_y + line_h
        assert window.winfo_children()[0].cget("text").startswith("Tempo must be 20-400")
        hints.tooltip._on_leave()
        assert hints.tooltip._tip_window is None
