"""Tell the user when audio can't play, without a dialog on every click.

The policy (Play reports every time, chord clicks once per session) is the
session's :class:`session.audio_policy.AudioFailurePolicy`. The main window
presents the session's ``AudioUnavailable`` events with
:func:`present_audio_unavailable`; the click sources that don't go through the
session yet (chord-sheet audition, chord identifier) call
:func:`show_audio_error`, which applies the same policy instance once the
window has installed it with :func:`use_policy`.
"""

import logging
import tkinter as tk
from tkinter import messagebox
from typing import Optional

from session.audio_policy import AudioFailurePolicy
from session.formatting import AUDIO_ERROR_TITLE, audio_unavailable_message

logger = logging.getLogger(__name__)

_policy = AudioFailurePolicy()


def use_policy(policy: AudioFailurePolicy) -> None:
    """Share ``policy`` (the session's) with :func:`show_audio_error`."""
    global _policy
    _policy = policy


def present_audio_unavailable(parent: Optional[tk.Misc], message: str) -> None:
    """Show an audio failure the policy already decided to report.

    Args:
        parent: Window to attach the dialog to.
        message: The full, user-facing message.
    """
    messagebox.showerror(AUDIO_ERROR_TITLE, message, parent=parent)


def show_audio_error(parent: Optional[tk.Misc], error: BaseException, from_click: bool = False) -> None:
    """Show why audio couldn't play, if the policy says to.

    Args:
        parent: Window to attach the dialog to.
        error: The failure, usually an ``AudioInitializationError``.
        from_click: True for click-to-hear actions; only the first of those
            in a session gets a dialog.
    """
    if not _policy.should_report(from_click):
        logger.warning(f"Audio unavailable (already reported): {error}")
        return
    present_audio_unavailable(parent, audio_unavailable_message(str(error), from_click))


def reset_click_error_shown() -> None:
    """Start over with a fresh policy (for tests)."""
    global _policy
    _policy = AudioFailurePolicy()
