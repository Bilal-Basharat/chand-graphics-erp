from __future__ import annotations

from PySide6.QtCore import Signal

from app.application.dto.commands import CreateCompanySettingsCommand, UpdateCompanySettingsCommand
from app.container import AppContainer
from app.presentation.viewmodels.base import BaseViewModel


class CompanySettingsViewModel(BaseViewModel):
    settingsLoaded = Signal(object)  # CompanySettings | None
    settingsSaved = Signal(object)   # CompanySettings

    def __init__(self, container: AppContainer) -> None:
        super().__init__()
        self._container = container

    def load(self) -> None:
        use_case = self._container.get_company_settings_use_case()
        self.run_async(use_case.execute, on_success=self.settingsLoaded.emit)

    def save(
        self,
        existing_id: int | None,
        company_name: str,
        phone: str | None,
        email: str | None,
        address: str | None,
        currency: str,
        invoice_footer: str | None,
    ) -> None:
        if existing_id is None:
            use_case = self._container.create_company_settings_use_case()
            command = CreateCompanySettingsCommand(
                company_name=company_name,
                phone=phone,
                email=email,
                address=address,
                currency=currency,
                invoice_footer=invoice_footer,
            )
        else:
            use_case = self._container.update_company_settings_use_case()
            command = UpdateCompanySettingsCommand(
                id=existing_id,
                company_name=company_name,
                phone=phone,
                email=email,
                address=address,
                currency=currency,
                invoice_footer=invoice_footer,
            )
        self.run_async(lambda: use_case.execute(command), on_success=self.settingsSaved.emit)
