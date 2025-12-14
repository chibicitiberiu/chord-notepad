"""
Quick Start dialog that shows on first launch
"""

import logging
import tkinter as tk
from tkinter import ttk
from typing import Optional

logger = logging.getLogger(__name__)


class QuickStartDialog(tk.Toplevel):
    """Quick Start dialog with paginated content and screenshot placeholders"""

    # Define pages with title, content, and screenshot description
    PAGES = [
        {
            "title": "Welcome to Chord Notepad",
            "content": (
                "Chord Notepad is a text editor for musicians that recognizes "
                "and plays chord symbols.\n\n"
                "Just type chords like C, Am, F, G and hear them play back.\n\n"
                "This quick tour will show you the basics in just a few steps."
            ),
            "screenshot": (
                "[Screenshot: Main window overview showing the text editor with "
                "some chords typed in, highlighting the blue underlined chords]"
            )
        },
        {
            "title": "Writing Chords",
            "content": (
                "Type chord names separated by spaces:\n"
                "  C  Am  F  G\n\n"
                "Valid chords appear in blue with an underline.\n\n"
                "You can use:\n"
                "  • American notation (C, D, E...)\n"
                "  • European notation (Do, Re, Mi...)\n"
                "  • Many chord types (7th, maj7, sus4, etc.)"
            ),
            "screenshot": (
                "[Screenshot: Text editor showing various chord types with "
                "blue underlines, and one invalid chord with gray underline]"
            )
        },
        {
            "title": "Playing Your Chords",
            "content": (
                "Click the Play button (▶) in the toolbar to hear your chords.\n\n"
                "Or click any individual chord to hear just that chord.\n\n"
                "Use the BPM slider to adjust tempo.\n"
                "The toolbar also has controls for:\n"
                "  • Key signature\n"
                "  • Time signature\n"
                "  • Notation system (AB/Do toggle)"
            ),
            "screenshot": (
                "[Screenshot: Toolbar with Play button and BPM slider highlighted, "
                "showing a chord being played with yellow highlight]"
            )
        },
        {
            "title": "Organizing Your Music",
            "content": (
                "Add comments to your chord sheets:\n"
                "  // Verse\n"
                "  C  Am  F  G\n\n"
                "Control playback with directives:\n"
                "  {bpm: 120}     Set tempo\n"
                "  {time: 4/4}    Set time signature\n"
                "  {key: C}       Set key\n\n"
                "Set chord duration:\n"
                "  C*2  Am*4      Hold chords longer"
            ),
            "screenshot": (
                "[Screenshot: Text editor showing a song with comments in gray, "
                "directives in purple, and chords with duration modifiers]"
            )
        },
        {
            "title": "You're Ready!",
            "content": (
                "That's all you need to get started.\n\n"
                "For more details:\n"
                "  • Press F1 for the full User Guide\n"
                "  • Use Help → User Guide menu\n"
                "  • Try Tools → Identify Chord to find chord names\n\n"
                "Have fun making music!"
            ),
            "screenshot": (
                "[Screenshot: Help menu expanded showing User Guide and "
                "Quick Start options]"
            )
        }
    ]

    def __init__(self, parent):
        """Initialize the Quick Start dialog.

        Args:
            parent: Parent window
        """
        super().__init__(parent)

        self.title("Quick Start")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        # Current page index
        self.current_page = 0

        # Configure window size
        self.geometry("600x500")

        # Main frame with padding
        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title label
        self.title_label = tk.Label(
            main_frame,
            text="",
            font=('TkDefaultFont', 14, 'bold'),
            anchor=tk.W,
            justify=tk.LEFT
        )
        self.title_label.pack(fill=tk.X, pady=(0, 15))

        # Content text area
        # Get the background color from the window
        bg_color = self.cget('background')
        self.content_text = tk.Text(
            main_frame,
            wrap=tk.WORD,
            height=10,
            width=60,
            relief=tk.FLAT,
            bg=bg_color,
            font=('TkDefaultFont', 10),
            cursor="arrow",
            state=tk.DISABLED
        )
        self.content_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Screenshot placeholder frame
        screenshot_frame = ttk.LabelFrame(main_frame, text="Screenshot Preview", padding="10")
        screenshot_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        self.screenshot_label = tk.Label(
            screenshot_frame,
            text="",
            font=('TkDefaultFont', 9, 'italic'),
            wraplength=540,
            justify=tk.LEFT,
            fg='#666666',
            anchor=tk.W
        )
        self.screenshot_label.pack(fill=tk.BOTH, expand=True)

        # Page indicator
        self.page_indicator = tk.Label(
            main_frame,
            text="",
            font=('TkDefaultFont', 9),
            fg='#666666'
        )
        self.page_indicator.pack(pady=(0, 10))

        # Don't show again checkbox
        self.dont_show_var = tk.BooleanVar(value=False)
        dont_show_check = ttk.Checkbutton(
            main_frame,
            text="Don't show this again on startup",
            variable=self.dont_show_var
        )
        dont_show_check.pack(pady=(0, 10))

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack()

        self.prev_button = ttk.Button(
            button_frame,
            text="← Previous",
            command=self._previous_page,
            state=tk.DISABLED
        )
        self.prev_button.pack(side=tk.LEFT, padx=5)

        self.next_button = ttk.Button(
            button_frame,
            text="Next →",
            command=self._next_page
        )
        self.next_button.pack(side=tk.LEFT, padx=5)

        self.close_button = ttk.Button(
            button_frame,
            text="Close",
            command=self._on_close
        )
        self.close_button.pack(side=tk.LEFT, padx=5)

        # Load first page
        self._load_page(0)

        # Center the dialog
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

        # Bind keyboard shortcuts
        self.bind("<Escape>", lambda e: self._on_close())
        self.bind("<Left>", lambda e: self._previous_page() if self.prev_button['state'] == tk.NORMAL else None)
        self.bind("<Right>", lambda e: self._next_page() if self.next_button['state'] == tk.NORMAL else None)

    def _load_page(self, page_index: int):
        """Load and display a specific page.

        Args:
            page_index: Index of the page to load
        """
        if not 0 <= page_index < len(self.PAGES):
            return

        self.current_page = page_index
        page = self.PAGES[page_index]

        # Update title
        self.title_label.config(text=page["title"])

        # Update content
        self.content_text.config(state=tk.NORMAL)
        self.content_text.delete('1.0', tk.END)
        self.content_text.insert('1.0', page["content"])
        self.content_text.config(state=tk.DISABLED)

        # Update screenshot placeholder
        self.screenshot_label.config(text=page["screenshot"])

        # Update page indicator
        self.page_indicator.config(
            text=f"Page {page_index + 1} of {len(self.PAGES)}"
        )

        # Update button states
        self.prev_button.config(
            state=tk.NORMAL if page_index > 0 else tk.DISABLED
        )

        if page_index < len(self.PAGES) - 1:
            self.next_button.config(state=tk.NORMAL, text="Next →")
        else:
            self.next_button.config(state=tk.DISABLED, text="Next →")

    def _previous_page(self):
        """Navigate to the previous page"""
        if self.current_page > 0:
            self._load_page(self.current_page - 1)

    def _next_page(self):
        """Navigate to the next page"""
        if self.current_page < len(self.PAGES) - 1:
            self._load_page(self.current_page + 1)

    def _on_close(self):
        """Handle dialog close"""
        self.destroy()

    def get_dont_show_again(self) -> bool:
        """Get the state of the 'don't show again' checkbox.

        Returns:
            True if user checked 'don't show again'
        """
        return self.dont_show_var.get()
