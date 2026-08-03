from __future__ import annotations

from PySide6.QtCore import Signal

from app.application.dto.commands import (
    CreateCabinetCommand,
    CreateCardCommand,
    UpdateCardCommand,
)
from app.application.dto.queries import SearchQuery
from app.container import AppContainer
from app.presentation.viewmodels.collection_viewmodel import CollectionViewModelBase


class WeddingCardsViewModel(CollectionViewModelBase):
    """
    Implements the collection contract (`rowsLoaded`/`load`/`search`) so the
    catalogue renders on the shared scaffold, and adds the cabinet lookup
    the card list and its dialogs need on top.
    """

    cabinetsLoaded = Signal(list)     # list[Cabinet]
    cabinetCreated = Signal(object)   # Cabinet

    def __init__(self, container: AppContainer) -> None:
        super().__init__()
        self._container = container

    def load(self, limit: int = 500) -> None:
        use_case = self._container.list_cards_use_case()
        self.run_async(lambda: use_case.execute(limit), on_success=self.rowsLoaded.emit)

    def search(self, term: str) -> None:
        term = term.strip()
        if not term:
            self.load()
            return
        use_case = self._container.search_cards_use_case()
        query = SearchQuery(term=term, limit=200)
        self.run_async(lambda: use_case.execute(query), on_success=self.rowsLoaded.emit)

    def load_cabinets(self) -> None:
        use_case = self._container.list_cabinets_use_case()
        self.run_async(lambda: use_case.execute(200), on_success=self.cabinetsLoaded.emit)

    def create_cabinet(self, command: CreateCabinetCommand) -> None:
        use_case = self._container.create_cabinet_use_case()

        def _on_success(cabinet) -> None:
            self.cabinetCreated.emit(cabinet)
            self.load_cabinets()

        self.run_async(lambda: use_case.execute(command), on_success=_on_success)

    @property
    def supports_editing(self) -> bool:
        return True

    def create(self, command: CreateCardCommand) -> None:
        use_case = self._container.create_card_use_case()

        def _on_success(card) -> None:
            self.itemCreated.emit(card)
            self.load()

        self.run_async(lambda: use_case.execute(command), on_success=_on_success)

    def update(self, command: UpdateCardCommand) -> None:
        use_case = self._container.update_card_use_case()

        def _on_success(card) -> None:
            self.itemUpdated.emit(card)
            self.load()

        self.run_async(lambda: use_case.execute(command), on_success=_on_success)

    def delete(self, card_id: int) -> None:
        use_case = self._container.delete_card_use_case()

        def _on_success(_result) -> None:
            self.itemDeleted.emit(card_id)
            self.load()

        self.run_async(lambda: use_case.execute(card_id), on_success=_on_success)
