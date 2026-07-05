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
from ui.chord_sheet.renderer_interface import (
    STRIP_BG,
    SheetContext,
    SlotBox,
    StripLayout,
    StripRenderer,
)
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


class _FakeRenderer(StripRenderer):
    """Configurable renderer for panel wiring tests.

    Records the ``ctx.zoom`` seen on every layout and the ``scroll_x``/zoom
    seen on every gutter paint, and lays out fixed-width slots so content is
    wide enough to scroll.
    """

    def __init__(self, id, *, supports_zoom=False, gutter=0.0):
        self.id = id
        self.label = id
        self.supports_zoom = supports_zoom
        self.requires_fingering = False
        self._gutter = float(gutter)
        self.layout_zooms = []
        self.gutter_calls = []

    def gutter_width(self, ctx, height):
        return self._gutter

    def paint_gutter(self, ops, ctx, height, scroll_x):
        self.gutter_calls.append((scroll_x, ctx.zoom))
        if self._gutter > 0:
            ops.rect(0, 0, self._gutter, height, fill="#222222", tags=("gutter",))

    def layout(self, ctx, height):
        self.layout_zooms.append(ctx.zoom)
        n = len(ctx.song.chords)
        slots = tuple(
            SlotBox(chord_index=i, x=float(i * 120), width=120.0) for i in range(n)
        )
        return StripLayout(width=max(1.0, n * 120.0), height=height, slots=slots)

    def paint(self, ops, ctx, layout):
        for slot in layout.slots:
            ops.rect(slot.x, 0, slot.width, layout.height, outline="#444", tags=("slot",))


def _make_panel_with_renderers(root, text, renderers, *, view):
    rendered = _render(text)
    auditions = []
    vm = ChordSheetViewModel(
        FakeConfig(chord_sheet_visible=True, chord_sheet_view=view),
        audio_service=None,
        application=None,
        render_fn=lambda lines, key: rendered,
        audition_fn=auditions.append,
        renderers=renderers,
        scheduler=ImmediateScheduler(),
        marshal=lambda fn: fn(),
    )
    from ui.chord_sheet.panel import ChordSheetPanel

    panel = ChordSheetPanel(root, vm)
    panel.pack(fill=tk.BOTH, expand=True)
    root.update_idletasks()
    vm.set_song([], "C")
    root.update_idletasks()
    return panel, vm, auditions


def test_gutter_pane_appears_with_declared_width(root):
    renderer = _FakeRenderer("g", gutter=40.0)
    panel, vm, _ = _make_panel_with_renderers(root, "C G Am F\n", [renderer], view="g")
    root.update_idletasks()

    assert panel._gutter_width == 40.0
    assert panel._gutter_canvas.winfo_manager() == "grid"   # shown (not removed)
    assert int(panel._gutter_canvas.winfo_reqwidth()) == 40
    assert panel._gutter_canvas.find_all()   # painted something
    assert renderer.gutter_calls             # paint_gutter was called


def test_gutter_corner_does_not_inflate_the_lane_row(root):
    # Regression: the gutter corner is a tk.Canvas; without an explicit
    # height it requests ~260px and inflates the marker-lane row, shoving
    # the strip to the bottom of a tall panel with a big blank band above.
    from ui.chord_sheet.panel import LANE_HEIGHT

    renderer = _FakeRenderer("g", gutter=40.0)
    panel, vm, _ = _make_panel_with_renderers(root, "C G Am F\n", [renderer], view="g")
    root.geometry("900x600")
    root.update_idletasks()
    root.update()

    assert panel._gutter_corner.winfo_height() <= int(LANE_HEIGHT) + 2
    # The strip canvas starts right below the lane, no dead band between.
    lane_bottom = panel._lane_canvas.winfo_y() + panel._lane_canvas.winfo_height()
    assert abs(panel._canvas.winfo_y() - lane_bottom) <= 2


def test_gutter_collapses_for_gutterless_renderer(root):
    renderer = _FakeRenderer("plain", gutter=0.0)
    panel, vm, _ = _make_panel_with_renderers(root, "C G Am F\n", [renderer], view="plain")
    root.update_idletasks()

    assert panel._gutter_width == 0.0
    assert panel._gutter_canvas.winfo_manager() == ""   # never gridded / removed
    assert not panel._gutter_canvas.find_all()


def test_gutter_repaints_on_scroll_with_updated_scroll_x(root):
    # Many chords -> content (~960px) wider than the ~600px viewport, so it scrolls.
    renderer = _FakeRenderer("g", gutter=40.0)
    panel, vm, _ = _make_panel_with_renderers(
        root, "C G Am F C G Am F\n", [renderer], view="g"
    )
    root.update_idletasks()
    assert renderer.gutter_calls[-1][0] == 0.0  # starts at the left edge

    panel._xview_both("moveto", 0.5)
    root.update_idletasks()

    # The gutter repainted with a positive scroll_x reflecting the new position.
    assert renderer.gutter_calls[-1][0] > 0.0


def test_gutter_threads_active_view_zoom(root):
    renderer = _FakeRenderer("g", supports_zoom=True, gutter=40.0)
    panel, vm, _ = _make_panel_with_renderers(root, "C G\n", [renderer], view="g")
    root.update_idletasks()

    vm.zoom_in()
    root.update_idletasks()
    assert renderer.gutter_calls[-1][1] == pytest.approx(1.2)


def test_highlight_and_click_work_with_gutter_present(root):
    renderer = _FakeRenderer("g", gutter=40.0)
    panel, vm, auditions = _make_panel_with_renderers(
        root, "C G Am F\n", [renderer], view="g"
    )
    root.update_idletasks()

    # Highlight follows the playhead: index 1 (slot x=120..240) draws a rect.
    vm.on_playback_chord(vm.rendered_song.chords[1].chord_info, chord_index=1)
    root.update_idletasks()
    assert panel._canvas.find_withtag("playhead-highlight")

    # Click mapping is unaffected by the gutter (event.x is strip-canvas local).
    class _Event:
        pass

    ev = _Event()
    ev.x = 130  # inside slot 1 (120..240) at scroll 0
    panel._on_canvas_click(ev)
    assert auditions and auditions[-1] == list(vm.rendered_song.chords[1].midi_notes)


def test_zoom_buttons_enabled_only_when_supported(root):
    zoomable = _FakeRenderer("z", supports_zoom=True)
    plain = _FakeRenderer("n", supports_zoom=False)
    panel, vm, _ = _make_panel_with_renderers(root, "C G\n", [zoomable, plain], view="z")
    root.update_idletasks()

    assert not panel._zoom_in_btn.instate(("disabled",))
    assert not panel._zoom_out_btn.instate(("disabled",))

    vm.set_active_view("n")
    root.update_idletasks()
    assert panel._zoom_in_btn.instate(("disabled",))
    assert panel._zoom_out_btn.instate(("disabled",))


def test_zoom_change_repaints_with_new_context_value(root):
    zoomable = _FakeRenderer("z", supports_zoom=True)
    panel, vm, _ = _make_panel_with_renderers(root, "C G Am\n", [zoomable], view="z")
    root.update_idletasks()

    zoomable.layout_zooms.clear()
    vm.zoom_in()
    root.update_idletasks()

    assert zoomable.layout_zooms                       # a relayout happened
    assert zoomable.layout_zooms[-1] == pytest.approx(1.2)


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


def test_view_picker_has_one_toggle_button_per_renderer_in_order(root):
    panel, vm = _make_panel(root, "C G\nAm F\n")
    labels_by_id = {renderer.id: renderer.label for renderer in vm.renderers}

    assert set(panel._view_buttons.keys()) == set(labels_by_id.keys())
    for view_id, button in panel._view_buttons.items():
        assert button.cget("text") == labels_by_id[view_id]


def test_fingering_gated_buttons_disabled_for_piano_rendered_song(root):
    # ``ChordNotePicker`` (used by ``_render``) voices for piano: no
    # fingering data, so the fretted views (fret box, tab) must be gated out
    # and shown disabled, while the ungated ones stay enabled.
    panel, vm = _make_panel(root, "C G\nAm F\n")
    assert "fret" not in vm.available_views
    assert "tab" not in vm.available_views
    assert "keyboard" in vm.available_views
    assert "staff" in vm.available_views

    for view_id, button in panel._view_buttons.items():
        if view_id in vm.available_views:
            assert not button.instate(("disabled",)), f"{view_id} should be enabled"
        else:
            assert button.instate(("disabled",)), f"{view_id} should be disabled"


def test_clicking_an_enabled_button_switches_the_active_view(root):
    panel, vm = _make_panel(root, "C G\nAm F\n")
    assert vm.active_view == "keyboard"

    panel._view_buttons["staff"].invoke()
    root.update_idletasks()

    assert vm.active_view == "staff"
    assert panel._view_var.get() == "staff"


def test_canvas_backgrounds_use_strip_bg(root):
    panel, vm = _make_panel(root, "C G\n")
    assert panel._canvas.cget("bg") == STRIP_BG
    assert panel._lane_canvas.cget("bg") == STRIP_BG


def _render_guitar(text):
    from audio.guitar_chord_picker import GuitarChordPicker

    lines = SongParserService().detect_chords_in_text(text)
    return SongRenderer().render(
        lines=lines,
        initial_key="C",
        initial_bpm=120,
        initial_time_sig=(4, 4),
        note_picker=GuitarChordPicker("standard"),
    )


def test_capo_suggestion_label_shows_only_for_fretboard_views(root):
    from models.fretboard_spec import BUILTIN_FRETBOARDS

    rendered = _render_guitar("F# B C# D#m\n")
    vm = ChordSheetViewModel(
        FakeConfig(chord_sheet_visible=True, chord_sheet_view="fret", allow_capo=True),
        audio_service=None,
        application=None,
        render_fn=lambda lines, key: rendered,
        audition_fn=lambda notes: None,
        scheduler=ImmediateScheduler(),
        marshal=lambda fn: fn(),
        capo_spec_fn=lambda: BUILTIN_FRETBOARDS["standard"],
    )
    from ui.chord_sheet.panel import ChordSheetPanel

    panel = ChordSheetPanel(root, vm)
    panel.pack(fill=tk.BOTH, expand=True)
    root.update_idletasks()
    vm.set_song([], "C")
    root.update_idletasks()
    # Fret becomes available once the fretted song is rendered; select it.
    vm.set_active_view("fret")
    root.update_idletasks()

    # The barre-heavy F# progression suggests a nonzero capo, shown on fret view.
    assert vm.capo_suggestion is not None
    assert vm.active_view == "fret"
    assert "capo" in panel._capo_label.cget("text").lower()

    # A non-fretboard view hides the suggestion...
    vm.set_active_view("keyboard")
    root.update_idletasks()
    assert panel._capo_label.cget("text") == ""

    # ...and the tab view shows it again.
    vm.set_active_view("tab")
    root.update_idletasks()
    assert "capo" in panel._capo_label.cget("text").lower()
