# Changelog

<!--
This file holds release notes for the *next* full release.
Write entries here as you work. When a full release is published, the contents
of this file are used as the GitHub release description, then automatically
moved to CHANGELOG_HISTORY.md and this file is reset.
-->

- macOS: sound follows the Mac's output device. Switching from headphones to the speakers (or the other way) while the app is open used to leave the sound on the old device, so you heard nothing; the app now moves to the new output within a second, even mid-song.
- macOS: the window's text and controls are the same size as on Windows and Linux; they were a quarter smaller, and looked small next to the chord sheet.
- Android: in Identify Chord, a double tap on a result no longer inserts it. A tap picks the chord and plays it; Insert puts the picked one in your song. A tap also plays at once now, without waiting to see whether a second tap follows.
- Android: Quick Start's examples fit on a narrow phone. A long chord line used to run past the box's right edge (it only scrolled sideways); the example's text now shrinks a little so the whole line shows, and chords still sit over their lyrics.
- Undo right after New no longer fills the new, untitled song with the previous song's text. New now starts an empty undo history, as Open does (desktop and Android).
- The app talks to FluidSynth through its own small binding instead of the pyFluidSynth package; nothing changes in how it sounds.
