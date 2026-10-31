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

### Fixed

- Pressing Pause right after Play, while the song is still being prepared,
  now pauses it. Before, the song started playing anyway while the Play
  button showed it as paused.
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
  not D.
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

### Changed

- Tempo can be 20 to 400 BPM everywhere, including a typed `{bpm}`. A
  relative change such as `{bpm: +50}` that would leave that range is
  clamped, with a warning in the status bar.
- Opening a song no longer changes your defaults in Settings. Values the song
  sets itself are shown as set by the song; a change you make that the song
  doesn't set lasts until you close the song. Only Settings changes the
  defaults.
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
