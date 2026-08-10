"""
"Which kind of item?" picker, shared by the screens that act on stock.

Built from the registry in `presentation/item_types.py`, so a special
item module appears here the moment it is registered and nowhere has to
list the kinds a second time.

It exists as much for correctness as for reuse. Qt stores combo userData
as a QVariant, and a `StrEnum` round-trips through that as a plain `str`:
`combo.currentData()` returns `"INVENTORY_ITEM"`, not
`ItemType.INVENTORY_ITEM`. Identity checks against the enum then fail
silently, and the plain string travels on into commands that expect an
enum. Reading the selection through `selected_type()` coerces it back at
the boundary.
"""
from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QWidget

from app.domain.enums.item_type import ItemType
from app.presentation.item_types import ITEM_KINDS


class ItemTypeCombo(QComboBox):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        for item_type, kind in ITEM_KINDS.items():
            self.addItem(kind.label, item_type)

    def selected_type(self) -> ItemType:
        return ItemType(self.currentData())
