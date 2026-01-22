from PyQt6.QtWidgets import QWidget, QVBoxLayout, QListWidget


class ErrorMessageList(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.list = QListWidget()
        layout.addWidget(self.list)
