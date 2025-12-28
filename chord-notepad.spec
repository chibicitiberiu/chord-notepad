# -*- mode: python ; coding: utf-8 -*-
import os
import sys
import glob

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

# Collect FluidSynth DLLs on Windows
binaries = []
if sys.platform == 'win32':
    # Look for FluidSynth DLLs in the environment variable set by the build workflow
    fluidsynth_path = os.environ.get('FLUIDSYNTH_PATH', '')
    if fluidsynth_path and os.path.isdir(fluidsynth_path):
        # Collect all DLLs from the FluidSynth bin directory
        for dll in glob.glob(os.path.join(fluidsynth_path, '*.dll')):
            binaries.append((dll, 'fluidsynth'))
        print(f"Found {len(binaries)} FluidSynth DLLs in {fluidsynth_path}")
    else:
        # Try common local development paths
        local_paths = [
            os.path.join(os.path.dirname(__file__), '.tools', 'bin'),
            r'C:\tools\fluidsynth\bin',
        ]
        for path in local_paths:
            if os.path.isdir(path):
                for dll in glob.glob(os.path.join(path, '*.dll')):
                    binaries.append((dll, 'fluidsynth'))
                print(f"Found {len(binaries)} FluidSynth DLLs in {path}")
                break
        if not binaries:
            print("WARNING: FluidSynth DLLs not found. Set FLUIDSYNTH_PATH or install to C:\\tools\\fluidsynth")

# Runtime hooks - handle FluidSynth DLL loading on Windows
runtime_hooks = []
if sys.platform == 'win32':
    runtime_hooks.append('hooks/hook-fluidsynth.py')

# Hidden imports - all our local modules
hiddenimports = [
    'ui',
    'ui.main_window',
    'ui.text_editor',
    'ui.help_window',
    'audio',
    'audio.player',
    'audio.chord_picker',
    'chord',
    'chord.converter',
]

# Exclude unused GUI frameworks
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
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=runtime_hooks,
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
