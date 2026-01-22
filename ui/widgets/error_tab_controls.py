from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QSpinBox, QPushButton


class ErrorTabControls(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)

        layout.addWidget(QLabel("Period (ms):"))
        self.err_period_spin = QSpinBox()
        self.err_period_spin.setRange(1, 100000)
        self.err_period_spin.setValue(100)
        layout.addWidget(self.err_period_spin)

        self.btn_err_build = QPushButton("Load Signals")
        layout.addWidget(self.btn_err_build)

        self.btn_err_send = QPushButton("Send Once")
        layout.addWidget(self.btn_err_send)

        self.btn_err_start = QPushButton("Start Periodic")
        layout.addWidget(self.btn_err_start)

        self.btn_err_stop = QPushButton("Stop Periodic")
        layout.addWidget(self.btn_err_stop)

        layout.addStretch()
