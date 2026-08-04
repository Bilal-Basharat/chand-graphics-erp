"""
"I've forgotten my password", from the sign-in screen.

Asks for the account's email and nothing else — anybody who could answer
a further question could also sign in. What comes back is a temporary
password in that mailbox, which is the proof of ownership.

The confirmation is deliberately left to the sign-in screen behind this
dialog: the user's next move is to type the temporary password into the
form that is already there, and a message box would only stand between
them and it.
"""
from __future__ import annotations

from PySide6.QtWidgets import QLineEdit, QWidget

from app.presentation.dialogs.form_dialog import FormDialog
from app.presentation.viewmodels.session_viewmodel import SessionViewModel


class ForgotPasswordDialog(FormDialog):
    def __init__(
        self,
        view_model: SessionViewModel,
        email: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            title="Forgot password",
            subtitle="We'll email a temporary password to your account.",
            submit_label="Send temporary password",
            parent=parent,
        )
        self._view_model = view_model
        self.bind(view_model.passwordResetSent, view_model.errorOccurred)

        self._email = QLineEdit(email)
        self._email.setPlaceholderText("you@example.com")
        self.add_row("Email", self._email, required=True)

        self.add_note(
            "Sign in with the temporary password, then change it from "
            "My profile. Your current password stops working as soon as "
            "the email is sent."
        )

    def build_command(self) -> str | None:
        return self._email.text().strip()

    def submit_command(self, command: str) -> None:
        self._view_model.request_password_reset(command)
