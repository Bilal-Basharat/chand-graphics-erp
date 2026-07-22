from PySide6.QtWidgets import QMainWindow


class DashboardWindow(QMainWindow):

    def __init__(self):

        super().__init__()

        self.setWindowTitle("Printing Press ERP")

        self.resize(1400, 900)

        # label = QLabel("Printing Press ERP")

        # self.setCentralWidget(label)