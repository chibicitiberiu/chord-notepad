========
Playback
========

This section covers audio playback features.


Playing Your Song
=================

Starting Playback
-----------------

There are several ways to start playing:

* Click the **Play button** (▶) in the toolbar
* The button changes to a **Pause button** (⏸) while playing

Playing from the Beginning
--------------------------

By default, clicking Play starts from the first chord in your document.

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

"Voicing" means how the notes of a chord are arranged and played. Chord Notepad
offers two main voicing styles.

Piano Voicing
-------------

The default voicing arranges chords in keyboard style:

* Voice leading between chords (common tones stay in place)
* Notes stay in the middle range
* Bass note added an octave below

Piano voicing works well for most styles.

Guitar Voicing
--------------

Guitar voicing uses fingerings based on a 6-string guitar:

* Generates chord shapes for the selected tuning
* Considers fret positions and finger stretches
* Produces a different sound character than piano voicing

To switch to guitar voicing:

1. Go to **Playback** → **Voicing**
2. Select a guitar tuning

Available Guitar Tunings
~~~~~~~~~~~~~~~~~~~~~~~~

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

How to Change Voicing
---------------------

1. Go to **Playback** menu
2. Click **Voicing**
3. Select **Piano** or one of the guitar tunings
4. Play your chords to hear the difference

Voice Leading Explained
-----------------------

Voice leading refers to how individual notes move from one chord to the next.
Chord Notepad applies voice leading automatically.

**Without voice leading:**
Each chord might have notes in arbitrary octaves, causing large jumps.

**With voice leading:**
Notes that are common between chords stay in place. Other notes move by the
smallest interval possible.

Voice leading is applied automatically for both piano and guitar voicing.


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
