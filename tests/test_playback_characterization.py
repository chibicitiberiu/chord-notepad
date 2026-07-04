"""Characterization (golden) tests for the playback event pipeline.

These tests freeze the exact ``MidiEvent`` stream that the CURRENT
``EventProducer`` emits for a fixed corpus of songs. They exist as a safety net
for an upcoming refactor that replaces the streaming ``EventProducer`` with a
pre-rendered pipeline: the new pipeline MUST reproduce these streams exactly.

How it works
------------
``produce_all_events`` is the single seam the refactor will re-point. Today it
constructs an ``EventProducer`` and drives its internal production method
synchronously on the calling thread (no real playback thread, no audio). After
the refactor, re-point this one function at the new pre-rendered pipeline and
every golden below still applies unchanged.

Each song is serialized into a golden JSON file under
``tests/fixtures/characterization/``. The serialization is split into two parts
that are asserted by SEPARATE tests so that an intentional change to voicing
does not invalidate the timing/structure coverage:

* ``structure`` — every stable field of every event EXCEPT ``midi_notes``
  (event type, timestamp, chord symbol + char offsets, bar, bpm, key, time
  signature, total bars, duration, downbeat flag). Asserted by ``test_structure``.
* ``voicing`` — the ``midi_notes`` list for each event, in order. Asserted by
  ``test_voicing``.

A planned voicer upgrade is expected to regenerate ONLY the ``voicing`` part;
the ``structure`` part should stay frozen across that change.

Regenerating goldens
---------------------
Run with ``REGEN_GOLDEN=1`` to rewrite the fixture files from current code
instead of asserting. The tests then FAIL on purpose (with a "goldens
regenerated" message) so CI can never silently regenerate them::

    REGEN_GOLDEN=1 pipenv run pytest tests/test_playback_characterization.py

Review the regenerated JSON by eye, then commit it.
"""
import json
import os
from pathlib import Path
from typing import List, Optional

import pytest

from services.event_producer import EventProducer
from services.song_parser_service import SongParserService
from audio.event_buffer import EventBuffer
from audio.chord_picker import ChordNotePicker
from audio.guitar_chord_picker import GuitarChordPicker
from models.playback_event_internal import MidiEvent, MidiEventType


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "characterization"
REGEN = os.environ.get("REGEN_GOLDEN") == "1"


# ---------------------------------------------------------------------------
# The seam. The refactor re-points this at the pre-rendered pipeline.
# ---------------------------------------------------------------------------
def produce_all_events(
    text: str,
    *,
    picker=None,
    initial_bpm: int = 120,
    initial_key: Optional[str] = None,
    initial_time_sig=(4, 4),
    start_line_index: int = 0,
    start_item_index: int = 0,
) -> List[MidiEvent]:
    """Parse ``text`` and return the full MidiEvent stream (incl. END_OF_SONG).

    Drives ``EventProducer._produce_events`` directly on the current thread with
    a large buffer so pushes never block. This is the single integration seam
    the refactor will re-point at the new pre-rendered pipeline; everything else
    in this file (serialization, golden comparison) stays the same.
    """
    parser = SongParserService()
    lines = parser.detect_chords_in_text(text)

    if picker is None:
        picker = ChordNotePicker()

    # Capacity far above any corpus song so push_event never blocks; there is no
    # consumer draining concurrently while production runs.
    buffer = EventBuffer(capacity=100_000)

    producer = EventProducer(
        lines=lines,
        initial_key=initial_key,
        initial_bpm=initial_bpm,
        initial_time_sig=initial_time_sig,
        note_picker=picker,
        event_buffer=buffer,
        application=None,
        player=None,
        on_event_callback=None,
        start_line_index=start_line_index,
        start_item_index=start_item_index,
    )

    # Synchronous, single-threaded production. __init__ already set
    # _current_bpm / _current_time_position, so we can call the loop directly.
    producer._produce_events()

    events: List[MidiEvent] = []
    while buffer.size() > 0:
        events.append(buffer.pop_event(timeout=0.0))
    return events


# ---------------------------------------------------------------------------
# Serialization: stable, deterministic dicts only.
# ---------------------------------------------------------------------------
def _round6(x) -> float:
    return round(float(x), 6)


def event_structure(ev: MidiEvent) -> dict:
    """Serialize everything about an event EXCEPT its midi_notes."""
    d = {
        "event_type": ev.event_type.name,
        "timestamp": _round6(ev.timestamp),
        "velocity": ev.velocity,
    }
    md = ev.metadata or {}

    chord_info = md.get("chord_info")
    if chord_info is not None:
        d["chord"] = chord_info.chord
        d["chord_start"] = chord_info.start
        d["chord_end"] = chord_info.end

    for key in ("bar", "bpm", "key", "total_bars"):
        if key in md:
            d[key] = md[key]

    if "time_signature_beats" in md:
        d["time_signature_beats"] = md["time_signature_beats"]
    if "time_signature_unit" in md:
        d["time_signature_unit"] = md["time_signature_unit"]
    if "duration_seconds" in md:
        d["duration_seconds"] = _round6(md["duration_seconds"])
    if "is_downbeat" in md:
        d["is_downbeat"] = md["is_downbeat"]

    return d


def serialize_stream(events: List[MidiEvent]) -> dict:
    """Split the stream into the two independently-asserted golden parts."""
    return {
        "structure": [event_structure(ev) for ev in events],
        "voicing": [list(ev.midi_notes) for ev in events],
    }


# ---------------------------------------------------------------------------
# Corpus. Each entry: id -> (text, kwargs for produce_all_events).
# ---------------------------------------------------------------------------
SONG1_TEXT = "C G\nAm F\n"

CASES = {
    # 1. Basic progression, piano picker, default (full-measure) durations.
    "basic_progression": (SONG1_TEXT, {}),

    # 2. Explicit + fractional durations and an NC rest.
    "durations_and_rests": ("C*2 G*1 NC*1 Am*4.5 F\n", {}),

    # 3. All BPM directive flavours mid-song, starting from 120.
    "bpm_directives": (
        "{bpm: 90} C\n"
        "{bpm: +30} G\n"
        "{bpm: 50%} Am\n"
        "{bpm: 2x} F\n"
        "{bpm: reset} C\n",
        {},
    ),

    # 4. Time-signature change mid-song (pins bar counting across meters).
    "time_signature_change": (
        "C G\n"
        "{time: 3/4}\n"
        "Am F G\n",
        {},
    ),

    # 5. Key + roman numerals; same numerals under two keys.
    "key_roman_numerals": (
        "{key: C}\n"
        "I V vi IV\n"
        "{key: D}\n"
        "I V vi IV\n",
        {},
    ),

    # 6. Loop with state restore. BPM is bumped INSIDE the labeled section, so
    #    each pass must restore to the label-time snapshot (passes identical,
    #    not compounding). THE REFACTOR MUST PRESERVE EXACTLY THIS SEMANTIC.
    "loop_state_restore": (
        "{label: verse}\n"
        "C G\n"
        "{bpm: +10}\n"
        "Am F\n"
        "{loop: verse 3}\n",
        {},
    ),

    # 7. Whole-song loop via the built-in @start label.
    "loop_at_start": (
        "C G\n"
        "Am F\n"
        "{loop: @start 2}\n",
        {},
    ),

    # 8. Start-position playback: song 1's text, starting at line 1 item 0 (Am).
    #    Pins that skipped chords produce no events and the first emitted event's
    #    timestamp is whatever the current code produces.
    "start_position": (
        SONG1_TEXT,
        {"start_line_index": 1, "start_item_index": 0},
    ),

    # 9. Guitar picker end-to-end on song 1's text.
    "guitar_picker": (SONG1_TEXT, {"picker_factory": GuitarChordPicker}),
}


def _run_case(case_id: str) -> dict:
    text, kwargs = CASES[case_id]
    kwargs = dict(kwargs)
    picker_factory = kwargs.pop("picker_factory", None)
    picker = picker_factory() if picker_factory is not None else None
    events = produce_all_events(text, picker=picker, **kwargs)
    return serialize_stream(events)


def _fixture_path(case_id: str) -> Path:
    return FIXTURE_DIR / f"{case_id}.json"


def _load_golden(case_id: str) -> dict:
    path = _fixture_path(case_id)
    if not path.exists():
        pytest.fail(
            f"Golden fixture missing: {path}. "
            f"Regenerate with REGEN_GOLDEN=1."
        )
    return json.loads(path.read_text())


def _regen(case_id: str, actual: dict) -> None:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    _fixture_path(case_id).write_text(json.dumps(actual, indent=2) + "\n")


@pytest.mark.parametrize("case_id", list(CASES))
def test_structure(case_id):
    """Freeze every event field except midi_notes (timing/bar/directive state)."""
    actual = _run_case(case_id)
    if REGEN:
        _regen(case_id, actual)
        pytest.fail(
            f"REGEN_GOLDEN=1: regenerated {case_id}.json. "
            f"Review the diff and re-run without REGEN_GOLDEN to assert."
        )
    golden = _load_golden(case_id)
    assert actual["structure"] == golden["structure"]


@pytest.mark.parametrize("case_id", list(CASES))
def test_voicing(case_id):
    """Freeze the midi_notes per event. A planned voicer upgrade regenerates
    ONLY this part; the structure golden stays frozen."""
    actual = _run_case(case_id)
    if REGEN:
        _regen(case_id, actual)
        pytest.fail(
            f"REGEN_GOLDEN=1: regenerated {case_id}.json. "
            f"Review the diff and re-run without REGEN_GOLDEN to assert."
        )
    golden = _load_golden(case_id)
    assert actual["voicing"] == golden["voicing"]
