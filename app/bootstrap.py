import sys

from PySide6.QtCore import QLocale
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication
from dotenv import load_dotenv

from app.container import AppContainer
from app.infrastructure.db import init_db
from app.presentation.session_controller import SessionController
from app.presentation.theme import tokens as t
from app.presentation.theme.stylesheet import build_stylesheet


def configure_locale() -> None:
    """
    Must run before any QWidget is constructed.

    The OS locale (e.g. ur_PK) makes Qt widgets render numbers with
    locale-native digit glyphs (Urdu uses Extended Arabic-Indic digits,
    not 0-9) — a spinbox showing "0" can render as an unrelated glyph.
    Force plain Western digits everywhere regardless of OS locale.
    """
    QLocale.setDefault(QLocale(QLocale.Language.English, QLocale.Country.UnitedStates))


def configure_application(app: QApplication) -> None:
    """
    Apply the app's style, base font and stylesheet.

    Split out from `bootstrap()` so that anything constructing widgets
    outside the normal entrypoint — screenshot harnesses, UI spikes —
    configures Qt exactly as the real app does. When this lived inline,
    such a harness silently reproduced the un-themed defaults and
    "found" problems the running app doesn't have.
    """
    # Native Windows styles ("windowsvista"/"windows11") partially ignore
    # QSS on complex controls — spinbox/combobox arrows in particular are
    # drawn by the OS theme engine, not our stylesheet, which is why they
    # kept looking dated no matter how the QSS around them changed.
    # Fusion is Qt's cross-platform style and fully honors QSS, so the flat
    # theme below actually reaches every control it targets.
    app.setStyle("Fusion")
    # Stylesheet only sets font-size in px, which leaves QFont.pointSize()
    # unset (-1) for anything falling back to the app-level font — Qt then
    # re-feeds that -1 into setPointSize() internally, logging
    # "QFont::setPointSize: Point size <= 0" and rendering some glyphs
    # (e.g. spinbox digits) with a broken/near-zero font. A valid base
    # font with a real point size avoids that fallback entirely.
    app.setFont(QFont(t.FONT_FAMILY, 10))
    app.setStyleSheet(build_stylesheet())


def bootstrap():

    configure_locale()

    load_dotenv()

    init_db()

    container = AppContainer()

    container.create_initializer().initialize()

    app = QApplication(sys.argv)
    configure_application(app)

    # Held for the app's lifetime — it owns the only references to the
    # sign-in window and the shell.
    controller = SessionController(container)
    controller.start()

    sys.exit(app.exec())
