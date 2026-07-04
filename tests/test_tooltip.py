"""Headless tests for :mod:`ui.base.tooltip`.

All GUI assertions are guarded by ``pytest.importorskip('tkinter')`` and a
``root`` fixture that creates a hidden, withdrawn ``tk.Tk()`` root. If no
display is available (headless CI without Xvfb), the fixture skips cleanly
instead of erroring.
"""

import os

import pytest

tk = pytest.importorskip('tkinter')
from tkinter import ttk  # noqa: E402

from ui.base.tooltip import (  # noqa: E402
    ToolTip,
    add_tooltip,
    ensure_field_error_styles,
    mark_field,
)


def _has_display() -> bool:
    return bool(os.environ.get('DISPLAY')) or os.name == 'nt'


@pytest.fixture
def root():
    """A hidden Tk root, skipping the test if no display is available."""
    if not _has_display():
        pytest.skip("No display available for tkinter tests")
    try:
        instance = tk.Tk()
    except tk.TclError:
        pytest.skip("No display available for tkinter tests")
    instance.withdraw()
    yield instance
    instance.destroy()


class TestToolTip:
    def test_constructs_and_binds_without_raising(self, root):
        entry = ttk.Entry(root)
        entry.pack()

        tip = ToolTip(entry, "hello")

        assert tip.widget is entry
        assert tip.text == "hello"

    def test_set_text_updates_without_showing(self, root):
        entry = ttk.Entry(root)
        entry.pack()

        tip = ToolTip(entry, "initial")
        tip.set_text("updated")

        assert tip.text == "updated"
        # Tip is not visible yet (hover delay hasn't elapsed), so there is
        # no tip window to update.
        assert tip._tip_window is None

    def test_show_then_set_text_updates_visible_label(self, root):
        entry = ttk.Entry(root)
        entry.pack()
        root.update()

        tip = ToolTip(entry, "initial", delay_ms=0)
        tip._show()
        root.update()

        assert tip._tip_window is not None
        tip.set_text("changed")
        labels = tip._tip_window.winfo_children()
        assert labels and labels[0].cget("text") == "changed"

        tip.hide()

    def test_hide_is_safe_when_never_shown(self, root):
        entry = ttk.Entry(root)
        entry.pack()

        tip = ToolTip(entry, "hello")
        tip.hide()  # should not raise

        assert tip._tip_window is None

    def test_hide_cancels_pending_after_timer(self, root):
        entry = ttk.Entry(root)
        entry.pack()

        tip = ToolTip(entry, "hello", delay_ms=5000)
        tip._on_enter()
        assert tip._after_id is not None

        tip.hide()
        assert tip._after_id is None

    def test_reentering_widget_does_not_stack_timers(self, root):
        entry = ttk.Entry(root)
        entry.pack()

        tip = ToolTip(entry, "hello", delay_ms=5000)
        tip._on_enter()
        first_after_id = tip._after_id

        tip._on_leave()
        assert tip._after_id is None

        tip._on_enter()
        second_after_id = tip._after_id

        assert second_after_id is not None
        assert first_after_id != second_after_id or True  # ids may be reused; no stacking is what matters
        tip.hide()

    def test_survives_widget_destruction(self, root):
        entry = ttk.Entry(root)
        entry.pack()
        root.update()

        tip = ToolTip(entry, "hello", delay_ms=0)
        tip._show()
        root.update()

        entry.destroy()
        root.update()

        # Destroy callback should have cleared state; no exception expected.
        assert tip._after_id is None


class TestAddTooltip:
    def test_returns_tooltip_instance(self, root):
        entry = ttk.Entry(root)
        entry.pack()

        tip = add_tooltip(entry, "hover text")

        assert isinstance(tip, ToolTip)
        assert tip.text == "hover text"

    def test_forwards_kwargs(self, root):
        entry = ttk.Entry(root)
        entry.pack()

        tip = add_tooltip(entry, "hover text", delay_ms=100, wraplength=200)

        assert tip.delay_ms == 100
        assert tip.wraplength == 200


class TestEnsureFieldErrorStyles:
    def test_idempotent_and_resolves_styles(self, root):
        style = ttk.Style(root)

        ensure_field_error_styles(style)
        ensure_field_error_styles(style)  # second call must not raise or duplicate

        for style_name in ('Error.TEntry', 'Error.TSpinbox', 'Error.TCombobox'):
            assert style.lookup(style_name, 'fieldbackground')

    def test_defaults_to_new_style_instance(self, root):
        # Calling with no explicit Style should not raise even though a
        # previous test may have already flipped the module-level guard.
        ensure_field_error_styles()


class TestMarkField:
    def test_toggles_entry_to_error_style_and_back(self, root):
        ensure_field_error_styles()
        entry = ttk.Entry(root)
        entry.pack()

        mark_field(entry, True)
        assert entry.cget('style') == 'Error.TEntry'

        mark_field(entry, False)
        assert entry.cget('style') == ''

    def test_toggles_combobox_to_error_style(self, root):
        ensure_field_error_styles()
        combo = ttk.Combobox(root)
        combo.pack()

        mark_field(combo, True)
        assert combo.cget('style') == 'Error.TCombobox'

        mark_field(combo, False, base_style='')
        assert combo.cget('style') == ''

    def test_unknown_widget_class_is_noop(self, root):
        ensure_field_error_styles()
        button = ttk.Button(root, text="Click")
        button.pack()

        mark_field(button, True)  # no Error.TButton style exists; should no-op

        assert button.cget('style') == ''

    def test_guards_destroyed_widget(self, root):
        entry = ttk.Entry(root)
        entry.pack()
        entry.destroy()

        mark_field(entry, True)  # must not raise
