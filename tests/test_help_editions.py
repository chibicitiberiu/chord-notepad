"""The User Guide's platform-edition extension (help/_ext/editions.py).

Each test builds a tiny Sphinx project with the extension, for one edition.
"""

import io
import sys
from pathlib import Path

import pytest

pytest.importorskip('sphinx')
from sphinx.application import Sphinx  # noqa: E402
from sphinx.util.docutils import docutils_namespace  # noqa: E402

EXT_DIR = Path(__file__).resolve().parent.parent / 'help' / '_ext'
PNG = (Path(__file__).resolve().parent.parent / 'help' / 'images' / 'shared' / 'jazz-clash.png').read_bytes()

CONF = """
import sys
sys.path.insert(0, {ext!r})
extensions = ['editions']
help_terms = {{'click': ('click', 'tap')}}
"""

INDEX = """
Guide
=====

.. toctree::

   both
   desktop_only
   android_only
"""


def build(tmp_path: Path, platform: str, pages: dict[str, str], images: list[str] = (),
          builder: str = 'html', warningiserror: bool = False) -> tuple[Path, str]:
    """Build ``pages`` (name -> body) for ``platform``; returns (outdir, warnings)."""
    src = tmp_path / 'src'
    src.mkdir(parents=True)
    (src / 'conf.py').write_text(CONF.format(ext=str(EXT_DIR)))
    (src / 'index.rst').write_text(INDEX)
    for name, body in pages.items():
        (src / f'{name}.rst').write_text(body)
    for image in images:
        path = src / 'images' / image
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(PNG)
    out = tmp_path / 'out'
    warnings = io.StringIO()
    # A fresh docutils registry per app, as sphinx.testing does.
    with docutils_namespace():
        app = Sphinx(str(src), str(src), str(out), str(tmp_path / 'doctrees'), builder,
                     status=None, warning=warnings, freshenv=True,
                     warningiserror=warningiserror, tags=[platform])
        app.build()
    sys.modules.pop('editions', None)
    return out, warnings.getvalue()


DEFAULT_PAGES = {
    'both': 'Both\n====\n\nShared text.\n',
    'desktop_only': ':platforms: desktop\n\nDesktop page\n============\n\nKeys.\n',
    'android_only': ':platforms: android\n\nAndroid page\n============\n\nTouch.\n',
}


def pages_with(both: str) -> dict[str, str]:
    """The default pages, with ``both.rst``'s body replaced."""
    return {**DEFAULT_PAGES, 'both': 'Both\n====\n\n' + both}


@pytest.mark.parametrize('platform', ['desktop', 'android'])
def test_page_sets(tmp_path, platform):
    out, warnings = build(tmp_path, platform, DEFAULT_PAGES)
    assert 'WARNING' not in warnings and 'ERROR' not in warnings, warnings
    other = 'android' if platform == 'desktop' else 'desktop'
    assert (out / f'{platform}_only.html').exists()
    assert not (out / f'{other}_only.html').exists()
    index = (out / 'index.html').read_text()
    assert f'{platform}_only.html' in index and f'{other}_only.html' not in index


def test_plat_role_and_terms(tmp_path):
    body = 'Now :plat:`**press** it|tap it` and |click| here, :plat:`|android only`.\n'
    out, warnings = build(tmp_path, 'android', pages_with(body))
    html = (out / 'both.html').read_text()
    assert 'Now tap it and tap here, android only.' in html
    out, _ = build(tmp_path / 'd', 'desktop', pages_with(body))
    html = (out / 'both.html').read_text()
    assert 'Now <strong>press</strong> it and click here, .' in html


def test_figure_resolves_per_platform(tmp_path):
    body = """
.. platform-figure:: shot
   :alt: Shared alt
   :android-alt: Phone alt
   :android-caption: The **phone**.

   The window.
"""
    images = ['desktop/shot.png', 'android/shot.png']
    out, warnings = build(tmp_path, 'android', pages_with(body), images)
    html = (out / 'both.html').read_text()
    assert 'alt="Phone alt"' in html and 'The <strong>phone</strong>.' in html
    assert '<picture>' not in html  # no dark variant
    out, _ = build(tmp_path / 'd', 'desktop', pages_with(body), images)
    html = (out / 'both.html').read_text()
    assert 'alt="Shared alt"' in html and 'The window.' in html


def test_missing_image_is_an_error(tmp_path):
    body = '.. platform-figure:: shot\n\n   Caption.\n'
    _, warnings = build(tmp_path, 'android', pages_with(body), ['desktop/shot.png'])
    assert 'ERROR' in warnings and 'android/shot' in warnings


def test_platforms_option_skips_other_edition(tmp_path):
    body = '.. platform-figure:: shot\n   :platforms: desktop\n\n   Desktop only caption.\n'
    out, warnings = build(tmp_path, 'android', pages_with(body), ['desktop/shot.png'])
    assert 'ERROR' not in warnings
    assert 'Desktop only caption' not in (out / 'both.html').read_text()


def test_shared_and_dark_variant(tmp_path):
    body = '.. platform-figure:: diagram\n   :shared:\n   :width: 100%\n\n   Diagram.\n'
    images = ['shared/diagram.png', 'shared/diagram.dark.png']
    out, warnings = build(tmp_path, 'android', pages_with(body), images)
    assert 'WARNING' not in warnings and 'ERROR' not in warnings, warnings
    html = (out / 'both.html').read_text()
    assert '<picture><source srcset="_images/diagram.dark.png" media="(prefers-color-scheme: dark)">' in html
    assert (out / '_images' / 'diagram.dark.png').exists()
    # The desktop edition ignores dark variants.
    out, _ = build(tmp_path / 'd', 'desktop', pages_with(body), images)
    html = (out / 'both.html').read_text()
    assert '<picture>' not in html and 'diagram.dark' not in html
    # Non-HTML builders get the plain image.
    out, warnings = build(tmp_path / 't', 'android', pages_with(body), images, builder='text')
    assert 'ERROR' not in warnings


def test_rejects_unknown_platform(tmp_path):
    body = '.. platform-figure:: shot\n   :platforms: ios\n'
    _, warnings = build(tmp_path, 'desktop', pages_with(body), ['desktop/shot.png'])
    assert 'unknown platform' in warnings


def test_figure_inside_other_editions_only_block_is_skipped(tmp_path):
    # ``.. only::`` content is parsed in every build; the figure must not
    # demand an image for an edition that drops it.
    body = '.. only:: desktop\n\n   .. platform-figure:: shot\n\n      Caption.\n'
    _, warnings = build(tmp_path, 'android', pages_with(body), ['desktop/shot.png'])
    assert 'ERROR' not in warnings, warnings
