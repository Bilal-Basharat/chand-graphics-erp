"""
Sales against purchases, month by month.

Two bars per month rather than two lines: the question the dashboard is
answering is "how did this month compare", and a bar is a quantity you can
put a finger on. Lines would imply a continuous reading that monthly
totals do not have.

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
"""Money in and money out. Deliberately not the success/warning pair: those
already mean "paid" and "part paid" on every list in the app, and a
purchase is neither."""

_EMPTY_MESSAGE = "No sales or purchases in the last 12 months."


class MonthlyBars(QWidget):
    """A grouped bar chart of monthly sales and purchases."""

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
        # component that failed rather than as a quiet year.
        self._empty = QLabel(_EMPTY_MESSAGE)
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setStyleSheet(f"color: {t.MUTED}; font-size: 13px;")

        self._layout.addWidget(self._view)
        self._layout.addWidget(self._empty)
        self.set_months([])

    def set_months(self, months: Sequence) -> None:
        """Render `MonthTotals`, oldest first."""
        if not months or not any(month.sales or month.purchases for month in months):
            self._layout.setCurrentWidget(self._empty)
            return

        sales = QBarSet("Sales")
        purchases = QBarSet("Purchases")
        for month in months:
            sales.append(float(month.sales))
            purchases.append(float(month.purchases))
        _paint(sales, SALES_COLOR)
        _paint(purchases, PURCHASES_COLOR)

        series = QBarSeries()
        series.append(sales)
        series.append(purchases)
        series.setBarWidth(0.75)

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
        categories.append([month.label for month in months])
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
