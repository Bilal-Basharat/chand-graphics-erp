import sys
from PySide6.QtWidgets import QApplication
from dotenv import load_dotenv

from app.infrastructure.db import init_db
from app.container import AppContainer
from app.presentation.windows.dashboard_window import DashboardWindow


def bootstrap():

    load_dotenv()

    init_db()

    container = AppContainer()

    container.create_initializer().initialize()

    app = QApplication(sys.argv)

    window = DashboardWindow()

    window.show()

    sys.exit(app.exec())
    