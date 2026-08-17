"""
A sale or a purchase written out in full, wherever it is opened from.

`builders` chooses what goes on a card. This is the step before: the two
lookups a document needs before it can be written out at all — what its
lines point at, and what its payments were made with — and the two calls
that put them together.

It exists because the same two cards are opened from several screens, and
each of them was otherwise a place to get the pairing subtly wrong: a
sale stamps its payments `received_at` and a purchase `paid_at`, so the
same document read two ways is a real possibility and a confusing one.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from app.application.dto.queries import PageQuery
from app.container import AppContainer
from app.domain.enums.item_type import ItemType
from app.presentation.formatting import payment_method_name
from app.presentation.item_types import ITEM_KINDS, item_names
from app.presentation.records.builders import purchase_card, sale_card
from app.presentation.records.card import RecordCard
from app.presentation.viewmodels.document_items import ItemCatalogue, payment_lines

_METHOD_LIMIT = 200
"""Payment methods are a short hand-kept list, as every screen assumes.
A ceiling, not a page size — every one of them belongs in the lookup."""


@dataclass(frozen=True, slots=True)
class DocumentNames:
    """Names for everything a written-out document refers to."""

    catalogue: ItemCatalogue
    method_name: Callable[[int | None], str]

    @classmethod
    def load(cls, container: AppContainer, documents) -> DocumentNames:
        """Fetch both lookups in one trip. Runs off the UI thread.

        For the documents given, by the ids their lines carry — never by
        loading a catalogue. A catalogue is a ceiling, and a card for a
        document above it printed a dash where the item's name goes.

        `ITEM_KINDS` is the one place that knows which item kinds exist, so
        a special item module reaches every card through here without this
        being touched.
        """
        catalogue = ItemCatalogue()
        documents = list(documents)
        for item_type in ITEM_KINDS:
            wanted = catalogue.missing_ids(documents, ItemType(item_type))
            catalogue.add_names(item_type, item_names(container, item_type, wanted))

        methods = {
            method.id: method.name
            for method in (
                container.page_payment_methods_use_case()
                .execute(PageQuery(page_size=_METHOD_LIMIT))
                .rows
            )
        }
        return cls(
            catalogue=catalogue,
            method_name=lambda method_id: payment_method_name(methods.get(method_id)),
        )


def sale_record_card(sale, *, customer: str, names: DocumentNames) -> RecordCard:
    return sale_card(
        sale,
        customer=customer,
        items=names.catalogue.lines_of(sale),
        payments=payment_lines(sale, dated=_received, method_name=names.method_name),
    )


def purchase_record_card(purchase, *, supplier: str, names: DocumentNames) -> RecordCard:
    return purchase_card(
        purchase,
        supplier=supplier,
        items=names.catalogue.lines_of(purchase),
        payments=payment_lines(purchase, dated=_paid, method_name=names.method_name),
    )


def _received(payment) -> datetime | None:
    return payment.received_at or payment.created_at


def _paid(payment) -> datetime | None:
    return payment.paid_at or payment.created_at
