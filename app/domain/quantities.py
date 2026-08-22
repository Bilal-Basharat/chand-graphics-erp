"""
How much of something there is, everywhere in this application.

Stock, and every quantity that moves it, is a `Decimal`. Not a float:
a shop that sells a quarter of a sheet three times has sold three
quarters, and 0.25 + 0.25 + 0.25 in binary floating point is not 0.75.
The difference shows up as a count that will not come back to zero, and
there is no way to explain that to whoever is holding the stock.

Four decimal places, because that is what the columns hold and what a
conversion needs: a unit worth 1/3 of a base unit is not a business
anybody runs, but 0.125 of one is.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

QUANTITY_PLACES = Decimal("0.0001")
"""The step every stored quantity sits on. Matches `Numeric(14, 4)`."""


def to_quantity(value: Decimal | int | str) -> Decimal:
    """`value` as a quantity — the one way one is made.

    Floats are refused rather than converted. A float that arrived here
    was read from somewhere that should have been Decimal all along, and
    quietly rounding it would hide that rather than fix it.
    """
    if isinstance(value, float):
        raise TypeError("quantities are Decimal, not float")
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(QUANTITY_PLACES, rounding=ROUND_HALF_UP)
