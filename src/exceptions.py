"""Custom exception hierarchy for Chord Notepad."""


class ChordNotepadError(Exception):
    """Base exception for all Chord Notepad errors."""
    pass


class ConfigurationError(ChordNotepadError):
    """Configuration-related errors."""
    pass


class AudioInitializationError(ChordNotepadError):
    """Audio system initialization failed."""
    pass


class FileOperationError(ChordNotepadError):
    """File I/O operation errors."""
    pass


class ChordDetectionError(ChordNotepadError):
    """Chord detection and parsing errors."""
    pass


class ServiceNotInitializedError(ChordNotepadError):
    """Service accessed before initialization."""
    pass


class RenderAborted(ChordNotepadError):
    """Cooperative-abort signal for a whole-song voicing search.

    Raised from :func:`audio.voicing_optimizer.optimize_sequence` (and the
    voicing/capo paths that thread its ``should_abort`` callback) when a newer
    render generation supersedes the one in flight, so the stale search stops
    promptly instead of running to completion. This is control flow, not an
    error condition: callers that start speculative renders (the chord-sheet
    strip) catch it and simply drop the abandoned work. The default
    ``should_abort=None`` everywhere means it is never raised on the playback or
    MIDI-export paths.
    """
    pass
