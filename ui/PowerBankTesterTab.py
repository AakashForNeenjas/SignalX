import time
import threading
from typing import Dict, Any, List

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QLineEdit,
    QDoubleSpinBox,
    QGroupBox,
    QCheckBox,
    QTableWidget,
    QTableWidgetItem,
    QListWidget,
    QTextEdit,
)

from core.powerbank.rs485 import (
    RaptorDevice,
    REGISTER_MAP,
    ALARM_BITS,
    FAULT_BITS,
    decode_running_block,
    decode_u16_words,
    decode_bitfield,
)

try:
    from serial.tools import list_ports
except Exception:  # pragma: no cover - optional dependency behavior
    list_ports = None


class PowerBankWorker(QThread):
    data_ready = pyqtSignal(dict)
    alarm_ready = pyqtSignal(list, list)
    status_ready = pyqtSignal(str)
    error_ready = pyqtSignal(str)

    def __init__(
        self,
        port: str,
        address: int,
        poll_period_s: float,
        baudrate: int,
        parity: str,
        stopbits: int,
        rs485_mode: bool,
        parent=None,
    ):
        super().__init__(parent)
        self.port = port
        self.address = address
        self.poll_period_s = poll_period_s
        self.baudrate = baudrate
        self.parity = parity
        self.stopbits = stopbits
        self.rs485_mode = rs485_mode
        self._stop_event = threading.Event()
        self._device = None
        self._last_error = ""
        self._last_error_ts = 0.0

    def stop(self):
        self._stop_event.set()

    def _emit_error(self, text: str, throttle_s: float = 2.0):
        now = time.time()
        if text == self._last_error and (now - self._last_error_ts) < throttle_s:
            return
        self._last_error = text
        self._last_error_ts = now
        self.error_ready.emit(text)

    def run(self):
        try:
            self._device = RaptorDevice(
                self.port,
                address=self.address,
                baudrate=self.baudrate,
                parity=self.parity,
                stopbits=self.stopbits,
                rs485_mode=self.rs485_mode,
            )
            self.status_ready.emit(f"Connected on {self.port}")
        except Exception as exc:
            self._emit_error(f"Connect failed: {exc}")
            return

        while not self._stop_event.is_set():
            cycle_start = time.time()
            try:
                running = self._device.read_running(0, 64)
                if running.get("status") == 0x00:
                    decoded = decode_running_block(running["data"], 0)
                    self.data_ready.emit(decoded)
                else:
                    self._emit_error(f"Running data status=0x{running.get('status', 0):02X}")

                af = self._device.read_alarm_fault()
                if af.get("status") == 0x00:
                    words = decode_u16_words(af["data"])
                    alarm_word = words[0] if len(words) > 0 else 0
                    fault_word = words[1] if len(words) > 1 else 0
                    alarms = decode_bitfield(alarm_word, ALARM_BITS)
                    faults = decode_bitfield(fault_word, FAULT_BITS)
                    self.alarm_ready.emit(alarms, faults)
                else:
                    self._emit_error(f"Alarm/Fault status=0x{af.get('status', 0):02X}")
            except Exception as exc:
                self._emit_error(str(exc))

            elapsed = time.time() - cycle_start
            sleep_s = max(0.0, self.poll_period_s - elapsed)
            self._stop_event.wait(sleep_s)

        try:
            if self._device:
                self._device.close()
        except Exception:
            pass
        self.status_ready.emit("Disconnected")


class PowerBankTesterTab(QWidget):
    def __init__(self, logger=None, parent=None):
        super().__init__(parent)
        self.logger = logger
        self.worker = None
        self.running_rows: Dict[str, int] = {}
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        header = QLabel("Power Bank Tester (RS485)")
        header.setStyleSheet("font-weight: bold; font-size: 16px;")
        layout.addWidget(header)

        conn_row = QHBoxLayout()
        self.port_combo = QComboBox()
        self.port_combo.setEditable(True)
        conn_row.addWidget(QLabel("COM Port:"))
        conn_row.addWidget(self.port_combo)
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_ports)
        conn_row.addWidget(self.refresh_btn)

        self.addr_edit = QLineEdit("0x000B")
        self.addr_edit.setMaximumWidth(120)
        conn_row.addWidget(QLabel("Address:"))
        conn_row.addWidget(self.addr_edit)

        self.poll_spin = QDoubleSpinBox()
        self.poll_spin.setRange(0.05, 5.0)
        self.poll_spin.setSingleStep(0.05)
        self.poll_spin.setValue(0.25)
        conn_row.addWidget(QLabel("Poll (s):"))
        conn_row.addWidget(self.poll_spin)

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.on_connect_clicked)
        conn_row.addWidget(self.connect_btn)
        conn_row.addStretch()
        layout.addLayout(conn_row)

        serial_row = QHBoxLayout()
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(["9600", "19200", "38400", "57600", "115200"])
        self.baud_combo.setCurrentText("115200")
        serial_row.addWidget(QLabel("Baud:"))
        serial_row.addWidget(self.baud_combo)

        self.parity_combo = QComboBox()
        self.parity_combo.addItems(["None", "Even", "Odd"])
        serial_row.addWidget(QLabel("Parity:"))
        serial_row.addWidget(self.parity_combo)

        self.stop_combo = QComboBox()
        self.stop_combo.addItems(["1", "2"])
        serial_row.addWidget(QLabel("Stop bits:"))
        serial_row.addWidget(self.stop_combo)

        self.rs485_check = QCheckBox("RS485 mode")
        self.rs485_check.setChecked(True)
        serial_row.addWidget(self.rs485_check)
        serial_row.addStretch()
        layout.addLayout(serial_row)

        self.status_label = QLabel("Disconnected")
        self.status_label.setStyleSheet("color: #9db4d4;")
        layout.addWidget(self.status_label)

        data_group = QGroupBox("Running Data")
        data_layout = QVBoxLayout()
        self.running_table = QTableWidget()
        self.running_table.setColumnCount(3)
        self.running_table.setHorizontalHeaderLabels(["Signal", "Value", "Unit"])
        self.running_table.verticalHeader().setVisible(False)
        self.running_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.running_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        data_layout.addWidget(self.running_table)
        data_group.setLayout(data_layout)
        layout.addWidget(data_group, 2)

        alarm_group = QGroupBox("Alarms / Faults")
        alarm_layout = QHBoxLayout()
        self.alarm_list = QListWidget()
        self.fault_list = QListWidget()
        alarm_layout.addWidget(self.alarm_list, 1)
        alarm_layout.addWidget(self.fault_list, 1)
        alarm_group.setLayout(alarm_layout)
        layout.addWidget(alarm_group, 1)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view, 1)

        self.refresh_ports()
        self._populate_running_table()

    def refresh_ports(self):
        self.port_combo.clear()
        ports = []
        if list_ports:
            ports = [p.device for p in list_ports.comports()]
        if not ports:
            ports = ["COM1", "COM2", "COM3"]
        self.port_combo.addItems(ports)

    def _populate_running_table(self):
        signals = [meta["name"] for _, meta in sorted(REGISTER_MAP["running_data"].items())]
        self.running_table.setRowCount(len(signals))
        self.running_rows.clear()
        for row, name in enumerate(signals):
            self.running_rows[name] = row
            self.running_table.setItem(row, 0, QTableWidgetItem(name))
            self.running_table.setItem(row, 1, QTableWidgetItem("-"))
            unit = ""
            for _, meta in REGISTER_MAP["running_data"].items():
                if meta.get("name") == name:
                    unit = meta.get("unit", "")
                    break
            self.running_table.setItem(row, 2, QTableWidgetItem(unit))

    def _set_status(self, text: str, ok: bool | None = None):
        self.status_label.setText(text)
        if ok is True:
            self.status_label.setStyleSheet("color: #5df0a1;")
        elif ok is False:
            self.status_label.setStyleSheet("color: #ff9b9b;")
        else:
            self.status_label.setStyleSheet("color: #9db4d4;")

    def on_connect_clicked(self):
        if self.worker and self.worker.isRunning():
            self.stop_worker()
            return
        port = self.port_combo.currentText().strip()
        if not port:
            self._set_status("Missing COM port", ok=False)
            return
        try:
            address = int(self.addr_edit.text().strip(), 0)
        except Exception:
            self._set_status("Invalid address", ok=False)
            return
        poll_period = self.poll_spin.value()
        baudrate = int(self.baud_combo.currentText())
        parity = self.parity_combo.currentText()
        stopbits = int(self.stop_combo.currentText())
        rs485_mode = self.rs485_check.isChecked()
        self.start_worker(port, address, poll_period, baudrate, parity, stopbits, rs485_mode)

    def start_worker(
        self,
        port: str,
        address: int,
        poll_period: float,
        baudrate: int,
        parity: str,
        stopbits: int,
        rs485_mode: bool,
    ):
        self.worker = PowerBankWorker(
            port,
            address,
            poll_period,
            baudrate,
            parity,
            stopbits,
            rs485_mode,
        )
        self.worker.data_ready.connect(self.on_data_ready)
        self.worker.alarm_ready.connect(self.on_alarm_ready)
        self.worker.status_ready.connect(self.on_status_ready)
        self.worker.error_ready.connect(self.on_error)
        self.worker.start()
        self.connect_btn.setText("Disconnect")
        self._set_status("Connecting...")

    def stop_worker(self):
        if self.worker:
            self.worker.stop()
            self.worker.wait(1500)
            self.worker = None
        self.connect_btn.setText("Connect")
        self._set_status("Disconnected")

    def on_status_ready(self, text: str):
        self._set_status(text, ok=text.startswith("Connected"))
        if self.logger:
            try:
                self.logger.info(f"[PowerBank] {text}")
            except Exception:
                pass

    def on_error(self, text: str):
        self.log_view.append(text)
        self._set_status("Error", ok=False)
        if self.logger:
            try:
                self.logger.warning(f"[PowerBank] {text}")
            except Exception:
                pass

    def on_data_ready(self, decoded: Dict[str, Dict[str, Any]]):
        for name, payload in decoded.items():
            row = self.running_rows.get(name)
            if row is None:
                continue
            value = payload.get("value")
            if isinstance(value, float):
                value_text = f"{value:.3f}"
            else:
                value_text = str(value)
            self.running_table.setItem(row, 1, QTableWidgetItem(value_text))

    def on_alarm_ready(self, alarms: List[str], faults: List[str]):
        self.alarm_list.clear()
        self.fault_list.clear()
        if alarms:
            self.alarm_list.addItems(sorted(alarms))
        else:
            self.alarm_list.addItem("None")
        if faults:
            self.fault_list.addItems(sorted(faults))
        else:
            self.fault_list.addItem("None")

    def close(self):
        self.stop_worker()
