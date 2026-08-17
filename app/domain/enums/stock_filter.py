from enum import StrEnum


class StockFilter(StrEnum):
    """How a catalogue can be narrowed by what is on the shelf.

    Domain vocabulary rather than a screen's: each member is one of the
    rules `InventoryItem` already states about itself, and the query, the
    dropdown and the status pill all have to mean the same thing by it.
    """

    LOW = "low"
    """At or below its minimum — `InventoryItem.is_low_stock`. What needs
    reordering, which is the question that brings people to the screen."""

    OUT = "out"
    """None left at all. A subset of LOW, and worth asking separately:
    it is the only one that stops a sale."""

    IN = "in"
    """Comfortably above its minimum: nothing to do about it."""
