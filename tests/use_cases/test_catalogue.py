"""
Shelves, the things on them, and the item that always comes with one.

The rule these are all circling is that a product and its first item are
one act, not two. A shopkeeper types a name and gets something that can
be bought, sold and counted; nothing in the flow asks them what a SKU is.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.application.dto.commands import (
    CreateCategoryCommand,
    CreateInventoryItemCommand,
    CreateProductCommand,
    CreatePurchaseCommand,
    PurchaseItemCommand,
    SkuUnitCommand,
    UpdateCategoryCommand,
    UpdateInventoryItemCommand,
    UpdateProductCommand,
)
from app.application.dto.queries import CataloguePageQuery, PageQuery
from app.application.auth.exceptions import PermissionDeniedError
from app.application.exceptions import DuplicateEntityError, EntityInUseError, NotFoundError
from app.application.use_cases.catalogue import (
    CreateCategoryUseCase,
    CreateProductUseCase,
    DeleteCategoryUseCase,
    DeleteProductUseCase,
    EnsureDefaultCategoryUseCase,
    GetSkuUnitsUseCase,
    PageCatalogueUseCase,
    PageCategoriesUseCase,
    UpdateCategoryUseCase,
    UpdateProductUseCase,
)
from app.application.use_cases.inventory_items import (
    CreateInventoryItemUseCase,
    DeleteInventoryItemUseCase,
    UpdateInventoryItemUseCase,
)
from app.application.use_cases.purchases import CreatePurchaseUseCase
from app.domain.entities.category import DEFAULT_CATEGORY_NAME
from app.domain.enums.item_type import ItemType
from app.domain.enums.stock_filter import StockFilter


def _category(uow, session, name: str, description: str | None = None):
    return CreateCategoryUseCase(uow, session).execute(
        CreateCategoryCommand(name=name, description=description)
    )


def _product(uow, session, name: str, category_id: int | None = None, unit: str = "Piece"):
    return CreateProductUseCase(uow, session).execute(
        CreateProductCommand(name=name, category_id=category_id, unit=unit)
    )


def _page(uow, session, **kwargs):
    return PageCatalogueUseCase(uow, session).execute(CataloguePageQuery(**kwargs))


def _row_named(page, name: str):
    return next(row for row in page.rows if row.name == name)


# ---------------------------------------------------------------- categories


def test_a_database_with_no_categories_gets_the_default_one(uow, admin_session):
    category = EnsureDefaultCategoryUseCase(uow).execute()

    assert category.name == DEFAULT_CATEGORY_NAME
    assert category.is_default


def test_the_default_category_is_made_once_and_reused(uow, admin_session):
    first = EnsureDefaultCategoryUseCase(uow).execute()
    second = EnsureDefaultCategoryUseCase(uow).execute()

    assert first.id == second.id
    assert PageCategoriesUseCase(uow, admin_session).execute(PageQuery()).total == 1


def test_a_category_is_created_and_listed(uow, admin_session):
    _category(uow, admin_session, "Papers", "Everything printed on.")

    page = PageCategoriesUseCase(uow, admin_session).execute(PageQuery())
    assert [row.name for row in page.rows] == ["Papers"]


def test_two_categories_cannot_share_a_name(uow, admin_session):
    _category(uow, admin_session, "Papers")

    with pytest.raises(DuplicateEntityError):
        _category(uow, admin_session, "Papers")


def test_a_category_needs_a_name(uow, admin_session):
    with pytest.raises(ValueError):
        _category(uow, admin_session, "   ")


def test_the_default_category_cannot_be_renamed_or_deleted(uow, admin_session):
    general = EnsureDefaultCategoryUseCase(uow).execute()

    with pytest.raises(ValueError):
        UpdateCategoryUseCase(uow, admin_session).execute(
            UpdateCategoryCommand(id=general.id, name="Bits and pieces")
        )
    with pytest.raises(ValueError):
        DeleteCategoryUseCase(uow, admin_session).execute(general.id)


def test_deleting_a_category_re_files_its_products_rather_than_refusing(uow, admin_session):
    papers = _category(uow, admin_session, "Papers")
    _product(uow, admin_session, "A4 Ivory", papers.id)
    _product(uow, admin_session, "A3 Ivory", papers.id)

    DeleteCategoryUseCase(uow, admin_session).execute(papers.id)

    page = _page(uow, admin_session)
    assert {row.category_name for row in page.rows} == {DEFAULT_CATEGORY_NAME}
    assert page.total == 2


def test_an_empty_category_shows_nothing_and_is_still_a_category(uow, admin_session):
    empty = _category(uow, admin_session, "Packaging")

    assert _page(uow, admin_session, category_id=empty.id).total == 0
    assert [
        row.name
        for row in PageCategoriesUseCase(uow, admin_session).execute(PageQuery()).rows
    ] == ["Packaging"]


# ------------------------------------------------------------------ products


def test_creating_a_product_creates_exactly_one_item_under_it(uow, admin_session):
    _product(uow, admin_session, "A4 Ivory 80gsm", unit="sheets")

    row = _row_named(_page(uow, admin_session), "A4 Ivory 80gsm")
    assert len(row.skus) == 1
    assert row.sku is not None
    assert row.sku.name == "A4 Ivory 80gsm"
    assert row.sku.unit == "sheets"
    assert row.sku.current_stock == Decimal("0")


def test_a_product_with_no_category_lands_on_the_default_shelf(uow, admin_session):
    _product(uow, admin_session, "Gold Foil")

    assert _row_named(_page(uow, admin_session), "Gold Foil").category_name == (
        DEFAULT_CATEGORY_NAME
    )


def test_a_product_is_filed_where_it_was_asked_for(uow, admin_session):
    papers = _category(uow, admin_session, "Papers")
    _product(uow, admin_session, "A4 Ivory", papers.id)

    assert _row_named(_page(uow, admin_session), "A4 Ivory").category_name == "Papers"


def test_a_product_cannot_be_filed_on_a_shelf_that_is_not_there(uow, admin_session):
    with pytest.raises(NotFoundError):
        _product(uow, admin_session, "A4 Ivory", 404)


def test_two_products_cannot_share_a_name(uow, admin_session):
    _product(uow, admin_session, "A4 Ivory")

    with pytest.raises(DuplicateEntityError):
        _product(uow, admin_session, "A4 Ivory")


def test_a_second_item_makes_the_product_a_row_that_opens(uow, admin_session):
    product = _product(uow, admin_session, "Visiting Card")
    CreateInventoryItemUseCase(uow, admin_session).execute(
        CreateInventoryItemCommand(name="Visiting Card Gloss", product_id=product.id, unit="Piece")
    )

    row = _row_named(_page(uow, admin_session), "Visiting Card")
    assert row.has_variants
    assert row.sku is None
    assert [sku.name for sku in row.skus] == ["Visiting Card", "Visiting Card Gloss"]


def test_an_item_added_on_its_own_still_gets_a_product(uow, admin_session):
    """Every caller written before products existed keeps working."""
    item = CreateInventoryItemUseCase(uow, admin_session).execute(
        CreateInventoryItemCommand(name="Gold Foil", unit="rolls")
    )

    assert item.product_id is not None
    assert _row_named(_page(uow, admin_session), "Gold Foil").sku.id == item.id


def test_renaming_a_product_with_one_item_renames_the_item_too(uow, admin_session):
    product = _product(uow, admin_session, "A4 Ivory 80gsm")

    UpdateProductUseCase(uow, admin_session).execute(
        UpdateProductCommand(id=product.id, name="A4 Ivory 80")
    )

    row = _row_named(_page(uow, admin_session), "A4 Ivory 80")
    assert row.sku.name == "A4 Ivory 80"


def test_renaming_a_product_with_several_items_leaves_their_names_alone(uow, admin_session):
    product = _product(uow, admin_session, "Visiting Card")
    CreateInventoryItemUseCase(uow, admin_session).execute(
        CreateInventoryItemCommand(name="Visiting Card Gloss", product_id=product.id)
    )

    UpdateProductUseCase(uow, admin_session).execute(
        UpdateProductCommand(id=product.id, name="Business Card")
    )

    row = _row_named(_page(uow, admin_session), "Business Card")
    assert [sku.name for sku in row.skus] == ["Visiting Card", "Visiting Card Gloss"]


def test_renaming_the_only_item_renames_its_product_too(uow, admin_session):
    """The row on screen is both, so they cannot drift apart."""
    product = _product(uow, admin_session, "A4 Ivory 80gsm")
    row = _row_named(_page(uow, admin_session), "A4 Ivory 80gsm")

    UpdateInventoryItemUseCase(uow, admin_session).execute(
        UpdateInventoryItemCommand(id=row.sku.id, name="A4 Ivory 80", minimum_stock=Decimal("5"))
    )

    renamed = _row_named(_page(uow, admin_session), "A4 Ivory 80")
    assert renamed.product.id == product.id
    assert renamed.sku.minimum_stock == Decimal("5")


def test_moving_a_product_changes_only_where_it_is_listed(uow, admin_session):
    papers = _category(uow, admin_session, "Papers")
    inks = _category(uow, admin_session, "Inks")
    product = _product(uow, admin_session, "Black Ink", papers.id)

    before = _row_named(_page(uow, admin_session), "Black Ink").sku
    UpdateProductUseCase(uow, admin_session).execute(
        UpdateProductCommand(id=product.id, category_id=inks.id)
    )
    after = _row_named(_page(uow, admin_session), "Black Ink")

    assert after.category_name == "Inks"
    assert after.sku.id == before.id
    assert after.sku.current_stock == before.current_stock
    assert after.sku.unit == before.unit


def test_a_product_cannot_be_moved_to_a_shelf_that_is_not_there(uow, admin_session):
    product = _product(uow, admin_session, "Black Ink")

    with pytest.raises(NotFoundError):
        UpdateProductUseCase(uow, admin_session).execute(
            UpdateProductCommand(id=product.id, category_id=404)
        )


def test_deleting_a_product_takes_its_items_with_it(uow, admin_session):
    product = _product(uow, admin_session, "Visiting Card")
    CreateInventoryItemUseCase(uow, admin_session).execute(
        CreateInventoryItemCommand(name="Visiting Card Gloss", product_id=product.id)
    )

    DeleteProductUseCase(uow, admin_session).execute(product.id)

    assert _page(uow, admin_session).total == 0


def test_a_product_holding_something_that_has_traded_cannot_be_deleted(uow, admin_session):
    product = _product(uow, admin_session, "A4 Ivory")
    row = _row_named(_page(uow, admin_session), "A4 Ivory")
    CreatePurchaseUseCase(uow, admin_session).execute(
        CreatePurchaseCommand(
            purchase_no="PUR-1",
            items=[
                PurchaseItemCommand(
                    item_type=ItemType.INVENTORY_ITEM,
                    inventory_item_id=row.sku.id,
                    quantity=Decimal("10"),
                    unit_price=Decimal("5.00"),
                )
            ],
            payments=[],
        )
    )

    with pytest.raises(EntityInUseError):
        DeleteProductUseCase(uow, admin_session).execute(product.id)

    assert _page(uow, admin_session).total == 1


def test_deleting_the_last_item_takes_its_product_with_it(uow, admin_session):
    _product(uow, admin_session, "Gold Foil")
    row = _row_named(_page(uow, admin_session), "Gold Foil")

    DeleteInventoryItemUseCase(uow, admin_session).execute(row.sku.id)

    assert _page(uow, admin_session).total == 0


def test_deleting_one_of_several_items_leaves_the_product(uow, admin_session):
    product = _product(uow, admin_session, "Visiting Card")
    gloss = CreateInventoryItemUseCase(uow, admin_session).execute(
        CreateInventoryItemCommand(name="Visiting Card Gloss", product_id=product.id)
    )

    DeleteInventoryItemUseCase(uow, admin_session).execute(gloss.id)

    row = _row_named(_page(uow, admin_session), "Visiting Card")
    assert not row.has_variants
    assert row.sku.name == "Visiting Card"


# ----------------------------------------------------------- listing the page


def test_the_catalogue_is_grouped_by_category_so_headings_are_contiguous(uow, admin_session):
    inks = _category(uow, admin_session, "Inks")
    papers = _category(uow, admin_session, "Papers")
    _product(uow, admin_session, "A4 Ivory", papers.id)
    _product(uow, admin_session, "Black Ink", inks.id)
    _product(uow, admin_session, "A3 Ivory", papers.id)

    names = [row.category_name for row in _page(uow, admin_session).rows]
    assert names == ["Inks", "Papers", "Papers"]


def test_a_search_matches_a_product_by_name(uow, admin_session):
    _product(uow, admin_session, "A4 Ivory 250gsm")
    _product(uow, admin_session, "Black Ink")

    page = _page(uow, admin_session, search="ivory")
    assert [row.name for row in page.rows] == ["A4 Ivory 250gsm"]
    assert page.total == 1


def test_a_search_matches_a_product_through_its_items(uow, admin_session):
    product = _product(uow, admin_session, "Visiting Card")
    CreateInventoryItemUseCase(uow, admin_session).execute(
        CreateInventoryItemCommand(name="Pearl Finish", product_id=product.id)
    )

    page = _page(uow, admin_session, search="pearl")
    assert [row.name for row in page.rows] == ["Visiting Card"]


def test_a_product_matching_through_two_items_is_still_one_row(uow, admin_session):
    product = _product(uow, admin_session, "Ivory Card")
    CreateInventoryItemUseCase(uow, admin_session).execute(
        CreateInventoryItemCommand(name="Ivory Card Gloss", product_id=product.id)
    )

    page = _page(uow, admin_session, search="ivory")
    assert page.total == 1
    assert len(page.rows) == 1


def test_the_stock_filter_asks_about_the_items_under_a_product(uow, admin_session):
    _product(uow, admin_session, "A4 Ivory")
    stocked = _product(uow, admin_session, "Black Ink")
    row = _row_named(_page(uow, admin_session), "Black Ink")
    CreatePurchaseUseCase(uow, admin_session).execute(
        CreatePurchaseCommand(
            purchase_no="PUR-1",
            items=[
                PurchaseItemCommand(
                    item_type=ItemType.INVENTORY_ITEM,
                    inventory_item_id=row.sku.id,
                    quantity=Decimal("100"),
                    unit_price=Decimal("5.00"),
                )
            ],
            payments=[],
        )
    )

    out = _page(uow, admin_session, stock=StockFilter.OUT)
    stocked_page = _page(uow, admin_session, stock=StockFilter.IN)

    assert [row.name for row in out.rows] == ["A4 Ivory"]
    assert [row.name for row in stocked_page.rows] == ["Black Ink"]
    assert stocked.name == "Black Ink"


def test_a_page_reports_the_whole_catalogue_not_the_page(uow, admin_session):
    for number in range(5):
        _product(uow, admin_session, f"Item {number}")

    page = _page(uow, admin_session, page_size=2)

    assert len(page.rows) == 2
    assert page.total == 5
    assert page.page_count == 3


def test_the_second_page_carries_on_where_the_first_stopped(uow, admin_session):
    for number in range(5):
        _product(uow, admin_session, f"Item {number}")

    first = _page(uow, admin_session, page_size=2, page=1)
    second = _page(uow, admin_session, page_size=2, page=2)

    assert {row.name for row in first.rows}.isdisjoint({row.name for row in second.rows})


def test_one_shelf_can_be_asked_for_on_its_own(uow, admin_session):
    papers = _category(uow, admin_session, "Papers")
    _product(uow, admin_session, "A4 Ivory", papers.id)
    _product(uow, admin_session, "Black Ink")

    page = _page(uow, admin_session, category_id=papers.id)
    assert [row.name for row in page.rows] == ["A4 Ivory"]


def test_staff_cannot_change_the_catalogue(uow, staff_session):
    with pytest.raises(PermissionDeniedError):
        _category(uow, staff_session, "Papers")
    with pytest.raises(PermissionDeniedError):
        _product(uow, staff_session, "A4 Ivory")


# ------------------------------------------------- one row, one form, one save


def test_an_item_is_created_with_its_units_in_one_go(uow, admin_session):
    """The form sets both, so nothing can half-save."""
    item = CreateInventoryItemUseCase(uow, admin_session).execute(
        CreateInventoryItemCommand(
            name="A4 Ivory",
            unit="Piece",
            units=(SkuUnitCommand(name="Box", factor=Decimal("288")),),
        )
    )

    units = GetSkuUnitsUseCase(uow, admin_session).execute(item.id)
    assert [(unit.name, unit.factor) for unit in units] == [("Box", Decimal("288.0000"))]


def test_the_only_item_of_a_product_can_be_re_filed_from_its_own_form(uow, admin_session):
    """That row is the product as far as the screen is concerned, so the
    form that edits it can move it."""
    papers = _category(uow, admin_session, "Papers")
    _product(uow, admin_session, "A4 Ivory")
    row = _row_named(_page(uow, admin_session), "A4 Ivory")

    UpdateInventoryItemUseCase(uow, admin_session).execute(
        UpdateInventoryItemCommand(
            id=row.sku.id, name="A4 Ivory", minimum_stock=Decimal("5"), category_id=papers.id
        )
    )

    moved = _row_named(_page(uow, admin_session), "A4 Ivory")
    assert moved.category_name == "Papers"
    assert moved.sku.id == row.sku.id


def test_a_variant_s_form_cannot_move_the_product_it_sits_under(uow, admin_session):
    """A shelf belongs to the product, and a product with two variants has
    no one of them that speaks for it."""
    papers = _category(uow, admin_session, "Papers")
    product = _product(uow, admin_session, "Visiting Card")
    gloss = CreateInventoryItemUseCase(uow, admin_session).execute(
        CreateInventoryItemCommand(name="Visiting Card Gloss", product_id=product.id)
    )
    before = _row_named(_page(uow, admin_session), "Visiting Card").category_name

    UpdateInventoryItemUseCase(uow, admin_session).execute(
        UpdateInventoryItemCommand(
            id=gloss.id, name="Visiting Card Gloss", category_id=papers.id
        )
    )

    assert _row_named(_page(uow, admin_session), "Visiting Card").category_name == before


def test_leaving_the_shelf_alone_leaves_it_alone(uow, admin_session):
    papers = _category(uow, admin_session, "Papers")
    _product(uow, admin_session, "A4 Ivory", papers.id)
    row = _row_named(_page(uow, admin_session), "A4 Ivory")

    UpdateInventoryItemUseCase(uow, admin_session).execute(
        UpdateInventoryItemCommand(id=row.sku.id, name="A4 Ivory 80")
    )

    assert _row_named(_page(uow, admin_session), "A4 Ivory 80").category_name == "Papers"
