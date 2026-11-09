# Changelog

<!--
This file holds release notes for the *next* full release.
Write entries here as you work. When a full release is published, the contents
of this file are used as the GitHub release description, then automatically
moved to CHANGELOG_HISTORY.md and this file is reset.
-->

- Chord identifier: names many more sets of notes. C E G♭ (or C E F♯) is C(b5); a chord with its 5th or 3rd left out gets a (no5) or (no3) name (C E B♭ is C7(no5), C D E is Cadd9(no5)); C G is C5; and rarer qualities the editor already reads now come back from the identifier too (C7#5#9, Cmaj7b5, C13#11 and others), also over a bass. A new fuzz test checks every chord the app reads, in every key and over every bass, against an independent theory table.
