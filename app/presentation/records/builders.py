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
    DASH,
    counted,
    date_only,
    date_time,
    money,
    money_or_blank,
    or_dash,
    percent,
    uncosted_caveat,
)
from app.presentation.records.card import (
    Field,
    Heading,
    RecordCard,
    Section,
    Tone,
    Total,
)
from app.presentation.viewmodels.document_items import (
    DocumentItemLine,
    PaymentLine,
    ReturnLine,
)
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

_LEDGER_HEADINGS = (
    Heading("DATE", width=170),
    Heading("REFERENCE", width=150),
    Heading("DETAIL"),
    Heading("DEBIT", "right", 120),
    Heading("CREDIT", "right", 120),
    Heading("BALANCE", "right", 130),
)
"""Debit and credit are named the same on both statements — which side a
line lands on is the caller's `sides`, not the heading's."""


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


_RETURN_HEADINGS = (
    Heading("DATE", width=170),
    Heading("RETURN #", width=150),
    Heading("ITEM"),
    Heading("QTY", "right", 70),
    Heading("VALUE", "right", 120),
    Heading("REFUNDED", "right", 120),
)


def _returns_section(title: str, lines: Sequence[ReturnLine]) -> Section:
    return Section(
        title=title,
        headings=_RETURN_HEADINGS,
        rows=tuple(
            (
                date_time(line.when),
                line.reference,
                line.label,
                str(line.quantity),
                money(line.value),
                money_or_blank(line.refunded),
            )
            for line in lines
        ),
        empty="Nothing has come back off this.",
    )


def _returns_made(lines: Sequence[ReturnLine]) -> int:
    """How many returns those rows came off.

    The rows are one per item and a return can bring back several, so
    counting rows would report two returns where a customer made one.
    """
    return len({line.reference for line in lines})


def _settlement_totals(document) -> tuple[Total, ...]:
    """Subtotal down to what is left to pay — the same figures, in the same
    order, on every document that can be paid in instalments.

    Returns appear only on a document that has any. An invoice nothing
    came back off reads exactly as it always did, and the two extra lines
    are then a signal rather than a pair of zeros to skip over.
    """
    settled = document.balance_amount <= _ZERO
    returned = getattr(document, "returned_amount", _ZERO)
    refunded = getattr(document, "refunded_amount", _ZERO)
    return (
        Total("Subtotal", money(document.subtotal)),
        Total("Discount", money(document.discount_amount), tone="muted"),
        Total("Total", money(document.grand_total), strong=not returned),
        # Between the total and what was paid, because that is where it
        # acts: the goods came back off the total before the money was
        # ever counted against it.
        *(
            (
                Total("Returned", money(returned), tone="warning"),
                Total("Net total", money(document.net_total), strong=True),
            )
            if returned
            else ()
        ),
        Total("Paid", money(document.paid_amount), tone="success"),
        *((Total("Refunded", money(refunded), tone="muted"),) if refunded else ()),
        Total(
            "Left to pay",
            money(document.balance_amount),
            tone="success" if settled else "danger",
        ),
    )


def _return_status(document, status: str, tone: Tone) -> tuple[str, Tone]:
    """What the head of the card says, once goods have come back.

    A fully returned document is not "Paid" whatever the money did — the
    first thing to know about it is that none of it stands.
    """
    returned = getattr(document, "returned_amount", _ZERO)
    if not returned:
        return status, tone
    if document.net_total <= _ZERO:
        return "Returned", "danger"
    return f"{status} · returned", "warning"


def sale_card(sale, *, customer: str, items: Sequence[DocumentItemLine],
              payments: Sequence[PaymentLine],
              returns: Sequence[ReturnLine] = ()) -> RecordCard:
    status, tone = _return_status(sale, payment_status_text(sale), _payment_tone(sale))
    return RecordCard(
        kind="Sale invoice",
        reference=sale.invoice_no,
        subtitle=f"{customer} • {date_time(sale.created_at)}",
        status=status,
        status_tone=tone,
        fields=(
            Field("Customer", customer),
            Field("Raised", date_time(sale.created_at)),
            Field("Items", counted(len(sale.items), "item")),
            Field("Payments", counted(len(sale.payments), "payment")),
            # Only when there is something to say: a Returns field reading
            # "0 returns" on every invoice in the shop is noise.
            *((Field("Returns", counted(_returns_made(returns), "return"), tone="warning"),)
              if returns else ()),
        ),
        sections=(
            _item_section("Items sold", items, "This invoice has no lines."),
            _payments_section("Payments received", payments),
            # Its own table rather than a note, because a return is a
            # dated event with a number, and the customer's statement
            # names that number too.
            *((_returns_section("Goods returned", returns),) if returns else ()),
        ),
        totals=_settlement_totals(sale),
        note=sale.note or "",
    )


def purchase_card(purchase, *, supplier: str, items: Sequence[DocumentItemLine],
                  payments: Sequence[PaymentLine],
                  returns: Sequence[ReturnLine] = ()) -> RecordCard:
    status, tone = _return_status(
        purchase, payment_status_text(purchase), _payment_tone(purchase)
    )
    return RecordCard(
        kind="Purchase",
        reference=purchase.purchase_no,
        subtitle=f"{supplier} • {date_time(purchase.created_at)}",
        status=status,
        status_tone=tone,
        fields=(
            Field("Supplier", supplier),
            Field("Supplier reference", or_dash(purchase.reference_no)),
            Field("Recorded", date_time(purchase.created_at)),
            Field("Items", counted(len(purchase.items), "item")),
            *((Field("Returns", counted(_returns_made(returns), "return"), tone="warning"),)
              if returns else ()),
        ),
        sections=(
            _item_section("Items bought", items, "This purchase has no lines."),
            _payments_section("Payments made", payments),
            *((_returns_section("Goods sent back", returns),) if returns else ()),
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


def ledger_card(ledger, *, party_kind: str, period_label: str, sides) -> RecordCard:
    """A party's account as a statement, ready to hand over or post.

    `sides` maps `(charge, payment)` to `(debit, credit)` and is the
    caller's to supply: a sale is a debit on a customer's statement and a
    purchase is a credit on a supplier's, and that is the only difference
    between the two. One function so the lines and the totals cannot
    disagree about which side they are on.

    The opening balance leads the table as a line of its own. Without it
    the first running balance appears to come from nowhere, which is the
    first thing anyone checking a statement asks about.
    """
    # No date and no document of its own: it is what was carried in.
    opening_row = (DASH, DASH, "Opening balance", "", "", money(ledger.opening_balance))
    total_debit, total_credit = sides(ledger.total_charges, ledger.total_payments)
    return RecordCard(
        kind="Account statement",
        reference=ledger.party_name,
        subtitle=f"{party_kind} • {period_label}",
        fields=(
            Field(party_kind, ledger.party_name),
            Field("Period", period_label),
            Field("Opening balance", money(ledger.opening_balance)),
            Field("Entries", counted(len(ledger.lines), "entry", "entries")),
        ),
        sections=(
            Section(
                title="Account activity",
                headings=_LEDGER_HEADINGS,
                rows=(
                    opening_row,
                    *(
                        (
                            date_time(line.occurred_at),
                            or_dash(line.reference),
                            line.detail,
                            *(
                                money_or_blank(amount)
                                for amount in sides(line.charge, line.payment)
                            ),
                            money(line.balance),
                        )
                        for line in ledger.lines
                    ),
                ),
                empty="Nothing happened on this account in this period.",
            ),
        ),
        totals=(
            Total("Opening balance", money(ledger.opening_balance), tone="muted"),
            Total("Debit", money(total_debit)),
            Total("Credit", money(total_credit)),
            Total(
                "Closing balance",
                money(ledger.closing_balance),
                tone="success" if ledger.closing_balance <= _ZERO else "danger",
                strong=True,
            ),
        ),
    )


_COST_NOTE = (
    "Cost is the average price the stock had been bought at, recorded on each "
    "sale as it was raised. Discounts given on a whole purchase are not "
    "apportioned to it, so cost runs a little high."
)


def profit_and_loss_card(report, *, period_label: str) -> RecordCard:
    """A period's trading, as an income statement.

    Deliberately the same card as a document. A report is a heading, some
    facts, a table and a column of totals like everything else, so it
    prints through the same page and needs no second design.
    """
    net = report.net_profit
    caveat = uncosted_caveat(report.uncosted_lines, report.uncosted_revenue)
    return RecordCard(
        kind="Profit & loss",
        reference=period_label,
        subtitle=f"{date_only(report.start)} to {date_only(report.end)}",
        fields=(
            Field("Invoices raised", counted(report.invoice_count, "invoice")),
            Field("Gross margin", percent(report.gross_margin)),
            # Beside the figures rather than among them: buying stock is
            # not a cost of this period, it is money moved into it.
            Field("Stock bought", money(report.stock_bought), tone="muted"),
            Field("Invoice discounts", money(report.invoice_discounts), tone="muted"),
            *(
                (Field("Lines with no cost", counted(report.uncosted_lines, "line"),
                       tone="warning"),)
                if caveat
                else ()
            ),
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
                    (row.name, str(row.count), money(row.total), f"{row.share}%")
                    for row in report.spending
                ),
                empty="Nothing was spent in this period.",
            ),
        ),
        totals=(
            Total("Revenue", money(report.revenue)),
            Total("Cost of goods sold", money(report.cost_of_goods_sold), tone="muted"),
            Total("Gross profit", money(report.gross_profit)),
            Total("Expenses", money(report.expenses_total), tone="muted"),
            Total(
                "Net profit",
                money(net),
                tone="success" if net >= _ZERO else "danger",
                strong=True,
            ),
        ),
        note=f"{caveat} {_COST_NOTE}".strip(),
    )


def item_profitability_card(report, *, period_label: str) -> RecordCard:
    """What each item earned over a period."""
    return RecordCard(
        kind="Item profitability",
        reference=period_label,
        subtitle=f"{date_only(report.start)} to {date_only(report.end)}",
        fields=(
            Field("Items sold", counted(len(report.rows), "item")),
            Field("Margin", percent(report.margin)),
            *(
                (Field("Lines with no cost", counted(report.uncosted_lines, "line"),
                       tone="warning"),)
                if report.uncosted_lines
                else ()
            ),
        ),
        sections=(
            Section(
                title="Items sold",
                headings=(
                    Heading("ITEM"),
                    Heading("QTY SOLD", "right", 100),
                    Heading("REVENUE", "right", 130),
                    Heading("COST", "right", 130),
                    Heading("PROFIT", "right", 130),
                    Heading("MARGIN", "right", 100),
                ),
                # A dash where a cost was never recorded — never a zero,
                # which would read as free stock and a perfect margin.
                rows=tuple(
                    (
                        row.name,
                        f"{row.quantity_sold:,}",
                        money(row.revenue),
                        money(row.cost),
                        money(row.profit),
                        percent(row.margin),
                    )
                    for row in report.rows
                ),
                empty="Nothing was sold in this period.",
            ),
        ),
        totals=(
            Total("Revenue", money(report.revenue)),
            Total("Cost", money(report.cost), tone="muted"),
            Total(
                "Profit",
                money(report.profit),
                tone="success" if report.profit >= _ZERO else "danger",
                strong=True,
            ),
        ),
        note=(
            "A dash means the item had never been bought, so what it cost is "
            "not known and no margin can be worked out for it. Revenue here is "
            "line totals; a discount given on a whole invoice belongs to the "
            f"invoice, not to any one item on it. {_COST_NOTE}"
        ),
    )


def ageing_card(report, *, title: str, party_noun: str) -> RecordCard:
    """What is outstanding, and how long it has been."""
    return RecordCard(
        kind=title,
        reference=f"as at {date_only(report.as_at)}",
        subtitle=counted(len(report.lines), "document"),
        fields=tuple(
            Field(band.label, money(band.total)) for band in report.bands
        ),
        sections=(
            Section(
                title="Outstanding documents",
                headings=(
                    Heading(party_noun.upper()),
                    Heading("REFERENCE", width=150),
                    Heading("RAISED", width=170),
                    Heading("AGE", "right", 100),
                    Heading("BAND", width=130),
                    Heading("OUTSTANDING", "right", 140),
                ),
                rows=tuple(
                    (
                        line.party,
                        line.reference,
                        date_time(line.occurred_at),
                        counted(line.age_days, "day"),
                        line.band,
                        money(line.outstanding),
                    )
                    for line in report.lines
                ),
                empty="Nothing is outstanding.",
            ),
        ),
        totals=(Total("Total outstanding", money(report.total), strong=True),),
        note=(
            "Aged from the day each document was raised. This app records no "
            "payment terms, so these are ages, not overdue periods."
        ),
    )
