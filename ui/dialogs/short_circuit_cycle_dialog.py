from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
)


class ShortCircuitCycleDialog(QDialog):
    def __init__(self, initial=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("LOAD / Short Circuit Cycle")
        initial = initial or {}

        form = QFormLayout()

        self.spin_cycles = QSpinBox()
        self.spin_cycles.setMinimum(1)
        self.spin_cycles.setMaximum(100000)
        self.spin_cycles.setValue(int(initial.get("cycles", 1)))

        self.spin_pulse = QDoubleSpinBox()
        self.spin_pulse.setDecimals(4)
        self.spin_pulse.setMinimum(0.001)
        self.spin_pulse.setMaximum(60.0)
        self.spin_pulse.setValue(float(initial.get("pulse_s", 0.1)))

        self.spin_input_delay = QDoubleSpinBox()
        self.spin_input_delay.setDecimals(3)
        self.spin_input_delay.setMinimum(0.0)
        self.spin_input_delay.setMaximum(3600.0)
        self.spin_input_delay.setValue(float(initial.get("input_on_delay_s", 0.0)))

        self.spin_dwell = QDoubleSpinBox()
        self.spin_dwell.setDecimals(3)
        self.spin_dwell.setMinimum(0.0)
        self.spin_dwell.setMaximum(3600.0)
        self.spin_dwell.setValue(float(initial.get("dwell_s", 0.0)))

        self.spin_precharge = QDoubleSpinBox()
        self.spin_precharge.setDecimals(3)
        self.spin_precharge.setMinimum(0.0)
        self.spin_precharge.setMaximum(3600.0)
        self.spin_precharge.setValue(float(initial.get("precharge_s", 0.0)))

        self.spin_cc = QDoubleSpinBox()
        self.spin_cc.setDecimals(4)
        self.spin_cc.setMinimum(0.0)
        self.spin_cc.setMaximum(1000.0)
        self.spin_cc.setValue(float(initial.get("cc_a", 0.0)))

        self.chk_ps_output = QCheckBox("PS Output ON during cycles")
        self.chk_ps_output.setChecked(bool(initial.get("ps_output", True)))

        self.chk_ps_toggle = QCheckBox("Toggle PS Output each cycle")
        self.chk_ps_toggle.setChecked(bool(initial.get("ps_toggle_each_cycle", False)))

        self.chk_gs_telemetry = QCheckBox("Measure GS telemetry")
        self.chk_gs_telemetry.setChecked(bool(initial.get("gs_telemetry", False)))

        self.chk_toggle_input = QCheckBox("Toggle Load Input each cycle")
        self.chk_toggle_input.setChecked(bool(initial.get("input_on_each_cycle", True)))

        self.chk_stop_on_fail = QCheckBox("Stop on first failure")
        self.chk_stop_on_fail.setChecked(bool(initial.get("stop_on_fail", True)))

        form.addRow("Cycles", self.spin_cycles)
        form.addRow("Pulse (s)", self.spin_pulse)
        form.addRow("Input ON delay (s)", self.spin_input_delay)
        form.addRow("Dwell between cycles (s)", self.spin_dwell)
        form.addRow("Precharge delay (s)", self.spin_precharge)
        form.addRow("CC Setpoint (A)", self.spin_cc)
        form.addRow("", self.chk_ps_output)
        form.addRow("", self.chk_ps_toggle)
        form.addRow("", self.chk_gs_telemetry)
        form.addRow("", self.chk_toggle_input)
        form.addRow("", self.chk_stop_on_fail)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(QLabel("JSON: {cycles, pulse_s, input_on_delay_s, dwell_s, precharge_s, cc_a, ps_output, ps_toggle_each_cycle, gs_telemetry, input_on_each_cycle, stop_on_fail}"))
        layout.addWidget(buttons)
        self.setLayout(layout)

    def get_values(self) -> dict:
        return {
            "cycles": int(self.spin_cycles.value()),
            "pulse_s": float(self.spin_pulse.value()),
            "input_on_delay_s": float(self.spin_input_delay.value()),
            "dwell_s": float(self.spin_dwell.value()),
            "precharge_s": float(self.spin_precharge.value()),
            "cc_a": float(self.spin_cc.value()),
            "ps_output": self.chk_ps_output.isChecked(),
            "ps_toggle_each_cycle": self.chk_ps_toggle.isChecked(),
            "gs_telemetry": self.chk_gs_telemetry.isChecked(),
            "input_on_each_cycle": self.chk_toggle_input.isChecked(),
            "stop_on_fail": self.chk_stop_on_fail.isChecked(),
        }
