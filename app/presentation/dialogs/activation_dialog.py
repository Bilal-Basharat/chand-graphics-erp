"""Where a shop turns a licence key into a working installation.

Opens in one of two situations, and the difference matters:

* **Blocked** — the app cannot start. Nothing is behind this dialog, so
  it also has to offer the two things a locked-out shop legitimately
  needs: a way to enter the renewed key, and a way to take its own data
  out. A shop that has stopped paying still owns its trading records.
* **Changing** — the app is running and the owner is entering a renewal
  from the licence screen. Cancel simply closes it.
"""
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.domain.licensing.state import LicenseState
from app.presentation.license_display import status_label, status_tone
from app.presentation.viewmodels.license_viewmodel import LicenseViewModel
from app.presentation.widgets.form_field import field
from app.presentation.widgets.qss import repolish

logger = logging.getLogger(__name__)

_BACKUP_FILTER = "Database backup (*.db)"
_KEY_BOX_HEIGHT = 96


class ActivationDialog(QDialog):
    def __init__(
        self,
        view_model: LicenseViewModel,
        *,
        state: LicenseState,
        blocked: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self._blocked = blocked

        self.setWindowTitle("Licence activation")
        self.setMinimumWidth(560)
        self.setModal(True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 22, 24, 20)
        outer.setSpacing(14)

        outer.addLayout(self._build_heading(state))
        outer.addLayout(self._build_installation_row())
        outer.addLayout(self._build_key_box())

        self._error = QLabel("")
        self._error.setObjectName("FormError")
        self._error.setWordWrap(True)
        self._error.hide()
        outer.addWidget(self._error)

        outer.addLayout(self._build_actions())

        self._view_model.stateChanged.connect(self._on_state_changed)
        self._view_model.errorOccurred.connect(self._show_error)
        self._view_model.busyChanged.connect(self._on_busy)

    # ---------------- building ----------------

    def _build_heading(self, state: LicenseState) -> QVBoxLayout:
        column = QVBoxLayout()
        column.setSpacing(6)

        title = QLabel("Activate this installation")
        title.setProperty("role", "pageTitle")
        column.addWidget(title)

        self._pill = QLabel(status_label(state))
        self._pill.setProperty("role", "tag")
        self._pill.setProperty("tone", status_tone(state))
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(self._pill)
        row.addStretch(1)
        column.addLayout(row)

        self._reason = QLabel(state.message or "")
        self._reason.setProperty("role", "pageSub")
        self._reason.setWordWrap(True)
        self._reason.setVisible(bool(state.message))
        column.addWidget(self._reason)

        return column

    def _build_installation_row(self) -> QVBoxLayout:
        installation_id = self._view_model.installation_id

        value = QLabel(installation_id)
        # Selectable because the whole point of this row is getting the id
        # to the vendor, and a shop without a working clipboard button
        # should still be able to read it out or copy it by hand.
        value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        copy = QPushButton("Copy")
        copy.setProperty("variant", "outline")
        copy.clicked.connect(lambda: self._copy(installation_id))

        holder = QWidget()
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        row.addWidget(value, 1)
        row.addWidget(copy)

        return field("Installation ID — quote this when asking for a licence", holder)

    def _build_key_box(self) -> QVBoxLayout:
        self._key = QPlainTextEdit()
        self._key.setPlaceholderText("Paste the licence key you were sent")
        self._key.setFixedHeight(_KEY_BOX_HEIGHT)

        load = QPushButton("Load from file…")
        load.setProperty("variant", "outline")
        load.clicked.connect(self._load_from_file)

        block = field("Licence key", self._key)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(load)
        block.addLayout(row)
        return block

    def _build_actions(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        if self._blocked:
            backup = QPushButton("Back up my data")
            backup.setProperty("variant", "outline")
            backup.clicked.connect(self._back_up)
            row.addWidget(backup)

        row.addStretch(1)

        cancel = QPushButton("Exit" if self._blocked else "Cancel")
        cancel.setProperty("variant", "outline")
        cancel.clicked.connect(self.reject)
        row.addWidget(cancel)

        self._activate = QPushButton("Activate")
        self._activate.setProperty("variant", "primary")
        self._activate.setDefault(True)
        self._activate.clicked.connect(self._submit)
        row.addWidget(self._activate)

        return row

    # ---------------- actions ----------------

    def _submit(self) -> None:
        license_key = self._key.toPlainText().strip()
        if not license_key:
            self._show_error("Please paste the licence key you were sent.")
            self._key.setFocus()
            return
        self._error.hide()
        self._view_model.activate(license_key)

    def _load_from_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open licence file", "", "Licence files (*.lic *.txt);;All files (*)"
        )
        if not path:
            return
        try:
            self._key.setPlainText(Path(path).read_text(encoding="utf-8").strip())
        except OSError as exc:
            logger.warning("Could not read licence file %s: %s", path, exc)
            self._show_error("That file could not be read.")

    def _copy(self, text: str) -> None:
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)

    def _back_up(self) -> None:
        """Let a locked-out shop take its own trading records with it."""
        # Imported here rather than at module scope: this dialog is built
        # before the app has decided it may run at all, and nothing about
        # showing it should pull in the database layer.
        from app.infrastructure.db.backup import backup_database

        suggested = f"chand-graphics-backup-{date.today():%Y-%m-%d}.db"
        path, _ = QFileDialog.getSaveFileName(self, "Back up data", suggested, _BACKUP_FILTER)
        if not path:
            return

        try:
            written = backup_database(Path(path))
        except Exception as exc:  # sqlite3.Error, OSError, FileNotFoundError
            logger.exception("Data backup failed")
            QMessageBox.warning(self, "Back up data", f"The backup could not be written.\n\n{exc}")
            return

        QMessageBox.information(self, "Back up data", f"Your data was copied to:\n\n{written}")

    # ---------------- view model ----------------

    def _on_state_changed(self, state: LicenseState) -> None:
        self._pill.setText(status_label(state))
        self._pill.setProperty("tone", status_tone(state))
        repolish(self._pill)

        if state.is_usable:
            self.accept()
            return

        # Reached when a key verifies but still does not open the app —
        # a licence that is genuine and suspended, say. `activate` would
        # have raised for those, so this is belt and braces around a
        # future provider that reports rather than raises.
        self._show_error(state.message or "This licence cannot be used on this installation.")

    def _show_error(self, message: str) -> None:
        self._error.setText(message)
        self._error.show()

    def _on_busy(self, busy: bool) -> None:
        self._activate.setEnabled(not busy)
