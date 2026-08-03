"""
Wedding cards catalogue: the collection scaffold plus its quick-add row.

Cards are entered in runs of dozens when a new batch arrives, so the
strip is the fast path and the dialog stays for the fuller form. The
strip itself is shared — see `widgets/quick_add_strip.py`.
"""
from __future__ import annotations

from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import QWidget

from app.application.dto.commands import CreateCardCommand
from app.presentation.dialogs.card_dialog import CardDialog
from app.presentation.formatting import DASH, or_dash
from app.presentation.viewmodels.wedding_cards_viewmodel import WeddingCardsViewModel
from app.presentation.views.collection_view import CollectionPage, EditableCollectionView
from app.presentation.widgets.modern_spinbox import ModernSpinBox
from app.presentation.widgets.quick_add_strip import QuickAddField, combo, line_edit, refill
from app.presentation.widgets.stock_status import (
    stock_filters,
    stock_status_color,
    stock_status_text,
)
from app.presentation.widgets.table_model import Column

_NO_CABINET = "— None —"


class WeddingCardsView(EditableCollectionView):
    def __init__(self, view_model: WeddingCardsViewModel, parent: QWidget | None = None) -> None:
        self._cards_view_model = view_model
        self._cabinet_names: dict[int, str] = {}

        super().__init__(
            CollectionPage(
                crumb=("Items", "Wedding cards"),
                title="Wedding cards",
                subtitle="Card catalogue with cabinet placement and stock levels.",
                panel_title="Card list",
                empty_message="No cards yet. Add one above, or use the quick-add row below.",
                unit="card",
                search_placeholder="Search cards by number or name",
                create_label="Add card",
            ),
            [
                Column("CARD #", lambda c: c.card_number, width=140),
                Column("NAME", lambda c: or_dash(c.name), sort_key=lambda c: (c.name or "").lower()),
                Column("CABINET", self._cabinet_label, width=150),
                Column(
                    "STOCK",
                    lambda c: c.current_stock,
                    align="right",
                    sort_key=lambda c: c.current_stock,
                    width=100,
                ),
                Column(
                    "MINIMUM",
                    lambda c: c.minimum_stock,
                    align="right",
                    sort_key=lambda c: c.minimum_stock,
                    width=110,
                ),
                Column(
                    "STATUS",
                    stock_status_text,
                    align="center",
                    color=stock_status_color,
                    sort_key=lambda c: c.current_stock,
                    width=130,
                ),
            ],
            view_model,
            parent,
        )

        view_model.cabinetsLoaded.connect(self._on_cabinets_loaded)

    def filter_options(self):
        return stock_filters()

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 (Qt override)
        super().showEvent(event)
        # Refreshed each visit rather than only when empty — cabinets get
        # added on their own screen, and a stale list here would silently
        # offer the wrong choices in the quick-add row and the dialog.
        self._cards_view_model.load_cabinets()

    # ---------------- quick-add strip ----------------

    def quick_add_fields(self):
        self._new_card_number = line_edit("Card #")
        self._new_name = line_edit("Name")
        self._new_cabinet = combo(_NO_CABINET)
        self._new_minimum_stock = ModernSpinBox()
        self._new_minimum_stock.setRange(0, 1_000_000)
        self._new_minimum_stock.setPrefix("Min: ")

        return (
            QuickAddField(self._new_card_number, 2),
            QuickAddField(self._new_name, 3),
            QuickAddField(self._new_cabinet, 2),
            QuickAddField(self._new_minimum_stock, 1),
        )

    def build_quick_add(self) -> CreateCardCommand | None:
        card_number = self._new_card_number.text().strip()
        if not card_number:
            self._new_card_number.setFocus()
            return None

        return CreateCardCommand(
            card_number=card_number,
            name=self._new_name.text().strip() or None,
            minimum_stock=self._new_minimum_stock.value(),
            current_stock=0,
            cabinet_id=self._new_cabinet.currentData(),
        )

    # ---------------- cabinets ----------------

    def _cabinet_label(self, card) -> str:
        if not card.cabinet_id:
            return DASH
        return self._cabinet_names.get(card.cabinet_id, DASH)

    def _on_cabinets_loaded(self, cabinets: list) -> None:
        self._cabinet_names = {c.id: c.code for c in cabinets}
        self.table.refresh()
        refill(
            self._new_cabinet,
            _NO_CABINET,
            sorted(
                ((code, cabinet_id) for cabinet_id, code in self._cabinet_names.items()),
                key=lambda entry: entry[0],
            ),
        )

    def open_create_dialog(self) -> None:
        CardDialog(self._cards_view_model, self._cabinet_names, parent=self).exec()

    def open_edit_dialog(self, row) -> None:
        CardDialog(self._cards_view_model, self._cabinet_names, card=row, parent=self).exec()

    def describe(self, row) -> str:
        return f"card {row.card_number}"
