"""
PyInstaller build hook for chardet (overrides the pyinstaller-hooks-contrib one).

chardet >= 7 is compiled with mypyc. On Windows the wheel ships one
``<name>__mypyc`` extension per module inside ``chardet/pipeline``, but the
contrib helper reports them as top-level modules (``validity__mypyc``), which
PyInstaller then warns it cannot find. This hook builds the full dotted names
from the distribution's file list instead.
"""

from importlib import metadata

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


def _mypyc_modules(dist_name):
    """Return the dotted names of every mypyc extension a distribution ships."""
    modules = []
    for entry in metadata.distribution(dist_name).files or []:
        if '__mypyc' in entry.name:
            parts = list(entry.parts[:-1]) + [entry.name.split('.')[0]]
            modules.append('.'.join(parts))
    return modules


hiddenimports = _mypyc_modules('chardet') + collect_submodules('chardet.pipeline')
datas = collect_data_files('chardet')
