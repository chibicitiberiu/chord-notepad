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

### Changed

- The Windows, macOS and Linux downloads are smaller: they no longer bundle
  numpy, matplotlib and other packages the app never used, and on Windows two
  unused FluidSynth libraries (libinstpatch and libgobject).
- The help and README say where to get Chord Notepad: the GitHub releases, the
  Snap Store, and the Microsoft Store (a paid supporter edition of the same
  app). The help's "Limitations" section no longer claims there is no staff or
  tab view.
- The About dialog and the Windows executable's file properties now state the
  correct licence (GNU AGPL-3.0) and copyright holder. They wrongly said MIT.
- Dropped "ChordPro" from the Linux desktop entry and AppStream search
  keywords.
