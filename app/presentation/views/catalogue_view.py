"""
The catalogue screen: shelves, the products on them, and their variants.

The shopkeeper's mental model is two levels — a category, and the things
in it. The third is there only where a product genuinely comes in more
than one form, and stays folded away until then: a product with a single
item behind it is one row showing that item's stock, unit and minimum,
and the word "SKU" appears nowhere on the screen.

Everything the list itself does — searching, filtering, paging, the empty
and error states, the toolbar — comes from `CollectionView` unchanged.
What is here is the tree it renders into, what an edit in a cell means,
and where a dragged product lands.
"""
from __future__ import annotations

from decimal import Decimal

from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import QMessageBox, QWidget

from app.application.dto.commands import (
    CreateProductCommand,
    UpdateInventoryItemCommand,
    UpdateProductCommand,
)
from app.application.dto.queries import CatalogueRow
from app.domain.entities.category import DEFAULT_CATEGORY_NAME, Category
from app.presentation.dialogs.confirm import confirm_destructive
from app.presentation.dialogs.master_data_dialogs import (
    CategoryDialog,
    InventoryItemDialog,
    ProductDialog,
)
from app.presentation.formatting import quantity
from app.presentation.viewmodels.catalogue_viewmodel import (
    CatalogueViewModel,
    quantity_or_none,
)
from app.presentation.views.collection_view import CollectionPage, EditableCollectionView
from app.presentation.widgets.catalogue_tree import (
    CABINET_FIELD,
    CatalogueEdit,
    CatalogueHeading,
    CatalogueTree,
    variant_columns,
)
from app.presentation.widgets.quick_add_strip import QuickAddField, combo, line_edit, refill
from app.presentation.widgets.row_actions import RowAction
from app.presentation.widgets.stock_status import (
    stock_filters,
    stock_status_color,
    stock_status_text,
)
from app.presentation.widgets.table_model import Column

_DASH = "—"

_ADD_VARIANT = "variant"


def _on_a_product(label: str):
    """Show this action on product rows and nowhere else.

    Adding a second version of something is about the product. On a
    variant row or a heading it would have nothing to act on, and an
    empty label is how an action stands down — see `row_actions._shows`.
    """
    return lambda row: label if isinstance(row, CatalogueRow) else ""


_ADD_VARIANT_ACTION = RowAction(
    _ADD_VARIANT,
    "Variant",
    label_of=_on_a_product("Variant"),
    hint="Add another version of this product",
)


def _sku_of(row) -> object | None:
    """The item a row shows, or None where the row is a category or a
    product with several and no single one to show."""
    if isinstance(row, CatalogueHeading):
        return None
    return row.sku if isinstance(row, CatalogueRow) else row


def _skus_of(row) -> tuple:
    """Every item behind a row — one for a variant, all of them for a
    product, none for a heading."""
    if isinstance(row, CatalogueHeading):
        return ()
    return row.skus if isinstance(row, CatalogueRow) else (row,)


def _shared_unit(skus) -> str | None:
    """The one unit these are all counted in, or None if they differ."""
    units = {sku.unit for sku in skus}
    return units.pop() if len(units) == 1 else None


def _status_word(skus) -> str:
    """What a row has to say about its stock, or nothing.

    A healthy row is left blank on purpose. Every row on a shop's
    catalogue is healthy on an ordinary day, and a column repeating "In
    stock" down the whole page is a wall the eye has to read past to find
    the two rows that need reordering. Blank means nothing to do; a word
    means do something.

    The word rather than the colour alone is what carries it — the stock
    figure is tinted too, and nobody should have to tell green from
    orange to run their shop.
    """
    worst = _worst_stocked(skus)
    if worst is None or not worst.is_low_stock:
        return ""
    return stock_status_text(worst)


def _worst_stocked(skus):
    """The item in the worst state of the lot: out of stock before low,
    low before healthy. What a row says about itself is whatever most
    needs doing about it."""
    if not skus:
        return None
    return min(skus, key=lambda sku: (sku.current_stock > 0, not sku.is_low_stock))


def _text(getter):
    """A column that reads a field off whichever record the row is."""

    def read(row):
        sku = _sku_of(row)
        return _DASH if sku is None else (getter(sku) or _DASH)

    return read


class CatalogueView(EditableCollectionView):
    def __init__(self, view_model: CatalogueViewModel, parent: QWidget | None = None) -> None:
        self._catalogue_view_model = view_model
        self._cabinets: dict[int, str] = {}
        self._categories: dict[int, str] = {}
        self._skus: dict[int, object] = {}
        """The items on the page in hand, so an edit to one cell can be
        sent as the whole record the update use case takes."""

        # Widths: everything whose content has a known short length is
        # fixed, and the name — the column people actually read down —
        # takes what is left. A description is optional and almost always
        # empty, so it is given room to be edited in and no more.
        columns = [
            Column("NAME", self._row_name, sort_field="name", editable="name"),
            Column(
                "DESCRIPTION",
                _text(lambda sku: sku.description),
                width=170,
                editable="description",
            ),
            Column("CABINET", self._cabinet_label, width=120, editable=CABINET_FIELD),
            Column("UNIT", self._unit_label, width=100),
            Column("STOCK", self._stock, align="right", width=110, color=self._status_color),
            Column("MINIMUM", self._minimum, align="right", width=100, editable="minimum_stock"),
            Column("STATUS", self._status, align="center", color=self._status_color, width=110),
        ]

        super().__init__(
            CollectionPage(
                crumb=("Items", "Inventory"),
                title="Inventory",
                panel_title="Catalogue",
                empty_message="Nothing here yet. Add a product above, or use the row below.",
                unit="product",
                search_placeholder="Search products and items by name",
                create_label="Add product",
                secondary_create_labels=("Add category",),
            ),
            columns,
            view_model,
            parent,
        )
        self._columns = columns

    # ---------------- the tree ----------------

    def create_table(self, columns):
        """A three-level tree rather than the flat table every other list
        uses — see `catalogue_tree`."""
        table = CatalogueTree(
            columns,
            variant_columns(
                columns,
                {
                    "NAME": ("", lambda sku: sku.name, "name"),
                    "DESCRIPTION": ("", lambda sku: sku.description or _DASH, "description"),
                    "CABINET": ("", self._cabinet_label, CABINET_FIELD),
                    "UNIT": ("", lambda sku: sku.unit or _DASH, None),
                    "STOCK": ("", lambda sku: quantity(sku.current_stock), None),
                    "MINIMUM": ("", lambda sku: quantity(sku.minimum_stock), "minimum_stock"),
                    "STATUS": ("", lambda sku: _status_word((sku,)), None),
                },
            ),
            placeholder=self._page.empty_message,
            parent=self,
        )
        table.editSubmitted.connect(self._on_edit)
        table.productMoved.connect(self._catalogue_view_model.move_product)
        return table

    def filter_options(self):
        return stock_filters()

    def row_actions(self):
        """Three, and only on the rows each one means something on.

        Where a product is filed is not a fourth button: it is a field on
        the form Edit already opens, which is where every other thing
        about the row is changed.
        """
        return (*super().row_actions(), _ADD_VARIANT_ACTION)

    # ---------------- columns ----------------

    def _row_name(self, row) -> str:
        return row.name

    def _cabinet_label(self, row) -> str:
        sku = _sku_of(row)
        if sku is None or not sku.cabinet_id:
            return _DASH
        return self._cabinets.get(sku.cabinet_id, _DASH)

    def _unit_label(self, row) -> str:
        """What the row is counted in.

        A product whose variants are counted the same way — which is
        nearly all of them — is counted that way too. One whose variants
        disagree has no single word, and says so; the row opens to show
        what each of them is.
        """
        unit = _shared_unit(_skus_of(row))
        return unit or _DASH

    def _stock(self, row) -> str:
        """What is on the shelf, added up where that means anything.

        A product with three variants of the same paper holds the three
        of them together, and hiding that behind a disclosure arrow would
        make the shopkeeper open every row to answer "how much have we
        got". Where the variants are counted differently there is no
        total to give, and none is invented.
        """
        skus = _skus_of(row)
        if not skus:
            return ""
        if len(skus) > 1 and _shared_unit(skus) is None:
            return _DASH
        return quantity(sum((sku.current_stock for sku in skus), Decimal("0")))

    def _minimum(self, row) -> str:
        """Only where one item answers for the row.

        Minimums are set per item, and adding them up would read as a
        threshold nobody chose.
        """
        sku = _sku_of(row)
        return quantity(sku.minimum_stock) if sku is not None else ""

    def _status(self, row) -> str:
        return _status_word(_skus_of(row))

    def _status_color(self, row) -> str | None:
        """Colour from the same rule that words it.

        On the stock figure as well as the status, so the number a
        shopkeeper is scanning down carries the warning itself rather
        than making them read across to find it.
        """
        worst = _worst_stocked(_skus_of(row))
        return stock_status_color(worst) if worst is not None else None

    # ---------------- loading ----------------

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 (Qt override)
        super().showEvent(event)
        # Both are maintained on other screens, so they are refreshed each
        # visit rather than only when empty — a stale list here would
        # quietly offer the wrong choices.
        self._catalogue_view_model.load_categories()
        self._catalogue_view_model.load_cabinets()

    def on_rows_loaded(self, rows: list) -> None:
        self._skus = {sku.id: sku for row in rows for sku in row.skus}

    def _on_categories(self, categories: list) -> None:
        self._categories = {category.id: category.name for category in categories}
        refill(
            self._new_category,
            DEFAULT_CATEGORY_NAME,
            sorted(((name, cid) for cid, name in self._categories.items()), key=lambda e: e[0]),
        )

    def _on_cabinets(self, cabinets: list) -> None:
        self._cabinets = {cabinet.id: cabinet.code for cabinet in cabinets}
        self.table.set_choices(CABINET_FIELD, self._cabinets)
        self.table.refresh()

    # ---------------- quick add ----------------

    def quick_add_fields(self):
        self._new_product = line_edit("e.g. A4 Ivory 250gsm")
        # The prompt names what happens when nothing is chosen rather than
        # showing a dash: a product filed nowhere goes to General, and the
        # row should say so before it does.
        self._new_category = combo(DEFAULT_CATEGORY_NAME)
        self._new_unit = line_edit("Unit, e.g. sheets")
        self._catalogue_view_model.categoriesLoaded.connect(self._on_categories)
        self._catalogue_view_model.cabinetsLoaded.connect(self._on_cabinets)
        return (
            QuickAddField(self._new_product, 3),
            QuickAddField(self._new_category, 2),
            QuickAddField(self._new_unit, 2),
        )

    def build_quick_add(self) -> CreateProductCommand | None:
        name = self._new_product.text().strip()
        if not name:
            self._new_product.setFocus()
            return None
        return CreateProductCommand(
            name=name,
            category_id=self._new_category.currentData(),
            unit=self._new_unit.text().strip() or None,
        )

    # ---------------- dialogs ----------------

    def open_create_dialog(self) -> None:
        ProductDialog(
            self.view_model, self._categories, self._cabinets, parent=self
        ).exec()

    def open_secondary_dialog(self, index: int) -> None:
        CategoryDialog(self.view_model, parent=self).exec()

    def open_edit_dialog(self, row) -> None:
        """Whichever record the row actually is.

        A product with one item is that item as far as the screen is
        concerned, so its row opens the item form — which is where its
        unit, its cabinet and its minimum live. A product with several has
        only its own name and shelf to edit, and a heading is a category.
        """
        if isinstance(row, CatalogueHeading):
            CategoryDialog(self.view_model, category=self._category(row), parent=self).exec()
            return

        sku = _sku_of(row)
        if sku is None:
            ProductDialog(
                self.view_model,
                self._categories,
                self._cabinets,
                product=row.product,
                parent=self,
            ).exec()
            return

        # A product with one item is one row, so its form carries the
        # shelf as well. A variant's does not: the shelf belongs to the
        # product it sits under, and is edited there.
        on_its_own = isinstance(row, CatalogueRow)
        dialog = InventoryItemDialog(
            self.view_model,
            self._cabinets,
            item=sku,
            categories=self._categories if on_its_own else None,
            category_id=row.category_id if on_its_own else None,
            parent=self,
        )
        self._catalogue_view_model.load_units(sku.id, dialog.load_units)
        dialog.exec()

    # ---------------- row actions ----------------

    def _category(self, heading: CatalogueHeading):
        """The category behind a heading, as the dialog needs it.

        Built from what the row already carries rather than fetched: the
        page brought the name and the id with it, and a round trip to
        re-read two fields it is holding would only be one more thing to
        go wrong.
        """
        return Category(id=heading.id, name=heading.name)

    def on_row_action(self, key: str, row) -> None:
        if key == _ADD_VARIANT:
            self._add_variant(row)
        else:
            super().on_row_action(key, row)

    def _add_variant(self, row) -> None:
        """Another item under this product — matt beside gloss.

        Offered on every row, including the ones that have only one item,
        because that is exactly when it is needed: a product becomes two
        variants the moment the second is added.
        """
        product_id = row.product.id if isinstance(row, CatalogueRow) else row.product_id
        InventoryItemDialog(
            self.view_model, self._cabinets, product_id=product_id, parent=self
        ).exec()

    def warn(self, message: str) -> None:
        """Say something went wrong the way the rest of the screen does."""
        QMessageBox.warning(self, self._page.title, message)

    def _noun(self, row) -> str:
        """What kind of record this row is, for the delete confirmation."""
        if isinstance(row, CatalogueHeading):
            return "category"
        if isinstance(row, CatalogueRow):
            return "product"
        return "variant"

    def describe(self, row) -> str:
        return row.name

    def delete_warning(self, row) -> str:
        if isinstance(row, CatalogueHeading):
            return (
                f"Whatever is filed under it goes back to {DEFAULT_CATEGORY_NAME}. "
                "No stock, price or document is affected."
            )
        if isinstance(row, CatalogueRow) and row.has_variants:
            return (
                f"All {len(row.skus)} of its versions go with it. Anything that has "
                "been bought or sold cannot be deleted at all."
            )
        return "An item that has been bought or sold cannot be deleted."

    def _remove(self, row) -> None:
        """The same confirmation, then whichever use case fits the row.

        A product row takes its items with it; a variant row is one item,
        and taking the last one takes the product too — a product nothing
        can be bought or sold under is not a catalogue record any more.
        """
        if not confirm_destructive(
            self,
            title=f"Delete {self._noun(row)}",
            message=f"Delete {self.describe(row)}?\n\n{self.delete_warning(row)}",
            confirm_label="Delete",
        ):
            return

        if isinstance(row, CatalogueHeading):
            self._catalogue_view_model.delete_category(row.id)
        elif isinstance(row, CatalogueRow):
            self._catalogue_view_model.delete_product(row.product.id)
        else:
            self._catalogue_view_model.delete_sku(row.id)

    # ---------------- editing ----------------

    def _on_edit(self, edit: CatalogueEdit) -> None:
        """Save what was typed into a cell.

        The table says what was typed and against which record; turning
        that into a command is this screen's, and deciding whether a
        product's rename reaches its item is the use case's.
        """
        if edit.field == "name" and edit.product_id is not None:
            self._catalogue_view_model.update(
                UpdateProductCommand(id=edit.product_id, name=edit.value)
            )
            return

        sku = self._skus.get(edit.sku_id)
        if sku is None:
            return

        command = self._sku_command(sku, edit)
        if command is not None:
            self._catalogue_view_model.update(command)

    def _sku_command(self, sku, edit: CatalogueEdit) -> UpdateInventoryItemCommand | None:
        """The item as it stands, with the one field that changed.

        The whole record, because that is what the use case takes — an
        update carrying only one field would clear the rest.
        """
        minimum: Decimal = sku.minimum_stock
        if edit.field == "minimum_stock":
            minimum = quantity_or_none(edit.value)
            if minimum is None:
                self.warn("A minimum has to be a number — 20, or 0.5.")
                return None

        return UpdateInventoryItemCommand(
            id=sku.id,
            name=edit.value.strip() if edit.field == "name" else sku.name,
            minimum_stock=minimum,
            description=(
                (edit.value.strip() or None) if edit.field == "description" else sku.description
            ),
            cabinet_id=(
                _as_id(edit.value) if edit.field == CABINET_FIELD else sku.cabinet_id
            ),
            unit=sku.unit,
        )


def _as_id(value: str) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
