"""
Sign-in screen, shown standalone before the main shell.

Two separate opt-ins, because they are genuinely different promises:

- **Keep me signed in** — persist the session, so the next launch goes
  straight to the shell. Nothing secret is stored; the session file only
  holds a user id.
- **Remember my credentials** — prefill this form next time. The email is
  stored as a preference; the password goes to the OS credential vault.

Errors appear inline rather than in a message box. A wrong password is an
ordinary, expected event during sign-in, and a modal that has to be
dismissed before you can correct the field is the wrong weight for it.
The same block reports a sent password reset, in green — the user's next
move is to type the temporary password into the form already in front of
them, and a message box would stand between them and it.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.presentation.dialogs.forgot_password_dialog import ForgotPasswordDialog
from app.presentation.viewmodels.session_viewmodel import SessionViewModel
from app.presentation.widgets.qss import repolish

_NO_MAIL_SERVER = (
    "This copy of the app cannot send email, so a temporary password "
    "cannot be sent to you.\n\n"
    "This is not something that can be fixed on this computer — it needs a "
    "corrected copy of the app."
)
"""A correctly packaged build sends mail without anything being set up, so
reaching this means the build itself was made wrong. It therefore names no
step for the user to take on this machine and promises no administrator who
can reset the password, because neither exists — only the contact line
appended below, which is the one thing that helps."""


class LoginView(QWidget):
    signedIn = Signal(object)  # CurrentUser

    def __init__(self, view_model: SessionViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Content")
        self.setWindowTitle("Chand Graphics — Sign in")
        self.resize(460, 560)
        self._view_model = view_model

        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(self._build_card(), alignment=Qt.AlignmentFlag.AlignCenter)

        view_model.signedIn.connect(self._on_signed_in)
        view_model.errorOccurred.connect(self._on_error)
        view_model.busyChanged.connect(self._on_busy_changed)
        view_model.passwordResetSent.connect(self._on_reset_sent)

    # ---------------- construction ----------------

    def _build_card(self) -> QFrame:
        card = QFrame()
        card.setProperty("role", "panel")
        card.setFixedWidth(380)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(32, 30, 32, 30)
        layout.setSpacing(12)

        mark = QLabel("CG")
        mark.setObjectName("BrandMark")
        mark.setFixedSize(44, 44)
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("Chand Graphics")
        title.setProperty("role", "pageTitle")
        subtitle = QLabel("Sign in to continue")
        subtitle.setProperty("role", "pageSub")

        layout.addWidget(mark, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(subtitle, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(10)

        # Reserved up front and hidden, so showing an error doesn't make the
        # card jump and shift the button out from under the cursor.
        self._error = QLabel("")
        self._error.setObjectName("FormError")
        self._error.setProperty("tone", "error")
        self._error.setWordWrap(True)
        self._error.setVisible(False)
        layout.addWidget(self._error)

        self._email = QLineEdit()
        self._email.setPlaceholderText("you@example.com")
        self._email.returnPressed.connect(self._focus_password)
        layout.addLayout(self._labelled("Email", self._email))

        self._password = QLineEdit()
        self._password.setPlaceholderText("Your password")
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._password.returnPressed.connect(self._submit)
        layout.addLayout(self._labelled("Password", self._build_password_row()))

        layout.addLayout(self._build_forgot_row())
        layout.addSpacing(4)

        self._remember_me = QCheckBox("Keep me signed in")
        self._remember_me.setToolTip(
            "Skip this screen next time on this computer. Leave it off on a shared machine."
        )
        layout.addWidget(self._remember_me)

        self._save_credentials = QCheckBox("Remember my credentials")
        if self._view_model.can_save_passwords:
            self._save_credentials.setToolTip(
                "Fills this form in next time. The password is kept in Windows "
                "Credential Manager, not in a file."
            )
        else:
            # Honest about the reduced promise rather than quietly dropping
            # half of what the label implies.
            self._save_credentials.setText("Remember my email address")
            self._save_credentials.setToolTip(
                "This computer has no credential vault available, so only the "
                "email address can be remembered."
            )
        layout.addWidget(self._save_credentials)

        layout.addSpacing(8)

        self._sign_in_btn = QPushButton("Sign in")
        self._sign_in_btn.setProperty("variant", "primary")
        self._sign_in_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._sign_in_btn.clicked.connect(self._submit)
        layout.addWidget(self._sign_in_btn)

        return card

    def _labelled(self, text: str, field: QWidget) -> QVBoxLayout:
        block = QVBoxLayout()
        block.setSpacing(5)
        label = QLabel(text)
        label.setProperty("role", "fieldLabel")
        block.addWidget(label)
        block.addWidget(field)
        return block

    def _build_forgot_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addStretch(1)

        self._forgot_btn = QPushButton("Forgot password?")
        self._forgot_btn.setProperty("variant", "link")
        self._forgot_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._forgot_btn.clicked.connect(self._open_forgot_password)
        # Always clickable, even in the build that cannot send mail. A
        # disabled button hides its reason in a tooltip the user has no
        # cause to hover, so someone who has genuinely forgotten their
        # password meets a dead control and no way out. Clicking it
        # explains, and says who to ring.
        row.addWidget(self._forgot_btn)
        return row

    def _build_password_row(self) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._reveal_btn = QPushButton("Show")
        self._reveal_btn.setCheckable(True)
        self._reveal_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._reveal_btn.setFixedWidth(62)
        self._reveal_btn.setToolTip("Show the password so you can check it before signing in")
        self._reveal_btn.toggled.connect(self._on_reveal_toggled)

        layout.addWidget(self._password, 1)
        layout.addWidget(self._reveal_btn)
        return row

    # ---------------- behaviour ----------------

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 (Qt override)
        super().showEvent(event)
        self._prefill()

    def _prefill(self) -> None:
        """Fill in whatever was remembered and focus the first empty field."""
        remembered = self._view_model.remembered_credentials()
        if remembered.email:
            self._email.setText(remembered.email)
            self._save_credentials.setChecked(True)
        if remembered.password:
            self._password.setText(remembered.password)

        if not self._email.text():
            self._email.setFocus()
        elif not self._password.text():
            self._password.setFocus()
        else:
            self._sign_in_btn.setFocus()

    def _focus_password(self) -> None:
        self._password.setFocus()
        self._password.selectAll()

    def _on_reveal_toggled(self, revealed: bool) -> None:
        self._password.setEchoMode(
            QLineEdit.EchoMode.Normal if revealed else QLineEdit.EchoMode.Password
        )
        self._reveal_btn.setText("Hide" if revealed else "Show")

    def _open_forgot_password(self) -> None:
        if not self._view_model.can_send_email:
            support = self._view_model.support_line
            QMessageBox.information(
                self,
                "Forgot password",
                f"{_NO_MAIL_SERVER}\n\nPlease contact {support}." if support else _NO_MAIL_SERVER,
            )
            return
        # Carries whatever is already typed, so the common case — the email
        # is right, the password isn't — needs no retyping.
        ForgotPasswordDialog(self._view_model, self._email.text().strip(), parent=self).exec()

    def _submit(self) -> None:
        email = self._email.text().strip()
        password = self._password.text()

        if not email:
            self._show_error("Enter your email address.", self._email)
            return
        if not password:
            self._show_error("Enter your password.", self._password)
            return

        self._clear_error()
        self._view_model.sign_in(
            email,
            password,
            remember_me=self._remember_me.isChecked(),
            save_credentials=self._save_credentials.isChecked(),
        )

    # ---------------- state ----------------

    def _on_busy_changed(self, busy: bool) -> None:
        self._sign_in_btn.setDisabled(busy)
        self._sign_in_btn.setText("Signing in…" if busy else "Sign in")

    def _on_signed_in(self, _result) -> None:
        self._clear_error()
        self._password.clear()
        self.signedIn.emit(self._view_model.current_user())

    def _on_error(self, message: str) -> None:
        # Land the cursor in the password box: for every sign-in failure
        # the user can act on, that's the field to retype.
        self._show_error(message, self._password)
        self._password.selectAll()

    def _on_reset_sent(self, email: str) -> None:
        self._email.setText(email)
        self._password.clear()
        self._set_message(
            f"A temporary password has been sent to {email}. "
            "Sign in with it, then change it from My profile.",
            tone="success",
        )
        self._password.setFocus()

    def _show_error(self, message: str, field: QWidget) -> None:
        self._set_message(message, tone="error")
        field.setFocus()

    def _set_message(self, message: str, *, tone: str) -> None:
        self._error.setText(message)
        self._error.setProperty("tone", tone)
        # The tone selector is resolved at polish time, not when the
        # property is set — see qss.repolish.
        repolish(self._error)
        self._error.setVisible(True)

    def _clear_error(self) -> None:
        self._error.clear()
        self._error.setVisible(False)
