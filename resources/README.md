# Resources

This directory contains application resources.

## Icons

**Source:** `chord-notepad-icon.svg`
- This is the master icon file
- Edit this file to change the application icon

**Generated Files:**
- `icon-32.png` - Window icon (32x32)
- `icon-128.png` - About dialog icon (128x128)
- `icon-256.png` - High resolution icon (256x256)
- `chord-notepad-icon.ico` - Windows executable icon (multi-resolution)

These PNG and ICO files are auto-generated from the SVG and are not tracked in git.

### Generating Icons

**Locally:**
```bash
make icons
```

**During build:**
```bash
make build  # Automatically generates icons first
```

**In CI:**
Icons are automatically generated during the GitHub Actions build process.

### Requirements

- ImageMagick 7+ (`magick` command)
- Install on Fedora: `sudo dnf install ImageMagick`
- Install on Ubuntu: `sudo apt install imagemagick`
- Install on macOS: `brew install imagemagick`

## Soundfont

**soundfont/GeneralUser-GS.sf2**
- FluidSynth soundfont for MIDI playback
- Licensed under GeneralUser GS License
- See `soundfont/GeneralUser-GS.LICENSE.txt` for details
