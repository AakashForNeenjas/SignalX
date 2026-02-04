from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt


class HeaderBar(QWidget):
    def __init__(self, on_check_updates=None, version_text="", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QLabel("AtomX")
        header.setStyleSheet(
            "font-size: 34px; font-weight: bold; color: #00ff88; padding: 1px;"
        )
        layout.addWidget(header)
        layout.addStretch()

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(2)
        right.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.btn_check_updates = QPushButton("Check for Updates")
        if on_check_updates:
            self.btn_check_updates.clicked.connect(on_check_updates)
        right.addWidget(self.btn_check_updates, alignment=Qt.AlignmentFlag.AlignRight)

        self.version_label = QLabel(version_text)
        self.version_label.setStyleSheet("font-size: 12px; color: #8ad9ff;")
        right.addWidget(self.version_label, alignment=Qt.AlignmentFlag.AlignRight)

        layout.addLayout(right)

    def set_version(self, version_text: str):
        self.version_label.setText(version_text)
