.PHONY: run test tests build clean setup-dev icons docs docs-html docs-html-android docs-pdf flatpak flatpak-check snap snap-check

# Tools directory for local dependencies
TOOLS_DIR := .tools

# Variables
PYTHON := pipenv run python
PYINSTALLER := pipenv run pyinstaller
SPHINX_BUILD := pipenv run sphinx-build
SPEC_FILE := chord-notepad.spec
DOCS_SOURCE := help
DOCS_BUILD := help/build

# Run application
run: docs-html
	$(PYTHON) src/main.py

# Run tests
test:
	$(PYTHON) -m pytest tests/ -v

# Run tests (alias)
tests: test

# Set up development environment
setup-dev:
	@echo "Setting up development environment..."
ifeq ($(OS),Windows_NT)
	@echo "Detected Windows"
	@if not exist "$(TOOLS_DIR)\bin\libfluidsynth-3.dll" ( \
		echo Installing FluidSynth to $(TOOLS_DIR)... \
		& if not exist "$(TOOLS_DIR)" mkdir "$(TOOLS_DIR)" \
		& curl -L -o "$(TOOLS_DIR)\fluidsynth.zip" https://github.com/FluidSynth/fluidsynth/releases/download/v2.3.4/fluidsynth-2.3.4-win10-x64.zip \
		& tar -xf "$(TOOLS_DIR)\fluidsynth.zip" -C "$(TOOLS_DIR)" \
		& del "$(TOOLS_DIR)\fluidsynth.zip" \
		& echo FluidSynth installed successfully \
	) else ( \
		echo FluidSynth already installed \
	)
else
	@case "$$(uname -s)" in \
		Darwin) \
			echo "Detected macOS"; \
			if ! command -v brew >/dev/null 2>&1; then \
				echo "ERROR: Homebrew is required but not installed."; \
				echo "Install it from https://brew.sh/"; \
				exit 1; \
			fi; \
			echo "Installing dependencies via Homebrew..."; \
			brew install fluid-synth imagemagick || true; \
			;; \
		Linux) \
			echo "Detected Linux"; \
			echo ""; \
			echo "Please install the following system dependencies for your distribution:"; \
			echo ""; \
			echo "  Ubuntu/Debian:"; \
			echo "    sudo apt-get install fluidsynth libfluidsynth3 imagemagick"; \
			echo ""; \
			echo "  Fedora:"; \
			echo "    sudo dnf install fluidsynth fluidsynth-libs ImageMagick"; \
			echo ""; \
			echo "  Arch Linux:"; \
			echo "    sudo pacman -S fluidsynth imagemagick"; \
			echo ""; \
			;; \
		*) \
			echo "Unknown OS. Please install FluidSynth and ImageMagick manually."; \
			;; \
	esac
endif
	@echo "Installing Python dependencies..."
	pipenv install --dev
	@echo ""
	@echo "Setup complete! Run 'make run' to start the application."

# Generate icon files from SVG
icons:
	@echo "Generating icon files from SVG..."
	@# ImageMagick's built-in SVG renderer paints the icon's linked gradient
	@# black, so prefer librsvg (rsvg-convert) when it is installed.
	cd resources && \
	if command -v rsvg-convert >/dev/null; then \
		for size in 16 32 48 64 128 256; do \
			rsvg-convert -w $$size -h $$size chord-notepad-icon.svg -o icon-$$size.png || exit 1; \
		done && \
		magick icon-256.png icon-128.png icon-64.png icon-48.png icon-32.png icon-16.png chord-notepad-icon.ico && \
		rm icon-16.png icon-48.png icon-64.png; \
	else \
		magick -background none -density 300 chord-notepad-icon.svg -resize 32x32 -quality 100 icon-32.png && \
		magick -background none -density 300 chord-notepad-icon.svg -resize 128x128 -quality 100 icon-128.png && \
		magick -background none -density 600 chord-notepad-icon.svg -resize 256x256 -quality 100 icon-256.png && \
		magick -background none -density 600 chord-notepad-icon.svg -define icon:auto-resize=256,128,64,48,32,16 chord-notepad-icon.ico; \
	fi
	@echo "Icon files generated in resources/"

# Build all documentation (HTML + PDF)
docs: docs-html docs-pdf

# Build HTML documentation
docs-html:
	$(SPHINX_BUILD) -t desktop -b html $(DOCS_SOURCE) $(DOCS_BUILD)/html
	@echo "HTML documentation built in $(DOCS_BUILD)/html"

# Build the Android variant of the HTML documentation
docs-html-android:
	$(SPHINX_BUILD) -t android -b html $(DOCS_SOURCE) $(DOCS_BUILD)/html-android
	@echo "Android HTML documentation built in $(DOCS_BUILD)/html-android"

# Build PDF documentation using rinohtype
docs-pdf:
	$(SPHINX_BUILD) -t desktop -b rinoh $(DOCS_SOURCE) $(DOCS_BUILD)/rinoh
	@echo "PDF documentation built in $(DOCS_BUILD)/rinoh"

# Build executable (works for both Windows and Linux)
build: icons docs-html
	$(PYINSTALLER) --clean $(SPEC_FILE)
	@echo "Executable built successfully in dist/"
	@echo "On Windows: dist/ChordNotepad.exe"
	@echo "On Linux: dist/ChordNotepad"

# Clean build artifacts
# Build the Flatpak and export a single-file bundle to dist/.
# Uses flatpak-builder if installed, else the org.flatpak.Builder flatpak.
FLATPAK_ID := io.github.chibicitiberiu.ChordNotepad
FLATPAK_DIR := packaging/flatpak
FLATPAK_BUILDER := $(shell command -v flatpak-builder 2>/dev/null || echo flatpak run --user --no-documents-portal org.flatpak.Builder)

flatpak: icons docs-html
	cd $(FLATPAK_DIR) && $(FLATPAK_BUILDER) --user --install-deps-from=flathub \
		--disable-rofiles-fuse --force-clean --repo=repo build-dir $(FLATPAK_ID).yml
	mkdir -p dist
	flatpak build-bundle --runtime-repo=https://dl.flathub.org/repo/flathub.flatpakrepo \
		$(FLATPAK_DIR)/repo dist/ChordNotepad-linux-x64.flatpak $(FLATPAK_ID)
	@echo "Bundle: dist/ChordNotepad-linux-x64.flatpak"

# Install the bundle (user) and import every app module on the real runtime.
flatpak-check:
	flatpak install --user -y --noninteractive --reinstall dist/ChordNotepad-linux-x64.flatpak
	flatpak run --command=python3 $(FLATPAK_ID) - < packaging/linux/smoke_test.py

# Build the snap (snap/snapcraft.yaml) into dist/. Needs snapcraft and LXD;
# CI passes SNAPCRAFT="sudo snapcraft".
SNAPCRAFT ?= snapcraft

snap: icons docs-html
	mkdir -p dist
	$(SNAPCRAFT) pack --use-lxd --output dist/ChordNotepad-linux-x64.snap
	@echo "Snap: dist/ChordNotepad-linux-x64.snap"

# Install the local snap and import every app module inside its confinement.
snap-check:
	sudo snap install --dangerous dist/ChordNotepad-linux-x64.snap
	snap run --shell chord-notepad -c '"$$SNAP/bin/python3" - "$$SNAP/share/chord-notepad"' < packaging/linux/smoke_test.py

clean:
	rm -rf build/ dist/ __pycache__ .pytest_cache
	rm -rf $(DOCS_BUILD)
	rm -f resources/icon-*.png resources/*.ico
	rm -rf $(FLATPAK_DIR)/.flatpak-builder $(FLATPAK_DIR)/build-dir $(FLATPAK_DIR)/repo
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
