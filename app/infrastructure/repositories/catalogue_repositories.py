"""
The three tables that give the catalogue its shape, and its units.

Categories and products are master data; a SKU's units are read by the
documents that were entered in them. They sit together here because the
catalogue screen is one list built from all three, and because a query
that reaches from a product through its SKUs is neither a master-data
query nor a document one.
"""
from __future__ import annotations

from collections.abc import Collection

from sqlalchemy import Select, or_, select, update
from sqlalchemy.orm import Session

from app.domain.entities.category import Category
from app.domain.entities.product import Product
from app.domain.entities.sku_unit import SkuUnit
from app.domain.enums.stock_filter import StockFilter
from app.domain.repositories.category_repository import (
    CategoryRepository as CategoryRepositoryPort,
)
from app.domain.repositories.product_repository import ProductRepository as ProductRepositoryPort
from app.domain.repositories.sku_unit_repository import (
    SkuUnitRepository as SkuUnitRepositoryPort,
)
from app.infrastructure.db.models.category_model import CategoryModel
from app.infrastructure.db.models.inventory_item_model import InventoryItemModel
from app.infrastructure.db.models.inventory_movement_model import InventoryMovementModel
from app.infrastructure.db.models.product_model import ProductModel
from app.infrastructure.db.models.purchase_item_model import PurchaseItemModel
from app.infrastructure.db.models.sale_item_model import SaleItemModel
from app.infrastructure.db.models.sku_unit_model import SkuUnitModel
from app.infrastructure.mappers.category_mapper import CategoryMapper
from app.infrastructure.mappers.product_mapper import ProductMapper
from app.infrastructure.mappers.sku_unit_mapper import SkuUnitMapper
from app.infrastructure.repositories.base import SQLAlchemyRepository
from app.infrastructure.repositories.master_data_repositories import _TextSearched
from app.infrastructure.repositories.paging import contains, matching


############################################################
################## Category Repository #####################
############################################################
class SqlAlchemyCategoryRepository(
    _TextSearched,
    SQLAlchemyRepository[Category, CategoryModel],
    CategoryRepositoryPort,
):
    """Persistence for the shelves products are listed on."""

    _SORTABLE = {"name": CategoryModel.name, "created": CategoryModel.created_at}
    _DEFAULT_SORT = "name"
    _SEARCHED = (CategoryModel.name, CategoryModel.description)

    def __init__(self, session: Session) -> None:
        super().__init__(session, CategoryModel, CategoryMapper)

    def get_by_name(self, name: str) -> Category | None:
        return self.find_one_by("name", name)

    def page_categories(
        self,
        *,
        search: str = "",
        sort_field: str | None = None,
        sort_desc: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Category]:
        return self._page(search, sort_field, sort_desc, limit, offset)

    def count_categories(self, *, search: str = "") -> int:
        return self.count_of(self._filtered(search))

    def names_by_id(self, category_ids: Collection[int]) -> dict[int, str]:
        ids = set(category_ids)
        if not ids:
            return {}
        stmt = select(CategoryModel.id, CategoryModel.name).where(CategoryModel.id.in_(ids))
        return {row.id: row.name for row in self.session.execute(stmt)}


############################################################
################### Product Repository #####################
############################################################
class SqlAlchemyProductRepository(
    SQLAlchemyRepository[Product, ProductModel],
    ProductRepositoryPort,
):
    """Persistence for what the shop trades in, and for the one list the
    catalogue screen is built from."""

    _SORTABLE = {"name": ProductModel.name, "created": ProductModel.created_at}
    """What the catalogue may be ordered by *within* a category. A column
    that is not here cannot be sorted on, and the heading for it says so
    by carrying no mark."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, ProductModel, ProductMapper)

    def get_by_name(self, name: str) -> Product | None:
        return self.find_one_by("name", name)

    def _filtered_catalogue(
        self, search: str, stock: str | None, category_id: int | None
    ) -> Select:
        """The conditions both the page and its count are subject to.

        Written once: a filter applied to the rows and forgotten in the
        count is a list that disagrees with its own page numbers.

        Both the search and the stock filter reach through to the SKUs, as
        `EXISTS` rather than as a join — a product with four variants
        matching a term is one row in the catalogue, and a join would list
        it four times.
        """
        stmt = select(ProductModel).join(
            CategoryModel, ProductModel.category_id == CategoryModel.id
        )

        if category_id is not None:
            stmt = stmt.where(ProductModel.category_id == category_id)

        if search:
            pattern = contains(search)
            in_a_sku = (
                select(InventoryItemModel.id)
                .where(
                    InventoryItemModel.product_id == ProductModel.id,
                    matching(pattern, InventoryItemModel.name, InventoryItemModel.description),
                )
                .exists()
            )
            stmt = stmt.where(or_(ProductModel.name.ilike(pattern), in_a_sku))

        level = self._stock_condition(stock)
        if level is not None:
            at_that_level = (
                select(InventoryItemModel.id)
                .where(InventoryItemModel.product_id == ProductModel.id, level)
                .exists()
            )
            stmt = stmt.where(at_that_level)

        return stmt

    @staticmethod
    def _stock_condition(stock: str | None):
        """Where one SKU has to be for its product to answer the filter."""
        if stock == StockFilter.LOW:
            return InventoryItemModel.current_stock <= InventoryItemModel.minimum_stock
        if stock == StockFilter.OUT:
            return InventoryItemModel.current_stock <= 0
        if stock == StockFilter.IN:
            return InventoryItemModel.current_stock > InventoryItemModel.minimum_stock
        return None

    def page_catalogue(
        self,
        *,
        search: str = "",
        stock: str | None = None,
        category_id: int | None = None,
        sort_field: str | None = None,
        sort_desc: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Product]:
        stmt = self._filtered_catalogue(search, stock, category_id)

        # Ordered here rather than through `paging.ordered`, which puts the
        # chosen column first. The catalogue's grouping is not a sort the
        # screen chose and cannot be given up: pages are cut out of one
        # long list, so a category whose products were not contiguous
        # would have its heading written again on the next page, and again
        # on the one after that. What the screen chooses orders products
        # *inside* a category. The primary key ends every order — see
        # `paging.ordered` for why a page without a tiebreak can show a
        # record twice and another not at all.
        column = self._SORTABLE.get(sort_field or "", ProductModel.name)
        chosen = column.desc() if sort_desc else column.asc()
        stmt = stmt.order_by(CategoryModel.name.asc(), chosen, ProductModel.id.asc())

        models = self.session.execute(stmt.limit(limit).offset(offset)).scalars().all()
        return [ProductMapper.to_entity(model) for model in models]

    def count_catalogue(
        self,
        *,
        search: str = "",
        stock: str | None = None,
        category_id: int | None = None,
    ) -> int:
        return self.count_of(self._filtered_catalogue(search, stock, category_id))

    def count_in_category(self, category_id: int) -> int:
        return self.count_of(
            select(ProductModel).where(ProductModel.category_id == category_id)
        )

    def move_category(self, *, from_category_id: int, to_category_id: int) -> int:
        stmt = (
            update(ProductModel)
            .where(ProductModel.category_id == from_category_id)
            .values(category_id=to_category_id)
        )
        return int(self.session.execute(stmt).rowcount)

    def names_by_id(self, product_ids: Collection[int]) -> dict[int, str]:
        ids = set(product_ids)
        if not ids:
            return {}
        stmt = select(ProductModel.id, ProductModel.name).where(ProductModel.id.in_(ids))
        return {row.id: row.name for row in self.session.execute(stmt)}


############################################################
################## SKU Unit Repository #####################
############################################################
class SqlAlchemySkuUnitRepository(
    SQLAlchemyRepository[SkuUnit, SkuUnitModel],
    SkuUnitRepositoryPort,
):
    """Persistence for the alternate units a SKU is traded in."""

    _CARRIED_ON = (SaleItemModel, PurchaseItemModel, InventoryMovementModel)
    """Everywhere a `uom_id` can appear.

    The one place that knows, the way `_item_column` is the one place that
    knows where an item id appears. A line table added without being added
    here would let a unit still in use be deleted out from under it.
    """

    def __init__(self, session: Session) -> None:
        super().__init__(session, SkuUnitModel, SkuUnitMapper)

    def list_for_sku(self, sku_id: int, *, active_only: bool = False) -> list[SkuUnit]:
        stmt = select(SkuUnitModel).where(SkuUnitModel.sku_id == sku_id)
        if active_only:
            stmt = stmt.where(SkuUnitModel.is_active.is_(True))
        models = self.session.execute(stmt.order_by(SkuUnitModel.name.asc())).scalars().all()
        return [SkuUnitMapper.to_entity(model) for model in models]

    def list_for_skus(self, sku_ids: Collection[int]) -> dict[int, list[SkuUnit]]:
        ids = set(sku_ids)
        if not ids:
            return {}
        stmt = (
            select(SkuUnitModel)
            .where(SkuUnitModel.sku_id.in_(ids))
            .order_by(SkuUnitModel.sku_id.asc(), SkuUnitModel.name.asc())
        )
        grouped: dict[int, list[SkuUnit]] = {}
        for model in self.session.execute(stmt).scalars():
            grouped.setdefault(model.sku_id, []).append(SkuUnitMapper.to_entity(model))
        return grouped

    def get_for_sku(self, sku_id: int, unit_id: int) -> SkuUnit | None:
        stmt = select(SkuUnitModel).where(
            SkuUnitModel.id == unit_id,
            SkuUnitModel.sku_id == sku_id,
        )
        model = self.session.execute(stmt).scalar_one_or_none()
        return None if model is None else SkuUnitMapper.to_entity(model)

    def count_usages(self, unit_id: int) -> int:
        return sum(
            self.count_of(select(model).where(model.uom_id == unit_id))
            for model in self._CARRIED_ON
        )

    def names_by_id(self, unit_ids: Collection[int]) -> dict[int, str]:
        ids = {unit_id for unit_id in unit_ids if unit_id is not None}
        if not ids:
            return {}
        stmt = select(SkuUnitModel.id, SkuUnitModel.name).where(SkuUnitModel.id.in_(ids))
        return {row.id: row.name for row in self.session.execute(stmt)}
