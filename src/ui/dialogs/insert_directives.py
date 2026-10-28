"""
Dialogs for inserting directives into the text editor.

The dialogs present an :class:`~session.events.InsertDirectiveRequest`: they
collect the directive's fields and check them with the session's validator
(:mod:`session.directives`) so mistakes are reported while the dialog is
still open. ``result`` is the ``{field: value}`` mapping to answer the
request with, or None if the user cancelled; the session builds and inserts
the directive.
"""

import logging
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Iterable, Optional
from utils.key_helpers import get_key_options
from models.notation import Notation
from session.directives import DirectiveKind, check_directive, loop_label_choices
from session.events import InsertDirectiveRequest

logger = logging.getLogger(__name__)


class BaseInsertDialog(tk.Toplevel):
    """Base class for insert directive dialogs"""

    # The directive kind the dialog collects fields for.
    kind: DirectiveKind

    def __init__(self, parent, title: str, description: str,
                 existing_labels: Iterable[str] = (),
                 notation: Notation = Notation.AMERICAN):
        """Initialize the dialog.

        Args:
            parent: Parent window
            title: Dialog title
            description: Dialog description text
            existing_labels: Labels already in the song (for the checks)
            notation: Notation of the key options (for the checks)
        """
        super().__init__(parent)

        self.existing_labels = set(existing_labels)
        self.notation = Notation(notation)

        self.title(title)
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        # The fields, set when the user clicks Insert
        self.result: Optional[Dict[str, str]] = None

        # Main frame with padding
        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Description label
        desc_label = tk.Label(
            main_frame,
            text=description,
            font=('TkDefaultFont', 9),
            wraplength=400,
            justify=tk.LEFT
        )
        desc_label.pack(pady=(0, 15))

        # Content frame for subclasses to add their widgets
        self.content_frame = ttk.Frame(main_frame)
        self.content_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=(10, 0))

        self.insert_button = ttk.Button(button_frame, text="Insert", command=self._on_insert)
        self.insert_button.pack(side=tk.LEFT, padx=5)

        ttk.Button(button_frame, text="Cancel", command=self._on_cancel).pack(side=tk.LEFT, padx=5)

        # Center the dialog
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

    def _on_insert(self):
        """Handle Insert button click: check the fields, then close with them"""
        if self.validate():
            self.result = self.get_values()
            self.destroy()

    def _on_cancel(self):
        """Handle Cancel button click"""
        self.result = None
        self.destroy()

    def validate(self) -> bool:
        """Check the fields with the session's validator; show what is wrong.

        Returns:
            True if validation passes, False otherwise
        """
        problem = check_directive(self.kind.value, self.get_values(),
                                  existing_labels=self.existing_labels,
                                  notation=self.notation.value)
        if problem is None:
            return True
        messagebox.showerror(problem.title, problem.message, parent=self)
        return False

    def get_values(self) -> Dict[str, str]:
        """The directive's fields as entered - overridden by subclasses.

        Returns:
            ``{field: value}`` (see :mod:`session.directives`)
        """
        return {}


class InsertBpmDialog(BaseInsertDialog):
    """Dialog for inserting a BPM/Tempo change directive"""

    kind = DirectiveKind.BPM

    def __init__(self, parent):
        description = (
            "Starting from this point, the tempo of playback changes to/by the given amount.\n\n"
            "Valid formats:\n"
            "  • 110 - absolute change\n"
            "  • +20 - relative change\n"
            "  • 20% - relative change by percentage\n"
            "  • 2x - multiplier\n"
            "  • reset or original - reset back to initial BPM"
        )
        super().__init__(parent, "Insert BPM/Tempo Change", description)

        # Create input field
        self.entry = ttk.Entry(self.content_frame, font=('TkDefaultFont', 11), width=20)
        self.entry.pack()
        self.entry.focus_set()

        # Bind Enter key to insert
        self.entry.bind('<Return>', lambda e: self._on_insert())

    def get_values(self) -> Dict[str, str]:
        """The BPM field"""
        return {"value": self.entry.get()}


class InsertTimeSignatureDialog(BaseInsertDialog):
    """Dialog for inserting a Time Signature change directive"""

    kind = DirectiveKind.TIME

    def __init__(self, parent):
        description = (
            "Starting from this point, the time signature of playback changes to this value.\n\n"
            "Valid format: 3/4"
        )
        super().__init__(parent, "Insert Time Signature Change", description)

        # Create input field
        input_frame = ttk.Frame(self.content_frame)
        input_frame.pack()

        self.beats_var = tk.IntVar(value=4)
        self.beats_spin = ttk.Spinbox(input_frame, from_=1, to=16,
                                      textvariable=self.beats_var,
                                      width=5)
        self.beats_spin.pack(side=tk.LEFT, padx=5)

        ttk.Label(input_frame, text="/", font=('TkDefaultFont', 12)).pack(side=tk.LEFT)

        self.unit_var = tk.IntVar(value=4)
        self.unit_spin = ttk.Spinbox(input_frame, values=(1, 2, 4, 8, 16),
                                     textvariable=self.unit_var,
                                     width=5)
        self.unit_spin.pack(side=tk.LEFT, padx=5)

        self.beats_spin.focus_set()

        # Bind Enter key to insert
        self.beats_spin.bind('<Return>', lambda e: self._on_insert())
        self.unit_spin.bind('<Return>', lambda e: self._on_insert())

    def get_values(self) -> Dict[str, str]:
        """The beats and unit fields"""
        return {"beats": self.beats_spin.get(), "unit": self.unit_spin.get()}


class InsertKeyDialog(BaseInsertDialog):
    """Dialog for inserting a Key change directive"""

    kind = DirectiveKind.KEY

    def __init__(self, parent, notation: Notation = Notation.AMERICAN):
        description = (
            "Starting from this point, the key in which relative chords play will change.\n\n"
            "Select the new key signature from the list below."
        )
        super().__init__(parent, "Insert Key Change", description, notation=notation)

        # Get keys based on current notation
        keys = get_key_options(notation)

        self.key_var = tk.StringVar(value=keys[0])  # Default to first key (C or Do)
        self.key_combo = ttk.Combobox(self.content_frame, textvariable=self.key_var,
                                      values=keys, state='readonly', width=10)
        self.key_combo.pack()
        self.key_combo.focus_set()

        # Bind Enter key to insert
        self.key_combo.bind('<Return>', lambda e: self._on_insert())

    def get_values(self) -> Dict[str, str]:
        """The key field"""
        return {"key": self.key_var.get()}


class InsertLabelDialog(BaseInsertDialog):
    """Dialog for inserting a Label directive"""

    kind = DirectiveKind.LABEL

    def __init__(self, parent, existing_labels=None):
        description = (
            "Inserts a label which can be used for making loops.\n\n"
            "Enter a unique label name (letters, numbers, and underscores only)."
        )
        super().__init__(parent, "Insert Label", description,
                         existing_labels=existing_labels or ())

        # Create input field
        self.entry = ttk.Entry(self.content_frame, font=('TkDefaultFont', 11), width=20)
        self.entry.pack()
        self.entry.focus_set()

        # Bind Enter key to insert
        self.entry.bind('<Return>', lambda e: self._on_insert())

    def get_values(self) -> Dict[str, str]:
        """The label field"""
        return {"label": self.entry.get()}


class InsertLoopDialog(BaseInsertDialog):
    """Dialog for inserting a Loop directive"""

    kind = DirectiveKind.LOOP

    def __init__(self, parent, existing_labels=None):
        description = (
            "Placed at the end of a loop.\n\n"
            "To set the beginning of a loop, use a label directive (Insert > Label).\n"
            "Use '@start' as a special keyword for the beginning of the song."
        )
        super().__init__(parent, "Insert Loop", description,
                         existing_labels=existing_labels or ())

        # Create input fields
        input_frame = ttk.Frame(self.content_frame)
        input_frame.pack()

        ttk.Label(input_frame, text="Label:").pack(side=tk.LEFT, padx=(0, 5))

        # The song's start, then the labels
        label_options = list(loop_label_choices(self.existing_labels))

        self.label_var = tk.StringVar(value=label_options[0])
        self.label_combo = ttk.Combobox(input_frame, textvariable=self.label_var,
                                        values=label_options, state='readonly', width=15)
        self.label_combo.pack(side=tk.LEFT, padx=5)

        ttk.Label(input_frame, text="Count:").pack(side=tk.LEFT, padx=(10, 5))

        self.count_var = tk.IntVar(value=2)
        self.count_spin = ttk.Spinbox(input_frame, from_=1, to=100,
                                      textvariable=self.count_var,
                                      width=5)
        self.count_spin.pack(side=tk.LEFT, padx=5)

        self.label_combo.focus_set()

        # Bind Enter key to insert
        self.label_combo.bind('<Return>', lambda e: self._on_insert())
        self.count_spin.bind('<Return>', lambda e: self._on_insert())

    def get_values(self) -> Dict[str, str]:
        """The label and count fields"""
        return {"label": self.label_var.get(), "count": self.count_spin.get()}


def dialog_for_request(parent, request: InsertDirectiveRequest) -> BaseInsertDialog:
    """Open the dialog that presents ``request`` (not waited for).

    Args:
        parent: Parent window
        request: What the session asks for

    Returns:
        The open dialog; its ``result`` answers the request once it closes
    """
    kind = DirectiveKind(request.kind)
    if kind is DirectiveKind.BPM:
        return InsertBpmDialog(parent)
    if kind is DirectiveKind.TIME:
        return InsertTimeSignatureDialog(parent)
    if kind is DirectiveKind.KEY:
        return InsertKeyDialog(parent, notation=Notation(request.notation))
    if kind is DirectiveKind.LABEL:
        return InsertLabelDialog(parent, existing_labels=request.existing_labels)
    return InsertLoopDialog(parent, existing_labels=request.existing_labels)
