from PySide6.QtWidgets import QApplication

from app.presentation.windows.dashboard_window import DashboardWindow


def bootstrap():

    app = QApplication([])

    window = DashboardWindow()

    window.show()

    app.exec()