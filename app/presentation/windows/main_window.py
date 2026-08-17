"""
Application shell: full-width header, sidebar, content stack, status bar.

Composes every screen's ViewModel from the container and injects it into
the matching View — Views never see the container directly.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QGridLayout,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QWidget,
)

from app.container import AppContainer
from app.domain.licensing.state import LicenseState
from app.presentation.dialogs.activation_dialog import ActivationDialog
from app.presentation.dialogs.change_password_dialog import ChangePasswordDialog
from app.presentation.license_display import status_notice, status_tone
from app.presentation.license_watch import LicenseWatcher
from app.presentation.navigation.routes import Route
from app.presentation.records import paper
from app.presentation.viewmodels.company_settings_viewmodel import CompanySettingsViewModel
from app.presentation.viewmodels.dashboard_viewmodel import DashboardViewModel
from app.presentation.viewmodels.license_viewmodel import LicenseViewModel
from app.presentation.viewmodels.sales_viewmodel import SalesViewModel
from app.presentation.viewmodels.session_viewmodel import SessionViewModel
from app.presentation.viewmodels.master_data_viewmodels import (
    InventoryViewModel,
    cabinets_view_model,
    customers_view_model,
    expense_categories_view_model,
    payment_methods_view_model,
    suppliers_view_model,
)
from app.presentation.views.account_ledger_view import (
    CUSTOMER_LEDGER_PAGE,
    SUPPLIER_LEDGER_PAGE,
    AccountLedgerView,
    CustomerLedgerViewModel,
    SupplierLedgerViewModel,
)
from app.presentation.views.collection_view import CollectionView
from app.presentation.views.company_settings_view import CompanySettingsView
from app.presentation.views.dashboard_view import DashboardView
from app.presentation.views.master_data_views import (
    CabinetsView,
    CustomersView,
    ExpenseCategoriesView,
    InventoryView,
    PaymentMethodsView,
    SuppliersView,
)
from app.presentation.views.expenses_view import (
    ExpensesView,
    categories_view_model,
    expenses_view_model,
)
from app.presentation.views.license_view import LicenseView
from app.presentation.views.inventory_movement_view import (
    InventoryMovementView,
    InventoryMovementViewModel,
)
from app.presentation.views.payments_view import (
    PURCHASE_PAYMENTS_PAGE,
    SALE_PAYMENTS_PAGE,
    PaymentsView,
    PurchasePaymentsViewModel,
    SalePaymentsViewModel,
)
from app.presentation.views.profile_view import ProfileView
from app.presentation.views.purchases_view import PurchasesView, PurchasesViewModel
from app.presentation.views.ageing_view import (
    PAYABLES_PAGE,
    RECEIVABLES_PAGE,
    AgeingView,
    PayablesAgeingViewModel,
    ReceivablesAgeingViewModel,
)
from app.presentation.views.item_profitability_view import (
    ItemProfitabilityView,
    ItemProfitabilityViewModel,
)
from app.presentation.views.profit_and_loss_view import (
    ProfitAndLossView,
    ProfitAndLossViewModel,
)
from app.presentation.views.sales_view import SalesView
from app.presentation.widgets.period_selector import PeriodSelection
from app.presentation.widgets.sidebar import UNLOCKED_ROUTES, Sidebar
from app.presentation.widgets.status_bar import AppStatusBar
from app.presentation.widgets.topbar import TopBar



class MainWindow(QMainWindow):
    # Handled by SessionController, which owns the login/shell lifecycle —
    # the shell can't tear itself down while its own code is running.
    signOutRequested = Signal()

    def __init__(
        self,
        container: AppContainer,
        session_view_model: SessionViewModel,
        watcher: LicenseWatcher,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._container = container
        self._session_view_model = session_view_model
        self._watcher = watcher
        self._pages: dict[Route, QWidget] = {}
        self._page_titles: dict[Route, str] = {}
        self._current_route = Route.DASHBOARD
        self._locked = False

        self.setWindowTitle("Chand Graphics — Printing Press ERP")
        self.resize(1400, 900)

        central = QWidget()
        grid = QGridLayout(central)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(0)

        self._sidebar = Sidebar()
        self._topbar = TopBar()
        self._status_bar = AppStatusBar(
            container.settings.app_version, container.settings.developed_by, container.settings.developer_email, container.settings.developer_contact
        )
        self._stack = QStackedWidget()
        self._stack.setObjectName("Content")

        grid.addWidget(self._topbar, 0, 0, 1, 2)
        grid.addWidget(self._sidebar, 1, 0)
        grid.addWidget(self._stack, 1, 1)
        grid.addWidget(self._status_bar, 2, 0, 1, 2)
        grid.setRowStretch(1, 1)
        grid.setColumnStretch(1, 1)

        self.setCentralWidget(central)

        self._register_views()

        self._sidebar.navigationRequested.connect(self.navigate)
        self._sidebar.collapsedChanged.connect(self._on_sidebar_collapsed)
        self._topbar.newSaleRequested.connect(lambda: self.navigate(Route.SALES))
        self._topbar.newPurchaseRequested.connect(lambda: self.navigate(Route.PURCHASES))
        self._topbar.searchSubmitted.connect(self._on_global_search)
        self._topbar.profileRequested.connect(lambda: self.navigate(Route.PROFILE))
        self._topbar.changePasswordRequested.connect(self._open_change_password)
        self._topbar.signOutRequested.connect(self.signOutRequested.emit)

        # The status bar advertised this shortcut but nothing implemented it.
        QShortcut(QKeySequence.StandardKey.Find, self, activated=self._focus_search)

        self._status_bar.licenseClicked.connect(lambda: self.navigate(Route.LICENSE))
        self._watcher.stateChanged.connect(self._on_license_state)

        current_user = self._session_view_model.current_user()
        if current_user is not None:
            self._topbar.set_user(current_user.full_name, current_user.role)

        self.navigate(Route.DASHBOARD)

        # Last, so the shell is fully built before a licence that has run
        # out can lock it or put a dialog in front of it.
        self._watcher.check()

    def _register_views(self) -> None:
        dashboard_period = PeriodSelection()
        dashboard = DashboardView(
            DashboardViewModel(self._container, dashboard_period), dashboard_period
        )
        dashboard.recordRequested.connect(self._open_record)
        self._add_page(Route.DASHBOARD, dashboard, "Dashboard")

        self._inventory_view = InventoryView(InventoryViewModel(self._container))
        self._add_page(Route.INVENTORY, self._inventory_view, "Inventory")

        settings_vm = CompanySettingsViewModel(self._container)
        # The shop's own details head every printed record. Taken once at
        # startup and again whenever they are saved, so a page printed
        # after an edit carries the new ones — see records/paper.py.
        settings_vm.settingsLoaded.connect(paper.set_company)
        settings_vm.settingsSaved.connect(paper.set_company)
        settings_vm.load()

        # The developer info sits in the footer of every printed record.
        # Taken once at startup from the application settings, which for
        # these fields means the build's own constants.
        paper.set_app_settings(self._container.settings)

        self._add_page(Route.COMPANY_SETTINGS, CompanySettingsView(settings_vm), "Company settings")

        self._add_page(
            Route.CABINETS,
            CabinetsView(cabinets_view_model(self._container)),
            "Cabinets",
        )
        self._register_party_views()
        self._add_page(
            Route.PAYMENT_METHODS,
            PaymentMethodsView(payment_methods_view_model(self._container)),
            "Payment methods",
        )
        self._add_page(
            Route.EXPENSE_CATEGORIES,
            ExpenseCategoriesView(expense_categories_view_model(self._container)),
            "Expense categories",
        )

        # Each period-filtered screen owns its own selection, so switching
        # to "Last month" on expenses doesn't silently retarget purchases.
        sales_period = PeriodSelection()
        self._add_page(
            Route.SALES,
            SalesView(
                SalesViewModel(self._container, sales_period),
                sales_period,
                self._current_user_id,
            ),
            "Sales",
        )

        purchases_period = PeriodSelection()
        self._add_page(
            Route.PURCHASES,
            PurchasesView(
                PurchasesViewModel(self._container, purchases_period),
                purchases_period,
                self._current_user_id,
            ),
            "Purchases",
        )

        sale_payments_period = PeriodSelection()
        self._add_page(
            Route.SALE_PAYMENTS,
            PaymentsView(
                SALE_PAYMENTS_PAGE,
                SalePaymentsViewModel(self._container, sale_payments_period),
                sale_payments_period,
            ),
            "Sale payments",
        )

        purchase_payments_period = PeriodSelection()
        self._add_page(
            Route.PURCHASE_PAYMENTS,
            PaymentsView(
                PURCHASE_PAYMENTS_PAGE,
                PurchasePaymentsViewModel(self._container, purchase_payments_period),
                purchase_payments_period,
            ),
            "Purchase payments",
        )

        expenses_period = PeriodSelection()
        self._add_page(
            Route.EXPENSES,
            ExpensesView(
                expenses_view_model(self._container, expenses_period),
                expenses_period,
                # A lookup for the filter and the pickers, not the
                # categories screen's own paged list.
                categories_view_model(self._container),
            ),
            "Expenses",
        )

        self._add_page(
            Route.INVENTORY_MOVEMENT,
            InventoryMovementView(InventoryMovementViewModel(self._container)),
            "Inventory movement",
        )

        # Each report screen keeps its own period, like every other period
        # screen: moving to last month on the profit & loss should not
        # silently change what the item breakdown beside it is showing.
        profit_period = PeriodSelection()
        self._add_page(
            Route.PROFIT_AND_LOSS,
            ProfitAndLossView(
                ProfitAndLossViewModel(self._container, profit_period), profit_period
            ),
            "Profit & loss",
        )

        item_period = PeriodSelection()
        self._add_page(
            Route.ITEM_PROFITABILITY,
            ItemProfitabilityView(
                ItemProfitabilityViewModel(self._container, item_period), item_period
            ),
            "Item profitability",
        )

        # No period on either: an ageing report is everything unpaid as at
        # now, whenever it was raised.
        self._add_page(
            Route.RECEIVABLES_AGEING,
            AgeingView(RECEIVABLES_PAGE, ReceivablesAgeingViewModel(self._container)),
            "Receivables ageing",
        )
        self._add_page(
            Route.PAYABLES_AGEING,
            AgeingView(PAYABLES_PAGE, PayablesAgeingViewModel(self._container)),
            "Payables ageing",
        )

        # Built on the watcher, so this page and the shell's own chip are
        # two views of one verdict rather than two readings of a file.
        self._license_view_model = LicenseViewModel(
            self._watcher,
            self._container.installation_identity(),
            self._container.settings,
        )
        self._add_page(Route.LICENSE, LicenseView(self._license_view_model), "Licence")

        self._add_page(
            Route.PROFILE,
            ProfileView(self._session_view_model),
            "My profile",
        )

    def _register_party_views(self) -> None:
        """The two party lists and the two ledgers behind them.

        Registered together because the Ledger button on a row of one
        opens the other, and that wiring is the only reason either knows
        the other exists.
        """
        customers = CustomersView(customers_view_model(self._container))
        customers.ledgerRequested.connect(
            lambda party_id, name: self._open_ledger(Route.CUSTOMER_LEDGER, party_id, name)
        )
        self._add_page(Route.CUSTOMERS, customers, "Customers")

        suppliers = SuppliersView(suppliers_view_model(self._container))
        suppliers.ledgerRequested.connect(
            lambda party_id, name: self._open_ledger(Route.SUPPLIER_LEDGER, party_id, name)
        )
        self._add_page(Route.SUPPLIERS, suppliers, "Suppliers")

        customer_ledger_period = PeriodSelection()
        self._add_page(
            Route.CUSTOMER_LEDGER,
            AccountLedgerView(
                CUSTOMER_LEDGER_PAGE,
                CustomerLedgerViewModel(self._container, customer_ledger_period),
                customer_ledger_period,
            ),
            "Customer ledger",
        )

        supplier_ledger_period = PeriodSelection()
        self._add_page(
            Route.SUPPLIER_LEDGER,
            AccountLedgerView(
                SUPPLIER_LEDGER_PAGE,
                SupplierLedgerViewModel(self._container, supplier_ledger_period),
                supplier_ledger_period,
            ),
            "Supplier ledger",
        )

    def _open_ledger(self, route: Route, party_id: int, party_name: str) -> None:
        """Open a party's ledger from the row that named them.

        By id and name rather than by search, unlike `_open_record`: this
        screen picks its subject from a dropdown rather than filtering a
        table, and that dropdown holds a page of names rather than every
        name. The row clicked knows both, so neither has to be looked up
        again.
        """
        self.navigate(route)
        page = self._pages.get(route)
        if isinstance(page, AccountLedgerView):
            page.select_party(party_id, party_name)

    def _open_change_password(self) -> None:
        ChangePasswordDialog(self._session_view_model, parent=self).exec()

    def _current_user_id(self) -> int | None:
        user = self._session_view_model.current_user()
        return user.user_id if user is not None else None

    def _add_page(self, route: Route, widget: QWidget, title: str) -> None:
        self._pages[route] = widget
        self._page_titles[route] = title
        self._stack.addWidget(widget)

    def navigate(self, route: Route) -> None:
        # The one gate every route passes through. Greying the rail says
        # what has happened; this is what makes it so, for the header
        # search and the dashboard's shortcuts as well as for the rail.
        if self._locked and route not in UNLOCKED_ROUTES:
            return
        widget = self._pages.get(route)
        if widget is None:
            return
        self._current_route = route
        self._stack.setCurrentWidget(widget)
        self._sidebar.set_active(route)
        hint = "Ctrl+F to search this list" if self._searchable_page() else ""
        self._status_bar.set_page(self._page_titles.get(route, ""), hint)

    def _open_record(self, route: Route, reference: str) -> None:
        """Open the screen a record lives on, narrowed to that record.

        Searching rather than selecting a row: the target screen filters by
        period, and the document being opened may well be older than
        whatever period that screen is currently showing. Its search runs
        against the whole table, so it finds the record either way.
        """
        self.navigate(route)
        page = self._pages.get(route)
        if isinstance(page, CollectionView) and page.supports_search:
            page.apply_search(reference)

    def _on_sidebar_collapsed(self, _collapsed: bool) -> None:
        self._topbar.set_brand_width(self._sidebar.width())

    # ---------------- licensing ----------------

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Look again whenever the shell is come back to.

        The timer is the primary mechanism, and this is the answer to the
        machine that was asleep when it should have fired: a laptop closed
        on Friday and opened on Monday has passed its expiry without ever
        running the code that was scheduled for it.
        """
        super().changeEvent(event)
        if event.type() is QEvent.Type.ActivationChange and self.isActiveWindow():
            self._watcher.check()

    def _on_license_state(self, state: LicenseState) -> None:
        """Everything the shell does about a licence, in one place."""
        self._status_bar.set_license_notice(status_notice(state), status_tone(state))
        self._set_locked(not state.is_usable)

        notice = self._watcher.take_notice()
        if notice is not None:
            self._announce(notice)

    def _set_locked(self, locked: bool) -> None:
        if locked == self._locked:
            return
        self._locked = locked
        self._sidebar.set_locked(locked)
        self._topbar.set_actions_enabled(not locked)
        if locked:
            # Off whatever screen the user was on and onto the only one
            # that can fix this. Nothing is closed and nothing is lost —
            # an unlicensed shop still owns its data and its window.
            self.navigate(Route.LICENSE)

    def _announce(self, state: LicenseState) -> None:
        """Say it once, in proportion to what has happened.

        A warning while the licence still works is a message to read and
        dismiss. A licence that has stopped working is the activation
        dialog itself, which is the only thing that can undo it — and
        which also offers the shop a backup of its own data.
        """
        if state.is_usable:
            QMessageBox.warning(self, "Licence", state.message or "")
            return
        ActivationDialog(
            self._license_view_model, state=state, blocked=True, parent=self
        ).exec()

    def _searchable_page(self) -> CollectionView | None:
        """The current screen, if it has a search box of its own."""
        widget = self._pages.get(self._current_route)
        if isinstance(widget, CollectionView) and widget.supports_search:
            return widget
        return None

    def _focus_search(self) -> None:
        page = self._searchable_page()
        if page is not None:
            page.focus_search()
        else:
            self._topbar.focus_search()

    def _on_global_search(self, term: str) -> None:
        # Search the screen the user is actually on, when that screen can
        # be searched. Otherwise fall back to the item catalogue, which is
        # the app's largest searchable dataset.
        if not term:
            return
        page = self._searchable_page()
        if page is not None:
            page.apply_search(term)
            return
        self.navigate(Route.INVENTORY)
        self._inventory_view.apply_search(term)
