# Changelog

<!--
This file holds release notes for the *next* full release.
Write entries here as you work. When a full release is published, the contents
of this file are used as the GitHub release description, then automatically
moved to CHANGELOG_HISTORY.md and this file is reset.
-->

- Word wrap is now a setting, and it's off by default: long lines scroll sideways, so each chord line stays over its lyric line, also on a narrow phone. Turn it on in Settings › General (on the desktop also View › Word Wrap, which now remembers its state). On the desktop this changes what you're used to: lines that used to wrap now scroll, with a scrollbar under the editor.
- Transpose keeps the spelling of chords from outside the key: F#m7b5 B7 Em in a song in Bb, up a tone, is G#m7b5 C#7 F#m (no longer Abm7b5 Db7), and transposing back gives the original chords.
- Transpose up and back down, and Convert there and back, give the song back as it was: the spaces and the mark a longer chord put into the lyric come out again. The mark in a word is now a middle dot (sin·ger), so your own hyphens are never added or removed.
- Convert keeps each chord over its syllable, as Transpose does (Rem Sol7 Do La7 converts to Dm G7 C A7 in the same columns).
- Transpose and Convert keep the cursor where it was (same line and column) instead of sending it to the end of the song.
- Transpose with nothing to move in the song's notation (Do selected over C G Am F) no longer moves the key or says it worked: it changes nothing and says "No European chords to transpose".
- Chord identifier: no more names that count the bass twice or pass an inversion off as an added tone: G B D F gives G7 and Bdim/G (not Bdimaddb6/G), and Bb D F Ab no longer lists Ddimaddb6. Typed notes can have double accidentals (Bbb, F##) and E#, B#, Cb, Fb.
- Inserting a chord from the identifier, or a directive, right after a chord keeps a space between them (F G7, not FG7).
- Insert Key offers the major and minor keys that have a key signature (Eb rather than D#).
- Chord sheet: a rest (`NC`) is no longer an unmarked gap. Every view labels it `NC`; the Staff view draws a whole rest on both staves (and a bar line where the rest starts a new bar), Tab a whole rest on the middle string line, and Fret cards a whole rest in a slim card. It's always shown as one bar's rest, whatever its length.
- Staff view: a chord outside the key is drawn as one stack of thirds in its own spelling (B in Db is B D# F#, no longer B Eb Gb).
- Guitar and other fretted voicings pick the shapes chord books show: B is x24442 (not x21x02), F is 133211 (not 10321x), G#m7 is 464444 (not 421102); open strings no longer get mixed into shapes up the neck.
- Chord sheet: the "Capo N" marker in the Tab and Fret cards views has its own place before its chord instead of covering the chord name, and the tab's fret numbers shrink with the strings in a short sheet or when zoomed, so they no longer overlap or get cut off. The piano roll's C2/C3/C4 labels are no longer cut off by the black keys.
- Voicings editor: a voicing can no longer be named like a built-in one ("Piano") or like another of your voicings in a different case; a number out of range says "Too high." or "Too low." once; messages name fields as the form does (Max fret, not 'max_fret'); Copy from existing no longer lists the voicing you're editing.
- Ensembles: putting a voice above a higher one (↑/↓) is now an error in the voicings editor instead of a voicing that silently plays fewer notes.
- Files: a song saved as Latin-1/Windows-1252 (or UTF-16) opens, and saving keeps a file's encoding and Windows line endings; only if your text has a character the file's encoding can't hold is it saved as UTF-8, and the status bar says so. Open and save errors name the file once.
- Export MIDI on a song without chords says so at once, without asking for a file (on Android it no longer leaves an empty .mid).
- A recent song that has gone leaves the recent list as soon as opening it fails, and the message gives its name (on Android it used to say a number).
- Android: release builds are shrunk and obfuscated with R8 (Play Console flagged 0% obfuscation). The code in the APK goes from 8.5 to 1.7 MB and the APK is about 7 MB smaller (universal 92.8 MB, arm64 71.8 MB). Keep rules cover what Python calls by name, and a unit test checks them; CI keeps the mapping files for retracing crashes.
- Android: renaming a song opened from Downloads no longer loses it. Android took away the app's access to the file right after the rename ("Permission Denial"), and the song dropped out of the recent list. Files from Downloads now get the "Couldn't rename" dialog with Save as… instead; the same file opened from the device's storage still renames in place.
- Android: a long-press in Edit no longer closes the app.
- Android: Back while the keyboard is up only closes the keyboard; it no longer asks to save and quit after you've typed.
- Android: dragging the playhead marker from a line's first chord scrubs instead of triggering the system Back gesture (which could close the app).
- Android: the chord identifier works on a phone held sideways (full screen, piano on the left, notes and chords on the right), and shows no chords while the typed notes have a mistake.
- Android: keyboard shortcuts (F1, Ctrl+N/O/S) keep working in the Play tab after you've typed in the editor; Ctrl+Z, Ctrl+Y and Ctrl+Shift+Z undo and redo even with Gboard.
- Android: Back on an instrument family returns to the families without leaving an invisible sheet that ate the next tap.
- Android: a song opened from another app always opens in the Play tab, closing Settings, the guide or About (Settings still asks first about a wrong value).
- Android: dialogs with a text field (Rename, Tempo, Label, Capo, Manual speed, voicing Rename) stay usable above the keyboard in landscape: title, field, message and buttons all show.
- Android: the landscape chord sheet column can't be made so narrow that a player button disappears.
- Android: Back → Don't save starts the next song with your Settings tempo, time signature and key; lowering Number of recent files applies at once; the Edit/Play tab survives the app being killed in the background.
- Android: phone landscape Edit shows the song's title (and the unsaved •; tap it to rename).
- Android: with word wrap on, a chord never splits across lines (D/F# stays whole).
- Android: rotating keeps what you typed in Manual speed and the cursor position in Insert dialogs; Rename no longer capitalises the first letter; the rename hint shows the " character.
- Android: Settings stays on the open page when you rotate; Edit in the problems dialog puts the cursor in the field that's wrong; − and + stop at their limits; drop-down menus are as wide as their field.
- Android: sheets and dialogs that scroll show a fade at the bottom while there's more, and landscape sheets no longer cover the status bar.
- Android: on a tablet the chord sheet starts at about a third of the screen height; the open-source licences list keeps its place after you read one; Back from the app's own licence returns to About.
- Android: Quick Start says the chord sheet shows in the Play tab.
- Android: TalkBack reads which voicing and instrument are selected, and names the instrument sheet's back arrow and the ribbon's › button.
