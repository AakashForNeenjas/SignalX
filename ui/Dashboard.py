from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QTableWidget, QTableWidgetItem, QLabel, QComboBox, 
                             QGridLayout, QDialog, QFrame, QTextEdit, QInputDialog, QMessageBox, QHeaderView,
                             QDialogButtonBox, QFormLayout, QDoubleSpinBox, QSpinBox, QLineEdit, QSpacerItem, QSizePolicy)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QPainter, QBrush

# ... (LEDIndicator class remains same, skipping for brevity in this tool call if possible, but replace_file_content needs contiguous block. 
# I will assume I need to replace the imports and the Dashboard class methods related to UI and logic)

# Since I cannot skip lines in the middle easily without multiple chunks, I will replace the imports first, then the Dashboard class content.
# Actually, I'll do it in one go if I can match the context.

# Let's just update the imports and the Dashboard class.


class LEDIndicator(QWidget):
    def __init__(self, color=Qt.GlobalColor.green):
        super().__init__()
        self.setFixedSize(20, 20)
        self.default_color = color
        self.color = color
        self.active = False

    def set_active(self, active):
        self.active = active
        self.update()
    
    def set_error(self, is_error):
        """Set LED to red if error (1), green if no error (0)"""
        if is_error:
            self.color = Qt.GlobalColor.red
            self.active = True
        else:
            self.color = Qt.GlobalColor.green
            self.active = True
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        if self.active:
            brush = QBrush(self.color)
        else:
            brush = QBrush(QColor(50, 50, 50))  # Dark gray for off
            
        painter.setBrush(brush)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(0, 0, 20, 20)


class RampDialog(QDialog):
    """Dialog to get ramp parameters: start, step, end, delay, tolerance, retries"""
    def __init__(self, action_type="GS / Ramp Up Voltage", initial=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(action_type)
        self.layout = QVBoxLayout(self)
        form = QFormLayout()

        self.spin_start = QDoubleSpinBox()
        self.spin_start.setRange(-10000, 10000)
        self.spin_start.setDecimals(3)
        self.spin_start.setValue(initial.get('start', 230) if initial else 230)

        self.spin_step = QDoubleSpinBox()
        self.spin_step.setRange(0.0001, 10000)
        self.spin_step.setDecimals(3)
        self.spin_step.setValue(initial.get('step', 1) if initial else 1)

        self.spin_end = QDoubleSpinBox()
        self.spin_end.setRange(-10000, 10000)
        self.spin_end.setDecimals(3)
        self.spin_end.setValue(initial.get('end', 0) if initial else 0)

        self.spin_delay = QDoubleSpinBox()
        self.spin_delay.setRange(0, 3600)
        self.spin_delay.setDecimals(3)
        self.spin_delay.setValue(initial.get('delay', 0.5) if initial else 0.5)

        self.spin_tol = QDoubleSpinBox()
        self.spin_tol.setRange(0, 1000)
        self.spin_tol.setDecimals(3)
        self.spin_tol.setValue(initial.get('tolerance', 0.5) if initial else 0.5)

        self.spin_retries = QSpinBox()
        self.spin_retries.setRange(0, 100)
        self.spin_retries.setValue(initial.get('retries', 3) if initial else 3)

        form.addRow("Start Voltage (V)", self.spin_start)
        form.addRow("Step Increment (V)", self.spin_step)
        form.addRow("End Voltage (V)", self.spin_end)
        form.addRow("Delay between steps (s)", self.spin_delay)
        form.addRow("Tolerance (V)", self.spin_tol)
        form.addRow("Retries", self.spin_retries)

        self.layout.addLayout(form)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)

    def get_values(self):
        return {
            'start': self.spin_start.value(),
            'step': self.spin_step.value(),
            'end': self.spin_end.value(),
            'delay': self.spin_delay.value(),
            'tolerance': self.spin_tol.value(),
            'retries': self.spin_retries.value()
        }


class PSVISetDialog(QDialog):
    """Dialog to get PS set voltage/current parameters (V, I)"""
    def __init__(self, action_type="PS / HV: Battery Set Charge (V,I)", initial=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(action_type)
        self.layout = QVBoxLayout(self)
        form = QFormLayout()

        self.spin_voltage = QDoubleSpinBox()
        self.spin_voltage.setRange(-10000, 10000)
        self.spin_voltage.setDecimals(3)
        self.spin_voltage.setValue(initial.get('voltage', 400) if initial else 400)

        self.spin_current = QDoubleSpinBox()
        self.spin_current.setRange(0, 10000)
        self.spin_current.setDecimals(3)
        self.spin_current.setValue(initial.get('current', 10) if initial else 10)

        form.addRow("Voltage (V)", self.spin_voltage)
        form.addRow("Current (A)", self.spin_current)
        self.layout.addLayout(form)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)

    def get_values(self):
        return {
            'voltage': self.spin_voltage.value(),
            'current': self.spin_current.value()
        }

class CANSignalReadDialog(QDialog):
    """Dialog for CAN / Read Signal Value"""
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
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def get_values(self):
        return {
            'signal_name': self.txt_signal.text(),
            'timeout': self.spin_timeout.value()
        }
    
    def accept(self):
        if not self.txt_signal.text().strip():
            QMessageBox.warning(self, "Missing Signal", "Signal name is required.")
            return
        super().accept()

class CANSignalToleranceDialog(QDialog):
    """Dialog for CAN / Check Signal (Tolerance)"""
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
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def get_values(self):
        return {
            'signal_name': self.txt_signal.text(),
            'expected_value': self.spin_expected.value(),
            'tolerance': self.spin_tolerance.value(),
            'timeout': self.spin_timeout.value()
        }
    
    def accept(self):
        if not self.txt_signal.text().strip():
            QMessageBox.warning(self, "Missing Signal", "Signal name is required.")
            return
        super().accept()

class CANConditionalJumpDialog(QDialog):
    """Dialog for CAN / Conditional Jump"""
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
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def get_values(self):
        return {
            'signal_name': self.txt_signal.text(),
            'expected_value': self.spin_expected.value(),
            'tolerance': self.spin_tolerance.value(),
            'target_step': self.spin_target_step.value()
        }
    
    def accept(self):
        if not self.txt_signal.text().strip():
            QMessageBox.warning(self, "Missing Signal", "Signal name is required.")
            return
        super().accept()

class CANWaitSignalChangeDialog(QDialog):
    """Dialog for CAN / Wait For Signal Change"""
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
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def get_values(self):
        return {
            'signal_name': self.txt_signal.text(),
            'initial_value': self.spin_initial.value(),
            'timeout': self.spin_timeout.value(),
            'poll_interval': self.spin_poll.value()
        }
    
    def accept(self):
        if not self.txt_signal.text().strip():
            QMessageBox.warning(self, "Missing Signal", "Signal name is required.")
            return
        super().accept()

class CANMonitorRangeDialog(QDialog):
    """Dialog for CAN / Monitor Signal Range"""
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
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def get_values(self):
        return {
            'signal_name': self.txt_signal.text(),
            'min_val': self.spin_min.value(),
            'max_val': self.spin_max.value(),
            'duration': self.spin_duration.value(),
            'poll_interval': self.spin_poll.value()
        }
    
    def accept(self):
        if not self.txt_signal.text().strip():
            QMessageBox.warning(self, "Missing Signal", "Signal name is required.")
            return
        super().accept()

class CANCompareSignalsDialog(QDialog):
    """Dialog for CAN / Compare Two Signals"""
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
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def get_values(self):
        return {
            'signal1': self.txt_signal1.text(),
            'signal2': self.txt_signal2.text(),
            'tolerance': self.spin_tolerance.value(),
            'timeout': self.spin_timeout.value()
        }
    
    def accept(self):
        if not self.txt_signal1.text().strip() or not self.txt_signal2.text().strip():
            QMessageBox.warning(self, "Missing Signal", "Both signal names are required.")
            return
        super().accept()

class CANSetAndVerifyDialog(QDialog):
    """Dialog for CAN / Set Signal and Verify"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("CAN / Set Signal and Verify")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        self.spin_msg_id = QSpinBox()
        self.spin_msg_id.setRange(0, 0x7FF)
        self.spin_msg_id.setValue(0x100)
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
        
        form.addRow("Message ID (hex):", self.spin_msg_id)
        form.addRow("Signal Name:", self.txt_signal)
        form.addRow("Target Value:", self.spin_target)
        form.addRow("Tolerance:", self.spin_tolerance)
        form.addRow("Verify Timeout (s):", self.spin_verify_timeout)
        layout.addLayout(form)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def get_values(self):
        return {
            'message_id': self.spin_msg_id.value(),
            'signal_name': self.txt_signal.text(),
            'target_value': self.spin_target.value(),
            'tolerance': self.spin_tolerance.value(),
            'verify_timeout': self.spin_verify_timeout.value()
        }
    
    def accept(self):
        if not self.txt_signal.text().strip():
            QMessageBox.warning(self, "Missing Signal", "Signal name is required.")
            return
        super().accept()

class Dashboard(QWidget):
    # Signals
    sig_init_instrument = pyqtSignal()
    sig_connect_can = pyqtSignal()
    sig_disconnect_can = pyqtSignal()
    sig_start_cyclic = pyqtSignal()
    sig_stop_cyclic = pyqtSignal()
    sig_start_trace = pyqtSignal()
    sig_run_sequence = pyqtSignal()
    sig_stop_sequence = pyqtSignal()
    sig_estop = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.last_saved_path = None
        self.is_modified = False  # Track if sequence has been modified
        self.loaded_sequence_name = None  # Track loaded sequence name
        self.sequence_meta = {
            "name": "Unsaved Sequence",
            "author": "",
            "description": "",
            "tags": [],
            "version": 1
        }
        self.init_ui()
        self.connect_signals()
        
    def connect_signals(self):
        self.btn_init.clicked.connect(self.sig_init_instrument.emit)
        self.btn_connect_can.clicked.connect(self.sig_connect_can.emit)
        self.btn_disconnect_can.clicked.connect(self.sig_disconnect_can.emit)
        self.btn_start_cyclic.clicked.connect(self.sig_start_cyclic.emit)
        self.btn_stop_cyclic.clicked.connect(self.sig_stop_cyclic.emit)
        self.btn_save_log.clicked.connect(self.sig_save_log.emit)
        self.btn_run_seq.clicked.connect(self.sig_run_sequence.emit)
        self.btn_force_stop.clicked.connect(self.sig_estop.emit)

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        
        # Left Panel (Controls & Sequence)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # 1. Top Controls
        top_controls = QWidget()
        top_layout = QGridLayout(top_controls)
        
        self.btn_init = QPushButton("Initialize Instrument")
        self.btn_connect_can = QPushButton("Connect CAN")
        self.btn_start_cyclic = QPushButton("Start Cyclic CAN")
        self.btn_start_trace = QPushButton("Start Trace")
        self.btn_disconnect_can = QPushButton("Disconnect CAN")
        self.btn_stop_cyclic = QPushButton("Stop Cyclic CAN")
        
        # Add icons later
        
        top_layout.addWidget(self.btn_init, 0, 0)
        top_layout.addWidget(self.btn_start_trace, 0, 1)
        top_layout.addWidget(self.btn_connect_can, 1, 0)
        top_layout.addWidget(self.btn_disconnect_can, 1, 1)
        top_layout.addWidget(self.btn_start_cyclic, 2, 0)
        top_layout.addWidget(self.btn_stop_cyclic, 2, 1)
        
        left_layout.addWidget(top_controls)
        
        # 2. Sequence Editor
        seq_control_layout = QHBoxLayout()
        self.combo_step = QComboBox()
        self.combo_step.addItems([
                # Keep only GS-prefixed, CAN-prefixed, Wait, and Initialize Instruments
                # Grid Simulator (GS) Actions - prefixed with shortform 'GS'
                "GS / Check Error", "GS / Clear Protection", "GS / Get IDN",
                "GS / Measure Current AC", "GS / Measure Current DC", "GS / Measure Frequency",
                "GS / Measure Voltage AC", "GS / Measure Voltage DC",
                "GS / Measure Power Apparent", "GS / Measure Power Real", "GS / Measure Power Reactive",
                "GS / Measure THD Current", "GS / Measure THD Voltage",
                "GS / Power: OFF", "GS / Power: ON", "GS / Ramp Down Voltage", "GS / Ramp Up Voltage",
                "GS / Reset System", "GS / Set Current AC", "GS / Set Current DC",
                "GS / Set Frequency", "GS / Set Voltage AC", "GS / Set Voltage DC",
                # Power Supply (PS) actions - prefix as 'PS'
                "PS / HV: Connect", "PS / HV: Disconnect", "PS / HV: Output ON", "PS / HV: Output OFF",
                "PS / HV: Measure VI", "PS / HV: Set Voltage DC", "PS / HV: Set Current (CC)", "PS / HV: Set Current (CV)",
                "PS / HV: Ramp Up Voltage", "PS / HV: Ramp Down Voltage", "PS / HV: Battery Set Charge (V,I)",
                "PS / HV: Battery Set Discharge (V,I)", "PS / HV: Read Errors", "PS / HV: Clear Errors",
                "PS / HV: Sweep Voltage and Log", "PS / HV: Sweep Current and Log", "PS / Advanced: HV Sweep Voltage and Log",
                # CAN (CAN Manager) Actions - prefixed with 'CAN /'
                "CAN / Connect", "CAN / Disconnect", "CAN / Start Cyclic CAN", "CAN / Stop Cyclic CAN",
                "CAN / Start Trace", "CAN / Stop Trace", "CAN / Send Message", "CAN / Start Cyclic By Name",
                "CAN / Stop Cyclic By Name", "CAN / Check Message", "CAN / Listen For Message",
                "CAN / Read Signal Value", "CAN / Check Signal (Tolerance)", "CAN / Conditional Jump",
                "CAN / Wait For Signal Change", "CAN / Monitor Signal Range", "CAN / Compare Two Signals",
                "CAN / Set Signal and Verify",
                # Utility Actions
                "Wait",
                # Button Actions (UI Controls)
                "Initialize Instruments"
            ])
        self.btn_add_step = QPushButton("+ Add Step")
        self.running_test_label = QLabel("")  # Label to show running test name
        self.running_test_label.setStyleSheet("color: #00FF00; font-weight: bold;")
        
        seq_control_layout.addWidget(QLabel("Test Step"))
        seq_control_layout.addWidget(self.combo_step)
        seq_control_layout.addWidget(self.btn_add_step)
        seq_control_layout.addWidget(self.running_test_label)
        seq_control_layout.addStretch()
        
        left_layout.addLayout(seq_control_layout)
        
        # Table and Side Buttons
        table_container = QHBoxLayout()
        self.sequence_table = QTableWidget(0, 4)
        self.sequence_table.setHorizontalHeaderLabels(["Step", "Action", "Parameters", "Status"])
        self.sequence_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.sequence_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.sequence_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        
        table_buttons_layout = QVBoxLayout()
        self.btn_del_step = QPushButton("Delete Step")
        self.btn_move_up = QPushButton("Move Up")
        self.btn_move_down = QPushButton("Move Down")
        self.btn_edit_step = QPushButton("Edit Step")
        self.btn_duplicate = QPushButton("Duplicate")
        self.btn_force_stop = QPushButton("E-Stop")
        self.btn_force_stop.setStyleSheet("background-color: red; color: white; font-weight: bold;")
        
        table_buttons_layout.addWidget(self.btn_del_step)
        table_buttons_layout.addWidget(self.btn_move_up)
        table_buttons_layout.addWidget(self.btn_move_down)
        table_buttons_layout.addWidget(self.btn_edit_step)
        table_buttons_layout.addWidget(self.btn_duplicate)
        table_buttons_layout.addWidget(self.btn_force_stop)
        table_buttons_layout.addStretch()
        
        table_container.addWidget(self.sequence_table)
        table_container.addLayout(table_buttons_layout)
        
        left_layout.addLayout(table_container)
        
        # 3. Bottom Controls (Run/Load/Save)
        bottom_controls = QHBoxLayout()
        self.btn_run_seq = QPushButton("Run Sequence")
        self.btn_load_seq = QPushButton("Load Sequence")
        self.btn_save_seq = QPushButton("Save Sequence")
        self.btn_clear_seq = QPushButton("Clear Sequence")
        self.btn_clear_output = QPushButton("Clear Output")
        
        bottom_controls.addWidget(self.btn_run_seq)
        bottom_controls.addWidget(self.btn_load_seq)
        bottom_controls.addWidget(self.btn_save_seq)
        bottom_controls.addWidget(self.btn_clear_seq)
        bottom_controls.addWidget(self.btn_clear_output)
        bottom_controls.addStretch()
        
        left_layout.addLayout(bottom_controls)
        
        # 4. Output Diagnosis
        left_layout.addWidget(QLabel("Output Diagnosis"))
        self.output_log = QTextEdit()
        self.output_log.setReadOnly(True)
        self.output_log.setMaximumHeight(100)
        left_layout.addWidget(self.output_log)

        # Right Panel (Status Indicators)
        right_panel = QWidget()
        right_layout = QGridLayout(right_panel)
        
        # Dictionary to store value indicator widgets
        self.value_inputs = {}
        
        # Example indicators based on image
        indicators = [
            "BL Version", "FW Version", "HW Version",
            "Grid Voltage", "Grid Current", "Bus Voltage",
            "BMS Voltage", "HV Voltage", "HV Current",
            "LV Voltage", "LV Current", "OBC Temperature",
            "OBC FET Temp", "HP DCDC Temp", "Transformer Temp",
            "Charge Current Limit", "Discharge Current Limit", "Regen Current Limit"
        ]
        
        for i, name in enumerate(indicators):
            right_layout.addWidget(QLabel(name), i, 0)
            val_label = QLabel("0.0") # Placeholder value
            val_label.setStyleSheet("border: 1px solid gray; padding: 2px;")
            right_layout.addWidget(val_label, i, 1)
            # Store reference for updates
            self.value_inputs[name] = val_label
            
        # Error/Warning LEDs (Rightmost column)
        # Dictionary to store LED indicator widgets
        self.led_indicators = {}
        
        errors = [
            "OBC Input AC Over Voltage", "OBC Input AC Under Voltage", "OBC Input Over Current",
            "OBC Output Over Current", "OBC High Temperature", "OBC Low Temperature",
            "OBC Temp Sensor Fail", "OBC Current Sensing Fail", "OBC Contactor/Relay Fail",
            "OBC Output Open Circuit", "OBC Output Short Circuit", "OBC Output Over Voltage",
            "OBC Output Under Voltage", "DCDC Output Over Voltage", "DCDC Input Over Voltage",
            "DCDC Input Under Voltage", "DCDC Input Over Current", "DCDC Output Over Current",
            "DCDC High Temperature", "DCDC Low Temperature", "DCDC Temp Sensor Fail",
            "DCDC Current Sensing Fail", "DCDC Contactor/Relay Fail", "DCDC Output Open Circuit",
            "DCDC Output Short Circuit", "DCDC Output Under Voltage", "DCDC Input Over Voltage L2",
            "OBC Input AC Distorted", "OBC Input Short Circuit", "OBC Bus Over Voltage",
            "OBC Bus Short Out"
        ]
        
        # Create a separate widget/layout for the LED column to align properly
        led_container = QWidget()
        led_layout = QGridLayout(led_container)
        
        for i, name in enumerate(errors):
            led_layout.addWidget(QLabel(name), i, 0)
            led = LEDIndicator()
            led_layout.addWidget(led, i, 1)
            # Store reference for updates
            self.led_indicators[name] = led
            
        # Add panels to main layout
        main_layout.addWidget(left_panel, 60) # 60% width
        main_layout.addWidget(right_panel, 20) # 20% width
        main_layout.addWidget(led_container, 20) # 20% width
    
    def setup_ui_updates(self, signal_manager, can_mgr):
        """
        Setup timer-based UI updates to decouple CAN traffic from UI refresh.
        Refresh rate: 100ms (10Hz)
        """
        self.signal_manager = signal_manager
        self.can_mgr = can_mgr
        
        # Timer for UI updates (100ms)
        self.ui_update_timer = QTimer()
        self.ui_update_timer.timeout.connect(self.update_ui_from_cache)
        self.ui_update_timer.start(100)  # 100ms refresh rate
        
    def update_ui_from_cache(self):
        """Update all UI indicators from CANManager's signal cache"""
        if not hasattr(self, 'can_mgr') or not self.can_mgr:
            return
            
        # Get latest signal values from cache (thread-safe)
        signal_cache = self.can_mgr.get_all_signals_from_cache()
        
        # Iterate through mappings and update UI
        if hasattr(self, 'signal_manager') and self.signal_manager:
            for mapping in self.signal_manager.signal_mappings:
                dbc_signal = mapping['dbc_signal']
                ui_element_name = mapping['ui_element']
                signal_type = mapping['type']
                
                # Check if we have data for this signal
                if dbc_signal in signal_cache:
                    data = signal_cache[dbc_signal]
                    value = data.get('value')
                    
                    if value is not None:
                        self.update_single_indicator(ui_element_name, value, signal_type, mapping)

    def update_single_indicator(self, indicator_name: str, value, signal_type: str, mapping=None):
        """Update a single UI element"""
        # Find the corresponding QLineEdit for value indicators
        if signal_type == "value":
            if indicator_name in self.value_inputs:
                line_edit = self.value_inputs[indicator_name]
                # Format value based on type
                if isinstance(value, float):
                    line_edit.setText(f"{value:.2f}")
                else:
                    line_edit.setText(str(value))
        
        elif signal_type == "status":
            if indicator_name in self.led_indicators:
                led = self.led_indicators[indicator_name]
                # Update LED color based on error value
                # Default: 1 = Error (Red), 0 = OK (Green)
                error_val = mapping.get('error_value', 1) if mapping else 1
                is_error = (value == error_val)
                led.set_error(is_error)

    def connect_signals(self):
        self.btn_init.clicked.connect(self.sig_init_instrument.emit)
        self.btn_connect_can.clicked.connect(self.sig_connect_can.emit)
        self.btn_disconnect_can.clicked.connect(self.sig_disconnect_can.emit)
        self.btn_start_cyclic.clicked.connect(self.sig_start_cyclic.emit)
        self.btn_stop_cyclic.clicked.connect(self.sig_stop_cyclic.emit)
        self.btn_start_trace.clicked.connect(self.sig_start_trace.emit)
        self.btn_run_seq.clicked.connect(self.sig_run_sequence.emit)
        self.btn_force_stop.clicked.connect(self.sig_stop_sequence.emit)
        
        # Table Controls
        self.btn_add_step.clicked.connect(self.add_step)
        self.btn_del_step.clicked.connect(self.delete_step)
        self.btn_move_up.clicked.connect(self.move_up)
        self.btn_move_down.clicked.connect(self.move_down)
        self.btn_edit_step.clicked.connect(self.edit_step)
        self.btn_duplicate.clicked.connect(self.duplicate_step)
        self.btn_clear_seq.clicked.connect(self.clear_sequence)
        self.btn_clear_output.clicked.connect(self.clear_output)
        self.btn_save_seq.clicked.connect(self.save_sequence)
        self.btn_load_seq.clicked.connect(self.load_sequence)

    def add_step(self):
        action = self.combo_step.currentText()
        params = ""
        # Handle GS Ramp actions with a structured dialog
        if action.startswith("GS / Ramp"):
            # Show dialog to get start, step, end, delay, tolerance and retries
            dialog = RampDialog(action_type=action)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                data = dialog.get_values()
                import json
                params = json.dumps(data)
            else:
                return  # Cancelled
        elif action.startswith("CAN /"):
            # Parametered CAN actions - prompt accordingly
            # CAN / Send Message -> params: {id, data list, is_extended}
            if "Send Message" in action:
                text, ok = QInputDialog.getText(self, "CAN Send Message", "Enter ID (hex) and Data bytes (comma separated). e.g. 0x123,01,02,03")
                if ok:
                    # Normalize input to JSON
                    try:
                        parts = [p.strip() for p in text.split(',') if p.strip()]
                        msg_id_raw = parts[0]
                        if msg_id_raw.lower().startswith('0x'):
                            msg_id = int(msg_id_raw, 16)
                        else:
                            msg_id = int(msg_id_raw)
                        data_bytes = [int(x, 16) if x.lower().startswith('0x') else int(x) for x in parts[1:]]
                        import json
                        params = json.dumps({'id': msg_id, 'data': data_bytes})
                    except Exception:
                        params = text
                else:
                    return
            elif "Start Cyclic By Name" in action or "Stop Cyclic By Name" in action:
                text, ok = QInputDialog.getText(self, "CAN Cyclic by Name", "Enter message name and cycle time in ms (e.g. Vehicle_Mode,100)")
                if ok:
                    try:
                        msg_name, cycle = [p.strip() for p in text.split(',')]
                        import json
                        params = json.dumps({'message_name': msg_name, 'cycle_time': int(cycle)})
                    except Exception:
                        params = text
                else:
                    return
            elif "Check Message" in action or "Listen For Message" in action:
                text, ok = QInputDialog.getText(self, "CAN Message Check", "Enter message ID or name and optional timeout (e.g. 0x123,2)")
                if ok:
                    params = text
                else:
                    return
            elif "Read Signal Value" in action:
                dialog = CANSignalReadDialog(parent=self)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    import json
                    params = json.dumps(dialog.get_values())
                else:
                    return
            elif "Check Signal (Tolerance)" in action:
                dialog = CANSignalToleranceDialog(parent=self)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    import json
                    params = json.dumps(dialog.get_values())
                else:
                    return
            elif "Conditional Jump" in action:
                dialog = CANConditionalJumpDialog(parent=self)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    import json
                    params = json.dumps(dialog.get_values())
                else:
                    return
            elif "Wait For Signal Change" in action:
                dialog = CANWaitSignalChangeDialog(parent=self)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    import json
                    params = json.dumps(dialog.get_values())
                else:
                    return
            elif "Monitor Signal Range" in action:
                dialog = CANMonitorRangeDialog(parent=self)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    import json
                    params = json.dumps(dialog.get_values())
                else:
                    return
            elif "Compare Two Signals" in action:
                dialog = CANCompareSignalsDialog(parent=self)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    import json
                    params = json.dumps(dialog.get_values())
                else:
                    return
            elif "Set Signal and Verify" in action:
                dialog = CANSetAndVerifyDialog(parent=self)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    import json
                    params = json.dumps(dialog.get_values())
                else:
                    return
            else:
                # Other CAN actions: no params, leave blank
                params = ""
        elif action.startswith("PS /"):
            # Power Supply (HV) actions
            if "Battery Set Charge" in action or "Battery Set Discharge" in action:
                # Show a small dialog to collect voltage and current
                # Parse possible initial JSON
                try:
                    import json
                    initial = {}
                    # No prefill available by default
                except Exception:
                    initial = {}
                dialog = PSVISetDialog(action_type=action, initial=initial)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    data = dialog.get_values()
                    import json
                    params = json.dumps(data)
                else:
                    return
            elif "Sweep Voltage" in action or "Sweep Current" in action or "Advanced: HV Sweep" in action:
                # Use Ramp dialog for sweep parameters and ask for optional filename
                dialog = RampDialog(action_type=action)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    data = dialog.get_values()
                    import json
                    # optional log filename
                    fname, ok = QInputDialog.getText(self, "Log Filename", "Optional log filename (no path, leave blank for default):")
                    if ok and fname:
                        data['log_file'] = fname
                    params = json.dumps(data)
                else:
                    return
            elif "Ramp" in action:
                # Reuse ramp dialog for PS ramp
                dialog = RampDialog(action_type=action)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    data = dialog.get_values()
                    import json
                    params = json.dumps(data)
                else:
                    return
            elif "Set" in action or "Measure" in action or "Read Errors" in action or "Clear Errors" in action:
                # These actions likely take a single value (Set Voltage/Current or Set Mode)
                text, ok = QInputDialog.getText(self, "Input Parameters", f"Enter value for {action}:")
                if ok:
                    params = text
                else:
                    return
        elif "Set" in action or "Wait" in action:
            text, ok = QInputDialog.getText(self, "Input Parameters", f"Enter value for {action}:")
            if ok:
                params = text
            else:
                return # Cancelled
        
        row = self.sequence_table.rowCount()
        self.sequence_table.insertRow(row)
        self.sequence_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
        self.sequence_table.setItem(row, 1, QTableWidgetItem(action))
        # If ramp GC param JSON, create a friendly display text and save JSON in UserRole
        if action.startswith("GS / Ramp") and params:
            import json
            try:
                data = json.loads(params)
                display = f"Start:{data.get('start')} Step:{data.get('step')} End:{data.get('end')} Delay:{data.get('delay')}s"
            except Exception:
                display = params
            item = QTableWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, params)
            self.sequence_table.setItem(row, 2, item)
        elif action.startswith("PS /") and params:
            import json
            try:
                data = json.loads(params)
                if 'voltage' in data and 'current' in data:
                    display = f"V:{data.get('voltage')}V I:{data.get('current')}A"
                elif 'start' in data:
                    display = f"Start:{data.get('start')} Step:{data.get('step')} End:{data.get('end')} Delay:{data.get('delay')}s"
                    if 'log_file' in data:
                        display += f" Log:{data.get('log_file')}"
                else:
                    display = params
            except Exception:
                display = params
            item = QTableWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, params)
            self.sequence_table.setItem(row, 2, item)
        else:
            item = QTableWidgetItem(params)
            # If CAN or JSON-like params, save raw JSON in UserRole for preserving exact structure
            if action.startswith("CAN /") or (params and params.strip().startswith('{')):
                try:
                    item.setData(Qt.ItemDataRole.UserRole, params)
                except Exception:
                    pass
            self.sequence_table.setItem(row, 2, item)
        self.sequence_table.setItem(row, 3, QTableWidgetItem("Pending"))
        self.is_modified = True  # Mark as modified

    def delete_step(self):
        row = self.sequence_table.currentRow()
        if row >= 0:
            self.sequence_table.removeRow(row)
            self.renumber_steps()
            self.is_modified = True  # Mark as modified

    def move_up(self):
        row = self.sequence_table.currentRow()
        if row > 0:
            self._swap_rows(row, row - 1)
            self.sequence_table.selectRow(row - 1)

    def move_down(self):
        row = self.sequence_table.currentRow()
        if row < self.sequence_table.rowCount() - 1 and row >= 0:
            self._swap_rows(row, row + 1)
            self.sequence_table.selectRow(row + 1)

    def _swap_rows(self, row1, row2):
        for col in range(self.sequence_table.columnCount()):
            item1 = self.sequence_table.takeItem(row1, col)
            item2 = self.sequence_table.takeItem(row2, col)
            self.sequence_table.setItem(row1, col, item2)
            self.sequence_table.setItem(row2, col, item1)
        self.renumber_steps()

    def edit_step(self):
        import json
        row = self.sequence_table.currentRow()
        if row >= 0:
            current_action = self.sequence_table.item(row, 1).text()
            params_item = self.sequence_table.item(row, 2)
            try:
                current_params = params_item.data(Qt.ItemDataRole.UserRole) or params_item.text()
            except Exception:
                current_params = params_item.text() if params_item else ""
            
            # Parse initial params
            initial = {}
            try:
                initial = json.loads(current_params) if isinstance(current_params, str) else current_params
            except Exception:
                pass
            
            if current_action.startswith("GS / Ramp"):
                dialog = RampDialog(action_type=current_action, initial=initial)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    data = dialog.get_values()
                    json_text = json.dumps(data)
                    display = f"Start:{data.get('start')} Step:{data.get('step')} End:{data.get('end')} Delay:{data.get('delay')}s"
                    item = QTableWidgetItem(display)
                    item.setData(Qt.ItemDataRole.UserRole, json_text)
                    self.sequence_table.setItem(row, 2, item)
                    self.is_modified = True
                    
            elif current_action.startswith("CAN /"):
                # CAN signal test action dialogs
                if "Read Signal Value" in current_action:
                    dialog = CANSignalReadDialog(initial=initial)
                    if dialog.exec() == QDialog.DialogCode.Accepted:
                        data = dialog.get_values()
                        json_text = json.dumps(data)
                        display = f"Signal:{data.get('signal_name')} Timeout:{data.get('timeout')}s"
                        item = QTableWidgetItem(display)
                        item.setData(Qt.ItemDataRole.UserRole, json_text)
                        self.sequence_table.setItem(row, 2, item)
                        self.is_modified = True
                        
                elif "Check Signal (Tolerance)" in current_action:
                    dialog = CANSignalToleranceDialog(initial=initial)
                    if dialog.exec() == QDialog.DialogCode.Accepted:
                        data = dialog.get_values()
                        json_text = json.dumps(data)
                        display = f"Signal:{data.get('signal_name')} Expected:{data.get('expected_value')} ±{data.get('tolerance')}"
                        item = QTableWidgetItem(display)
                        item.setData(Qt.ItemDataRole.UserRole, json_text)
                        self.sequence_table.setItem(row, 2, item)
                        self.is_modified = True
                        
                elif "Conditional Jump" in current_action:
                    dialog = CANConditionalJumpDialog(initial=initial)
                    if dialog.exec() == QDialog.DialogCode.Accepted:
                        data = dialog.get_values()
                        json_text = json.dumps(data)
                        display = f"Signal:{data.get('signal_name')} = {data.get('expected_value')} → Step {data.get('target_step')}"
                        item = QTableWidgetItem(display)
                        item.setData(Qt.ItemDataRole.UserRole, json_text)
                        self.sequence_table.setItem(row, 2, item)
                        self.is_modified = True
                        
                elif "Wait For Signal Change" in current_action:
                    dialog = CANWaitSignalChangeDialog(initial=initial)
                    if dialog.exec() == QDialog.DialogCode.Accepted:
                        data = dialog.get_values()
                        json_text = json.dumps(data)
                        display = f"Signal:{data.get('signal_name')} Timeout:{data.get('timeout')}s"
                        item = QTableWidgetItem(display)
                        item.setData(Qt.ItemDataRole.UserRole, json_text)
                        self.sequence_table.setItem(row, 2, item)
                        self.is_modified = True
                        
                elif "Monitor Signal Range" in current_action:
                    dialog = CANMonitorRangeDialog(initial=initial)
                    if dialog.exec() == QDialog.DialogCode.Accepted:
                        data = dialog.get_values()
                        json_text = json.dumps(data)
                        display = f"Signal:{data.get('signal_name')} [{data.get('min_val')}, {data.get('max_val')}] Duration:{data.get('duration')}s"
                        item = QTableWidgetItem(display)
                        item.setData(Qt.ItemDataRole.UserRole, json_text)
                        self.sequence_table.setItem(row, 2, item)
                        self.is_modified = True
                        
                elif "Compare Two Signals" in current_action:
                    dialog = CANCompareSignalsDialog(initial=initial)
                    if dialog.exec() == QDialog.DialogCode.Accepted:
                        data = dialog.get_values()
                        json_text = json.dumps(data)
                        display = f"{data.get('signal1')} vs {data.get('signal2')} ±{data.get('tolerance')}"
                        item = QTableWidgetItem(display)
                        item.setData(Qt.ItemDataRole.UserRole, json_text)
                        self.sequence_table.setItem(row, 2, item)
                        self.is_modified = True
                        
                elif "Set Signal and Verify" in current_action:
                    dialog = CANSetAndVerifyDialog(initial=initial)
                    if dialog.exec() == QDialog.DialogCode.Accepted:
                        data = dialog.get_values()
                        json_text = json.dumps(data)
                        display = f"Signal:{data.get('signal_name')} = {data.get('target_value')} (verify {data.get('verify_timeout')}s)"
                        item = QTableWidgetItem(display)
                        item.setData(Qt.ItemDataRole.UserRole, json_text)
                        self.sequence_table.setItem(row, 2, item)
                        self.is_modified = True
                        
                elif "Send Message" in current_action:
                    text, ok = QInputDialog.getText(self, "Edit CAN Send", "Enter ID (hex) and Data (comma separated):", text=current_params)
                    if ok:
                        try:
                            j = json.loads(text)
                            item = QTableWidgetItem(f"ID:0x{int(j.get('id')):X} Data:{j.get('data')}")
                            item.setData(Qt.ItemDataRole.UserRole, text)
                            self.sequence_table.setItem(row, 2, item)
                        except Exception:
                            self.sequence_table.setItem(row, 2, QTableWidgetItem(text))
                        self.is_modified = True
                        
                elif "Start Cyclic By Name" in current_action or "Stop Cyclic By Name" in current_action:
                    text, ok = QInputDialog.getText(self, "Edit CAN Cyclic", "Enter message name and cycle ms:", text=current_params)
                    if ok:
                        try:
                            parts = [p.strip() for p in text.split(',')]
                            json_text = json.dumps({'message_name': parts[0], 'cycle_time': int(parts[1]) if len(parts) > 1 else 100})
                            item = QTableWidgetItem(f"Message:{parts[0]} Cycle:{int(parts[1])}ms" if len(parts) > 1 else f"Message:{parts[0]}")
                            item.setData(Qt.ItemDataRole.UserRole, json_text)
                            self.sequence_table.setItem(row, 2, item)
                        except Exception:
                            self.sequence_table.setItem(row, 2, QTableWidgetItem(text))
                        self.is_modified = True
                        
                elif "Check Message" in current_action or "Listen For Message" in current_action:
                    text, ok = QInputDialog.getText(self, "Edit CAN Check", "Enter message ID or name, timeout:", text=current_params)
                    if ok:
                        self.sequence_table.setItem(row, 2, QTableWidgetItem(text))
                        self.is_modified = True
                else:
                    QMessageBox.information(self, "Info", "No parameters for this CAN action.")
                    
            elif current_action.startswith("PS /"):
                if "Battery Set Charge" in current_action or "Battery Set Discharge" in current_action:
                    dialog = PSVISetDialog(action_type=current_action, initial=initial)
                    if dialog.exec() == QDialog.DialogCode.Accepted:
                        data = dialog.get_values()
                        json_text = json.dumps(data)
                        display = f"V:{data.get('voltage')}V I:{data.get('current')}A"
                        item = QTableWidgetItem(display)
                        item.setData(Qt.ItemDataRole.UserRole, json_text)
                        self.sequence_table.setItem(row, 2, item)
                        self.is_modified = True
                elif "Sweep" in current_action or "Ramp" in current_action:
                    dialog = RampDialog(action_type=current_action, initial=initial)
                    if dialog.exec() == QDialog.DialogCode.Accepted:
                        data = dialog.get_values()
                        json_text = json.dumps(data)
                        display = f"Start:{data.get('start')} Step:{data.get('step')} End:{data.get('end')} Delay:{data.get('delay')}s"
                        if 'log_file' in data:
                            display += f" Log:{data.get('log_file')}"
                        item = QTableWidgetItem(display)
                        item.setData(Qt.ItemDataRole.UserRole, json_text)
                        self.sequence_table.setItem(row, 2, item)
                        self.is_modified = True
                else:
                    text, ok = QInputDialog.getText(self, "Edit Parameters", f"Enter value for {current_action}:", text=current_params)
                    if ok:
                        self.sequence_table.setItem(row, 2, QTableWidgetItem(text))
                        self.is_modified = True
            else:
                QMessageBox.information(self, "Info", "This action has no parameters to edit.")

    def duplicate_step(self):
        row = self.sequence_table.currentRow()
        if row >= 0:
            action = self.sequence_table.item(row, 1).text()
            params = self.sequence_table.item(row, 2).text()
            
            new_row = self.sequence_table.rowCount()
            self.sequence_table.insertRow(new_row)
            self.sequence_table.setItem(new_row, 0, QTableWidgetItem(str(new_row + 1)))
            self.sequence_table.setItem(new_row, 1, QTableWidgetItem(action))
            self.sequence_table.setItem(new_row, 2, QTableWidgetItem(params))
            self.sequence_table.setItem(new_row, 3, QTableWidgetItem("Pending"))
            self.is_modified = True  # Mark as modified

    def clear_sequence(self):
        self.sequence_table.setRowCount(0)
        self.is_modified = False  # Reset modification flag
        self.loaded_sequence_name = None  # Clear loaded sequence name
        self.sequence_meta["name"] = "Unsaved Sequence"

    def clear_output(self):
        """Clear the output diagnosis log"""
        self.output_log.clear()

    def save_sequence(self):
        """Save current sequence to Test Sequence folder"""
        import os
        import json
        from datetime import datetime
        from PyQt6.QtWidgets import QFileDialog
        from PyQt6.QtWidgets import QDialog, QFormLayout, QDialogButtonBox, QLineEdit, QVBoxLayout, QLabel
        
        # Create Test Sequence folder if it doesn't exist
        seq_dir = "Test Sequence"
        if not os.path.exists(seq_dir):
            os.makedirs(seq_dir)
        
        # Open file dialog
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save Test Sequence",
            os.path.join(seq_dir, "sequence.json"),
            "JSON Files (*.json)"
        )
        
        if filename:
            try:
                steps = self.get_sequence_steps()
                # Prompt for metadata before saving
                meta_dialog = QDialog(self)
                meta_dialog.setWindowTitle("Test Details")
                meta_dialog.setWindowIcon(self.windowIcon())
                form = QFormLayout(meta_dialog)
                name_edit = QLineEdit(self.sequence_meta.get("name", os.path.basename(filename).replace('.json', '')))
                author_edit = QLineEdit(self.sequence_meta.get("author", ""))
                desc_edit = QLineEdit(self.sequence_meta.get("description", ""))
                tags_edit = QLineEdit(", ".join(self.sequence_meta.get("tags", [])))
                form.addRow("Name:", name_edit)
                form.addRow("Author:", author_edit)
                form.addRow("Description:", desc_edit)
                form.addRow("Tags (comma):", tags_edit)
                buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, parent=meta_dialog)
                buttons.accepted.connect(meta_dialog.accept)
                buttons.rejected.connect(meta_dialog.reject)
                vbox = QVBoxLayout()
                vbox.addLayout(form)
                # Spacer to push buttons to bottom
                vbox.addItem(QSpacerItem(0, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
                vbox.addWidget(buttons)
                vbox.setAlignment(buttons, Qt.AlignmentFlag.AlignRight)
                meta_dialog.setLayout(vbox)
                result = meta_dialog.exec()
                # If user cancels, still proceed to save with existing/default meta
                if result == QDialog.DialogCode.Rejected:
                    name_val = self.sequence_meta.get("name", os.path.basename(filename).replace('.json', ''))
                    author_val = self.sequence_meta.get("author", "")
                    desc_val = self.sequence_meta.get("description", "")
                    tags_val = ", ".join(self.sequence_meta.get("tags", []))
                else:
                    name_val = name_edit.text().strip() or os.path.basename(filename).replace('.json', '')
                    author_val = author_edit.text().strip()
                    desc_val = desc_edit.text().strip()
                    tags_val = tags_edit.text().strip()
                meta = self.sequence_meta.copy()
                meta["name"] = name_val or os.path.basename(filename).replace('.json', '')
                meta["author"] = author_val
                meta["description"] = desc_val
                meta["tags"] = [t.strip() for t in tags_val.split(",") if t.strip()] if tags_val else []
                meta["name"] = os.path.basename(filename).replace('.json', '')
                meta["last_modified"] = datetime.now().isoformat()
                payload = {
                    "meta": meta,
                    "steps": steps
                }
                with open(filename, 'w') as f:
                    json.dump(payload, f, indent=2, sort_keys=True)
                self.output_log.append(f"✓ Sequence saved to: {filename}")
                self.last_saved_path = filename  # Store for later use
                self.loaded_sequence_name = os.path.basename(filename).replace('.json', '')
                self.sequence_meta = meta
                self.is_modified = False  # Reset modification flag after save
                return filename
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save sequence: {e}")
        return None

    def load_sequence(self):
        """Load sequence from Test Sequence folder"""
        import os
        import json
        from PyQt6.QtWidgets import QFileDialog
        
        # Create Test Sequence folder if it doesn't exist
        seq_dir = "Test Sequence"
        if not os.path.exists(seq_dir):
            os.makedirs(seq_dir)
        
        # Open file dialog
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Load Test Sequence",
            seq_dir,
            "JSON Files (*.json)"
        )
        
        if filename:
            try:
                with open(filename, 'r') as f:
                    payload = json.load(f)
                if isinstance(payload, dict) and "steps" in payload:
                    steps = payload.get("steps", [])
                    self.sequence_meta = payload.get("meta", self.sequence_meta)
                else:
                    steps = payload  # backward compatibility (list only)
                
                # Clear current sequence
                self.sequence_table.setRowCount(0)
                
                # Load steps
                for step in steps:
                    row = self.sequence_table.rowCount()
                    self.sequence_table.insertRow(row)
                    self.sequence_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
                    self.sequence_table.setItem(row, 1, QTableWidgetItem(step['action']))
                    # Try to parse params as JSON and show friendly summary for ramps
                    params_text = step.get('params', '')
                    try:
                        import json
                        data = json.loads(params_text) if params_text else None
                        if data and step['action'].startswith('GS / Ramp'):
                            display = f"Start:{data.get('start')} Step:{data.get('step')} End:{data.get('end')} Delay:{data.get('delay')}s"
                            item = QTableWidgetItem(display)
                            item.setData(Qt.ItemDataRole.UserRole, params_text)
                            self.sequence_table.setItem(row, 2, item)
                        elif data and step['action'].startswith('CAN /'):
                            # Display friendly CAN param text
                            if 'id' in data:
                                display = f"ID:0x{int(data['id']):X} Data:{data.get('data', [])}"
                            elif 'message_name' in data:
                                display = f"Message:{data.get('message_name')} Cycle:{data.get('cycle_time') or data.get('cycle', '')}ms"
                            else:
                                display = params_text
                            item = QTableWidgetItem(display)
                            item.setData(Qt.ItemDataRole.UserRole, params_text)
                            self.sequence_table.setItem(row, 2, item)
                        elif data and step['action'].startswith('PS /'):
                            # Display friendly PS params
                            if 'voltage' in data and 'current' in data:
                                display = f"V:{data.get('voltage')}V I:{data.get('current')}A"
                            elif 'start' in data:
                                display = f"Start:{data.get('start')} Step:{data.get('step')} End:{data.get('end')} Delay:{data.get('delay')}s"
                                if 'log_file' in data:
                                    display += f" Log:{data.get('log_file')}"
                            else:
                                display = params_text
                            item = QTableWidgetItem(display)
                            item.setData(Qt.ItemDataRole.UserRole, params_text)
                            self.sequence_table.setItem(row, 2, item)
                        else:
                            self.sequence_table.setItem(row, 2, QTableWidgetItem(params_text))
                    except Exception:
                        self.sequence_table.setItem(row, 2, QTableWidgetItem(params_text))
                    self.sequence_table.setItem(row, 3, QTableWidgetItem("Pending"))
                
                self.output_log.append(f"✓ Sequence loaded from: {filename}")
                self.loaded_sequence_name = os.path.basename(filename).replace('.json', '')
                self.last_saved_path = filename
                self.is_modified = False  # Mark as not modified after loading
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load sequence: {e}")

    def renumber_steps(self):
        for row in range(self.sequence_table.rowCount()):
            self.sequence_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))

    def get_sequence_steps(self):
        steps = []
        for row in range(self.sequence_table.rowCount()):
            action = self.sequence_table.item(row, 1).text()
            params_item = self.sequence_table.item(row, 2)
            # Try to get raw JSON from UserRole (used for ramps), otherwise use displayed text
            try:
                raw_params = params_item.data(Qt.ItemDataRole.UserRole)
            except Exception:
                raw_params = None
            params_text = raw_params if raw_params else params_item.text() if params_item else ""
            steps.append({
                'action': action,
                'params': params_text
            })
        return steps
    
    def update_step_status(self, index, status):
        """Update the status of a specific step in the table with color coding"""
        from PyQt6.QtGui import QColor, QBrush
        from PyQt6.QtCore import Qt
        
        if index < self.sequence_table.rowCount():
            item = QTableWidgetItem(status)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            
            # Set font color based on status (no background color)
            if status == "Pass":
                item.setForeground(QBrush(QColor(0, 255, 0)))  # Bright Green
            elif status == "Fail":
                item.setForeground(QBrush(QColor(255, 0, 0)))  # Bright Red
            elif status == "Running":
                item.setForeground(QBrush(QColor(255, 165, 0)))  # Orange
            # Pending remains default color
            
            self.sequence_table.setItem(index, 3, item)
    
    def set_running_test_name(self, test_name):
        """Display the currently running test name"""
        self.running_test_label.setText(f"Running: {test_name}")
    
    def clear_running_test_name(self):
        """Clear the running test name display"""
        self.running_test_label.setText("")
        

