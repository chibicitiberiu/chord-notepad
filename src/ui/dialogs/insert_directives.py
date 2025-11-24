"""
Dialogs for inserting directives into the text editor
"""

import logging
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Callable
import re
from utils.key_helpers import get_key_options
from models.notation import Notation

logger = logging.getLogger(__name__)


class BaseInsertDialog(tk.Toplevel):
    """Base class for insert directive dialogs"""

    def __init__(self, parent, title: str, description: str):
        """Initialize the dialog.

        Args:
            parent: Parent window
            title: Dialog title
            description: Dialog description text
        """
        super().__init__(parent)

        self.title(title)
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        # Result will be set when user clicks Insert
        self.result = None

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
        """Handle Insert button click - to be overridden by subclasses"""
        if self.validate():
            self.result = self.get_directive_text()
            self.destroy()

    def _on_cancel(self):
        """Handle Cancel button click"""
        self.result = None
        self.destroy()

    def validate(self) -> bool:
        """Validate the input - to be overridden by subclasses.

        Returns:
            True if validation passes, False otherwise
        """
        return True

    def get_directive_text(self) -> str:
        """Get the directive text to insert - to be overridden by subclasses.

        Returns:
            Directive text string
        """
        return ""


class InsertBpmDialog(BaseInsertDialog):
    """Dialog for inserting a BPM/Tempo change directive"""

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

    def validate(self) -> bool:
        """Validate BPM input"""
        value = self.entry.get().strip()

        if not value:
            messagebox.showerror("Invalid Input", "Please enter a BPM value.", parent=self)
            return False

        # Check for reset keywords
        if value.lower() in ('reset', 'original'):
            return True

        # Check for percentage
        if value.endswith('%'):
            try:
                float(value[:-1])
                return True
            except ValueError:
                messagebox.showerror("Invalid Input", "Invalid percentage value.", parent=self)
                return False

        # Check for multiplier
        if value.endswith('x'):
            try:
                float(value[:-1])
                return True
            except ValueError:
                messagebox.showerror("Invalid Input", "Invalid multiplier value.", parent=self)
                return False

        # Check for relative adjustment
        if value.startswith(('+', '-')):
            try:
                int(value)
                return True
            except ValueError:
                messagebox.showerror("Invalid Input", "Invalid relative BPM value.", parent=self)
                return False

        # Check for absolute BPM value
        try:
            bpm = int(value)
            if bpm < 20 or bpm > 300:
                messagebox.showerror("Invalid Input", "BPM must be between 20 and 300.", parent=self)
                return False
            return True
        except ValueError:
            messagebox.showerror("Invalid Input", "Invalid BPM value.", parent=self)
            return False

    def get_directive_text(self) -> str:
        """Get the BPM directive text"""
        value = self.entry.get().strip()
        return f"{{bpm: {value}}}"


class InsertTimeSignatureDialog(BaseInsertDialog):
    """Dialog for inserting a Time Signature change directive"""

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

    def validate(self) -> bool:
        """Validate time signature input"""
        beats = self.beats_var.get()
        unit = self.unit_var.get()

        if beats < 1 or beats > 16:
            messagebox.showerror("Invalid Input", "Beats must be between 1 and 16.", parent=self)
            return False

        if unit not in (1, 2, 4, 8, 16):
            messagebox.showerror("Invalid Input", "Beat unit must be 1, 2, 4, 8, or 16.", parent=self)
            return False

        return True

    def get_directive_text(self) -> str:
        """Get the time signature directive text"""
        beats = self.beats_var.get()
        unit = self.unit_var.get()
        return f"{{time: {beats}/{unit}}}"


class InsertKeyDialog(BaseInsertDialog):
    """Dialog for inserting a Key change directive"""

    def __init__(self, parent, notation: Notation = Notation.AMERICAN):
        description = (
            "Starting from this point, the key in which relative chords play will change.\n\n"
            "Select the new key signature from the list below."
        )
        super().__init__(parent, "Insert Key Change", description)

        # Get keys based on current notation
        keys = get_key_options(notation)

        self.key_var = tk.StringVar(value=keys[0])  # Default to first key (C or Do)
        self.key_combo = ttk.Combobox(self.content_frame, textvariable=self.key_var,
                                      values=keys, state='readonly', width=10)
        self.key_combo.pack()
        self.key_combo.focus_set()

        # Bind Enter key to insert
        self.key_combo.bind('<Return>', lambda e: self._on_insert())

    def get_directive_text(self) -> str:
        """Get the key directive text"""
        key = self.key_var.get()
        return f"{{key: {key}}}"


class InsertLabelDialog(BaseInsertDialog):
    """Dialog for inserting a Label directive"""

    def __init__(self, parent, existing_labels=None):
        description = (
            "Inserts a label which can be used for making loops.\n\n"
            "Enter a unique label name (letters, numbers, and underscores only)."
        )
        super().__init__(parent, "Insert Label", description)

        self.existing_labels = existing_labels or set()

        # Create input field
        self.entry = ttk.Entry(self.content_frame, font=('TkDefaultFont', 11), width=20)
        self.entry.pack()
        self.entry.focus_set()

        # Bind Enter key to insert
        self.entry.bind('<Return>', lambda e: self._on_insert())

    def validate(self) -> bool:
        """Validate label input"""
        label = self.entry.get().strip()

        if not label:
            messagebox.showerror("Invalid Input", "Please enter a label name.", parent=self)
            return False

        # Check if label name is valid (alphanumeric and underscores only)
        if not re.match(r'^[a-zA-Z0-9_]+$', label):
            messagebox.showerror(
                "Invalid Input",
                "Label name can only contain letters, numbers, and underscores.",
                parent=self
            )
            return False

        # Check if label already exists
        if label in self.existing_labels:
            messagebox.showerror(
                "Duplicate Label",
                f"A label named '{label}' already exists. Please use a unique name.",
                parent=self
            )
            return False

        return True

    def get_directive_text(self) -> str:
        """Get the label directive text"""
        label = self.entry.get().strip()
        return f"{{label: {label}}}"


class InsertLoopDialog(BaseInsertDialog):
    """Dialog for inserting a Loop directive"""

    def __init__(self, parent, existing_labels=None):
        description = (
            "Placed at the end of a loop.\n\n"
            "To set the beginning of a loop, use a label directive (Insert > Label).\n"
            "Use '@start' as a special keyword for the beginning of the song."
        )
        super().__init__(parent, "Insert Loop", description)

        self.existing_labels = existing_labels or set()

        # Create input fields
        input_frame = ttk.Frame(self.content_frame)
        input_frame.pack()

        ttk.Label(input_frame, text="Label:").pack(side=tk.LEFT, padx=(0, 5))

        # Add @start as a special label option
        label_options = ["@start"] + sorted(list(self.existing_labels))

        self.label_var = tk.StringVar(value="@start" if "@start" in label_options else "")
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

    def validate(self) -> bool:
        """Validate loop input"""
        label = self.label_var.get().strip()

        if not label:
            messagebox.showerror("Invalid Input", "Please select a label.", parent=self)
            return False

        count = self.count_var.get()
        if count < 1:
            messagebox.showerror("Invalid Input", "Loop count must be at least 1.", parent=self)
            return False

        return True

    def get_directive_text(self) -> str:
        """Get the loop directive text"""
        label = self.label_var.get()
        count = self.count_var.get()
        return f"{{loop: {label} {count}}}"
