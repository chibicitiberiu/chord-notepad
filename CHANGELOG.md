# Changelog

<!--
This file holds release notes for the *next* full release.
Write entries here as you work. When a full release is published, the contents
of this file are used as the GitHub release description, then automatically
moved to CHANGELOG_HISTORY.md and this file is reset.
-->

**A completely redesigned app.** Chord Notepad 0.6.0 is a top-to-bottom redesign and modernization of the desktop app, rebuilt from scratch with Qt Quick. It has a clean, modern look that is the same on Linux, Windows and macOS, light and dark themes, and sharp text and icons at any display scaling. Writing and playing now have their own workspaces, Edit and Play; the player has a real timeline with speed and volume controls; directives are inserted from a palette instead of dialogs; and the chord sheet is redrawn, with a piano roll on a time grid and a continuous staff with repeat signs. The editor gained the features you'd expect from a modern text editor, such as find and replace, line operations and go to line, and clicking any chord in the text plays it.

- Desktop: macOS now needs 14.4 or newer, and downloads are about 30 MB bigger because they carry Qt.
- Settings: before an upgrade first changes your settings file, the file is copied next to it (`settings.json.bak-v<version>-<date>-<time>`). A value that can't be used goes back to its default and the other settings stay, and a damaged file is set aside as `settings.json.corrupt-<date>-<time>` with a notice, where before either one reset every setting.
- Settings: copies of the built-in choirs and the String Quartet take the presets' new values for every setting you left unchanged; the settings you changed stay. A setting added in a new version starts at its default, or at the built-in's value in a copy of a built-in.
- Suggest Capo shows its choices instead of inserting a capo at once. While it scores the song a spinner turns; then every capo position from none to the 7th fret is listed in words, such as "Capo 3 · G D Em C · Easier", the recommended one first and already chosen. The capo the song already has there is marked Current, and choosing another voicing scores the list again. Pick a row and Apply it, or Cancel to change nothing. On the desktop and Android.
- Ensembles: a tone a chord alters chromatically goes on the way it was altered, so over F, Fdim, C/E a violin can play A, G♯, G where it used to leap from the G♯ up to C (new setting "Chromatic line continues").
- Fixed: since 0.3.0, a voicing made on the first day the app ran could have its penalties turned into rewards at the next start. Voicings that were hit get their signs back.
