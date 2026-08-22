"""
The short list of "other ways this is counted", inside the item form.

A shop that buys A4 by the box and sells it by the piece says so once,
here: a name and how many base units one of them is worth. Two fields and
a remove button per row, and a button to add another — deliberately not a
screen of its own, because setting one up is part of describing the item
rather than a separate job.

The rows are read out as they stand and handed over whole. Nothing here
knows that a unit a document has used is retired rather than deleted —
that is the use case's, and it is exactly the kind of rule that should
not be in a widget.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.application.dto.commands import SkuUnitCommand
from app.presentation.theme import tokens as t


@dataclass(slots=True)
class _UnitRow:
    widget: QWidget
    name: QLineEdit
    factor: QLineEdit
    unit_id: int | None


class UnitRows(QWidget):
    """The alternate units of one item, as an editable list."""

    def __init__(self, base_unit: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows: list[_UnitRow] = []
        self._base_unit = base_unit or "unit"

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(6)

        self._add_button = QPushButton("+ Add unit")
        self._add_button.setProperty("variant", "link")
        self._add_button.clicked.connect(lambda: self.add_row())
        self._layout.addWidget(self._add_button)

    def set_base_unit(self, unit: str | None) -> None:
        """What one of *these* is called — the word every factor is in."""
        self._base_unit = unit or "unit"
        for row in self._rows:
            row.factor.setPlaceholderText(self._placeholder)

    @property
    def _placeholder(self) -> str:
        return f"how many {self._base_unit}"

    def set_units(self, units: Sequence) -> None:
        """Show the units this item already has."""
        for row in list(self._rows):
            self._remove(row)
        for unit in units:
            self.add_row(unit.name, unit.factor, unit.id)

    def add_row(
        self, name: str = "", factor: Decimal | None = None, unit_id: int | None = None
    ) -> None:
        container = QWidget(self)
        line = QHBoxLayout(container)
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(6)

        name_field = QLineEdit(name)
        name_field.setPlaceholderText("Box")
        name_field.setMaximumWidth(140)

        factor_field = QLineEdit("" if factor is None else _trimmed(factor))
        factor_field.setPlaceholderText(self._placeholder)

        equals = QLabel("=")
        equals.setStyleSheet(f"color: {t.MUTED};")

        remove = QPushButton("×")
        remove.setProperty("variant", "link")
        remove.setFixedWidth(28)
        remove.setToolTip("Remove this unit")

        line.addWidget(name_field)
        line.addWidget(equals)
        line.addWidget(factor_field, 1)
        line.addWidget(remove)

        row = _UnitRow(widget=container, name=name_field, factor=factor_field, unit_id=unit_id)
        remove.clicked.connect(lambda: self._remove(row))

        # Above the Add button, which stays at the bottom of the block.
        self._layout.insertWidget(self._layout.count() - 1, container)
        self._rows.append(row)

    def _remove(self, row: _UnitRow) -> None:
        self._rows.remove(row)
        row.widget.setParent(None)
        row.widget.deleteLater()

    # ---------------- reading ----------------

    def units(self) -> tuple[SkuUnitCommand, ...] | None:
        """The list as it stands, or None if something in it is not a unit.

        A half-typed row is a mistake worth pointing at rather than
        quietly dropping: somebody typed "Box" and meant to finish.
        """
        units: list[SkuUnitCommand] = []
        for row in self._rows:
            name = row.name.text().strip()
            factor = _as_factor(row.factor.text())
            if not name and factor is None:
                continue  # an empty row somebody added and left alone
            if not name or factor is None:
                return None
            units.append(SkuUnitCommand(name=name, factor=factor, id=row.unit_id))
        return tuple(units)

    def first_incomplete(self) -> QWidget | None:
        """The field to put the cursor in when `units()` refused."""
        for row in self._rows:
            if not row.name.text().strip():
                return row.name
            if _as_factor(row.factor.text()) is None:
                return row.factor
        return None


def _as_factor(text: str) -> Decimal | None:
    try:
        value = Decimal(text.strip().replace(",", ""))
    except (InvalidOperation, ValueError):
        return None
    return value if value > 0 else None


def _trimmed(value: Decimal) -> str:
    """A factor without the trailing zeros of the column it came out of."""
    text = f"{Decimal(value):f}"
    return text.rstrip("0").rstrip(".") if "." in text else text
