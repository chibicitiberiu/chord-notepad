"""Shared Settings-window UI infra: hover tooltips and invalid-field styling.

This module has no dependency on any specific dialog or view model. It is
consumed by the Settings window (Voicings page, Options dialog, etc.) to:

* attach a small hover tooltip to a widget (:class:`ToolTip` / :func:`add_tooltip`)
* mark a ttk field widget as invalid with a red visual style
  (:func:`ensure_field_error_styles` / :func:`mark_field`)
"""

import logging
import tkinter as tk
from tkinter import ttk
from typing import Optional

logger = logging.getLogger(__name__)

#: Ttk widget classes that have a matching ``Error.<class>`` style, and the
#: mapping from widget class name to that style name.
_ERROR_STYLE_BY_CLASS = {
    'TEntry': 'Error.TEntry',
    'TSpinbox': 'Error.TSpinbox',
    'TCombobox': 'Error.TCombobox',
}

#: Module-level guard so :func:`ensure_field_error_styles` is idempotent.
_configured = False


class ToolTip:
    """A small hover tooltip attached to a Tkinter widget.

    Shows a borderless :class:`tkinter.Toplevel` containing a label after the
    pointer has hovered over ``widget`` for ``delay_ms`` milliseconds. The tip
    is positioned just below and to the right of the pointer. It hides again
    on ``<Leave>``, on ``<ButtonPress>``, or when the widget is destroyed.

    Re-entering the widget while the tip is pending/showing does not stack
    multiple tooltip windows: any pending timer is cancelled on ``<Leave>``
    and a fresh one is scheduled on the next ``<Enter>``.
    """

    def __init__(self, widget: tk.Widget, text: str, delay_ms: int = 500, wraplength: int = 320) -> None:
        """Create and arm a tooltip for ``widget``.

        Args:
            widget: The widget to attach the tooltip to.
            text: The text to display in the tooltip.
            delay_ms: Hover delay in milliseconds before the tip appears.
            wraplength: Maximum pixel width before the tip text wraps.
        """
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self.wraplength = wraplength

        self._after_id: Optional[str] = None
        self._tip_window: Optional[tk.Toplevel] = None

        self.widget.bind('<Enter>', self._on_enter, add='+')
        self.widget.bind('<Leave>', self._on_leave, add='+')
        self.widget.bind('<ButtonPress>', self._on_leave, add='+')
        self.widget.bind('<Destroy>', self._on_destroy, add='+')

    def set_text(self, text: str) -> None:
        """Update the tooltip text.

        If the tip is currently visible, its label is updated immediately.

        Args:
            text: The new tooltip text.
        """
        self.text = text
        if self._tip_window is not None and self._tip_window.winfo_exists():
            for child in self._tip_window.winfo_children():
                child.configure(text=text)

    def hide(self) -> None:
        """Hide the tooltip and cancel any pending show timer."""
        self._cancel_pending()

        tip_window = self._tip_window
        self._tip_window = None
        if tip_window is not None and tip_window.winfo_exists():
            tip_window.destroy()

    def _on_enter(self, _event: Optional[tk.Event] = None) -> None:
        """Schedule the tooltip to show after ``delay_ms``."""
        self._cancel_pending()
        if not self.widget.winfo_exists():
            return
        self._after_id = self.widget.after(self.delay_ms, self._show)

    def _on_leave(self, _event: Optional[tk.Event] = None) -> None:
        """Hide the tooltip (and cancel any pending timer)."""
        self.hide()

    def _on_destroy(self, _event: Optional[tk.Event] = None) -> None:
        """Clean up when the owning widget is destroyed."""
        self._cancel_pending()
        self._tip_window = None

    def _cancel_pending(self) -> None:
        """Cancel the pending ``after`` timer, if any."""
        if self._after_id is not None:
            try:
                if self.widget.winfo_exists():
                    self.widget.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None

    def _show(self) -> None:
        """Create and display the tooltip Toplevel below-right of the pointer."""
        self._after_id = None

        if self._tip_window is not None:
            return
        if not self.widget.winfo_exists():
            return

        try:
            x = self.widget.winfo_pointerx() + 12
            y = self.widget.winfo_pointery() + 16

            tip_window = tk.Toplevel(self.widget)
            tip_window.wm_overrideredirect(True)
            tip_window.wm_geometry(f'+{x}+{y}')

            label = tk.Label(
                tip_window,
                text=self.text,
                justify=tk.LEFT,
                background='#ffffe0',
                relief=tk.SOLID,
                borderwidth=1,
                wraplength=self.wraplength,
                padx=4,
                pady=4,
            )
            label.pack()

            self._tip_window = tip_window
        except tk.TclError:
            logger.debug("Could not show tooltip; widget or display unavailable", exc_info=True)
            self._tip_window = None


def add_tooltip(widget: tk.Widget, text: str, **kwargs) -> ToolTip:
    """Attach a :class:`ToolTip` to ``widget`` and return it.

    Convenience wrapper around ``ToolTip(widget, text, **kwargs)`` for callers
    that don't need to hold on to any other reference style.

    Args:
        widget: The widget to attach the tooltip to.
        text: The text to display in the tooltip.
        **kwargs: Extra keyword arguments forwarded to :class:`ToolTip`
            (``delay_ms``, ``wraplength``).

    Returns:
        The created :class:`ToolTip` instance.
    """
    return ToolTip(widget, text, **kwargs)


def ensure_field_error_styles(style: Optional[ttk.Style] = None) -> None:
    """Create the ``Error.TEntry`` / ``Error.TSpinbox`` / ``Error.TCombobox`` styles.

    Idempotent: safe to call many times (e.g. once per dialog construction);
    subsequent calls are no-ops. The styles derive from the base ttk styles
    and paint the field's ``fieldbackground`` red, mapping the same red across
    ``focus``, ``readonly`` and ``active`` states since many themes otherwise
    reset ``fieldbackground`` in those states. ``foreground`` is also set to a
    dark red as a secondary signal, since some native themes ignore
    ``fieldbackground`` entirely.

    Args:
        style: The :class:`ttk.Style` to configure. Defaults to a new
            ``ttk.Style()`` bound to the current Tk interpreter.
    """
    global _configured
    if _configured:
        return

    if style is None:
        style = ttk.Style()

    error_bg = '#ffdddd'
    error_fg = '#8b0000'

    for base_class, error_style in _ERROR_STYLE_BY_CLASS.items():
        style.configure(
            error_style,
            fieldbackground=error_bg,
            foreground=error_fg,
        )
        style.map(
            error_style,
            fieldbackground=[
                ('readonly', error_bg),
                ('disabled', error_bg),
                ('focus', error_bg),
                ('active', error_bg),
                ('!disabled', error_bg),
            ],
            foreground=[
                ('readonly', error_fg),
                ('disabled', error_fg),
                ('focus', error_fg),
                ('active', error_fg),
                ('!disabled', error_fg),
            ],
            bordercolor=[
                ('!disabled', 'red'),
                ('focus', 'red'),
            ],
        )

    _configured = True


def mark_field(widget: tk.Widget, error: bool, base_style: str = '') -> None:
    """Toggle a ttk field widget between its error style and its base style.

    Maps the widget's ttk class name (``TEntry`` / ``TSpinbox`` / ``TCombobox``)
    to the matching ``Error.<class>`` style created by
    :func:`ensure_field_error_styles`. If the widget's class has no known error
    style, this is a no-op.

    Args:
        widget: The ttk widget to mark or unmark.
        error: ``True`` to apply the red error style, ``False`` to restore
            ``base_style``.
        base_style: The style to restore when ``error`` is ``False``. Defaults
            to ``''`` (the theme default for the widget's class).
    """
    if not widget.winfo_exists():
        return

    if error:
        widget_class = widget.winfo_class()
        error_style = _ERROR_STYLE_BY_CLASS.get(widget_class)
        if error_style is None:
            return
        widget.configure(style=error_style)
    else:
        widget.configure(style=base_style)
