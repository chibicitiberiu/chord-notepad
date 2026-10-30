"""
Main application window with text editor and menu bar
"""

import logging
import tkinter as tk
from tkinter import ttk, messagebox, font as tkfont
import os
import sys
from typing import TYPE_CHECKING, Any, Optional
from PIL import Image, ImageTk
from ui.scrubber import Scrubber
from utils import error_reporting
from ui.text_editor import ChordTextEditor, REDO_ACCELERATOR
from ui.chord_identifier import ChordIdentifierWindow
from ui.builders.menu_builder import MenuBuilder
from ui.audio_errors import present_audio_unavailable
from ui.menu_style import iter_menus, style_menu
from ui.dialogs import (
    OptionsDialog,
    TransposeDialog,
    CapoDialog,
)
from ui.dialogs.insert_directives import dialog_for_request
from utils.display_scaling import apply_xft_dpi
from utils.icon_loader import IconLoader
from utils.ui_helpers import create_tooltip, resolve_font_family
from utils.file_dialogs import ask_open_filename, ask_save_as_filename
from models.notation import Notation
from session import formatting
from session.events import (
    AudioUnavailable, CapoChoiceRequest, CloseApproved, ConfirmDiscardRequest, DiscardChoice,
    InsertDirectiveRequest, PickDocumentRequest, PickMode, TextEdited, UserError,
)
from session.state import (
    ChordSheetState, DocumentState, EditorState, HighlightState, InstrumentMenuState,
    PlayAction, PlaybackState, RecentDocumentsState, StatusState, ToolbarState,
    VoicingMenuState,
)
from session.toolbar import (
    BPM_SCALE, MULTIPLIER_SCALE, ScrubScale, format_bpm, format_multiplier_pct, parse_bpm,
    parse_multiplier_pct,
)
from exceptions import ChordNotepadError
from constants import (
    DEFAULT_FONT_SIZE,
    TAG_CHORD_PLAYING,
    UI_ACCENT,
    UI_ACCENT_ACTIVE,
    UI_BG,
    UI_BORDER,
    UI_HOVER,
    UI_SCROLL_THUMB,
    UI_SCROLL_THUMB_ACTIVE,
    UI_TEXT_MUTED,
    WM_CLASS,
)

if TYPE_CHECKING:
    from session.session import AppSession
    from ui.tk_host import TkHost

logger = logging.getLogger(__name__)

# The Play/Pause button's tooltip for what pressing it does.
_PLAY_PAUSE_TOOLTIPS = {
    PlayAction.PLAY: "Play from start (Shift+Click to play from cursor)",
    PlayAction.PAUSE: "Pause playback",
    PlayAction.RESUME: "Resume playback",
}

# How the native file pickers are shown for each PickDocumentRequest mode:
# (title, default extension, file types).
_TEXT_FILE_TYPES = [("Text Files", "*.txt"), ("All Files", "*.*")]
_PICKERS = {
    PickMode.SAVE: ("Save File As", ".txt", _TEXT_FILE_TYPES),
    PickMode.EXPORT_MIDI: ("Export MIDI", ".mid", [("MIDI files", "*.mid"), ("All files", "*.*")]),
}

# Import build info (may be auto-generated during CI build)
try:
    from build_info import VERSION, BUILD_TYPE, COMMIT_SHORT, BUILD_DATE
    try:
        from build_info import BUILD_NUMBER
    except ImportError:
        BUILD_NUMBER = "0"
except ImportError:
    VERSION = "dev-local"
    BUILD_TYPE = "development"
    COMMIT_SHORT = "unknown"
    BUILD_DATE = "unknown"
    BUILD_NUMBER = "0"


class MainWindow(tk.Tk):
    """Main application window: a Tk view over the application session.

    It sends the session commands and maps the states and events it
    subscribes to onto widgets. Everything else here is a view concern:
    widgets and theme, dialogs and pickers, pixel/cursor to offset
    conversion, the sash and the window geometry.
    """

    def __init__(self, session: "AppSession", host: "TkHost", resources: Any) -> None:
        """Initialize the main window.

        Args:
            session: The application session: every command goes to it and
                everything shown comes from it.
            host: The Tk host; this window becomes its root, so the
                session's timers and posted callbacks run on it.
            resources: ResourceService for resolving resource paths (icons,
                help).
        """
        # On Linux the class becomes the X11 WM_CLASS, which desktops match to
        # the .desktop file (StartupWMClass) to show the right icon and name.
        # Windows and macOS keep Tk's default.
        if sys.platform.startswith('linux'):
            super().__init__(className=WM_CLASS)
            apply_xft_dpi(self)
        else:
            super().__init__()

        # The host's timers run on this window. Attach before building the
        # chord sheet, which arms its debounce timer through the host.
        host.attach(self)

        # Set platform-native ttk theme
        self._setup_theme()

        self.session = session
        # The latest editor and chord-sheet states (fonts for dialogs, the
        # strip's height for the sash) and the voicing groups last built.
        self._editor_state: Optional[EditorState] = None
        self._chord_sheet_state: Optional[ChordSheetState] = None
        self._voicing_groups: Optional[tuple] = None
        # The playing chord last painted: (span, chord index, bar).
        self._shown_progress: Optional[tuple] = None
        self.resource_service = resources
        self._icons = IconLoader(resources)
        self.chord_sheet_panel = None
        self._closing = False

        # Replaced by the session's DocumentState once subscribed.
        self.title("Chord Notepad")
        self.geometry("900x600")

        # Set window icon
        self._set_window_icon()

        # Apply saved window geometry
        saved_geometry = self.session.window_geometry
        if saved_geometry:
            self.geometry(saved_geometry)

        # Create UI components (text editor first so menu can reference it)
        self.create_text_editor()
        self.create_menu()
        self.create_toolbar()
        self.create_statusbar()

        # Chord-sheet strip docked under the editor (built after the editor's
        # paned window exists).
        self.create_chord_sheet()

        # Pack the toolbar at the top, above the editor pane that was packed first.
        self.toolbar.pack(side=tk.TOP, fill=tk.X, before=self.content_paned)

        # The session's output: replays the current states, then updates.
        # Subscribed once every widget a state maps to exists.
        self._session_subscription = self.session.subscribe(self._on_session_output)

        # Bind events
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.bind("<Control-MouseWheel>", self.on_mouse_wheel_zoom)

        # Track modifications
        self.text_editor.bind("<<Modified>>", self.on_text_modified)

        # Make chords clickable
        self.text_editor.bind("<Button-1>", self.on_chord_click)

    def show_quick_start_if_needed(self) -> None:
        """Show the Quick Start dialog if this is the first run."""
        if self.session.show_quick_start_on_startup:
            # Use after() to show the dialog after the main window is fully displayed
            self.after(100, self.show_quick_start)

    def report_callback_exception(self, exc: type, val: BaseException, tb: Any) -> None:
        """Log errors raised in Tk callbacks and tell the user.

        Tk's default prints the traceback to stderr, which nobody sees in a
        packaged app, so a failing menu command looked like it did nothing.
        """
        error_reporting.report_unexpected_error(self, (exc, val, tb), "UI callback")

    def _setup_theme(self) -> None:
        """Set up the ttk theme to use platform-native styling."""
        import sys
        style = ttk.Style()

        # Get available themes
        available = style.theme_names()

        # Select platform-appropriate theme
        if sys.platform == 'win32':
            # Windows: 'vista' is the modern native look; 'winnative' is the
            # Windows 95-style classic one, kept only as a last resort.
            preferred = ['vista', 'xpnative', 'winnative']
        elif sys.platform == 'darwin':
            # macOS: 'aqua' is the native theme
            preferred = ['aqua']
        else:
            # Linux: 'clam' looks most modern/native
            preferred = ['clam', 'alt']

        # Apply first available preferred theme
        for theme in preferred:
            if theme in available:
                style.theme_use(theme)
                logger.debug(f"Using ttk theme: {theme}")
                break

        if style.theme_use() == 'clam':
            self._restyle_clam(style)

        style.configure('Muted.TLabel', foreground=UI_TEXT_MUTED)
        style.configure('Status.TLabel', foreground=UI_TEXT_MUTED, padding=(8, 2))

        # Classic tk widgets in the toolbar don't follow the ttk theme, so they
        # take the themed surface color explicitly.
        self._ui_bg = style.lookup('TFrame', 'background') or UI_BG

    def _restyle_clam(self, style: ttk.Style) -> None:
        """Flatten clam's beveled grey look into a lighter, flat one."""
        # Classic tk widgets (menus, dialog windows, a few labels/buttons) read
        # their colors from the option database, not the ttk theme. Match them
        # to the restyled surface. Text/Entry/Listbox are left alone, so the
        # editor keeps its own colors.
        for option, value in (
            ('*Toplevel.background', UI_BG),
            ('*Frame.background', UI_BG),
            ('*Label.background', UI_BG),
            ('*Button.background', UI_BG),
            ('*Button.activeBackground', UI_HOVER),
            ('*Button.highlightBackground', UI_BG),
            ('*Canvas.background', UI_BG),
            ('*Canvas.highlightBackground', UI_BG),
            ('*Menu.background', UI_BG),
            ('*Menu.activeBackground', UI_ACCENT),
            ('*Menu.activeForeground', 'white'),
            # The outline comes from ui/menu_style.py.
            ('*Menu.relief', 'flat'),
            ('*Menu.borderWidth', 1),
            # A flat active border doubles as per-entry padding. activeRelief
            # only exists from Tk 8.7: Tk 8.6 draws the active border raised,
            # so it gets none there.
            ('*Menu.activeRelief', 'flat'),
            ('*Menu.activeBorderWidth', 4 if tk.TkVersion >= 8.7 else 0),
        ):
            self.option_add(option, value)
        # The root window exists before the options above, so it needs its
        # color set directly (it shows around the toolbar and content pane).
        self.configure(background=UI_BG)

        style.configure(
            '.',
            background=UI_BG,
            bordercolor=UI_BORDER,
            lightcolor=UI_BG,
            darkcolor=UI_BG,
            troughcolor=UI_BG,
            focuscolor=UI_ACCENT,
        )
        # Tk 9's clam scales check and radio indicators with the DPI; Tk 8.6
        # draws them at a fixed 10px, tiny on a scaled desktop.
        if tk.TkVersion < 9.0:
            pixels_per_point = float(self.tk.call('tk', 'scaling'))
            indicator = round(10 * pixels_per_point * 72 / 96)
            style.configure('TCheckbutton', indicatorsize=indicator)
            style.configure('TRadiobutton', indicatorsize=indicator)
        style.map('TButton', background=[('pressed', UI_BORDER), ('active', UI_HOVER)])
        style.map('Toolbutton', background=[('selected', UI_HOVER), ('active', UI_HOVER)])
        # Selections (tree rows, list rows, entry text) use the accent color
        # instead of clam's slate grey.
        style.configure('.', selectbackground=UI_ACCENT, selectforeground='white')
        style.map('Treeview', background=[('selected', UI_ACCENT)],
                  foreground=[('selected', 'white')])
        style.configure('Treeview', rowheight=24)
        self.option_add('*Listbox.selectBackground', UI_ACCENT)
        self.option_add('*Listbox.selectForeground', 'white')
        # Readonly comboboxes (Key) read as a plain white field, not a grey slab.
        style.map('TCombobox',
                  fieldbackground=[('readonly', 'white')],
                  selectbackground=[('readonly', 'white')],
                  selectforeground=[('readonly', 'black')],
                  background=[('active', UI_HOVER)])
        style.configure('TCombobox', arrowcolor=UI_TEXT_MUTED)
        style.configure('TSpinbox', arrowcolor=UI_TEXT_MUTED)

        # Slim, arrowless scrollbars: just a thumb in a flat trough.
        for orient in ('Vertical', 'Horizontal'):
            style.layout(f'{orient}.TScrollbar', [
                (f'{orient}.Scrollbar.trough', {'sticky': 'nswe', 'children': [
                    (f'{orient}.Scrollbar.thumb', {'expand': '1', 'sticky': 'nswe'}),
                ]}),
            ])
        style.configure(
            'TScrollbar',
            background=UI_SCROLL_THUMB,
            lightcolor=UI_SCROLL_THUMB,
            darkcolor=UI_SCROLL_THUMB,
            bordercolor=UI_BG,
            troughcolor=UI_BG,
            gripcount=0,
            arrowsize=11,
        )
        style.map('TScrollbar', background=[('pressed', UI_SCROLL_THUMB_ACTIVE),
                                            ('active', UI_SCROLL_THUMB_ACTIVE)])

    def _on_session_output(self, item: object) -> None:
        """Apply one state or event delivered by the session."""
        if isinstance(item, TextEdited):
            self.text_editor.apply_edit(item)
        elif isinstance(item, HighlightState):
            self.text_editor.apply_highlight(item)
        elif isinstance(item, PlaybackState):
            self._apply_playback(item)
        elif isinstance(item, ToolbarState):
            self._apply_toolbar(item)
        elif isinstance(item, StatusState):
            self.statusbar.config(text=item.text)
        elif isinstance(item, EditorState):
            self._apply_editor(item)
        elif isinstance(item, VoicingMenuState):
            self.rebuild_voicing_menu(item)
        elif isinstance(item, InstrumentMenuState):
            self.build_instrument_menu(item)
        elif isinstance(item, ChordSheetState):
            self._apply_chord_sheet(item)
        elif isinstance(item, DocumentState):
            self.title(item.title)
        elif isinstance(item, RecentDocumentsState):
            self._apply_recent_documents(item)
        elif isinstance(item, AudioUnavailable):
            # Over the window the click came from (e.g. the chord identifier).
            present_audio_unavailable(self._dialog_parent(), item.message)
        elif isinstance(item, UserError):
            messagebox.showerror(item.title, item.message, parent=self)
        elif isinstance(item, InsertDirectiveRequest):
            # Shown once delivery is over: a modal dialog run from here would
            # hold back the session's output (playback progress) until closed.
            self.after_idle(self._present_directive_request, item)
        elif isinstance(item, CapoChoiceRequest):
            self.after_idle(self._present_capo_request, item)
        elif isinstance(item, ConfirmDiscardRequest):
            self.after_idle(self._present_confirm_discard, item)
        elif isinstance(item, PickDocumentRequest):
            self.after_idle(self._present_pick_document, item)
        elif isinstance(item, CloseApproved):
            # Not from inside delivery: closing shuts the session down.
            self.after_idle(self._close_window)

    def _apply_editor(self, state: EditorState) -> None:
        """Lock or unlock the editor and apply its font."""
        self._editor_state = state
        self.text_editor.config(state=tk.DISABLED if state.read_only else tk.NORMAL)
        self.apply_font()

    def _dialog_parent(self) -> tk.Misc:
        """The window that has the focus (a dialog), else the main window."""
        try:
            focus = self.focus_get()
        except (KeyError, tk.TclError):
            focus = None
        return focus.winfo_toplevel() if focus is not None else self

    def _apply_toolbar(self, state: ToolbarState) -> None:
        """Show the session's toolbar state (setting widgets sends nothing back)."""
        self._notation = state.notation
        self.update_notation_buttons()

        # While a song plays the BPM scrubber is a read-only display of the
        # effective tempo; afterwards it shows the user's base value again.
        self.bpm_scrubber.set_readonly(not state.bpm_editable)
        self.bpm_scrubber.set_value(state.bpm)
        if not state.bpm_editable:
            self.bpm_scrubber.set_display_text(format_bpm(state.bpm_display))
        self.multiplier_scrubber.set_value(state.multiplier_pct)

        self.key_combo['values'] = state.key_options
        self.key_var.set(state.key)
        self.time_sig_beats_var.set(state.beats)
        self.time_sig_unit_var.set(state.unit)
        self._refresh_metronome_button(state.metronome)

        pausing = state.play_action is PlayAction.PAUSE
        self.play_pause_button.config(image=self._icon_pause if pausing else self._icon_play)
        self._play_pause_tooltip.text = _PLAY_PAUSE_TOOLTIPS[state.play_action]

    def _apply_playback(self, state: PlaybackState) -> None:
        """Highlight (and scroll to) the chord that is sounding."""
        # Repaint (and scroll to) the playing chord only when playback moved
        # on, not when it was merely paused.
        progress = (state.playing_span, state.chord_index, state.bar)
        if progress == self._shown_progress:
            return
        self._shown_progress = progress
        self.text_editor.tag_remove(TAG_CHORD_PLAYING, '1.0', tk.END)
        span = state.playing_span
        if span is not None:
            start = f"1.0 + {span.start} chars"
            self.text_editor.tag_add(TAG_CHORD_PLAYING, start, f"1.0 + {span.end} chars")
            # Above the chord tags, so it shows
            self.text_editor.tag_raise(TAG_CHORD_PLAYING)
            self.text_editor.see(start)

    def _set_window_icon(self) -> None:
        """Set the window icon"""
        try:
            # Get the icon path (relative to project root)
            icon_path = self.resource_service.get_resource_path('resources/icon-32.png')
            if os.path.exists(icon_path):
                icon_image = tk.PhotoImage(file=icon_path)
                self.iconphoto(True, icon_image)
        except Exception as e:
            logger.warning(f"Could not load window icon: {e}")

    def create_menu(self) -> None:
        """Create menu bar using MenuBuilder"""
        menubar = MenuBuilder.create_menubar(self)

        # File menu
        # The Recent Files submenu is filled from the session's
        # RecentDocumentsState.
        self.recent_menu = tk.Menu(menubar, tearoff=0)

        file_menu = MenuBuilder(menubar) \
            .add_command("New", self.new_file, accelerator="Ctrl+N") \
            .add_command("Open...", self.open_file, accelerator="Ctrl+O") \
            .add_command("Save", self.save_file, accelerator="Ctrl+S") \
            .add_command("Save As...", self.save_file_as, accelerator="Ctrl+Shift+S") \
            .add_command("Export MIDI...", self.export_midi) \
            .add_separator() \
            .build()

        file_menu.add_cascade(label="Recent Files", menu=self.recent_menu)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_close, accelerator="Ctrl+Q")

        menubar.add_cascade(label="File", menu=file_menu)

        # Edit menu
        edit_menu = MenuBuilder(menubar) \
            .add_command("Undo", self.text_editor.edit_undo, accelerator="Ctrl+Z") \
            .add_command("Redo", self.text_editor.edit_redo, accelerator=REDO_ACCELERATOR) \
            .add_separator() \
            .add_command("Cut", lambda: self.text_editor.event_generate("<<Cut>>"), accelerator="Ctrl+X") \
            .add_command("Copy", lambda: self.text_editor.event_generate("<<Copy>>"), accelerator="Ctrl+C") \
            .add_command("Paste", lambda: self.text_editor.event_generate("<<Paste>>"), accelerator="Ctrl+V") \
            .add_command("Select All", self.select_all, accelerator="Ctrl+A") \
            .build()
        menubar.add_cascade(label="Edit", menu=edit_menu)

        # View menu
        # Set from the session's ChordSheetState.
        self._chord_sheet_var = tk.BooleanVar(value=False)
        view_menu = MenuBuilder(menubar) \
            .add_command("Font...", self.choose_font) \
            .add_separator() \
            .add_checkbutton("Chord Sheet", self._chord_sheet_var, self.toggle_chord_sheet) \
            .add_separator() \
            .add_command("Increase Font Size", self.increase_font_size, accelerator="Ctrl+Plus") \
            .add_command("Decrease Font Size", self.decrease_font_size, accelerator="Ctrl+Minus") \
            .add_command("Reset Font Size", self.reset_font_size, accelerator="Ctrl+0") \
            .build()
        menubar.add_cascade(label="View", menu=view_menu)

        # Playback menu. The Voicing and Instrument submenus are filled from
        # the session's menu states (and rebuilt when those change).
        self.voicing_var = tk.StringVar()
        self.voicing_menu = tk.Menu(menubar, tearoff=0)
        self.instrument_var = tk.IntVar()
        self.instrument_menu = tk.Menu(menubar, tearoff=0)

        playback_menu = tk.Menu(menubar, tearoff=0)
        playback_menu.add_cascade(label="Voicing", menu=self.voicing_menu)
        self._playback_menu = playback_menu
        playback_menu.add_cascade(label="Instrument", menu=self.instrument_menu)

        menubar.add_cascade(label="Playback", menu=playback_menu)

        # Tools menu with Insert submenu
        insert_menu = MenuBuilder(menubar) \
            .add_command("BPM/Tempo Change...", self.insert_bpm) \
            .add_command("Time Signature Change...", self.insert_time_signature) \
            .add_command("Key Change...", self.insert_key) \
            .add_separator() \
            .add_command("Label...", self.insert_label) \
            .add_command("Loop...", self.insert_loop) \
            .build()

        tools_menu = MenuBuilder(menubar) \
            .add_command("Identify Chord...", self.open_chord_identifier) \
            .add_separator() \
            .build()

        tools_menu.add_cascade(label="Insert", menu=insert_menu)
        tools_menu.add_separator()
        tools_menu.add_command(label="Transpose...", command=self.open_transpose_dialog)
        tools_menu.add_command(label="Suggest Capo...", command=self.open_suggest_capo_dialog)
        tools_menu.add_separator()
        tools_menu.add_command(label="Convert to American Notation", command=self.convert_to_american)
        tools_menu.add_command(label="Convert to European Notation", command=self.convert_to_european)
        tools_menu.add_separator()
        tools_menu.add_command(label="Settings...", command=self.show_options)

        menubar.add_cascade(label="Tools", menu=tools_menu)

        # Help menu
        help_menu = MenuBuilder(menubar) \
            .add_command("User Guide", self.show_help, accelerator="F1") \
            .add_command("Quick Start", self.show_quick_start) \
            .add_separator() \
            .add_command("About", self.show_about) \
            .build()
        menubar.add_cascade(label="Help", menu=help_menu)

        # Restyled clam menus: outlined dropdowns, a menubar spaced as before.
        if ttk.Style(self).theme_use() == 'clam':
            menubar.configure(borderwidth=4)
            for menu in iter_menus(self):
                if menu is not menubar:
                    style_menu(menu)

        # Bind keyboard shortcuts
        self.bind_all("<Control-n>", lambda e: self.new_file())
        self.bind_all("<Control-o>", lambda e: self.open_file())
        self.bind_all("<Control-s>", lambda e: self.save_file())
        self.bind_all("<Control-Shift-S>", lambda e: self.save_file_as())
        self.bind_all("<Control-q>", lambda e: self.on_close())
        self.bind_all("<Control-a>", lambda e: self.select_all())
        self.bind_all("<Control-plus>", lambda e: self.increase_font_size())
        self.bind_all("<Control-equal>", lambda e: self.increase_font_size())  # Ctrl+= is same key as Ctrl++
        self.bind_all("<Control-minus>", lambda e: self.decrease_font_size())
        self.bind_all("<Control-0>", lambda e: self.reset_font_size())
        self.bind_all("<F1>", lambda e: self.show_help())

    def create_toolbar(self) -> None:
        """Create toolbar with controls"""
        # Packed later in __init__, once the editor pane exists to pack above.
        self.toolbar = ttk.Frame(self, padding=(6, 4, 6, 4))

        # The widgets start neutral: the session's ToolbarState fills them in
        # when the window subscribes, and keeps them current.
        self._notation = Notation.AMERICAN.value

        # Create toggle button frame
        # A segmented control: two flat buttons inside a 1px border.
        notation_frame = tk.Frame(self.toolbar, bd=0, highlightthickness=1,
                                  highlightbackground=UI_BORDER, highlightcolor=UI_BORDER)
        notation_frame.pack(side=tk.LEFT, padx=(0, 10))

        btn_font = ('TkDefaultFont', 10)
        self.american_btn = tk.Button(notation_frame, text="AB", font=btn_font,
                                      width=3, height=1, relief=tk.FLAT, bd=0,
                                      highlightthickness=0, cursor='hand2',
                                      command=lambda: self.set_notation('american'))
        self.american_btn.pack(side=tk.LEFT)
        self.create_tooltip(self.american_btn, "American notation (C, D, E...)")

        self.european_btn = tk.Button(notation_frame, text="Do", font=btn_font,
                                      width=3, height=1, relief=tk.FLAT, bd=0,
                                      highlightthickness=0, cursor='hand2',
                                      command=lambda: self.set_notation('european'))
        self.european_btn.pack(side=tk.LEFT)
        self.create_tooltip(self.european_btn, "European notation (Do, Re, Mi...)")

        # Update button appearance based on current selection
        self.update_notation_buttons()

        # Speed (BPM and multiplier)
        self._toolbar_separator()
        ttk.Label(self.toolbar, text="Speed", style='Muted.TLabel').pack(side=tk.LEFT, padx=(0, 6))

        self.bpm_scrubber = self._make_scrubber(
            BPM_SCALE, format_bpm, parse_bpm, self._on_bpm_scrubber_change, width=4)
        self.bpm_scrubber.pack(side=tk.LEFT)
        self.create_tooltip(self.bpm_scrubber, "Beats per minute. Drag to change, click to type, middle-click to reset to 120. Read-only during playback.")
        self.bpm_unit_label = ttk.Label(self.toolbar, text="bpm")
        self.bpm_unit_label.pack(side=tk.LEFT, padx=(1, 6))

        ttk.Label(self.toolbar, text="×", style='Muted.TLabel').pack(side=tk.LEFT, padx=(2, 6))

        self.multiplier_scrubber = self._make_scrubber(
            MULTIPLIER_SCALE, format_multiplier_pct, parse_multiplier_pct,
            self._on_multiplier_scrubber_change, width=5)
        self.multiplier_scrubber.pack(side=tk.LEFT)
        self.create_tooltip(self.multiplier_scrubber, "Speed multiplier applied on top of BPM. Middle-click to reset to 100%. Adjustable during playback.")
        self.multiplier_unit_label = ttk.Label(self.toolbar, text="%")
        self.multiplier_unit_label.pack(side=tk.LEFT, padx=(1, 0))

        # Key selector
        self._toolbar_separator()
        ttk.Label(self.toolbar, text="Key", style='Muted.TLabel').pack(side=tk.LEFT, padx=(0, 6))
        self.key_var = tk.StringVar()
        self.key_combo = ttk.Combobox(self.toolbar, textvariable=self.key_var,
                                      state='readonly', width=5)
        self.key_combo.pack(side=tk.LEFT)
        # Only a user's pick is sent; the session's state sets the variable.
        self.key_combo.bind('<<ComboboxSelected>>', self.on_key_change)
        self.create_tooltip(self.key_combo, "Key signature for roman numeral chords")

        # Time signature control
        self._toolbar_separator()
        ttk.Label(self.toolbar, text="Time", style='Muted.TLabel').pack(side=tk.LEFT, padx=(0, 6))
        self.time_sig_beats_var = tk.IntVar(value=4)
        self.time_sig_beats_spin = ttk.Spinbox(self.toolbar, from_=1, to=16,
                                               textvariable=self.time_sig_beats_var,
                                               width=3, command=self.on_time_signature_change)
        self.time_sig_beats_spin.pack(side=tk.LEFT)
        self.create_tooltip(self.time_sig_beats_spin, "Beats per measure")

        ttk.Label(self.toolbar, text="/", style='Muted.TLabel').pack(side=tk.LEFT, padx=3)

        self.time_sig_unit_var = tk.IntVar(value=4)
        self.time_sig_unit_spin = ttk.Spinbox(self.toolbar, values=(1, 2, 4, 8, 16),
                                              textvariable=self.time_sig_unit_var,
                                              width=3, command=self.on_time_signature_change)
        self.time_sig_unit_spin.pack(side=tk.LEFT)
        self.create_tooltip(self.time_sig_unit_spin, "Beat unit (4 = quarter note)")

        # Cache icons up front so PhotoImage refs survive
        ICON_SIZE = 24
        # Pastel tints — actions get a friendly color hint
        PLAY_GREEN = (95, 175, 99)
        PAUSE_BLUE = (88, 140, 199)
        STOP_CORAL = (240, 128, 128)
        METRONOME_OFF = (140, 140, 140)
        METRONOME_ON = (217, 102, 64)  # warm amber when armed
        self._icon_play = self._icons.load('resources/icons/play.png', ICON_SIZE, PLAY_GREEN)
        self._icon_pause = self._icons.load('resources/icons/pause.png', ICON_SIZE, PAUSE_BLUE)
        self._icon_stop = self._icons.load('resources/icons/stop.png', ICON_SIZE, STOP_CORAL)
        self._icon_metronome_off = self._icons.load('resources/icons/metronome.png', ICON_SIZE, METRONOME_OFF)
        self._icon_metronome_on = self._icons.load('resources/icons/metronome.png', ICON_SIZE, METRONOME_ON)

        # Metronome toggle
        self._toolbar_separator()
        self.metronome_button = self._make_icon_button(
            self.toolbar, self._icon_metronome_off, command=self._on_metronome_toggle)
        self.metronome_button.pack(side=tk.LEFT)
        self.create_tooltip(self.metronome_button, "Click track during playback. Toggle this on, then press Play.")

        # Playback buttons
        self._toolbar_separator()

        playback_frame = tk.Frame(self.toolbar, bg=self._ui_bg)
        playback_frame.pack(side=tk.LEFT)

        self.play_pause_button = self._make_icon_button(playback_frame, self._icon_play)
        self.play_pause_button.pack(side=tk.LEFT, padx=(0, 2))
        self.play_pause_button.bind('<Button-1>', self.on_play_pause_click)
        self._play_pause_tooltip = create_tooltip(
            self.play_pause_button, _PLAY_PAUSE_TOOLTIPS[PlayAction.PLAY])

        self.stop_button = self._make_icon_button(
            playback_frame, self._icon_stop, command=self.stop_playback)
        self.stop_button.pack(side=tk.LEFT)
        self.create_tooltip(self.stop_button, "Stop playback")

    def _make_scrubber(self, scale: ScrubScale, formatter: Any, parser: Any,
                       on_change: Any, width: int) -> Scrubber:
        """A toolbar scrubber on ``scale`` (the session snaps values the same way)."""
        return Scrubber(
            self.toolbar,
            value=scale.default if scale.default is not None else scale.min_value,
            min_value=scale.min_value,
            max_value=scale.max_value,
            step=scale.step,
            drag_step=scale.drag_step,
            snap_tolerance=scale.snap_tolerance,
            formatter=formatter,
            parser=parser,
            on_change=on_change,
            width=width,
            default_value=scale.default,
        )

    def _toolbar_separator(self) -> None:
        """Add a vertical divider between toolbar groups."""
        ttk.Separator(self.toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=2)

    def _make_icon_button(self, parent: tk.Widget, image: Any,
                          command: Optional[Any] = None) -> tk.Button:
        """Create a flat toolbar icon button that highlights on hover.

        The color it returns to after hover is kept in ``_rest_bg`` so toggle
        buttons (the metronome) can change their resting tint.
        """
        button = tk.Button(
            parent, image=image, command=command, relief=tk.FLAT, bd=0,
            highlightthickness=0, padx=6, pady=4, cursor='hand2',
            bg=self._ui_bg, activebackground=UI_HOVER,
        )
        button._rest_bg = self._ui_bg
        button.bind('<Enter>', lambda _e: button.config(bg=UI_HOVER), add='+')
        button.bind('<Leave>', lambda _e: button.config(bg=button._rest_bg), add='+')
        return button

    def create_text_editor(self) -> None:
        """Create text editor widget"""
        # Vertical paned window so the chord-sheet strip can dock under the
        # editor with a user-draggable divider.
        self.content_paned = ttk.PanedWindow(self, orient=tk.VERTICAL)
        self.content_paned.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 4))

        # Frame for text editor and scrollbar (top pane). It draws the editor's
        # 1px border, which turns accent-colored while the editor has focus.
        editor_frame = tk.Frame(self.content_paned, bd=0, highlightthickness=1,
                                highlightbackground=UI_BORDER, highlightcolor=UI_BORDER)
        self.content_paned.add(editor_frame, weight=3)

        # Scrollbar
        scrollbar = ttk.Scrollbar(editor_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Text editor (paints the session's highlighting)
        self.text_editor = ChordTextEditor(
            editor_frame,
            session=self.session,
            yscrollcommand=scrollbar.set,
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
            padx=6,
            pady=4,
        )
        self.text_editor.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.text_editor.yview)
        self.text_editor.bind(
            '<FocusIn>', lambda _e: editor_frame.config(highlightbackground=UI_ACCENT), add='+')
        self.text_editor.bind(
            '<FocusOut>', lambda _e: editor_frame.config(highlightbackground=UI_BORDER), add='+')

        # Apply font settings
        self.apply_font()

    def create_statusbar(self) -> None:
        """Create status bar"""
        status_frame = ttk.Frame(self)
        # Packed ahead of the editor pane: pack hands out space in packing
        # order, so a window shorter than the content would otherwise squeeze
        # the status bar to nothing.
        status_frame.pack(side=tk.BOTTOM, fill=tk.X, before=self.content_paned)
        ttk.Separator(status_frame, orient=tk.HORIZONTAL).pack(side=tk.TOP, fill=tk.X)
        self.statusbar = ttk.Label(status_frame, text="Ready", anchor=tk.W, style='Status.TLabel')
        self.statusbar.pack(side=tk.TOP, fill=tk.X)

    def create_chord_sheet(self) -> None:
        """Create the chord-sheet strip and dock it under the editor.

        The panel is added to the content paned window only while the
        session's ChordSheetState says it is visible (hidden = removed from
        the pane, not just blanked). The session feeds it the parsed song and
        moves its playhead; the window persists its height on sash drags.
        """
        if not self.session.has_chord_sheet:
            return

        from ui.chord_sheet.panel import ChordSheetPanel

        # The panel paints the strip's rendered song (the one read it still
        # makes past the session, see ui/chord_sheet/panel.py); its zoom, tab
        # and click commands go through the session.
        self.chord_sheet_panel = ChordSheetPanel(self.content_paned, session=self.session)

        # Persist the strip height whenever the sash is released.
        self.content_paned.bind('<ButtonRelease-1>', self._on_content_sash_moved)

        # Visibility comes with the session's ChordSheetState.

    def _apply_chord_sheet(self, state: ChordSheetState) -> None:
        """Show or hide the strip pane and keep the View menu check in step."""
        self._chord_sheet_state = state
        if self._chord_sheet_var.get() != state.visible:
            self._chord_sheet_var.set(state.visible)
        if state.visible:
            self._show_chord_sheet_pane()
        else:
            self._hide_chord_sheet_pane()

    def _show_chord_sheet_pane(self) -> None:
        """Insert the chord-sheet panel as the bottom pane if not present."""
        if self.chord_sheet_panel is None:
            return
        panes = self.content_paned.panes()
        if str(self.chord_sheet_panel) in panes:
            return
        self.content_paned.add(self.chord_sheet_panel, weight=1)
        # Position the sash so the strip gets its persisted height.
        self.after(50, self._apply_saved_chord_sheet_height)

    def _hide_chord_sheet_pane(self) -> None:
        """Remove the chord-sheet panel from the paned window."""
        if self.chord_sheet_panel is None:
            return
        if str(self.chord_sheet_panel) in self.content_paned.panes():
            self.content_paned.forget(self.chord_sheet_panel)

    def _apply_saved_chord_sheet_height(self) -> None:
        """Move the sash so the strip matches its persisted height."""
        state = self._chord_sheet_state
        if state is None or self.chord_sheet_panel is None:
            return
        if str(self.chord_sheet_panel) not in self.content_paned.panes():
            return
        try:
            total = self.content_paned.winfo_height()
            sash_y = max(0, total - state.height)
            self.content_paned.sashpos(0, sash_y)
        except Exception as e:
            logger.debug(f"Could not apply chord-sheet height: {e}")

    def _on_content_sash_moved(self, _event: Any) -> None:
        """Persist the chord-sheet height after a sash drag."""
        if self.chord_sheet_panel is None:
            return
        if str(self.chord_sheet_panel) not in self.content_paned.panes():
            return
        height = self.chord_sheet_panel.winfo_height()
        if height > 1:
            self.session.set_chord_sheet_height(height)

    def toggle_chord_sheet(self) -> None:
        """Toggle chord-sheet visibility (View menu checkbutton command)."""
        self.session.set_chord_sheet_visible(self._chord_sheet_var.get())

    # -- documents: the session runs the flows, the window presents requests --

    def _send_text(self) -> None:
        """Make sure the session has the editor's text (a no-op unless an
        edit's <<Modified>> is still queued)."""
        self.session.set_text(self.text_editor.get_text())

    def new_file(self) -> None:
        """File > New."""
        self._send_text()
        self.session.new_document()

    def open_file(self) -> None:
        """File > Open..."""
        self._send_text()
        self.session.open_document()

    def save_file(self) -> None:
        """File > Save."""
        self._send_text()
        self.session.save()

    def save_file_as(self) -> None:
        """File > Save As..."""
        self._send_text()
        self.session.save_as()

    def export_midi(self) -> None:
        """File > Export MIDI..."""
        self._send_text()
        self.session.export_midi()

    def _open_recent(self, ref: Any) -> None:
        """File > Recent Files > a document."""
        self._send_text()
        self.session.open_recent(ref)

    def _present_confirm_discard(self, request: ConfirmDiscardRequest) -> None:
        """Ask whether to save the unsaved changes; answer the session."""
        response = messagebox.askyesnocancel(
            formatting.CONFIRM_DISCARD_TITLE,
            formatting.CONFIRM_DISCARD_MESSAGE,
            parent=self,
        )
        if response is None:
            choice = DiscardChoice.CANCEL
        else:
            choice = DiscardChoice.SAVE if response else DiscardChoice.DISCARD
        self.session.respond(request.request_id, choice.value)

    def _present_pick_document(self, request: PickDocumentRequest) -> None:
        """Show the native file picker; answer the session with a ref or None."""
        if request.mode is PickMode.OPEN:
            filename = ask_open_filename(self, title="Open File", filetypes=_TEXT_FILE_TYPES)
        else:
            title, extension, filetypes = _PICKERS[request.mode]
            # A name with its extension: the Flatpak's portal dialog only
            # grants access to the exact name chosen.
            filename = ask_save_as_filename(
                self,
                title=title,
                defaultextension=extension,
                filetypes=filetypes,
                initialfile=request.suggested_name,
            )
        ref = self.session.document_ref(filename) if filename else None
        self.session.respond(request.request_id, ref)

    def select_all(self) -> str:
        """Select all text"""
        self.text_editor.tag_add(tk.SEL, "1.0", tk.END)
        self.text_editor.mark_set(tk.INSERT, "1.0")
        self.text_editor.see(tk.INSERT)
        return 'break'

    def choose_font(self) -> None:
        """Open font selection dialog"""
        dialog = tk.Toplevel(self)
        dialog.title("Choose Font")
        dialog.geometry("400x200")
        dialog.transient(self)
        dialog.grab_set()

        # Get available fonts
        families = sorted(list(tkfont.families()))
        current_family, current_size = self._editor_font()

        # Font family selection
        ttk.Label(dialog, text="Font Family:").pack(pady=(10, 5))
        font_var = tk.StringVar(value=current_family)
        font_combo = ttk.Combobox(dialog, textvariable=font_var, values=families,
                                  state='readonly', width=40)
        font_combo.pack(padx=20, pady=5)

        # Font size selection
        ttk.Label(dialog, text="Font Size:").pack(pady=(10, 5))
        size_var = tk.IntVar(value=current_size)
        sizes = list(range(6, 73))  # 6 to 72
        size_combo = ttk.Combobox(dialog, textvariable=size_var, values=sizes,
                                  state='readonly', width=10)
        size_combo.pack(pady=5)

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=15)

        def on_ok() -> None:
            self.session.set_font(font_var.get(), size_var.get())
            dialog.destroy()

        def on_cancel() -> None:
            dialog.destroy()

        ttk.Button(button_frame, text="OK", command=on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=on_cancel).pack(side=tk.LEFT, padx=5)

        # Center the dialog
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - (dialog.winfo_width() // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")

    def increase_font_size(self) -> None:
        """Increase font size"""
        self.session.step_font_size(1)

    def decrease_font_size(self) -> None:
        """Decrease font size"""
        self.session.step_font_size(-1)

    def reset_font_size(self) -> None:
        """Reset font size to default"""
        self.session.reset_font_size()

    def on_mouse_wheel_zoom(self, event: Any) -> None:
        """Handle Ctrl+MouseWheel for zooming"""
        self.session.step_font_size(1 if event.delta > 0 else -1)

    def set_notation(self, notation: str) -> None:
        """Detect chords in ``notation`` (a notation button)."""
        self.session.set_notation(notation)

    def update_notation_buttons(self) -> None:
        """Update toggle button appearance based on selected notation"""
        current = self._notation
        selected, other = ((self.american_btn, self.european_btn) if current == 'american'
                           else (self.european_btn, self.american_btn))
        selected.config(bg=UI_ACCENT, fg='white', activebackground=UI_ACCENT_ACTIVE,
                        activeforeground='white')
        other.config(bg=self._ui_bg, fg='black', activebackground=UI_HOVER,
                     activeforeground='black')

    def _editor_font(self) -> tuple:
        """The configured editor font as ``(family, size)`` (from EditorState)."""
        state = self._editor_state
        if state is None:
            return ("TkFixedFont", DEFAULT_FONT_SIZE)
        return (state.font_family, state.font_size)

    def apply_font(self) -> None:
        """Apply font settings to text editor"""
        family, size = self._editor_font()
        self.text_editor.configure(font=(resolve_font_family(self.text_editor, family), size))

    def on_text_modified(self, event: Optional[Any] = None) -> None:
        """Send the edited text to the session (which re-detects after a pause)."""
        if self.text_editor.edit_modified():
            self.session.set_text(self.text_editor.get_text())
            self.text_editor.edit_modified(False)

    def _on_bpm_scrubber_change(self, value: float) -> None:
        """Handle BPM scrubber change."""
        self.session.set_bpm(value)

    def _on_multiplier_scrubber_change(self, value_pct: float) -> None:
        """Handle multiplier scrubber change (input is a percentage)."""
        self.session.set_multiplier_pct(value_pct)

    def _on_metronome_toggle(self) -> None:
        self.session.toggle_metronome()

    def _refresh_metronome_button(self, enabled: bool) -> None:
        """Tint the metronome button while the click track is on."""
        if enabled:
            rest_bg = "#ffe4cf"  # warm tint matching the on-icon
            image = self._icon_metronome_on
        else:
            rest_bg = self._ui_bg
            image = self._icon_metronome_off
        self.metronome_button._rest_bg = rest_bg
        self.metronome_button.config(image=image, background=rest_bg)

    def on_key_change(self, *args: Any) -> None:
        """The user picked a key in the toolbar."""
        self.session.set_key(self.key_var.get() or None)

    def on_time_signature_change(self) -> None:
        """The user stepped a time-signature spinbox."""
        self.session.set_time_signature(self.time_sig_beats_var.get(),
                                        self.time_sig_unit_var.get())

    def on_voicing_change(self) -> None:
        """The user picked a voicing in the menu."""
        self.session.set_voicing(self.voicing_var.get())

    def rebuild_voicing_menu(self, state: VoicingMenuState) -> None:
        """Show the session's Voicing menu: rebuilt when its choices changed
        (Settings edited the voicings), else only the selection moves."""
        if state.groups != self._voicing_groups:
            self._voicing_groups = state.groups
            self.voicing_menu.delete(0, tk.END)
            for index, group in enumerate(state.groups):
                if index:
                    self.voicing_menu.add_separator()
                for item in group:
                    self.voicing_menu.add_radiobutton(
                        label=item.label, variable=self.voicing_var, value=item.value,
                        command=self.on_voicing_change)
        self.voicing_var.set(state.selected)
        # Locked while a song plays (it is rendered up front); pausing unlocks.
        self._playback_menu.entryconfigure(
            "Voicing", state=tk.DISABLED if state.locked_reason else tk.NORMAL)

    def on_instrument_change(self) -> None:
        """The user picked an instrument in the menu."""
        self.session.set_instrument(self.instrument_var.get())

    def build_instrument_menu(self, state: InstrumentMenuState) -> None:
        """Rebuild the Instrument menu from the session's state (one submenu
        per General MIDI family, the current one marked)."""
        self.instrument_menu.delete(0, tk.END)
        for child in self.instrument_menu.winfo_children():
            child.destroy()  # the previous family submenus

        # Same-size marker images keep the family names aligned whether or not
        # they carry the current-instrument dot (text bullets vary in width).
        if not hasattr(self, '_category_markers'):
            self._category_markers = (self._make_menu_marker(False),
                                      self._make_menu_marker(True))

        for family in state.families:
            category_menu = tk.Menu(self.instrument_menu, tearoff=0)
            for item in family.items:
                category_menu.add_radiobutton(
                    label=item.label,
                    variable=self.instrument_var,
                    value=int(item.value),
                    command=self.on_instrument_change,
                )
            style_menu(category_menu)  # built after startup's styling pass
            self.instrument_menu.add_cascade(
                label=family.name, menu=category_menu,
                image=self._category_markers[family.is_current], compound=tk.LEFT,
            )
        self.instrument_var.set(state.current)

    def _make_menu_marker(self, filled: bool, width: int = 20, height: int = 14) -> tk.PhotoImage:
        """Return a menu-entry marker: a small dot, or a blank of the same size."""
        image = tk.PhotoImage(master=self, width=width, height=height)
        if filled:
            cx, cy = (width - 1) / 2, (height - 1) / 2
            radius = 3.5
            for y in range(height):
                for x in range(width):
                    if (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2:
                        image.put('#333333', (x, y))
        return image

    def _apply_recent_documents(self, state: RecentDocumentsState) -> None:
        """Rebuild File > Recent Files."""
        self.recent_menu.delete(0, tk.END)
        if not state.items:
            self.recent_menu.add_command(label="(No recent files)", state=tk.DISABLED)
        else:
            for ref in state.items:
                self.recent_menu.add_command(
                    label=ref.display_name,
                    command=lambda r=ref: self._open_recent(r)
                )

    def on_close(self) -> None:
        """The window's close button, File > Exit, Ctrl+Q: ask the session.

        It asks about unsaved changes and answers with CloseApproved, which
        closes the window (:meth:`_close_window`).
        """
        self._send_text()
        self.session.request_close()

    def _close_window(self) -> None:
        """Tear the window down (the session approved).

        Destroying the root ends the main loop; the application then shuts
        the session and the services down and saves the config.
        """
        if self._closing:
            return  # a second approval queued before the first ran
        self._closing = True
        # Save window geometry before closing
        self.session.set_window_geometry(self.geometry())
        # Persist the chord-sheet height while the pane still exists
        self._on_content_sash_moved(None)
        # Stop playback
        self.session.stop()
        self._session_subscription.cancel()
        self.destroy()

    def create_tooltip(self, widget: tk.Widget, text: str) -> None:
        """Create a tooltip for a widget using ui_helpers.create_tooltip"""
        create_tooltip(widget, text)

    def open_chord_identifier(self) -> None:
        """Open the chord identifier window (with a model of its own)."""
        ChordIdentifierWindow(
            self,
            self.session.chord_identifier_model(),
            on_insert_chord=self._on_insert_chord_from_identifier,
            on_audio_error=self._on_identifier_audio_error,
        )

    def _on_identifier_audio_error(self, error: BaseException) -> None:
        """Report the identifier's audio failure by the session's click policy."""
        self.session.report_audio_failure(str(error), from_click=True)

    def _on_insert_chord_from_identifier(self, chord_name: str) -> None:
        """Handle chord insertion from chord identifier.

        Args:
            chord_name: Chord name to insert
        """
        try:
            # Make sure the session's copy matches the widget before splicing
            # (a no-op unless an edit's <<Modified>> is still queued).
            self.session.set_text(self.text_editor.get_text())
            # The session inserts it into the editor and says so (refused
            # while playing).
            self.session.insert_chord(self.text_editor.offset_of(tk.INSERT), chord_name)
            self.text_editor.focus_set()
        except Exception as e:
            logger.error(f"Error inserting chord: {e}", exc_info=True)
            messagebox.showerror("Error", f"Could not insert the chord {chord_name}.\n\n{e}", parent=self)

    def show_help(self) -> None:
        """Show the help window with user documentation."""
        from ui.help_window import show_help
        docs_path = self.resource_service.get_resource_path('help/build/html')
        try:
            show_help(docs_path)
        except ChordNotepadError as e:
            messagebox.showwarning("Help Unavailable", str(e), parent=self)

    def show_quick_start(self) -> None:
        """Show the Quick Start dialog."""
        from ui.dialogs import QuickStartDialog
        family, size = self._editor_font()
        editor_font = (resolve_font_family(self.text_editor, family), size)
        # The snippets are display only: the dialog highlights them itself.
        dialog = QuickStartDialog(self, editor_font=editor_font,
                                  resource_service=self.resource_service)
        self.wait_window(dialog)

        # Update config if user chose not to show again
        if dialog.get_dont_show_again():
            self.session.set_show_quick_start_on_startup(False)

    def show_options(self) -> None:
        """Show the Settings dialog; the session applies what it saved."""
        dialog = OptionsDialog(self, self.session.settings_model(),
                               on_apply=self.session.apply_settings)
        self.wait_window(dialog)

    def show_about(self) -> None:
        """Show About dialog with version information"""
        about_dialog = tk.Toplevel(self)
        about_dialog.title("About Chord Notepad")
        about_dialog.geometry("450x400")
        about_dialog.transient(self)
        about_dialog.grab_set()
        about_dialog.resizable(False, False)

        # Main frame with padding
        main_frame = ttk.Frame(about_dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # App icon
        try:
            icon_path = self.resource_service.get_resource_path('resources/icon-128.png')
            if os.path.exists(icon_path):
                icon_img = Image.open(icon_path)
                icon_photo = ImageTk.PhotoImage(icon_img)
                icon_label = tk.Label(main_frame, image=icon_photo)
                icon_label.image = icon_photo  # Keep a reference
                icon_label.pack(pady=(0, 10))
        except Exception as e:
            logger.warning(f"Could not load About icon: {e}")

        # App title
        title_label = tk.Label(main_frame, text="Chord Notepad",
                              font=('TkDefaultFont', 16, 'bold'))
        title_label.pack(pady=(0, 10))

        # Version info
        version_frame = ttk.Frame(main_frame)
        version_frame.pack(pady=10, fill=tk.X)

        info_lines = [
            ("Version:", VERSION),
            ("Build Type:", BUILD_TYPE),
            ("Build Number:", BUILD_NUMBER),
            ("Commit:", COMMIT_SHORT),
            ("Build Date:", BUILD_DATE),
        ]

        for label, value in info_lines:
            row = ttk.Frame(version_frame)
            row.pack(fill=tk.X, pady=2)
            ttk.Label(row, text=label, font=('TkDefaultFont', 9, 'bold')).pack(side=tk.LEFT)
            ttk.Label(row, text=value, font=('TkDefaultFont', 9)).pack(side=tk.LEFT, padx=(5, 0))

        # Description
        desc_label = tk.Label(main_frame,
                             text="A simple text editor for musicians with\nchord detection and playback",
                             font=('TkDefaultFont', 9),
                             justify=tk.CENTER)
        desc_label.pack(pady=15)

        # Copyright
        copyright_label = tk.Label(main_frame,
                                  text="© 2025–2026 Tiberiu Chibici\nGNU AGPL-3.0 · github.com/chibicitiberiu/chord-notepad",
                                  font=('TkDefaultFont', 8),
                                  fg='gray')
        copyright_label.pack(pady=5)

        # Close button
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=(15, 0))
        ttk.Button(button_frame, text="Close", command=about_dialog.destroy).pack()

        # Center the dialog
        about_dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - (about_dialog.winfo_width() // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (about_dialog.winfo_height() // 2)
        about_dialog.geometry(f"+{x}+{y}")

    def convert_to_american(self) -> None:
        """Convert all chords in the text to American notation"""
        self.session.set_text(self.text_editor.get_text())
        self.session.convert_notation(Notation.AMERICAN.value)

    def convert_to_european(self) -> None:
        """Convert all chords in the text to European notation"""
        self.session.set_text(self.text_editor.get_text())
        self.session.convert_notation(Notation.EUROPEAN.value)

    def open_transpose_dialog(self) -> None:
        """Open the Transpose dialog; the session applies it as one undo step."""
        region = self._selection_char_range()

        dialog = TransposeDialog(self, has_selection=region is not None)
        self.wait_window(dialog)

        if dialog.result is None or dialog.result == 0:
            return

        self.session.set_text(self.text_editor.get_text())
        self.session.transpose(dialog.result, region)

    def open_suggest_capo_dialog(self) -> None:
        """Suggest a capo for a chosen voicing and insert a {capo} directive.

        The session asks which fretboard voicing to optimize for (a
        :class:`CapoChoiceRequest`, presented by :meth:`_present_capo_request`),
        scores the selection (or whole song), and inserts a ``{capo: N}``
        directive as one undo step -- or reports that no capo helps.
        """
        region = self._selection_char_range()
        self.session.set_text(self.text_editor.get_text())
        self.session.request_suggest_capo(region)

    def _present_capo_request(self, request: CapoChoiceRequest) -> None:
        """Show the Suggest Capo dialog and answer the session's request."""
        labels = [option.label for option in request.options]
        default_label = next(
            (o.label for o in request.options if o.value == request.default),
            labels[0] if labels else "",
        )
        dialog = CapoDialog(self, labels, default_label)
        self.wait_window(dialog)
        value = next((o.value for o in request.options if o.label == dialog.result), None)
        self.session.respond(request.request_id, value)

    def _selection_char_range(self) -> Optional[tuple]:
        """Return the current selection as a (start, end) character range.

        Returns None when there is no active selection.
        """
        try:
            if not self.text_editor.tag_ranges(tk.SEL):
                return None
            start = self.text_editor.count("1.0", tk.SEL_FIRST, "chars")[0]
            end = self.text_editor.count("1.0", tk.SEL_LAST, "chars")[0]
        except (tk.TclError, TypeError, IndexError):
            return None
        if end <= start:
            return None
        return (start, end)

    def on_chord_click(self, event: Any) -> None:
        """A click in the editor plays the chord under the pointer, if any."""
        self.session.tap_chord_at(self.text_editor.offset_at(event.x, event.y))

    def on_play_pause_click(self, event: Any) -> None:
        """Play/Pause: play from the start, pause, or resume.

        Shift+click while idle plays from the cursor instead.
        """
        # Make sure the session plays the text in the widget.
        self.session.set_text(self.text_editor.get_text())
        shift_held = event.state & 0x1
        from_offset = self.text_editor.offset_of(tk.INSERT) if shift_held else None
        self.session.play_pause(from_offset)

    def stop_playback(self) -> None:
        """Stop playback"""
        self.session.stop()

    def insert_bpm(self) -> None:
        """Open dialog to insert a BPM/Tempo change directive"""
        self._request_directive("bpm")

    def insert_time_signature(self) -> None:
        """Open dialog to insert a Time Signature change directive"""
        self._request_directive("time")

    def insert_key(self) -> None:
        """Open dialog to insert a Key change directive"""
        self._request_directive("key")

    def insert_label(self) -> None:
        """Open dialog to insert a Label directive"""
        self._request_directive("label")

    def insert_loop(self) -> None:
        """Open dialog to insert a Loop directive"""
        self._request_directive("loop")

    def _request_directive(self, kind: str) -> None:
        """Ask the session to insert a ``kind`` directive at the cursor."""
        self.session.set_text(self.text_editor.get_text())
        self.session.request_insert_directive(kind, self.text_editor.offset_of(tk.INSERT))

    def _present_directive_request(self, request: InsertDirectiveRequest) -> None:
        """Show the directive's dialog and answer the session's request."""
        dialog = dialog_for_request(self, request)
        self.wait_window(dialog)
        self.session.respond(request.request_id, dialog.result)
        if dialog.result:
            self.text_editor.focus_set()
