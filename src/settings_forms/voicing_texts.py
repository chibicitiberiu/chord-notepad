"""Words of the voicings editor: labels, help texts and section blurbs.

Shared by every view of the editor (the desktop Settings window shows the help
texts as hover tooltips; Android shows them as supporting text). Wording is
taken from help/fretted.rst and help/ensembles.rst; keep the two in step.
"""

from typing import Dict

# Human-readable labels, taken verbatim from help/fretted.rst and
# help/ensembles.rst, keyed by the weight's config key.
FRETBOARD_WEIGHT_LABELS: Dict[str, str] = {
    'sounding_string_bonus': 'Sounding string',
    'open_string_bonus': 'Open string',
    'bass_note_bonus': 'Correct bass note',
    'slash_bass_bonus': 'Correct slash bass',
    'span_penalty': 'Wide stretch',
    'stretch_penalty': 'Compact shape',
    'awkward_stretch_penalty': 'Awkward stretch',
    'position_penalty': 'High neck position',
    'fretted_finger_penalty': 'Fretted finger',
    'barre_penalty': 'Barre',
    'interior_mute_penalty': 'Muted inner string',
    'movement_penalty': 'Hand movement',
    'kept_finger_bonus': 'Kept finger',
}

ENSEMBLE_WEIGHT_LABELS: Dict[str, str] = {
    'movement': 'Voice movement',
    'bass_movement': 'Bass movement',
    'leap_penalty': 'Large leap',
    'octave_leap_penalty': 'Octave leap',
    'tritone_leap_penalty': 'Tritone leap',
    'common_tone_bonus': 'Common tone held',
    'parallel_perfect_penalty': 'Parallel fifths/octaves',
    'contrary_motion_bonus': 'Contrary motion',
    'seventh_resolution_bonus': 'Seventh resolves down',
    'leading_tone_resolution_bonus': 'Leading tone resolves',
    'double_leading_tone_penalty': 'Doubled leading tone',
    'range_comfort_penalty': 'Out-of-comfort range',
    'unison_penalty': 'Unison between voices',
    'upper_spacing_penalty': 'Wide upper spacing',
}

PIANO_WEIGHT_LABELS: Dict[str, str] = {
    'rh_note_bonus': 'Right-hand note',
    'rh_center_penalty': 'Right-hand center',
    'lh_below_bass_penalty': 'Bass below range',
    'lh_above_bass_penalty': 'Bass above range',
    'lh_double_penalty': 'Doubled bass',
    'lh_double_low_penalty': 'Doubled bass low',
    'rh_low_interval_penalty': 'Muddy low interval',
    'rh_wide_gap_penalty': 'Wide right-hand gap',
    'muddy_gap_penalty': 'Hands too close',
    'common_tone_bonus': 'Common tone held',
    'movement_penalty': 'Voice movement',
}

# Two piano weight keys collide by name with an existing fretboard/ensemble
# weight key ('movement_penalty', 'common_tone_bonus'); a shared TOOLTIPS dict
# keyed by bare 'weight:<key>' can't hold two different texts for the same
# key, so those two get a piano-prefixed tooltip key instead. See
# piano_weight_tooltip below.
PIANO_WEIGHT_TOOLTIP_OVERRIDES: Dict[str, str] = {
    'movement_penalty': 'weight:piano_movement_penalty',
    'common_tone_bonus': 'weight:piano_common_tone_bonus',
}

# Titles for the three nested-weight sub-frames.
NESTED_WEIGHT_TITLES: Dict[str, str] = {
    'doubling': 'Doubling',
    'omit': 'Omission',
    'inversion': 'Inversion',
}

# Human labels for the per-role sub-keys of the nested weights.
ROLE_LABELS: Dict[str, str] = {
    'root': 'Root',
    'third': 'Third',
    'fifth': 'Fifth',
    'seventh': 'Seventh',
    'color': 'Color',
    'extension': 'Extension',
    'first': 'First',
    'second': 'Second',
}

#: Display names of the three models, in the order the model selector lists them.
MODEL_LABELS: Dict[str, str] = {'fretboard': 'Fretboard', 'ensemble': 'Ensemble', 'piano': 'Piano'}

#: Display names for a voice's staff selector ('Auto' is the absent/None key).
STAFF_LABELS = ((None, 'Auto'), ('treble', 'Treble'), ('bass', 'Bass'))

#: Editor strings that aren't tied to one field.
EDITOR_TEXTS: Dict[str, str] = {
    'load_button': 'Load config',
    'name_label': 'Name:',
    'model_label': 'Model:',
    'placeholder': 'Select a voicing to edit, or add one with "+".',
    'load_confirm_title': 'Load configuration',
    'load_confirm': 'Loading a configuration replaces all parameters of this voicing. Continue?',
    'model_confirm_title': 'Change Model',
    'model_confirm': ('Switching model will replace the current parameters with defaults. '
                      'Continue?'),
    'remove_confirm_title': 'Remove Voicing',
    'remove_confirm': "Remove voicing '{name}'?",
    'rename_error_title': 'Rename Voicing',
}

# Small grey introducing every 'Weights' section.
WEIGHTS_BLURB = (
    "Each weight adds to a voicing's score, so a higher number always means "
    "more preferred. Positive values pull the picker toward a trait; negative "
    "values push it away. Zero is neutral. The defaults suit most music, so "
    "change these only if the results aren't to your taste."
)

# ---------------------------------------------------------------------------
# Tooltip texts -- one concrete sentence per input, grounded in the parameter
# tables of help/fretted.rst and help/ensembles.rst. Kept here (module level)
# so the wording is maintainable in one place.
# ---------------------------------------------------------------------------
TOOLTIPS: Dict[str, str] = {
    # Header controls.
    'name': "The name of this voicing, shown in the Playback → Voicing menu.",
    'model': ("The engine that renders this voicing: fretboard (a fretted "
              "instrument), ensemble (independent voices), or piano."),
    'load': ("Replace this voicing's parameters with those of a built-in preset "
             "or another voicing. The name is kept."),
    'tree_add': "Add a new voicing.",
    'tree_remove': "Remove the selected voicing.",

    # Fretboard physical parameters.
    'tuning': ("Open-string pitches in string order, lowest string first "
               "(note names or MIDI numbers, e.g. E2 A2 D3 G3 B3 E4). Required."),
    'max_fret': "Highest fret the picker will reach; higher allows shapes further up the neck.",
    'fingers': "How many fretting fingers the hand has available.",
    'max_span': "Widest fret stretch the hand holds on a normal pass.",
    'relaxed_span': ("Widest stretch accepted as a last resort when nothing fits "
                     "the normal span; must be at least the stretch."),
    'allow_barres': ("Whether one finger flattened across several strings can stand "
                     "in for several fretted fingers at once."),

    # Fretboard weights.
    'weight:sounding_string_bonus': ("How the picker treats strings that actually sound. More "
                                     "positive favors fuller-sounding fingerings; negative would "
                                     "favor sparser ones."),
    'weight:open_string_bonus': ("How the picker treats open strings (fret 0), on top of the "
                                 "sounding-string weight. More positive favors open strings."),
    'weight:bass_note_bonus': ("How the picker treats the chord's root landing on the lowest "
                               "sounding string. More positive encourages it."),
    'weight:slash_bass_bonus': ("How the picker treats a slash chord's named bass note landing "
                                "in the bass (the G in C/G). More positive encourages it."),
    'weight:span_penalty': ("How the picker treats wide finger stretches. More negative avoids "
                            "them; positive would seek them out."),
    'weight:stretch_penalty': ("How the picker treats a shape's overall fret span beyond a "
                               "single fret. More negative favors compact shapes; a one-fret "
                               "span costs nothing."),
    'weight:awkward_stretch_penalty': ("How the picker treats a three-fret shape that isn't a "
                                       "clean index-to-pinky reach on an outer string -- one "
                                       "that would force an inner finger to make the stretch. "
                                       "Set strongly negative to reject shapes no hand can hold."),
    'weight:position_penalty': ("How the picker treats fingerings further up the neck. More "
                                "negative keeps fingerings closer to the nut."),
    'weight:fretted_finger_penalty': ("How the picker treats fretted fingers. More negative "
                                      "favors shapes that leave more strings open or muted."),
    'weight:barre_penalty': ("How the picker treats fingerings that need a barre, on top of the "
                             "fretted-finger weight. More negative avoids barres."),
    'weight:interior_mute_penalty': ("How the picker treats a muted string buried between two "
                                     "sounding strings. More negative avoids that shape."),
    'weight:movement_penalty': ("How the picker treats the hand shifting from the previous "
                                "chord, across the whole song. More negative steadies the hand."),
    'weight:kept_finger_bonus': ("How the picker treats a finger staying on the same string and "
                                 "fret between chords. More positive rewards keeping it there."),

    # Ensemble voices / spacing / unisons.
    'voice_name': "Name of this voice, e.g. Soprano. Free text.",
    'voice_low': "Lowest note this voice may sing, inclusive (note name or MIDI number).",
    'voice_high': "Highest note this voice may sing, inclusive (note name or MIDI number).",
    'voice_staff': ("Which staff of a grand-staff chord sheet this voice is drawn on. Auto "
                    "picks treble or bass from the voice's range; Treble/Bass pins it."),
    'add_voice': "Add another voice to the ensemble (2 to 8 voices).",
    'remove_voice': "Remove this voice from the ensemble.",
    'max_spacing': ("Maximum semitone gap allowed between each pair of neighbouring voices; "
                    "comma-separated, one value per gap."),
    'allow_unisons': "Whether two neighbouring voices may land on the same pitch.",

    # Ensemble weights.
    'weight:movement': ("How the picker treats an inner or upper voice moving between chords "
                        "(a single number, or one per voice). More negative discourages "
                        "movement; positive would encourage it."),
    'weight:bass_movement': ("How the picker treats the bottom voice moving between chords, "
                             "normally set less negative than the inner-voice movement weight."),
    'weight:leap_penalty': ("How the picker treats a voice jumping more than a fifth between "
                            "chords. More negative avoids large leaps."),
    'weight:octave_leap_penalty': ("How the picker treats a voice jumping a full octave or more. "
                                   "More negative avoids octave leaps."),
    'weight:tritone_leap_penalty': ("How the picker treats a voice leaping exactly a tritone (six "
                                    "semitones). More negative avoids tritone leaps."),
    'weight:common_tone_bonus': ("How the picker treats a voice holding the pitch class it just "
                                 "sang. More positive rewards holding common tones."),
    'weight:parallel_perfect_penalty': ("How the picker treats a pair of voices moving in "
                                        "parallel fifths or octaves. More negative avoids them; "
                                        "set strongly negative by default."),
    'weight:contrary_motion_bonus': ("How the picker treats the outer two voices moving in "
                                     "opposite directions. More positive encourages it."),
    'weight:seventh_resolution_bonus': ("How the picker treats a chordal seventh resolving down "
                                        "by step. More positive encourages that resolution."),
    'weight:leading_tone_resolution_bonus': ("How the picker treats the leading tone resolving up "
                                             "to the tonic. More positive encourages it."),
    'weight:double_leading_tone_penalty': ("How the picker treats two voices doubling the leading "
                                           "tone. More negative avoids doubling it."),
    'weight:range_comfort_penalty': ("How the picker treats a voice sitting in the outer 2 "
                                     "semitones of its range. More negative keeps voices off "
                                     "their extremes."),
    'weight:unison_penalty': ("How the picker treats a pair of neighbouring voices on the same "
                              "pitch, when unisons are allowed. More negative avoids unisons."),
    'weight:upper_spacing_penalty': ("How the picker treats an upper-voice gap exceeding an "
                                     "octave. More negative favors closer spacing above the "
                                     "bass."),

    # Piano hands & range.
    'lh_range_low': "Lowest note the left hand may play (note name or MIDI number).",
    'lh_range_high': "Highest note the left hand may play (note name or MIDI number).",
    'rh_range_low': "Lowest note the right hand may play (note name or MIDI number).",
    'rh_range_high': "Highest note the right hand may play (note name or MIDI number).",
    'bass_range_low': ("Lowest note of the preferred bass register. Sitting below it costs "
                       "the bass-below-range weight per semitone."),
    'bass_range_high': ("Highest note of the preferred bass register. Sitting above it costs "
                        "the bass-above-range weight per semitone."),
    'rh_low_anchor_low': "Lowest note the right hand's lowest note is anchored within.",
    'rh_low_anchor_high': "Highest note the right hand's lowest note is anchored within.",
    'rh_center': ("Target for the right hand's mean pitch. Drifting from it costs the "
                 "right-hand center weight per semitone."),
    'rh_low_interval_floor': ("Right-hand close intervals sounding below this note are "
                             "considered muddy and cost the muddy-low-interval weight."),
    'hand_span': "Widest reach of one hand, in semitones (a ninth by default).",
    'max_notes_per_hand': "Most notes one hand may play at once.",
    'max_total_notes': "Most notes both hands may play together.",
    'hand_gap_floor': ("The right hand should clear the bass by more than this many "
                       "semitones, or it costs the hands-too-close weight."),
    'add_bass': "Whether to include the left-hand bass note at all.",

    # Piano weights.
    'weight:rh_note_bonus': ("How the picker treats a note kept in the right hand. More "
                             "positive favors fuller voicings; negative would favor sparser "
                             "ones."),
    'weight:rh_center_penalty': ("How the picker treats the right hand's mean pitch straying "
                                 "from its target center. More negative keeps it closer to "
                                 "center."),
    'weight:lh_below_bass_penalty': ("How the picker treats the bass sitting below the "
                                     "preferred bass range. More negative discourages a bass "
                                     "that's too low."),
    'weight:lh_above_bass_penalty': ("How the picker treats the bass sitting above the "
                                     "preferred bass range. More negative discourages a bass "
                                     "that's too high."),
    'weight:lh_double_penalty': ("How the picker treats octave-doubling the bass note. More "
                                 "negative avoids doubling it."),
    'weight:lh_double_low_penalty': ("How the picker treats an octave-doubled bass sitting "
                                     "below the preferred bass range, on top of the doubling "
                                     "weight. More negative avoids it."),
    'weight:rh_low_interval_penalty': ("How the picker treats a close right-hand interval "
                                       "sounding below the muddy-interval floor. More negative "
                                       "avoids muddy low intervals."),
    'weight:rh_wide_gap_penalty': ("How the picker treats an interior right-hand gap wider "
                                   "than an octave. More negative avoids wide gaps."),
    'weight:muddy_gap_penalty': ("How the picker treats the hands clearing each other by less "
                                 "than the hand gap floor. More negative keeps the hands "
                                 "apart."),
    'weight:piano_common_tone_bonus': ("How the picker treats a note holding the same pitch "
                                       "across a chord change. More positive rewards holding "
                                       "common tones."),
    'weight:piano_movement_penalty': ("How the picker treats a note's nearest-neighbour "
                                      "movement across a chord change, across the whole song. "
                                      "More negative steadies the voicing."),
}


def nested_tooltip(group: str, role: str) -> str:
    """Build a per-role tooltip for a nested-weight spinbox."""
    role_label = ROLE_LABELS.get(role, role).lower()
    if group == 'doubling':
        return (f"How much to favor doubling the {role_label} when there are more voices "
                f"than chord tones. Positive encourages it, negative avoids it.")
    if group == 'omit':
        return (f"How reluctant the picker is to drop the {role_label} when there are fewer "
                f"voices than chord tones. More negative keeps it; nearer zero allows "
                f"dropping it.")
    if group == 'inversion':
        return (f"How much to favor putting the {role_label} in the bass. Higher is more "
                f"preferred; 0 is neutral.")
    return f"{group} {role_label}"


def piano_weight_tooltip(key: str) -> str:
    """The help text of a flat piano weight (two keys share a name with other models)."""
    tip_key = PIANO_WEIGHT_TOOLTIP_OVERRIDES.get(key, f'weight:{key}')
    return TOOLTIPS.get(tip_key, key)
