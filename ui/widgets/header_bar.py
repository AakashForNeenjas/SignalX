from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton


class HeaderBar(QWidget):
    def __init__(self, on_check_updates=None, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QLabel("AtomX")
        header.setStyleSheet(
            "font-size: 34px; font-weight: bold; color: #00ff88; padding: 1px;"
        )
        layout.addWidget(header)
        layout.addStretch()

        self.btn_check_updates = QPushButton("Check for Updates")
        if on_check_updates:
            self.btn_check_updates.clicked.connect(on_check_updates)
        layout.addWidget(self.btn_check_updates)
