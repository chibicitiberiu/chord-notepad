# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
import os

project = 'Chord Notepad User Guide'
copyright = '2024-2026, Chord Notepad'
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
    'voicings_settings': (':menuselection:`Tools --> Settings...` --> Voicings',
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

    tokens = {
        'root': [
            # Comments - everything after //
            (r'//.*$', Comment),
            # Directives - {anything}
            (r'\{[^}]+\}', Name.Decorator),
            # Chords - American notation with optional modifiers and duration
            # Matches: C, Am, G7, Cmaj7, F#m7b5, C/G, Am*2, etc.
            (r'[A-G][#b]?'                    # Root note (C, C#, Db, etc.)
             r'(?:m|min|maj|dim|aug)?'        # Quality (m, min, maj, dim, aug)
             r'(?:M|Δ)?'                      # Major 7 symbols
             r'(?:sus[24]?)?'                 # Suspended
             r'(?:add)?'                      # Add chords
             r'(?:[2679]|11|13)?'             # Extensions
             r'(?:b5|#5|b9|#9|#11|b13)?'      # Alterations
             r'(?:/[A-G][#b]?)?'              # Slash bass note
             r'(?:\*[\d.]+)?',                # Duration modifier
             Keyword),
            # European notation chords (Do, Re, Mi, Fa, Sol, La, Si)
            (r'(?:Do|Re|Mi|Fa|Sol|La|Si)[#b]?'
             r'(?:m|min|maj|dim|aug)?'
             r'(?:M|Δ)?'
             r'(?:sus[24]?)?'
             r'(?:add)?'
             r'(?:[2679]|11|13)?'
             r'(?:b5|#5|b9|#9|#11|b13)?'
             r'(?:/(?:Do|Re|Mi|Fa|Sol|La|Si)[#b]?)?'
             r'(?:\*[\d.]+)?',
             Keyword),
            # Roman numerals (I, ii, IV, V7, etc.)
            (r'[#b]?'                         # Optional accidental
             r'(?:VII|VII|VI|IV|III|II|I|vii|vi|iv|iii|ii|i|V|v)'  # Numeral
             r'(?:°|dim|aug|maj|m)?'          # Quality
             r'(?:[2679]|11|13)?'             # Extensions
             r'(?:b5|#5)?'                    # Alterations
             r'(?:/[#b]?(?:VII|VI|IV|III|II|I|vii|vi|iv|iii|ii|i|V|v))?',  # Slash
             Keyword),
            # Whitespace
            (r'\s+', Whitespace),
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
