"""Licence screen: what this installation is licensed to do, and until when.

Read-only apart from two buttons. Everything shown here comes out of the
signed licence itself, so it is also the page a shop reads back to its
supplier when something is wrong.
"""
from __future__ import annotations

from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from app.domain.licensing.state import LicenseState
from app.presentation.dialogs.activation_dialog import ActivationDialog
from app.presentation.dialogs.confirm import confirm_destructive
from app.presentation.formatting import DASH, counted, date_only
from app.presentation.license_display import status_label, status_tone
from app.presentation.viewmodels.license_viewmodel import LicenseViewModel
from app.presentation.widgets.page_header import PageHeader
from app.presentation.widgets.page_scroll import page_scroll
from app.presentation.widgets.qss import repolish

_DETAILS = (
    ("Customer", "customer"),
    ("Plan", "plan"),
    ("Licence ID", "license_id"),
    ("Expires", "expires"),
    ("Devices allowed", "devices"),
    ("Features", "features"),
    ("Installation ID", "installation"),
)


class LicenseView(QWidget):
    def __init__(self, view_model: LicenseViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view_model = view_model
        # Held from the last signal: the activation dialog needs a state to
        # open showing, and the view model reads off the UI thread.
        self._state = LicenseState.not_activated()

        outer = QVBoxLayout(page_scroll(self))
        outer.setContentsMargins(24, 20, 24, 24)
        outer.setSpacing(0)

        header = PageHeader(
            ("Settings", "Licence"),
            "Licence",
            "What this installation is licensed for, and how long it runs.",
        )
        header.add_action("Deactivate", self._deactivate)
        header.add_action("Enter licence key", self._change_license, variant="primary")
        outer.addWidget(header)
        outer.addSpacing(16)

        outer.addWidget(self._build_panel())
        outer.addStretch(1)

        self._view_model.stateChanged.connect(self._on_state_changed)
        self._view_model.errorOccurred.connect(self._on_error)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 (Qt override)
        super().showEvent(event)
        self._view_model.load()

    # ---------------- building ----------------

    def _build_panel(self) -> QFrame:
        panel = QFrame()
        panel.setProperty("role", "panel")

        column = QVBoxLayout(panel)
        column.setContentsMargins(18, 16, 18, 18)
        column.setSpacing(12)

        status_row = QHBoxLayout()
        status_row.setSpacing(10)
        self._pill = QLabel(DASH)
        self._pill.setProperty("role", "tag")
        self._pill.setProperty("tone", "muted")
        status_row.addWidget(self._pill)
        status_row.addStretch(1)
        column.addLayout(status_row)

        self._message = QLabel("")
        self._message.setProperty("role", "panelSub")
        self._message.setWordWrap(True)
        self._message.hide()
        column.addWidget(self._message)

        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(10)
        grid.setColumnStretch(1, 1)

        self._values: dict[str, QLabel] = {}
        for row, (label_text, key) in enumerate(_DETAILS):
            label = QLabel(label_text)
            label.setProperty("role", "fieldLabel")
            value = QLabel(DASH)
            value.setWordWrap(True)
            grid.addWidget(label, row, 0)
            grid.addWidget(value, row, 1)
            self._values[key] = value

        column.addLayout(grid)
        return panel

    # ---------------- view model ----------------

    def _on_state_changed(self, state: LicenseState) -> None:
        self._state = state
        self._pill.setText(status_label(state))
        self._pill.setProperty("tone", status_tone(state))
        repolish(self._pill)

        self._message.setText(state.message or "")
        self._message.setVisible(bool(state.message))

        self._values["installation"].setText(self._view_model.installation_id)

        entitlement = state.entitlement
        if entitlement is None:
            for key in ("customer", "plan", "license_id", "expires", "devices", "features"):
                self._values[key].setText(DASH)
            return

        self._values["customer"].setText(entitlement.customer_name or DASH)
        self._values["plan"].setText(entitlement.plan_code or DASH)
        self._values["license_id"].setText(entitlement.license_id)
        self._values["expires"].setText(self._expiry_text(state))
        self._values["devices"].setText(counted(entitlement.max_devices, "device"))
        self._values["features"].setText(
            ", ".join(sorted(entitlement.features)) if entitlement.features else DASH
        )

    @staticmethod
    def _expiry_text(state: LicenseState) -> str:
        entitlement = state.entitlement
        if entitlement is None or entitlement.is_perpetual:
            return "Never — perpetual licence"
        expires = date_only(entitlement.expires_at)
        if state.days_remaining is None:
            return expires
        return f"{expires} ({counted(state.days_remaining, 'day')} left)"

    def _on_error(self, message: str) -> None:
        QMessageBox.warning(self, "Licence", message)

    # ---------------- actions ----------------

    def _change_license(self) -> None:
        dialog = ActivationDialog(
            self._view_model,
            state=self._state,
            blocked=False,
            parent=self,
        )
        dialog.exec()
        self._view_model.refresh()

    def _deactivate(self) -> None:
        if not confirm_destructive(
            self,
            title="Deactivate licence",
            message=(
                "Remove this licence from this computer?\n\n"
                "The app will not open again until a licence key is entered."
            ),
            confirm_label="Deactivate",
            cancel_label="Keep licence",
        ):
            return
        self._view_model.deactivate()
