"""PlaybackService.stop_playback doesn't wait for the render thread.

A start lock orders the render thread's "check cancel -> start the player"
against stop's "cancel -> stop the player", so a stop that lands while the
song is still being rendered never lets the player start, however the
threads interleave. These tests use real threads.
"""

import random
import threading
import time
from unittest.mock import patch

from services.playback_service import PlaybackService
from services.song_parser_service import SongParserService
from services.song_renderer import SongRenderer
from session.testing import FakePlayer


class FakeConfig:
    def __init__(self, **values):
        self._values = dict(values)

    def get(self, key, default=None):
        return self._values.get(key, default)

    def set(self, key, value):
        self._values[key] = value


class Dispatch:
    """Collects posted callbacks without running them."""

    def __init__(self):
        self.posted = []

    def queue_ui_callback(self, cb):
        self.posted.append(cb)


def make_service():
    player = FakePlayer(auto_play=False)
    return PlaybackService(FakeConfig(), player=player, application=Dispatch()), player


def song():
    return SongParserService().detect_chords_in_text("C G Am F\nDm G C", "american")


def test_stop_returns_while_the_render_is_still_running_and_the_player_never_starts():
    service, player = make_service()
    entered, release = threading.Event(), threading.Event()
    real_render = SongRenderer.render

    def slow_render(self, *args, **kwargs):
        entered.set()
        release.wait(10)
        return real_render(self, *args, **kwargs)

    with patch.object(SongRenderer, "render", slow_render):
        assert service.start_song_playback(song(), None)
        assert entered.wait(10)
        began = time.monotonic()
        service.stop_playback()
        assert time.monotonic() - began < 0.5  # used to join for up to 2 s
        thread = service._render_thread
        assert thread.is_alive()
        release.set()
        thread.join(10)

    assert "start" not in player.calls
    assert not player.is_playing


def test_a_new_render_waits_for_the_stopped_one_so_they_never_share_the_picker():
    service, player = make_service()
    release = threading.Event()
    active, overlaps, calls = [], [], []
    lock = threading.Lock()
    real_render = SongRenderer.render

    def tracked_render(self, *args, **kwargs):
        with lock:
            if active:
                overlaps.append(True)
            active.append(1)
            calls.append(threading.current_thread())
        try:
            if len(calls) == 1:
                release.wait(10)
            return real_render(self, *args, **kwargs)
        finally:
            with lock:
                active.pop()

    with patch.object(SongRenderer, "render", tracked_render):
        assert service.start_song_playback(song(), None)
        first = service._render_thread
        service.stop_playback()
        assert service.start_song_playback(song(), None)
        second = service._render_thread
        time.sleep(0.05)
        assert len(calls) == 1  # the second render is waiting for the first
        release.set()
        first.join(10)
        second.join(10)

    assert overlaps == []
    # Only the second run started the player.
    assert player.calls.count("start") == 1 and player.calls[-1] == "start"
    assert player.is_playing


def test_stress_stop_during_render_never_leaves_the_player_running():
    service, player = make_service()
    lines = song()
    rng = random.Random(1234)
    real_compile = __import__("services.event_compiler", fromlist=["compile_events"]).compile_events

    def jittery_compile(*args, **kwargs):
        # Widen the window between rendering and starting the player.
        time.sleep(rng.random() * 0.002)
        return real_compile(*args, **kwargs)

    started = 0
    with patch("services.playback_service.compile_events", jittery_compile):
        for i in range(200):
            assert service.start_song_playback(lines, None)
            if i % 4 == 0:
                # Now and then let it start first (bounded wait).
                deadline = time.monotonic() + 5
                while not player.is_playing and time.monotonic() < deadline:
                    time.sleep(0.001)
            else:
                delay = rng.random() * 0.01
                if delay > 0.002:
                    time.sleep(delay)
            service.stop_playback()
            thread = service._render_thread
            thread.join(10)
            assert not thread.is_alive()
            # Whichever thread got the start lock first, the player is off now.
            assert not player.is_playing, player.calls[-4:]
            started += player.calls.count("start")
            player.calls.clear()
    # Both orders happen (a stop before the start, and after it); the
    # assertion above has to hold for each.
    assert started > 0


def test_a_failed_render_after_a_stop_reports_nothing():
    service, player = make_service()
    finished, errors = [], []
    entered, release = threading.Event(), threading.Event()

    def broken_render(self, *args, **kwargs):
        entered.set()
        release.wait(10)
        raise ValueError("render broke")

    with patch.object(SongRenderer, "render", broken_render):
        service.start_song_playback(song(), None, on_finished_callback=lambda: finished.append(1),
                                    on_error_callback=errors.append)
        assert entered.wait(10)
        service.stop_playback()
        release.set()
        service._render_thread.join(10)

    assert finished == [] and errors == []
    assert "start" not in player.calls


def test_cleanup_cancels_a_render_in_flight():
    service, player = make_service()
    entered, release = threading.Event(), threading.Event()
    real_render = SongRenderer.render

    def slow_render(self, *args, **kwargs):
        entered.set()
        release.wait(10)
        return real_render(self, *args, **kwargs)

    with patch.object(SongRenderer, "render", slow_render):
        service.start_song_playback(song(), None)
        assert entered.wait(10)
        service.cleanup()
        release.set()
        service._render_thread.join(10)

    assert "start" not in player.calls
