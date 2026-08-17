from enum import StrEnum


class PaymentFilter(StrEnum):
    """How far a document has been paid.

    Named after what `Sale` and `Purchase` already compute about
    themselves — `paid_amount` against `grand_total` — so a list narrowed
    to "part paid" and a document that says it is part paid cannot
    disagree.

    All four states are here on purpose. A choice a screen offers that the
    query cannot express does not fail: it stays in the dropdown and
    quietly hands back everything.
    """

    NOT_FULLY_PAID = "not_fully_paid"
    """Anything still owed on it — what a collection screen opens on."""

    NOTHING_PAID = "nothing_paid"
    PART_PAID = "part_paid"
    FULLY_PAID = "fully_paid"
