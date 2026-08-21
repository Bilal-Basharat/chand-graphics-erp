"""
Company settings screen: business identity, currency, invoice footer.
"""
from __future__ import annotations

from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.presentation.viewmodels.company_settings_viewmodel import CompanySettingsViewModel
from app.presentation.widgets.input_validation import NOT_A_PHONE, PhoneInput, parse_phone
from app.presentation.widgets.page_header import panel_title
from app.presentation.widgets.page_scroll import page_scroll


class CompanySettingsView(QWidget):
    def __init__(self, view_model: CompanySettingsViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self._existing_id: int | None = None

        # Two tall form panels — the tallest screen in the app, and well
        # past a 768px laptop screen, so it scrolls.
        outer = QVBoxLayout(page_scroll(self))
        outer.setContentsMargins(24, 20, 24, 24)
        outer.setSpacing(0)

        crumb = QLabel("Home / Settings / Company")
        crumb.setProperty("role", "crumb")
        outer.addWidget(crumb)
        outer.addSpacing(6)

        title = QLabel("Company settings")
        title.setProperty("role", "pageTitle")
        outer.addWidget(title)
        outer.addSpacing(16)

        outer.addWidget(self._build_profile_panel())
        outer.addSpacing(14)
        outer.addWidget(self._build_invoicing_panel())
        outer.addSpacing(14)
        outer.addLayout(self._build_actions())
        outer.addStretch(1)

        self._view_model.settingsLoaded.connect(self._on_loaded)
        self._view_model.settingsSaved.connect(self._on_saved)
        self._view_model.errorOccurred.connect(self._on_error)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 (Qt override)
        super().showEvent(event)
        self._view_model.load()

    def _field(
        self,
        label_text: str,
        help_text: str = "",
        widget: QLineEdit | None = None,
    ) -> tuple[QVBoxLayout, QLineEdit]:
        """A labelled input for this page's grid. `widget` is for the
        fields that police their own input, such as the phone."""
        layout = QVBoxLayout()
        layout.setSpacing(6)
        label = QLabel(label_text)
        label.setProperty("role", "fieldLabel")
        field = widget if widget is not None else QLineEdit()
        layout.addWidget(label)
        layout.addWidget(field)
        if help_text:
            help_label = QLabel(help_text)
            help_label.setProperty("role", "fieldHelp")
            layout.addWidget(help_label)
        return layout, field

    def _build_profile_panel(self) -> QFrame:
        panel = QFrame()
        panel.setProperty("role", "panel")
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(0, 0, 0, 0)

        outer.addWidget(panel_title("Company profile"))

        grid = QGridLayout()
        grid.setContentsMargins(18, 0, 18, 18)
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(14)

        name_layout, self._company_name = self._field("Company name *")
        phone_layout, self._phone = self._field(
            "Phone", "Primary contact number shown on invoices.", PhoneInput()
        )
        email_layout, self._email = self._field("Email")
        address_layout, self._address = self._field("Address")

        grid.addLayout(name_layout, 0, 0)
        grid.addLayout(phone_layout, 0, 1)
        grid.addLayout(email_layout, 1, 0)
        grid.addLayout(address_layout, 1, 1)
        outer.addLayout(grid)
        return panel

    def _build_invoicing_panel(self) -> QFrame:
        panel = QFrame()
        panel.setProperty("role", "panel")
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(0, 0, 0, 0)

        outer.addWidget(panel_title("Invoicing"))

        body = QVBoxLayout()
        body.setContentsMargins(18, 0, 18, 18)
        body.setSpacing(14)

        currency_layout, self._currency = self._field("Currency", "Used for all amounts across the app.")
        self._currency.setText("PKR")
        body.addLayout(currency_layout)

        footer_label = QLabel("Invoice footer")
        footer_label.setProperty("role", "fieldLabel")
        self._footer = QTextEdit()
        self._footer.setFixedHeight(80)
        footer_help = QLabel("Max 500 characters.")
        footer_help.setProperty("role", "fieldHelp")

        body.addWidget(footer_label)
        body.addWidget(self._footer)
        body.addWidget(footer_help)
        outer.addLayout(body)
        return panel

    def _build_actions(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addStretch(1)
        reset_btn = QPushButton("Reset")
        reset_btn.setProperty("variant", "outline")
        reset_btn.clicked.connect(self._view_model.load)

        self._save_btn = QPushButton("Save changes")
        self._save_btn.setProperty("variant", "primary")
        self._save_btn.clicked.connect(self._save)

        row.addWidget(reset_btn)
        row.addWidget(self._save_btn)
        return row

    def _reject(self, message: str, field: QWidget) -> None:
        """Report what has to be fixed, and put the cursor on it — the same
        thing `FormDialog.reject_with` does for the dialogs."""
        QMessageBox.warning(self, "Company settings", message)
        field.setFocus()

    def _save(self) -> None:
        company_name = self._company_name.text().strip()
        if not company_name:
            self._reject("Company name is required.", self._company_name)
            return

        phone = parse_phone(self._phone.text())
        if phone is None:
            self._reject(NOT_A_PHONE, self._phone)
            return

        footer_text = self._footer.toPlainText().strip()
        if len(footer_text) > 500:
            self._reject("Invoice footer must be 500 characters or fewer.", self._footer)
            return

        self._view_model.save(
            existing_id=self._existing_id,
            company_name=company_name,
            phone=phone or None,
            email=self._email.text().strip() or None,
            address=self._address.text().strip() or None,
            currency=self._currency.text().strip() or "PKR",
            invoice_footer=footer_text or None,
        )

    def _on_loaded(self, settings) -> None:
        if settings is None:
            self._existing_id = None
            return
        self._existing_id = settings.id
        self._company_name.setText(settings.company_name)
        self._phone.setText(settings.phone or "")
        self._email.setText(settings.email or "")
        self._address.setText(settings.address or "")
        self._currency.setText(settings.currency or "PKR")
        self._footer.setPlainText(settings.invoice_footer or "")

    def _on_saved(self, settings) -> None:
        self._existing_id = settings.id
        QMessageBox.information(self, "Company settings", "Settings saved.")

    def _on_error(self, message: str) -> None:
        QMessageBox.warning(self, "Company settings", message)
