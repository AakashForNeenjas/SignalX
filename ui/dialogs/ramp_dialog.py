from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QComboBox,
    QLineEdit,
    QDoubleSpinBox,
    QSpinBox,
    QLabel,
    QPushButton,
    QDialogButtonBox,
    QWidget,
    QHBoxLayout,
)


class RampDialog(QDialog):
    """Dialog to get ramp parameters and target selection."""

    _last_gs_voltage = 230.0
    _last_ps_voltage = 0.0

    def __init__(self, action_type="GS / Ramp Up Voltage", initial=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(action_type)
        self.layout = QVBoxLayout(self)
        form = QFormLayout()

        self.combo_target = QComboBox()
        self.combo_target.addItems(["GS_VOLT", "GS_FREQUENCY", "PS_VOLT", "PS_CURRENT", "CAN_SIGNAL"])
        if initial and initial.get("target", {}).get("type"):
            t = initial["target"]["type"].upper()
            idx = self.combo_target.findText(t)
            if idx >= 0:
                self.combo_target.setCurrentIndex(idx)
        self.edit_msg = QLineEdit(initial.get("target", {}).get("message", "") if initial else "")
        self.edit_sig = QLineEdit(initial.get("target", {}).get("signal", "") if initial else "")
        self.edit_msg.setPlaceholderText("CAN message name")
        self.edit_sig.setPlaceholderText("CAN signal name")
        form.addRow("Target Type", self.combo_target)
        form.addRow("CAN Message", self.edit_msg)
        form.addRow("CAN Signal", self.edit_sig)

        self.spin_start = QDoubleSpinBox()
        self.spin_start.setRange(-10000, 10000)
        self.spin_start.setDecimals(3)
        self.spin_start.setValue(initial.get("start", 0) if initial else 0)

        self.spin_step = QDoubleSpinBox()
        self.spin_step.setRange(0.0001, 10000)
        self.spin_step.setDecimals(3)
        self.spin_step.setValue(initial.get("step", 1) if initial else 1)

        self.spin_end = QDoubleSpinBox()
        self.spin_end.setRange(-10000, 10000)
        self.spin_end.setDecimals(3)
        self.spin_end.setValue(initial.get("end", 0) if initial else 0)

        self.spin_gs_voltage = QDoubleSpinBox()
        self.spin_gs_voltage.setRange(0, 10000)
        self.spin_gs_voltage.setDecimals(3)
        if initial and "gs_voltage" in initial:
            self.spin_gs_voltage.setValue(initial.get("gs_voltage", 0))
        else:
            self.spin_gs_voltage.setValue(self._last_gs_voltage)

        self.spin_ps_voltage = QDoubleSpinBox()
        self.spin_ps_voltage.setRange(0, 10000)
        self.spin_ps_voltage.setDecimals(3)
        if initial and "ps_voltage" in initial:
            self.spin_ps_voltage.setValue(initial.get("ps_voltage", 0))
        else:
            self.spin_ps_voltage.setValue(self._last_ps_voltage)

        self.spin_delay = QDoubleSpinBox()
        self.spin_delay.setRange(0, 3600)
        self.spin_delay.setDecimals(3)
        self.spin_delay.setValue(initial.get("delay", 0.5) if initial else 0.5)

        self.spin_tol = QDoubleSpinBox()
        self.spin_tol.setRange(0, 1000)
        self.spin_tol.setDecimals(3)
        self.spin_tol.setValue(initial.get("tolerance", 0.5) if initial else 0.5)

        self.spin_retries = QSpinBox()
        self.spin_retries.setRange(0, 100)
        self.spin_retries.setValue(initial.get("retries", 3) if initial else 3)

        self.check_verify = QPushButton("Verify setpoint (enable)")
        self.check_verify.setCheckable(True)
        self.check_verify.setChecked(bool(initial.get("verify", False)) if initial else False)

        self.check_measure_gs = QPushButton("Measure GS")
        self.check_measure_gs.setCheckable(True)
        self.check_measure_gs.setChecked(bool(initial.get("measure", {}).get("gs", True)) if initial else True)
        self.check_measure_ps = QPushButton("Measure PS")
        self.check_measure_ps.setCheckable(True)
        self.check_measure_ps.setChecked(bool(initial.get("measure", {}).get("ps", True)) if initial else True)
        self.check_measure_load = QPushButton("Measure Load")
        self.check_measure_load.setCheckable(True)
        self.check_measure_load.setChecked(bool(initial.get("measure", {}).get("load", True)) if initial else True)

        self.lbl_start = QLabel("Start")
        self.lbl_step = QLabel("Step")
        self.lbl_end = QLabel("End")
        self.lbl_gs_voltage = QLabel("GS Voltage (V)")
        self.lbl_ps_voltage = QLabel("PS Voltage Limit (V)")
        form.addRow(self.lbl_start, self.spin_start)
        form.addRow(self.lbl_step, self.spin_step)
        form.addRow(self.lbl_end, self.spin_end)
        form.addRow(self.lbl_gs_voltage, self.spin_gs_voltage)
        form.addRow(self.lbl_ps_voltage, self.spin_ps_voltage)
        form.addRow("Dwell between steps (s)", self.spin_delay)
        form.addRow("Tolerance", self.spin_tol)
        form.addRow("Retries", self.spin_retries)
        form.addRow("Verify setpoint", self.check_verify)
        form.addRow("Measure toggles", self._build_measure_row())

        self.layout.addLayout(form)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)
        hint = QLabel(
            "JSON: {target:{type,msg,signal}, start, step, end, gs_voltage, ps_voltage, dwell, tolerance, retries, verify, measure:{gs,ps,load}}"
        )
        hint.setStyleSheet("color: #888; font-size: 10px;")
        self.layout.addWidget(hint)

        self.combo_target.currentTextChanged.connect(self._toggle_target_fields)
        self._toggle_target_fields(self.combo_target.currentText())

    def _build_measure_row(self):
        row = QHBoxLayout()
        row.addWidget(self.check_measure_gs)
        row.addWidget(self.check_measure_ps)
        row.addWidget(self.check_measure_load)
        w = QWidget()
        w.setLayout(row)
        return w

    def _toggle_target_fields(self, text):
        target = text.upper()
        is_can = target == "CAN_SIGNAL"
        is_gs_freq = target == "GS_FREQUENCY"
        is_ps_current = target == "PS_CURRENT"
        self.edit_msg.setEnabled(is_can)
        self.edit_sig.setEnabled(is_can)
        self.spin_gs_voltage.setEnabled(is_gs_freq)
        self.lbl_gs_voltage.setEnabled(is_gs_freq)
        self.spin_ps_voltage.setEnabled(is_ps_current)
        self.lbl_ps_voltage.setEnabled(is_ps_current)
        if is_gs_freq:
            self.lbl_start.setText("Start Frequency (Hz)")
            self.lbl_step.setText("Step Frequency (Hz)")
            self.lbl_end.setText("End Frequency (Hz)")
        elif target == "GS_VOLT":
            self.lbl_start.setText("Start Voltage (V)")
            self.lbl_step.setText("Step Voltage (V)")
            self.lbl_end.setText("End Voltage (V)")
        elif target == "PS_VOLT":
            self.lbl_start.setText("Start Voltage (V)")
            self.lbl_step.setText("Step Voltage (V)")
            self.lbl_end.setText("End Voltage (V)")
        elif target == "PS_CURRENT":
            self.lbl_start.setText("Start Current (A)")
            self.lbl_step.setText("Step Current (A)")
            self.lbl_end.setText("End Current (A)")
        else:
            self.lbl_start.setText("Start")
            self.lbl_step.setText("Step")
            self.lbl_end.setText("End")

    def get_values(self):
        ps_voltage = self.spin_ps_voltage.value() if self.spin_ps_voltage.isEnabled() else None
        values = {
            "target": {
                "type": self.combo_target.currentText(),
                "message": self.edit_msg.text().strip(),
                "signal": self.edit_sig.text().strip(),
            },
            "start": self.spin_start.value(),
            "step": self.spin_step.value(),
            "end": self.spin_end.value(),
            "gs_voltage": self.spin_gs_voltage.value(),
            "ps_voltage": ps_voltage,
            "dwell": self.spin_delay.value(),
            "tolerance": self.spin_tol.value(),
            "retries": self.spin_retries.value(),
            "verify": self.check_verify.isChecked(),
            "measure": {
                "gs": self.check_measure_gs.isChecked(),
                "ps": self.check_measure_ps.isChecked(),
                "load": self.check_measure_load.isChecked(),
            },
        }
        self.__class__._last_gs_voltage = values.get("gs_voltage", self._last_gs_voltage)
        if ps_voltage is not None:
            self.__class__._last_ps_voltage = ps_voltage
        return values
