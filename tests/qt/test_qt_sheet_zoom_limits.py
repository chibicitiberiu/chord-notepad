"""The Qt chord sheet's zoom limits: ChordSheetModel's constants come from
the core's (``chord_sheet_viewmodel.ZOOM_MIN``/``ZOOM_MAX``)."""

from PySide6.QtCore import QObject, Signal

from chordnotepad.viewmodels.chord_sheet_viewmodel import ZOOM_MAX, ZOOM_MIN
from chordnotepad_desktop.chord_sheet import ChordSheetModel


class _State:
    def value(self, _key):
        return None


class _Store(QObject):
    stateChanged = Signal(str)

    def state(self, _name):
        return _State()


def test_the_model_exposes_the_zoom_limits(qtbot):
    model = ChordSheetModel(_Store())
    assert (model.property("zoomMin"), model.property("zoomMax")) == (ZOOM_MIN, ZOOM_MAX)
    assert (ZOOM_MIN, ZOOM_MAX) == (0.5, 2.5)
