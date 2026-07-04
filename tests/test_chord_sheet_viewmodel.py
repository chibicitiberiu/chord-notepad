"""Tests for the headless ``ChordSheetViewModel``.

The threading seams (debounce scheduler + UI-thread marshal) are injected so
everything runs synchronously: a ``ManualScheduler`` records the single pending
debounced call and fires it on ``flush()``, and the marshal is a direct call.
"""

from typing import Optional

import pytest

from models.rendered_song import RenderedSong, RenderedChord
from models.chord import ChordInfo
from ui.chord_sheet.name_card import NameCardRenderer
from ui.chord_sheet.renderer_interface import (
    SheetContext,
    SlotBox,
    StripLayout,
    StripRenderer,
)
from viewmodels.chord_sheet_viewmodel import ChordSheetViewModel


# --------------------------------------------------------------------------
# Fakes / helpers
# --------------------------------------------------------------------------


class FakeConfig:
    def __init__(self, **values):
        self._values = values

    def get(self, key, default=None):
        return self._values.get(key, default)

    def set(self, key, value):
        self._values[key] = value


class FakeAudio:
    """Stand-in for PlaybackService: records renders and auditions."""

    def __init__(self, rendered=None):
        self.rendered = rendered
        self.render_calls = []
        self.auditions = []

    def render_song(self, lines, key):
        self.render_calls.append((lines, key))
        return self.rendered

    def play_notes_immediate(self, notes):
        self.auditions.append(list(notes))


class ManualScheduler:
    """Debounce scheduler that keeps only the latest pending call."""

    def __init__(self):
        self.pending = None  # (handle, fn)

    def schedule(self, delay, fn):
        handle = object()
        self.pending = (handle, fn)
        return handle

    def cancel(self, handle):
        if self.pending is not None and self.pending[0] is handle:
            self.pending = None

    def flush(self):
        if self.pending is not None:
            _, fn = self.pending
            self.pending = None
            fn()


def direct_marshal(fn):
    fn()


class FingeringRenderer(StripRenderer):
    """Minimal renderer that only makes sense with fingering data."""

    id = "fret"
    label = "Fret"
    requires_fingering = True

    def layout(self, ctx: SheetContext, height: float) -> StripLayout:
        return StripLayout(width=1.0, height=height, slots=())

    def paint(self, ops, ctx, layout):
        pass


def make_chord(symbol="C", start=0, end=1, is_rest=False, midi_notes=(60, 64, 67), fingering=None):
    return RenderedChord(
        chord_info=ChordInfo(chord=symbol, start=start, end=end, is_valid=True),
        chord_notes=None,
        midi_notes=None if is_rest else list(midi_notes),
        line_index=0,
        item_index=0,
        start_beat=0.0,
        duration_beats=1.0,
        start_time=0.0,
        duration_seconds=0.0,
        bpm=120,
        time_sig=(4, 4),
        key=None,
        bar=1,
        is_rest=is_rest,
        fingering=fingering,
    )


def make_vm(rendered=None, config=None, renderers=None, audio=None, scheduler=None):
    audio = audio or FakeAudio(rendered=rendered)
    scheduler = scheduler or ManualScheduler()
    vm = ChordSheetViewModel(
        config or FakeConfig(),
        audio,
        application=None,
        renderers=renderers,
        scheduler=scheduler,
        marshal=direct_marshal,
    )
    return vm, audio, scheduler


# --------------------------------------------------------------------------
# Debounce
# --------------------------------------------------------------------------


def test_debounce_collapses_rapid_song_changes_into_one_render():
    song = RenderedSong(chords=[make_chord("C")])
    vm, audio, scheduler = make_vm(rendered=song)

    vm.set_song([], "C")
    vm.set_song([], "G")
    vm.set_song([], "Am")  # only the last should survive
    assert audio.render_calls == []  # nothing rendered until the timer fires

    scheduler.flush()
    assert len(audio.render_calls) == 1
    assert audio.render_calls[0][1] == "Am"  # latest key won
    assert vm.rendered_song is song


def test_render_result_notifies_observers():
    song = RenderedSong(chords=[make_chord("C")])
    vm, audio, scheduler = make_vm(rendered=song)
    seen = []
    vm.observe("rendered_song", seen.append)

    vm.set_song([], None)
    scheduler.flush()
    assert seen == [song]


# --------------------------------------------------------------------------
# current_index driven by playback pings
# --------------------------------------------------------------------------


def test_current_index_follows_playback_pings():
    song = RenderedSong(chords=[
        make_chord("C", start=0, end=1),
        make_chord("G", start=2, end=3),
        make_chord("Am", start=4, end=6),
    ])
    vm, _, scheduler = make_vm(rendered=song)
    vm.set_song([], None)
    scheduler.flush()

    vm.on_playback_chord(ChordInfo(chord="G", start=2, end=3))
    assert vm.current_index == 1

    vm.on_playback_chord(ChordInfo(chord="Am", start=4, end=6))
    assert vm.current_index == 2

    vm.on_playback_chord(None)
    assert vm.current_index is None


def test_current_index_none_when_chord_not_in_song():
    song = RenderedSong(chords=[make_chord("C", start=0, end=1)])
    vm, _, scheduler = make_vm(rendered=song)
    vm.set_song([], None)
    scheduler.flush()

    vm.on_playback_chord(ChordInfo(chord="Z", start=99, end=100))
    assert vm.current_index is None


def test_new_render_clears_stale_index():
    song = RenderedSong(chords=[make_chord("C", start=0, end=1)])
    vm, _, scheduler = make_vm(rendered=song)
    vm.set_song([], None)
    scheduler.flush()
    vm.on_playback_chord(ChordInfo(chord="C", start=0, end=1))
    assert vm.current_index == 0

    vm.set_song([], None)
    scheduler.flush()
    assert vm.current_index is None


# --------------------------------------------------------------------------
# View gating + fallback
# --------------------------------------------------------------------------


def test_fingering_renderer_hidden_for_piano_song():
    renderers = [NameCardRenderer(), FingeringRenderer()]
    piano_song = RenderedSong(chords=[make_chord("C", fingering=None)])
    vm, _, scheduler = make_vm(rendered=piano_song, renderers=renderers)

    # Before any render: no fingering data -> fret hidden.
    assert "fret" not in vm.available_views
    assert vm.available_views == ["name"]

    vm.set_song([], None)
    scheduler.flush()
    assert vm.available_views == ["name"]


def test_fingering_renderer_shown_for_fretted_song():
    renderers = [NameCardRenderer(), FingeringRenderer()]
    fretted_song = RenderedSong(chords=[make_chord("C", fingering=[-1, 3, 2, 0, 1, 0])])
    vm, _, scheduler = make_vm(rendered=fretted_song, renderers=renderers)

    vm.set_song([], None)
    scheduler.flush()
    assert "fret" in vm.available_views


def test_active_view_falls_back_when_it_becomes_unavailable():
    renderers = [NameCardRenderer(), FingeringRenderer()]
    fretted = RenderedSong(chords=[make_chord("C", fingering=[0, 0, 0, 0, 0, 0])])
    vm, audio, scheduler = make_vm(rendered=fretted, renderers=renderers)

    vm.set_song([], None)
    scheduler.flush()
    vm.set_active_view("fret")  # now selectable (fingering present)
    assert vm.active_view == "fret"

    # Re-render a piano song: fret disappears, active view falls back to 'name'.
    audio.rendered = RenderedSong(chords=[make_chord("C", fingering=None)])
    vm.set_song([], None)
    scheduler.flush()
    assert "fret" not in vm.available_views
    assert vm.active_view == "name"


def test_persisted_unavailable_view_falls_back_on_construction():
    renderers = [NameCardRenderer(), FingeringRenderer()]
    config = FakeConfig(chord_sheet_view="fret")  # no song yet -> fret unavailable
    vm, _, _ = make_vm(renderers=renderers, config=config)
    assert vm.active_view == "name"


# --------------------------------------------------------------------------
# Audition
# --------------------------------------------------------------------------


def test_audition_plays_exact_midi_notes():
    song = RenderedSong(chords=[make_chord("C", midi_notes=(48, 60, 64, 67))])
    vm, audio, scheduler = make_vm(rendered=song)
    vm.set_song([], None)
    scheduler.flush()

    vm.audition(0)
    assert audio.auditions == [[48, 60, 64, 67]]


def test_audition_ignores_rest_and_out_of_range():
    song = RenderedSong(chords=[make_chord("NC", is_rest=True)])
    vm, audio, scheduler = make_vm(rendered=song)
    vm.set_song([], None)
    scheduler.flush()

    vm.audition(0)   # rest -> no notes
    vm.audition(5)   # out of range
    assert audio.auditions == []


# --------------------------------------------------------------------------
# Visibility persistence
# --------------------------------------------------------------------------


def test_visibility_toggle_persists_to_config():
    config = FakeConfig(chord_sheet_visible=False)
    vm, _, _ = make_vm(config=config)
    assert vm.visible is False

    vm.toggle_visible()
    assert vm.visible is True
    assert config.get("chord_sheet_visible") is True


def test_set_active_view_persists_and_ignores_unavailable():
    config = FakeConfig()
    vm, _, _ = make_vm(config=config)
    vm.set_active_view("does-not-exist")
    assert vm.active_view == "name"  # unchanged
    vm.set_active_view("name")
    assert config.get("chord_sheet_view") == "name"


def test_set_height_persists():
    config = FakeConfig()
    vm, _, _ = make_vm(config=config)
    vm.set_height(240)
    assert vm.height == 240
    assert config.get("chord_sheet_height") == 240


# --------------------------------------------------------------------------
# scroll_target math
# --------------------------------------------------------------------------

st = ChordSheetViewModel.scroll_target


def test_scroll_no_move_inside_comfortable_band():
    # playhead at 50% of viewport, current scroll 0 -> inside [25%, 70%].
    assert st(playhead_x=500, viewport_width=1000, current_scroll_x=0, content_width=5000) is None


def test_scroll_snaps_to_25_percent_past_70_percent():
    # playhead at 80% of viewport -> past 70%, snap so it lands at 25%.
    target = st(playhead_x=800, viewport_width=1000, current_scroll_x=0, content_width=5000)
    assert target == pytest.approx(800 - 0.25 * 1000)  # 550


def test_scroll_snaps_on_backward_jump():
    # Loop restart: playhead jumps back behind the 25% line -> snap to 25%.
    target = st(playhead_x=1000, viewport_width=1000, current_scroll_x=1500, content_width=5000)
    # relative = 1000 - 1500 = -500 (< 25%) -> snap to place at 25%.
    assert target == pytest.approx(1000 - 0.25 * 1000)  # 750


def test_scroll_clamps_at_song_end():
    # Near the end: desired scroll would exceed content_width - viewport.
    target = st(playhead_x=4900, viewport_width=1000, current_scroll_x=0, content_width=5000)
    assert target == pytest.approx(4000)  # clamped to content_width - viewport


def test_scroll_clamps_at_start_no_negative():
    # At the very start the snap target would be negative -> clamp to 0 == current -> None.
    assert st(playhead_x=0, viewport_width=1000, current_scroll_x=0, content_width=5000) is None


def test_scroll_none_when_content_fits_viewport():
    assert st(playhead_x=100, viewport_width=1000, current_scroll_x=0, content_width=500) is None


def test_scroll_zero_viewport_returns_none():
    assert st(playhead_x=100, viewport_width=0, current_scroll_x=0, content_width=500) is None
