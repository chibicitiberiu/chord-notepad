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

``IOS`` is the SwiftUI app. It behaves like Android in every flag below except
:data:`PICKER_CREATES_FILE` and :data:`SAVES_EXPORT_AFTER_WRITE`, so
:func:`pick` falls back ios -> android -> desktop: a text with no iOS variant
uses Android's, and one with neither uses the desktop's. Only a text that
names something Android-only (Android's Back button, say) or says something
that isn't so on iOS needs an iOS variant of its own.
"""

from typing import Mapping, TypeVar

DESKTOP = "desktop"
ANDROID = "android"
DESKTOP_QT = "desktop_qt"
IOS = "ios"
#: Every platform a host may name.
PLATFORMS = (DESKTOP, ANDROID, DESKTOP_QT, IOS)

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
    """The variant for ``platform``: for iOS, its own, else Android's; for any
    platform, else the desktop's when it has none."""
    if platform in variants:
        return variants[platform]
    if platform == IOS and ANDROID in variants:
        return variants[ANDROID]
    return variants[DESKTOP]


#: Whether the playhead follows playback and chord taps (``AppSession``).
#: Android's and the Qt desktop's players show a playhead: playback moves it,
#: the end of the song brings it back to the first chord, a tapped or clicked
#: chord takes it, and a song always has one once it has chords. The Tk
#: desktop has no playhead UI, so there nothing moves it but an explicit
#: ``set_playhead``/``rewind`` (which the Tk window never sends) and Play
#: keeps starting at the top.
TRACKS_PLAYHEAD = {DESKTOP: False, ANDROID: True, DESKTOP_QT: True, IOS: True}

#: Whether Stop also puts the playhead back on the first chord, so Stop is
#: "pause and go to the beginning" and ▶ then plays from the top. The Qt
#: desktop's (Tibi, 2026-11-15); Android's Stop leaves the playhead where
#: playback was, and the Tk desktop has no playhead.
STOP_REWINDS = {DESKTOP: False, ANDROID: False, DESKTOP_QT: True, IOS: False}

#: Whether ``PlaybackState.bar`` and ``beat`` (and the desktop's "Bar n/N"
#: status) count from the top of the song. Android's status and the Qt
#: desktop's timeline do; the Tk desktop's status restarts at bar 1 where
#: playback started, as it always has.
COUNTS_SONG_BARS = {DESKTOP: False, ANDROID: True, DESKTOP_QT: True, IOS: True}

#: Whether the status line shows the position (``Bar 6/24``, with what is
#: playing) in place of the desktop's sentences ("Ready", "Stopped", "Playing
#: 12 chords"). The mobile players have no room for them and show where the
#: playhead is instead.
POSITION_STATUS = {DESKTOP: False, ANDROID: True, DESKTOP_QT: False, IOS: True}

#: Whether the export picker has already created the file when the export
#: runs, so a failed export leaves an empty file the store can't delete and
#: the error says so. Android's Storage Access Framework creates it. Desktop
#: pickers only return a path. iOS stays False: its export picker needs the
#: file to exist first, so the iOS store owns that file and no note is added
#: (revisit with the iOS document store).
PICKER_CREATES_FILE = {DESKTOP: False, ANDROID: True, DESKTOP_QT: False, IOS: False}

#: Whether the user picks where an export goes after its file is written.
#: iOS's export picker needs the file first: the session publishes the
#: export in ``ExportState`` while it is prepared and saved, and says
#: "Exported MIDI: …" only once the app reports the save
#: (``AppSession.export_finished``); a cancelled picker says nothing. The
#: desktop's and Android's pickers choose the place before the export runs.
SAVES_EXPORT_AFTER_WRITE = {DESKTOP: False, ANDROID: False, DESKTOP_QT: False, IOS: True}
