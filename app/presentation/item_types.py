"""
The one place that knows what kinds of item this installation trades in.

The app sells and buys one kind today — inventory. It still asks "which
kind?" everywhere, because a *special item module* (a catalogue with its
own table, screen and rules, as wedding cards were) is a member added to
`ItemType` and an entry added here. Every picker, dropdown, document line
and stock ledger reads the registry rather than naming a catalogue of its
own, so registering the kind is what puts it on all of them.

Five things vary per kind and nothing else does: what it is called, how
one of its records names itself, which id a document line carries it in,
how a search of it is run, and how names are fetched for ids already in
hand.

Both of those last two are here because neither a picker nor a document
line may load a catalogue. A shop's catalogue outgrows any ceiling put on
it, and the ceiling did not announce itself: a picker simply could not
find the item, and a line pointing past it read as a dash.
"""
from __future__ import annotations

from collections.abc import Callable, Collection
from dataclasses import dataclass
from typing import Any

from app.application.dto.queries import InventoryPageQuery
from app.container import AppContainer
from app.domain.enums.item_type import ItemType

PICKER_MATCHES = 50
"""How many matches a picker offers as it is typed into. A shortlist to
choose from, not a page to read: past this, the answer is more typing."""


@dataclass(frozen=True, slots=True)
class ItemKind:
    label: str
    """How this kind is offered in a picker — "Inventory"."""

    name_of: Callable[[Any], str]
    """How one catalogue record of this kind names itself in a list or a
    line."""

    id_of: Callable[[Any], int | None]
    """Which id a document line or stock movement carries this kind in."""

    search: Callable[[AppContainer, str, int], list]
    """The records of this kind matching what has been typed, at most that
    many. An empty term is the first page of the catalogue — what a picker
    offers before anything is typed."""

    names_by_id: Callable[[AppContainer, Collection[int]], dict[int, str]]
    """Names for ids already in hand, for naming the lines on a page of
    documents without loading anything to look them up in."""


ITEM_KINDS: dict[ItemType, ItemKind] = {
    ItemType.INVENTORY_ITEM: ItemKind(
        label="Inventory",
        name_of=lambda item: item.name,
        id_of=lambda line: line.inventory_item_id,
        search=lambda container, term, limit: (
            container.page_inventory_items_use_case()
            .execute(InventoryPageQuery(search=term, page_size=limit))
            .rows
        ),
        names_by_id=lambda container, ids: (
            container.inventory_item_names_use_case().execute(ids)
        ),
    ),
}


def search_catalogues(
    container: AppContainer, term: str, limit: int = PICKER_MATCHES
) -> dict[ItemType, list]:
    """Every kind's matches for a term, in one trip. Runs off the UI thread."""
    return {
        item_type: kind.search(container, term, limit)
        for item_type, kind in ITEM_KINDS.items()
    }


def item_names(
    container: AppContainer, item_type: ItemType, item_ids: Collection[int]
) -> dict[int, str]:
    """Names for a set of ids of one kind."""
    if not item_ids:
        return {}
    return ITEM_KINDS[ItemType(item_type)].names_by_id(container, item_ids)


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
