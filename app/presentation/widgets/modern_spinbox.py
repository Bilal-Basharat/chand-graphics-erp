"""
Composite numeric stepper: a borderless QSpinBox flanked by flat +/- step
buttons we draw ourselves, instead of a native QSpinBox with its built-in
up/down arrows.

The native arrows are drawn by the Qt style's internal arrow primitive,
which does not reliably follow QSS once the button subcontrols carry
custom styling (confirmed empirically: it renders as a blank box or a
solid rectangle depending on the style, never a clean chevron). Drawing
the steppers as plain QPushButtons sidesteps that entirely — a "+"/"-"
glyph in our own font always renders crisply, on any style.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QPaintEvent
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QStyle,
    QStyleOption,
    QWidget,
)


class ModernSpinBox(QWidget):
    valueChanged = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ModernSpinBox")
        # A stepper reads as compact everywhere it's used — without a cap,
        # QFormLayout stretches it to the full field-column width, same as
        # a text input, leaving the +/- buttons stranded far from the value.
        self.setMaximumWidth(160)

        self._spin = QSpinBox()
        self._spin.setObjectName("ModernSpinBoxField")
        self._spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self._spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Fill the control's height so the button dividers meet its edges
        # instead of overshooting a shorter, vertically centred field.
        self._spin.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._spin.valueChanged.connect(self.valueChanged)
        self._spin.valueChanged.connect(self._sync_step_buttons)

        self._down_btn = self._build_step_button("−", "SpinStepDown", self._spin.stepDown)
        self._up_btn = self._build_step_button("+", "SpinStepUp", self._spin.stepUp)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._down_btn)
        layout.addWidget(self._spin, 1)
        layout.addWidget(self._up_btn)

        self._sync_step_buttons()

    def _sync_step_buttons(self) -> None:
        """Grey out a step that would do nothing.

        A button that stays lit at the end of its range invites a click
        that silently does nothing; disabling it says where the limit is.
        """
        self._down_btn.setEnabled(self._spin.value() > self._spin.minimum())
        self._up_btn.setEnabled(self._spin.value() < self._spin.maximum())

    @staticmethod
    def _build_step_button(glyph: str, object_name: str, on_click) -> QPushButton:
        button = QPushButton(glyph)
        button.setObjectName(object_name)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setAutoRepeat(True)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # tabbing should land on the value
        # A button's default vertical policy is Fixed, which leaves the
        # steppers short and floating against the taller value field
        # instead of reading as one control.
        button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        button.clicked.connect(on_click)
        return button

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 (Qt override)
        # A plain QWidget subclass does not draw the background, border or
        # radius a stylesheet gives it — Qt only does that for widgets that
        # paint PE_Widget themselves. Without this the QSS frame around the
        # stepper silently does nothing and the +/- buttons read as three
        # loose glyphs rather than one control.
        option = QStyleOption()
        option.initFrom(self)
        painter = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, option, painter, self)

    def value(self) -> int:
        return self._spin.value()

    def setValue(self, value: int) -> None:
        self._spin.setValue(value)

    def maximum(self) -> int:
        """The most this will accept — the cap a caller set with
        `setRange`, readable back for one that has to explain it."""
        return self._spin.maximum()

    def setRange(self, minimum: int, maximum: int) -> None:
        self._spin.setRange(minimum, maximum)
        self._sync_step_buttons()

    def setPrefix(self, prefix: str) -> None:
        self._spin.setPrefix(prefix)
