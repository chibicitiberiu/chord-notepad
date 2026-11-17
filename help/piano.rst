==============
Piano Voicing
==============

Piano is the default instrument, and the *piano model* is the engine behind
it: a two-hand keyboard voicer that treats voicing as an optimization rather
than a fixed template. A *voicing* is a named configuration -- a model (the
engine that renders it) plus that model's parameters. The other two models
are covered elsewhere: fretted instruments like guitar in :doc:`fretted`, and
groups of independent singers or players in :doc:`ensembles`.


How the Two Hands Are Voiced
================================

The left hand plays the bass -- a single note or an octave-doubled one, down
in the low register -- and the right hand plays a voicing of the chord's core
tones (everything inside the octave: root, third, fifth, and a seventh, sixth
or suspended tone where present), tried in root position and every inversion,
at a few different octave placements. Any extensions a
chord carries -- a 9th, an 11th, a 13th -- always stack on top of that core
voicing rather than displacing it, so a dense jazz chord still reads as the
plain triad or seventh underneath with color added above.
When they don't all fit in one hand, leaving out the extension the chord's
name spells costs twice as much as leaving out one the name only stacks in,
so the named one usually stays: in Dm9 G13 Cmaj9 the G13 keeps its 13th (E)
and gives up the 9th. An altered 9th (C7♭9) counts as named. It is a
weight, not a rule, so a voicing that sits much better can still win.

Not every voicing that's built this way is playable, so the picker throws
out anything that breaks the physical model first: too many notes for one
hand, too wide a stretch, or the right hand crossing below the left. What
survives is scored on two things -- how good the voicing is on its own
(register, spacing, whether a close interval is sitting low enough to sound
muddy) and how smoothly it follows from the previous chord (common tones
held, small movements preferred) -- and the whole song is optimized together,
not chord by chord, so the hands settle into a stable register instead of
drifting up or down over a long song or a repeated section.


The Built-in Voicing
=========================

.. only:: desktop

   Chord Notepad ships with one built-in piano voicing, listed as **Piano** in
   the :menuselection:`Playback --> Voicing` menu and as **Piano (default)**
   in the **Add voicing** menu of the Voicings page. It's the voicing a fresh install
   starts with, and its parameters are the defaults listed under `Voicing
   Parameters`_ below.

.. only:: android

   Chord Notepad ships with one built-in piano voicing, listed as **Piano** in
   the player's Voicing sheet and as **Piano (default)** under Copy from existing in
   the Voicings editor. It's the voicing a fresh install starts with, and its
   parameters are the defaults listed under `Voicing Parameters`_ below.


Defining a Custom Piano Voicing
=====================================

.. only:: desktop

   If you want the piano to sit in a different register, spread the hands
   further apart, or trade completeness for a sparser texture, add a custom
   piano voicing from |voicings_settings|:
   click **Add voicing** and pick **Piano (default)** as a starting point,
   change what's different (ranges, span, weights), and click **Save**. See :doc:`settings` for the page itself.

.. only:: android

   If you want the piano to sit in a different register, spread the hands
   further apart, or trade completeness for a sparser texture, make a custom
   piano voicing:

   1. Open |voicings_settings| and tap **Add voicing**. The new
      voicing starts out as a guitar.
   2. Tap **Copy from existing** and pick **Piano (default)**. The form switches to
      the piano's fields, with the built-in values filled in. (Picking
      **Piano** under **Model** gives you the same values.)
   3. Tap the **Name** field to name the voicing.
   4. Change what's different: the hand ranges, the hand span, the weights.
      Each change is saved as you make it.

   See :doc:`fretted` for how errors are shown, and :doc:`settings` for the
   page itself.

.. only:: desktop

   Power users can also edit the configuration file directly -- the same
   mechanism used for custom fretted instruments and ensembles. The file lives
   at ``~/.config/chord-notepad/settings.json`` on Linux, or the equivalent
   per-user application-data folder on Windows and macOS.

.. only:: desktop

   Add a ``voicings`` object at the top level, keyed by the voicing's name;
   each entry needs a ``"model": "piano"`` and describes one keyboard
   configuration. Here's a voicing that moves the right hand down toward the
   left without letting the hands crowd each other, suited to a slow, intimate
   ballad:

   .. code-block:: json

      {
        "voicings": {
          "Close & Low": {
            "model": "piano",
            "rh_center": 55,
            "hand_gap_floor": 4,
            "weights": {
              "rh_wide_gap_penalty": -1.2
            }
          }
        }
      }

   * ``model`` is required and must be ``"piano"`` for a voicing defined this
     way (a fretted instrument uses ``"model": "fretboard"``, and an ensemble
     uses ``"model": "ensemble"`` -- see :doc:`fretted` and :doc:`ensembles`).
   * The key (``"Close & Low"`` here) is the voicing's name, the one the
     Voicing menu and the Settings window show.
   * ``lh_range``, ``rh_range``, ``bass_range``, and ``rh_low_anchor`` are all
     optional ``[low, high]`` pairs. Give each endpoint as a note name
     (``"C3"``, ``"E4"``) or a raw MIDI number; middle C is ``C4``.
   * ``rh_center``, ``rh_low_interval_floor``, ``hand_span``,
     ``max_notes_per_hand``, ``max_total_notes``, ``hand_gap_floor``, and
     ``add_bass`` are all optional -- see the parameter reference below for
     what each controls and its default.
   * ``weights`` is optional and partial -- give only the settings you want to
     change, and everything else keeps its default. See the parameter
     reference below for the full list of keys.

.. only:: android

   Here's a voicing that moves the right hand down toward the left without
   letting the hands crowd each other, suited to a slow, intimate ballad.
   Start from **Piano (default)** and change these fields:

   .. list-table::
      :header-rows: 1
      :widths: 50 50

      * - Field
        - Value
      * - Name
        - Close & Low
      * - RH center
        - 55
      * - Hand gap floor
        - 4
      * - Wide right-hand gap (under Weights)
        - -1.2

   Notes are written as note names (``C3``, ``E4``, or ``Do3``, ``Mi4`` in
   European notation) or MIDI numbers; middle C is ``C4``, MIDI 60. The parameter reference below explains every field.

.. only:: desktop

   Custom piano voicings appear in the Voicing menus as soon as you save
   them in the Settings window, in the last group with your other custom
   voicings, sorted by model and then name.

.. only:: android

   Custom piano voicings appear in the player's Voicing sheet, under **Your
   voicings**, as soon as they're saved.


How to Change Voicing
=========================

.. only:: desktop

   1. Pause or stop the song if it is playing.
   2. Click the **Voicing** button in the player bar (or open **Playback →
      Voicing**).
   3. Select **Piano**, or any custom piano voicing you've defined (see
      above).
   4. Play your chords to hear the difference.

.. only:: android

   1. In the Play tab, tap the **Voicing** button (the music note, first in
      the player's row of buttons).
   2. Select **Piano**, or any custom piano voicing you've defined (see
      above).
   3. Play your chords to hear the difference.

.. only:: desktop

   A checkmark shows the current voicing, the same as for :doc:`playback`.

.. only:: android

   A filled radio button marks the current voicing. While a song plays the
   Voicing button is greyed out: pause first (see :doc:`playback`).


Voicing Parameters
=======================

.. only:: desktop

   Every piano voicing, built-in or custom, is steered by the same physical
   hand limits, the same scoring anchors, and the same set of numeric weights.
   These are the controls the Voicings page of :menuselection:`Tools -->
   Settings...` exposes, one control per row -- see :doc:`settings` for the
   page itself; they can also be set directly in a voicing's entry in
   ``settings.json``.

.. only:: android

   Every piano voicing, built-in or custom, is steered by the same physical
   hand limits, the same scoring anchors, and the same set of numeric weights.
   These are the fields of a piano voicing's form in |voicings_settings|
   (see :doc:`settings`). The four ranges are under **Hands & range**, each
   with a Low and a High note. **Config key** is the setting's
   name in the app's configuration file; you only need it if you share
   voicings with the desktop version of Chord Notepad.

Hands and Range
------------------

.. list-table::
   :header-rows: 1
   :widths: 28 40 20 12

   * - Control
     - What it does
     - Config key
     - Default
   * - Left hand
     - The lowest and highest key the left hand will ever play.
     - ``lh_range``
     - C1 - C3
   * - Right hand
     - The highest key the right hand will ever play. The low end is only
       used by the fallback voicing for a chord nothing else fits; where the
       right hand really starts is "RH lowest-note anchor".
     - ``rh_range``
     - C3 - C6
   * - Bass (preferred)
     - Where the bass note should ideally sit. It isn't a hard limit --
       sitting outside this window costs the below/above-bass weights per
       semitone, so the left hand can still stray from it when the chord
       demands.
     - ``bass_range``
     - C2 - B2
   * - RH lowest-note anchor
     - The window the right hand's *lowest* note is anchored within when the
       optimizer places a voicing at a given octave. A hard limit.
     - ``rh_low_anchor``
     - C3 - E4
   * - RH center
     - The ideal mean pitch of the right hand. Drifting away from this costs
       the center-penalty weight per semitone.
     - ``rh_center``
     - 63 (Eb4)
   * - Muddy floor
     - Below this pitch, a close right-hand interval (a third or narrower)
       starts to sound muddy rather than rich. Costs the low-interval-penalty
       weight per such interval.
     - ``rh_low_interval_floor``
     - 52 (E3)
   * - Hand span
     - The widest reach of the right hand, in semitones -- a ninth by
       default. Extensions that won't fit are dropped. The left hand plays
       one bass note or an octave, whatever this is set to.
     - ``hand_span``
     - 14
   * - Max notes/hand
     - The most notes the right hand may hold at once -- five fingers, five
       notes. Extensions are dropped first.
     - ``max_notes_per_hand``
     - 5
   * - Max total notes
     - The most notes both hands may play together for one chord.
     - ``max_total_notes``
     - 10
   * - Hand gap floor
     - The right hand should clear the left hand's top note by more than
       this many semitones. A gap of this many or fewer costs the "Hands
       too close" weight.
     - ``hand_gap_floor``
     - 2
   * - Add bass note
     - Whether the left hand plays a bass note at all. Turn this off for a
       right-hand-only texture, e.g. when something else is already covering
       the bass.
     - ``add_bass``
     - true

Weights steer the picker when it scores a candidate voicing. Every weight is
a signed number added to the voicing's score. Positive values make that
trait more likely, negative values less likely, and higher is always more
preferred. A trait you want the picker to chase gets a positive weight; one
you want it to steer clear of gets a negative one; zero leaves it neutral.

.. list-table::
   :header-rows: 1
   :widths: 28 40 20 12

   * - Control
     - What it does
     - Config key
     - Default
   * - Right-hand note
     - Added per note kept in the right hand. More positive favors fuller
       voicings; less positive lets the picker thin them out.
     - ``rh_note_bonus``
     - +0.6
   * - Right-hand center
     - Subtracted per semitone the right hand's mean pitch strays from
       "RH center".
     - ``rh_center_penalty``
     - -1.4
   * - Bass below range
     - Subtracted per semitone the bass sits below "Bass (preferred)".
     - ``lh_below_bass_penalty``
     - -1.5
   * - Bass above range
     - Subtracted per semitone the bass sits above "Bass (preferred)".
     - ``lh_above_bass_penalty``
     - -1.5
   * - Doubled bass
     - Subtracted once when the bass note is octave-doubled in the left
       hand.
     - ``lh_double_penalty``
     - -1.0
   * - Doubled bass low
     - An extra cost per semitone an octave-doubled bass sits below
       "Bass (preferred)", on top of "Doubled bass".
     - ``lh_double_low_penalty``
     - -1.0
   * - Muddy low interval
     - Subtracted per close right-hand interval (a third or narrower)
       sounding below "Muddy floor".
     - ``rh_low_interval_penalty``
     - -2.0
   * - Wide right-hand gap
     - Subtracted per interior right-hand gap wider than an octave.
     - ``rh_wide_gap_penalty``
     - -0.6
   * - Hands too close
     - Subtracted when the gap between the hands is no wider than "Hand gap
       floor": once at exactly the floor, and once more per semitone
       closer.
     - ``muddy_gap_penalty``
     - -1.5
   * - Common tone held
     - Added per common tone held across a chord change (voice leading).
     - ``common_tone_bonus``
     - +1.5
   * - Voice movement
     - Subtracted per semitone of nearest-neighbour movement across a chord
       change (voice leading). More negative keeps both hands stiller from
       one chord to the next.
     - ``movement_penalty``
     - -0.35
   * - Outer parallels
     - Subtracted when the bass and the top note move the same way and keep
       the octave or fifth they formed (G2-G4 to A2-A4), which the ear hears
       as the bass line doubled on top. Inner notes moving in parallel cost
       nothing, as in most piano comping.
     - ``outer_parallel_penalty``
     - -1.5
   * - Ending on the root
     - Added when the song's last chord has its top note on the chord's
       root, so the song closes on the root (C on top of the final C)
       rather than its third or fifth. Only the song's last chord with
       notes counts.
     - ``final_top_root_bonus``
     - +2.0
   * - Omission
     - Added to the score for dropping a chord tone entirely when the hand
       and note limits don't leave room for everything. The values are
       negative, so a more negative one keeps that tone more insistently.
       The piano only ever leaves out the fifth, the root (and only when the
       left hand plays it), or an extension that won't fit, so the third,
       seventh and color weights rarely come into play. The root's weight
       is also charged when a plain three-note chord's right hand leaves out
       the root the left hand plays, which would leave a bare two-note right
       hand (E2 | B3 G♯4 for an E). The fifth is the
       perfect fifth only: the diminished or augmented fifth of ``m7b5``,
       ``7b5``, ``aug`` or ``7#5`` counts as a color tone and is kept.
       An extension the chord's name only stacks in (G13's 9th) costs half
       the ``extension`` value, so the named one is more likely to stay, and
       an added tone (the 9th of ``add9`` or ``6/9``, a chord with no
       seventh) costs the ``color`` value.
       Same role taxonomy as the ensemble model's omission weights (see
       :doc:`ensembles`): ``root`` (-4.0), ``third`` (-40.0), ``fifth``
       (-8.0), ``seventh`` (-40.0), ``color`` (-30.0), ``extension`` (-7.0).
     - ``omit.root`` / ``.third`` / ``.fifth`` / ``.seventh`` / ``.color`` /
       ``.extension``
     - :plat:`see left|per key, above`

.. note::
   These weights apply per piano voicing. A custom piano voicing that omits
   ``weights`` entirely uses the defaults above; one that sets ``weights``
   only needs to list the keys it wants to change; anything else falls back
   to the same defaults.
