"""
Recording goods coming back, against the document they came off.

The form is arranged the way the counter is: the invoice first, then
which line off it, then how many — because what may come back is decided
by the line, and until one is chosen there is no quantity to type. The
cap is applied to the spinner rather than checked on submit, so a
shopkeeper cannot enter twelve against a line that sold ten and find out
afterwards.

Several lines at a time, added one at a time to a list, the same way a
sale is built. A customer who hands back two things is making one return
— one number, one conversation about the refund, one line on their
account — and asking for it twice would record two of each.

Sales and purchases share the class. A return is the same act either way
— goods, some lines, and money that may or may not change hands — and the
two differ only in the nouns and in which use case is called, so those
arrive as a `ReturnKind` rather than as a second dialog.

Refunding is asked, not assumed. Goods coming back always reduce what the
document is worth; whether money goes back with them is the shopkeeper's
call, and leaving it at nothing puts the value on the party's account as
credit. The box opens on the answer that is usually right — nothing while
the invoice still has a balance to absorb it, the full value once it is
settled or there is no account to carry it.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QWidget,
)

from app.application.dto.commands import (
    RecordPurchaseReturnCommand,
    RecordSaleReturnCommand,
    ReturnedLineCommand,
)
from app.application.dto.queries import ReturnableDocument, ReturnableLine
from app.presentation.dialogs.form_dialog import FormDialog
from app.presentation.formatting import money
from app.presentation.widgets.document_lines import LinesTable
from app.presentation.widgets.input_validation import MoneyInput, parse_amount_or_zero
from app.presentation.widgets.modern_spinbox import ModernSpinBox
from app.presentation.widgets.payment_method_combo import PaymentMethodCombo
from app.presentation.widgets.searchable_combo import SearchableComboBox
from app.shared.datetimes import now_pkt

ZERO = Decimal("0.00")


@dataclass(frozen=True, slots=True)
class ReturnKind:
    """Everything that differs between a sale return and a purchase one."""

    action_label: str
    """Wording on the button that opens it, where two of them sit side by
    side — so the label and the dialog it opens cannot drift apart."""

    title: str
    subtitle: str
    document_noun: str
    """"Invoice" or "Purchase" — what the first row is labelled."""
    pick_prompt: str
    """What the picker reads before one has been chosen."""
    line_noun: str
    refund_label: str
    prefix: str
    """What return numbers of this kind start with — SR- or PR-."""
    command: type
    note: str


SALE_RETURNS = ReturnKind(
    action_label="Customer return",
    title="Record a customer return",
    subtitle="Goods coming back off an invoice. Stock goes up and the invoice is worth less.",
    document_noun="Invoice",
    pick_prompt="— Choose an invoice —",
    line_noun="Item sold",
    refund_label="Refund to customer",
    prefix="SR",
    command=RecordSaleReturnCommand,
    note=(
        "Only what an invoice actually sold can come back off it. Leave the refund "
        "at nothing to put the value on the customer's account instead."
    ),
)

PURCHASE_RETURNS = ReturnKind(
    action_label="Supplier return",
    title="Record a return to supplier",
    subtitle="Goods going back off a purchase. Stock goes down and the bill is worth less.",
    document_noun="Purchase",
    pick_prompt="— Choose a purchase —",
    line_noun="Item bought",
    refund_label="Refund from supplier",
    prefix="PR",
    command=RecordPurchaseReturnCommand,
    note=(
        "Only what a purchase actually bought can go back off it, and only while "
        "the stock is still on the shelf."
    ),
)


def new_return_number(prefix: str) -> str:
    """A number for this return, the same shape as an invoice's.

    Made here rather than by the database for the same reason `INV-` is —
    it goes on the form the moment it opens, so what is about to be
    recorded can be read before it is.
    """
    return f"{prefix}-{now_pkt():%y%m%d%H%M%S}"


@dataclass(slots=True)
class ReturningLine:
    """One of the document's lines, and how many of it are going back.

    Named for `LinesTable`, which reads `label`, `quantity`, `unit_price`
    and `total` off whatever it is given — so the list of goods on a
    return is drawn exactly like the list of goods on a sale.
    """

    line: ReturnableLine
    quantity: int

    @property
    def label(self) -> str:
        return self.line.label

    @property
    def unit_price(self) -> Decimal:
        return self.line.unit_price

    @property
    def total(self) -> Decimal:
        return self.line.unit_price * Decimal(self.quantity)


class RecordReturnDialog(FormDialog):
    def __init__(
        self,
        view_model,
        kind: ReturnKind,
        *,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            title=kind.title,
            subtitle=kind.subtitle,
            submit_label="Record return",
            parent=parent,
        )
        # Wider than a plain form: it carries the list of what is going
        # back, and an item name squeezed to nothing is the one column
        # that has to be readable.
        self.setMinimumWidth(620)

        self._view_model = view_model
        self._kind = kind
        self._document: ReturnableDocument | None = None
        self._returning: list[ReturningLine] = []
        self.bind(view_model.returnRecorded, view_model.errorOccurred)
        self._connect(view_model.documentsSearched, self._on_documents_searched)
        self._connect(view_model.documentResolved, self._on_document_resolved)

        self._reference = SearchableComboBox()
        self._reference.setToolTip("Type any part of the number to find it")
        self._reference.setMinimumWidth(240)
        # Nothing is chosen until somebody chooses it. Without this the
        # box would show whichever document came back first and stand
        # there beside an empty list of items, looking like the document
        # had none.
        self._reference.set_placeholder_item(kind.pick_prompt, None)
        self._reference.searchRequested.connect(view_model.search_documents)
        self._reference.activated.connect(self._on_reference_chosen)
        self.add_row(kind.document_noun, self._reference)

        self._line = QComboBox()
        self._line.currentIndexChanged.connect(self._on_line_changed)
        self.add_row(kind.line_noun, self._line)

        self._quantity = ModernSpinBox()
        self._quantity.setRange(1, 1)
        self._add = QPushButton("Add item")
        self._add.setProperty("variant", "outline")
        self._add.clicked.connect(self.add_line)
        self.add_row("Quantity", _beside(self._quantity, self._add))

        self._lines = LinesTable()
        self._lines.set_placeholder("Nothing added yet — choose an item above.")
        self._lines.setMinimumHeight(130)
        self._lines.editRequested.connect(self._edit_line)
        self._lines.removeRequested.connect(self._remove_line)
        self.add_row("Returning", self._lines)

        self._value = QLineEdit()
        self._value.setReadOnly(True)
        self.add_row("Return value", self._value)

        self._refund = MoneyInput()
        self._refund.textEdited.connect(self._on_refund_edited)
        self.add_row(kind.refund_label, self._refund)

        self._method = PaymentMethodCombo()
        self.add_row("Refund method", self._method)

        self._reason = self.add_row("Reason", QLineEdit())
        self._reason.setPlaceholderText("Why the goods came back")

        self._note = self.add_row("Note", QTextEdit())
        self._note.setFixedHeight(60)

        self.add_note(kind.note)

        view_model.search_documents("")
        self._render()

    # ---------------- choosing the document ----------------

    def _on_documents_searched(self, term: str, rows: list[tuple[str, int]]) -> None:
        self._reference.set_options(rows, term=term or None)

    def _on_reference_chosen(self, _index: int) -> None:
        document_id = self._reference.currentData()
        if document_id is None:
            return
        # Choosing the document already showing is not a change of mind:
        # Qt reports a click on the standing choice like any other, and
        # taking it as one would fetch it again and throw away whatever
        # had been added.
        if self._document is not None and self._document.document_id == document_id:
            return
        self._view_model.resolve_document(document_id)

    def _on_document_resolved(self, document: ReturnableDocument) -> None:
        self._take(document)

    def _take(self, document: ReturnableDocument) -> None:
        """Show a document's returnable lines, and nothing else.

        A line that has already come back in full is left out rather than
        offered and refused — there is nothing to do on it.

        Anything staged against the document before is dropped: those
        lines belong to an invoice that is no longer the one on screen.
        """
        self._document = document
        # Selected rather than listed, so what the box reads is always the
        # document whose lines are underneath it.
        self._reference.select(document.reference, document.document_id)

        self._returning.clear()
        self._line.clear()
        for line in document.returnable_lines:
            self._line.addItem(
                f"{line.label} — {line.remaining} of {line.quantity} left", line.line_id
            )
        if self._line.count() == 0:
            self._line.addItem("Everything on this has already come back", None)
        self._render()

    # ---------------- the lines going back ----------------

    def _selected_line(self) -> ReturnableLine | None:
        line_id = self._line.currentData()
        if self._document is None or line_id is None:
            return None
        return next(
            (line for line in self._document.lines if line.line_id == line_id), None
        )

    def _staged(self, line_id: int) -> ReturningLine | None:
        return next(
            (staged for staged in self._returning if staged.line.line_id == line_id), None
        )

    def _available(self, line: ReturnableLine) -> int:
        """How many more of this line may still be added.

        What the line has left, less whatever is already on this return —
        so two goes at the same line cannot together exceed it.
        """
        staged = self._staged(line.line_id)
        return line.remaining - (staged.quantity if staged else 0)

    def _on_line_changed(self, _index: int = 0) -> None:
        line = self._selected_line()
        available = self._available(line) if line else 0
        # The cap made unclickable rather than checked on submit: the
        # spinner will not go past what that line has left.
        self._quantity.setRange(1, max(1, available))
        self._quantity.setValue(1)
        self._quantity.setEnabled(available > 0)

    def add_line(self) -> None:
        """Take what is in the picker onto the return."""
        line = self._selected_line()
        if line is None:
            self.reject_with("There is nothing left to return on this.", self._line)
            return

        available = self._available(line)
        if available <= 0:
            self.reject_with(
                "Everything that line has left is already on this return.", self._line
            )
            return

        quantity = min(self._quantity.value(), available)
        staged = self._staged(line.line_id)
        if staged is not None:
            # The same line twice is one line coming back, exactly as the
            # same item twice is one line on a sale.
            staged.quantity += quantity
        else:
            self._returning.append(ReturningLine(line=line, quantity=quantity))
        self._render()

    def _edit_line(self, row: int) -> None:
        """Put a staged line back in the picker to be entered again.

        Cheaper than a dialog to change one number, and it leaves the
        quantity under the same cap it was added under.
        """
        staged = self._line_at(row)
        if staged is None:
            return
        self._returning.remove(staged)
        self._render()
        index = self._line.findData(staged.line.line_id)
        if index >= 0:
            self._line.setCurrentIndex(index)
        self._quantity.setValue(staged.quantity)

    def _remove_line(self, row: int) -> None:
        staged = self._line_at(row)
        if staged is None:
            return
        self._returning.remove(staged)
        self._render()

    def _line_at(self, row: int) -> ReturningLine | None:
        return self._returning[row] if 0 <= row < len(self._returning) else None

    # ---------------- what it is worth ----------------

    def _render(self) -> None:
        """Redraw everything that follows from the staged lines."""
        self._lines.set_rows(list(self._returning))
        value = self._return_value()
        self._value.setText(money(value))
        self._refund.setText(money(self._suggested_refund(value)))
        self._on_line_changed()
        self._refresh_method_row()

    def _return_value(self) -> Decimal:
        return sum((staged.total for staged in self._returning), ZERO)

    def _suggested_refund(self, value: Decimal) -> Decimal:
        """What the refund box opens on — a starting point, not a rule.

        Nothing while there is still a balance the credit can come off and
        an account to carry it: that is what a credit customer expects,
        and handing cash back on an unpaid invoice would be paying twice.

        Otherwise the full value, capped at what has actually been
        received — the document is settled, or there is no account at all
        (a walk-in), and the only way to make the party whole is money.
        """
        if self._document is None:
            return ZERO
        if self._document.has_party and self._document.balance_amount > ZERO:
            return ZERO
        return min(value, self._document.refundable)

    def _on_refund_edited(self, _text: str) -> None:
        self._refresh_method_row()

    def _refresh_method_row(self) -> None:
        # Only asked when there is money to hand over; a method beside a
        # zero refund is a question about nothing.
        self.set_row_visible(self._method, parse_amount_or_zero(self._refund.text()) > ZERO)

    # ---------------- submitting ----------------

    def build_command(self):
        if self._document is None:
            self.reject_with(
                f"Choose the {self._kind.document_noun.lower()} these goods came off.",
                self._reference,
            )
            return None
        if not self._returning:
            self.reject_with("Add what is coming back first.", self._line)
            return None

        refund = parse_amount_or_zero(self._refund.text())
        value = self._return_value()
        if refund > value:
            self.reject_with(
                f"A refund cannot be more than the {money(value)} these goods "
                "were worth.",
                self._refund,
            )
            return None
        if refund > self._document.refundable:
            self.reject_with(
                f"Only {money(self._document.refundable)} has been received on this "
                "and is available to refund.",
                self._refund,
            )
            return None

        return self._kind.command(
            return_no=new_return_number(self._kind.prefix),
            **self._document_field(),
            lines=[
                ReturnedLineCommand(line_id=staged.line.line_id, quantity=staged.quantity)
                for staged in self._returning
            ],
            refund_amount=refund,
            refund_method_id=self._method.method_id if refund > ZERO else None,
            reason=self._reason.text().strip() or None,
            note=self._note.toPlainText().strip() or None,
        )

    def _document_field(self) -> dict:
        """The document id, under the name its kind's command uses."""
        if self._kind is SALE_RETURNS:
            return {"sale_id": self._document.document_id}
        return {"purchase_id": self._document.document_id}

    def submit_command(self, command) -> None:
        self._view_model.record_return(command)


def _beside(*widgets: QWidget) -> QWidget:
    """Two controls sharing one form row, left-aligned."""
    holder = QWidget()
    row = QHBoxLayout(holder)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(8)
    for widget in widgets:
        row.addWidget(widget)
    row.addStretch(1)
    return holder
