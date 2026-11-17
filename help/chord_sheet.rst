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

A rest (``NC``) keeps its slot in the timeline, labelled with ``NC``, so the
strip's rhythm still reads correctly even where nothing sounds. The Staff,
Fret cards and Tab views also draw a rest symbol in it (in Fret cards a rest
gets a card as wide as a chord's); the piano roll leaves its lane empty.

Roman-numeral chords show the chord they resolve to in the current key in
parentheses: ``V7`` in the key of C is labeled ``V7 (G7)``. If the key
changes mid-song, each card resolves against the key in effect at that
point.

Every second section of the song sits on a slightly darker background
(slightly lighter in the dark theme), so you can see where one section ends
and the next begins in every view. Sections start where the marker lane's
section and loop flags are (see below): a part before the first
``{label}`` counts as the first section, and each pass of a loop is a
section of its own.

.. only:: desktop

   Click any chord in the strip to hear that exact voicing once, the same
   way clicking a chord in the editor plays it. The playhead moves to it, and
   the text scrolls to show that chord if it was out of view.
   **Shift+click** a chord to hear it rolled, one note at a time from the
   lowest up, like a quick strum; the playhead moves the same way.

.. only:: android

   Tap any chord in the strip to hear that exact voicing once. The playhead
   moves to it too, the same as tapping the chord in the text, so **▶** plays
   from there. While a song plays, a tap on a chord in the strip makes
   playback jump to it instead.


Showing and Resizing the Strip
==================================

.. only:: desktop

   In the **Play** workspace the strip is always there. In **Edit**, toggle it
   with **F9**, the **Chord sheet** button in the toolbar, or
   :menuselection:`View --> Chord sheet under the text`. Hiding it stops
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
   can't be used right now is greyed out. Tap it to see why (the
   song has no chords yet, or it needs a fretted voicing such as Guitar,
   picked in the player's Voicing sheet). If the tabs don't all fit, swipe
   them sideways.

Piano roll
-------------

A DAW-style piano roll: pitch runs bottom-to-top, time runs left to right,
and every voiced note is a horizontal bar whose length follows the chord's
duration. Rows for black-key pitches are shaded and a guide line marks each
octave under its C (a darker one under middle C), with a small keyboard
along the left edge for orientation, its Cs labelled in the song's notation
(C4 or Do4). Available for any voicing. Bars are color-coded: for the piano
model the two hands get two tones, for an ensemble each voice gets its own
color, and other voicings use one indigo.

The piano roll's horizontal axis is time, measured in beats: a chord is
exactly as wide as it is long, so ``C*8`` in 4/4 spans two bars, every bar
of a time signature has the same width (a 3/4 bar is three quarters of a
4/4 one), and a rest takes its full length too. A tempo change doesn't
change any widths. Bar lines and fainter beat lines between them form a
regular grid; when you zoom out far enough for the beats to crowd together,
the beat lines are left out. A chord too short for its name to fit above it
shows its bars without the name. The other views aren't time-accurate yet:
they give a long chord more room, but not in proportion.

When a bar is tall and long enough, it carries its note's name, such as
F#3 (or Fa#3 in European notation). Notes are named the way the Staff view
spells them, from the chord and the key, so an E flat chord in E flat shows
Eb, G and Bb, never D#. The bars are taller when the strip is taller or the
song spans fewer notes; on a short strip the names are left out. Zooming
the piano roll stretches time only: its rows always fill the strip.

.. platform-figure:: chord-sheet-piano-roll
   :platforms: desktop
   :alt: The piano roll under the text: a small keyboard on the left, the
         section's name and the chord names along the top, a bar for each
         voiced note (right hand blue, left hand brown), and the playing
         chord's column shaded.

   The piano roll.

.. platform-figure:: chord-sheet-piano-roll
   :platforms: android
   :alt: The piano roll: a small keyboard on the left, chord names along the
         top and horizontal note bars, brown for the left hand and blue for
         the right.

   Piano roll, piano voicing: the left hand in brown, the right hand in blue.

Staff
--------

One continuous grand staff running the length of the song, engraved with
real music-font glyphs: note heads, sharps, flats, and naturals. Rhythm
isn't shown yet: every chord is drawn as a whole note, however long it
lasts, and a longer chord only gets more room. The chord names all have one
size and sit on one line; a chord too short for its name gets a wider slot.

.. only:: desktop

   A note at the bottom left of the strip, just above the scroll bar, says
   so while the Staff view is shown. Click **Dismiss** after it to hide it
   for good; the app remembers that.

The key signature is drawn after the clefs from the song's key, and again
after a double barline wherever a ``{key}`` directive changes it; notes
then only carry accidentals where they deviate from the signature
(including a natural sign to cancel it). Notes are spelled to match the
key signature -- a ``Db`` chord in F# major is drawn as C# with no
accidental -- while the chord labels stay exactly as you typed them.
A rest (``NC``) shows as a whole rest on both staves; it's always drawn as
one bar's rest, whatever its length.

Since loops are unrolled, the passes of a repeated part follow one another
on the staff, marked with repeat signs: every pass opens with ``|:`` and
ends with ``:|``, so two passes meet at ``:||:``. The last pass ends with
``:|`` too, where the ``{loop}`` sits and the song moves on. The song ends
with a final bar line (a thin line and a thick one), which takes the repeat
dots, ``:||``, when a loop is the last thing in it. A song that plays
``Am F`` twice between ``C G`` and ``Dm`` reads
``| C G |: Am F :||: Am F :| Dm ||``. If the key changes where a pass starts
or right after a loop, the new key signature comes right after the repeat
sign.

The staff grows with the strip up to a comfortable size; on a taller strip
it keeps that size and sits in the middle. Zoom in to draw it larger, up to
the size that still fits the strip's height.

Available for any voicing. An
ensemble voicing routes each voice to the staff (treble or bass) set for
it -- see :doc:`ensembles` for where that per-voice ``staff`` setting comes
from -- and colors each voice, with a small legend at the left that lists
the voices from the highest down (Soprano, Alto, Tenor, Bass). An ensemble
can also set its upper staff to a treble clef with a small 8 below, the usual
clef for tenors: the notes on that staff are then written an octave higher
than they sound (the Male Choir (TTBB) preset does this). The piano
model splits by hand (left hand to the bass staff, right hand to the
treble); everything else splits at middle C.

.. platform-figure:: chord-sheet-staff
   :platforms: desktop
   :alt: The Staff view: treble and bass staves with the chords stacked as
         notes, the key signature and a repeat sign at the left, the playing
         chord's column shaded, and the note that rhythm isn't shown yet
         beside the view tabs.

   The staff view.

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
   :platforms: desktop
   :alt: The Fret cards view: a guitar chord diagram for each chord, with
         the playing chord's card shaded.

   Fret cards with a guitar voicing.

.. platform-figure:: chord-sheet-fret-cards
   :platforms: android
   :alt: Fret cards: one chord diagram per chord, with open and muted string
         marks above the nut and dots for the fretted notes.

   Fret cards with the Guitar (Standard - EADGBE) voicing.

Tab
------

A continuous tab lane: string lines spanning the whole strip, with each
chord's fret numbers written onto them at its position. Like Fret cards, this
needs fingering data and is only available for a fretboard-model voicing.

.. platform-figure:: chord-sheet-tab
   :platforms: desktop
   :alt: The Tab view: the strings of a guitar with the fret numbers of each chord.

   Tab with a guitar voicing.

.. platform-figure:: chord-sheet-tab
   :platforms: android
   :alt: The Tab view: six string lines with each chord's fret numbers written
         on them under the chord name.

   Tab with the Guitar (Standard - EADGBE) voicing.

If you switch to a voicing that doesn't produce fingering data (piano or an
ensemble) while Fret cards or Tab is active, the strip falls back to
the Piano roll automatically, and goes back to your view when you pick a
fretted voicing again.

Parts of a view that you need for orientation stay pinned at the left edge
while the strip scrolls: the piano roll's keyboard, and the staff's clefs
and key signature (which switches to show the key in effect at the first
visible chord once you scroll past a ``{key}`` change).

.. only:: desktop

   Every view has **−** / **+** buttons at the right end of the strip's header
   to make its drawing smaller or larger (the piano roll gets wider or
   narrower); clicking the percentage between them goes back to 100%. You
   can also hold Ctrl and turn the mouse wheel over the strip, or use
   **View → Chord sheet view → Zoom in**, **Zoom out** and **Reset zoom**.
   The zoom level is remembered per view.

   To move along the song, scroll the mouse wheel over the strip, drag it
   sideways with the mouse (the pointer turns into a closed hand; a drag
   doesn't play the chord it started on), or use the scroll bar at the bottom.

.. only:: android

   Every view has zoom buttons (magnifiers with **−** and **+**) at the right
   end of the strip's header to make its drawing smaller or larger, or you
   can pinch the sheet with two fingers (the piano roll gets wider or
   narrower). The zoom level is remembered per view.

   Swipe the strip sideways to scroll through the song.


Capo
======================

A capo is set with a ``{capo: N}`` directive in the song (see
:doc:`directives`). When one is in effect and a fretboard voicing is active,
the **Fret cards** and **Tab** views draw the chord shapes *relative to the
capo* -- the top of a fret diagram becomes the capo, and the fret numbers are
counted from there, so an awkward barre song reads as the easy open shapes you
would actually play. A small ``Capo N`` marker appears by the chord it starts
at (and again wherever a mid-song ``{capo}`` changes it). The capo never
changes the key: a written ``Eb`` still sounds as E♭. It does change which
shapes a fretboard voicing picks, so playback, the piano roll and the staff
follow those shapes (the same chord can come out with different notes than
without the capo). Piano and ensemble voicings ignore it.

Suggesting a Capo
-----------------

.. only:: desktop

   To find a good capo, click **Capo** in the Edit toolbar (the capo icon, next
   to Transpose) or use :menuselection:`Tools --> Suggest capo...`. It asks
   which fretboard voicing to optimize for -- defaulting to the current one, or
   standard guitar when the active voicing is not a fretboard voicing -- then
   scores capo positions over the selection (or the whole song when nothing is
   selected) and writes the ``{capo: N}`` directive, as a single undo step. It
   looks for the position that makes the part easiest to play: fewest barres,
   lowest on the neck, most open strings. If no capo helps, it says so and
   changes nothing. A capo has to make the chords easier on average, so a
   long song or a chorus that repeats is judged the same as a short one.

   .. platform-figure:: capo-suggest
      :platforms: desktop
      :alt: The Suggest Capo dialog: an explanation, the part of the song it
            applies to, a Voicing box set to Guitar (Standard - EADGBE), and
            the Cancel and Suggest buttons.

      Suggest Capo asks which fretted instrument to optimize for.

   The directive goes at the very top of the song, or at the start of the
   selection's first line. If a ``{capo}`` already sits between there and the
   first chord, it is replaced instead of adding a second one.

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
   song) and writes the ``{capo: N}`` directive, as a single undo step. It
   looks for the position that makes the part easiest to play: fewest barres,
   lowest on the neck, most open strings. If no capo helps, it says so and
   changes nothing. A capo has to make the chords easier on average, so a long
   song or a chorus that repeats is judged the same as a short one. The
   directive goes at the very top of the song, or at the
   start of the selection's first line; a ``{capo}`` already sitting between
   there and the first chord is replaced instead. Switch back to Play and pick a fretted
   voicing to see the new shapes in Fret cards or Tab.


Following Playback
======================

While the song plays, the chord currently sounding is highlighted, and the
strip auto-scrolls to keep the playhead in a comfortable spot rather than
jumping around: normal forward playback nudges the view forward as the
playhead approaches the right edge, and a loop restart or a play-from-cursor
jump snaps the view to keep the new position in view.

The sounding chord's column gets a light tint of the app's accent colour,
over everything drawn there, with a stronger line of the same colour along
its top and bottom. While nothing plays, a thin line in the accent colour
runs down the left edge of the chord the playhead is on, so you can see
where **▶** will start.


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
