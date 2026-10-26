# Changelog

<!--
This file holds release notes for the *next* full release.
Write entries here as you work. When a full release is published, the contents
of this file are used as the GitHub release description, then automatically
moved to CHANGELOG_HISTORY.md and this file is reset.
-->

### Added

- **Windows:** Release builds are now code-signed with Azure Trusted Signing.
  This clears the SmartScreen "unknown publisher" warning and lets the app
  launch on machines that enforce Windows Application Control (WDAC / Smart App
  Control), which previously blocked the unsigned executable.

### Changed

- Refreshed look: a modern native theme on Windows (it was using the classic
  Windows 95-style one), a lighter flat style on Linux, a tidier toolbar with
  hover feedback, slim scrollbars and a flat status bar.
- The chord sheet's views (Piano roll, Staff, Fret cards, Tab) are now tabs.
  Hovering a greyed-out tab explains how to enable it.

### Fixed

- The editor's default font is monospace again on a fresh install. The default
  (Tk's fixed-width font) was being read as an unknown font name, so Tk fell
  back to a proportional font and chords drifted out of line above the lyrics.
