"""
Thin bottom status strip: where you are on the left, what the app is on
the right.

The right-hand side is handed its text rather than reading the settings
itself — a widget that imports configuration is a widget you cannot put
on screen without an environment behind it. The licence chip between them
is the same: it is told what to say and never asks.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from app.presentation.theme import tokens as t
from app.presentation.widgets.qss import repolish


SEPARATOR = "   •   "


class _LicenseChip(QLabel):
    """The licence warning, where it can be seen without being in the way.

    A chip rather than a banner: a licence with a fortnight left is worth
    knowing about every day, and a strip across the top of every screen
    for a fortnight is a strip people stop seeing. Clicking it goes to the
    Licence page, so the warning leads somewhere.
    """

    clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("role", "tag")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Open the licence page")
        self.hide()

    def show_notice(self, text: str, tone: str) -> None:
        self.setText(text)
        self.setProperty("tone", tone)
        repolish(self)
        self.show()

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().mousePressEvent(event)
        self.clicked.emit()


class AppStatusBar(QWidget):
    licenseClicked = Signal()

    def __init__(
        self,
        app_version: str,
        developed_by: str,
        developer_email: str,
        developer_contact: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("StatusBar")
        # Required for the #StatusBar rule's background to be painted at
        # all — see the note in theme/stylesheet.py.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(t.STATUSBAR_HEIGHT)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 14, 0)

        self._label = QLabel("")
        self._label.setStyleSheet(f"color: {t.MUTED}; font-size: 11px;")
        layout.addWidget(self._label)
        layout.addStretch(1)

        self._license = _LicenseChip()
        self._license.clicked.connect(self.licenseClicked.emit)
        layout.addWidget(self._license)
        layout.addSpacing(12)

        about = QLabel(
            SEPARATOR.join(
                ["Local database", f"v{app_version}", f"Developed by: {developed_by}", 
                #  f"{developer_email}", f"{developer_contact}"
                 ]
            )
        )
        about.setStyleSheet(f"color: {t.MUTED}; font-size: 11px;")
        layout.addWidget(about)

    def set_page(self, page_name: str, hint: str = "") -> None:
        """`hint` is whatever is true of the *current* screen — the shortcut
        line used to name one module regardless of where you actually were."""
        self._label.setText(f"{page_name}{SEPARATOR}{hint}" if hint else page_name)

    def set_license_notice(self, text: str, tone: str) -> None:
        """Show the licence chip, or hide it when `text` is empty.

        A licence in order says nothing: an indicator that is always
        present is one nobody reads when it changes.
        """
        if not text:
            self._license.clear()
            self._license.hide()
            return
        self._license.show_notice(text, tone)
