# Chord Notepad

A text editor for chord notation. Write chord symbols above your lyrics and Chord Notepad detects them, highlights them and plays them back, voiced the way a real musician would on piano or guitar. The sound is real MIDI synthesis through FluidSynth.

**[Watch the demo](https://youtu.be/1Pf2bl4FVAc)** · **[Read how it was built](https://tibich.com/blog/chord-notepad-release/)**

<img width="1084" height="830" alt="image" src="https://github.com/user-attachments/assets/54ebad77-a203-4140-a018-d04476315819" />

## Notes:

- macOS version has had limited testing; feedback welcome.

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
- Choose the instrument: piano, or guitar in standard, Drop D, DADGAD, or Open G tuning, plus a ukulele preset (any custom fretted instrument or custom piano voicing too, built with the Tools → Settings voicing editor)
- Real MIDI synthesis through FluidSynth, with a soundfont bundled in
- A metronome you can switch on and off mid-playback
- A chord sheet strip (View → Chord Sheet) shows the song's voiced chords left to right as they'll actually play, follows along during playback, and switches between keyboard, staff, chord box, and tab views

**A small format for songs**
- Hold a chord longer with `C*2` (two beats), rest with `NC`, comment with `//`
- Inline directives drive the player: `{bpm: 120}`, `{bpm: +20}`, `{time: 3/4}`, `{key: G}`, `{label: verse}`, `{loop: verse 4}`
- Tempo and key can change partway through a song, and loops replay a labelled section

**Also**
- A reverse tool: click notes on a keyboard and it names the chord, inversions and slash spellings included
- File operations, recent files, adjustable font size
- Export the song as a standard MIDI file, for use in DAWs or notation software

## Documentation

**For users**, the [User Guide](https://github.com/chibicitiberiu/chord-notepad/releases/latest/download/ChordNotepad-UserGuide.pdf) covers everything: writing chords, directives, playback, instruments and ensembles, the chord sheet, transpose and capo, MIDI export, settings and shortcuts. The same guide is built into the app (**Help → User Guide**, or F1; on Android, **Help** in the menu). Its source is in [`help/`](help/). Good places to start:

- [Getting started](help/getting_started.rst)
- [Writing chords](help/writing_chords.rst) and [directives](help/directives.rst) (`{bpm}`, `{key}`, `{label}`, `{loop}` and the rest)
- [Keyboard shortcuts](help/shortcuts.rst)

**For developers:**

- [Architecture: the session layer](docs/architecture/session.md) both UIs sit on
- [Android port](docs/ANDROID.md): building, the Kotlin/Compose UI, the Python bridge
- [Writing the User Guide](docs/HELP_AUTHORING.md) (one source, desktop and Android editions)
- [Releasing](docs/RELEASE.md): CI, signing, the stores
- [Contributing](CONTRIBUTING.md), [Privacy](PRIVACY.md), [Changelog](CHANGELOG.md) ([older releases](CHANGELOG_HISTORY.md))

## Installation

### Pre-built downloads (recommended)

Download the latest release from the [Releases](https://github.com/chibicitiberiu/chord-notepad/releases/latest) page:
- **Linux**: `ChordNotepad-linux-x64.flatpak` (sandboxed; install with
  `flatpak install --user ChordNotepad-linux-x64.flatpak`, which also fetches
  the runtime from Flathub), or `ChordNotepad-linux-x64` (standalone
  executable; needs the FluidSynth library, see below)
- **Windows**: `ChordNotepad-windows-x64.exe` (FluidSynth is bundled)
- **macOS**: `ChordNotepad-macos-arm64` (needs FluidSynth from Homebrew:
  `brew install fluid-synth`)

Every release is built and tested by GitHub Actions, and comes with the full
source code and the source of the bundled libraries.

It is also available from app stores:
- **Linux**: [Snap Store](https://snapcraft.io/chord-notepad)
  (`sudo snap install chord-notepad`)
- **Windows**: [Microsoft Store](https://apps.microsoft.com/detail/9nb07qdfwjf4).
  This is a paid supporter edition: the same app as the free download, with
  automatic updates. Buying it is a way to support development.
- **Android**: Google Play (coming soon). Free, with every feature; an
  optional one-time purchase inside the app supports development. The
  Android APK on the GitHub releases page has no purchase and no Google
  libraries.

The standalone Linux executable needs FluidSynth installed:

```bash
sudo dnf install fluidsynth        # Fedora/RHEL
sudo apt install libfluidsynth3    # Ubuntu/Debian
sudo pacman -S fluidsynth          # Arch
```

### Run from source

You need Python 3.14 (the version in the [Pipfile](Pipfile)), Pipenv, and
FluidSynth as above.

```bash
git clone https://github.com/chibicitiberiu/chord-notepad.git
cd chord-notepad
pipenv install --dev
make run          # or: pipenv run python src/main.py
make test         # run the tests
make docs-check   # build both editions of the User Guide
```

### Build a standalone executable

```bash
make build        # Linux: dist/ChordNotepad
```

On Windows, run `pipenv run pyinstaller --clean chord-notepad.spec`
(output: `dist\ChordNotepad.exe`). PyInstaller only builds for the platform it
runs on. The Android app has its own build; see [docs/ANDROID.md](docs/ANDROID.md).

## Project structure

```
chord-notepad/
├── src/            # The app: Tk UI, view-models, services, audio, chord detection
│   └── session/    # AppSession, the shared layer the desktop and Android UIs sit on
├── android/        # Android app (Kotlin/Compose over the same Python core)
├── help/           # User Guide source (Sphinx, desktop and Android editions)
├── docs/           # Developer docs
├── tests/          # pytest suite
├── resources/      # Soundfont, icons, licence texts
└── packaging/      # Flatpak, snap, MSIX and store material
```

## License

Licensed under [GNU Affero General Public License v3.0](LICENSE), with additional
permissions for app stores and terms about the project's name and logos (see
[ADDITIONAL-TERMS.txt](ADDITIONAL-TERMS.txt)).

- The user guide (`help/`) and the developer docs (`docs/`) are under
  [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
- The logo and the store material are not free to reuse: forks need their own name and
  icon. See [ARTWORK-TERMS.txt](ARTWORK-TERMS.txt).

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for how to send one and the licence terms it comes under.

## Acknowledgments

- [FluidSynth](https://www.fluidsynth.org/) for MIDI synthesis
- [PyChord](https://github.com/yuma-m/pychord) and [music21](https://web.mit.edu/music21/) for chord parsing
- [GeneralUser GS](https://schristiancollins.com/generaluser.php) soundfont by S. Christian Collins

The full list of bundled components and their licences is in the app
(**Help → Open Source Licences**).
