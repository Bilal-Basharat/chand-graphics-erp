from __future__ import annotations

import os

import pytest


@pytest.fixture(scope="session")
def qt_app():
    """The one application every widget in this folder is built under.

    A widget cannot exist without a QApplication, and there may only ever
    be one per process — so it is made once and left running. Offscreen,
    because these tests exercise widgets rather than show them, and a test
    run should not throw windows at whoever started it.
    """
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])
