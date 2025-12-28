.PHONY: run test tests build clean setup-dev icons docs docs-html docs-pdf

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
	cd resources && \
	magick -background none -density 300 chord-notepad-icon.svg -resize 32x32 -quality 100 icon-32.png && \
	magick -background none -density 300 chord-notepad-icon.svg -resize 128x128 -quality 100 icon-128.png && \
	magick -background none -density 600 chord-notepad-icon.svg -resize 256x256 -quality 100 icon-256.png && \
	magick -background none -density 600 chord-notepad-icon.svg -define icon:auto-resize=256,128,64,48,32,16 chord-notepad-icon.ico
	@echo "Icon files generated in resources/"

# Build all documentation (HTML + PDF)
docs: docs-html docs-pdf

# Build HTML documentation
docs-html:
	$(SPHINX_BUILD) -b html $(DOCS_SOURCE) $(DOCS_BUILD)/html
	@echo "HTML documentation built in $(DOCS_BUILD)/html"

# Build PDF documentation using rinohtype
docs-pdf:
	$(SPHINX_BUILD) -b rinoh $(DOCS_SOURCE) $(DOCS_BUILD)/rinoh
	@echo "PDF documentation built in $(DOCS_BUILD)/rinoh"

# Build executable (works for both Windows and Linux)
build: icons docs-html
	$(PYINSTALLER) --clean $(SPEC_FILE)
	@echo "Executable built successfully in dist/"
	@echo "On Windows: dist/ChordNotepad.exe"
	@echo "On Linux: dist/ChordNotepad"

# Clean build artifacts
clean:
	rm -rf build/ dist/ __pycache__ .pytest_cache
	rm -rf $(DOCS_BUILD)
	rm -f resources/icon-*.png resources/*.ico
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
