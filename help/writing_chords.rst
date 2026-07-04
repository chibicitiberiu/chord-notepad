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

.. tip::
   You can type the real musical symbols too: ``♯`` works anywhere ``#`` does,
   and ``♭`` anywhere ``b`` does (so ``C♯`` = ``C#`` and ``E♭`` = ``Eb``).
   Chord Notepad treats the unicode and ASCII forms as identical. The same goes
   for chord qualities further down -- see :ref:`alternative-spellings`.

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
Minor, sevenths, and every other quality below use the same suffixes as American
notation, just on a solfège root: ``Dom`` is C minor, ``Sol7`` is G7, ``Lam7``
is A minor 7.

Switching Notations
-------------------

The **AB / Do** toggle in the toolbar decides which system Chord Notepad *reads
and displays*:

1. Click **AB** for American note names (C, D, E ...).
2. Click **Do** for European solfège (Do, Re, Mi ...).

The key selector updates to match, and from that point on the editor recognizes
and highlights chords in the notation you picked.

.. important::
   The toggle does **not** rewrite text you have already typed. Flipping from
   **AB** to **Do** does not turn a ``C`` on the page into ``Do`` -- it only
   changes what the editor expects going forward, so your existing ``C`` chords
   simply stop being recognized until you toggle back.

   To actually rewrite the chords in your document from one system to the other,
   use :menuselection:`Tools --> Convert to American Notation` or
   :menuselection:`Tools --> Convert to European Notation`. Those commands
   rewrite every chord in place; the toggle never does.

Roman numerals (see :ref:`roman-numerals`) are independent of this toggle. They
are recognized in both modes and always resolve against the current key.


Chord Types and Modifiers
=========================

Everything in this section is a **quality suffix** added to a root note. The
suffix is what matters, and it works the same on any root and in any of the
three notations. A dominant seventh is ``7`` whether you write ``G7`` (American),
``Sol7`` (European), or ``V7`` (roman, in the key that puts G on the fifth
degree). So the examples below mostly use American roots for brevity, but each
one has a European and a roman equivalent:

.. list-table::
   :header-rows: 1
   :widths: 25 25 25 25

   * - Quality
     - American
     - European
     - Roman (key of C)
   * - Major
     - ``C``
     - ``Do``
     - ``I``
   * - Minor
     - ``Am``
     - ``Lam``
     - ``vi``
   * - Dominant 7
     - ``G7``
     - ``Sol7``
     - ``V7``
   * - Minor 7
     - ``Dm7``
     - ``Rem7``
     - ``iim7``
   * - Major 7
     - ``Cmaj7``
     - ``Domaj7``
     - ``Imaj7``
   * - Sus4
     - ``Gsus4``
     - ``Solsus4``
     - ``Vsus4``

.. _alternative-spellings:

Alternative Spellings
---------------------

Most chord qualities can be written more than one way, and Chord Notepad accepts
all of the common spellings, including the real musical symbols. These are
exactly equivalent -- pick whichever you like to type:

.. list-table::
   :header-rows: 1
   :widths: 30 45 25

   * - Quality
     - Accepted spellings
     - Example
   * - Sharp
     - ``#`` or ``♯``
     - ``F#`` = ``F♯``
   * - Flat
     - ``b`` or ``♭``
     - ``Bb`` = ``B♭``
   * - Minor
     - ``m``, ``min``, ``mi``, ``-``, or a lowercase root
     - ``Cm`` = ``Cmin`` = ``C-`` = ``c``
   * - Major 7
     - ``maj7``, ``M7``, or ``Δ`` (with or without a ``7``)
     - ``Cmaj7`` = ``CM7`` = ``CΔ`` = ``CΔ7``
   * - Dominant 7
     - ``7`` or ``dom7``
     - ``C7`` = ``Cdom7``
   * - Diminished
     - ``dim`` or ``°``
     - ``Cdim`` = ``C°``
   * - Half-diminished
     - ``m7b5`` or ``ø``
     - ``Cm7b5`` = ``Cø``
   * - Augmented
     - ``aug`` or ``+``
     - ``Caug`` = ``C+``

.. note::
   The unicode symbols (``♯ ♭ ° ø Δ``) and their ASCII stand-ins (``# b dim
   m7b5 maj7``) are treated as identical, so a sheet that mixes them still plays
   correctly. The triangle ``Δ`` means a major *seventh*: ``CΔ`` is ``Cmaj7``,
   and a number after it carries the extension (``CΔ9`` is ``Cmaj9``). There is
   one spelling that is deliberately notation-specific: ``o`` for diminished --
   covered under :ref:`aug-dim` below.

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

Sixth Chords
------------

Sixth chords add the sixth note of the scale to a triad. Unlike a seventh, the
sixth sits a whole step below the octave, giving a softer, resolved sound often
heard at the end of a phrase:

**Major 6th** - Add ``6``:

.. code-block:: chord

   C6   G6   F6      // C6 = C + E + G + A

**Minor 6th** - Add ``m6``:

.. code-block:: chord

   Cm6   Am6   Dm6   // Cm6 = C + Eb + G + A

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
   Cmaj13   // Major 13
   Cm13     // Minor 13

Extended chords are common in jazz.

.. note::

   Chord Notepad voices these the way a player would rather than stacking
   every interval. The 11th and major 11th drop the 3rd, which sits a
   semitone below the 11th, and the 13th chords (``C13``, ``Cm13``,
   ``Cmaj13``) drop the 11th for the same reason. Minor 11ths keep the
   flat 3rd, since it doesn't clash.

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

.. _aug-dim:

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

.. note::
   **The ``o`` shorthand for diminished works only in roman numerals.** In
   classical harmony a small circle after a numeral -- often typed as a plain
   letter ``o`` -- marks a diminished chord, so ``viio`` and ``io`` are
   recognized (see :ref:`roman-numerals`).

   It is deliberately **not** accepted on American or European chords, because
   there ``o`` is ambiguous: it collides with note names and solfège syllables.
   ``Do`` already means C in European notation, and a trailing ``o`` on a letter
   root (``Bo``, ``Co``) is too easy to confuse with a typo. For lettered and
   solfège chords, write ``dim`` or ``°`` instead -- ``Cdim`` or ``C°``, never
   ``Co``.

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


.. _roman-numerals:

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

   I        // Major triad
   Imaj7    // Major 7
   ii7      // Minor 7 -- lowercase stays minor (Dm7 in C)
   V7       // Dominant 7 -- uppercase (G7 in C)
   II7      // Secondary dominant -- uppercase forces major (D7 in C)
   viim7b5  // Half-diminished (natural in minor keys)

.. note::
   The case of the numeral sets the chord quality, and it carries through to the
   extension. A lowercase numeral stays minor: ``ii7`` is a minor seventh (Dm7
   in C), ``ii9`` a minor ninth, ``ii6`` a minor sixth. An uppercase numeral
   stays major, so its seventh is dominant (``V7`` is G7). To write a
   **secondary dominant** -- a major-quality seventh on a degree that is
   normally minor -- use an uppercase numeral: ``II7`` in C is D7, the V-of-V. A
   ``maj7`` is major either way (``iimaj7`` is D major 7).

Slash Bass with Roman Numerals
------------------------------

You can even write slash chords with roman numerals:

.. code-block:: chord

   I/V      // Tonic chord with the fifth in the bass
   vi/IV    // vi chord with IV as bass note


Chord Duration
==============

By default, each chord lasts **one bar** -- a full measure of the current time
signature. So in 4/4 a bare ``C`` is held for four beats; in 3/4 it is held for
three. Use ``*`` to give a chord a specific length in **beats** instead.

.. note::
   Duration is always counted in *beats*, while the default (no ``*``) is one
   whole *bar*. The two line up only when you happen to fill a bar: in 4/4,
   ``C`` and ``C*4`` sound the same, but ``C*1`` is a quarter of that bar.
   Change the bar length with a ``{time: ...}`` directive (see
   :doc:`directives`).

Setting Duration
----------------

**Format:** ``Chord*beats``

.. code-block:: chord

   C*2      // C major for 2 beats
   Am*4     // A minor for 4 beats
   G*1      // G major for just 1 beat (a bare G fills the whole bar)

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

Lyrics Are Not Comments
-----------------------

A common mistake is to comment out lyrics with ``//``. **Don't** -- lyrics go on
their own line, with no markers at all. Writing chords above the words they go
with is exactly what Chord Notepad is built for:

.. code-block:: chord

   C         Am        F         G
   When I find myself in times of trouble
   F         G         C
   Mother Mary comes to me

Chord Notepad reads the sheet line by line and works out on its own which lines
are chords and which are lyrics (see :doc:`introduction`). The chord line lights
up and plays; the lyric line is displayed but never played, no ``//`` required.
A lyric that happens to contain a chord-like word -- an *Am*, a *La*, a *Do* --
is still left alone, because the line as a whole doesn't read as chords.

So keep ``//`` for things that genuinely aren't part of the song.

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
   {loop: verse 2}    // play the verse twice

   {label: chorus}
   // Chorus - more energy
   Em  C  G  D
   Em  C  G*2
   {loop: chorus 2}   // play the chorus twice

   // Build to end
   {bpm: +10}
   C  D  G*4  NC*2    // Dramatic pause to finish

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
