from enum import StrEnum


class ItemType(StrEnum):
    """Which catalogue a document line, or a stock movement, points at.

    One member today, and still a choice rather than an assumption. A
    *special item module* — a catalogue with its own table, screen and
    rules, as wedding cards were for a printing press — arrives as a new
    member here plus its own nullable foreign key beside
    `inventory_item_id` on the three tables that carry this enum. Every
    picker and dropdown in the app is built from the members, so the new
    kind is offered as soon as it is registered.

    See "Adding a special item module" in the README for the full list of
    what one touches.
    """

    INVENTORY_ITEM = "INVENTORY_ITEM"
