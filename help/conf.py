# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
project = 'Chord Notepad User Guide'
copyright = '2024, Chord Notepad'
author = 'Chord Notepad'
release = '1.0'

# -- General configuration ---------------------------------------------------
extensions = []

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
