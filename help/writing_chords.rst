==============
Writing Chords
==============

This section covers all the chord notation that Chord Notepad recognizes.

Basic Chord Notation
====================

American Notation
-----------------

If you're used to writing chords as C, D, E, F, G, A, B - you already know
American notation. This is the most common system in the English-speaking world.

**The seven natural notes:**

.. code-block:: chord

   C   D   E   F   G   A   B

Each letter represents a major chord by default. So ``C`` means "C major."

**Adding sharps and flats:**

Use ``#`` for sharp and ``b`` for flat:

.. code-block:: chord

   C#  Db  D#  Eb  F#  Gb  G#  Ab  A#  Bb

.. note::
   ``C#`` and ``Db`` sound the same - they're just different names for the same
   note. Use whichever feels natural for your song's key.

European Notation (Solfège)
---------------------------

In many countries, chords use solfège syllables instead of letters:

.. list-table::
   :header-rows: 1
   :widths: 20 20 20

   * - American
     - European
     - Sound
   * - C
     - Do
     - C major
   * - D
     - Re
     - D major
   * - E
     - Mi
     - E major
   * - F
     - Fa
     - F major
   * - G
     - Sol
     - G major
   * - A
     - La
     - A major
   * - B
     - Si
     - B major

Sharps and flats work the same way: ``Do#``, ``Reb``, ``Fa#``, ``Solb``, etc.

To switch notations, use the **AB/Do** toggle in the toolbar. Existing chords
are converted automatically.

Switching Notations
-------------------

To switch notation systems:

1. Click the **AB** button for American notation
2. Click the **Do** button for European notation

The key selector in the toolbar will also update to match your chosen notation.


Chord Types and Modifiers
=========================

Major and Minor Chords
----------------------

**Major chords** are written as just the note name:

.. code-block:: chord

   C    F    G    D    A    E

**Minor chords** add ``m`` after the note:

.. code-block:: chord

   Cm   Fm   Gm   Dm   Am   Em

You can also write minor chords with a lowercase letter:

.. code-block:: chord

   c    f    g    d    a    e

Both ``Cm`` and ``c`` produce the same C minor chord.

Seventh Chords
--------------

Seventh chords add a seventh interval to the basic triad:

**Dominant 7th** - Add ``7``:

.. code-block:: chord

   C7   G7   D7   A7   E7

Common in jazz, blues, and rock.

**Major 7th** - Add ``maj7``:

.. code-block:: chord

   Cmaj7   Fmaj7   Gmaj7   Dmaj7

Common in jazz and pop.

**Minor 7th** - Add ``m7``:

.. code-block:: chord

   Cm7   Am7   Dm7   Em7

A minor triad with a minor seventh.

**Minor-Major 7th** - Add ``mM7``:

.. code-block:: chord

   CmM7   AmM7

A minor triad with a major seventh.

**Diminished 7th** - Add ``dim7``:

.. code-block:: chord

   Cdim7   Ddim7   Bdim7

All intervals are minor thirds.

**Half-Diminished** - Add ``m7b5`` or use ``ø``:

.. code-block:: chord

   Cm7b5   Am7b5   Bm7b5

Also called "minor 7 flat 5." Common in jazz as a ii chord in minor keys.

Extended Chords (9th, 11th, 13th)
---------------------------------

Extended chords stack more notes on top:

**Ninth chords:**

.. code-block:: chord

   C9       // Dominant 9 (C7 + 9th)
   Cmaj9    // Major 9 (Cmaj7 + 9th)
   Cm9      // Minor 9 (Cm7 + 9th)

**Eleventh chords:**

.. code-block:: chord

   C11      // Dominant 11
   Cmaj11   // Major 11
   Cm11     // Minor 11

**Thirteenth chords:**

.. code-block:: chord

   C13      // Dominant 13

Extended chords are common in jazz.

Suspended Chords
----------------

Suspended chords replace the third with another note:

**Sus4** - The third becomes a fourth:

.. code-block:: chord

   Csus4   Gsus4   Dsus4

**Sus2** - The third becomes a second:

.. code-block:: chord

   Csus2   Gsus2   Dsus2

**Sus** by itself means sus4:

.. code-block:: chord

   Csus    // Same as Csus4

Suspended chords often resolve to the corresponding major or minor chord.

Augmented and Diminished
------------------------

**Augmented** chords raise the fifth by a half step:

.. code-block:: chord

   Caug   C+   Gaug   G+

Both ``aug`` and ``+`` mean augmented.

**Diminished** chords lower the fifth by a half step:

.. code-block:: chord

   Cdim   C°   Gdim   G°

Both ``dim`` and ``°`` mean diminished.

Add Chords
----------

Add chords include an extra note without the seventh:

.. code-block:: chord

   Cadd9    // C major + 9th (no 7th)
   Cadd11   // C major + 11th
   Cadd2    // Same as Cadd9 (octave lower)

The difference between ``C9`` and ``Cadd9``:

* ``C9`` = C + E + G + Bb + D (includes the 7th)
* ``Cadd9`` = C + E + G + D (no 7th)

Power Chords
------------

Power chords contain only the root and fifth (no third):

.. code-block:: chord

   C5   G5   D5   A5   E5

Common in rock music, especially with distorted guitar.

Altered Chords
--------------

Jazz players often alter chord tones. You can write:

.. code-block:: chord

   C7b5     // Dominant 7 with flat 5
   C7#5     // Dominant 7 with sharp 5
   C7b9     // Dominant 7 with flat 9
   C7#9     // Dominant 7 with sharp 9 (the "Hendrix chord")
   C7#11    // Dominant 7 with sharp 11
   C7b13    // Dominant 7 with flat 13

You can combine alterations:

.. code-block:: chord

   C7b9b13  // Dominant 7 with flat 9 and flat 13

The shorthand ``alt`` means an altered dominant:

.. code-block:: chord

   Calt     // Interpreted as C7b9b13


Slash Chords (Bass Notes)
=========================

A slash chord tells you to play a specific bass note under the chord:

.. code-block:: chord

   C/G      // C major with G in the bass
   Am/E     // A minor with E in the bass
   D/F#     // D major with F# in the bass

**Format:** ``Chord/BassNote``

Slash chords are written as the chord, then a forward slash, then the bass note.
The bass note can be any note, not just notes from the chord.

**Common uses:**

* **Inversions** - ``C/E`` and ``C/G`` are inversions of C major
* **Walking bass** - ``C  C/B  Am  Am/G  F`` creates a descending bass line
* **Pedal bass** - ``C/G  F/G  G`` keeps G in the bass throughout

.. code-block:: chord

   // Walking bass line example
   C  C/B  Am  Am/G  F  G  C


Roman Numeral Notation
======================

Roman numerals represent chords relative to the key. Instead of writing specific
notes, you write the chord's position in the scale.

What Are Roman Numerals?
------------------------

In the key of C:

.. list-table::
   :header-rows: 1
   :widths: 15 15 25

   * - Roman
     - Chord
     - Scale Degree
   * - I
     - C
     - First (tonic)
   * - ii
     - Dm
     - Second
   * - iii
     - Em
     - Third
   * - IV
     - F
     - Fourth
   * - V
     - G
     - Fifth (dominant)
   * - vi
     - Am
     - Sixth
   * - vii°
     - Bdim
     - Seventh

**Uppercase = major**, **lowercase = minor**.

Major vs Minor (I vs i)
-----------------------

The case tells you the chord quality:

.. code-block:: chord

   I    // Major chord on the first degree
   i    // Minor chord on the first degree
   IV   // Major chord on the fourth degree
   iv   // Minor chord on the fourth degree

Common Progressions
-------------------

Roman numerals make it easy to write progressions that work in any key:

.. code-block:: chord

   I   IV   V   I       // Classic rock/pop
   I   V   vi  IV       // The "four chord" progression
   ii  V   I            // Jazz turnaround
   I   vi  IV  V        // 50s progression

Set the key using the key selector in the toolbar (or a ``{key:}`` directive),
and Chord Notepad will play the right chords.

Using Accidentals
-----------------

Put accidentals **before** the numeral:

.. code-block:: chord

   bVII     // Flat seven (major chord a whole step below I)
   bIII     // Flat three (major chord)
   #IV      // Sharp four (major chord)
   #iv°     // Sharp four diminished

**Example - a rock progression:**

.. code-block:: chord

   {key: A}
   I   bVII   IV   I    // A  G  D  A

Roman Numerals with Extensions
------------------------------

Add chord extensions just like with regular chords:

.. code-block:: chord

   I        // Major
   Imaj7    // Major 7
   ii7      // Minor 7 (ii is already minor)
   V7       // Dominant 7
   viim7b5  // Half-diminished (natural in minor keys)

Slash Bass with Roman Numerals
------------------------------

You can even write slash chords with roman numerals:

.. code-block:: chord

   I/V      // Tonic chord with the fifth in the bass
   vi/IV    // vi chord with IV as bass note


Chord Duration
==============

By default, each chord lasts one beat. Use ``*`` to change this.

Setting Duration
----------------

**Format:** ``Chord*beats``

.. code-block:: chord

   C*2      // C major for 2 beats
   Am*4     // A minor for 4 beats
   G*1      // G major for 1 beat (default)

Decimal Durations
-----------------

You can use decimal values:

.. code-block:: chord

   C*1.5    // One and a half beats
   F*0.5    // Half a beat
   G*2.5    // Two and a half beats

Mixed Durations
---------------

Combine different durations on the same line:

.. code-block:: chord

   C*2  F  G*2         // C for 2 beats, F for 1, G for 2
   Am*4 G*2 F*2        // Am for 4, G for 2, F for 2

**Example - a waltz feel (3/4 time):**

.. code-block:: chord

   {time: 3/4}
   C*3  Am*3  F*3  G*3   // Each chord fills a full measure


NC (No Chord) - Rests and Silence
=================================

The ``NC`` symbol represents silence or a rest during playback. Use it to create
pauses, breaks, or empty space in your chord progressions.

Basic NC Usage
--------------

Write ``NC`` wherever you want silence:

.. code-block:: chord

   C  G  NC  Am        // Play C, G, silence, then Am

NC with Duration
----------------

Like regular chords, NC supports duration modifiers:

.. code-block:: chord

   C*4  G*4  NC*2  Am*4    // Two beats of silence between G and Am
   NC*4                     // A full measure of silence

**Common uses:**

* **Song intros** - Start with silence before the first chord
* **Breaks and pauses** - Create dramatic pauses in the music
* **Endings** - End a song with a rest instead of sustaining a chord
* **Count-ins** - Give yourself time to prepare before playing

Examples
--------

**Intro with count-in:**

.. code-block:: chord

   NC*4                    // One measure rest (count-in)
   C*4  Am*4  F*4  G*4     // Verse starts

**Dramatic pause:**

.. code-block:: chord

   C  G  Am  F             // Build up
   NC*2                     // Dramatic pause
   G*4                      // Resolution

**Ending with silence:**

.. code-block:: chord

   C*4  G*4  C*8           // Final progression
   NC*4                     // Clean ending with silence


Adding Comments
===============

Comments let you add notes that won't be played.

Comment Syntax
--------------

Use ``//`` to start a comment:

.. code-block:: chord

   // This is a comment
   C  Am  F  G  // This is also a comment

Everything after ``//`` on that line is ignored during playback.

Using Comments for Lyrics
-------------------------

Add lyrics to help you remember the song structure:

.. code-block:: chord

   // Verse 1
   C         Am        F         G
   // When I find myself in times of trouble

   // Chorus
   F    G    C    Am
   // Let it be, let it be

Using Comments for Notes
------------------------

Leave reminders for yourself:

.. code-block:: chord

   C*2  G  Am  F    // TODO: try different voicing here

   // Bridge - modulate to D major
   D  A  Bm  G


Putting It All Together
=======================

Here's an example that uses everything you've learned:

.. code-block:: chord

   // "My Song" - Full Arrangement
   {bpm: 120}
   {time: 4/4}
   {key: G}

   // Count-in (one measure of silence)
   NC*4

   // Intro - sparse, let it breathe
   G*4  D/F#*4

   {label: verse}
   // Verse - steady rhythm
   G  D  Em  C
   G  D  C*2

   {label: chorus}
   // Chorus - more energy
   Em  C  G  D
   Em  C  G*2

   // Build to end
   {bpm: +10}
   C  D  G*4  NC*2    // Dramatic pause before repeat

   // Repeat the whole song
   {loop: verse 2}
   {loop: chorus 2}

This example shows:

* Comments for organization
* Directives for tempo, time, and key
* Various chord types
* Duration modifiers
* Slash chords
* NC for rests and pauses
* Labels and loops

See :doc:`directives` for more on ``{bpm}``, ``{time}``, ``{key}``, ``{label}``,
and ``{loop}``.
