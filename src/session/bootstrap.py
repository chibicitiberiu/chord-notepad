"""Building the core without a toolkit: services, viewmodels, the session.

The desktop ``Application`` and the Android host (``chordnotepad_android
.host``) build the same core; only the host, the document store and the
audio options differ::

    services = build_core_services(appdata, HostDispatch(host))
    session = create_session(host, services, documents)   # on the session thread
    session.start()

Nothing here imports Tk; :func:`create_session` imports the chord-sheet
viewmodel (and with it the headless renderers) only when a chord sheet is
asked for.
"""

import logging
from dataclasses import dataclass
from typing import Any, Optional

from audio.audio_options import AudioOptions
from audio.player_interface import IPlayer
from constants import CHORD_DETECTION_DEBOUNCE_MS
from services.appdata_service import AppDataService
from services.config_service import ConfigService
from services.file_service import FileService
from services.playback_service import PlaybackService
from services.song_parser_service import SongParserService
from session.documents import DocumentStore
from session.host import Host, HostDispatch
from session.session import AppSession
from session.workers import BackgroundWorker

logger = logging.getLogger(__name__)


@dataclass
class CoreServices:
    """The services every UI shares, built by :func:`build_core_services`.

    Attributes:
        appdata: Where config, logs and caches live.
        config: The settings (loaded).
        song_parser: Chord detection and music-theory helpers.
        playback: Audio: song playback and click-to-hear.
        files: Local file I/O (the desktop's document store sits on it).
    """

    appdata: AppDataService
    config: ConfigService
    song_parser: SongParserService
    playback: PlaybackService
    files: FileService


def build_core_services(appdata: AppDataService, dispatch: Any, *,
                        player: Optional[IPlayer] = None,
                        audio_options: Optional[AudioOptions] = None) -> CoreServices:
    """Create the core services in dependency order and load the config.

    Args:
        appdata: The data directories (created here if missing).
        dispatch: Anything with ``queue_ui_callback(cb)`` that posts to the
            session thread: the desktop ``Application``, or
            ``HostDispatch(host)``. Playback pings go through it.
        player: A ready player (tests, a headless run); None creates the
            FluidSynth player the first time audio is needed.
        audio_options: Synth settings from the host (Android: sample rate,
            period size, Oboe settings); None for the desktop defaults.
    """
    appdata.ensure_directories_exist()
    config = ConfigService(appdata)
    config.load_config()
    return CoreServices(
        appdata=appdata,
        config=config,
        song_parser=SongParserService(),
        playback=PlaybackService(config, player=player, application=dispatch,
                                 audio_options=audio_options),
        files=FileService(config),
    )


def create_session(host: Host, services: CoreServices, documents: DocumentStore, *,
                   dispatch: Any = None, chord_sheet: bool = True,
                   worker: Optional[BackgroundWorker] = None,
                   detection_delay_s: float = CHORD_DETECTION_DEBOUNCE_MS / 1000,
                   ) -> AppSession:
    """Build the viewmodels over ``services`` and the session that composes them.

    Call it on the session thread: the chord-sheet viewmodel and the session
    may arm timers. Start the session (``session.start()``) once the host
    runs timers.

    Args:
        host: Owns the session thread.
        services: From :func:`build_core_services`.
        documents: Where documents are read and written and the recent list
            kept (desktop: ``FileSystemDocumentStore``).
        dispatch: What the viewmodels post through (``queue_ui_callback``);
            ``HostDispatch(host)`` by default.
        chord_sheet: Build the chord-sheet strip (its renderers import the
            chord-sheet drawing code).
        worker: The session's background worker; a new one by default.
        detection_delay_s: The typing debounce before chords are re-detected.
    """
    from viewmodels.main_window_viewmodel import MainWindowViewModel
    from viewmodels.text_editor_viewmodel import TextEditorViewModel

    dispatch = dispatch if dispatch is not None else HostDispatch(host)
    main = MainWindowViewModel(
        services.config, services.playback, documents, services.song_parser, dispatch)
    detector = TextEditorViewModel(services.song_parser)
    sheet = None
    if chord_sheet:
        # Renders through the playback service's note picker off the session
        # thread; debounces and marshals its results through the host.
        from viewmodels.chord_sheet_viewmodel import ChordSheetViewModel
        sheet = ChordSheetViewModel(services.config, services.playback, host=host)
    return AppSession(
        host,
        main_window_viewmodel=main,
        text_editor_viewmodel=detector,
        chord_sheet_viewmodel=sheet,
        worker=worker,
        detection_delay_s=detection_delay_s,
        services=services,
    )
