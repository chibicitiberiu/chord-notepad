"""Crafted song text must not freeze the parser.

The parser runs on every keystroke and on every file opened (Android's Open
with takes up to 5 MB). Each input here took the old code 30 s or more; the
new code takes milliseconds. The bound is a generous 5 s so a loaded, shared
machine can't make the tests flaky.

Each case runs in a child process with a hard timeout, so a regression fails
instead of hanging the suite. The child measures only the parse (not its own
start-up), through ``SongParserService.detect_chords_in_text`` and through
``transpose_text``.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / 'src'
BOUND_S = 5.0
# Start-up (imports) plus both paths at their bound; past this the child is killed.
CHILD_TIMEOUT_S = 60.0

CASES = {
    # A failing chord token with a long digit run (exponential backtracking).
    'digit_run': "'C' + '1' * 40 + 'x'",
    # Unclosed braces: the old directive pattern crossed them and backtracked.
    'open_braces': "'{' * 20000",
    'brace_x_line': "'{x' * 100000",
    # The old loop-count regex was quadratic on a long run of spaces.
    'loop_spaces': "'{loop: a' + ' ' * 200000 + 'x}'",
    # Each repeated label counted the newlines up to the first one (4 MB in;
    # the whole text stays under Android's 5 MB Open-with limit).
    'duplicate_labels': "'// ' + 'x' * 4000000 + '\\n' + '{label: a}\\n' * 25000",
    # Every directive was checked against every comment, and every line
    # against every directive.
    'directives_and_comments': "'{bpm: 100}\\n// c\\n' * 20000",
}

_CHILD = r'''
import json, logging, sys, time
sys.path.insert(0, sys.argv[1])
logging.disable(logging.CRITICAL)
from services.song_parser_service import SongParserService
from services.transpose_service import transpose_text
text = eval(sys.argv[2])
t = time.perf_counter()
SongParserService().detect_chords_in_text(text)
detect = time.perf_counter() - t
t = time.perf_counter()
transpose_text(text, 2, 'american')
transpose = time.perf_counter() - t
print(json.dumps({'detect': detect, 'transpose': transpose}))
'''


@pytest.mark.parametrize('case', sorted(CASES))
def test_crafted_input_parses_quickly(case):
    try:
        result = subprocess.run(
            [sys.executable, '-c', _CHILD, str(SRC), CASES[case]],
            capture_output=True, text=True, timeout=CHILD_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        pytest.fail(f"{case}: still parsing after {CHILD_TIMEOUT_S:.0f} s")
    assert result.returncode == 0, result.stderr
    timings = json.loads(result.stdout.strip().splitlines()[-1])
    for path, seconds in timings.items():
        assert seconds < BOUND_S, f"{case} via {path} took {seconds:.2f} s"
