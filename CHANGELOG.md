# Changelog

<!--
This file holds release notes for the *next* full release.
Write entries here as you work. When a full release is published, the contents
of this file are used as the GitHub release description, then automatically
moved to CHANGELOG_HISTORY.md and this file is reset.
-->

- Android: the drawer has Examples, which opens a copy of one of the example songs.
- Chords: C2 and C4 now play Csus2 (C D G) and Csus4 (C F G), as guitar books use them, instead of C with an added 9th or 11th. Songs that use C2 or C4 (on any root) sound different.
- Chords: new 7sus2 (C7sus2 is C D G B♭; C9sus2 is the same chord, since its 9th is the sus2) and 9sus (the same as 9sus4).
- Chords: fixed chords that played the wrong notes. C69(no5) and C69(no3) lost both the 3rd and the 5th; 13th chords with (no5) or (no3) gained the 11th they leave out; CmM9(no5) lost its 3rd instead of its 5th and CmM9(no3) its 9th; CM13, C13-9 and C13(#11) gained an 11th; C7(b9,#9) played C♭ E♭ G♭ D; and a 7th chord with an altered tone in parentheses lost its 7th (Cmaj7(#5), Cmaj7(#11), Cm7(b5), C7(9,#11)). Cmaj9, Cmaj13, Cm69, Cmaj9#11 and Cmaj13#11 with (no5) or (no3), Cmaj7(9,#11) and C7sus4(9) now play instead of being unknown.
- Chords: Caddb5 now adds a flat 5th and keeps the 5th (C E G G♭), as "add" does everywhere else; C(b5) is still C E G♭.
- Chord identifier: a bass that is a note of the chord is spelled as the chord spells it, so C E F♯ over F♯ is C(b5)/G♭, not C(b5)/F♯ (and C7#9 over its ♯9 is C7#9/D♯). C D G B♭ is C7sus2, and voicings without their 5th get the chord's own name: C E B D is Cmaj9(no5), C E B♭ D A is C13(no5).
- Chord identifier: names many more sets of notes. C E G♭ (or C E F♯) is C(b5); a chord with its 5th or 3rd left out gets a (no5) or (no3) name (C E B♭ is C7(no5), C D E is Cadd9(no5)); C G is C5; and rarer qualities the editor already reads now come back from the identifier too (C7#5#9, Cmaj7b5, C13#11 and others), also over a bass. A new fuzz test checks every chord the app reads, in every key and over every bass, against an independent theory table.
- Guitar voicings: the fretboard search now plays grips where the ring finger or pinky lies flat across two or three strings above the index, so up the neck a 9th is the chord-book grip (C9 x32333, D9 x54555, E9 076777, Cm9 x31333) instead of a thinner or wider shape, and 7♯9 and 13th chords get fuller, more compact shapes. Such a barre costs more than an index barre (a new "Ring or pinky barre" weight, per string under it); a barre over four strings, one with two fingers above it, or one in a four-fret stretch is still ruled out.
