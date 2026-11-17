"""Build the note picker of a voicing from its saved parameters.

One function serves both the playback service (which plays the voicing) and
the Settings validation (which decides whether a voicing may be saved), so a
voicing the form accepts is one playback can build.
"""

import copy
from typing import Any, Mapping

from chordnotepad.audio.note_picker_interface import INotePicker
from chordnotepad.exceptions import ConfigurationError


def build_picker(name: str, params: Mapping[str, Any]) -> INotePicker:
    """The note picker of the registry voicing ``name`` with parameters ``params``.

    ``params`` is the voicing dict (``{"model": "fretboard" | "ensemble" |
    "piano", ...}``); it isn't changed.

    Raises:
        ConfigurationError: if the model is unknown, the parameters don't
            validate, or the picker can't be built from them (the message
            says why, in the spec's words).
    """
    params = copy.deepcopy(dict(params))
    model = params.pop("model", None)
    try:
        if model == "fretboard":
            from chordnotepad.audio.guitar_chord_picker import GuitarChordPicker
            from chordnotepad.models.fretboard_spec import FretboardSpec

            return GuitarChordPicker(FretboardSpec.from_dict(name, params))
        if model == "ensemble":
            from chordnotepad.audio.ensemble_voicer import EnsembleVoicer
            from chordnotepad.models.ensemble_spec import EnsembleSpec

            return EnsembleVoicer(EnsembleSpec.from_dict(name, params))
        if model == "piano":
            from chordnotepad.audio.chord_picker import ChordNotePicker
            from chordnotepad.models.piano_spec import PianoSpec

            return ChordNotePicker(PianoSpec.from_dict(name, params))
    except ConfigurationError:
        raise
    except Exception as exc:  # noqa: BLE001 - any build failure is a bad voicing
        raise ConfigurationError(
            f"Voicing {name!r} can't be built: {type(exc).__name__}: {exc}") from exc
    raise ConfigurationError(f"Voicing {name!r}: unknown model {model!r}")
