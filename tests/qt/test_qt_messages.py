"""Qt's own messages go to logging (plan step C3)."""

import logging

import pytest

from tests.conftest import QT_PROBLEM

if QT_PROBLEM:
    pytest.skip(f"Qt not available: {QT_PROBLEM}", allow_module_level=True)

from PySide6.QtCore import qInfo  # noqa: E402
from PySide6.QtQml import QQmlComponent, QQmlEngine  # noqa: E402

from chordnotepad_desktop.qt_messages import install_message_handler, logger_name  # noqa: E402


def test_logger_names():
    assert logger_name("qt.qpa.xcb") == "qt.qpa.xcb"
    assert logger_name("qml") == "qt.qml"
    assert logger_name(None) == logger_name("") == "qt.default"


def test_qt_messages_are_logged_and_still_reach_the_previous_handler(qapp, qtlog, caplog):
    caplog.set_level(logging.DEBUG)
    uninstall = install_message_handler()
    try:
        qInfo("hello from Qt")
    finally:
        uninstall()
    record = next(r for r in caplog.records if r.getMessage() == "hello from Qt")
    assert record.name == "qt.default" and record.levelno == logging.INFO
    # pytest-qt's handler (installed before ours) still saw it.
    assert any(r.message == "hello from Qt" for r in qtlog.records)


def test_a_qml_message_names_its_file_and_line(qapp, caplog, tmp_path):
    caplog.set_level(logging.DEBUG)
    qml = tmp_path / "Hello.qml"
    qml.write_text('import QtQuick\nItem { Component.onCompleted: console.info("from QML") }\n',
                   encoding="utf-8")
    uninstall = install_message_handler()
    try:
        engine = QQmlEngine()
        component = QQmlComponent(engine, str(qml))
        item = component.create()
        assert item is not None, component.errorString()
    finally:
        uninstall()
    record = next(r for r in caplog.records if r.getMessage().startswith("from QML"))
    assert record.name == "qt.qml" and record.levelno == logging.INFO
    assert "Hello.qml:2" in record.getMessage()


def test_uninstall_stops_the_logging(qapp, caplog):
    caplog.set_level(logging.DEBUG)
    install_message_handler()()
    qInfo("after uninstall")
    assert not [r for r in caplog.records if r.getMessage() == "after uninstall"]
