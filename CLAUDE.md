# Chord Notepad

A text editor for musicians that detects and plays guitar/piano chords using FluidSynth synthesis.

## Quick Reference

```bash
# Run application
make run

# Run tests
make test

# Build executable
make build

# Install dependencies
make install
```

## Tech Stack

- **Language:** Python 3.10+
- **GUI:** Tkinter
- **Audio:** FluidSynth (pyfluidsynth)
- **Music theory:** pychord, mingus, music21
- **Testing:** pytest, hypothesis
- **Packaging:** PyInstaller, Pipenv

## Architecture

MVVM pattern with dependency injection:

```
src/
├── main.py              # Entry point
├── application.py       # DI container, lifecycle management
├── constants.py         # Global constants, colors, tags
├── exceptions.py        # Custom exception hierarchy
├── models/              # Dataclasses (Song, Line, ChordInfo, Directive, Config)
├── views → ui/          # Tkinter widgets (MainWindow, ChordTextEditor)
├── viewmodels/          # Business logic (MainWindowViewModel, TextEditorViewModel)
├── services/            # Cross-cutting concerns
│   ├── playback_service.py    # Audio orchestration
│   ├── song_parser_service.py # Parse songs, detect chords
│   ├── config_service.py      # Settings persistence
│   └── file_service.py        # File I/O
├── audio/               # FluidSynth wrapper, voice leading
│   ├── player.py              # NotePlayer (FluidSynth wrapper)
│   ├── chord_picker.py        # Piano voicing
│   ├── guitar_chord_picker.py # Guitar voicing
│   └── event_buffer.py        # Producer-consumer queue
├── chord/               # Chord detection
│   ├── detector.py            # Regex-based detection
│   ├── helper.py              # pychord/music21 validation
│   └── converter.py           # Notation conversion
└── utils/               # Observable pattern, helpers
```

## Key Patterns

### Dependency Injection
Services created in `Application.on_initialize_services()` in dependency order. Access via properties.

### Observable (Pub-Sub)
ViewModels inherit from `Observable`. Views subscribe: `viewmodel.observe('property', callback)`.

### Threading
- Main thread: Tkinter GUI
- Playback thread: FluidSynth with precise timing
- Cross-thread: Queue-based via `Application._event_queue`

### Producer-Consumer (Audio)
`EventProducer` → `EventBuffer` → `NotePlayer` (FluidSynth)

## Code Conventions

- **Classes:** PascalCase
- **Functions:** snake_case
- **Constants:** UPPER_SNAKE_CASE
- **Private:** Leading underscore (`_config`)
- **Type hints:** Required on all public functions
- **Docstrings:** Required on all public methods
- **Logging:** `logger = logging.getLogger(__name__)` per module

## Testing

```bash
pytest tests/ -v                           # All tests
pytest tests/test_chord_detector.py -v     # Specific file
pytest tests/ --cov=src                    # With coverage
```

Key fixtures in `tests/conftest.py`:
- `american_detector`, `european_detector` - ChordDetector instances
- `song_parser` - SongParserService instance

## Important Constants

From `src/constants.py`:
- `MIN_BPM=60`, `MAX_BPM=240`, `DEFAULT_BPM=120`
- `MIN_FONT_SIZE=6`, `MAX_FONT_SIZE=72`
- `CHORD_DETECTION_DEBOUNCE_MS=500`
- Tag names: `TAG_CHORD_VALID`, `TAG_CHORD_INVALID`, `TAG_CHORD_PLAYING`, `TAG_DIRECTIVE_VALID`

## Chord Detection

Supports:
- **American:** C, Am, C7, Cmaj7, C/G, Csus4, C#, Db
- **European:** Do, rem, Fa#, Sol (with accents)
- **Roman numerals:** I, ii, V7, vi/I, ♭III
- **Duration:** C*2 (2 beats), Am*4.5
- **ChordPro directives:** `{bpm: 120}`, `{time: 4/4}`, `{key: C}`, `{label: chorus}`, `{loop: chorus 2}`

## Adding Features

1. **Models:** Dataclasses in `src/models/`
2. **Services:** Business logic in `src/services/`
3. **ViewModels:** UI logic in `src/viewmodels/`
4. **Views:** Tkinter widgets in `src/ui/`
5. **Config:** Add to `src/models/config.py`, load/save via `ConfigService`
6. **Tests:** Create in `tests/`, use conftest fixtures

## Exception Handling

Use custom exceptions from `src/exceptions.py`:
- `ChordNotepadError` (base)
- `ConfigurationError`
- `AudioInitializationError`
- `FileOperationError`
- `ChordDetectionError`
- `ServiceNotInitializedError`

## Platform Notes

FluidSynth library required:
- **Linux:** `libfluidsynth` (Fedora) / `libfluidsynth3` (Ubuntu)
- **Windows:** DLL bundled with executable
- **macOS:** Via Homebrew

PyInstaller builds are platform-specific. Build on target platform.
