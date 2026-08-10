"""
The one place that knows what kinds of item this installation trades in.

The app sells and buys one kind today — inventory. It still asks "which
kind?" everywhere, because a *special item module* (a catalogue with its
own table, screen and rules, as wedding cards were) is a member added to
`ItemType` and an entry added here. Every picker, dropdown, document line
and stock ledger reads the registry rather than naming a catalogue of its
own, so registering the kind is what puts it on all of them.

Four things vary per kind and nothing else does: what it is called, how
one of its records names itself, which id a document line carries it in,
and how its catalogue is fetched.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.container import AppContainer
from app.domain.enums.item_type import ItemType

CATALOGUE_LIMIT = 500
"""How much of a catalogue a picker offers. Master data is small by
nature for a single shop; search narrows rather than paginates."""


@dataclass(frozen=True, slots=True)
class ItemKind:
    label: str
    """How this kind is offered in a picker — "Inventory"."""

    name_of: Callable[[Any], str]
    """How one catalogue record names itself in a list or a line."""

    id_of: Callable[[Any], int | None]
    """Which id a document line or stock movement carries this kind in."""

    catalogue: Callable[[AppContainer, int], list]
    """Every record of this kind, up to a limit."""


ITEM_KINDS: dict[ItemType, ItemKind] = {
    ItemType.INVENTORY_ITEM: ItemKind(
        label="Inventory",
        name_of=lambda item: item.name,
        id_of=lambda line: line.inventory_item_id,
        catalogue=lambda container, limit: (
            container.list_inventory_items_use_case().execute(limit)
        ),
    ),
}


def load_catalogues(
    container: AppContainer, limit: int = CATALOGUE_LIMIT
) -> dict[ItemType, list]:
    """Every kind's catalogue, in one trip. Runs off the UI thread."""
    return {
        item_type: kind.catalogue(container, limit)
        for item_type, kind in ITEM_KINDS.items()
    }


def item_name(item_type: ItemType, record: Any) -> str:
    """How one catalogue record of `item_type` names itself."""
    return ITEM_KINDS[ItemType(item_type)].name_of(record)


def catalogue_key(line: Any) -> tuple[ItemType, int | None]:
    """Which catalogue record a document line or stock movement points at.

    The pair, not the id alone: two kinds can each hold a record numbered
    3, and a lookup keyed on the number would name the wrong one.
    """
    item_type = ItemType(line.item_type)
    return item_type, ITEM_KINDS[item_type].id_of(line)
