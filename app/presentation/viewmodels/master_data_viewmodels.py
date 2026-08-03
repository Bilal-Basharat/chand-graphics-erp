"""
View model factories for the master-data screens.

These five modules are all "list, search, create", so they share
`CollectionViewModel` and differ only in the use cases wired in here.
Keeping the wiring in one file means the views stay free of container
knowledge and MainWindow stays a composition root rather than a place
where five blocks of plumbing accumulate.

Each callable runs on a worker thread, so it builds *and* executes its
use case — see `CollectionSource`.
"""
from __future__ import annotations

from app.application.dto.queries import SearchQuery
from app.container import AppContainer
from app.presentation.viewmodels.collection_viewmodel import CollectionSource, CollectionViewModel

# Master data lists are small by nature (cabinets, payment methods) or
# comfortably bounded for a single print shop (customers, suppliers,
# items). One page holds all of them; search narrows rather than paginates.
_LIST_LIMIT = 500
_SEARCH_LIMIT = 200


def cabinets_view_model(container: AppContainer) -> CollectionViewModel:
    return CollectionViewModel(
        CollectionSource(
            list_all=lambda: container.list_cabinets_use_case().execute(_LIST_LIMIT),
            create=lambda command: container.create_cabinet_use_case().execute(command),
            update=lambda command: container.update_cabinet_use_case().execute(command),
            delete=lambda cabinet_id: container.delete_cabinet_use_case().execute(cabinet_id),
        )
    )


def payment_methods_view_model(container: AppContainer) -> CollectionViewModel:
    return CollectionViewModel(
        CollectionSource(
            list_all=lambda: container.list_payment_methods_use_case().execute(_LIST_LIMIT),
            create=lambda command: container.create_payment_method_use_case().execute(command),
            update=lambda command: container.update_payment_method_use_case().execute(command),
            delete=lambda method_id: container.delete_payment_method_use_case().execute(method_id),
        )
    )


def customers_view_model(container: AppContainer) -> CollectionViewModel:
    return CollectionViewModel(
        CollectionSource(
            # There is no separate "list all" use case for parties — the
            # search one lists everything when given an empty term.
            list_all=lambda: container.search_customers_use_case().execute(
                SearchQuery(term="", limit=_LIST_LIMIT)
            ),
            search=lambda term: container.search_customers_use_case().execute(
                SearchQuery(term=term, limit=_SEARCH_LIMIT)
            ),
            create=lambda command: container.create_customer_use_case().execute(command),
            update=lambda command: container.update_customer_use_case().execute(command),
            delete=lambda customer_id: container.delete_customer_use_case().execute(customer_id),
        )
    )


def suppliers_view_model(container: AppContainer) -> CollectionViewModel:
    return CollectionViewModel(
        CollectionSource(
            list_all=lambda: container.search_suppliers_use_case().execute(
                SearchQuery(term="", limit=_LIST_LIMIT)
            ),
            search=lambda term: container.search_suppliers_use_case().execute(
                SearchQuery(term=term, limit=_SEARCH_LIMIT)
            ),
            create=lambda command: container.create_supplier_use_case().execute(command),
            update=lambda command: container.update_supplier_use_case().execute(command),
            delete=lambda supplier_id: container.delete_supplier_use_case().execute(supplier_id),
        )
    )


def inventory_items_view_model(container: AppContainer) -> CollectionViewModel:
    return CollectionViewModel(
        CollectionSource(
            list_all=lambda: container.list_inventory_items_use_case().execute(_LIST_LIMIT),
            search=lambda term: container.search_inventory_items_use_case().execute(
                SearchQuery(term=term, limit=_SEARCH_LIMIT)
            ),
            create=lambda command: container.create_inventory_item_use_case().execute(command),
            update=lambda command: container.update_inventory_item_use_case().execute(command),
            delete=lambda item_id: container.delete_inventory_item_use_case().execute(item_id),
        )
    )


def expense_categories_view_model(container: AppContainer) -> CollectionViewModel:
    return CollectionViewModel(
        CollectionSource(
            list_all=lambda: container.list_expense_categories_use_case().execute(_LIST_LIMIT),
            create=lambda command: container.create_expense_category_use_case().execute(command),
            update=lambda command: container.update_expense_category_use_case().execute(command),
            delete=lambda category_id: container.delete_expense_category_use_case().execute(
                category_id
            ),
        )
    )
