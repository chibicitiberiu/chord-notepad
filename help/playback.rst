========
Playback
========

This section covers audio playback features.


Playing Your Song
=================

Starting Playback
-----------------

Click the **Play** button (▶) in the toolbar. By default playback starts from
the first chord in your document and runs to the end. The button turns into a
**Pause** button (⏸) while a song is playing.

Playing from the Cursor
-----------------------

Want to start from a specific point?

1. Click in the text where you want to start
2. **Shift+Click** the Play button
3. Playback begins from that position

This lets you start from a specific section without playing the entire document.

Pausing and Resuming
--------------------

* Click the **Pause button** (⏸) to pause playback
* Click the **Play button** (▶) to resume from where you stopped
* The currently playing chord stays highlighted

Stopping Playback
-----------------

* Click the **Stop button** (⏹) to stop completely
* The highlight clears and playback resets

During Playback
---------------

While playing:

* The text editor becomes **read-only** (you can't edit while playing)
* The **current chord** is highlighted in yellow
* The **status bar** shows: bar number, BPM, time signature, key, and chord name
* The editor **auto-scrolls** to keep the playing chord visible


Click-to-Play
=============

You can play individual chords without starting full playback.

Clicking Individual Chords
--------------------------

1. Move your mouse over any valid chord (the cursor changes to a hand pointer)
2. Click the chord
3. The chord plays

This works even when playback is stopped. Uses include:

* Testing how a chord sounds
* Comparing different chord options
* Chord ear training

Clicking During Playback
------------------------

Clicking a chord while the song is playing will:

* Play that chord immediately
* Not interrupt the ongoing playback


Voicing Options
===============

A chord, as raw data, is just a set of notes: C major is C, E, and G. But nobody
plays three bare notes floating in space. A pianist spreads them across two hands
with a low root and a couple of notes doubled on top; a guitarist holds a
particular six-string shape with some open strings ringing. *Voicing* is that
second step, turning the set of notes into something that sounds like a person
played it. Chord Notepad does it two different ways, because a keyboard and a
fretboard don't think alike.

Switch between them under :menuselection:`Playback --> Voicing`: pick **Piano**,
or one of the guitar tunings. Voicing is independent of the **instrument** you
choose (see :ref:`changing-instruments`) -- you can play a piano voicing through
a saxophone, or a guitar voicing through a synth pad.

Piano Voicing
-------------

The piano voicing is built around **voice leading**: moving as little as possible
from one chord to the next. Going from C to Am, it looks at where the hand just
was and picks the shape of Am nearest to it, holding any shared notes exactly
where they are instead of leaping across the keyboard. It shifts the whole chord
up or down by octaves to stay in a comfortable range, drops a root into the bass,
and scores each candidate by how far the notes had to travel.

.. figure:: /images/voiceleading.png
   :alt: Four piano keyboards for C, Am, F, and G shown twice: with voice
         leading the shapes stay close together; without it every chord snaps
         to root position and the top notes leap around.
   :align: center
   :width: 100%

   The same four chords with and without voice leading. Without it, every chord
   snaps to root position in one octave, so the top notes jump; with it, the
   shapes stay close and the notes barely move.

The effect is easiest to hear slowly. Play ``Cmaj7  Am7  Dm7  G7`` at
``{bpm: 40}`` and listen to how the inner notes hold or slide a half step
instead of jumping.

Guitar Voicing
--------------

The guitar side has a harder problem: on a guitar, not every set of notes is
even physically playable. Fingers only reach so far, and there are only so many
of them. So instead of arranging notes freely, the guitar picker hunts for a
*fingering* -- a specific fret on each string that a hand can actually hold.

It generates candidates two ways. The first is a small library of familiar open
shapes (the cowboy C, G, D, A, and E, plus a barre shape) slid up and down the
neck. The second builds fingerings from scratch, one string at a time,
from a map of which note sits at every fret. Every candidate then has to clear
two bars:

* **It must spell the chord** -- cover all the notes, and add nothing that isn't
  in the chord (the one slash-bass note excepted).
* **It must be reachable** -- no more than a four-fret stretch, and no more
  fretted fingers than a hand has, unless it can use a barre.

Whatever survives is scored, and, just like the piano, the first chord favors
low open positions while every chord after it is scored on how little the
fretting hand has to shift from the shape before. Same voice-leading instinct,
different instrument.

When a chord is too dense to hold on six strings, the picker relaxes rather than
give up: it allows a partial voicing (drop a note or two from the fuller
extended chords), and as a last resort plays just the root so you still hear
something on the beat.

Available Guitar Tunings
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 35 40

   * - Tuning
     - Strings (low to high)
     - Best For
   * - Standard
     - E A D G B E
     - Most music, default choice
   * - Drop D
     - D A D G B E
     - Heavy rock, metal, alternate bass
   * - DADGAD
     - D A D G A D
     - Celtic, folk, fingerstyle
   * - Open G
     - D G D G B D
     - Blues, slide guitar, Keith Richards

.. figure:: /images/voicings.png
   :alt: Piano keyboard and guitar chord-box diagrams for C, G, Am, and F,
         showing the notes each picker chose.
   :align: center
   :width: 100%

   What the two pickers actually chose for C, G, Am, and F: keys pressed on the
   left, guitar fingering on the right.

.. note::
   These are the shapes the *algorithm* settled on, not the ones you'd copy from
   a chord book. It picks whatever is easy to reach and closest to the previous
   shape, which sometimes lands on unusual choices -- a barre where you'd play an
   open chord, or the top strings left silent. They all spell the chord
   correctly; they just aren't always the textbook fingerings.

Smart Voicing for Jazz Chords
-----------------------------

For most chords, arranging the notes is all that's needed. A few extended chords
need one extra decision, because the textbook stack of notes contains a clash no
real player leaves in.

Take a dominant eleventh, ``C11``. Stacked in full it is C, E, G, B♭, D, F. The
E is the major third and the F is the eleventh, and they sit a semitone apart,
which grinds. Pianists drop the third and let the eleventh speak. Chord Notepad
does the same:

.. figure:: /images/jazz-clash.png
   :alt: Two piano keyboards for a dominant eleventh. On the left the major
         third is left in and marked as clashing; on the right it is dropped.
   :align: center
   :width: 90%

   A dominant eleventh with the third left in (what a raw note stack gives you)
   versus dropped (what Chord Notepad plays). The flagged key is the third, a
   semitone below the eleventh.

The same reasoning is applied to a small set of extended chords:

* ``C11`` and ``Cmaj11`` drop the **third**, which clashes with the eleventh.
* ``C13``, ``Cm13``, and ``Cmaj13`` drop the **eleventh**, a practical voicing
  players use.
* Minor elevenths (``Cm11``) keep their flat third, since a minor third against
  the eleventh doesn't clash.

Everything else is voiced straight from the notes the chord names, so this only
affects the handful of tall jazz chords where it matters.

How to Change Voicing
---------------------

1. Open the **Playback** menu.
2. Click **Voicing**.
3. Select **Piano** or one of the guitar tunings.
4. Play your chords to hear the difference.

A checkmark shows the current voicing. It applies to full playback and to
single chords you click.


.. _changing-instruments:

Changing Instruments
====================

Chord Notepad uses FluidSynth for instrument synthesis. The General MIDI
standard provides 128 instruments.

How to Change Instruments
-------------------------

1. Go to **Playback** menu
2. Click **Instrument**
3. Browse through the categories
4. Click an instrument to select it

A checkmark (✓) shows the currently selected instrument.

Instrument Categories
---------------------

Instruments are organized by family:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Category
     - Includes
   * - Piano
     - Acoustic Grand, Bright Acoustic, Electric Grand, Honky-tonk, etc.
   * - Chromatic Percussion
     - Celesta, Glockenspiel, Music Box, Vibraphone, Marimba, Xylophone
   * - Organ
     - Drawbar Organ, Percussive Organ, Rock Organ, Church Organ, etc.
   * - Guitar
     - Acoustic Nylon, Acoustic Steel, Jazz Guitar, Clean Electric, etc.
   * - Bass
     - Acoustic Bass, Electric Bass (finger/pick), Fretless, Slap Bass
   * - Strings
     - Violin, Viola, Cello, Contrabass, Tremolo/Pizzicato Strings
   * - Ensemble
     - String Ensemble, Synth Strings, Choir Aahs, Voice Oohs
   * - Brass
     - Trumpet, Trombone, Tuba, French Horn, Brass Section
   * - Reed
     - Soprano/Alto/Tenor/Baritone Sax, Oboe, Clarinet, Bassoon
   * - Pipe
     - Piccolo, Flute, Recorder, Pan Flute, Ocarina
   * - Synth Lead
     - Square, Sawtooth, Calliope, Chiff, Charang
   * - Synth Pad
     - New Age, Warm, Polysynth, Choir, Bowed, Metallic
   * - Synth Effects
     - Rain, Soundtrack, Crystal, Atmosphere, Brightness
   * - Ethnic
     - Sitar, Banjo, Shamisen, Koto, Kalimba, Bagpipe
   * - Percussive
     - Tinkle Bell, Agogo, Steel Drums, Woodblock, Taiko
   * - Sound Effects
     - Guitar Fret Noise, Breath Noise, Seashore, Bird Tweet

Instrument Suggestions
----------------------

* **General use**: Acoustic Grand Piano (the default)
* **Pop/rock**: Electric Piano or Clean Guitar
* **Jazz**: Jazz Guitar or Vibraphone
* **Classical**: String Ensemble or Acoustic Grand
* **Electronic**: Synth leads or pads

Different instruments can highlight different aspects of a chord progression.


The Status Bar
==============

During playback, the status bar at the bottom shows useful information:

* **Bar number** - Which measure you're in (e.g., "Bar 3/8")
* **BPM** - Current tempo
* **Time signature** - Current time signature
* **Key** - Current key
* **Playing chord** - Name of the chord currently sounding

Watch the status bar to keep track of where you are in longer songs.


Playback Tips
=============

Practice Loops
--------------

Use ``{label}`` and ``{loop}`` to repeat difficult sections:

.. code-block:: chord

   {label: tricky_part}
   Am7  D9  Gmaj7  Cmaj7

   {loop: tricky_part 10}    // Repeat 10 times

Tempo Training
--------------

Start slow and gradually increase:

.. code-block:: chord

   {bpm: 60}
   C  Am  F  G
   {bpm: +10}
   C  Am  F  G
   {bpm: +10}
   C  Am  F  G
   // Keep adding {bpm: +10} blocks

A/B Testing Chords
------------------

Write two versions and click between them:

.. code-block:: chord

   // Option A
   C  Am  F  G

   // Option B
   C  Am  Dm  G

Click each chord to compare the sounds.

Checking Voice Leading
----------------------

Play a progression slowly to hear how voices move:

.. code-block:: chord

   {bpm: 40}
   Cmaj7  Am7  Dm7  G7

Slow tempos make voice leading transitions more audible.
