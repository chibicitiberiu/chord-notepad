"""Base UI classes for common Tkinter patterns."""

from .frame_mixin import FrameMixin
from .tooltip import ToolTip, add_tooltip, ensure_field_error_styles, mark_field
from .window_mixin import WindowMixin

__all__ = [
    'FrameMixin',
    'WindowMixin',
    'ToolTip',
    'add_tooltip',
    'ensure_field_error_styles',
    'mark_field',
]
