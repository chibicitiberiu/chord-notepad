"""AppSession.export_audio: the picker, the job, its progress and its file.

The session runs on a ManualHost over the real parser, viewmodels and
PlaybackService (a silent FakePlayer); the audio export has its own
BackgroundWorker and renders into a temp folder of the test's. The synth is
a fake (``audio_export.open_synth``), so no FluidSynth is needed; the WAV it
writes is real.
"""

import threading
import wave

import pytest

from chordnotepad.services import audio_export
from chordnotepad.services.playback_service import PlaybackService
from chordnotepad.services.song_parser_service import SongParserService
from chordnotepad.session import formatting
from chordnotepad.session.events import PickDocumentRequest, PickMode, UserError
from chordnotepad.session.host import HostDispatch
from chordnotepad.session.session import AppSession
from chordnotepad.session.state import StatusState
from chordnotepad.session.testing import EventRecorder, FakePlayer, InMemoryDocumentStore, ManualHost
from chordnotepad.session.workers import BackgroundWorker
from chordnotepad.viewmodels.main_window_viewmodel import MainWindowViewModel
from chordnotepad.viewmodels.text_editor_viewmodel import TextEditorViewModel

SONG = "{bpm: 120}\nC G Am F\n"


class FakeConfig:
    def __init__(self, **values):
        self._values = dict(values)

    def get(self, key, default=None):
        return self._values.get(key, default)

    def set(self, key, value):
        self._values[key] = value


class FakeSynth:
    """Silence, block by block; ``gate`` (when set) holds every render."""

    instances = []
    gate = None

    def __init__(self, soundfont, sample_rate):
        self.soundfont = soundfont
        self.settings = None
        self.deleted = False
        self.played = []
        FakeSynth.instances.append(self)

    def setup(self, settings):
        self.settings = settings

    def play(self, event):
        self.played.append(event)

    def render(self, frames):
        if FakeSynth.gate is not None:
            FakeSynth.gate.wait(10)
        return bytes(4 * frames)

    def delete(self):
        self.deleted = True


@pytest.fixture(autouse=True)
def fake_synth(monkeypatch):
    FakeSynth.instances = []
    FakeSynth.gate = None
    monkeypatch.setattr(audio_export, "open_synth", FakeSynth)
    # Whether libfluidsynth loads here doesn't matter: the synth is a fake.
    monkeypatch.setattr(audio_export, "synth_problem", lambda: None)
    yield FakeSynth
    if FakeSynth.gate is not None:
        FakeSynth.gate.set()


class Env:
    def __init__(self, tmp_path, text=SONG, platform="desktop"):
        self.host = ManualHost()
        dispatch = HostDispatch(self.host)
        self.soundfont = tmp_path / "test.sf2"
        self.soundfont.write_bytes(b"sf2")
        self.config = FakeConfig(soundfont_path=str(self.soundfont), instrument=24)
        self.player = FakePlayer(auto_play=False)
        self.audio = PlaybackService(self.config, player=self.player, application=dispatch)
        self.store = InMemoryDocumentStore({"song.txt": SONG})
        self.main = MainWindowViewModel(
            self.config, self.audio, self.store, SongParserService(), dispatch)
        self.worker = BackgroundWorker(self.host)
        self.audio_worker = BackgroundWorker(self.host, name="AudioExport")
        self.temp = tmp_path / "cache"
        self.session = AppSession(
            self.host, main_window_viewmodel=self.main,
            text_editor_viewmodel=TextEditorViewModel(SongParserService()),
            worker=self.worker, audio_export_worker=self.audio_worker,
            export_temp_dir=str(self.temp), platform=platform)
        self.recorder = EventRecorder()
        self.session.subscribe(self.recorder)
        self.session.start()
        if text:
            self.session.set_text(text)
            self.host.advance(0.5)
        self.recorder.clear()

    def settle(self):
        assert self.audio_worker.wait_idle(timeout=30)
        self.host.run_pending()

    def request(self):
        pending = self.session._flows.pending_request_id
        found = [r for r in self.recorder.of_type(PickDocumentRequest) if r.request_id == pending]
        assert found, f"no pending picker (recorded: {self.recorder.compact()})"
        return found[0]

    def answer(self, value):
        request = self.request()
        self.session.respond(request.request_id, value)

    def statuses(self):
        return [s.text for s in self.recorder.of_type(StatusState)]

    def status(self):
        return self.session._emitter.state(StatusState).text

    def errors(self):
        return [(e.title, e.message) for e in self.recorder.of_type(UserError)]

    def temp_files(self):
        return sorted(p.name for p in self.temp.iterdir()) if self.temp.exists() else []


@pytest.fixture
def env(tmp_path):
    env = Env(tmp_path)
    yield env
    env.session.shutdown()


def test_export_asks_for_a_wav_named_after_the_song(tmp_path):
    env = Env(tmp_path, text="")
    env.session.open_document(env.store.ref("song.txt"))
    env.recorder.clear()
    env.session.export_audio()
    request = env.request()
    assert (request.mode, request.suggested_name) == (PickMode.EXPORT_AUDIO, "song.wav")
    env.session.shutdown()


def test_an_untitled_song_suggests_its_first_lyric_line(tmp_path):
    env = Env(tmp_path, text="C G\nAmazing grace\n")
    env.session.export_audio()
    assert env.request().suggested_name == "Amazing grace.wav"
    env.session.shutdown()


def test_export_writes_the_wav_off_the_session_thread_with_progress(env):
    env.session.export_audio()
    env.answer(env.store.ref("out.wav"))
    assert env.status() == "Exporting audio… 0%"
    env.settle()

    data = env.store.contents["memory:out.wav"]
    assert data[:4] == b"RIFF" and data[8:12] == b"WAVE"
    [thread] = env.store.write_file_threads
    assert thread is not threading.main_thread() and thread.name == "AudioExport"
    statuses = env.statuses()
    assert statuses[0] == "Exporting audio… 0%"
    assert "Exporting audio… 50%" in statuses and "Exporting audio… 95%" in statuses
    assert statuses[-1] == "Exported audio: out.wav"
    assert env.errors() == []
    # The temp file is gone; exports don't join the recent list.
    assert env.temp_files() == []
    assert env.session._documents.recent() == []


def test_export_sounds_like_play_now(env):
    env.session.toggle_metronome()
    env.session.set_multiplier_pct(200)
    env.session.set_instrument(33)
    env.main.set_volume(0.4)
    env.main.set_metronome_volume(0.7)
    env.session.export_audio()
    env.answer(env.store.ref("out.wav"))
    env.settle()
    synth = FakeSynth.instances[0]
    player = env.player
    assert synth.soundfont == str(env.soundfont) == env.audio.soundfont_in_use()
    # What the live player was given is what the export plays with.
    assert (synth.settings.instrument, synth.settings.music_volume,
            synth.settings.metronome_volume, synth.settings.metronome_on,
            synth.settings.multiplier) == (
        player.instrument, player.music_volume, player.metronome_volume,
        player.metronome_enabled, player.bpm_multiplier)
    assert (player.instrument, player.metronome_enabled, player.bpm_multiplier) == (33, True, 2.0)
    # Four bars at 120 at double speed: the last note-off at 4 s.
    assert max(e.tick for e in synth.played) == 4000
    with wave.open(_saved(env, "out.wav")) as w:
        assert w.getnframes() == round((4.0 + audio_export.TAIL_SECONDS) * 44100)


def _saved(env, name):
    path = env.temp.parent / name
    path.write_bytes(env.store.contents[f"memory:{name}"])
    return str(path)


def test_the_song_is_exported_as_it_was_when_the_file_was_picked(env, monkeypatch):
    # Hold the job before it renders, then change the song.
    started, release = threading.Event(), threading.Event()
    render_song = env.audio.render_song

    def held(lines, *args, **kwargs):
        started.set()
        assert release.wait(10)
        return render_song(lines, *args, **kwargs)

    monkeypatch.setattr(env.audio, "render_song", held)
    env.session.export_audio()
    env.answer(env.store.ref("out.wav"))
    assert started.wait(10)
    env.session.set_text("{bpm: 60}\nD\n")
    env.host.advance(0.5)
    release.set()
    env.settle()
    synth = FakeSynth.instances[0]
    chords = [e for e in synth.played if e.kind == "on" and e.channel == 0]
    # C G Am F at 120: four chords over 8 s, not one D at 60 over 4 s.
    assert sorted({e.tick for e in chords}) == [0, 2000, 4000, 6000]
    assert 62 not in {e.key % 12 + 60 for e in chords if e.tick == 0}


def test_no_chords_says_so_before_asking_for_a_file(tmp_path):
    env = Env(tmp_path, text="just words\n")
    env.session.export_audio()
    assert env.recorder.of_type(PickDocumentRequest) == []
    assert env.errors() == [(formatting.FILE_ERROR_TITLE,
                             "Failed to export audio file:\nThere are no chords to export.")]
    env.session.shutdown()


def test_a_second_export_while_one_runs_is_refused_before_the_picker(env):
    FakeSynth.gate = threading.Event()
    env.session.export_audio()
    env.answer(env.store.ref("out.wav"))
    env.recorder.clear()
    env.session.export_audio()
    assert env.recorder.of_type(PickDocumentRequest) == []
    assert env.errors() == [(formatting.AUDIO_EXPORT_BUSY_TITLE, formatting.AUDIO_EXPORT_BUSY_MESSAGE)]
    FakeSynth.gate.set()
    env.settle()
    assert env.status() == "Exported audio: out.wav"
    # Once it's done, the next one asks for its file.
    env.recorder.clear()
    env.session.export_audio()
    assert env.request().mode == PickMode.EXPORT_AUDIO


def test_no_soundfont_says_so_before_asking_for_a_file(env):
    env.soundfont.unlink()
    env.session.export_audio()
    assert env.recorder.of_type(PickDocumentRequest) == []
    assert env.errors() == [(formatting.FILE_ERROR_TITLE, "Failed to export audio file:\n"
                             f"Soundfont not found: {env.soundfont}")]


def test_no_fluidsynth_says_so_before_asking_for_a_file(env, monkeypatch):
    monkeypatch.setattr(audio_export, "synth_problem",
                        lambda: "FluidSynth could not be loaded: no lib")
    env.session.export_audio()
    assert env.recorder.of_type(PickDocumentRequest) == []
    assert env.errors() == [(formatting.FILE_ERROR_TITLE, "Failed to export audio file:\n"
                             "FluidSynth could not be loaded: no lib")]


def test_a_failure_on_android_says_the_picked_file_is_left(tmp_path):
    env = Env(tmp_path, platform="android")
    env.store.write_error = "disk full"
    env.session.export_audio()
    env.answer(env.store.ref("out.wav"))
    env.settle()
    assert env.errors() == [("Error", "Failed to export audio file:\nout.wav\n\ndisk full\n\n"
                             + formatting.audio_export_left_file_note("out.wav"))]
    env.session.shutdown()


def test_a_cancelled_picker_exports_nothing(env):
    env.session.export_audio()
    env.answer(None)
    env.settle()
    assert FakeSynth.instances == [] and env.store.contents.keys() == {"memory:song.txt"}
    assert env.session._audio_job is None


def test_a_write_failure_is_a_user_error_and_the_temp_file_goes(env):
    env.store.write_error = "disk full"
    env.session.export_audio()
    env.answer(env.store.ref("out.wav"))
    env.settle()
    assert env.errors() == [("Error", "Failed to export audio file:\nout.wav\n\ndisk full")]
    assert env.status() == formatting.READY
    assert env.temp_files() == []


def test_a_synth_failure_is_a_user_error(env, monkeypatch):
    def broken(soundfont, rate):
        raise audio_export.AudioInitializationError("FluidSynth could not be loaded: no lib")

    monkeypatch.setattr(audio_export, "open_synth", broken)
    env.session.export_audio()
    env.answer(env.store.ref("out.wav"))
    env.settle()
    assert env.errors() == [("Error", "Failed to export audio file:\nout.wav\n\n"
                                      "FluidSynth could not be loaded: no lib")]
    assert env.temp_files() == []
    assert "memory:out.wav" not in env.store.contents


def test_shutdown_stops_a_running_export_and_deletes_its_temp_file(env):
    FakeSynth.gate = threading.Event()
    env.session.export_audio()
    env.answer(env.store.ref("out.wav"))
    # Wait until the job is rendering into its temp file.
    for _ in range(200):
        if env.temp_files():
            break
        threading.Event().wait(0.01)
    assert len(env.temp_files()) == 1
    # The render in progress finishes its block a moment later.
    threading.Timer(0.2, FakeSynth.gate.set).start()
    env.session.shutdown()
    # Shutdown waited for the job: the temp file is already gone.
    assert env.temp_files() == []
    env.host.run_pending()
    assert "memory:out.wav" not in env.store.contents
    assert FakeSynth.instances[0].deleted


def test_startup_removes_only_stale_temp_files(tmp_path):
    import os
    import time

    cache = tmp_path / "cache"
    cache.mkdir()
    stale, fresh = cache / "audio-export-a.wav", cache / "audio-export-b.wav"
    for path in (stale, fresh):
        path.write_bytes(b"x")
    two_days_ago = time.time() - 2 * 86400
    os.utime(stale, (two_days_ago, two_days_ago))
    env = Env(tmp_path)
    assert env.temp_files() == ["audio-export-b.wav"]
    env.session.shutdown()
