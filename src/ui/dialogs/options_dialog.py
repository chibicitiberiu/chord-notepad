"""Settings dialog: a left page list (General / Playback & Audio / Voicings)
backed by a single SettingsViewModel working copy, with Save/Cancel at the
bottom. Nothing is written to configuration until Save is pressed.
"""

import logging
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, font as tkfont
from typing import Any, Callable, Dict, Optional

from constants import MIN_FONT_SIZE, MAX_FONT_SIZE
from viewmodels.settings_viewmodel import SettingsViewModel
from ui.dialogs.voicings_page import VoicingsPage

logger = logging.getLogger(__name__)

# BPM bounds mirror Config.validate() (models/config.py) and the toolbar's
# BPM scrubber (ui/main_window.py); there is no shared constant for these yet.
MIN_BPM = 20
MAX_BPM = 400

MIN_RECENT_FILES = 1
MAX_RECENT_FILES = 30

LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
TIME_SIGNATURE_UNITS = [2, 4, 8, 16]
AUDIO_DRIVERS = ["", "alsa", "pulseaudio", "jack", "dsound", "coreaudio"]

# Fixed set of default-key choices (one spelling per semitone). Deliberately
# smaller than utils.key_helpers.get_key_options(), which lists every
# enharmonic spelling for the toolbar's roman-numeral key selector; the
# Settings default key just needs a single sane starting point.
DEFAULT_KEY_OPTIONS = [
    "C", "C#", "Db", "D", "Eb", "E", "F", "F#",
    "Gb", "G", "Ab", "A", "Bb", "B",
]

RESTART_HINT = "Takes effect after restart."

_HINT_FG = "#666666"


class OptionsDialog(tk.Toplevel):
    """Modal Settings dialog with a left page list and Save/Cancel."""

    def __init__(
        self,
        parent: tk.Misc,
        config_service: Any,
        on_apply: Optional[Callable[[Any], None]] = None,
    ) -> None:
        """Initialize the Settings dialog.

        Args:
            parent: Parent window (MainWindow).
            config_service: ConfigService used to build the working-copy
                SettingsViewModel. Nothing is read from or written to it
                directly by this dialog.
            on_apply: Optional callback invoked with the SettingsChanges
                returned by SettingsViewModel.commit() after a successful
                Save.
        """
        super().__init__(parent)

        self.on_apply = on_apply
        self._viewmodel = SettingsViewModel(config_service)

        self.title("Settings")
        self.transient(parent)
        self.grab_set()
        self.resizable(True, True)
        self.geometry("800x600")
        self.minsize(640, 480)

        self._pages: Dict[str, ttk.Frame] = {}
        self._build_ui()

        # Center on parent.
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.bind("<Escape>", lambda e: self._on_cancel())

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Build the page list, page frames, and Save/Cancel buttons."""
        outer = ttk.Frame(self, padding=10)
        outer.pack(fill=tk.BOTH, expand=True)

        body = ttk.Frame(outer)
        body.pack(fill=tk.BOTH, expand=True)

        # Left page list.
        self._nav = ttk.Treeview(body, show="tree", selectmode="browse", height=10)
        self._nav.column("#0", width=160, stretch=False)
        self._nav.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        self._nav.insert("", "end", iid="general", text="General")
        self._nav.insert("", "end", iid="playback_audio", text="Playback & Audio")
        self._nav.insert("", "end", iid="voicings", text="Voicings")
        self._nav.bind("<<TreeviewSelect>>", self._on_nav_select)

        # Right content area: stacked page frames.
        content_host = ttk.Frame(body)
        content_host.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        content_host.rowconfigure(0, weight=1)
        content_host.columnconfigure(0, weight=1)

        self._pages["general"] = self._build_general_page(content_host)
        self._pages["playback_audio"] = self._build_playback_audio_page(content_host)
        self._voicings_page = VoicingsPage(content_host, self._viewmodel)
        self._pages["voicings"] = self._voicings_page

        for frame in self._pages.values():
            frame.grid(row=0, column=0, sticky="nsew")

        # Bottom buttons.
        button_bar = ttk.Frame(outer)
        button_bar.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(button_bar, text="Cancel", command=self._on_cancel).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(button_bar, text="Save", command=self._on_save).pack(side=tk.RIGHT)

        # Default to the General page.
        self._nav.selection_set("general")
        self._show_page("general")

    def _build_general_page(self, parent: tk.Misc) -> ttk.Frame:
        """Build the General settings page."""
        page = ttk.Frame(parent, padding=16)
        page.columnconfigure(1, weight=1)
        row = 0

        # Font family
        ttk.Label(page, text="Font family:").grid(row=row, column=0, sticky="w", pady=6)
        family_var = tk.StringVar(value=self._viewmodel.font_family)
        family_combo = ttk.Combobox(
            page, textvariable=family_var, state="readonly",
            values=self._sane_font_families(self._viewmodel.font_family), width=30,
        )
        family_combo.grid(row=row, column=1, sticky="w", pady=6)
        self._bind_var(family_var, "font_family")
        row += 1

        # Font size
        ttk.Label(page, text="Font size:").grid(row=row, column=0, sticky="w", pady=6)
        size_var = tk.IntVar(value=self._viewmodel.font_size)
        size_spin = ttk.Spinbox(
            page, from_=MIN_FONT_SIZE, to=MAX_FONT_SIZE, textvariable=size_var, width=6,
        )
        size_spin.grid(row=row, column=1, sticky="w", pady=6)
        self._bind_var(size_var, "font_size")
        row += 1

        # Notation
        ttk.Label(page, text="Notation:").grid(row=row, column=0, sticky="w", pady=6)
        notation_frame = ttk.Frame(page)
        notation_frame.grid(row=row, column=1, sticky="w", pady=6)
        notation_var = tk.StringVar(value=self._viewmodel.notation)
        ttk.Radiobutton(
            notation_frame, text="American", variable=notation_var, value="american",
        ).pack(side=tk.LEFT)
        ttk.Radiobutton(
            notation_frame, text="European", variable=notation_var, value="european",
        ).pack(side=tk.LEFT, padx=(10, 0))
        self._bind_var(notation_var, "notation")
        row += 1

        # Default key
        ttk.Label(page, text="Default key:").grid(row=row, column=0, sticky="w", pady=6)
        key_var = tk.StringVar(value=self._viewmodel.key)
        key_combo = ttk.Combobox(
            page, textvariable=key_var, state="readonly", values=DEFAULT_KEY_OPTIONS, width=6,
        )
        key_combo.grid(row=row, column=1, sticky="w", pady=6)
        self._bind_var(key_var, "key")
        row += 1

        # Show quick start on startup
        quick_start_var = tk.BooleanVar(value=self._viewmodel.show_quick_start_on_startup)
        ttk.Checkbutton(
            page, text="Show quick start at startup", variable=quick_start_var,
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=6)
        self._bind_var(quick_start_var, "show_quick_start_on_startup")
        row += 1

        # Max recent files
        ttk.Label(page, text="Max recent files:").grid(row=row, column=0, sticky="w", pady=6)
        recent_var = tk.IntVar(value=self._viewmodel.max_recent_files)
        recent_spin = ttk.Spinbox(
            page, from_=MIN_RECENT_FILES, to=MAX_RECENT_FILES, textvariable=recent_var, width=6,
        )
        recent_spin.grid(row=row, column=1, sticky="w", pady=6)
        self._bind_var(recent_var, "max_recent_files")
        row += 1

        # Log level
        ttk.Label(page, text="Log level:").grid(row=row, column=0, sticky="w", pady=6)
        log_level_var = tk.StringVar(value=self._viewmodel.log_level)
        log_level_combo = ttk.Combobox(
            page, textvariable=log_level_var, state="readonly", values=LOG_LEVELS, width=10,
        )
        log_level_combo.grid(row=row, column=1, sticky="w", pady=6)
        self._bind_var(log_level_var, "log_level")
        row += 1

        ttk.Label(page, text=RESTART_HINT, foreground=_HINT_FG).grid(
            row=row, column=0, columnspan=2, sticky="w",
        )

        return page

    def _build_playback_audio_page(self, parent: tk.Misc) -> ttk.Frame:
        """Build the Playback & Audio settings page."""
        page = ttk.Frame(parent, padding=16)
        page.columnconfigure(1, weight=1)
        row = 0

        # Default BPM
        ttk.Label(page, text="Default BPM:").grid(row=row, column=0, sticky="w", pady=6)
        bpm_var = tk.IntVar(value=self._viewmodel.bpm)
        bpm_spin = ttk.Spinbox(page, from_=MIN_BPM, to=MAX_BPM, textvariable=bpm_var, width=6)
        bpm_spin.grid(row=row, column=1, sticky="w", pady=6)
        self._bind_var(bpm_var, "bpm")
        row += 1

        # Default time signature
        ttk.Label(page, text="Default time signature:").grid(row=row, column=0, sticky="w", pady=6)
        time_sig_frame = ttk.Frame(page)
        time_sig_frame.grid(row=row, column=1, sticky="w", pady=6)
        beats_var = tk.IntVar(value=self._viewmodel.time_signature_beats)
        ttk.Spinbox(time_sig_frame, from_=1, to=16, textvariable=beats_var, width=4).pack(side=tk.LEFT)
        ttk.Label(time_sig_frame, text="/").pack(side=tk.LEFT, padx=4)
        unit_var = tk.IntVar(value=self._viewmodel.time_signature_unit)
        ttk.Combobox(
            time_sig_frame, textvariable=unit_var, state="readonly",
            values=TIME_SIGNATURE_UNITS, width=4,
        ).pack(side=tk.LEFT)
        self._bind_var(beats_var, "time_signature_beats")
        self._bind_var(unit_var, "time_signature_unit")
        row += 1

        # Soundfont path
        ttk.Label(page, text="Soundfont path:").grid(row=row, column=0, sticky="w", pady=6)
        soundfont_frame = ttk.Frame(page)
        soundfont_frame.grid(row=row, column=1, sticky="ew", pady=6)
        soundfont_var = tk.StringVar(value=self._viewmodel.soundfont_path or "")
        soundfont_entry = ttk.Entry(soundfont_frame, textvariable=soundfont_var, width=32)
        soundfont_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(
            soundfont_frame, text="Browse...", command=lambda: self._browse_soundfont(soundfont_var),
        ).pack(side=tk.LEFT, padx=(5, 0))
        self._bind_var(soundfont_var, "soundfont_path", transform=lambda v: v or None)
        row += 1

        ttk.Label(
            page, text="Leave empty to use the bundled default soundfont. " + RESTART_HINT,
            foreground=_HINT_FG, wraplength=420, justify=tk.LEFT,
        ).grid(row=row, column=0, columnspan=2, sticky="w")
        row += 1

        # Audio driver
        ttk.Label(page, text="Audio driver:").grid(row=row, column=0, sticky="w", pady=6)
        driver_var = tk.StringVar(value=self._viewmodel.audio_driver or "")
        driver_combo = ttk.Combobox(page, textvariable=driver_var, values=AUDIO_DRIVERS, width=15)
        driver_combo.grid(row=row, column=1, sticky="w", pady=6)
        self._bind_var(driver_var, "audio_driver", transform=lambda v: v or None)
        row += 1

        ttk.Label(
            page, text="Empty means auto-detect. " + RESTART_HINT, foreground=_HINT_FG,
        ).grid(row=row, column=0, columnspan=2, sticky="w")

        return page

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _sane_font_families(current: str) -> list:
        """Return a sorted, de-duplicated list of usable font family names.

        Filters out internal/vertical-writing pseudo-fonts (names starting
        with '@', seen on Windows) and blank entries. Always includes the
        current family even if tk.font.families() didn't report it.
        """
        families = {f for f in tkfont.families() if f and not f.startswith("@")}
        if current:
            families.add(current)
        return sorted(families, key=str.lower)

    def _bind_var(self, var: tk.Variable, attr: str, transform: Optional[Callable[[Any], Any]] = None) -> None:
        """Two-way bind a Tk variable to a SettingsViewModel working-copy attribute.

        Writes are pushed to the attribute on every variable change. Reads
        happen once at widget-construction time (the variable is seeded with
        the attribute's current value).
        """
        def _on_write(*_args: Any) -> None:
            try:
                value = var.get()
            except tk.TclError:
                # Transient invalid state (e.g. Spinbox momentarily empty
                # while the user is typing); ignore until it's valid again.
                return
            if transform is not None:
                value = transform(value)
            setattr(self._viewmodel, attr, value)

        var.trace_add("write", _on_write)

    def _browse_soundfont(self, soundfont_var: tk.StringVar) -> None:
        """Open a file picker for the soundfont path and update the entry."""
        filename = filedialog.askopenfilename(
            title="Select SoundFont",
            filetypes=[("SoundFont files", "*.sf2"), ("All files", "*.*")],
            parent=self,
        )
        if filename:
            soundfont_var.set(filename)

    def _on_nav_select(self, _event: Any = None) -> None:
        """Handle page-list selection changes."""
        selection = self._nav.selection()
        if not selection:
            return
        self._show_page(selection[0])

    def _show_page(self, key: str) -> None:
        """Raise the page frame for the given key to the front."""
        page = self._pages.get(key)
        if page is None:
            return
        page.tkraise()
        if key == "voicings":
            self._voicings_page.refresh()

    # ------------------------------------------------------------------
    # Save / Cancel
    # ------------------------------------------------------------------

    def _on_cancel(self) -> None:
        """Discard the working copy and close without saving."""
        self.destroy()

    def _on_save(self) -> None:
        """Validate, and either report the first error or commit and close."""
        errors = self._viewmodel.validate_all()
        if errors:
            name, message = errors[0]
            messagebox.showerror("Invalid Voicing", f"{name}: {message}", parent=self)
            self._nav.selection_set("voicings")
            self._show_page("voicings")
            self._voicings_page.select_voicing(name)
            return

        changes = self._viewmodel.commit()
        if self.on_apply is not None:
            self.on_apply(changes)
        self.destroy()
