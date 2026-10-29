================
The Chord Sheet
================

.. only:: desktop

   The chord sheet is a strip docked under the editor that shows your song's
   voiced chords laid out left to right, in the order they play. It's a way to
   see -- and hear -- exactly what playback will do, chord by chord.

.. only:: android

   The chord sheet is a strip in the **Play** tab that shows your song's
   voiced chords laid out left to right, in the order they play. It's a way to
   see, and hear, exactly what playback will do, chord by chord. In portrait
   it sits under the song text; in landscape it sits beside it.


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

.. only:: desktop

   Click any chord in the strip to hear that exact voicing once, the same
   way clicking a chord in the editor plays it.

.. only:: android

   Tap any chord in the strip to hear that exact voicing once. This doesn't
   move the playhead, so you can audition chords anywhere in the song and
   still press **▶** to play from where you were.


Showing and Resizing the Strip
==================================

.. only:: desktop

   Toggle the strip from :menuselection:`View --> Chord Sheet`. Hiding it stops
   the (fairly expensive) voicing work the strip does in the background; showing
   it again picks up whatever you've typed since and renders it.

   A sash between the editor and the strip lets you drag it taller or shorter to
   suit how much of the song you want visible at once. Both the panel's height
   and the view you last picked (see below) are remembered between sessions.

.. only:: android

   The chord sheet belongs to the **Play** tab. It is never shown in Edit, so
   the text gets the whole screen while you write. In Play, the **▭** button
   at the right end of the player shows or hides it; the button is tinted
   while the sheet is shown. The sheet starts out hidden, and the app
   remembers your choice. Hiding it stops the (fairly expensive) voicing work
   the strip does in the background; showing it again picks up whatever
   you've typed since and renders it. A thin progress bar under the view tabs
   runs while the strip is being drawn.

   **In portrait**, the sheet sits below the text. Drag the small handle on
   its top edge to make it taller or shorter (up to about 60% of the screen).

   **In landscape** (phones and tablets), the text is on the left, and the
   chord sheet and a narrower player share the right column. Drag the
   vertical handle between them to change the width of that column, from 30%
   to 70% of the screen. With the sheet hidden, the text takes the whole
   width and the player goes back to the bottom.

.. platform-figure:: landscape-play
   :platforms: android
   :alt: A phone held sideways in the Play tab: the song text on the left,
         the chord sheet's piano roll and the player in the right column,
         with a vertical handle between them.

   A phone in landscape. The handle between the text and the right column
   sets the column's width.

.. only:: android

   The sheet's height, the column width and the view you last picked (see
   below) are remembered between sessions.


The Four Views
==================

.. only:: desktop

   The tabs above the strip switch between four ways of drawing the same voiced
   chords. Which ones are available depends on the active voicing; a tab that
   can't be used right now is greyed out, and hovering it tells you why (the
   song has no chords yet, or it needs a fretted voicing such as Guitar, picked
   from :menuselection:`Playback --> Voicing`):

.. only:: android

   The tabs above the strip switch between four ways of drawing the same voiced
   chords. Which ones are available depends on the active voicing; a tab that
   can't be used right now is greyed out. Touch and hold it to see why (the
   song has no chords yet, or it needs a fretted voicing such as Guitar,
   picked in the player's Voicing sheet). If the tabs don't all fit, swipe
   them sideways.

Piano roll
-------------

A DAW-style piano roll: pitch runs bottom-to-top, time runs left to right,
and every voiced note is a horizontal bar whose length follows the chord's
duration. Rows for black-key pitches are shaded and each C gets a guide
line, with a small keyboard along the left edge for orientation. Available
for any voicing. Bars are color-coded: for the piano model the two hands
get two tones, and for an ensemble each voice gets its own color.

.. platform-figure:: chord-sheet-piano-roll
   :platforms: android
   :alt: The piano roll: a small keyboard on the left, chord names along the
         top and horizontal note bars, brown for the left hand and blue for
         the right.

   Piano roll, piano voicing: the left hand in brown, the right hand in blue.

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

.. platform-figure:: chord-sheet-staff
   :platforms: android
   :alt: The Staff view: a grand staff with the key signature of G, whole-note
         chords under their names, and the zoom buttons at the top right.
         The Fret cards and Tab tabs are greyed out.

   Staff view with a piano voicing. Fret cards and Tab are greyed out because
   they need a fretted voicing.

Fret cards
------------

.. only:: desktop

   A standard vertical chord diagram: strings, frets, and finger positions,
   nut at the top. Only available when a fretboard-model voicing (guitar or
   another fretted instrument, see :doc:`fretted`) is active, because this view
   needs fingering data -- a specific fret per string -- that only a fretboard
   voicing produces. Pick a guitar or other fretted voicing under
   :menuselection:`Playback --> Voicing` to unlock it.

.. only:: android

   A standard vertical chord diagram: strings, frets, and finger positions,
   nut at the top. Only available when a fretboard-model voicing (guitar or
   another fretted instrument, see :doc:`fretted`) is active, because this view
   needs fingering data -- a specific fret per string -- that only a fretboard
   voicing produces. Pick a guitar or other fretted voicing in the player's Voicing
   sheet to unlock it.

.. platform-figure:: chord-sheet-fret-cards
   :platforms: android
   :alt: Fret cards: one chord diagram per chord, with open and muted string
         marks above the nut and dots for the fretted notes.

   Fret cards with the Guitar (Standard) voicing.

Tab
------

A continuous tab lane: string lines spanning the whole strip, with each
chord's fret numbers written onto them at its position. Like Fret cards, this
needs fingering data and is only available for a fretboard-model voicing.

.. platform-figure:: chord-sheet-tab
   :platforms: android
   :alt: The Tab view: six string lines with each chord's fret numbers written
         on them under the chord name.

   Tab with the Guitar (Standard) voicing.

If you switch to a voicing that doesn't produce fingering data (piano or an
ensemble) while Fret cards or Tab is active, the strip falls back to
the Piano roll automatically.

Parts of a view that you need for orientation stay pinned at the left edge
while the strip scrolls: the piano roll's keyboard, and the staff's clefs
and key signature (which switches to show the key in effect at the first
visible chord once you scroll past a ``{key}`` change).

.. only:: desktop

   The Staff, Fret cards, and Tab views have **−** / **+** buttons at the right
   end of the strip's header to make their drawing smaller or larger. The zoom
   level is remembered per view.

.. only:: android

   The Staff, Fret cards, and Tab views have zoom buttons (magnifiers with
   **−** and **+**) at the right end of the strip's header to make their
   drawing smaller or larger, or you can pinch the sheet with two fingers.
   The piano roll doesn't zoom, so it shows no zoom buttons and ignores a
   pinch. The zoom level is remembered per view.

   Swipe the strip sideways to scroll through the song.


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

.. only:: desktop

   To find a good capo, use :menuselection:`Tools --> Suggest Capo...`. It asks
   which fretboard voicing to optimize for -- defaulting to the current one, or
   standard guitar when the active voicing is not a fretboard voicing -- then
   scores capo positions over the selection (or the whole song when nothing is
   selected) and inserts the ``{capo: N}`` directive at that point, as a single
   undo step. It looks for the position that makes the part easiest to play:
   fewest barres, lowest on the neck, most open strings. If no capo helps, it says
   so and inserts nothing.

.. only:: android

   To find a good capo:

   1. Go to the **Edit** tab. To get a capo for one part of the song only,
      select that part; otherwise the whole song is used.
   2. Tap **＋ Insert** in the Edit ribbon, then **Capo**.
   3. Tap **Suggest**. If you already know the fret, type it in the
      **Fret** field (0 to 12, where 0 means no capo) and tap **Insert**
      instead.
   4. Pick the fretboard voicing to optimize for and tap **OK**. It starts on
      the current voicing, or on standard guitar when the current voicing
      isn't a fretboard voicing.

.. platform-figure:: capo-suggest
   :platforms: android
   :alt: The Suggest Capo dialog with a list of fretboard voicings, Guitar
         (Standard - EADGBE) selected, and Cancel and OK buttons.

   Suggest Capo asks which fretted instrument to optimize for.

.. only:: android

   Chord Notepad then scores capo positions over the selection (or the whole
   song) and inserts the ``{capo: N}`` directive at that point, as a single
   undo step. It looks for the position that makes the part easiest to play:
   fewest barres, lowest on the neck, most open strings. If no capo helps, it
   says so and inserts nothing. Switch back to Play and pick a fretted
   voicing to see the new shapes in Fret cards or Tab.


Following Playback
======================

While the song plays, the chord currently sounding is highlighted, and the
strip auto-scrolls to keep the playhead in a comfortable spot rather than
jumping around: normal forward playback nudges the view forward as the
playhead approaches the right edge, and a loop restart or a play-from-cursor
jump snaps the view to keep the new position in view.

.. only:: android

   The sounding chord's column is shaded yellow. While nothing plays, a thin
   line in the app's accent colour runs down the left edge of the chord the
   playhead is on, so you can see where **▶** will start.


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
