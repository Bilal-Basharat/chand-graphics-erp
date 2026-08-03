"""
My profile: who you're signed in as, what that role can do, what this
computer remembers about you, and your recent sign-in activity.

The history panel is permission-gated. `ListLoginHistoryUseCase` requires
VIEW_REPORTS, which the staff role does not hold — so rather than let
staff trigger a permission error on a screen about their own account, the
panel explains that it isn't available to them.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.application.auth.permissions import Permission
from app.domain.enums.login_event_type import LoginEventType
from app.presentation.dialogs.change_password_dialog import ChangePasswordDialog
from app.presentation.formatting import date_time, or_dash
from app.presentation.theme import tokens as t
from app.presentation.viewmodels.session_viewmodel import SessionViewModel
from app.presentation.widgets.data_table import DataTable
from app.presentation.widgets.page_header import PageHeader
from app.presentation.widgets.table_model import Column

# What each permission means in the user's language, not the codebase's.
_PERMISSION_LABELS: dict[Permission, str] = {
    Permission.MANAGE_USERS: "Manage user accounts",
    Permission.MANAGE_SETTINGS: "Change company settings",
    Permission.MANAGE_MASTER_DATA: "Add cards, items, cabinets and parties",
    Permission.MANAGE_PURCHASES: "Record purchases",
    Permission.MANAGE_SALES: "Record sales",
    Permission.MANAGE_EXPENSES: "Record expenses",
    Permission.VIEW_REPORTS: "View reports and history",
}

_EVENT_LABELS: dict[LoginEventType, str] = {
    LoginEventType.SIGN_IN_SUCCESS: "Signed in",
    LoginEventType.SIGN_IN_FAILURE: "Failed sign-in",
    LoginEventType.SIGN_OUT: "Signed out",
    LoginEventType.SESSION_RESTORED: "Session resumed",
}


def _initials(full_name: str) -> str:
    parts = [part for part in full_name.strip().split() if part]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def _event_label(audit) -> str:
    return _EVENT_LABELS.get(audit.event_type, audit.event_type.value.replace("_", " ").title())


def _outcome(audit) -> str:
    return "Success" if audit.success else "Failed"


def _outcome_color(audit) -> str:
    return t.SUCCESS if audit.success else t.DANGER


class ProfileView(QWidget):
    def __init__(self, view_model: SessionViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view_model = view_model

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 24)
        outer.setSpacing(16)

        self._header = PageHeader(
            ("System", "My profile"),
            "My profile",
            "Your account, what your role allows, and how you've signed in recently.",
        )
        self._header.add_action("Change password", self._open_change_password, variant="primary")
        outer.addWidget(self._header)

        top_row = QHBoxLayout()
        top_row.setSpacing(16)
        top_row.addWidget(self._build_identity_panel(), 1)
        top_row.addWidget(self._build_permissions_panel(), 1)
        outer.addLayout(top_row)

        outer.addWidget(self._build_history_panel(), 1)

        view_model.loginHistoryLoaded.connect(self._on_history_loaded)
        view_model.passwordChanged.connect(self._on_password_changed)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 (Qt override)
        super().showEvent(event)
        self.refresh()

    def refresh(self) -> None:
        self._render_identity()
        self._render_permissions()
        if self._view_model.has_permission(Permission.VIEW_REPORTS):
            self._view_model.load_login_history()

    # ---------------- identity ----------------

    def _build_identity_panel(self) -> QFrame:
        panel = QFrame()
        panel.setProperty("role", "panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)

        title = QLabel("Account")
        title.setProperty("role", "panelTitle")
        layout.addWidget(title)

        identity_row = QHBoxLayout()
        identity_row.setSpacing(14)

        self._avatar = QLabel("?")
        self._avatar.setObjectName("ProfileAvatar")
        self._avatar.setFixedSize(56, 56)
        self._avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)

        name_block = QVBoxLayout()
        name_block.setSpacing(2)
        self._name = QLabel("")
        self._name.setStyleSheet(f"font-size: 17px; font-weight: {t.WEIGHT_SEMIBOLD};")
        self._email = QLabel("")
        self._email.setProperty("role", "pageSub")
        name_block.addWidget(self._name)
        name_block.addWidget(self._email)

        identity_row.addWidget(self._avatar)
        identity_row.addLayout(name_block, 1)
        layout.addLayout(identity_row)

        self._detail_grid = QGridLayout()
        self._detail_grid.setHorizontalSpacing(16)
        self._detail_grid.setVerticalSpacing(8)
        layout.addLayout(self._detail_grid)

        self._forget_btn = QPushButton("Forget saved sign-in details")
        self._forget_btn.setProperty("variant", "outline")
        self._forget_btn.clicked.connect(self._forget_credentials)
        layout.addWidget(self._forget_btn)

        layout.addStretch(1)
        return panel

    def _render_identity(self) -> None:
        user = self._view_model.current_user()
        if user is None:
            return

        self._avatar.setText(_initials(user.full_name))
        self._name.setText(user.full_name)
        self._email.setText(user.email)

        remembered = self._view_model.remembered_credentials()
        if not remembered.has_email:
            saved = "Not saved on this computer"
        elif remembered.password:
            saved = "Email and password saved"
        else:
            saved = "Email saved"

        self._set_details(
            [
                ("Role", user.role.capitalize()),
                ("Saved sign-in", saved),
            ]
        )
        self._forget_btn.setEnabled(remembered.has_email)

    def _set_details(self, rows: list[tuple[str, str]]) -> None:
        while self._detail_grid.count():
            item = self._detail_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        for row, (label_text, value_text) in enumerate(rows):
            label = QLabel(label_text)
            label.setProperty("role", "statLabel")
            value = QLabel(value_text)
            value.setStyleSheet(f"font-size: 13px; color: {t.INK};")
            self._detail_grid.addWidget(label, row, 0)
            self._detail_grid.addWidget(value, row, 1)
        self._detail_grid.setColumnStretch(1, 1)

    # ---------------- permissions ----------------

    def _build_permissions_panel(self) -> QFrame:
        panel = QFrame()
        panel.setProperty("role", "panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        title = QLabel("What this role can do")
        title.setProperty("role", "panelTitle")
        layout.addWidget(title)

        self._permissions_layout = QVBoxLayout()
        self._permissions_layout.setSpacing(6)
        layout.addLayout(self._permissions_layout)
        layout.addStretch(1)
        return panel

    def _render_permissions(self) -> None:
        while self._permissions_layout.count():
            item = self._permissions_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        granted = self._view_model.permissions()
        # Every permission is listed, granted or not, so the user can see
        # what they *can't* do — that's the half that explains a refusal.
        for permission, label_text in _PERMISSION_LABELS.items():
            allowed = permission in granted
            row = QLabel(f"{'✓' if allowed else '✕'}   {label_text}")
            tone = t.SUCCESS if allowed else t.MUTED
            row.setStyleSheet(f"color: {tone}; font-size: 13px;")
            self._permissions_layout.addWidget(row)

    # ---------------- history ----------------

    def _build_history_panel(self) -> QFrame:
        panel = QFrame()
        panel.setProperty("role", "panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(1, 0, 1, 1)
        layout.setSpacing(0)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(18, 14, 18, 10)
        title = QLabel("Recent sign-in activity")
        title.setProperty("role", "panelTitle")
        self._history_note = QLabel("")
        self._history_note.setProperty("role", "panelSub")
        title_row.addWidget(title)
        title_row.addStretch(1)
        title_row.addWidget(self._history_note)
        layout.addLayout(title_row)

        allowed = self._view_model.has_permission(Permission.VIEW_REPORTS)
        self._history = DataTable(
            [
                Column("WHEN", lambda a: date_time(a.created_at), width=200),
                Column("EVENT", _event_label, width=170),
                Column("OUTCOME", _outcome, width=110, color=_outcome_color),
                Column("DETAIL", lambda a: or_dash(a.message)),
                Column("VERSION", lambda a: or_dash(a.app_version), width=110),
            ],
            placeholder=(
                "No sign-in activity recorded yet."
                if allowed
                else "Your role doesn't include permission to view sign-in history."
            ),
        )
        self._history.setMinimumHeight(220)
        layout.addWidget(self._history, 1)
        return panel

    def _on_history_loaded(self, rows: list) -> None:
        self._history.set_rows(rows)
        self._history_note.setText("1 event" if len(rows) == 1 else f"{len(rows)} events")

    # ---------------- actions ----------------

    def _open_change_password(self) -> None:
        ChangePasswordDialog(self._view_model, parent=self).exec()

    def _on_password_changed(self) -> None:
        # Only meaningful while this screen is the one on show; the dialog
        # reports its own success otherwise.
        if self.isVisible():
            QMessageBox.information(self, "Change password", "Your password has been changed.")
            self.refresh()

    def _forget_credentials(self) -> None:
        answer = QMessageBox.question(
            self,
            "Forget saved sign-in details",
            "Remove the saved email and password from this computer?\n\n"
            "You'll need to type them in next time you sign in.",
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes,
            QMessageBox.StandardButton.Cancel,
        )
        if answer is not QMessageBox.StandardButton.Yes:
            return
        self._view_model.forget_credentials()
        self._render_identity()
