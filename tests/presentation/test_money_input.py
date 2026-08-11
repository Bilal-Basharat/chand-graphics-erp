from __future__ import annotations

from decimal import Decimal

import pytest

from app.presentation.widgets.document_lines import parse_balance

# `parse_balance` backs both ways of entering a party's opening balance —
# the dialog and the quick-add row — so its three rules are pinned here
# rather than being rediscovered from whichever screen is being read.


@pytest.mark.parametrize("text", ["", "   ", "\t"])
def test_blank_reads_as_zero(text):
    """A balance nobody typed is nothing owed, not a refusal — the
    quick-add row would otherwise demand a 0 on every party."""
    assert parse_balance(text) == Decimal("0.00")


def test_a_negative_is_kept_rather_than_clamped():
    """Unlike `parse_amount_or_zero`: on an account it means the party
    paid in advance."""
    assert parse_balance("-750") == Decimal("-750.00")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("2500.50", "2500.50"),
        ("2500", "2500.00"),
        ("  1200.75  ", "1200.75"),
        ("2500.567", "2500.57"),
    ],
)
def test_a_figure_comes_back_at_two_decimals(text, expected):
    """Rounded here rather than by the database driver, so the form shows
    what was actually stored."""
    assert parse_balance(text) == Decimal(expected)


@pytest.mark.parametrize("text", ["twelve", "1,200", "12.5.3", "-", "$500"])
def test_anything_that_is_not_a_number_is_refused(text):
    """None rather than zero: silently banking a typo as 0 is how an
    opening balance goes missing."""
    assert parse_balance(text) is None
