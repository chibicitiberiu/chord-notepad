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
from session.highlighting import compute_spans
from ui.text_editor import ChordTextEditor

logger = logging.getLogger(__name__)

# A page is a title plus a list of blocks. A block is one of
#   ("text", paragraph)
#   ("snippet", song_text, notation)
#   ("image", resource_path)
# Snippets are rendered by a read-only ChordTextEditor painting the spans of the
# real chord detection, so they look exactly like the editor (colors, font,
# underlines).


class QuickStartDialog(tk.Toplevel):
    """Quick Start tour: short explanations with live-highlighted examples."""

    PAGES: List[dict] = [
        {
            "title": "Welcome to Chord Notepad",
            "blocks": [
                ("text",
                 "Chord Notepad is a text editor for musicians. Write a song the way "
                 "a chord sheet looks: chords on their own line, right above the "
                 "lyrics they go with."),
                ("snippet",
                 "C        C/E      F      C\n"
                 "Twinkle, twinkle, little star,\n"
                 "Dm    Am     G        C\n"
                 "How I wonder what you are!",
                 "american"),
                ("text",
                 "The app recognizes chord lines on its own and highlights their "
                 "chords; lyric lines are left alone. Click any chord in the editor "
                 "to hear it, or press ▶ in the toolbar to play the whole song."),
            ],
        },
        {
            "title": "How Chord Lines Are Detected",
            "blocks": [
                ("text",
                 "There is nothing to mark up. A line counts as a chord line when "
                 "most of its words are chords, so a lyric that happens to contain "
                 "a word like “A” stays plain text."),
                ("snippet",
                 "G              D/F#        Em          C\n"
                 "A song for you, a melody I made\n"
                 "Am7   Dsus4   Cmaj7   G/B   F#m7b5   E7#9",
                 "american"),
                ("text",
                 "Chords can be as rich as you need: sevenths, suspended and added "
                 "notes, extensions, altered notes, and slash chords for a specific "
                 "bass note."),
            ],
        },
        {
            "title": "Do-Re-Mi and Roman Numerals",
            "blocks": [
                ("text",
                 "Prefer solfège? Switch to European notation with the Do button "
                 "in the toolbar and write chords as Do, Re, Mi… with a lowercase "
                 "m for minor."),
                ("snippet",
                 "Do        Lam       Rem7      Sol7\n"
                 "Somewhere a melody is calling\n"
                 "Fa        Do/Mi     Rem       Sol\n"
                 "Every note is coming home",
                 "european"),
                ("text",
                 "Roman numerals write chords relative to the key, set with "
                 "{key: …} or the Key box. Change the key and the same song plays "
                 "in the new key."),
                ("snippet",
                 "{key: G}\n"
                 "I         vi        IV        V7\n"
                 "Here's a tune in any key you like\n"
                 "ii7       V7        I\n"
                 "Play it high or play it low",
                 "american"),
            ],
        },
        {
            "title": "Tempo, Meter and Timing",
            "blocks": [
                ("text",
                 "Directives in {braces} set the tempo, time signature and key. They "
                 "can go anywhere, so a song can speed up or change key halfway "
                 "through."),
                ("snippet",
                 "{bpm: 90} {time: 3/4}\n"
                 "G         G7        C*6\n"
                 "Walking slow in waltz time,\n"
                 "D7*1.5   C*1.5    G     NC\n"
                 "step and turn and home",
                 "american"),
                ("text",
                 "Each chord lasts one bar unless you add *beats after it: C*6 holds "
                 "for two bars of 3/4, D7*1.5 for a beat and a half. NC is a bar of "
                 "silence. The toolbar's Speed, Key and Time controls set the "
                 "defaults for the whole song."),
            ],
        },
        {
            "title": "Song Structure",
            "blocks": [
                ("text",
                 "Name a section with {label: …} and repeat it with {loop: name "
                 "times}. Lines starting with // are comments: they're notes for you "
                 "and are never played."),
                ("snippet",
                 "{label: chorus}\n"
                 "F         C         G         Am\n"
                 "Sing it loud and sing it clear,\n"
                 "F         C         G\n"
                 "everybody gather near\n"
                 "// Chorus twice at the end\n"
                 "{loop: chorus 2}",
                 "american"),
                ("text",
                 "Tools → Insert has small dialogs for adding labels, loops and "
                 "other directives if you'd rather not type them."),
            ],
        },
        {
            "title": "The Chord Sheet",
            "blocks": [
                ("text",
                 "The panel under the editor draws the song's chords as you write: "
                 "as a piano roll, on a music staff, as guitar chord diagrams (Fret "
                 "cards), or as tab. It follows along while the song plays."),
                ("image", "resources/quickstart/chord_sheet.png"),
                ("text",
                 "Fret cards and Tab need a fretted instrument, picked in Playback "
                 "→ Voicing (for example Guitar). Show or hide the panel with "
                 "View → Chord Sheet."),
            ],
        },
        {
            "title": "You're Ready!",
            "blocks": [
                ("text", "That's all you need to get started."),
                ("text",
                 "Press F1 any time for the full User Guide (also in the Help menu). "
                 "Tools → Identify Chord names a chord from the notes you pick, "
                 "and Help → Quick Start brings this tour back."),
                ("text", "Have fun making music!"),
            ],
        },
    ]

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
