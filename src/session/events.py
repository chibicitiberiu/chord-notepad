"""The session's one-off events: things that happened, delivered in order.

Unlike states, events are never coalesced and never replayed to a new
listener (see :mod:`session.emitter`). Like states they are frozen and carry
only plain values, so the bridge can serialize them.

Only the events the session already emits are defined here; the rest of the
design's list (``docs/architecture/session.md``) arrives with the steps that
emit them.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class UserError:
    """Something the user asked for failed in an expected way; tell them why.

    Attributes:
        title: A short title (the dialog's title on desktop).
        message: The full, user-facing explanation.
    """

    title: str
    message: str


@dataclass(frozen=True)
class AudioUnavailable:
    """Audio couldn't be started for something the user did.

    The session already applied the reporting policy: failures of Play are
    emitted every time, failures of click-to-hear actions only the first time
    in a session (later ones are only logged).

    Attributes:
        message: The full, user-facing explanation.
        from_click: True if a click-to-hear action (a chord tap) failed,
            False for Play.
    """

    message: str
    from_click: bool
