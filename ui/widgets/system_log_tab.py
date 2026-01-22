import os
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit
from PyQt6.QtCore import QTimer


class SystemLogTab(QWidget):
    def __init__(self, log_path=None, on_check_health=None, parent=None):
        super().__init__(parent)
        self.log_path = log_path
        self.on_check_health = on_check_health
        self._build_ui()
        self._init_timer()
        self.load_log_tail()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        self.log_label = QLabel(f"Log file: {self.log_path or os.path.join('logs', 'app.log')}")
        self.btn_refresh_log = QPushButton("Refresh Logs")
        self.btn_health = QPushButton("Check Instrument Health")
        self.btn_refresh_log.clicked.connect(self.load_log_tail)
        if self.on_check_health:
            self.btn_health.clicked.connect(self.on_check_health)
        header.addWidget(self.log_label)
        header.addStretch()
        header.addWidget(self.btn_health)
        header.addWidget(self.btn_refresh_log)
        layout.addLayout(header)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self.log_view)

    def _init_timer(self):
        self.log_timer = QTimer(self)
        self.log_timer.setInterval(2000)
        self.log_timer.timeout.connect(self.load_log_tail)

    def start_auto_refresh(self):
        self.load_log_tail()
        self.log_timer.start()

    def stop_auto_refresh(self):
        if self.log_timer.isActive():
            self.log_timer.stop()

    def load_log_tail(self, max_lines=400):
        path = self.log_path or os.path.join("logs", "app.log")
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            tail_lines = lines[-max_lines:]
            tail = "".join(reversed(tail_lines))
            self.log_view.setPlainText(tail)
        except FileNotFoundError:
            self.log_view.setPlainText(f"No log file yet at {path}")
        except Exception as e:
            self.log_view.setPlainText(f"Error reading log: {e}")

    def set_log_path(self, log_path):
        self.log_path = log_path
        self.log_label.setText(f"Log file: {self.log_path or os.path.join('logs', 'app.log')}")
