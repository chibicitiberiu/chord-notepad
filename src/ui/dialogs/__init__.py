"""Dialog modules for the application"""

from .insert_directives import (
    InsertBpmDialog,
    InsertTimeSignatureDialog,
    InsertKeyDialog,
    InsertLabelDialog,
    InsertLoopDialog,
)
from .quick_start import QuickStartDialog
from .options_dialog import OptionsDialog
from .transpose_dialog import TransposeDialog
from .capo_dialog import CapoDialog

__all__ = [
    'InsertBpmDialog',
    'InsertTimeSignatureDialog',
    'InsertKeyDialog',
    'InsertLabelDialog',
    'InsertLoopDialog',
    'QuickStartDialog',
    'OptionsDialog',
    'TransposeDialog',
    'CapoDialog',
]
