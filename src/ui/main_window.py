"""
Main application window with text editor and menu bar
"""

import logging
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, font as tkfont
import os
from pathlib import Path
from typing import Any, Optional, List
from PIL import Image, ImageTk
from ui.text_editor import ChordTextEditor
from ui.chord_identifier import ChordIdentifierWindow
from ui.builders.menu_builder import MenuBuilder
from ui.dialogs import (
    InsertBpmDialog,
    InsertTimeSignatureDialog,
    InsertKeyDialog,
    InsertLabelDialog,
    InsertLoopDialog,
)
from utils.ui_helpers import create_tooltip
from utils.key_helpers import get_key_options
from models.notation import Notation

logger = logging.getLogger(__name__)

# Import build info (may be auto-generated during CI build)
try:
    from build_info import VERSION, BUILD_TYPE, COMMIT_SHORT, BUILD_DATE
except ImportError:
    VERSION = "dev-local"
    BUILD_TYPE = "development"
    COMMIT_SHORT = "unknown"
    BUILD_DATE = "unknown"


class MainWindow(tk.Tk):
    """Main application window"""

    def __init__(self, viewmodel: Any, text_editor_viewmodel: Any, application: Any, resource_service: Any) -> None:
        """Initialize the main window.

        Args:
            viewmodel: MainWindowViewModel for MVVM pattern
            text_editor_viewmodel: TextEditorViewModel
            application: Application instance for event queue access
            resource_service: ResourceService for resolving resource paths
        """
        super().__init__()

        # Store ViewModels and Services
        self.viewmodel = viewmodel
        self.text_editor_viewmodel = text_editor_viewmodel
        self.application = application
        self.resource_service = resource_service

        # Set up observers for ViewModel properties
        self._setup_viewmodel_observers()

        self.title("Chord Notepad")
        self.geometry("900x600")

        # Set window icon
        self._set_window_icon()

        # Apply saved window geometry
        saved_geometry = self.viewmodel.get_window_geometry()
        if saved_geometry:
            self.geometry(saved_geometry)

        # Create UI components (text editor first so menu can reference it)
        self.create_text_editor()
        self.create_menu()
        self.create_toolbar()
        self.create_statusbar()

        # Repack toolbar at the top (after menu bar)
        self.toolbar.pack_forget()
        self.toolbar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5, before=self.text_editor.master)

        # Bind events
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.bind("<Control-MouseWheel>", self.on_mouse_wheel_zoom)

        # Track modifications
        self.text_editor.bind("<<Modified>>", self.on_text_modified)

        # Make chords clickable
        self.text_editor.bind("<Button-1>", self.on_chord_click)

    def show_quick_start_if_needed(self) -> None:
        """Show the Quick Start dialog if this is the first run."""
        if self.viewmodel.get_show_quick_start_on_startup():
            # Use after() to show the dialog after the main window is fully displayed
            self.after(100, self.show_quick_start)

    def _setup_viewmodel_observers(self) -> None:
        """Set up observers for ViewModel property changes."""
        # Font size changes
        self.viewmodel.observe('font_size', self._on_font_size_changed)

        # Notation changes
        self.viewmodel.observe('notation', self._on_notation_changed)

        # File state changes
        self.viewmodel.observe('current_file', self._on_current_file_changed)
        self.viewmodel.observe('is_modified', self._on_is_modified_changed)

        # Playback state changes
        self.viewmodel.observe('is_playing', self._on_is_playing_changed)
        self.viewmodel.observe('is_paused', self._on_is_paused_changed)

        # BPM changes
        self.viewmodel.observe('bpm', self._on_bpm_changed)

        # Key and time signature changes
        self.viewmodel.observe('key', self._on_key_changed)
        self.viewmodel.observe('time_signature_beats', self._on_time_signature_changed)
        self.viewmodel.observe('time_signature_unit', self._on_time_signature_changed)

        # Text content changes
        self.viewmodel.observe('current_text', self._on_current_text_changed)

        # Playback event changes
        self.viewmodel.observe('current_playback_event', self._on_playback_event_changed)

    # ViewModel observer callbacks

    def _on_font_size_changed(self, new_value: int) -> None:
        """React to font size changes from ViewModel."""
        self.apply_font()

    def _on_notation_changed(self, new_value: Notation) -> None:
        """React to notation changes from ViewModel."""
        from chord.converter import NotationConverter

        # Convert Notation enum to string value for UI components
        notation_str = new_value.value
        self.notation_var.set(notation_str)
        self.update_notation_buttons()
        self.text_editor.set_notation(notation_str)

        # Convert current key to new notation
        current_key = self.key_var.get()
        if current_key:
            if new_value == Notation.EUROPEAN:
                # Converting to European
                converted_key = NotationConverter.american_to_european(current_key)
            else:
                # Converting to American
                converted_key = NotationConverter.european_to_american(current_key)
            self.key_var.set(converted_key)

        # Update key options based on new notation
        self.key_combo['values'] = get_key_options(new_value)

    def _on_current_file_changed(self, new_value: Optional[Path]) -> None:
        """React to current file changes from ViewModel."""
        self.title(self.viewmodel.get_window_title())

    def _on_is_modified_changed(self, new_value: bool) -> None:
        """React to modification state changes from ViewModel."""
        self.title(self.viewmodel.get_window_title())

    def _on_is_playing_changed(self, new_value: bool) -> None:
        """React to playback state changes from ViewModel."""
        if new_value:
            # Playback started/resumed - show pause icon
            self.play_pause_button.config(text="⏸")
            self._update_play_pause_tooltip()
            # Lock editor during playback
            self.text_editor.config(state=tk.DISABLED)
        else:
            # Playback stopped (idle state) - show play icon
            self.play_pause_button.config(text="▶")
            self._update_play_pause_tooltip()
            # Unlock editor
            self.text_editor.config(state=tk.NORMAL)
            # Clear playing highlight
            self.text_editor.tag_remove('chord_playing', '1.0', tk.END)
            # Update statusbar
            self.update_statusbar("Ready")

    def _on_is_paused_changed(self, new_value: bool) -> None:
        """React to pause state changes from ViewModel."""
        if new_value:
            # Paused state - show play icon
            self.play_pause_button.config(text="▶")
            self._update_play_pause_tooltip()
        else:
            # Playing state (resumed or started) - show pause icon
            if self.viewmodel.is_playing:
                self.play_pause_button.config(text="⏸")
                self._update_play_pause_tooltip()

    def _update_play_pause_tooltip(self) -> None:
        """Update the Play/Pause button tooltip based on current state."""
        # Determine tooltip text based on state
        if self.viewmodel.is_playing and not self.viewmodel.is_paused:
            tooltip_text = "Pause playback"
        elif self.viewmodel.is_paused:
            tooltip_text = "Resume playback"
        else:
            tooltip_text = "Play from start (Shift+Click to play from cursor)"

        # Create tooltip on first call, update text on subsequent calls
        if not hasattr(self, '_play_pause_tooltip'):
            self._play_pause_tooltip = create_tooltip(self.play_pause_button, tooltip_text)
        else:
            # Just update the text attribute
            self._play_pause_tooltip.text = tooltip_text

    def _on_bpm_changed(self, new_value: int) -> None:
        """React to BPM changes from ViewModel."""
        self.bpm_label.config(text=f"{new_value} BPM")
        self.bpm_var.set(new_value)

    def _on_key_changed(self, new_value: Optional[str]) -> None:
        """React to key changes from ViewModel."""
        self.key_var.set(new_value or "")

    def _on_time_signature_changed(self, new_value: int) -> None:
        """React to time signature changes from ViewModel."""
        self.time_sig_beats_var.set(self.viewmodel.time_signature_beats)
        self.time_sig_unit_var.set(self.viewmodel.time_signature_unit)

    def _on_current_text_changed(self, new_value: str) -> None:
        """React to text content changes from ViewModel."""
        # Update text editor content
        self.text_editor.delete('1.0', tk.END)
        self.text_editor.insert('1.0', new_value)

    def _on_playback_event_changed(self, event_args: Optional[Any]) -> None:
        """React to playback event changes from ViewModel.

        Args:
            event_args: PlaybackEventArgs or None
        """
        from models.playback_event import PlaybackEventType

        # Temporarily enable editor to modify tags (disabled state prevents tag modifications)
        was_disabled = str(self.text_editor.cget('state')) == tk.DISABLED
        if was_disabled:
            self.text_editor.config(state=tk.NORMAL)

        # Clear previous playing highlight
        self.text_editor.tag_remove('chord_playing', '1.0', tk.END)

        if event_args is None:
            # Playback finished or stopped
            if was_disabled:
                self.text_editor.config(state=tk.DISABLED)
            self.update_statusbar("Ready")
            return

        # Highlight currently playing chord
        if event_args.event_type == PlaybackEventType.CHORD_START and event_args.chord_info:
            chord_info = event_args.chord_info
            start_idx = f"1.0 + {chord_info.start} chars"
            end_idx = f"1.0 + {chord_info.end} chars"
            self.text_editor.tag_add('chord_playing', start_idx, end_idx)

            # Raise the tag priority so it's visible over other tags
            self.text_editor.tag_raise('chord_playing')

            # Autoscroll to show the playing chord
            self.text_editor.see(start_idx)

            # Update statusbar with playback state
            status_parts = []
            status_parts.append(f"Bar {event_args.current_bar}/{event_args.total_bars}")
            status_parts.append(f"{event_args.bpm} BPM")
            status_parts.append(f"{event_args.time_signature_beats}/{event_args.time_signature_unit}")
            if event_args.key:
                status_parts.append(f"Key: {event_args.key}")
            status_parts.append(f"Playing: {chord_info.chord}")

            status_text = " | ".join(status_parts)
            self.update_statusbar(status_text)

        # Restore disabled state
        if was_disabled:
            self.text_editor.config(state=tk.DISABLED)

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
        # Create recent files submenu first
        self.recent_menu = tk.Menu(menubar, tearoff=0)
        self.update_recent_files_menu()

        file_menu = MenuBuilder(menubar) \
            .add_command("New", self.new_file, accelerator="Ctrl+N") \
            .add_command("Open...", self.open_file, accelerator="Ctrl+O") \
            .add_command("Save", self.save_file, accelerator="Ctrl+S") \
            .add_command("Save As...", self.save_file_as, accelerator="Ctrl+Shift+S") \
            .add_separator() \
            .build()

        file_menu.add_cascade(label="Recent Files", menu=self.recent_menu)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_close, accelerator="Ctrl+Q")

        menubar.add_cascade(label="File", menu=file_menu)

        # Edit menu
        edit_menu = MenuBuilder(menubar) \
            .add_command("Undo", self.text_editor.edit_undo, accelerator="Ctrl+Z") \
            .add_command("Redo", self.text_editor.edit_redo, accelerator="Ctrl+Y") \
            .add_separator() \
            .add_command("Cut", lambda: self.text_editor.event_generate("<<Cut>>"), accelerator="Ctrl+X") \
            .add_command("Copy", lambda: self.text_editor.event_generate("<<Copy>>"), accelerator="Ctrl+C") \
            .add_command("Paste", lambda: self.text_editor.event_generate("<<Paste>>"), accelerator="Ctrl+V") \
            .add_command("Select All", self.select_all, accelerator="Ctrl+A") \
            .build()
        menubar.add_cascade(label="Edit", menu=edit_menu)

        # View menu
        view_menu = MenuBuilder(menubar) \
            .add_command("Font...", self.choose_font) \
            .add_separator() \
            .add_command("Increase Font Size", self.increase_font_size, accelerator="Ctrl+Plus") \
            .add_command("Decrease Font Size", self.decrease_font_size, accelerator="Ctrl+Minus") \
            .add_command("Reset Font Size", self.reset_font_size, accelerator="Ctrl+0") \
            .build()
        menubar.add_cascade(label="View", menu=view_menu)

        # Playback menu
        self.voicing_var = tk.StringVar(value=self.viewmodel.get_voicing())

        # Create voicing submenu
        voicing_menu = tk.Menu(menubar, tearoff=0)
        voicing_menu.add_radiobutton(label="Piano", variable=self.voicing_var,
                                     value="piano", command=self.on_voicing_change)

        # Add guitar tunings
        voicing_menu.add_separator()
        voicing_menu.add_radiobutton(label="Guitar (Standard - EADGBE)", variable=self.voicing_var,
                                     value="guitar:standard", command=self.on_voicing_change)
        voicing_menu.add_radiobutton(label="Guitar (Drop D)", variable=self.voicing_var,
                                     value="guitar:drop_d", command=self.on_voicing_change)
        voicing_menu.add_radiobutton(label="Guitar (DADGAD)", variable=self.voicing_var,
                                     value="guitar:dadgad", command=self.on_voicing_change)
        voicing_menu.add_radiobutton(label="Guitar (Open G)", variable=self.voicing_var,
                                     value="guitar:open_g", command=self.on_voicing_change)

        # Add custom tunings if any
        custom_tunings = self.viewmodel.get_custom_tunings()
        if custom_tunings:
            voicing_menu.add_separator()
            for tuning_name in sorted(custom_tunings.keys()):
                label = f"Guitar ({tuning_name})"
                value = f"guitar:{tuning_name}"
                voicing_menu.add_radiobutton(label=label, variable=self.voicing_var,
                                           value=value, command=self.on_voicing_change)

        # Create instrument submenu with categories
        self.instrument_var = tk.IntVar(value=self.viewmodel.get_instrument())
        self.instrument_menu = tk.Menu(menubar, tearoff=0)
        self.build_instrument_menu()

        playback_menu = tk.Menu(menubar, tearoff=0)
        playback_menu.add_cascade(label="Voicing", menu=voicing_menu)
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
        tools_menu.add_command(label="Convert to American Notation", command=self.convert_to_american)
        tools_menu.add_command(label="Convert to European Notation", command=self.convert_to_european)

        menubar.add_cascade(label="Tools", menu=tools_menu)

        # Help menu
        help_menu = MenuBuilder(menubar) \
            .add_command("User Guide", self.show_help, accelerator="F1") \
            .add_command("Quick Start", self.show_quick_start) \
            .add_separator() \
            .add_command("About", self.show_about) \
            .build()
        menubar.add_cascade(label="Help", menu=help_menu)

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
        self.toolbar = ttk.Frame(self)
        self.toolbar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        # Notation selection with icon toggle buttons
        self.notation_var = tk.StringVar(value=self.viewmodel.notation.value)

        # Create toggle button frame
        notation_frame = tk.Frame(self.toolbar, relief=tk.SUNKEN, bd=1)
        notation_frame.pack(side=tk.LEFT, padx=(5, 15))

        btn_font = ('TkDefaultFont', 10)
        self.american_btn = tk.Button(notation_frame, text="AB", font=btn_font,
                                      width=2, height=1, relief=tk.FLAT, bd=0,
                                      command=lambda: self.set_notation('american'))
        self.american_btn.pack(side=tk.LEFT, padx=1, pady=1)
        self.create_tooltip(self.american_btn, "American notation (C, D, E...)")

        self.european_btn = tk.Button(notation_frame, text="Do", font=btn_font,
                                      width=2, height=1, relief=tk.FLAT, bd=0,
                                      command=lambda: self.set_notation('european'))
        self.european_btn.pack(side=tk.LEFT, padx=1, pady=1)
        self.create_tooltip(self.european_btn, "European notation (Do, Re, Mi...)")

        # Update button appearance based on current selection
        self.update_notation_buttons()

        # BPM control
        ttk.Separator(self.toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        ttk.Label(self.toolbar, text="BPM:").pack(side=tk.LEFT, padx=5)
        self.bpm_var = tk.IntVar(value=self.viewmodel.bpm)
        self.bpm_slider = ttk.Scale(self.toolbar, from_=60, to=240,
                                    variable=self.bpm_var, orient=tk.HORIZONTAL, length=150)
        self.bpm_slider.pack(side=tk.LEFT, padx=5)
        self.bpm_label = ttk.Label(self.toolbar, text=f"{self.bpm_var.get()} BPM")
        self.bpm_label.pack(side=tk.LEFT)
        self.bpm_var.trace_add('write', self.on_bpm_change)

        # Key selector
        ttk.Separator(self.toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        ttk.Label(self.toolbar, text="Key:").pack(side=tk.LEFT, padx=(5, 2))
        # Get default key based on current notation
        default_key = self.viewmodel.key or ("Do" if self.viewmodel.notation == Notation.EUROPEAN else "C")
        self.key_var = tk.StringVar(value=default_key)
        # Key options will be set based on notation
        self.key_combo = ttk.Combobox(self.toolbar, textvariable=self.key_var,
                                      values=get_key_options(self.viewmodel.notation), state='readonly', width=5)
        self.key_combo.pack(side=tk.LEFT, padx=(0, 5))
        self.key_var.trace_add('write', self.on_key_change)
        self.create_tooltip(self.key_combo, "Key signature for roman numeral chords")

        # Time signature control
        ttk.Separator(self.toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        ttk.Label(self.toolbar, text="Time:").pack(side=tk.LEFT, padx=(5, 2))
        self.time_sig_beats_var = tk.IntVar(value=self.viewmodel.time_signature_beats)
        self.time_sig_beats_spin = ttk.Spinbox(self.toolbar, from_=1, to=16,
                                               textvariable=self.time_sig_beats_var,
                                               width=3, command=self.on_time_signature_change)
        self.time_sig_beats_spin.pack(side=tk.LEFT)
        self.create_tooltip(self.time_sig_beats_spin, "Beats per measure")

        ttk.Label(self.toolbar, text="/").pack(side=tk.LEFT, padx=2)

        self.time_sig_unit_var = tk.IntVar(value=self.viewmodel.time_signature_unit)
        self.time_sig_unit_spin = ttk.Spinbox(self.toolbar, values=(1, 2, 4, 8, 16),
                                              textvariable=self.time_sig_unit_var,
                                              width=3, command=self.on_time_signature_change)
        self.time_sig_unit_spin.pack(side=tk.LEFT, padx=(0, 5))
        self.create_tooltip(self.time_sig_unit_spin, "Beat unit (4 = quarter note)")

        # Playback buttons
        ttk.Separator(self.toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)

        playback_frame = tk.Frame(self.toolbar)
        playback_frame.pack(side=tk.LEFT, padx=5)

        self.play_pause_button = tk.Button(playback_frame, text="▶", font=('TkDefaultFont', 12),
                                           width=2, height=1)
        self.play_pause_button.pack(side=tk.LEFT, padx=1)
        # Bind both regular click and shift+click
        self.play_pause_button.bind('<Button-1>', self.on_play_pause_click)
        # Tooltip will be set dynamically in _update_play_pause_tooltip()
        self._update_play_pause_tooltip()

        self.stop_button = tk.Button(playback_frame, text="⏹", font=('TkDefaultFont', 12),
                                     width=2, height=1, command=self.stop_playback)
        self.stop_button.pack(side=tk.LEFT, padx=1)
        self.create_tooltip(self.stop_button, "Stop playback")

    def create_text_editor(self) -> None:
        """Create text editor widget"""
        # Frame for text editor and scrollbar
        editor_frame = ttk.Frame(self)
        editor_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Scrollbar
        scrollbar = ttk.Scrollbar(editor_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Text editor (uses TextEditorViewModel)
        self.text_editor = ChordTextEditor(
            editor_frame,
            viewmodel=self.text_editor_viewmodel,
            yscrollcommand=scrollbar.set
        )
        self.text_editor.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.text_editor.yview)

        # Set initial notation (sync with main ViewModel)
        self.text_editor.set_notation(self.viewmodel.notation.value)

        # Apply font settings
        self.apply_font()

    def create_statusbar(self) -> None:
        """Create status bar"""
        self.statusbar = ttk.Label(self, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.statusbar.pack(side=tk.BOTTOM, fill=tk.X)

    def new_file(self) -> None:
        """Create new file"""
        if self.prompt_save_if_modified():
            self.viewmodel.new_file()
            self.update_statusbar("New file created")

    def open_file(self) -> None:
        """Open file dialog and load file"""
        if not self.prompt_save_if_modified():
            return

        filename = filedialog.askopenfilename(
            title="Open File",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )

        if filename:
            self.load_file(filename)

    def load_file(self, filename: str) -> None:
        """Load file content"""
        # Check for unsaved changes before loading
        if not self.prompt_save_if_modified():
            return

        success = self.viewmodel.open_file(Path(filename))
        if success:
            self.text_editor.edit_reset()  # Reset undo history
            self.text_editor._detect_chords()  # Trigger chord detection
            self.update_recent_files_menu()  # Update menu with new recent files
            self.update_statusbar(f"Opened: {filename}")
        else:
            messagebox.showerror("Error", f"Failed to open file:\n{filename}")

    def save_file(self) -> None:
        """Save current file"""
        # Update ViewModel with current text before saving
        current_text = self.text_editor.get("1.0", "end-1c")
        self.viewmodel.on_text_changed(current_text)

        success = self.viewmodel.save_file()
        if not success:
            # No current file, show save-as dialog
            self.save_file_as()
        else:
            self.update_statusbar(f"Saved: {self.viewmodel.current_file}")

    def save_file_as(self) -> None:
        """Save file with new name"""
        filename = filedialog.asksaveasfilename(
            title="Save File As",
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )

        if filename:
            # Update ViewModel with current text before saving
            current_text = self.text_editor.get("1.0", "end-1c")
            self.viewmodel.on_text_changed(current_text)

            success = self.viewmodel.save_file_as(Path(filename))
            if success:
                self.update_recent_files_menu()  # Update menu with new recent files
                self.update_statusbar(f"Saved: {filename}")
            else:
                messagebox.showerror("Error", f"Failed to save file:\n{filename}")

    def prompt_save_if_modified(self) -> bool:
        """Prompt to save if file is modified. Returns True if ok to continue."""
        if self.viewmodel.is_modified:
            response = messagebox.askyesnocancel(
                "Unsaved Changes",
                "Do you want to save your changes?"
            )
            if response:  # Yes
                self.save_file()
                return True
            elif response is None:  # Cancel
                return False
            else:  # No
                return True
        return True

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
        current_family = self.viewmodel.font_family
        current_size = self.viewmodel.font_size

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
            self.viewmodel.set_font_family(font_var.get())
            self.viewmodel.set_font_size(size_var.get())
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
        self.viewmodel.increase_font_size()

    def decrease_font_size(self) -> None:
        """Decrease font size"""
        self.viewmodel.decrease_font_size()

    def reset_font_size(self) -> None:
        """Reset font size to default"""
        self.viewmodel.reset_font_size()

    def on_mouse_wheel_zoom(self, event: Any) -> None:
        """Handle Ctrl+MouseWheel for zooming"""
        self.viewmodel.on_mouse_wheel_zoom(event.delta)

    def set_notation(self, notation: str) -> None:
        """Set the notation type"""
        # Convert string to Notation enum
        notation_enum = Notation(notation)
        self.viewmodel.set_notation(notation_enum)

    def update_notation_buttons(self) -> None:
        """Update toggle button appearance based on selected notation"""
        current = self.notation_var.get()
        inactive_bg = '#e1e1e1'  # Light gray for inactive buttons

        if current == 'american':
            self.american_btn.config(bg='#0078d4', fg='white', activebackground='#006cc1')
            self.european_btn.config(bg=inactive_bg, fg='black', activebackground='#d0d0d0')
        else:
            self.european_btn.config(bg='#0078d4', fg='white', activebackground='#006cc1')
            self.american_btn.config(bg=inactive_bg, fg='black', activebackground='#d0d0d0')

    def apply_font(self) -> None:
        """Apply font settings to text editor"""
        family = self.viewmodel.font_family
        size = self.viewmodel.font_size
        self.text_editor.configure(font=(family, size))

    def on_text_modified(self, event: Optional[Any] = None) -> None:
        """Handle text modification"""
        if self.text_editor.edit_modified():
            current_text = self.text_editor.get("1.0", "end-1c")
            self.viewmodel.on_text_changed(current_text)
            self.text_editor.edit_modified(False)

    def on_bpm_change(self, *args: Any) -> None:
        """Handle BPM slider change"""
        bpm = self.bpm_var.get()
        self.viewmodel.set_bpm(bpm)

    def on_key_change(self, *args: Any) -> None:
        """Handle key selector change"""
        key = self.key_var.get()
        self.viewmodel.set_key(key if key else None)

    def on_time_signature_change(self) -> None:
        """Handle time signature change"""
        beats = self.time_sig_beats_var.get()
        unit = self.time_sig_unit_var.get()
        self.viewmodel.set_time_signature(beats, unit)

    def on_voicing_change(self) -> None:
        """Handle voicing selection change"""
        voicing = self.voicing_var.get()
        self.viewmodel.set_voicing(voicing)

    def on_instrument_change(self) -> None:
        """Handle instrument selection change"""
        program = self.instrument_var.get()
        self.viewmodel.set_instrument(program)
        # Rebuild the menu to update the indicator
        self.build_instrument_menu()

    def build_instrument_menu(self) -> None:
        """Build or rebuild the instrument menu with category indicators"""
        # Clear existing menu items
        self.instrument_menu.delete(0, tk.END)

        # Get available instruments from soundfont
        instruments = self.viewmodel.get_available_instruments()
        current_instrument = self.viewmodel.get_instrument()

        # Group instruments by General MIDI families (8 instruments per family)
        instrument_categories = [
            (0, 7, "Piano"),
            (8, 15, "Chromatic Percussion"),
            (16, 23, "Organ"),
            (24, 31, "Guitar"),
            (32, 39, "Bass"),
            (40, 47, "Strings"),
            (48, 55, "Ensemble"),
            (56, 63, "Brass"),
            (64, 71, "Reed"),
            (72, 79, "Pipe"),
            (80, 87, "Synth Lead"),
            (88, 95, "Synth Pad"),
            (96, 103, "Synth Effects"),
            (104, 111, "Ethnic"),
            (112, 119, "Percussive"),
            (120, 127, "Sound Effects"),
        ]

        # Create a submenu for each category
        for start, end, category_name in instrument_categories:
            category_menu = tk.Menu(self.instrument_menu, tearoff=0)
            for program, name in instruments:
                if start <= program <= end:
                    category_menu.add_radiobutton(
                        label=f"{program:3d} - {name}",
                        variable=self.instrument_var,
                        value=program,
                        command=self.on_instrument_change
                    )

            # Add indicator if current instrument is in this category
            if start <= current_instrument <= end:
                label = "• " + category_name
            else:
                label = "\u2003" + category_name  # Em-space for alignment (≈ bullet width)

            self.instrument_menu.add_cascade(label=label, menu=category_menu)

    def update_recent_files_menu(self) -> None:
        """Update recent files menu"""
        self.recent_menu.delete(0, tk.END)
        recent_files = self.viewmodel.get_recent_files()
        if not recent_files:
            self.recent_menu.add_command(label="(No recent files)", state=tk.DISABLED)
        else:
            for filepath in recent_files:
                self.recent_menu.add_command(
                    label=os.path.basename(str(filepath)),
                    command=lambda f=filepath: self.load_file(str(f))
                )

    def update_statusbar(self, message: str) -> None:
        """Update status bar message"""
        self.statusbar.config(text=message)

    def on_close(self) -> None:
        """Handle window close"""
        if self.prompt_save_if_modified():
            # Save window geometry before closing
            self.viewmodel.set_window_geometry(self.geometry())
            # Stop playback
            self.viewmodel.stop_playback()
            # Clean up observers to prevent memory leaks
            self.viewmodel.clear_observers()
            self.text_editor.cleanup_observers()
            # Trigger application shutdown (handles cleanup and config save)
            self.application.on_shutdown()
            self.destroy()

    def create_tooltip(self, widget: tk.Widget, text: str) -> None:
        """Create a tooltip for a widget using ui_helpers.create_tooltip"""
        create_tooltip(widget, text)

    def open_chord_identifier(self) -> None:
        """Open the chord identifier window"""
        from viewmodels.chord_identifier_viewmodel import ChordIdentifierViewModel

        # Create ViewModel for chord identifier (with audio service for playback)
        chord_id_viewmodel = ChordIdentifierViewModel(
            song_parser_service=self.application.song_parser_service,
            audio_service=self.application.audio_service
        )

        # Create window with ViewModel and insert callback
        ChordIdentifierWindow(
            parent=self,
            viewmodel=chord_id_viewmodel,
            on_insert_chord=self._on_insert_chord_from_identifier
        )

    def _on_insert_chord_from_identifier(self, chord_name: str) -> None:
        """Handle chord insertion from chord identifier.

        Args:
            chord_name: Chord name to insert
        """
        try:
            self.text_editor.insert(tk.INSERT, chord_name + " ")
            # Trigger chord detection after inserting
            self.text_editor._detect_chords()
            self.text_editor.focus_set()
            self.update_statusbar(f"Inserted chord: {chord_name}")
        except Exception as e:
            logger.error(f"Error inserting chord: {e}", exc_info=True)

    def show_help(self) -> None:
        """Show the help window with user documentation."""
        from ui.help_window import show_help
        docs_path = self.resource_service.get_resource_path('help/build/html')
        if not show_help(docs_path):
            from tkinter import messagebox
            messagebox.showwarning(
                "Help Unavailable",
                "Could not open help documentation.\n\n"
                "Ensure the documentation has been built:\n"
                "  make docs-html"
            )

    def show_quick_start(self) -> None:
        """Show the Quick Start dialog."""
        from ui.dialogs import QuickStartDialog
        dialog = QuickStartDialog(self)
        self.wait_window(dialog)

        # Update config if user chose not to show again
        if dialog.get_dont_show_again():
            self.viewmodel.set_show_quick_start_on_startup(False)

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
                                  text="© 2024 Chord Notepad Contributors\nMIT License",
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
        # Sync current text to ViewModel before conversion
        current_text = self.text_editor.get("1.0", "end-1c")
        self.viewmodel.on_text_changed(current_text)
        # Explicitly convert text
        self.viewmodel.convert_text_to_american()
        self.update_statusbar("Converted to American notation")

    def convert_to_european(self) -> None:
        """Convert all chords in the text to European notation"""
        # Sync current text to ViewModel before conversion
        current_text = self.text_editor.get("1.0", "end-1c")
        self.viewmodel.on_text_changed(current_text)
        # Explicitly convert text
        self.viewmodel.convert_text_to_european()
        self.update_statusbar("Converted to European notation")

    def on_chord_click(self, event: Any) -> None:
        """Handle click on text editor - play chord if clicked"""
        chord_info = self.text_editor.get_chord_at_coordinates(event.x, event.y)
        if chord_info and chord_info.is_valid:
            self.viewmodel.on_chord_clicked(chord_info)
            self.update_statusbar(f"Playing: {chord_info.chord}")

    def on_play_pause_click(self, event: Any) -> None:
        """Handle Play/Pause button click with Shift modifier support.

        States:
        - Initial (not playing): Normal=Play from start, Shift=Play from cursor
        - Playing: Pause
        - Paused: Resume
        """
        shift_held = event.state & 0x1  # Check if Shift key is held

        if self.viewmodel.is_playing and not self.viewmodel.is_paused:
            # Currently playing - pause it
            logger.info("View: Pausing playback")
            self.viewmodel.pause_playback()
            self.update_statusbar("Paused playback")
        elif self.viewmodel.is_paused:
            # Paused - resume from current position
            logger.info("View: Resuming playback")
            self.viewmodel.resume_playback()
            self.update_statusbar("Resumed playback")
        else:
            # Not playing - start playback
            # Sync current text to ViewModel before starting playback
            current_text = self.text_editor.get("1.0", "end-1c")
            self.viewmodel.on_text_changed(current_text)

            if shift_held:
                # Shift+click - play from cursor position
                logger.info("View: Playing from cursor position")
                cursor_pos = self.text_editor.index(tk.INSERT)
                success = self.viewmodel.start_playback_from_cursor(cursor_pos)
                if success:
                    all_chords = [c for c in self.text_editor.get_detected_chords()
                                  if c.is_valid]
                    self.update_statusbar(f"Playing from cursor ({len(all_chords)} chords)...")
                else:
                    self.update_statusbar("No chords to play from cursor")
            else:
                # Normal click - play from start
                logger.info("View: Playing from start")
                success = self.viewmodel.start_playback()
                if success:
                    all_chords = [c for c in self.text_editor.get_detected_chords()
                                  if c.is_valid]
                    self.update_statusbar(f"Playing {len(all_chords)} chords...")
                else:
                    self.update_statusbar("No chords to play")

    def stop_playback(self) -> None:
        """Stop playback"""
        self.viewmodel.stop_playback()
        self.update_statusbar("Stopped playback")

    def insert_bpm(self) -> None:
        """Open dialog to insert a BPM/Tempo change directive"""
        dialog = InsertBpmDialog(self)
        self.wait_window(dialog)

        if dialog.result:
            self.text_editor.insert(tk.INSERT, dialog.result + " ")
            self.text_editor.focus_set()
            self.update_statusbar(f"Inserted: {dialog.result}")

    def insert_time_signature(self) -> None:
        """Open dialog to insert a Time Signature change directive"""
        dialog = InsertTimeSignatureDialog(self)
        self.wait_window(dialog)

        if dialog.result:
            self.text_editor.insert(tk.INSERT, dialog.result + " ")
            self.text_editor.focus_set()
            self.update_statusbar(f"Inserted: {dialog.result}")

    def insert_key(self) -> None:
        """Open dialog to insert a Key change directive"""
        dialog = InsertKeyDialog(self, notation=self.viewmodel.notation)
        self.wait_window(dialog)

        if dialog.result:
            self.text_editor.insert(tk.INSERT, dialog.result + " ")
            self.text_editor.focus_set()
            self.update_statusbar(f"Inserted: {dialog.result}")

    def insert_label(self) -> None:
        """Open dialog to insert a Label directive"""
        # Get existing labels from the current text
        existing_labels = self._get_existing_labels()

        dialog = InsertLabelDialog(self, existing_labels=existing_labels)
        self.wait_window(dialog)

        if dialog.result:
            self.text_editor.insert(tk.INSERT, dialog.result + " ")
            self.text_editor.focus_set()
            self.update_statusbar(f"Inserted: {dialog.result}")

    def insert_loop(self) -> None:
        """Open dialog to insert a Loop directive"""
        # Get existing labels from the current text
        existing_labels = self._get_existing_labels()

        dialog = InsertLoopDialog(self, existing_labels=existing_labels)
        self.wait_window(dialog)

        if dialog.result:
            self.text_editor.insert(tk.INSERT, dialog.result + " ")
            self.text_editor.focus_set()
            self.update_statusbar(f"Inserted: {dialog.result}")

    def _get_existing_labels(self) -> set:
        """Get existing labels from the current text.

        Returns:
            Set of label names
        """
        try:
            # Get current text
            current_text = self.text_editor.get("1.0", "end-1c")

            # Parse the text to find labels
            song = self.application.song_parser_service.build_song(
                current_text,
                self.viewmodel.notation
            )

            # Extract label names
            return set(song.labels.keys())
        except Exception as e:
            logger.warning(f"Could not extract labels from text: {e}")
            return set()
