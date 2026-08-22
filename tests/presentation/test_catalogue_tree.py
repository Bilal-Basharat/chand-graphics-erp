"""
The catalogue tree: what each depth shows, and what a row hands back.

The point of the widget is that a product with one item does not look
like a tree at all, so most of what is checked here is what is *not*
there: no expander, no second row, no SKU vocabulary.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from PySide6.QtCore import QMimeData, QModelIndex, Qt

from app.application.dto.queries import CatalogueRow
from app.domain.entities.inventory_item import InventoryItem
from app.domain.entities.product import Product
from app.presentation.widgets.catalogue_tree import (
    PRODUCT_MIME,
    CatalogueEdit,
    CatalogueTree,
    NodeKind,
    variant_columns,
)
from app.presentation.widgets.table_model import Column


def _columns():
    return [
        Column("NAME", lambda row: row.name, editable="name"),
        Column("UNIT", lambda row: getattr(row.sku, "unit", "") if hasattr(row, "sku") else ""),
        Column(
            "STOCK",
            lambda row: row.sku.current_stock if getattr(row, "sku", None) else "",
            align="right",
        ),
        Column("MINIMUM", lambda row: "", align="right", editable="minimum_stock"),
    ]


def _variant_columns(columns):
    return variant_columns(
        columns,
        {
            "NAME": ("", lambda sku: sku.name, "name"),
            "UNIT": ("", lambda sku: sku.unit or "", None),
            "STOCK": ("", lambda sku: sku.current_stock, None),
            "MINIMUM": ("", lambda sku: sku.minimum_stock, "minimum_stock"),
        },
    )


def _sku(item_id: int, name: str, *, stock="0", unit="Piece", product_id: int = 1) -> InventoryItem:
    return InventoryItem(
        id=item_id,
        name=name,
        product_id=product_id,
        unit=unit,
        current_stock=Decimal(stock),
    )


def _row(product_id: int, name: str, category: str, skus, category_id: int = 1) -> CatalogueRow:
    return CatalogueRow(
        product=Product(id=product_id, name=name, category_id=category_id),
        category_id=category_id,
        category_name=category,
        skus=tuple(skus),
    )


@pytest.fixture(scope="module")
def tree(qt_app) -> CatalogueTree:
    """One tree for the whole file, refilled by each test.

    Built once, like the application it lives under: the widget installs
    an event filter on its own viewport, and fourteen of them left to be
    torn down at exit have Qt calling back into wrappers Python has
    already emptied. Every test sets its own rows, so there is no state
    to carry between them.
    """
    columns = _columns()
    return CatalogueTree(columns, _variant_columns(columns))


def _headings(tree: CatalogueTree) -> list[str]:
    model = tree.model()
    return [
        model.index(row, 0).data(Qt.ItemDataRole.DisplayRole)
        for row in range(model.rowCount())
    ]


def _products_under(tree: CatalogueTree, heading: int) -> list[str]:
    model = tree.model()
    parent = model.index(heading, 0)
    return [
        model.index(row, 0, parent).data(Qt.ItemDataRole.DisplayRole)
        for row in range(model.rowCount(parent))
    ]


def test_a_product_with_one_item_is_a_row_and_not_a_tree(tree):
    tree.set_rows([_row(1, "A4 Ivory 80gsm", "Papers", [_sku(10, "A4 Ivory 80gsm")])])

    model = tree.model()
    product = model.index(0, 0, model.index(0, 0))
    assert model.rowCount(product) == 0
    assert product.data(Qt.ItemDataRole.DisplayRole) == "A4 Ivory 80gsm"


def test_a_product_with_several_opens_to_show_them(tree):
    tree.set_rows(
        [
            _row(
                1,
                "Visiting Card",
                "Papers",
                [_sku(10, "300gsm Matt"), _sku(11, "300gsm Gloss")],
            )
        ]
    )

    model = tree.model()
    product = model.index(0, 0, model.index(0, 0))
    assert model.rowCount(product) == 2
    assert [
        model.index(row, 0, product).data(Qt.ItemDataRole.DisplayRole) for row in range(2)
    ] == ["300gsm Matt", "300gsm Gloss"]


def test_categories_become_headings_over_the_products_on_them(tree):
    tree.set_rows(
        [
            _row(1, "A4 Ivory", "Papers", [_sku(10, "A4 Ivory")]),
            _row(2, "A3 Ivory", "Papers", [_sku(11, "A3 Ivory")]),
            _row(3, "Black Ink", "Inks", [_sku(12, "Black Ink")], category_id=2),
        ]
    )

    assert _headings(tree) == ["Papers", "Inks"]
    assert _products_under(tree, 0) == ["A4 Ivory", "A3 Ivory"]
    assert _products_under(tree, 1) == ["Black Ink"]


def test_the_count_is_of_products_not_of_headings(tree):
    tree.set_rows(
        [
            _row(1, "A4 Ivory", "Papers", [_sku(10, "A4 Ivory")]),
            _row(2, "Black Ink", "Inks", [_sku(11, "Black Ink")], category_id=2),
        ]
    )
    assert tree.row_count() == 2


def test_every_depth_is_a_record_something_can_act_on(tree):
    """Including the heading: a shelf somebody mistyped can be renamed."""
    tree.set_rows(
        [_row(1, "Visiting Card", "Papers", [_sku(10, "Matt"), _sku(11, "Gloss")])]
    )
    model = tree.model()

    heading = model.index(0, 0)
    product = model.index(0, 0, heading)
    variant = model.index(0, 0, product)

    assert tree.acts_on(heading)
    assert tree.acts_on(product)
    assert tree.acts_on(variant)


def test_a_heading_hands_back_the_category_it_stands_for(tree):
    tree.set_rows([_row(1, "A4 Ivory", "Papers", [_sku(10, "A4 Ivory")], category_id=7)])
    model = tree.model()

    heading = tree.row_at(tree.row_key(model.index(0, 0)))

    assert (heading.id, heading.name) == (7, "Papers")


def test_a_row_action_finds_the_record_it_was_pressed_on(tree):
    tree.set_rows(
        [_row(1, "Visiting Card", "Papers", [_sku(10, "Matt"), _sku(11, "Gloss")])]
    )
    model = tree.model()
    product = model.index(0, 0, model.index(0, 0))
    variant = model.index(1, 0, product)

    assert tree.row_at(tree.row_key(product)).name == "Visiting Card"
    assert tree.row_at(tree.row_key(variant)).name == "Gloss"


def test_typing_a_name_into_a_product_row_reports_the_product(tree):
    tree.set_rows([_row(7, "A4 Ivory", "Papers", [_sku(10, "A4 Ivory")])])
    edits: list[CatalogueEdit] = []
    tree.editSubmitted.connect(edits.append)

    model = tree.model()
    product = model.index(0, 0, model.index(0, 0))
    model.setData(product, "A4 Ivory 80", Qt.ItemDataRole.EditRole)

    assert edits == [
        CatalogueEdit(field="name", value="A4 Ivory 80", product_id=7, sku_id=10)
    ]


def test_stock_cannot_be_typed_over(tree):
    tree.set_rows([_row(1, "A4 Ivory", "Papers", [_sku(10, "A4 Ivory", stock="500")])])
    model = tree.model()
    product = model.index(0, 2, model.index(0, 0))

    assert not model.flags(product) & Qt.ItemFlag.ItemIsEditable


def test_a_minimum_cannot_be_typed_into_a_product_with_variants(tree):
    """It would have no one item to mean — which is why the row opens."""
    tree.set_rows(
        [_row(1, "Visiting Card", "Papers", [_sku(10, "Matt"), _sku(11, "Gloss")])]
    )
    model = tree.model()
    product = model.index(0, 3, model.index(0, 0))
    variant = model.index(0, 3, model.index(0, 0, model.index(0, 0)))

    assert not model.flags(product) & Qt.ItemFlag.ItemIsEditable
    assert model.flags(variant) & Qt.ItemFlag.ItemIsEditable


def test_dropping_a_product_on_a_heading_asks_for_it_to_be_re_filed(tree):
    tree.set_rows(
        [
            _row(1, "A4 Ivory", "Papers", [_sku(10, "A4 Ivory")], category_id=1),
            _row(2, "Black Ink", "Inks", [_sku(11, "Black Ink")], category_id=2),
        ]
    )
    moves: list[tuple[int, int]] = []
    tree.productMoved.connect(lambda product_id, category_id: moves.append((product_id, category_id)))

    payload = QMimeData()
    payload.setData(PRODUCT_MIME, b"1")
    model = tree.model()
    inks = model.index(1, 0)

    assert model.canDropMimeData(payload, Qt.DropAction.MoveAction, -1, -1, inks)
    model.dropMimeData(payload, Qt.DropAction.MoveAction, -1, -1, inks)

    assert moves == [(1, 2)]


def test_a_drop_outside_the_tree_moves_nothing(tree):
    tree.set_rows([_row(1, "A4 Ivory", "Papers", [_sku(10, "A4 Ivory")])])
    payload = QMimeData()
    payload.setData(PRODUCT_MIME, b"1")

    assert not tree.model().canDropMimeData(
        payload, Qt.DropAction.MoveAction, -1, -1, QModelIndex()
    )


def test_an_empty_catalogue_shows_its_placeholder(tree):
    tree.set_rows([])
    assert tree.row_count() == 0
    assert tree.model().rowCount() == 0


def test_a_product_row_knows_which_kind_of_node_it_is(tree):
    tree.set_rows([_row(1, "A4 Ivory", "Papers", [_sku(10, "A4 Ivory")])])
    model = tree.model()

    assert model.node_at(model.index(0, 0)).kind is NodeKind.CATEGORY
    assert model.node_at(model.index(0, 0, model.index(0, 0))).kind is NodeKind.PRODUCT
