# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None

# Get absolute path to src directory
src_path = os.path.abspath('src')

# Collect data files (soundfont)
datas = [
    ('resources/soundfont/GeneralUser-GS.sf2', 'resources/soundfont'),
]

# Hidden imports - all our local modules
hiddenimports = [
    'ui',
    'ui.main_window',
    'ui.text_editor',
    'audio',
    'audio.player',
    'audio.chord_picker',
    'chord',
    'chord.converter',
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
    excludes=[],
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
)
