import sys
from PySide6.QtWidgets import QApplication

from app.infrastructure.db import init_db
from app.container import AppContainer
from app.presentation.windows.dashboard_window import DashboardWindow


def bootstrap():

    init_db()

    container = AppContainer()

    app = QApplication(sys.argv)

    window = DashboardWindow()

    window.show()

    sys.exit(app.exec())
    