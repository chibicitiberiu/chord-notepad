"""
Main application window with text editor and menu bar
"""

import logging
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, font as tkfont
import os
import sys
from pathlib import Path
from PIL import Image, ImageTk
from ui.text_editor import ChordTextEditor
from ui.chord_identifier import ChordIdentifierWindow
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

    def __init__(self, viewmodel, text_editor_viewmodel, application, resource_service):
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

    def _setup_viewmodel_observers(self):
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

        # Text content changes
        self.viewmodel.observe('current_text', self._on_current_text_changed)

    # ViewModel observer callbacks

    def _on_font_size_changed(self, new_value):
        """React to font size changes from ViewModel."""
        self.apply_font()

    def _on_notation_changed(self, new_value: Notation):
        """React to notation changes from ViewModel."""
        # Convert Notation enum to string value for UI components
        notation_str = new_value.value
        self.notation_var.set(notation_str)
        self.update_notation_buttons()
        self.text_editor.set_notation(notation_str)

    def _on_current_file_changed(self, new_value):
        """React to current file changes from ViewModel."""
        self.title(self.viewmodel.get_window_title())

    def _on_is_modified_changed(self, new_value):
        """React to modification state changes from ViewModel."""
        self.title(self.viewmodel.get_window_title())

    def _on_is_playing_changed(self, new_value):
        """React to playback state changes from ViewModel."""
        if new_value:
            # Playback started
            self.play_button.config(state=tk.DISABLED)
            self.pause_button.config(state=tk.NORMAL)
        else:
            # Playback stopped
            self.play_button.config(state=tk.NORMAL)
            self.pause_button.config(state=tk.DISABLED, text="⏸")
            # Clear playing highlight
            self.text_editor.tag_remove('chord_playing', '1.0', tk.END)
            # Update statusbar
            self.update_statusbar("Ready")

    def _on_is_paused_changed(self, new_value):
        """React to pause state changes from ViewModel."""
        if new_value:
            # Paused
            self.pause_button.config(text="▶")
        else:
            # Resumed (or started)
            self.pause_button.config(text="⏸")

    def _on_bpm_changed(self, new_value):
        """React to BPM changes from ViewModel."""
        self.bpm_label.config(text=f"{new_value} BPM")
        self.bpm_var.set(new_value)

    def _on_current_text_changed(self, new_value):
        """React to text content changes from ViewModel."""
        # Update text editor content
        self.text_editor.delete('1.0', tk.END)
        self.text_editor.insert('1.0', new_value)

    def _set_window_icon(self):
        """Set the window icon"""
        try:
            # Get the icon path (relative to project root)
            icon_path = self.resource_service.get_resource_path('resources/icon-32.png')
            if os.path.exists(icon_path):
                icon_image = tk.PhotoImage(file=icon_path)
                self.iconphoto(True, icon_image)
        except Exception as e:
            logger.warning(f"Could not load window icon: {e}")

    def create_menu(self):
        """Create menu bar"""
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="New", command=self.new_file, accelerator="Ctrl+N")
        file_menu.add_command(label="Open...", command=self.open_file, accelerator="Ctrl+O")
        file_menu.add_command(label="Save", command=self.save_file, accelerator="Ctrl+S")
        file_menu.add_command(label="Save As...", command=self.save_file_as, accelerator="Ctrl+Shift+S")
        file_menu.add_separator()

        # Recent files submenu
        self.recent_menu = tk.Menu(file_menu, tearoff=0)
        file_menu.add_cascade(label="Recent Files", menu=self.recent_menu)
        self.update_recent_files_menu()

        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_close, accelerator="Ctrl+Q")
        menubar.add_cascade(label="File", menu=file_menu)

        # Edit menu
        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="Undo", command=self.text_editor.edit_undo, accelerator="Ctrl+Z")
        edit_menu.add_command(label="Redo", command=self.text_editor.edit_redo, accelerator="Ctrl+Y")
        edit_menu.add_separator()
        edit_menu.add_command(label="Cut", command=lambda: self.text_editor.event_generate("<<Cut>>"), accelerator="Ctrl+X")
        edit_menu.add_command(label="Copy", command=lambda: self.text_editor.event_generate("<<Copy>>"), accelerator="Ctrl+C")
        edit_menu.add_command(label="Paste", command=lambda: self.text_editor.event_generate("<<Paste>>"), accelerator="Ctrl+V")
        edit_menu.add_command(label="Select All", command=self.select_all, accelerator="Ctrl+A")
        menubar.add_cascade(label="Edit", menu=edit_menu)

        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Font...", command=self.choose_font)
        view_menu.add_separator()
        view_menu.add_command(label="Increase Font Size", command=self.increase_font_size, accelerator="Ctrl+Plus")
        view_menu.add_command(label="Decrease Font Size", command=self.decrease_font_size, accelerator="Ctrl+Minus")
        view_menu.add_command(label="Reset Font Size", command=self.reset_font_size, accelerator="Ctrl+0")
        menubar.add_cascade(label="View", menu=view_menu)

        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        tools_menu.add_command(label="Identify Chord...", command=self.open_chord_identifier)
        tools_menu.add_separator()
        tools_menu.add_command(label="Convert to American Notation", command=self.convert_to_american)
        tools_menu.add_command(label="Convert to European Notation", command=self.convert_to_european)
        menubar.add_cascade(label="Tools", menu=tools_menu)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self.show_about)
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

    def create_toolbar(self):
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

        # Playback buttons (will be implemented in later phases)
        ttk.Separator(self.toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)

        playback_frame = tk.Frame(self.toolbar)
        playback_frame.pack(side=tk.LEFT, padx=5)

        self.play_button = tk.Button(playback_frame, text="▶", font=('TkDefaultFont', 12),
                                     width=2, height=1, command=self.start_playback)
        self.play_button.pack(side=tk.LEFT, padx=1)
        self.create_tooltip(self.play_button, "Play chords automatically")

        self.pause_button = tk.Button(playback_frame, text="⏸", font=('TkDefaultFont', 12),
                                      width=2, height=1, state=tk.DISABLED, command=self.pause_playback)
        self.pause_button.pack(side=tk.LEFT, padx=1)
        self.create_tooltip(self.pause_button, "Pause playback")

        self.stop_button = tk.Button(playback_frame, text="⏹", font=('TkDefaultFont', 12),
                                     width=2, height=1, command=self.stop_playback)
        self.stop_button.pack(side=tk.LEFT, padx=1)
        self.create_tooltip(self.stop_button, "Stop all sounds")

    def create_text_editor(self):
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

    def create_statusbar(self):
        """Create status bar"""
        self.statusbar = ttk.Label(self, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.statusbar.pack(side=tk.BOTTOM, fill=tk.X)

    def new_file(self):
        """Create new file"""
        if self.prompt_save_if_modified():
            self.viewmodel.new_file()
            self.update_statusbar("New file created")

    def open_file(self):
        """Open file dialog and load file"""
        if not self.prompt_save_if_modified():
            return

        filename = filedialog.askopenfilename(
            title="Open File",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )

        if filename:
            self.load_file(filename)

    def load_file(self, filename):
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

    def save_file(self):
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

    def save_file_as(self):
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

    def prompt_save_if_modified(self):
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

    def select_all(self):
        """Select all text"""
        self.text_editor.tag_add(tk.SEL, "1.0", tk.END)
        self.text_editor.mark_set(tk.INSERT, "1.0")
        self.text_editor.see(tk.INSERT)
        return 'break'

    def choose_font(self):
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

        def on_ok():
            self.viewmodel.set_font_family(font_var.get())
            self.viewmodel.set_font_size(size_var.get())
            dialog.destroy()

        def on_cancel():
            dialog.destroy()

        ttk.Button(button_frame, text="OK", command=on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=on_cancel).pack(side=tk.LEFT, padx=5)

        # Center the dialog
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - (dialog.winfo_width() // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")

    def increase_font_size(self):
        """Increase font size"""
        self.viewmodel.increase_font_size()

    def decrease_font_size(self):
        """Decrease font size"""
        self.viewmodel.decrease_font_size()

    def reset_font_size(self):
        """Reset font size to default"""
        self.viewmodel.reset_font_size()

    def on_mouse_wheel_zoom(self, event):
        """Handle Ctrl+MouseWheel for zooming"""
        self.viewmodel.on_mouse_wheel_zoom(event.delta)

    def set_notation(self, notation):
        """Set the notation type"""
        # Convert string to Notation enum
        notation_enum = Notation(notation)
        self.viewmodel.set_notation(notation_enum)

    def update_notation_buttons(self):
        """Update toggle button appearance based on selected notation"""
        current = self.notation_var.get()
        inactive_bg = '#e1e1e1'  # Light gray for inactive buttons

        if current == 'american':
            self.american_btn.config(bg='#0078d4', fg='white', activebackground='#006cc1')
            self.european_btn.config(bg=inactive_bg, fg='black', activebackground='#d0d0d0')
        else:
            self.european_btn.config(bg='#0078d4', fg='white', activebackground='#006cc1')
            self.american_btn.config(bg=inactive_bg, fg='black', activebackground='#d0d0d0')

    def apply_font(self):
        """Apply font settings to text editor"""
        family = self.viewmodel.font_family
        size = self.viewmodel.font_size
        self.text_editor.configure(font=(family, size))

    def on_text_modified(self, event=None):
        """Handle text modification"""
        if self.text_editor.edit_modified():
            current_text = self.text_editor.get("1.0", "end-1c")
            self.viewmodel.on_text_changed(current_text)
            self.text_editor.edit_modified(False)

    def on_bpm_change(self, *args):
        """Handle BPM slider change"""
        bpm = self.bpm_var.get()
        self.viewmodel.set_bpm(bpm)

    def update_recent_files_menu(self):
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

    def update_statusbar(self, message):
        """Update status bar message"""
        self.statusbar.config(text=message)

    def on_close(self):
        """Handle window close"""
        if self.prompt_save_if_modified():
            # Save window geometry before closing
            self.viewmodel.set_window_geometry(self.geometry())
            # Stop playback
            self.viewmodel.stop_playback()
            # Trigger application shutdown (handles cleanup and config save)
            self.application.on_shutdown()
            self.destroy()

    def create_tooltip(self, widget, text):
        """Create a tooltip for a widget"""
        def on_enter(event):
            tooltip = tk.Toplevel()
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
            label = tk.Label(tooltip, text=text, background="#ffffe0",
                           relief=tk.SOLID, borderwidth=1, padx=5, pady=2)
            label.pack()
            widget._tooltip = tooltip

        def on_leave(event):
            if hasattr(widget, '_tooltip'):
                widget._tooltip.destroy()
                del widget._tooltip

        widget.bind("<Enter>", on_enter)
        widget.bind("<Leave>", on_leave)

    def open_chord_identifier(self):
        """Open the chord identifier window"""
        from viewmodels.chord_identifier_viewmodel import ChordIdentifierViewModel

        # Create ViewModel for chord identifier (with audio service for playback)
        chord_id_viewmodel = ChordIdentifierViewModel(
            chord_detection_service=self.application.chord_detection_service,
            audio_service=self.application.audio_service
        )

        # Create window with ViewModel and insert callback
        ChordIdentifierWindow(
            parent=self,
            viewmodel=chord_id_viewmodel,
            on_insert_chord=self._on_insert_chord_from_identifier
        )

    def _on_insert_chord_from_identifier(self, chord_name: str):
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

    def show_about(self):
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

    def convert_to_american(self):
        """Convert all chords in the text to American notation"""
        # Sync current text to ViewModel before conversion
        current_text = self.text_editor.get("1.0", "end-1c")
        self.viewmodel.on_text_changed(current_text)
        # Explicitly convert text
        self.viewmodel.convert_text_to_american()
        self.update_statusbar("Converted to American notation")

    def convert_to_european(self):
        """Convert all chords in the text to European notation"""
        # Sync current text to ViewModel before conversion
        current_text = self.text_editor.get("1.0", "end-1c")
        self.viewmodel.on_text_changed(current_text)
        # Explicitly convert text
        self.viewmodel.convert_text_to_european()
        self.update_statusbar("Converted to European notation")

    def on_chord_click(self, event):
        """Handle click on text editor - play chord if clicked"""
        chord_info = self.text_editor.get_chord_at_coordinates(event.x, event.y)
        if chord_info and chord_info.is_valid and chord_info.notes:
            self.viewmodel.on_chord_clicked(chord_info)
            self.update_statusbar(f"Playing: {chord_info.chord}")

    def start_playback(self):
        """Start auto-playing chords"""
        logger.info("View start_playback called")
        # Sync current text to ViewModel before starting playback
        current_text = self.text_editor.get("1.0", "end-1c")
        logger.info(f"Current text length: {len(current_text)}")
        self.viewmodel.on_text_changed(current_text)

        success = self.viewmodel.start_playback()
        logger.info(f"Playback started: {success}")
        if success:
            # Get chord count for status message
            all_chords = [c for c in self.text_editor.get_detected_chords()
                          if c.is_valid and c.notes]
            self.update_statusbar(f"Playing {len(all_chords)} chords...")
        else:
            self.update_statusbar("No chords to play")

    def pause_playback(self):
        """Pause/resume playback"""
        if self.viewmodel.is_paused:
            # Resume
            self.viewmodel.resume_playback()
            self.update_statusbar("Resumed playback")
        else:
            # Pause
            self.viewmodel.pause_playback()
            self.update_statusbar("Paused playback")

    def stop_playback(self):
        """Stop playback"""
        self.viewmodel.stop_playback()
        self.update_statusbar("Stopped playback")
