"""When to tell the user that audio is broken.

Pressing Play always reports the problem. Clicking a chord (in the editor,
the chord sheet or the chord identifier) also places the cursor or selects a
note, so when audio is broken those clicks report it once per session and
then only log it; otherwise editing would mean dismissing a dialog per click.

The session owns one :class:`AudioFailurePolicy` and applies it to every
click source: editor taps, chord-sheet auditions and the chord identifier
(which reports through ``AppSession.report_audio_failure``), so they report
only once between them.
"""


class AudioFailurePolicy:
    """Decides which audio failures are reported; the rest are only logged.

    Single-threaded: used on the session thread only.
    """

    def __init__(self) -> None:
        """Start with nothing reported."""
        self._click_reported = False

    def should_report(self, from_click: bool) -> bool:
        """Whether to report a failure now (and note that it was).

        Args:
            from_click: True for click-to-hear actions (reported once per
                session); False for Play (reported every time).
        """
        if not from_click:
            return True
        if self._click_reported:
            return False
        self._click_reported = True
        return True

    def reset(self) -> None:
        """Forget that a click failure was reported."""
        self._click_reported = False
