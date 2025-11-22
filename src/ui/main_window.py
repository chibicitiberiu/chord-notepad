"""
Main application window with text editor and menu bar
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, font as tkfont
import json
import os
import sys
import re
import threading
import queue
from pathlib import Path
from PIL import Image, ImageTk
from ui.text_editor import ChordTextEditor
from ui.chord_identifier import ChordIdentifierWindow
from chord.converter import NotationConverter
from audio.player import NotePlayer
from audio.chord_picker import ChordNotePicker

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

    def __init__(self):
        super().__init__()

        self.title("Chord Notepad")
        self.geometry("900x600")

        # Set window icon
        self._set_window_icon()

        # Application state
        self.current_file = None
        self.is_modified = False
        self.recent_files = []
        self.settings = self.load_settings()

        # Apply saved settings
        self.apply_settings()

        # Initialize audio player
        try:
            self.audio_player = NotePlayer()
            # Set callback to get next note (with read lock)
            self.audio_player.set_next_note_callback(self._get_next_note_for_playback)
            # Set callback for when playback finishes
            self.audio_player.set_playback_finished_callback(self._on_playback_finished)
        except Exception as e:
            print(f"Warning: Could not initialize audio player: {e}")
            self.audio_player = None

        # Initialize chord note picker
        self.chord_picker = ChordNotePicker(chord_octave=3, bass_octave=2, add_bass=True)

        # Auto-play state
        self.current_chord_index = 0
        self.playback_chords = []
        self.playback_lock = None

        # Queue for cross-thread communication (player thread -> UI thread)
        self.event_queue = queue.Queue()

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

        # Start queue processor for cross-thread method calls
        self._process_event_queue()

    def _set_window_icon(self):
        """Set the window icon"""
        try:
            # Get the icon path (relative to project root)
            icon_path = self._get_resource_path('resources/icon-32.png')
            if os.path.exists(icon_path):
                icon_image = tk.PhotoImage(file=icon_path)
                self.iconphoto(True, icon_image)
        except Exception as e:
            print(f"Warning: Could not load window icon: {e}")

    def _get_resource_path(self, relative_path):
        """Get absolute path to resource, works for dev and PyInstaller"""
        try:
            # PyInstaller creates a temp folder and stores path in _MEIPASS
            base_path = sys._MEIPASS
        except Exception:
            # Running in development mode
            # Navigate from src/ui/main_window.py to project root
            base_path = Path(__file__).parent.parent.parent

        return os.path.join(base_path, relative_path)

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
        self.notation_var = tk.StringVar(value=self.settings.get('notation', 'american'))

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
        self.bpm_var = tk.IntVar(value=self.settings.get('bpm', 120))
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

        # Text editor
        self.text_editor = ChordTextEditor(editor_frame, yscrollcommand=scrollbar.set)
        self.text_editor.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.text_editor.yview)

        # Set initial notation
        self.text_editor.set_notation(self.settings.get('notation', 'american'))

        # Apply font settings
        self.apply_font()

    def create_statusbar(self):
        """Create status bar"""
        self.statusbar = ttk.Label(self, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.statusbar.pack(side=tk.BOTTOM, fill=tk.X)

    def new_file(self):
        """Create new file"""
        if self.prompt_save_if_modified():
            self.text_editor.delete("1.0", tk.END)
            self.current_file = None
            self.is_modified = False
            self.title("Chord Notepad")
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

        try:
            with open(filename, 'r', encoding='utf-8') as f:
                content = f.read()

            self.text_editor.delete("1.0", tk.END)
            self.text_editor.insert("1.0", content)
            self.current_file = filename
            self.is_modified = False
            self.text_editor.edit_reset()  # Reset undo history
            # Trigger chord detection after loading file
            self.text_editor._detect_chords()
            self.title(f"Chord Notepad - {os.path.basename(filename)}")
            self.add_to_recent_files(filename)
            self.update_statusbar(f"Opened: {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open file:\n{str(e)}")

    def save_file(self):
        """Save current file"""
        if self.current_file:
            self.write_file(self.current_file)
        else:
            self.save_file_as()

    def save_file_as(self):
        """Save file with new name"""
        filename = filedialog.asksaveasfilename(
            title="Save File As",
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )

        if filename:
            self.write_file(filename)
            self.current_file = filename
            self.title(f"Chord Notepad - {os.path.basename(filename)}")
            self.add_to_recent_files(filename)

    def write_file(self, filename):
        """Write content to file"""
        try:
            content = self.text_editor.get("1.0", "end-1c")
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            self.is_modified = False
            self.update_statusbar(f"Saved: {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save file:\n{str(e)}")

    def prompt_save_if_modified(self):
        """Prompt to save if file is modified. Returns True if ok to continue."""
        if self.is_modified:
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
        current_family = self.settings.get('font_family', 'TkDefaultFont')
        current_size = self.settings.get('font_size', 11)

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
            self.settings['font_family'] = font_var.get()
            self.settings['font_size'] = size_var.get()
            self.apply_font()
            self.save_settings()
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
        current_size = self.settings.get('font_size', 11)
        self.settings['font_size'] = min(current_size + 1, 72)
        self.apply_font()
        self.save_settings()

    def decrease_font_size(self):
        """Decrease font size"""
        current_size = self.settings.get('font_size', 11)
        self.settings['font_size'] = max(current_size - 1, 6)
        self.apply_font()
        self.save_settings()

    def reset_font_size(self):
        """Reset font size to default"""
        self.settings['font_size'] = 11
        self.apply_font()
        self.save_settings()

    def on_mouse_wheel_zoom(self, event):
        """Handle Ctrl+MouseWheel for zooming"""
        if event.delta > 0:
            self.increase_font_size()
        else:
            self.decrease_font_size()

    def set_notation(self, notation):
        """Set the notation type and update button appearance"""
        self.notation_var.set(notation)
        self.settings['notation'] = notation
        self.update_notation_buttons()
        self.text_editor.set_notation(notation)
        self.save_settings()

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
        family = self.settings.get('font_family', 'TkDefaultFont')
        size = self.settings.get('font_size', 11)
        self.text_editor.configure(font=(family, size))

    def on_text_modified(self, event=None):
        """Handle text modification"""
        if self.text_editor.edit_modified():
            self.is_modified = True
            self.text_editor.edit_modified(False)

    def on_bpm_change(self, *args):
        """Handle BPM slider change"""
        bpm = self.bpm_var.get()
        self.bpm_label.config(text=f"{bpm} BPM")
        self.settings['bpm'] = bpm
        # Update player BPM if audio player is available
        if self.audio_player:
            self.audio_player.set_bpm(bpm)

    def add_to_recent_files(self, filename):
        """Add file to recent files list"""
        if filename in self.recent_files:
            self.recent_files.remove(filename)
        self.recent_files.insert(0, filename)
        self.recent_files = self.recent_files[:10]  # Keep max 10
        self.update_recent_files_menu()
        self.save_settings()

    def update_recent_files_menu(self):
        """Update recent files menu"""
        self.recent_menu.delete(0, tk.END)
        if not self.recent_files:
            self.recent_menu.add_command(label="(No recent files)", state=tk.DISABLED)
        else:
            for filepath in self.recent_files:
                self.recent_menu.add_command(
                    label=os.path.basename(filepath),
                    command=lambda f=filepath: self.load_file(f)
                )

    def update_statusbar(self, message):
        """Update status bar message"""
        self.statusbar.config(text=message)

    def get_settings_path(self):
        """Get path to settings file"""
        if os.name == 'nt':  # Windows
            config_dir = Path(os.environ.get('APPDATA', '')) / 'ChordNotepad'
        else:  # Linux/Mac
            config_dir = Path.home() / '.config' / 'chord-notepad'

        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / 'settings.json'

    def load_settings(self):
        """Load settings from file"""
        settings_path = self.get_settings_path()
        default_settings = {
            'font_family': 'TkFixedFont',
            'font_size': 11,
            'bpm': 120,
            'notation': 'american',
            'window_geometry': '900x600',
            'recent_files': []
        }

        try:
            if settings_path.exists():
                with open(settings_path, 'r') as f:
                    loaded = json.load(f)
                    default_settings.update(loaded)
                    self.recent_files = default_settings.get('recent_files', [])
        except Exception as e:
            print(f"Warning: Failed to load settings: {e}")

        return default_settings

    def save_settings(self):
        """Save settings to file"""
        settings_path = self.get_settings_path()
        self.settings['recent_files'] = self.recent_files
        self.settings['window_geometry'] = self.geometry()
        self.settings['notation'] = self.notation_var.get()

        try:
            with open(settings_path, 'w') as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to save settings: {e}")

    def apply_settings(self):
        """Apply loaded settings"""
        geom = self.settings.get('window_geometry', '900x600')
        self.geometry(geom)

    def on_close(self):
        """Handle window close"""
        if self.prompt_save_if_modified():
            # Stop playback
            self.stop_playback()
            # Clean up audio player
            if self.audio_player:
                self.audio_player.cleanup()
            self.save_settings()
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
        ChordIdentifierWindow(self)

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
            icon_path = self._get_resource_path('resources/icon-128.png')
            if os.path.exists(icon_path):
                icon_img = Image.open(icon_path)
                icon_photo = ImageTk.PhotoImage(icon_img)
                icon_label = tk.Label(main_frame, image=icon_photo)
                icon_label.image = icon_photo  # Keep a reference
                icon_label.pack(pady=(0, 10))
        except Exception as e:
            print(f"Warning: Could not load About icon: {e}")

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
        text = self.text_editor.get("1.0", "end-1c")
        converted_text = self._convert_chords_in_text(text, 'american')
        self.text_editor.delete("1.0", tk.END)
        self.text_editor.insert("1.0", converted_text)
        # Switch toolbar to American mode
        self.set_notation('american')
        self.update_statusbar("Converted to American notation")

    def convert_to_european(self):
        """Convert all chords in the text to European notation"""
        text = self.text_editor.get("1.0", "end-1c")
        converted_text = self._convert_chords_in_text(text, 'european')
        self.text_editor.delete("1.0", tk.END)
        self.text_editor.insert("1.0", converted_text)
        # Switch toolbar to European mode
        self.set_notation('european')
        self.update_statusbar("Converted to European notation")

    def _convert_chords_in_text(self, text, target_notation):
        """Convert all chords in chord lines to target notation, maintaining X-position alignment"""
        # Use cached Line objects from text editor
        lines = self.text_editor.get_lines()

        if not lines:
            # Fall back to original text if no classification available
            return text

        result_lines = []
        i = 0

        while i < len(lines):
            line = lines[i]

            if line.is_chord_line():
                # Check if next line is a lyric line
                next_line = lines[i + 1] if i + 1 < len(lines) else None

                if next_line and next_line.is_text_line():
                    # Convert chords with lyric alignment
                    converted_chord, converted_lyric = self._convert_chord_line_with_lyrics(
                        line, next_line, target_notation)
                    result_lines.append(converted_chord)
                    result_lines.append(converted_lyric)
                    i += 2
                else:
                    # Convert chords without lyrics
                    converted_line = self._convert_chord_line(line, target_notation)
                    result_lines.append(converted_line)
                    i += 1
            else:
                # Keep text lines unchanged
                result_lines.append(line.content)
                i += 1

        return '\n'.join(result_lines)

    def _convert_chord_line(self, line, target_notation):
        """Convert all chords in a chord line using cached chord data"""
        # Use cached chord positions from Line object
        result = list(line.content)
        offset = 0

        for chord_info in line.chords:
            start = chord_info.line_offset
            chord_str = chord_info.chord

            # Convert to shortest representation
            converted = self._convert_chord_shortest(chord_str, target_notation)

            old_len = len(chord_str)
            new_len = len(converted)
            length_diff = new_len - old_len

            # Adjust position with offset
            adj_start = start + offset
            adj_end = adj_start + old_len

            if length_diff > 0:
                # Chord got longer - try to absorb trailing spaces
                spaces_after = 0
                check_pos = adj_end
                while check_pos < len(result) and result[check_pos] == ' ':
                    spaces_after += 1
                    check_pos += 1

                # Check if there's content after the spaces (another chord)
                has_content_after = check_pos < len(result) and result[check_pos] != ' '

                # Keep at least 1 space if there's content after
                spaces_to_keep = 1 if has_content_after else 0
                absorbable_spaces = max(0, spaces_after - spaces_to_keep)

                if absorbable_spaces >= length_diff:
                    # Absorb spaces from chord line
                    result[adj_start:adj_end + length_diff] = list(converted)
                else:
                    # Can't absorb enough - keep chord as is and add padding
                    result[adj_start:adj_end] = list(converted)
                    offset += length_diff

            elif length_diff < 0:
                # Chord got shorter - add spaces after
                result[adj_start:adj_end] = list(converted) + [' '] * abs(length_diff)

            else:
                # Same length
                result[adj_start:adj_end] = list(converted)

        return ''.join(result)

    def _convert_chord_shortest(self, chord_str, target_notation):
        """Convert chord using shortest representation"""
        if target_notation == 'european':
            converted = NotationConverter.american_to_european(chord_str)
            # Use shortest form: prefer "do" over "Dom", "Do" over "DoM"
            converted = self._shorten_european(converted)
        else:
            converted = NotationConverter.european_to_american(chord_str)
            # Use shortest form: prefer "c" over "Cm" for display (but PyChord needs Cm)
            converted = self._shorten_american(converted)
        return converted

    def _shorten_european(self, chord):
        """Use shortest European representation"""
        # DoM -> Do, Dom -> do, Domaj -> do, etc.
        for note in ['Do', 'Re', 'Mi', 'Fa', 'Sol', 'La', 'Si']:
            if chord == note + 'M':
                return note  # DoM -> Do
            if chord == note + 'maj':
                return note  # Domaj -> Do

        for note in ['do', 're', 'mi', 'fa', 'sol', 'la', 'si']:
            if chord == note + 'm':
                return note  # dom -> do
            if chord == note + 'min':
                return note  # domin -> do

        return chord

    def _shorten_american(self, chord):
        """Use shortest American representation"""
        # Cm -> c, Dm -> d, etc. (for display)
        if len(chord) == 2 and chord[1] == 'm':
            return chord[0].lower()  # Cm -> c
        if len(chord) > 2 and chord.endswith('min'):
            # Cmin -> c, but Cmin7 stays as is
            if chord[:-3].isalpha() and len(chord[:-3]) <= 2:
                return chord[0].lower()
        return chord

    def _convert_chord_line_with_lyrics(self, chord_line, lyric_line, target_notation):
        """Convert chords while maintaining alignment with lyrics below using cached chord data"""
        # Use cached chord positions from Line object
        result_chord = list(chord_line.content)
        result_lyric = list(lyric_line.content)
        offset = 0

        for chord_info in chord_line.chords:
            start = chord_info.line_offset
            chord_str = chord_info.chord

            # Convert to shortest representation
            converted = self._convert_chord_shortest(chord_str, target_notation)

            old_len = len(chord_str)
            new_len = len(converted)
            length_diff = new_len - old_len

            adj_start = start + offset
            adj_end = adj_start + old_len

            if length_diff > 0:
                # Chord got longer - try to absorb trailing spaces
                spaces_after = 0
                check_pos = adj_end
                while check_pos < len(result_chord) and result_chord[check_pos] == ' ':
                    spaces_after += 1
                    check_pos += 1

                # Check if there's content after the spaces (another chord)
                has_content_after = check_pos < len(result_chord) and result_chord[check_pos] != ' '

                # Keep at least 1 space if there's content after
                spaces_to_keep = 1 if has_content_after else 0
                absorbable_spaces = max(0, spaces_after - spaces_to_keep)

                if absorbable_spaces >= length_diff:
                    # Absorb spaces from chord line
                    result_chord[adj_start:adj_end + length_diff] = list(converted)
                else:
                    # Can't absorb enough - need to extend lyric line
                    result_chord[adj_start:adj_end] = list(converted)
                    spaces_needed = length_diff - absorbable_spaces

                    # Insert at position after chord + absorbed spaces
                    insert_pos = adj_end + absorbable_spaces
                    if insert_pos <= len(result_lyric):
                        # Check if we're at a word boundary (space, end of line, or start of line)
                        at_word_boundary = (
                            insert_pos == 0 or
                            insert_pos >= len(result_lyric) or
                            result_lyric[insert_pos - 1] == ' ' or
                            (insert_pos < len(result_lyric) and result_lyric[insert_pos] == ' ')
                        )

                        # Use spaces at word boundaries, '-' within words
                        fill_char = ' ' if at_word_boundary else '-'
                        result_lyric[insert_pos:insert_pos] = [fill_char] * spaces_needed
                    offset += spaces_needed

            elif length_diff < 0:
                # Chord got shorter - add spaces after
                result_chord[adj_start:adj_end] = list(converted) + [' '] * abs(length_diff)

            else:
                # Same length
                result_chord[adj_start:adj_end] = list(converted)

        return ''.join(result_chord), ''.join(result_lyric)

    def on_chord_click(self, event):
        """Handle click on text editor - play chord if clicked"""
        if not self.audio_player:
            return

        # Get the index of the click
        index = self.text_editor.index(f"@{event.x},{event.y}")

        # Convert index to character position
        line, col = map(int, index.split('.'))
        char_pos = 0

        # Calculate character position from line and column
        text = self.text_editor.get("1.0", "end-1c")
        lines = text.split('\n')
        for i in range(line - 1):
            char_pos += len(lines[i]) + 1  # +1 for newline
        char_pos += col

        # Check if we clicked on a chord
        for chord_info in self.text_editor.get_detected_chords():
            if hasattr(chord_info, 'start') and hasattr(chord_info, 'end'):
                if chord_info.start <= char_pos < chord_info.end:
                    # Clicked on a chord!
                    if chord_info.is_valid and chord_info.notes:
                        # Convert chord to MIDI notes
                        midi_notes = self.chord_picker.chord_to_midi(chord_info.notes)
                        # Play immediately (bypass queue)
                        self.audio_player.play_notes_immediate(midi_notes)
                        self.update_statusbar(f"Playing: {chord_info.chord}")
                    break

    def start_playback(self):
        """Start auto-playing chords"""
        if not self.audio_player:
            self.update_statusbar("Audio player not available")
            return

        # Get all valid chords from the document
        all_chords = [c for c in self.text_editor.get_detected_chords()
                      if c.is_valid and c.notes]

        if not all_chords:
            self.update_statusbar("No chords to play")
            return

        # Store chord list for playback (with read lock)
        import threading
        self.playback_lock = threading.Lock()
        with self.playback_lock:
            self.playback_chords = all_chords
            self.current_chord_index = 0

        # Update button states
        self.play_button.config(state=tk.DISABLED)
        self.pause_button.config(state=tk.NORMAL)

        # Update player BPM
        self.audio_player.set_bpm(self.bpm_var.get())

        # Start playing in separate thread
        self.update_statusbar(f"Playing {len(all_chords)} chords...")
        self.audio_player.start_playback()

    def pause_playback(self):
        """Pause/resume playback"""
        if not self.audio_player:
            return

        if self.audio_player.is_paused:
            # Resume
            self.pause_button.config(text="⏸")
            self.audio_player.resume_playback()
            self.update_statusbar("Resumed playback")
        else:
            # Pause
            self.pause_button.config(text="▶")
            self.audio_player.pause_playback()
            self.update_statusbar("Paused playback")

    def stop_playback(self):
        """Stop playback and reset state"""
        # Stop audio player
        if self.audio_player:
            self.audio_player.stop_playback()

        # Clear playing highlight (schedule on UI thread)
        self.after(0, lambda: self.text_editor.tag_remove('chord_playing', '1.0', tk.END))

        # Reset state (with lock)
        if self.playback_lock:
            with self.playback_lock:
                self.current_chord_index = 0
                self.playback_chords = []

        # Update button states
        self.play_button.config(state=tk.NORMAL)
        self.pause_button.config(state=tk.DISABLED, text="⏸")

        self.update_statusbar("Stopped playback")

    def _get_next_note_for_playback(self):
        """
        Callback for player thread to get next note

        Returns:
            (midi_notes, duration_beats) or None if no more notes
        """
        if not self.playback_lock:
            return None

        with self.playback_lock:
            # Check if we have more chords
            if self.current_chord_index >= len(self.playback_chords):
                # No more chords
                return None

            # Get current chord
            chord_info = self.playback_chords[self.current_chord_index]
            self.current_chord_index += 1

            # Highlight current chord (schedule on UI thread)
            self.after(0, lambda: self._highlight_chord(chord_info))

            # Update status (schedule on UI thread)
            status_msg = f"Playing: {chord_info.chord} ({self.current_chord_index}/{len(self.playback_chords)})"
            self.after(0, lambda msg=status_msg: self.update_statusbar(msg))

            # Convert chord to MIDI notes
            midi_notes = self.chord_picker.chord_to_midi(chord_info.notes)

            # Return notes and duration (4 beats = 1 bar in 4/4 time)
            beats_per_measure = self.audio_player.time_signature[0]
            return (midi_notes, beats_per_measure)

    def _highlight_chord(self, chord_info):
        """Highlight a chord in the editor (must be called from UI thread)"""
        self.text_editor.tag_remove('chord_playing', '1.0', tk.END)
        if hasattr(chord_info, 'start') and hasattr(chord_info, 'end'):
            start_idx = f"1.0 + {chord_info.start} chars"
            end_idx = f"1.0 + {chord_info.end} chars"
            self.text_editor.tag_add('chord_playing', start_idx, end_idx)
            self.text_editor.tag_raise('chord_playing')

    def _process_event_queue(self):
        """Process queued method calls from background threads (runs on UI thread)"""
        try:
            # Process all pending events in queue
            while True:
                callback = self.event_queue.get_nowait()
                callback()
        except queue.Empty:
            pass

        # Schedule next check in 100ms
        self.after(100, self._process_event_queue)

    def _on_playback_finished(self):
        """Called by player thread when playback finishes naturally"""
        # Queue the UI reset method to be executed on main thread
        self.event_queue.put(self._reset_playback_ui)

    def _reset_playback_ui(self):
        """Reset UI controls after playback finishes (must run on UI thread)"""

        # Clear playing highlight
        self.text_editor.tag_remove('chord_playing', '1.0', tk.END)

        # Reset state (with lock)
        if self.playback_lock:
            with self.playback_lock:
                self.current_chord_index = 0
                self.playback_chords = []

        # Update button states
        self.play_button.config(state=tk.NORMAL)
        self.pause_button.config(state=tk.DISABLED, text="⏸")

        self.update_statusbar("Playback finished")
