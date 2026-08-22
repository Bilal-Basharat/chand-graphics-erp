"""
The two number fields, and the digits they are written in.

Both matter more than they look. This shop's machine runs under `ur_PK`,
where Qt writes 3000 as ٣٠٠٠ while every figure the rest of the
application prints is 3,000 — one number in two alphabets on the same
form. And a quantity held to four places has no business showing a
shopkeeper "3000.0000" for a minimum they typed as three thousand.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.presentation.widgets.modern_spinbox import ModernDecimalSpinBox, ModernSpinBox


@pytest.fixture(scope="module")
def whole(qt_app) -> ModernSpinBox:
    field = ModernSpinBox()
    field.setRange(0, 1_000_000)
    return field


@pytest.fixture(scope="module")
def fractional(qt_app) -> ModernDecimalSpinBox:
    field = ModernDecimalSpinBox()
    field.setRange(0, 1_000_000)
    return field


def _shown(field) -> str:
    return field._spin.text()


def test_a_whole_number_is_written_the_way_the_rest_of_the_app_writes_one(whole):
    whole.setValue(3000)
    assert _shown(whole) == "3,000"


def test_a_quantity_is_written_the_same_way(fractional):
    fractional.setValue(Decimal("2880"))
    assert _shown(fractional) == "2,880"


@pytest.mark.parametrize(
    ("typed", "shown"),
    [("3000", "3,000"), ("0.5", "0.5"), ("0.125", "0.125"), ("0", "0")],
)
def test_a_quantity_shows_only_the_decimals_it_is_using(fractional, typed, shown):
    fractional.setValue(Decimal(typed))
    assert _shown(fractional) == shown


@pytest.mark.parametrize("typed", ["3000", "0.5", "0.125", "0.0625"])
def test_what_goes_in_comes_back_out_as_the_same_number(fractional, typed):
    fractional.setValue(Decimal(typed))
    assert fractional.value() == Decimal(typed)


def test_a_quantity_comes_back_as_a_decimal_and_not_a_float(fractional):
    """Everything counting stock works in Decimal, and a control handing
    back a float here would put binary rounding into the one place this
    application refuses to have it."""
    fractional.setValue(Decimal("0.1"))
    assert isinstance(fractional.value(), Decimal)
    assert fractional.value() == Decimal("0.1")


def test_a_cap_is_read_back_in_the_same_type(fractional):
    fractional.setRange(0, Decimal("2880"))
    assert fractional.maximum() == Decimal("2880")
    fractional.setRange(0, 1_000_000)


def test_each_control_reports_what_was_typed_into_it(whole, fractional):
    seen: list = []
    whole.valueChanged.connect(seen.append)
    fractional.valueChanged.connect(seen.append)

    whole.setValue(7)
    fractional.setValue(Decimal("0.25"))

    assert seen == [7, Decimal("0.25")]
