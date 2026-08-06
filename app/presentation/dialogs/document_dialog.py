"""
The shared skeleton of "new sale" and "new purchase".

Both documents are the same three decisions in the same order — who it is
with, what is on it, what was paid — and everything that follows from
that is identical: the same line list, the same totals arithmetic, the
same "is this submittable" checks, the same asynchronous create and the
same signal teardown. Only three things genuinely differ, and those are
the hooks below: the identity fields, how an item gets picked, and which
command is built.

Numbering the steps and giving each its own titled panel makes the order
of work explicit; without it the form reads as one long stack of bands.

Subclasses set their own attributes *before* calling `super().__init__`,
because the hooks run during construction here.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.domain.enums.item_type import ItemType
from app.presentation.dialogs.line_item_dialog import LineItemDialog
from app.presentation.widgets.document_lines import (
    ZERO,
    DocumentLine,
    DocumentTotals,
    LinesTable,
)
from app.presentation.widgets.totals_panel import TotalsPanel


class DocumentDialog(QDialog):
    def __init__(
        self,
        view_model,
        *,
        title: str,
        subtitle: str,
        submit_label: str,
        items_title: str,
        empty_lines_message: str,
        payment_methods: list,
        current_user_id: int | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)

        self._view_model = view_model
        self._title = title
        self._current_user_id = current_user_id
        self._lines: list[DocumentLine] = []

        # The three steps scroll; the buttons do not. Laid out as one
        # column, the form's natural height ran past the bottom of a
        # laptop screen and took Record/Cancel with it — the two controls
        # you always need and could no longer reach.
        frame = QVBoxLayout(self)
        frame.setContentsMargins(0, 0, 0, 0)
        frame.setSpacing(0)

        scroll = QScrollArea(self)
        scroll.setObjectName("PageScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        body.setObjectName("PageScrollBody")
        scroll.setWidget(body)
        frame.addWidget(scroll, 1)

        outer = QVBoxLayout(body)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(14)

        heading = QLabel(title)
        heading.setProperty("role", "pageTitle")
        caption = QLabel(subtitle)
        caption.setProperty("role", "pageSub")
        outer.addWidget(heading)
        outer.addWidget(caption)

        outer.addWidget(self.build_identity_step())
        outer.addWidget(self._build_items_step(items_title, empty_lines_message), 1)
        outer.addWidget(self._build_payment_step(payment_methods))

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save
        )
        self._submit_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        self._submit_button.setText(submit_label)
        self._submit_button.setProperty("variant", "primary")
        buttons.accepted.connect(self._submit)
        buttons.rejected.connect(self.reject)
        footer = QWidget()
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(24, 12, 24, 16)
        footer_layout.addWidget(buttons)
        frame.addWidget(footer)

        self._size_to_screen(body, footer)

        self._connections = [
            (view_model.itemCreated, self._on_created),
            (view_model.errorOccurred, self._on_error),
        ]
        for signal, slot in self._connections:
            signal.connect(slot)

        self._render_lines()

    def _size_to_screen(self, body: QWidget, footer: QWidget) -> None:
        """Open as large as the form wants, but never larger than the screen.

        Measured from the scrolled body rather than from the dialog: a
        QScrollArea reports a modest size hint of its own whatever it
        holds, so asking the dialog would open it a couple of steps tall
        and leave the rest to scrolling that isn't needed.

        `availableGeometry` excludes the taskbar, so the dialog can never
        open with its own footer behind it.
        """
        available = self.screen().availableGeometry()
        margin = 80
        wanted = body.sizeHint().height() + footer.sizeHint().height()

        self.setMinimumWidth(min(880, available.width() - margin))
        self.resize(
            min(980, available.width() - margin),
            min(wanted, available.height() - margin),
        )

    # ---------------- subclass hooks ----------------

    def build_identity_step(self) -> QFrame:
        """Step 1: who the document is with, and how it is numbered."""
        raise NotImplementedError

    def build_picker(self) -> QWidget:
        """The control that chooses an item, shown above the line list."""
        raise NotImplementedError

    def validate(self) -> bool:
        """Check this document's own fields, warning and focusing on failure."""
        raise NotImplementedError

    def build_command(self, totals: DocumentTotals) -> Any | None:
        """The create command for these lines and totals."""
        raise NotImplementedError

    # ---------------- construction ----------------

    def _build_items_step(self, title: str, empty_message: str) -> QFrame:
        panel, layout = step_panel("2", title)
        layout.addWidget(self.build_picker())

        self._lines_table = LinesTable()
        self._lines_table.set_placeholder(empty_message)
        self._lines_table.setMinimumHeight(150)
        self._lines_table.doubleClicked.connect(lambda index: self._edit_line(index.row()))
        self._lines_table.editRequested.connect(self._edit_line)
        self._lines_table.removeRequested.connect(self._remove_line)
        layout.addWidget(self._lines_table, 1)
        return panel

    def _build_payment_step(self, payment_methods: list) -> QFrame:
        panel, layout = step_panel("3", "Discount and payment")
        self._totals = TotalsPanel(paid_caption="Paid now")
        self._totals.set_payment_methods(payment_methods)
        self._totals.changed.connect(self._recompute)
        layout.addWidget(self._totals)
        return panel

    # ---------------- lines ----------------

    @property
    def lines(self) -> list[DocumentLine]:
        return self._lines

    def add_line(
        self,
        *,
        item_type: ItemType,
        item_id: int,
        label: str,
        quantity: int,
        unit_price,
    ) -> None:
        """Add a line, or fold it into the matching one already there.

        Same item at the same price is one line with a larger quantity —
        two identical rows would only be harder to read. At a different
        price it is genuinely a second line, and stays one.
        """
        existing = next(
            (line for line in self._lines if line.matches(item_type, item_id)), None
        )
        if existing is not None and existing.unit_price == unit_price:
            existing.quantity += quantity
        else:
            self._lines.append(
                DocumentLine(
                    item_type=item_type,
                    item_id=item_id,
                    label=label,
                    quantity=quantity,
                    unit_price=unit_price,
                )
            )
        self._render_lines()

    def line_for(self, item_type: ItemType, item_id: int) -> DocumentLine | None:
        return next((line for line in self._lines if line.matches(item_type, item_id)), None)

    def _edit_line(self, row: int) -> None:
        line = self._line_at(row)
        if line is None:
            return
        dialog = LineItemDialog(
            item_label=line.label,
            title="Update line",
            submit_label="Update line",
            quantity=line.quantity,
            unit_price=line.unit_price,
            available_stock=self.available_stock(line.item_type, line.item_id),
            parent=self,
        )
        # `line()` is the one source of truth for "was a line actually
        # entered" — a dialog can be accepted without one.
        dialog.exec()
        entered = dialog.line()
        if entered is None:
            return
        line.quantity, line.unit_price = entered
        self._render_lines()

    def available_stock(self, item_type: ItemType, item_id: int) -> int | None:
        """Stock the quantity field should be capped at, if there is a cap.

        A purchase raises stock, so it has none; a sale does.
        """
        return None

    def _remove_line(self, row: int) -> None:
        line = self._line_at(row)
        if line is None:
            return
        self._lines.remove(line)
        self._render_lines()

    def _line_at(self, row: int) -> DocumentLine | None:
        return self._lines[row] if 0 <= row < len(self._lines) else None

    def _render_lines(self) -> None:
        self._lines_table.set_rows(list(self._lines))
        self._submit_button.setEnabled(bool(self._lines))
        self._recompute()

    def _recompute(self) -> None:
        self._totals.render(self._lines)

    # ---------------- submit ----------------

    def warn(self, message: str) -> None:
        QMessageBox.warning(self, self._title, message)

    def _submit(self) -> None:
        if not self.validate():
            return
        if not self._lines:
            self.warn("Add at least one item first.")
            return

        totals = self._totals.render(self._lines)
        if totals.paid > totals.grand_total:
            self.warn("Paid now is more than the total. Reduce it or add a discount.")
            self._totals.focus_paid()
            return
        if totals.paid > ZERO and self._current_user_id is None:
            self.warn("Your session has ended. Sign in again to record a payment.")
            return

        command = self.build_command(totals)
        if command is None:
            return

        self._submit_button.setEnabled(False)
        self._view_model.create(command)

    def _on_created(self, *_result: Any) -> None:
        self.accept()

    def _on_error(self, message: str) -> None:
        self._submit_button.setEnabled(bool(self._lines))
        self.warn(message)

    def done(self, result: int) -> None:  # noqa: D102 (Qt override)
        # The view model outlives this dialog; see FormDialog for why these
        # have to be torn down explicitly.
        for signal, slot in self._connections:
            signal.disconnect(slot)
        self._connections.clear()
        super().done(result)


def step_panel(number: str, title: str) -> tuple[QFrame, QVBoxLayout]:
    """A titled panel numbered so the order of work is obvious."""
    panel = QFrame()
    panel.setProperty("role", "panel")
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(16, 12, 16, 14)
    layout.setSpacing(10)

    heading = QHBoxLayout()
    heading.setSpacing(9)
    badge = QLabel(number)
    badge.setObjectName("StepBadge")
    badge.setFixedSize(22, 22)
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    caption = QLabel(title)
    caption.setProperty("role", "panelTitle")
    heading.addWidget(badge)
    heading.addWidget(caption)
    heading.addStretch(1)
    layout.addLayout(heading)
    return panel, layout


def field(label_text: str, widget: QWidget) -> QVBoxLayout:
    """A labelled control. A blank label keeps a control's baseline level
    with its labelled neighbours in the same row."""
    block = QVBoxLayout()
    block.setSpacing(5)
    label = QLabel(label_text or " ")
    label.setProperty("role", "fieldLabel")
    block.addWidget(label)
    block.addWidget(widget)
    return block
