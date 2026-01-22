from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QDoubleSpinBox,
    QSpinBox,
    QLabel,
    QPushButton,
    QDialogButtonBox,
    QWidget,
    QHBoxLayout,
    QCheckBox,
)


class LineLoadDialog(QDialog):
    """Dialog for Line and Load Regulation action parameters."""

    def __init__(self, action_type="RAMP / Line and Load Regulation", initial=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(action_type)
        self.layout = QVBoxLayout(self)
        form = QFormLayout()

        def _spin(default, min_val=-10000, max_val=10000, decimals=3):
            spin = QDoubleSpinBox()
            spin.setRange(min_val, max_val)
            spin.setDecimals(decimals)
            spin.setValue(default)
            return spin

        def _section_label(text):
            lbl = QLabel(text)
            lbl.setStyleSheet("color: #9db4d4; font-weight: bold; padding-top: 6px;")
            return lbl

        gs = initial.get("gs", {}) if initial else {}
        ps = initial.get("ps", {}) if initial else {}
        dl = initial.get("dl", {}) if initial else {}
        verify = initial.get("verify", {}) if initial else {}

        form.addRow(_section_label("Grid Simulator (GS)"))
        self.gs_start = _spin(gs.get("start", 0))
        self.gs_step = _spin(gs.get("step", 1), min_val=0.0001, max_val=10000)
        self.gs_end = _spin(gs.get("end", 0))
        self.gs_dwell = _spin(gs.get("dwell", 0.5), min_val=0, max_val=3600)
        self.gs_tol = _spin(gs.get("tolerance", 0.5), min_val=0, max_val=1000)
        form.addRow("GS Start (V)", self.gs_start)
        form.addRow("GS Step (V)", self.gs_step)
        form.addRow("GS End (V)", self.gs_end)
        form.addRow("GS Dwell (s)", self.gs_dwell)
        form.addRow("GS Tolerance (V)", self.gs_tol)

        form.addRow(_section_label("Power Supply (PS)"))
        self.ps_start = _spin(ps.get("start", 0))
        self.ps_step = _spin(ps.get("step", 1), min_val=0.0001, max_val=10000)
        self.ps_end = _spin(ps.get("end", 0))
        self.ps_dwell = _spin(ps.get("dwell", 0.5), min_val=0, max_val=3600)
        self.ps_tol = _spin(ps.get("tolerance", 0.5), min_val=0, max_val=1000)
        form.addRow("PS Start (V)", self.ps_start)
        form.addRow("PS Step (V)", self.ps_step)
        form.addRow("PS End (V)", self.ps_end)
        form.addRow("PS Dwell (s)", self.ps_dwell)
        form.addRow("PS Tolerance (V)", self.ps_tol)

        form.addRow(_section_label("DC Load (DL)"))
        self.dl_start = _spin(dl.get("start", 0))
        self.dl_step = _spin(dl.get("step", 1), min_val=0.0001, max_val=10000)
        self.dl_end = _spin(dl.get("end", 0))
        self.dl_dwell = _spin(dl.get("dwell", 0.5), min_val=0, max_val=3600)
        self.dl_tol = _spin(dl.get("tolerance", 0.1), min_val=0, max_val=1000)
        form.addRow("DL Start (A)", self.dl_start)
        form.addRow("DL Step (A)", self.dl_step)
        form.addRow("DL End (A)", self.dl_end)
        form.addRow("DL Dwell (s)", self.dl_dwell)
        form.addRow("DL Tolerance (A)", self.dl_tol)

        self.spin_retries = QSpinBox()
        self.spin_retries.setRange(0, 100)
        self.spin_retries.setValue(int(initial.get("retries", 2)) if initial else 2)
        form.addRow("Retries", self.spin_retries)

        self.check_verify_gs = QPushButton("Verify GS setpoint")
        self.check_verify_gs.setCheckable(True)
        self.check_verify_gs.setChecked(bool(verify.get("gs", True)) if initial else True)
        self.check_verify_ps = QPushButton("Verify PS setpoint")
        self.check_verify_ps.setCheckable(True)
        self.check_verify_ps.setChecked(bool(verify.get("ps", True)) if initial else True)
        self.check_verify_dl = QPushButton("Verify DL setpoint")
        self.check_verify_dl.setCheckable(True)
        self.check_verify_dl.setChecked(bool(verify.get("dl", True)) if initial else True)

        verify_row = QHBoxLayout()
        verify_row.addWidget(self.check_verify_gs)
        verify_row.addWidget(self.check_verify_ps)
        verify_row.addWidget(self.check_verify_dl)
        verify_widget = QWidget()
        verify_widget.setLayout(verify_row)
        form.addRow("Verify", verify_widget)

        self.check_dl_reset = QPushButton("Disable DL between PS steps")
        self.check_dl_reset.setCheckable(True)
        self.check_dl_reset.setChecked(bool(initial.get("dl_reset", True)) if initial else True)
        form.addRow("DL Reset", self.check_dl_reset)

        self.check_abort = QPushButton("Abort on first failure")
        self.check_abort.setCheckable(True)
        self.check_abort.setChecked(bool(initial.get("abort_on_fail", True)) if initial else True)
        form.addRow("Abort", self.check_abort)

        self.check_plot = QCheckBox("Include efficiency plot in report")
        self.check_plot.setChecked(bool(initial.get("plot_efficiency", False)) if initial else False)
        form.addRow("Plot", self.check_plot)

        self.layout.addLayout(form)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)

    def get_values(self):
        return {
            "gs": {
                "start": self.gs_start.value(),
                "step": self.gs_step.value(),
                "end": self.gs_end.value(),
                "dwell": self.gs_dwell.value(),
                "tolerance": self.gs_tol.value(),
            },
            "ps": {
                "start": self.ps_start.value(),
                "step": self.ps_step.value(),
                "end": self.ps_end.value(),
                "dwell": self.ps_dwell.value(),
                "tolerance": self.ps_tol.value(),
            },
            "dl": {
                "start": self.dl_start.value(),
                "step": self.dl_step.value(),
                "end": self.dl_end.value(),
                "dwell": self.dl_dwell.value(),
                "tolerance": self.dl_tol.value(),
            },
            "verify": {
                "gs": self.check_verify_gs.isChecked(),
                "ps": self.check_verify_ps.isChecked(),
                "dl": self.check_verify_dl.isChecked(),
            },
            "retries": self.spin_retries.value(),
            "dl_reset": self.check_dl_reset.isChecked(),
            "abort_on_fail": self.check_abort.isChecked(),
            "plot_efficiency": self.check_plot.isChecked(),
        }
