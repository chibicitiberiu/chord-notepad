# Changelog

<!--
This file holds release notes for the *next* full release.
Write entries here as you work. When a full release is published, the contents
of this file are used as the GitHub release description, then automatically
moved to CHANGELOG_HISTORY.md and this file is reset.
-->

### Added

- Android: Chord Notepad now runs on Android phones and tablets (Android 7.0
  or newer, 64-bit). It's the same app as on the desktop: chord detection
  with highlighting, playback with the same sound font, transpose, capo
  suggestions, the chord sheet (piano roll, staff, chord boxes and tab),
  custom voicings, MIDI export and the built-in user guide. Songs are opened
  and saved through Android's file picker. It needs no permissions and works
  offline. The APK (`ChordNotepad-android.apk`) and the full source code
  are attached to this release; a Google Play version will follow. Both are
  free with every feature. The Play version asks for support once a day,
  starting a week after install, and offers an optional one-time supporter
  purchase that adds a badge in Settings; the GitHub version has a
  donation link in About instead. The two are signed differently, so one
  can't update the other.
- Android: open `.txt` files from a file manager or another app with
  "Open with" Chord Notepad.
- Desktop: **Help → Open Source Licences** (also a button in About) lists
  every component the app is built from, with its version, licence and full
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

- Directives that can't work are now shown in red and skipped during
  playback: an out-of-range or badly formatted value, a missing parameter,
  an unknown key, or a loop placed above its label. While the cursor is in a
  directive, the status bar (on Android, a strip above the keyboard) shows
  its correct syntax; hover over a red one (on Android, long-press it) to see
  what's wrong.
- A `{capo}`, `{bpm}`, `{time}` or `{key}` that another of the same kind
  overrides before any chord plays is shown faded, with a "has no effect"
  hint.
- A line that starts with `.` is always plain text, for lyric lines such as
  "la la la" that would otherwise be read as chords.
- Roman numerals accept `iim7` and Berklee-style `IIm7` as minor chords.
- Desktop: **Tools → Insert → Capo**.
- The Chord Identifier also offers added-tone readings, trying each note as
  the root: E G# B C gives `Eaddb6` (E major with an added flat 6th) before
  `Caugmaj7/E`, C E G F# gives `Cadd#11`, and C E G A gives `C6` as well as
  `Am7/C`. Songs can now use sharp and flat added notes too, written after
  `add` (`Eaddb6`, `Eaddb13`, `Cadd#11`, `Cmaddb9`, or in brackets like
  `E(addb6)`), in American and European notation and with roman numerals.
- Desktop: in the Chord Identifier, the keys a chord actually sounds light
  up in amber for a few seconds when you click it, and a note off either end
  of the piano is named beside it. A new **Play** button plays the selected
  keys as they are. Shift+click a chord, or Shift+click or right-click Play,
  to hear the notes rolled, one at a time from the lowest.
- More chord spellings: `C6/9` (also with a bass, `C6/9/E`), `Cmmaj9`,
  `Cdim(maj7)` and `Csus2sus4` (or `Csus24`).

### Fixed

- `C13b9`, `C13#9` and `C13b5` no longer play the natural 11th, which
  clashed with the 3rd (a 13th chord leaves it out, as `C13` always did),
  and `C11b9` plays its flat 9th; it played a natural 9th instead.
- The staff writes the notes of 11th, 13th and some altered chords with
  the right letters: the flat 9th of `C7b9b13` is D♭, not C♯, and the
  third of `C#13` is E♯, not F.
- Converting `C-` (minor written with a dash) to European gave `Do-`, which
  wasn't read as a chord. European notation now takes `-` for minor too.
- Converting from European to American keeps the song as you wrote it:
  lowercase minors stay lowercase (`do7` becomes `c7`, not `Cm7`), `DoM7`
  becomes `CM7` and `♯` stays `♯`, so converting there and back gives the
  same text.
- Convert puts a `.` in front of a lyric line that would read as chords in
  the other notation, so `la la la` stays a lyric in a European song and
  isn't turned into `a a a` when you convert back.

- Settings: the Default key list now follows the chord notation (Do, Re,
  Mi... when European is picked, switching as soon as you change it) instead
  of always showing American names. The key is saved the same way in either
  notation, so it stays right when you switch notation later.
- Converting to European notation kept lowercase minor chords minor only in
  name: `c c# f#` became `Do Do# Fa#`, which are major. They now become
  `do do# fa#` and convert back to `Cm C#m F#m`.
- Pressing Pause right after Play, while the song is still being prepared,
  now pauses it. Before, the song started playing anyway while the Play
  button showed it as paused.
- Lowercase minor chords with a flat root (`bb`, `eb`, `ab`, and `sib`,
  `mib` in European) are now chords. Before, they weren't highlighted or
  played, and transposing `A b c` down a tone gave `G a bb`, which didn't
  work. Chords written with `♯` or `♭` after a lowercase root or in a slash
  bass (`c♯`, `C/G♭`) also play and transpose correctly now.
- Converting between American and European notation also converts `{key}`
  directives: `{key: G}` becomes `{key: Sol}`.
- Opening another song or starting a new one while a song plays or is
  paused now stops it. Before, Play went on with the old song and lit up
  its chords in the new text.
- A mistyped string in a custom voicing's tuning (for example `E2 A2 X9 G3`)
  now reports the actual bad note (`X9`) instead of a confusing message about
  the letter `E` or "20 strings".
- If the selected custom voicing can no longer be built (for example after
  editing settings.json by hand), Chord Notepad starts with piano voicing
  instead of failing to start.
- Playback keeps time more accurately. Notes, the metronome and speed changes
  stay on the beat even while Chord Notepad is busy with something else (for
  example redrawing the chord sheet), and long songs no longer slowly fall
  behind.
- The **Audio driver** setting is now used: Chord Notepad tries that driver
  first. Before, it was saved but ignored.
- If an audio driver can't start, Chord Notepad now tries the next one, and
  tells you when there's no working audio output at all. Before, a failed
  driver could leave playback silently doing nothing.
- Piano playback no longer drops a chord's root over a slash bass that isn't
  the root. A power chord with another bass note, such as `Ab5/C`, could come
  out as just C and Eb. The root is now left out only when the bass already
  plays it.

- The Chord Identifier names chords with flats correctly: "Bb D F" is Bb,
  not D. It no longer offers a name that means other notes: E Ab B C was
  `Abaugmaj7` (now `Caugmaj7`), D F# A C E G# was `D13` (now `D9#11`).
- `{bpm: 0}`, a negative tempo or `{time: 0/4}` no longer crash or hang
  playback, and two loops that point at each other no longer render
  forever.
- Roman numerals with `ø` (`viiø`, `iiø7`) play, and `bVI` in C plays Ab
  major, not G#. Symbols such as `C77`, `C79` and `Cadd4` are no longer
  accepted as chords.
- `{bpm: reset}` returns to the song's first tempo in a typed song too, not
  only in one opened from a file.
- `{loop: my verse 2}` finds `{label: my verse}`: labels can contain spaces.
- MIDI export includes songs written with European keys (Do, Lam).
- The speed control shows the speed the song actually plays at after
  snapping (112.5%, not the 110% you dragged to).
- Ensembles keep the chord's root when a chord has more notes than voices,
  so a 3-voice G7 is no longer rootless.
- The help texts of some custom voicing fields now match what the voicing
  engine does.
- The Insert Capo dialog no longer claims a capo never changes the sound:
  with a fretted voicing it does.
- Desktop on Linux: the Edit menu shows the Redo shortcut that actually
  works (Ctrl+Shift+Z).

- Unusual song text can no longer freeze Chord Notepad. A chord with a long
  run of digits, many unclosed `{`, or a very large file with many
  directives and comments used to take seconds to minutes to read; it's now
  instant. A directive has to fit on one line.
- Clicking a chord to hear it while the song is playing no longer interferes
  with playback, and clicked chords keep their smooth voice leading from one
  click to the next instead of starting over each time you press Play.

### Changed

- A lowercase root is always minor: `cmaj7`, `cM7` and `cΔ` are now C
  minor-major 7 (they played C major 7), like `c7` is `Cm7`. Roman numerals
  follow the same rule: `iimaj7` in C is D F A C#.
- Tempo can be 20 to 400 BPM everywhere, including a typed `{bpm}`. A
  relative change such as `{bpm: +50}` that would leave that range is
  clamped, with a warning in the status bar.
- Opening a song no longer changes your defaults in Settings. Values the song
  sets itself are shown as set by the song; a change you make that the song
  doesn't set lasts until you close the song. Only Settings changes the
  defaults.
- The AB / Do notation toggle in the toolbar now switches only the song you
  have open; it no longer changes your default. A new song starts in the
  notation set in Settings, and changing it there also switches a song you
  haven't switched by hand.
- Opening a song, or pasting one into an empty document, picks the notation
  its chords are written in: a song in `Sol Re Mim Do` opens in European
  even when American is the default. On Android this also covers a song
  restored after the system closed the app in the background. A song
  without chord names starts in the Settings default.
- Settings › Voicings shows note names (strings, voice ranges, hand ranges)
  in the notation chosen in Settings, so `Mi2 La2 Re3` with European, and
  accepts either spelling when you type one.
- Identify Chord names chords and notes in the notation of the song you
  have open: in a European song the keys, the notes and the results read
  `Do Mi Sol`, `Lam7`, `Domaj7/Mi`, and an inserted chord goes in that way.
  Typed notes can be in either notation (`Do Mi Sol` or `C E G`). On the
  desktop, switching AB / Do while it's open renames everything at once.
- Transpose spells chords for the key they land in: a song moved into B now
  gets `F#`, `C#` and `G#m` instead of `Gb`, `Db` and `Abm`, and one moved
  into Db gets `Gb` and `Ab7`. The key comes from the song's `{key}`, or
  from its chords when there is none. A diminished chord leading up a
  semitone gets a sharp (`D#dim7 Em7`). Transposed keys take the spelling
  with fewer sharps or flats, so C up a semitone is `Db` and Am down one is
  `G#m`, in the `{key}` and the toolbar key alike.
- Suggest Capo replaces a `{capo}` that comes before the first chord instead
  of adding a second one, and on a selection it changes only that part.
- The Windows, macOS and Linux downloads are smaller: they no longer bundle
  numpy, matplotlib, chardet and other packages the app never used, and on
  Windows two unused FluidSynth libraries (libinstpatch and libgobject). The
  Flatpak and snap no longer include chardet either.
- The help and README say where to get Chord Notepad: the GitHub releases, the
  Snap Store, and the Microsoft Store (a paid supporter edition of the same
  app). The help's "Limitations" section no longer claims there is no staff or
  tab view.
- The About dialog and the Windows executable's file properties now state the
  correct licence (GNU AGPL-3.0) and copyright holder. They wrongly said MIT.
- Dropped "ChordPro" from the Linux desktop entry and AppStream search
  keywords.
