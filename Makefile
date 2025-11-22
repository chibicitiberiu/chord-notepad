.PHONY: run test build clean install icons

# Variables
PYTHON := pipenv run python
PYINSTALLER := pipenv run pyinstaller
SPEC_FILE := chord-notepad.spec

# Run application
run:
	$(PYTHON) src/main.py

# Run tests
test:
	$(PYTHON) -m pytest tests/

# Install dependencies
install:
	pipenv install --dev

# Generate icon files from SVG
icons:
	@echo "Generating icon files from SVG..."
	cd resources && \
	magick -background none -density 300 chord-notepad-icon.svg -resize 32x32 -quality 100 icon-32.png && \
	magick -background none -density 300 chord-notepad-icon.svg -resize 128x128 -quality 100 icon-128.png && \
	magick -background none -density 600 chord-notepad-icon.svg -resize 256x256 -quality 100 icon-256.png && \
	magick -background none -density 600 chord-notepad-icon.svg -define icon:auto-resize=256,128,64,48,32,16 chord-notepad-icon.ico
	@echo "Icon files generated in resources/"

# Build executable (works for both Windows and Linux)
build: icons
	$(PYINSTALLER) --clean $(SPEC_FILE)
	@echo "Executable built successfully in dist/"
	@echo "On Windows: dist/ChordNotepad.exe"
	@echo "On Linux: dist/ChordNotepad"

# Clean build artifacts
clean:
	rm -rf build/ dist/ __pycache__ .pytest_cache
	rm -f resources/icon-*.png resources/*.ico
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
