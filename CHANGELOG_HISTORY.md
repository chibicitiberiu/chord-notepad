# Release History

Append-only log of published releases. Newer releases at the top.
Entries are added automatically by the release pipeline.

## v0.2.0 — 2026-07-04

### Chord detection and voicing

- Extended chords are now voiced the way a player would: `C11` and `Cmaj11`
  drop the third that clashes with the eleventh, and `C13`/`Cm13`/`Cmaj13`
  drop the eleventh. Minor elevenths keep their flat third.
- Extension notes (9ths, 11ths, 13ths) now keep their proper octave during
  playback instead of collapsing into the root octave, so the colour of a
  chord is audible.
- Roman numerals: a lowercase numeral with a bare seventh is now minor, not
  dominant. `ii7` is Dm7; write `II7` for a secondary dominant (D7).
- `{loop: @start N}` now works. `@start` is a built-in label for the top of
  the document, so you can repeat a whole song without adding a `{label}`.
- The `Δ` (triangle) symbol now means a major *seventh*: `CΔ` is `Cmaj7`, and a
  number after it carries the extension (`CΔ9` is `Cmaj9`).
- Parenthesised major-seventh qualities resolve correctly: `Cm(maj7)` is a
  minor-major seventh, `C(maj7)` is `Cmaj7`.
- European chords that start with a solfège syllable (`Faug`, `Fadd9`, …) are
  no longer mangled during conversion.

### Fixes

- Released binaries no longer print `No module named 'PIL._tkinter_finder'`
  warnings while loading the toolbar icons.

### Documentation

- Rewrote the user guide with labelled screenshots and deeper explanations of
  how voice leading, voicings, loops, tempo, and chord notation actually work.
- Corrected the chord, directive, and reference tables against the code, and
  documented the notation shorthands (`# ♯`, `b ♭`, `°`, `ø`, `Δ`, `m(maj7)`).

## v0.1-build76 — 2026-05-30

- Initial release.

