from __future__ import annotations

from dataclasses import dataclass

from app.domain.entities.base import AuditEntity

DEFAULT_CATEGORY_NAME = "General"
"""The category a product belongs to when nobody has said otherwise.

Every product has one, so there has to be one that needs no decision.
Without it, "add a product" would open with a question the shopkeeper
did not come to answer, and a product filed nowhere would be a product
nobody finds again.
"""


@dataclass(slots=True, kw_only=True)
class Category(AuditEntity):
    """A shelf in the catalogue: "Papers", "Inks", "Packaging".

    Groups products and nothing else. It holds no stock, no price and no
    rule — moving a product between categories cannot change what is on
    the shelf, only where it is listed.
    """

    id: int | None = None
    name: str
    description: str | None = None

    def __post_init__(self) -> None:
        self.name = " ".join(self.name.split())
        if not self.name:
            raise ValueError("name cannot be empty")

    @property
    def is_default(self) -> bool:
        """Whether this is the category products fall back to.

        Matched on the name rather than on an id or a flag: the row is
        created by a migration on some databases and by the initializer
        on others, so its id differs between installations while the name
        never does.
        """
        return self.name.casefold() == DEFAULT_CATEGORY_NAME.casefold()
