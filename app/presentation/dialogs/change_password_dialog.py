"""
Change password for the signed-in user.

Validation lives here as well as in the use case on purpose: the use case
enforces what must be true of the data, this enforces what the user needs
told *before* a round trip — that the confirmation doesn't match, or that
the new password is too short to be worth setting.
"""
from __future__ import annotations

from PySide6.QtWidgets import QLineEdit, QWidget

# The rule itself lives with the use case that enforces it; this dialog
# only repeats it early so the user hears it before a round trip.
from app.application.auth.use_cases import MINIMUM_PASSWORD_LENGTH
from app.presentation.dialogs.form_dialog import FormDialog
from app.presentation.viewmodels.session_viewmodel import SessionViewModel


class ChangePasswordDialog(FormDialog):
    def __init__(self, view_model: SessionViewModel, parent: QWidget | None = None) -> None:
        super().__init__(
            title="Change password",
            subtitle="You'll stay signed in on this computer after changing it.",
            submit_label="Change password",
            parent=parent,
        )
        self._view_model = view_model
        self.bind(view_model.passwordChanged, view_model.errorOccurred)

        self._current = self._password_row("Current password", required=True)
        self._new = self._password_row("New password", required=True)
        self._confirm = self._password_row("Confirm new password", required=True)

        self.add_note(
            f"Use at least {MINIMUM_PASSWORD_LENGTH} characters. If this computer "
            "remembers your sign-in details, they'll be updated automatically."
        )

    def _password_row(self, label: str, *, required: bool = False) -> QLineEdit:
        field = QLineEdit()
        field.setEchoMode(QLineEdit.EchoMode.Password)
        self.add_row(label, field, required=required)
        return field

    def build_command(self) -> tuple[str, str] | None:
        current = self._current.text()
        new_password = self._new.text()
        confirmation = self._confirm.text()

        if len(new_password) < MINIMUM_PASSWORD_LENGTH:
            self.reject_with(
                f"The new password must be at least {MINIMUM_PASSWORD_LENGTH} characters.",
                self._new,
            )
            return None

        if new_password != confirmation:
            self.reject_with("The new passwords don't match.", self._confirm)
            return None

        if new_password == current:
            self.reject_with("The new password must be different from the current one.", self._new)
            return None

        return current, new_password

    def submit_command(self, command: tuple[str, str]) -> None:
        current, new_password = command
        self._view_model.change_password(current, new_password)
