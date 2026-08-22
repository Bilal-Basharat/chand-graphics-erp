"""
What a catalogue row says about itself.

The interesting case is the product with several variants. It is one row
standing over several items, and the question each column has to answer
is whether it can honestly speak for all of them.
"""
from __future__ import annotations

from decimal import Decimal

from app.application.dto.queries import CatalogueRow
from app.domain.entities.inventory_item import InventoryItem
from app.domain.entities.product import Product
from app.presentation.views.catalogue_view import (
    _shared_unit,
    _skus_of,
    _status_word,
    _worst_stocked,
)
from app.presentation.widgets.catalogue_tree import CatalogueHeading


def _sku(name: str, *, stock: str = "0", minimum: str = "0", unit: str = "sheets"):
    return InventoryItem(
        id=abs(hash(name)) % 10_000,
        name=name,
        product_id=1,
        unit=unit,
        current_stock=Decimal(stock),
        minimum_stock=Decimal(minimum),
    )


def _row(*skus) -> CatalogueRow:
    return CatalogueRow(
        product=Product(id=1, name="Art Card", category_id=1),
        category_id=1,
        category_name="Papers",
        skus=tuple(skus),
    )


# ----------------------------------------------------------- what is behind


def test_a_heading_stands_for_no_items_of_its_own():
    assert _skus_of(CatalogueHeading(id=1, name="Papers")) == ()


def test_a_product_stands_for_every_item_under_it():
    matt, gloss = _sku("Matt"), _sku("Gloss")
    assert _skus_of(_row(matt, gloss)) == (matt, gloss)


def test_a_variant_stands_for_itself():
    matt = _sku("Matt")
    assert _skus_of(matt) == (matt,)


# ------------------------------------------------------------------- units


def test_variants_counted_the_same_way_give_the_row_that_unit():
    assert _shared_unit(_skus_of(_row(_sku("Matt"), _sku("Gloss")))) == "sheets"


def test_variants_counted_differently_leave_the_row_without_one():
    row = _row(_sku("Matt"), _sku("Boxed", unit="boxes"))
    assert _shared_unit(_skus_of(row)) is None


def test_a_single_item_gives_its_own_unit():
    assert _shared_unit(_skus_of(_row(_sku("Matt")))) == "sheets"


# ------------------------------------------------------------------ status


def test_a_row_reports_the_item_in_the_worst_state():
    """What a row says about itself is whatever most needs doing."""
    healthy = _sku("Matt", stock="500", minimum="100")
    low = _sku("Gloss", stock="90", minimum="100")
    out = _sku("Pearl", stock="0", minimum="10")

    assert _worst_stocked((healthy, low, out)) is out
    assert _worst_stocked((healthy, low)) is low
    assert _worst_stocked((healthy,)) is healthy


def test_out_of_stock_outranks_low_stock():
    out = _sku("Pearl", stock="0", minimum="0")
    low = _sku("Gloss", stock="5", minimum="10")

    assert _worst_stocked((low, out)) is out


def test_nothing_behind_a_row_is_nothing_to_report():
    assert _worst_stocked(()) is None


# ------------------------------------------------------------ what it says


def test_a_healthy_row_says_nothing():
    """Blank means nothing to do. Every row is healthy on an ordinary day,
    and a column repeating "In stock" is a wall to read past."""
    assert _status_word((_sku("Matt", stock="500", minimum="100"),)) == ""


def test_a_row_that_needs_reordering_says_so_in_words():
    assert _status_word((_sku("Gloss", stock="90", minimum="100"),)) == "Low stock"
    assert _status_word((_sku("Pearl", stock="0", minimum="10"),)) == "Out of stock"


def test_one_variant_needing_attention_speaks_for_the_whole_product():
    healthy = _sku("Matt", stock="500", minimum="100")
    low = _sku("Gloss", stock="90", minimum="100")

    assert _status_word(_skus_of(_row(healthy, low))) == "Low stock"


def test_a_heading_says_nothing_about_stock():
    assert _status_word(_skus_of(CatalogueHeading(id=1, name="Papers"))) == ""
