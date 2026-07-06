"""Dialog for choosing which fretboard voicing to optimize a capo for."""

import logging
import tkinter as tk
from tkinter import ttk
from typing import List, Optional

logger = logging.getLogger(__name__)


class CapoDialog(tk.Toplevel):
    """Modal dialog to pick a voicing to optimize a capo suggestion for.

    The dialog only *selects* a voicing: after OK, ``result`` holds the chosen
    voicing display name (a value from ``voicing_names``); after Cancel it is
    ``None``. It does not compute a capo or call any advisor -- the caller is
    expected to resolve the returned name to a voicing and run the suggestion.
    """

    def __init__(self, parent, voicing_names: List[str], default_name: str):
        """Initialize the dialog.

        Args:
            parent: Parent window.
            voicing_names: Display names of the available fretboard voicings.
            default_name: Voicing name to preselect in the combobox.
        """
        super().__init__(parent)

        self.title("Suggest Capo")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        self.result: Optional[str] = None

        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        desc = (
            "Suggest a capo position for this song.\n\n"
            "Choose the fretboard voicing the suggestion should optimize for; "
            "the recommended capo makes those shapes easiest to play."
        )
        ttk.Label(
            main_frame, text=desc, font=('TkDefaultFont', 9),
            wraplength=320, justify=tk.LEFT
        ).pack(pady=(0, 15))

        row = ttk.Frame(main_frame)
        row.pack()
        ttk.Label(row, text="Voicing:").pack(side=tk.LEFT, padx=(0, 8))

        self.voicing_var = tk.StringVar(value=default_name)
        self.combo = ttk.Combobox(
            row, textvariable=self.voicing_var, values=list(voicing_names),
            state='readonly', width=20
        )
        self.combo.pack(side=tk.LEFT)
        self.combo.focus_set()
        self.combo.bind('<Return>', lambda e: self._on_ok())

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=(18, 0))
        ttk.Button(button_frame, text="OK", command=self._on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self._on_cancel).pack(side=tk.LEFT, padx=5)

        self.bind('<Escape>', lambda e: self._on_cancel())
        self.bind('<Return>', lambda e: self._on_ok())

        # Center over the parent.
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

    def _on_ok(self) -> None:
        self.result = self.voicing_var.get()
        self.destroy()

    def _on_cancel(self) -> None:
        self.result = None
        self.destroy()
