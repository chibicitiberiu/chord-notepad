"""
Fretboard voicing model - chooses a fretted-instrument fingering for a chord.

Terminology: a *voicing* is a named configuration made of a *model* (the engine
that renders it) plus that model's parameters. This file is the **fretboard
model**: a spec-driven engine that voices chords on any fretted instrument
(guitar, ukulele, banjo, 7-string, ...) described as a :class:`FretboardSpec`
(``src/models/fretboard_spec.py``) -- its tuning (3-12 strings, re-entrant
allowed), physical limits (fret range, finger count, stretch), and the tunable
weights that steer the fingering search. Nothing about six-string guitar is
hard-coded; every constant the engine once carried now comes from the spec.

Rather than matching against a library of memorized chord shapes, the model
treats voicing as a pure optimization problem:

1. **Enumerate** every fingering whose strings only sound chord tones (plus the
   slash bass, if any), within a playable fret span (``spec.max_span``).
2. **Filter** on physical playability (finger count ``spec.fingers``, barre
   feasibility -- and, if ``spec.allow_barres`` is false, reject any fingering
   that would need a barre).
3. **Filter** on note coverage: prefer fingerings that spell the whole chord;
   fall back to partial voicings only for dense chords that cannot be held in
   full on the available strings. The required-tones floor auto-scales to the
   string count.
4. **Score** every survivor with a single weighted heuristic that rewards full,
   low, open voicings with the correct bass and penalizes stretches, barres,
   unstrummable interior mutes, and (mid-progression) movement of the fretting
   hand away from the previous shape. The reward/penalty values are the spec's
   weights (:data:`DEFAULT_WEIGHTS`), each a signed contribution the scorer adds
   directly: rewards are positive, penalties negative, higher score wins.
5. Return the highest-scoring fingering.

Enumeration is cached per chord (it depends only on the pitch classes involved);
scoring runs on every call because it depends on the mutable transition state.
The cache is per-instance, so the spec's identity is already baked into every
cache key -- two pickers with different specs never share a cache.

Re-entrant tunings (e.g. ukulele high-G, where the first string sounds *above*
the second) are fully supported: bass-note identification compares actual
sounding pitch (``tuning[string] + fret``), never string index, so the "bass"
is always the lowest-pitched sounding string. Interior-mute detection stays
string-order based, which is correct -- a strummer sweeps strings in order
regardless of their pitch.
"""

from typing import Any, Callable, Dict, List, Optional, Tuple, Set, Union, TYPE_CHECKING
from dataclasses import dataclass, asdict
from copy import deepcopy
import logging
from audio.note_picker_interface import INotePicker, VoicedChord
from audio.voicing_optimizer import optimize_sequence
from chord.midi_converter import parse_note_to_semitone
from models.fretboard_spec import FretboardSpec, BUILTIN_FRETBOARDS

if TYPE_CHECKING:
    from models.chord_notes import ChordNotes

logger = logging.getLogger(__name__)


@dataclass
class GuitarPickerState:
    """Immutable state object for guitar chord picker"""
    previous_fingering: Optional[List[int]] = None
    previous_chord_notes: Optional[List[str]] = None
    current_position: int = 0  # Average fret position
    position_context: Optional[int] = None  # Track general position on neck

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for serialization"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GuitarPickerState':
        """Create from dict"""
        return cls(**data)


class GuitarChordPicker(INotePicker):
    """Fretboard voicing model: optimizes fingerings for any fretted instrument.

    Driven by a :class:`FretboardSpec` (its tuning, physical limits, and tunable
    weights) rather than by six-string-guitar constants. The historical name is
    kept for import compatibility.
    """

    def __init__(self, tuning: Union[str, List[int], FretboardSpec] = 'standard') -> None:
        """Initialize the fretboard voicing model.

        Args:
            tuning: One of three forms:

                - a :class:`FretboardSpec` (the primary path): used directly.
                - a ``str`` fretboard name looked up in
                  :data:`BUILTIN_FRETBOARDS`; an unknown name logs a warning and
                  falls back to ``'standard'``.
                - a ``List[int]`` of open-string MIDI values (string order,
                  lowest string first): wrapped in an ad-hoc ``FretboardSpec``
                  with default limits/weights. The number of strings is
                  validated by the spec (3-12), replacing the old fixed-6 check.
        """

        # Resolve the incoming argument to a FretboardSpec.
        if isinstance(tuning, FretboardSpec):
            spec = tuning
        elif isinstance(tuning, str):
            spec = BUILTIN_FRETBOARDS.get(tuning)
            if spec is None:
                logger.warning(
                    "Unknown fretboard tuning %r; falling back to 'standard'", tuning)
                spec = BUILTIN_FRETBOARDS['standard']
        else:
            # Ad-hoc tuning provided as MIDI values; the spec enforces 3-12
            # strings and per-entry pitch validity.
            spec = FretboardSpec.from_dict('custom', {'tuning': list(tuning)})

        self.spec = spec

        # Tuning MIDI values (string order, lowest string first). Kept as a
        # public attribute for callers/tests that read it directly.
        self.tuning_midi: List[int] = list(spec.tuning)
        self._num_strings = len(self.tuning_midi)

        # Physical limits, resolved once from the spec.
        self._max_fret = spec.max_fret
        self._max_span = spec.max_span
        self._relaxed_span = spec.relaxed_span
        self._fingers = spec.fingers
        self._allow_barres = spec.allow_barres

        # Scoring weights, resolved once from the spec. Every value is a signed
        # contribution (see DEFAULT_WEIGHTS): rewards are positive, penalties
        # negative, and the scorer adds each one directly. Under default
        # weights this reproduces the old signed SCORE_* constants exactly.
        self._w_sounding = spec.weight('sounding_string_bonus')
        self._w_open = spec.weight('open_string_bonus')
        self._w_bass = spec.weight('bass_note_bonus')
        self._w_slash_bass = spec.weight('slash_bass_bonus')
        self._w_span = spec.weight('span_penalty')
        self._w_stretch = spec.weight('stretch_penalty')
        self._w_awkward = spec.weight('awkward_stretch_penalty')
        self._w_position = spec.weight('position_penalty')
        self._w_fretted = spec.weight('fretted_finger_penalty')
        self._w_barre = spec.weight('barre_penalty')
        self._w_interior_mute = spec.weight('interior_mute_penalty')
        self._w_movement = spec.weight('movement_penalty')
        self._w_kept = spec.weight('kept_finger_bonus')

        # Derive note names from MIDI values
        self.tuning_notes = [self._midi_to_note(midi) for midi in self.tuning_midi]

        # Initialize state
        self._state = GuitarPickerState()

        # Cache for enumerated candidate fingerings (keyed by chord pitch
        # classes). Per-instance, so the spec's identity is implicit in the
        # cache and never needs to be part of the key.
        self._fingering_cache: Dict[Tuple[Tuple[int, ...], Optional[int]], List[List[int]]] = {}

        # Pre-compute fret-to-note mapping for each string (used by the fallback)
        self._string_note_map = self._build_string_note_map()

    def _build_string_note_map(self) -> List[Dict[int, str]]:
        """Pre-compute which note each fret produces on each string"""
        string_maps = []

        for string_idx in range(self._num_strings):
            fret_map = {}
            for fret in range(self._max_fret + 1):
                midi = self.tuning_midi[string_idx] + fret
                note = self._midi_to_note(midi)
                fret_map[fret] = note  # Keep sharps/flats!
            string_maps.append(fret_map)

        return string_maps

    @staticmethod
    def _normalize_note(note: str) -> int:
        """Convert note to MIDI pitch class (0-11), accepting any enharmonic spelling.

        Falls back to 0 (C) only when the input is wholly unparseable, with a log warning,
        so callers never get silent corruption from missing dict entries.
        """
        semitone = parse_note_to_semitone(note)
        if semitone is None:
            logger.warning("Unparseable note name %r in guitar picker; falling back to C", note)
            return 0
        return semitone

    @staticmethod
    def _notes_match(note1: str, note2: str) -> bool:
        """Check if two notes are enharmonically equivalent"""
        return GuitarChordPicker._normalize_note(note1) == GuitarChordPicker._normalize_note(note2)

    @property
    def state(self) -> GuitarPickerState:
        """Get current state (returns a copy)"""
        return deepcopy(self._state)

    @state.setter
    def state(self, new_state: GuitarPickerState) -> None:
        """Set state (accepts a copy)"""
        self._state = deepcopy(new_state)

    def reset(self) -> None:
        """Reset to initial state"""
        self._state = GuitarPickerState()
        self._fingering_cache.clear()

    def chord_to_midi(self, chord_notes: 'ChordNotes') -> List[int]:
        """Convert chord to MIDI notes via guitar fingering"""

        # Extract notes from ChordNotes object
        notes = chord_notes.notes
        bass_note = chord_notes.bass_note

        if not notes:
            return []

        # Find best fingering
        fingering = self._find_best_fingering(notes, bass_note)

        # Convert fingering to MIDI notes
        midi_notes = self._fingering_to_midi(fingering)

        # Update state
        self._update_state(fingering, notes)

        return midi_notes

    def _find_best_fingering(self, chord_notes: List[str], bass_note: Optional[str] = None) -> List[int]:
        """Find the best playable fingering for the chord.

        Enumerates (and caches) all candidate fingerings, then scores each one
        against the current transition state and returns the argmax.
        """

        chord_pitch_classes = {self._normalize_note(n) for n in chord_notes}
        bass_pc = self._normalize_note(bass_note) if bass_note else None

        cache_key = (tuple(sorted(chord_pitch_classes)), bass_pc)

        candidates = self._fingering_cache.get(cache_key)
        if candidates is None:
            candidates = self._build_candidate_ladder(chord_notes, bass_note)
            self._fingering_cache[cache_key] = candidates

        if not candidates:
            logger.warning(f"No fingerings found for {chord_notes}, using fallback")
            return self._get_fallback_fingering(chord_notes[0])

        # max() returns the first argmax, so DFS order breaks ties deterministically.
        return max(candidates, key=lambda f: self._score_fingering(f, chord_notes, bass_note))

    def _build_candidate_ladder(self, chord_notes: List[str],
                                bass_note: Optional[str]) -> List[List[int]]:
        """Enumerate candidate fingerings, relaxing constraints stepwise.

        The normal pass (span <= ``max_span``, default coverage rules) handles
        the overwhelming majority of chords. Only when it yields nothing do we
        walk down the ladder, each step running solely if the previous produced
        no candidates:

        1. Normal: span <= ``spec.max_span`` with the default coverage rules.
        2. Wide stretch: span <= ``spec.relaxed_span``, same coverage rules.
        3. Wide stretch plus relaxed coverage: require ``num_unique - 1`` chord
           tones, then ``- 2``, ... down to 1, returning the first non-empty
           level (a triad thus degrades to two chord tones rather than one).

        The lone-root fallback in :meth:`_get_fallback_fingering` remains the
        absolute last resort, applied by the caller when this returns nothing.
        The whole ladder cost is paid once per chord because the caller caches
        the result.
        """

        # Step 1: normal pass.
        candidates = self._enumerate_candidates(chord_notes, bass_note,
                                                max_span=self._max_span)
        if candidates:
            return candidates

        # Step 2: allow a wider stretch, keep the default coverage rules.
        candidates = self._enumerate_candidates(chord_notes, bass_note,
                                                max_span=self._relaxed_span)
        if candidates:
            logger.info("Fretboard voicing for %s used relaxed ladder step 2 "
                        "(wide stretch, span <= %d)", chord_notes, self._relaxed_span)
            return candidates

        # Step 3: keep the wide stretch and relax coverage one tone at a time.
        num_unique = len({self._normalize_note(n) for n in chord_notes})
        for min_present in range(num_unique - 1, 0, -1):
            candidates = self._enumerate_candidates(
                chord_notes, bass_note,
                max_span=self._relaxed_span, min_present_override=min_present)
            if candidates:
                logger.warning("Fretboard voicing for %s used relaxed ladder step 3 "
                               "(span <= %d, require %d of %d chord tones)",
                               chord_notes, self._relaxed_span, min_present, num_unique)
                return candidates

        return []

    def _enumerate_candidates(self, chord_notes: List[str],
                              bass_note: Optional[str],
                              max_span: Optional[int] = None,
                              min_present_override: Optional[int] = None) -> List[List[int]]:
        """Enumerate all playable candidate fingerings for the chord.

        Walks every combination of per-string fret options (mute plus any fret
        whose pitch class is a chord tone or the slash bass), pruning branches
        that exceed ``max_span``. Complete voicings (every chord tone present)
        are preferred; partial voicings are returned only when no complete
        voicing exists.

        Args:
            chord_notes: The chord tones (note names).
            bass_note: Optional slash-bass note name.
            max_span: Widest fret stretch allowed. Defaults to ``spec.max_span``.
            min_present_override: If given, overrides the minimum number of
                chord tones a candidate must cover to be kept. Used by the
                relaxation ladder to accept sparser voicings.
        """

        if max_span is None:
            max_span = self._max_span

        num_strings = self._num_strings

        chord_pcs = {self._normalize_note(n) for n in chord_notes}
        bass_pc = self._normalize_note(bass_note) if bass_note else None

        allowed = set(chord_pcs)
        if bass_pc is not None:
            allowed.add(bass_pc)

        # Slash bass notes that are not chord tones do not count toward coverage.
        num_unique = len(chord_pcs)
        pc_bit = {pc: i for i, pc in enumerate(chord_pcs)}

        # Minimum number of chord tones a candidate must cover to be kept at all
        # (complete or partial). Anything below this is pruned during the DFS.
        if num_unique <= 3:
            min_present = num_unique
        elif num_unique <= 5:
            min_present = num_unique - 1
        else:
            min_present = 4

        # Auto-scale the coverage floor to the instrument: a chord can never
        # cover more distinct tones than there are strings. On >=6-string
        # instruments this clamp is a no-op (the floor never exceeds 4); on
        # fewer strings it lets, e.g., a 4-string instrument voice a 5-tone
        # chord through the normal pass instead of always hitting the ladder.
        min_present = min(min_present, num_strings)

        # The ladder can force a sparser coverage floor (clamped to the chord).
        if min_present_override is not None:
            min_present = max(1, min(min_present_override, num_unique))

        max_fret = self._max_fret
        tuning = self.tuning_midi
        fingers = self._fingers
        allow_barres = self._allow_barres

        # Per-string options as (fret, coverage_bit) tuples. Mute is (-1, 0).
        string_options: List[List[Tuple[int, int]]] = []
        for string_idx in range(num_strings):
            base = tuning[string_idx]
            opts: List[Tuple[int, int]] = [(-1, 0)]
            for fret in range(0, max_fret + 1):
                pc = (base + fret) % 12
                if pc in allowed:
                    opts.append((fret, 1 << pc_bit[pc] if pc in pc_bit else 0))
            string_options.append(opts)

        # Suffix union of coverage bits still reachable from string_idx onward,
        # used to prune branches that can never cover enough chord tones.
        reachable = [0] * (num_strings + 1)
        for string_idx in range(num_strings - 1, -1, -1):
            bits = reachable[string_idx + 1]
            for _, bit in string_options[string_idx]:
                bits |= bit
            reachable[string_idx] = bits

        complete: List[List[int]] = []
        partial: List[List[int]] = []
        buf = [0] * num_strings

        def dfs(string_idx: int, min_f: int, max_f: int, mask: int,
                n_sound: int, n_fret: int) -> None:
            # Coverage prune: even sounding every remaining string cannot reach
            # the minimum number of chord tones required.
            if (mask | reachable[string_idx]).bit_count() < min_present:
                return

            if string_idx == num_strings:
                if n_sound == 0:
                    return

                # Playability: more fretted strings than fingers need a feasible
                # barre (one flat finger across the lowest-fret strings, leaving
                # at most fingers-1 fingers for strings above it).
                if n_fret > fingers:
                    if not allow_barres:
                        return
                    lo = hi = -1
                    above = 0
                    for s in range(num_strings):
                        fs = buf[s]
                        if fs == min_f:
                            if lo == -1:
                                lo = s
                            hi = s
                        elif fs > min_f:
                            above += 1
                    if above > fingers - 1:
                        return
                    # No open string may sit inside the barre's string range.
                    for s in range(lo, hi + 1):
                        if buf[s] == 0:
                            return

                present = mask.bit_count()
                if present == num_unique:
                    complete.append(buf[:])
                elif present >= min_present:
                    partial.append(buf[:])
                return

            for fret, bit in string_options[string_idx]:
                if fret > 0:
                    nmin = fret if fret < min_f else min_f
                    nmax = fret if fret > max_f else max_f
                    if nmax - nmin > max_span:
                        continue
                    buf[string_idx] = fret
                    dfs(string_idx + 1, nmin, nmax, mask | bit, n_sound + 1, n_fret + 1)
                elif fret == 0:
                    buf[string_idx] = 0
                    dfs(string_idx + 1, min_f, max_f, mask | bit, n_sound + 1, n_fret)
                else:  # mute
                    buf[string_idx] = -1
                    dfs(string_idx + 1, min_f, max_f, mask, n_sound, n_fret)

        # Sentinels chosen so the first fretted string always sets both bounds.
        dfs(0, max_fret + 1, 0, 0, 0, 0)

        return complete if complete else partial

    def _is_playable(self, fingering: Union[List[int], Tuple[int, ...]]) -> bool:
        """Check if a fingering is physically playable.

        Up to ``spec.fingers`` fretted strings each get a finger. More than that
        requires a barre: one finger lies flat across the strings fretted at the
        lowest fret, covering the contiguous range they span. Any open string
        inside that range cannot ring, and the strings fretted above the barre
        still need separate fingers (at most ``spec.fingers - 1`` of them). When
        the spec forbids barres, any fingering that would need one is unplayable.
        """

        fretted = [(s, f) for s, f in enumerate(fingering) if f > 0]
        if not fretted:
            return True

        frets = [f for _, f in fretted]
        if max(frets) - min(frets) > self._max_span:
            return False

        if len(fretted) <= self._fingers:
            return True

        if not self._allow_barres:
            return False

        # Barre required: the flat finger sits at the lowest fretted fret.
        f_min = min(frets)
        barre_strings = [s for s, f in fretted if f == f_min]
        lo, hi = min(barre_strings), max(barre_strings)

        for s in range(lo, hi + 1):
            if fingering[s] == 0:  # open string trapped under the barre
                return False

        above = sum(1 for _, f in fretted if f > f_min)
        return above <= self._fingers - 1

    def _is_clean_lengthwise_stretch(self, fingering: List[int],
                                     fretted: List[int]) -> bool:
        """Whether a wide shape is a clean lengthwise (index<->pinky) reach.

        A hand can span three frets comfortably only when a single *outer*
        finger does the reaching while the others stay anchored together. This
        returns ``True`` when all three hold:

        1. exactly one fretted string sits at the far (highest) fret -- one
           finger makes the stretch, not two;
        2. that far string is the lowest- or highest-*indexed* fretted string
           (an outer finger, i.e. index or pinky, takes the reach) rather than
           an interior one (which would force a middle finger to stretch);
        3. every other fretted note lies within ``[min, min + 1]`` -- the
           anchoring fingers stay compact instead of also splaying.

        The reported unplayable B, ``x-2-1-4-0-2``, fails (2): its far note
        (fret 4) sits on an interior string while strings on both sides are also
        fretted. A true index<->pinky reach such as a single fret-4 note on the
        outermost fretted string passes.

        Args:
            fingering: The per-string fret list (mute ``-1``, open ``0``).
            fretted: The indices of the fretted strings (``fingering[s] > 0``),
                as gathered by the caller.

        Returns:
            ``True`` if the shape is a clean lengthwise reach; ``False`` if an
            inner finger would have to make the stretch.
        """
        fret_vals = [fingering[s] for s in fretted]
        lo, hi = min(fret_vals), max(fret_vals)

        far_strings = [s for s in fretted if fingering[s] == hi]
        if len(far_strings) != 1:
            return False
        far = far_strings[0]
        if far != min(fretted) and far != max(fretted):
            return False
        return all(fingering[s] <= lo + 1 for s in fretted if s != far)

    def _score_fingering(self, fingering: List[int], chord_notes: List[str],
                         bass_note: Optional[str]) -> float:
        """Score a fingering against the current transition state; higher is better.

        The greedy (click-to-play / streaming) path: intrinsic quality plus the
        transition cost relative to ``self._state.previous_fingering``. Kept as
        the sum of the two split scorers so that both the greedy path and the
        whole-song optimizer share exactly the same weights.
        """

        return (self._score_quality(fingering, chord_notes, bass_note)
                + self._score_transition(self._state.previous_fingering, fingering))

    def _score_quality(self, fingering: List[int], chord_notes: List[str],
                       bass_note: Optional[str]) -> float:
        """Intrinsic quality of a fingering in isolation; higher is better.

        Rewards full, low, open voicings with the correct bass note and
        penalizes wide stretches, barres, and interior mutes. Carries no
        transition (previous-shape) term -- that lives in
        :meth:`_score_transition` so the whole-song optimizer can weigh the two
        independently.
        """

        tuning = self.tuning_midi

        sounding = [s for s in range(self._num_strings) if fingering[s] >= 0]
        if not sounding:
            # An all-muted fingering (only reachable via a degenerate fallback)
            # sounds nothing; rank it below any real voicing.
            return float('-inf')
        fretted = [s for s in sounding if fingering[s] > 0]

        score = self._w_sounding * len(sounding)
        score += self._w_open * sum(1 for s in sounding if fingering[s] == 0)

        # Bass term: reward/penalize whether the lowest sounding note matches the
        # target bass. A true slash bass matters more than a plain root bass.
        # The bass is the lowest sounding *pitch* (tuning + fret), never the
        # lowest string index -- correct for re-entrant tunings.
        target_pc = self._normalize_note(bass_note) if bass_note else None
        if target_pc is not None:
            is_slash = not self._notes_match(bass_note, chord_notes[0])
            weight = self._w_slash_bass if is_slash else self._w_bass
            lowest_string = min(sounding, key=lambda s: tuning[s] + fingering[s])
            lowest_pc = (tuning[lowest_string] + fingering[lowest_string]) % 12
            score += weight if lowest_pc == target_pc else -weight

        if fretted:
            fret_vals = [fingering[s] for s in fretted]
            span = max(fret_vals) - min(fret_vals)
            avg_fret = sum(fret_vals) / len(fret_vals)
            score += self._w_span * span
            score += self._w_position * avg_fret
            score += self._w_fretted * len(fretted)
            if len(fretted) > self._fingers:
                score += self._w_barre
            # Whole-shape stretch cost: free up to a one-fret span, then per fret.
            score += self._w_stretch * max(0, span - 1)
            # Middle-finger cost: a span-3 shape that is not a clean lengthwise
            # (index<->pinky) reach forces an inner finger to make the far
            # stretch, which no hand can hold. Charged on top of the mild,
            # sign-agnostic stretch cost above.
            if span == 3 and not self._is_clean_lengthwise_stretch(fingering, fretted):
                score += self._w_awkward

        # Interior mutes: muted strings between the first and last sounding
        # string cannot be avoided while strumming. String-order based, which is
        # correct: a strummer sweeps strings in order regardless of their pitch.
        first, last = sounding[0], sounding[-1]
        interior_mutes = sum(1 for s in range(first + 1, last) if fingering[s] == -1)
        score += self._w_interior_mute * interior_mutes

        return score

    def _score_transition(self, prev_fingering: Optional[List[int]],
                          fingering: List[int]) -> float:
        """Transition cost of moving to ``fingering`` from ``prev_fingering``.

        Penalizes fretting-hand movement and rewards fingers left in place. When
        there is no previous fingering (start of a sequence) the transition cost
        is zero.
        """

        if not prev_fingering:
            return 0.0

        movement = abs(self._get_position(fingering) - self._get_position(prev_fingering))
        score = self._w_movement * movement
        kept = sum(1 for s in range(self._num_strings)
                   if fingering[s] == prev_fingering[s] and fingering[s] > 0)
        score += self._w_kept * kept
        return score

    def voice_sequence(self, sequence: List['ChordNotes'],
                       should_abort: Optional[Callable[[], bool]] = None) -> List[List[int]]:
        """Voice a whole song at once, optimizing transitions with lookahead.

        Thin wrapper over :meth:`voice_sequence_details`: it runs the same
        whole-song optimization and returns just the MIDI-note lists, discarding
        the per-chord fingerings. The two therefore always agree.
        """

        return [vc.midi_notes
                for vc in self.voice_sequence_details(sequence, should_abort=should_abort)]

    def voice_sequence_details(self, sequence: List['ChordNotes'],
                              should_abort: Optional[Callable[[], bool]] = None) -> List[VoicedChord]:
        """Voice a whole song at once, keeping each chord's winning fingering.

        Instead of greedily choosing each chord's shape against only the
        previous one, this gathers every chord's candidate fingerings and runs a
        beam-pruned Viterbi DP (:func:`optimize_sequence`) that maximizes the sum
        of intrinsic quality (:meth:`_score_quality`) plus voice-leading
        transitions (:meth:`_score_transition`) across the entire sequence. A
        locally weaker shape is accepted when it makes the rest of the song flow
        more smoothly.

        Each returned :class:`VoicedChord` carries both the voiced MIDI notes
        and the chosen fingering (per-string fret list; see
        :attr:`VoicedChord.fingering`).

        Deterministic by construction: it resets first and the DP breaks ties by
        candidate order, so the same sequence always yields the same voicings.
        """

        candidate_sets, chosen, _unary, _transition = self._optimize_sequence(
            sequence, should_abort=should_abort)
        result: List[VoicedChord] = []
        for pos, idx in enumerate(chosen):
            fingering = candidate_sets[pos][idx]
            result.append(VoicedChord(
                midi_notes=self._fingering_to_midi(fingering),
                fingering=list(fingering),
            ))
        return result

    def voice_sequence_score(self, sequence: List['ChordNotes'],
                            should_abort: Optional[Callable[[], bool]] = None) -> float:
        """Total score of the winning whole-song path for ``sequence``.

        Runs the exact same candidate enumeration and beam-Viterbi search as
        :meth:`voice_sequence_details` (both delegate to
        :meth:`_optimize_sequence`), then sums the score the DP maximized for
        the path it chose: each chosen candidate's unary (intrinsic-quality)
        score plus the transition score between consecutive chosen candidates.
        Because it reuses the same code paths, the score can never disagree
        with the fingerings :meth:`voice_sequence_details` returns.

        This is the playability figure the capo advisor
        (:mod:`services.capo_advisor`) compares across capo positions: raising
        the tuning changes the enumerated shapes, and the weighted score --
        driven chiefly by ``open_string_bonus``, ``position_penalty`` and
        ``barre_penalty`` -- reflects how much easier the song is to play.

        Args:
            sequence: The chords to voice, in playback order.

        Returns:
            The summed unary + transition score of the chosen path, or ``0.0``
            for an empty sequence.
        """
        candidate_sets, chosen, unary, transition = self._optimize_sequence(
            sequence, should_abort=should_abort)
        total = 0.0
        prev_fingering: Optional[List[int]] = None
        for pos, idx in enumerate(chosen):
            fingering = candidate_sets[pos][idx]
            total += unary(pos, fingering)
            if prev_fingering is not None:
                total += transition(prev_fingering, fingering)
            prev_fingering = fingering
        return total

    def _optimize_sequence(
        self, sequence: List['ChordNotes'],
        should_abort: Optional[Callable[[], bool]] = None,
    ) -> Tuple[List[List[List[int]]], List[int], Any, Any]:
        """Shared whole-song enumeration + beam-Viterbi search.

        Resets the picker, gathers every chord's candidate fingerings, and runs
        :func:`optimize_sequence` over them with the unary/transition scoring
        callbacks. Both :meth:`voice_sequence_details` (which turns the choice
        into voiced notes + fingerings) and :meth:`voice_sequence_score` (which
        sums the chosen path's score) build on this single method so the two can
        never diverge.

        Returns:
            A ``(candidate_sets, chosen, unary, transition)`` tuple:
            ``candidate_sets[pos]`` is the (original, unpruned) candidate list
            for position ``pos``, ``chosen[pos]`` indexes into it, and ``unary``
            /``transition`` are the exact scoring closures the DP used.
        """
        self.reset()

        # Per position: the candidate fingerings and the (notes, bass) needed to
        # score them. Empty-candidate chords fall back to a single-candidate set
        # so the DP always has something to choose and never raises.
        candidate_sets: List[List[List[int]]] = []
        chord_data: List[Tuple[List[str], Optional[str]]] = []
        for chord_notes in sequence:
            notes = chord_notes.notes
            bass_note = chord_notes.bass_note
            chord_data.append((notes, bass_note))

            if not notes:
                candidate_sets.append([[-1] * self._num_strings])
                continue

            chord_pcs = {self._normalize_note(n) for n in notes}
            bass_pc = self._normalize_note(bass_note) if bass_note else None
            cache_key = (tuple(sorted(chord_pcs)), bass_pc)

            candidates = self._fingering_cache.get(cache_key)
            if candidates is None:
                candidates = self._build_candidate_ladder(notes, bass_note)
                self._fingering_cache[cache_key] = candidates
            if not candidates:
                logger.warning(f"No fingerings found for {notes}, using fallback")
                candidates = [self._get_fallback_fingering(notes[0])]
            candidate_sets.append(candidates)

        def unary(position: int, fingering: List[int]) -> float:
            notes, bass_note = chord_data[position]
            if not notes:
                return 0.0
            return self._score_quality(fingering, notes, bass_note)

        def transition(prev_fingering: List[int], fingering: List[int]) -> float:
            return self._score_transition(prev_fingering, fingering)

        chosen = optimize_sequence(
            candidate_sets, unary, transition, beam_width=20, prune_to=30,
            should_abort=should_abort,
        )
        return candidate_sets, chosen, unary, transition

    def _get_position(self, fingering: List[int]) -> float:
        """Get average position"""

        fretted = [f for f in fingering if f > 0]
        return sum(fretted) / len(fretted) if fretted else 0

    def _fingering_to_midi(self, fingering: List[int]) -> List[int]:
        """Convert fingering to MIDI notes"""

        midi_notes = []

        for string_idx, fret in enumerate(fingering):
            if fret >= 0:
                midi = self.tuning_midi[string_idx] + fret
                midi_notes.append(midi)

        return sorted(midi_notes)

    def _midi_to_note(self, midi: int) -> str:
        """Convert MIDI to note name"""

        note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        return note_names[midi % 12]

    def _get_fallback_fingering(self, root_note: str) -> List[int]:
        """Simple fallback - just play the root note"""

        # Try to find the root on the lowest few strings using enharmonic
        # matching. Capped at 3 strings (or fewer for tiny instruments) to keep
        # the fallback bass low.
        for string_idx in range(min(3, self._num_strings)):
            for fret in range(self._max_fret + 1):  # Check all frets
                note = self._string_note_map[string_idx][fret]
                if self._notes_match(note, root_note):
                    fingering = [-1] * self._num_strings
                    fingering[string_idx] = fret
                    # Just play the root, don't add anything else
                    return fingering

        # Last resort: mute everything
        return [-1] * self._num_strings

    def _update_state(self, fingering: List[int], chord_notes: List[str]) -> None:
        """Update state after playing"""

        self._state.previous_fingering = fingering
        self._state.previous_chord_notes = chord_notes
        self._state.current_position = int(self._get_position(fingering))

        if fingering:
            fretted = [f for f in fingering if f > 0]
            if fretted:
                self._state.position_context = max(fretted)
