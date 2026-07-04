==================
Ensemble Voicings
==================

Besides the piano and guitar voicings, Chord Notepad can voice a song for a
fixed group of singers or string players: a four-part choir, a string
quartet, and so on. Instead of one instrument playing a chord, each member
of the ensemble sings or plays exactly one note, and the voicing engine
decides who sings what, the way a vocal arranger or a string coach would.

Reach for an ensemble voicing when you're arranging for real singers or
players rather than sketching a song at a keyboard -- writing SATB harmony
for a choir, checking how a progression sounds as close four-part harmony,
or scoring a chord chart for a string quartet. Reach for piano or guitar
when you just want to hear the chords played back on the instrument you'd
actually play them on.

Piano, guitar, and ensembles are all *voicings*: a voicing is a named
configuration for one of Chord Notepad's three rendering *models* --
piano, the *fretboard* model (guitar and other fretted instruments, see
:doc:`fretted`), or the *ensemble* model covered on this page.


The Four Presets
=================

Chord Notepad ships with four built-in ensembles, each a fixed set of
voices with its own comfortable range. Voices are listed top to bottom
(highest to lowest); "max gap below" is the largest interval the engine
will ever put between that voice and the one under it -- ensembles are
usually allowed to spread wider at the bottom of the texture than at the
top, since a big gap between bass and tenor is normal but the same gap
between soprano and alto sounds hollow.

Choir (SATB)
------------

The traditional four-part mixed choir.

.. list-table::
   :header-rows: 1
   :widths: 25 30 20

   * - Voice
     - Range
     - Max gap below
   * - Soprano
     - C4 - G5
     - 12 semitones
   * - Alto
     - F3 - D5
     - 12 semitones
   * - Tenor
     - C3 - G4
     - 19 semitones
   * - Bass
     - E2 - C4
     - --

Male Choir (TTBB)
-----------------

A four-part male choir: two tenor lines above a baritone and bass.

.. list-table::
   :header-rows: 1
   :widths: 25 30 20

   * - Voice
     - Range
     - Max gap below
   * - Tenor 1
     - C3 - A4
     - 12 semitones
   * - Tenor 2
     - A2 - F4
     - 12 semitones
   * - Baritone
     - F2 - D4
     - 12 semitones
   * - Bass
     - E2 - C4
     - --

Treble Choir (SSA)
------------------

A three-part treble choir: two soprano lines over an alto.

.. list-table::
   :header-rows: 1
   :widths: 25 30 20

   * - Voice
     - Range
     - Max gap below
   * - Soprano 1
     - C4 - A5
     - 12 semitones
   * - Soprano 2
     - A3 - F5
     - 12 semitones
   * - Alto
     - F3 - D5
     - --

String Quartet
---------------

Two violins, viola, and cello, each ranged to its actual instrument.

.. list-table::
   :header-rows: 1
   :widths: 25 30 20

   * - Voice
     - Range
     - Max gap below
   * - Violin I
     - G3 - E6
     - 14 semitones
   * - Violin II
     - G3 - C6
     - 14 semitones
   * - Viola
     - C3 - E5
     - 24 semitones
   * - Cello
     - C2 - E4
     - --

All four presets allow adjacent voices to land on the same pitch (a
unison), since that's an ordinary, occasional occurrence in real choral and
string writing rather than something to avoid outright.


How Voicing Decisions Are Made
================================

Each voice tries to keep the note it's already singing (a common tone),
and moves by the smallest useful step when it has to move at all. Two
voices are never allowed to slide in parallel fifths or parallel octaves --
that one motion is the fastest way to make four-part harmony sound wrong.
When a ``{key:}`` is set, the leading tone resolves up to the tonic instead
of wandering off somewhere else. If a chord has more notes than there are
voices, the least characteristic tone is dropped first -- the fifth goes
before the third or seventh, and a suspended fourth is always kept, since
losing it would erase the whole point of the ``sus`` chord. If a chord has
fewer notes than voices, something gets doubled, and the engine reaches for
the root first. A slash chord's bass note always lands in the bottom
voice. And when a chord simply won't fit the ensemble as written -- an
awkward key, a tight cluster of notes and not enough room to spread them --
the engine doesn't give up; it relaxes its rules one step at a time
(a wider gap here, a parallel it would normally avoid there) until it
finds something an ensemble could actually sing or play.


How to Change Voicing
=======================

1. Open the **Playback** menu.
2. Click **Voicing**.
3. Select **Choir (SATB)**, **Male Choir (TTBB)**, **Treble Choir (SSA)**,
   **String Quartet**, or any custom ensemble you've defined (see below).
4. Play your chords to hear the difference.

A checkmark shows the current voicing, the same as for :doc:`playback`.

A suitable instrument sound makes ensemble voicings much more convincing --
try **Choir Aahs** or **Voice Oohs** for the choir presets, or **String
Ensemble** for the quartet. Change it under
:menuselection:`Playback --> Instrument`; see :ref:`changing-instruments`.


Custom Ensembles
==================

If the four presets don't match the group you're writing for, define your
own from :menuselection:`Tools --> Settings...` --> Voicings: load a
built-in ensemble as a starting point, change the voices, spacing, or
weights, and save. See :doc:`settings` for the page itself and a worked
example (built there for a fretted instrument, but the same steps apply
to an ensemble).

Power users can also edit the configuration file directly -- the same
schema the Settings window reads and writes. Chord Notepad keeps every
non-built-in voicing -- ensemble or fretted instrument alike -- in a
single ``voicings`` object in its configuration file; the same registry
holds custom guitar tunings and other fretted instruments (see
:doc:`fretted`). The file lives at ``~/.config/chord-notepad/settings.json``
on Linux, or the equivalent per-user application-data folder on Windows
and macOS.

Add a ``voicings`` object at the top level, keyed by a short slug you'll
use internally; each entry needs a ``"model": "ensemble"`` and describes
one ensemble:

.. code-block:: json

   {
     "voicings": {
       "jazz_trio": {
         "model": "ensemble",
         "label": "Jazz Vocal Trio",
         "voices": [
           {"name": "Lead", "range": ["A3", "F5"]},
           {"name": "Harmony", "range": ["F3", "D5"]},
           {"name": "Bass", "range": ["E2", "C4"]}
         ],
         "max_spacing": [12, 19],
         "allow_unisons": false,
         "weights": {
           "movement": -0.6,
           "common_tone_bonus": 2.5,
           "parallel_perfect_penalty": -15.0
         }
       }
     }
   }

* ``model`` is required and must be ``"ensemble"`` for a voicing defined
  this way (a fretted instrument uses ``"model": "fretboard"`` instead --
  see :doc:`fretted`).
* ``label`` is what shows up in the Voicing menu (defaults to the slug if
  omitted).
* ``voices`` is required: 2 to 8 entries, listed top voice first, each with
  a ``name`` and a ``range`` of ``[low, high]``. Give the range as note
  names (``"C4"``, ``"F#3"``) or raw MIDI numbers; middle C is ``C4``.
* ``max_spacing`` is optional: the maximum semitone gap allowed between
  each pair of neighbouring voices, one entry per gap (so one fewer entry
  than there are voices). Leave it out and Chord Notepad defaults every
  gap to an octave, except the bottom gap, which gets an octave and a
  fifth to leave the bass room to move.
* ``allow_unisons`` is optional (default ``true``): set it to ``false`` if
  you never want two neighbouring voices landing on the same pitch.
* ``weights`` is optional and partial -- give only the settings you want to
  change, and everything else keeps its default. See the parameter
  reference below for the full list of keys.

Custom ensembles appear in :menuselection:`Playback --> Voicing` automatically
the next time Chord Notepad starts, sorted alongside every other voicing --
built-in or custom, ensemble or fretted -- by model and then name.

.. note::
   Upgrading from an older version? Chord Notepad moves any entries it
   finds under the old ``custom_tunings`` or ``custom_ensembles`` keys into
   ``voicings`` automatically the first time it starts, including
   whichever voicing you had selected. There's nothing to do by hand.


Voicing Parameters
====================

Every ensemble, built-in or custom, is steered by the same set of
numeric parameters. These are the controls the Voicings page of
:menuselection:`Tools --> Settings...` exposes, one control per row --
see :doc:`settings` for the page itself; they can also be set directly in
the ``weights`` object for an ensemble in ``settings.json``. Every weight
is a signed number added to the voicing's score. Positive values make that
trait more likely, negative values less likely, and higher is always more
preferred. A trait you want the engine to seek gets a positive weight; one
you want it to avoid gets a negative one; zero is neutral.

.. list-table::
   :header-rows: 1
   :widths: 28 40 20 12

   * - Control
     - What it does
     - Config key
     - Default
   * - Voice movement
     - Added per semitone an inner or upper voice moves from one chord to
       the next. It's negative, so a more negative value makes those voices
       sit stiller; nearer zero lets them roam more freely.
     - ``movement``
     - -0.4
   * - Bass movement
     - The same, but for the bottom voice specifically. Basses conventionally
       leap more than inner voices, so this sits nearer zero than
       "Voice movement".
     - ``bass_movement``
     - -0.15
   * - Large leap
     - Subtracted when a single voice jumps more than a fifth between
       chords, on top of the per-semitone movement weight.
     - ``leap_penalty``
     - -2.0
   * - Octave leap
     - Subtracted when a voice jumps a full octave or more.
     - ``octave_leap_penalty``
     - -6.0
   * - Tritone leap
     - Subtracted when a voice leaps exactly a tritone (six semitones), an
       interval singers and string players find hard to place accurately.
     - ``tritone_leap_penalty``
     - -3.0
   * - Common tone held
     - Added when a voice holds the same pitch class it just sang. More
       positive keeps more notes "tied over" between chords.
     - ``common_tone_bonus``
     - +1.5
   * - Parallel fifths/octaves
     - Subtracted per pair of voices that move in parallel perfect fifths
       or octaves -- the classic part-writing fault. Set strongly negative
       by default because it's rarely wanted.
     - ``parallel_perfect_penalty``
     - -25.0
   * - Contrary motion
     - Added when the outer two voices (typically soprano and bass) move
       in opposite directions.
     - ``contrary_motion_bonus``
     - +0.8
   * - Seventh resolves down
     - Added when a chordal seventh resolves downward by step into the
       next chord, the way a seventh conventionally wants to fall.
     - ``seventh_resolution_bonus``
     - +1.5
   * - Leading tone resolves
     - Added when the leading tone (the raised 7th degree of the current
       key) resolves upward by step into the tonic.
     - ``leading_tone_resolution_bonus``
     - +1.5
   * - Doubled leading tone
     - Subtracted if two voices end up doubling the leading tone, which
       traditionally produces awkward parallel octaves at the resolution.
     - ``double_leading_tone_penalty``
     - -8.0
   * - Doubling (by tone role)
     - Added to the score for which chord tone gets doubled when there are
       more voices than notes in the chord. Positive favors doubling that
       tone, negative avoids it. Keys: ``root`` (+2.0), ``fifth``
       (+0.5), ``third`` (-2.0), ``seventh`` (-6.0), ``color`` (-6.0),
       ``extension`` (-6.0).
     - ``doubling.root`` / ``.fifth`` / ``.third`` / ``.seventh`` /
       ``.color`` / ``.extension``
     - see left
   * - Omission (by tone role)
     - Added to the score for dropping a chord tone entirely when there are
       fewer voices than notes. The values are negative, so a more negative
       one keeps that tone more insistently. Keys: ``root`` (-4.0),
       ``third`` (-40.0), ``fifth`` (-8.0), ``seventh`` (-40.0), ``color``
       (-30.0), ``extension`` (-7.0).
     - ``omit.root`` / ``.third`` / ``.fifth`` / ``.seventh`` /
       ``.color`` / ``.extension``
     - see left
   * - Inversion (by bass tone)
     - Added to the score for the bass note's chosen inversion. Keys:
       ``root`` (0.0), ``first`` (-1.5), ``second`` (-5.0), ``third``
       (-3.0); nearer zero favors that inversion, more negative avoids it.
     - ``inversion.root`` / ``.first`` / ``.second`` / ``.third``
     - see left
   * - Out-of-comfort range
     - Subtracted per semitone a voice sits within the outermost 2 semitones
       of its configured range. More negative keeps voices away from the
       very top or bottom of what they can sing.
     - ``range_comfort_penalty``
     - -0.5
   * - Unison between voices
     - Subtracted per pair of neighbouring voices landing on the same pitch.
       Only relevant when ``allow_unisons`` is ``true``.
     - ``unison_penalty``
     - -0.5
   * - Wide upper spacing
     - Subtracted per semitone that a gap between two upper voices exceeds
       an octave. Separate from ``max_spacing``, which is a hard limit; this
       is a soft nudge toward closer spacing above the bass.
     - ``upper_spacing_penalty``
     - -0.15

.. note::
   These weights apply per ensemble. A custom ensemble that omits
   ``weights`` entirely uses the defaults above; one that sets ``weights``
   only needs to list the keys it wants to change; anything else falls
   back to the same defaults.
