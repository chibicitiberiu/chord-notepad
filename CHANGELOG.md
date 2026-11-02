# Changelog

<!--
This file holds release notes for the *next* full release.
Write entries here as you work. When a full release is published, the contents
of this file are used as the GitHub release description, then automatically
moved to CHANGELOG_HISTORY.md and this file is reset.
-->

- Android: during playback, only a tap on a chord moves the playhead; a tap between chords no longer makes the song jump. Chords are also a little easier to hit, and tapping one while nothing plays scrolls the chord sheet to it.
- Android: tap a greyed-out button or chord sheet tab to see why it's unavailable (was touch and hold).
- Voicings editor: the **Load config** button is now **Copy from existing**, which says better what it does.
- Tempo, time signature and key can now be changed while a song is paused, not only when it's stopped. Press Play and it carries on from the paused chord with the new values. While a song plays they are locked, like the voicing.
- Android: the song pill's sheet is now called **Playback settings**. Each row says what it does, a note says the values aren't saved in the song, and **Write into song** works while paused too (Play then starts from the paused chord).
- Android: tapping a chord in the chord sheet moves the playhead there too, like tapping it in the text. During playback the song jumps to it.
- Chord sheet: the Staff view draws the key signature for keys in European notation (Sol, Fa, Mib...) too; before, those songs showed none.
- Chord sheet: an ensemble's upper staff can use a treble clef with a small 8 below (**Upper staff** in the voicing's settings), so tenors are written an octave above how they sound, as in men's choir music. The Male Choir (TTBB) preset uses it, with its tenors on the upper staff; the Treble Choir and String Quartet presets now set each voice's staff too (the viola stays on Auto).
