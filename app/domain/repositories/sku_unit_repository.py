from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Collection

from app.domain.entities.sku_unit import SkuUnit
from app.domain.repositories.base import Repository


class SkuUnitRepository(Repository[SkuUnit], ABC):
    @abstractmethod
    def list_for_sku(self, sku_id: int, *, active_only: bool = False) -> list[SkuUnit]:
        """The alternate units of one SKU.

        `active_only` for the places that offer a choice; everything that
        reads a document back wants them all, or a retired unit would
        leave the line that used it naming nothing.
        """
        raise NotImplementedError

    @abstractmethod
    def list_for_skus(self, sku_ids: Collection[int]) -> dict[int, list[SkuUnit]]:
        """The alternate units of several SKUs at once, keyed by SKU id.

        For a page of the catalogue, or a picker offering a unit per line:
        one trip rather than one per row.
        """
        raise NotImplementedError

    @abstractmethod
    def get_for_sku(self, sku_id: int, unit_id: int) -> SkuUnit | None:
        """One unit, but only if it belongs to that SKU.

        The pair, never the id alone. A unit id from another SKU is the
        one way a quantity could be converted by a factor that has nothing
        to do with what is being traded, so nothing looks one up without
        saying which SKU it must belong to.
        """
        raise NotImplementedError

    @abstractmethod
    def count_usages(self, unit_id: int) -> int:
        """How many document lines were entered in this unit.

        A unit that has been used is retired rather than removed: the
        lines that used it are read back through it.
        """
        raise NotImplementedError

    @abstractmethod
    def names_by_id(self, unit_ids: Collection[int]) -> dict[int, str]:
        """Unit names for a set of ids, keyed by id — for naming the lines
        on a page of documents without loading a SKU to look them up in."""
        raise NotImplementedError
