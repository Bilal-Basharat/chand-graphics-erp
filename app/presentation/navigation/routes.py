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
    JOBS = "jobs"
    JOB_PAYMENTS = "job_payments"
    PURCHASES = "purchases"
    PURCHASE_PAYMENTS = "purchase_payments"
    PAYMENT_METHODS = "payment_methods"
    PRODUCT_TYPES = "product_types"
    LABOUR_CHARGES = "labour_charges"
    WEDDING_CARDS = "wedding_cards"
    INVENTORY_ITEMS = "inventory_items"
    CABINETS = "cabinets"
    INVENTORY_MOVEMENT = "inventory_movement"
    CUSTOMERS = "customers"
    SUPPLIERS = "suppliers"
    EXPENSES = "expenses"
    EXPENSE_CATEGORIES = "expense_categories"
    COMPANY_SETTINGS = "company_settings"
    REPORTS = "reports"
    PROFILE = "profile"
