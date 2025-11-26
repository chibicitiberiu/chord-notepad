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

**Additional Features (Phases 7-13) - COMPLETE:**
- ✅ Loop/repeat mode for playback
- ✅ Instrument/voicing selection (Piano, Guitar Standard, Drop D, DADGAD, etc.)
- ✅ Key signature selector in toolbar
- ✅ Time signature control (beats per measure and beat unit)
- ✅ Roman numeral chord notation support
- ✅ ChordPro directive support:
  - ✅ BPM changes (`{tempo: 120}`)
  - ✅ Time signature changes (`{time: 4/4}`)
  - ✅ Key changes (`{key: C}`)
  - ✅ Labels (`{label: intro}`)
  - ✅ Loops (`{loop: intro 3}`)
- ✅ Beat count annotations (e.g., `C*2` for 2 beats)
- ✅ About dialog

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

### Comment Syntax

**Tasks:**
1. Support `//` line comments
   - Lines starting with `//` are skipped during chord detection
   - Skipped during playback
   - Rendered in gray/italic in the editor
   - Example: `// Intro (skip for now)`

### NC (No Chord) Notation

**Tasks:**
1. Support NC for rests/pauses
   - `NC` treated as special chord symbol meaning silence/rest
   - Works with beat counts: `NC*2` = silence for 2 beats
   - Useful for breaks, intros, endings
   - Example: `C*4  G*4  NC*2  Am*4` (play C, G, silence, then Am)

### Preferences Dialog

**Tasks:**
1. Create preferences dialog window
   - Custom soundfont path selection (file picker)
   - MIDI velocity (volume) slider
   - Default chord duration preference
   - Auto-save preferences to JSON file

### Help & Documentation

**Tasks:**
1. Keyboard shortcuts reference dialog
   - Help → Keyboard Shortcuts (show reference dialog)
   - List all shortcuts in organized table
   - File operations, editing, playback, etc.
   - Copy reference to clipboard option

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
```

### Transpose Dialog

**Tasks:**
1. Create transpose dialog UI
   - Numeric spinner: -12 to +12 semitones
   - Preview button (show what chords will become)
   - Apply button (transpose all chords in document)
   - Tools → Transpose menu item

### Metronome & Capo Support

**Tasks:**
1. Metronome click track
   - Toggle button in toolbar
   - Play click sound on each beat during auto-play
   - Sync with BPM and time signature
   - Independent volume control
   - Auto count-in (1 bar) when metronome enabled

2. Capo support (global, affects playback only)
   - Toolbar spinner: "Capo: [-12 to +12]" (or -24 to +24)
   - Transposes playback pitch, NOT display
   - Text shows: C, Am, F, G (unchanged)
   - Positive values (like capo): Capo +2 plays D, Bm, G, A
   - Negative values (like downtuning): Capo -2 plays Bb, Gm, Eb, F
   - Use cases:
     - Match vocalist's range without rewriting chart
     - Play along with recording in different key
     - Simulate guitar downtuning
   - No `{capo:}` directive - global UI control only

3. Global tempo/speed percentage slider
   - Slider range: 50% to 150% (or 25% to 200%)
   - Default: 100%
   - Label: "Speed: 75%" or "Tempo Scale: 75%"
   - Multiplies ALL tempos proportionally:
     - Initial BPM slider value
     - All `{tempo: N}` directives in the song
   - Preserves tempo structure and changes
   - Perfect for practice: slow down entire song while keeping tempo variations
   - Optional keyboard shortcuts: `[` decrease 5%, `]` increase 5%

### Export to MIDI

**Tasks:**
1. Export song to MIDI file
   - File → Export to MIDI menu item
   - Convert detected chords to MIDI notes
   - Respect tempo, time signature, beat counts
   - Respect loops and labels
   - Use selected voicing/instrument

### Arpeggiation / Backing Track Generator

**Tasks:**
1. Add arpeggiation patterns for chords
   - Different arpeggio styles: up, down, up-down, pattern-based
   - Rhythm patterns: whole notes, quarter notes, eighth notes, etc.
   - Pattern selector in toolbar or preferences
   - Elevates from simple chord playback to full backing track

2. Strumming patterns (for guitar voicings)
   - Up/down strum patterns
   - Timing variations
   - Accent patterns

### Chord Diagrams

**Tasks:**
1. Display chord diagrams
   - Show guitar/piano fingering diagrams for detected chords
   - Popup on hover or click
   - Support for different voicings/positions
   - Visual representation of fretboard or keyboard

### Guitar Tab Generation

**Tasks:**
1. Generate guitar tablature from chord progression
   - Use existing guitar voicing data (fingering patterns already known)
   - Combine with timing information (beat counts, tempo)
   - Export to text-based tab format or ASCII art
   - Support for different tunings (standard, drop D, DADGAD, etc.)
   - File → Export to Tab menu item
   - Could also display tabs inline in the editor

### Export to Audio

**Tasks:**
1. Render backing track to audio file
   - File → Export to WAV/MP3 menu item
   - Use FluidSynth's audio rendering capability
   - Respect all playback settings (tempo, loops, patterns, etc.)
   - Progress bar during rendering
   - Audio format options: WAV (lossless), MP3 (compressed)

### Volume & Dynamics Control

**Tasks:**
1. Volume control via directives
   - `{v: 80}` or `{volume: 80}` directive (MIDI velocity 0-127)
   - Apply to subsequent chords until changed
   - Default velocity configurable in preferences
   - Useful for creating dynamic backing tracks

### Custom Rhythm Patterns

**Tasks:**
1. Per-section rhythm/arpeggio patterns
   - `{pattern: arpeggio-up}` - ascending arpeggio
   - `{pattern: arpeggio-down}` - descending arpeggio
   - `{pattern: strum-down}` - downstroke strum
   - `{pattern: strum-alternate}` - up-down strumming
   - `{pattern: whole}` - whole note (default)
   - Pattern library extensible
   - Different patterns for intro/verse/chorus

---

## Additional Future Ideas

Features that may be considered for future versions but are not currently planned:

### Deferred (Maybe Later):
- **Export to PDF/image** - Print/export chord sheets as PDF or image files
- **Dark mode** - UI theme
- **Multiple tabs** - Work on multiple songs simultaneously
- **Multi-track support** - Separate tracks for melody, chords, bass (complex, requires style programming)
- **Playback through MIDI device** - Send MIDI output to external devices instead of just FluidSynth

---

## Success Criteria

**Core Features:**
- [x] Application runs on Windows and Linux as standalone executable
- [x] Detects chords in American, European, and Roman numeral notation
- [x] Plays chords with acceptable audio quality
- [x] UI is responsive (no freezing during playback)
- [x] File operations work correctly (load/save)
- [x] Auto-play feature works with adjustable BPM
- [x] Stop button immediately stops all audio
- [x] Loop mode works
- [x] Instrument/voicing selection works
- [x] ChordPro directives work (tempo, time signature, key, labels, loops)
- [x] Beat count annotations work

**Remaining - Near Term:**
- [ ] Comment syntax (`//`)
- [ ] NC (No Chord) notation for rests
- [ ] Transpose dialog
- [ ] Keyboard shortcuts help
- [ ] Preferences dialog
- [ ] Metronome (with auto count-in)
- [ ] Capo support (playback pitch shift)
- [ ] Global tempo/speed percentage slider
- [ ] Executable tested on Windows and Linux
- [ ] Application starts in <3 seconds
- [x] Executable size is reasonable

**Remaining - Longer Term:**
- [ ] Export to MIDI
- [ ] Export to audio (WAV/MP3)
- [ ] Arpeggiation/backing track patterns
- [ ] Custom rhythm patterns per section
- [ ] Volume/dynamics control (`{v: 80}`)
- [ ] Chord diagrams
- [ ] Guitar tab generation

---

## References

- PyInstaller Documentation: https://pyinstaller.org/
- PyChord Repository: https://github.com/yuma-m/pychord
- Tkinter Reference: https://docs.python.org/3/library/tkinter.html
- FluidSynth Documentation: https://www.fluidsynth.org/
