# Changelog

<!--
This file holds release notes for the *next* full release.
Write entries here as you work. When a full release is published, the contents
of this file are used as the GitHub release description, then automatically
moved to CHANGELOG_HISTORY.md and this file is reset.
-->

### Added

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
  defined in the config file under `custom_ensembles`, the same way custom
  guitar tunings are. Exporting MIDI with an ensemble voicing active writes
  one named track per voice instead of a single chord track. See the new
  Ensemble Voicings help page for the preset ranges and the full list of
  tunable voicing parameters.

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

### Changed

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
