from __future__ import annotations

from collections.abc import Collection

from app.application.dto.commands import (
    CreateInventoryItemCommand,
    UpdateInventoryItemCommand,
)
from app.application.dto.queries import InventoryPageQuery, PageResult

from app.domain.entities.inventory_item import InventoryItem
from app.domain.entities.product import Product
from app.domain.enums.item_type import ItemType
from app.domain.uow import UnitOfWork

from app.application.exceptions import DuplicateEntityError, NotFoundError
from app.application.use_cases.catalogue import ensure_default_category, set_sku_units
from app.application.use_cases.deletion_guard import ensure_not_in_use

from app.application.auth.session import CurrentUserSession
from app.application.auth.authorization import AuthorizationService
from app.application.auth.permissions import Permission
from app.application.use_cases.authenticated_base import AuthenticatedUseCase
from app.application.use_cases.base import UseCase
from app.application.use_cases.authorized_base import (
    AuthorizedUnitOfWorkUseCase,
    AuthorizedUseCase,
)


def add_sku(
    uow: UnitOfWork,
    request: CreateInventoryItemCommand,
    current_user_id: int,
) -> InventoryItem:
    """Create one SKU, whoever is asking.

    Both callers land here — a product being created with its first
    variant, and a variant added to a product that already exists — so
    there is one place that knows what a new SKU needs and one set of
    checks it has to pass.

    A `product_id` of None means "make a product for this", named after
    the item and filed under `General`. That is what a lone item has
    always meant, and it keeps every caller written before products
    existed working exactly as it did.
    """
    items = UseCase.require(uow.inventory_items, "inventory_items")
    cabinets = UseCase.require(uow.cabinets, "cabinets")

    name = request.name.strip()
    if items.get_by_name(name) is not None:
        raise DuplicateEntityError(f"Inventory item '{name}' already exists")

    if request.cabinet_id is not None and cabinets.get_by_id(request.cabinet_id) is None:
        raise NotFoundError(f"Cabinet id={request.cabinet_id} not found")

    product_id = request.product_id
    if product_id is None:
        product_id = _product_for_lone_item(uow, name, current_user_id)
    else:
        products = UseCase.require(uow.products, "products")
        if products.get_by_id(product_id) is None:
            raise NotFoundError(f"Product id={product_id} not found")

    item = items.add(
        InventoryItem(
            name=name,
            product_id=product_id,
            current_stock=request.current_stock,
            minimum_stock=request.minimum_stock,
            description=request.description,
            cabinet_id=request.cabinet_id,
            unit=request.unit,
            created_by_user_id=current_user_id,
        )
    )
    # In the same unit of work as the item: a SKU and the ways it is
    # counted are one thing to save, and a form that set both must not be
    # able to half-save.
    set_sku_units(uow, item, request.units, current_user_id)
    return item


def _product_for_lone_item(uow: UnitOfWork, name: str, current_user_id: int) -> int:
    products = UseCase.require(uow.products, "products")
    category = ensure_default_category(uow, current_user_id)

    existing = products.get_by_name(name)
    if existing is not None:
        raise DuplicateEntityError(f"Product '{name}' already exists")

    product = products.add(
        Product(name=name, category_id=category.id, created_by_user_id=current_user_id)
    )
    return product.id


def ensure_sku_not_traded(uow: UnitOfWork, sku: InventoryItem) -> None:
    """Refuse to remove a SKU that any document names.

    Those documents record what was traded at what price. Deleting the
    item they name would leave them describing something that no longer
    exists, so the caller is told what is holding it instead.
    """
    sales = UseCase.require(uow.sales, "sales")
    purchases = UseCase.require(uow.purchases, "purchases")
    ensure_not_in_use(
        sku.name,
        {
            "sale": sales.count_by_item(ItemType.INVENTORY_ITEM, sku.id),
            "purchase": purchases.count_by_item(ItemType.INVENTORY_ITEM, sku.id),
        },
    )


class CreateInventoryItemUseCase(AuthorizedUseCase[CreateInventoryItemCommand, InventoryItem]):
    """Add a SKU — a further variant of a product, or an item on its own."""

    def __init__(
        self,
        uow: UnitOfWork,
        current_user_session: CurrentUserSession | None = None,
        authorization_service: AuthorizationService | None = None,
    ) -> None:
        if current_user_session is None:
            current_user_session = CurrentUserSession()
        if authorization_service is None:
            authorization_service = AuthorizationService(current_user_session)
        super().__init__(current_user_session, authorization_service)
        self.uow = uow

    def execute(self, request: CreateInventoryItemCommand) -> InventoryItem:
        self.require_permission(Permission.MANAGE_MASTER_DATA)

        if request.current_stock != 0:
            raise ValueError("New items must start with zero stock; stock is set by recording a purchase.")

        current_user_id = self.current_user_id()

        with self.uow as uow:
            return add_sku(uow, request, current_user_id)


class UpdateInventoryItemUseCase(AuthorizedUnitOfWorkUseCase[UpdateInventoryItemCommand, InventoryItem]):
    """Correct a SKU's catalogue details. Stock is untouched — it is the
    result of purchases, sales and adjustments, not a field to type over.

    **Where a product has one SKU, the two are one row on the catalogue
    screen and one form here.** So renaming reaches the product, and so
    does the shelf it is filed on: letting either drift apart from what
    the shopkeeper typed would show them a record they did not enter.
    A product with several SKUs has neither — its name and its shelf are
    its own, and are edited on the product.
    """

    def execute(self, request: UpdateInventoryItemCommand) -> InventoryItem:
        self.require_permission(Permission.MANAGE_MASTER_DATA)

        current_user_id = self.current_user_id()

        with self.uow as uow:
            items = self.require(uow.inventory_items, "inventory_items")
            cabinets = self.require(uow.cabinets, "cabinets")

            item = items.get_by_id(request.id)
            if item is None:
                raise NotFoundError(f"Inventory item id={request.id} not found")

            name = request.name.strip()
            clash = items.get_by_name(name)
            if clash is not None and clash.id != request.id:
                raise DuplicateEntityError(f"Inventory item '{name}' already exists")

            if request.cabinet_id is not None and cabinets.get_by_id(request.cabinet_id) is None:
                raise NotFoundError(f"Cabinet id={request.cabinet_id} not found")

            self._follow_the_lone_product(uow, item, name, request, current_user_id)

            item.name = name
            item.minimum_stock = request.minimum_stock
            item.description = request.description
            item.cabinet_id = request.cabinet_id
            item.unit = request.unit
            item.updated_by_user_id = current_user_id

            saved = items.update(item)
            set_sku_units(uow, saved, request.units, current_user_id)
            return saved

    def _follow_the_lone_product(
        self,
        uow: UnitOfWork,
        item: InventoryItem,
        name: str,
        request: UpdateInventoryItemCommand,
        current_user_id: int,
    ) -> None:
        """Carry the name and the shelf up to the product, where it has
        only this one SKU under it."""
        if item.product_id is None:
            return

        items = self.require(uow.inventory_items, "inventory_items")
        if items.count_by_product(item.product_id) != 1:
            return

        products = self.require(uow.products, "products")
        product = products.get_by_id(item.product_id)
        if product is None:
            return

        changed = False
        if name != product.name:
            clash = products.get_by_name(name)
            if clash is not None and clash.id != product.id:
                raise DuplicateEntityError(f"Product '{name}' already exists")
            product.name = name
            changed = True

        if request.category_id is not None and request.category_id != product.category_id:
            categories = self.require(uow.categories, "categories")
            if categories.get_by_id(request.category_id) is None:
                raise NotFoundError(f"Category id={request.category_id} not found")
            product.category_id = request.category_id
            changed = True

        if changed:
            product.updated_by_user_id = current_user_id
            products.update(product)


class DeleteInventoryItemUseCase(AuthorizedUnitOfWorkUseCase[int, None]):
    """Remove a SKU, unless it has been bought or sold.

    A product left with no SKUs goes with it. One that could not be
    bought, sold or counted is not a catalogue record any more, and
    leaving it behind would put an empty row on the screen that nothing
    could ever fill."""

    def execute(self, request: int) -> None:
        self.require_permission(Permission.MANAGE_MASTER_DATA)

        with self.uow as uow:
            items = self.require(uow.inventory_items, "inventory_items")
            products = self.require(uow.products, "products")

            item = items.get_by_id(request)
            if item is None:
                raise NotFoundError(f"Inventory item id={request} not found")

            ensure_sku_not_traded(uow, item)
            items.delete(request)

            if item.product_id is not None and items.count_by_product(item.product_id) == 0:
                products.delete(item.product_id)


class PageInventoryItemsUseCase(AuthenticatedUseCase[InventoryPageQuery, PageResult]):
    """One page of the catalogue, as a screen asks for it.

    The page and the count run inside one unit of work, so a record added
    between the two cannot leave a list of a hundred rows claiming to be a
    hundred and one.
    """

    def __init__(self, uow: UnitOfWork, current_user_session: CurrentUserSession | None = None) -> None:
        super().__init__(current_user_session)
        self.uow = uow

    def execute(self, request: InventoryPageQuery) -> PageResult:
        with self.uow as uow:
            items = self.require(uow.inventory_items, "inventory_items")
            rows = items.page_items(
                search=request.search,
                stock=request.stock,
                sort_field=request.sort_field,
                sort_desc=request.sort_desc,
                limit=request.page_size,
                offset=request.offset,
            )
            return PageResult(
                rows=rows,
                total=items.count_items(search=request.search, stock=request.stock),
                page=request.page,
                page_size=request.page_size,
            )


class GetInventoryItemNamesUseCase(AuthenticatedUseCase[Collection[int], dict[int, str]]):
    """The names behind a set of item ids.

    For naming the lines on one page of a document list without loading a
    catalogue to look them up in — which is what the screens did until a
    shop had more items than the catalogue was capped at, and every line
    past that read as a dash.
    """

    def __init__(self, uow: UnitOfWork, current_user_session: CurrentUserSession | None = None) -> None:
        super().__init__(current_user_session)
        self.uow = uow

    def execute(self, request: Collection[int]) -> dict[int, str]:
        with self.uow as uow:
            items = self.require(uow.inventory_items, "inventory_items")
            return items.names_by_id(request)


class GetInventoryItemByNameUseCase(AuthenticatedUseCase[str, InventoryItem | None]):
    def __init__(self, uow: UnitOfWork, current_user_session: CurrentUserSession | None = None) -> None:
        super().__init__(current_user_session)
        self.uow = uow

    def execute(self, request: str) -> InventoryItem | None:
        with self.uow as uow:
            items = self.require(uow.inventory_items, "inventory_items")
            return items.get_by_name(request.strip())


class ListLowStockInventoryItemsUseCase(AuthenticatedUseCase[int, list[InventoryItem]]):
    def __init__(self, uow: UnitOfWork, current_user_session: CurrentUserSession | None = None) -> None:
        super().__init__(current_user_session)
        self.uow = uow

    def execute(self, request: int = 100) -> list[InventoryItem]:
        with self.uow as uow:
            items = self.require(uow.inventory_items, "inventory_items")
            return items.list_low_stock(limit=request)
