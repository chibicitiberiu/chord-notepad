========
Playback
========

This section covers audio playback features.


Playing Your Song
=================

Starting Playback
-----------------

.. only:: desktop

   Click the **Play** button (▶) in the toolbar. By default playback starts from
   the first chord in your document and runs to the end. The button turns into a
   **Pause** button (⏸) while a song is playing.

.. only:: android

   Playback lives in the **Play** tab. A song you open starts there; a new song
   starts in Edit, so tap **Play** in the app bar once you have some chords.
   The player sits at the bottom of the screen:

.. platform-figure:: player-labeled
   :platforms: android
   :alt: The player while a song plays: the song pill on top, seven buttons in
         a row, and the status line underneath.

   The player while a song plays, with the metronome on and the speed at 125%.

.. only:: android

   1. **Song pill**: the tempo, time signature and key the song starts with.
      Tap it for Song defaults (see :ref:`song-defaults`).
   2. **Voicing**: how each chord is spread into notes. Greyed out while a
      song plays.
   3. **Instrument**: the sound.
   4. **⏮**: stop and go back to the first chord.
   5. **▶ / ⏸**: play and pause.
   6. **Metronome**: a click on every beat.
   7. **Speed**: play slower or faster than written. The badge shows the
      speed when it isn't 100%.
   8. **Chord sheet**: show or hide it (see :doc:`chord_sheet`).
   9. **Status line**: the bar you're in and what's happening.

.. only:: android

   Tap the big **▶** button. Playback starts at the **playhead**, the small
   marker (a coloured bar with a triangle) before the chord where playback
   begins. A song you just opened has it on the first chord.

   Chord Notepad works out the whole song before the first note sounds, so a
   ring spins around the button for a moment (longer for a long song on a slow
   phone). Taps on the button are ignored until the music starts. Then the
   button turns into **⏸**.

:plat:`Playing from the Cursor|Playing from the Playhead`
---------------------------------------------------------

Want to start from a specific point?

.. only:: desktop

   1. Click in the text where you want to start
   2. **Shift+Click** the Play button
   3. Playback begins from that position

.. only:: android

   1. In the Play tab, tap the chord you want to start from. The playhead moves
      there and the chord plays once.
   2. Tap **▶**.
   3. Playback begins from the playhead.

   There are two other ways to move the playhead, both silent:

   * Tap anywhere that isn't a chord. The playhead goes to the nearest chord,
     preferring one on the line you tapped.
   * Put your finger on the marker and drag it. It steps through the song
     chord by chord. This works while nothing plays; during playback the
     marker follows the music.

.. platform-figure:: playhead
   :platforms: android
   :alt: Song text in the Play tab with the playhead marker, a bar with a
         small triangle on top, just before the Em chord.

   The playhead before **Em**. Playback starts here.

This lets you start from a specific section without playing the entire document.

Pausing and Resuming
--------------------

.. only:: desktop

   * Click the **Pause button** (⏸) to pause playback
   * Click the **Play button** (▶) to resume from where you stopped
   * The currently playing chord stays highlighted

.. only:: android

   * Tap **⏸** to pause playback. The playhead stays on the chord that was
     sounding.
   * Tap **▶** to resume from there.
   * The chord that was playing stays highlighted.

   Moving the playhead while paused (a tap, or a drag of the marker) drops the
   paused song, so the next **▶** starts from the new position.

Stopping Playback
-----------------

.. only:: desktop

   * Click the **Stop button** (⏹) to stop completely
   * The highlight clears and playback resets

.. only:: android

   There is no Stop button. Pause (**⏸**) when you want to carry on from the
   same place later, and use **⏮** to start over:

   * **⏮** stops playback and sends the playhead back to the first chord. The
     highlight clears.
   * When a song reaches its end, the playhead returns to the first chord by
     itself.
   * Switching to the **Edit** tab also stops playback, paused or not. The
     playhead stays where it was.

During Playback
---------------

While playing:

.. only:: desktop

   * The text editor becomes **read-only** (you can't edit while playing).
     Tools that change the text (Transpose, Suggest Capo, the notation
     conversions, the Insert menu and the chord identifier's Insert) leave it
     unchanged until you stop.
   * The **current chord** is highlighted in yellow
   * The **status bar** shows: bar number, BPM, time signature, key, and chord name
   * The editor **auto-scrolls** to keep the playing chord visible

.. only:: android

   * The text is frozen: the Play tab never opens the keyboard. To change
     something, switch to the **Edit** tab, which stops playback.
   * The **current chord** is highlighted in yellow (dark yellow in the dark
     theme).
   * The player's status line shows the bar and the chord, for example
     "Bar 6/24 · Playing Em", or "Bar 6/24 · Paused". Bars are counted from
     the top of the song, even when you started further down.
   * The text **auto-scrolls** to keep the playing chord visible.
   * The screen stays on while a song plays, so it doesn't dim halfway through
     a verse. Once you pause or stop, the screen goes back to its usual
     timeout.
   * You can change the instrument, the speed and the metronome while the song
     plays. The voicing and the tempo wait until you pause or stop (see
     `Voicing Options`_ and :ref:`song-defaults`).

   Chord Notepad doesn't play in the background. Playback pauses, and stays
   paused until you tap **▶**, when:

   * the app leaves the screen (you switch apps, go to the home screen or turn
     the screen off);
   * a call comes in, or another app starts playing audio;
   * headphones are unplugged or a Bluetooth headset disconnects, so the song
     doesn't suddenly play out loud through the speaker.

   A short sound from another app, such as a navigation prompt, doesn't pause
   it: Android lowers the volume for a moment instead.

.. only:: android

   .. rubric:: Metronome

   The **metronome** button adds a click on every beat. You can turn it on or
   off during playback too, and it takes effect at once. The button gets a tinted background while the metronome is on. The
   click is only for practice: it is never written into an exported MIDI file.

   .. rubric:: Playback Speed

   The **speed** button plays the song slower or faster than written, without
   changing the song. It scales every tempo in the song, including each
   ``{bpm}`` change, so a slow verse and a fast chorus stay in proportion.
   Tap the button to open the speed sheet:

.. platform-figure:: speed-sheet
   :platforms: android
   :alt: The Playback speed sheet at 125%, with a slider from 25% to 400% and
         the Reset, Manual and Done buttons.

   The speed sheet.

.. only:: android

   * Drag the slider (25% to 400%, in steps of 5%). The new speed applies
     right away, also while a song plays.
   * **Reset** goes back to 100%.
   * **Manual…** lets you type an exact value from 25 to 400.
   * **Done** closes the sheet.

   When the speed isn't 100%, the button shows it as a badge (``1.25×``) and
   gets a tinted background, so you can see at a glance that you're not
   hearing the written tempo. The speed only affects what you hear: MIDI
   export always uses the song's real tempo (see :doc:`midi_export`).


|Click|-to-Play
===============

You can play individual chords without starting full playback.

|Clicking| Individual Chords
----------------------------

.. only:: desktop

   1. Move your mouse over any valid chord (the cursor changes to a hand pointer)
   2. Click the chord
   3. The chord plays

.. only:: android

   1. Switch to the **Play** tab.
   2. Find any valid chord (blue and underlined).
   3. Tap the chord.
   4. The playhead moves to it and the chord plays.

   In the Edit tab a tap on a chord only places the cursor and stays silent.
   If a song is paused, tapping a chord drops the paused song and plays the
   chord, and the next **▶** starts from it.

   The chord sheet has its own version: tap a chord in the sheet to hear that
   exact voicing once, without moving the playhead (see :doc:`chord_sheet`).

This works even when playback is stopped. Uses include:

* Testing how a chord sounds
* Comparing different chord options
* Chord ear training

|Clicking| During Playback
--------------------------

.. only:: desktop

   Clicking a chord while the song is playing will:

.. only:: android

   Tapping a chord while the song is playing:

.. only:: desktop

   * Play that chord immediately
   * Not interrupt the ongoing playback

.. only:: android

   * Jumps playback to that chord, which keeps playing from there. The
     playhead moves with it.


Voicing Options
===============

A chord, as raw data, is just a set of notes: C major is C, E, and G. But nobody
plays three bare notes floating in space. A pianist spreads them across two hands
with a low root and a couple of notes doubled on top; a guitarist holds a
particular six-string shape with some open strings ringing. *Voicing* is that
second step, turning the set of notes into something that sounds like a person
played it. Chord Notepad does it several different ways, because a keyboard,
a fretboard, and a section of singers or players don't think alike.

.. only:: desktop

   Switch between them under :menuselection:`Playback --> Voicing`: pick **Piano**,
   one of the fretted-instrument voicings (guitar in various tunings, **Ukulele**,
   or an instrument you've configured yourself) covered in :doc:`fretted`, or one
   of the ensemble presets (a four-part choir, a string quartet) covered in
   :doc:`ensembles`. Voicing is independent of the **instrument** you choose (see
   :ref:`changing-instruments`) -- you can play a piano voicing through a
   saxophone, or a guitar voicing through a synth pad.

.. only:: android

   Switch between them with the **Voicing** button (the note icon on the left
   of the player). The sheet groups the voicings as **Piano**, **Fretted**,
   **Ensembles** and **Your voicings**:

   * **Piano**: the two-hand piano voicing described below.
   * **Fretted**: guitar in four tunings and **Ukulele** (see :doc:`fretted`).
   * **Ensembles**: the choir and string quartet presets (see
     :doc:`ensembles`).
   * **Your voicings**: the ones you made in ☰ → Settings → Voicings. The
     group is missing until you add one.

   **Edit voicings…** at the bottom of the sheet opens Settings › Voicings.

.. platform-figure:: voicing-sheet
   :platforms: android
   :alt: The Voicing sheet with radio buttons grouped under Piano, Fretted,
         Ensembles and Your voicings, and Edit voicings and Done at the bottom.

   The Voicing sheet. Piano is selected; My 7-String is a custom voicing.

.. only:: android

   Voicing is independent of the **instrument** you choose (see
   :ref:`changing-instruments`): you can play a piano voicing through a
   saxophone, or a guitar voicing through a synth pad.

The voicing can't change while a song is playing, because the whole song is
worked out before the first note (the Voicing control is greyed out until you
pause). Pause, pick another voicing, and press Play: the song starts again from
the chord where you paused, with the new voicing. The instrument can change at
any time, including during playback.

.. only:: android

   Touch and hold the greyed-out Voicing button to see why it is disabled
   ("Pause to change the voicing").

Piano Voicing
-------------

The piano voicing models a pianist's **two hands**. The left hand plays the bass
(the chord's root, or the slash bass for a chord like ``C/G``) down in the
low register; the right hand plays the chord itself around middle C. Each hand
reaches only so far -- at most five notes spanning no more than a ninth -- so the
voicer never asks for a shape a real hand could not hold.

For the right hand it lays out several ways to play the chord: root position and
every **inversion**, at a couple of octaves, and -- for tall chords that won't
fit one hand -- with an inner note or two dropped (the fifth first, then the
doubled root). Ninths, elevenths and thirteenths always sit above the core
triad, so an eleventh sounds like an eleventh rather than collapsing into a
clashing second next to the root. Every candidate is scored on how complete and
how centered it is, then on **voice leading** -- how little the notes have to
move from the previous chord, holding shared notes in place instead of leaping.

Rather than deciding each chord in isolation, the voicer optimizes the **whole
song at once**. That keeps the right hand anchored in a stable central register
from start to finish: a chord that comes back on a looped verse is voiced the
same way it was the first time, instead of drifting an octave lower each pass.

.. platform-figure:: voiceleading
   :shared:
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

Guitar is voiced by Chord Notepad's *fretboard model*, the same engine that
handles any other fretted instrument -- ukulele, or one you configure
yourself; see :doc:`fretted` for the full story and how to add your own.

The guitar side has a harder problem: on a guitar, not every set of notes is
even physically playable. Fingers only reach so far, and there are only so many
of them. So instead of arranging notes freely, the guitar picker hunts for a
*fingering* -- a specific fret on each string that a hand can actually hold.

It builds every candidate from scratch, one string at a time, from a map of
which note sits at each fret -- no memorized chord shapes involved. Each string
may be muted or fretted anywhere its note belongs to the chord (plus the one
slash-bass note, if any). Every candidate then has to clear two bars:

* **It must spell the chord** -- cover all the notes, and add nothing that isn't
  in the chord (the one slash-bass note excepted).
* **It must be reachable** -- no more than a four-fret stretch, and no more
  fretted fingers than a hand has, unless it can use a barre.

Whatever survives is scored on two things: how good the fingering is on its own
-- full, low, open-sounding, with the right note in the bass, and no wide
stretches, barres, or silent strings buried in the middle of a strum -- and how
smoothly it flows to and from its neighbours, keeping the fretting hand close to
the surrounding shapes.

Rather than deciding chord by chord, the guitar picker plans the **whole song at
once**. It looks at every chord's fingering options together and chooses the
combination that reads best overall, weighing each shape's own quality against
the smoothness of every transition. That lookahead lets it accept a slightly
plainer shape for one chord when doing so keeps the next few flowing, instead of
grabbing the locally prettiest fingering and then lurching up the neck to reach
whatever comes next. Because the plan is made for the song as a whole, a
repeated section (say a looped verse) is voiced in the context it actually plays
in each time through.

When a chord is too dense to hold on six strings, the picker relaxes rather than
give up: it allows a partial voicing (drop a note or two from the fuller
extended chords), and as a last resort plays just the root so you still hear
something on the beat.

Built-in Fretted-Instrument Voicings
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 35 40

   * - Voicing
     - Strings (in string order)
     - Best For
   * - Guitar (Standard)
     - E A D G B E
     - Most music, default choice
   * - Guitar (Drop D)
     - D A D G B E
     - Heavy rock, metal, alternate bass
   * - Guitar (DADGAD)
     - D A D G A D
     - Celtic, folk, fingerstyle
   * - Guitar (Open G)
     - D G D G B D
     - Blues, slide guitar, Keith Richards
   * - Ukulele
     - G C E A (re-entrant)
     - Uke songs, standard "my dog has fleas" tuning

.. only:: desktop

   Beyond these five, you can define a voicing for any fretted instrument with
   3 to 12 strings -- a baritone ukulele, a banjo, a seven-string guitar in a
   tuning of your own -- by adding it to the config file. See :doc:`fretted`
   for a worked example and the full list of tunable parameters.

.. only:: android

   Beyond these five, you can define a voicing for any fretted instrument with
   3 to 12 strings -- a baritone ukulele, a banjo, a seven-string guitar in a
   tuning of your own -- in ☰ → Settings → Voicings. See
   :doc:`fretted` for a worked example and the full list of tunable parameters.

.. platform-figure:: voicings
   :shared:
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

.. platform-figure:: jazz-clash
   :shared:
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

.. only:: desktop

   1. Open the **Playback** menu.
   2. Click **Voicing**.
   3. Select **Piano**, one of the fretted-instrument voicings (guitar
      tunings, **Ukulele**, or a custom instrument), or one of the ensemble
      presets -- see :doc:`fretted` for how each fretted voicing plays and how
      to define your own, and :doc:`ensembles` for the same on ensembles.
   4. Play your chords to hear the difference.

.. only:: android

   1. In the Play tab, pause or stop the song if it is playing.
   2. Tap **Voicing** in the player.
   3. Select **Piano**, one of the fretted-instrument voicings (guitar
      tunings, **Ukulele**, or a custom instrument), or one of the ensemble
      presets. See :doc:`fretted` for how each fretted voicing plays and how
      to define your own, and :doc:`ensembles` for the same on ensembles.
      The choice applies at once; the sheet stays open so you can try
      another.
   4. Tap **Done**, then play your chords to hear the difference.

.. only:: desktop

   A checkmark shows the current voicing. It applies to full playback and to
   single chords you click.

.. only:: android

   A filled radio button marks the current voicing. It applies to full
   playback, to single chords you tap, to the chord sheet and to MIDI export.


.. _changing-instruments:

Changing Instruments
====================

Chord Notepad uses FluidSynth for instrument synthesis. The General MIDI
standard provides 128 instruments.

How to Change Instruments
-------------------------

.. only:: desktop

   1. Go to **Playback** menu
   2. Click **Instrument**
   3. Browse through the categories
   4. Click an instrument to select it

.. only:: android

   1. In the Play tab, tap **Instrument** in the player (the guitar icon).
   2. Pick one of the 16 General MIDI families. A filled dot marks the family
      in use, with the current instrument's name on the right.
   3. Tap an instrument to select it. Each family has eight, listed with their
      General MIDI program numbers (0 to 127). The new sound applies at once,
      even in the middle of a song.
   4. **←** goes back to the families; **Done** closes the sheet.

.. platform-figure:: instrument-families
   :platforms: android
   :alt: The Instrument sheet listing the 16 General MIDI families, with Piano
         marked and Grand Piano shown on its right.

   The first level: the families. Piano is in use, playing Grand Piano.

.. platform-figure:: instrument-programs
   :platforms: android
   :alt: The Guitar family's eight instruments with their program numbers 24
         to 31; Steel Guitar is selected.

   The second level: the Guitar family, with Steel Guitar selected.

.. only:: desktop

   A checkmark (✓) shows the currently selected instrument.

.. only:: android

   A filled radio button shows the currently selected instrument.

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


.. _song-defaults:

:plat:`The Status Bar|The Status Line and Song Defaults`
========================================================

.. only:: desktop

   During playback, the status bar at the bottom shows useful information:

   * **Bar number** - Which measure you're in (e.g., "Bar 3/8")
   * **BPM** - Current tempo
   * **Time signature** - Current time signature
   * **Key** - Current key
   * **Playing chord** - Name of the chord currently sounding

   Watch the status bar to keep track of where you are in longer songs.

.. only:: android

   Under the player's buttons a status line shows where you are, for example
   "Bar 6/24 · Playing Em" or "Bar 6/24 · Paused". While nothing plays it
   shows the bar the playhead is in. Messages such as "Exported MIDI: …" show
   there too while you're in the Play tab; in the Edit tab they pop up at the
   bottom of the screen instead.

   Above the buttons, the **song pill** (something like "𝄞 90 · 3/4 · G")
   shows the tempo, time signature and key the song starts with. Tap it to
   open **Song defaults**:

.. platform-figure:: song-defaults
   :platforms: android
   :alt: The Song defaults sheet: Tempo 90 bpm set by a bpm directive in the
         song, with an Edit link; Time signature 3/4 and Key G as drop-down
         defaults; Write into song and Done at the bottom.

   This song sets its tempo with ``{bpm: 90}``. The time signature and the
   key are defaults you can change here.

.. only:: android

   * A value the song sets with a directive is read-only and reads "Set by
     ``{bpm: 90}`` in the song · Edit". **Edit** switches to the Edit tab with
     the cursor on that directive, so you can change it there.
   * A value the song doesn't set is a default you can change: tap it to type
     a tempo (20 to 400), or to pick a time signature or a key from a list.
     A default applies only where the song has no directive, and it is not
     saved with the file. New songs start from the defaults in ☰ → Settings
     → Playback and General.
   * **Write into song** inserts the missing directives at the top of the
     song as one line, so the file keeps them. It is greyed out when the
     song already sets all three.

   The tempo and **Write into song** don't work while a song plays or is
   paused: tap **⏮** first. A time signature or key you change during
   playback is heard once you stop and play again. To play faster or slower
   without touching the song, use the **speed** button instead.


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

.. only:: android

   To practise a finished song without editing it, use the **speed** button
   instead: start at 50% and step it up as the song gets comfortable.

A/B Testing Chords
------------------

.. only:: desktop

   Write two versions and click between them:

.. only:: android

   Write two versions and, in the Play tab, tap between them:

.. code-block:: chord

   // Option A
   C  Am  F  G

   // Option B
   C  Am  Dm  G

.. only:: desktop

   Click each chord to compare the sounds.

.. only:: android

   Tap each chord to compare the sounds.

Checking Voice Leading
----------------------

Play a progression slowly to hear how voices move:

.. code-block:: chord

   {bpm: 40}
   Cmaj7  Am7  Dm7  G7

Slow tempos make voice leading transitions more audible.

.. only:: android

   With the chord sheet's **Staff** view open (see :doc:`chord_sheet`) you can
   also watch each voice move while you listen.
