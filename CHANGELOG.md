# Changelog

<!--
This file holds release notes for the *next* full release.
Write entries here as you work. When a full release is published, the contents
of this file are used as the GitHub release description, then automatically
moved to CHANGELOG_HISTORY.md and this file is reset.
-->

- macOS: sound follows the Mac's output device. Switching from headphones to the speakers (or the other way) while the app is open used to leave the sound on the old device, so you heard nothing; the app now moves to the new output within a second, even mid-song.
- The app talks to FluidSynth through its own small binding instead of the pyFluidSynth package; nothing changes in how it sounds.
