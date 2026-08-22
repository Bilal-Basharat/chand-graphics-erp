"""
View models for the master-data screens.

These modules are all "list, search, create", so they share
`CollectionViewModel` and differ only in the use cases wired in here.
Keeping the wiring in one file means the views stay free of container
knowledge and MainWindow stays a composition root rather than a place
where six blocks of plumbing accumulate.

Each callable runs on a worker thread, so it builds *and* executes its
use case — see `CollectionSource`.

Every list here is one page of its list. What is typed, what is filtered
and what is sorted by all travel in the query rather than being applied to
the rows that came back, so a shop with two thousand items can reach the
last of them.
"""
from __future__ import annotations

from PySide6.QtCore import Signal

from app.application.dto.queries import InventoryPageQuery, PageQuery
from app.container import AppContainer
from app.presentation.viewmodels.collection_viewmodel import CollectionSource, CollectionViewModel


def cabinets_view_model(container: AppContainer) -> CollectionViewModel:
    return CollectionViewModel(
        CollectionSource(
            page=lambda query: container.page_cabinets_use_case().execute(query),
            create=lambda command: container.create_cabinet_use_case().execute(command),
            update=lambda command: container.update_cabinet_use_case().execute(command),
            delete=lambda cabinet_id: container.delete_cabinet_use_case().execute(cabinet_id),
        )
    )


def payment_methods_view_model(container: AppContainer) -> CollectionViewModel:
    return CollectionViewModel(
        CollectionSource(
            page=lambda query: container.page_payment_methods_use_case().execute(query),
            create=lambda command: container.create_payment_method_use_case().execute(command),
            update=lambda command: container.update_payment_method_use_case().execute(command),
            delete=lambda method_id: container.delete_payment_method_use_case().execute(method_id),
        )
    )


def customers_view_model(container: AppContainer) -> CollectionViewModel:
    return CollectionViewModel(
        CollectionSource(
            page=lambda query: container.page_customers_use_case().execute(query),
            create=lambda command: container.create_customer_use_case().execute(command),
            update=lambda command: container.update_customer_use_case().execute(command),
            delete=lambda customer_id: container.delete_customer_use_case().execute(customer_id),
        )
    )


def suppliers_view_model(container: AppContainer) -> CollectionViewModel:
    return CollectionViewModel(
        CollectionSource(
            page=lambda query: container.page_suppliers_use_case().execute(query),
            create=lambda command: container.create_supplier_use_case().execute(command),
            update=lambda command: container.update_supplier_use_case().execute(command),
            delete=lambda supplier_id: container.delete_supplier_use_case().execute(supplier_id),
        )
    )


def expense_categories_view_model(container: AppContainer) -> CollectionViewModel:
    return CollectionViewModel(
        CollectionSource(
            page=lambda query: container.page_expense_categories_use_case().execute(query),
            create=lambda command: container.create_expense_category_use_case().execute(command),
            update=lambda command: container.update_expense_category_use_case().execute(command),
            delete=lambda category_id: container.delete_expense_category_use_case().execute(
                category_id
            ),
        )
    )
