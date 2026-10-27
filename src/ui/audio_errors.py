"""Tell the user when audio can't play, without a dialog on every click.

Pressing Play always reports the problem. Clicking a chord (in the editor,
the chord sheet or the chord identifier) also places the cursor or selects a
note, so when audio is broken those clicks report it once per session and
then only log it; otherwise editing would mean dismissing a dialog per click.
"""

import logging
import tkinter as tk
from tkinter import messagebox
from typing import Optional

logger = logging.getLogger(__name__)

_click_error_shown = False


def show_audio_error(parent: Optional[tk.Misc], error: BaseException, from_click: bool = False) -> None:
    """Show why audio couldn't play.

    Args:
        parent: Window to attach the dialog to.
        error: The failure, usually an ``AudioInitializationError``.
        from_click: True for click-to-hear actions; only the first of those
            in a session gets a dialog.
    """
    global _click_error_shown
    if from_click:
        if _click_error_shown:
            logger.warning(f"Audio unavailable (already reported): {error}")
            return
        _click_error_shown = True

    message = str(error) or "Audio is not available."
    if from_click:
        message += "\n\nClicked chords won't play until this is fixed."
    messagebox.showerror("Audio Error", message, parent=parent)


def reset_click_error_shown() -> None:
    """Forget that a click error was shown (for tests)."""
    global _click_error_shown
    _click_error_shown = False
