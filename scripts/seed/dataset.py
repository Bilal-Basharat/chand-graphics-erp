"""
What a seeded database is made of: plain values, nothing else.

No database, no use cases, no absolute dates. A day is written as *how
many days ago*, so a seeded database always lands in a sensible window
around whenever it was seeded rather than drifting further into the past
every month this file is not touched.

Two kinds of data live here, and the split is the point:

* **Fixtures** — one of every case a screen has to be able to draw: a
  part-paid invoice, a bill with nothing paid against it, a walk-in sale
  with no customer, a payment received a month after the invoice it
  settles, a customer who is in credit, an item that is genuinely low on
  stock. Written out by hand so they are always present, always the same,
  and can be pointed at in a bug report.
* **Filler** — routine months of trading generated from the same
  catalogue, so lists, period selectors and reports have volume to work
  with. Deterministic: the same seed always produces the same database.

Prices live on the catalogue rather than on every line, so a document
that trades at the usual price says nothing about price at all.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from random import Random

from app.config import constants

CURRENCY = Decimal("0.01")
"""What money rounds to. Every amount here is quantized to it."""


class Profile(StrEnum):
    """How much data to make."""

    SMOKE = "smoke"
    """Fixtures only — a handful of documents, seeded in a second."""

    DEMO = "demo"
    """Fixtures plus half a year of trading."""

    LOAD = "load"
    """Fixtures plus enough volume for load/performance testing."""


# ---------------------------------------------------------------- shapes


@dataclass(frozen=True, slots=True)
class NamedSeed:
    """Master data that is a name and a line about it — cabinets by code,
    expense categories by name."""

    name: str
    description: str | None = None


@dataclass(frozen=True, slots=True)
class PartySeed:
    name: str
    phone: str | None = None
    address: str | None = None
    opening_balance: Decimal = Decimal("0.00")
    """What they owed, or were owed, before the app was installed.
    Negative means the account is in credit."""
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class ItemSeed:
    name: str
    unit: str
    cabinet: str
    """Cabinet code. Every item here is filed; the app allows unfiled ones."""
    opening_stock: int
    """What was on the shelf before any of this was recorded. It arrives
    as a counted-in stock adjustment, because the app refuses to let a new
    item be created with stock already on it."""
    minimum_stock: int
    cost_price: Decimal
    """What it is bought at — the default price on a purchase line."""
    sale_price: Decimal
    """What it is sold at — the default price on a sale line."""
    quantity_sold: tuple[int, int]
    """The range a filler sale line draws from."""
    bought: bool = True
    sold: bool = True
    """Whether filler documents may buy or sell this item. An ink is
    bought and consumed, never resold; the foil roll is neither, so that
    the low-stock screen always has something to show."""

    @property
    def quantity_bought(self) -> tuple[int, int]:
        """A shop buys in bigger lots than it sells out of them."""
        low, high = self.quantity_sold
        return low * _PURCHASE_LOT, high * _PURCHASE_LOT


@dataclass(frozen=True, slots=True)
class LineSeed:
    item: str
    quantity: int
    unit_price: Decimal | None = None
    """None means the catalogue price for whichever side of the trade
    this line is on."""


@dataclass(frozen=True, slots=True)
class PaymentSeed:
    days_ago: int
    amount: Decimal
    method: str | None = None
    """A payment method by name. None is cash over the counter, which is
    what the app shows when nothing is recorded — most payments here."""


@dataclass(frozen=True, slots=True)
class DocumentSeed:
    """A sale or a purchase. The two are the same shape, so they are the
    same record here and are told apart by which list they are in."""

    reference: str
    """Invoice number or purchase number."""
    party: str | None
    """Customer or supplier by name. None is a walk-in sale or a counter
    purchase with nobody to bill."""
    days_ago: int
    lines: tuple[LineSeed, ...]
    payments: tuple[PaymentSeed, ...] = ()
    discount: Decimal = Decimal("0.00")
    reference_no: str | None = None
    """The other party's own document number, on purchases."""
    note: str | None = None

    def __post_init__(self) -> None:
        if not self.lines:
            raise ValueError(f"{self.reference}: a document needs at least one line")
        for payment in self.payments:
            # Larger days_ago is further back, so a payment may not have a
            # larger one than the document it settles.
            if payment.days_ago > self.days_ago:
                raise ValueError(
                    f"{self.reference}: paid {payment.days_ago} days ago, "
                    f"before the document dated {self.days_ago} days ago"
                )


@dataclass(frozen=True, slots=True)
class ExpenseSeed:
    name: str
    category: str
    days_ago: int
    amount: Decimal | None = None
    quantity: int | None = None
    unit_price: Decimal | None = None
    """An expense is either one amount or a quantity at a price. The app
    accepts both, so both are seeded."""
    remarks: str | None = None


@dataclass(frozen=True, slots=True)
class MovementSeed:
    """Stock that moved without a document — damage, a return, a count
    correction."""

    item: str
    movement_type: str
    quantity_change: int
    days_ago: int
    reason: str | None = None
    note: str | None = None


@dataclass(frozen=True, slots=True)
class AuditSeed:
    """One line of the sign-in history.

    Seeded because nothing else writes any: a seeding run signs in once
    and deliberately leaves no trace, so without these the history screen
    has a single row and its paging is never exercised.
    """

    email: str
    event_type: str
    success: bool
    days_ago: int
    message: str | None = None


@dataclass(frozen=True, slots=True)
class CompanySeed:
    company_name: str
    phone: str
    email: str
    address: str
    invoice_footer: str


@dataclass(frozen=True, slots=True)
class Dataset:
    company: CompanySeed
    cabinets: tuple[NamedSeed, ...]
    payment_methods: tuple[str, ...]
    expense_categories: tuple[NamedSeed, ...]
    customers: tuple[PartySeed, ...]
    suppliers: tuple[PartySeed, ...]
    items: tuple[ItemSeed, ...]
    purchases: tuple[DocumentSeed, ...]
    sales: tuple[DocumentSeed, ...]
    expenses: tuple[ExpenseSeed, ...]
    movements: tuple[MovementSeed, ...]
    audits: tuple[AuditSeed, ...] = ()


# ---------------------------------------------------------------- master data

COMPANY = CompanySeed(
    company_name="Chand Graphics",
    phone="042-37654321",
    email="info@chandgraphics.test",
    address="12 Circular Road, Lahore",
    invoice_footer="Thank you for your business.",
)

CABINETS = (
    NamedSeed("A1", "Paper store"),
    NamedSeed("B2", "Ink shelf"),
    NamedSeed("C3", "Finishing rack"),
)

# No "Cash" here on purpose: a payment with no method recorded already
# reads as cash everywhere in the app, and a row by that name would make
# two ways of saying the same thing.
PAYMENT_METHODS = ("Bank transfer", "Easypaisa", "Cheque", "Card")

EXPENSE_CATEGORIES = (
    NamedSeed("Rent", "Shop and store rent"),
    NamedSeed("Utilities", "Electricity, gas, internet"),
    NamedSeed("Salaries", "Staff wages"),
    NamedSeed("Transport", "Deliveries and fuel"),
    NamedSeed("Machine maintenance", "Press and cutter servicing"),
    NamedSeed("Miscellaneous", None),
)

CUSTOMERS = (
    PartySeed(
        "Ahmad Traders",
        "0300-4412233",
        "Shop 14, Urdu Bazaar, Lahore",
        Decimal("45000.00"),
        notes="Carried over from the old register.",
    ),
    PartySeed("Al-Noor Printers", "0321-7788990", "Township, Lahore"),
    # In credit: they paid an advance before the app was installed.
    PartySeed(
        "Bilal Stationers",
        "0333-1122334",
        "Main Market, Gujranwala",
        Decimal("-12500.00"),
    ),
    PartySeed("City School System", "042-35881122", "Model Town, Lahore"),
    PartySeed("Decent Marriage Hall", "0301-9988776", "Ferozepur Road, Lahore", Decimal("8000.00")),
    PartySeed("Faisal Book Depot", "0345-6677889", "Anarkali, Lahore"),
)

SUPPLIERS = (
    PartySeed(
        "Packages Paper Mill",
        "042-35991100",
        "Kot Lakhpat, Lahore",
        Decimal("60000.00"),
        notes="Monthly account, settled by cheque.",
    ),
    PartySeed("Ink World Karachi", "021-32334455", "SITE Area, Karachi"),
    # We are in credit with them — an advance already sent.
    PartySeed("Lahore Foil & Lamination", "0302-5566778", "Badami Bagh, Lahore", Decimal("-5000.00")),
    PartySeed("Metro Board Suppliers", "0311-2233445", "Shahdara, Lahore"),
)

_PURCHASE_LOT = 5

ITEMS = (
    ItemSeed("Art Card 250gsm (23x36)", "sheets", "A1", 40_000, 2_000,
             Decimal("38.00"), Decimal("55.00"), (25, 150)),
    ItemSeed("Matt Paper 130gsm (20x30)", "sheets", "A1", 60_000, 3_000,
             Decimal("12.50"), Decimal("20.00"), (50, 400)),
    ItemSeed("Offset Paper 70gsm (23x36)", "sheets", "A1", 120_000, 5_000,
             Decimal("6.75"), Decimal("11.00"), (200, 1_500)),
    ItemSeed("Cyan Offset Ink 1kg", "tins", "B2", 45, 10,
             Decimal("1450.00"), Decimal("1900.00"), (2, 6), sold=False),
    ItemSeed("Black Offset Ink 1kg", "tins", "B2", 60, 12,
             Decimal("1250.00"), Decimal("1700.00"), (2, 8), sold=False),
    ItemSeed("Lamination Roll 12in", "rolls", "C3", 400, 10,
             Decimal("2600.00"), Decimal("3400.00"), (1, 4)),
    ItemSeed("Binding Wire Spool", "spools", "C3", 600, 20,
             Decimal("850.00"), Decimal("1200.00"), (2, 10)),
    # Below its own minimum and kept out of every document, so the
    # low-stock screen is never empty.
    ItemSeed("Gold Foil Roll 6in", "rolls", "C3", 3, 6,
             Decimal("4200.00"), Decimal("5500.00"), (1, 2), bought=False, sold=False),
)


# ---------------------------------------------------------------- fixtures

FIXTURE_PURCHASES = (
    # The oldest bill in the file, and the only one Metro Board appears
    # on. It is here so the paper that sells most is costed from near the
    # start: without a purchase behind it, every sale of an item reports
    # unknown margin, and a demo where a fifth of the revenue is uncosted
    # reads as a broken report rather than an honest one.
    DocumentSeed(
        reference="PUR-1000",
        party="Metro Board Suppliers",
        days_ago=170,
        lines=(LineSeed("Matt Paper 130gsm (20x30)", 8_000),),
        reference_no="MB/2291",
        payments=(PaymentSeed(days_ago=170, amount=Decimal("100000.00"), method="Cheque"),),
    ),
    # Settled in two goes, the second nearly two weeks after the bill.
    DocumentSeed(
        reference="PUR-1001",
        party="Packages Paper Mill",
        days_ago=150,
        lines=(
            LineSeed("Art Card 250gsm (23x36)", 1_000),
            LineSeed("Offset Paper 70gsm (23x36)", 5_000),
        ),
        discount=Decimal("750.00"),
        reference_no="PM/4471",
        payments=(
            PaymentSeed(days_ago=150, amount=Decimal("40000.00"), method="Bank transfer"),
            PaymentSeed(days_ago=138, amount=Decimal("31000.00"), method="Cheque"),
        ),
    ),
    # Part paid — leaves a supplier balance standing.
    DocumentSeed(
        reference="PUR-1002",
        party="Ink World Karachi",
        days_ago=95,
        lines=(
            LineSeed("Cyan Offset Ink 1kg", 20),
            LineSeed("Black Offset Ink 1kg", 25),
        ),
        payments=(PaymentSeed(days_ago=95, amount=Decimal("30000.00"), method="Bank transfer"),),
    ),
    # No supplier at all: bought over the counter, paid on the spot.
    DocumentSeed(
        reference="PUR-1003",
        party=None,
        days_ago=40,
        lines=(LineSeed("Binding Wire Spool", 10),),
        payments=(PaymentSeed(days_ago=40, amount=Decimal("8500.00")),),
        note="Bought over the counter.",
    ),
    # Nothing paid against it yet.
    DocumentSeed(
        reference="PUR-1004",
        party="Lahore Foil & Lamination",
        days_ago=12,
        lines=(LineSeed("Lamination Roll 12in", 10),),
    ),
)

FIXTURE_SALES = (
    DocumentSeed(
        reference="INV-2001",
        party="Ahmad Traders",
        days_ago=120,
        lines=(
            LineSeed("Art Card 250gsm (23x36)", 200),
            LineSeed("Matt Paper 130gsm (20x30)", 500),
        ),
        payments=(PaymentSeed(days_ago=120, amount=Decimal("21000.00")),),
    ),
    # The ledger case: a payment received forty days after the invoice, so
    # the two fall in different periods.
    DocumentSeed(
        reference="INV-2002",
        party="Al-Noor Printers",
        days_ago=60,
        lines=(LineSeed("Offset Paper 70gsm (23x36)", 3_000),),
        payments=(
            PaymentSeed(days_ago=60, amount=Decimal("15000.00"), method="Bank transfer"),
            PaymentSeed(days_ago=20, amount=Decimal("10000.00"), method="Easypaisa"),
        ),
    ),
    # Walk-in: belongs to no customer, so it must appear on no ledger.
    DocumentSeed(
        reference="INV-2003",
        party=None,
        days_ago=30,
        lines=(
            LineSeed("Matt Paper 130gsm (20x30)", 100),
            LineSeed("Binding Wire Spool", 2),
        ),
        payments=(PaymentSeed(days_ago=30, amount=Decimal("4400.00")),),
    ),
    # Unpaid, against a customer who was in credit — their balance crosses
    # from negative to positive.
    DocumentSeed(
        reference="INV-2004",
        party="Bilal Stationers",
        days_ago=8,
        lines=(LineSeed("Lamination Roll 12in", 4),),
    ),
    # Discounted and part paid.
    DocumentSeed(
        reference="INV-2005",
        party="City School System",
        days_ago=3,
        lines=(
            LineSeed("Offset Paper 70gsm (23x36)", 2_000),
            LineSeed("Art Card 250gsm (23x36)", 150),
        ),
        discount=Decimal("250.00"),
        payments=(PaymentSeed(days_ago=3, amount=Decimal("10000.00"), method="Cheque"),),
        note="School order — balance on delivery.",
    ),
)

FIXTURE_EXPENSES = (
    # Priced by quantity rather than as one amount.
    ExpenseSeed(
        name="Cutter blade replacement",
        category="Machine maintenance",
        days_ago=70,
        quantity=3,
        unit_price=Decimal("4500.00"),
        remarks="Three blades, one spare.",
    ),
    ExpenseSeed(
        name="Shop sign repainting",
        category="Miscellaneous",
        days_ago=25,
        amount=Decimal("14500.00"),
    ),
)

FIXTURE_MOVEMENTS = (
    MovementSeed(
        item="Matt Paper 130gsm (20x30)",
        movement_type="DAMAGE",
        quantity_change=-250,
        days_ago=45,
        reason="Water damage in the store",
    ),
    MovementSeed(
        item="Binding Wire Spool",
        movement_type="ADJUSTMENT",
        quantity_change=6,
        days_ago=20,
        reason="Stock count correction",
    ),
    MovementSeed(
        item="Art Card 250gsm (23x36)",
        movement_type="RETURN",
        quantity_change=-100,
        days_ago=33,
        note="Sent back to the mill — wrong shade.",
    ),
)


# ---------------------------------------------------------------- filler

_FILLER_MONTHS: dict[Profile, int] = {
    Profile.SMOKE: 0,
    Profile.DEMO: 6,
    Profile.LOAD: 34,
}

_SALES_PER_MONTH: dict[Profile, int] = {
    Profile.SMOKE: 0,
    Profile.DEMO: 18,
    # Two invoices a day, near enough: enough to page through and enough
    # that a total over a period is not a figure anyone could add up by
    # eye from the rows on screen.
    Profile.LOAD: 60,
}

_PURCHASES_PER_MONTH: dict[Profile, int] = {
    Profile.SMOKE: 0,
    Profile.DEMO: 3,
    # Fewer than the sales, as a shop buys in lots and sells out of them.
    Profile.LOAD: 30,
}

_EXPENSES_PER_MONTH: dict[Profile, int] = {
    Profile.SMOKE: 0,
    Profile.DEMO: 5,
    Profile.LOAD: 30,
}

_DAYS_PER_MONTH = 30

# Mostly cash over the counter, which is how a shop like this is paid.
_METHOD_CHOICES = (None, None, None, None, "Bank transfer", "Easypaisa", "Cheque", "Card")

# What the same item goes out at on a good day and a bad one.
_PRICE_JITTER = (Decimal("0.95"), Decimal("1.00"), Decimal("1.00"), Decimal("1.05"), Decimal("1.10"))

_ROUTINE_EXPENSES = (
    ("Electricity bill", "Utilities", 9_000, 21_000),
    ("Internet bill", "Utilities", 4_500, 4_500),
    ("Staff salaries", "Salaries", 42_000, 56_000),
    ("Delivery charges", "Transport", 1_500, 6_000),
    ("Press servicing", "Machine maintenance", 3_500, 12_000),
    ("Tea and refreshments", "Miscellaneous", 800, 3_000),
    ("Packing material", "Miscellaneous", 2_000, 9_000),
)
"""Sized against what the filler sales actually bill.

A shop turning over what this dataset turns over does not pay a
six-figure wage bill, and a demo that opens on a heavy loss teaches the
reader to distrust the report rather than read it.
"""

_MONTHLY_RENT = Decimal("28000.00")


def build(profile: Profile, rng: Random) -> Dataset:
    """The fixtures, plus as many months of filler as the profile asks for."""
    if profile is Profile.LOAD:
        return _build_load(rng)

    months = _FILLER_MONTHS[profile]

    return Dataset(
        company=COMPANY,
        cabinets=CABINETS,
        payment_methods=PAYMENT_METHODS,
        expense_categories=EXPENSE_CATEGORIES,
        customers=CUSTOMERS,
        suppliers=SUPPLIERS,
        items=ITEMS,
        purchases=FIXTURE_PURCHASES + _filler_purchases(profile, rng, months, ITEMS, SUPPLIERS),
        sales=FIXTURE_SALES + _filler_sales(profile, rng, months, ITEMS, CUSTOMERS),
        expenses=FIXTURE_EXPENSES + _filler_expenses(profile, rng, months),
        movements=FIXTURE_MOVEMENTS,
    )


def _filler_purchases(
    profile: Profile,
    rng: Random,
    months: int,
    items: tuple[ItemSeed, ...],
    suppliers: tuple[PartySeed, ...],
) -> tuple[DocumentSeed, ...]:
    catalogue = tuple(item for item in items if item.bought)
    parties = tuple(supplier.name for supplier in suppliers)
    documents: list[DocumentSeed] = []

    for index, days_ago in enumerate(_days(rng, months, _PURCHASES_PER_MONTH[profile])):
        lines = _lines(rng, catalogue, count=rng.randint(1, 2), selling=False)
        total = _total(lines)

        documents.append(
            DocumentSeed(
                reference=f"PUR-{1100 + index:04d}",
                party=rng.choice(parties),
                days_ago=days_ago,
                lines=lines,
                payments=_settlement(rng, total, days_ago),
            )
        )

    return tuple(documents)


def _filler_sales(
    profile: Profile,
    rng: Random,
    months: int,
    items: tuple[ItemSeed, ...],
    customers: tuple[PartySeed, ...],
) -> tuple[DocumentSeed, ...]:
    catalogue = tuple(item for item in items if item.sold)
    parties = tuple(customer.name for customer in customers)
    documents: list[DocumentSeed] = []

    for index, days_ago in enumerate(_days(rng, months, _SALES_PER_MONTH[profile])):
        lines = _lines(rng, catalogue, count=rng.randint(1, 3), selling=True)
        total = _total(lines)

        # Roughly one sale in eight is a walk-in with nobody to bill.
        party = None if rng.randint(1, 8) == 1 else rng.choice(parties)

        documents.append(
            DocumentSeed(
                reference=f"INV-{2100 + index:04d}",
                party=party,
                days_ago=days_ago,
                lines=lines,
                # A walk-in pays before they leave.
                payments=(
                    (PaymentSeed(days_ago=days_ago, amount=total, method=rng.choice(_METHOD_CHOICES)),)
                    if party is None
                    else _settlement(rng, total, days_ago)
                ),
            )
        )

    return tuple(documents)


def _filler_expenses(profile: Profile, rng: Random, months: int) -> tuple[ExpenseSeed, ...]:
    expenses: list[ExpenseSeed] = []
    per_month = min(_EXPENSES_PER_MONTH[profile], len(_ROUTINE_EXPENSES))

    for month in range(months):
        first, last = _month_bounds(month)

        expenses.append(
            ExpenseSeed(
                name="Shop rent",
                category="Rent",
                days_ago=last,
                amount=_MONTHLY_RENT,
            )
        )

        for name, category, low, high in rng.sample(_ROUTINE_EXPENSES, per_month):
            expenses.append(
                ExpenseSeed(
                    name=name,
                    category=category,
                    days_ago=rng.randint(first, last),
                    amount=Decimal(rng.randrange(low, high + 1, 50)).quantize(CURRENCY),
                )
            )

    return tuple(expenses)


def _days(rng: Random, months: int, per_month: int) -> list[int]:
    """One date per document, spread through each month, oldest first.

    Oldest first so that document numbers climb with time, the way a
    numbered book of invoices does.
    """
    days: list[int] = []
    for month in reversed(range(months)):
        first, last = _month_bounds(month)
        days.extend(sorted((rng.randint(first, last) for _ in range(per_month)), reverse=True))
    return days


def _month_bounds(month: int) -> tuple[int, int]:
    """How many days ago that month began and ended, newest month first."""
    return month * _DAYS_PER_MONTH + 1, (month + 1) * _DAYS_PER_MONTH


def _lines(rng: Random, catalogue: tuple[ItemSeed, ...], *, count: int, selling: bool) -> tuple[LineSeed, ...]:
    chosen = rng.sample(catalogue, min(count, len(catalogue)))
    return tuple(
        LineSeed(
            item=item.name,
            quantity=rng.randint(*(item.quantity_sold if selling else item.quantity_bought)),
            unit_price=_jittered(rng, item.sale_price if selling else item.cost_price),
        )
        for item in chosen
    )


def _jittered(rng: Random, price: Decimal) -> Decimal:
    return (price * rng.choice(_PRICE_JITTER)).quantize(CURRENCY)


def _total(lines: tuple[LineSeed, ...]) -> Decimal:
    # Filler lines always carry their own price, so the total is knowable
    # here — which is what lets a payment be written as a share of it.
    return sum(
        (line.unit_price * line.quantity for line in lines if line.unit_price is not None),
        Decimal("0.00"),
    ).quantize(CURRENCY)


def _settlement(rng: Random, total: Decimal, days_ago: int) -> tuple[PaymentSeed, ...]:
    """How this one got paid: on the spot, half now, half later, or not yet."""
    roll = rng.random()
    method = rng.choice(_METHOD_CHOICES)

    if roll < 0.55:
        return (PaymentSeed(days_ago=days_ago, amount=total, method=method),)

    half = (total / 2).quantize(CURRENCY)
    if roll < 0.75:
        # Settled later — the rest arrives somewhere between the document
        # and today, which is what puts a payment in a later period than
        # the document it belongs to.
        later = rng.randint(0, days_ago)
        return (
            PaymentSeed(days_ago=days_ago, amount=half, method=method),
            PaymentSeed(days_ago=later, amount=total - half, method=rng.choice(_METHOD_CHOICES)),
        )
    if roll < 0.90:
        return (PaymentSeed(days_ago=days_ago, amount=half, method=method),)
    return ()



# ---------------------------------------------------------------- load profile

# Volume, written as though a real shop had grown into it. The point of
# this profile is a database big enough that a screen has to page through
# it, and a screen full of "Load Item 00417" tells you nothing about
# whether it reads correctly at that size — a name has to be long enough
# to elide, a party has to be findable by typing part of it, and a column
# of them has to look like a column of records.
#
# Combined rather than random, so every name is unique without having to
# check: three lists multiplied out give more than a thousand of anything
# here, and the same seed always deals them in the same order.


def _dealt(rng: Random, *axes: tuple[str, ...]) -> list[tuple[str, ...]]:
    """Every combination of the axes, in a shuffled but repeatable order."""
    combinations = [()]
    for axis in axes:
        combinations = [(*prefix, value) for prefix in combinations for value in axis]
    rng.shuffle(combinations)
    return combinations


_PAPER = (
    "Art Card", "Matt Paper", "Offset Paper", "Ivory Board", "Duplex Board",
    "Kraft Paper", "Gloss Art Paper", "Bond Paper", "Textured Card",
    "Coated Board", "Newsprint", "Tracing Paper",
)
_WEIGHT = ("70gsm", "80gsm", "100gsm", "130gsm", "170gsm", "210gsm", "250gsm", "300gsm")
_SHEET = ("20x30", "23x36", "25x36", "19x25", "18x23", "22x28", "24x34", "26x38")

# Two families rather than one, because what a thing is decides both how
# it is described and how it is packed: an ink has a colour and comes in a
# tin, a roll has a width and comes on a core. Crossing all three lists
# produced "Cyan Lamination Roll 1kg tin", which is not a thing.
_LIQUID = ("Offset Ink", "UV Varnish", "Fountain Solution", "Blanket Wash", "Plate Cleaner")
_SHADE = (
    "Cyan", "Magenta", "Yellow", "Black", "Pantone 485", "Pantone 032",
    "Pantone 877", "Rich Black", "Warm Red", "Reflex Blue", "Process Green",
    "Opaque White",
)
_TIN = ("1kg tin", "2.5kg tin", "5kg drum", "20kg drum")

_ROLLED = ("Lamination Roll", "Binding Wire", "Foil Roll", "Thermal Ribbon", "Masking Tape")
_FINISH = ("Gloss", "Matte", "Soft Touch", "Gold", "Silver", "Holographic", "Clear")
_WIDTH = ("6in", "12in", "18in", "24in", "500m spool")

_HOUSE = (
    "Al-Noor", "Chand", "Faisal", "Gulberg", "Ittefaq", "Karim", "Madina",
    "Mehran", "New Star", "Pak", "Rehman", "Royal", "Sadiq", "Shalimar",
    "Sitara", "Usman", "Zeeshan", "Green Line", "Blue Dot", "Crescent",
)
_TRADE = (
    "Printers", "Press", "Publishers", "Stationers", "Book Depot", "Packaging",
    "Graphics", "Advertisers", "Card Centre", "Print House",
)
_CITY = (
    "Lahore", "Karachi", "Faisalabad", "Multan", "Gujranwala", "Sialkot",
    "Rawalpindi", "Sargodha", "Bahawalpur", "Sahiwal",
)

_MILL = (
    "Packages", "Century", "Bulleh Shah", "Roshan", "Indus", "Ravi", "Chenab",
    "Khyber", "Sapphire", "Nishat", "Crescent", "Ittehad", "Pioneer", "Falcon",
)
_SUPPLY = (
    "Paper Mill", "Board Mills", "Ink House", "Chemicals", "Paper Mart",
    "Trading Co", "Enterprises", "Suppliers", "Agencies", "Impex",
)

_BANK = (
    "HBL", "Meezan", "UBL", "Bank Alfalah", "MCB", "Askari", "Faysal",
    "Standard Chartered", "JS Bank", "Bank of Punjab", "Soneri", "Summit",
)
_ACCOUNT = ("Current", "Savings", "Business", "Counter", "Deposit", "Cheque")
_BRANCH = (
    "Circular Road", "Urdu Bazaar", "Township", "Model Town", "Anarkali",
    "Shahdara", "Gulberg", "Kot Lakhpat", "Badami Bagh", "Cantt", "Ravi Road",
    "Mall Road", "Garden Town", "Johar Town",
)

_EXPENSE_CATEGORY_NAMES: tuple[str, ...] = (
    "Shop rent",
    "Electricity bill",
    "Gas bill",
    "Water bill",
    "Internet bill",
    "Telephone bill",
    "Staff salaries",
    "Overtime",
    "Transport",
    "Fuel",
    "Courier",
    "Machine maintenance",
    "Printing plates",
    "Blankets and rollers",
    "Chemicals",
    "Packing material",
    "Office supplies",
    "Repairs",
    "Insurance",
    "Marketing",
    "Bank charges",
    "Cleaning",
    "Security",
    "Waste disposal",
    "Tea and refreshments",
    "Stationery",
    "Licences and permits",
    "Software subscriptions",
    "Training",
    "Spare parts",
)

_ROOM = ("Paper store", "Ink shelf", "Finishing rack", "Board store", "Plate room",
         "Dispatch bay", "Overflow store", "Cold store")


def _load_cabinets(count: int, rng: Random) -> tuple[NamedSeed, ...]:
    """Codes, which is what a cabinet is. The room it stands in only
    describes it, so it is chosen from the code rather than multiplied
    through it — two cabinets called A-07 would be one cabinet twice."""
    letters = tuple("ABCDEFGHJKLMNPQRSTUVWXYZ")
    numbers = tuple(f"{n:02d}" for n in range(1, 46))
    return tuple(
        NamedSeed(
            name=f"{letter}-{number}",
            description=f"{_ROOM[index % len(_ROOM)]}, rack {number}",
        )
        for index, (letter, number) in enumerate(_dealt(rng, letters, numbers)[:count])
    )


def _load_payment_methods(count: int, rng: Random) -> tuple[str, ...]:
    return tuple(
        f"{bank} {account} — {branch}"
        for (bank, account, branch) in _dealt(rng, _BANK, _ACCOUNT, _BRANCH)[:count]
    )


def _load_expense_categories(count: int, rng: Random) -> tuple[NamedSeed, ...]:
    """Curated expense categories — no generated combinations."""
    fixture_names = {cat.name for cat in EXPENSE_CATEGORIES}
    available = [n for n in _EXPENSE_CATEGORY_NAMES if n not in fixture_names]
    rng.shuffle(available)
    return tuple(NamedSeed(name=n) for n in available[:count])


def _phone(rng: Random) -> str:
    return f"03{rng.randrange(0, 60):02d}-{rng.randrange(1000000, 9999999)}"


def _load_customers(count: int, rng: Random) -> tuple[PartySeed, ...]:
    return tuple(
        PartySeed(
            name=f"{house} {trade}, {city}",
            phone=_phone(rng),
            address=f"{rng.randrange(1, 400)} {rng.choice(_BRANCH)}, {city}",
            # A few accounts carried over, and a couple in credit, so the
            # ageing and ledger screens have something to show at volume.
            opening_balance=_opening_balance(rng),
            notes=None,
        )
        for (house, trade, city) in _dealt(rng, _HOUSE, _TRADE, _CITY)[:count]
    )


def _load_suppliers(count: int, rng: Random) -> tuple[PartySeed, ...]:
    return tuple(
        PartySeed(
            name=f"{mill} {supply}, {city}",
            phone=_phone(rng),
            address=f"{rng.choice(_BRANCH)}, {city}",
            opening_balance=_opening_balance(rng),
            notes=None,
        )
        for (mill, supply, city) in _dealt(rng, _MILL, _SUPPLY, _CITY)[:count]
    )


def _opening_balance(rng: Random) -> Decimal:
    roll = rng.random()
    if roll < 0.75:
        return Decimal("0.00")
    amount = Decimal(rng.randrange(2_500, 90_000, 500))
    # One in ten of the rest is in credit — they paid ahead.
    return (-amount if roll > 0.97 else amount).quantize(CURRENCY)


def _load_items(
    count: int,
    cabinet_codes: tuple[str, ...],
    rng: Random,
) -> tuple[ItemSeed, ...]:
    sheets = [
        (f"{paper} {weight} ({sheet})", "sheets", (25, 400), 60_000, (500, 9_000))
        for (paper, weight, sheet) in _dealt(rng, _PAPER, _WEIGHT, _SHEET)
    ]
    liquids = [
        (f"{shade} {liquid} {tin}", tin.split()[-1] + "s", (1, 8), 300, (65_000, 700_000))
        for (liquid, shade, tin) in _dealt(rng, _LIQUID, _SHADE, _TIN)
    ]
    rolls = [
        (f"{finish} {rolled} {width}", "rolls", (1, 6), 250, (90_000, 900_000))
        for (rolled, finish, width) in _dealt(rng, _ROLLED, _FINISH, _WIDTH)
    ]
    # Paper first: it is what a print shop mostly keeps, and it is the
    # family whose names are long enough to test a column that elides.
    # Anything a fixture already named is dropped — the fixtures are hand
    # written from the same vocabulary, and the app refuses a second item
    # by the same name.
    taken = {item.name for item in ITEMS}
    catalogue = [row for row in sheets + liquids + rolls if row[0] not in taken][:count]

    items = []
    for index, (name, unit, sold_range, stock, price_range) in enumerate(catalogue):
        # Priced by what it is: a sheet of paper is rupees and a drum of
        # varnish is thousands, and one range across both would put a
        # column of nonsense in front of whoever is reading the screen.
        cost_price = (
            Decimal(rng.randrange(price_range[0], price_range[1], 25)) / Decimal(100)
        ).quantize(CURRENCY)
        items.append(
            ItemSeed(
                name=name,
                unit=unit,
                cabinet=cabinet_codes[index % len(cabinet_codes)],
                opening_stock=stock,
                minimum_stock=max(1, stock // 20),
                cost_price=cost_price,
                sale_price=(cost_price * Decimal("1.40")).quantize(CURRENCY),
                quantity_sold=sold_range,
                bought=True,
                sold=True,
            )
        )
    return tuple(items)


_BIG_SPEND = frozenset(
    {"Shop rent", "Staff salaries", "Electricity bill", "Insurance", "Equipment hire"}
)
"""What a shop pays in tens of thousands rather than hundreds. A single
range across every kind put a two-hundred-rupee rent on the screen."""


def _load_expenses(
    rng: Random,
    months: int,
    per_month: int,
    categories: tuple[NamedSeed, ...],
) -> tuple[ExpenseSeed, ...]:
    expenses: list[ExpenseSeed] = []
    for days_ago in _days(rng, months, per_month):
        category = rng.choice(categories)
        low, high = (
            (2_000_000, 25_000_000)
            if category.name in _BIG_SPEND
            else (50_000, 2_500_000)
        )
        amount = (Decimal(rng.randrange(low, high, 50)) / Decimal(100)).quantize(CURRENCY)
        expenses.append(
            ExpenseSeed(
                name=category.name,
                category=category.name,
                days_ago=days_ago,
                amount=amount,
            )
        )
    return tuple(expenses)


_SIGN_INS = (
    ("sign_in_success", True, None),
    ("sign_in_success", True, None),
    ("sign_in_success", True, None),
    ("session_restored", True, None),
    ("sign_out", True, None),
    ("sign_out", True, None),
    ("sign_in_failure", False, "Invalid email or password"),
    ("password_changed", True, None),
)
"""Mostly ordinary days, with the occasional mistyped password — which is
the row the screen exists to make findable. Written as the enum's own
values, so an event nobody records cannot be seeded."""


def _load_audits(rng: Random, months: int, per_month: int, email: str) -> tuple[AuditSeed, ...]:
    return tuple(
        AuditSeed(
            email=email,
            event_type=event,
            success=success,
            days_ago=days_ago,
            message=message,
        )
        for days_ago in _days(rng, months, per_month)
        for event, success, message in (rng.choice(_SIGN_INS),)
    )


def _build_load(rng: Random) -> Dataset:
    cabinets = CABINETS + _load_cabinets(1_000, rng)
    payment_methods = PAYMENT_METHODS + _load_payment_methods(1_000, rng)

    # 10–100+ expense categories: 6 fixtures + 30 load = 36 total
    expense_categories = EXPENSE_CATEGORIES + _load_expense_categories(30, rng)

    # 100+ customers: 6 fixtures + 120 load = 126 total
    customers = CUSTOMERS + _load_customers(120, rng)

    # 100+ suppliers: 4 fixtures + 120 load = 124 total
    suppliers = SUPPLIERS + _load_suppliers(120, rng)

    cabinet_codes = tuple(cabinet.name for cabinet in cabinets)
    items = ITEMS + _load_items(1_200, cabinet_codes, rng)

    months = _FILLER_MONTHS[Profile.LOAD]
    purchases = (
        FIXTURE_PURCHASES
        + _filler_purchases(Profile.LOAD, rng, months, items, suppliers)
    )
    sales = (
        FIXTURE_SALES
        + _filler_sales(Profile.LOAD, rng, months, items, customers)
    )
    expenses = (
        FIXTURE_EXPENSES
        + _load_expenses(
            rng,
            months,
            _EXPENSES_PER_MONTH[Profile.LOAD],
            expense_categories,
        )
    )
    return Dataset(
        company=COMPANY,
        cabinets=cabinets,
        payment_methods=payment_methods,
        expense_categories=expense_categories,
        customers=customers,
        suppliers=suppliers,
        items=items,
        purchases=purchases,
        sales=sales,
        expenses=expenses,
        movements=FIXTURE_MOVEMENTS,
        audits=_load_audits(rng, months, 30, constants.DEFAULT_ADMIN_EMAIL),
    )
