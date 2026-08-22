"""
The catalogue: shelves, the things on them, and how those are counted.

Three records and one screen. A **category** is a shelf. A **product** is
what the shop calls a thing it trades in. A **SKU** — `InventoryItem`, the
record every document line and every count has always pointed at — is the
stockable identity underneath it, and nearly every product has exactly
one. That last fact is the whole design: a shopkeeper adds "A4 Ivory
250gsm" and gets a product with one SKU, never sees the word SKU, and
only meets the idea when a product genuinely has two of them.

Nothing here creates a SKU. `CreateInventoryItemUseCase` does, and does it
for both callers — the product being created with its first variant, and
a variant added to a product that already exists — so there is one place
that knows what a new SKU needs.
"""
from __future__ import annotations

from collections.abc import Collection

from app.application.auth.session import CurrentUserSession
from app.application.dto.commands import (
    CreateCategoryCommand,
    CreateInventoryItemCommand,
    CreateProductCommand,
    UpdateCategoryCommand,
    UpdateInventoryItemCommand,
    UpdateProductCommand,
)
from app.application.dto.queries import (
    CataloguePageQuery,
    CatalogueRow,
    PageQuery,
    PageResult,
)
from app.application.exceptions import DuplicateEntityError, NotFoundError
from app.application.use_cases.authenticated_base import AuthenticatedUseCase
from app.application.use_cases.authorized_base import AuthorizedUnitOfWorkUseCase
from app.application.use_cases.base import UseCase
from app.application.use_cases.master_data import _MasterDataPageUseCase, _NamesByIdUseCase
from app.domain.entities.category import DEFAULT_CATEGORY_NAME, Category
from app.domain.entities.product import Product
from app.domain.entities.sku_unit import SkuUnit
from app.domain.uow import UnitOfWork
from app.application.auth.permissions import Permission

_DEFAULT_CATEGORY_DESCRIPTION = "Everything not filed anywhere else yet."


def ensure_default_category(uow: UnitOfWork, created_by_user_id: int | None = None) -> Category:
    """The `General` category, made if this database has never had one.

    Looked up by name rather than by id: the row is written by a
    migration on a database that already has data and by the initializer
    on a fresh one, so its id differs between installations while its
    name never does.
    """
    categories = UseCase.require(getattr(uow, "categories", None), "categories")
    existing = categories.get_by_name(DEFAULT_CATEGORY_NAME)
    if existing is not None:
        return existing
    return categories.add(
        Category(
            name=DEFAULT_CATEGORY_NAME,
            description=_DEFAULT_CATEGORY_DESCRIPTION,
            created_by_user_id=created_by_user_id,
        )
    )


############################################################
################## Category Use Cases ######################
############################################################
class EnsureDefaultCategoryUseCase(UseCase[None, Category]):
    """Give a database the one category that needs no decision.

    Runs at startup beside the initial administrator, and for the same
    reason: a product must be filed somewhere, and a shop opening the app
    for the first time should not be asked where before it can add one.
    Unauthenticated, because nobody has signed in yet when it runs.
    """

    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def execute(self, request: None = None) -> Category:
        with self.uow as uow:
            return ensure_default_category(uow)


class CreateCategoryUseCase(AuthorizedUnitOfWorkUseCase[CreateCategoryCommand, Category]):
    def execute(self, request: CreateCategoryCommand) -> Category:
        self.require_permission(Permission.MANAGE_MASTER_DATA)
        current_user_id = self.current_user_id()

        with self.uow as uow:
            categories = self.require(uow.categories, "categories")
            name = " ".join(request.name.split())

            # Checked here rather than left to a unique index, as every
            # other master-data record is: a driver error could only be
            # reported as "something went wrong", and two shelves with one
            # name is an ordinary mistake deserving an ordinary message.
            if categories.get_by_name(name) is not None:
                raise DuplicateEntityError(f"Category '{name}' already exists")

            return categories.add(
                Category(
                    name=name,
                    description=request.description,
                    created_by_user_id=current_user_id,
                )
            )


class UpdateCategoryUseCase(AuthorizedUnitOfWorkUseCase[UpdateCategoryCommand, Category]):
    def execute(self, request: UpdateCategoryCommand) -> Category:
        self.require_permission(Permission.MANAGE_MASTER_DATA)
        current_user_id = self.current_user_id()

        with self.uow as uow:
            categories = self.require(uow.categories, "categories")

            category = categories.get_by_id(request.id)
            if category is None:
                raise NotFoundError(f"Category id={request.id} not found")

            name = " ".join(request.name.split())
            clash = categories.get_by_name(name)
            if clash is not None and clash.id != request.id:
                raise DuplicateEntityError(f"Category '{name}' already exists")

            if category.is_default and not Category(name=name).is_default:
                raise ValueError(
                    f"'{DEFAULT_CATEGORY_NAME}' is where products go when no other shelf "
                    "is chosen, so it cannot be renamed."
                )

            category.name = name
            category.description = request.description
            category.updated_by_user_id = current_user_id
            return categories.update(category)


class DeleteCategoryUseCase(AuthorizedUnitOfWorkUseCase[int, None]):
    """Remove a shelf. Whatever was on it goes back to `General`.

    Deliberately not refused while it holds products, the way deleting a
    traded item is. A category is where a product is listed, not what it
    is: nothing about the products changes, and refusing would leave the
    shopkeeper re-filing a dozen of them by hand before a tidy-up.
    """

    def execute(self, request: int) -> None:
        self.require_permission(Permission.MANAGE_MASTER_DATA)
        current_user_id = self.current_user_id()

        with self.uow as uow:
            categories = self.require(uow.categories, "categories")
            products = self.require(uow.products, "products")

            category = categories.get_by_id(request)
            if category is None:
                raise NotFoundError(f"Category id={request} not found")

            if category.is_default:
                raise ValueError(
                    f"'{DEFAULT_CATEGORY_NAME}' is where products go when no other shelf "
                    "is chosen, so it cannot be deleted."
                )

            fallback = ensure_default_category(uow, current_user_id)
            products.move_category(from_category_id=request, to_category_id=fallback.id)
            categories.delete(request)


class PageCategoriesUseCase(_MasterDataPageUseCase):
    def _rows_and_total(self, uow: UnitOfWork, request: PageQuery) -> tuple[list, int]:
        categories = self.require(uow.categories, "categories")
        rows = categories.page_categories(
            search=request.search,
            sort_field=request.sort_field,
            sort_desc=request.sort_desc,
            limit=request.page_size,
            offset=request.offset,
        )
        return rows, categories.count_categories(search=request.search)


class GetCategoryNamesUseCase(_NamesByIdUseCase):
    def _repository(self, uow: UnitOfWork):
        return self.require(uow.categories, "categories")


############################################################
################### Product Use Cases ######################
############################################################
class CreateProductUseCase(AuthorizedUnitOfWorkUseCase[CreateProductCommand, Product]):
    """A product, and the one SKU it starts life with.

    Both in one unit of work: a product with nothing under it could not be
    bought, sold or counted, and a half-finished pair left behind by a
    failure would be exactly that.

    The SKU takes the product's own name, because for the great majority
    of products there will only ever be one and that name is what belongs
    on an invoice. A second variant is added later and named for what
    tells it apart.
    """

    def execute(self, request: CreateProductCommand) -> Product:
        self.require_permission(Permission.MANAGE_MASTER_DATA)
        current_user_id = self.current_user_id()

        with self.uow as uow:
            categories = self.require(uow.categories, "categories")
            products = self.require(uow.products, "products")
            items = self.require(uow.inventory_items, "inventory_items")

            name = " ".join(request.name.split())
            if not name:
                raise ValueError("name cannot be empty")

            if products.get_by_name(name) is not None:
                raise DuplicateEntityError(f"Product '{name}' already exists")

            # The SKU's name is the product's, so a name already taken by
            # an item would fail further down with a message about
            # something the shopkeeper never mentioned.
            if items.get_by_name(name) is not None:
                raise DuplicateEntityError(f"Inventory item '{name}' already exists")

            if request.category_id is None:
                category = ensure_default_category(uow, current_user_id)
            else:
                category = categories.get_by_id(request.category_id)
                if category is None:
                    raise NotFoundError(f"Category id={request.category_id} not found")

            if request.cabinet_id is not None:
                cabinets = self.require(uow.cabinets, "cabinets")
                if cabinets.get_by_id(request.cabinet_id) is None:
                    raise NotFoundError(f"Cabinet id={request.cabinet_id} not found")

            product = products.add(
                Product(
                    name=name,
                    category_id=category.id,
                    created_by_user_id=current_user_id,
                )
            )

            # Through the SKU use case rather than the repository, so a
            # product's first variant is created by the same code as its
            # second — one place that knows what a new SKU needs.
            _create_sku(
                uow,
                CreateInventoryItemCommand(
                    name=name,
                    product_id=product.id,
                    unit=request.unit,
                    minimum_stock=request.minimum_stock,
                    description=request.description,
                    cabinet_id=request.cabinet_id,
                ),
                current_user_id,
            )
            return product


class UpdateProductUseCase(AuthorizedUnitOfWorkUseCase[UpdateProductCommand, Product]):
    """Rename a product, or file it on another shelf, or both.

    **Renaming reaches its SKU when it has exactly one.** That row on the
    catalogue screen *is* the SKU as far as the shopkeeper is concerned —
    it shows its stock and its unit — so a rename that left the invoice
    still saying the old name would read as the software ignoring them.
    Where a product has several SKUs they carry their own names, and the
    product's name is only the heading they sit under.

    Moving between categories touches `category_id` and nothing else. No
    stock, no unit, no price and no document is affected by where a
    product is listed, which is what makes dragging one safe.
    """

    def execute(self, request: UpdateProductCommand) -> Product:
        self.require_permission(Permission.MANAGE_MASTER_DATA)
        current_user_id = self.current_user_id()

        with self.uow as uow:
            products = self.require(uow.products, "products")
            categories = self.require(uow.categories, "categories")
            items = self.require(uow.inventory_items, "inventory_items")

            product = products.get_by_id(request.id)
            if product is None:
                raise NotFoundError(f"Product id={request.id} not found")

            if request.category_id is not None and request.category_id != product.category_id:
                if categories.get_by_id(request.category_id) is None:
                    raise NotFoundError(f"Category id={request.category_id} not found")
                product.category_id = request.category_id

            if request.name is not None:
                name = " ".join(request.name.split())
                if not name:
                    raise ValueError("name cannot be empty")

                clash = products.get_by_name(name)
                if clash is not None and clash.id != product.id:
                    raise DuplicateEntityError(f"Product '{name}' already exists")

                if name != product.name:
                    self._rename_only_sku(items, product.id, name, current_user_id)
                    product.name = name

            product.updated_by_user_id = current_user_id
            return products.update(product)

    @staticmethod
    def _rename_only_sku(items, product_id: int, name: str, current_user_id: int) -> None:
        skus = items.list_by_product_ids([product_id]).get(product_id, [])
        if len(skus) != 1:
            return

        sku = skus[0]
        clash = items.get_by_name(name)
        if clash is not None and clash.id != sku.id:
            raise DuplicateEntityError(f"Inventory item '{name}' already exists")

        sku.name = name
        sku.updated_by_user_id = current_user_id
        items.update(sku)


class DeleteProductUseCase(AuthorizedUnitOfWorkUseCase[int, None]):
    """Remove a product and the SKUs under it.

    Every one of those SKUs is checked the way a single item is: anything
    that has been bought or sold stays, because the documents naming it
    would otherwise describe something that no longer exists. Checked
    before any of them is removed, so a product with three variants and
    one sale is refused whole rather than half-deleted.
    """

    def execute(self, request: int) -> None:
        self.require_permission(Permission.MANAGE_MASTER_DATA)

        with self.uow as uow:
            products = self.require(uow.products, "products")
            items = self.require(uow.inventory_items, "inventory_items")

            product = products.get_by_id(request)
            if product is None:
                raise NotFoundError(f"Product id={request} not found")

            skus = items.list_by_product_ids([request]).get(request, [])
            for sku in skus:
                _ensure_sku_not_traded(uow, sku)
            for sku in skus:
                items.delete(sku.id)

            products.delete(request)


class PageCatalogueUseCase(AuthenticatedUseCase[CataloguePageQuery, PageResult]):
    """One page of the catalogue, assembled for the screen that shows it.

    Three queries for a page of any size: the products, their SKUs, and
    the names of the categories they are filed under. Not one per row —
    a hundred-row page would then be two hundred and one round trips, and
    the screen would slow down as the shop grew.
    """

    def __init__(self, uow: UnitOfWork, current_user_session: CurrentUserSession | None = None) -> None:
        super().__init__(current_user_session)
        self.uow = uow

    def execute(self, request: CataloguePageQuery) -> PageResult:
        with self.uow as uow:
            products = self.require(uow.products, "products")
            items = self.require(uow.inventory_items, "inventory_items")
            categories = self.require(uow.categories, "categories")

            conditions = {
                "search": request.search,
                "stock": request.stock,
                "category_id": request.category_id,
            }
            page = products.page_catalogue(
                **conditions,
                sort_field=request.sort_field,
                sort_desc=request.sort_desc,
                limit=request.page_size,
                offset=request.offset,
            )

            skus = items.list_by_product_ids([product.id for product in page])
            names = categories.names_by_id({product.category_id for product in page})

            rows = [
                CatalogueRow(
                    product=product,
                    category_id=product.category_id,
                    category_name=names.get(product.category_id, DEFAULT_CATEGORY_NAME),
                    skus=tuple(skus.get(product.id, ())),
                )
                for product in page
            ]
            return PageResult(
                rows=rows,
                total=products.count_catalogue(**conditions),
                page=request.page,
                page_size=request.page_size,
            )


class GetProductNamesUseCase(_NamesByIdUseCase):
    def _repository(self, uow: UnitOfWork):
        return self.require(uow.products, "products")


############################################################
#################### SKU Unit Use Cases ####################
############################################################
class GetSkuUnitsUseCase(AuthenticatedUseCase[int, list[SkuUnit]]):
    """A SKU's alternate units — all of them, retired ones included.

    Everything that *reads* a document needs the retired ones too, or a
    line entered in one would name nothing. The places that offer a
    choice ask for the active ones.
    """

    def __init__(self, uow: UnitOfWork, current_user_session: CurrentUserSession | None = None) -> None:
        super().__init__(current_user_session)
        self.uow = uow

    def execute(self, request: int) -> list[SkuUnit]:
        with self.uow as uow:
            return self.require(uow.sku_units, "sku_units").list_for_sku(request)


class GetActiveSkuUnitsUseCase(GetSkuUnitsUseCase):
    """The units a new document line may be entered in."""

    def execute(self, request: int) -> list[SkuUnit]:
        with self.uow as uow:
            units = self.require(uow.sku_units, "sku_units")
            return units.list_for_sku(request, active_only=True)


def set_sku_units(uow: UnitOfWork, sku, specs, current_user_id: int) -> list[SkuUnit]:
    """A SKU's alternate units, as the dialog left them.

    The whole list at once, because that is what the shopkeeper edited.
    What happens to a unit no longer in it depends on whether anything
    used it: one that was never used is deleted, and one that a document
    was entered in is **retired instead**. Deleting that one would leave
    the line that used it naming nothing and its base quantity
    unexplained — the conversion is history, not configuration.

    A unit still in the list keeps its identity, so correcting a mistyped
    factor corrects the unit rather than replacing it. Past documents are
    unaffected either way: they carry the base quantity the factor
    produced at the time.

    A function rather than a use case of its own: units are saved with
    the item they belong to, in the item's own unit of work, so that a
    form which changed both cannot half-save.
    """
    units = UseCase.require(getattr(uow, "sku_units", None), "sku_units")

    wanted = _validated_units(specs, sku)
    existing = units.list_for_sku(sku.id)
    matched = {_match_unit(unit, existing) for unit in wanted}

    # Dropped first, so a unit being renamed frees its name before
    # anything tries to take it — (sku, name) is unique, and the other
    # order fails on the swap.
    _retire_or_remove(
        units,
        [unit for unit in existing if unit.id not in matched],
        current_user_id,
    )

    kept: list[SkuUnit] = []
    for spec in wanted:
        unit_id = _match_unit(spec, existing)
        if unit_id is None:
            kept.append(
                units.add(
                    SkuUnit(
                        sku_id=sku.id,
                        name=spec.name,
                        factor=spec.factor,
                        created_by_user_id=current_user_id,
                    )
                )
            )
            continue
        unit = next(unit for unit in existing if unit.id == unit_id)
        unit.name = spec.name
        unit.factor = spec.factor
        # Naming it again brings it back: a shop that stopped selling by
        # the box and started again means the box it already has, not a
        # second one beside it.
        unit.is_active = True
        unit.updated_by_user_id = current_user_id
        kept.append(units.update(unit))

    return kept


def _match_unit(spec: SkuUnit, existing: list[SkuUnit]) -> int | None:
    """Which unit this line of the list is, if it is one already there.

    By id where the dialog carried one, and otherwise by name — because a
    name is what a unit *is* to the person typing it, and a list retyped
    without ids must not try to add a second "Box" beside the one that is
    already there.
    """
    if spec.id is not None:
        return spec.id
    folded = spec.name.casefold()
    return next((unit.id for unit in existing if unit.name.casefold() == folded), None)


def _validated_units(specs, sku) -> list[SkuUnit]:
    """The list as stated, refused where it could not mean anything.

    A unit named the same as the SKU's base unit is the one that would
    genuinely confuse a count: two entries in a dropdown reading "Piece",
    one of them worth 288 of the other.
    """
    base = (sku.unit or "").strip().casefold()
    seen: set[str] = set()
    checked = []
    for spec in specs:
        name = " ".join(spec.name.split())
        if not name:
            raise ValueError("a unit needs a name")
        if name.casefold() == base:
            raise ValueError(
                f"'{name}' is already this item's own unit, so it cannot also be another one."
            )
        if name.casefold() in seen:
            raise DuplicateEntityError(f"'{name}' is listed twice")
        seen.add(name.casefold())
        # Validated by the entity rather than here — a factor of zero is
        # refused in one place, whoever is building one.
        checked.append(SkuUnit(id=spec.id, sku_id=sku.id, name=name, factor=spec.factor))
    return checked


def _retire_or_remove(units, dropped: list, current_user_id: int) -> None:
    """A unit no longer in the list: gone if nothing used it, retired if
    something did."""
    for unit in dropped:
        if units.count_usages(unit.id):
            if not unit.is_active:
                continue
            unit.is_active = False
            unit.updated_by_user_id = current_user_id
            units.update(unit)
            continue
        units.delete(unit.id)


############################################################
###################### SKU helpers #########################
############################################################
def _create_sku(uow: UnitOfWork, command: CreateInventoryItemCommand, current_user_id: int):
    """Add a SKU through the use case that owns doing so.

    Imported here rather than at the top of the module: the item use
    cases reach back into this one for the default category, and naming
    each other at import time would be a cycle.
    """
    from app.application.use_cases.inventory_items import add_sku

    return add_sku(uow, command, current_user_id)


def _ensure_sku_not_traded(uow: UnitOfWork, sku) -> None:
    from app.application.use_cases.inventory_items import ensure_sku_not_traded

    ensure_sku_not_traded(uow, sku)


__all__ = [
    "CreateCategoryUseCase",
    "CreateProductUseCase",
    "DeleteCategoryUseCase",
    "DeleteProductUseCase",
    "EnsureDefaultCategoryUseCase",
    "GetActiveSkuUnitsUseCase",
    "GetCategoryNamesUseCase",
    "GetProductNamesUseCase",
    "GetSkuUnitsUseCase",
    "PageCatalogueUseCase",
    "PageCategoriesUseCase",
    "set_sku_units",
    "UpdateCategoryUseCase",
    "UpdateProductUseCase",
    "ensure_default_category",
]
