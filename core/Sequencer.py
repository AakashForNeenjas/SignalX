import time
import threading
import json
import traceback
from PyQt6.QtCore import QObject, pyqtSignal

class Sequencer(QObject):
    step_completed = pyqtSignal(int, str) # step_index, status
    action_info = pyqtSignal(int, str)    # step_index, message
    sequence_finished = pyqtSignal()
    
    def __init__(self, instrument_manager, can_manager, logger=None):
        super().__init__()
        self.inst_mgr = instrument_manager
        self.can_mgr = can_manager
        self.steps = []
        self.running = False
        self.thread = None
        self.stop_event = threading.Event()
        self.logger = logger

    def _log(self, level, message):
        if self.logger:
            try:
                self.logger.log(level, message)
            except Exception:
                pass

    def _log_cmd(self, message):
        """Log instrument command intent for traceability."""
        self._log(20, f"CMD: {message}")
        print(f"[CMD] {message}")

    def set_steps(self, steps):
        self.steps = steps

    def start_sequence(self):
        if self.running:
            return
        self.running = True
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run_sequence)
        self.thread.daemon = True
        self.thread.start()
        self._log(20, "Sequence started")

    def stop_sequence(self):
        self.running = False
        self.stop_event.set()
        self._log(20, "Sequence stop requested")

    def _run_sequence(self):
        print("Starting Sequence...")
        self._log(20, "Sequence thread running")
        try:
            for i, step in enumerate(self.steps):
                if self.stop_event.is_set() or not self.running:
                    self._log(20, "Sequence aborted by user")
                    break
                
                action = step.get('action')
                params = step.get('params')
                
                print(f"Executing Step {i+1}: {action}")
                self.step_completed.emit(i, "Running")
                
                try:
                    # Execute action and get success/failure status and message
                    result = self._execute_action(action, params, i)
                    if not isinstance(result, tuple) or len(result) != 2:
                        success, message = False, f"Action returned invalid result shape: {result}"
                    else:
                        success, message = result
                    # Emit message to output log using action_info
                    if message:
                        self.action_info.emit(i, message)
                        self._log(20 if success else 30, f"Step {i+1}: {message}")

                    if success:
                        self.step_completed.emit(i, "Pass")
                        print(f"Step {i+1}: Pass")
                    else:
                        self.step_completed.emit(i, "Fail")
                        print(f"Step {i+1}: Fail")
                        # Stop on failure
                        self.running = False
                        self.stop_event.set()
                        break
                        
                except Exception as e:
                    tb = traceback.format_exc()
                    print(f"Step {i+1} Failed with exception: {e}")
                    self._log(40, f"Step {i+1} exception: {e}\n{tb}")
                    self.step_completed.emit(i, "Fail")
                    # Stop on failure
                    self.running = False
                    self.stop_event.set()
                    break
                
                # Delay between steps, but remain responsive to stop
                delay = 0.5
                elapsed = 0.0
                while elapsed < delay and self.running and not self.stop_event.is_set():
                    time.sleep(0.05)
                    elapsed += 0.05
                
        finally:
            self.running = False
            self.stop_event.set()
            self.sequence_finished.emit()
            print("Sequence Finished")
            self._log(20, "Sequence finished")

    def _execute_action(self, action, params, index=None):
        """
        Execute an action and return (success: bool, message: str).
        All actions must verify their success and return an informative message for the UI.
        """
        try:
            # Track current step index so helpers can emit structured data (e.g., ramp logs)
            self._current_index = index
            # Support instrument-prefixed actions (format: "XX / Action Name")
            if " / " in action:
                prefix, action_name = [p.strip() for p in action.split("/", 1)]
                prefix = prefix.upper()

                # Generic ramp handler (available via RAMP prefix)
                if prefix == "RAMP":
                    return self._handle_ramp_action(action_name, params)

                # Grid Simulator (GS) actions
                if prefix == "GS":
                    # Ensure grid emulator driver is available
                    if not hasattr(self.inst_mgr, 'itech7900') or self.inst_mgr.itech7900 is None:
                        print("GS action failed: Instrument not initialized")
                        return False
                    # Connect common ITECH7900 methods
                    gs = self.inst_mgr.itech7900
                    # Examples of actions: "Set Voltage AC", "Measure Power Real", "Power: ON"
                    if "Set Voltage" in action_name:
                        try:
                            val = float(params.replace("V", "").strip())
                        except Exception:
                            val = float(params)
                        self._log_cmd(f"GS VOLT {val}")
                        gs.set_grid_voltage(val)
                        msg = f"GS Set Voltage: {val}V"
                        print(msg)
                        return True, msg

                    if action_name.startswith("Set Current"):
                        try:
                            val = float(params.replace("A", "").strip())
                        except Exception:
                            val = float(params)
                        self._log_cmd(f"GS CURR {val}")
                        gs.set_grid_current(val)
                        msg = f"GS Set Current: {val}A"
                        print(msg)
                        return True, msg

                    if action_name.startswith("Set Frequency"):
                        try:
                            val = float(params.replace("Hz", "").strip())
                        except Exception:
                            val = float(params)
                        self._log_cmd(f"GS FREQ {val}")
                        gs.set_grid_frequency(val)
                        msg = f"GS Set Frequency: {val}Hz"
                        print(msg)
                        return True, msg

                    if action_name.startswith("Measure Voltage"):
                        val = gs.get_grid_voltage()
                        msg = f"GS Measure Voltage: {val}V"
                        print(msg)
                        return True, msg

                    if action_name.startswith("Measure Current"):
                        val = gs.get_grid_current()
                        msg = f"GS Measure Current: {val}A"
                        print(msg)
                        return True, msg

                    if action_name.startswith("Measure Frequency"):
                        val = gs.get_grid_frequency()
                        msg = f"GS Measure Frequency: {val}Hz"
                        print(msg)
                        return True, msg

                    if action_name.startswith("Measure Power Real"):
                        val = gs.measure_power_real()
                        msg = f"GS Measure Power Real: {val}W"
                        print(msg)
                        return True, msg

                    if action_name.startswith("Measure Power Reactive"):
                        val = gs.measure_power_reactive()
                        msg = f"GS Measure Power Reactive: {val}VAR"
                        print(msg)
                        return True, msg

                    if action_name.startswith("Measure Power Apparent"):
                        val = gs.measure_power_apparent()
                        msg = f"GS Measure Power Apparent: {val}VA"
                        print(msg)
                        return True, msg

                    if action_name.startswith("Measure Power Factor"):
                        val = gs.measure_power_factor()
                        msg = f"GS Measure Power Factor: {val}"
                        print(msg)
                        return True, msg

                    if action_name.startswith("Measure THD Current"):
                        val = gs.measure_thd_current()
                        msg = f"GS Measure THD Current: {val}%"
                        print(msg)
                        return True, msg

                    if action_name.startswith("Measure THD Voltage"):
                        val = gs.measure_thd_voltage()
                        msg = f"GS Measure THD Voltage: {val}%"
                        print(msg)
                        return True, msg

                    if action_name.startswith("Power:"):
                        if "ON" in action_name:
                            self._log_cmd("GS OUTP ON")
                            gs.power_on()
                            msg = "GS Power ON"
                            print(msg)
                        else:
                            self._log_cmd("GS OUTP OFF")
                            gs.power_off()
                            msg = "GS Power OFF"
                            print(msg)
                        return True, msg

                    if action_name.startswith("Ramp Up Voltage"):
                        # Expect params as JSON {start, step, end, delay, tolerance, retries}
                        import json
                        try:
                            data = json.loads(params) if params else {}
                        except Exception:
                            # Fallback: single value as end voltage
                            data = {'end': float(params)} if params else {}

                        # Defaults
                        start = data.get('start', None)
                        step = data.get('step', 1.0)
                        end = data.get('end', None)
                        delay = data.get('delay', 0.5)
                        tolerance = data.get('tolerance', 0.5)
                        retries = int(data.get('retries', 3))

                        # If start or end not provided, use measured grid voltage
                        try:
                            measured_start = gs.get_grid_voltage()
                        except Exception:
                            measured_start = 0.0
                        if start is None:
                            start = measured_start
                        if end is None:
                            end = measured_start

                        # Ensure we ramp up (end >= start)
                        if end < start:
                            msg = f"Ramp Up failed: end ({end}) < start ({start})."
                            print(msg)
                            return False, msg

                        # Iterate from start to end
                        current = start
                        steps_executed = 0
                        last_measured = measured_start
                        while current <= end and (self.running or index is not None):
                            gs.set_grid_voltage(float(current))
                            # Wait briefly for change
                            time.sleep(0.1)

                            # Closed-loop: verify measured value within tolerance
                            success_local = False
                            for attempt in range(retries + 1):
                                try:
                                    last_measured = gs.get_grid_voltage()
                                except Exception:
                                    last_measured = last_measured
                                if abs(last_measured - current) <= tolerance:
                                    success_local = True
                                    break
                                else:
                                    # Re-issue the set to correct
                                    gs.set_grid_voltage(float(current))
                                    time.sleep(0.1)

                            steps_executed += 1
                            msg = f"GS RampUp step {steps_executed}: set {current}V, measured {last_measured}V, within_tol={success_local}"
                            print(msg)
                            # Emit intermediate message for UI
                            if index is not None:
                                self.action_info.emit(index, msg)
                            else:
                                self.action_info.emit(0, msg)

                            if not self.running and index is None:
                                break
                            # Inter-step delay
                            time.sleep(delay)
                            current += abs(step)

                        final_msg = f"GS RampUp complete: steps={steps_executed}, final_meas={last_measured}V"
                        print(final_msg)
                        return True, final_msg

                    if action_name.startswith("Ramp Down Voltage"):
                        # Expect params as JSON {start, step, end, delay, tolerance, retries}
                        import json
                        try:
                            data = json.loads(params) if params else {}
                        except Exception:
                            data = {'end': float(params)} if params else {}

                        start = data.get('start', None)
                        step = data.get('step', 1.0)
                        end = data.get('end', None)
                        delay = data.get('delay', 0.5)
                        tolerance = data.get('tolerance', 0.5)
                        retries = int(data.get('retries', 3))

                        try:
                            measured_start = gs.get_grid_voltage()
                        except Exception:
                            measured_start = 0.0
                        if start is None:
                            start = measured_start
                        if end is None:
                            end = measured_start

                        # Ensure we ramp down (end <= start)
                        if end > start:
                            msg = f"Ramp Down failed: end ({end}) > start ({start})."
                            print(msg)
                            return False, msg

                        current = start
                        steps_executed = 0
                        last_measured = measured_start
                        while current >= end and (self.running or index is not None):
                            gs.set_grid_voltage(float(current))
                            time.sleep(0.1)

                            success_local = False
                            for attempt in range(retries + 1):
                                try:
                                    last_measured = gs.get_grid_voltage()
                                except Exception:
                                    last_measured = last_measured
                                if abs(last_measured - current) <= tolerance:
                                    success_local = True
                                    break
                                else:
                                    gs.set_grid_voltage(float(current))
                                    time.sleep(0.1)

                            steps_executed += 1
                            msg = f"GS RampDown step {steps_executed}: set {current}V, measured {last_measured}V, within_tol={success_local}"
                            print(msg)
                            if index is not None:
                                self.action_info.emit(index, msg)
                            else:
                                self.action_info.emit(0, msg)

                            if not self.running and index is None:
                                break
                            time.sleep(delay)
                            current -= abs(step)

                        final_msg = f"GS RampDown complete: steps={steps_executed}, final_meas={last_measured}V"
                        print(final_msg)
                        return True, final_msg

                    if action_name.startswith("Reset System"):
                        gs.reset_system()
                        msg = "GS Reset System"
                        print(msg)
                        return True, msg

                    if action_name.startswith("Ramp Set & Measure"):
                        return self._handle_ramp_action(action_name, params)

                    if action_name.startswith("Get IDN"):
                        try:
                            resp = gs.query("*IDN?")
                            msg = f"GS IDN: {resp}"
                            print(msg)
                        except Exception:
                            pass
                        return True, msg

                    if action_name.startswith("Check Error"):
                        # Attempt to query the error/status register
                        try:
                            resp = gs.query("SYST:ERR?")
                            msg = f"GS Error Status: {resp}"
                            print(msg)
                        except Exception:
                            pass
                        return True, msg

                    if action_name.startswith("Clear Protection"):
                        try:
                            gs.write("PROT:CLER")
                        except Exception:
                            pass
                        msg = "GS Clear Protection"
                        print(msg)
                        return True, msg

                # If prefix found but not specifically handled, continue to generic handling
                # CAN actions
                if prefix == "CAN":
                    # Ensure CAN manager is available
                    if not hasattr(self, 'can_mgr') or self.can_mgr is None:
                        msg = "CAN action failed: CAN Manager is not initialized"
                        print(msg)
                        return False, msg
                    # Handle CAN-prefixed actions
                    if action_name.lower() in ["connect", "connect can", "connect can bus"]:
                        # If already connected, reuse the existing handle instead of erroring
                        if getattr(self.can_mgr, "is_connected", False):
                            msg = "CAN Connect: already connected, reusing existing session"
                            print(msg)
                            return True, msg
                        success, connect_msg = self.can_mgr.connect()
                        msg = f"CAN Connect: {connect_msg}"
                        print(msg)
                        return success, msg

                    if action_name.lower() in ["disconnect", "disconnect can"]:
                        try:
                            self.can_mgr.disconnect()
                            msg = "CAN Disconnected"
                            print(msg)
                            return True, msg
                        except Exception as e:
                            msg = f"CAN Disconnect failed: {e}"
                            print(msg)
                            return False, msg

                    if action_name.startswith("Start Cyclic CAN"):
                        started_messages, failed_messages = self.can_mgr.start_all_cyclic_messages()
                        msg = f"CAN Start Cyclic: Started: {', '.join(started_messages)}; Failed: {', '.join(failed_messages)}"
                        print(msg)
                        return len(started_messages) > 0, msg

                    if action_name.startswith("Stop Cyclic CAN"):
                        success = self.can_mgr.stop_all_cyclic_messages()
                        msg = "CAN Stop Cyclic: Success" if success else "CAN Stop Cyclic: Some messages may not have stopped"
                        print(msg)
                        return success, msg

                    if action_name.startswith("Start Trace"):
                        from datetime import datetime
                        try:
                            filename_base = f"trace_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                            full_path = self.can_mgr.start_logging(filename_base)
                            msg = f"CAN Trace Started: {filename_base}"
                            print(msg)
                            return True, msg
                        except Exception as e:
                            msg = f"CAN Start Trace failed: {e}"
                            print(msg)
                            return False, msg

                    if action_name.startswith("Stop Trace"):
                        try:
                            self.can_mgr.stop_logging()
                            msg = "CAN Trace Stopped"
                            print(msg)
                            return True, msg
                        except Exception as e:
                            msg = f"CAN Stop Trace failed: {e}"
                            print(msg)
                            return False, msg

                    if action_name.startswith("Send Message"):
                        # Accept params in JSON {'id':123, 'data':[1,2,3], 'extended': False} or '0x123,01,02'
                        try:
                            import json
                            data = {}
                            if params:
                                try:
                                    data = json.loads(params)
                                except Exception:
                                    # parse id,data
                                    parts = [p.strip() for p in params.split(',') if p.strip()]
                                    id_raw = parts[0]
                                    if id_raw.lower().startswith('0x'):
                                        arbid = int(id_raw, 16)
                                    else:
                                        arbid = int(id_raw)
                                    data_list = [int(x, 16) if x.lower().startswith('0x') else int(x) for x in parts[1:]]
                                    data = {'id': arbid, 'data': data_list}

                            arbid = data.get('id')
                            payload = data.get('data', [])
                            is_extended = data.get('extended', False)
                            if arbid is None:
                                msg = "CAN Send Message failed: No message ID provided"
                                print(msg)
                                return False, msg
                            self.can_mgr.send_message(arbid, payload, is_extended)
                            msg = f"CAN Sent: ID=0x{arbid:X}, Data={payload}"
                            print(msg)
                            return True, msg
                        except Exception as e:
                            msg = f"CAN Send Message failed: {e}"
                            print(msg)
                            return False, msg

                    if action_name.startswith("Start Cyclic By Name"):
                        # params JSON: {'message_name':'Vehicle_Mode', 'cycle_time': 100, 'signals': {...}}
                        try:
                            import json
                            details = json.loads(params) if params else {}
                            msg_name = details.get('message_name') or details.get('name')
                            cycle_ms = details.get('cycle_time') or details.get('cycle') or 100
                            sigs = details.get('signals', {})
                            if not msg_name:
                                msg = "CAN Start Cyclic By Name failed: no message name provided"
                                print(msg)
                                return False, msg
                            success = self.can_mgr.start_cyclic_message_by_name(msg_name, sigs, cycle_ms)
                            msg = f"CAN Start Cyclic By Name: {msg_name} -> {success}"
                            print(msg)
                            return success, msg
                        except Exception as e:
                            msg = f"CAN Start Cyclic By Name failed: {e}"
                            print(msg)
                            return False, msg

                    if action_name.startswith("Stop Cyclic By Name"):
                        # params JSON: {'message_name':'Vehicle_Mode'}
                        try:
                            import json
                            details = json.loads(params) if params else {}
                            msg_name = details.get('message_name') or details.get('name')
                            if not msg_name:
                                msg = "CAN Stop Cyclic By Name failed: no message name provided"
                                print(msg)
                                return False, msg
                            # find message id via DBC parser
                            if self.can_mgr.dbc_parser and self.can_mgr.dbc_parser.database:
                                try:
                                    message = self.can_mgr.dbc_parser.database.get_message_by_name(msg_name)
                                    self.can_mgr.stop_cyclic_message(message.frame_id)
                                    msg = f"CAN Stop Cyclic By Name: {msg_name} stopped"
                                    print(msg)
                                    return True, msg
                                except Exception as e:
                                    msg = f"CAN Stop Cyclic By Name: failed to stop {msg_name}: {e}"
                                    print(msg)
                                    return False, msg
                            else:
                                msg = "CAN Stop Cyclic By Name failed: DBC not loaded"
                                print(msg)
                                return False, msg
                        except Exception as e:
                            msg = f"CAN Stop Cyclic By Name failed: {e}"
                            print(msg)
                            return False, msg

                    # CAN Signal Test Actions
                    if "Read Signal Value" in action_name:
                        try:
                            import json
                            details = json.loads(params) if isinstance(params, str) else params
                            signal_name = details.get('signal_name', '')
                            timeout = float(details.get('timeout', 2.0))
                            if not signal_name:
                                msg = "CAN Read Signal Value failed: no signal name provided"
                                print(msg)
                                return False, msg
                            ok, value, diag_msg = self.can_mgr.read_signal_value(signal_name, timeout)
                            print(diag_msg)
                            self.action_info.emit(index, diag_msg)
                            return ok, diag_msg
                        except Exception as e:
                            msg = f"CAN Read Signal Value failed: {e}"
                            print(msg)
                            return False, msg

                    if "Check Signal (Tolerance)" in action_name:
                        try:
                            import json
                            details = json.loads(params) if isinstance(params, str) else params
                            signal_name = details.get('signal_name', '')
                            expected = float(details.get('expected_value', 0))
                            tolerance = float(details.get('tolerance', 0.1))
                            timeout = float(details.get('timeout', 2.0))
                            if not signal_name:
                                msg = "CAN Check Signal (Tolerance) failed: no signal name provided"
                                print(msg)
                                return False, msg
                            ok, value, diag_msg = self.can_mgr.check_signal_tolerance(
                                signal_name, expected, tolerance, timeout
                            )
                            print(diag_msg)
                            self.action_info.emit(index, diag_msg)
                            return ok, diag_msg
                        except Exception as e:
                            msg = f"CAN Check Signal (Tolerance) failed: {e}"
                            print(msg)
                            return False, msg

                    if "Conditional Jump" in action_name:
                        try:
                            import json
                            details = json.loads(params) if isinstance(params, str) else params
                            signal_name = details.get('signal_name', '')
                            expected = float(details.get('expected_value', 0))
                            tolerance = float(details.get('tolerance', 0.1))
                            target_step = int(details.get('target_step', 0))
                            if not signal_name:
                                msg = "CAN Conditional Jump failed: no signal name provided"
                                print(msg)
                                return False, msg
                            ok, diag_msg = self.can_mgr.conditional_jump_check(signal_name, expected, tolerance)
                            print(diag_msg)
                            self.action_info.emit(index, diag_msg)
                            if ok:
                                self.current_step = target_step - 1  # Will be incremented
                                msg = f"CAN Conditional Jump: jumping to step {target_step}"
                                print(msg)
                                return True, msg
                            else:
                                return True, diag_msg  # Condition not met, continue normally
                        except Exception as e:
                            msg = f"CAN Conditional Jump failed: {e}"
                            print(msg)
                            return False, msg

                    if "Wait For Signal Change" in action_name:
                        try:
                            import json
                            details = json.loads(params) if isinstance(params, str) else params
                            signal_name = details.get('signal_name', '')
                            initial_value = float(details.get('initial_value', 0))
                            timeout = float(details.get('timeout', 5.0))
                            poll_interval = float(details.get('poll_interval', 0.1))
                            if not signal_name:
                                msg = "CAN Wait For Signal Change failed: no signal name provided"
                                print(msg)
                                return False, msg
                            ok, new_value, diag_msg = self.can_mgr.wait_for_signal_change(
                                signal_name, initial_value, timeout, poll_interval
                            )
                            print(diag_msg)
                            self.action_info.emit(index, diag_msg)
                            return ok, diag_msg
                        except Exception as e:
                            msg = f"CAN Wait For Signal Change failed: {e}"
                            print(msg)
                            return False, msg

                    if "Monitor Signal Range" in action_name:
                        try:
                            import json
                            details = json.loads(params) if isinstance(params, str) else params
                            signal_name = details.get('signal_name', '')
                            min_val = float(details.get('min_val', 0))
                            max_val = float(details.get('max_val', 100))
                            duration = float(details.get('duration', 5.0))
                            poll_interval = float(details.get('poll_interval', 0.1))
                            if not signal_name:
                                msg = "CAN Monitor Signal Range failed: no signal name provided"
                                print(msg)
                                return False, msg
                            ok, readings, diag_msg = self.can_mgr.monitor_signal_range(
                                signal_name, min_val, max_val, duration, poll_interval
                            )
                            print(diag_msg)
                            self.action_info.emit(index, diag_msg)
                            return ok, diag_msg
                        except Exception as e:
                            msg = f"CAN Monitor Signal Range failed: {e}"
                            print(msg)
                            return False, msg

                    if "Compare Two Signals" in action_name:
                        try:
                            import json
                            details = json.loads(params) if isinstance(params, str) else params
                            signal1 = details.get('signal1', '')
                            signal2 = details.get('signal2', '')
                            tolerance = float(details.get('tolerance', 0.1))
                            timeout = float(details.get('timeout', 2.0))
                            if not signal1 or not signal2:
                                msg = "CAN Compare Two Signals failed: signal names not provided"
                                print(msg)
                                return False, msg
                            ok, values, diag_msg = self.can_mgr.compare_two_signals(
                                signal1, signal2, tolerance, timeout
                            )
                            print(diag_msg)
                            self.action_info.emit(index, diag_msg)
                            return ok, diag_msg
                        except Exception as e:
                            msg = f"CAN Compare Two Signals failed: {e}"
                            print(msg)
                            return False, msg

                    if "Set Signal Value" in action_name:
                        try:
                            import json
                            details = json.loads(params) if isinstance(params, str) else params
                            raw_mid = details.get('message_id', 0)
                            message_id = int(raw_mid, 16) if isinstance(raw_mid, str) and raw_mid else int(raw_mid)
                            signal_name = details.get('signal_name', '')
                            target_value = float(details.get('target_value', 0))
                            tolerance = float(details.get('tolerance', 0.1))
                            verify_timeout = float(details.get('verify_timeout', 2.0))
                            if not signal_name:
                                msg = "CAN Set Signal Value failed: no signal name provided"
                                print(msg)
                                return False, msg
                            db = getattr(self.can_mgr, "dbc_parser", None)
                            if not db or not db.database:
                                msg = "CAN Set Signal Value failed: DBC not loaded"
                                print(msg)
                                return False, msg
                            msg_def = db.database.get_message_by_frame_id(message_id)
                            # Apply override and send once
                            self.can_mgr.send_message_with_overrides(msg_def.name, {signal_name: target_value})
                            # If this message is running cyclic, restart it with updated overrides (preserving other signals)
                            try:
                                if message_id in getattr(self.can_mgr, "cyclic_tasks", {}):
                                    cycle_ms = 100
                                    try:
                                        import can_messages
                                        cfg = can_messages.CYCLIC_CAN_MESSAGES.get(msg_def.name, {})
                                        cycle_ms = cfg.get("cycle_time", cycle_ms)
                                    except Exception:
                                        pass
                                    # Build base using last sent signals (preferred) else cache
                                    base = {}
                                    try:
                                        base = dict(getattr(self.can_mgr, "last_sent_signals", {}).get(msg_def.name, {}))
                                    except Exception:
                                        base = {}
                                    if not base:
                                        try:
                                            cache = getattr(self.can_mgr, "signal_cache", {})
                                            for sig in msg_def.signals:
                                                if sig.name in cache and "value" in cache[sig.name]:
                                                    base[sig.name] = cache[sig.name]["value"]
                                        except Exception:
                                            base = {}
                                    # start_cyclic_message will stop the existing one if present
                                    self.can_mgr.start_cyclic_message_by_name(msg_def.name, base, cycle_ms)
                            except Exception:
                                pass
                            ok, detail = self.can_mgr.verify_signal_value(signal_name, target_value, timeout=verify_timeout, tolerance=tolerance)
                            diag = detail if detail else f"Set {msg_def.name}.{signal_name} to {target_value}"
                            print(diag)
                            self.action_info.emit(index, diag)
                            return ok, diag
                        except Exception as e:
                            msg = f"CAN Set Signal Value failed: {e}"
                            print(msg)
                            return False, msg

                    if "Set Signal and Verify" in action_name:
                        try:
                            import json
                            details = json.loads(params) if isinstance(params, str) else params
                            raw_mid = details.get('message_id', 0)
                            message_id = int(raw_mid, 16) if isinstance(raw_mid, str) and raw_mid else int(raw_mid)
                            signal_name = details.get('signal_name', '')
                            target_value = float(details.get('target_value', 0))
                            tolerance = float(details.get('tolerance', 0.1))
                            verify_timeout = float(details.get('verify_timeout', 2.0))
                            if not signal_name:
                                msg = "CAN Set Signal and Verify failed: no signal name provided"
                                print(msg)
                                return False, msg
                            ok, value, round_trip_time, diag_msg = self.can_mgr.set_signal_and_verify(
                                message_id, signal_name, target_value, verify_timeout, tolerance
                            )
                            print(diag_msg)
                            self.action_info.emit(index, diag_msg)
                            return ok, diag_msg
                        except Exception as e:
                            msg = f"CAN Set Signal and Verify failed: {e}"
                            print(msg)
                            return False, msg

                # Power Supply (PS) actions
                if prefix == "PS":
                    # Ensure PS driver available
                    if not hasattr(self.inst_mgr, 'itech6000') or self.inst_mgr.itech6000 is None:
                        msg = "PS action failed: PS not initialized"
                        print(msg)
                        return False, msg
                    ps = self.inst_mgr.itech6000
                    # Example action patterns
                    if "Connect" in action_name:
                        self._log_cmd("PS CONNECT")
                        if getattr(ps, "connected", False):
                            msg = "PS Connect: already connected, reusing session"
                            print(msg)
                            return True, msg
                        s, m = ps.connect()
                        msg = f"PS Connect: {m}"
                        print(msg)
                        return s, msg
                    if "Disconnect" in action_name:
                        self._log_cmd("PS DISCONNECT")
                        ps.disconnect()
                        msg = "PS Disconnected"
                        print(msg)
                        return True, msg
                    if "Output" in action_name:
                        if "ON" in action_name:
                            ps.power_on()
                            msg = "PS Output ON"
                        else:
                            ps.power_off()
                            msg = "PS Output OFF"
                        print(msg)
                        return True, msg
                    if "Measure VI" in action_name:
                        v, i = ps.measure_vi()
                        msg = f"PS Measure VI: V={v}V I={i}A"
                        print(msg)
                        return True, msg

                    if "Measure Voltage, Current, Power" in action_name:
                        v, i, p = ps.measure_power_vi()
                        msg = f"PS Measure VIP: V={v}V I={i}A P={p}W"
                        print(msg)
                        return True, msg
                    if "Set Voltage" in action_name:
                        try:
                            val = float(params)
                        except Exception:
                            # If JSON with voltage provided
                            import json
                            try:
                                d = json.loads(params)
                                val = float(d.get('voltage', 0))
                            except Exception:
                                val = 0.0
                        self._log_cmd(f"PS VOLT {val}")
                        ps.set_voltage(val)
                        msg = f"PS Set Voltage: {val}V"
                        print(msg)
                        return True, msg
                    if "Set Current" in action_name:
                        try:
                            val = float(params)
                        except Exception:
                            import json
                            try:
                                d = json.loads(params)
                                val = float(d.get('current', 0))
                            except Exception:
                                val = 0.0
                        self._log_cmd(f"PS CURR {val}")
                        ps.set_current(val)
                        msg = f"PS Set Current: {val}A"
                        print(msg)
                        return True, msg
                    if "Ramp Up" in action_name or "Ramp Down" in action_name:
                        import json
                        try:
                            data = json.loads(params) if params else {}
                        except Exception:
                            data = {}
                        start = data.get('start', None)
                        step = data.get('step', 1.0)
                        end = data.get('end', None)
                        delay = data.get('delay', 0.5)
                        tolerance = data.get('tolerance', 0.5)
                        retries = int(data.get('retries', 3))
                        # Use ps.ramp_up_voltage / ramp_down_voltage
                        if "Ramp Up" in action_name:
                                # Implement closed-loop ramp in Sequencer for UI feedback
                                try:
                                    try:
                                        measured_start = ps.get_voltage()
                                    except Exception:
                                        measured_start = 0.0
                                    if start is None:
                                        start = measured_start
                                    if end is None:
                                        end = measured_start
                                    if end < start:
                                        msg = f"PS Ramp Up failed: end ({end}) < start ({start})"
                                        print(msg)
                                        return False, msg
                                    current = start
                                    steps_executed = 0
                                    last_measured = measured_start
                                    while current <= end and (self.running or index is not None):
                                        ps.set_voltage(float(current))
                                        time.sleep(0.1)
                                        success_local = False
                                        for attempt in range(retries + 1):
                                            try:
                                                last_measured = ps.get_voltage()
                                            except Exception:
                                                last_measured = last_measured
                                            if abs(last_measured - current) <= tolerance:
                                                success_local = True
                                                break
                                            else:
                                                ps.set_voltage(float(current))
                                                time.sleep(0.1)
                                        steps_executed += 1
                                        msg = f"PS RampUp step {steps_executed}: set {current}V, measured {last_measured}V, within_tol={success_local}"
                                        print(msg)
                                        if index is not None:
                                            self.action_info.emit(index, msg)
                                        else:
                                            self.action_info.emit(0, msg)
                                        if not self.running and index is None:
                                            break
                                        time.sleep(delay)
                                        current += abs(step)
                                    final_msg = f"PS RampUp complete: steps={steps_executed}, final_meas={last_measured}V"
                                    print(final_msg)
                                    return True, final_msg
                                except Exception as e:
                                    msg = f"PS RampUp failed: {e}"
                                    print(msg)
                                    return False, msg
                        elif "Ramp Down" in action_name:
                            # Closed-loop ramp down implemented here
                            try:
                                try:
                                    measured_start = ps.get_voltage()
                                except Exception:
                                    measured_start = 0.0
                                if start is None:
                                    start = measured_start
                                if end is None:
                                    end = measured_start
                                if end > start:
                                    msg = f"PS Ramp Down failed: end ({end}) > start ({start})"
                                    print(msg)
                                    return False, msg
                                current = start
                                steps_executed = 0
                                last_measured = measured_start
                                while current >= end and (self.running or index is not None):
                                    ps.set_voltage(float(current))
                                    time.sleep(0.1)
                                    success_local = False
                                    for attempt in range(retries + 1):
                                        try:
                                            last_measured = ps.get_voltage()
                                        except Exception:
                                            last_measured = last_measured
                                        if abs(last_measured - current) <= tolerance:
                                            success_local = True
                                            break
                                        else:
                                            ps.set_voltage(float(current))
                                            time.sleep(0.1)
                                    steps_executed += 1
                                    msg = f"PS RampDown step {steps_executed}: set {current}V, measured {last_measured}V, within_tol={success_local}"
                                    print(msg)
                                    if index is not None:
                                        self.action_info.emit(index, msg)
                                    else:
                                        self.action_info.emit(0, msg)
                                    if not self.running and index is None:
                                        break
                                    time.sleep(delay)
                                    current -= abs(step)
                                final_msg = f"PS RampDown complete: steps={steps_executed}, final_meas={last_measured}V"
                                print(final_msg)
                                return True, final_msg
                            except Exception as e:
                                msg = f"PS RampDown failed: {e}"
                                print(msg)
                                return False, msg
                    if "Battery Set Charge" in action_name:
                        import json
                        try:
                            data = json.loads(params) if params else {}
                            voltage = float(data.get('voltage'))
                            current = float(data.get('current'))
                            ps.battery_set_charge(voltage, current)
                            msg = f"PS Battery Set Charge: V={voltage}V I={current}A"
                            print(msg)
                            return True, msg
                        except Exception as e:
                            msg = f"PS Battery Set Charge failed: {e}"
                            print(msg)
                            return False, msg
                    if "Battery Set Discharge" in action_name:
                        import json
                        try:
                            data = json.loads(params) if params else {}
                            voltage = float(data.get('voltage'))
                            current = float(data.get('current'))
                            ps.battery_set_discharge(voltage, current)
                            msg = f"PS Battery Set Discharge: V={voltage}V I={current}A"
                            print(msg)
                            return True, msg
                        except Exception as e:
                            msg = f"PS Battery Set Discharge failed: {e}"
                            print(msg)
                            return False, msg
                    if "Read Errors" in action_name:
                        try:
                            resp = ps.read_errors()
                            msg = f"PS Error Status: {resp}"
                            print(msg)
                            return True, msg
                        except Exception as e:
                            msg = f"PS Read Errors failed: {e}"
                            print(msg)
                            return False, msg
                    if "Clear Errors" in action_name:
                        try:
                            ps.clear_errors()
                            msg = "PS Clear Errors"
                            print(msg)
                            return True, msg
                        except Exception as e:
                            msg = f"PS Clear Errors failed: {e}"
                            print(msg)
                            return False, msg
                    if "Sweep Voltage" in action_name:
                        try:
                            import json
                            d = json.loads(params) if params else {}
                            start = d.get('start')
                            step = d.get('step')
                            end = d.get('end')
                            delay = d.get('delay', 0.5)
                            log_file = d.get('log_file')
                            results = ps.sweep_voltage_and_log(start, step, end, delay=delay, log_path=log_file)
                            msg = f"PS Sweep Voltage logged {len(results)} points"
                            print(msg)
                            return True, msg
                        except Exception as e:
                            msg = f"PS Sweep Voltage failed: {e}"
                            print(msg)
                            return False, msg
                    if "Sweep Current" in action_name:
                        try:
                            import json
                            d = json.loads(params) if params else {}
                            start = d.get('start')
                            step = d.get('step')
                            end = d.get('end')
                            delay = d.get('delay', 0.5)
                            log_file = d.get('log_file')
                            results = ps.sweep_current_and_log(start, step, end, delay=delay, log_path=log_file)
                            msg = f"PS Sweep Current logged {len(results)} points"
                            print(msg)
                            return True, msg
                        except Exception as e:
                            msg = f"PS Sweep Current failed: {e}"
                            print(msg)
                            return False, msg
                # Oscilloscope (OS) actions
                if prefix == "OS":
                    if not hasattr(self.inst_mgr, 'siglent') or self.inst_mgr.siglent is None:
                        msg = "OS action failed: Oscilloscope not initialized"
                        print(msg)
                        return False, msg
                    scope = self.inst_mgr.siglent

                    def _parse_num(default=None):
                        if not params:
                            return default
                        try:
                            return float(params)
                        except Exception:
                            try:
                                d = json.loads(params)
                                if isinstance(d, dict) and d:
                                    return list(d.values())[0]
                            except Exception:
                                return default
                        return default

                    def _parse_dict():
                        if not params:
                            return {}
                        try:
                            return json.loads(params) if params else {}
                        except Exception:
                            return {}

                    if "Run" in action_name:
                        try:
                            self._log_cmd("OS RUN")
                            scope.run()
                            msg = "OS Run"
                            print(msg)
                            return True, msg
                        except Exception as e:
                            msg = f"OS Run failed: {e}"
                            print(msg)
                            return False, msg
                    if "Stop" in action_name:
                        try:
                            self._log_cmd("OS STOP")
                            scope.stop()
                            msg = "OS Stop"
                            print(msg)
                            return True, msg
                        except Exception as e:
                            msg = f"OS Stop failed: {e}"
                            print(msg)
                            return False, msg
                    if "Get Waveform" in action_name:
                        try:
                            self._log_cmd("OS GET WAVEFORM")
                            data = scope.get_waveform()
                            msg = f"OS Waveform length: {len(data) if data else 0}"
                            print(msg)
                            return True, msg
                        except Exception as e:
                            msg = f"OS Get Waveform failed: {e}"
                            print(msg)
                            return False, msg
                    if "Set Timebase" in action_name:
                        val = _parse_num()
                        try:
                            self._log_cmd(f"OS TIM:SCAL {val}")
                            scope.write(f"TIM:SCAL {val}")
                            return True, f"OS Timebase set to {val}"
                        except Exception as e:
                            return False, f"OS Set Timebase failed: {e}"
                    if "Set Channel Enable" in action_name:
                        d = _parse_dict()
                        ch = d.get("channel", 1)
                        state = str(d.get("state", "ON")).upper()
                        try:
                            self._log_cmd(f"OS C{ch}:TRA {state}")
                            scope.write(f"C{ch}:TRA {state}")
                            return True, f"OS CH{ch} {state}"
                        except Exception as e:
                            return False, f"OS Set Channel Enable failed: {e}"
                    if "Set Channel Scale" in action_name:
                        d = _parse_dict()
                        ch = d.get("channel", 1)
                        scale = d.get("scale", _parse_num())
                        try:
                            self._log_cmd(f"OS C{ch}:SCAL {scale}")
                            scope.write(f"C{ch}:SCAL {scale}")
                            return True, f"OS CH{ch} scale {scale}"
                        except Exception as e:
                            return False, f"OS Set Channel Scale failed: {e}"
                    if "Set Channel Offset" in action_name:
                        d = _parse_dict()
                        ch = d.get("channel", 1)
                        offset = d.get("offset", _parse_num())
                        try:
                            self._log_cmd(f"OS C{ch}:OFFS {offset}")
                            scope.write(f"C{ch}:OFFS {offset}")
                            return True, f"OS CH{ch} offset {offset}"
                        except Exception as e:
                            return False, f"OS Set Channel Offset failed: {e}"
                    if "Set Coupling" in action_name:
                        d = _parse_dict()
                        ch = d.get("channel", 1)
                        mode = d.get("mode", "DC").upper()
                        try:
                            self._log_cmd(f"OS C{ch}:COUP {mode}")
                            scope.write(f"C{ch}:COUP {mode}")
                            return True, f"OS CH{ch} coupling {mode}"
                        except Exception as e:
                            return False, f"OS Set Coupling failed: {e}"
                    if "Set Bandwidth Limit" in action_name:
                        d = _parse_dict()
                        ch = d.get("channel", 1)
                        state = str(d.get("state", "ON")).upper()
                        try:
                            self._log_cmd(f"OS C{ch}:BWL {state}")
                            scope.write(f"C{ch}:BWL {state}")
                            return True, f"OS CH{ch} BWL {state}"
                        except Exception as e:
                            return False, f"OS Set Bandwidth Limit failed: {e}"
                    if "Set Probe Attenuation" in action_name:
                        d = _parse_dict()
                        ch = d.get("channel", 1)
                        att = d.get("attenuation", _parse_num(10))
                        try:
                            self._log_cmd(f"OS C{ch}:PROB {att}")
                            scope.write(f"C{ch}:PROB {att}")
                            return True, f"OS CH{ch} probe {att}x"
                        except Exception as e:
                            return False, f"OS Set Probe Attenuation failed: {e}"
                    if "Set Acquisition Mode" in action_name:
                        mode = str(params or "NORM").upper()
                        try:
                            self._log_cmd(f"OS ACQ:MDEP {mode}")
                            scope.write(f"ACQ:MDEP {mode}")
                            return True, f"OS Acquisition mode {mode}"
                        except Exception as e:
                            return False, f"OS Set Acquisition Mode failed: {e}"
                    if "Set Memory Depth" in action_name:
                        depth = _parse_num()
                        try:
                            self._log_cmd(f"OS ACQ:MDEP {depth}")
                            scope.write(f"ACQ:MDEP {depth}")
                            return True, f"OS Memory depth {depth}"
                        except Exception as e:
                            return False, f"OS Set Memory Depth failed: {e}"
                    if "Set Trigger Source" in action_name:
                        src = str(params or "C1").upper()
                        try:
                            self._log_cmd(f"OS TRIG:SOUR {src}")
                            scope.write(f"TRIG:SOUR {src}")
                            return True, f"OS Trigger source {src}"
                        except Exception as e:
                            return False, f"OS Set Trigger Source failed: {e}"
                    if "Set Trigger Type" in action_name:
                        typ = str(params or "EDGE").upper()
                        try:
                            self._log_cmd(f"OS TRIG:MODE {typ}")
                            scope.write(f"TRIG:MODE {typ}")
                            return True, f"OS Trigger type {typ}"
                        except Exception as e:
                            return False, f"OS Set Trigger Type failed: {e}"
                    if "Set Trigger Level" in action_name:
                        level = _parse_num()
                        try:
                            self._log_cmd(f"OS TRIG:LEV {level}")
                            scope.write(f"TRIG:LEV {level}")
                            return True, f"OS Trigger level {level}"
                        except Exception as e:
                            return False, f"OS Set Trigger Level failed: {e}"
                    if "Set Trigger Slope" in action_name or "Set Trigger Polarity" in action_name:
                        slope = str(params or "POS").upper()
                        try:
                            self._log_cmd(f"OS TRIG:SLOP {slope}")
                            scope.write(f"TRIG:SLOP {slope}")
                            return True, f"OS Trigger slope {slope}"
                        except Exception as e:
                            return False, f"OS Set Trigger Slope failed: {e}"
                    if "Force Trigger" in action_name:
                        try:
                            self._log_cmd("OS TRIG:FORC")
                            scope.write("TRIG:FORC")
                            return True, "OS Trigger forced"
                        except Exception as e:
                            return False, f"OS Force Trigger failed: {e}"
                    if "Auto Setup" in action_name:
                        try:
                            self._log_cmd("OS AUTO")
                            scope.write("AUTO")
                            return True, "OS Auto setup"
                        except Exception as e:
                            return False, f"OS Auto Setup failed: {e}"
                    if "Measure (single)" in action_name:
                        d = _parse_dict()
                        meas = d.get("type", "VPP").upper()
                        ch = d.get("channel", 1)
                        try:
                            self._log_cmd(f"OS C{ch}:MEAS:{meas}?")
                            resp = scope.query(f"C{ch}:MEAS:{meas}?")
                            return True, f"OS Measure {meas} CH{ch}: {resp}"
                        except Exception as e:
                            return False, f"OS Measure failed: {e}"
                    if "Measure (all enabled)" in action_name:
                        try:
                            self._log_cmd("OS MEAS:ALL?")
                            resp = scope.query("MEAS:ALL?")
                            return True, f"OS Measures: {resp}"
                        except Exception as e:
                            return False, f"OS Measure all failed: {e}"
                    if "Acquire Screenshot" in action_name:
                        d = _parse_dict()
                        path = d.get("path", "scope.png")
                        try:
                            self._log_cmd("OS SCDP?")
                            data = scope.query("SCDP?")  # placeholder
                            with open(path, "wb") as f:
                                if isinstance(data, bytes):
                                    f.write(data)
                                else:
                                    f.write(str(data).encode())
                            return True, f"OS Screenshot saved: {path}"
                        except Exception as e:
                            return False, f"OS Acquire Screenshot failed: {e}"
                    if "Save Setup" in action_name:
                        d = _parse_dict()
                        path = d.get("path", "setup.stp")
                        try:
                            self._log_cmd(f"OS SAVE:SETT \"{path}\"")
                            scope.write(f"SAVE:SETT \"{path}\"")
                            return True, f"OS Setup saved: {path}"
                        except Exception as e:
                            return False, f"OS Save Setup failed: {e}"
                    if "Load Setup" in action_name:
                        d = _parse_dict()
                        path = d.get("path", "setup.stp")
                        try:
                            self._log_cmd(f"OS LOAD:SETT \"{path}\"")
                            scope.write(f"LOAD:SETT \"{path}\"")
                            return True, f"OS Setup loaded: {path}"
                        except Exception as e:
                            return False, f"OS Load Setup failed: {e}"

                # DC Load actions (LOAD)
                if prefix == "LOAD":
                    if "Connect" in action_name:
                        return self.inst_mgr.init_load()
                    if "Disconnect" in action_name:
                        return self.inst_mgr.end_load()
                    if not getattr(self.inst_mgr, "dc_load", None):
                        return False, "DC Load not initialized"
                    if "Input ON" in action_name:
                        return self.inst_mgr.dc_load_enable_input(True)
                    if "Input OFF" in action_name:
                        return self.inst_mgr.dc_load_enable_input(False)
                    if action_name.startswith("Set CC"):
                        try:
                            val = float(params)
                        except Exception:
                            return False, "Invalid current value"
                        self._log_cmd(f"LOAD CC {val}")
                        return self.inst_mgr.dc_load_set_cc(val)
                    if action_name.startswith("Set CV"):
                        try:
                            val = float(params)
                        except Exception:
                            return False, "Invalid voltage value"
                        self._log_cmd(f"LOAD CV {val}")
                        return self.inst_mgr.dc_load_set_cv(val)
                    if action_name.startswith("Set CP"):
                        try:
                            val = float(params)
                        except Exception:
                            return False, "Invalid power value"
                        self._log_cmd(f"LOAD CP {val}")
                        return self.inst_mgr.dc_load_set_cp(val)
                    if action_name.startswith("Set CR"):
                        try:
                            val = float(params)
                        except Exception:
                            return False, "Invalid resistance value"
                        self._log_cmd(f"LOAD CR {val}")
                        return self.inst_mgr.dc_load_set_cr(val)
                    if action_name.startswith("Measure VI"):
                        return self.inst_mgr.dc_load_measure_vi()
                    if action_name.startswith("Measure Power"):
                        return self.inst_mgr.dc_load_measure_power()
                    return False, f"Unsupported LOAD action: {action_name}"

                # Instrument lifecycle actions (INSTR)
                if prefix == "INSTR":
                    name = action_name.strip().upper()
                    if name == "INITIALIZE INSTRUMENTS":
                        s, m = self.inst_mgr.initialize_instruments()
                        msg = f"INSTR Init All: {m}"
                        print(msg)
                        return s, msg
                    if name == "INIT PS":
                        s, m = self.inst_mgr.init_ps()
                        msg = f"INSTR Init PS: {m}"
                        print(msg)
                        return s, msg
                    if name == "INIT GS":
                        s, m = self.inst_mgr.init_gs()
                        msg = f"INSTR Init GS: {m}"
                        print(msg)
                        return s, msg
                    if name == "INIT OS":
                        s, m = self.inst_mgr.init_os()
                        msg = f"INSTR Init OS: {m}"
                        print(msg)
                        return s, msg
                    if name == "END PS":
                        s, m = self.inst_mgr.end_ps()
                        msg = f"INSTR End PS: {m}"
                        print(msg)
                        return s, msg
                    if name == "END GS":
                        s, m = self.inst_mgr.end_gs()
                        msg = f"INSTR End GS: {m}"
                        print(msg)
                        return s, msg
                    if name == "END OS":
                        s, m = self.inst_mgr.end_os()
                        msg = f"INSTR End OS: {m}"
                        print(msg)
                        return s, msg
                    # fall through to other prefixes

                    if action_name.startswith("Check Message") or action_name.startswith("Listen For Message"):
                        # Expect params '0x123, timeout_s' or JSON {'id':123, 'timeout':2}
                        try:
                            if params:
                                import json
                                try:
                                    details = json.loads(params)
                                    search_id = details.get('id') or details.get('message_id')
                                    timeout = float(details.get('timeout', 2))
                                except Exception:
                                    parts = [p.strip() for p in params.split(',')]
                                    id_raw = parts[0]
                                    search_id = int(id_raw, 16) if id_raw.lower().startswith('0x') else int(id_raw)
                                    timeout = float(parts[1]) if len(parts) > 1 else 2.0
                            else:
                                msg = "CAN Check Message failed: no parameters provided"
                                print(msg)
                                return False, msg

                            found_event = threading.Event()
                            found_msg = {'msg': None}

                            def _listener(msg):
                                if msg.arbitration_id == search_id:
                                    found_msg['msg'] = msg
                                    found_event.set()

                            self.can_mgr.add_listener(_listener)
                            result = found_event.wait(timeout)
                            # Remove listener (best-effort — CANManager doesn't provide removal, but listeners is a list)
                            try:
                                self.can_mgr.listeners.remove(_listener)
                            except Exception:
                                pass

                            if result:
                                msg = f"CAN Message received: ID=0x{search_id:X}"
                                print(msg)
                                return True, msg
                            else:
                                msg = f"CAN Message not received within {timeout}s: ID=0x{search_id:X}"
                                print(msg)
                                return False, msg
                        except Exception as e:
                            msg = f"CAN Check Message failed: {e}"
                            print(msg)
                            return False, msg
            # Instrument Control Actions
            # Removed top-level instrument Set/Read actions - use instrument-prefixed actions (GS/PS) instead
                
            # Utility Actions
            elif action == "Wait":
                duration = float(params)
                print(f"Wait: {duration}s (starting)")
                # Use non-blocking wait to allow UI updates
                start_time = time.time()
                while time.time() - start_time < duration:
                    if not self.running:  # Allow early termination
                        msg = "Wait: Interrupted"
                        print(msg)
                        return False, msg
                    time.sleep(0.1)  # Sleep in small increments to allow responsiveness
                msg = f"Wait: {duration}s (completed)"
                print(msg)
                return True, msg
                
            # Removed top-level Check CAN - use 'CAN / Check Message' instead
                
            # Button Actions - These must verify their success
            elif action == "Initialize Instruments":
                success, msg = self.inst_mgr.initialize_instruments()
                print(f"Initialize Instruments: {msg}")
                return success, msg
                
            # Removed top-level Connect/Disconnect CAN - use prefixed 'CAN / Connect' or buttons instead
                    
            # Removed top-level start/stop cyclic CAN actions (use 'CAN / Start Cyclic CAN' prefixed form).
                    
            # Removed legacy top-level Start Trace/Stop Trace - use 'CAN / Start Trace' and 'CAN / Stop Trace'
                    
            else:
                msg = f"Unknown action: {action}"
                print(msg)
                return False, msg
                
        except Exception as e:
            msg = f"Action '{action}' failed with exception: {e}"
            print(msg)
            return False, msg

    def _handle_ramp_action(self, action_name, params):
        """
        Ramp a target (GS/PS/CAN) and measure GS+PS per step.
        Params expected as JSON:
        {
          "target": {"type": "GS_VOLT"|"PS_VOLT"|"CAN_SIGNAL", "message": "...", "signal": "..."},
          "start": 0, "end": 100, "step": 5, "dwell": 0.5,
          "retries": 2, "verify": true,
          "measure": {"gs": true, "ps": true}
        }
        """
        import json
        try:
            cfg = json.loads(params) if params else {}
        except Exception as e:
            return False, f"Invalid JSON params: {e}"

        target = cfg.get("target", {})
        start = float(cfg.get("start", 0))
        end = float(cfg.get("end", 0))
        step = float(cfg.get("step", 1))
        dwell = float(cfg.get("dwell", 0.5))
        retries = int(cfg.get("retries", 2))
        verify = bool(cfg.get("verify", False))
        measure_gs = bool(cfg.get("measure", {}).get("gs", True))
        measure_ps = bool(cfg.get("measure", {}).get("ps", True))

        if step == 0:
            return False, "Step cannot be zero"
        points = []
        v = start
        if start <= end and step > 0:
            while v <= end + 1e-9:
                points.append(round(v, 6))
                v += step
        elif start >= end and step < 0:
            while v >= end - 1e-9:
                points.append(round(v, 6))
                v += step
        else:
            return False, "Step sign does not move from start to end"

        gs = getattr(self.inst_mgr, "itech7900", None)
        # Some builds name the PS driver itech6000; fall back if itech6006 is absent
        ps = getattr(self.inst_mgr, "itech6006", None) or getattr(self.inst_mgr, "itech6000", None)

        def set_target(val):
            tt = target.get("type", "").upper()
            if tt == "GS_VOLT":
                if not gs:
                    return False, "GS not initialized"
                self._log_cmd(f"GS VOLT {val}")
                gs.set_grid_voltage(val)
                return True, f"GS set V={val}"
            if tt == "PS_VOLT":
                if not ps:
                    return False, "PS not initialized"
                self._log_cmd(f"PS VOLT {val}")
                ps.set_voltage(val)
                return True, f"PS set V={val}"
            if tt == "CAN_SIGNAL":
                if not self.can_mgr or not self.can_mgr.dbc_parser:
                    return False, "CAN not initialized or DBC missing"
                msg_name = target.get("message")
                sig_name = target.get("signal")
                if not msg_name or not sig_name:
                    return False, "Missing CAN message/signal"
                try:
                    self.can_mgr.send_message_with_overrides(msg_name, {sig_name: val})
                    return True, f"CAN {msg_name}.{sig_name}={val}"
                except Exception as e:
                    return False, f"CAN set failed: {e}"
            return False, "Unsupported target type"

        def measure_all():
            readings = {}
            if measure_gs and gs:
                try:
                    readings["gs_voltage"] = gs.get_grid_voltage()
                    readings["gs_current"] = gs.get_grid_current()
                    readings["gs_power"] = gs.measure_power_real()
                    readings["gs_pf"] = gs.measure_power_factor()
                    readings["gs_ithd"] = gs.measure_thd_current()
                    readings["gs_vthd"] = gs.measure_thd_voltage()
                    readings["gs_freq"] = gs.get_grid_frequency()
                except Exception:
                    readings["gs_error"] = "GS measure failed"
            if measure_ps and ps:
                try:
                    readings["ps_voltage"] = ps.get_voltage()
                    readings["ps_current"] = ps.get_current()
                    try:
                        readings["ps_power"] = ps.get_power()
                    except Exception:
                        v = readings.get("ps_voltage")
                        c = readings.get("ps_current")
                        readings["ps_power"] = v * c if v is not None and c is not None else None
                except Exception:
                    readings["ps_error"] = "PS measure failed"
            return readings

        logs = []
        for val in points:
            if self.stop_event.is_set() or not self.running:
                break
            ok, msg = set_target(val)
            if not ok:
                logs.append({"value": val, "status": "fail", "message": msg})
                return False, f"Ramp aborted at {val}: {msg}"

            if verify:
                verified = False
                for _ in range(retries + 1):
                    try:
                        tt = target.get("type", "").upper()
                        if tt == "GS_VOLT" and gs:
                            rb = gs.get_grid_voltage()
                            if abs(rb - val) <= 0.5:
                                verified = True
                                break
                        if tt == "PS_VOLT" and ps:
                            rb = ps.get_voltage()
                            if abs(rb - val) <= 0.5:
                                verified = True
                                break
                        if tt == "CAN_SIGNAL":
                            cache = getattr(self.can_mgr, "signal_cache", {})
                            sig = target.get("signal")
                            if cache.get(sig, {}).get("value") is not None:
                                verified = True
                                break
                    except Exception:
                        pass
                    time.sleep(0.1)
                if not verified:
                    logs.append({"value": val, "status": "fail", "message": "Verify failed"})
                    return False, f"Verify failed at {val}"

            time.sleep(dwell)
            readings = measure_all()
            logs.append({"value": val, "status": "ok", "readings": readings})

        # Emit structured ramp data for reporting (captured by MainWindow)
        try:
            if hasattr(self, "action_info") and hasattr(self, "_current_index") and self._current_index is not None:
                payload = json.dumps(logs)
                self.action_info.emit(self._current_index, f"[RAMP_LOG]{payload}")
        except Exception:
            pass

        self._log(20, f"Ramp completed with {len(logs)} points")
        return True, f"Ramp completed ({len(logs)} points)"
