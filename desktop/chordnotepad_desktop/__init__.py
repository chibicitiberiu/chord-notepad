"""Chord Notepad's Qt Quick desktop front end (``--ui qt``), being built.

It replaces the Tk front end (``chordnotepad_tk``) at the 0.6.0 switch. It
talks to the core (``chordnotepad``) only, never to ``chordnotepad_tk``,
which is deleted the release after; the one exception is the shared entry
point (``chordnotepad_tk.main``), which starts it.

Keep this file free of imports: the entry point checks that PySide6 is
installed before it imports anything from here.

Layout:

* ``main.py``: start-up (:func:`chordnotepad_desktop.main.run`) and the
  window loading.
* ``application.py``: :class:`QtApplication`, the lifecycle (start-up order,
  the close flow, shutdown), the window's identity and icon.
* ``qt_host.py``, ``session_store.py``: the session on the Qt event loop, and
  its states, events, requests and commands for QML (over the bridge).
* ``error_presenter.py``, ``qt_messages.py``: errors shown in the window, Qt's
  messages in the log.
* ``rendering.py``: GPU or software rendering.
* ``window_geometry.py``: the window's saved size and place.
* ``editor_bridge.py``, ``offsets.py``, ``editor_font.py``: the editor's text
  between the TextArea and the session (highlighting, the session's edits,
  paste normalisation), code points and UTF-16, the editor's font and zoom.
* ``fonts.py``, ``icons.py``, ``dpr.py``, ``alt_watcher.py``: the mockup's
  scaling and text recipe, the icon provider, the hidden menu bar's keys.
* ``qml/CNTheme``: the Theme singleton (colours, units, type) and the
  pixel-snapping helpers SnapTranslate, SText and SnapLine.
* ``qml/CNStyle``: the Controls style, the one look on every OS.
* ``qml/app``: the window.

Qt Quick pitfalls met while building the mockup (parity checklist §13).
Each is also noted where it applies, as "pitfall N":

1. A property named ``on<Capital>`` is read as a signal handler (Theme.qml).
2. Names like ``display`` and ``right`` clash with FINAL properties of
   controls and Text (IconText.qml).
3. Templates controls have zero implicit size: each CNStyle control sets its
   own (Button.qml).
4. A negative ``z`` also puts an item below its parent for input
   (PopupBackground.qml).
5. A DragHandler inside a button doesn't work; use a MouseArea with
   ``preventStealing`` (the tempo readout and the timeline, E1/E2; the
   palette tiles, F5).
6. One handler per piano key fires for two keys where they overlap; hit-test
   the keyboard centrally, black keys first (the identifier piano, F5).
7. Menu has no Repeater: use ``createObject`` and ``addItem`` (Menu.qml;
   VoicingMenu.qml, InstrumentMenu.qml).
8. Keep a Python reference to the ``QQuickTextDocument`` wrapper, or it is
   collected under the highlighter (editor_bridge.py).
9. On KDE Wayland the ratio from Screen or QML is wrong; read it from the
   window in Python (dpr.py).
10. Text laid out at an old ratio keeps its glyph positions: bump the font
    revision and call ``releaseResources`` (dpr.py, Theme.qml).
11. Hinting isn't inherited: set it on every font; Inter with full hinting
    breaks (fonts.py, Theme.qml).
12. Layouts position children in the polish pass, so snapping is debounced
    to the next frame (Theme.bumpLayout).
13. A 1 px line comes out 1 or 2 device pixels wide; snap it (Theme.hairline,
    SnapLine.qml).
14. IconImage blurs at a fractional ratio; use PixelIcon and the provider
    (icons.py, PixelIcon.qml).
15. The software backend has no MultiEffect (PopupBackground.qml).
16. A disabled control gets no hover: hang its tooltip off a HoverHandler
    (ToolTip.qml; the locked voicing button, PlayerBar.qml).
17. Elide with TextMetrics, so the unsaved dot after a title stays visible
    (the title, C4; the player bar's title block, PlayerBar.qml).
18. There is no Alt-only shortcut, and a hidden MenuBar has no mnemonics: an
    event filter on window events only (alt_watcher.py).
19. The ▾ value chip needs a sticky hover region and a grace period, or it
    vanishes on the way to it (EditorPane.qml).
20. SpinBox holds integers: scale fractional values and commit typed text on
    Enter (SpinBox.qml).
21. Menus use ``popupType: Popup.Item``; macOS keeps the native menu bar
    (Menu.qml).
22. ``QTest.keyClicks`` takes a QWidget only: tests send key events to the
    QQuickWindow (tests/qt/conftest.py).
23. A popup takes focus only in ``onOpened`` (Popup.qml, ValuePicker.qml,
    the speed dropdown's box).
24. An ``inline:`` URL hangs ``engine.load``: load from a file (main.py).
25. Repeater delegates aren't in the QObject tree, so ``findChild`` misses
    them (tests/qt/conftest.py; tests/qt/test_qt_value_picker.py walks the
    visual tree).
26. DialogButtonBox ignores ``highlighted``: the footer is our own row
    (Dialog.qml).
"""
