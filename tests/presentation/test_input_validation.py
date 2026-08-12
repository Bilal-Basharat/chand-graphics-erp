from __future__ import annotations

from decimal import Decimal

import pytest
from PySide6.QtGui import QValidator

from app.presentation.widgets.input_validation import (
    money_validator,
    parse_balance,
    parse_phone,
    phone_validator,
)


def _accepts(validator, text: str) -> bool:
    """Whether a field wearing this validator would hold the text at all."""
    return validator.validate(text, 0)[0] is not QValidator.State.Invalid


# ------------------------------------------------------------------ money

# `parse_balance` backs both ways of entering a party's opening balance —
# the dialog and the quick-add row — so its three rules are pinned here
# rather than being rediscovered from whichever screen is being read.


@pytest.mark.parametrize("text", ["", "   ", "\t"])
def test_a_blank_balance_reads_as_zero(text):
    """A balance nobody typed is nothing owed, not a refusal — the
    quick-add row would otherwise demand a 0 on every party."""
    assert parse_balance(text) == Decimal("0.00")


def test_a_negative_balance_is_kept_rather_than_clamped():
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
def test_a_balance_that_is_not_a_number_is_refused(text):
    """None rather than zero: silently banking a typo as 0 is how an
    opening balance goes missing."""
    assert parse_balance(text) is None


@pytest.mark.parametrize("text", ["", "0", "250", "250.", "250.5", "250.50", "1200000"])
def test_a_money_figure_is_typeable(text):
    """Including the half-typed states passed through on the way to a
    whole one — refusing "250." makes the field impossible to type in."""
    assert _accepts(money_validator(), text)


@pytest.mark.parametrize("text", ["twelve", "12a", "1,200", "$500", "12.5.3", "250.505", "1 000"])
def test_what_is_not_a_money_figure_never_reaches_the_field(text):
    """Turned away at the keystroke rather than accepted and explained on
    submit — including the third decimal place, which would otherwise be
    silently rounded away after the fact."""
    assert not _accepts(money_validator(), text)


def test_a_minus_is_refused_unless_the_money_field_is_signed():
    """Only an opening balance may go negative; a price, a discount or a
    payment cannot."""
    assert not _accepts(money_validator(), "-750")
    assert _accepts(money_validator(signed=True), "-750")


# ------------------------------------------------------------------ phone

# The phone rule is deliberately loose about format and strict about
# substance, and both halves are easy to tighten by accident — so the
# shapes a real number arrives in are pinned here.


@pytest.mark.parametrize(
    "text",
    ["", "03001234567", "0300-1234567", "042 3576 1234", "+92 300 1234567", "(042) 3576-1234"],
)
def test_a_number_is_typeable_however_it_is_punctuated(text):
    """Spaces, dashes, brackets and a country code are all how people
    actually write a number down — refusing any of them is how a phone
    field ends up worked around."""
    assert _accepts(phone_validator(), text)


@pytest.mark.parametrize("text", ["call me", "0300_1234567", "0300.1234567", "92+3001234567"])
def test_what_is_not_a_number_never_reaches_the_field(text):
    """Including a plus anywhere but the front, where it means nothing."""
    assert not _accepts(phone_validator(), text)


def test_a_blank_phone_is_not_a_refusal():
    """A party with no phone on file is ordinary. "" rather than None, so
    the caller can tell it apart from a number it has to report."""
    assert parse_phone("") == ""
    assert parse_phone("   ") == ""


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("0300-1234567", "0300-1234567"),
        ("  042 3576 1234  ", "042 3576 1234"),
        ("+92   300   1234567", "+92 300 1234567"),
    ],
)
def test_a_number_is_stored_as_written_less_stray_spacing(text, expected):
    """The punctuation is the owner's; the whitespace around it is noise
    that would otherwise make the same number look like two."""
    assert parse_phone(text) == expected


@pytest.mark.parametrize("text", ["123456", "()-", "1234567890123456"])
def test_too_few_or_too_many_digits_is_refused(text):
    """None rather than storing it: a number nobody can ring is worse
    than a blank, because it reads as a way to reach the party."""
    assert parse_phone(text) is None
