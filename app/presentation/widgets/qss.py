"""
The one QSS mechanic widgets have to know about.

Qt resolves property selectors — `[collapsed="true"]`, `[selected="true"]`
— when a widget is polished, not when the property is set. Change one
without this and the rule simply never applies, which reads as "the
stylesheet is wrong" rather than "the style hasn't been told".
"""
from __future__ import annotations

from PySide6.QtWidgets import QWidget


def repolish(widget: QWidget, *, children: bool = False) -> None:
    """Re-evaluate `widget`'s QSS after a dynamic property changed.

    `children` re-evaluates its descendants too, for rules that reach
    through the widget — a selected row recolouring its own labels, say.
    Polishing a parent does not reach them on its own.
    """
    targets = [widget, *widget.findChildren(QWidget)] if children else [widget]
    for target in targets:
        target.style().unpolish(target)
        target.style().polish(target)
