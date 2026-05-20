"""Scrubber widget: a compact numeric control that looks like underlined text.

Drag horizontally to change the value, click without dragging to type a precise
value. Used in the toolbar where a slider would take too much space.
"""

import tkinter as tk
from tkinter import ttk, font as tkfont
from typing import Callable, Optional


class Scrubber(ttk.Frame):
    """A draggable/typable numeric text control styled like a hyperlink.

    The widget alternates between two modes:
      * idle: shows the formatted value as a label, underlined and link-blue
      * editing: shows a tk.Entry where the user can type a precise value

    Dragging horizontally on the label changes the value. When `snap_tolerance`
    is non-zero, `step` acts as a "magnetic snap" — values aren't restricted to
    snap points, but as you drag near one, the value latches to it. Otherwise
    `step` is a strict grid.
    """

    DRAG_THRESHOLD_PX = 3
    DEFAULT_PIXELS_PER_STEP = 4
    LINK_COLOR = "#1565c0"
    READONLY_COLOR = "#888888"

    def __init__(
        self,
        parent: tk.Widget,
        value: float,
        min_value: float,
        max_value: float,
        step: float = 1.0,
        drag_step: Optional[float] = None,
        snap_tolerance: float = 0.0,
        formatter: Optional[Callable[[float], str]] = None,
        parser: Optional[Callable[[str], float]] = None,
        on_change: Optional[Callable[[float], None]] = None,
        pixels_per_step: int = DEFAULT_PIXELS_PER_STEP,
        width: int = 7,
        default_value: Optional[float] = None,
    ) -> None:
        super().__init__(parent)

        self._min = min_value
        self._max = max_value
        self._step = step
        self._drag_step = drag_step if drag_step is not None else step
        self._snap_tolerance = snap_tolerance
        self._formatter = formatter or (lambda v: f"{v:g}")
        self._parser = parser or float
        self._on_change = on_change
        self._pixels_per_step = max(1, pixels_per_step)
        self._width = width
        self._readonly = False

        self._value = self._clamp_and_snap(value)
        self._default_value: Optional[float] = (
            self._clamp_and_snap(default_value) if default_value is not None else None
        )

        self._drag_start_x: Optional[int] = None
        self._drag_start_value: Optional[float] = None
        self._dragged = False

        self._build()
        self._refresh_label()

    def _build(self) -> None:
        base_font = tkfont.nametofont("TkDefaultFont")
        self._idle_font = tkfont.Font(
            family=base_font.cget("family"),
            size=base_font.cget("size"),
            weight="bold",
            underline=True,
        )
        self._label = tk.Label(
            self,
            text="",
            font=self._idle_font,
            fg=self.LINK_COLOR,
            cursor="sb_h_double_arrow",
            width=self._width,
            anchor="e",
            padx=0,
            bd=0,
        )
        self._label.pack(side=tk.LEFT)

        self._label.bind("<ButtonPress-1>", self._on_press)
        self._label.bind("<B1-Motion>", self._on_drag)
        self._label.bind("<ButtonRelease-1>", self._on_release)
        self._label.bind("<Button-2>", self._on_reset_click)
        self._label.bind("<MouseWheel>", self._on_wheel)
        self._label.bind("<Button-4>", lambda _e: self._step_by(1))
        self._label.bind("<Button-5>", lambda _e: self._step_by(-1))

        self._entry_var = tk.StringVar()
        self._entry: Optional[tk.Entry] = None

    def _clamp(self, value: float) -> float:
        if value < self._min:
            return self._min
        if value > self._max:
            return self._max
        return value

    def _snap_to_grid(self, value: float, tolerance: Optional[float] = None) -> float:
        if self._step <= 0:
            return value
        steps = round((value - self._min) / self._step)
        snapped = self._min + steps * self._step
        if snapped > self._max:
            snapped = self._max
        if tolerance is None or tolerance <= 0:
            return snapped
        if abs(snapped - value) <= tolerance:
            return snapped
        return value

    def _clamp_and_snap(self, value: float) -> float:
        """Used for direct value assignment (init, set_value, reset, typed input).

        Honors `snap_tolerance`: strict snap when tolerance == 0, magnetic
        (preserves arbitrary values not near a snap point) when > 0.
        """
        return self._snap_to_grid(self._clamp(value), tolerance=self._snap_tolerance)

    def _quantize_drag(self, value: float) -> float:
        """Apply magnetic snap to a drag-relative value (already at drag_step granularity)."""
        return self._snap_to_grid(self._clamp(value), tolerance=self._snap_tolerance)

    def _refresh_label(self) -> None:
        self._label.config(text=self._formatter(self._value))

    def _on_press(self, event: tk.Event) -> None:
        if self._readonly:
            return
        self._drag_start_x = event.x_root
        self._drag_start_value = self._value
        self._dragged = False

    def _on_drag(self, event: tk.Event) -> None:
        if self._readonly or self._drag_start_x is None:
            return
        dx = event.x_root - self._drag_start_x
        if abs(dx) >= self.DRAG_THRESHOLD_PX:
            self._dragged = True
        if not self._dragged:
            return
        steps = dx // self._pixels_per_step
        raw = self._drag_start_value + steps * self._drag_step
        new_value = self._quantize_drag(raw)
        if new_value != self._value:
            self._value = new_value
            self._refresh_label()
            self._notify()

    def _on_release(self, event: tk.Event) -> None:
        if self._readonly:
            self._drag_start_x = None
            return
        was_drag = self._dragged
        self._drag_start_x = None
        self._drag_start_value = None
        self._dragged = False
        if not was_drag:
            self._enter_edit_mode()

    def _on_wheel(self, event: tk.Event) -> None:
        if self._readonly:
            return
        direction = 1 if event.delta > 0 else -1
        self._step_by(direction)

    def _on_reset_click(self, _event: tk.Event) -> None:
        if self._readonly or self._default_value is None:
            return
        if self._value == self._default_value:
            return
        self._value = self._default_value
        self._refresh_label()
        self._notify()

    def _step_by(self, direction: int) -> None:
        if self._readonly:
            return
        new_value = self._quantize_drag(self._value + direction * self._drag_step)
        if new_value != self._value:
            self._value = new_value
            self._refresh_label()
            self._notify()

    def _enter_edit_mode(self) -> None:
        self._label.pack_forget()
        self._entry_var.set(self._formatter(self._value))
        self._entry = tk.Entry(
            self,
            textvariable=self._entry_var,
            width=self._width,
            justify="center",
        )
        self._entry.pack(side=tk.LEFT)
        self._entry.focus_set()
        self._entry.select_range(0, tk.END)
        self._entry.icursor(tk.END)
        self._entry.bind("<Return>", lambda _e: self._commit_edit())
        self._entry.bind("<KP_Enter>", lambda _e: self._commit_edit())
        self._entry.bind("<Escape>", lambda _e: self._cancel_edit())
        self._entry.bind("<FocusOut>", lambda _e: self._commit_edit())

    def _commit_edit(self) -> None:
        if self._entry is None:
            return
        text = self._entry_var.get().strip()
        try:
            parsed = self._parser(text)
            new_value = self._clamp_and_snap(parsed)
        except (ValueError, TypeError):
            new_value = self._value
        changed = new_value != self._value
        self._value = new_value
        self._exit_edit_mode()
        if changed:
            self._notify()

    def _cancel_edit(self) -> None:
        self._exit_edit_mode()

    def _exit_edit_mode(self) -> None:
        if self._entry is not None:
            self._entry.destroy()
            self._entry = None
        self._refresh_label()
        self._label.pack(side=tk.LEFT)

    def _notify(self) -> None:
        if self._on_change is not None:
            self._on_change(self._value)

    @property
    def value(self) -> float:
        return self._value

    def set_value(self, value: float, notify: bool = False) -> None:
        new_value = self._clamp_and_snap(value)
        if new_value == self._value:
            return
        self._value = new_value
        if self._entry is None:
            self._refresh_label()
        else:
            self._entry_var.set(self._formatter(new_value))
        if notify:
            self._notify()

    def set_display_text(self, text: str) -> None:
        """Override the visible text without changing the underlying value.

        Used to show a live/effective value (e.g. directive-driven BPM) while
        the widget is in readonly mode.
        """
        if self._entry is None:
            self._label.config(text=text)

    def set_readonly(self, readonly: bool) -> None:
        if readonly == self._readonly:
            return
        self._readonly = readonly
        if readonly:
            if self._entry is not None:
                self._cancel_edit()
            self._label.config(cursor="arrow", fg=self.READONLY_COLOR)
            self._idle_font.config(underline=False)
        else:
            self._label.config(cursor="sb_h_double_arrow", fg=self.LINK_COLOR)
            self._idle_font.config(underline=True)
            self._refresh_label()
