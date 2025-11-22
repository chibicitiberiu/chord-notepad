# Chord-Playing Notepad Application - Remaining Implementation

## What's Already Implemented

**Core MVP (Phases 1-5) - COMPLETE:**
- ✅ Full text editor with file operations, undo/redo, recent files
- ✅ Font selection and size adjustment (Ctrl+Wheel, Ctrl+Plus/Minus/0)
- ✅ Line-based chord detection with PyChord validation
- ✅ American and European notation support with conversion
- ✅ FluidSynth audio playback with GeneralUser-GS soundfont
- ✅ Clickable chords (left-click to play)
- ✅ Auto-play with BPM control (60-240 BPM)
- ✅ Play/Pause/Stop controls with threading
- ✅ Current chord highlighting during playback
- ✅ Settings persistence (font, BPM, notation, window geometry, recent files)
- ✅ Makefile and PyInstaller spec for packaging

**Partially Implemented:**
- ⚠️ Middle-click to comment chords (NOT implemented)

## Remaining Work

### Phase 6: Packaging & Distribution (Partially Complete)

**Remaining Tasks:**
1. Test on target platforms
   - Windows 10/11 testing
   - Ubuntu 22.04/Fedora 39 testing
   - Verify audio playback works
   - Check file operations

---

## Future Enhancements (Post-MVP)

### Phase 7: Visual Feedback & Playback Enhancements

**Tasks:**
1. Loop/repeat mode
   - **Toggle button**: Loop entire song
   - When enabled, restart from beginning after last chord
   - Works with play/pause/stop controls

2. Commented chords feature (from Phase 4)
   - **Middle click on chord**: mark as "commented" (red color with overstrike)
   - **Middle click again**: remove comment
   - Track commented chords state
   - Skip commented chords during auto-play

**UI Components:**
```python
# Loop mode toggle in toolbar
self.loop_var = tk.BooleanVar(value=False)
loop_check = ttk.Checkbutton(
    toolbar,
    text="Loop",
    variable=self.loop_var
)

# Middle-click chord binding
self.text_editor.tag_bind('chord', '<Button-2>', self.on_chord_middle_click)

def on_chord_middle_click(self, event):
    """Toggle chord comment state"""
    # Get chord at position
    # Toggle in commented_chords set
    # Update tag (chord_comment has red color and overstrike)
```

### Phase 8: Instrument Selection

**Tasks:**
1. Enumerate available instruments from soundfont
   - Read GM (General MIDI) program numbers from soundfont
   - Standard instruments: Piano (0), Guitar (24-31), Bass (32-39), Strings (40-55), etc.
   - Create instrument picker in toolbar

2. Implement instrument switching
   - Use FluidSynth `program_select()` to change instrument
   - Save instrument preference in settings

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
   - Playback duration for chords (default 1 bar)
   - MIDI velocity (volume) slider
   - Auto-save preferences to JSON file

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
    ttk.Label(pref_window, text="Chord Duration (beats):").grid(row=2, column=0)
    duration_spinbox = ttk.Spinbox(pref_window, from_=1, to=16, increment=1)
    duration_spinbox.grid(row=2, column=1)
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

View:
  Ctrl+Plus       Increase Font Size
  Ctrl+Minus      Decrease Font Size
  Ctrl+0          Reset Font Size
  Ctrl+Wheel      Zoom In/Out

Playback:
  Click Chord     Play Single Chord
  Middle-Click    Comment/Uncomment Chord (when implemented)
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
- **Dark mode** - UI theme
- **Multiple tabs** - Work on multiple songs simultaneously
- **Multi-track support** - Separate tracks for melody, chords, bass
- **Cloud sync** - Save/load files from cloud storage
- **Mobile version** - Android/iOS version of the app

---

## Success Criteria

- [x] Application runs on Windows and Linux as standalone executable
- [x] Detects chords in both American and European notation
- [x] Plays chords with acceptable audio quality
- [x] UI is responsive (no freezing during playback)
- [x] File operations work correctly (load/save)
- [x] Auto-play feature works with adjustable BPM
- [x] Stop button immediately stops all audio
- [ ] Middle-click chord commenting works
- [ ] Executable tested on Windows and Linux
- [ ] Application starts in <3 seconds
- [x] Executable size is reasonable (estimated 50-70MB with soundfont)

---

## References

- PyInstaller Documentation: https://pyinstaller.org/
- PyChord Repository: https://github.com/yuma-m/pychord
- Tkinter Reference: https://docs.python.org/3/library/tkinter.html
- FluidSynth Documentation: https://www.fluidsynth.org/
