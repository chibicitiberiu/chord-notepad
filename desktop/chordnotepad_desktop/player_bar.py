"""The Play workspace's player bar (plan steps E1-E3): the Python side.

``PlayerBar.qml`` reads the session's states itself (``ToolbarState``,
``PlaybackState``, ``DocumentState``, ``VoicingMenuState``,
``InstrumentMenuState``) and sends the plain commands (``set_bpm``,
``toggle_metronome``, ...). What needs more than a state field is here:

* **Texts:** the tooltips are the core's (``session/toolbar_texts.py``, the
  Tk toolbar's), with the Qt wording where the Qt bar differs.
* **Transport:** :meth:`PlayerBarModel.playPause` (Shift: from the editor's
  cursor) and :meth:`PlayerBarModel.rewind`. The core's ``rewind`` stops a
  playing song; ⏮ keeps it playing by sending ``play_pause`` right after
  (both are bridge commands and run in order, so Play starts at the
  playhead ``rewind`` has just put on the first chord). No core change: a
  seek while playing (``seek_to_bar``) stops and restarts the same way.
* **The position** (:attr:`PlayerBarModel.position`, bar:beat from the top
  of the song): the core pings once per chord (``PlaybackState.bar`` and
  ``beat`` change per chord, B2), so between pings the beat is counted on at
  the chord's tempo times the speed (``AppSession.timeline_position``, a
  direct call, says where the chord started, its meter and tempo). Paused,
  it stands still; idle, it is the playhead's chord.
* **Seeking:** :meth:`PlayerBarModel.seekBar` sends ``seek_to_bar``: the core
  puts the playhead on the chord that bar lands on, in the bar's pass of a
  loop (a text offset alone would be the first pass). ``timeline_offset``
  (a direct call) only says whether there is anywhere to go.
* **Song values:** the tempo's scale (drag, wheel, the Q2 wheel fix), the
  key and time pickers (D5's ValuePicker with the toolbar's choices; a pick
  sends ``set_key`` / ``set_time_signature``), and where each value's
  directive is (``setting_directive_start``) for the links.
* **Speed and volume:** the log slider's mapping, steps and parsing; the
  volume and mute, which have no state (``volume``/``muted`` direct calls,
  read again after each of the bar's own commands, B3).
"""

import logging
import math
import re
import time
from typing import Any, Callable, Optional

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from chordnotepad.session import pickers, toolbar, toolbar_texts
from chordnotepad.session.bridge import to_json_value
from chordnotepad.session.platform import DESKTOP_QT
from chordnotepad.session.state import PlayAction
from chordnotepad_desktop.value_picker import initial_values

logger = logging.getLogger(__name__)

#: How often the counted-on beat is recomputed while a song plays.
TICK_MS = 40
#: The speed slider's ends, in percent (``toolbar.MULTIPLIER_SCALE``).
SPEED_MIN = toolbar.MULTIPLIER_SCALE.min_value
SPEED_MAX = toolbar.MULTIPLIER_SCALE.max_value
#: One wheel notch or Ctrl+] / Ctrl+[ (resolution 2: 5%).
SPEED_STEP = 5.0
#: The speed dropdown's presets.
SPEED_PRESETS = (50, 75, 90, 100, 125, 150)

_INSTRUMENT_PREFIX = re.compile(r"^\s*\d+\s+-\s+")
_TIME = re.compile(r"^\s*(\d+)\s*/\s*(\d+)\s*$")

#: Texts the bar shows (QML reads them from :attr:`PlayerBarModel.texts`).
TEXTS = {
    "bpm": toolbar_texts.BPM_TOOLTIP,
    "key": toolbar_texts.KEY_TOOLTIP,
    "time": toolbar_texts.TIME_TOOLTIP,
    "speed": toolbar_texts.MULTIPLIER_TOOLTIP,
    "metronome": toolbar_texts.METRONOME_TOOLTIP,
    "stop": toolbar_texts.STOP_TOOLTIP,
    "rewind": "Back to the first chord",
}


def speed_position(pct: float) -> float:
    """Where ``pct`` sits on the log slider, 0-1 (100% near the middle)."""
    pct = toolbar.MULTIPLIER_SCALE.clamp(float(pct))
    return math.log(pct / SPEED_MIN) / math.log(SPEED_MAX / SPEED_MIN)


def speed_at(position: float) -> float:
    """The speed, in whole percent, at slider ``position`` (0-1)."""
    position = min(1.0, max(0.0, float(position)))
    pct = SPEED_MIN * math.pow(SPEED_MAX / SPEED_MIN, position)
    return toolbar.MULTIPLIER_SCALE.normalize(round(pct))


def speed_stepped(pct: float, direction: int) -> float:
    """``pct`` one 5% step up or down, kept in 12.5-400%."""
    step = SPEED_STEP if direction > 0 else -SPEED_STEP
    return toolbar.MULTIPLIER_SCALE.normalize(float(pct) + step)


def instrument_name(label: str) -> str:
    """The instrument's name from its menu label (`` 24 - Nylon Guitar``)."""
    return _INSTRUMENT_PREFIX.sub("", label or "")


class BeatClock:
    """The beat counted on between the core's per-chord pings.

    ``anchor`` is where the chord the last ping started is
    (:class:`~chordnotepad.session.timeline.TimelinePosition`); the beats
    since then run at its tempo times the speed while :attr:`running`.
    """

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self.anchor: Any = None
        self.running = False
        self._done = 0.0        # beats counted before the current run
        self._since = 0.0       # when the current run started
        self._rate = 0.0        # beats per second in the current run

    def reset(self, anchor: Any, running: bool, speed_pct: float) -> None:
        """Count from ``anchor`` again (a new chord, or idle)."""
        self.anchor = anchor
        self._done = 0.0
        self.running = False
        self._rate = self._rate_for(speed_pct)
        if running:
            self.start(speed_pct)

    def _rate_for(self, speed_pct: float) -> float:
        bpm = getattr(self.anchor, "bpm", 0) or 0
        return bpm * float(speed_pct) / 100.0 / 60.0

    def elapsed(self) -> float:
        """Beats since the anchor."""
        if not self.running:
            return self._done
        return self._done + max(0.0, self._clock() - self._since) * self._rate

    def start(self, speed_pct: float) -> None:
        """Run (playing, or resumed), at ``speed_pct``."""
        if self.running:
            return
        self._since = self._clock()
        self._rate = self._rate_for(speed_pct)
        self.running = True

    def stop(self) -> None:
        """Stand still (paused)."""
        if self.running:
            self._done = self.elapsed()
            self.running = False

    def set_speed(self, speed_pct: float) -> None:
        """The speed changed: count on from here at the new rate."""
        if self.running:
            self._done = self.elapsed()
            self._since = self._clock()
        self._rate = self._rate_for(speed_pct)

    def position(self) -> Optional[tuple]:
        """``(bar, beat, played)``: the bar and beat counted to, and the bars
        played for the timeline's fill (the beat under way counts), or None
        without an anchor."""
        anchor = self.anchor
        if anchor is None:
            return None
        per_bar = max(1, int(anchor.beats_per_bar))
        beats = (anchor.bar - 1) * per_bar + (anchor.beat - 1) + self.elapsed()
        total = max(1, int(anchor.total_bars)) * per_bar
        beats = min(max(0.0, beats), total - 1e-6)
        bar = int(beats // per_bar) + 1
        beat = int(math.floor(beats - (bar - 1) * per_bar + 1e-9)) + 1
        return bar, beat, (bar - 1) + beat / per_bar


class PlayerBarModel(QObject):
    """See the module docstring.

    Args:
        store: The window's SessionStore.
        editor: The EditorBridge (the cursor for Shift+▶, positions for the links).
        clock: The beat clock's time source (tests pass a fake).
    """

    #: The bar:beat position or the timeline's fill moved.
    positionChanged = Signal()
    #: The volume or the mute changed.
    volumeChanged = Signal()

    def __init__(self, store: Any, editor: Any, parent: Optional[QObject] = None,
                 clock: Callable[[], float] = time.monotonic) -> None:
        super().__init__(parent)
        self._store = store
        self._editor = editor
        self._beats = BeatClock(clock)
        self._status = "idle"
        self._ping = None               # (chord_index, bar, beat) of the last ping
        self._speed = 100.0
        self._shown = (1, 1, 0.0)
        self._has_position = False
        self._volume = 1.0
        self._muted = False
        self._asks: dict = {}
        self._timer = QTimer(self)
        self._timer.setInterval(TICK_MS)
        self._timer.timeout.connect(self._tick)
        store.stateChanged.connect(self._on_state)
        self._read_volume()
        self._take_toolbar()
        self._take_playback()

    # -- states -----------------------------------------------------------------------

    def _value(self, type_name: str, key: str) -> Any:
        return self._store.state(type_name).value(key)

    def _on_state(self, type_name: str) -> None:
        if type_name == "PlaybackState":
            self._take_playback()
        elif type_name == "ToolbarState":
            self._take_toolbar()

    def _take_toolbar(self) -> None:
        speed = self._value("ToolbarState", "multiplier_pct")
        if speed is None or float(speed) == self._speed:
            return
        self._speed = float(speed)
        self._beats.set_speed(self._speed)

    def _position(self) -> Any:
        if self._store.closed:
            return None
        return self._store.direct("timeline_position")

    def _take_playback(self) -> None:
        status = self._value("PlaybackState", "status") or "idle"
        ping = (self._value("PlaybackState", "chord_index"), self._value("PlaybackState", "bar"),
                self._value("PlaybackState", "beat"))
        was = self._status
        self._status = status
        if status == "idle":
            self._ping = None
            self._beats.reset(self._position(), False, self._speed)
        elif ping != self._ping and ping[0] is not None:
            # A new chord started (or the song was re-rendered from one).
            self._ping = ping
            self._beats.reset(self._position(), status == "playing", self._speed)
        elif status == "playing" and was != "playing":
            self._beats.start(self._speed)
        elif status == "paused":
            self._beats.stop()
        if self._beats.running:
            self._timer.start()
        else:
            self._timer.stop()
        self._tick()

    def _tick(self) -> None:
        found = self._beats.position()
        shown = found if found is not None else (1, 1, 0.0)
        if self._status == "idle" and found is not None:
            shown = (found[0], found[1], float(found[0] - 1))   # the playhead's bar starts there
        has = found is not None
        if shown != self._shown or has != self._has_position:
            self._shown, self._has_position = shown, has
            self.positionChanged.emit()

    def _get_position(self) -> str:
        return f"{self._shown[0]}:{self._shown[1]}"

    #: "bar:beat", from the top of the song ("1:1" before anything is known).
    position = Property(str, _get_position, notify=positionChanged)

    def _get_played(self) -> float:
        return self._shown[2]

    #: Bars played, for the timeline's fill and handle (the beat under way counts).
    played = Property(float, _get_played, notify=positionChanged)

    def _get_has_position(self) -> bool:
        return self._has_position

    #: Whether the position is known (the sheet has rendered, or a song plays).
    hasPosition = Property(bool, _get_has_position, notify=positionChanged)

    # -- texts ------------------------------------------------------------------------

    def _get_texts(self) -> dict:
        return dict(TEXTS)

    #: The bar's fixed texts (:data:`TEXTS`).
    texts = Property("QVariantMap", _get_texts, constant=True)

    @Slot(str, result=str)
    def playTooltip(self, action: str) -> str:  # noqa: N802 (Qt)
        """▶'s tooltip for ``ToolbarState.play_action``."""
        try:
            return toolbar_texts.play_pause_tooltip(PlayAction(action or "play"), DESKTOP_QT)
        except ValueError:
            return toolbar_texts.play_pause_tooltip(PlayAction.PLAY, DESKTOP_QT)

    @Slot(str, result=str)
    def setByTooltip(self, directive: str) -> str:  # noqa: N802 (Qt)
        """"Set by {bpm: 90} in the song"."""
        return toolbar_texts.set_by_tooltip(directive)

    # -- transport --------------------------------------------------------------------

    @Slot(bool)
    def playPause(self, from_cursor: bool) -> None:  # noqa: N802 (Qt)
        """▶ / ⏸: play, pause or resume. ``from_cursor`` (Shift): an idle
        song starts at the editor's cursor instead of the playhead."""
        offset = None
        if from_cursor and self._status == "idle":
            cursor = self._editor.cursor_position()
            if cursor is not None:
                offset = self._editor.to_code_point(cursor)
        self._store.submit("play_pause", {"from_offset": offset})

    @Slot()
    def rewind(self) -> None:
        """⏮: the playhead to the first chord; a playing song goes on from there."""
        playing = self._status == "playing"
        self._store.submit("rewind")
        if playing:
            self._store.submit("play_pause", {"from_offset": None})

    @Slot(int, result=bool)
    def seekBar(self, bar: int) -> bool:  # noqa: N802 (Qt)
        """Move the playhead to the chord a seek to ``bar`` lands on, in that
        bar's pass of a loop (a playing song restarts there). False when
        there is nowhere to go."""
        if self._store.closed:
            return False
        if self._store.direct("timeline_offset", int(bar)) is None:
            return False
        self._store.submit("seek_to_bar", {"bar": int(bar)})
        return True

    @Slot()
    def revealPlayhead(self) -> None:  # noqa: N802 (Qt)
        """Scroll the text to the chord the playhead is on (the seek bar's
        press, and the release of a drag; not each bar of an idle drag)."""
        self._editor.revealPlayhead()

    # -- song values ------------------------------------------------------------------

    @Slot(str, result=int)
    def directivePosition(self, value: str) -> int:  # noqa: N802 (Qt)
        """The editor position just inside the directive that sets ``value``
        (``tempo``, ``time``, ``key``), from the live text; -1 without one."""
        if self._store.closed:
            return -1
        offset = self._store.direct("setting_directive_start", value)
        if offset is None:
            return -1
        return self._editor.to_utf16(offset + 1)

    @Slot(int, int, result=int)
    def bpmDragged(self, start: int, steps: int) -> int:  # noqa: N802 (Qt)
        """The tempo a drag of ``steps`` 4-px steps from ``start`` gives
        (measured from where the press started; magnetic to tens)."""
        return int(round(toolbar.BPM_SCALE.stepped(start, int(steps))))

    @Slot(str, result="QVariantMap")
    def songPicker(self, kind: str) -> dict:  # noqa: N802 (Qt)
        """What the key or time picker shows for the song's starting value,
        in the shape ValuePicker.qml takes (as ValuePickerModel's)."""
        notation = self._value("ToolbarState", "notation") or "american"
        if kind == pickers.KEY:
            options = pickers.song_key_options(notation, self._value("ToolbarState", "key") or "")
        elif kind == pickers.TIME:
            beats, unit = self._value("ToolbarState", "beats"), self._value("ToolbarState", "unit")
            current = f"{beats}/{unit}" if beats and unit else ""
            options = pickers.picker_options(pickers.TIME, pickers.PickerContext(current=current))
        else:
            raise ValueError(f"no song value picker for {kind!r}")
        picker = pickers.DirectivePicker(kind, 0, 0, 0, 0, options)
        return {"kind": kind, "current": options.current, "options": to_json_value(options),
                "initial": initial_values(picker)}

    @Slot(str, str, result=bool)
    def applySongValue(self, kind: str, value: str) -> bool:  # noqa: N802 (Qt)
        """Send a picked key or time signature (only one that changed)."""
        if kind == pickers.KEY:
            if not value or value == self._value("ToolbarState", "key"):
                return False
            self._store.submit("set_key", {"key": value})
            return True
        if kind == pickers.TIME:
            match = _TIME.match(value or "")
            if not match:
                return False
            beats, unit = int(match.group(1)), int(match.group(2))
            if (beats, unit) == (self._value("ToolbarState", "beats"),
                                 self._value("ToolbarState", "unit")):
                return False
            self._store.submit("set_time_signature", {"beats": beats, "unit": unit})
            return True
        return False

    @Slot(str, result=str)
    def keyLabel(self, key: str) -> str:  # noqa: N802 (Qt)
        """A key as the bar shows it (``C♯``, ``Si♭``)."""
        if not key:
            return ""
        notation = self._value("ToolbarState", "notation") or "american"
        try:
            return pickers.key_label(toolbar.convert_key(key, "american"), notation)
        except (KeyError, IndexError, ValueError):
            return key

    # -- speed ------------------------------------------------------------------------

    @Slot(float, result=float)
    def speedPosition(self, pct: float) -> float:  # noqa: N802 (Qt)
        return speed_position(pct)

    @Slot(float, result=float)
    def speedAt(self, position: float) -> float:  # noqa: N802 (Qt)
        return speed_at(position)

    @Slot(float, int, result=float)
    def speedStepped(self, pct: float, direction: int) -> float:  # noqa: N802 (Qt)
        return speed_stepped(pct, direction)

    @Slot(float, result=str)
    def formatSpeed(self, pct: float) -> str:  # noqa: N802 (Qt)
        """``87.5``, ``100``: the multiplier as the toolbar shows it."""
        return toolbar.format_multiplier_pct(pct)

    @Slot(float, float, result=str)
    def effectiveTempo(self, bpm: float, pct: float) -> str:  # noqa: N802 (Qt)
        """``"143 bpm (150%)"``: the tempo heard at speed ``pct``; ``""`` at 100%."""
        return toolbar.format_effective_bpm(bpm, pct)

    def _get_speed_presets(self) -> list:
        return list(SPEED_PRESETS)

    #: The dropdown's preset chips, in percent.
    speedPresets = Property("QVariantList", _get_speed_presets, constant=True)

    def _asked(self, key: str) -> Any:
        """The value last asked for while the command is still queued, else
        the state's: fast wheel notches step on from there, not from a state
        that hasn't caught up yet."""
        asked = self._asks.get(key)
        return asked if asked is not None else self._value("ToolbarState", key)

    def _ask(self, key: str, command: str, args: dict, value: Any) -> None:
        self._asks[key] = value
        self._store.submit(command, args)
        self._store.after_commands(lambda: self._asks.pop(key, None))

    @Slot(int)
    def stepSpeed(self, direction: int) -> None:  # noqa: N802 (Qt)
        """One 5% step (the wheel, Ctrl+] and Ctrl+[); live while playing."""
        pct = self._asked("multiplier_pct")
        if pct is None:
            return
        target = speed_stepped(pct, direction)
        if target != pct:
            self._ask("multiplier_pct", "set_multiplier_pct", {"pct": target}, target)

    @Slot(int)
    def stepBpm(self, direction: int) -> None:  # noqa: N802 (Qt)
        """The tempo one wheel notch or arrow up or down (Q2: never stuck at a
        multiple of ten). The session ignores it when the tempo is locked."""
        bpm = self._asked("bpm")
        if bpm is None:
            return
        target = int(round(toolbar.BPM_SCALE.nudged(bpm, int(direction))))
        if target != bpm:
            self._ask("bpm", "set_bpm", {"bpm": target}, target)

    # -- volume -----------------------------------------------------------------------

    def _read_volume(self) -> None:
        if self._store.closed:
            return
        volume = float(self._store.direct("volume"))
        muted = bool(self._store.direct("muted"))
        if (volume, muted) != (self._volume, self._muted):
            self._volume, self._muted = volume, muted
            self.volumeChanged.emit()

    def _volume_command(self, name: str, args: dict) -> None:
        self._store.submit(name, args)
        self._store.after_commands(self._read_volume)

    def _get_volume(self) -> float:
        return self._volume

    #: The volume slider, 0-1 (config ``volume``).
    volume = Property(float, _get_volume, notify=volumeChanged)

    def _get_muted(self) -> bool:
        return self._muted

    #: Muted (not saved: every run starts unmuted).
    muted = Property(bool, _get_muted, notify=volumeChanged)

    @Slot(float)
    def setVolume(self, volume: float) -> None:  # noqa: N802 (Qt)
        """The slider moved: that volume, and unmuted (the mockup's rule)."""
        volume = min(1.0, max(0.0, round(float(volume), 2)))
        self._volume_command("set_volume", {"volume": volume})
        if self._muted:
            self._volume_command("set_muted", {"muted": False})

    @Slot(int)
    def stepVolume(self, steps: int) -> None:  # noqa: N802 (Qt)
        """The wheel over the volume button: 5% steps, unmuting."""
        self._volume_command("step_volume", {"steps": int(steps)})

    @Slot(bool)
    def setMuted(self, muted: bool) -> None:  # noqa: N802 (Qt)
        self._volume_command("set_muted", {"muted": bool(muted)})

    # -- menus ------------------------------------------------------------------------

    @Slot(str, result=str)
    def instrumentName(self, label: str) -> str:  # noqa: N802 (Qt)
        return instrument_name(label)

    def close(self) -> None:
        """Stop the beat clock (the window is going away)."""
        self._timer.stop()
