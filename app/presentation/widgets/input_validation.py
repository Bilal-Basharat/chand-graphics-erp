"""
The fields that police what can be typed into them, and the parsing that
reads back what was.

Two kinds of value in this app cannot be left to a plain text box. A money
figure has to be a number, because everything downstream of it is
arithmetic. A phone number has to be dialable, because a number nobody
can ring reads as a way to reach a party and isn't one.

Both are handled the same way and so live together: a validator that
turns away the keystroke rather than accepting the text and explaining on
submit, a `QLineEdit` that wears it, and a parse function that says what
the finished text means. The validators are separate from the fields
because a validator can be exercised without a running application and a
widget cannot.

The two halves of each rule have to agree — a field that accepts what its
parser then rejects is a form nobody can submit — which is the reason
they are written next to each other rather than beside the screens that
use them.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import QLineEdit, QWidget

# ---------------------------------------------------------------- money

ZERO = Decimal("0.00")

# Digits, then at most one point and at most two places after it. The
# digit cap is generous enough for any figure this shop will record and
# tight enough that a stuck key cannot grow the text forever.
_UNSIGNED = r"\d{0,12}(\.\d{0,2})?"
_SIGNED = rf"-?{_UNSIGNED}"


def money_validator(
    *, signed: bool = False, parent: QWidget | None = None
) -> QRegularExpressionValidator:
    """What a money field lets through, keystroke by keystroke."""
    return QRegularExpressionValidator(QRegularExpression(_SIGNED if signed else _UNSIGNED), parent)


class MoneyInput(QLineEdit):
    """A text field that will only ever hold a money figure.

    Rejects at the keystroke: letters, a second point, a third decimal
    place, and — unless `signed` — a minus sign. A partly typed figure
    ("12.", "-") is still allowed through, since refusing it would make
    the field impossible to type into; those read as not-a-number until
    the caller parses them.

    On leaving the field an entered figure is squared up to two decimals,
    so "250" reads back as "250.00" — the same shape the totals beside it
    are printed in.
    """

    def __init__(
        self,
        amount: Decimal | None = None,
        *,
        signed: bool = False,
        placeholder: str = "0.00",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setValidator(money_validator(signed=signed, parent=self))
        self.setPlaceholderText(placeholder)
        self.set_amount(amount)
        self.editingFinished.connect(self._normalise)

    def set_amount(self, amount: Decimal | None) -> None:
        """Show a figure the app already holds, or empty the field."""
        self.setText("" if amount is None else f"{amount:.2f}")

    def _normalise(self) -> None:
        amount = parse_amount(self.text())
        if amount is not None:
            self.set_amount(amount)


def parse_amount(text: str) -> Decimal | None:
    """A money figure typed by a user, or None if it isn't one."""
    try:
        return Decimal(text.strip())
    except (InvalidOperation, ValueError):
        return None


def parse_amount_or_zero(text: str) -> Decimal:
    value = parse_amount(text)
    return value if value is not None and value >= ZERO else ZERO


def parse_balance(text: str) -> Decimal | None:
    """A money figure that may be left blank, and may be negative.

    Blank reads as zero — a balance nobody typed is nothing owed. A
    negative is kept rather than clamped, unlike `parse_amount_or_zero`:
    on a party's account it means they are in credit. None means the text
    was not a number at all, which is the caller's to report.
    """
    if not text.strip():
        return ZERO
    value = parse_amount(text)
    return None if value is None else value.quantize(ZERO)


# ---------------------------------------------------------------- phone

_MIN_PHONE_DIGITS = 7
"""A local landline with no area code — the shortest thing anyone here
would write down as a phone number."""

_MAX_PHONE_DIGITS = 15
"""The most digits an international number can have (E.164)."""

NOT_A_PHONE = (
    f"Enter a phone number of {_MIN_PHONE_DIGITS} to {_MAX_PHONE_DIGITS} digits, "
    "or leave it blank."
)
"""Said the same way on every screen that asks for one."""

# A plus only at the front, then digits and the separators a number gets
# written with. The length cap is on the text rather than the digits so a
# heavily spaced number still fits; `parse_phone` counts the digits.
_PHONE = r"\+?[\d ()-]{0,23}"


def phone_validator(parent: QWidget | None = None) -> QRegularExpressionValidator:
    """What a phone field lets through, keystroke by keystroke."""
    return QRegularExpressionValidator(QRegularExpression(_PHONE), parent)


class PhoneInput(QLineEdit):
    """A text field that will only ever hold something dialable.

    Numbers reach this shop's books in every shape people write them —
    0300-1234567, 042 3576 1234, +92 300 1234567 — and all of them are
    the same number to whoever rings it. So this policies the alphabet
    rather than the format: digits, the separators people actually type,
    and a leading country-code plus. Refusing a real number for being
    punctuated the "wrong" way is how a phone field ends up worked around
    instead of used.

    Whether there are enough digits is `parse_phone`'s to answer, since a
    number is short only until it is finished being typed.
    """

    def __init__(
        self,
        *,
        placeholder: str = "e.g. 0300-1234567",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setValidator(phone_validator(self))
        self.setPlaceholderText(placeholder)
        self.editingFinished.connect(self._normalise)

    def _normalise(self) -> None:
        number = parse_phone(self.text())
        if number:
            self.setText(number)


def parse_phone(text: str) -> str | None:
    """A phone number as it will be stored.

    Returns "" when nothing was typed — a party with no phone on file is
    ordinary, not an error — and None when what was typed has too few or
    too many digits to ring, which is the caller's to report.
    """
    number = " ".join(text.split())
    if not number:
        return ""
    digits = sum(character.isdigit() for character in number)
    return number if _MIN_PHONE_DIGITS <= digits <= _MAX_PHONE_DIGITS else None
