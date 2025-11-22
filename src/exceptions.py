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
