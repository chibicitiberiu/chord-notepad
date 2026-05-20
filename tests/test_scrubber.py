"""Tests for the Scrubber widget."""

import os
import tkinter as tk

import pytest


def _has_display() -> bool:
    return os.environ.get("DISPLAY") or os.name == "nt"


@pytest.fixture
def root():
    if not _has_display():
        pytest.skip("No display available for tkinter tests")
    root = tk.Tk()
    root.withdraw()
    yield root
    root.destroy()


def _make_scrubber(root, **overrides):
    from ui.scrubber import Scrubber

    kwargs = dict(
        value=100,
        min_value=0,
        max_value=200,
        step=1,
        on_change=lambda _v: None,
    )
    kwargs.update(overrides)
    return Scrubber(root, **kwargs)


class TestClampAndSnap:
    def test_initial_value_is_clamped_high(self, root):
        s = _make_scrubber(root, value=999, min_value=0, max_value=100)
        assert s.value == 100

    def test_initial_value_is_clamped_low(self, root):
        s = _make_scrubber(root, value=-50, min_value=0, max_value=100)
        assert s.value == 0

    def test_initial_value_snaps_to_step(self, root):
        s = _make_scrubber(root, value=37, min_value=0, max_value=100, step=10)
        assert s.value == 40

    def test_snap_relative_to_min(self, root):
        # Snap is computed from min; 12.5 + 12.5*N grid
        s = _make_scrubber(root, value=50, min_value=12.5, max_value=400, step=12.5)
        assert s.value == 50  # 12.5 + 3*12.5 = 50

    def test_snap_handles_half_steps(self, root):
        # 30 should snap to nearest of 25 or 37.5 with step=12.5 starting from 12.5
        s = _make_scrubber(root, value=30, min_value=12.5, max_value=400, step=12.5)
        assert s.value == 25.0


class TestMagneticSnap:
    def test_typed_value_near_snap_point_snaps(self, root):
        s = _make_scrubber(
            root, value=100, min_value=12.5, max_value=400,
            step=12.5, snap_tolerance=3,
        )
        s._enter_edit_mode()
        s._entry_var.set("26")  # close to 25
        s._commit_edit()
        assert s.value == 25.0

    def test_typed_value_outside_tolerance_preserved(self, root):
        s = _make_scrubber(
            root, value=100, min_value=12.5, max_value=400,
            step=12.5, snap_tolerance=3,
        )
        s._enter_edit_mode()
        s._entry_var.set("30")  # 5 from 25, 7.5 from 37.5
        s._commit_edit()
        assert s.value == 30.0

    def test_drag_step_finer_than_snap_step(self, root):
        # With drag_step=1, step=12.5, snap_tolerance=2, snap points are
        # 12.5, 25, 37.5, ... — magnetic zones are [23..27], [35.5..39.5], ...
        s = _make_scrubber(
            root, value=30, min_value=12.5, max_value=400,
            step=12.5, drag_step=1, snap_tolerance=2,
        )
        s._step_by(-1)
        assert s.value == 29  # |29-25|=4, outside tolerance
        s._step_by(-1)
        assert s.value == 28  # |28-25|=3, outside tolerance
        s._step_by(-1)
        assert s.value == 25  # |27-25|=2, inside tolerance, snaps to 25


class TestSetValue:
    def test_set_value_clamps(self, root):
        s = _make_scrubber(root, value=50, min_value=0, max_value=100)
        s.set_value(9999)
        assert s.value == 100
        s.set_value(-1)
        assert s.value == 0

    def test_set_value_does_not_notify_by_default(self, root):
        calls = []
        s = _make_scrubber(root, value=50, on_change=calls.append)
        s.set_value(75)
        assert calls == []

    def test_set_value_notifies_when_asked(self, root):
        calls = []
        s = _make_scrubber(root, value=50, on_change=calls.append)
        s.set_value(75, notify=True)
        assert calls == [75]

    def test_set_value_same_value_is_noop(self, root):
        calls = []
        s = _make_scrubber(root, value=50, on_change=calls.append)
        s.set_value(50, notify=True)
        assert calls == []


class TestStepBy:
    def test_step_by_one(self, root):
        calls = []
        s = _make_scrubber(root, value=50, step=5, on_change=calls.append)
        s._step_by(1)
        assert s.value == 55
        assert calls == [55]

    def test_step_by_clamps_at_max(self, root):
        s = _make_scrubber(root, value=100, max_value=100, step=5)
        s._step_by(1)
        assert s.value == 100

    def test_step_by_disabled_when_readonly(self, root):
        s = _make_scrubber(root, value=50, step=5)
        s.set_readonly(True)
        s._step_by(1)
        assert s.value == 50


class TestReset:
    def test_middle_click_resets_to_default(self, root):
        calls = []
        s = _make_scrubber(
            root, value=50, min_value=0, max_value=200, step=1,
            default_value=120, on_change=calls.append,
        )
        s.set_value(75)
        # synthesize middle-click
        s._on_reset_click(tk.Event())
        assert s.value == 120
        assert calls == [120]

    def test_reset_noop_when_already_at_default(self, root):
        calls = []
        s = _make_scrubber(
            root, value=120, default_value=120, on_change=calls.append,
        )
        s._on_reset_click(tk.Event())
        assert s.value == 120
        assert calls == []

    def test_reset_noop_when_no_default(self, root):
        calls = []
        s = _make_scrubber(root, value=50, on_change=calls.append)
        s._on_reset_click(tk.Event())
        assert s.value == 50
        assert calls == []

    def test_reset_disabled_when_readonly(self, root):
        s = _make_scrubber(root, value=50, default_value=100)
        s.set_readonly(True)
        s._on_reset_click(tk.Event())
        assert s.value == 50


class TestReadonly:
    def test_readonly_disables_underline(self, root):
        s = _make_scrubber(root, value=50)
        assert s._idle_font.cget("underline") in (1, True)
        s.set_readonly(True)
        assert s._idle_font.cget("underline") in (0, False)

    def test_set_display_text_overrides_label_in_readonly(self, root):
        s = _make_scrubber(root, value=50)
        s.set_readonly(True)
        s.set_display_text("LIVE")
        assert s._label.cget("text") == "LIVE"
        # underlying value unchanged
        assert s.value == 50

    def test_exiting_readonly_restores_label(self, root):
        s = _make_scrubber(root, value=50)
        s.set_readonly(True)
        s.set_display_text("LIVE")
        s.set_readonly(False)
        assert s._label.cget("text") == "50"


class TestFormatterParser:
    def test_custom_formatter(self, root):
        s = _make_scrubber(root, value=50, formatter=lambda v: f"{v}%")
        assert s._label.cget("text") == "50%"

    def test_custom_parser_round_trips_via_edit(self, root):
        calls = []
        s = _make_scrubber(
            root,
            value=50,
            min_value=0,
            max_value=200,
            step=1,
            parser=lambda text: float(text.rstrip("%")),
            on_change=calls.append,
        )
        s._enter_edit_mode()
        s._entry_var.set("75%")
        s._commit_edit()
        assert s.value == 75
        assert calls == [75]

    def test_invalid_input_keeps_previous_value(self, root):
        s = _make_scrubber(root, value=50)
        s._enter_edit_mode()
        s._entry_var.set("not a number")
        s._commit_edit()
        assert s.value == 50
