from __future__ import annotations

from enum import StrEnum


class Permission(StrEnum):
    MANAGE_USERS = "manage_users"
    MANAGE_SETTINGS = "manage_settings"
    MANAGE_MASTER_DATA = "manage_master_data"
    MANAGE_PURCHASES = "manage_purchases"
    MANAGE_SALES = "manage_sales"
    MANAGE_EXPENSES = "manage_expenses"
    VIEW_REPORTS = "view_reports"


ROLE_PERMISSIONS: dict[str, frozenset[Permission]] = {
    "admin": frozenset(Permission),
    "manager": frozenset(
        {
            Permission.MANAGE_SETTINGS,
            Permission.MANAGE_MASTER_DATA,
            Permission.MANAGE_PURCHASES,
            Permission.MANAGE_SALES,
            Permission.MANAGE_EXPENSES,
            Permission.VIEW_REPORTS,
        }
    ),
    "staff": frozenset(
        {
            Permission.MANAGE_PURCHASES,
            Permission.MANAGE_SALES,
        }
    ),
}