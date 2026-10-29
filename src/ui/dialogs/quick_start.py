"""
Quick Start dialog that shows on first launch
"""

import logging
import tkinter as tk
from tkinter import ttk
from typing import Any, List, Optional

from constants import UI_BORDER
from services.resource_service import ResourceService
from services.song_parser_service import SongParserService
from session import quick_start
from session.highlighting import compute_spans
from session.platform import DESKTOP
from ui.text_editor import ChordTextEditor

logger = logging.getLogger(__name__)

# A page is a title plus a list of blocks (see session.quick_start). Snippets
# are rendered by a read-only ChordTextEditor painting the spans of the real
# chord detection, so they look exactly like the editor (colors, font,
# underlines).


class QuickStartDialog(tk.Toplevel):
    """Quick Start tour: short explanations with live-highlighted examples."""

    # The pages are shared with Android (session.quick_start); these are the
    # desktop's.
    PAGES: List[dict] = quick_start.pages(DESKTOP)

    def __init__(self, parent: tk.Misc,
                 song_parser_service: Optional[SongParserService] = None,
                 editor_font: Optional[Any] = None,
                 resource_service: Optional[ResourceService] = None) -> None:
        """Initialize the Quick Start dialog.

        Args:
            parent: Parent window
            song_parser_service: Chord detection for the example snippets
                (a fresh one is created if omitted)
            editor_font: Font the main editor uses, so snippets match it
            resource_service: Resolves bundled image paths (a fresh one is
                created if omitted)
        """
        super().__init__(parent)

        self.title("Quick Start")
        self.transient(parent)
        try:
            self.grab_set()
        except tk.TclError:
            # Parent not viewable (e.g. headless tests); the dialog still works.
            logger.debug("Quick Start grab failed", exc_info=True)
        self.resizable(False, False)

        self._parser = song_parser_service or SongParserService()
        self._editor_font = editor_font
        self._resources = resource_service or ResourceService()
        self._snippets: List[ChordTextEditor] = []
        # PhotoImages shown on the current page; Tk drops them if unreferenced.
        self._images: List[tk.PhotoImage] = []

        # Current page index
        self.current_page = 0

        self.geometry("760x620")

        # Main frame with padding
        main_frame = ttk.Frame(self, padding=(24, 20, 24, 16))
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title row: page title, with the page indicator at the right
        title_row = ttk.Frame(main_frame)
        title_row.pack(fill=tk.X, pady=(0, 12))
        self.page_indicator = ttk.Label(title_row, text="", style='Muted.TLabel')
        self.page_indicator.pack(side=tk.RIGHT)
        self.title_label = ttk.Label(
            title_row,
            text="",
            font=('TkDefaultFont', 14, 'bold'),
            anchor=tk.W,
        )
        self.title_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Page body: rebuilt from the page's blocks on every page change
        self.body = ttk.Frame(main_frame)
        self.body.pack(fill=tk.BOTH, expand=True)

        # Footer: "don't show again" on the left, navigation on the right
        footer = ttk.Frame(main_frame)
        footer.pack(fill=tk.X, pady=(12, 0))

        self.dont_show_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            footer,
            text="Don't show this again on startup",
            variable=self.dont_show_var,
        ).pack(side=tk.LEFT)

        self.close_button = ttk.Button(footer, text="Close", command=self._on_close)
        self.close_button.pack(side=tk.RIGHT, padx=(5, 0))
        self.next_button = ttk.Button(footer, text="Next →", command=self._next_page)
        self.next_button.pack(side=tk.RIGHT, padx=(5, 0))
        self.prev_button = ttk.Button(
            footer, text="← Previous", command=self._previous_page, state=tk.DISABLED)
        self.prev_button.pack(side=tk.RIGHT)

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

    def _clear_body(self) -> None:
        """Remove the current page's widgets."""
        self._snippets = []
        self._images = []
        for child in self.body.winfo_children():
            child.destroy()

    def _add_text(self, text: str) -> None:
        """Add a wrapped paragraph to the page body."""
        ttk.Label(self.body, text=text, wraplength=700, justify=tk.LEFT).pack(
            fill=tk.X, anchor=tk.W, pady=(0, 10))

    def _add_image(self, relative_path: str) -> None:
        """Add a bundled picture (with a 1px border) to the page body."""
        try:
            image = tk.PhotoImage(master=self, file=self._resources.get_resource_path(relative_path))
        except tk.TclError:
            logger.warning(f"Quick Start image missing: {relative_path}")
            return
        self._images.append(image)
        frame = tk.Frame(self.body, bd=0, highlightthickness=1,
                         highlightbackground=UI_BORDER, highlightcolor=UI_BORDER)
        frame.pack(anchor=tk.W, pady=(0, 12))
        tk.Label(frame, image=image, bd=0).pack()

    def _add_snippet(self, text: str, notation: str) -> None:
        """Add a read-only, chord-highlighted example to the page body.

        Args:
            text: Song text to show
            notation: "american" or "european" (selects chord detection)
        """
        frame = tk.Frame(self.body, bd=0, highlightthickness=1,
                         highlightbackground=UI_BORDER, highlightcolor=UI_BORDER)
        frame.pack(fill=tk.X, pady=(0, 12))

        snippet = ChordTextEditor(
            frame,
            height=text.count('\n') + 1,
            width=60,
            wrap=tk.NONE,
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
            padx=8,
            pady=6,
            cursor='arrow',
            undo=False,
        )
        if self._editor_font:
            snippet.configure(font=self._editor_font)
        snippet.insert('1.0', text)
        lines = self._parser.detect_chords_in_text(text, notation)
        snippet.paint_spans(compute_spans(lines, text))
        snippet.configure(state=tk.DISABLED)
        # Display only: no hand cursor over chords, no paste handling.
        for sequence in ('<Motion>', '<<Paste>>'):
            snippet.unbind(sequence)
        snippet.pack(fill=tk.X)
        self._snippets.append(snippet)

    def _load_page(self, page_index: int) -> None:
        """Load and display a specific page.

        Args:
            page_index: Index of the page to load
        """
        if not 0 <= page_index < len(self.PAGES):
            return

        self.current_page = page_index
        page = self.PAGES[page_index]

        self.title_label.config(text=page["title"])

        self._clear_body()
        for block in page["blocks"]:
            if block[0] == "text":
                self._add_text(block[1])
            elif block[0] == "snippet":
                self._add_snippet(block[1], block[2])
            elif block[0] == "image":
                self._add_image(block[1])

        self.page_indicator.config(text=f"{page_index + 1} / {len(self.PAGES)}")

        self.prev_button.config(state=tk.NORMAL if page_index > 0 else tk.DISABLED)
        last = page_index == len(self.PAGES) - 1
        self.next_button.config(state=tk.DISABLED if last else tk.NORMAL)

    def _previous_page(self) -> None:
        """Navigate to the previous page"""
        if self.current_page > 0:
            self._load_page(self.current_page - 1)

    def _next_page(self) -> None:
        """Navigate to the next page"""
        if self.current_page < len(self.PAGES) - 1:
            self._load_page(self.current_page + 1)

    def _on_close(self) -> None:
        """Handle dialog close"""
        self._clear_body()
        self.destroy()

    def get_dont_show_again(self) -> bool:
        """Get the state of the 'don't show again' checkbox.

        Returns:
            True if user checked 'don't show again'
        """
        return self.dont_show_var.get()
