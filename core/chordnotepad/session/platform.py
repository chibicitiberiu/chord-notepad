"""Which UI the core is talking to, for the texts that differ between them.

A few user-facing strings name desktop gestures and menus ("Click", "Playback
→ Voicing", "F1"). The host says which platform it is when it builds the
session (``create_session(..., platform=ANDROID)``); every such string has a
variant per platform, picked with :func:`pick`. The desktop variant is always
the text the desktop showed before there were variants.

There are two desktop front ends while the desktop moves from Tk to Qt Quick:
``DESKTOP`` is the Tk one and keeps every text and behaviour it had;
``DESKTOP_QT`` is the Qt one. It shares the desktop's texts (:func:`pick`
falls back to them) except where those name a Tk menu or control, and it has
a playhead like Android's (:data:`TRACKS_PLAYHEAD`).
"""

from typing import Mapping, TypeVar

DESKTOP = "desktop"
ANDROID = "android"
DESKTOP_QT = "desktop_qt"
#: Every platform a host may name.
PLATFORMS = (DESKTOP, ANDROID, DESKTOP_QT)

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
#: Android's and the Qt desktop's players show a playhead: playback moves it,
#: the end of the song brings it back to the first chord, a tapped or clicked
#: chord takes it, and a song always has one once it has chords. The Tk
#: desktop has no playhead UI, so there nothing moves it but an explicit
#: ``set_playhead``/``rewind`` (which the Tk window never sends) and Play
#: keeps starting at the top.
TRACKS_PLAYHEAD = {DESKTOP: False, ANDROID: True, DESKTOP_QT: True}
