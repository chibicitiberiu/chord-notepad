# Changelog

<!--
This file holds release notes for the *next* full release.
Write entries here as you work. When a full release is published, the contents
of this file are used as the GitHub release description, then automatically
moved to CHANGELOG_HISTORY.md and this file is reset.
-->

### Added

- **Chord sheet** (View → Chord Sheet): a collapsible strip docked under the
  editor that lays out the song's voiced chords left to right, in playback
  order -- loops are unrolled, so a repeated section appears once per pass,
  and voice leading means the same chord symbol can be voiced differently
  from one pass to the next, exactly as it sounds. Four views, switched with
  toggle buttons: **Piano roll** (DAW-style, duration-proportional note bars,
  hands/voices color-coded) and **Staff** (one continuous engraved grand
  staff with key signatures, signature-relative accidentals, and per-voice
  colors) work for any voicing; **Fret cards** and **Tab** need fingering data
  and are only available for a fretboard-model voicing. A marker lane above
  the strip shows section labels, loop passes (``chorus (2/3)``), and
  tempo/meter changes. Roman-numeral chords are labeled with their resolution
  in the current key, e.g. ``V7 (G7)``. The strip follows playback with a
  highlight and auto-scroll, and clicking a chord plays that exact voicing.
  The piano roll's keyboard and the staff's clefs and key signature stay
  pinned at the left edge while the strip scrolls, and the Staff, Fret
  cards, and Tab views have per-view zoom buttons. The active view, zoom,
  and the panel's height are remembered between sessions. See the new
  Chord Sheet help page.

- **Transpose** (Tools → Transpose...): shift every chord in the selection
  (or the whole song, when nothing is selected) up or down by a number of
  semitones. Slash basses and ``{key}`` directives shift too, and a
  whole-song transpose also moves the toolbar key, so roman-numeral chords
  keep sounding the same. European chord names stay European. Chords keep
  their position above the right lyric syllable: the chord line absorbs
  small changes, and when a chord genuinely outgrows its slot the lyric
  line stretches with it (a space at a word gap, or a hyphen mid-word).
  One undo step reverses the whole operation.

- **Capo suggestion**: with **Allow capo** enabled (Tools → Settings... →
  Playback & Audio) and a fretboard voicing active, the chord sheet's Chord
  box and Tab views show the capo position that makes the whole song easiest
  to play (e.g. ``Suggested: capo 2`` for a song in F# major). Advice only --
  nothing is re-voiced.


- **Configurable piano voicing** (Tools → Settings... → Voicings): the
  piano model is now fully editable, the same as the fretboard and ensemble
  models. Hand ranges (left hand, right hand, preferred bass), scoring
  anchors (right-hand low anchor and center, low-interval floor, hand span,
  note-count limits, hand gap floor), the add-bass toggle, and every signed
  weight -- including the per-role omission group -- can all be tuned per
  voicing or loaded from **Grand Piano** as a starting point. See the new
  Piano Voicing help page for the full parameter reference.

- **Settings window** (Tools → Settings...): a proper settings UI with
  three pages -- General (font, notation, default key, quick start at
  startup, recent-files count, log level), Playback & Audio (default BPM
  and time signature, soundfont path, audio driver), and Voicings -- and
  Save/Cancel. The Voicings page is a fully functional editor for custom
  voicings: load any built-in preset or existing custom voicing as a
  starting point, edit its name, model, and every parameter (strings,
  frets, weights for fretboard; voices, spacing, weights for ensemble),
  and save. Save validates everything and reports exactly which voicing
  and field is wrong. Renaming or deleting the voicing currently selected
  for playback is handled correctly, and new or changed voicings appear in
  Playback → Voicing as soon as you save, no restart needed. Editing the
  config file by hand still works. See the new Settings help page.

- **Ensemble voicings** (Playback → Voicing): four new presets voice every
  chord for a fixed group of singers or players instead of one instrument --
  **Choir (SATB)**, **Male Choir (TTBB)**, **Treble Choir (SSA)**, and
  **String Quartet**. Each voice moves the way a trained ensemble would:
  common tones held, small steps preferred, parallel fifths and octaves
  avoided, and the leading tone resolving to the tonic when a `{key:}` is
  set. Chords with more notes than voices drop the least characteristic
  tone first (the fifth before the third, a `sus4`'s suspended note never
  dropped); chords with fewer notes double tones, preferring the root; slash
  chords put the bass note in the lowest voice. Custom ensembles can be
  defined in the config file under the `voicings` registry
  (`"model": "ensemble"`), the same mechanism used for custom fretted
  instruments. Exporting MIDI with an ensemble voicing active writes
  one named track per voice instead of a single chord track. See the new
  Ensemble Voicings help page for the preset ranges and the full list of
  tunable voicing parameters.

- **Arbitrary fretted instruments** (Playback → Voicing): the guitar voicer
  is now a general "fretboard model" that can voice any fretted instrument
  with 3 to 12 strings, including re-entrant tunings (a string tuned higher
  than the one before it, like a ukulele's high G) -- the bass is always
  whichever string actually sounds lowest, not whichever is listed first. A
  new **Ukulele** preset (G4 C4 E4 A4) joins the four existing guitar
  tunings. Custom fretted instruments -- a baritone ukulele, a banjo, a
  seven-string guitar in a tuning of your own -- can be defined the same way
  custom guitar tunings always could. See the new Guitar and Fretted
  Instruments help page for the built-in voicings, a worked custom example,
  and the full parameter reference.

- **Unified `voicings` config registry**: custom guitar/fretted tunings and
  custom ensembles now live together under a single `voicings` key in the
  config file, each entry tagged `"model": "fretboard"` or
  `"model": "ensemble"`. They appear in Playback → Voicing automatically,
  sorted by model then name.

- **Export MIDI...** (File menu) saves the current song as a standard MIDI
  file. The file matches playback exactly: the selected piano or guitar
  voicing, the real timing, tempo changes from `{bpm}`, time and key
  signature events from `{time}`/`{key}`, and the currently selected
  instrument as the MIDI program. Loops are unrolled into their repeated
  passes, `NC` sections become silence, and the whole song is exported from
  the beginning regardless of cursor position. The playback speed
  multiplier is not applied -- the file always uses the song's real tempo.
  Written as two tracks (conductor + chords) for easy import into DAWs and
  notation software.

### Fixed

- Pasting text with Windows-style line endings (CRLF) no longer leaves stray
  carriage-return characters in the editor (they showed up as junk glyphs at
  the ends of pasted lines). Pasted and opened text is also cleaned of
  non-breaking and zero-width spaces, which look right but silently break
  chord detection. Files on disk are never rewritten by this; the cleaned
  text only reaches the file when you save.

### Changed

- Guitar fingering selection now penalizes wide fretting-hand stretches:
  compact shapes are preferred generally, and 4-fret shapes that would force
  a middle finger to make the far reach (rather than a lengthwise
  index-to-pinky stretch) effectively always lose to a playable alternative.
  Both penalties are editable weights in the fretboard voicing settings.


- Voicing weights now use one consistent convention. Every weight is a
  signed number added to a voicing's score: positive seeks the trait,
  negative avoids it, zero is neutral, and higher is always more preferred.
  The old mix of "penalty", "cost", and "bonus" labels with all-positive
  magnitudes is gone; controls now carry neutral trait names (for example
  "Wide stretch" at `-1.2`, "Correct bass note" at `+8.0`) whose sign tells
  you the direction. Existing config files are upgraded automatically the
  first time Chord Notepad starts after the change, with old positive
  penalty magnitudes negated on load, so custom voicings keep behaving the
  same. Config keys are unchanged (`span_penalty` and the rest); only their
  sign and display labels changed.

- The **Options...** menu item is now **Settings...**, reflecting what it
  actually opens.

- Config files using the old `custom_tunings` or `custom_ensembles` keys are
  migrated to the unified `voicings` registry automatically the first time
  Chord Notepad starts after upgrading, including whichever voicing was
  selected at the time. There's nothing to do by hand.

- Guitar voicings are now chosen for the whole song at once instead of chord by
  chord. The picker weighs each fingering's own quality against how smoothly it
  transitions to its neighbours across the entire progression, using lookahead
  to avoid locally-pretty shapes that force awkward jumps later. Repeated
  sections (such as looped verses) are voiced in the context they actually play
  in each time through.

- Piano voicings now follow a two-hand model: a left hand on the bass and a
  right hand on the chord, each limited to a real hand's reach (five notes, a
  ninth span). The voicer chooses among root position and inversions, keeps
  extensions (9ths/11ths/13ths) above the core triad, and optimizes the whole
  song at once. This keeps the right hand in a stable central register instead
  of drifting downward over long progressions and looped sections -- a repeated
  chord is now voiced the same way every time through.

- The Voicings settings page is easier to use correctly: every control has a
  hover tooltip, invalid fields turn red as soon as you type them instead of
  only on Save, and cross-field problems (a relaxed span smaller than the
  normal span, a voice's low note above its high note) show up as a message
  at the top of the editor. Load config now asks for confirmation, since it
  replaces every parameter of the voicing you're editing. The ensemble
  voices editor is a proper table (Name / Low / High columns, Add voice,
  per-row remove), the parameter forms use a tidier multi-column layout, and
  each Weights section explains the signed-weight rule up front.
