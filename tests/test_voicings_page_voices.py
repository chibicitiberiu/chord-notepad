"""Tk tests for the Voicings page's voices table: gaps, move buttons, the banner.

Builds the real :class:`~ui.dialogs.voicings_page.VoicingsPage` over a
:class:`SettingsViewModel` on a throwaway config and drives its widgets.
Needs a display (they skip without one).
"""

import pytest

tk = pytest.importorskip('tkinter')
from tkinter import ttk

from models.config import Config
from services.config_service import ConfigService
from settings_forms.voicing_texts import EDITOR_TEXTS
from viewmodels.settings_viewmodel import SettingsViewModel

TRIO = {
    'model': 'ensemble',
    'voices': [
        {'name': 'Lead', 'range': [57, 77]},
        {'name': 'Harmony', 'range': [53, 74]},
        {'name': 'Bass', 'range': [40, 60]},
    ],
    'max_spacing': [10, 19],
}


class _StubAppData:
    def __init__(self, path):
        self._path = path

    def get_config_file_path(self, filename=None):
        return self._path


@pytest.fixture
def root():
    try:
        instance = tk.Tk()
    except tk.TclError:
        pytest.skip("No display available for tkinter tests")
    instance.withdraw()
    ttk.Style(instance).theme_use('clam')
    yield instance
    instance.destroy()


@pytest.fixture
def page(root, tmp_path):
    from ui.dialogs.voicings_page import VoicingsPage

    service = ConfigService(_StubAppData(tmp_path / 'settings.json'))
    config = Config()
    config.voicings = {'Trio': dict(TRIO)}
    service._config = config
    vm = SettingsViewModel(service)
    page = VoicingsPage(root, vm)
    page.select_voicing('Trio')
    root.update_idletasks()
    return page


def _voices_frame(page):
    """The labelled frame holding the voices table."""
    def walk(widget):
        for child in widget.winfo_children():
            if isinstance(child, ttk.LabelFrame) and child.cget('text') == 'Voices':
                return child
            found = walk(child)
            if found is not None:
                return found
        return None
    return walk(page._form_host)


def _cell(page, row, column):
    frame = _voices_frame(page)
    widgets = frame.grid_slaves(row=row + 2, column=column)
    assert len(widgets) == 1
    return widgets[0]


def _button(page, row, text):
    frame = _voices_frame(page)
    for widget in frame.grid_slaves(row=row + 2):
        if isinstance(widget, ttk.Button) and widget.cget('text') == text:
            return widget
    raise LookupError(text)


def _names(page):
    return [row['name'] for row in page._form_values()['voices']]


def test_each_voice_has_a_gap_and_the_last_one_is_off(page):
    assert page._form_values()['voices'][0]['gap'] == '10'
    gap_column = 4
    assert _cell(page, 0, gap_column).get() == '10'
    assert _cell(page, 1, gap_column).get() == '19'
    last = _cell(page, 2, gap_column)
    assert last.instate(['disabled']) and last.get() == ''


def test_move_buttons_are_off_at_the_ends(page):
    assert _button(page, 0, '↑').instate(['disabled'])
    assert not _button(page, 0, '↓').instate(['disabled'])
    assert not _button(page, 2, '↑').instate(['disabled'])
    assert _button(page, 2, '↓').instate(['disabled'])


def test_moving_the_bottom_voice_to_the_top(page):
    _button(page, 2, '↑').invoke()
    _button(page, 1, '↑').invoke()
    assert _names(page) == ['Bass', 'Lead', 'Harmony']
    assert [row['gap'] for row in page._form_values()['voices']] == ['12', '10', '19']
    assert page._vm.get_voicings()['Trio']['max_spacing'] == [12, 10]
    # Harmony, now the bottom voice, still has its 19 in the form: back it goes.
    _button(page, 2, '↑').invoke()
    assert _names(page) == ['Bass', 'Harmony', 'Lead']
    assert page._vm.get_voicings()['Trio']['max_spacing'] == [12, 19]


def test_a_bad_gap_is_red_and_the_banner_asks_to_fix_it(page):
    entry = _cell(page, 0, 4)
    entry.delete(0, 'end')
    entry.insert(0, '0')
    page._commit_form()
    assert entry.cget('style') == 'Error.TSpinbox'
    assert page._banner.winfo_manager() == 'grid'
    # The marked field says what's wrong; the spec's message would only repeat it.
    assert page._banner.cget('text') == EDITOR_TEXTS['errors_banner']
    entry.delete(0, 'end')
    entry.insert(0, '7')
    page._commit_form()
    assert entry.cget('style') != 'Error.TSpinbox'
    assert page._banner.winfo_manager() == ''


def test_a_rule_across_fields_shows_under_the_banner(page):
    low = _cell(page, 0, 1)
    low.delete(0, 'end')
    low.insert(0, 'C7')
    page._commit_form()
    lines = page._banner.cget('text').split('\n')
    assert lines[0] == EDITOR_TEXTS['errors_banner']
    assert 'low < high' in lines[1]
