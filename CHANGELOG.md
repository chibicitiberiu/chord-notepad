# Changelog

<!--
This file holds release notes for the *next* full release.
Write entries here as you work. When a full release is published, the contents
of this file are used as the GitHub release description, then automatically
moved to CHANGELOG_HISTORY.md and this file is reset.
-->

### Added

- **Linux packages.** Chord Notepad is now built as a Flatpak (a
  `.flatpak` file attached to each release) and as a snap for the Snap Store.
  Both run sandboxed, with settings and logs kept in the sandbox's own folder.
- **Native file dialogs on Linux.** Open, Save As, Export MIDI and the
  soundfont picker use your desktop's own file dialog (GNOME, KDE and others)
  when it is available, instead of Tk's dated one.

### Changed

- **Errors are always shown.** When something goes wrong, the app now says so
  in a dialog with the reason (and where the log file is), instead of failing
  silently. This covers opening, saving and exporting files, playback and
  audio problems, the help window, and settings. If audio can't start, Play
  explains why instead of playing silence.
- On Linux, settings and logs follow the XDG base directories
  (`$XDG_CONFIG_HOME`, `$XDG_DATA_HOME`) when they are set. The defaults
  (`~/.config` and `~/.local/share`) are unchanged.

### Fixed

- Choosing "Yes" to save unsaved changes no longer discards your edits when
  the save fails; the New/Open/Close you started is stopped instead.
- Saving to an existing file that can't be written no longer silently opens
  Save As; it tells you why the save failed.
- The Transpose dialog no longer closes silently on input that isn't a number.
- Linux desktops show Chord Notepad's own icon and name for its window.
