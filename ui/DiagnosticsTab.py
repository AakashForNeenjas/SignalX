import os
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QHBoxLayout,
)

from core.diagnostics import collect_diagnostics


class DiagnosticsTab(QWidget):
    def __init__(self, profile_name, profile, parent=None):
        super().__init__(parent)
        self.profile_name = profile_name
        self.profile = profile
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Prerequisites Checklist"))
        self.prereq_text = QTextEdit()
        self.prereq_text.setReadOnly(True)
        self.prereq_text.setMinimumHeight(160)
        layout.addWidget(self.prereq_text)

        button_row = QHBoxLayout()
        button_row.addWidget(QLabel("Diagnostics"))
        button_row.addStretch()
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh)
        button_row.addWidget(self.refresh_button)
        layout.addLayout(button_row)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Component", "Status", "Details"])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

    def _load_prereq_text(self):
        path = os.path.join("docs", "PREREQUISITES.md")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.prereq_text.setPlainText(f.read())
                    return
            except Exception:
                pass
        self.prereq_text.setPlainText("Prerequisites file not found.")

    def set_profile(self, profile_name, profile):
        self.profile_name = profile_name
        self.profile = profile
        self.refresh()

    def refresh(self):
        self._load_prereq_text()
        rows = collect_diagnostics(self.profile_name, self.profile)
        self.table.setRowCount(len(rows))
        for r, (name, status, details) in enumerate(rows):
            self.table.setItem(r, 0, QTableWidgetItem(name))
            self.table.setItem(r, 1, QTableWidgetItem(status))
            self.table.setItem(r, 2, QTableWidgetItem(details))
