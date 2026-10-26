# Changelog

<!--
This file holds release notes for the *next* full release.
Write entries here as you work. When a full release is published, the contents
of this file are used as the GitHub release description, then automatically
moved to CHANGELOG_HISTORY.md and this file is reset.
-->

### Changed

- **Refreshed look.** Windows now uses its modern native theme (the app was
  using the classic Windows 95-style one); Linux gets a lighter, flat style.
  The toolbar is tidier, with hover feedback on its buttons and the BPM and
  speed values shown as chips; scrollbars are slim, menus have more breathing
  room, and the status bar is flat.
- **Chord sheet tabs.** The chord sheet's views (Piano roll, Staff, Fret cards,
  Tab) are now tabs. Hovering a greyed-out tab explains how to enable it.
- **New Quick Start tour.** Examples are shown exactly as they appear in the
  editor, with chords highlighted: chords over lyrics, how chord lines are
  detected, Do-Re-Mi and Roman numerals, timing, song sections, and a picture
  of the chord sheet.

### Fixed

- The editor's default font is monospace again on a fresh install. The default
  (Tk's fixed-width font) was being read as an unknown font name, so Tk fell
  back to a proportional font and chords drifted out of line above the lyrics.
- The chord sheet remembers the view you picked. Starting with an empty
  document used to replace a saved Fret cards or Tab choice with Piano roll;
  now it shows Piano roll only until chords load, then switches back.
- The instrument menu's marker for the current instrument family now lines up
  with the other family names.
