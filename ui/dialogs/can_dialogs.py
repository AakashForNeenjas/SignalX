from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QDoubleSpinBox,
    QSpinBox,
    QDialogButtonBox,
    QMessageBox,
)

from ui.dialogs.common import parse_can_id


class CANSignalReadDialog(QDialog):
    """Dialog for CAN / Read Signal Value."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("CAN / Read Signal Value")
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.txt_signal = QLineEdit()
        self.txt_signal.setPlaceholderText("e.g., GridVol, HvCur")
        self.spin_timeout = QDoubleSpinBox()
        self.spin_timeout.setRange(0.1, 60)
        self.spin_timeout.setValue(2.0)
        self.spin_timeout.setDecimals(1)

        form.addRow("Signal Name:", self.txt_signal)
        form.addRow("Timeout (s):", self.spin_timeout)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_values(self):
        return {
            "signal_name": self.txt_signal.text(),
            "timeout": self.spin_timeout.value(),
        }

    def accept(self):
        if not self.txt_signal.text().strip():
            QMessageBox.warning(self, "Missing Signal", "Signal name is required.")
            return
        super().accept()


class CANSignalToleranceDialog(QDialog):
    """Dialog for CAN / Check Signal (Tolerance)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("CAN / Check Signal (Tolerance)")
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.txt_signal = QLineEdit()
        self.txt_signal.setPlaceholderText("e.g., GridVol")
        self.spin_expected = QDoubleSpinBox()
        self.spin_expected.setRange(-10000, 10000)
        self.spin_expected.setValue(230)
        self.spin_expected.setDecimals(3)
        self.spin_tolerance = QDoubleSpinBox()
        self.spin_tolerance.setRange(0, 10000)
        self.spin_tolerance.setValue(5)
        self.spin_tolerance.setDecimals(3)
        self.spin_timeout = QDoubleSpinBox()
        self.spin_timeout.setRange(0.1, 60)
        self.spin_timeout.setValue(2.0)

        form.addRow("Signal Name:", self.txt_signal)
        form.addRow("Expected Value:", self.spin_expected)
        form.addRow("Tolerance (+/-):", self.spin_tolerance)
        form.addRow("Timeout (s):", self.spin_timeout)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_values(self):
        return {
            "signal_name": self.txt_signal.text(),
            "expected_value": self.spin_expected.value(),
            "tolerance": self.spin_tolerance.value(),
            "timeout": self.spin_timeout.value(),
        }

    def accept(self):
        if not self.txt_signal.text().strip():
            QMessageBox.warning(self, "Missing Signal", "Signal name is required.")
            return
        super().accept()


class CANConditionalJumpDialog(QDialog):
    """Dialog for CAN / Conditional Jump."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("CAN / Conditional Jump")
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.txt_signal = QLineEdit()
        self.txt_signal.setPlaceholderText("e.g., SystemStatus")
        self.spin_expected = QDoubleSpinBox()
        self.spin_expected.setRange(-10000, 10000)
        self.spin_tolerance = QDoubleSpinBox()
        self.spin_tolerance.setRange(0, 10000)
        self.spin_tolerance.setValue(0.1)
        self.spin_target_step = QSpinBox()
        self.spin_target_step.setRange(1, 9999)
        self.spin_target_step.setValue(1)

        form.addRow("Signal Name:", self.txt_signal)
        form.addRow("Expected Value:", self.spin_expected)
        form.addRow("Tolerance:", self.spin_tolerance)
        form.addRow("Jump to Step:", self.spin_target_step)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_values(self):
        return {
            "signal_name": self.txt_signal.text(),
            "expected_value": self.spin_expected.value(),
            "tolerance": self.spin_tolerance.value(),
            "target_step": self.spin_target_step.value(),
        }

    def accept(self):
        if not self.txt_signal.text().strip():
            QMessageBox.warning(self, "Missing Signal", "Signal name is required.")
            return
        super().accept()


class CANWaitSignalChangeDialog(QDialog):
    """Dialog for CAN / Wait For Signal Change."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("CAN / Wait For Signal Change")
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.txt_signal = QLineEdit()
        self.txt_signal.setPlaceholderText("e.g., GridVol")
        self.spin_initial = QDoubleSpinBox()
        self.spin_initial.setRange(-10000, 10000)
        self.spin_initial.setValue(0)
        self.spin_initial.setDecimals(3)
        self.spin_timeout = QDoubleSpinBox()
        self.spin_timeout.setRange(0.1, 60)
        self.spin_timeout.setValue(5.0)
        self.spin_poll = QDoubleSpinBox()
        self.spin_poll.setRange(0.01, 5)
        self.spin_poll.setValue(0.1)
        self.spin_poll.setDecimals(3)

        form.addRow("Signal Name:", self.txt_signal)
        form.addRow("Initial Value:", self.spin_initial)
        form.addRow("Timeout (s):", self.spin_timeout)
        form.addRow("Poll Interval (s):", self.spin_poll)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_values(self):
        return {
            "signal_name": self.txt_signal.text(),
            "initial_value": self.spin_initial.value(),
            "timeout": self.spin_timeout.value(),
            "poll_interval": self.spin_poll.value(),
        }

    def accept(self):
        if not self.txt_signal.text().strip():
            QMessageBox.warning(self, "Missing Signal", "Signal name is required.")
            return
        super().accept()


class CANMonitorRangeDialog(QDialog):
    """Dialog for CAN / Monitor Signal Range."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("CAN / Monitor Signal Range")
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.txt_signal = QLineEdit()
        self.txt_signal.setPlaceholderText("e.g., GridVol")
        self.spin_min = QDoubleSpinBox()
        self.spin_min.setRange(-10000, 10000)
        self.spin_min.setValue(200)
        self.spin_min.setDecimals(3)
        self.spin_max = QDoubleSpinBox()
        self.spin_max.setRange(-10000, 10000)
        self.spin_max.setValue(240)
        self.spin_max.setDecimals(3)
        self.spin_duration = QDoubleSpinBox()
        self.spin_duration.setRange(0.1, 300)
        self.spin_duration.setValue(5.0)
        self.spin_poll = QDoubleSpinBox()
        self.spin_poll.setRange(0.1, 10)
        self.spin_poll.setValue(0.5)

        form.addRow("Signal Name:", self.txt_signal)
        form.addRow("Min Value:", self.spin_min)
        form.addRow("Max Value:", self.spin_max)
        form.addRow("Duration (s):", self.spin_duration)
        form.addRow("Poll Interval (s):", self.spin_poll)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_values(self):
        return {
            "signal_name": self.txt_signal.text(),
            "min_val": self.spin_min.value(),
            "max_val": self.spin_max.value(),
            "duration": self.spin_duration.value(),
            "poll_interval": self.spin_poll.value(),
        }

    def accept(self):
        if not self.txt_signal.text().strip():
            QMessageBox.warning(self, "Missing Signal", "Signal name is required.")
            return
        super().accept()


class CANCompareSignalsDialog(QDialog):
    """Dialog for CAN / Compare Two Signals."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("CAN / Compare Two Signals")
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.txt_signal1 = QLineEdit()
        self.txt_signal1.setPlaceholderText("e.g., GridVol")
        self.txt_signal2 = QLineEdit()
        self.txt_signal2.setPlaceholderText("e.g., BusVol")
        self.spin_tolerance = QDoubleSpinBox()
        self.spin_tolerance.setRange(0, 10000)
        self.spin_tolerance.setValue(1.0)
        self.spin_tolerance.setDecimals(3)
        self.spin_timeout = QDoubleSpinBox()
        self.spin_timeout.setRange(0.1, 60)
        self.spin_timeout.setValue(2.0)

        form.addRow("Signal 1:", self.txt_signal1)
        form.addRow("Signal 2:", self.txt_signal2)
        form.addRow("Tolerance:", self.spin_tolerance)
        form.addRow("Timeout (s):", self.spin_timeout)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_values(self):
        return {
            "signal1": self.txt_signal1.text(),
            "signal2": self.txt_signal2.text(),
            "tolerance": self.spin_tolerance.value(),
            "timeout": self.spin_timeout.value(),
        }

    def accept(self):
        if not self.txt_signal1.text().strip() or not self.txt_signal2.text().strip():
            QMessageBox.warning(self, "Missing Signal", "Both signal names are required.")
            return
        super().accept()


class CANSetAndVerifyDialog(QDialog):
    """Dialog for CAN / Set Signal and Verify."""

    def __init__(self, parent=None, initial=None):
        super().__init__(parent)
        self.setWindowTitle("CAN / Set Signal and Verify")
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.txt_msg_id = QLineEdit()
        self.txt_msg_id.setPlaceholderText("e.g., 0x123 or 291")
        self.txt_signal = QLineEdit()
        self.txt_signal.setPlaceholderText("e.g., GridVol")
        self.spin_target = QDoubleSpinBox()
        self.spin_target.setRange(-10000, 10000)
        self.spin_target.setValue(230)
        self.spin_target.setDecimals(3)
        self.spin_verify_timeout = QDoubleSpinBox()
        self.spin_verify_timeout.setRange(0.1, 60)
        self.spin_verify_timeout.setValue(2.0)
        self.spin_tolerance = QDoubleSpinBox()
        self.spin_tolerance.setRange(0, 10000)
        self.spin_tolerance.setValue(0.5)
        self.spin_tolerance.setDecimals(3)

        if initial:
            mid = initial.get("message_id")
            if mid is not None:
                self.txt_msg_id.setText(str(mid))
            if "signal_name" in initial:
                self.txt_signal.setText(str(initial.get("signal_name", "")))
            if "target_value" in initial:
                try:
                    self.spin_target.setValue(float(initial.get("target_value")))
                except Exception:
                    pass
            if "tolerance" in initial:
                try:
                    self.spin_tolerance.setValue(float(initial.get("tolerance")))
                except Exception:
                    pass
            if "verify_timeout" in initial:
                try:
                    self.spin_verify_timeout.setValue(float(initial.get("verify_timeout")))
                except Exception:
                    pass

        form.addRow("Message ID (hex or dec):", self.txt_msg_id)
        form.addRow("Signal Name:", self.txt_signal)
        form.addRow("Target Value:", self.spin_target)
        form.addRow("Tolerance:", self.spin_tolerance)
        form.addRow("Verify Timeout (s):", self.spin_verify_timeout)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_values(self):
        return {
            "message_id": self.txt_msg_id.text().strip(),
            "signal_name": self.txt_signal.text().strip(),
            "target_value": self.spin_target.value(),
            "tolerance": self.spin_tolerance.value(),
            "verify_timeout": self.spin_verify_timeout.value(),
        }

    def accept(self):
        if not self.txt_signal.text().strip():
            QMessageBox.warning(self, "Missing Signal", "Signal name is required.")
            return
        try:
            parse_can_id(self.txt_msg_id.text())
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Invalid ID",
                f"Message ID must be hex (0x123) or decimal (291).\nDetails: {exc}",
            )
            return
        super().accept()
