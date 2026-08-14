from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from app.application.auth.session import CurrentUserSession
from app.domain.notifications.email_sender import EmailSender
from app.domain.security.password_hasher import PasswordHasher
from app.infrastructure.notifications.smtp_email_sender import SmtpEmailSender
from app.infrastructure.security.bcrypt_password_hasher import BcryptPasswordHasher
from app.infrastructure.security.secret_vault import SecretVault
from app.infrastructure.uow import SqlAlchemyUnitOfWork
from app.application.auth.initial_admin import EnsureInitialAdminUserUseCase
from app.config.settings import AppSettings

from app.application.auth.authorization import AuthorizationService
from app.application.auth.permissions import Permission
from app.application.auth.commands import RecordLoginAuditCommand
from app.application.auth.login_audit_use_cases import RecordLoginAuditUseCase, ListLoginHistoryUseCase
from app.application.auth.session_store import SessionStore
from app.domain.enums.login_event_type import LoginEventType
from app.infrastructure.auth import FileSessionStore
from app.config.paths import INSTALLATION_FILE_PATH, LICENSE_FILE_PATH, SESSION_FILE_PATH
from app.application.auth.throttling import LoginThrottleService
from app.application.licensing.manager import LicenseManager
from app.domain.licensing.ports import InstallationIdentity, LicenseProvider
from app.infrastructure.licensing.file_installation_identity import FileInstallationIdentity
from app.infrastructure.licensing.file_license_store import FileLicenseStore
from app.shared.datetimes import now_pkt

@dataclass(slots=True)
class AppContainer:
    """
    Simple composition root for the application.
    """
    settings: AppSettings = field(default_factory=AppSettings.load)
    # One clock for the whole application. Injected rather than read
    # wherever it is needed, so that expiry and grace are a rule a test
    # can move past in microseconds rather than a wait — and so the licence
    # evaluation and the timer scheduled off it can never disagree about
    # what time it is.
    clock: Callable[[], datetime] = now_pkt
    current_user_session: CurrentUserSession = field(default_factory=CurrentUserSession)
    password_hasher: PasswordHasher = field(default_factory=BcryptPasswordHasher)
    session_store: SessionStore = field(default_factory=lambda: FileSessionStore(SESSION_FILE_PATH))
    _license_manager: LicenseManager | None = field(default=None, init=False, repr=False)

    def create_uow(self) -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork()

    def sign_in_use_case(self):
        from app.application.auth.use_cases import SignInUseCase
        return SignInUseCase(self.create_uow(), self.password_hasher, self.current_user_session, self.session_store, self.record_login_audit_use_case(), self.login_throttle_service())

    def authorization_service(self) -> AuthorizationService:
        return AuthorizationService(self.current_user_session)

    def sign_out_use_case(self):
        from app.application.auth.use_cases import SignOutUseCase
        return SignOutUseCase(self.current_user_session, self.session_store, self.record_login_audit_use_case(),)

    def restore_session_use_case(self):
        from app.application.auth.use_cases import RestoreSessionUseCase
        return RestoreSessionUseCase(
            self.create_uow(),
            self.current_user_session,
            self.session_store,
            self.record_login_audit_use_case(),
        )

    def current_user_use_case(self):
        from app.application.auth.use_cases import GetCurrentUserUseCase
        return GetCurrentUserUseCase(self.current_user_session)

    def change_password_use_case(self):
        from app.application.auth.use_cases import ChangePasswordUseCase
        return ChangePasswordUseCase(self.create_uow(), self.password_hasher, self.current_user_session, self.record_login_audit_use_case())

    def change_email_use_case(self):
        from app.application.auth.use_cases import ChangeEmailUseCase
        return ChangeEmailUseCase(
            self.create_uow(),
            self.password_hasher,
            self.current_user_session,
            self.record_login_audit_use_case(),
        )

    def email_sender(self) -> EmailSender:
        # The server's details come from configuration; its password comes
        # from the OS credential vault, which the sender reads at the
        # moment it authenticates.
        return SmtpEmailSender(self.settings.smtp, SecretVault())

    def request_password_reset_use_case(self):
        from app.application.auth.password_reset import RequestPasswordResetUseCase
        return RequestPasswordResetUseCase(
            self.create_uow(),
            self.password_hasher,
            self.email_sender(),
            self.record_login_audit_use_case(),
            self.settings.app_name,
        )

    def ensure_initial_admin_use_case(self) -> EnsureInitialAdminUserUseCase:
        return EnsureInitialAdminUserUseCase(self.create_uow(), self.password_hasher)

    def create_initializer(self):
        from app.application.startup.application_initializer import ApplicationInitializer
        return ApplicationInitializer(
        ensure_initial_admin_use_case=self.ensure_initial_admin_use_case(),
        restore_session_use_case=self.restore_session_use_case(),
        )

    def record_login_audit_use_case(self) -> RecordLoginAuditUseCase:
        return RecordLoginAuditUseCase(self.create_uow(), self.settings.app_version)

    def login_history_use_case(self):
        from app.application.auth.login_audit_use_cases import ListLoginHistoryUseCase
        return ListLoginHistoryUseCase(
            self.create_uow(),
            self.current_user_session,
            self.authorization_service(),
        )

    def login_throttle_service(self) -> LoginThrottleService:
        return LoginThrottleService(self.create_uow(), self.settings)

    ############################################################
    ##################### Licensing #############################
    ############################################################

    def license_provider(self) -> LicenseProvider:
        """Where this build gets its licence from.

        The single seam the whole licensing feature turns on. Today it is
        a key the shop typed in, verified offline. When the licensing
        server exists, this method returns a `LaravelLicenseProvider`
        instead and nothing else in the app changes — not the manager,
        not the gate, not either screen.
        """
        from app.infrastructure.licensing.ed25519_verifier import Ed25519SignatureVerifier
        from app.infrastructure.licensing.manual_provider import ManualLicenseProvider
        from app.infrastructure.licensing.public_keys import LICENSE_PUBLIC_KEYS

        return ManualLicenseProvider(
            store=FileLicenseStore(LICENSE_FILE_PATH),
            identity=self.installation_identity(),
            verifier=Ed25519SignatureVerifier(LICENSE_PUBLIC_KEYS),
            product_code=self.settings.product_code,
            expiring_soon_days=self.settings.license_expiry_warning_days,
            clock=self.clock,
        )

    def installation_identity(self) -> InstallationIdentity:
        return FileInstallationIdentity(INSTALLATION_FILE_PATH)

    def license_manager(self) -> LicenseManager:
        """Held for the run, unlike everything else here.

        The gate, the licence screen and any feature check must all see
        the same verdict; a fresh manager per caller would re-read the
        file and could answer one of them differently from another.
        """
        if self._license_manager is None:
            self._license_manager = LicenseManager(self.license_provider())
        return self._license_manager

    ############################################################
    ##################### Inventory Use Cases ###################
    ############################################################
    def create_inventory_item_use_case(self):
        from app.application.use_cases.inventory_items import CreateInventoryItemUseCase
        return CreateInventoryItemUseCase(self.create_uow(), self.current_user_session, self.authorization_service())

    def update_inventory_item_use_case(self):
        from app.application.use_cases.inventory_items import UpdateInventoryItemUseCase
        return UpdateInventoryItemUseCase(self.create_uow(), self.current_user_session, self.authorization_service())

    def delete_inventory_item_use_case(self):
        from app.application.use_cases.inventory_items import DeleteInventoryItemUseCase
        return DeleteInventoryItemUseCase(self.create_uow(), self.current_user_session, self.authorization_service())

    def list_inventory_items_use_case(self):
        from app.application.use_cases.inventory_items import ListInventoryItemsUseCase
        return ListInventoryItemsUseCase(self.create_uow(), self.current_user_session)

    def get_inventory_item_by_name_use_case(self):
        from app.application.use_cases.inventory_items import GetInventoryItemByNameUseCase
        return GetInventoryItemByNameUseCase(self.create_uow(), self.current_user_session)

    def list_low_stock_inventory_items_use_case(self):
        from app.application.use_cases.inventory_items import ListLowStockInventoryItemsUseCase
        return ListLowStockInventoryItemsUseCase(self.create_uow(), self.current_user_session)

    ############################################################
    #################### Expense Use Cases #######################
    ############################################################
    def create_expense_use_case(self):
        from app.application.use_cases.expenses import CreateExpenseUseCase
        return CreateExpenseUseCase(self.create_uow(), self.current_user_session, self.authorization_service())

    def list_expenses_by_date_range_use_case(self):
        from app.application.use_cases.expenses import ListExpensesByDateRangeUseCase
        return ListExpensesByDateRangeUseCase(self.create_uow(), self.current_user_session)

    ############################################################
    #################### Master Data Use Cases ###################
    ############################################################
    def create_cabinet_use_case(self):
        from app.application.use_cases.master_data import CreateCabinetUseCase
        return CreateCabinetUseCase(self.create_uow(), self.current_user_session, self.authorization_service())

    def list_cabinets_use_case(self):
        from app.application.use_cases.master_data import ListCabinetsUseCase
        return ListCabinetsUseCase(self.create_uow(), self.current_user_session)

    def get_cabinet_by_code_use_case(self):
        from app.application.use_cases.master_data import GetCabinetByCodeUseCase
        return GetCabinetByCodeUseCase(self.create_uow(), self.current_user_session)

    def update_cabinet_use_case(self):
        from app.application.use_cases.master_data import UpdateCabinetUseCase
        return UpdateCabinetUseCase(self.create_uow(), self.current_user_session, self.authorization_service())

    def delete_cabinet_use_case(self):
        from app.application.use_cases.master_data import DeleteCabinetUseCase
        return DeleteCabinetUseCase(self.create_uow(), self.current_user_session, self.authorization_service())

    def create_customer_use_case(self):
        from app.application.use_cases.master_data import CreateCustomerUseCase
        return CreateCustomerUseCase(self.create_uow(), self.current_user_session, self.authorization_service())

    def search_customers_use_case(self):
        from app.application.use_cases.master_data import SearchCustomersUseCase
        return SearchCustomersUseCase(self.create_uow(), self.current_user_session)

    def update_customer_use_case(self):
        from app.application.use_cases.master_data import UpdateCustomerUseCase
        return UpdateCustomerUseCase(self.create_uow(), self.current_user_session, self.authorization_service())

    def delete_customer_use_case(self):
        from app.application.use_cases.master_data import DeleteCustomerUseCase
        return DeleteCustomerUseCase(self.create_uow(), self.current_user_session, self.authorization_service())

    def create_supplier_use_case(self):
        from app.application.use_cases.master_data import CreateSupplierUseCase
        return CreateSupplierUseCase(self.create_uow(), self.current_user_session, self.authorization_service())

    def search_suppliers_use_case(self):
        from app.application.use_cases.master_data import SearchSuppliersUseCase
        return SearchSuppliersUseCase(self.create_uow(), self.current_user_session)

    def update_supplier_use_case(self):
        from app.application.use_cases.master_data import UpdateSupplierUseCase
        return UpdateSupplierUseCase(self.create_uow(), self.current_user_session, self.authorization_service())

    def delete_supplier_use_case(self):
        from app.application.use_cases.master_data import DeleteSupplierUseCase
        return DeleteSupplierUseCase(self.create_uow(), self.current_user_session, self.authorization_service())

    def create_payment_method_use_case(self):
        from app.application.use_cases.master_data import CreatePaymentMethodUseCase
        return CreatePaymentMethodUseCase(self.create_uow(), self.current_user_session, self.authorization_service())

    def list_payment_methods_use_case(self):
        from app.application.use_cases.master_data import ListPaymentMethodsUseCase
        return ListPaymentMethodsUseCase(self.create_uow(), self.current_user_session)

    def update_payment_method_use_case(self):
        from app.application.use_cases.master_data import UpdatePaymentMethodUseCase
        return UpdatePaymentMethodUseCase(self.create_uow(), self.current_user_session, self.authorization_service())

    def delete_payment_method_use_case(self):
        from app.application.use_cases.master_data import DeletePaymentMethodUseCase
        return DeletePaymentMethodUseCase(self.create_uow(), self.current_user_session, self.authorization_service())

    def create_expense_category_use_case(self):
        from app.application.use_cases.master_data import CreateExpenseCategoryUseCase
        return CreateExpenseCategoryUseCase(self.create_uow(), self.current_user_session, self.authorization_service())

    def list_expense_categories_use_case(self):
        from app.application.use_cases.master_data import ListExpenseCategoriesUseCase
        return ListExpenseCategoriesUseCase(self.create_uow(), self.current_user_session)

    def update_expense_category_use_case(self):
        from app.application.use_cases.master_data import UpdateExpenseCategoryUseCase
        return UpdateExpenseCategoryUseCase(self.create_uow(), self.current_user_session, self.authorization_service())

    def delete_expense_category_use_case(self):
        from app.application.use_cases.master_data import DeleteExpenseCategoryUseCase
        return DeleteExpenseCategoryUseCase(self.create_uow(), self.current_user_session, self.authorization_service())

    def create_company_settings_use_case(self):
        from app.application.use_cases.master_data import CreateCompanySettingsUseCase
        return CreateCompanySettingsUseCase(self.create_uow(), self.current_user_session, self.authorization_service())

    def get_company_settings_use_case(self):
        from app.application.use_cases.master_data import GetCompanySettingsUseCase
        return GetCompanySettingsUseCase(self.create_uow(), self.current_user_session)

    def update_company_settings_use_case(self):
        from app.application.use_cases.master_data import UpdateCompanySettingsUseCase
        return UpdateCompanySettingsUseCase(self.create_uow(), self.current_user_session, self.authorization_service())

    ############################################################
    #################### Purchase Use Cases #######################
    ############################################################
    def create_purchase_use_case(self):
        from app.application.use_cases.purchases import CreatePurchaseUseCase
        return CreatePurchaseUseCase(self.create_uow(), self.current_user_session, self.authorization_service())

    def record_purchase_payment_use_case(self):
        from app.application.use_cases.purchases import RecordPurchasePaymentUseCase
        return RecordPurchasePaymentUseCase(self.create_uow(), self.current_user_session, self.authorization_service())

    def get_purchase_by_no_use_case(self):
        from app.application.use_cases.purchases import GetPurchaseByNoUseCase
        return GetPurchaseByNoUseCase(self.create_uow(), self.current_user_session)

    def get_purchase_payment_status_use_case(self):
        from app.application.use_cases.purchases import GetPurchasePaymentStatusUseCase
        return GetPurchasePaymentStatusUseCase(self.create_uow(), self.current_user_session)

    def list_purchases_by_date_range_use_case(self):
        from app.application.use_cases.purchases import ListPurchasesByDateRangeUseCase
        return ListPurchasesByDateRangeUseCase(self.create_uow(), self.current_user_session)

    def get_supplier_purchase_total_use_case(self):
        from app.application.use_cases.purchases import GetSupplierPurchaseTotalUseCase
        return GetSupplierPurchaseTotalUseCase(self.create_uow(), self.current_user_session)

    ############################################################
    ###################### Sale Use Cases #########################
    ############################################################
    def create_sale_use_case(self):
        from app.application.use_cases.sales import CreateSaleUseCase
        return CreateSaleUseCase(self.create_uow(), self.current_user_session, self.authorization_service())

    def record_sale_payment_use_case(self):
        from app.application.use_cases.sales import RecordSalePaymentUseCase
        return RecordSalePaymentUseCase(self.create_uow(), self.current_user_session, self.authorization_service())

    def get_sale_by_invoice_no_use_case(self):
        from app.application.use_cases.sales import GetSaleByInvoiceNoUseCase
        return GetSaleByInvoiceNoUseCase(self.create_uow(), self.current_user_session)

    def get_sale_payment_status_use_case(self):
        from app.application.use_cases.sales import GetSalePaymentStatusUseCase
        return GetSalePaymentStatusUseCase(self.create_uow(), self.current_user_session)

    def list_sales_by_date_range_use_case(self):
        from app.application.use_cases.sales import ListSalesByDateRangeUseCase
        return ListSalesByDateRangeUseCase(self.create_uow(), self.current_user_session)

    ############################################################
    ############### Inventory Movement Use Cases ###################
    ############################################################
    def record_inventory_movement_use_case(self):
        from app.application.use_cases.inventory_movements import RecordInventoryMovementUseCase
        return RecordInventoryMovementUseCase(self.create_uow(), self.current_user_session, self.authorization_service())

    def list_inventory_movements_by_source_document_use_case(self):
        from app.application.use_cases.inventory_movements import ListInventoryMovementsBySourceDocumentUseCase
        return ListInventoryMovementsBySourceDocumentUseCase(self.create_uow(), self.current_user_session)

    def list_inventory_movements_by_inventory_item_use_case(self):
        from app.application.use_cases.inventory_movements import ListInventoryMovementsByInventoryItemUseCase
        return ListInventoryMovementsByInventoryItemUseCase(self.create_uow(), self.current_user_session)

    ############################################################
    ##################### Account Ledger Use Cases #################
    ############################################################
    # The two ledgers are one use case assembled two ways. This is the
    # only place the application says "a customer's account is moved by
    # sales" — a build where job orders do that too adds its source to
    # the tuple below and changes nothing else.
    def get_customer_ledger_use_case(self):
        from app.application.ledger.sources import CustomerLookup, SaleLedgerSource
        from app.application.use_cases.ledger import GetPartyLedgerUseCase
        return GetPartyLedgerUseCase(
            self.create_uow(),
            self.current_user_session,
            self.authorization_service(),
            party=CustomerLookup(),
            sources=(SaleLedgerSource(),),
        )

    def get_supplier_ledger_use_case(self):
        from app.application.ledger.sources import PurchaseLedgerSource, SupplierLookup
        from app.application.use_cases.ledger import GetPartyLedgerUseCase
        return GetPartyLedgerUseCase(
            self.create_uow(),
            self.current_user_session,
            self.authorization_service(),
            party=SupplierLookup(),
            sources=(PurchaseLedgerSource(),),
        )

    ############################################################
    ##################### Report Use Cases #########################
    ############################################################
    # Each enforces Permission.VIEW_REPORTS, so each needs the
    # authorization service — without it there is nothing to check.
    def profit_and_loss_use_case(self):
        from app.application.use_cases.reports import GetProfitAndLossUseCase
        return GetProfitAndLossUseCase(
            self.create_uow(), self.current_user_session, self.authorization_service()
        )

    def item_profitability_use_case(self):
        from app.application.use_cases.reports import GetItemProfitabilityUseCase
        return GetItemProfitabilityUseCase(
            self.create_uow(), self.current_user_session, self.authorization_service()
        )

    # Two ageing reports, one use case — the same arrangement as the two
    # ledgers, and the only place the app says receivables are invoices.
    def receivables_ageing_use_case(self):
        from app.application.reporting.sources import ReceivablesSource
        from app.application.use_cases.reports import GetAgeingUseCase
        return GetAgeingUseCase(
            self.create_uow(),
            self.current_user_session,
            self.authorization_service(),
            source=ReceivablesSource(),
        )

    def payables_ageing_use_case(self):
        from app.application.reporting.sources import PayablesSource
        from app.application.use_cases.reports import GetAgeingUseCase
        return GetAgeingUseCase(
            self.create_uow(),
            self.current_user_session,
            self.authorization_service(),
            source=PayablesSource(),
        )

    ############################################################
    ###################### Search Use Cases ########################
    ############################################################
    def search_inventory_items_use_case(self):
        from app.application.use_cases.search import SearchInventoryItemsUseCase
        return SearchInventoryItemsUseCase(self.create_uow(), self.current_user_session)

    def search_purchases_use_case(self):
        from app.application.use_cases.search import SearchPurchasesUseCase
        return SearchPurchasesUseCase(self.create_uow(), self.current_user_session)

    def search_sales_use_case(self):
        from app.application.use_cases.search import SearchSalesUseCase
        return SearchSalesUseCase(self.create_uow(), self.current_user_session)