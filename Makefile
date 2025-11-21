.PHONY: run test build clean install

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

# Build executable (works for both Windows and Linux)
build:
	$(PYINSTALLER) --clean $(SPEC_FILE)
	@echo "Executable built successfully in dist/"
	@echo "On Windows: dist/ChordNotepad.exe"
	@echo "On Linux: dist/ChordNotepad"

# Clean build artifacts
clean:
	rm -rf build/ dist/ __pycache__ .pytest_cache
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
