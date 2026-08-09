"""
Shared date-range filter for the screens that read by period — the
dashboard, sales, purchases, both payment lists, expenses and reports.

One list of presets, used everywhere: "this month" has to mean the same
month on every screen, and a screen that grew its own copy would be the
one that drifted.

`PeriodSelection` is a small mutable holder rather than state inside the
view: a view model's query callable needs to read the current period, and
the selector widget needs to write it, but neither should own the other.
Both are handed the same `PeriodSelection`, which keeps the wiring a
straight line instead of a cycle.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta

from PySide6.QtCore import Signal

from app.shared.datetimes import now_pkt
from PySide6.QtWidgets import QComboBox, QWidget

from app.application.dto.commands import DateRangeQuery

# Well before any record this app could hold — an "all time" lower bound
# that avoids datetime.min, which some drivers refuse to bind.
_EPOCH = datetime(1970, 1, 1)


def _month_start(moment: datetime) -> datetime:
    return moment.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _day_start(moment: datetime) -> datetime:
    return moment.replace(hour=0, minute=0, second=0, microsecond=0)


def _today(now: datetime) -> tuple[datetime, datetime]:
    return _day_start(now), now


def _this_week(now: datetime) -> tuple[datetime, datetime]:
    # From Monday, which is where the working week starts here — not a
    # rolling seven days, which would answer a different question.
    return _day_start(now) - timedelta(days=now.weekday()), now


def _this_month(now: datetime) -> tuple[datetime, datetime]:
    return _month_start(now), now


def _last_month(now: datetime) -> tuple[datetime, datetime]:
    this_month_start = _month_start(now)
    last_month_end = this_month_start - timedelta(microseconds=1)
    return _month_start(last_month_end), last_month_end


def _last_three_months(now: datetime) -> tuple[datetime, datetime]:
    start = _month_start(now)
    for _ in range(2):
        start = _month_start(start - timedelta(days=1))
    return start, now


def _this_year(now: datetime) -> tuple[datetime, datetime]:
    return now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0), now


def _all_time(now: datetime) -> tuple[datetime, datetime]:
    return _EPOCH, now


_PRESETS: list[tuple[str, Callable[[datetime], tuple[datetime, datetime]]]] = [
    ("Today", _today),
    ("This week", _this_week),
    ("This month", _this_month),
    ("Last month", _last_month),
    ("Last 3 months", _last_three_months),
    ("This year", _this_year),
    ("All time", _all_time),
]

DEFAULT_PRESET_LABEL = "This month"
"""What every screen opens on. A month is the period the shop already
thinks in — its bills, its stock runs and its balances all land there."""

DEFAULT_PRESET_INDEX = next(
    index for index, (label, _) in enumerate(_PRESETS) if label == DEFAULT_PRESET_LABEL
)


class PeriodSelection:
    """The currently selected period, resolved against the clock on read."""

    def __init__(self, index: int = DEFAULT_PRESET_INDEX) -> None:
        self._index = index

    @property
    def index(self) -> int:
        return self._index

    @property
    def label(self) -> str:
        return _PRESETS[self._index][0]

    def set_index(self, index: int) -> None:
        self._index = index

    def range(self) -> tuple[datetime, datetime]:
        return _PRESETS[self._index][1](now_pkt())

    def as_query(self, limit: int = 500) -> DateRangeQuery:
        start, end = self.range()
        return DateRangeQuery(start=start, end=end, limit=limit)


class PeriodSelector(QComboBox):
    periodChanged = Signal()

    def __init__(self, selection: PeriodSelection, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._selection = selection
        for label, _ in _PRESETS:
            self.addItem(label)
        self.setCurrentIndex(selection.index)
        self.setMinimumWidth(150)
        self.currentIndexChanged.connect(self._on_changed)

    def _on_changed(self, index: int) -> None:
        self._selection.set_index(index)
        self.periodChanged.emit()
