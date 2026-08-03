"""
Base class for the app's "create a record" modals.

Every module's create dialog is the same shape — labelled fields, a note,
Cancel/Save — so only the fields and the command differ. Subclasses build
their rows in `__init__`, then implement `build_command()`; everything
below is handled here:

- **Required-field validation** in one place, with focus moved to the
  offending field instead of only showing a message.
- **Double-submit protection.** Use-case calls are asynchronous, so
  without disabling the button while one is in flight, an impatient
  second click creates a second record.
- **Signal lifetime.** View models outlive the dialogs that use them, and
  a dialog parented to its view is not destroyed when `exec()` returns.
  Connections are therefore torn down in `done()` — otherwise the second
  open of a dialog has two live listeners, the third has three, and each
  create fires every stale handler.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from app.presentation.theme import tokens as t


class FormDialog(QDialog):
    def __init__(
        self,
        *,
        title: str,
        subtitle: str | None = None,
        submit_label: str = "Save",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(400)
        self.setModal(True)

        self._title = title
        self._required: list[tuple[str, QWidget]] = []
        self._connections: list[tuple[Any, Any]] = []

        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(20, 18, 20, 18)
        self._outer.setSpacing(14)

        heading = QLabel(title)
        heading.setProperty("role", "panelTitle")
        self._outer.addWidget(heading)

        if subtitle:
            sub = QLabel(subtitle)
            sub.setProperty("role", "panelSub")
            sub.setWordWrap(True)
            self._outer.addWidget(sub)

        self._form = QFormLayout()
        self._form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        self._form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        self._form.setHorizontalSpacing(14)
        self._form.setVerticalSpacing(10)
        self._outer.addLayout(self._form)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save
        )
        self._submit_button = self._buttons.button(QDialogButtonBox.StandardButton.Save)
        self._submit_button.setText(submit_label)
        self._submit_button.setProperty("variant", "primary")
        self._buttons.accepted.connect(self._on_submit)
        self._buttons.rejected.connect(self.reject)
        self._outer.addWidget(self._buttons)

    # ---------------- building ----------------

    def add_row(self, label: str, field: QWidget, *, required: bool = False) -> QWidget:
        self._form.addRow(f"{label} *" if required else label, field)
        if required:
            self._required.append((label, field))
        return field

    def set_row_visible(self, field: QWidget, visible: bool) -> None:
        """Show/hide a field together with its label, for forms whose shape
        depends on an earlier answer."""
        field.setVisible(visible)
        label = self._form.labelForField(field)
        if label is not None:
            label.setVisible(visible)

    def add_note(self, text: str) -> None:
        note = QLabel(text)
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {t.MUTED}; font-size: 12px;")
        self._outer.insertWidget(self._outer.count() - 1, note)

    def bind(self, created_signal, error_signal) -> None:
        """Close on a successful create, surface failures in place.

        Both are torn down in `done()` — see the class docstring.
        """
        self._connect(created_signal, self._on_created)
        self._connect(error_signal, self._on_error)

    def _connect(self, signal, slot) -> None:
        signal.connect(slot)
        self._connections.append((signal, slot))

    # ---------------- subclass hooks ----------------

    def build_command(self) -> Any | None:
        """Return the command to submit, or None to abort (having already
        told the user why)."""
        raise NotImplementedError

    def submit_command(self, command: Any) -> None:
        """Hand the command to the view model."""
        raise NotImplementedError

    # ---------------- submit flow ----------------

    def _on_submit(self) -> None:
        for label, field in self._required:
            if not _field_text(field):
                QMessageBox.warning(self, self._title, f"{label} is required.")
                field.setFocus()
                return

        command = self.build_command()
        if command is None:
            return

        self._submit_button.setEnabled(False)
        self.submit_command(command)

    def _on_created(self, *_result: Any) -> None:
        # Accepts any arity: the success signals differ by screen — the
        # collection ones carry the created record, `passwordChanged`
        # carries nothing. Requiring an argument raised a TypeError inside
        # the slot, which left this *modal* dialog open and therefore
        # blocked every other action in the window.
        self.accept()

    def _on_error(self, message: str) -> None:
        self._submit_button.setEnabled(True)
        QMessageBox.warning(self, self._title, message)

    def reject_with(self, message: str, field: QWidget | None = None) -> None:
        """Report a validation failure `build_command()` found, and put the
        cursor where the user has to fix it."""
        QMessageBox.warning(self, self._title, message)
        if field is not None:
            field.setFocus()

    def done(self, result: int) -> None:  # noqa: D102 (Qt override)
        for signal, slot in self._connections:
            signal.disconnect(slot)
        self._connections.clear()
        super().done(result)


def _field_text(field: QWidget) -> str:
    if isinstance(field, QLineEdit):
        return field.text().strip()
    getter = getattr(field, "toPlainText", None) or getattr(field, "currentText", None)
    return getter().strip() if getter else ""
