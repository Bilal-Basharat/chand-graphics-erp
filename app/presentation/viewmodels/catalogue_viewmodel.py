"""
What the catalogue screen asks for, and what it does when something is
typed into it.

One view model rather than the shared `CollectionViewModel`, because this
screen writes to three things: a category, a product, and the SKU under
it. A single `update` and a single `delete` could not say which — and the
row the shopkeeper is editing is sometimes a product, sometimes one
variant of one.

No business rule lives here. Every method below runs one use case off the
UI thread and reloads the page it was on.
"""
from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from PySide6.QtCore import Signal

from app.application.dto.commands import (
    CreateCategoryCommand,
    CreateInventoryItemCommand,
    CreateProductCommand,
    UpdateCategoryCommand,
    UpdateInventoryItemCommand,
    UpdateProductCommand,
)
from app.application.dto.queries import CataloguePageQuery, PageQuery, PageResult
from app.container import AppContainer
from app.presentation.viewmodels.collection_viewmodel import CollectionViewModelBase

CHOICE_PAGE = 500
"""How many categories or cabinets a picker offers.

Filing is a choice from a list somebody keeps by hand, and a shop with
more than a page of shelves has a naming problem rather than a paging
one — the same reasoning the cabinet picker already follows.
"""


class CatalogueViewModel(CollectionViewModelBase):
    categoriesLoaded = Signal(object)  # [Category]
    cabinetsLoaded = Signal(object)  # [Cabinet]
    unitsLoaded = Signal(int, object)  # sku id, [SkuUnit]

    def __init__(self, container: AppContainer) -> None:
        super().__init__()
        self._container = container

    # ---------------- reading ----------------

    def build_query(self) -> CataloguePageQuery:
        return CataloguePageQuery(**self._state.as_kwargs(), stock=self._state.filter_value)

    def fetch(self, query: PageQuery) -> PageResult:
        return self._container.page_catalogue_use_case().execute(query)

    @property
    def supports_editing(self) -> bool:
        return True

    def load_categories(self) -> None:
        """The shelves a product can be filed on."""
        self.run_async(
            lambda: self._container.page_categories_use_case()
            .execute(PageQuery(page_size=CHOICE_PAGE))
            .rows,
            on_success=self.categoriesLoaded.emit,
        )

    def load_cabinets(self) -> None:
        """Where an item can be kept — maintained on its own screen, so
        refreshed each time this one is opened."""
        self.run_async(
            lambda: self._container.page_cabinets_use_case()
            .execute(PageQuery(page_size=CHOICE_PAGE))
            .rows,
            on_success=self.cabinetsLoaded.emit,
        )

    def load_units(self, sku_id: int, on_loaded: Callable[[list], None]) -> None:
        """One item's alternate units, for the dialog that edits them."""
        self.run_async(
            lambda: self._container.sku_units_use_case().execute(sku_id),
            on_success=on_loaded,
        )

    # ---------------- writing ----------------

    def create(self, command: object) -> None:
        """Save something new, whatever kind of record it is.

        The shared form dialog knows it has a command and a view model,
        not which of three tables the command lands in — so the dispatch
        is here rather than a third dialog base class up there.
        """
        self._write(self._creator(command), created=True, fresh=True)

    def update(self, command: object) -> None:
        self._write(self._updater(command), created=False)

    def _creator(self, command: object) -> Callable[[], object]:
        if isinstance(command, CreateCategoryCommand):
            return lambda: self._container.create_category_use_case().execute(command)
        if isinstance(command, CreateProductCommand):
            return lambda: self._container.create_product_use_case().execute(command)
        if isinstance(command, CreateInventoryItemCommand):
            return lambda: self._container.create_inventory_item_use_case().execute(command)
        raise TypeError(f"Nothing on this screen creates a {type(command).__name__}")

    def _updater(self, command: object) -> Callable[[], object]:
        if isinstance(command, UpdateCategoryCommand):
            return lambda: self._container.update_category_use_case().execute(command)
        if isinstance(command, UpdateProductCommand):
            return lambda: self._container.update_product_use_case().execute(command)
        if isinstance(command, UpdateInventoryItemCommand):
            return lambda: self._container.update_inventory_item_use_case().execute(command)
        raise TypeError(f"Nothing on this screen updates a {type(command).__name__}")

    def move_product(self, product_id: int, category_id: int) -> None:
        """Re-file a product. Nothing but where it is listed changes."""
        self.update(UpdateProductCommand(id=product_id, category_id=category_id))

    def delete_category(self, category_id: int) -> None:
        self._remove(
            lambda: self._container.delete_category_use_case().execute(category_id),
            category_id,
        )

    def delete_product(self, product_id: int) -> None:
        self._remove(
            lambda: self._container.delete_product_use_case().execute(product_id),
            product_id,
        )

    def delete_sku(self, sku_id: int) -> None:
        self._remove(
            lambda: self._container.delete_inventory_item_use_case().execute(sku_id), sku_id
        )

    def _write(self, work: Callable[[], object], *, created: bool, fresh: bool = False) -> None:
        """Run one use case, announce it, then show what it did.

        Always a reload rather than a change to the rows in hand: what the
        screen shows is then what was saved, so an edit the use case
        refused never appears to have worked. `fresh` goes back to the
        first page, where something newly added sorts.

        The announcement is what closes an open dialog — see
        `_CollectionFormDialog` — so a save that failed leaves the form up
        with what was typed still in it.
        """

        def _on_success(result: object) -> None:
            (self.itemCreated if created else self.itemUpdated).emit(result)
            if fresh:
                self.reload_from_start()
            else:
                self.reload()

        self.run_async(work, on_success=_on_success)

    def _remove(self, work: Callable[[], object], record_id: int) -> None:
        def _on_success(_result: object) -> None:
            self.itemDeleted.emit(record_id)
            self.reload()

        self.run_async(work, on_success=_on_success)


def quantity_or_none(text: str) -> Decimal | None:
    """What was typed as a quantity, or None if it is not one.

    Here rather than in the table: refusing a minimum stock of "twenty"
    is a rule about the field, and a widget that decided it would be
    deciding what a quantity is.
    """
    try:
        value = Decimal(text.strip().replace(",", ""))
    except (ArithmeticError, ValueError):
        return None
    return value if value >= 0 else None
