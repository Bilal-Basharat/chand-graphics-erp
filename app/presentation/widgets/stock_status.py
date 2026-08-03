"""
Stock status wording and colour, shared by every screen that shows a
stocked record (wedding cards, inventory items, movement history).

Both stocked entities expose `current_stock` / `is_low_stock`, so one
formatter keeps "Low stock" meaning the same thing — and rendering the
same colour — everywhere it appears.
"""
from __future__ import annotations

from typing import Protocol

from app.presentation.theme import tokens as t
from app.presentation.widgets.list_controls import FilterOption


class Stocked(Protocol):
    current_stock: int

    @property
    def is_low_stock(self) -> bool: ...


def stock_status_text(item: Stocked) -> str:
    if item.current_stock <= 0:
        return "Out of stock"
    if item.is_low_stock:
        return "Low stock"
    return "In stock"


def stock_status_color(item: Stocked) -> str | None:
    if item.current_stock <= 0:
        return t.DANGER
    if item.is_low_stock:
        return t.WARNING
    return t.SUCCESS


def stock_filters() -> tuple[FilterOption, ...]:
    """The stock filters both catalogues offer, in the order that matters:
    "what do I need to reorder" is the question that brings people here."""
    return (
        FilterOption("Needs reordering", lambda item: item.is_low_stock),
        FilterOption("Out of stock", lambda item: item.current_stock <= 0),
        FilterOption("In stock", lambda item: not item.is_low_stock),
    )
