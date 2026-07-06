================
The Chord Sheet
================

The chord sheet is a strip docked under the editor that shows your song's
voiced chords laid out left to right, in the order they play. It's a way to
see -- and hear -- exactly what playback will do, chord by chord.


What It Shows
================

Every chord in the strip is the *exact* voicing that plays: the same
optimization pass that decides what you hear also decides what the strip
draws, so there's no separate "preview" logic to drift out of sync with
playback. Loops are unrolled, so a section played three times appears three
times, once per pass -- and because voice leading looks at the chord before
and after each occurrence, the same chord symbol can come out with different
notes (or a different fingering) each time through, exactly as it sounds.

A rest (``NC``) keeps its slot in the timeline as a gap, so the strip's
rhythm still reads correctly even where nothing sounds.

Roman-numeral chords show the chord they resolve to in the current key in
parentheses: ``V7`` in the key of C is labeled ``V7 (G7)``. If the key
changes mid-song, each card resolves against the key in effect at that
point.

Click any chord in the strip to hear that exact voicing once, the same
way clicking a chord in the editor plays it.


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

Piano roll
-------------

A DAW-style piano roll: pitch runs bottom-to-top, time runs left to right,
and every voiced note is a horizontal bar whose length follows the chord's
duration. Rows for black-key pitches are shaded and each C gets a guide
line, with a small keyboard along the left edge for orientation. Available
for any voicing. Bars are color-coded: for the piano model the two hands
get two tones, and for an ensemble each voice gets its own color.

Staff
--------

One continuous grand staff running the length of the song, engraved with
real music-font glyphs: whole-note heads, sharps, flats, and naturals.
The key signature is drawn after the clefs from the song's key, and again
after a double barline wherever a ``{key}`` directive changes it; notes
then only carry accidentals where they deviate from the signature
(including a natural sign to cancel it). Notes are spelled to match the
key signature -- a ``Db`` chord in F# major is drawn as C# with no
accidental -- while the chord labels stay exactly as you typed them.
Available for any voicing. An
ensemble voicing routes each voice to the staff (treble or bass) set for
it -- see :doc:`ensembles` for where that per-voice ``staff`` setting comes
from -- and colors each voice, with a small legend at the left. The piano
model splits by hand (left hand to the bass staff, right hand to the
treble); everything else splits at middle C.

Fret cards
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
chord's fret numbers written onto them at its position. Like Fret cards, this
needs fingering data and is only available for a fretboard-model voicing.

If you switch to a voicing that doesn't produce fingering data (piano or an
ensemble) while Fret cards or Tab is active, the strip falls back to
the Piano roll automatically.

Parts of a view that you need for orientation stay pinned at the left edge
while the strip scrolls: the piano roll's keyboard, and the staff's clefs
and key signature (which switches to show the key in effect at the first
visible chord once you scroll past a ``{key}`` change).

The Staff, Fret cards, and Tab views have **−** / **+** buttons at the right
end of the strip's header to make their drawing smaller or larger. The zoom
level is remembered per view.


Capo
======================

A capo is set with a ``{capo: N}`` directive in the song (see
:doc:`directives`). When one is in effect and a fretboard voicing is active,
the **Fret cards** and **Tab** views draw the chord shapes *relative to the
capo* -- the top of a fret diagram becomes the capo, and the fret numbers are
counted from there, so an awkward barre song reads as the easy open shapes you
would actually play. A small ``Capo N`` marker appears by the chord it starts
at (and again wherever a mid-song ``{capo}`` changes it). The capo changes only
the shapes shown, never the pitch: playback, the piano roll, and the staff are
unaffected, and non-fretboard voicings ignore it.

Suggesting a Capo
-----------------

To find a good capo, use :menuselection:`Tools --> Suggest Capo...`. It asks
which fretboard voicing to optimize for -- defaulting to the current one, or
standard guitar when the active voicing is not a fretboard voicing -- then
scores capo positions over the selection (or the whole song when nothing is
selected) and inserts the ``{capo: N}`` directive at that point, as a single
undo step. It looks for the position that makes the part easiest to play:
fewest barres, lowest on the neck, most open strings. If no capo helps, it says
so and inserts nothing.


Following Playback
======================

While the song plays, the chord currently sounding is highlighted, and the
strip auto-scrolls to keep the playhead in a comfortable spot rather than
jumping around: normal forward playback nudges the view forward as the
playhead approaches the right edge, and a loop restart or a play-from-cursor
jump snaps the view to keep the new position in view.


The Timeline Marker Lane
============================

A slim lane above the strip marks points in the timeline: section starts
(from ``{label}``), loop repeats (from ``{loop}``, shown as the section name
and which pass you're on, e.g. ``chorus (2/3)``), tempo changes (from
``{bpm}``), meter changes (from ``{time}``), and key changes (from
``{key}``). See :doc:`directives` for how those directives work. Markers
that fall on the same beat share a single combined flag, with one colored
tick per marker. The markers are purely informational -- they don't affect
playback or the voicing, just what you see above it.
