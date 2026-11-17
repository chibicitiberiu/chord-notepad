"""Export audio (services.audio_export): the event plan, the WAV writer, the
temp files, the SoundFont in use and the desktop store's copy.

The event plan is song playback's own: the real SongScheduler into an
OfflineSequencer, checked against the live FakeSequencer of
test_song_scheduler. The WAV writer runs on a fake synth (open_synth is
replaced), except one smoke test on the real FluidSynth and the bundled
SoundFont, skipped where either is missing.
"""

import array
import os
import time
import wave
from pathlib import Path

import pytest

from chordnotepad.audio.song_scheduler import PLAYER_CLICK, START_LEAD_TICKS
from chordnotepad.audio.volume import metronome_cc, music_cc
from chordnotepad.exceptions import AudioInitializationError, FileOperationError, RenderAborted
from chordnotepad.models.notation import Notation
from chordnotepad.models.playback_event_internal import MidiEvent, MidiEventType
from chordnotepad.services import audio_export
from chordnotepad.services.audio_export import (
    NOTE_OFF, NOTE_ON, AudioExportSettings, PlannedEvent, plan_events, total_frames, write_wav,
)
from chordnotepad.services.event_compiler import compile_events
from chordnotepad.services.file_service import FileService
from chordnotepad.services.playback_service import PlaybackService
from chordnotepad.services.song_parser_service import SongParserService
from chordnotepad.session.documents import FileSystemDocumentStore
from tests.test_song_scheduler import FakeSequencer, run

REPO = Path(__file__).resolve().parents[1]
SOUNDFONT = REPO / "resources" / "soundfont" / "GeneralUser-GS.sf2"


class FakeConfig:
    def __init__(self, **values):
        self._values = dict(values)

    def get(self, key, default=None):
        return self._values.get(key, default)

    def set(self, key, value):
        self._values[key] = value


def rendered_song(text="{bpm: 120}\nC G Am F\n", voicing="piano"):
    playback = PlaybackService(FakeConfig(voicing=voicing))
    lines = SongParserService().detect_chords_in_text(text, Notation.AMERICAN)
    return playback.render_song(lines, None, raise_errors=True, initial_bpm=120,
                                initial_time_sig=(4, 4))


def clicked_chords():
    """Two chords with metronome ticks, as compile_events makes them."""
    events = []
    for index, (start, notes) in enumerate([(0.0, [60, 64, 67]), (1.0, [62, 65, 69])]):
        events += [MidiEvent(start + 0.5 * i, MidiEventType.METRONOME_TICK,
                             metadata={'is_downbeat': i == 0}) for i in range(2)]
        events.append(MidiEvent(start, MidiEventType.NOTE_ON, notes, 90, {}))
        events.append(MidiEvent(start + 1.0, MidiEventType.NOTE_OFF, notes, 0, {}))
    return events + [MidiEvent(2.0, MidiEventType.END_OF_SONG)]


# -- the event plan ------------------------------------------------------------------


def live_play(events, multiplier=1.0):
    """What the live player's sequencer plays for ``events``, from tick 0."""
    from chordnotepad.audio.song_scheduler import SongScheduler

    seq = FakeSequencer()
    sched = SongScheduler(events, seq, source=1, channel=0, click=PLAYER_CLICK,
                          multiplier=multiplier)
    sched.start(-START_LEAD_TICKS)
    end = max(e.timestamp for e in events)
    run(seq, sched, until=int(end * 1000 / multiplier) + 1000)
    return seq.played


def test_the_plan_is_in_the_order_the_live_sequencer_plays():
    events = clicked_chords()
    planned = plan_events(events)
    assert [(e.tick, e.kind, e.channel, e.key) for e in planned] == live_play(events)


def test_the_plan_of_a_rendered_song_matches_live_playback():
    events = compile_events(rendered_song("{bpm: 100}\n{time: 3/4}\nC G Am F\nDm G7 C\n"), False)
    planned = plan_events(events)
    assert [(e.tick, e.kind, e.channel, e.key) for e in planned] == live_play(events)
    assert planned[0].tick == 0
    assert {e.channel for e in planned} == {0, PLAYER_CLICK.channel}


def test_the_plan_plays_note_offs_first_at_a_tick():
    planned = plan_events(clicked_chords())
    at_one_second = [e for e in planned if e.tick == 1000 and e.channel == 0]
    assert [e.kind for e in at_one_second] == [NOTE_OFF] * 3 + [NOTE_ON] * 3


def test_the_plan_carries_velocities_and_the_players_click():
    planned = plan_events(clicked_chords())
    assert {e.velocity for e in planned if e.kind == NOTE_ON and e.channel == 0} == {90}
    clicks = [(e.key, e.velocity) for e in planned
              if e.kind == NOTE_ON and e.channel == PLAYER_CLICK.channel]
    assert clicks == [(76, 127), (77, 102)] * 2


def test_double_speed_halves_the_ticks():
    events = clicked_chords()
    normal = plan_events(events)
    fast = plan_events(events, multiplier=2.0)
    # The click's length stays 40 ms; everything else is twice as fast.
    assert [(e.tick, e.kind, e.key) for e in fast if not (e.kind == NOTE_OFF and e.channel == 9)] == [
        (e.tick // 2, e.kind, e.key) for e in normal if not (e.kind == NOTE_OFF and e.channel == 9)]
    assert max(e.tick for e in fast) < max(e.tick for e in normal)


def test_an_empty_song_plans_nothing():
    assert plan_events([MidiEvent(0.0, MidiEventType.END_OF_SONG)]) == []
    assert total_frames([]) == int(audio_export.TAIL_SECONDS * audio_export.SAMPLE_RATE)


# -- the synth set-up ----------------------------------------------------------------


class RecordingFluidSynth:
    """pyfluidsynth's Synth calls FluidSynthRenderer.setup and play make."""

    def __init__(self):
        self.calls = []

    def program_select(self, *args):
        self.calls.append(("program_select",) + args)

    def cc(self, *args):
        self.calls.append(("cc",) + args)

    def noteon(self, *args):
        self.calls.append(("noteon",) + args)

    def noteoff(self, *args):
        self.calls.append(("noteoff",) + args)


def renderer_over(fake):
    renderer = object.__new__(audio_export.FluidSynthRenderer)
    renderer._synth = fake
    renderer._sfid = 3
    return renderer


@pytest.mark.parametrize("on", [True, False])
def test_setup_selects_the_instrument_and_the_sliders_levels(on):
    fake = RecordingFluidSynth()
    renderer_over(fake).setup(AudioExportSettings(
        "x.sf2", instrument=24, music_volume=0.5, metronome_volume=0.8, metronome_on=on))
    assert fake.calls == [
        ("program_select", 0, 3, 0, 24),
        ("cc", 0, 7, music_cc(0.5)),
        ("program_select", 9, 3, 128, 0),
        ("cc", 9, 7, metronome_cc(0.8, on)),
    ]
    assert (fake.calls[-1][-1] == 0) is (not on)


def test_play_sends_note_ons_and_offs():
    fake = RecordingFluidSynth()
    renderer = renderer_over(fake)
    renderer.play(PlannedEvent(0, NOTE_ON, 0, 60, 90))
    renderer.play(PlannedEvent(5, NOTE_OFF, 0, 60))
    assert fake.calls == [("noteon", 0, 60, 90), ("noteoff", 0, 60)]


# -- the WAV writer, on a fake synth -------------------------------------------------


class FakeSynth:
    """open_synth's stand-in: records events against the frame they land on."""

    instances = []

    def __init__(self, soundfont, sample_rate):
        self.soundfont = soundfont
        self.frames = 0
        self.played = []
        self.settings = None
        self.deleted = False
        FakeSynth.instances.append(self)

    def setup(self, settings):
        self.settings = settings

    def play(self, event):
        self.played.append((self.frames, event))

    #: The (left, right) sample every frame holds; below SILENCE_PEAK, so
    #: the file ends after the shortest tail.
    sample = (3, -5)

    def render(self, frames):
        assert 0 < frames <= audio_export.BLOCK_FRAMES
        self.frames += frames
        return array.array("h", self.sample * frames).tobytes()

    def delete(self):
        self.deleted = True


@pytest.fixture
def fake_synth(monkeypatch):
    FakeSynth.instances = []
    monkeypatch.setattr(audio_export, "open_synth", FakeSynth)
    return FakeSynth


@pytest.fixture
def soundfont(tmp_path):
    path = tmp_path / "test.sf2"
    path.write_bytes(b"sf2")
    return str(path)


def test_write_wav_plays_each_event_at_its_frame(fake_synth, soundfont, tmp_path):
    planned = plan_events(clicked_chords())
    out = tmp_path / "out.wav"
    settings = AudioExportSettings(soundfont, instrument=5)
    progress = []
    write_wav(planned, str(out), settings, progress=progress.append)

    synth = fake_synth.instances[0]
    assert synth.settings == settings and synth.deleted
    assert [(frame, e) for frame, e in synth.played] == [
        (audio_export.frame_of(e.tick), e) for e in planned]
    with wave.open(str(out)) as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (2, 2, 44100)
        assert w.getnframes() == total_frames(planned) == synth.frames
        assert w.getnframes() == round((2.0 + audio_export.TAIL_SECONDS) * 44100)  # last off at 2 s
        assert array.array("h", w.readframes(2)).tolist() == [3, -5, 3, -5]
    assert progress == pytest.approx([0.05 * i for i in range(1, 21)])


class DecayingSynth(FakeSynth):
    """A pad: full level until the last note-off, then halving every 0.25 s."""

    def __init__(self, soundfont, sample_rate):
        super().__init__(soundfont, sample_rate)
        self.released_at = None

    def play(self, event):
        super().play(event)
        self.released_at = self.frames if event.kind == NOTE_OFF else None

    def render(self, frames):
        out = array.array("h")
        for i in range(frames):
            t = self.frames + i
            level = 8000 if self.released_at is None else int(
                8000 * 0.5 ** ((t - self.released_at) / (0.25 * 44100)))
            out.extend((level, -level))
        self.frames += frames
        return out.tobytes()


def test_a_long_release_rings_out_until_a_block_is_silent(monkeypatch, soundfont, tmp_path):
    monkeypatch.setattr(audio_export, "open_synth", DecayingSynth)
    planned = plan_events(clicked_chords())
    end = audio_export.frame_of(planned[-1].tick)
    out = tmp_path / "pad.wav"
    progress = []
    write_wav(planned, str(out), AudioExportSettings(soundfont), progress=progress.append)
    with wave.open(str(out)) as w:
        frames = w.getnframes()
        samples = array.array("h", w.readframes(frames))
    # 8000 halves to below 16 in log2(500) ~ 9 quarter-seconds: longer than
    # the 2 s minimum, and it stops at the first silent block.
    tail = (frames - end) / 44100
    assert 2.0 < tail < 2.6
    assert max(abs(v) for v in samples[-2 * audio_export.BLOCK_FRAMES:]) < audio_export.SILENCE_PEAK
    assert max(abs(v) for v in samples[-4 * audio_export.BLOCK_FRAMES:-2 * audio_export.BLOCK_FRAMES]) \
        >= audio_export.SILENCE_PEAK
    assert progress[-1] == 1.0 and progress == sorted(progress)


def test_a_release_that_never_ends_is_cut_at_the_longest_tail(monkeypatch, fake_synth, soundfont,
                                                              tmp_path):
    monkeypatch.setattr(FakeSynth, "sample", (500, 500))
    planned = plan_events(clicked_chords())
    out = tmp_path / "drone.wav"
    write_wav(planned, str(out), AudioExportSettings(soundfont))
    with wave.open(str(out)) as w:
        assert w.getnframes() == total_frames(planned, tail_seconds=audio_export.MAX_TAIL_SECONDS)


def test_write_wav_stops_when_asked_and_frees_the_synth(fake_synth, soundfont, tmp_path):
    planned = plan_events(clicked_chords())
    calls = []

    def should_abort():
        calls.append(1)
        return len(calls) > 3

    with pytest.raises(RenderAborted):
        write_wav(planned, str(tmp_path / "out.wav"), AudioExportSettings(soundfont),
                  should_abort=should_abort)
    assert fake_synth.instances[0].deleted
    assert len(calls) == 4
    assert 0 < fake_synth.instances[0].frames <= 3 * audio_export.BLOCK_FRAMES


def test_write_wav_needs_a_soundfont(fake_synth, tmp_path):
    with pytest.raises(AudioInitializationError, match="Choose one in Settings"):
        write_wav([], str(tmp_path / "a.wav"), AudioExportSettings(None))
    with pytest.raises(AudioInitializationError, match="Soundfont not found"):
        write_wav([], str(tmp_path / "a.wav"), AudioExportSettings(str(tmp_path / "gone.sf2")))
    assert fake_synth.instances == []


def test_problems_are_named_before_any_file_is_asked_for(tmp_path, monkeypatch):
    assert audio_export.soundfont_problem(None) == "No soundfont found. Choose one in Settings."
    assert audio_export.soundfont_problem(str(tmp_path / "gone.sf2")).startswith("Soundfont not found")
    (tmp_path / "a.sf2").write_bytes(b"x")
    assert audio_export.soundfont_problem(str(tmp_path / "a.sf2")) is None
    import builtins

    real_import = builtins.__import__

    def no_fluidsynth(name, *args, **kwargs):
        if name == "chordnotepad.audio.fluidsynth_import":
            raise OSError("libfluidsynth.so.3: cannot open shared object file")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_fluidsynth)
    assert audio_export.synth_problem() == (
        "FluidSynth could not be loaded: libfluidsynth.so.3: cannot open shared object file")


# -- temp files --------------------------------------------------------------------


def test_temp_paths_are_new_names_in_the_folder(tmp_path):
    folder = tmp_path / "cache"
    a, b = audio_export.temp_path(str(folder)), audio_export.temp_path(str(folder))
    assert a != b and folder.is_dir()
    assert os.path.dirname(a) == str(folder)
    assert os.path.basename(a).startswith("audio-export-") and a.endswith(".wav")


def test_only_temp_files_older_than_a_day_are_removed(tmp_path):
    now = time.time()
    old = tmp_path / "audio-export-old.wav"
    new = tmp_path / "audio-export-new.wav"
    other = tmp_path / "song.wav"
    for path in (old, new, other):
        path.write_bytes(b"x")
        os.utime(path, (now - 2 * 86400, now - 2 * 86400))
    os.utime(new, (now - 3600, now - 3600))
    assert audio_export.remove_stale_temp_files(str(tmp_path), now=now) == 1
    assert sorted(p.name for p in tmp_path.iterdir()) == ["audio-export-new.wav", "song.wav"]
    assert audio_export.remove_stale_temp_files(str(tmp_path / "missing")) == 0


# -- the SoundFont in use ------------------------------------------------------------


def test_soundfont_in_use_before_playback_is_the_configs_or_the_bundled_one(tmp_path):
    bundled = tmp_path / "bundled.sf2"
    bundled.write_bytes(b"x")
    assert PlaybackService(FakeConfig(), bundled_soundfont=str(bundled)).soundfont_in_use() == str(bundled)
    assert PlaybackService(FakeConfig(soundfont_path="/my.sf2"),
                           bundled_soundfont=str(bundled)).soundfont_in_use() == "/my.sf2"
    assert PlaybackService(FakeConfig(), bundled_soundfont=str(tmp_path / "gone.sf2")
                           ).soundfont_in_use() is None


def test_soundfont_in_use_is_the_one_playback_loaded_until_a_restart(tmp_path, monkeypatch):
    from chordnotepad.services import playback_service as module

    loaded = []

    class Player:
        def __init__(self, soundfont_path, **kwargs):
            loaded.append(soundfont_path)

        def __getattr__(self, name):
            return lambda *a, **k: None

    monkeypatch.setattr(module, "NotePlayer", Player)
    config = FakeConfig(soundfont_path="/first.sf2")
    service = PlaybackService(config)
    assert service.initialize_player()
    config.set("soundfont_path", "/second.sf2")     # takes effect after a restart
    assert loaded == ["/first.sf2"]
    assert service.soundfont_in_use() == "/first.sf2"


# -- the desktop store's copy --------------------------------------------------------


def test_the_file_store_copies_an_export(tmp_path):
    store = FileSystemDocumentStore(FileService(FakeConfig()))
    source = tmp_path / "audio-export-1.wav"
    source.write_bytes(b"RIFF" + bytes(range(256)) * 100)
    target = tmp_path / "song.wav"
    target.write_bytes(b"old and longer" * 10000)
    store.write_file(store.ref_for_path(target), str(source))
    assert target.read_bytes() == source.read_bytes()
    with pytest.raises(FileOperationError, match="Failed to write file"):
        store.write_file(store.ref_for_path(tmp_path / "no" / "such" / "x.wav"), str(source))


# -- the real synth ----------------------------------------------------------------


def _fluidsynth_available():
    try:
        from chordnotepad.audio.fluidsynth_import import fluidsynth  # noqa: F401
    except Exception:
        return False
    return True


@pytest.mark.skipif(not SOUNDFONT.exists() or not _fluidsynth_available(),
                    reason="needs libfluidsynth and the bundled SoundFont")
def test_a_real_export_is_a_wav_of_the_songs_length_with_sound(tmp_path):
    events = compile_events(rendered_song("{bpm: 120}\nC G Am F\n"), False)
    planned = plan_events(events)
    out = tmp_path / "song.wav"
    write_wav(planned, str(out), AudioExportSettings(str(SOUNDFONT), metronome_on=True))
    with wave.open(str(out)) as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (2, 2, 44100)
        frames = w.getnframes()
        samples = array.array("h", w.readframes(frames))
    # Four bars at 120 (8 s), then 2 s of tail or a little more while the
    # piano rings.
    assert total_frames(planned) <= frames < total_frames(planned, tail_seconds=4.0)
    assert abs(frames / 44100 - (8.0 + audio_export.TAIL_SECONDS)) < 0.5
    assert max(abs(s) for s in samples[:44100]) > 1000          # the first chord sounds
    assert max(abs(s) for s in samples[-4410:]) < 200            # and the tail dies away
