from __future__ import annotations

from enum import StrEnum


class Route(StrEnum):
    """
    Screen keys shared by the sidebar (which routes get emitted) and the
    main window (which routes have a registered page).
    """

    DASHBOARD = "dashboard"
    SALES = "sales"
    SALE_PAYMENTS = "sale_payments"
    PURCHASES = "purchases"
    PURCHASE_PAYMENTS = "purchase_payments"
    PAYMENT_METHODS = "payment_methods"
    INVENTORY = "inventory"
    CABINETS = "cabinets"
    INVENTORY_MOVEMENT = "inventory_movement"
    CUSTOMERS = "customers"
    SUPPLIERS = "suppliers"
    CUSTOMER_LEDGER = "customer_ledger"
    SUPPLIER_LEDGER = "supplier_ledger"
    EXPENSES = "expenses"
    EXPENSE_CATEGORIES = "expense_categories"
    COMPANY_SETTINGS = "company_settings"
    LICENSE = "license"
    PROFIT_AND_LOSS = "profit_and_loss"
    ITEM_PROFITABILITY = "item_profitability"
    RECEIVABLES_AGEING = "receivables_ageing"
    PAYABLES_AGEING = "payables_ageing"
    PROFILE = "profile"
