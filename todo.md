# To decide / to fix

App bugs and questions found while fact-checking the user guide (2026-10-30). Nothing below has been changed in the app yet; each needs Tibi's call. Details and evidence: the fact-check records (scratchpad factcheck_A.md / factcheck_B.md, summarised here).

## Decided by Tibi (2026-10-30)
- **Suggest Capo:** if a `{capo}` directive comes before the first chord, replace it; otherwise insert at the beginning (in progress).
- **Desktop:** add Capo to Tools → Insert (in progress).
- **Tempo range:** 20–400 everywhere, including typed `{bpm}` (in progress).
- **Invalid directives** (out of range, bad format, wrong/missing parameters) are highlighted red and ignored during playback (in progress). Each gets a reason and the correct syntax in the core. **To design:** a tooltip that suggests the syntax while typing, on desktop and Android.
- **Defaults:** opening a song must NOT change the defaults in Settings. Values the song sets are shown as overridden and can't be edited from the UI. Changing a value the song doesn't set (toolbar / Song defaults) is an immediate, temporary change only, not saved to Settings. Only Settings changes the defaults. With a mid-song tempo change, the toolbar shows the song's starting value, greyed out (to do).
- **Relative tempo out of 20–400** (e.g. `{bpm: +50}` at 380, or inside loops): clamp it and warn in the status bar; it isn't red (in progress).
- **Suggest Capo on a selection** applies to that part only, and the dialog says so (in progress).
- **A loop above its label** is invalid (red).
- **"la la la" lyric lines detected as chords:** a known issue, too ambiguous for a heuristic (chord lines can have directions and "?" too). Workaround: a line starting with `.` is plain text (in progress).
- **`iim7` and Berklee-style `IIm7`:** accept both as minor (in progress).
- **Voicing `label`:** keep it internal and never show it. The name is the display name. No change.
- **Syntax tooltip, design approved.** Desktop: the hint in the status bar while the cursor is in a directive, and a hover tooltip on a red directive. Android Edit mode: a hint strip above the keyboard, and long-press a red directive for the reason. To build after the core part lands.

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

## After the release: song structure (Tibi's idea, 2026-10-30; not before the Android release)
- Reusable parts that can be called from anywhere, e.g. `{part: verse1}` … `{endpart}` then `{call: verse1}`. Or the ChordPro-like alternative: `{play: chorus}` replays a section that's already labelled. Avoid `goto`.
- Label-less repeat blocks, `{loop: 3}` … `{endloop}`.
