"""The version and preset link of a saved voicing, and its migrations.

Every voicing the user saves carries:

* ``version``: how many of :data:`MIGRATIONS` it has been through. A voicing
  without one is version 0 (everything saved before 0.6).
* ``based_on``: the built-in it was copied from, when it was: ``guitar:<slug>``
  (a ``BUILTIN_FRETBOARDS`` key), ``ensemble:<slug>`` (``BUILTIN_ENSEMBLES``)
  or ``piano``. Absent for a blank, a voicing made from scratch, or an
  origin that isn't known.

No screen shows either. Saved weights override a preset's, so a preset
tuned in a later release never reaches a copy of it by itself; the link lets
a migration move the values the user never changed.

Migration ``MIGRATIONS[i]`` moves a voicing from version ``i`` to ``i + 1``.
Each one is a pure function on the voicing dict that returns whether it
changed anything; it changes a value only while that value is one the user
never touched, and it never toggles, so running it twice, or on a dict a
newer release already moved, changes nothing.
"""

from typing import Any, Callable, Mapping, MutableMapping, Optional, Tuple

#: The version a voicing saved by this release has.
VOICING_VERSION = 0

#: ``MIGRATIONS[i]`` moves a voicing dict from version ``i`` to ``i + 1``,
#: in place, and returns whether it changed it.
MIGRATIONS: Tuple[Callable[[MutableMapping[str, Any]], bool], ...] = ()

assert len(MIGRATIONS) == VOICING_VERSION

#: The ``based_on`` of a copy of the built-in piano.
PIANO_ID = "piano"


def fretboard_id(slug: str) -> str:
    """The ``based_on`` of a copy of built-in fretboard ``slug``."""
    return f"guitar:{slug}"


def ensemble_id(slug: str) -> str:
    """The ``based_on`` of a copy of built-in ensemble ``slug``."""
    return f"ensemble:{slug}"


def voicing_version(entry: Mapping[str, Any]) -> int:
    """The saved ``version`` of a voicing dict: a whole number of at least 0,
    else 0 (missing, or junk: a string, a float, a bool)."""
    raw = entry.get("version")
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
        return 0
    return raw


def stamp(entry: MutableMapping[str, Any], based_on: Optional[str] = None) -> MutableMapping[str, Any]:
    """Give ``entry`` this release's ``version`` (a higher one, from a newer
    release, is kept) and, if given, the ``based_on`` link. In place; returns
    ``entry``."""
    entry["version"] = max(voicing_version(entry), VOICING_VERSION)
    if based_on is not None:
        entry["based_on"] = based_on
    return entry


def migrate_voicing(entry: MutableMapping[str, Any]) -> bool:
    """Run the migrations ``entry`` hasn't been through, in place, and stamp it.

    An entry already at or above :data:`VOICING_VERSION` (with a valid
    ``version``) is left exactly as it is.

    Returns:
        Whether the dict changed (a value moved, or the version was written).
    """
    before = entry.get("version")
    current = voicing_version(entry)
    if current >= VOICING_VERSION and before == current and type(before) is int:
        return False
    changed = False
    for migration in MIGRATIONS[current:]:
        changed = migration(entry) or changed
    stamp(entry)
    return changed or type(before) is not int or entry["version"] != before
