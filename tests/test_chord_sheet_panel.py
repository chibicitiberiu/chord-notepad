"""Tk-backed tests for the chord-sheet panel (skipped without a display).

These exercise the wiring the headless renderer/viewmodel tests can't reach: the
two-canvas marker lane, clef-image resolution during replay, and view switching.
"""

import os

import pytest

tk = pytest.importorskip("tkinter")

from audio.chord_picker import ChordNotePicker
from services.song_parser_service import SongParserService
from services.song_renderer import SongRenderer
from viewmodels.chord_sheet_viewmodel import ChordSheetViewModel


def _has_display() -> bool:
    return bool(os.environ.get("DISPLAY")) or os.name == "nt"


@pytest.fixture
def root():
    if not _has_display():
        pytest.skip("No display available for tkinter tests")
    r = tk.Tk()
    r.geometry("600x300")
    r.update_idletasks()
    yield r
    r.destroy()


class FakeConfig:
    def __init__(self, **values):
        self._values = values

    def get(self, key, default=None):
        return self._values.get(key, default)

    def set(self, key, value):
        self._values[key] = value


class ImmediateScheduler:
    """Runs the scheduled render synchronously (no real timer)."""

    def schedule(self, delay, fn):
        fn()
        return None

    def cancel(self, handle):
        pass


def _render(text):
    lines = SongParserService().detect_chords_in_text(text)
    return SongRenderer().render(
        lines=lines,
        initial_key="C",
        initial_bpm=120,
        initial_time_sig=(4, 4),
        note_picker=ChordNotePicker(),
    )


def _make_panel(root, text, *, view="keyboard"):
    rendered = _render(text)

    def render_fn(lines, key):
        return rendered

    vm = ChordSheetViewModel(
        FakeConfig(chord_sheet_visible=True, chord_sheet_view=view),
        audio_service=None,
        application=None,
        render_fn=render_fn,
        audition_fn=lambda notes: None,
        scheduler=ImmediateScheduler(),
        marshal=lambda fn: fn(),
    )
    from ui.chord_sheet.panel import ChordSheetPanel

    panel = ChordSheetPanel(root, vm)
    panel.pack(fill=tk.BOTH, expand=True)
    root.update_idletasks()
    vm.set_song([], "C")
    root.update_idletasks()
    return panel, vm


def test_panel_paints_all_views_without_error(root):
    panel, vm = _make_panel(root, "{label: verse}\nC G\n{bpm: 140}\nAm F\n")
    for view in vm.available_views:
        vm.set_active_view(view)
        root.update_idletasks()
        # Main strip drew something for every view.
        assert panel._canvas.find_all()


def test_marker_lane_is_populated(root):
    # A {label} + {bpm} song produces section and tempo markers.
    panel, vm = _make_panel(root, "{label: verse}\nC G\n{bpm: 140}\nAm F\n")
    root.update_idletasks()
    # The lane canvas has items (separator + marker rules/flags).
    assert panel._lane_canvas.find_all()


def test_staff_view_resolves_clef_images(root):
    panel, vm = _make_panel(root, "C G\nAm F\n", view="staff")
    vm.set_active_view("staff")
    root.update_idletasks()
    # Clef image keys were resolved into referenced PhotoImages.
    assert any(k.startswith("clef_") for k in panel._images)


def test_hidden_panel_paints_after_being_shown(root):
    rendered = _render("C G\n")
    vm = ChordSheetViewModel(
        FakeConfig(chord_sheet_visible=False),
        audio_service=None,
        application=None,
        render_fn=lambda lines, key: rendered,
        audition_fn=lambda notes: None,
        scheduler=ImmediateScheduler(),
        marshal=lambda fn: fn(),
    )
    from ui.chord_sheet.panel import ChordSheetPanel

    panel = ChordSheetPanel(root, vm)
    panel.pack(fill=tk.BOTH, expand=True)
    root.update_idletasks()

    vm.set_song([], "C")  # hidden: no render happens
    root.update_idletasks()
    assert vm.rendered_song is None

    vm.set_visible(True)  # shown: flushes the held input and renders
    root.update_idletasks()
    assert vm.rendered_song is rendered
    assert panel._canvas.find_all()
