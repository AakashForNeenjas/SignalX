from PyQt6.QtWidgets import QWidget, QGridLayout, QLabel


class StatusIndicators(QWidget):
    def __init__(self, indicators=None, parent=None):
        super().__init__(parent)
        layout = QGridLayout(self)
        self.value_inputs = {}

        if indicators is None:
            indicators = [
                "BL Version", "FW Version", "HW Version",
                "Grid Voltage", "Grid Current", "Bus Voltage",
                "BMS Voltage", "HV Voltage", "HV Current",
                "LV Voltage", "LV Current", "OBC Temperature",
                "OBC FET Temp", "HP DCDC Temp", "Transformer Temp",
                "Charge Current Limit", "Discharge Current Limit", "Regen Current Limit",
            ]

        for i, name in enumerate(indicators):
            layout.addWidget(QLabel(name), i, 0)
            val_label = QLabel("0.0")
            val_label.setStyleSheet("border: 1px solid gray; padding: 2px;")
            layout.addWidget(val_label, i, 1)
            self.value_inputs[name] = val_label
