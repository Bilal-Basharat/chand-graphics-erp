"""
Full-width header: brand, global search, primary actions, current user.

Purely presentational — emits signals for actions, exposes `set_user()` for
the caller to push current-user display state in. No use-case calls here.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.presentation.theme import tokens as t


def _initials(full_name: str) -> str:
    parts = [p for p in full_name.strip().split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


class _UserChip(QFrame):
    """
    Clickable header chip that drops the account menu.

    A QFrame rather than a QPushButton because the chip lays out its own
    avatar and two lines of text: a button's size hint comes from its own
    text and icon, ignores a child layout, and so reports a width far
    narrower than its contents — which clips them. QFrame also paints its
    stylesheet background and border, which a bare QWidget subclass does
    not.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._menu: QMenu | None = None
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_menu(self, menu: QMenu) -> None:
        self._menu = menu

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().mousePressEvent(event)
        if self._menu is None:
            return
        # Dropped from the chip's bottom-left so it hangs under the chip,
        # the way a header account menu is expected to behave.
        self._menu.popup(self.mapToGlobal(self.rect().bottomLeft()))


class TopBar(QWidget):
    newSaleRequested = Signal()
    newPurchaseRequested = Signal()
    searchSubmitted = Signal(str)
    profileRequested = Signal()
    changePasswordRequested = Signal()
    signOutRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Header")
        # Required for the #Header rule's background to be painted at all
        # — see the note in theme/stylesheet.py.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(t.HEADER_HEIGHT)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_brand())
        layout.addWidget(self._build_search(), 1)
        layout.addLayout(self._build_actions())

        self.setLayout(layout)

    def _build_brand(self) -> QWidget:
        self._brand = QWidget()
        self._brand.setFixedWidth(t.SIDEBAR_WIDTH)
        layout = QHBoxLayout(self._brand)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(9)

        mark = QLabel("CG")
        mark.setObjectName("BrandMark")
        mark.setFixedSize(28, 28)
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._brand_text = QWidget()
        text_block = QVBoxLayout(self._brand_text)
        text_block.setContentsMargins(0, 0, 0, 0)
        text_block.setSpacing(0)
        name = QLabel("Chand Graphics")
        name.setObjectName("BrandName")
        sub = QLabel("Printing Press ERP")
        sub.setObjectName("BrandSub")
        text_block.addWidget(name)
        text_block.addWidget(sub)

        layout.addWidget(mark)
        layout.addWidget(self._brand_text)
        layout.addStretch(1)
        return self._brand

    def set_brand_width(self, width: int) -> None:
        """Keep the brand block the same width as the sidebar below it, so
        the search box stays aligned with the content area either side of
        a collapse."""
        self._brand.setFixedWidth(width)
        # Below roughly this width the wordmark can't fit; the "CG" mark
        # alone still identifies the app.
        self._brand_text.setVisible(width >= t.SIDEBAR_WIDTH - 40)

    def _build_search(self) -> QWidget:
        wrap = QWidget()
        layout = QHBoxLayout(wrap)
        layout.setContentsMargins(16, 10, 16, 10)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search…")
        self._search.setMaximumWidth(460)
        self._search.returnPressed.connect(
            lambda: self.searchSubmitted.emit(self._search.text().strip())
        )
        layout.addWidget(self._search)
        layout.addStretch(1)
        return wrap

    def _build_actions(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 16, 0)
        layout.setSpacing(8)

        # The three things the shop records all day, in the same order the
        # rail lists them. Only the first is primary: three buttons of
        # equal weight is three, and none of them reads as the usual one.
        self._actions: list[QPushButton] = []
        for label, variant, signal in (
            ("New Sale", "primary", self.newSaleRequested),
            ("New Purchase", "outline", self.newPurchaseRequested),
        ):
            button = QPushButton(label)
            button.setProperty("variant", variant)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(signal.emit)
            layout.addWidget(button)
            self._actions.append(button)

        layout.addLayout(self._build_user_chip())
        return layout

    def _build_user_chip(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(6, 0, 0, 0)

        # The whole avatar-plus-name area is the click target; a menu
        # reachable only from the small caret is one people miss.
        self._chip = _UserChip()
        self._chip.setObjectName("UserChip")
        self._chip.setToolTip("Account options")

        chip_layout = QHBoxLayout(self._chip)
        chip_layout.setContentsMargins(5, 4, 9, 4)
        chip_layout.setSpacing(9)

        self._avatar = QLabel("?")
        self._avatar.setObjectName("UserAvatar")
        self._avatar.setFixedSize(30, 30)
        self._avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)

        text_block = QVBoxLayout()
        text_block.setSpacing(0)
        self._name_label = QLabel("")
        self._name_label.setStyleSheet(f"font-weight: {t.WEIGHT_SEMIBOLD}; font-size: 13px;")
        self._role_label = QLabel("")
        self._role_label.setStyleSheet(f"color: {t.MUTED}; font-size: 11px;")
        text_block.addWidget(self._name_label)
        text_block.addWidget(self._role_label)

        caret = QLabel("⌄")
        caret.setStyleSheet(f"color: {t.MUTED}; font-size: 13px;")

        chip_layout.addWidget(self._avatar)
        chip_layout.addLayout(text_block)
        chip_layout.addWidget(caret)

        self._chip.set_menu(self._build_user_menu())
        layout.addWidget(self._chip)
        return layout

    def _build_user_menu(self) -> QMenu:
        menu = QMenu(self)
        menu.addAction("My profile", self.profileRequested.emit)
        menu.addAction("Change password…", self.changePasswordRequested.emit)
        menu.addSeparator()
        menu.addAction("Sign out", self.signOutRequested.emit)
        return menu

    def set_actions_enabled(self, enabled: bool) -> None:
        """The two record-something buttons, off while nothing may be
        recorded. The account menu and the search stay live: signing out
        and looking things up are not what a licence pays for."""
        for button in self._actions:
            button.setEnabled(enabled)

    def set_user(self, full_name: str, role: str) -> None:
        self._avatar.setText(_initials(full_name))
        self._name_label.setText(full_name)
        self._role_label.setText(role.capitalize())

    def focus_search(self) -> None:
        """Where Ctrl+F lands when the current screen has no search of its own."""
        self._search.setFocus()
        self._search.selectAll()
