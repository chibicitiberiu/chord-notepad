# Changelog

<!--
This file holds release notes for the *next* full release.
Write entries here as you work. When a full release is published, the contents
of this file are used as the GitHub release description, then automatically
moved to CHANGELOG_HISTORY.md and this file is reset.
-->

- Android: release builds are shrunk and obfuscated with R8 (Play Console flagged 0% obfuscation). The code in the APK goes from 8.5 to 1.7 MB and the APK is about 7 MB smaller (universal 92.8 MB, arm64 71.8 MB). Keep rules cover what Python calls by name, and a unit test checks them; CI keeps the mapping files for retracing crashes.
- Android: renaming a song opened from Downloads no longer loses it. Android took away the app's access to the file right after the rename ("Permission Denial"), and the song dropped out of the recent list. Files from Downloads now get the "Couldn't rename" dialog with Save as… instead; the same file opened from the device's storage still renames in place.
- Chord sheet: a rest (`NC`) is no longer an unmarked gap. Every view labels it `NC`; the Staff view draws a whole rest on both staves (and a bar line where the rest starts a new bar), Tab a whole rest on the middle string line, and Fret cards a whole rest in a slim card. It's always shown as one bar's rest, whatever its length.
