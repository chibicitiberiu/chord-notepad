# Changelog

<!--
This file holds release notes for the *next* full release.
Write entries here as you work. When a full release is published, the contents
of this file are used as the GitHub release description, then automatically
moved to CHANGELOG_HISTORY.md and this file is reset.
-->

- Android: available on Chromebooks and other devices without a touchscreen (Google Play no longer requires one).
- Android: the Quick Start's example songs follow dark mode instead of staying black on white.
- Android: during playback, only a tap on a chord moves the playhead; a tap between chords no longer makes the song jump. Chords are also a little easier to hit, and tapping one while nothing plays scrolls the chord sheet to it.
- Android: tap a greyed-out button or chord sheet tab to see why it's unavailable (was touch and hold).
- Linux: ARM64 builds (a standalone `ChordNotepad-linux-arm64`, a Flatpak and a snap) next to the x64 ones.
- macOS: a proper app in a disk image (`.dmg`): drag it to Applications and open it like any other Mac app, instead of running a bare program from Terminal.
- macOS: a build for Intel Macs (`ChordNotepad-macos-x64.dmg`), next to the Apple silicon one.
- macOS: FluidSynth is built into the app, so installing it from Homebrew is no longer needed.
- Voicings editor: the **Load config** button is now **Copy from existing**, which says better what it does.
