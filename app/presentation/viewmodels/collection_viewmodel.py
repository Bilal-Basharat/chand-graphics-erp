"""
View model for the "list, search, create" screens.

Cabinets, payment methods, customers, suppliers and inventory items differ
only in *which* use cases they call — the state machine around those calls
is identical. Rather than five near-identical view model classes, each
screen supplies a `CollectionSource` of three callables and reuses this.

Screens whose behaviour genuinely differs (sales, purchases, reports)
still get their own view model; this is for the ones that don't.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import Signal

from app.presentation.viewmodels.base import BaseViewModel


@dataclass(frozen=True, slots=True)
class CollectionSource:
    """
    Each callable is invoked on a worker thread, so it should both build
    and execute its use case — that keeps the unit of work created and
    consumed on the same thread.
    """

    list_all: Callable[[], list]
    search: Callable[[str], list] | None = None
    create: Callable[[Any], Any] | None = None
    update: Callable[[Any], Any] | None = None
    delete: Callable[[int], None] | None = None


class CollectionViewModelBase(BaseViewModel):
    """
    The contract `CollectionView` renders against.

    Most screens get it via `CollectionViewModel` below. Screens whose
    listing genuinely isn't a whole-collection fetch — inventory movement,
    scoped to one item — subclass this directly instead of forcing their
    shape into `CollectionSource`.
    """

    rowsLoaded = Signal(list)
    itemCreated = Signal(object)
    itemUpdated = Signal(object)
    itemDeleted = Signal(int)

    def load(self) -> None:
        raise NotImplementedError

    def search(self, term: str) -> None:
        raise NotImplementedError

    @property
    def supports_editing(self) -> bool:
        """Whether rows can be edited and removed in place.

        Drives whether the list screen shows per-row actions at all — a
        column of buttons that always fail is worse than no column.
        """
        return False


class CollectionViewModel(CollectionViewModelBase):
    def __init__(self, source: CollectionSource) -> None:
        super().__init__()
        self._source = source

    @property
    def supports_search(self) -> bool:
        return self._source.search is not None

    def load(self) -> None:
        self.run_async(self._source.list_all, on_success=self.rowsLoaded.emit)

    def search(self, term: str) -> None:
        term = term.strip()
        search_fn = self._source.search
        if not term or search_fn is None:
            self.load()
            return
        self.run_async(lambda: search_fn(term), on_success=self.rowsLoaded.emit)

    @property
    def supports_editing(self) -> bool:
        return self._source.update is not None and self._source.delete is not None

    def create(self, command: Any) -> None:
        create_fn = self._source.create
        if create_fn is None:
            raise RuntimeError("This collection is read-only — no create use case was supplied.")

        def _on_success(created: Any) -> None:
            self.itemCreated.emit(created)
            self.load()

        self.run_async(lambda: create_fn(command), on_success=_on_success)

    def update(self, command: Any) -> None:
        update_fn = self._source.update
        if update_fn is None:
            raise RuntimeError("This collection has no update use case.")

        def _on_success(updated: Any) -> None:
            self.itemUpdated.emit(updated)
            self.load()

        self.run_async(lambda: update_fn(command), on_success=_on_success)

    def delete(self, entity_id: int) -> None:
        delete_fn = self._source.delete
        if delete_fn is None:
            raise RuntimeError("This collection has no delete use case.")

        def _on_success(_result: Any) -> None:
            self.itemDeleted.emit(entity_id)
            self.load()

        self.run_async(lambda: delete_fn(entity_id), on_success=_on_success)
