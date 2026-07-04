"""Ensemble voicer - voices a chord as N monophonic lines (SATB-style).

Where the guitar picker chooses a fingering and the piano picker chooses a
two-hand block, this voicer treats an :class:`~models.ensemble_spec.EnsembleSpec`
(a fixed set of ordered voices, each with a comfortable range and a maximum
leap to its neighbour) as the instrument, and spreads every chord across those
voices as independent melodic parts. It follows the exact same shape as the
other two optimizers -- enumerate, hard-filter, score, beam-Viterbi -- so all
three share the :func:`audio.voicing_optimizer.optimize_sequence` harness and
the :mod:`audio.chord_tones` role taxonomy:

1. **Enumerate** every stacking of the chord across the voices:

   - Pick a bass note. A slash chord pins the bottom voice to the slash pitch
     class; a plain chord lets any chord tone sit in the bass (inversions),
     each scored by ``weights['inversion']``.
   - Pick the pitch-class multiset for the remaining voices. More tones than
     voices means dropping the cheapest tones (``weights['omit']``); fewer
     means doubling the most agreeable ones (``weights['doubling']``).
   - Assign octaves bottom-up, keeping each voice inside its range, strictly
     above the voice below (or equal, if the spec allows unisons), and within
     the spec's maximum spacing for that adjacent pair. A beam keeps the search
     tractable for large ensembles.

2. **Hard-filter** happens inside enumeration (range, ordering, spacing). When
   a stage yields nothing, a relaxation ladder widens ranges, then drops the
   spacing caps, then finally builds one guaranteed closed stack so voicing
   never fails.

3. **Score** every survivor with :meth:`_score_quality` (doubling, omission,
   inversion, range comfort, unisons, upper spacing, doubled leading tone) plus
   :meth:`_score_transition` (per-voice movement, leaps, common tones, parallel
   perfect fifths/octaves, contrary motion of the outer voices, and 7th /
   leading-tone resolution).

4. **Optimize**: :meth:`chord_to_midi` greedily picks the argmax against the
   stored previous voicing; :meth:`voice_sequence` runs the whole-song beam DP
   so voice leading is optimized with lookahead across loops.

Voices in an :class:`EnsembleSpec` are ordered top-first; this module assigns
octaves bottom-up and emits voicings low-to-high, so the index mapping between
the two orders (``spec.voices[N - 1 - b]`` is bottom-up voice ``b``) is applied
explicitly and unit-tested. Enumeration is cached per chord signature; scoring
runs every call because it depends on the mutable transition state. All tunable
values come from the spec's weights via its accessors -- nothing is hardcoded.
"""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from itertools import combinations, combinations_with_replacement
import logging
from typing import Any, Dict, FrozenSet, List, NamedTuple, Optional, Tuple, TYPE_CHECKING

from audio.note_picker_interface import INotePicker
from audio.chord_tones import classify_role
from audio.voicing_optimizer import optimize_sequence
from chord.midi_converter import parse_note_to_semitone, intervals_from_note_names

if TYPE_CHECKING:
    from models.chord_notes import ChordNotes
    from models.ensemble_spec import EnsembleSpec

logger = logging.getLogger(__name__)


# --- Enumeration / scoring constants (structural, not musical weights) --------
_OCTAVE = 12
_LEAP_THRESHOLD = 7          # a leap wider than a perfect fifth is penalized
_TRITONE = 6                 # an exact tritone leap is penalized
_UPPER_SPACING_THRESHOLD = 7  # upper-voice adjacent gaps beyond this cost per st
_RANGE_COMFORT_EDGE = 2      # the outer 2 semitones of a range are uncomfortable
_RANGE_PAD = 2               # semitones the ladder widens each range end by
_BEAM_STACKS = 300           # partial octave-stacks kept per DFS level
_TOP_CANDIDATES = 60         # complete voicings kept per chord for the DP
_DROP_SETS_KEPT = 3          # cheapest drop-sets kept per bass choice (k > N)
_DOUBLING_SETS_KEPT = 6      # best doubling multisets kept per bass choice (k < N)

# Maps a bass tone's harmonic role to the ``weights['inversion']`` key that
# scores putting that tone in the bass. Color/extension tones fall through to
# ``'second'`` (treated like a fifth in the bass), per the design.
_INVERSION_KEY: Dict[str, str] = {
    'root': 'root',
    'third': 'first',
    'fifth': 'second',
    'seventh': 'third',
}


class _ChordContext(NamedTuple):
    """Per-chord facts the transition scorer needs about a *previous* chord.

    Carried alongside each candidate so the whole-song optimizer can look up
    the predecessor chord's resolving tones from only the two candidates it is
    handed.
    """
    seventh_pcs: FrozenSet[int]
    """Pitch classes of any seventh-role tone in the chord (for 7th resolution)."""
    leading_tone_pc: Optional[int]
    """Leading-tone pitch class implied by the chord's key, or ``None``."""


@dataclass
class _ChordMeta:
    """Everything derived from a :class:`ChordNotes` needed to voice it."""
    root_pc: int
    bass_pc: int
    is_slash: bool
    tones: Tuple[Tuple[int, str], ...]     # unique (pitch class, role), chord order
    role_by_pc: Dict[int, str]
    ctx: _ChordContext
    empty: bool = False


class _Cand(NamedTuple):
    """One candidate voicing for the optimizer: notes low-to-high, plus position.

    ``pos`` lets the transition callback recover the *previous* chord's context
    (via the predecessor candidate) without the harness passing positions to it.
    """
    notes: Tuple[int, ...]
    pos: int


@dataclass
class EnsembleVoicerState:
    """Mutable transition state: the previous chord's voicing and context."""
    previous_voicing: Optional[Tuple[int, ...]] = None  # low -> high
    previous_seventh_pcs: Optional[Tuple[int, ...]] = None
    previous_leading_tone_pc: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a JSON-friendly dict for serialization."""
        return {
            'previous_voicing': list(self.previous_voicing)
            if self.previous_voicing is not None else None,
            'previous_seventh_pcs': list(self.previous_seventh_pcs)
            if self.previous_seventh_pcs is not None else None,
            'previous_leading_tone_pc': self.previous_leading_tone_pc,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EnsembleVoicerState':
        """Rebuild a state object from :meth:`to_dict` output."""
        pv = data.get('previous_voicing')
        ps = data.get('previous_seventh_pcs')
        return cls(
            previous_voicing=tuple(pv) if pv is not None else None,
            previous_seventh_pcs=tuple(ps) if ps is not None else None,
            previous_leading_tone_pc=data.get('previous_leading_tone_pc'),
        )

    @property
    def context(self) -> _ChordContext:
        """The previous chord's :class:`_ChordContext` (empty if no history)."""
        return _ChordContext(
            frozenset(self.previous_seventh_pcs or ()),
            self.previous_leading_tone_pc,
        )


class EnsembleVoicer(INotePicker):
    """Voices chords across a fixed ensemble of monophonic voices."""

    def __init__(self, spec: 'EnsembleSpec') -> None:
        """Initialize the voicer for a given ensemble.

        Args:
            spec: The ensemble (voices top-first, ranges, spacing caps, weights)
                to voice chords for.
        """
        self._spec = spec
        self._n = len(spec.voices)

        # Bottom-up range arrays: index b is the b-th voice from the bottom.
        # spec.voices is top-first, so bottom-up voice b is spec.voices[N-1-b].
        n = self._n
        self._lo: Tuple[int, ...] = tuple(spec.voices[n - 1 - b].low for b in range(n))
        self._hi: Tuple[int, ...] = tuple(spec.voices[n - 1 - b].high for b in range(n))

        # spec.max_spacing is top-first too: entry i bounds voices[i]/voices[i+1].
        # Bottom-up, the gap above voice b (between b and b+1) is max_spacing[N-2-b].
        self._gap_max: Tuple[int, ...] = tuple(
            spec.max_spacing[n - 2 - b] for b in range(n - 1)
        )

        self._allow_unisons = spec.allow_unisons

        # Movement weight per voice, top-first (aligns with spec.voices).
        self._movement: Tuple[float, ...] = spec.movement_per_voice()

        # Scalar weights, read once via the spec accessors.
        w = spec.weight
        self._leap_penalty = float(w('leap_penalty'))
        self._octave_leap_penalty = float(w('octave_leap_penalty'))
        self._tritone_leap_penalty = float(w('tritone_leap_penalty'))
        self._common_tone_bonus = float(w('common_tone_bonus'))
        self._parallel_perfect_penalty = float(w('parallel_perfect_penalty'))
        self._contrary_motion_bonus = float(w('contrary_motion_bonus'))
        self._seventh_resolution_bonus = float(w('seventh_resolution_bonus'))
        self._leading_tone_resolution_bonus = float(w('leading_tone_resolution_bonus'))
        self._double_leading_tone_penalty = float(w('double_leading_tone_penalty'))
        self._range_comfort_penalty = float(w('range_comfort_penalty'))
        self._unison_penalty = float(w('unison_penalty'))
        self._upper_spacing_penalty = float(w('upper_spacing_penalty'))
        self._doubling: Dict[str, float] = dict(w('doubling'))
        self._omit: Dict[str, float] = dict(w('omit'))
        self._inversion: Dict[str, float] = dict(w('inversion'))

        self._state = EnsembleVoicerState()
        # Cache of enumerated candidate stacks, keyed by chord signature.
        self._cache: Dict[Any, List[Tuple[int, ...]]] = {}

    # ------------------------------------------------------------------
    # INotePicker plumbing
    # ------------------------------------------------------------------
    @property
    def state(self) -> EnsembleVoicerState:
        """Get current transition state (a copy)."""
        return deepcopy(self._state)

    @state.setter
    def state(self, new_state: EnsembleVoicerState) -> None:
        """Set transition state (stores a copy)."""
        self._state = deepcopy(new_state)

    def reset(self) -> None:
        """Reset transition state and clear the enumeration cache."""
        self._state = EnsembleVoicerState()
        self._cache.clear()

    @property
    def voice_labels(self) -> Optional[List[str]]:
        """Voice names, top voice first (per the :class:`INotePicker` contract)."""
        return [v.name for v in self._spec.voices]

    # ------------------------------------------------------------------
    # Public conversion
    # ------------------------------------------------------------------
    def chord_to_midi(self, chord_notes: 'ChordNotes') -> List[int]:
        """Voice one chord greedily against the stored previous voicing.

        Enumerates this chord's candidates, scores each as intrinsic quality
        plus the transition from the previous voicing, picks the argmax
        (ties: highest score, then lexicographically smallest voicing), stores
        it as the new previous voicing, and returns the voicing as an ascending
        de-duplicated MIDI list (so a click-to-play unison is not double-struck).

        Args:
            chord_notes: The chord to voice.

        Returns:
            Ascending, de-duplicated MIDI note numbers (empty for an empty chord).
        """
        meta = self._build_meta(chord_notes)
        if meta.empty:
            return []

        candidates = self._candidates(chord_notes, meta)
        prev = self._state.previous_voicing
        prev_ctx = self._state.context

        best_stack: Optional[Tuple[int, ...]] = None
        best_score: Optional[float] = None
        for stack in candidates:
            score = (self._score_quality(stack, meta)
                     + self._score_transition(prev, stack, prev_ctx))
            if (best_score is None or score > best_score
                    or (score == best_score and stack < best_stack)):
                best_score = score
                best_stack = stack

        assert best_stack is not None  # candidates is always non-empty
        self._store_state(best_stack, meta)
        return sorted(set(best_stack))

    def voice_sequence(self, sequence: List['ChordNotes']) -> List[List[int]]:
        """Voice a whole song at once, optimizing voice leading with lookahead.

        Resets, enumerates every chord's candidate voicings, and runs the
        beam-pruned Viterbi DP (:func:`optimize_sequence`) that maximizes the
        sum of intrinsic quality (:meth:`_score_quality`) plus per-transition
        voice leading (:meth:`_score_transition`) across the whole sequence.

        Returns one voicing per chord, each a low-to-high list with duplicates
        preserved (one entry per voice; the renderer de-duplicates for the synth
        while keeping the per-voice notes). Leaves the state at the last voiced
        chord. Deterministic: resets first and the DP breaks ties by candidate
        order, so identical input yields identical output.

        Args:
            sequence: The chords to voice, in playback order.

        Returns:
            One low-to-high, duplicate-preserving voicing per chord.
        """
        self.reset()
        if not sequence:
            return []

        metas = [self._build_meta(cn) for cn in sequence]
        candidate_sets: List[List[_Cand]] = []
        for pos, (cn, meta) in enumerate(zip(sequence, metas)):
            if meta.empty:
                candidate_sets.append([_Cand((), pos)])
                continue
            stacks = self._candidates(cn, meta)
            candidate_sets.append([_Cand(stack, pos) for stack in stacks])

        def unary(position: int, cand: _Cand) -> float:
            meta = metas[position]
            if meta.empty:
                return 0.0
            return self._score_quality(cand.notes, meta)

        def transition(prev_cand: _Cand, cand: _Cand) -> float:
            if not prev_cand.notes or not cand.notes:
                return 0.0
            prev_ctx = metas[prev_cand.pos].ctx
            return self._score_transition(prev_cand.notes, cand.notes, prev_ctx)

        chosen = optimize_sequence(
            candidate_sets, unary, transition, beam_width=20, prune_to=30
        )
        result = [list(candidate_sets[pos][idx].notes)
                  for pos, idx in enumerate(chosen)]

        # Leave state at the last non-empty voicing.
        for pos in range(len(chosen) - 1, -1, -1):
            notes = candidate_sets[pos][chosen[pos]].notes
            if notes:
                self._store_state(notes, metas[pos])
                break
        return result

    # ------------------------------------------------------------------
    # Chord metadata
    # ------------------------------------------------------------------
    def _build_meta(self, chord_notes: 'ChordNotes') -> _ChordMeta:
        """Derive roles, bass, and key context from a :class:`ChordNotes`."""
        notes = chord_notes.notes
        if not notes:
            return _ChordMeta(
                root_pc=0, bass_pc=0, is_slash=False, tones=(), role_by_pc={},
                ctx=_ChordContext(frozenset(), None), empty=True,
            )

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

        role_by_pc: Dict[int, str] = {}
        tones: List[Tuple[int, str]] = []
        for interval in intervals:
            pc = (root_pc + interval) % _OCTAVE
            if pc not in role_by_pc:
                role = classify_role(interval)
                role_by_pc[pc] = role
                tones.append((pc, role))

        seventh_pcs = frozenset(pc for pc, role in tones if role == 'seventh')
        leading_tone_pc = self._leading_tone_pc(chord_notes.key)
        ctx = _ChordContext(seventh_pcs, leading_tone_pc)

        return _ChordMeta(
            root_pc=root_pc,
            bass_pc=bass_pc,
            is_slash=(bass_pc != root_pc),
            tones=tuple(tones),
            role_by_pc=role_by_pc,
            ctx=ctx,
        )

    @staticmethod
    def _leading_tone_pc(key: Optional[str]) -> Optional[int]:
        """Return the leading-tone pitch class for a key name, or ``None``.

        The leading tone is a semitone below the tonic (``tonic + 11 mod 12``).
        A trailing ``'m'`` (minor) is stripped before parsing the tonic; both
        major and minor keys use the raised seventh.
        """
        if not key:
            return None
        tonic = key[:-1] if key.endswith('m') else key
        tonic_pc = parse_note_to_semitone(tonic)
        if tonic_pc is None:
            return None
        return (tonic_pc + 11) % _OCTAVE

    # ------------------------------------------------------------------
    # Candidate enumeration (cached)
    # ------------------------------------------------------------------
    def _candidates(self, chord_notes: 'ChordNotes',
                    meta: _ChordMeta) -> List[Tuple[int, ...]]:
        """Return (cached) candidate voicings for a chord, best-scoring first.

        Runs the relaxation ladder, then keeps the top :data:`_TOP_CANDIDATES`
        complete voicings by intrinsic quality (ties by voicing tuple ascending).
        Always returns at least one voicing.
        """
        key = (
            tuple(chord_notes.notes),
            chord_notes.bass_note,
            chord_notes.root,
            tuple(chord_notes.intervals or ()),
            chord_notes.key,
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        stacks = self._build_ladder(meta)
        # Rank by intrinsic quality; deterministic tie-break by the tuple.
        scored = [(self._score_quality(stack, meta), stack) for stack in stacks]
        scored.sort(key=lambda item: (-item[0], item[1]))
        result = [stack for _score, stack in scored[:_TOP_CANDIDATES]]
        if not result:
            result = [self._closed_stack(meta)]
        self._cache[key] = result
        return result

    def _build_ladder(self, meta: _ChordMeta) -> List[Tuple[int, ...]]:
        """Enumerate candidate voicings, relaxing constraints only when needed."""
        stacks = self._enumerate(meta, pad=0, ignore_spacing=False)
        if stacks:
            return stacks

        stacks = self._enumerate(meta, pad=_RANGE_PAD, ignore_spacing=False)
        if stacks:
            logger.debug("Ensemble voicing relaxed to widened ranges (+%d st)", _RANGE_PAD)
            return stacks

        stacks = self._enumerate(meta, pad=_RANGE_PAD, ignore_spacing=True)
        if stacks:
            logger.debug("Ensemble voicing relaxed to widened ranges + no spacing caps")
            return stacks

        logger.debug("Ensemble voicing fell back to a forced closed stack")
        return [self._closed_stack(meta)]

    def _enumerate(self, meta: _ChordMeta, *, pad: int,
                   ignore_spacing: bool) -> List[Tuple[int, ...]]:
        """Enumerate complete voicings for every bass choice and PC plan.

        Args:
            meta: The chord metadata.
            pad: Semitones to widen every voice range by at both ends (0 for the
                normal pass; :data:`_RANGE_PAD` on the relaxation ladder).
            ignore_spacing: When true, adjacent-voice spacing caps are dropped.

        Returns:
            A de-duplicated list of complete low-to-high voicings.
        """
        place_lo = tuple(lo - pad for lo in self._lo)
        place_hi = tuple(hi + pad for hi in self._hi)

        seen: set = set()
        results: List[Tuple[int, ...]] = []
        for bass_pc, upper_multiset in self._pc_plans(meta):
            for stack in self._octave_stacks(
                bass_pc, upper_multiset, place_lo, place_hi, ignore_spacing
            ):
                if stack not in seen:
                    seen.add(stack)
                    results.append(stack)
        return results

    def _pc_plans(self, meta: _ChordMeta) -> List[Tuple[int, List[int]]]:
        """Enumerate ``(bass_pc, upper_multiset)`` plans for a chord.

        The bass pitch class is fixed per plan; ``upper_multiset`` is the list
        of ``N - 1`` pitch classes the remaining voices must sing (assignment to
        specific voices happens later, during octave placement). Plans differ by
        bass choice (inversions, unless slash) and by which tones are dropped
        (too many tones) or doubled (too few).
        """
        n_upper = self._n - 1
        tones = meta.tones

        if meta.is_slash:
            bass_choices: List[int] = [meta.bass_pc]
        else:
            bass_choices = [pc for pc, _role in tones]

        plans: List[Tuple[int, List[int]]] = []
        for bass_pc in bass_choices:
            # Tones the upper voices must still cover (bass covers its own pc).
            to_place = [(pc, role) for pc, role in tones if pc != bass_pc]
            m = len(to_place)

            if m == n_upper:
                plans.append((bass_pc, [pc for pc, _role in to_place]))
            elif m > n_upper:
                plans.extend(self._drop_plans(bass_pc, to_place, m - n_upper))
            else:  # m < n_upper: double the most agreeable tones
                plans.extend(
                    self._double_plans(bass_pc, to_place, tones, n_upper - m)
                )

        if not plans:
            # Degenerate (e.g. a single-note "chord" with n_upper == 0): the
            # bass voice alone carries it.
            plans = [(meta.bass_pc, [])]
        return plans

    def _drop_plans(self, bass_pc: int, to_place: List[Tuple[int, str]],
                    drop_count: int) -> List[Tuple[int, List[int]]]:
        """Plans that drop ``drop_count`` tones, cheapest drop-sets first."""
        ranked = self._ranked_drop_sets(to_place, drop_count)
        plans: List[Tuple[int, List[int]]] = []
        for drop_pcs in ranked[:_DROP_SETS_KEPT]:
            drop_set = set(drop_pcs)
            kept = [pc for pc, _role in to_place if pc not in drop_set]
            plans.append((bass_pc, kept))
        return plans

    def _ranked_drop_sets(self, to_place: List[Tuple[int, str]],
                          drop_count: int) -> List[Tuple[int, ...]]:
        """Return drop-sets (pitch-class tuples) ranked cheapest-first.

        ``weights['omit']`` is now a signed (negative) contribution, so the
        cheapest tone to drop is the one whose omission hurts the score least,
        i.e. the drop-set with the *largest* (least-negative) summed weight.
        We therefore rank by summed weight descending; ties break by the
        pitch-class tuple for determinism. Exposed for direct unit testing.
        """
        scored: List[Tuple[float, Tuple[int, ...]]] = []
        for combo in combinations(to_place, drop_count):
            cost = sum(self._omit[role] for _pc, role in combo)
            pcs = tuple(sorted(pc for pc, _role in combo))
            scored.append((cost, pcs))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [pcs for _cost, pcs in scored]

    def _double_plans(self, bass_pc: int, to_place: List[Tuple[int, str]],
                      tones: Tuple[Tuple[int, str], ...],
                      double_count: int) -> List[Tuple[int, List[int]]]:
        """Plans that double ``double_count`` tones, best doubling first.

        Doublings are drawn from every chord tone (including the bass tone);
        each is scored by ``weights['doubling']`` for its role, summed, and the
        best :data:`_DOUBLING_SETS_KEPT` multisets are kept (ties by pitch
        classes). Repeated picks (double-doubling) are allowed for small chords.
        """
        base = [pc for pc, _role in to_place]
        scored: List[Tuple[float, Tuple[int, ...], List[int]]] = []
        for combo in combinations_with_replacement(tones, double_count):
            bonus = sum(self._doubling[role] for _pc, role in combo)
            extra = [pc for pc, _role in combo]
            scored.append((bonus, tuple(sorted(extra)), extra))
        # Highest doubling score first; deterministic tie-break by pitch classes.
        scored.sort(key=lambda item: (-item[0], item[1]))
        plans: List[Tuple[int, List[int]]] = []
        for _bonus, _pcs, extra in scored[:_DOUBLING_SETS_KEPT]:
            plans.append((bass_pc, base + extra))
        return plans

    def _octave_stacks(self, bass_pc: int, upper_multiset: List[int],
                       place_lo: Tuple[int, ...], place_hi: Tuple[int, ...],
                       ignore_spacing: bool) -> List[Tuple[int, ...]]:
        """Assign octaves bottom-up, returning every complete low-to-high stack.

        The bottom voice takes each octave of ``bass_pc`` in its range; each
        higher voice takes every remaining pitch class at every octave in its
        range that sits above (or equal to, if unisons are allowed) the voice
        below and within the spacing cap. A beam keeps only the best
        :data:`_BEAM_STACKS` partial stacks per level so large ensembles stay
        tractable.
        """
        # A partial stack: (partial_score, notes_so_far, remaining_multiset).
        beam: List[Tuple[float, Tuple[int, ...], Tuple[int, ...]]] = []
        remaining0 = tuple(sorted(upper_multiset))
        for midi in self._octaves_in_range(bass_pc, place_lo[0], place_hi[0]):
            beam.append((self._comfort(midi, 0), (midi,), remaining0))
        if not beam:
            return []

        for b in range(1, self._n):
            next_beam: List[Tuple[float, Tuple[int, ...], Tuple[int, ...]]] = []
            gap_cap = self._gap_max[b - 1]
            for score, notes, remaining in beam:
                below = notes[-1]
                for pc in sorted(set(remaining)):
                    for midi in self._octaves_in_range(pc, place_lo[b], place_hi[b]):
                        if self._allow_unisons:
                            if midi < below:
                                continue
                        elif midi <= below:
                            continue
                        gap = midi - below
                        if not ignore_spacing and gap > gap_cap:
                            continue
                        add = self._comfort(midi, b)
                        if midi == below:
                            add += self._unison_penalty
                        if b >= 2 and gap > _UPPER_SPACING_THRESHOLD:
                            add += self._upper_spacing_penalty * (gap - _UPPER_SPACING_THRESHOLD)
                        new_remaining = list(remaining)
                        new_remaining.remove(pc)
                        next_beam.append(
                            (score + add, notes + (midi,), tuple(new_remaining))
                        )
            if not next_beam:
                return []
            next_beam.sort(key=lambda item: (-item[0], item[1]))
            beam = next_beam[:_BEAM_STACKS]

        return [notes for _score, notes, _remaining in beam]

    @staticmethod
    def _octaves_in_range(pc: int, low: int, high: int) -> List[int]:
        """Every MIDI note in ``[low, high]`` with pitch class ``pc``."""
        start = low + ((pc - low) % _OCTAVE)
        return list(range(start, high + 1, _OCTAVE))

    def _closed_stack(self, meta: _ChordMeta) -> Tuple[int, ...]:
        """Build one guaranteed voicing when every enumeration stage fails.

        The bottom voice takes the octave of the bass pitch class nearest the
        middle of its widened range; each higher voice takes the next chord
        pitch class (cycled), placed at the octave nearest the voice below but
        not descending, clamped into its widened range and forced weakly
        ascending. Never fails.
        """
        place_lo = tuple(lo - _RANGE_PAD for lo in self._lo)
        place_hi = tuple(hi + _RANGE_PAD for hi in self._hi)

        mid = (place_lo[0] + place_hi[0]) // 2
        bottom = self._nearest_octave(meta.bass_pc, mid)
        bottom = min(max(bottom, place_lo[0]), place_hi[0])
        stack = [bottom]

        pcs = [pc for pc, _role in meta.tones] or [meta.bass_pc]
        prev = bottom
        for b in range(1, self._n):
            pc = pcs[(b - 1) % len(pcs)]
            midi = prev + ((pc - prev) % _OCTAVE)  # smallest >= prev with this pc
            midi = min(max(midi, place_lo[b]), place_hi[b])
            if midi < prev:
                midi = prev  # force weakly ascending
            stack.append(midi)
            prev = midi
        return tuple(stack)

    @staticmethod
    def _nearest_octave(pc: int, target: int) -> int:
        """MIDI note of pitch class ``pc`` in the octave nearest ``target``."""
        base = pc + _OCTAVE * round((target - pc) / _OCTAVE)
        return base

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------
    def _comfort(self, midi: int, voice_index: int) -> float:
        """Range-comfort contribution for one voice (bottom-up index)."""
        low = self._lo[voice_index]
        high = self._hi[voice_index]
        under = _RANGE_COMFORT_EDGE - (midi - low)
        over = _RANGE_COMFORT_EDGE - (high - midi)
        penalty = (under if under > 0 else 0) + (over if over > 0 else 0)
        return self._range_comfort_penalty * penalty

    def _score_quality(self, stack: Tuple[int, ...], meta: _ChordMeta) -> float:
        """Intrinsic quality of a voicing in isolation; higher is better.

        Rewards a complete, comfortably-spaced voicing with an agreeable
        doubling and a rooted bass; penalizes dropped tones, awkward doublings,
        inversions, cramped/edge placements, unisons, gappy upper voices, and a
        doubled leading tone.
        """
        if not stack:
            return float('-inf')

        counts = Counter(m % _OCTAVE for m in stack)
        voiced = set(counts)
        score = 0.0

        # Doubling: extra copies of each pitch class, by role.
        for pc, count in counts.items():
            if count > 1:
                role = meta.role_by_pc.get(pc)
                if role is not None:
                    score += (count - 1) * self._doubling[role]

        # Omission: chord tones not sung at all.
        for pc, role in meta.tones:
            if pc not in voiced:
                score += self._omit[role]

        # Inversion: which chord tone is in the bass (plain chords only).
        if not meta.is_slash:
            bass_role = meta.role_by_pc.get(stack[0] % _OCTAVE)
            inv_key = _INVERSION_KEY.get(bass_role, 'second') if bass_role else 'second'
            score += self._inversion[inv_key]

        # Range comfort per voice.
        for b, midi in enumerate(stack):
            score += self._comfort(midi, b)

        # Unisons: adjacent equal pitches.
        for lower, upper in zip(stack, stack[1:]):
            if lower == upper:
                score += self._unison_penalty

        # Upper spacing: adjacent gaps not involving the bottom voice.
        for i in range(1, len(stack) - 1):
            gap = stack[i + 1] - stack[i]
            if gap > _UPPER_SPACING_THRESHOLD:
                score += self._upper_spacing_penalty * (gap - _UPPER_SPACING_THRESHOLD)

        # Doubled leading tone.
        lt = meta.ctx.leading_tone_pc
        if lt is not None and counts.get(lt, 0) >= 2:
            score += self._double_leading_tone_penalty

        return score

    def _score_transition(self, prev_notes: Optional[Tuple[int, ...]],
                          cur_notes: Tuple[int, ...],
                          prev_ctx: _ChordContext) -> float:
        """Voice-leading score from ``prev_notes`` to ``cur_notes``; higher is better.

        Both voicings are low-to-high and voice-aligned. Penalizes per-voice
        movement and leaps, rewards common tones and contrary motion of the
        outer voices, penalizes parallel perfect fifths/octaves, and rewards a
        chordal seventh resolving down or a leading tone resolving up by step
        (both keyed off the *previous* chord's context).
        """
        if not prev_notes or not cur_notes or len(prev_notes) != len(cur_notes):
            return 0.0

        n = len(cur_notes)
        deltas = [cur_notes[b] - prev_notes[b] for b in range(n)]
        score = 0.0

        for b in range(n):
            # movement weight is top-first; low-to-high voice b maps to N-1-b.
            weight = self._movement[n - 1 - b]
            delta = deltas[b]
            magnitude = abs(delta)
            score += weight * magnitude
            if magnitude > _LEAP_THRESHOLD:
                score += self._leap_penalty
            if magnitude > _OCTAVE:
                score += self._octave_leap_penalty
            if magnitude == _TRITONE:
                score += self._tritone_leap_penalty
            if delta == 0:
                score += self._common_tone_bonus

        # Parallel perfect fifths/octaves between any two moving voices.
        for i in range(n):
            if deltas[i] == 0:
                continue
            for j in range(i + 1, n):
                if deltas[j] == 0:
                    continue
                prev_ic = (prev_notes[j] - prev_notes[i]) % _OCTAVE
                cur_ic = (cur_notes[j] - cur_notes[i]) % _OCTAVE
                if prev_ic == cur_ic and prev_ic in (0, 7):
                    score += self._parallel_perfect_penalty

        # Contrary motion of the outer voices.
        if n >= 2 and deltas[0] != 0 and deltas[n - 1] != 0:
            if (deltas[0] > 0) != (deltas[n - 1] > 0):
                score += self._contrary_motion_bonus

        # Seventh resolution: a prev seventh-role tone stepping down 1-2 st.
        if prev_ctx.seventh_pcs:
            for b in range(n):
                if (prev_notes[b] % _OCTAVE) in prev_ctx.seventh_pcs:
                    if (prev_notes[b] - cur_notes[b]) in (1, 2):
                        score += self._seventh_resolution_bonus

        # Leading-tone resolution: a prev leading tone stepping up exactly 1 st.
        lt = prev_ctx.leading_tone_pc
        if lt is not None:
            for b in range(n):
                if prev_notes[b] % _OCTAVE == lt and (cur_notes[b] - prev_notes[b]) == 1:
                    score += self._leading_tone_resolution_bonus

        return score

    # ------------------------------------------------------------------
    # State update
    # ------------------------------------------------------------------
    def _store_state(self, stack: Tuple[int, ...], meta: _ChordMeta) -> None:
        """Record ``stack`` and ``meta``'s context as the previous voicing."""
        self._state.previous_voicing = tuple(stack)
        self._state.previous_seventh_pcs = tuple(sorted(meta.ctx.seventh_pcs))
        self._state.previous_leading_tone_pc = meta.ctx.leading_tone_pc
