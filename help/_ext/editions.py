"""Desktop / Android editions of the User Guide.

The guide builds once per platform (``-t desktop`` or ``-t android``). This
extension gives the sources the pieces that ``.. only::`` alone can't:

``.. platform-figure:: <name>``
    A figure whose image is ``images/<platform>/<name>.png`` for the edition
    being built (or ``images/shared/<name>.png`` with ``:shared:``). A missing
    image for the active platform is an error, so ``-W`` builds catch an
    incomplete edition. ``:platforms: desktop`` limits the figure to one
    edition. ``:desktop-caption:`` / ``:android-caption:`` and
    ``:desktop-alt:`` / ``:android-alt:`` override the shared caption (the
    body) and ``:alt:``. In the Android edition an optional
    ``<name>.dark.png`` next to the image is shown when the page is dark.

``:plat:`desktop text|android text```
    Inline choice between two short texts. Either side may be empty, and
    may hold inline markup that needs no backquotes (``**bold**``).

``|click|`` and friends
    Substitutions defined per platform in conf.py (``help_terms``).

``:platforms: desktop`` (file-wide field at the very top of a page)
    The page is only part of that edition. The other edition excludes the
    file and drops it from toctrees silently; ``:doc:`` links to it from
    shared text still fail, so wrap those in ``.. only::``.

docs/HELP_AUTHORING.md has the authoring guide.
"""

from __future__ import annotations

import os
import posixpath
import re
import urllib.parse
from typing import Any

from docutils import nodes
from docutils.parsers.rst import directives
from docutils.statemachine import StringList
from sphinx import addnodes
from sphinx.application import Sphinx
from sphinx.config import Config
from sphinx.directives.patches import Figure
from sphinx.util import logging
from sphinx.util.docutils import SphinxDirective, SphinxRole

logger = logging.getLogger(__name__)

PLATFORMS = ('desktop', 'android')
IMAGE_EXTENSIONS = ('.png', '.svg', '.jpg', '.jpeg', '.webp')
# Where the images live, relative to the source directory.
IMAGE_ROOT = 'images'
SHARED = 'shared'
# Pages say ":platforms: desktop" before their title (file-wide metadata).
_PAGE_PLATFORMS = re.compile(r'^:platforms:\s*(.+?)\s*$')
# The build's tags, for ``.. only::`` around a figure (set at config-inited).
_TAGS: dict[str, Any] = {}


def _platform_list(value: str) -> list[str]:
    """Option converter for ``:platforms:``: names separated by spaces or commas."""
    names = [p for p in re.split(r'[\s,]+', value or '') if p]
    for name in names:
        if name not in PLATFORMS:
            raise ValueError(f'unknown platform {name!r} (expected one of {", ".join(PLATFORMS)})')
    if not names:
        raise ValueError('at least one platform is needed')
    return names


class dark_image(nodes.image):
    """The dark-mode variant of a figure's image (``<source>`` in a ``<picture>``)."""


class picture(nodes.General, nodes.Element):
    """A ``<picture>``: a :class:`dark_image` then the regular image."""


class PlatformFigure(Figure, SphinxDirective):
    """``.. platform-figure:: <name>``: a figure resolved per edition."""

    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = False
    option_spec = dict(Figure.option_spec)
    option_spec.update({
        'platforms': _platform_list,
        'shared': directives.flag,
        'desktop-alt': directives.unchanged,
        'android-alt': directives.unchanged,
        'desktop-caption': directives.unchanged,
        'android-caption': directives.unchanged,
    })

    def run(self) -> list[nodes.Node]:
        """Resolve the image for the active platform and build the figure."""
        platform = self.config.help_platform
        name = self.arguments[0]
        if platform not in self.options.get('platforms', PLATFORMS) or self._in_excluded_only():
            return []

        folder = SHARED if 'shared' in self.options else platform
        rel = self._find_image(folder, name)
        if rel is None:
            tried = ', '.join(f'{IMAGE_ROOT}/{folder}/{name}{ext}' for ext in self._extensions(name))
            msg = (f'platform-figure {name!r}: no image for the {platform} edition '
                   f'(looked for {tried}). Add the image, or limit the figure with '
                   f'":platforms:".')
            logger.error(msg, location=self.get_location())
            # A re-read once the image appears (a missing dependency always
            # counts as changed).
            self.env.note_dependency(os.path.join(self.env.srcdir, IMAGE_ROOT, folder, name))
            return []

        for key in ('platforms', 'shared'):
            self.options.pop(key, None)
        alt = self.options.pop(f'{platform}-alt', None)
        caption = self.options.pop(f'{platform}-caption', None)
        for other in PLATFORMS:
            self.options.pop(f'{other}-alt', None)
            self.options.pop(f'{other}-caption', None)
        if alt is not None:
            self.options['alt'] = alt
        if caption is not None:
            self.content = StringList(caption.splitlines(), source=self.get_source_info()[0])
        self.arguments = ['/' + rel]

        result = super().run()

        dark = self._dark_variant(rel) if platform == 'android' else None
        if dark is not None:
            for image in (n for r in result for n in r.findall(nodes.image)):
                variant = dark_image(uri='/' + dark, alt=image.get('alt', ''))
                # A link around the <img> would take it out of the <picture>.
                image['classes'].append('no-scaled-link')
                wrapper = picture()
                image.replace_self(wrapper)
                wrapper += variant
                wrapper += image
                break
        return result

    def _in_excluded_only(self) -> bool:
        """Inside an ``.. only::`` this build drops (parsed all the same)."""
        tags = _TAGS.get('tags')
        node = self.state.parent
        while node is not None and tags is not None:
            if isinstance(node, addnodes.only) and not tags.eval_condition(node['expr']):
                return True
            node = node.parent
        return False

    @staticmethod
    def _extensions(name: str) -> tuple[str, ...]:
        return ('',) if os.path.splitext(name)[1] else IMAGE_EXTENSIONS

    def _find_image(self, folder: str, name: str) -> str | None:
        """The image's path relative to the source dir, or None if missing."""
        for ext in self._extensions(name):
            rel = f'{IMAGE_ROOT}/{folder}/{name}{ext}'
            if os.path.isfile(os.path.join(self.env.srcdir, rel)):
                return rel
        return None

    def _dark_variant(self, rel: str) -> str | None:
        """``foo.dark.png`` next to ``foo.png`` if it exists (optional)."""
        stem, ext = os.path.splitext(rel)
        dark = f'{stem}.dark{ext}'
        path = os.path.join(self.env.srcdir, dark)
        # Noted either way: adding the variant later re-reads the page.
        self.env.note_dependency(path)
        return dark if os.path.isfile(path) else None


class PlatRole(SphinxRole):
    """``:plat:`desktop|android```: the side for the active edition."""

    def run(self) -> tuple[list[nodes.Node], list[nodes.system_message]]:
        """Pick the text for the active platform and parse its inline markup."""
        parts = self.text.split('|')
        if len(parts) != 2:
            msg = self.inliner.reporter.error(
                f':plat: needs exactly one "|" between the desktop and Android text: {self.rawtext}',
                line=self.lineno)
            return [self.inliner.problematic(self.rawtext, self.rawtext, msg)], [msg]
        text = parts[PLATFORMS.index(self.config.help_platform)]
        if not text:
            return [], []
        return self.inliner.parse(text, self.lineno, self.inliner, self.inliner.parent)


def _page_platforms(path: str) -> list[str] | None:
    """The ``:platforms:`` field before the page's title, if any."""
    with open(path, encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            match = _PAGE_PLATFORMS.match(line)
            if match:
                return _platform_list(match.group(1))
            if not line.startswith(':'):
                return None
    return None


def _on_config_inited(app: Sphinx, config: Config) -> None:
    _TAGS['tags'] = app.tags
    if config.help_platform is None:
        config.help_platform = 'android' if app.tags.has('android') else 'desktop'
    if config.help_platform not in PLATFORMS:
        raise ValueError(f'help_platform must be one of {PLATFORMS}, not {config.help_platform!r}')

    # Pages limited to other editions are left out of this one.
    excluded = []
    for root, dirs, files in os.walk(app.srcdir):
        dirs[:] = [d for d in dirs if not d.startswith(('_', '.')) and d != 'build']
        for file in files:
            if file.endswith('.rst'):
                path = os.path.join(root, file)
                platforms = _page_platforms(path)
                if platforms and config.help_platform not in platforms:
                    excluded.append(os.path.relpath(path, app.srcdir).replace(os.sep, '/'))
    config.exclude_patterns = list(config.exclude_patterns) + excluded
    # Toctrees list every page; the ones this edition excludes just drop out.
    config.suppress_warnings = list(config.suppress_warnings) + ['toc.excluded']

    # |term| substitutions, per platform.
    lines = []
    for term, values in (config.help_terms or {}).items():
        value = dict(zip(PLATFORMS, values))[config.help_platform]
        lines.append(f'.. |{term}| replace:: {value}')
    if lines:
        config.rst_prolog = (config.rst_prolog or '') + '\n' + '\n'.join(lines) + '\n'


def _on_doctree_read(app: Sphinx, doctree: nodes.document) -> None:
    # The |term| definitions come from rst_prolog into every page; they are
    # applied by now, and left in they would put "click" etc. in every
    # page's search terms.
    terms = set(app.config.help_terms or {})
    for node in list(doctree.findall(nodes.substitution_definition)):
        if terms.intersection(node['names']):
            node.parent.remove(node)


def _on_doctree_resolved(app: Sphinx, doctree: nodes.document, docname: str) -> None:
    # Only HTML knows <picture>; everything else gets the plain image.
    if app.builder.format == 'html':
        return
    for node in list(doctree.findall(picture)):
        node.replace_self([c for c in node.children if not isinstance(c, dark_image)])


def _visit_picture(self: Any, node: picture) -> None:
    self.body.append('<picture>')


def _depart_picture(self: Any, node: picture) -> None:
    self.body.append('</picture>')


def _visit_dark_image(self: Any, node: dark_image) -> None:
    uri = node['uri']
    if uri in self.builder.images:  # as HTML5Translator.visit_image does
        uri = posixpath.join(self.builder.imgpath, urllib.parse.quote(self.builder.images[uri]))
    self.body.append(f'<source srcset="{self.attval(uri)}" media="(prefers-color-scheme: dark)">')
    raise nodes.SkipNode


def _skip(self: Any, node: nodes.Node) -> None:
    raise nodes.SkipNode


def setup(app: Sphinx) -> dict[str, Any]:
    """Register the directive, role, nodes and config values."""
    # None: worked out from the -t tag (android, else desktop).
    app.add_config_value('help_platform', None, 'env', types=frozenset({str, type(None)}))
    # {name: (desktop text, android text)} -> |name| substitutions.
    app.add_config_value('help_terms', {}, 'env', types=frozenset({dict}))
    app.add_node(picture, html=(_visit_picture, _depart_picture))
    app.add_node(dark_image, html=(_visit_dark_image, None),
                 text=(_skip, None), latex=(_skip, None), man=(_skip, None), texinfo=(_skip, None))
    app.add_directive('platform-figure', PlatformFigure)
    app.add_role('plat', PlatRole())
    app.connect('config-inited', _on_config_inited)
    app.connect('doctree-read', _on_doctree_read)
    app.connect('doctree-resolved', _on_doctree_resolved)
    return {'version': '1.0', 'parallel_read_safe': True, 'parallel_write_safe': True}
