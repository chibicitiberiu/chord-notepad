"""Piano chord picker - chooses a two-hand keyboard voicing for a chord.

Like the guitar picker, this treats voicing as an optimization problem rather
than applying a rigid, register-preserving template:

1. **Enumerate** two-hand voicings: a left hand playing the bass (single or
   octave-doubled, low register) and a right hand playing a chord-tone voicing
   (root position + inversions, at a few anchor octaves, with tone-omission
   variants for dense chords). Extensions (9th/11th/13th) are always stacked
   above the core tones - the register-preserving principle the old picker
   embodied, kept while dropping its rigidity.
2. **Hard-filter** on the physical model: at most five notes per hand, a span of
   at most a ninth (:data:`HAND_SPAN_SEMITONES`) per hand, everything inside the
   playable range, and the right hand strictly above the left (no hand crossing,
   which also guarantees no duplicated key).
3. **Score** every survivor with :meth:`_score_quality` (completeness, right-hand
   register centering, left-hand register preference, low-interval and spacing
   sanity) plus :meth:`_score_transition` (nearest-neighbour voice leading with a
   common-tone reward).
4. **Optimize**: :meth:`chord_to_midi` greedily picks the argmax against the
   previous chord; :meth:`voice_sequence` runs the whole-song beam DP so the
   register stays stable across loops instead of drifting.

Enumeration is cached per chord signature (root pitch class + intervals + bass
pitch class); scoring runs every call because it depends on the mutable
transition state.
"""

from typing import Any, Dict, List, NamedTuple, Optional, Tuple, TYPE_CHECKING
from dataclasses import dataclass, asdict
from copy import deepcopy
import logging

from audio.note_picker_interface import INotePicker
from audio.voicing_optimizer import optimize_sequence
from chord.midi_converter import parse_note_to_semitone, intervals_from_note_names

if TYPE_CHECKING:
    from models.chord_notes import ChordNotes

logger = logging.getLogger(__name__)


class Voicing(NamedTuple):
    """A two-hand keyboard voicing: left hand (bass) and right hand (chord).

    Both are sorted-ascending tuples of MIDI note numbers. The combined MIDI
    list is ``sorted(lh + rh)``; by construction the right hand sits strictly
    above the left, so the two never share a key.
    """
    lh: Tuple[int, ...]
    rh: Tuple[int, ...]


@dataclass
class ChordPickerState:
    """Immutable state object for the piano chord picker."""
    previous_chord_midi: Optional[List[int]] = None
    previous_chord_notes: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for serialization"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChordPickerState':
        """Create from dict"""
        return cls(**data)


class ChordNotePicker(INotePicker):
    """Picks MIDI notes for chords with a playable two-hand voicing model."""

    # --- Physical model (a pianist's two hands) -------------------------------
    HAND_SPAN_SEMITONES = 14   # widest reach of one hand (a ninth); tunable
    MAX_NOTES_PER_HAND = 5     # five fingers per hand
    MAX_TOTAL_NOTES = 10       # both hands together

    # Registers (MIDI). Left hand lives low, right hand around/above middle C.
    LH_MIN = 24                # C1
    LH_MAX = 48                # C3
    LH_OCTAVE2_LOW = 36        # C2 - preferred bass octave, lower edge
    LH_OCTAVE2_HIGH = 47       # B2 - preferred bass octave, upper edge
    RH_MIN = 48                # C3
    RH_MAX = 84                # C6
    RH_LOW_ANCHOR_MIN = 48     # lowest right-hand note anchored no lower than C3
    RH_LOW_ANCHOR_MAX = 64     # ...and no higher than E4, so voicings stay central
    RH_IDEAL_CENTER = 63.0     # right-hand mean gravitates here (~Eb4)
    RH_LOW_INTERVAL_FLOOR = 52  # close intervals below ~E3 sound muddy

    # --- Scoring weights (higher score = better). All tunable. ----------------
    # Completeness: penalty (subtracted) for each chord tone missing from the
    # whole voicing, keyed by the tone's harmonic role. The bass covers the root,
    # so an omitted root is cheap; the third, seventh and colour tones define the
    # chord and are effectively never dropped.
    OMIT_PENALTY = {
        'root': 4.0,
        'third': 40.0,
        'fifth': 8.0,
        'seventh': 40.0,
        'color': 30.0,
        'extension': 7.0,
    }
    SCORE_PER_RH_NOTE = 0.6       # reward per right-hand note (favour full voicings)
    SCORE_CENTER = -1.4            # per semitone of right-hand mean from ideal
    SCORE_LH_BELOW_OCT2 = -1.5    # per semitone the bass sits below C2
    SCORE_LH_ABOVE_OCT2 = -1.5    # per semitone the bass sits above B2
    SCORE_LH_DOUBLE = -1.0        # applied once when the bass is octave-doubled
    SCORE_LH_DOUBLE_LOW = -1.0    # per semitone an octave-doubled bass sits below C2
    SCORE_RH_LOW_INTERVAL = -2.0  # per close (<=4 st) right-hand interval sounding low
    SCORE_RH_WIDE_GAP = -0.6      # per interior right-hand gap wider than an octave
    SCORE_MUDDY_GAP = -1.5        # per semitone the hand gap is below the clearance floor
    HAND_GAP_FLOOR = 2            # right hand should clear the bass by more than this

    # Transition (voice leading): rewards common tones, penalizes movement. Kept
    # small so quality dominates and transitions only break ties.
    SCORE_COMMON_TONE = 1.5       # per right-hand-ish common tone held
    SCORE_PER_MOVE = -0.35        # per semitone of nearest-neighbour movement

    def __init__(self, chord_octave: int = 3, bass_octave: int = 2, add_bass: bool = True) -> None:
        """Initialize the piano chord picker.

        Args:
            chord_octave: Retained for backward compatibility (the register is
                now chosen by scoring, not a fixed octave).
            bass_octave: Retained for backward compatibility.
            add_bass: Whether to include the left-hand bass note (default True).
        """
        self.chord_octave = chord_octave
        self.bass_octave = bass_octave
        self.add_bass = add_bass
        self._state = ChordPickerState()

        # Cache of enumerated candidate voicings, keyed by chord signature.
        self._voicing_cache: Dict[Tuple[int, Tuple[int, ...], Optional[int]], List[Voicing]] = {}

    # ------------------------------------------------------------------
    # State API (mirrors the guitar picker)
    # ------------------------------------------------------------------
    @property
    def state(self) -> ChordPickerState:
        """Get current state (returns a copy to prevent external modification)."""
        return deepcopy(self._state)

    @state.setter
    def state(self, new_state: ChordPickerState) -> None:
        """Set state (accepts a copy to prevent external references)."""
        self._state = deepcopy(new_state)

    def reset(self) -> None:
        """Reset to initial state."""
        self._state = ChordPickerState()
        self._voicing_cache.clear()

    # ------------------------------------------------------------------
    # Public conversion
    # ------------------------------------------------------------------
    def chord_to_midi(self, chord_notes: 'ChordNotes') -> List[int]:
        """Convert a chord to MIDI notes, greedily against the previous chord.

        Args:
            chord_notes: ChordNotes with notes, bass_note, root and (optionally)
                register-preserving intervals.

        Returns:
            Sorted list of MIDI note numbers (bass first).
        """
        notes = chord_notes.notes
        if not notes:
            return []

        candidates = self._get_candidates(chord_notes)

        best = max(
            candidates,
            key=lambda v: (self._score_quality(v, chord_notes)
                           + self._score_transition(self._state.previous_chord_midi,
                                                    self._voicing_to_midi(v))),
        )
        midi = self._voicing_to_midi(best)
        self._update_state(midi, notes)
        return midi

    def voice_sequence(self, sequence: List['ChordNotes']) -> List[List[int]]:
        """Voice a whole song at once, optimizing transitions with lookahead.

        Gathers each chord's candidate voicings and runs the beam-pruned Viterbi
        DP (:func:`optimize_sequence`) that maximizes intrinsic quality plus
        voice-leading transitions across the entire song. This is what keeps the
        right hand in a stable central register across loop repeats instead of
        drifting the way a purely greedy pass does.

        Deterministic: it resets first and the DP breaks ties by candidate order,
        so the same sequence always yields the same voicings.
        """
        self.reset()
        if not sequence:
            return []

        candidate_sets: List[List[Voicing]] = []
        for chord_notes in sequence:
            if not chord_notes.notes:
                # An empty chord contributes a single silent candidate so the DP
                # always has something to choose and never raises.
                candidate_sets.append([Voicing((), ())])
                continue
            candidate_sets.append(self._get_candidates(chord_notes))

        def unary(position: int, voicing: Voicing) -> float:
            chord_notes = sequence[position]
            if not chord_notes.notes:
                return 0.0
            return self._score_quality(voicing, chord_notes)

        def transition(prev: Voicing, cur: Voicing) -> float:
            return self._score_transition(self._voicing_to_midi(prev),
                                          self._voicing_to_midi(cur))

        chosen = optimize_sequence(
            candidate_sets, unary, transition, beam_width=20, prune_to=30
        )
        return [self._voicing_to_midi(candidate_sets[pos][idx])
                for pos, idx in enumerate(chosen)]

    # ------------------------------------------------------------------
    # Candidate enumeration
    # ------------------------------------------------------------------
    def _get_candidates(self, chord_notes: 'ChordNotes') -> List[Voicing]:
        """Return (cached) candidate voicings for a chord.

        Always returns at least one voicing: a degenerate clamped block is used
        as a last resort so odd chords (single-note, dense, unresolvable) still
        produce something.
        """
        root_pc, intervals, bass_pc = self._chord_signature(chord_notes)
        key = (root_pc, tuple(intervals), bass_pc)

        cached = self._voicing_cache.get(key)
        if cached is not None:
            return cached

        candidates = self._generate_candidates(root_pc, intervals, bass_pc)
        if not candidates:
            candidates = [self._fallback_voicing(root_pc, intervals, bass_pc)]
        self._voicing_cache[key] = candidates
        return candidates

    @staticmethod
    def _chord_signature(chord_notes: 'ChordNotes') -> Tuple[int, List[int], Optional[int]]:
        """Extract (root pitch class, register-preserving intervals, bass pc)."""
        notes = chord_notes.notes
        root_name = chord_notes.root or notes[0]
        root_pc = parse_note_to_semitone(root_name)
        if root_pc is None:
            root_pc = 0

        intervals = chord_notes.intervals
        if not intervals or len(intervals) != len(notes):
            intervals = intervals_from_note_names(notes)
        if not intervals:
            intervals = [0]

        bass_name = chord_notes.bass_note or root_name
        bass_pc = parse_note_to_semitone(bass_name)
        if bass_pc is None:
            bass_pc = root_pc
        return root_pc, list(intervals), bass_pc

    @staticmethod
    def _role(interval: int) -> str:
        """Classify a chord tone by its register-preserving interval."""
        if interval >= 12:
            return 'extension'
        m = interval % 12
        if m == 0:
            return 'root'
        if m in (3, 4):
            return 'third'
        if m in (10, 11):
            return 'seventh'
        if m in (6, 7, 8):
            return 'fifth'
        return 'color'  # sus2/sus4/6th and other defining colour tones

    def _generate_candidates(self, root_pc: int, intervals: List[int],
                             bass_pc: Optional[int]) -> List[Voicing]:
        """Enumerate all playable two-hand voicings passing the hard filters."""

        # Partition chord tones into core (below the octave) and extensions.
        core: List[Tuple[int, str]] = []   # (pitch class, role), stacking order
        exts: List[int] = []               # extension pitch classes, low->high
        seen_core_pc = set()
        for interval in intervals:
            role = self._role(interval)
            pc = (root_pc + interval) % 12
            if role == 'extension':
                exts.append(pc)
            elif pc not in seen_core_pc:
                seen_core_pc.add(pc)
                core.append((pc, role))
        if not core:
            # Degenerate (all tones marked as extensions): fold the lowest down.
            core.append((exts.pop(0) if exts else root_pc, 'root'))

        left_hands = self._enumerate_left_hands(bass_pc)
        right_hands = self._enumerate_right_hands(core, exts)

        candidates: List[Voicing] = []
        seen: set = set()
        for rh in right_hands:
            rh_low = rh[0]
            for lh in left_hands:
                if lh and max(lh) >= rh_low:
                    continue  # hard reject: no hand crossing / no shared key
                if len(lh) + len(rh) > self.MAX_TOTAL_NOTES:
                    continue
                voicing = Voicing(lh, rh)
                dedupe_key = (lh, rh)
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                candidates.append(voicing)
        return candidates

    def _enumerate_left_hands(self, bass_pc: Optional[int]) -> List[Tuple[int, ...]]:
        """Enumerate left-hand bass placements (single and octave-doubled)."""
        if bass_pc is None or not self.add_bass:
            return [()]

        singles = [m for m in range(self.LH_MIN, self.LH_MAX + 1) if m % 12 == bass_pc]
        hands: List[Tuple[int, ...]] = [(m,) for m in singles]
        # Octave doubling: two notes an octave apart, both inside the LH range.
        for m in singles:
            if self.LH_MIN <= m and m + 12 <= self.LH_MAX:
                hands.append((m, m + 12))
        if not hands:
            hands = [()]
        return hands

    def _enumerate_right_hands(self, core: List[Tuple[int, str]],
                               exts: List[int]) -> List[Tuple[int, ...]]:
        """Enumerate right-hand chord-tone voicings across inversions/anchors."""
        results: List[Tuple[int, ...]] = []
        seen: set = set()

        n = len(core)
        for inv in range(n):
            order = core[inv:] + core[:inv]  # rotate: this tone becomes the bass
            low_pc = order[0][0]
            anchors = [m for m in range(self.RH_LOW_ANCHOR_MIN, self.RH_LOW_ANCHOR_MAX + 1)
                       if m % 12 == low_pc]
            for anchor in anchors:
                for core_kept in self._core_reductions(order):
                    rh = self._stack_right_hand(core_kept, exts, anchor)
                    if rh is None:
                        continue
                    key = tuple(rh)
                    if key in seen:
                        continue
                    seen.add(key)
                    results.append(key)
        return results

    def _core_reductions(self, order: List[Tuple[int, str]]) -> List[List[Tuple[int, str]]]:
        """Yield the full core plus fifth-/root-omitted variants.

        Only the fifth and the root may be dropped, and never the lowest tone of
        the inversion (it defines the anchor). The third, seventh and colour
        tones are never dropped here.
        """
        variants = [list(order)]
        lowest = order[0]

        no_fifth = [t for t in order if not (t is not lowest and t[1] == 'fifth')]
        if no_fifth != order and no_fifth:
            variants.append(no_fifth)

        no_fifth_root = [t for t in no_fifth if not (t is not lowest and t[1] == 'root')]
        if no_fifth_root != no_fifth and no_fifth_root:
            variants.append(no_fifth_root)

        return variants

    def _stack_right_hand(self, core_kept: List[Tuple[int, str]], exts: List[int],
                          anchor: int) -> Optional[Tuple[int, ...]]:
        """Stack a right-hand voicing and drop over-reaching extensions.

        Core tones are stacked in closest position from ``anchor`` upward;
        extensions are added above the top core tone, lowest first, each dropped
        if it would break the per-hand span, count or range limit. Returns the
        sorted voicing, or ``None`` if even the core does not fit.
        """
        notes: List[int] = []
        prev: Optional[int] = None
        for i, (pc, _role) in enumerate(core_kept):
            m = anchor if i == 0 else self._next_above(prev, pc)
            if m > self.RH_MAX:
                return None
            notes.append(m)
            prev = m

        if not notes:
            return None
        if max(notes) - min(notes) > self.HAND_SPAN_SEMITONES:
            return None
        if len(notes) > self.MAX_NOTES_PER_HAND:
            return None

        for pc in exts:
            if len(notes) >= self.MAX_NOTES_PER_HAND:
                break
            m = self._next_above(prev, pc)
            if m > self.RH_MAX:
                continue
            if m - min(notes) > self.HAND_SPAN_SEMITONES:
                continue  # drop this (higher) extension; it over-reaches the hand
            notes.append(m)
            prev = m

        return tuple(notes)

    @staticmethod
    def _next_above(prev: int, pc: int) -> int:
        """Smallest MIDI note strictly above ``prev`` with pitch class ``pc``."""
        m = prev - (prev % 12) + pc
        while m <= prev:
            m += 12
        return m

    def _fallback_voicing(self, root_pc: int, intervals: List[int],
                          bass_pc: Optional[int]) -> Voicing:
        """Degenerate fallback: the rigid root+intervals block clamped into range.

        Guarantees every chord produces at least one voicing, however odd.
        """
        # Anchor the root near the bottom of the right-hand range.
        root_midi = self.RH_MIN + ((root_pc - self.RH_MIN) % 12)
        block = [root_midi + iv for iv in intervals]
        while block and max(block) > self.RH_MAX:
            block = [m - 12 for m in block]
        # Clamp and dedupe into the right hand.
        rh = tuple(sorted({max(self.RH_MIN, min(self.RH_MAX, m)) for m in block}))
        rh = rh[:self.MAX_NOTES_PER_HAND]

        lh: Tuple[int, ...] = ()
        if self.add_bass and bass_pc is not None and rh:
            bass = self.LH_OCTAVE2_LOW + ((bass_pc - self.LH_OCTAVE2_LOW) % 12)
            if bass < rh[0]:
                lh = (bass,)
        return Voicing(lh, rh)

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------
    @staticmethod
    def _voicing_to_midi(voicing: Voicing) -> List[int]:
        """Flatten a voicing into a sorted, de-duplicated MIDI list (bass first)."""
        return sorted(set(voicing.lh) | set(voicing.rh))

    def split_hands(self, chord_notes: 'ChordNotes') -> Tuple[List[int], List[int]]:
        """Return the greedily-chosen voicing split into (left hand, right hand).

        Exposed for testing the per-hand physical constraints without having to
        reverse-engineer the split from a flat MIDI list. Does not mutate state.
        """
        notes = chord_notes.notes
        if not notes:
            return [], []
        candidates = self._get_candidates(chord_notes)
        best = max(
            candidates,
            key=lambda v: (self._score_quality(v, chord_notes)
                           + self._score_transition(self._state.previous_chord_midi,
                                                    self._voicing_to_midi(v))),
        )
        return list(best.lh), list(best.rh)

    def _score_quality(self, voicing: Voicing, chord_notes: 'ChordNotes') -> float:
        """Intrinsic quality of a voicing in isolation; higher is better."""
        lh, rh = voicing.lh, voicing.rh
        if not rh and not lh:
            return float('-inf')

        root_pc, intervals, _bass_pc = self._chord_signature(chord_notes)
        voiced_pcs = {m % 12 for m in lh} | {m % 12 for m in rh}

        score = 0.0

        # Completeness: penalize each chord tone missing from the voicing.
        for interval in intervals:
            pc = (root_pc + interval) % 12
            if pc not in voiced_pcs:
                score -= self.OMIT_PENALTY[self._role(interval)]

        # Right-hand register centering (strong: prevents drift over long songs).
        if rh:
            score += self.SCORE_PER_RH_NOTE * len(rh)
            rh_mean = sum(rh) / len(rh)
            score += self.SCORE_CENTER * abs(rh_mean - self.RH_IDEAL_CENTER)

            # Low-interval limit: close intervals sounding low are muddy.
            for a, b in zip(rh, rh[1:]):
                if b - a <= 4 and a < self.RH_LOW_INTERVAL_FLOOR:
                    score += self.SCORE_RH_LOW_INTERVAL
                if b - a > 12:
                    score += self.SCORE_RH_WIDE_GAP

        # Left-hand register preference: octave 2 (C2..B2) is best.
        if lh:
            lh_low = min(lh)
            if lh_low < self.LH_OCTAVE2_LOW:
                score += self.SCORE_LH_BELOW_OCT2 * (self.LH_OCTAVE2_LOW - lh_low)
            elif lh_low > self.LH_OCTAVE2_HIGH:
                score += self.SCORE_LH_ABOVE_OCT2 * (lh_low - self.LH_OCTAVE2_HIGH)
            if len(lh) > 1:
                score += self.SCORE_LH_DOUBLE
                if lh_low < self.LH_OCTAVE2_LOW:
                    score += self.SCORE_LH_DOUBLE_LOW * (self.LH_OCTAVE2_LOW - lh_low)

            # Clearance: the right hand should not crowd the bass.
            if rh:
                gap = rh[0] - max(lh)
                if gap <= self.HAND_GAP_FLOOR:
                    score += self.SCORE_MUDDY_GAP * (self.HAND_GAP_FLOOR - gap + 1)

        return score

    def _score_transition(self, prev_midi: Optional[List[int]],
                          cur_midi: List[int]) -> float:
        """Voice-leading score from ``prev_midi`` to ``cur_midi``; higher is better.

        Adapted from the old ``_calculate_voice_distance``: each current note is
        matched to its nearest previous note, common tones are rewarded and
        movement is penalized. Sign is flipped (this returns higher-is-better) so
        it composes with the quality score and the maximizing optimizer. Kept
        small so quality dominates and transitions only break ties.
        """
        if not prev_midi or not cur_midi:
            return 0.0

        score = 0.0
        for note in cur_midi:
            min_dist = min(abs(note - other) for other in prev_midi)
            if min_dist == 0:
                score += self.SCORE_COMMON_TONE
            else:
                score += self.SCORE_PER_MOVE * min_dist
        return score

    # ------------------------------------------------------------------
    # State update
    # ------------------------------------------------------------------
    def _update_state(self, chord_midi: List[int], chord_notes: List[str]) -> None:
        """Update internal state after voicing a chord."""
        self._state.previous_chord_midi = chord_midi
        self._state.previous_chord_notes = chord_notes
