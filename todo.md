# To decide / to fix

App bugs and questions found while fact-checking the user guide (2026-10-30). Nothing below has been changed in the app yet; each needs Tibi's call. Details and evidence: the fact-check records (scratchpad factcheck_A.md / factcheck_B.md, summarised here).

## Questions
- **Suggest Capo insert position:** it inserts `{capo: N}` at the top of the song (or the start of the selection), never at the cursor. Keep it, or insert at the cursor?
- **Desktop has no Capo in Tools → Insert** (Android's Insert sheet does). Add it?
- **Two BPM ranges:** the Insert dialog takes 20–300, the toolbar and Song defaults take 20–400. Unify?

## Bugs (from fact-check A)
1. **Chord Identifier and flats:** "Bb D F" gives `D`, "Eb G Bb" gives `G`, `G/D#`, "Db F Ab" gives `F`, `F/C#`. The notes are rewritten as sharps before identification.
2. **Tempo isn't range-checked in the song text.** `{bpm: 0}` crashes rendering (ZeroDivisionError); `{bpm: -200}` gives a negative tempo.
3. **Roman numerals with `ø`** (`viiø`, `iiø7`) show as valid but play silence. `iim7` isn't recognised. `C77`, `C79` and `Cadd4` count as valid.
4. **`{bpm: reset}`** returns to the song's first `{bpm}` only for a song opened from a file. For a typed song it goes to 120.
5. **Any key name is accepted:** `{key: Xyz}` shows as valid, and the Roman numerals after it play nothing. The same happens when Default key is None.
6. **Solfège lyric lines become chords:** a European line of only "la la la" is detected as chords, so it plays and Transpose changes it to "si si si".
7. **Desktop Redo shortcut:** the Edit menu shows Ctrl+Y on Linux, where Tk binds Ctrl+Shift+Z.
