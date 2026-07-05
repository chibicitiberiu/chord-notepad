"""Dialog for transposing chords in the document."""

import logging
import tkinter as tk
from tkinter import ttk
from typing import Optional

logger = logging.getLogger(__name__)


class TransposeDialog(tk.Toplevel):
    """Modal dialog to pick a transposition amount in semitones.

    ``result`` is the chosen number of semitones (an int in -11..+11) after
    OK, or ``None`` if the user cancelled.
    """

    def __init__(self, parent, has_selection: bool = False):
        """Initialize the dialog.

        Args:
            parent: Parent window.
            has_selection: Whether a text selection is active (controls whether
                the transpose applies to the selection or the whole song).
        """
        super().__init__(parent)

        self.title("Transpose")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        self.result: Optional[int] = None
        self._has_selection = has_selection

        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        scope_text = (
            "Transpose selection" if has_selection else "Transpose whole song"
        )
        desc = (
            f"{scope_text}.\n\n"
            "Shift every chord by the chosen number of semitones "
            "(positive = up, negative = down)."
        )
        ttk.Label(
            main_frame, text=desc, font=('TkDefaultFont', 9),
            wraplength=320, justify=tk.LEFT
        ).pack(pady=(0, 15))

        row = ttk.Frame(main_frame)
        row.pack()
        ttk.Label(row, text="Semitones:").pack(side=tk.LEFT, padx=(0, 8))

        self.semitones_var = tk.IntVar(value=0)
        self.spin = ttk.Spinbox(
            row, from_=-11, to=11, textvariable=self.semitones_var, width=5
        )
        self.spin.pack(side=tk.LEFT)
        self.spin.focus_set()
        self.spin.bind('<Return>', lambda e: self._on_ok())

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=(18, 0))
        ttk.Button(button_frame, text="OK", command=self._on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self._on_cancel).pack(side=tk.LEFT, padx=5)

        self.bind('<Escape>', lambda e: self._on_cancel())

        # Center over the parent.
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

    def _on_ok(self) -> None:
        try:
            value = int(self.semitones_var.get())
        except (tk.TclError, ValueError):
            value = 0
        value = max(-11, min(11, value))
        self.result = value
        self.destroy()

    def _on_cancel(self) -> None:
        self.result = None
        self.destroy()
