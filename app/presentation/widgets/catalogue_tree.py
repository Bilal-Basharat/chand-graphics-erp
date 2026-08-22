"""
The catalogue, as a shopkeeper reads it: shelves, and what is on them.

Three levels, and the middle one is the point. A **category** is a
heading. A **product** is a row. A product's **SKUs** are that row opened
— and only when there is more than one of them, which for most of a shop's
catalogue there never will be. A product with a single SKU *is* the row:
its stock, its unit and its minimum are shown against the product's own
name, and the word "SKU" never appears on screen.

`GroupedTable` is the two-level version of this idea and is left alone for
the document screens. This is not a generalisation of it: a third level
changes what a row means at each depth, and folding both into one model
would put a depth check in front of every answer it gives. What the two
share are the pieces underneath — the column specs, the cell rendering,
the sizing, the empty state — which are imported rather than rewritten.

Editing happens in place. The table does not save anything: it emits what
was typed and against which record, and the screen hands that to a use
case. A widget that wrote to the database would be the business rule for
renaming a product living in a table.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any

from PySide6.QtCore import (
    QAbstractItemModel,
    QMimeData,
    QModelIndex,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QFont, QPaintEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QStyledItemDelegate,
    QTreeView,
    QWidget,
)

from app.application.dto.queries import CatalogueRow
from app.domain.quantities import to_quantity
from app.presentation.formatting import quantity
from app.presentation.theme import tokens as t
from app.presentation.widgets.data_table import apply_column_sizing, paint_placeholder
from app.presentation.widgets.sortable_header import SortableHeader
from app.presentation.widgets.table_model import Column, cell_alignment, column_data

PRODUCT_MIME = "application/x-chand-product"
"""What a dragged row carries. Its own type rather than plain text, so a
name dragged in from anywhere else cannot be read as a product id."""

CABINET_FIELD = "cabinet_id"
"""The one edited field that is a choice rather than something typed.

Named here because the editor for it is a dropdown, and the list it
offers comes from the screen — cabinets are maintained elsewhere.
"""

QUANTITY_FIELDS = frozenset({"minimum_stock"})
"""Fields that are counts, and are refused rather than rounded when what
was typed is not one."""

_HEADING_FONT: QFont | None = None


def _heading_font() -> QFont:
    """A category heading's type: the row font, one weight up. It is a
    label for the block under it, not a record in its own right."""
    global _HEADING_FONT
    if _HEADING_FONT is None:
        font = QApplication.font()
        font.setWeight(QFont.Weight.DemiBold)
        _HEADING_FONT = font
    return _HEADING_FONT


class NodeKind(Enum):
    CATEGORY = "category"
    PRODUCT = "product"
    SKU = "sku"


@dataclass(slots=True)
class _Node:
    """One row of the tree, and enough to answer anything asked of it.

    Held rather than derived on demand because Qt asks for a parent from
    a child index and for children from a parent index, over and over,
    during every repaint.
    """

    kind: NodeKind
    key: int
    record: Any
    """What this row is: a `CatalogueRow` for a product, an
    `InventoryItem` for a SKU, a `CatalogueHeading` for a heading."""

    parent: "_Node | None" = None
    row: int = 0
    children: list["_Node"] = field(default_factory=list)
    """Empty on a variant, which is as deep as the tree goes."""


@dataclass(frozen=True, slots=True)
class CatalogueHeading:
    """A category, as the row standing over its products.

    Carries its id as well as its name because the heading is a record
    the screen can act on — renaming a shelf somebody mistyped, or
    clearing one out — and a name alone could not say which.
    """

    id: int
    name: str


@dataclass(frozen=True, slots=True)
class CatalogueEdit:
    """Something typed into a row, and what it was typed into.

    Both ids, because one edit can mean two records: renaming a product
    that has a single SKU renames that SKU too, and only the use case
    should decide so. The table says what was typed and against which
    row, and nothing more.
    """

    field: str
    value: str
    product_id: int | None
    sku_id: int | None


def _sku_of(node: _Node):
    """The SKU a row edits, or None where the row is not one.

    A product with exactly one SKU stands in for it — that row shows its
    stock and its unit, so typing a minimum into it can only mean that
    SKU. A product with several has no single SKU to mean.
    """
    if node.kind is NodeKind.SKU:
        return node.record
    if node.kind is NodeKind.PRODUCT:
        return node.record.sku
    return None


class CatalogueModel(QAbstractItemModel):
    def __init__(
        self,
        columns: Sequence[Column],
        variant_columns: Sequence[Column],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._columns = list(columns)
        self._variant_columns = list(variant_columns)
        self._roots: list[_Node] = []
        self._by_key: dict[int, _Node] = {}
        self._choices: dict[str, dict[Any, str]] = {}

    # ---------------- data ----------------

    def set_rows(self, rows: Sequence[CatalogueRow]) -> None:
        """Rebuild the tree from one page of the catalogue.

        The page arrives ordered by category, so headings are cut where
        the category changes rather than by grouping the rows again here
        — which would quietly disagree with the order they came in.
        """
        self.beginResetModel()
        self._roots = []
        self._by_key = {}
        key = 0

        heading: _Node | None = None
        for row in rows:
            if heading is None or heading.record.id != row.category_id:
                key += 1
                heading = _Node(
                    kind=NodeKind.CATEGORY,
                    key=key,
                    record=CatalogueHeading(id=row.category_id, name=row.category_name),
                    row=len(self._roots),
                )
                self._roots.append(heading)
                self._by_key[key] = heading

            key += 1
            product = _Node(
                kind=NodeKind.PRODUCT,
                key=key,
                record=row,
                parent=heading,
                row=len(heading.children),
            )
            heading.children.append(product)
            self._by_key[key] = product

            # A single SKU is the row itself. Listing it underneath as
            # well would make every product in the shop expandable to
            # reveal a copy of the row above it.
            if row.has_variants:
                for sku in row.skus:
                    key += 1
                    node = _Node(
                        kind=NodeKind.SKU,
                        key=key,
                        record=sku,
                        parent=product,
                        row=len(product.children),
                    )
                    product.children.append(node)
                    self._by_key[key] = node

        self.endResetModel()

    def refresh(self) -> None:
        """Re-render the rows in hand — after a name lookup a getter reads
        has arrived, say."""
        if not self._roots:
            return
        self.dataChanged.emit(
            self.index(0, 0),
            self.index(len(self._roots) - 1, len(self._columns) - 1),
        )
        for heading in self._roots:
            self._refresh_under(self.index(heading.row, 0))

    def _refresh_under(self, parent: QModelIndex) -> None:
        rows = self.rowCount(parent)
        if not rows:
            return
        self.dataChanged.emit(
            self.index(0, 0, parent),
            self.index(rows - 1, len(self._columns) - 1, parent),
        )
        for row in range(rows):
            self._refresh_under(self.index(row, 0, parent))

    def set_choices(self, field: str, choices: dict[Any, str]) -> None:
        """What a dropdown-edited field may be set to."""
        self._choices[field] = dict(choices)

    def choices_for(self, field: str) -> dict[Any, str]:
        return self._choices.get(field, {})

    def node_at(self, index: QModelIndex) -> _Node | None:
        if not index.isValid():
            return None
        return index.internalPointer()

    def node_for_key(self, key: int) -> _Node | None:
        return self._by_key.get(key)

    def row_count(self) -> int:
        """How many products this page holds — what the screen counts.

        Headings are not records: a page of six products under two
        shelves is six things, and saying eight would disagree with the
        total the query reported.
        """
        return sum(len(heading.children) for heading in self._roots)

    # ---------------- structure ----------------

    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        siblings = self._roots if not parent.isValid() else parent.internalPointer().children
        return self.createIndex(row, column, siblings[row])

    def parent(self, index: QModelIndex = QModelIndex()) -> QModelIndex:  # noqa: N802 (Qt override)
        node = self.node_at(index)
        if node is None or node.parent is None:
            return QModelIndex()
        return self.createIndex(node.parent.row, 0, node.parent)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802 (Qt override)
        if not parent.isValid():
            return len(self._roots)
        if parent.column() > 0:
            return 0
        return len(parent.internalPointer().children)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802 (Qt override)
        return len(self._columns)

    # ---------------- rendering ----------------

    def headerData(  # noqa: N802 (Qt override)
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):
        if orientation != Qt.Orientation.Horizontal:
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            return self._columns[section].header
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return cell_alignment(self._columns[section])
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        node = self.node_at(index)
        if node is None:
            return None

        if node.kind is NodeKind.CATEGORY:
            return self._heading_data(node, index, role)

        columns = self._columns if node.kind is NodeKind.PRODUCT else self._variant_columns
        if index.column() >= len(columns):
            return None
        column = columns[index.column()]

        if role == Qt.ItemDataRole.EditRole:
            # What the field holds, not what the column shows. A minimum
            # reading "2,000" is a formatted figure, and an editor opened
            # on it has to offer the number back rather than leave every
            # edit to unpick the formatting again on the way in.
            return self._edited_value(node, column)

        if (
            role == Qt.ItemDataRole.ForegroundRole
            and node.kind is NodeKind.SKU
            and column.color is None
        ):
            # A variant reads as supporting detail under the row it
            # belongs to — the same rule the grouped document lists
            # follow — unless the column asked for a colour of its own.
            return QColor(t.INK_SOFT)

        return column_data(column, node.record, role)

    @staticmethod
    def _edited_value(node: _Node, column: Column) -> str:
        """What an editor opens on: the field itself.

        The name belongs to the row — a product's on a product row, a
        variant's on a variant row — and everything else to the item
        behind it.
        """
        if column.editable is None:
            return ""
        record = node.record if column.editable == "name" else _sku_of(node)
        value = getattr(record, column.editable, None)
        if value is None:
            return ""
        # A count is offered the way somebody would write it. Stored to
        # four places, a minimum of a hundred reads back as "100.0000",
        # and an editor pre-filled with that invites it to be saved again.
        return quantity(value) if isinstance(value, Decimal) else str(value)

    @staticmethod
    def _heading_data(node: _Node, index: QModelIndex, role: int):
        # A band across the whole row. The heading names the block under
        # it rather than filling a cell in the NAME column, and reading as
        # another row of data is exactly what it must not do.
        if role == Qt.ItemDataRole.BackgroundRole:
            return QColor(t.CANVAS)
        if index.column() != 0:
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            return node.record.name
        if role == Qt.ItemDataRole.FontRole:
            return _heading_font()
        if role == Qt.ItemDataRole.ForegroundRole:
            return QColor(t.INK)
        return None

    # ---------------- editing ----------------

    editSubmitted = Signal(object)  # CatalogueEdit
    productMoved = Signal(int, int)  # product id, category id

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        node = self.node_at(index)
        if node is None:
            return Qt.ItemFlag.NoItemFlags

        if node.kind is NodeKind.CATEGORY:
            # Selectable, because a shelf is a record too — one somebody
            # mistyped can be renamed, and an empty one cleared away. It
            # is also where a dragged product lands.
            return (
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsDropEnabled
            )

        flags = (
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsDragEnabled
        )
        if node.kind is NodeKind.PRODUCT:
            # A product dropped onto another product means the shelf that
            # one is on, which is what aiming at a row rather than at a
            # heading obviously means.
            flags |= Qt.ItemFlag.ItemIsDropEnabled

        if self._field_at(node, index.column()) is not None:
            flags |= Qt.ItemFlag.ItemIsEditable
        return flags

    def _field_at(self, node: _Node, column: int) -> str | None:
        """Which field this cell edits, or None where it is only read.

        Stock and price are never here: they are what purchases, sales
        and adjustments left behind, and a cell that typed over one would
        be a second, untracked way to change the same number.
        """
        columns = self._columns if node.kind is NodeKind.PRODUCT else self._variant_columns
        if column >= len(columns):
            return None

        field = columns[column].editable
        if field is None:
            return None
        if field == "name":
            return field
        # Everything else belongs to a SKU, and a product with several has
        # no single one to mean.
        return field if _sku_of(node) is not None else None

    def setData(  # noqa: N802 (Qt override)
        self, index: QModelIndex, value: Any, role: int = Qt.ItemDataRole.EditRole
    ) -> bool:
        if role != Qt.ItemDataRole.EditRole:
            return False
        node = self.node_at(index)
        if node is None:
            return False
        field = self._field_at(node, index.column())
        if field is None:
            return False

        sku = _sku_of(node)
        self.editSubmitted.emit(
            CatalogueEdit(
                field=field,
                value="" if value is None else str(value),
                product_id=node.record.id if node.kind is NodeKind.PRODUCT else None,
                sku_id=sku.id if sku is not None else None,
            )
        )
        # False, deliberately: nothing has been saved yet. The screen runs
        # the use case off the UI thread and reloads, and the row is
        # written by what came back rather than by what was typed — so a
        # rename the use case refuses never appears to have worked.
        return False

    # ---------------- dragging ----------------

    def supportedDropActions(self) -> Qt.DropAction:  # noqa: N802 (Qt override)
        return Qt.DropAction.MoveAction

    def mimeTypes(self) -> list[str]:  # noqa: N802 (Qt override)
        return [PRODUCT_MIME]

    def mimeData(self, indexes: Sequence[QModelIndex]) -> QMimeData:  # noqa: N802 (Qt override)
        payload = QMimeData()
        for index in indexes:
            node = self.node_at(index)
            if node is not None and node.kind is NodeKind.PRODUCT and node.record.id:
                payload.setData(PRODUCT_MIME, str(node.record.id).encode("ascii"))
                break
        return payload

    def canDropMimeData(  # noqa: N802 (Qt override)
        self,
        data: QMimeData,
        action: Qt.DropAction,
        row: int,
        column: int,
        parent: QModelIndex,
    ) -> bool:
        return data.hasFormat(PRODUCT_MIME) and self._target_category(parent) is not None

    def dropMimeData(  # noqa: N802 (Qt override)
        self,
        data: QMimeData,
        action: Qt.DropAction,
        row: int,
        column: int,
        parent: QModelIndex,
    ) -> bool:
        category_id = self._target_category(parent)
        if category_id is None or not data.hasFormat(PRODUCT_MIME):
            return False
        try:
            product_id = int(bytes(data.data(PRODUCT_MIME)).decode("ascii"))
        except ValueError:
            return False

        self.productMoved.emit(product_id, category_id)
        # False again: the move is a use case, and the tree is rebuilt
        # from what it returns. Moving the row here as well would show it
        # on the new shelf before anything had agreed to put it there.
        return False

    def _target_category(self, parent: QModelIndex) -> int | None:
        """Which shelf a drop at `parent` means, or None if it means none."""
        node = self.node_at(parent)
        if node is None:
            return None
        if node.kind is NodeKind.PRODUCT:
            return node.record.category_id
        if node.kind is NodeKind.CATEGORY:
            first = node.children[0] if node.children else None
            return first.record.category_id if first is not None else None
        return None


class _CatalogueEditor(QStyledItemDelegate):
    """The editors the catalogue opens in place.

    A dropdown where the field is a choice somebody keeps a list of, and
    the ordinary line editor everywhere else. Numbers are checked on the
    way out rather than restricted on the way in — a spin box in a table
    cell reads as a form, and this is meant to read as a list.
    """

    def __init__(self, model: CatalogueModel, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._model = model

    def createEditor(self, parent, option, index: QModelIndex):  # noqa: N802 (Qt override)
        if self._field(index) != CABINET_FIELD:
            return super().createEditor(parent, option, index)

        editor = QComboBox(parent)
        editor.addItem("—", None)
        for value, label in sorted(self._model.choices_for(CABINET_FIELD).items(), key=lambda e: e[1]):
            editor.addItem(label, value)
        return editor

    def setEditorData(self, editor, index: QModelIndex) -> None:  # noqa: N802 (Qt override)
        if not isinstance(editor, QComboBox):
            super().setEditorData(editor, index)
            return
        # Off the model's edit value, like every other field here: the id
        # the cell holds rather than the code it shows.
        current = index.data(Qt.ItemDataRole.EditRole)
        position = editor.findData(int(current)) if current else -1
        editor.setCurrentIndex(max(0, position))

    def setModelData(self, editor, model, index: QModelIndex) -> None:  # noqa: N802 (Qt override)
        if isinstance(editor, QComboBox):
            data = editor.currentData()
            model.setData(index, "" if data is None else str(data), Qt.ItemDataRole.EditRole)
            return

        text = editor.text().strip() if hasattr(editor, "text") else ""
        if self._field(index) in QUANTITY_FIELDS and not _is_quantity(text):
            # Refused rather than rounded to something. A minimum typed as
            # "twenty" is a slip, and silently saving nothing would leave
            # the shopkeeper believing it had been set.
            return
        model.setData(index, text, Qt.ItemDataRole.EditRole)

    def _field(self, index: QModelIndex) -> str | None:
        node = self._model.node_at(index)
        return None if node is None else self._model._field_at(node, index.column())


def _is_quantity(text: str) -> bool:
    try:
        return to_quantity(Decimal(text.replace(",", ""))) >= 0
    except (InvalidOperation, ValueError, TypeError):
        return False


class CatalogueTree(QTreeView):
    """The catalogue's table: headings, product rows, variants underneath."""

    editSubmitted = Signal(object)  # CatalogueEdit
    productMoved = Signal(int, int)  # product id, category id

    def __init__(
        self,
        columns: Sequence[Column],
        variant_columns: Sequence[Column],
        placeholder: str = "Nothing to show yet.",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._placeholder = placeholder
        self._model = CatalogueModel(columns, variant_columns, self)
        self.setModel(self._model)
        self._model.editSubmitted.connect(self.editSubmitted)
        self._model.productMoved.connect(self.productMoved)

        self._sorting = SortableHeader(columns, self)
        self._sorting.install(self)

        self.setItemDelegate(_CatalogueEditor(self._model, self))
        self.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setAlternatingRowColors(False)
        self.setWordWrap(False)
        self.setUniformRowHeights(True)
        self.setRootIsDecorated(True)
        self.setIndentation(20)
        self.setExpandsOnDoubleClick(False)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)

        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)

        self._widths = apply_column_sizing(self, columns)

    @property
    def sorting(self) -> SortableHeader:
        return self._sorting

    # ---------------- data ----------------

    def set_rows(self, rows: list) -> None:
        self._model.set_rows(rows)
        # Shelves open. A heading you have to click to see behind is an
        # obstacle rather than a summary — unlike a product's variants,
        # which are an answer to a question most rows never raise.
        self.expandAll()
        self._span_headings()
        self.viewport().update()

    def refresh(self) -> None:
        self._model.refresh()

    def set_choices(self, field: str, choices: dict) -> None:
        self._model.set_choices(field, choices)

    def _span_headings(self) -> None:
        for row in range(self._model.rowCount()):
            self.setFirstColumnSpanned(row, QModelIndex(), True)

    def row_count(self) -> int:
        return self._model.row_count()

    def row_at(self, key: int):
        """The record a row action was pressed on.

        Keyed rather than numbered — see `row_key`. A key from a page that
        has since been replaced simply is not there, which is what the
        callers already handle.
        """
        node = self._model.node_for_key(key)
        return None if node is None else node.record

    def row_key(self, index: QModelIndex) -> int:
        node = self._model.node_at(index)
        return node.key if node is not None else -1

    def acts_on(self, index: QModelIndex) -> bool:
        """Every row here is a record, at all three depths.

        A category is one too — a shelf somebody named, which they may
        want to rename or clear away — so the actions are offered on it
        as well, and which of them apply is the screen's to say.
        """
        return self._model.node_at(index) is not None

    def selected_row(self):
        indexes = self.selectionModel().selectedRows()
        if not indexes:
            return None
        node = self._model.node_at(indexes[0])
        return None if node is None else node.record

    def set_placeholder(self, text: str) -> None:
        if text == self._placeholder:
            return
        self._placeholder = text
        self.viewport().update()

    # ---------------- painting ----------------

    def drawRow(self, painter, option, index: QModelIndex) -> None:  # noqa: N802 (Qt override)
        # A QSS rule on `QTreeView::item` hands item drawing to Qt's
        # stylesheet style, and that path ignores `Qt.BackgroundRole`
        # entirely. A heading's band is not decoration — it is what stops
        # it reading as another row of data — so it is filled in here.
        # At row level rather than in a delegate, so the indent under the
        # disclosure arrow is covered instead of leaving a white notch.
        background = index.data(Qt.ItemDataRole.BackgroundRole)
        if isinstance(background, QColor):
            painter.fillRect(option.rect, background)
        super().drawRow(painter, option, index)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 (Qt override)
        super().paintEvent(event)
        if self._model.rowCount() == 0:
            paint_placeholder(self, self._placeholder)


def variant_columns(
    columns: Sequence[Column],
    under: dict[str, tuple[str, Callable[[Any], Any], str | None]],
) -> list[Column]:
    """The variant rows' columns, lined up under the product's.

    Written as "under this heading, read that off the SKU" rather than as
    a second list of widths to keep in step with the first by hand. A
    product column with no entry renders empty on a variant row.
    """
    blank = ("", lambda _row: "", None)
    return [
        Column(
            under.get(column.header, blank)[0],
            under.get(column.header, blank)[1],
            align=column.align,
            width=column.width,
            editable=under.get(column.header, blank)[2],
            color=column.color if column.header in under else None,
        )
        for column in columns
    ]
