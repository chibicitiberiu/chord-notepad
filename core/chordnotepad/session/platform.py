"""Which UI the core is talking to, for the texts that differ between them.

A few user-facing strings name desktop gestures and menus ("Click", "Playback
→ Voicing", "F1"). The host says which platform it is when it builds the
session (``create_session(..., platform=ANDROID)``); every such string has a
variant per platform, picked with :func:`pick`. The desktop variant is always
the text the desktop showed before there were variants.
"""

from typing import Mapping, TypeVar

DESKTOP = "desktop"
ANDROID = "android"
#: Every platform a host may name.
PLATFORMS = (DESKTOP, ANDROID)

T = TypeVar("T")


def check_platform(platform: str) -> str:
    """Return ``platform`` if it is one of :data:`PLATFORMS`.

    Raises:
        ValueError: For any other value.
    """
    if platform not in PLATFORMS:
        raise ValueError(f"unknown platform {platform!r}; expected one of {PLATFORMS}")
    return platform


def pick(variants: Mapping[str, T], platform: str) -> T:
    """The variant for ``platform``, or the desktop one when it has none."""
    return variants.get(platform, variants[DESKTOP])

#: Whether the playhead follows playback and chord taps (``AppSession``).
#: Android's player shows a playhead: playback moves it, the end of the song
#: brings it back to the first chord, a tapped chord takes it, and a song
#: always has one once it has chords. The desktop has no playhead UI yet, so
#: there nothing moves it but an explicit ``set_playhead``/``rewind`` (which
#: the Tk window never sends) and Play keeps starting at the top.
TRACKS_PLAYHEAD = {DESKTOP: False, ANDROID: True}
