# Changelog

<!--
This file holds release notes for the *next* full release.
Write entries here as you work. When a full release is published, the contents
of this file are used as the GitHub release description, then automatically
moved to CHANGELOG_HISTORY.md and this file is reset.
-->

### Added

- **Chord Notepad for Android.** It runs on Android phones and tablets
  (Android 7.0 or newer, 64-bit) and is the same app as on the desktop:
  chord detection with highlighting, playback with the same sound font,
  transpose, capo suggestions, the chord sheet (piano roll, staff, chord
  boxes and tab), custom voicings, the Chord Identifier, MIDI export and the
  built-in user guide. Songs are opened and saved through Android's file
  picker, and `.txt` files open from a file manager or another app with
  "Open with". It needs no permissions and works offline. The APK
  (`ChordNotepad-android.apk`) and its full source code are attached to this
  release; a Google Play version will follow. Both are free with every
  feature. The Play version asks for support once a day, starting a week
  after install, and offers an optional one-time supporter purchase that
  adds a badge in Settings; the GitHub version has a donation link in About
  instead. The two are signed differently, so one can't update the other.
- **Directives are checked as you type.** A directive that can't work is
  shown in red and skipped during playback: an out-of-range or badly
  formatted value, a missing parameter, an unknown key, or a loop placed
  above its label. While the cursor is in a directive, the status bar (on
  Android, a strip above the keyboard) shows its correct syntax; hover over
  a red one (on Android, long-press it) to see what's wrong. A `{capo}`,
  `{bpm}`, `{time}` or `{key}` that another of the same kind overrides
  before any chord plays is shown faded, with a "has no effect" hint.
- **Chord Identifier.** The keys a chord actually sounds light up in amber
  for a few seconds when you play it, and a note off either end of the piano
  is named beside it. A new **Play** button plays the selected keys as they
  are; long-press a chord or Play (on the desktop, Shift+click, or
  right-click Play) to hear the notes rolled, one at a time from the lowest.
  It also offers added-tone readings, trying each note as the root: E G# B C
  gives `Eaddb6` (E major with an added flat 6th) before `Caugmaj7/E`, and
  C E G F# gives `Cadd#11`.
- **More chords.** Sharp and flat added notes, written after `add`
  (`Eaddb6`, `Eaddb13`, `Cadd#11`, `Cmaddb9`, or in brackets like
  `E(addb6)`), in American and European notation and with roman numerals.
  Also `C6/9` (and with a bass, `C6/9/E`), `Cmmaj9`, `Cdim(maj7)` and
  `Csus2sus4` (or `Csus24`). Roman numerals accept `iim7` and Berklee-style
  `IIm7` as minor chords.
- **Open-source licences and source code.** On the desktop,
  **Help → Open Source Licences** (also a button in About) lists every
  component the app is built from, with its version, licence and full
  licence text, including the additional terms of Chord Notepad's own
  licence, the logo's terms, the user guide's CC BY-SA 4.0 licence and the
  guide's fonts and scripts. Each release now also carries the source code
  of Chord Notepad (`ChordNotepad-<version>-source.tar.gz`) and of the
  bundled LGPL, GPL and MPL libraries
  (`ChordNotepad-<version>-third-party-sources.tar`); for the Linux binary
  and the snap, whose libraries come from Ubuntu, that's the Ubuntu source
  packages of the GPL and LGPL ones, and a list of the others. To use your
  own FluidSynth build, set `CHORD_NOTEPAD_LIBFLUIDSYNTH` to its path (not
  in the snap).
- A line that starts with `.` is always plain text, for lyric lines such as
  "la la la" that would otherwise be read as chords.
- Desktop: **Tools → Insert → Capo**.
- An empty song shows "Type or paste a song here" in grey until you type or
  paste; it isn't part of the text.

### Changed

- **Transpose spells chords for the key they land in.** A song moved into B
  now gets `F#`, `C#` and `G#m` instead of `Gb`, `Db` and `Abm`, and one
  moved into Db gets `Gb` and `Ab7`. The key comes from the song's `{key}`,
  or from its chords when there is none. A diminished chord leading up a
  semitone gets a sharp (`D#dim7 Em7`). Transposed keys take the spelling
  with fewer sharps or flats, so C up a semitone is `Db` and Am down one is
  `G#m`, in the `{key}` and the toolbar key alike.
- **Notation is per song.** The AB / Do toggle switches only the song you
  have open; it no longer changes your default. A new song starts in the
  notation set in Settings. Opening a song, or pasting one into an empty
  document, picks the notation its chords are written in, so a song in
  `Sol Re Mim Do` opens in European even when American is the default (on
  Android, also a song restored after the system closed the app in the
  background). Changing the default in Settings also switches a song you
  haven't switched by hand and whose chords didn't decide it.
- **Songs no longer change your defaults.** Opening a song leaves your
  Settings alone. Values the song sets itself are shown as set by the song;
  a change you make that the song doesn't set lasts until you close the
  song. Only Settings changes the defaults.
- The Chord Identifier names chords and notes in the notation of the song
  you have open: in a European song the keys, the notes and the results
  read `Do Mi Sol`, `Lam7`, `Domaj7/Mi`, and an inserted chord goes in that
  way. Typed notes can be in either notation (`Do Mi Sol` or `C E G`).
- Settings shows the Default key list and the voicing editor's note names
  (strings, voice ranges, hand ranges) in the notation chosen in Settings,
  so `Mi2 La2 Re3` with European, switching as soon as you change it, and
  accepts either spelling when you type a note.
- A lowercase root is always minor: `cmaj7`, `cM7` and `cΔ` are now C
  minor-major 7 (they played C major 7), as `c7` is `Cm7`. Roman numerals
  follow the same rule: `iimaj7` in C is D F A C#.
- Converting between American and European notation keeps the song as you
  wrote it: lowercase minors stay lowercase and minor (`c c# f#` becomes
  `do do# fa#` and back), `DoM7` becomes `CM7` and `♯` stays `♯`, so
  converting there and back gives the same text. `{key}` directives are
  converted too (`{key: G}` becomes `{key: Sol}`), and a lyric line that
  would read as chords in the other notation gets a `.` in front, so
  `la la la` stays a lyric.
- Tempo can be 20 to 400 BPM everywhere, including a typed `{bpm}`. A
  relative change such as `{bpm: +50}` that would leave that range is
  clamped, with a warning in the status bar.
- Suggest Capo replaces a `{capo}` that comes before the first chord instead
  of adding a second one, and on a selection it changes only that part.
- The Windows, macOS and Linux downloads are smaller: they no longer bundle
  numpy, matplotlib, chardet and other packages the app never used, and on
  Windows two unused FluidSynth libraries (libinstpatch and libgobject). The
  Flatpak and snap no longer include chardet either.
- The help and README say where to get Chord Notepad: the GitHub releases,
  the Snap Store, and the Microsoft Store (a paid supporter edition of the
  same app). The help's "Limitations" section no longer claims there is no
  staff or tab view.
- The About dialog and the Windows executable's file properties now state
  the correct licence (GNU AGPL-3.0) and copyright holder. They wrongly said
  MIT.
- Dropped "ChordPro" from the Linux desktop entry and AppStream search
  keywords.

### Fixed

- **Chords play the right notes.** Every chord quality is now tested
  against music theory in every key. Fixed along the way:
  - `C13b9`, `C13#9` and `C13b5` played the natural 11th, which clashes with
    the 3rd (a 13th chord leaves it out, as `C13` always did);
  - `C11b9` played a natural 9th instead of its flat 9th;
  - piano playback dropped a chord's root over a slash bass that isn't the
    root, so `Ab5/C` could come out as just C and Eb;
  - ensembles left out the root when a chord had more notes than voices, so
    a 3-voice G7 was rootless;
  - `bVI` in C played G# major instead of Ab, and roman numerals with `ø`
    (`viiø`, `iiø7`) didn't play;
  - the staff wrote some notes with the wrong letter: the flat 9th of
    `C7b9b13` is D♭, not C♯, and the third of `C#13` is E♯, not F.
- **Chords that weren't read.** Lowercase minors with a flat root (`bb`,
  `eb`, `ab`, and `sib`, `mib` in European) weren't chords, so transposing
  `A b c` down a tone gave an unusable `G a bb`. Chords with `♯` or `♭`
  after a lowercase root or in a slash bass (`c♯`, `C/G♭`) didn't play or
  transpose right. European notation now also takes `-` for minor, so
  converting `C-` no longer gives an unread `Do-`. Symbols such as `C77`,
  `C79` and `Cadd4` are no longer accepted as chords.
- **Playback.**
  - It keeps time more accurately: notes, the metronome and speed changes
    stay on the beat even while Chord Notepad is busy (for example redrawing
    the chord sheet), and long songs no longer slowly fall behind.
  - Opening another song or starting a new one while a song plays or is
    paused now stops it. Before, Play went on with the old song and lit up
    its chords in the new text.
  - Pressing Pause right after Play, while the song is still being prepared,
    now pauses it. Before, the song started playing anyway while the Play
    button showed it as paused.
  - Clicking a chord to hear it while the song is playing no longer
    interferes with playback, and clicked chords keep their smooth voice
    leading from one click to the next.
  - The **Audio driver** setting is now used: Chord Notepad tries that driver
    first. If it can't start, the next one is tried, and you're told when
    there's no working audio output at all, instead of silence.
- **Song text.**
  - Unusual text can no longer freeze Chord Notepad. A chord with a long run
    of digits, many unclosed `{`, or a very large file with many directives
    and comments used to take seconds to minutes to read; it's now instant.
    A directive has to fit on one line.
  - `{bpm: 0}`, a negative tempo or `{time: 0/4}` no longer crash or hang
    playback, and two loops that point at each other no longer render
    forever.
  - `{bpm: reset}` returns to the song's first tempo in a typed song too,
    not only in one opened from a file.
  - `{loop: my verse 2}` finds `{label: my verse}`: labels can contain
    spaces.
  - MIDI export includes songs written with European keys (Do, Lam).
- The Chord Identifier names chords with flats correctly ("Bb D F" is Bb,
  not D) and no longer offers a name that means other notes: E Ab B C was
  `Abaugmaj7` (now `Caugmaj7`), D F# A C E G# was `D13` (now `D9#11`).
- Custom voicings:
  - a mistyped string in a tuning (for example `E2 A2 X9 G3`) reports the
    actual bad note (`X9`) instead of a confusing message about the letter
    `E` or "20 strings";
  - if the selected custom voicing can no longer be built (for example after
    editing settings.json by hand), Chord Notepad starts with piano voicing
    instead of failing to start;
  - the help texts of some voicing fields now match what the voicing engine
    does.
- The speed control shows the speed the song actually plays at after
  snapping (112.5%, not the 110% you dragged to).
- The Insert Capo dialog no longer claims a capo never changes the sound:
  with a fretted voicing it does.
- Desktop on Linux: the Edit menu shows the Redo shortcut that actually
  works (Ctrl+Shift+Z).
