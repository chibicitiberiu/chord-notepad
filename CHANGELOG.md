# Changelog

<!--
This file holds release notes for the *next* full release.
Write entries here as you work. When a full release is published, the contents
of this file are used as the GitHub release description, then automatically
moved to CHANGELOG_HISTORY.md and this file is reset.
-->

- Desktop: a new window, built with Qt Quick, replaces the old one. It looks the same on Linux, Windows and macOS, in a light or a dark theme (Settings › General, ☰ › Dark theme or Ctrl+Shift+L; System follows your desktop), and the whole window can be zoomed (Ctrl+Alt+Plus, Ctrl+Alt+Minus). Run `chord-notepad --ui tk` to get the old Tk window back; it stays for this release only and is removed in the next one. Downloads are about 30 MB bigger because they carry Qt.
- Desktop: two workspaces. **Edit** (Ctrl+1) has the toolbar and the rail with the Directives palette and the Chord identifier; **Play** (Ctrl+2) has the player bar, the frozen text and the chord sheet, always shown. In Edit, F9 shows or hides the chord sheet.
- Desktop: the menus moved to a ☰ button. The File, Edit, View, Playback, Tools and Help menu bar is still there: ☰ › Show menu bar keeps it, tapping Alt shows it for a moment, and Alt+F, Alt+E and so on open a menu.
- Desktop: the player bar in Play has a timeline with a segment for each labelled section (click or drag to seek), the bar and beat, a speed popup (slider, box and presets), a volume slider with mute, and buttons for the voicing and the instrument. Tempo, key and time signature are under the song's name; click one the song sets with a directive to jump to that directive.
- Desktop: a playhead, as on Android. Click a chord to hear it and move the marker there; ▶ plays from the marker, Shift+▶ from the text cursor, and a click while a song plays jumps playback to that chord. ⏮ keeps playing if the song was playing. Bars are counted from the top of the song.
- Desktop: the Insert dialogs are gone. The Directives palette inserts a tempo, time, key, capo, label, loop, rest or comment with its value selected, and a ▾ next to a directive opens a picker for its value. The Chord identifier is a sidebar now: click a result to insert it, ▶ to hear it (Shift+▶ rolled).
- Desktop: Settings is a window that saves as you go, with no Save and Cancel; a number outside its range is marked and never saved. The font is in Settings › General, and so is the new Theme.
- Desktop: shortcuts that were missing or wrong now work: Undo and Redo are greyed out when there is nothing to undo, Ctrl+Y and Ctrl+Shift+Z both redo, Ctrl+O no longer types a line break, shortcuts work with Caps Lock on and don't fire behind a dialog, every dialog closes with Escape, a time signature you type is applied, and the tempo wheel no longer sticks at multiples of 10. New: F5 and Shift+F5, Ctrl+M, Ctrl+] and Ctrl+[ for the speed, Ctrl+T, Ctrl+,, F11 and Alt+1 to Alt+4 for the chord sheet's views.
- Desktop: the user guide and the Quick Start describe the new window, with new screenshots.
