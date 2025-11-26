# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None

# Get absolute path to src directory
src_path = os.path.abspath('src')

# Collect data files (soundfont, icons, and documentation)
datas = [
    ('resources/soundfont/GeneralUser-GS.sf2', 'resources/soundfont'),
    ('resources/icon-32.png', 'resources'),
    ('resources/icon-128.png', 'resources'),
    ('resources/icon-256.png', 'resources'),
    # Bundle HTML documentation for in-app help
    ('help/build/html', 'help/build/html'),
]

# Hidden imports - all our local modules
hiddenimports = [
    'ui',
    'ui.main_window',
    'ui.text_editor',
    'ui.help_window',
    'ui.help_viewer',
    'audio',
    'audio.player',
    'audio.chord_picker',
    'chord',
    'chord.converter',
    # pywebview for help documentation viewer
    'webview',
]

# Exclude unused GUI frameworks that pywebview might pull in
excludes = [
    'PyQt5',
    'PyQt6',
    'PySide2',
    'PySide6',
    'wx',
]

a = Analysis(
    ['src/main.py'],
    pathex=[src_path],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ChordNotepad',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window for GUI app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='resources/chord-notepad-icon.ico',  # Windows icon
)
