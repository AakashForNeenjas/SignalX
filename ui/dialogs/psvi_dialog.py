from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QDoubleSpinBox,
    QDialogButtonBox,
)


class PSVISetDialog(QDialog):
    """Dialog to get PS set voltage/current parameters (V, I)."""

    def __init__(self, action_type="PS / HV: Battery Set Charge (V,I)", initial=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(action_type)
        self.layout = QVBoxLayout(self)
        form = QFormLayout()

        self.spin_voltage = QDoubleSpinBox()
        self.spin_voltage.setRange(-10000, 10000)
        self.spin_voltage.setDecimals(3)
        self.spin_voltage.setValue(initial.get("voltage", 400) if initial else 400)

        self.spin_current = QDoubleSpinBox()
        self.spin_current.setRange(0, 10000)
        self.spin_current.setDecimals(3)
        self.spin_current.setValue(initial.get("current", 10) if initial else 10)

        form.addRow("Voltage (V)", self.spin_voltage)
        form.addRow("Current (A)", self.spin_current)
        self.layout.addLayout(form)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)

    def get_values(self):
        return {
            "voltage": self.spin_voltage.value(),
            "current": self.spin_current.value(),
        }
