===================================
Guitar and Fretted Instruments
===================================

Guitar is the flagship case, but Chord Notepad's fretting engine -- the
*fretboard model* -- isn't guitar-specific. A *voicing* is a named
configuration: a model (the engine that renders it) plus that model's
parameters. The fretboard model can voice any instrument with 3 to 12
strings and frets -- guitar in any tuning, ukulele, banjo, a baritone
ukulele, a seven-string guitar -- as long as you can describe its open
strings. The other two models are covered elsewhere: piano in
:doc:`playback`, and groups of independent singers or players in
:doc:`ensembles`.


How Fingerings Are Chosen
============================

On a fretted instrument, not every set of notes is even physically
playable -- fingers only reach so far, and there are only so many of them --
so instead of arranging notes freely the way the piano model does, the
fretboard model searches for a *fingering*: a specific fret on each string
(or no fret at all, if the string is muted) that a hand could actually
hold. It builds every candidate fingering from scratch for the instrument's
actual tuning, throws out anything that doesn't spell the chord correctly
or that no hand could hold (too wide a stretch, more fretted notes than
there are fingers, unless a barre covers several at once), and scores what
survives on two things: how good the fingering is on its own -- full, low
on the neck, open strings ringing, the right note in the bass -- and how
smoothly the hand moves from one fingering to the next across the *whole
song*, not chord by chord, so a repeated section is voiced in the context
it actually plays in each time through.


The Five Built-in Voicings
==============================

Chord Notepad ships with five built-in fretboard voicings: four guitar
tunings and a ukulele.

.. list-table::
   :header-rows: 1
   :widths: 28 32 40

   * - Voicing
     - Strings (in string order)
     - Best for
   * - Guitar (Standard - EADGBE)
     - E2 A2 D3 G3 B3 E4
     - Most music, default choice
   * - Guitar (Drop D)
     - D2 A2 D3 G3 B3 E4
     - Heavy rock, metal, alternate bass
   * - Guitar (DADGAD)
     - D2 A2 D3 G3 A3 D4
     - Celtic, folk, fingerstyle
   * - Guitar (Open G)
     - D2 G2 D3 G3 B3 D4
     - Blues, slide guitar, Keith Richards
   * - Ukulele
     - G4 C4 E4 A4
     - Uke songs, standard "my dog has fleas" tuning

Ukulele is **re-entrant**: its first string, G4, is tuned *higher* than the
C4 next to it, rather than lower like every other string on the list. The
fretboard model handles that correctly -- strings are always kept in the
order given, never resorted by pitch, and whichever string ends up
sounding the lowest actual pitch in a fingering is treated as the bass,
regardless of which string that happens to be.

Because of that re-entrancy, the Ukulele preset also ships with two weights
adjusted from the guitar defaults: the *Correct bass note* weight is
lowered to +1.0 (within the uke's single octave there is rarely a true low
root to chase, and insisting on one drags shapes up the neck) and the
*Sounding string* weight is raised to +2.5 (with only four strings, every one that rings
counts). With these values the picker lands on the familiar chord-book
shapes: C as 0003, G as 0232, G7 as 0212, F as 2010.


Defining a Custom Fretted Voicing
======================================

.. only:: desktop

   If none of the five match the instrument you're writing for, add one from
   |voicings_settings|: load a built-in
   preset as a starting point, change what's different (tuning, span,
   weights), and save. See :doc:`settings` for the full walkthrough,
   including a seven-string guitar built from the Guitar (Standard) preset.

.. only:: android

   If none of the five match the instrument you're writing for, make your own
   in the Voicings editor:

   1. Open |voicings_settings|. (From the player, **Voicing → Edit
      voicings…** gets you there too.)
   2. Tap **Add voicing**. A new voicing called "New voicing" appears under
      **Fretboard**, already set up as a six-string guitar in standard
      tuning, and its form opens.
   3. To start from another instrument, tap **Load config** and pick a
      preset: the built-in voicings, grouped by model, then your own. It
      replaces every parameter but keeps the name, and asks first.
   4. Tap the **Name** field (or its pencil) to give the voicing a name. That
      name is what the Voicing sheet shows.
   5. Change what's different: the strings, the fret range, the stretch, the
      weights. Each field explains itself in the small text under it.
   6. Tap **Save** at the top right.

.. platform-figure:: settings-voicing-form
   :platforms: android
   :alt: The voicing form for My 7-String: the Name field with a pencil, the
         Model drop-down set to Fretboard, Load config and Remove voicing,
         then the Strings field with B1 E2 A2 D3 G3 B3 E4 and the Max fret,
         Fingers and Max span steppers.

   The top of a fretted voicing's form.

.. only:: android

   Problems show up in red as you type: under the field for a value the app
   can't read (a misspelt note name, say), or at the top of the form for
   values that don't fit together (a relaxed span smaller than the normal
   one). A voicing with errors is marked **Has errors** in the list, and
   **Save** is greyed out until it's fixed; tap it anyway and the app tells
   you what's wrong and opens that voicing. **Remove voicing** deletes the
   voicing after asking. If you leave Settings with unsaved changes, the app
   asks whether to discard them.

   See :doc:`settings` for the whole Settings screen, including a seven-string
   guitar built step by step.

.. only:: desktop

   Power users can also edit the configuration file directly -- the same
   mechanism used for custom ensembles, and the same schema the Settings
   window reads and writes. The file lives at
   ``~/.config/chord-notepad/settings.json`` on Linux, or the equivalent
   per-user application-data folder on Windows and macOS.

.. only:: desktop

   Add a ``voicings`` object at the top level, keyed by a short slug you'll
   use internally; each entry needs a ``"model": "fretboard"`` and describes
   one instrument. Here's a seven-string guitar (a standard six-string guitar
   with an extra low B string):

   .. code-block:: json

      {
        "voicings": {
          "seven_string": {
            "model": "fretboard",
            "label": "7-String Guitar",
            "tuning": ["B1", "E2", "A2", "D3", "G3", "B3", "E4"],
            "max_fret": 12,
            "fingers": 4,
            "max_span": 4,
            "relaxed_span": 5,
            "allow_barres": true,
            "weights": {
              "bass_note_bonus": 10.0
            }
          }
        }
      }

   * ``model`` is required and must be ``"fretboard"`` for a voicing defined
     this way (an ensemble uses ``"model": "ensemble"`` instead -- see
     :doc:`ensembles`).
   * ``label`` is what shows up in the Voicing menu (defaults to the slug if
     omitted).
   * ``tuning`` is required: 3 to 12 entries, listed in **string order** --
     the order a player would strike the strings, not sorted by pitch. Each
     entry is a note name (``"E2"``, ``"B1"``) or a raw MIDI number; middle C
     is ``C4``. Re-entrant tunings, like the ukulele's, are legal and are kept
     in the order you give them.
   * ``max_fret``, ``fingers``, ``max_span``, ``relaxed_span``, and
     ``allow_barres`` are all optional -- see the parameter reference below
     for what each controls and its default.
   * ``weights`` is optional and partial -- give only the settings you want to
     change, and everything else keeps its default. See the parameter
     reference below for the full list of keys.

.. only:: android

   As an example, here is a seven-string guitar: a standard six-string guitar
   with an extra low B string. After **Add voicing**, fill in the form like
   this and leave everything else as it is:

   .. list-table::
      :header-rows: 1
      :widths: 40 60

      * - Field
        - Value
      * - Name
        - 7-String Guitar
      * - Strings
        - B1 E2 A2 D3 G3 B3 E4
      * - Max fret
        - 12
      * - Fingers
        - 4
      * - Max span
        - 4
      * - Relaxed span
        - 5
      * - Allow barre chords
        - on
      * - Correct bass note (under Weights)
        - 10.0

   * **Strings** lists the open strings in **string order**: the order a
     player would strike them, not sorted by pitch. Separate them with
     spaces. Each is a note name (``E2``, ``B1``) or a MIDI number; middle C
     is ``C4``. You need 3 to 12 strings. Re-entrant tunings, like the
     ukulele's, are fine and are kept in the order you give them.
   * The other fields have defaults; see the parameter reference below for
     what each one does.
   * The weights start at their defaults. Change only the ones you want to.

.. only:: desktop

   Custom fretted voicings appear in :menuselection:`Playback --> Voicing`
   automatically the next time Chord Notepad starts, sorted alongside every
   other voicing -- built-in or custom, fretted or ensemble -- by model and
   then name.

.. only:: android

   Custom fretted voicings appear in the player's Voicing sheet, under **Your
   voicings**, as soon as you save them. They are also offered in Suggest
   Capo (see :doc:`chord_sheet`).

.. only:: desktop

   .. note::
      Upgrading from an older version? Chord Notepad moves any entries it
      finds under the old ``custom_tunings`` or ``custom_ensembles`` keys into
      ``voicings`` automatically the first time it starts, including
      whichever voicing you had selected. There's nothing to do by hand.


How to Change Voicing
=========================

.. only:: desktop

   1. Open the **Playback** menu.
   2. Click **Voicing**.
   3. Select **Guitar (Standard - EADGBE)**, **Guitar (Drop D)**,
      **Guitar (DADGAD)**, **Guitar (Open G)**, **Ukulele**, or any custom
      fretted voicing you've defined (see above).
   4. Play your chords to hear the difference.

.. only:: android

   1. In the Play tab, tap **Voicing** in the player.
   2. Select **Guitar (Standard - EADGBE)**, **Guitar (Drop D)**,
      **Guitar (DADGAD)**, **Guitar (Open G)**, **Ukulele**, or any custom
      fretted voicing you've defined (see above).
   3. Play your chords to hear the difference.

.. only:: desktop

   A checkmark shows the current voicing, the same as for :doc:`playback`.

.. only:: android

   A filled radio button marks the current voicing. While a song plays the
   Voicing button is greyed out: pause first (see :doc:`playback`).


Voicing Parameters
======================

.. only:: desktop

   Every fretted voicing, built-in or custom, is steered by the same
   physical limits and the same set of numeric weights. These are the
   controls the Voicings page of :menuselection:`Tools --> Settings...`
   exposes, one control per row -- see :doc:`settings` for the page itself;
   they can also be set directly in a voicing's entry in ``settings.json``.

.. only:: android

   Every fretted voicing, built-in or custom, is steered by the same
   physical limits and the same set of numeric weights. These are the fields
   of a fretted voicing's form in |voicings_settings| (see
   :doc:`settings`). The **Config key** column is the setting's name in the
   app's configuration file; you only need it if you share voicings with the
   desktop version of Chord Notepad.

Physical Parameters
------------------------

.. list-table::
   :header-rows: 1
   :widths: 28 40 20 12

   * - Control
     - What it does
     - Config key
     - Default
   * - Strings
     - The open-string pitches, in string order. Required -- there is no
       default.
     - ``tuning``
     - --
   * - Max fret
     - The highest fret considered when searching for a fingering. Higher
       lets the picker reach further up the neck; lower keeps everything
       close to the nut.
     - ``max_fret``
     - 12
   * - Fingers
     - How many fretting fingers the hand has available.
     - ``fingers``
     - 4
   * - Max span
     - The widest fret span the hand holds on a normal pass.
     - ``max_span``
     - 4
   * - Relaxed span
     - The widest span the picker will accept as a last resort, when
       nothing fits within "Max span". Must be at least as
       large as "Max span".
     - ``relaxed_span``
     - 5
   * - Allow barre chords
     - Whether a single finger flattened across several strings can stand
       in for several fretted fingers at once.
     - ``allow_barres``
     - true

Weights steer the picker when it scores a candidate fingering. Every
weight is a signed number added to the voicing's score. Positive values
make that trait more likely, negative values less likely, and higher is
always more preferred. A trait you want the picker to chase gets a
positive weight; one you want it to steer clear of gets a negative one;
zero leaves it neutral. The sign already carries the meaning, so raising
``span_penalty`` from ``-1.2`` toward ``0`` tolerates wider stretches,
while pushing it more negative clamps down on them.

.. list-table::
   :header-rows: 1
   :widths: 28 40 20 12

   * - Control
     - What it does
     - Config key
     - Default
   * - Sounding string
     - Added per string that actually sounds (isn't muted). More positive
       favors fuller-sounding fingerings.
     - ``sounding_string_bonus``
     - +1.2
   * - Open string
     - Added per string played open (fret 0), on top of the sounding-string
       weight. Open strings ring fuller and cost nothing to hold, so this
       stays positive.
     - ``open_string_bonus``
     - +0.5
   * - Correct bass note
     - Added when the chord's root lands on the lowest sounding string.
     - ``bass_note_bonus``
     - +8.0
   * - Correct slash bass
     - The same, but for a slash chord's named bass note (the G in
       ``C/G``). Set more positive than "Correct bass note" since a slash
       bass is a deliberate instruction, not just a preference.
     - ``slash_bass_bonus``
     - +12.0
   * - Wide stretch
     - Subtracted per fret of span between the lowest and highest fretted
       note. More negative favors compact shapes even within the allowed
       stretch.
     - ``span_penalty``
     - -1.2
   * - Compact shape
     - Subtracted per fret of the shape's total span beyond the first, on top
       of "Wide stretch" -- a one-fret span costs nothing, a two-fret span
       once, a three-fret span twice. A gentle nudge toward compact shapes.
     - ``stretch_penalty``
     - -0.7
   * - Awkward stretch
     - Subtracted once when a three-fret shape is *not* a clean index-to-pinky
       reach -- that is, when the far fret isn't a single note on an outer
       string with the rest bunched near the low fret -- so an inner finger
       would have to make the stretch. Set strongly negative because no hand
       can hold such a shape; a clean lengthwise reach pays only "Compact
       shape".
     - ``awkward_stretch_penalty``
     - -6.0
   * - High neck position
     - Subtracted per fret of the fingering's average position up the neck.
       More negative keeps fingerings closer to the nut.
     - ``position_penalty``
     - -0.6
   * - Fretted finger
     - Subtracted per fretted finger the fingering requires. More negative
       favors fingerings that leave more strings open or muted.
     - ``fretted_finger_penalty``
     - -0.5
   * - Barre
     - Subtracted when a fingering requires a barre, on top of the
       fretted-finger weight. Barres are harder to hold cleanly than
       individually fretted fingers.
     - ``barre_penalty``
     - -1.0
   * - Muted inner string
     - Subtracted per muted string sitting between two sounding strings -- a
       "buried" mute that a strum can't skip cleanly. Set strongly negative so
       a plain barre chord beats a contorted shape with a dead string in the
       middle.
     - ``interior_mute_penalty``
     - -4.0
   * - Hand movement
     - Subtracted per fret the hand's average position shifts from the
       previous chord's fingering, evaluated across the whole song. More
       negative keeps the hand from jumping up and down the neck.
     - ``movement_penalty``
     - -1.0
   * - Kept finger
     - Added per finger that can stay on the same string and fret from one
       chord to the next.
     - ``kept_finger_bonus``
     - +0.4

.. note::
   These weights apply per voicing. A custom fretted voicing that omits
   ``weights`` entirely uses the defaults above; one that sets ``weights``
   only needs to list the keys it wants to change; anything else falls
   back to the same defaults.
