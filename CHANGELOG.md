# Changelog

<!--
This file holds release notes for the *next* full release.
Write entries here as you work. When a full release is published, the contents
of this file are used as the GitHub release description, then automatically
moved to CHANGELOG_HISTORY.md and this file is reset.
-->

- Android: the hint strip at the bottom of the Edit tab, which showed a directive's syntax while the cursor was inside it, is gone. Touch and hold a red or faded directive in the Play tab still explains it.
- Loops: the loop picker (desktop) and the Insert form's count (Android) start at 2, since a count of 1 would not loop at all. A `{loop: verse 1}` you type or already have still works and plays the section once; opened in the picker it shows 2.
