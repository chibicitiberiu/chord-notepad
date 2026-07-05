================
The Chord Sheet
================

The chord sheet is a strip docked under the editor that shows your song's
voiced chords laid out left to right, in the order they play. It's a way to
see -- and hear -- exactly what playback will do, one card per chord.


What It Shows
================

Every card in the strip is the *exact* voicing that plays: the same
optimization pass that decides what you hear also decides what the strip
draws, so there's no separate "preview" logic to drift out of sync with
playback. Loops are unrolled, so a section played three times gets three
cards, one per pass -- and because voice leading looks at the chord before
and after each occurrence, the same chord symbol can come out with different
notes (or a different fingering) each time through, exactly as it sounds.

A rest (``NC``) gets a slim, empty card rather than a blank gap, so the
strip's rhythm still reads correctly even where nothing sounds.

Roman-numeral chords show the chord they resolve to in the current key in
parentheses: ``V7`` in the key of C is labeled ``V7 (G7)``. If the key
changes mid-song, each card resolves against the key in effect at that
point.

Click any card to hear that exact voicing once, the same way clicking a
chord in the editor plays it.


Showing and Resizing the Strip
==================================

Toggle the strip from :menuselection:`View --> Chord Sheet`. Hiding it stops
the (fairly expensive) voicing work the strip does in the background; showing
it again picks up whatever you've typed since and renders it.

A sash between the editor and the strip lets you drag it taller or shorter to
suit how much of the song you want visible at once. Both the panel's height
and the view you last picked (see below) are remembered between sessions.


The Four Views
==================

A **View** picker above the strip switches between four ways of drawing the
same voiced chords. Which ones are available depends on the active voicing:

Keyboard
-----------

A miniature piano keyboard per chord, with the sounding notes highlighted.
Available for any voicing. For the piano model specifically, each card
stacks two keyboards -- right hand on top, left hand below -- matching how
the piano model splits a chord across the hands; every other model draws a
single keyboard row.

Staff
--------

A grand staff per chord, with the voiced notes drawn as whole notes.
Available for any voicing. An ensemble voicing routes each voice to the
staff (treble or bass) set for it -- see :doc:`ensembles` for where that
per-voice ``staff`` setting comes from. The piano model splits by hand
(left hand to the bass staff, right hand to the treble); everything else
splits at middle C.

Chord box
------------

A standard vertical chord diagram: strings, frets, and finger positions,
nut at the top. Only available when a fretboard-model voicing (guitar or
another fretted instrument, see :doc:`fretted`) is active, because this view
needs fingering data -- a specific fret per string -- that only a fretboard
voicing produces. Pick a guitar or other fretted voicing under
:menuselection:`Playback --> Voicing` to unlock it.

Tab
------

A continuous tab lane: string lines spanning the whole strip, with each
chord's fret numbers written onto them at its position. Like Chord box, this
needs fingering data and is only available for a fretboard-model voicing.

If you switch to a voicing that doesn't produce fingering data (piano or an
ensemble) while Chord box or Tab is active, the strip falls back to
Keyboard automatically.


Capo Suggestion
======================

When **Allow capo** is enabled (see :doc:`settings`) and a fretboard voicing
is active, the header row shows a hint such as ``Suggested: capo 2`` next to
the view buttons while the Chord box or Tab view is active. It names the capo
position that makes the whole song easiest to play -- fewest barres, lowest on
the neck, most open strings -- for songs written in awkward keys. Nothing is
re-voiced or transposed; it is advice only, telling you where a capo would
help. Nothing is shown when the best choice is no capo, when a non-fretboard
voicing is active, or when the setting is off.


Following Playback
======================

While the song plays, the chord currently sounding is highlighted, and the
strip auto-scrolls to keep the playhead in a comfortable spot rather than
jumping around: normal forward playback nudges the view forward as the
playhead approaches the right edge, and a loop restart or a play-from-cursor
jump snaps the view to keep the new position in view.


The Timeline Marker Lane
============================

A slim lane above the cards marks points in the timeline: section starts
(from ``{label}``), loop repeats (from ``{loop}``, shown as the section name
and which pass you're on, e.g. ``chorus (2/3)``), tempo changes (from
``{bpm}``), and meter changes (from ``{time}``). See :doc:`directives` for
how those directives work. The markers are purely informational -- they
don't affect playback or the voicing, just what you see above it.
