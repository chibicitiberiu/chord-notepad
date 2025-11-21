# Chord-Playing Notepad Application - Implementation Plan

## Executive Summary

This document outlines the implementation plan for a cross-platform Python application that functions as a simple notepad with automatic chord detection and playback capabilities.

## Technology Stack & Rationale

### 1. UI Framework: **Tkinter** (Primary Choice)

**Rationale:**
- Zero external dependencies (built into Python)
- Cross-platform (Windows, Linux, macOS)
- Sufficient for simple text editor with clickable regions
- Text widget supports tags for creating hyperlinks
- Simple toolbar creation with buttons and sliders
- Minimal learning curve
- Smallest package size for distribution

### 2. Chord Detection: **Line-Based Classification + Regex Patterns**

**Strategy:** Classify entire lines as "chord lines" or "lyric lines" to avoid false positives

**Line Classification Algorithm:**
```python
def is_chord_line(line):
    """Returns True if line appears to contain only chords"""
    words = line.strip().split()
    if not words:
        return False

    chord_count = 0
    for word in words:
        if matches_chord_pattern(word):
            chord_count += 1

    # If >60% of words are chords, it's a chord line
    return (chord_count / len(words)) >= 0.6
```

**Simplified American Notation Pattern** (includes slash chords):
```regex
\b([A-G](?:[#b])?(?:m(?:aj)?(?:7|9|11|13)?|min|maj7|maj9|maj11|maj13|7|9|11|13|6|sus[24]|dim|aug|add\d)?(?:[b#]\d+)*(?:/[A-G](?:[#b])?)?)\b
```

**Simplified European Notation Pattern** (includes slash chords):
```regex
\b((?:Do|Re|Mi|Fa|Sol|La|Si)(?:[#b])?(?:m(?:aj)?(?:7|9|11|13)?|min|maj7|7|9|11|13|sus[24]|dim|aug)?(?:/(?:Do|Re|Mi|Fa|Sol|La|Si)(?:[#b])?)?)\b
```

**Slash Chord Examples:**
- `C/E` - C major with E in bass
- `Am/G` - A minor with G in bass
- `G7/B` - G7 with B in bass
- `Dm7/F` - D minor 7 with F in bass

**Benefits:**
- No false positives (lyrics in lyric lines won't be detected)
- Simpler regex patterns (only used for line classification heuristic)
- Matches how musicians actually write chord sheets
- More accurate chord detection
- Allows words like "Am" in lyrics without triggering detection
- **PyChord validates all chords** - if it parses, it's valid (blue); if not, it's gray
- Automatically supports all chord types PyChord knows (including slash chords)
- No need to maintain comprehensive regex for all chord variants

### 3. Chord-to-Notes Conversion: **PyChord**

**Rationale:**
- Zero dependencies (pure Python)
- Simple, clean API
- Fast performance
- Active maintenance
- Perfect for chord name → notes conversion

**Usage Example:**
```python
from pychord import Chord
chord = Chord("Cm7")
notes = chord.components()  # ['C', 'Eb', 'G', 'Bb']
```

**Alternative:** mingus (if MIDI integration needed)

### 4. Audio Playback: **FluidSynth + Soundfont**

**Rationale:**
- High-quality audio (much better than sine waves)
- Works universally (Windows + Linux) without system dependencies
- Bundle small soundfont file (~5-10MB)
- Supports simultaneous note playback (chords)
- Stop/pause capabilities
- Python library: **pyfluidsynth** (wraps FluidSynth C library)

**Playback Approach:**
- Bundle a small General MIDI soundfont (e.g., FluidR3_GM.sf2 ~140MB or smaller alternative)
- Use pyfluidsynth to load soundfont and play MIDI notes
- Convert chord names to MIDI note numbers (C4=60, etc.)
- Send note_on/note_off messages to FluidSynth
- FluidSynth handles synthesis and audio output

**Bundling Strategy:**
- Include soundfont file in resources/
- Bundle FluidSynth library with PyInstaller/AppImage
- Use resource path helper for soundfont location

### 5. Package Management: **pipenv**

**Dependencies:**
```
[packages]
pychord = "*"
pyfluidsynth = "*"

[dev-packages]
pyinstaller = "*"
pytest = "*"
```

**Note:**
- pyfluidsynth requires FluidSynth C library installed on system during development
- Will be bundled for distribution

### 6. Packaging: **PyInstaller**

**Windows:** PyInstaller → .exe
**Linux:** PyInstaller → AppImage (via appimage-builder)

---

## Application Architecture

### Module Structure

```
chord-notepad/
├── Pipfile
├── Pipfile.lock
├── Makefile                    # Build automation
├── src/
│   ├── main.py                 # Entry point
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── main_window.py      # Main window with text area and toolbar
│   │   └── text_editor.py      # Custom Text widget with chord detection
│   ├── chord/
│   │   ├── __init__.py
│   │   ├── detector.py         # Line-based chord detection
│   │   ├── converter.py        # Chord name → MIDI notes
│   │   └── notation.py         # American/European notation handling
│   ├── audio/
│   │   ├── __init__.py
│   │   └── player.py           # FluidSynth playback manager
│   └── utils/
│       ├── __init__.py
│       └── file_handler.py     # Load/save text files
├── build/
│   └── chord-notepad.spec      # PyInstaller spec file
├── resources/
│   ├── icon.png                # Application icon
│   └── soundfont.sf2           # Bundled soundfont (~5-10MB)
├── tests/
│   ├── test_detector.py
│   ├── test_converter.py
│   └── test_player.py
└── README.md
```

---

## Detailed Implementation Plan

### Phase 1: Core Text Editor (Foundation)

**Tasks:**
1. Set up pipenv environment and install dependencies
   ```bash
   # Install system dependencies first
   # Ubuntu/Debian:
   sudo apt install fluidsynth libfluidsynth-dev
   # Fedora:
   sudo dnf install fluidsynth fluidsynth-devel
   # Windows: Download FluidSynth binary

   # Setup Python environment
   pipenv --python 3.11
   pipenv install pychord pyfluidsynth
   pipenv install --dev pyinstaller pytest
   ```

2. Create basic Tkinter window with text area
   - `Text` widget for editing with undo enabled
   - Menu bar with File and Edit menus
   - Font selection dialog (View → Font)
   - Font size adjustment (Ctrl+Wheel, Ctrl+Plus, Ctrl+Minus, Ctrl+0 to reset)

3. Implement file operations
   - **New file** (Ctrl+N) - clear current, prompt if unsaved
   - **Open file** (Ctrl+O) - load text files (.txt)
   - **Save** (Ctrl+S) / **Save As** (Ctrl+Shift+S)
   - **Recent files** list (last 5-10 files)
   - **Confirm before closing** unsaved changes
   - Basic copy/paste (Ctrl+C, Ctrl+V, Ctrl+X - built into Text widget)
   - Select All (Ctrl+A)

4. Error handling foundation
   - Try/catch around file operations
   - User-friendly error messages (tkinter.messagebox)
   - Log errors for debugging

**Key Components:**
```python
# src/ui/main_window.py
class MainWindow(tk.Tk):
    def __init__(self):
        self.text_editor = ChordTextEditor(self)
        self.create_menu()
        self.create_toolbar()
```

### Phase 2: Chord Detection System

**Tasks:**
1. Implement line-based chord detector
   - Line classification algorithm (chord vs lyric)
   - American notation regex (simplified)
   - European notation regex (simplified)
   - Configurable via radio button selection

2. Implement idle timer (typing detection)
   - Start timer on key press
   - Reset timer on subsequent key presses
   - Fire after 1 second of inactivity
   - Trigger chord detection on timer fire

3. Tag detected chords in text
   - Use `Text.tag_add()` to mark chord regions
   - Apply hyperlink styling (blue, underlined)
   - Bind click events to tags

**Key Components:**
```python
# src/chord/detector.py
class ChordDetector:
    def __init__(self, notation='american'):
        self.notation = notation
        # Simplified patterns (no false positive filtering)
        self.regex_american = re.compile(
            r'\b([A-G](?:[#b])?(?:m(?:aj)?(?:7|9|11|13)?|min|maj7|maj9|'
            r'maj11|maj13|7|9|11|13|6|sus[24]|dim|aug|add\d)?(?:[b#]\d+)*)\b'
        )
        self.regex_european = re.compile(
            r'\b(Do|Re|Mi|Fa|Sol|La|Si)(?:[#b])?'
            r'(?:m(?:aj)?(?:7|9|11|13)?|min|maj7|7|9|11|13|sus[24]|dim|aug)?\b'
        )

    def is_chord_line(self, line):
        """Classify line as chord line or lyric line"""
        words = line.strip().split()
        if not words:
            return False

        pattern = (self.regex_american if self.notation == 'american'
                   else self.regex_european)

        chord_count = sum(1 for word in words if pattern.match(word))
        return (chord_count / len(words)) >= 0.6  # 60% threshold

    def detect_chords(self, text):
        """Returns list of (chord_name, start_pos, end_pos, line_num, is_valid)

        For each word in chord lines:
        - Try to parse with PyChord
        - is_valid=True if PyChord can parse it
        - is_valid=False if PyChord fails (will be styled gray/unstyled)
        """
        from pychord import Chord

        results = []
        lines = text.split('\n')
        char_offset = 0

        for line_num, line in enumerate(lines):
            if self.is_chord_line(line):
                # Try to parse every word in chord line
                words = line.split()
                word_offset = 0

                for word in words:
                    if len(word) < 2:  # Skip single characters
                        word_offset = line.find(word, word_offset) + len(word)
                        continue

                    word_start = line.find(word, word_offset)
                    word_end = word_start + len(word)

                    # Convert European to American if needed
                    chord_to_parse = word
                    if self.notation == 'european':
                        chord_to_parse = self.convert_to_american(word)

                    # Try to parse with PyChord
                    is_valid = False
                    try:
                        Chord(chord_to_parse)
                        is_valid = True
                    except:
                        pass  # Invalid chord, will be marked as such

                    start = char_offset + word_start
                    end = char_offset + word_end
                    results.append((word, start, end, line_num, is_valid))

                    word_offset = word_end

            char_offset += len(line) + 1  # +1 for newline

        return results

# src/ui/text_editor.py
class ChordTextEditor(tk.Text):
    def __init__(self, parent):
        self.typing_timer = None
        self.bind('<Key>', self.on_key_press)

    def on_key_press(self, event):
        """Reset timer on keypress"""
        if self.typing_timer:
            self.after_cancel(self.typing_timer)
        self.typing_timer = self.after(1000, self.scan_for_chords)
```

### Phase 3: Audio Playback with FluidSynth

**Tasks:**
1. Download and bundle soundfont
   - Find small GM soundfont (~5-10MB)
   - Options: GeneralUser GS (~30MB), TimGM6mb (~5.6MB)
   - Place in resources/ folder

2. Implement FluidSynth playback
   - Initialize FluidSynth with error handling
   - Load soundfont from resources
   - **Graceful degradation if FluidSynth/soundfont fails:**
     - Show clear error message to user
     - Disable playback features
     - Allow text editing to continue
   - Convert note names to MIDI note numbers (C4=60, A4=69, etc.)
   - Send note_on/note_off messages
   - Handle multiple simultaneous notes (chords + bass)

3. Chord-to-notes conversion
   - Integrate PyChord library
   - Handle American notation (C, Dm, G7, etc.)
   - **Play chord notes in mid octave (octave 4)**
   - **Add bass note in lower octave (octave 2) for fuller sound**
   - **Handle slash chords** (C/E, G/B, etc.)
     - For slash chords: use specified bass note (e.g., C/E → bass is E)
     - For regular chords: use root note as bass (e.g., Am → bass is A)
   - Convert European notation to American first
   - Convert note names to MIDI numbers

**Key Components:**
```python
# src/audio/player.py
import fluidsynth
from pychord import Chord
import sys
import os

class AudioPlayer:
    def __init__(self):
        # Initialize FluidSynth
        self.fs = fluidsynth.Synth()
        self.fs.start(driver="alsa")  # or "dsound" on Windows

        # Load soundfont
        soundfont_path = self.get_resource_path('resources/soundfont.sf2')
        self.sfid = self.fs.sfload(soundfont_path)
        self.fs.program_select(0, self.sfid, 0, 0)  # Channel 0, piano

        self.playing_notes = []

    def get_resource_path(self, relative_path):
        """Get absolute path to resource for PyInstaller"""
        if hasattr(sys, '_MEIPASS'):
            return os.path.join(sys._MEIPASS, relative_path)
        return os.path.join(os.path.abspath("."), relative_path)

    def note_to_midi(self, note_name):
        """Convert 'C4' to MIDI number 60"""
        note_map = {'C': 0, 'C#': 1, 'Db': 1, 'D': 2, 'D#': 3, 'Eb': 3,
                    'E': 4, 'F': 5, 'F#': 6, 'Gb': 6, 'G': 7, 'G#': 8,
                    'Ab': 8, 'A': 9, 'A#': 10, 'Bb': 10, 'B': 11}

        note = note_name[:-1]  # Remove octave
        octave = int(note_name[-1])
        return note_map[note] + (octave + 1) * 12

    def play_chord(self, chord_name):
        """Play a chord by name with bass note for fuller sound"""
        try:
            chord = Chord(chord_name)

            # Get chord notes in octave 4 (middle range)
            notes = chord.components_with_pitch(root_pitch=4)

            # Stop previous notes
            self.stop()

            # Determine bass note
            if '/' in chord_name:
                # Slash chord: use specified bass note
                bass_note_name = chord_name.split('/')[1]
                # Remove any chord quality markers (e.g., C#m/E → E)
                bass_note_name = bass_note_name.rstrip('m7b#augdimsus0123456789')
                bass_note = bass_note_name + '2'  # Octave 2 for bass
            else:
                # Regular chord: use root note as bass
                root = chord.root.note
                bass_note = root + '2'  # Octave 2 for bass

            # Play bass note (lower octave, slightly louder)
            bass_midi = self.note_to_midi(bass_note)
            self.fs.noteon(0, bass_midi, 110)  # Velocity 110 (louder)
            self.playing_notes.append(bass_midi)

            # Play chord notes (mid octave)
            for note in notes:
                midi_num = self.note_to_midi(note)
                self.fs.noteon(0, midi_num, 90)  # Velocity 90 (softer than bass)
                self.playing_notes.append(midi_num)

        except Exception as e:
            print(f"Could not play chord {chord_name}: {e}")

    def stop(self):
        """Stop all playing notes"""
        for midi_num in self.playing_notes:
            self.fs.noteoff(0, midi_num)
        self.playing_notes = []
```

### Phase 4: Interactive Features

**Tasks:**
1. Make chords clickable
   - **Left click: play chord sound for 1 bar (4 beats) OR until another chord clicked**
   - Middle click: mark as "commented" (red color, ignored)
   - Track commented chords state
   - Stop previous chord when new chord clicked

2. Implement notation switcher
   - Radio buttons in toolbar (American/European)
   - Re-scan text when notation changes
   - Convert between notations for audio playback

3. Handle text editing
   - Clear chord tags in edited regions
   - Re-scan after typing stops
   - Preserve commented state if text unchanged

4. Add keyboard shortcuts
   - Document all shortcuts in code
   - Consistent with standard text editors
   - Space: Play/Pause (during auto-play)
   - Escape: Stop playback

**Key Components:**
```python
# src/ui/text_editor.py
class ChordTextEditor(tk.Text):
    def __init__(self, parent):
        self.commented_chords = set()  # Track position ranges
        self.tag_bind('chord', '<Button-1>', self.on_chord_click)
        self.tag_bind('chord', '<Button-2>', self.on_chord_middle_click)

    def on_chord_click(self, event):
        """Play the clicked chord"""
        chord_name = self.get_chord_at_position(event)
        self.audio_player.play_chord(chord_name)

    def on_chord_middle_click(self, event):
        """Mark chord as commented (red)"""
        chord_range = self.get_chord_range_at_position(event)
        self.commented_chords.add(chord_range)
        self.tag_config(chord_range, foreground='red')
```

### Phase 5: Auto-Play Feature

**Tasks:**
1. Create playback controls toolbar
   - Play button: start playback sequence
   - Pause/Resume button: pause and resume
   - Stop button: stop playback and reset
   - **BPM slider: adjust tempo (60-240 BPM, default 120)**
   - Display current BPM value

2. Implement sequential playback with timing
   - **Default: 4/4 time signature, 120 BPM**
   - **Each chord plays for 1 whole bar (4 beats) by default**
   - Calculate delay from BPM: `delay_seconds = (60 / BPM) * 4`
   - Get all detected chords in order
   - Skip commented (red) chords
   - Play each chord with calculated delay
   - Update UI to show current chord
   - Handle pause/resume state

3. Thread management
   - Run playback in separate thread
   - Avoid blocking UI
   - Handle stop interruption cleanly

**Key Components:**
```python
# src/audio/player.py
class AudioPlayer:
    def __init__(self):
        self.playing = False
        self.paused = False
        self.playback_thread = None
        self.bpm = 120  # Default BPM
        self.time_signature = (4, 4)  # Default 4/4

    def calculate_chord_duration(self, beats=4):
        """Calculate duration in seconds for given number of beats

        Args:
            beats: Number of beats (default 4 = whole bar in 4/4)

        Returns:
            Duration in seconds
        """
        # 60 seconds per minute / BPM = seconds per beat
        seconds_per_beat = 60.0 / self.bpm
        return seconds_per_beat * beats

    def play_sequence(self, chord_list, bpm=120):
        """Play all chords in sequence

        Args:
            chord_list: List of chord names to play
            bpm: Beats per minute (60-240)
        """
        self.bpm = bpm
        self.playing = True
        self.playback_thread = threading.Thread(
            target=self._playback_loop,
            args=(chord_list,)
        )
        self.playback_thread.start()

    def _playback_loop(self, chord_list):
        """Thread function for sequential playback"""
        for i, chord in enumerate(chord_list):
            if not self.playing:
                break
            while self.paused:
                time.sleep(0.1)

            # Play chord
            self.play_chord(chord)

            # Calculate duration (default: 1 whole bar = 4 beats in 4/4)
            beats_per_bar = self.time_signature[0]
            duration = self.calculate_chord_duration(beats_per_bar)

            # Wait for duration
            time.sleep(duration)

# UI component for BPM slider
bpm_var = tk.IntVar(value=120)
bpm_slider = ttk.Scale(
    toolbar,
    from_=60, to=240,
    variable=bpm_var,
    orient=tk.HORIZONTAL,
    length=200
)
bpm_label = ttk.Label(toolbar, text="BPM:")
bpm_value_label = ttk.Label(toolbar, textvariable=bpm_var)

# Update label when slider changes
def on_bpm_change(*args):
    bpm_value_label.config(text=f"{bpm_var.get()} BPM")
bpm_var.trace('w', on_bpm_change)
```

### Phase 6: Packaging & Distribution

**Tasks:**
1. Create Makefile for build automation
   - Targets: run, test, build-windows, build-linux, clean
   - Handle PyInstaller and AppImage builds
   - Copy FluidSynth libraries and soundfont

2. Create PyInstaller spec file
   - Single-file executable mode
   - Include icon and soundfont
   - Bundle FluidSynth library
   - Hide console window for GUI mode

3. Build with Makefile
   ```bash
   make build-windows   # Build Windows .exe
   make build-linux     # Build Linux AppImage
   make test           # Run tests
   make clean          # Clean build artifacts
   ```

4. Test on target platforms
   - Windows 10/11 testing
   - Ubuntu 22.04/Fedora 39 testing
   - Verify audio playback works
   - Check file operations

**Makefile:**
```makefile
.PHONY: run test build-windows build-linux clean install

# Variables
PYTHON := pipenv run python
PYINSTALLER := pipenv run pyinstaller
SPEC_FILE := build/chord-notepad.spec

# Run application
run:
	$(PYTHON) src/main.py

# Run tests
test:
	$(PYTHON) -m pytest tests/

# Install dependencies
install:
	pipenv install --dev

# Build Windows executable
build-windows:
	$(PYINSTALLER) --clean $(SPEC_FILE)
	@echo "Windows executable: dist/ChordNotepad.exe"

# Build Linux AppImage
build-linux:
	$(PYINSTALLER) --clean $(SPEC_FILE)
	cd dist && appimage-builder --recipe ../build/AppImageBuilder.yml
	@echo "Linux AppImage: dist/*.AppImage"

# Clean build artifacts
clean:
	rm -rf build/ dist/ __pycache__ .pytest_cache
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
```

**PyInstaller Spec File:**
```python
# build/chord-notepad.spec
import sys
import os
from PyInstaller.utils.hooks import collect_dynamic_libs

# Collect FluidSynth binaries
binaries = collect_dynamic_libs('fluidsynth')

a = Analysis(
    ['src/main.py'],
    pathex=[],
    binaries=binaries,
    datas=[
        ('resources/icon.png', 'resources'),
        ('resources/soundfont.sf2', 'resources')
    ],
    hiddenimports=['pychord', 'fluidsynth'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ChordNotepad',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='resources/icon.png',
)
```

---

## Future Enhancements (Post-MVP)

These features should be implemented after the core functionality is complete and stable.

### Phase 7: Visual Feedback & Playback Enhancements

**Tasks:**
1. Visual feedback during auto-play
   - **Highlight currently playing chord** (yellow background or similar)
   - **Auto-scroll** to keep current chord visible
   - Update as playback progresses
   - Clear highlight when stopped

2. Loop/repeat mode
   - **Toggle button**: Loop entire song
   - When enabled, restart from beginning after last chord
   - Works with play/pause/stop controls

3. Settings persistence
   - Save settings to JSON file on change
   - Location: `~/.config/chord-notepad/settings.json` (Linux) or `%APPDATA%/ChordNotepad/settings.json` (Windows)
   - **Settings to persist:**
     - Last used BPM
     - Last used instrument (when Phase 8 implemented)
     - American vs European notation choice
     - Window size and position
     - Last opened file path
     - Font family and size
     - Loop mode enabled/disabled
   - Load settings on startup
   - Use defaults if settings file missing

4. Recent files list
   - Track last 5-10 opened files
   - Show in File menu
   - Click to open
   - Persist in settings file

### Phase 8: Instrument Selection

**Tasks:**
1. Enumerate available instruments from soundfont
   - Read GM (General MIDI) program numbers from soundfont
   - Standard instruments: Piano (0), Guitar (24-31), Bass (32-39), Strings (40-55), etc.
   - Create instrument picker in toolbar

2. Implement instrument switching
   - Use FluidSynth `program_select()` to change instrument
   - Apply to channel 0 (or allow multiple channels)
   - Save instrument preference

**UI Components:**
```python
# Toolbar dropdown for instrument selection
instrument_var = tk.StringVar()
instrument_dropdown = ttk.Combobox(
    toolbar,
    textvariable=instrument_var,
    values=["Piano", "Acoustic Guitar", "Electric Bass", "Strings", ...]
)
instrument_dropdown.bind('<<ComboboxSelected>>', on_instrument_change)

def on_instrument_change(event):
    instrument_name = instrument_var.get()
    program_number = INSTRUMENT_MAP[instrument_name]
    audio_player.set_instrument(program_number)
```

### Phase 9: Options/Preferences Dialog

**Tasks:**
1. Create preferences dialog window
   - Custom soundfont path selection (file picker)
   - Default instrument selection
   - Playback duration for chords (default 1 second)
   - MIDI velocity (volume) slider
   - Auto-save preferences to JSON file

2. Settings storage
   - Save to `~/.config/chord-notepad/settings.json` (Linux)
   - Save to `%APPDATA%/ChordNotepad/settings.json` (Windows)
   - Load on startup

**UI Components:**
```python
# Menu: Edit → Preferences
def show_preferences():
    pref_window = tk.Toplevel()
    pref_window.title("Preferences")

    # Soundfont selection
    ttk.Label(pref_window, text="Soundfont:").grid(row=0, column=0)
    soundfont_entry = ttk.Entry(pref_window, width=40)
    soundfont_entry.grid(row=0, column=1)
    ttk.Button(pref_window, text="Browse...",
              command=select_soundfont).grid(row=0, column=2)

    # Default instrument
    ttk.Label(pref_window, text="Default Instrument:").grid(row=1, column=0)
    # ... instrument dropdown

    # Chord duration
    ttk.Label(pref_window, text="Chord Duration (s):").grid(row=2, column=0)
    duration_spinbox = ttk.Spinbox(pref_window, from_=0.5, to=5.0, increment=0.1)
    duration_spinbox.grid(row=2, column=1)

    # Save/Cancel buttons
```

### Phase 10: Help/About & Documentation

**Tasks:**
1. Create Help menu
   - Help → Keyboard Shortcuts (show reference dialog)
   - Help → About (show version, credits, links)

2. Keyboard shortcuts reference dialog
   - List all shortcuts in organized table
   - File operations, editing, playback, etc.
   - Copy reference to clipboard option

3. About dialog
   - Application name and version
   - Credits and attribution
   - Link to GitHub/documentation
   - License information

**Keyboard Shortcuts to Document:**
```
File Operations:
  Ctrl+N          New File
  Ctrl+O          Open File
  Ctrl+S          Save
  Ctrl+Shift+S    Save As
  Ctrl+Q          Quit

Editing:
  Ctrl+Z          Undo
  Ctrl+Y          Redo
  Ctrl+C          Copy
  Ctrl+V          Paste
  Ctrl+X          Cut
  Ctrl+A          Select All
  Ctrl+F          Find (future)

View:
  Ctrl+Plus       Increase Font Size
  Ctrl+Minus      Decrease Font Size
  Ctrl+0          Reset Font Size
  Ctrl+Wheel      Zoom In/Out

Playback:
  Space           Play/Pause
  Escape          Stop
  Click Chord     Play Single Chord
  Middle-Click    Comment/Uncomment Chord
```

### Phase 11: Transpose Dialog

**Tasks:**
1. Create transpose dialog
   - Numeric spinner: -12 to +12 semitones
   - Preview button (show what chords will become)
   - Apply button (transpose all chords in document)

2. Implement transposition logic
   - Parse all detected chords
   - Transpose each chord by N semitones
   - Handle enharmonic equivalents (C# vs Db)
   - Replace chords in text while preserving formatting

**Transposition Algorithm:**
```python
def transpose_chord(chord_name, semitones):
    """Transpose a chord by N semitones

    Examples:
        transpose_chord("C", 2) → "D"
        transpose_chord("Am7", -3) → "F#m7"
        transpose_chord("G/B", 5) → "C/E"
    """
    from pychord import Chord

    # Parse chord
    chord = Chord(chord_name)

    # Get root note
    root = chord.root

    # Transpose root
    note_map = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    root_index = note_map.index(root)
    new_index = (root_index + semitones) % 12
    new_root = note_map[new_index]

    # Rebuild chord with new root
    quality = chord.quality.quality  # Keep quality (m, 7, maj7, etc.)
    new_chord_name = new_root + quality

    # Handle slash chords
    if '/' in chord_name:
        bass = chord_name.split('/')[1]
        bass_index = note_map.index(bass)
        new_bass_index = (bass_index + semitones) % 12
        new_bass = note_map[new_bass_index]
        new_chord_name += '/' + new_bass

    return new_chord_name

def transpose_document(text, semitones):
    """Transpose all chords in document"""
    # Detect all chords
    chords = detector.detect_chords(text)

    # Transpose in reverse order (to preserve positions)
    for chord_name, start, end, line_num, is_valid in reversed(chords):
        if is_valid:
            new_chord = transpose_chord(chord_name, semitones)
            # Replace in text
            text = text[:start] + new_chord + text[end:]

    return text
```

**UI Dialog:**
```python
def show_transpose_dialog():
    dialog = tk.Toplevel()
    dialog.title("Transpose")

    ttk.Label(dialog, text="Transpose by:").grid(row=0, column=0)
    semitones_var = tk.IntVar(value=0)
    spinbox = ttk.Spinbox(dialog, from_=-12, to=12,
                         textvariable=semitones_var, width=5)
    spinbox.grid(row=0, column=1)
    ttk.Label(dialog, text="semitones").grid(row=0, column=2)

    # Preview
    def preview():
        semitones = semitones_var.get()
        # Show what chords will become
        preview_text = "C → " + transpose_chord("C", semitones) + "\n"
        preview_text += "Am → " + transpose_chord("Am", semitones) + "\n"
        # ... show more examples
        messagebox.showinfo("Preview", preview_text)

    ttk.Button(dialog, text="Preview", command=preview).grid(row=1, column=0)

    # Apply
    def apply_transpose():
        semitones = semitones_var.get()
        current_text = text_editor.get("1.0", "end-1c")
        new_text = transpose_document(current_text, semitones)
        text_editor.delete("1.0", "end")
        text_editor.insert("1.0", new_text)
        dialog.destroy()

    ttk.Button(dialog, text="Apply", command=apply_transpose).grid(row=1, column=1)
    ttk.Button(dialog, text="Cancel", command=dialog.destroy).grid(row=1, column=2)
```

### Phase 12: Roman Numeral Notation

**Tasks:**
1. Add key selection dropdown
   - All 12 major keys: C, C#, D, Eb, E, F, F#, G, Ab, A, Bb, B
   - All 12 minor keys: Cm, C#m, Dm, etc.
   - Toolbar dropdown for quick key switching

2. Implement Roman numeral chord detection
   - Regex pattern: `\b([IV]{1,4}|[iv]{1,4}|[#b]?[IV]{1,4})\b`
   - Case matters: I, II, III, IV, V, VI, VII (major)
   - Lowercase: i, ii, iii, iv, v, vi, vii° (minor/diminished)
   - Accidentals: #IV, bVII, etc.

3. Convert Roman numerals to actual chords based on key
   - I in C major → C
   - vi in C major → Am
   - V7 in G major → D7
   - bVII in A minor → G

4. Bi-directional conversion
   - Display detected letter chords as Roman numerals (optional mode)
   - Allow mixing both notations in same document

**Roman Numeral System:**
```python
# Major scale degrees
MAJOR_SCALE_CHORDS = {
    'I': 'maj',      # Major
    'ii': 'm',       # Minor
    'iii': 'm',      # Minor
    'IV': 'maj',     # Major
    'V': 'maj',      # Major (often V7)
    'vi': 'm',       # Minor
    'vii°': 'dim',   # Diminished
}

def roman_to_chord(numeral, key):
    """Convert Roman numeral to chord name

    Examples:
        roman_to_chord("I", "C") → "C"
        roman_to_chord("vi", "C") → "Am"
        roman_to_chord("V7", "G") → "D7"
        roman_to_chord("bVII", "Am") → "G"
    """
    # Parse key
    key_root, key_quality = parse_key(key)  # "C" → ("C", "major")

    # Get scale
    scale = get_scale(key_root, key_quality)
    # C major scale: ['C', 'D', 'E', 'F', 'G', 'A', 'B']

    # Parse numeral
    accidental = ''
    if numeral.startswith('#') or numeral.startswith('b'):
        accidental = numeral[0]
        numeral = numeral[1:]

    # Convert numeral to scale degree
    roman_map = {'I': 0, 'II': 1, 'III': 2, 'IV': 3, 'V': 4, 'VI': 5, 'VII': 6}
    degree = roman_map[numeral.upper().rstrip('°7')]

    # Get note
    note = scale[degree]

    # Apply accidental
    if accidental == '#':
        note = sharpen(note)
    elif accidental == 'b':
        note = flatten(note)

    # Get quality
    is_minor = numeral[0].islower()
    is_diminished = '°' in numeral
    has_seventh = '7' in numeral

    if is_diminished:
        quality = 'dim'
    elif is_minor:
        quality = 'm'
    else:
        quality = ''

    if has_seventh:
        quality += '7'

    return note + quality

def chord_to_roman(chord_name, key):
    """Convert chord to Roman numeral in given key

    Examples:
        chord_to_roman("C", "C") → "I"
        chord_to_roman("Am", "C") → "vi"
        chord_to_roman("D7", "G") → "V7"
    """
    # Reverse of roman_to_chord
    # ... implementation
```

**UI Components:**
```python
# Key selection in toolbar
ttk.Label(toolbar, text="Key:").pack(side=tk.LEFT, padx=5)
key_var = tk.StringVar(value="C")
key_dropdown = ttk.Combobox(
    toolbar,
    textvariable=key_var,
    values=["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B",
            "Cm", "C#m", "Dm", "Ebm", "Em", "Fm", "F#m", "Gm", "Abm", "Am", "Bbm", "Bm"],
    width=8
)
key_dropdown.pack(side=tk.LEFT, padx=5)

# Toggle Roman numerals display
show_roman_var = tk.BooleanVar(value=False)
ttk.Checkbutton(toolbar, text="Show as Roman Numerals",
               variable=show_roman_var,
               command=on_toggle_roman).pack(side=tk.LEFT, padx=5)
```

### Phase 13: Advanced Timing & ChordPro Tags

**Tasks:**

1. Implement beat count annotations
   - Parse `*` notation: `C*2` means C for 2 beats
   - Unannotated chords default to whole bar (4 beats in 4/4)
   - Update playback to respect beat counts
   - Update detection to preserve `*N` suffix

2. Implement ChordPro-style directive tags
   - `{tempo: 120}` - change BPM mid-song
   - `{time: 4/4}` - change time signature mid-song
   - `{key: C}` - set base key (used by Roman numeral feature)
   - **`{label: intro}` - mark position with label**
   - **`{loop: intro 3}` - loop from label N times**
   - Parse directives in chord detection
   - Apply changes at directive location during playback

3. Update playback engine
   - Track current BPM and time signature
   - Update when directives encountered
   - Calculate beat durations dynamically

**Beat Count Notation:**
```
Example song with beat annotations:

C*4      Am*4     F*2  G*2
When I   find     my - self

Dm*3  G*1    C*4
In    times  of trouble
```

**Calculation:**
- C*4 at 120 BPM = (60/120) * 4 = 2 seconds
- F*2 at 120 BPM = (60/120) * 2 = 1 second
- Unannotated = whole bar = time_signature[0] beats

**ChordPro Tags Example:**
```
{tempo: 120}
{time: 4/4}
{key: C}

C        Am       F        G
Verse lyrics here...

{tempo: 140}
F        G        C*2  Am*2
Faster chorus here...

{time: 3/4}
Am       F        C
Waltz section...
```

**Implementation:**
```python
# src/chord/detector.py
import re

class ChordDetector:
    def __init__(self, notation='american'):
        self.notation = notation
        # Pattern for beat count: chord name followed by *N
        self.beat_pattern = re.compile(r'([A-G][#b]?(?:m|maj|dim|aug|sus)?[0-9]*(?:/[A-G][#b]?)?)\*(\d+)')
        # Pattern for directives
        self.directive_pattern = re.compile(r'\{(\w+):\s*([^}]+)\}')

    def parse_directive(self, line):
        """Parse ChordPro-style directives

        Returns: (directive_type, value) or (None, None)

        Examples:
            "{tempo: 120}" → ("tempo", 120)
            "{time: 3/4}" → ("time", (3, 4))
            "{key: Am}" → ("key", "Am")
        """
        match = self.directive_pattern.search(line)
        if not match:
            return None, None

        directive_type = match.group(1).lower()
        value_str = match.group(2).strip()

        if directive_type == "tempo":
            return "tempo", int(value_str)
        elif directive_type == "time":
            parts = value_str.split('/')
            return "time", (int(parts[0]), int(parts[1]))
        elif directive_type == "key":
            return "key", value_str
        else:
            return directive_type, value_str

    def extract_beat_count(self, chord_text):
        """Extract beat count from chord notation

        Examples:
            "C*4" → ("C", 4)
            "Am7*2" → ("Am7", 2)
            "C" → ("C", None)  # Default to whole bar
        """
        match = self.beat_pattern.match(chord_text)
        if match:
            chord_name = match.group(1)
            beat_count = int(match.group(2))
            return chord_name, beat_count
        return chord_text, None

    def detect_chords(self, text):
        """Returns list of (chord_name, start, end, line_num, is_valid, beat_count)"""
        from pychord import Chord

        results = []
        lines = text.split('\n')
        char_offset = 0

        for line_num, line in enumerate(lines):
            # Check for directives
            directive_type, directive_value = self.parse_directive(line)
            if directive_type:
                # Return directive as special entry
                results.append((f"{{directive:{directive_type}}}",
                              char_offset,
                              char_offset + len(line),
                              line_num,
                              True,
                              directive_value))
                char_offset += len(line) + 1
                continue

            if self.is_chord_line(line):
                words = line.split()
                word_offset = 0

                for word in words:
                    if len(word) < 2:
                        word_offset = line.find(word, word_offset) + len(word)
                        continue

                    word_start = line.find(word, word_offset)
                    word_end = word_start + len(word)

                    # Extract beat count
                    chord_name, beat_count = self.extract_beat_count(word)

                    # Convert European to American if needed
                    chord_to_parse = chord_name
                    if self.notation == 'european':
                        chord_to_parse = self.convert_to_american(chord_name)

                    # Try to parse with PyChord
                    is_valid = False
                    try:
                        Chord(chord_to_parse)
                        is_valid = True
                    except:
                        pass

                    start = char_offset + word_start
                    end = char_offset + word_end
                    results.append((chord_name, start, end, line_num, is_valid, beat_count))

                    word_offset = word_end

            char_offset += len(line) + 1

        return results

# src/audio/player.py
class AudioPlayer:
    def __init__(self):
        # ... existing code ...
        self.bpm = 120
        self.time_signature = (4, 4)

    def _playback_loop(self, chord_list_with_beats):
        """Thread function for sequential playback

        Args:
            chord_list_with_beats: List of (chord_name, beat_count, directive_info)
        """
        for item in chord_list_with_beats:
            if not self.playing:
                break
            while self.paused:
                time.sleep(0.1)

            chord_name, beat_count, directive_info = item

            # Handle directives
            if directive_info:
                directive_type, value = directive_info
                if directive_type == "tempo":
                    self.bpm = value
                    continue
                elif directive_type == "time":
                    self.time_signature = value
                    continue
                # ... handle other directives

            # Determine beat count
            if beat_count is None:
                # Default: whole bar
                beat_count = self.time_signature[0]

            # Play chord
            self.play_chord(chord_name)

            # Calculate duration
            duration = self.calculate_chord_duration(beat_count)
            time.sleep(duration)
```

**Examples:**

**Simple (MVP behavior):**
```
C    Am    F    G
```
At 120 BPM, 4/4: Each chord = 2 seconds (4 beats)

**With beat counts:**
```
C*4    Am*2  G*2    F*4
```
At 120 BPM: C=2s, Am=1s, G=1s, F=2s

**With directives:**
```
{tempo: 100}
{time: 4/4}

C*4       Am*4      F*2   G*2

{tempo: 140}
C*2  G*2  Am*2  F*2
```
First line at 100 BPM, second line at 140 BPM (faster)

**With labels and loops:**
```
{tempo: 120}

{label: intro}
C*4    G*4    Am*4   F*4

{label: verse}
C*2 G*2   Am*2 F*2   C*2 G*2   F*4

{label: chorus}
F*2 G*2   C*4   Am*2 G*2   F*4

{loop: intro 1}
{loop: verse 2}
{loop: chorus 2}
{loop: verse 1}
{loop: chorus 2}
```
Structure: Intro once, Verse twice, Chorus twice, Verse once, Chorus twice

### Phase 14: Metronome & Capo Support

**Tasks:**

1. Metronome click track
   - Toggle button: Enable/Disable metronome
   - Play click sound on each beat during auto-play
   - Use high-pitched short sound (woodblock or similar from soundfont)
   - Sync with BPM and time signature
   - Independent volume control for clicks

2. Capo support
   - `{capo: N}` directive (where N = fret number 1-12)
   - **Transpose display only, not actual playback**
   - Show chords as if capo is applied
   - Example: `{capo: 2}` - C chord displays as D, but still plays C
   - Useful for guitarists to match shapes
   - Toggle: "Show as if capo at fret X" vs "Show concert pitch"

**Metronome Implementation:**
```python
class AudioPlayer:
    def __init__(self):
        # ... existing code ...
        self.metronome_enabled = False
        self.click_midi_note = 76  # High woodblock sound

    def play_metronome_click(self, is_downbeat=False):
        """Play metronome click

        Args:
            is_downbeat: True for beat 1 (louder), False for other beats
        """
        if not self.metronome_enabled:
            return

        velocity = 127 if is_downbeat else 90
        self.fs.noteon(9, self.click_midi_note, velocity)  # Channel 9 = percussion
        time.sleep(0.05)  # Short click
        self.fs.noteoff(9, self.click_midi_note)

    def _playback_loop(self, chord_list_with_beats):
        """Enhanced playback with metronome"""
        for item in chord_list_with_beats:
            # ... chord playback ...

            # Play metronome clicks for this chord's duration
            beat_count = self.get_beat_count(item)
            seconds_per_beat = 60.0 / self.bpm

            for beat in range(beat_count):
                if not self.playing:
                    break

                is_downbeat = (beat == 0)
                self.play_metronome_click(is_downbeat)
                time.sleep(seconds_per_beat)
```

**Capo Support:**
```python
# In chord detector
class ChordDetector:
    def __init__(self):
        self.capo_fret = 0  # 0 = no capo

    def parse_directive(self, line):
        # ... existing code ...
        if directive_type == "capo":
            return "capo", int(value_str)

    def display_chord_with_capo(self, chord_name):
        """Transpose chord display for capo

        Example: capo_fret=2, chord="C" → "D" (display only)
        """
        if self.capo_fret == 0:
            return chord_name

        # Transpose down by capo_fret semitones for display
        return transpose_chord(chord_name, -self.capo_fret)
```

**UI Components:**
```python
# Metronome toggle
metronome_var = tk.BooleanVar(value=False)
metronome_check = ttk.Checkbutton(
    toolbar,
    text="Metronome",
    variable=metronome_var,
    command=lambda: audio_player.set_metronome(metronome_var.get())
)

# Capo selector
ttk.Label(toolbar, text="Capo:").pack(side=tk.LEFT)
capo_var = tk.IntVar(value=0)
capo_spin = ttk.Spinbox(
    toolbar,
    from_=0, to=12,
    textvariable=capo_var,
    width=3,
    command=lambda: on_capo_change(capo_var.get())
)
```

---

## Technical Implementation Details

### 1. Note Frequency Mapping

```python
# Standard A4 = 440Hz tuning
NOTE_FREQUENCIES = {
    'C4': 261.63,  'C#4': 277.18,  'D4': 293.66,  'D#4': 311.13,
    'E4': 329.63,  'F4': 349.23,   'F#4': 369.99, 'G4': 392.00,
    'G#4': 415.30, 'A4': 440.00,   'A#4': 466.16, 'B4': 493.88,
    'C5': 523.25,  # ... extend to other octaves
}

# Alternative: Calculate from formula
# frequency = 440 * 2^((n - 49) / 12)
# where n is MIDI note number
```

### 2. European to American Notation Conversion

```python
EUROPEAN_TO_AMERICAN = {
    'Do': 'C',
    'Re': 'D',
    'Mi': 'E',
    'Fa': 'F',
    'Sol': 'G',
    'La': 'A',
    'Si': 'B',
}

def convert_european_to_american(chord_name):
    for eu, am in EUROPEAN_TO_AMERICAN.items():
        if chord_name.startswith(eu):
            return chord_name.replace(eu, am, 1)
    return chord_name
```

### 3. Chord Voicing with Bass Note

**Strategy:** For fuller, more musical sound, play each chord with:
- **Bass note** in low octave (octave 2) - slightly louder
- **Chord notes** in mid octave (octave 4) - slightly softer

```python
from pychord import Chord

def get_chord_voicing(chord_name):
    """Get chord voicing with bass note for fuller sound

    Returns: (bass_note, chord_notes)

    Examples:
        "C"     → ('C2', ['C4', 'E4', 'G4'])
        "Am7"   → ('A2', ['A4', 'C5', 'E5', 'G5'])
        "C/E"   → ('E2', ['C4', 'E4', 'G4'])  # Slash chord: bass is E
        "Am7/G" → ('G2', ['A4', 'C5', 'E5', 'G5'])  # Slash chord: bass is G
    """
    chord = Chord(chord_name)

    # Get chord notes in middle octave
    chord_notes = chord.components_with_pitch(root_pitch=4)

    # Determine bass note
    if '/' in chord_name:
        # Slash chord: extract bass note
        bass_note_name = chord_name.split('/')[1]
        # Clean up (remove any modifiers)
        bass_note_name = bass_note_name.rstrip('m7b#augdimsus0123456789')
        bass_note = bass_note_name + '2'
    else:
        # Regular chord: use root as bass
        root = chord.root.note
        bass_note = root + '2'

    return bass_note, chord_notes

# Example usage:
bass, chord_notes = get_chord_voicing("C")
# bass = 'C2'
# chord_notes = ['C4', 'E4', 'G4']
# Play: C2 (loud) + C4, E4, G4 (softer) = fuller sound

bass, chord_notes = get_chord_voicing("C/E")
# bass = 'E2'  # Bass note from slash chord
# chord_notes = ['C4', 'E4', 'G4']
# Play: E2 (loud) + C4, E4, G4 (softer) = C major with E in bass
```

**MIDI Velocity Settings:**
- Bass note: velocity 110 (louder, more prominent)
- Chord notes: velocity 90 (softer, supporting)

### 4. Line Classification Example

**Sample Chord Sheet:**
```
Amazing Grace

C        C7        F
Amazing grace how sweet the sound
F           C              Am
That saved a wretch like me
C           C7         F
I once was lost but now am found
F          C         G7      C
Was blind but now I see
```

**Line-by-Line Classification:**
```python
Line 0: "Amazing Grace"
  Words: ["Amazing", "Grace"]
  Chords detected: 0
  Ratio: 0/2 = 0.0 < 0.6 → LYRIC LINE ✗

Line 2: "C        C7        F"
  Words: ["C", "C7", "F"]
  Chords detected: 3
  Ratio: 3/3 = 1.0 >= 0.6 → CHORD LINE ✓
  Detected: C, C7, F

Line 3: "Amazing grace how sweet the sound"
  Words: ["Amazing", "grace", "how", "sweet", "the", "sound"]
  Chords detected: 0
  Ratio: 0/6 = 0.0 < 0.6 → LYRIC LINE ✗

Line 4: "F           C              Am"
  Words: ["F", "C", "Am"]
  Chords detected: 3
  Ratio: 3/3 = 1.0 >= 0.6 → CHORD LINE ✓
  Detected: F, C, Am (note: "Am" is OK here, not "am I")

Line 5: "That saved a wretch like me"
  Words: ["That", "saved", "a", "wretch", "like", "me"]
  Chords detected: 0 (even though "a" exists)
  Ratio: 0/6 = 0.0 < 0.6 → LYRIC LINE ✗
```

**Result:** Only lines 2, 4, etc. (chord lines) have their words processed as clickable chords. Lyric lines are completely ignored, eliminating false positives.

### 5. PyChord-Based Validation

**Example with slash chords and edge cases:**

```
C    G/B    Am    C/G    F    C/E    Dm7    Gsus4

Verse 1:
D    A/C#   Bm    D/A    G    repeat    (intro)

Time to say goodbye...
```

**Detection Results (using PyChord parser):**

Line 0: `C    G/B    Am    C/G    F    C/E    Dm7    Gsus4`
- ✓ **C** - PyChord parses → blue, clickable
- ✓ **G/B** - PyChord parses slash chord → blue, clickable
- ✓ **Am** - PyChord parses → blue, clickable
- ✓ **C/G** - PyChord parses slash chord → blue, clickable
- ✓ **F** - PyChord parses → blue, clickable
- ✓ **C/E** - PyChord parses slash chord → blue, clickable
- ✓ **Dm7** - PyChord parses → blue, clickable
- ✓ **Gsus4** - PyChord parses → blue, clickable

Line 3: `D    A/C#   Bm    D/A    G    repeat    (intro)`
- ✓ **D** - PyChord parses → blue, clickable
- ✓ **A/C#** - PyChord parses slash chord with accidental → blue, clickable
- ✓ **Bm** - PyChord parses → blue, clickable
- ✓ **D/A** - PyChord parses → blue, clickable
- ✓ **G** - PyChord parses → blue, clickable
- ✗ **repeat** - PyChord fails to parse → gray, not clickable
- ✗ **(intro)** - PyChord fails to parse → gray, not clickable

**Visual Representation:**
```
Chord line with valid and invalid:
[C]ᵇˡᵘᵉ  [G/B]ᵇˡᵘᵉ  [Am]ᵇˡᵘᵉ  [repeat]ᵍʳᵃʸ  [(intro)]ᵍʳᵃʸ

Where:
- Blue + underlined = Valid chord (PyChord parsed it), clickable, will play
- Gray + no underline = Invalid/unparseable word, ignored
```

**Advantages of this approach:**
- PyChord is the authority on valid chords (knows more than regex)
- Handles all chord notations PyChord supports automatically
- No need to maintain complex regex patterns
- Regex only used for line classification heuristic
- Simpler, more maintainable code

### 6. Wave Synthesis with Envelope

```python
def generate_tone_with_envelope(frequency, duration=1.0, sample_rate=44100):
    """Generate sine wave with ADSR envelope for natural sound"""
    samples = int(duration * sample_rate)
    t = np.linspace(0, duration, samples, False)

    # Generate sine wave
    wave = np.sin(2 * np.pi * frequency * t)

    # Apply ADSR envelope
    attack = int(0.05 * sample_rate)   # 50ms attack
    decay = int(0.1 * sample_rate)     # 100ms decay
    sustain_level = 0.7
    release = int(0.2 * sample_rate)   # 200ms release

    envelope = np.ones(samples)

    # Attack phase
    envelope[:attack] = np.linspace(0, 1, attack)

    # Decay phase
    envelope[attack:attack+decay] = np.linspace(1, sustain_level, decay)

    # Sustain phase (already at sustain_level)

    # Release phase
    release_start = samples - release
    envelope[release_start:] = np.linspace(sustain_level, 0, release)

    return wave * envelope
```

### 6. Handling Text Position Tracking

```python
def get_chord_at_position(text_widget, index):
    """Get chord name at given text position"""
    # Get all tags at this position
    tags = text_widget.tag_names(index)

    # Find chord tag
    for tag in tags:
        if tag.startswith('chord_'):
            # Extract chord name from tag
            chord_name = tag.replace('chord_', '')
            return chord_name
    return None

def apply_chord_tags(text_widget, chord_positions):
    """Apply tags to detected chords

    chord_positions: list of (chord_name, start, end, line_num, is_valid)
    - is_valid=True: PyChord parsed it successfully (blue, clickable)
    - is_valid=False: PyChord failed to parse (gray, not clickable)
    """
    # Clear existing chord tags
    for tag in text_widget.tag_names():
        if tag.startswith('chord_') or tag.startswith('invalid_'):
            text_widget.tag_delete(tag)

    # Apply new tags
    for chord_name, start, end, line_num, is_valid in chord_positions:
        if is_valid:
            # Valid chord - blue and clickable
            tag_name = f'chord_{chord_name}_{start}'
            text_widget.tag_add(tag_name, f'1.0+{start}c', f'1.0+{end}c')
            text_widget.tag_config(tag_name, foreground='blue', underline=True)
            # Bind click event to play chord
            text_widget.tag_bind(tag_name, '<Button-1>',
                               lambda e, c=chord_name: play_chord(c))
        else:
            # Invalid chord - gray, no underline, not clickable
            tag_name = f'invalid_{chord_name}_{start}'
            text_widget.tag_add(tag_name, f'1.0+{start}c', f'1.0+{end}c')
            text_widget.tag_config(tag_name, foreground='gray')
```

---

## Testing Strategy

### Unit Tests

1. **Chord Detection Tests**
   - Test line classification (chord lines vs lyric lines)
   - Test American notation patterns
   - Test European notation patterns
   - Verify no false positives in lyric lines ("am I dreaming")
   - Test mixed chord/lyric documents
   - Test edge cases (empty lines, punctuation, partial matches)

2. **Conversion Tests**
   - Test chord-to-notes conversion (PyChord)
   - Test note-to-frequency mapping
   - Test European-to-American conversion

3. **Audio Playback Tests**
   - Test FluidSynth initialization
   - Test soundfont loading
   - Test note-to-MIDI conversion
   - Test chord playback (multiple simultaneous notes)
   - Test note_on/note_off messaging

### Integration Tests

1. **UI Tests**
   - Test typing timer (verify 1-second delay)
   - Test chord tagging after detection
   - Test click event handling
   - Test notation switching

2. **Playback Tests**
   - Test single chord playback
   - Test sequential playback
   - Test pause/resume functionality
   - Test stop functionality
   - Test slider delay adjustment

### Manual Testing Checklist

- [ ] Load various text files with chords
- [ ] Type text and verify chord detection after 1 second
- [ ] Click individual chords and verify sound
- [ ] Middle-click chords and verify red color
- [ ] Switch between American/European notation
- [ ] Use Play button to play all chords
- [ ] Adjust delay slider during playback
- [ ] Pause and resume playback
- [ ] Stop playback mid-sequence
- [ ] Edit text and verify tags update correctly
- [ ] Save and load files
- [ ] Copy/paste text with chords

---

## Performance Considerations

### Optimization Strategies

1. **Chord Detection:**
   - Compile regex patterns once at initialization
   - Only re-scan modified text regions (optional enhancement)
   - Limit detection to visible text (optional for large files)

2. **Audio Synthesis:**
   - Cache generated waveforms for repeated chords
   - Pre-generate common chords at startup
   - Use lower sample rate (22050 Hz) if performance issues

3. **UI Responsiveness:**
   - Run audio synthesis in background thread
   - Use queue for playback requests
   - Debounce typing timer (already planned with 1s delay)

### Memory Management

- Clear unused Sound objects after playback
- Limit cache size for generated waveforms
- Use generators for large chord sequences

---

## Additional Future Ideas (Beyond Phase 14)

Features that may be considered for future versions but are not currently planned:

### Not Now (Deferred):
- **Export to PDF/image** - Print/export chord sheets as PDF or image files
- **Chord diagrams** - Show guitar/piano fingering diagrams for each chord
- **Import from MIDI/MusicXML** - Load existing music files
- **Chord progression analysis** - Identify common progressions (I-V-vi-IV, etc.)
- **Automatic key detection** - Analyze chords and suggest the key
- **Chord voicing selection** - Choose inversions (root position, 1st inversion, etc.)

### Less Likely (Low Priority):
- **Dark mode** - UI theme (only if Tkinter supports it well)
- **Multiple tabs** - Work on multiple songs simultaneously
- **Multi-track support** - Separate tracks for melody, chords, bass
- **Cloud sync** - Save/load files from cloud storage
- **Mobile version** - Android/iOS version of the app
- **Syntax highlighting** - Different colors for chord lines vs lyric lines (already have chord/lyric line detection)

---

## Risk Mitigation

### Potential Issues & Solutions

1. **Audio Library Dependencies**
   - Risk: pygame requires SDL on Linux
   - Mitigation: PyInstaller bundles SDL; AppImage includes system libraries
   - Fallback: Use simpleaudio if pygame issues persist

2. **Chord Detection Accuracy**
   - Risk: False positives/negatives in regex
   - Mitigation: Comprehensive test suite; user feedback integration
   - Enhancement: Allow manual chord marking

3. **Cross-Platform Compatibility**
   - Risk: Different behavior on Windows/Linux
   - Mitigation: Test on both platforms regularly
   - Use platform-agnostic Python constructs

4. **Package Size**
   - Risk: Large executable size (100MB+)
   - Mitigation: Use UPX compression; exclude unnecessary modules
   - Alternative: Use Nuitka for smaller binaries

---

## Timeline Estimate

### Core MVP (Phases 1-6)
- **Phase 1 (Text Editor):** 2-3 days
- **Phase 2 (Chord Detection):** 2-3 days
- **Phase 3 (Audio Playback):** 3-4 days
- **Phase 4 (Interactive Features):** 2-3 days
- **Phase 5 (Auto-Play):** 2-3 days
- **Phase 6 (Packaging):** 2-3 days
- **Testing & Bug Fixes:** 3-4 days

**MVP Total:** 16-23 days (individual developer)

### Future Enhancements (Phases 7-14)
- **Phase 7 (Visual Feedback & Settings):** 2-3 days
- **Phase 8 (Instrument Selection):** 1-2 days
- **Phase 9 (Options Dialog):** 2-3 days
- **Phase 10 (Help/About):** 1 day
- **Phase 11 (Transpose):** 2-3 days
- **Phase 12 (Roman Numerals):** 3-4 days
- **Phase 13 (Advanced Timing & Loops):** 3-4 days
- **Phase 14 (Metronome & Capo):** 2-3 days
- **Additional Testing:** 2-3 days

**Enhancements Total:** 18-28 days

**Grand Total:** 34-51 days (all phases)

---

## Success Criteria

- [ ] Application runs on Windows and Linux as standalone executable
- [ ] Detects chords in both American and European notation
- [ ] Plays chords with acceptable audio quality
- [ ] UI is responsive (no freezing during playback)
- [ ] File operations work correctly (load/save)
- [ ] Auto-play feature works with adjustable delay
- [ ] Stop button immediately stops all audio
- [ ] Middle-click chord commenting works
- [ ] Executable size is reasonable (<100MB)
- [ ] Application starts in <3 seconds

---

## Appendix: Complete Dependency List

```toml
# Pipfile
[packages]
pychord = "~=0.6.0"
pyfluidsynth = "~=1.3.0"

[dev-packages]
pyinstaller = "~=6.0.0"
pytest = "~=7.4.0"
```

**System Dependencies (development):**
- FluidSynth library
  - Ubuntu/Debian: `libfluidsynth-dev`
  - Fedora: `fluidsynth-devel`
  - Windows: FluidSynth DLL

Total size estimate:
- pychord: <1MB
- FluidSynth library: ~2-3MB
- Soundfont (TimGM6mb): ~5.6MB
- Python runtime: ~30MB
- **Expected final .exe/.AppImage size:** 50-70MB (with UPX compression)

**Note:** Much smaller than original plan thanks to removing NumPy (~50MB savings)!

---

## References

- PyInstaller Documentation: https://pyinstaller.org/
- pygame Documentation: https://www.pygame.org/docs/
- PyChord Repository: https://github.com/yuma-m/pychord
- Tkinter Reference: https://docs.python.org/3/library/tkinter.html
- AppImage Builder: https://appimage-builder.readthedocs.io/
