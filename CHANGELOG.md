# Changelog

<!--
This file holds release notes for the *next* full release.
Write entries here as you work. When a full release is published, the contents
of this file are used as the GitHub release description, then automatically
moved to CHANGELOG_HISTORY.md and this file is reset.
-->

### Changed

- Guitar voicings are now chosen for the whole song at once instead of chord by
  chord. The picker weighs each fingering's own quality against how smoothly it
  transitions to its neighbours across the entire progression, using lookahead
  to avoid locally-pretty shapes that force awkward jumps later. Repeated
  sections (such as looped verses) are voiced in the context they actually play
  in each time through.
