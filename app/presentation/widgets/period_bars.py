"""
Sales, purchases and expenses, bucket by bucket.

Bars rather than lines: the question the dashboard is answering is "how
did this stretch compare", and a bar is a quantity you can put a finger
on. Lines would imply a continuous reading that period totals do not
have.

The widget draws whatever buckets it is handed — days, months or years —
and never works out which; that follows from the period being shown and
belongs with the view model that resolves it.

Built on QtCharts, which ships with PySide6 — no new dependency, and the
same painting engine as the rest of the app so the type and colours match.
"""
from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCharts import QBarCategoryAxis, QBarSeries, QBarSet, QChart, QChartView, QValueAxis
from PySide6.QtCore import QMargins, Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QLabel, QSizePolicy, QStackedLayout, QWidget

from app.presentation.theme import tokens as t

SALES_COLOR = t.PRIMARY
PURCHASES_COLOR = t.INK_SOFT
EXPENSES_COLOR = t.WARNING
"""Money in, money out on stock, money out on everything else.

Sales and purchases are deliberately not the success/danger pair: those
already mean "paid" and "unpaid" on every list in the app, and neither a
sale nor a purchase is either. Expenses take the remaining warm colour,
which is also the one that reads as "watch this".
"""

_EMPTY_MESSAGE = "Nothing recorded in this period."

_CROWDED_BUCKETS = 14
"""Past this many columns the category labels overlap, so they are turned
on their side rather than left to collide."""


class PeriodBars(QWidget):
    """A grouped bar chart of sales and purchases, one pair per bucket."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(260)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        self._layout = QStackedLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

        self._view = QChartView()
        self._view.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self._view.setBackgroundBrush(QColor(t.SURFACE))
        self._view.setFrameShape(QChartView.Shape.NoFrame)

        # A chart with nothing in it draws an empty grid, which reads as a
        # component that failed rather than as a quiet period.
        self._empty = QLabel(_EMPTY_MESSAGE)
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setStyleSheet(f"color: {t.MUTED}; font-size: 13px;")

        self._layout.addWidget(self._view)
        self._layout.addWidget(self._empty)
        self.set_buckets([])

    def set_buckets(self, buckets: Sequence) -> None:
        """Render `BucketTotals`, oldest first."""
        if not buckets or not any(
            b.sales or b.purchases or b.expenses for b in buckets
        ):
            self._layout.setCurrentWidget(self._empty)
            return

        sales = QBarSet("Sales")
        purchases = QBarSet("Purchases")
        expenses = QBarSet("Expenses")
        for bucket in buckets:
            sales.append(float(bucket.sales))
            purchases.append(float(bucket.purchases))
            expenses.append(float(bucket.expenses))
        _paint(sales, SALES_COLOR)
        _paint(purchases, PURCHASES_COLOR)
        _paint(expenses, EXPENSES_COLOR)

        series = QBarSeries()
        series.append(sales)
        series.append(purchases)
        series.append(expenses)
        # Width is a share of the column, so a period with one or two
        # columns — "Today" most of all — otherwise draws slabs across the
        # whole plot. Narrower keeps them reading as bars.
        series.setBarWidth(0.75 if len(buckets) > 2 else 0.3)

        chart = QChart()
        chart.addSeries(series)
        chart.setBackgroundBrush(QColor(t.SURFACE))
        chart.setPlotAreaBackgroundVisible(False)
        chart.setMargins(QMargins(0, 6, 0, 0))
        chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)
        chart.legend().setLabelColor(QColor(t.MUTED))
        chart.legend().setFont(_font(11))
        chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)

        categories = QBarCategoryAxis()
        categories.append([bucket.label for bucket in buckets])
        if len(buckets) > _CROWDED_BUCKETS:
            categories.setLabelsAngle(-60)
        _style_axis(categories)
        chart.addAxis(categories, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(categories)

        amounts = QValueAxis()
        amounts.setLabelFormat("%d")
        amounts.setTickCount(5)
        # From zero always: a bar chart whose baseline floats exaggerates
        # every difference on it.
        amounts.setMin(0)
        _style_axis(amounts)
        amounts.setGridLineColor(QColor(t.LINE_SOFT))
        chart.addAxis(amounts, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(amounts)

        previous = self._view.chart()
        self._view.setChart(chart)
        if previous is not None:
            previous.deleteLater()
        self._layout.setCurrentWidget(self._view)


def _paint(bar_set: QBarSet, color: str) -> None:
    bar_set.setColor(QColor(color))
    bar_set.setBorderColor(QColor(color))
    bar_set.setLabelColor(QColor(t.INK))


def _style_axis(axis) -> None:
    axis.setLabelsColor(QColor(t.MUTED))
    axis.setLabelsFont(_font(11))
    axis.setLineVisible(False)
    axis.setGridLineVisible(isinstance(axis, QValueAxis))


def _font(size: int) -> QFont:
    font = QFont(t.FONT_FAMILY)
    font.setPixelSize(size)
    return font
