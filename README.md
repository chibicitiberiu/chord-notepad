# Chord Notepad

A simple text editor for musicians that automatically detects and plays guitar/piano chords using FluidSynth synthesis.

## Features

- Text editor with syntax highlighting for chord symbols
- Real-time chord detection (supports major, minor, 7th, dim, aug, sus, and complex jazz chords)
- Interactive chord playback (click any chord to hear it)
- Auto-play mode with configurable BPM and time signature
- Visual chord highlighting during playback
- File operations (New, Open, Save, Save As)
- Recent files menu
- Configurable font size and BPM settings

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
│   │   ├── player.py           # FluidSynth audio player
│   │   └── chord_picker.py     # Chord-to-MIDI converter
│   └── chord/
│       └── converter.py        # Chord notation parser
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
- **Main Thread**: Tkinter GUI event loop
- **Player Thread**: FluidSynth playback with precise timing
- **Cross-thread Communication**: Queue-based invoke system for thread-safe GUI updates

### Audio Playback
- Uses FluidSynth for high-quality MIDI synthesis
- Supports real-time note triggering (click-to-play)
- Scheduled playback with configurable BPM and time signatures
- Each chord plays for 1 bar (4 beats in 4/4 time)

## Dependencies

### Runtime
- `pyfluidsynth`: Python bindings for FluidSynth
- `pychord`: Chord parsing and music theory
- `tkinter`: GUI framework (included with Python)

### Development
- `pyinstaller`: Creates standalone executables
- `pytest`: Testing framework

## License

MIT License - feel free to use and modify for your own projects.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Acknowledgments

- FluidSynth for MIDI synthesis
- PyChord for chord parsing
- GeneralUser GS soundfont by S. Christian Collins
