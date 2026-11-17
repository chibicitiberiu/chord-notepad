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
(highest to lowest), and a voice of your own can't start or end below the
one under it: the voicings editor tells you if it does. "Max gap below" is
the largest interval the engine normally puts between that voice and the
one under it -- ensembles are
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

The Staff view of the chord sheet (see :doc:`chord_sheet`) draws the soprano
and alto on the treble staff, the tenor and bass on the bass staff.

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

In the Staff view the two tenors are on the upper staff, under a treble clef
with a small 8 below it: as in printed men's choir music, their notes are
written an octave higher than they sound, so a tenor's middle C sits in the
third space instead of on a ledger line. The baritone and bass are on the
bass staff.

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

All three voices are drawn on the treble staff.

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

The violins are drawn on the treble staff and the cello on the bass staff.
The viola, normally written in the alto clef, picks its staff from its range,
which puts it on the treble staff.

The String Quartet is tuned as a background pad rather than four-part
choir writing, so it has a few weights of its own. Violin I, the line you
hear on top, costs twice as much to move as the two middle voices (the Movement
costs are ``-0.8, -0.4, -0.4, -0.15``), and the leading tone's bonus for
rising to the tonic is 4.5, so the calmer top line still resolves it in G
to Am. Its upper voices may spread an octave apart before Wide
upper spacing costs anything (Upper spacing allowed is 12; a choir keeps 7,
a fifth). When Violin I or the cello leaps more than a fifth, each semitone
past the fifth costs another 0.5 (Wide outer leap is -0.5). Each upper voice
also pays 0.5 for every semitone it strays outside the middle half of its
range, and the cello for every semitone above it (Outside the middle range
is -0.5), so the quartet stays in one register
through a song and sounds alike in every key. It also has
Allow unisons off: four instruments playing a triad can always double a
note an octave apart instead.

The three choirs allow adjacent voices to land on the same pitch (a
unison), since that's an ordinary, occasional occurrence in real choral
writing rather than something to avoid outright. Their seventh and leading
tone resolve more firmly than the defaults (Seventh resolves down 3,
Leading tone resolves 4): with both chords on their roots, G to Am only
keeps the leading tone rising if the choir doubles the A minor's third.
Like the quartet, each voice pays 0.5 for every semitone it strays outside
the middle half of its range, the bass only above it (Outside the middle
range is -0.5), which keeps the basses low: C G Am F is C3 G2 A2 F2 rather
than C3 G3 A3 F3. In the Treble Choir the top voice also costs twice as much
to move as the others (Movement ``-0.8, -0.4, -0.15``): with three voices the
alto carries the bass line, and the top line had been leaping up and back.

All four presets keep a plain chord on its root (Inversion ``first`` -4,
``third`` -6, ``second`` -8; the defaults, which a custom ensemble starts
from, are -1.5, -3 and -5). Write a slash chord when you want an inversion.


How Voicing Decisions Are Made
================================

Each voice tries to keep the note it's already singing (a common tone),
and moves by the smallest useful step when it has to move at all. Parallel
fifths and octaves between two voices carry a heavy penalty -- that one
motion is the fastest way to make four-part harmony sound wrong -- so the
engine avoids them whenever another voicing is available. The one exception
is an ensemble of five voices or more: there two voices that both play the
bass line may move in octaves, the way a cello and a double bass do. The
leading tone earns a bonus for resolving up to the tonic, and doubling it is
avoided.

Which note is the leading tone comes from the key. With a ``{key:}`` line it
is that key's. Without one, the engine works the key out from the chords
around each chord, four before and four after, and how clearly they belong
to one key rather than another: a loop like C G Am F is clearly in C, a
passage like C E A♭ C belongs to no key. Where the key is clear the leading
tone counts in full; where it is borderline it counts less, and in a
chromatic passage not at all. On top of that, a major or dominant chord whose
root falls a fifth to the next chord's root has its third treated as a
leading tone for that change, so a secondary dominant resolves too (the C♯
of A7 rises to D in A7 Dm). A ``{key:}`` line always wins over both.

If a chord has more notes than there are voices, the tone with the
cheapest Omission weight is left out. With the defaults that's the fifth,
as in four-part writing: a G7 for three voices comes out as G, B and F, and
a C9 for four voices as C, E, B♭ and D. Next comes an extension the chord's
name only stacks in (the 9th of a G13, which costs half the Extension
weight), then the named one (G13's 13th, an Am11's 11th, an altered 9th),
then the root; the third, the seventh and a ``sus`` chord's suspended tone
are kept. So a G13 for four voices is G, B, F and E. (The piano drops the root before the fifth, because its left hand
plays the root; an ensemble keeps it.) If a chord has fewer
notes than voices, something gets doubled, and the engine reaches for the
root first. A chord that fills the voices exactly may also leave out its
perfect fifth and double the root instead, as four-part writing does to
resolve a G7 to C with both chords on their roots; a diminished or augmented
fifth is always kept.

Only a perfect fifth counts as the fifth. The ♭5 of ``m7b5`` or ``7b5`` and
the ♯5 of ``aug`` or ``7#5`` count as color tones, because without them the
chord is heard as m7, 7 or a major triad. So with too few voices such a chord
gives up its root instead: C7♯5 for three voices is E, G♯ and B♭, the
rootless voicing a jazz arranger writes. A diminished seventh chord is the
exception: its four tones are a minor third apart, any three of them sound the
same chord, so it still leaves out its ♭5 and keeps the root.

The bass line is planned first, on its own, before the other voices are
placed. A slash chord's bass note always lands in the bottom voice; a plain
chord may take any chord tone there, weighed by the Inversion weights. The
plan keeps the line in one octave while it fits the bottom voice's range, so
``C C/B Am Em/G F`` walks down C B A G F instead of jumping up an octave in
the middle, and changes octave where the line leaps anyway. Holding the bass
note into the next chord earns the usual common-tone bonus, except when that
would put a plain chord on something other than its root (Am then F stays
F, not F/A). It never picks a
bass note that would leave too little room above it for the rest of the
chord. Because the plan only looks at the line and the range, the same song
in another key gets the same inversions.

When a chord sits next to itself over another bass, say C then C/E, you
expect to hear the bass move, so the plain C is nudged off E and back onto
its own root. Without that nudge the easiest answer is to keep every
voice where it was, and both chords would sound the same.

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
   own from |voicings_settings|: click **Add voicing**, pick a
   built-in ensemble as a starting point, change the voices, spacing, or
   weights, and click **Save**. See :doc:`settings` for the page itself and a worked
   example (built there for a fretted instrument, but the same steps apply
   to an ensemble).

   The **Voices** table has a row per voice, top voice first: **Name**,
   **Low** and **High** (the range), **Staff** (where the Staff view draws
   it; see the ``staff`` key below for what **Auto** does), **Max gap to
   next voice**, the largest gap in semitones between this voice and the
   one below it, and **Movement cost**, how much the picker dislikes this
   voice moving between chords (per semitone; a more negative value keeps
   the voice calmer, and the bottom voice's is the bass's, normally nearer
   zero). The bottom voice has no voice below, so its gap is greyed out.
   Drag the grip at the left of a row to move that voice up or down (or
   focus a row and press :kbd:`Alt+Up` or :kbd:`Alt+Down`); its gap and
   movement cost go with it. **⧉** copies a voice right below itself, with
   the same range, staff, gap and movement cost and a name that ends in 2
   (3, 4... if taken), **✕** removes it, and **Add voice** adds one at the
   bottom. A new bottom voice starts with the old bottom voice's movement
   cost, and the old one takes the inner voices' average. A voice
   that gets a voice below it and has no gap yet starts at 12, an octave.

.. only:: android

   If the four presets don't match the group you're writing for, define your
   own:

   1. Open |voicings_settings| and tap **Add voicing**. The new
      voicing starts out as a guitar.
   2. Tap **Copy from existing** and pick the built-in ensemble closest to what you
      want, such as **Choir (SATB)**. Or set **Model** to **Ensemble** to
      start from two plain voices.
   3. Tap the **Name** field to name the voicing.
   4. Change the voices, the spacing or the weights (see below). Each change
      is saved as you make it.

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
     voice's range: ``"bass"`` if the range center sits below middle C (below
     C3 when ``upper_clef`` is ``"treble_8vb"``, where C3 is written as middle
     C), ``"treble"`` otherwise. The built-ins pin their voices explicitly (the
     staffs listed under `The Four Presets`_), except the string quartet's
     viola.
   * ``upper_clef`` is optional: the clef of the Staff view's upper staff.
     ``"treble"`` (the default) is the plain treble clef; ``"treble_8vb"`` is
     the treble clef with a small 8 below, used for tenors: every note on the
     upper staff is written an octave higher than it sounds. It only changes
     the drawing, never what plays. The built-in Male Choir (TTBB) uses
     ``"treble_8vb"``.
   * ``max_spacing`` is optional: the maximum semitone gap allowed between
     each pair of neighbouring voices, one entry per gap (so one fewer entry
     than there are voices), top gap first. The Settings window shows entry
     *i* as the **Max gap to next voice** of voice *i*. Leave it out and Chord
     Notepad defaults every gap to an octave, except the bottom gap, which
     gets an octave and a fifth to leave the bass room to move.
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
     ``F#3``, or ``Do4``, ``Fa#3`` in European notation) or MIDI numbers;
     middle C is ``C4``.
   * **Staff**: where the chord sheet's Staff view draws the voice (see
     :doc:`chord_sheet`). **Auto** picks it from the range: the bass staff
     if the middle of the range is below middle C, the treble staff
     otherwise. With **Upper staff** set to the octave-lower treble (below),
     the split is C3 instead, which that clef writes as middle C. The
     built-ins set each voice's staff (listed under `The Four Presets`_);
     only the string quartet's viola is on Auto.
   * **Max gap to next voice**: the largest gap, in semitones, allowed
     between this voice and the one below it. The bottom voice has none, so
     its field is greyed out. A voice that gets a voice below it and has no
     gap yet starts at 12, an octave.
   * **Movement cost**: added per semitone this voice moves from one chord
     to the next. More negative keeps the voice calmer. The bottom voice's
     is the bass's, normally nearer zero.

   **Add voice** adds a voice at the bottom, with the old bottom voice's
   movement cost (the old one takes the inner voices' average). **↑** and
   **↓** move a voice up or down a place (its gap and movement cost go with
   it), the copy button duplicates a voice right below itself (same range,
   staff, gap and movement cost, named "<name> 2", then 3...), and **✕**
   removes one. To make a new voice the top one, add it, then tap its **↑**
   until it's first. An ensemble has 2 to 8 voices.

.. platform-figure:: settings-voicing-ensemble
   :platforms: android
   :alt: The Jazz Vocal Trio form scrolled to Voices: short help lines for
         Name, Low, High, Staff and Max gap to next voice, then a card per
         voice with up and down arrows, a copy button and an X: Lead, A3 to F5, Staff Auto,
         Max gap 12, and the top of Harmony's card.

   The voices of a custom ensemble, one card each.

.. only:: android

   Under the voices:

   * **Upper staff**: the clef of the Staff view's upper staff. **Treble** is
     the plain treble clef. **Treble, octave lower (tenors)** adds a small 8
     below it and writes every note on that staff an octave higher than it
     sounds, as men's choir music does for tenors. It only changes the
     drawing. The built-in Male Choir (TTBB) uses it.
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
      * - Voices (Name, Low, High, Max gap to next voice, Movement cost)
        - Lead, A3, F5, 12, -0.6; Harmony, F3, D5, 19, -0.6; Bass, E2, C4, no gap, -0.15
      * - Allow unisons
        - off
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
   voicings**, as soon as they're saved.

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
   * - Movement cost (a column of the Voices table)
     - Added per semitone that voice moves from one chord to the next. It's
       negative, so a more negative value makes the voice sit stiller; nearer
       zero lets it roam more freely. The bottom voice's is the bass's: bass
       lines conventionally leap more than inner voices, so it usually sits
       nearer zero. Saved as one value per voice, top voice first. In the
       file, a single number is also accepted (every voice but the bottom
       takes it, and the bottom takes ``bass_movement``), and a list of the
       wrong length is stretched to the voices: the first value stays the top
       voice's, the last the bottom's, and the inner voices take the inner
       values by position.
     - ``movement`` (``bass_movement`` with a single number)
     - -0.4 (-0.15)
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
   * - Wide outer leap
     - Subtracted per semitone that the top or the bottom voice leaps beyond
       a fifth, on top of "Large leap", so a wider leap of an outer line costs
       more. Off (0) by default; the String Quartet uses -0.5.
     - ``outer_leap_penalty``
     - 0
   * - Tritone leap
     - Subtracted when a voice leaps exactly a tritone (six semitones), an
       interval singers and string players find hard to place accurately.
     - ``tritone_leap_penalty``
     - -4.5
   * - Augmented second
     - Subtracted when a voice moves an augmented second: three semitones
       between neighbouring letter names, as the two chords spell them (F to
       G♯ when F goes to E in A minor; F to A♭ is a minor third and costs
       nothing). The classic place is VI to V in a minor key, where the
       doubled root of F would otherwise climb to the G♯. Keep it more
       negative than "Tritone leap", or the voice leaps a tritone instead.
     - ``augmented_second_penalty``
     - -4.0
   * - Common tone held
     - Added when a voice holds the same note it just sang (the same pitch,
       not the same note an octave away). More positive keeps more notes
       "tied over" between chords.
     - ``common_tone_bonus``
     - +1.5
   * - Parallel fifths/octaves
     - Subtracted per pair of voices that move in parallel perfect fifths
       or octaves -- the classic part-writing fault. Set strongly negative
       by default because it's rarely wanted. With five voices or more, two
       voices that both play the bass line (the bass note of each chord, in
       another octave) aren't charged for moving in octaves.
     - ``parallel_perfect_penalty``
     - -25.0
   * - Hidden fifths/octaves
     - Subtracted when the top and bottom voices move the same way into a
       perfect fifth or octave (counted in any octave) while the top voice
       leaps, by more than a whole tone. A top voice moving by step is never
       charged, as in four-part writing.
     - ``hidden_perfect_penalty``
     - -2.0
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
       key) resolves upward by step into the tonic. Without ``{key:}`` the
       key is inferred (see above), and the third of a dominant falling a
       fifth counts as a leading tone too.
     - ``leading_tone_resolution_bonus``
     - +1.5
   * - Doubled leading tone
     - Subtracted if two voices end up doubling the leading tone, which
       traditionally produces awkward parallel octaves at the resolution.
       Without ``{key:}``, as for "Leading tone resolves".
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
       one keeps that tone more insistently. Keys: ``root`` (-20.0),
       ``third`` (-40.0), ``fifth`` (-3.0), ``seventh`` (-40.0), ``color``
       (-30.0), ``extension`` (-6.0). The fifth is the perfect fifth only;
       a diminished or augmented fifth (``m7b5``, ``7#5``) is a color tone.
       An extension the chord's name only stacks in (G13's 9th) costs half
       the ``extension`` value, so the named one is kept first.
     - ``omit.root`` / ``.third`` / ``.fifth`` / ``.seventh`` /
       ``.color`` / ``.extension``
     - :plat:`see left|per key, above`
   * - Inversion (Root, First, Second, Third)
     - Added to the score for the bass note's chosen inversion (not used for
       slash chords, whose bass is fixed). The bass line is planned with
       them: against a bass held from the chord before (worth "Common tone
       held") or a shorter step, the defaults still let a plain chord be
       inverted now and then; the presets use ``first`` -4, ``third`` -6,
       ``second`` -8 to keep it on its root. Keys: ``root`` (0.0), ``first``
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
   * - Outside the middle range
     - Subtracted per semitone a voice sits outside the middle half of its
       range: a quarter of the range in from each end. Cello C2 - E4 spans 28
       semitones, so its middle half runs from G2 to A3. The bottom voice pays
       only above its band (a bass may sit as low as its range allows), so the
       cello costs nothing up to A3. More negative keeps
       every voice in one register through a song, and the same song in
       another key in the same register. Off (0) by default; the String
       Quartet uses -0.5.
     - ``middle_range_penalty``
     - 0
   * - Unison between voices
     - Subtracted per pair of neighbouring voices landing on the same pitch.
       Only relevant when ``allow_unisons`` is ``true``.
     - ``unison_penalty``
     - -0.5
   * - Muddy low interval
     - Subtracted per semitone that the lower of two neighbouring voices
       up to a tenth apart sits below that interval's low interval limit,
       the point below which it sounds muddy: a minor second below E3, a
       major second below Eb3, a minor third below C3, a major third or a
       tritone below Bb2, a fourth below A2, a minor sixth below G2, a major
       sixth or a seventh below F2, a fifth below Bb1, a minor ninth below
       E2, a major ninth below Eb2, a minor tenth below C2, a major tenth
       below Bb1 (the wide ones matter for a double bass under a cello). Sources differ a
       little (some put the tritone at B2 and the fourth at Bb2). The cost
       fades in at the limit: a pair one semitone under it costs little, A2
       with C3 above it (three under) costs three times as much. It keeps the
       third of a chord out of the double bass and cello's low register, so
       the low voices spread to fifths and octaves and the third sounds
       higher up.
     - ``low_interval_limit_penalty``
     - -2.0
   * - Wide upper spacing
     - Subtracted per semitone that a gap between two neighbouring voices
       above the bass exceeds "Upper spacing allowed". Separate from
       ``max_spacing``, which is a hard limit; this is a soft nudge toward
       closer spacing above the bass.
     - ``upper_spacing_penalty``
     - -0.15
   * - Upper spacing allowed
     - Not a score but a size: the widest gap, in semitones, two
       neighbouring voices above the bass may have before "Wide upper
       spacing" applies. 7 (a perfect fifth) keeps a choir in close
       position; the String Quartet allows 12 (an octave), which sounds
       warmer on strings.
     - ``upper_spacing_threshold``
     - 7
   * - Same chord, same bass
     - Subtracted when two neighbouring chords are the same chord over
       different written basses (C and C/E, or C/E and C/G) but both
       voicings would sound the same lowest note. A plain chord's written
       bass is its root. More negative keeps a plain chord next to its slash
       chord on its own root.
     - ``same_bass_penalty``
     - -8.0
   * - Voice overlap
     - Subtracted per voice that moves past where its neighbour just was:
       the tenor going below the note the bass just sang, or the alto above
       the soprano's last note. The two lines cross in the listener's ear
       and on the staff even though no voice crosses within a chord. Most
       common in the close choirs (TTBB, SSA).
     - ``voice_overlap_penalty``
     - -1.0

.. note::
   These weights apply per ensemble. A custom ensemble that omits
   ``weights`` entirely uses the defaults above; one that sets ``weights``
   only needs to list the keys it wants to change; anything else falls
   back to the same defaults.
