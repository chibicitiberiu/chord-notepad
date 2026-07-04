# Chord Notepad

A text editor for songwriters. Write chord symbols above your lyrics, the way you'd jot a song on the back of an envelope, and Chord Notepad detects them, highlights them, and plays them back, voiced the way a real musician would on piano or guitar. The sound is real MIDI synthesis through FluidSynth.

<img width="1084" height="830" alt="image" src="https://github.com/user-attachments/assets/54ebad77-a203-4140-a018-d04476315819" />

## Features

**Writing chords**
- Highlights chord symbols as you type, and tells chord lines apart from lyric lines on its own
- Three notations you can switch between: American (`C`, `Am`, `Bb7`), European solfège (`Do`, `Re`, `Mi`), and roman numerals (`I`, `V`, `vi`)
- Roman numerals follow the key: write `I V vi IV`, set `{key: D}`, and hear it in D; change the key and the same lines play anywhere
- Understands the full range, from plain triads to slash chords and altered jazz voicings (`C/E`, `C7b9`, `Cmaj7#5(9)`, `Cm7b5`)

**Playing them back**
- Click any chord to hear it, or press play to run the whole song with each chord lighting up as it sounds
- Chords are voiced like a player, not stacked mechanically: the piano voicing moves smoothly from one chord to the next (voice leading), and the guitar voicing finds real, playable fingerings on the fretboard
- Or voice for an ensemble instead of one instrument: Choir (SATB), Male Choir (TTBB), Treble Choir (SSA), and String Quartet presets voice each chord as independent parts with real voice leading (custom ensembles too), and MIDI export writes them out one track per voice
- Choose the instrument: piano, or guitar in standard, Drop D, DADGAD, or Open G tuning, plus a ukulele preset (any custom fretted instrument too, built with the Options → Settings voicing editor)
- Real MIDI synthesis through FluidSynth, with a soundfont bundled in
- A metronome you can switch on and off mid-playback

**A small format for songs**
- Hold a chord longer with `C*2` (two beats), rest with `NC`, comment with `//`
- Inline directives drive the player: `{bpm: 120}`, `{bpm: +20}`, `{time: 3/4}`, `{key: G}`, `{label: verse}`, `{loop: verse 4}`
- Tempo and key can change partway through a song, and loops replay a labelled section

**Also**
- A reverse tool: click notes on a keyboard and it names the chord, inversions and slash spellings included
- File operations, recent files, adjustable font size
- Export the song as a standard MIDI file, for use in DAWs or notation software

## Requirements

### Runtime Requirements
- **Linux**: FluidSynth library (`libfluidsynth` package)
  ```bash
  # Fedora/RHEL
  sudo dnf install fluidsynth

  # Ubuntu/Debian
  sudo apt install libfluidsynth3

  # Arch
  sudo pacman -S fluidsynth
  ```

- **Windows**: No additional dependencies needed (FluidSynth DLL will be bundled with the executable)

### Development Requirements
- Python 3.10+
- Pipenv for dependency management

## Installation

### Option 1: Use Pre-built Executables (Recommended)

Download the latest release from the [Releases](../../releases) page:
- **Linux**: `ChordNotepad-linux-x64` (standalone executable)
- **Windows**: `ChordNotepad-windows-x64.exe`
- **macOS**: `ChordNotepad-macos-x64`

All releases are automatically built and tested using GitHub Actions.

### Option 2: Run from Source

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/chord-notepad.git
   cd chord-notepad
   ```

2. Install dependencies:
   ```bash
   pipenv install
   ```

3. Run the application:
   ```bash
   make run
   # or
   pipenv run python src/main.py
   ```

## Building from Source

### Prerequisites
Install development dependencies:
```bash
pipenv install --dev
```

### Build for Your Platform

Build a standalone executable for your current platform:
```bash
make build
```

The executable will be created in the `dist/` directory:
- **Linux**: `dist/ChordNotepad`
- **Windows**: `dist/ChordNotepad.exe`

### Cross-Platform Build Notes

**Building on Linux for Linux:**
```bash
make build
# Output: dist/ChordNotepad
```

**Building on Windows for Windows:**
```cmd
pipenv install --dev
pipenv run pyinstaller --clean chord-notepad.spec
REM Output: dist\ChordNotepad.exe
```

Note: PyInstaller creates platform-specific executables. To build for Windows, you must run the build on a Windows machine. To build for Linux, run on a Linux machine.

## Usage

### Basic Workflow

1. **Create or Open a File**: Use File > New or File > Open
2. **Write Lyrics with Chords**: Type chord symbols above lyrics
   ```
   C       Am      F       G
   This is a simple song

   Dm7     G7      Cmaj7
   With jazz chords too
   ```

3. **Click Chords**: Click any highlighted chord to hear it
4. **Auto-Play**: Click the Play button to auto-play all chords sequentially
5. **Configure Settings**:
   - Settings > BPM: Adjust playback speed (default: 120)
   - Settings > Font Size: Adjust editor font size

### Supported Chord Types

- **Major**: C, D, E, F, G, A, B
- **Minor**: Cm, Dm, Em, Am
- **Seventh**: C7, Dm7, Gmaj7, Am7
- **Diminished**: C°, Ddim, Cdim7
- **Augmented**: C+, Daug
- **Suspended**: Csus2, Csus4, Dsus
- **Extended**: C9, D11, E13
- **Alterations**: C7b5, D7#9, Em7b5
- **Half-diminished**: Cø7, Dm7b5
- **Add chords**: Cadd9, Dadd11
- **Slash chords / inversions**: C/E, Am/G, G/B

### Keyboard Shortcuts

- `Ctrl+N`: New file
- `Ctrl+O`: Open file
- `Ctrl+S`: Save file
- `Ctrl+Shift+S`: Save As
- `Ctrl+Q`: Quit
- `Ctrl+MouseWheel`: Zoom in/out

## Project Structure

```
chord-notepad/
├── src/
│   ├── main.py                 # Application entry point
│   ├── ui/
│   │   ├── main_window.py      # Main window with menu and toolbar
│   │   └── text_editor.py      # Custom text editor widget
│   ├── audio/
│   │   ├── player.py               # FluidSynth playback engine
│   │   ├── chord_picker.py         # Piano voice-leading picker
│   │   └── guitar_chord_picker.py  # Guitar fingering search
│   ├── services/                   # Song parsing, playback, event production
│   ├── viewmodels/                 # MVVM view-models
│   └── chord/
│       ├── helper.py               # Symbol -> notes, notes -> chord name
│       └── detector.py             # Line classification and detection
├── resources/
│   └── soundfont/
│       └── GeneralUser-GS.sf2  # Bundled soundfont
├── chord-notepad.spec          # PyInstaller spec file
├── Pipfile                     # Python dependencies
├── Makefile                    # Build commands
└── README.md
```

## Development

### Running Tests
```bash
make test
```

### Clean Build Artifacts
```bash
make clean
```

### Code Style
The project uses standard Python conventions with:
- 4-space indentation
- Clear, descriptive variable names
- Docstrings for all public methods

## Architecture

### Threading Model
- **Main thread**: Tkinter GUI event loop
- **Producer thread**: walks the song ahead of time and pushes a single merged, timestamped stream of events (chord notes plus metronome ticks) into a bounded buffer
- **Player thread**: pops events, waits for each one's moment, and fires FluidSynth; the GUI stays out of the timing loop and is signalled through a queue

### Audio Playback
- FluidSynth MIDI synthesis, both for click-to-play and full-song playback
- Every event is anchored to an absolute time, so tempo and key can change mid-song without drift
- Chord durations are set per chord in the text (a bare chord is one beat, `C*2` is two)

## Dependencies

### Runtime
- `pyfluidsynth`: Python bindings for FluidSynth
- `pychord`: fast chord parsing (the first-pass parser)
- `music21`: fallback parser for more exotic chord spellings
- `pillow`: image handling
- `tkinter`: GUI framework (included with Python)

### Development
- `pyinstaller`: creates standalone executables
- `pytest`: test runner
- `hypothesis`: property-based tests (fuzzes the voicing, asserting it never plays a note outside the chord)
- `sphinx` / `rinohtype`: build the user guide

## License

Licensed under [GNU Affero General Public License v3.0](LICENSE).

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Acknowledgments

- FluidSynth for MIDI synthesis
- PyChord for chord parsing
- GeneralUser GS soundfont by S. Christian Collins
