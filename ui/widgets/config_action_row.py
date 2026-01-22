from PyQt6.QtWidgets import QWidget, QGridLayout, QPushButton


class ConfigActionRow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QGridLayout(self)

        self.btn_init = QPushButton("Initialize Instrument")
        self.btn_connect_can = QPushButton("Connect CAN")
        self.btn_start_cyclic = QPushButton("Start Cyclic CAN")
        self.btn_start_trace = QPushButton("Start Trace")
        self.btn_disconnect_can = QPushButton("Disconnect CAN")
        self.btn_stop_cyclic = QPushButton("Stop Cyclic CAN")

        layout.addWidget(self.btn_init, 0, 0)
        layout.addWidget(self.btn_start_trace, 0, 1)
        layout.addWidget(self.btn_connect_can, 1, 0)
        layout.addWidget(self.btn_disconnect_can, 1, 1)
        layout.addWidget(self.btn_start_cyclic, 2, 0)
        layout.addWidget(self.btn_stop_cyclic, 2, 1)
