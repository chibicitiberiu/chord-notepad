"""Wrong Settings values kept for next time, never applied (Android).

Android's Settings screen saves every valid change at once and keeps the
wrong ones (a voicing field that doesn't parse, a number out of range) in
the working copy until they are fixed or discarded. If the app goes away
before that (Home and then swiped away, the system stopping it, a crash),
this file keeps them: ``settings-staged.json`` next to the config. The next
``AppSession.begin_settings_edit`` puts them back into the working copy. The
config itself only ever holds valid values.

Format::

    {"version": 1,
     "voicings": {"Bass": {"model": "fretboard", "tuning": "E2 X9", ...}},
     "numbers": {"font_size": "999"}}

``voicings`` holds the working data of each voicing with a wrong value (a
value that doesn't parse stays the raw text); ``numbers`` the text of each
General/Playback number field that isn't a whole number in range.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple

from session.settings import NUMBER_SETTINGS

logger = logging.getLogger(__name__)

STAGING_VERSION = 1


class SettingsStaging:
    """The staging file of one config."""

    def __init__(self, path: Path) -> None:
        self.path = path
        # What the file holds as far as we know (None: not looked at yet).
        self._written: Optional[Dict[str, Any]] = None

    @classmethod
    def beside(cls, config_path: Path) -> "SettingsStaging":
        """The staging file next to the config file ``config_path``."""
        return cls(config_path.with_name(f"{config_path.stem}-staged.json"))

    def load(self) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, str]]:
        """The staged ``(voicings, numbers)``; empty when there is no file or
        it can't be read (a damaged file is logged and ignored)."""
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            self._written = {}
            return {}, {}
        except (OSError, ValueError) as e:
            logger.warning("Ignoring the staged settings in %s: %s", self.path, e)
            return {}, {}
        if not isinstance(data, dict):
            logger.warning("Ignoring the staged settings in %s: not an object", self.path)
            return {}, {}
        voicings = {str(name): voicing for name, voicing in (data.get("voicings") or {}).items()
                    if isinstance(voicing, dict) and "model" in voicing}
        numbers = {key: text for key, text in (data.get("numbers") or {}).items()
                   if key in NUMBER_SETTINGS and isinstance(text, str)}
        self._written = data
        return voicings, numbers

    def save(self, voicings: Mapping[str, Any], numbers: Mapping[str, str]) -> None:
        """Keep ``voicings`` and ``numbers`` (the file goes when both are
        empty); nothing is written when the file already holds them. A file
        that can't be written is logged: staging is a safety net."""
        if not voicings and not numbers:
            self.clear()
            return
        content = {"version": STAGING_VERSION, "voicings": dict(voicings), "numbers": dict(numbers)}
        if content == self._written:
            return
        temp = self.path.with_name(self.path.name + ".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp.write_text(json.dumps(content, ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(temp, self.path)
        except OSError as e:
            logger.error("Could not keep the staged settings in %s: %s", self.path, e)
            return
        self._written = content

    def clear(self) -> None:
        """Remove the file (nothing staged)."""
        if self._written == {}:
            return
        try:
            self.path.unlink(missing_ok=True)
        except OSError as e:
            logger.error("Could not remove the staged settings %s: %s", self.path, e)
            return
        self._written = {}
