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
normally puts between that voice and the one under it -- ensembles are
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
and moves by the smallest useful step when it has to move at all. Parallel
fifths and octaves between two voices carry a heavy penalty -- that one
motion is the fastest way to make four-part harmony sound wrong -- so the
engine avoids them whenever another voicing is available. When a key is in
effect (``{key:}``), the leading tone earns a bonus for resolving up to the
tonic, and doubling it is avoided.

If a chord has more notes than there are voices, the tone with the
cheapest Omission weight is left out. With the defaults that's the root:
the chord is then sung in inversion, so a G7 for three voices comes out as
B, D, F. Next come a 9th or other extension, then the fifth; the third, the
seventh and a ``sus`` chord's suspended tone are kept. If a chord has fewer
notes than voices, something gets doubled, and the engine reaches for the
root first. Any chord tone may go in the bass, though the Inversion weights
favor root position; a slash chord's bass note always lands in the bottom
voice.

And when a chord simply won't fit the ensemble as written -- an awkward
key, a tight cluster of notes and not enough room to spread them -- the
engine doesn't give up. It first lets each voice go up to two semitones past
its range, then drops the "max gap below" limits, and as a last resort
stacks the chord in close position.


How to Change Voicing
=======================

.. only:: desktop

   1. Open the **Playback** menu.
   2. Click **Voicing**.
   3. Select **Choir (SATB)**, **Male Choir (TTBB)**, **Treble Choir (SSA)**,
      **String Quartet**, or any custom ensemble you've defined (see below).
   4. Play your chords to hear the difference.

.. only:: android

   1. In the Play tab, tap the **Voicing** button (the music note, first in
      the player's row of buttons).
   2. Select **Choir (SATB)**, **Male Choir (TTBB)**, **Treble Choir (SSA)**,
      **String Quartet**, or any custom ensemble you've defined (see below).
   3. Play your chords to hear the difference.

.. only:: desktop

   A checkmark shows the current voicing, the same as for :doc:`playback`.

.. only:: android

   A filled radio button marks the current voicing. While a song plays the
   Voicing button is greyed out: pause first (see :doc:`playback`).

.. only:: desktop

   A suitable instrument sound makes ensemble voicings much more convincing --
   try **52 - Concert Choir** or **53 - Voice Oohs** for the choir presets, or
   **48 - Fast Strings** or **49 - Slow Strings** for the quartet. Change it
   under :menuselection:`Playback --> Instrument` (they're in the Ensemble
   family); see :ref:`changing-instruments`.

.. only:: android

   A suitable instrument sound makes ensemble voicings much more convincing --
   try **52 - Concert Choir** or **53 - Voice Oohs** for the choir presets, or
   **48 - Fast Strings** or **49 - Slow Strings** for the quartet. They're in
   the **Ensemble** family under the **Instrument** button in the Play tab's
   player; see :ref:`changing-instruments`.


Custom Ensembles
==================

.. only:: desktop

   If the four presets don't match the group you're writing for, define your
   own from |voicings_settings|: load a
   built-in ensemble as a starting point, change the voices, spacing, or
   weights, and save. See :doc:`settings` for the page itself and a worked
   example (built there for a fretted instrument, but the same steps apply
   to an ensemble).

.. only:: android

   If the four presets don't match the group you're writing for, define your
   own:

   1. Open |voicings_settings| and tap **Add voicing**. The new
      voicing starts out as a guitar.
   2. Tap **Load config** and pick the built-in ensemble closest to what you
      want, such as **Choir (SATB)**. Or set **Model** to **Ensemble** to
      start from two plain voices.
   3. Tap the **Name** field to name the voicing.
   4. Change the voices, the spacing or the weights (see below).
   5. Tap **Save**.

   See :doc:`fretted` for how errors are shown, and :doc:`settings` for the
   page itself and a worked example (built there for a fretted instrument,
   but the same steps apply to an ensemble).

.. only:: desktop

   Power users can also edit the configuration file directly -- the same
   schema the Settings window reads and writes. Chord Notepad keeps every
   non-built-in voicing -- ensemble or fretted instrument alike -- in a
   single ``voicings`` object in its configuration file; the same registry
   holds custom guitar tunings and other fretted instruments (see
   :doc:`fretted`). The file lives at ``~/.config/chord-notepad/settings.json``
   on Linux, or the equivalent per-user application-data folder on Windows
   and macOS.

.. only:: desktop

   Add a ``voicings`` object at the top level, keyed by the voicing's name;
   each entry needs a ``"model": "ensemble"`` and describes one ensemble:

   .. code-block:: json

      {
        "voicings": {
          "Jazz Vocal Trio": {
            "model": "ensemble",
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
   * The key (``"Jazz Vocal Trio"`` here) is the voicing's name, the one the
     Voicing menu and the Settings window show.
   * ``voices`` is required: 2 to 8 entries, listed top voice first, each with
     a ``name`` and a ``range`` of ``[low, high]``. Give the range as note
     names (``"C4"``, ``"F#3"``) or raw MIDI numbers; middle C is ``C4``. Each
     voice also takes an optional ``staff`` (``"treble"`` or ``"bass"``),
     used by the chord sheet's Staff view (see :doc:`chord_sheet`) to draw a
     voicing on a grand staff.
     Leave it out and Chord Notepad picks the staff automatically from the
     voice's range: ``"bass"`` if the range center sits below middle C,
     ``"treble"`` otherwise. The built-in Choir (SATB) pins soprano and alto
     to ``"treble"`` and tenor and bass to ``"bass"`` explicitly; every other
     built-in leaves it to the automatic rule.
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

.. only:: android

   An ensemble's form starts with its **Voices**, top voice first. On a phone
   each voice is a small card:

   * **Name**: what the voice is called, for example Soprano. MIDI export
     names the voice's track after it.
   * **Low** and **High**: the voice's range, as note names (``C4``,
     ``F#3``) or MIDI numbers; middle C is ``C4``.
   * **Staff**: where the chord sheet's Staff view draws the voice (see
     :doc:`chord_sheet`). **Auto** picks it from the range: the bass staff
     if the middle of the range is below middle C, the treble staff
     otherwise. The built-in Choir (SATB) sets soprano and alto to Treble
     and tenor and bass to Bass; every other built-in leaves it on Auto.

   **Add voice** adds a voice at the bottom and **✕** removes one. An
   ensemble has 2 to 8 voices.

.. platform-figure:: settings-voicing-ensemble
   :platforms: android
   :alt: The Jazz Vocal Trio form scrolled to Voices: short help lines for
         Name, Low, High and Staff, then a card per voice: Lead, A3 to F5,
         and Harmony, F3 to D5, each with Staff set to Auto and an X to
         remove it.

   The voices of a custom ensemble, one card each.

.. only:: android

   Under the voices:

   * **Max spacing**: the largest gap, in semitones, allowed between each
     pair of neighbouring voices, as a comma-separated list with one number
     fewer than there are voices. The hint under the field says how many it
     expects. Left empty, every gap is an octave, except the bottom one,
     which gets an octave and a fifth to leave the bass room to move.
   * **Allow unisons**: turn it off if you never want two neighbouring
     voices on the same pitch.
   * **Weights**, then **Doubling**, **Omission** and **Inversion**: see the
     parameter reference below. Change only the ones you want to.

   As an example, a jazz vocal trio. Start from **Model: Ensemble**, add a
   third voice, and fill in:

   .. list-table::
      :header-rows: 1
      :widths: 50 50

      * - Field
        - Value
      * - Name
        - Jazz Vocal Trio
      * - Voices (Name, Low, High)
        - Lead, A3, F5; Harmony, F3, D5; Bass, E2, C4
      * - Max spacing
        - 12, 19
      * - Allow unisons
        - off
      * - Voice movement (under Weights)
        - -0.6
      * - Common tone held
        - 2.5
      * - Parallel fifths/octaves
        - -15.0

.. only:: desktop

   Custom ensembles appear in :menuselection:`Playback --> Voicing` the next
   time Chord Notepad starts (or as soon as you save them in the Settings
   window), in the last group of the menu with your other custom voicings,
   sorted by model and then name.

.. only:: android

   Custom ensembles appear in the player's Voicing sheet, under **Your
   voicings**, as soon as you save them.

.. only:: desktop

   .. note::
      Upgrading from an older version? Chord Notepad moves any entries it
      finds under the old ``custom_tunings`` or ``custom_ensembles`` keys into
      ``voicings`` automatically the first time it starts, including
      whichever voicing you had selected. There's nothing to do by hand.


Voicing Parameters
====================

.. only:: desktop

   Every ensemble, built-in or custom, is steered by the same set of
   numeric parameters. These are the controls the Voicings page of
   :menuselection:`Tools --> Settings...` exposes, one control per row --
   see :doc:`settings` for the page itself; they can also be set directly in
   the ``weights`` object for an ensemble in ``settings.json``. Every weight
   is a signed number added to the voicing's score. Positive values make that
   trait more likely, negative values less likely, and higher is always more
   preferred. A trait you want the engine to seek gets a positive weight; one
   you want it to avoid gets a negative one; zero is neutral.

.. only:: android

   Every ensemble, built-in or custom, is steered by the same set of
   numeric parameters. These are the fields under **Weights**, **Doubling**,
   **Omission** and **Inversion** in an ensemble's form in
   |voicings_settings| (see :doc:`settings`). **Config key** is the
   setting's name in the app's configuration file; you only need it if you
   share voicings with the desktop version of Chord Notepad. Every weight
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
       sit stiller; nearer zero lets them roam more freely. You can also
       give one value per voice, top voice first, separated by commas; that
       list then sets the bottom voice too, in place of "Bass movement".
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
     - Subtracted when a voice jumps more than an octave, on top of "Large
       leap". A leap of exactly an octave pays only "Large leap".
     - ``octave_leap_penalty``
     - -6.0
   * - Tritone leap
     - Subtracted when a voice leaps exactly a tritone (six semitones), an
       interval singers and string players find hard to place accurately.
     - ``tritone_leap_penalty``
     - -3.0
   * - Common tone held
     - Added when a voice holds the same note it just sang (the same pitch,
       not the same note an octave away). More positive keeps more notes
       "tied over" between chords.
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
   * - Doubling (Root, Fifth, Third, Seventh, Color, Extension)
     - Added to the score for which chord tone gets doubled when there are
       more voices than notes in the chord, once per extra copy. Positive
       favors doubling that tone, negative avoids it. Keys: ``root`` (+2.0), ``fifth``
       (+0.5), ``third`` (-2.0), ``seventh`` (-6.0), ``color`` (-6.0),
       ``extension`` (-6.0).
     - ``doubling.root`` / ``.fifth`` / ``.third`` / ``.seventh`` /
       ``.color`` / ``.extension``
     - :plat:`see left|per key, above`
   * - Omission (Root, Third, Fifth, Seventh, Color, Extension)
     - Added to the score for dropping a chord tone entirely when there are
       fewer voices than notes. The values are negative, so a more negative
       one keeps that tone more insistently. Keys: ``root`` (-4.0),
       ``third`` (-40.0), ``fifth`` (-8.0), ``seventh`` (-40.0), ``color``
       (-30.0), ``extension`` (-7.0).
     - ``omit.root`` / ``.third`` / ``.fifth`` / ``.seventh`` /
       ``.color`` / ``.extension``
     - :plat:`see left|per key, above`
   * - Inversion (Root, First, Second, Third)
     - Added to the score for the bass note's chosen inversion (not used for
       slash chords, whose bass is fixed). Keys: ``root`` (0.0), ``first``
       (-1.5), ``second`` (-5.0), ``third`` (-3.0); nearer zero favors that
       inversion, more negative avoids it. A sixth, sus tone or extension in
       the bass counts as ``second``.
     - ``inversion.root`` / ``.first`` / ``.second`` / ``.third``
     - :plat:`see left|per key, above`
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
     - Subtracted per semitone that a gap between two neighbouring voices
       above the bass exceeds a perfect fifth (7 semitones). Separate from
       ``max_spacing``, which is a hard limit; this is a soft nudge toward
       closer spacing above the bass.
     - ``upper_spacing_penalty``
     - -0.15

.. note::
   These weights apply per ensemble. A custom ensemble that omits
   ``weights`` entirely uses the defaults above; one that sets ``weights``
   only needs to list the keys it wants to change; anything else falls
   back to the same defaults.
