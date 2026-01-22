from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QTableWidget, QTableWidgetItem, QLabel, QComboBox,
                             QGridLayout, QDialog, QFrame, QTextEdit, QInputDialog, QMessageBox, QHeaderView,
                             QDialogButtonBox, QFormLayout, QDoubleSpinBox, QSpinBox, QLineEdit, QSpacerItem, QSizePolicy, QCheckBox)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QPropertyAnimation
from PyQt6.QtGui import QColor, QBrush
import time
import json
import csv
from core.action_registry import INSTRUMENT_ACTIONS, ACTION_LOOKUP, CAN_ACTIONS, UTILITY_ACTIONS


from ui.dialogs import (
    LEDIndicator,
    RampDialog,
    LineLoadDialog,
    PSVISetDialog,
    CANSignalReadDialog,
    CANSignalToleranceDialog,
    CANConditionalJumpDialog,
    CANWaitSignalChangeDialog,
    CANMonitorRangeDialog,
    CANCompareSignalsDialog,
    CANSetAndVerifyDialog,
    ShortCircuitCycleDialog,
    parse_can_id as _parse_can_id,
    format_line_load_summary as _format_line_load_summary,
)
from ui.widgets import (
    ConfigActionRow,
    OutputDiagnosis,
    SequenceEditorRow,
    SequenceTablePanel,
    StatusIndicators,
    WarningLedPanel,
)

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
        self.action_row = ConfigActionRow()
        self.btn_init = self.action_row.btn_init
        self.btn_connect_can = self.action_row.btn_connect_can
        self.btn_start_cyclic = self.action_row.btn_start_cyclic
        self.btn_start_trace = self.action_row.btn_start_trace
        self.btn_disconnect_can = self.action_row.btn_disconnect_can
        self.btn_stop_cyclic = self.action_row.btn_stop_cyclic

        left_layout.addWidget(self.action_row)
        
        # 2. Sequence Editor
        self.sequence_editor = SequenceEditorRow()
        self.sequence_editor.populate_actions(
            INSTRUMENT_ACTIONS, CAN_ACTIONS, UTILITY_ACTIONS
        )
        self.combo_step = self.sequence_editor.combo_step
        self.btn_add_step = self.sequence_editor.btn_add_step
        self.running_test_label = self.sequence_editor.running_test_label
        self.run_status_label = self.sequence_editor.run_status_label
        self.run_timer_label = self.sequence_editor.run_timer_label
        self.toast_label = self.sequence_editor.toast_label
        self.run_timer = QTimer()
        self.run_timer.setInterval(1000)
        self.run_timer.timeout.connect(self._tick_timer)
        self.run_start_ts = None
        left_layout.addWidget(self.sequence_editor)
        
        # Table and Side Buttons
        self.sequence_panel = SequenceTablePanel()
        self.sequence_table = self.sequence_panel.sequence_table
        self.btn_del_step = self.sequence_panel.btn_del_step
        self.btn_move_up = self.sequence_panel.btn_move_up
        self.btn_move_down = self.sequence_panel.btn_move_down
        self.btn_edit_step = self.sequence_panel.btn_edit_step
        self.btn_duplicate = self.sequence_panel.btn_duplicate
        self.btn_force_stop = self.sequence_panel.btn_force_stop
        left_layout.addWidget(self.sequence_panel)
        left_layout.setStretchFactor(self.sequence_panel, 1)
        
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
        self.output_diagnosis = OutputDiagnosis()
        self.output_log = self.output_diagnosis.output_log
        left_layout.addWidget(self.output_diagnosis)

        # Right Panel (Status Indicators)
        self.status_panel = StatusIndicators()
        self.value_inputs = self.status_panel.value_inputs

        self.warning_panel = WarningLedPanel()
        self.led_indicators = self.warning_panel.led_indicators

        # Add panels to main layout
        main_layout.addWidget(left_panel, 60) # 60% width
        main_layout.addWidget(self.status_panel, 20) # 20% width
        main_layout.addWidget(self.warning_panel, 20) # 20% width
    
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
                    raw_value = data.get('raw_value')
                    
                    if value is not None or raw_value is not None:
                        self.update_single_indicator(
                            ui_element_name,
                            value,
                            signal_type,
                            mapping,
                            raw_value=raw_value,
                        )

    def update_single_indicator(self, indicator_name: str, value, signal_type: str, mapping=None, raw_value=None):
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
                numeric_val = self._coerce_status_value(value, raw_value)
                is_error = (numeric_val == error_val)
                led.set_error(is_error)

    @staticmethod
    def _coerce_status_value(value, raw_value=None):
        """
        Prefer raw numeric values from CAN cache for status LEDs.
        Fall back to best-effort mapping for decoded strings.
        """
        if isinstance(raw_value, (int, float)) and not isinstance(raw_value, bool):
            return int(raw_value)
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return int(value)
        if isinstance(value, str):
            text = value.strip().lower()
            if text in {"1", "true", "on", "enable", "enabled", "error", "fault", "fail"}:
                return 1
            if text in {"0", "false", "off", "disable", "disabled", "no error", "ok", "normal", "pass"}:
                return 0
            try:
                return int(float(text))
            except Exception:
                return None
        return None

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
        # Handle Ramp actions with a structured dialog
        if action.startswith("RAMP / Line and Load Regulation"):
            dialog = LineLoadDialog(action_type=action)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                data = dialog.get_values()
                import json
                params = json.dumps(data)
            else:
                return
        elif action.startswith("GS / Ramp") or action.startswith("RAMP / Ramp"):
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
                        msg_id = _parse_can_id(parts[0])
                        data_bytes = [int(x, 16) if x.lower().startswith('0x') else int(x) for x in parts[1:]]
                        import json
                        params = json.dumps({'id': msg_id, 'data': data_bytes})
                    except Exception as exc:
                        QMessageBox.warning(self, "Invalid CAN Send", f"Could not parse input. Use e.g. 0x123,01,02\nDetails: {exc}")
                        return
                else:
                    return
            elif "Start Cyclic By Name" in action or "Stop Cyclic By Name" in action:
                text, ok = QInputDialog.getText(self, "CAN Cyclic by Name", "Enter message name and cycle time in ms (e.g. Vehicle_Mode,100)")
                if ok:
                    try:
                        msg_name, cycle = [p.strip() for p in text.split(',')]
                        import json
                        params = json.dumps({'message_name': msg_name, 'cycle_time': int(cycle)})
                    except Exception as exc:
                        QMessageBox.warning(self, "Invalid CAN Cyclic", f"Use format MessageName,PeriodMs\nDetails: {exc}")
                        return
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
            elif "Set Signal Value" in action:
                dialog = CANSetAndVerifyDialog(parent=self)
                dialog.setWindowTitle("CAN / Set Signal Value")
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    import json
                    params = json.dumps(dialog.get_values())
                else:
                    return
            else:
                # Other CAN actions: no params, leave blank
                params = ""
        elif action.startswith("LOAD /"):
            # DC Load actions
            if action.startswith("LOAD / Short Circuit Cycle"):
                dialog = ShortCircuitCycleDialog(parent=self)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    import json
                    params = json.dumps(dialog.get_values())
                else:
                    return
            else:
                meta = ACTION_LOOKUP.get(action)
                if meta and meta.param_type == "float":
                    val, ok = QInputDialog.getDouble(self, "LOAD Parameter", f"Enter value for {action}:", decimals=4)
                    if ok:
                        params = str(val)
                    else:
                        return
                elif meta and meta.param_type == "str":
                    text, ok = QInputDialog.getText(self, "LOAD Parameter", f"Enter value for {action}:")
                    if ok:
                        params = text
                    else:
                        return
                else:
                    # measure/connect/disconnect/input or unknown -> no params
                    params = ""
        elif action.startswith("PS /"):
            # Power Supply (HV) actions
            if action.startswith("PS / Measure"):
                # Measurement actions require no parameters
                params = ""
            elif "Battery Set Charge" in action or "Battery Set Discharge" in action:
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
                # Reuse ramp dialog for PS ramp or generic RAMP
                dialog = RampDialog(action_type=action)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    data = dialog.get_values()
                    import json
                    params = json.dumps(data)
                else:
                    return
            elif "Set" in action or "Measure" in action or "Read Errors" in action or "Clear Errors" in action:
                # Use registry hint for parameter type
                meta = ACTION_LOOKUP.get(action)
                if meta and meta.param_type == "float":
                    val, ok = QInputDialog.getDouble(self, "Input Parameters", f"Enter value for {action}:", decimals=4)
                    if ok:
                        params = str(val)
                    else:
                        return
                elif meta and meta.param_type == "str":
                    text, ok = QInputDialog.getText(self, "Input Parameters", f"Enter value for {action}:")
                    if ok:
                        params = text
                    else:
                        return
                else:
                    params = ""
        elif action.startswith("OS /"):
            meta = ACTION_LOOKUP.get(action)
            if meta and meta.param_type == "float":
                val, ok = QInputDialog.getDouble(self, "Input Parameters", f"Enter value for {action}:", decimals=4)
                if ok:
                    params = str(val)
                else:
                    return
            elif meta and meta.param_type == "str":
                text, ok = QInputDialog.getText(self, "Input Parameters", f"Enter value for {action}:")
                if ok:
                    params = text
                else:
                    return
            else:
                params = ""
        elif action in ACTION_LOOKUP:
            # Generic registry-backed prompt (GS/PS/OS/LOAD/INSTR with no special handling)
            meta = ACTION_LOOKUP[action]
            if meta.param_type == "float":
                val, ok = QInputDialog.getDouble(self, "Input Parameters", f"Enter value for {action}:", decimals=4)
                if ok:
                    params = str(val)
                else:
                    return
            elif meta.param_type == "str":
                text, ok = QInputDialog.getText(self, "Input Parameters", f"Enter value for {action}:")
                if ok:
                    params = text
                else:
                    return
            else:
                params = ""
        elif "Set" in action or "Wait" in action:
            # Fallback for legacy actions not in registry
            meta = ACTION_LOOKUP.get(action)
            if meta and meta.param_type == "float":
                val, ok = QInputDialog.getDouble(self, "Input Parameters", f"Enter value for {action}:", decimals=4)
                if ok:
                    params = str(val)
                else:
                    return
            else:
                text, ok = QInputDialog.getText(self, "Input Parameters", f"Enter value for {action}:")
                if ok:
                    params = text
                else:
                    return # Cancelled
        
        row = self.sequence_table.rowCount()
        self.sequence_table.insertRow(row)
        self.sequence_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
        self.sequence_table.setItem(row, 1, QTableWidgetItem(action))
        # If ramp param JSON, create a friendly display text and save JSON in UserRole
        if action.startswith("RAMP / Line and Load Regulation") and params:
            import json
            try:
                data = json.loads(params)
                display = _format_line_load_summary(data)
            except Exception:
                display = params
            item = QTableWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, params)
            self.sequence_table.setItem(row, 2, item)
        elif (action.startswith("GS / Ramp") or action.startswith("RAMP / Ramp")) and params:
            import json
            try:
                data = json.loads(params)
                display = f"Start:{data.get('start')} Step:{data.get('step')} End:{data.get('end')} Delay:{data.get('delay')}s"
                if data.get("ps_voltage"):
                    display += f" PSV:{data.get('ps_voltage')}"
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
        elif action.startswith("GS / Set") and params:
            item = QTableWidgetItem(params)
            item.setData(Qt.ItemDataRole.UserRole, params)
            self.sequence_table.setItem(row, 2, item)
        elif action.startswith("LOAD / Short Circuit Cycle") and params:
            import json
            try:
                data = json.loads(params)
                display = (
                    f"Cycles:{data.get('cycles')} Pulse:{data.get('pulse_s')}s "
                    f"Delay:{data.get('input_on_delay_s')}s Dwell:{data.get('dwell_s')}s "
                    f"CC:{data.get('cc_a')} PS_Toggle:{data.get('ps_toggle_each_cycle')} "
                    f"GS:{data.get('gs_telemetry')}"
                )
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

        def _ensure_json_dict(raw, title):
            """Validate JSON string -> dict; warn and return None on failure."""
            if not raw:
                return {}
            if isinstance(raw, dict):
                return raw
            try:
                return json.loads(raw)
            except Exception as exc:
                QMessageBox.warning(self, title, f"Parameters are not valid JSON.\nDetails: {exc}")
                return None

        row = self.sequence_table.currentRow()
        if row >= 0:
            current_action = self.sequence_table.item(row, 1).text()
            params_item = self.sequence_table.item(row, 2)
            try:
                current_params = params_item.data(Qt.ItemDataRole.UserRole) or params_item.text()
            except Exception:
                current_params = params_item.text() if params_item else ""
            
            # Parse initial params
            initial = _ensure_json_dict(current_params, "Invalid Parameters")
            if initial is None:
                return  # abort edit if params are malformed
            
            if current_action.startswith("RAMP / Line and Load Regulation"):
                dialog = LineLoadDialog(action_type=current_action, initial=initial)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    data = dialog.get_values()
                    json_text = json.dumps(data)
                    display = _format_line_load_summary(data)
                    item = QTableWidgetItem(display)
                    item.setData(Qt.ItemDataRole.UserRole, json_text)
                    self.sequence_table.setItem(row, 2, item)
                    self.is_modified = True

            elif (current_action.startswith("GS / Ramp") or current_action.startswith("RAMP / Ramp")):
                dialog = RampDialog(action_type=current_action, initial=initial)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    data = dialog.get_values()
                    json_text = json.dumps(data)
                    display = f"Start:{data.get('start')} Step:{data.get('step')} End:{data.get('end')} Delay:{data.get('delay')}s"
                    if data.get("ps_voltage"):
                        display += f" PSV:{data.get('ps_voltage')}"
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

                elif "Set Signal Value" in current_action:
                    dialog = CANSetAndVerifyDialog(initial=initial)
                    dialog.setWindowTitle("CAN / Set Signal Value")
                    if dialog.exec() == QDialog.DialogCode.Accepted:
                        data = dialog.get_values()
                        json_text = json.dumps(data)
                        display = f"Signal:{data.get('signal_name')} = {data.get('target_value')}"
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
            elif current_action.startswith("LOAD /"):
                if current_action.startswith("LOAD / Short Circuit Cycle"):
                    dialog = ShortCircuitCycleDialog(initial=initial, parent=self)
                    if dialog.exec() == QDialog.DialogCode.Accepted:
                        data = dialog.get_values()
                        json_text = json.dumps(data)
                        display = (
                            f"Cycles:{data.get('cycles')} Pulse:{data.get('pulse_s')}s "
                            f"Delay:{data.get('input_on_delay_s')}s Dwell:{data.get('dwell_s')}s "
                            f"CC:{data.get('cc_a')} PS_Toggle:{data.get('ps_toggle_each_cycle')} "
                            f"GS:{data.get('gs_telemetry')}"
                        )
                        item = QTableWidgetItem(display)
                        item.setData(Qt.ItemDataRole.UserRole, json_text)
                        self.sequence_table.setItem(row, 2, item)
                        self.is_modified = True
                    return
                if "Measure" in current_action or "Connect" in current_action or "Disconnect" in current_action or "Input" in current_action:
                    return
                text, ok = QInputDialog.getText(self, "Edit LOAD Parameter", f"Enter value for {current_action}:", text=current_params)
                if ok:
                    self.sequence_table.setItem(row, 2, QTableWidgetItem(text))
                    self.is_modified = True
                return
            
            elif current_action in ACTION_LOOKUP:
                meta = ACTION_LOOKUP[current_action]
                if meta.param_type == "float":
                    val, ok = QInputDialog.getDouble(self, "Edit Parameters", f"Enter value for {current_action}:", text=current_params if current_params else "0", decimals=4)
                    if ok:
                        self.sequence_table.setItem(row, 2, QTableWidgetItem(str(val)))
                        self.is_modified = True
                    return
                elif meta.param_type == "str":
                    text, ok = QInputDialog.getText(self, "Edit Parameters", f"Enter value for {current_action}:", text=current_params)
                    if ok:
                        self.sequence_table.setItem(row, 2, QTableWidgetItem(text))
                        self.is_modified = True
                    return
                else:
                    QMessageBox.information(self, "Info", "This action has no parameters to edit.")
                    return

            elif current_action.startswith("PS /"):
                if current_action.startswith("PS / Measure"):
                    return  # measurement actions need no params edit
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
                    # Ensure existing params are valid JSON before editing
                    if current_params and not isinstance(initial, dict):
                        initial = _ensure_json_dict(current_params, "Invalid Sweep Parameters")
                        if initial is None:
                            return
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

    def show_warning(self, message: str):
        """Inline warning helper to surface potential issues near the log area."""
        label = message if message.lower().startswith("warning") else f"Sequence Warning: {message}"
        self._show_toast(label, kind="warning")
        self.output_log.append(f"[WARNING] {message}")

    def _show_toast(self, message: str, kind: str = "info", duration_ms: int = 2500):
        """Non-blocking toast/badge near the step controls."""
        if not hasattr(self, "toast_label"):
            return
        self.toast_label.setText(message)
        if kind == "warning":
            self.toast_label.setStyleSheet("background: #7a2f2f; color: #ffdddd; padding: 6px 10px; border-radius: 6px;")
        else:
            self.toast_label.setStyleSheet("background: #2f4f7a; color: #dce9ff; padding: 6px 10px; border-radius: 6px;")
        self.toast_label.setVisible(True)
        # Simple timer to hide
        QTimer.singleShot(duration_ms, lambda: self.toast_label.setVisible(False))

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
                        if data and step['action'].startswith('RAMP / Line and Load Regulation'):
                            display = _format_line_load_summary(data)
                            item = QTableWidgetItem(display)
                            item.setData(Qt.ItemDataRole.UserRole, params_text)
                            self.sequence_table.setItem(row, 2, item)
                        elif data and (step['action'].startswith('GS / Ramp') or step['action'].startswith('RAMP / Ramp')):
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
                item.setBackground(QBrush(QColor(0, 80, 40)))
            elif status == "Fail":
                item.setForeground(QBrush(QColor(255, 0, 0)))  # Bright Red
                item.setBackground(QBrush(QColor(80, 0, 0)))
            elif status == "Running":
                item.setForeground(QBrush(QColor(255, 200, 0)))  # Yellow/Orange
                item.setBackground(QBrush(QColor(60, 45, 0)))
            self.sequence_table.setItem(index, 3, item)

    def set_running_test_name(self, test_name):
        """Display the currently running test name"""
        self.running_test_label.setText(f"Running: {test_name}")
        self.run_status_label.setText("Running")
        self.run_status_label.setStyleSheet("color: #5df0a1;")
        self.run_start_ts = time.time()
        self.run_timer.start()
    
    def clear_running_test_name(self):
        """Clear the running test name display"""
        self.running_test_label.setText("")
        self.run_status_label.setText("Idle")
        self.run_status_label.setStyleSheet("color: #9db4d4;")
        self.run_timer.stop()
        self.run_timer_label.setText("00:00")
        self.run_start_ts = None

    def _tick_timer(self):
        if self.run_start_ts:
            elapsed = int(time.time() - self.run_start_ts)
            mins = elapsed // 60
            secs = elapsed % 60
            self.run_timer_label.setText(f"{mins:02d}:{secs:02d}")
    

