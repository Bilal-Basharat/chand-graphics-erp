"""
Each kind of record, written out as the one card.

A builder here is a choice of facts, not a layout: it picks which fields
belong at the top, which lines go into which table, and which figures the
record comes down to. Nothing here knows about widgets or paper.

The names a record refers to — the customer, the products, the payment
methods — are resolved by the caller and passed in. Every screen that
opens a card already holds those lookups for its own list, so a builder
that fetched them would be a second, slower answer to a question already
answered.
"""
from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from app.presentation.formatting import (
    counted,
    date_only,
    date_time,
    money,
    or_dash,
)
from app.presentation.records.card import (
    Field,
    Heading,
    RecordCard,
    Section,
    Tone,
    Total,
)
from app.presentation.viewmodels.document_items import DocumentItemLine, PaymentLine
from app.presentation.widgets.payment_status import payment_status_text

_ZERO = Decimal("0.00")

# The payment-status colours the lists already use, said as tones. The
# card cannot take the hex ones: paper has its own palette.
_PAYMENT_TONES: dict[str, Tone] = {
    "Paid": "success",
    "Part paid": "warning",
    "Unpaid": "danger",
}

_ITEM_HEADINGS = (
    Heading("ITEM"),
    Heading("QTY", "right", 70),
    Heading("UNIT PRICE", "right", 120),
    Heading("LINE TOTAL", "right", 130),
)

_PAYMENT_HEADINGS = (
    Heading("DATE", width=170),
    Heading("PAYMENT", width=140),
    Heading("METHOD"),
    Heading("AMOUNT", "right", 120),
    Heading("BALANCE", "right", 120),
)


def _payment_tone(document) -> Tone:
    return _PAYMENT_TONES.get(payment_status_text(document), "muted")


def _item_section(title: str, lines: Sequence[DocumentItemLine], empty: str) -> Section:
    return Section(
        title=title,
        headings=_ITEM_HEADINGS,
        rows=tuple(
            (line.label, str(line.quantity), money(line.unit_price), money(line.total))
            for line in lines
        ),
        empty=empty,
    )


def _payments_section(title: str, lines: Sequence[PaymentLine]) -> Section:
    return Section(
        title=title,
        headings=_PAYMENT_HEADINGS,
        rows=tuple(
            (
                date_time(line.when),
                line.sequence,
                line.method,
                money(line.amount),
                money(line.balance_after),
            )
            for line in lines
        ),
        empty="Nothing paid against this yet.",
    )


def _settlement_totals(document) -> tuple[Total, ...]:
    """Subtotal down to what is left to pay — the same five figures, in the
    same order, on every document that can be paid in instalments."""
    settled = document.balance_amount <= _ZERO
    return (
        Total("Subtotal", money(document.subtotal)),
        Total("Discount", money(document.discount_amount), tone="muted"),
        Total("Total", money(document.grand_total), strong=True),
        Total("Paid", money(document.paid_amount), tone="success"),
        Total(
            "Left to pay",
            money(document.balance_amount),
            tone="success" if settled else "danger",
        ),
    )


def sale_card(sale, *, customer: str, items: Sequence[DocumentItemLine],
              payments: Sequence[PaymentLine]) -> RecordCard:
    return RecordCard(
        kind="Sale invoice",
        reference=sale.invoice_no,
        subtitle=f"{customer} • {date_time(sale.created_at)}",
        status=payment_status_text(sale),
        status_tone=_payment_tone(sale),
        fields=(
            Field("Customer", customer),
            Field("Raised", date_time(sale.created_at)),
            Field("Items", counted(len(sale.items), "item")),
            Field("Payments", counted(len(sale.payments), "payment")),
        ),
        sections=(
            _item_section("Items sold", items, "This invoice has no lines."),
            _payments_section("Payments received", payments),
        ),
        totals=_settlement_totals(sale),
        note=sale.note or "",
    )


def purchase_card(purchase, *, supplier: str, items: Sequence[DocumentItemLine],
                  payments: Sequence[PaymentLine]) -> RecordCard:
    return RecordCard(
        kind="Purchase",
        reference=purchase.purchase_no,
        subtitle=f"{supplier} • {date_time(purchase.created_at)}",
        status=payment_status_text(purchase),
        status_tone=_payment_tone(purchase),
        fields=(
            Field("Supplier", supplier),
            Field("Supplier reference", or_dash(purchase.reference_no)),
            Field("Recorded", date_time(purchase.created_at)),
            Field("Items", counted(len(purchase.items), "item")),
        ),
        sections=(
            _item_section("Items bought", items, "This purchase has no lines."),
            _payments_section("Payments made", payments),
        ),
        totals=_settlement_totals(purchase),
        note=purchase.note or "",
    )


def expense_card(expense, *, category: str) -> RecordCard:
    """An expense has no lines to table — it is one amount, spent once."""
    priced = expense.quantity is not None and expense.unit_price is not None
    return RecordCard(
        kind="Expense",
        reference=expense.expense_name,
        subtitle=date_time(expense.created_at),
        fields=(
            Field("Category", category),
            Field("Recorded", date_time(expense.created_at)),
            *(
                (
                    Field("Quantity", str(expense.quantity)),
                    Field("Unit price", money(expense.unit_price)),
                )
                if priced
                else ()
            ),
        ),
        totals=(Total("Total", money(expense.total_amount), strong=True),),
        note=expense.remarks or "",
    )


def report_card(summary, *, period_label: str, share_of_expenses) -> RecordCard:
    """A period's trading, as the reports screen has just worked it out.

    Deliberately the same card as a document. A report is a heading, some
    facts, a table and a column of totals like everything else, so it
    prints through the same page and needs no second design.
    """
    net = summary.gross_profit
    return RecordCard(
        kind="Report",
        reference=period_label,
        subtitle=f"{date_only(summary.start)} to {date_only(summary.end)}",
        fields=(
            Field("Invoices raised", counted(summary.sales_count, "invoice")),
            Field("Purchases recorded", counted(summary.purchases_count, "purchase")),
            Field("Expenses recorded", counted(summary.expenses_count, "expense")),
            Field("To collect from customers", money(summary.receivable), tone="danger"),
            Field("To pay suppliers", money(summary.payable), tone="warning"),
        ),
        sections=(
            Section(
                title="Spending by category",
                headings=(
                    Heading("CATEGORY"),
                    Heading("ENTRIES", "right", 110),
                    Heading("TOTAL", "right", 150),
                    Heading("SHARE", "right", 110),
                ),
                rows=tuple(
                    (row.name, str(row.count), money(row.total), share_of_expenses(row))
                    for row in summary.expense_breakdown
                ),
                empty="No expenses recorded in this period.",
            ),
        ),
        totals=(
            Total("Sales", money(summary.sales_total)),
            Total("Purchases", money(summary.purchases_total), tone="muted"),
            Total("Expenses", money(summary.expenses_total), tone="muted"),
            Total(
                "Net movement",
                money(net),
                tone="success" if net >= _ZERO else "danger",
                strong=True,
            ),
        ),
        note=(
            "Net movement is sales less what was bought and spent in the same "
            "window. It is a period measure, not margin: stock bought this "
            "month may well be sold next."
        ),
    )
