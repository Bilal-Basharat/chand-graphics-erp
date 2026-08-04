"""
Change the address you sign in with.

The database is seeded with a placeholder admin address so somebody can
get in on day one. This is how the person who actually uses the account
replaces it — which also means the confirmation copy has to be blunt
about the consequence: the old address stops working immediately.
"""
from __future__ import annotations

from PySide6.QtWidgets import QLineEdit, QWidget

from app.presentation.dialogs.form_dialog import FormDialog
from app.presentation.viewmodels.session_viewmodel import SessionViewModel


class ChangeEmailDialog(FormDialog):
    def __init__(self, view_model: SessionViewModel, parent: QWidget | None = None) -> None:
        super().__init__(
            title="Change email address",
            subtitle="This is the address you sign in with.",
            submit_label="Change email",
            parent=parent,
        )
        self._view_model = view_model
        self.bind(view_model.emailChanged, view_model.errorOccurred)

        current = QLineEdit()
        current.setReadOnly(True)
        user = view_model.current_user()
        current.setText(user.email if user is not None else "")
        self.add_row("Current email", current)

        self._new_email = QLineEdit()
        self._new_email.setPlaceholderText("you@example.com")
        self.add_row("New email", self._new_email, required=True)

        self._password = QLineEdit()
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self.add_row("Your password", self._password, required=True)

        self.add_note(
            "Your password confirms the change — it is not being altered. "
            "After this, sign in with the new address."
        )

    def build_command(self) -> tuple[str, str] | None:
        # Format and uniqueness are checked by the use case, which is the
        # only place that can see the other accounts. This catches the one
        # thing the form itself knows: that nothing has been typed.
        return self._new_email.text().strip(), self._password.text()

    def submit_command(self, command: tuple[str, str]) -> None:
        new_email, password = command
        self._view_model.change_email(new_email, password)
