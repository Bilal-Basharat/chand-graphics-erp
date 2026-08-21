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
from math import ceil

from PySide6.QtCharts import QBarCategoryAxis, QBarSeries, QBarSet, QChart, QChartView, QValueAxis
from PySide6.QtCore import QMargins, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QResizeEvent
from PySide6.QtWidgets import QLabel, QSizePolicy, QStackedLayout, QWidget

from app.presentation.theme import tokens as t

SALES_COLOR = t.PRIMARY
PURCHASES_COLOR = t.INK_SOFT
EXPENSES_COLOR = t.WARNING
"""Money in over the counter, money in from work made to order, money out
on stock, money out on everything else. Drawn in that order, so the two
that earn stand together and the two that spend follow.

None of them is the success/danger pair: those already mean "paid" and
"unpaid" on every list in the app, and a sale is neither. Expenses take
the remaining warm colour, which is also the one that reads as "watch
this".
"""

_EMPTY_MESSAGE = "Nothing recorded in this period."

_LABEL_SIZE = 11

_LABEL_GAP = 8
"""Blank pixels wanted between one bucket label and the next. Closer than
this and the labels read as one run of characters instead of one name per
column."""

_AXIS_GUTTER = 60
"""About what the amounts axis takes off the left before the columns
start. Only the label spacing is worked out from it, and that in whole
columns, so being a few pixels out costs nothing."""


class PeriodBars(QWidget):
    """A grouped bar chart of sales and purchases, one pair per bucket."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._buckets: Sequence = []
        self._categories: QBarCategoryAxis | None = None
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
        self._buckets = buckets
        if not buckets or not any(
            b.sales or b.purchases or b.expenses for b in buckets
        ):
            self._categories = None
            self._layout.setCurrentWidget(self._empty)
            return

        series = QBarSeries()
        for name, amount_of, color in (
            ("Sales", lambda b: b.sales, SALES_COLOR),
            ("Purchases", lambda b: b.purchases, PURCHASES_COLOR),
            ("Expenses", lambda b: b.expenses, EXPENSES_COLOR),
        ):
            bar_set = QBarSet(name)
            for bucket in buckets:
                bar_set.append(float(amount_of(bucket)))
            _paint(bar_set, color)
            series.append(bar_set)
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
        categories.append(self._labels())
        # Qt otherwise cuts each label down to its own column's width, and
        # a column narrow enough leaves nothing but the ellipsis. Spacing
        # the labels out is `_labels`' job; here they are drawn whole.
        categories.setTruncateLabels(False)
        _style_axis(categories)
        chart.addAxis(categories, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(categories)
        self._categories = categories

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

    def resizeEvent(self, event: QResizeEvent) -> None:
        # How many labels fit is a fact about the width, so it is settled
        # again every time the width changes.
        super().resizeEvent(event)
        if self._categories is not None:
            labels = self._labels()
            if labels != self._categories.categories():
                self._categories.setCategories(labels)

    def _labels(self) -> list[str]:
        """A label for every column that has room for one, blank for the rest.

        Every bucket keeps its bar — dropping columns would redraw the
        period — but a month of days or three years of months cannot all
        be named across a panel this wide. Naming every second or third
        column still says where in the period the eye is, which is all the
        axis is for, and is the reading a squeezed label never gives.
        """
        labels = [bucket.label for bucket in self._buckets]
        metrics = QFontMetrics(_font(_LABEL_SIZE))
        widest = max(metrics.horizontalAdvance(label) for label in labels)
        column = max(self.width() - _AXIS_GUTTER, 1) / len(labels)
        stride = ceil((widest + _LABEL_GAP) / column)
        return [name if index % stride == 0 else "" for index, name in enumerate(labels)]


def _paint(bar_set: QBarSet, color: str) -> None:
    bar_set.setColor(QColor(color))
    bar_set.setBorderColor(QColor(color))
    bar_set.setLabelColor(QColor(t.INK))


def _style_axis(axis) -> None:
    axis.setLabelsColor(QColor(t.MUTED))
    # The size `_labels` measures against, so what is drawn and what was
    # measured cannot drift apart.
    axis.setLabelsFont(_font(_LABEL_SIZE))
    axis.setLineVisible(False)
    axis.setGridLineVisible(isinstance(axis, QValueAxis))


def _font(size: int) -> QFont:
    font = QFont(t.FONT_FAMILY)
    font.setPixelSize(size)
    return font
