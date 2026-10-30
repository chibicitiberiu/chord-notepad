# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
import os

project = 'Chord Notepad User Guide'
copyright = '2024-2026, Chord Notepad'
_COPYRIGHT = copyright


def setup(app):
    # Sphinx rewrites the copyright's last year to SOURCE_DATE_EPOCH's
    # (config-inited, priority 800). The APK build pins that epoch to 2023
    # for reproducible HTML, which turned the footer into "2024-2023".
    def keep_copyright(_app, config):
        config.copyright = _COPYRIGHT
    app.connect('config-inited', keep_copyright, priority=900)
author = 'Chord Notepad'

# Keep the guide's version in sync with the application's VERSION file so the
# title page never drifts from the released version.
with open(os.path.join(os.path.dirname(__file__), '..', 'VERSION')) as _vf:
    release = _vf.read().strip()
version = release

# -- General configuration ---------------------------------------------------
# The guide builds in two variants: ``-t desktop`` and ``-t android``. A plain
# build (CI) is the desktop guide.
if not (tags.has('desktop') or tags.has('android')):  # noqa: F821
    tags.add('desktop')  # noqa: F821

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '_ext'))

# Platform editions: platform-figure, :plat:, |terms|, per-platform pages
# (docs/HELP_AUTHORING.md).
extensions = ['editions']

# |name| substitutions: (desktop text, android text). Use them where only a
# word differs; anything longer goes in ``.. only::`` blocks.
help_terms = {
    'click': ('click', 'tap'),
    'Click': ('Click', 'Tap'),
    'clicks': ('clicks', 'taps'),
    'clicking': ('clicking', 'tapping'),
    'Clicking': ('Clicking', 'Tapping'),
    'settings': (':menuselection:`Tools --> Settings...`', '**☰ → Settings**'),
    'voicings_settings': (':menuselection:`Tools --> Settings... --> Voicings`',
                          '**☰ → Settings → Voicings**'),
}

# Optional: PDF generation via rinohtype (only needed for make docs-pdf)
try:
    import rinoh
    extensions.append('rinoh.frontend.sphinx')
except ImportError:
    pass

templates_path = ['_templates']
exclude_patterns = ['build', 'Thumbs.db', '.DS_Store']

# -- Custom lexer for chord notation syntax highlighting ---------------------
from sphinx.highlighting import lexers
from pygments.lexer import RegexLexer
from pygments.token import Comment, Name, Keyword, Text, Whitespace


class ChordLexer(RegexLexer):
    """Pygments lexer for chord notation.

    Highlights:
    - Comments (// ...) in gray
    - Directives ({bpm: 120}) in purple
    - Chords (C, Am, G7, etc.) in blue
    """
    name = 'chord'
    aliases = ['chord']

    # The chord shapes of src/chord/detector.py, without the text-line
    # heuristics: a root, any run of quality/extension tokens (longest
    # alternatives first), a slash bass and a duration, ending the word.
    _mods = (r'(?:°|ø|\+|Δ|-|maj|min|mi|dim|aug|dom|alt|sus[24]?|add\d+|no\d+'
             r'|omit\d+|m|M|\d+|[#b♯♭]\d+|\([^)]+\))*')
    _euro = r'(?:D[oóò]|R[eéèê]|Mi|F[aáà]|Sol|L[aáà]|Si)[#b♯♭]?'
    _amer = r'[A-G][#b♯♭]?'
    _numeral = r'[#b♭]?(?:VII|VI|IV|III|II|I|vii|vi|iv|iii|ii|i|V|v)'
    _duration = r'(?:\*[\d.]+)?'
    _end = r'(?![\w#])'

    tokens = {
        'root': [
            # Comments - everything after //
            (r'//.*$', Comment),
            # Directives - {anything}
            (r'\{[^}]+\}', Name.Decorator),
            # No chord (a rest): NC, NC*2
            (r'NC' + _duration + _end, Keyword),
            # European chords (Do, Re, Mi, Fa, Sol, La, Si): before American,
            # which would take the D of Do and the F of Fa
            (_euro + _mods + r'(?:/' + _euro + r')?' + _duration + _end, Keyword),
            # American chords: C, Am, Cmaj7, F#m7b5, C5, C7b9b13, C/G, Am*2
            (_amer + _mods + r'(?:/' + _amer + r')?' + _duration + _end, Keyword),
            # Roman numerals: I, ii, V7, vii°, vi/I, bVII
            (_numeral + r'(?:°|ø|\+|dim|aug|maj|m)?(?:\d+)?(?:[#b]\d+)?'
             r'(?:/' + _numeral + r')?' + _duration + _end, Keyword),
            # Whitespace
            (r'\s+', Whitespace),
            # Any other word (lyrics, Gsus5): whole, so no chord is found
            # inside it
            (r'\w+', Text),
            # Everything else
            (r'.', Text),
        ]
    }


# Register the chord lexer
lexers['chord'] = ChordLexer()

# -- Options for HTML output -------------------------------------------------
html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']
html_css_files = ['custom.css']
html_show_sourcelink = False
html_copy_source = False

if tags.has('android'):  # noqa: F821
    # The in-app WebView (android/.../ui/help/UserGuideScreen.kt): a phone
    # stylesheet with the app's colours and dark mode, instead of the desktop
    # guide's coral.
    html_css_files = ['android.css']
    # Image height cap from the screen size (vh is 0 in the app's WebView).
    html_js_files = ['android.js']
    # No "Built with Sphinx ... Read the Docs" links out of the app.
    html_show_sphinx = False
    # An image wrapped in a link can't sit in a <picture> (dark variants);
    # the full-size image adds nothing on a phone anyway.
    html_scaled_image_link = False

# -- Options for rinohtype PDF output ----------------------------------------
rinoh_documents = [
    dict(
        doc='index',
        target='ChordNotepad-UserGuide',
        title='Chord Notepad User Guide',
        author='Chord Notepad Contributors',
        toctree_only=False,
    )
]
