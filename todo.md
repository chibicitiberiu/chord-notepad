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

## Bugs (from fact-check B)
8. **Loops that point at each other never finish rendering.** For example `{label: a}` C `{loop: b 2}` `{label: b}` G `{loop: a 2}`. The chord sheet probably hits this while you type.
9. **`{time: 0/4}` hangs the renderer.** A relative tempo change can also go negative (see 2).
10. **European keys (Do, Lam) are left out of MIDI export.** They aren't converted to the American spelling first.
11. **Opening a song rewrites the default tempo, time signature and key in Settings.** New song keeps them afterwards. Intended?
12. **The speed sheet shows the value you dragged to (110%)** while the song plays at the snapped speed (112.5%).
13. **The Insert Capo dialog says "It changes the shapes, not the sound".** With a fretted voicing the notes do change.
14. **Ensembles reuse the piano's omission weights.** When a chord has more notes than voices, the root goes first, giving rootless inversions (G7 for 3 voices comes out B3 D4 F4).
15. **Some voicing field help texts disagree with the engine:** octave leap, upper spacing, common tone (`src/settings_forms/voicing_texts.py`).
16. **A voicing's `label` is stored** (and Load config copies it), but it isn't shown anywhere.
17. **`bVI` in C plays G# major** instead of Ab.
18. **`{loop: my verse 2}` can't reach `{label: my verse}`**, so labels with spaces can't be looped.
