import time
import threading
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
        self.logger = logger

    def _log(self, level, message):
        if self.logger:
            try:
                self.logger.log(level, message)
            except Exception:
                pass

    def set_steps(self, steps):
        self.steps = steps

    def start_sequence(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run_sequence)
        self.thread.daemon = True
        self.thread.start()
        self._log(20, "Sequence started")

    def stop_sequence(self):
        self.running = False
        self._log(20, "Sequence stop requested")

    def _run_sequence(self):
        print("Starting Sequence...")
        self._log(20, "Sequence thread running")
        for i, step in enumerate(self.steps):
            if not self.running:
                self._log(20, "Sequence aborted by user")
                break
            
            action = step.get('action')
            params = step.get('params')
            
            print(f"Executing Step {i+1}: {action}")
            self.step_completed.emit(i, "Running")
            
            try:
                # Execute action and get success/failure status and message
                success, message = self._execute_action(action, params, i)
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
                    break
                    
            except Exception as e:
                print(f"Step {i+1} Failed with exception: {e}")
                self._log(40, f"Step {i+1} exception: {e}")
                self.step_completed.emit(i, "Fail")
                # Stop on failure
                self.running = False
                break
            
            time.sleep(0.5)  # Delay between steps
            
        self.running = False
        self.sequence_finished.emit()
        print("Sequence Finished")
        self._log(20, "Sequence finished")

    def _execute_action(self, action, params, index=None):
        """
        Execute an action and return (success: bool, message: str).
        All actions must verify their success and return an informative message for the UI.
        """
        try:
            # Support instrument-prefixed actions (format: "XX / Action Name")
            if " / " in action:
                prefix, action_name = [p.strip() for p in action.split("/", 1)]
                prefix = prefix.upper()

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
                        gs.set_grid_voltage(val)
                        msg = f"GS Set Voltage: {val}V"
                        print(msg)
                        return True, msg

                    if action_name.startswith("Set Current"):
                        try:
                            val = float(params.replace("A", "").strip())
                        except Exception:
                            val = float(params)
                        gs.set_grid_current(val)
                        msg = f"GS Set Current: {val}A"
                        print(msg)
                        return True, msg

                    if action_name.startswith("Set Frequency"):
                        try:
                            val = float(params.replace("Hz", "").strip())
                        except Exception:
                            val = float(params)
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
                            gs.power_on()
                            msg = "GS Power ON"
                            print(msg)
                        else:
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

                    if "Set Signal and Verify" in action_name:
                        try:
                            import json
                            details = json.loads(params) if isinstance(params, str) else params
                            message_id = int(details.get('message_id', 0), 16) if isinstance(details.get('message_id'), str) else int(details.get('message_id', 0))
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
                        if getattr(ps, "connected", False):
                            msg = "PS Connect: already connected, reusing session"
                            print(msg)
                            return True, msg
                        s, m = ps.connect()
                        msg = f"PS Connect: {m}"
                        print(msg)
                        return s, msg
                    if "Disconnect" in action_name:
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
                    # Examples: Connect, Disconnect, Start Cyclic CAN, Stop Cyclic CAN, Send Message
                        except Exception as e:
                            msg = f"CAN Stop Cyclic By Name failed: {e}"
                            print(msg)
                            return False, msg

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
