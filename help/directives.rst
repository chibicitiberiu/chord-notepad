==========
Directives
==========

Directives are special commands that control how your song plays. They're
written in curly braces and don't produce sound themselves - they change the
*context* of playback.

Directives appear in **purple** in the editor when valid.


Tempo (BPM)
===========

The ``{bpm}`` directive controls how fast your song plays.

Setting Tempo
-------------

**Format:** ``{bpm: value}``

.. code-block:: chord

   {bpm: 120}     // 120 beats per minute
   {bpm: 90}      // Slower - 90 BPM
   {bpm: 160}     // Faster - 160 BPM

Valid range: 20-400 BPM. The toolbar's speed multiplier is applied on top of
this value, so a song written at ``{bpm: 120}`` with the multiplier set to
50% plays at 60 BPM.

Place the directive before the chords it should affect:

.. code-block:: chord

   {bpm: 100}
   C  Am  F  G    // Plays at 100 BPM

   {bpm: 140}
   C  Am  F  G    // Same chords, now at 140 BPM

Changing Tempo Mid-Song
-----------------------

You can change tempo anywhere in your song:

.. code-block:: chord

   // Verse - moderate tempo
   {bpm: 110}
   C  Am  F  G
   C  Am  F  G

   // Chorus - faster
   {bpm: 130}
   F  G  Am  C
   F  G  C

Relative Tempo Changes
----------------------

Instead of setting an exact BPM, you can adjust relative to the current tempo:

**Add or subtract:**

.. code-block:: chord

   {bpm: +20}     // Increase by 20 BPM
   {bpm: -15}     // Decrease by 15 BPM
   {bpm: +5}      // Slight increase

**Example - gradual build:**

.. code-block:: chord

   {bpm: 100}
   C  Am  F  G

   {bpm: +10}     // Now 110 BPM
   C  Am  F  G

   {bpm: +10}     // Now 120 BPM
   C  Am  F  G

**Percentage:**

.. code-block:: chord

   {bpm: 50%}     // Half speed
   {bpm: 200%}    // Double speed
   {bpm: 75%}     // Three-quarter speed

**Multiplier:**

.. code-block:: chord

   {bpm: 2x}      // Double speed
   {bpm: 0.5x}    // Half speed
   {bpm: 1.5x}    // 1.5 times faster

Resetting Tempo
---------------

Return to the original tempo you started with:

.. code-block:: chord

   {bpm: reset}      // Back to starting tempo
   {bpm: original}   // Same as reset

**Example:**

.. code-block:: chord

   {bpm: 120}        // Start at 120
   C  Am  F  G

   {bpm: 160}        // Speed up for chorus
   F  G  C  Am

   {bpm: reset}      // Back to 120 for next verse
   C  Am  F  G

``{tempo}`` is an alias for ``{bpm}`` - both work the same way.


Time Signature
==============

The ``{time}`` directive sets the time signature (beats per measure).

Setting Time Signature
----------------------

**Format:** ``{time: beats/unit}``

.. code-block:: chord

   {time: 4/4}    // Four quarter-note beats per measure (most common)
   {time: 3/4}    // Three beats - waltz time
   {time: 6/8}    // Six eighth-note beats - compound duple
   {time: 2/2}    // Two half-note beats - cut time

Common Time Signatures
----------------------

.. list-table::
   :header-rows: 1
   :widths: 15 30 30

   * - Signature
     - Feel
     - Examples
   * - 4/4
     - Standard, "four on the floor"
     - Most pop, rock, R&B
   * - 3/4
     - Waltz, flowing
     - Waltzes, ballads
   * - 6/8
     - Two groups of three, lilting
     - Irish music, slow rock
   * - 2/4
     - March, polka
     - Marches, some folk
   * - 5/4
     - Unusual, asymmetric
     - "Take Five" by Dave Brubeck
   * - 7/8
     - Complex, driving
     - Progressive rock

Changing Time Signature
-----------------------

You can change time signatures mid-song:

.. code-block:: chord

   // Verse in 4/4
   {time: 4/4}
   C  Am  F  G

   // Bridge in 3/4
   {time: 3/4}
   F*3  G*3  Am*3

   // Back to 4/4 for chorus
   {time: 4/4}
   F  G  C  Am


Key Signature
=============

The ``{key}`` directive sets the musical key, which affects how roman numerals
are interpreted.

Setting the Key
---------------

**Format:** ``{key: note}``

.. code-block:: chord

   {key: C}       // Key of C major
   {key: G}       // Key of G major
   {key: Am}      // Key of A minor
   {key: F#}      // Key of F# major
   {key: Bb}      // Key of Bb major

Why Key Matters
---------------

The key determines what notes roman numerals translate to:

**In the key of C:**

.. code-block:: chord

   {key: C}
   I  IV  V  I    // Plays as: C  F  G  C

**In the key of G:**

.. code-block:: chord

   {key: G}
   I  IV  V  I    // Plays as: G  C  D  G

Same roman numerals, different actual chords.

Key Changes (Modulation)
------------------------

Change keys within a song:

.. code-block:: chord

   // Start in C
   {key: C}
   C  Am  F  G    // or: I  vi  IV  V

   // Modulate to D
   {key: D}
   D  Bm  G  A    // Same progression, new key

.. note::
   The key directive also updates the "Key" display in the status bar during
   playback.


Labels and Loops
================

Labels mark positions in your song. Loops jump back to labels and repeat
sections. Together, they let you build full song structures without copying
and pasting.

Creating Labels
---------------

**Format:** ``{label: name}``

.. code-block:: chord

   {label: verse}
   C  Am  F  G

   {label: chorus}
   F  G  C  Am

Label names:

* Can contain letters, numbers, and underscores
* Are case-sensitive (``verse`` and ``Verse`` are different)
* Should be descriptive (``verse``, ``chorus``, ``bridge``, ``intro``, etc.)

Creating Loops
--------------

**Format:** ``{loop: labelname}`` or ``{loop: labelname count}``

.. code-block:: chord

   {loop: verse}        // Play "verse" section 2 times (default)
   {loop: verse 3}      // Play "verse" section 3 times
   {loop: chorus 1}     // Play "chorus" section 1 time

Building Song Structure
-----------------------

A loop repeats the stretch of song **between its label and the loop directive**,
in place. This is the one thing to get right about loops: a loop is not a
playlist and not a "goto." There is no instruction that jumps around to play
sections in a different order than they are written. You write the song out in
playing order, and drop a loop wherever a section should repeat before moving on.

Put the ``{label}`` at the start of a section and its matching ``{loop}`` at the
end:

.. code-block:: chord

   {bpm: 120}
   {key: G}

   {label: verse}
   G  D  Em  C
   G  D  C*2
   {loop: verse 2}     // play the verse twice, then carry on

   {label: chorus}
   Em  C  G  D
   Em  C  G*2
   {loop: chorus 2}    // play the chorus twice

This plays: **verse, verse, chorus, chorus.** Each section runs once as playback
reaches it; the loop directive then sends it back to the label for the remaining
repeats before falling through to whatever comes next.

Because a loop always covers everything from its label down to itself, you can
repeat several sections together by putting the label earlier:

.. code-block:: chord

   {label: main}
   G  D  Em  C        // verse
   Em  C  G  D        // chorus
   {loop: main 2}     // repeat the verse-and-chorus pair twice

If you want a verse-chorus-verse-chorus form where sections come back later, you
write them out in that order -- looping cannot fetch a section that has already
gone by.

Special Label: @start
---------------------

The ``@start`` label always refers to the beginning of the document:

.. code-block:: chord

   C  Am  F  G
   C  Am  F  G
   {loop: @start 2}    // Repeat everything from the beginning twice

Loop Behavior
-------------

Step by step, when playback reaches a ``{loop: label N}`` directive:

1. The section has just played once -- playback ran from the label straight down
   to the loop directive.
2. Playback jumps back to the label. The BPM, time signature, and key are
   restored to whatever they were *at that label*, so a tempo or key change made
   inside the section doesn't carry over into the next repeat.
3. The section plays again. Steps 2-3 repeat until it has played ``N`` times in
   total.
4. Playback then continues past the loop directive to the rest of the song.

A ``count`` of ``1`` (or no valid label) is a no-op -- the section simply plays
its single inline pass. Labels and loops are also handy for drilling one tricky
section over and over while you practice.


Multiple Directives
===================

You can put multiple directives on one line:

.. code-block:: chord

   {bpm: 120} {time: 4/4} {key: C}
   C  Am  F  G

Directives don't take up beats - they change playback settings but produce no
sound of their own. Each one takes effect at its position in the song, so a
directive placed mid-song affects only the chords after it.


Directive Summary
=================

.. list-table::
   :header-rows: 1
   :widths: 20 40 40

   * - Directive
     - Purpose
     - Examples
   * - ``{bpm}``
     - Set tempo
     - ``{bpm: 120}``, ``{bpm: +20}``, ``{bpm: reset}``
   * - ``{tempo}``
     - Same as bpm
     - ``{tempo: 100}``
   * - ``{time}``
     - Set time signature
     - ``{time: 4/4}``, ``{time: 3/4}``
   * - ``{key}``
     - Set musical key
     - ``{key: C}``, ``{key: Am}``, ``{key: F#}``
   * - ``{label}``
     - Mark a position
     - ``{label: verse}``, ``{label: chorus}``
   * - ``{loop}``
     - Repeat a section
     - ``{loop: verse}``, ``{loop: chorus 3}``
