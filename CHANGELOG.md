# Changelog

<!--
This file holds release notes for the *next* full release.
Write entries here as you work. When a full release is published, the contents
of this file are used as the GitHub release description, then automatically
moved to CHANGELOG_HISTORY.md and this file is reset.
-->

### Fixed

- The **Audio driver** setting is now used: Chord Notepad tries that driver
  first. Before, it was saved but ignored.
- If an audio driver can't start, Chord Notepad now tries the next one, and
  tells you when there's no working audio output at all. Before, a failed
  driver could leave playback silently doing nothing.

### Changed

- The help and README say where to get Chord Notepad: the GitHub releases, the
  Snap Store, and the Microsoft Store (a paid supporter edition of the same
  app). The help's "Limitations" section no longer claims there is no staff or
  tab view.
- The About dialog and the Windows executable's file properties now state the
  correct licence (GNU AGPL-3.0) and copyright holder. They wrongly said MIT.
- Dropped "ChordPro" from the Linux desktop entry and AppStream search
  keywords.
