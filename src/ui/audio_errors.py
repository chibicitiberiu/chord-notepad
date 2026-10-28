"""Present audio failures the session decided to report.

The policy (Play reports every time, click-to-hear actions once per session)
is the session's :class:`session.audio_policy.AudioFailurePolicy`; every
click source (editor taps, chord-sheet auditions, the chord identifier) goes
through the session, which emits ``AudioUnavailable`` only when the policy
says so. The main window shows those events with
:func:`present_audio_unavailable`.
"""

import tkinter as tk
from tkinter import messagebox
from typing import Optional

from session.formatting import AUDIO_ERROR_TITLE


def present_audio_unavailable(parent: Optional[tk.Misc], message: str) -> None:
    """Show an audio failure the policy already decided to report.

    Args:
        parent: Window to attach the dialog to.
        message: The full, user-facing message.
    """
    messagebox.showerror(AUDIO_ERROR_TITLE, message, parent=parent)
