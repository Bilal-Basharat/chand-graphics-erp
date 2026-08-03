"""
"Wedding card or inventory item?" picker, shared by the screens that act
on either kind of stock.

It exists as much for correctness as for reuse. Qt stores combo userData
as a QVariant, and a `StrEnum` round-trips through that as a plain `str`:
`combo.currentData()` returns `"CARD"`, not `ItemType.CARD`. Identity
checks against the enum then fail silently — the picker says "Wedding
card" while the code takes the inventory-item branch — and the plain
string travels on into commands that expect an enum. Reading the
selection through `selected_type()` coerces it back at the boundary.
"""
from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QWidget

from app.domain.enums.item_type import ItemType


class ItemTypeCombo(QComboBox):
    def __init__(
        self,
        *,
        card_label: str = "Wedding card",
        item_label: str = "Inventory item",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.addItem(card_label, ItemType.CARD)
        self.addItem(item_label, ItemType.INVENTORY_ITEM)

    def selected_type(self) -> ItemType:
        return ItemType(self.currentData())

    @property
    def is_card(self) -> bool:
        return self.selected_type() is ItemType.CARD
