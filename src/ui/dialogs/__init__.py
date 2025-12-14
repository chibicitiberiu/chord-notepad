"""Dialog modules for the application"""

from .insert_directives import (
    InsertBpmDialog,
    InsertTimeSignatureDialog,
    InsertKeyDialog,
    InsertLabelDialog,
    InsertLoopDialog,
)
from .quick_start import QuickStartDialog

__all__ = [
    'InsertBpmDialog',
    'InsertTimeSignatureDialog',
    'InsertKeyDialog',
    'InsertLabelDialog',
    'InsertLoopDialog',
    'QuickStartDialog',
]
