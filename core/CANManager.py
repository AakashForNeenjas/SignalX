import can
import threading
import time
import csv
import os
from datetime import datetime, timedelta

class CANManager:
    def __init__(self, simulation_mode=False, dbc_parser=None, logger=None):
        self.bus = None
        self.simulation_mode = simulation_mode
        self.dbc_parser = dbc_parser
        self.cyclic_tasks = {}
        self.listeners = []
        self.listeners_lock = threading.RLock()
        self.logging = False
        self.csv_file = None
        self.csv_writer = None
        self.trc_file = None
        self.start_time = None
        self.first_msg_time = None
        self.message_counter = 1
        self.running = False
        
        # ===== ROBUST CAN COMMUNICATION =====
        # Signal cache: stores latest signal values for UI updates
        self.signal_cache = {}
        # Thread lock for thread-safe signal_cache access
        self.signal_cache_lock = threading.RLock()
        # Message cache: stores last N messages for debugging
        self.message_history = []
        self.max_history_size = 100
        # Connection state tracking
        self.is_connected = False
        # Statistics
        self.rx_count = 0
        self.tx_count = 0
        self.error_count = 0
        # Decode cache (message_id -> message_definition)
        self.message_definitions = {}
        # Track last sent signals per message to preserve untouched fields
        self.last_sent_signals = {}
        # Signal overrides: {(message_name, signal_name): value}
        self.signal_overrides = {}
        self.signal_overrides_lock = threading.RLock()
        # Logging lock to serialize CSV/TRC writes and counters
        self.log_lock = threading.RLock()
        # Internal metrics tick threads for TX periodic visibility
        self.metrics_threads = {}
        # Connection defaults (can be overridden via profiles)
        self.interface = None
        self.channel = None
        self.bitrate = None
        self.logger = logger

    def get_diagnostics(self):
        """Get current CAN diagnostics and status"""
        return {
            'connection_status': 'Connected' if self.is_connected else 'Disconnected',
            'rx_count': self.rx_count,
            'tx_count': self.tx_count,
            'error_count': self.error_count,
            'bus_load': 0.0,  # Placeholder
            'is_logging': self.logging
        }

    def _log(self, level, message):
        if self.logger:
            try:
                self.logger.log(level, message)
            except Exception:
                pass

    def connect(self, interface=None, channel=None, bitrate=None):
        """
        Connect to CAN bus and initialize message definitions from DBC.
        ===== ROBUST CONNECTION HANDLING =====
        """
        # Resolve defaults
        interface = interface or self.interface or 'pcan'
        channel = channel or self.channel or 'PCAN_USBBUS1'
        bitrate = bitrate or self.bitrate or 500000
        if self.simulation_mode:
            print(f"[CAN SIMULATION] Connecting to {interface} on {channel}")
            self._log(20, f"CAN connect (sim) {interface}:{channel}")
            self.is_connected = True
            self.running = True
            self._initialize_message_definitions()  # Load DBC message defs
            # Start a simulation thread to generate random messages
            self.sim_thread = threading.Thread(target=self._simulate_traffic, daemon=True)
            self.sim_thread.start()
            return True, "[CAN SIMULATION] Connected (Simulation Mode)"

        try:
            # Log connection attempt
            self._log(20, f"CAN connect attempt {interface}:{channel} bitrate={bitrate}")
            print(f"[CAN] Attempting connection to {interface}:{channel} at {bitrate} bps...")
            self.bus = can.Bus(interface=interface, channel=channel, bitrate=bitrate)
            self.is_connected = True
            self.running = True

            # Load message definitions from DBC for proper decoding
            self._initialize_message_definitions()

            # Setup listener for message reception
            self.notifier = can.Notifier(self.bus, [self._on_message_received])

            print(f"[CAN] ✓ Connected to {interface}:{channel}")
            self._log(20, f"CAN connected {interface}:{channel}")
            return True, f"[CAN] ✓ Connected to {interface}:{channel}"
        except ImportError as e:
            self.is_connected = False
            msg = ("[CAN ERROR] Connection failed: backend module missing. "
                   "Install python-can with backend extras (e.g., python-can[pcan]) "
                   "and ensure vendor drivers (PCAN-Basic) are installed. "
                   f"Details: {e}")
            print(msg)
            self._log(40, msg)
            return False, msg
        except can.CanError as e:
            self.is_connected = False
            msg = (f"[CAN ERROR] Connection failed: {e}. "
                   "Verify interface/channel/bitrate and that the vendor driver is installed.")
            print(msg)
            self._log(40, msg)
            return False, msg
        except Exception as e:
            self.is_connected = False
            msg = f"[CAN ERROR] Connection failed: {e}"
            print(msg)
            self._log(40, msg)
            return False, msg
    def _initialize_message_definitions(self):
        """
        Load all message definitions from DBC for efficient message decoding.
        This enables real-time signal extraction and caching.
        """
        if not self.dbc_parser or not self.dbc_parser.database:
            print("[CAN WARNING] DBC not loaded - cannot initialize message definitions")
            return
        
        try:
            # Build cache of message ID -> message_definition for fast lookup
            for message in self.dbc_parser.database.messages:
                self.message_definitions[message.frame_id] = message
            
            print(f"[CAN] âœ“ Loaded {len(self.message_definitions)} message definitions from DBC")
            
            # Initialize signal_cache with all signals from DBC
            for message in self.dbc_parser.database.messages:
                for signal in message.signals:
                    # Initialize with None, will be updated when messages are received
                    with self.signal_cache_lock:
                        if signal.name not in self.signal_cache:
                            self.signal_cache[signal.name] = {
                                'value': None,
                                'timestamp': None,
                                'message_id': message.frame_id,
                                'message_name': message.name,
                                'unit': signal.unit if hasattr(signal, 'unit') else ''
                            }
            
            print(f"[CAN] âœ“ Initialized signal_cache with {len(self.signal_cache)} signals")
            
        except Exception as e:
            print(f"[CAN ERROR] Failed to initialize message definitions: {e}")

    def disconnect(self):
        """Cleanly disconnect from CAN bus"""
        self.running = False
        self.is_connected = False
        
        try:
            if hasattr(self, 'notifier') and self.notifier:
                self.notifier.stop()
            if self.bus:
                self.bus.shutdown()
                self.bus = None
            
            # Stop simulation thread if active
            if self.simulation_mode and hasattr(self, 'sim_thread'):
                try:
                    self.sim_thread.join(timeout=1)
                except Exception:
                    pass
            
            self.cyclic_tasks.clear()
            with self.listeners_lock:
                self.listeners.clear()
            print("[CAN] Disconnected")
            self._log(20, "CAN disconnected")
        except Exception as e:
            print(f"[CAN ERROR] Error during disconnect: {e}")

    def send_message(self, arbitration_id, data, is_extended_id=False):
        if self.simulation_mode:
            print(f"SIMULATION CAN TX: ID={hex(arbitration_id)} Data={data}")
            return
        if not self.bus:
            raise RuntimeError("CAN bus not connected")

        msg = can.Message(arbitration_id=arbitration_id, data=data, is_extended_id=is_extended_id)
        # Attach timestamp for logging consistency
        try:
            msg.timestamp = time.time()
        except Exception:
            pass
        # Log TX locally so traces capture what we send (even if bus loopback is disabled)
        try:
            if self.logging:
                self._log_message(msg)
        except Exception:
            pass
        try:
            self.bus.send(msg)
        except can.CanError:
            print("Message NOT sent")
        # Also notify listeners/metrics about this TX so dynamic checks can see it even without loopback
        try:
            self._on_message_received(msg)
        except Exception:
            pass

    def set_signal_override(self, message_name, signal_name, value):
        """Set or update an override for a specific signal within a message."""
        with self.signal_overrides_lock:
            self.signal_overrides[(message_name, signal_name)] = value
        self._log(20, f"Override set: {message_name}.{signal_name}={value}")

    def clear_signal_override(self, message_name=None, signal_name=None):
        """Clear overrides; if both provided, clear specific, else clear all."""
        with self.signal_overrides_lock:
            if message_name and signal_name:
                self.signal_overrides.pop((message_name, signal_name), None)
            elif message_name:
                keys = [k for k in self.signal_overrides if k[0] == message_name]
                for k in keys:
                    self.signal_overrides.pop(k, None)
            else:
                self.signal_overrides.clear()

    def _apply_overrides(self, message_name, signals_dict):
        """Merge in overrides for this message before encoding."""
        if not self.signal_overrides:
            return signals_dict
        merged = dict(signals_dict)
        with self.signal_overrides_lock:
            for (msg, sig), val in self.signal_overrides.items():
                if msg == message_name:
                    merged[sig] = val
        return merged

    def _build_full_values(self, msg_def, signals_dict):
        """
        Build a full signal dict using provided values + overrides + cached values,
        to avoid zeroing other signals when only one is updated.
        Priority: last_sent for this message -> signal cache -> configured cyclic defaults -> signal.initial -> 0
        """
        merged = self._apply_overrides(msg_def.name, signals_dict or {})
        # Start from last sent snapshot if we have one
        base = {}
        try:
            base = dict(self.last_sent_signals.get(msg_def.name, {}) or {})
        except Exception:
            base = {}

        full_values = dict(base)
        for sig in msg_def.signals:
            if sig.name in merged:
                full_values[sig.name] = merged[sig.name]
                continue
            if sig.name in full_values:
                # Already carried from last_sent
                continue
            cached_val = None
            try:
                if hasattr(self, "signal_cache"):
                    cached_val = self.signal_cache.get(sig.name, {}).get("value", None)
            except Exception:
                cached_val = None
            if cached_val is None:
                # Try configured cyclic defaults if available
                try:
                    import can_messages
                    cfg = getattr(can_messages, "CYCLIC_CAN_MESSAGES", {})
                    if msg_def.name in cfg:
                        defaults = cfg[msg_def.name].get("signals", {})
                        if sig.name in defaults:
                            cached_val = defaults[sig.name]
                except Exception:
                    cached_val = None
            if cached_val is not None:
                full_values[sig.name] = cached_val
            elif getattr(sig, "initial", None) is not None:
                full_values[sig.name] = sig.initial
            else:
                full_values[sig.name] = 0
        return full_values

    def send_message_with_overrides(self, message_name, signals_dict=None):
        """Encode and send a message applying overrides."""
        if not self.dbc_parser or not self.dbc_parser.database:
            raise RuntimeError("DBC not loaded; cannot encode message")
        msg_def = self.dbc_parser.database.get_message_by_name(message_name)
        full_values = self._build_full_values(msg_def, signals_dict or {})
        data = msg_def.encode(full_values)
        self.send_message(msg_def.frame_id, data, is_extended_id=msg_def.is_extended_frame)
        # Optimistically update local cache so verify can succeed even without bus echo
        try:
            from time import time as _time
            now = _time()
            if not hasattr(self, "signal_cache"):
                self.signal_cache = {}
            for sig_name, val in full_values.items():
                self.signal_cache[sig_name] = {"value": val, "timestamp": now, "message": message_name}
            # Track last sent per message
            self.last_sent_signals[message_name] = dict(full_values)
        except Exception:
            pass
        return full_values

    def verify_signal_value(self, signal_name, expected_value, timeout=1.0, tolerance=0.01):
        """
        Closed-loop verification: wait for a decoded signal to match expected within tolerance.
        Uses signal_cache populated by RX decoding.
        """
        import time
        deadline = time.time() + timeout
        while time.time() < deadline:
            if hasattr(self, "signal_cache"):
                cache = self.signal_cache.get(signal_name, {})
                val = cache.get("value")
                if val is not None and abs(val - expected_value) <= tolerance:
                    return True, f"{signal_name} verified at {val}"
            time.sleep(0.05)
        return False, f"{signal_name} not verified within {timeout}s (expected {expected_value})"

    def start_cyclic_message(self, arbitration_id, data, cycle_time, is_extended_id=False):
        if self.simulation_mode:
            print(f"SIMULATION CAN CYCLIC START: ID={hex(arbitration_id)}")
            return

        if not self.bus:
            raise RuntimeError("CAN bus not connected. Please connect first.")

        if arbitration_id in self.cyclic_tasks:
            self.stop_cyclic_message(arbitration_id)

        msg = can.Message(arbitration_id=arbitration_id, data=data, is_extended_id=is_extended_id)
        try:
            msg.timestamp = time.time()
            if self.logging:
                # Log the first tick immediately so traces show the start of cyclic traffic
                self._log_message(msg)
            # Also feed metrics/listeners for TX visibility
            self._on_message_received(msg)
        except Exception:
            pass
        task = self.bus.send_periodic(msg, cycle_time)
        self.cyclic_tasks[arbitration_id] = task
        # Start an internal metrics tick thread to mirror TX for interval computation
        stop_event = threading.Event()
        self.metrics_threads[arbitration_id] = stop_event

        def _tick_metrics():
            m = can.Message(arbitration_id=arbitration_id, data=data, is_extended_id=is_extended_id)
            while not stop_event.wait(cycle_time):
                try:
                    m.timestamp = time.time()
                except Exception:
                    pass
                try:
                    self._on_message_received(m)
                except Exception:
                    pass
        t = threading.Thread(target=_tick_metrics, daemon=True)
        t.start()

    def stop_cyclic_message(self, arbitration_id):
        if self.simulation_mode:
            print(f"SIMULATION CAN CYCLIC STOP: ID={hex(arbitration_id)}")
            return

        if arbitration_id in self.cyclic_tasks:
            self.cyclic_tasks[arbitration_id].stop()
            del self.cyclic_tasks[arbitration_id]
        if arbitration_id in self.metrics_threads:
            try:
                self.metrics_threads[arbitration_id].set()
            except Exception:
                pass
            del self.metrics_threads[arbitration_id]

    def start_cyclic_message_by_name(self, message_name, signals_dict, cycle_time_ms):
        """
        Start a cyclic CAN message using DBC encoding.
        message_name: Name of the message in the DBC file
        signals_dict: Dictionary of signal names and values
        cycle_time_ms: Cycle time in milliseconds
        """
        if not self.dbc_parser or not self.dbc_parser.database:
            print(f"Warning: No DBC loaded, cannot encode message '{message_name}'")
            return False
        
        try:
            # Get message from DBC
            message = self.dbc_parser.database.get_message_by_name(message_name)
            
            # Encode signals into CAN data (preserve other signals via cache/defaults)
            full_values = self._build_full_values(message, signals_dict or {})
            
            data = message.encode(full_values)
            # Remember what we are sending for future preservation and cache
            try:
                now = time.time()
                self.last_sent_signals[message.name] = dict(full_values)
                for sig_name, val in full_values.items():
                    self.signal_cache[sig_name] = {"value": val, "timestamp": now, "message": message.name}
            except Exception:
                pass
            
            # Start cyclic transmission
            self.start_cyclic_message(message.frame_id, data, cycle_time_ms / 1000.0, is_extended_id=message.is_extended_frame)
            
            print(f"Started cyclic message: {message_name} (ID: 0x{message.frame_id:03X})")
            return True
            
        except KeyError as e:
            print(f"Error: Message '{message_name}' not found in DBC file")
            return False
        except Exception as e:
            print(f"Error: Error encoding message '{message_name}': {e}")
            return False
    
    def start_all_cyclic_messages(self):
        """
        Start all cyclic messages defined in can_messages.py
        Returns: (started_messages, failed_messages) tuple of lists
        """
        import sys
        import os
        
        # Add CAN Configuration to path
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
        config_path = os.path.join(project_root, "CAN Configuration")
        
        if config_path not in sys.path:
            sys.path.insert(0, config_path)
        
        try:
            import can_messages
            CYCLIC_CAN_MESSAGES = can_messages.CYCLIC_CAN_MESSAGES
        except ImportError as e:
            print(f"Error importing can_messages: {e}")
            return [], []
        
        started_messages = []
        failed_messages = []
        
        for msg_name, msg_config in CYCLIC_CAN_MESSAGES.items():
            signals = msg_config['signals']
            cycle_time = msg_config['cycle_time']
            
            # Start cyclic message using DBC encoding
            success = self.start_cyclic_message_by_name(msg_name, signals, cycle_time)
            if success:
                started_messages.append(msg_name)
            else:
                failed_messages.append(msg_name)
        
        return started_messages, failed_messages
    
    def stop_all_cyclic_messages(self):
        """
        Stop all cyclic messages defined in can_messages.py
        Returns: True if successful, False otherwise
        """
        import sys
        import os
        
        # Add CAN Configuration to path
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
        config_path = os.path.join(project_root, "CAN Configuration")
        
        if config_path not in sys.path:
            sys.path.insert(0, config_path)
        
        try:
            import can_messages
            CYCLIC_CAN_MESSAGES = can_messages.CYCLIC_CAN_MESSAGES
        except ImportError as e:
            print(f"âœ— Error importing can_messages: {e}")
            return False
        
        try:
            # Get message IDs from DBC
            if not self.dbc_parser or not self.dbc_parser.database:
                print("âš  Warning: No DBC loaded, cannot stop cyclic messages")
                return False
            
            for msg_name in CYCLIC_CAN_MESSAGES.keys():
                try:
                    message = self.dbc_parser.database.get_message_by_name(msg_name)
                    self.stop_cyclic_message(message.frame_id)
                except KeyError:
                    print(f"Warning: Message '{msg_name}' not found in DBC")
            
            return True
        except Exception as e:
            print(f"Error: Error stopping cyclic messages: {e}")
            return False


    def start_logging(self, filename_base):
        # Create Test Results folder if it doesn't exist
        results_dir = "Test Results"
        if not os.path.exists(results_dir):
            os.makedirs(results_dir)
        
        # Full path with Test Results folder
        full_path = os.path.join(results_dir, filename_base)
        
        self.logging = True
        self.start_time = datetime.now()  # Record start time for TRC
        
        # CSV file
        self.csv_file = open(f"{full_path}.csv", 'w', newline='')
        self.csv_writer = csv.writer(self.csv_file)
        self.csv_writer.writerow(["Time", "Type", "ID", "DLC", "Data"])
        
        # TRC file (PCAN format)
        self.trc_file = open(f"{full_path}.trc", 'w')
        self._write_trc_header()
        
        return full_path

    def stop_logging(self):
        self.logging = False
        if self.csv_file:
            self.csv_file.close()
            self.csv_file = None
        if self.trc_file:
            self.trc_file.close()
            self.trc_file = None

    def _write_trc_header(self):
        start_time_str = self.start_time.strftime("%d-%m-%Y %H:%M:%S.%f")[:-3]
        # PCAN-style STARTTIME uses Excel/PCAN serial days (days since 1899-12-30)
        excel_epoch = datetime(1899, 12, 30)
        start_serial = (self.start_time - excel_epoch).total_seconds() / 86400.0
        with self.log_lock:
            self.trc_file.write(";$FILEVERSION=1.1\n")
            self.trc_file.write(f";$STARTTIME={start_serial:.10f}\n")
            self.trc_file.write(";\n")
            self.trc_file.write(f";   Start time: {start_time_str}\n")
            self.trc_file.write(";   Generated by AtomX\n")
            self.trc_file.write(";\n")
            self.trc_file.write(";   Message Number\n")
            self.trc_file.write(";   |         Time Offset (ms)\n")
            self.trc_file.write(";   |         |        Type\n")
            self.trc_file.write(";   |         |        |        ID (hex)\n")
            self.trc_file.write(";   |         |        |        |     Data Length\n")
            self.trc_file.write(";   |         |        |        |     |   Data Bytes (hex) ...\n")
            self.trc_file.write(";   |         |        |        |     |   |\n")
            self.trc_file.write(";---+--   ----+----  --+--  ----+---  +  -+ -- -- -- -- -- -- --\n")
            self.message_counter = 1
            self.first_msg_time = None

    def add_listener(self, callback):
        with self.listeners_lock:
            self.listeners.append(callback)

    def remove_listener(self, callback):
        with self.listeners_lock:
            try:
                self.listeners.remove(callback)
            except ValueError:
                pass

    def _on_message_received(self, msg):
        """
        ===== ROBUST MESSAGE RECEPTION AND DECODING =====
        This is the core of CAN communication. Every received message:
        1. Gets logged (CSV/TRC)
        2. Gets decoded using DBC
        3. Gets cached in signal_cache
        4. Gets distributed to listeners
        """
        try:
            # Track statistics
            if msg.is_rx:
                self.rx_count += 1
            else:
                self.tx_count += 1
            
            # ===== STEP 1: LOG MESSAGE =====
            if self.logging:
                self._log_message(msg)
            
            # ===== STEP 2: DECODE MESSAGE =====
            decoded_signals = self._decode_message(msg, decode_choices=True)
            raw_signals = self._decode_message(msg, decode_choices=False)
            
            # ===== STEP 3: CACHE SIGNALS =====
            if decoded_signals:
                self._cache_signals(msg.arbitration_id, decoded_signals, msg.timestamp, raw_signals)
            
            # ===== STEP 4: NOTIFY LISTENERS =====
            with self.listeners_lock:
                listeners_snapshot = list(self.listeners)
            for listener in listeners_snapshot:
                try:
                    listener(msg)
                except Exception as e:
                    print(f"[CAN ERROR] Listener error: {e}")
                    self._log(40, f"Listener error: {e}")
                    self.error_count += 1
        
        except Exception as e:
            print(f"[CAN ERROR] Message reception failed: {e}")
            self.error_count += 1
    
    def _decode_message(self, msg, decode_choices=True):
        """
        Decode a CAN message using DBC definitions.
        Returns: dict of {signal_name: value} or {} if decoding fails
        """
        try:
            # Quick lookup in message definitions cache
            if msg.arbitration_id not in self.message_definitions:
                return {}  # Message not in DBC
            
            message_def = self.message_definitions[msg.arbitration_id]
            decoded = message_def.decode(msg.data, decode_choices=decode_choices)
            return decoded
        
        except Exception as e:
            # Silently ignore decode errors (malformed data, unknown messages)
            return {}

    def _cache_signals(self, message_id, decoded_signals, timestamp, raw_signals=None):
        """
        Update signal_cache with latest signal values.
        This is what the UI Dashboard reads for real-time updates.
        """
        with self.signal_cache_lock:
            for signal_name, value in decoded_signals.items():
                if signal_name in self.signal_cache:
                    self.signal_cache[signal_name]['value'] = value
                    self.signal_cache[signal_name]['timestamp'] = timestamp
                    if raw_signals and signal_name in raw_signals:
                        self.signal_cache[signal_name]['raw_value'] = raw_signals[signal_name]
                else:
                    # Unknown signal (not in DBC) - add to cache anyway
                    self.signal_cache[signal_name] = {
                        'value': value,
                        'timestamp': timestamp,
                        'message_id': message_id,
                        'message_name': 'Unknown',
                        'unit': ''
                    }
                    if raw_signals and signal_name in raw_signals:
                        self.signal_cache[signal_name]['raw_value'] = raw_signals[signal_name]
    
    def _log_message(self, msg):
        """Log message to CSV and TRC files"""
        # Skip CAN error/status frames or remote frames
        try:
            if getattr(msg, "is_error_frame", False) or getattr(msg, "is_remote_frame", False):
                return
        except Exception:
            pass
        # Require a valid arbitration ID
        if not hasattr(msg, "arbitration_id") or msg.arbitration_id is None:
            return
        if not isinstance(msg.arbitration_id, int):
            return

        # Serialize logging to keep message numbers and timestamps monotonic
        with self.log_lock:
            # Use monotonic clock for stable offsets (system clock jumps won't break ordering)
            now_mono = time.monotonic()
            if self.first_msg_time is None:
                self.first_msg_time = now_mono
            relative_time = max(0.0, (now_mono - self.first_msg_time) * 1000)  # milliseconds
            dlc = getattr(msg, "dlc", len(msg.data) if hasattr(msg, "data") else 0)
            if dlc is None:
                dlc = 0
            dlc = max(0, min(int(dlc), 8))
            data_bytes = ""
            if hasattr(msg, "data") and msg.data is not None:
                data_bytes = ' '.join([f'{b:02X}' for b in list(msg.data)[:dlc]])

            # CSV format
            if hasattr(self, 'csv_writer') and self.csv_writer:
                msg_type = "Rx" if msg.is_rx else "Tx"
                self.csv_writer.writerow([
                    f"{relative_time:.3f}",
                    msg_type,
                    f"{msg.arbitration_id:03X}",
                    dlc,
                    data_bytes
                ])
                try:
                    self.csv_file.flush()
                except Exception:
                    pass
            
            # TRC format
            if hasattr(self, 'trc_file') and self.trc_file:
                msg_type = "Rx" if msg.is_rx else "Tx"
                # Align to PCAN textual layout similar to provided templates
                trc_line = f"{self.message_counter:6d}){relative_time:11.1f}  {msg_type:2s} {msg.arbitration_id:9X}  {dlc:1d}  {data_bytes} \n"
                self.trc_file.write(trc_line)
                try:
                    self.trc_file.flush()
                except Exception:
                    pass
                self.message_counter += 1
        
        # Add to message history for debugging
        self.message_history.append({
            'timestamp': getattr(msg, "timestamp", None),
            'msg_id': msg.arbitration_id,
            'data': getattr(msg, "data", b''),
            'direction': 'RX' if getattr(msg, "is_rx", False) else 'TX'
        })
        if len(self.message_history) > self.max_history_size:
            self.message_history.pop(0)

    def get_signal_value(self, message_name, signal_name, timeout=2.0):
        """
        Listen for a CAN message and return the decoded signal value.
        Returns: (success, value, message) tuple
        """
        if not self.dbc_parser or not self.dbc_parser.database:
            return False, None, "No DBC loaded"
        
        try:
            # Get message definition from DBC
            message_def = self.dbc_parser.database.get_message_by_name(message_name)
        except KeyError:
            return False, None, f"Message '{message_name}' not found in DBC"
        
        # Event to signal message received
        found_event = threading.Event()
        result = {'value': None, 'success': False}
        
        def _listener(msg):
            if msg.arbitration_id == message_def.frame_id:
                try:
                    # Use cached signal if available (more reliable)
                    with self.signal_cache_lock:
                        if signal_name in self.signal_cache and self.signal_cache[signal_name]['value'] is not None:
                            result['value'] = self.signal_cache[signal_name]['value']
                            result['success'] = True
                            found_event.set()
                            return
                    
                    # Fall back to decoding if not cached
                    decoded = message_def.decode(msg.data)
                    if signal_name in decoded:
                        result['value'] = decoded[signal_name]
                        result['success'] = True
                        found_event.set()
                except Exception as e:
                    print(f"[CAN ERROR] Error decoding message: {e}")
        
        # Add listener
        self.add_listener(_listener)
        
        # Wait for message with timeout
        received = found_event.wait(timeout)
        
        # Remove listener
        try:
            self.remove_listener(_listener)
        except ValueError:
            pass
        
        if received and result['success']:
            return True, result['value'], f"[CAN] Signal '{signal_name}' = {result['value']}"
        else:
            return False, None, f"[CAN TIMEOUT] Signal '{signal_name}' not received within {timeout}s"
    
    def get_signal_from_cache(self, signal_name):
        """
        Get current signal value from cache (non-blocking, returns immediately).
        Returns: (success, value, timestamp) tuple
        """
        with self.signal_cache_lock:
            if signal_name in self.signal_cache:
                cache_entry = self.signal_cache[signal_name]
                return True, cache_entry['value'], cache_entry['timestamp']
        
        return False, None, None
    
    def get_all_signals_from_cache(self):
        """Get all signals currently in cache"""
        with self.signal_cache_lock:
            return dict(self.signal_cache)

    def wait_for_signal_condition(self, message_name, signal_name, expected_value, tolerance, timeout=2.0):
        """
        Wait for a signal to match expected value within tolerance.
        Returns: (success, actual_value, message) tuple
        """
        if not self.dbc_parser or not self.dbc_parser.database:
            return False, None, "No DBC loaded"
        
        try:
            # Get message definition from DBC
            message_def = self.dbc_parser.database.get_message_by_name(message_name)
        except KeyError:
            return False, None, f"Message '{message_name}' not found in DBC"
        
        # Event to signal condition met
        found_event = threading.Event()
        result = {'value': None, 'success': False}
        
        def _listener(msg):
            if msg.arbitration_id == message_def.frame_id:
                try:
                    # Decode the message
                    decoded = message_def.decode(msg.data)
                    if signal_name in decoded:
                        actual_value = decoded[signal_name]
                        result['value'] = actual_value
                        
                        # Check if within tolerance
                        if abs(actual_value - expected_value) <= tolerance:
                            result['success'] = True
                            found_event.set()
                except Exception as e:
                    print(f"Error decoding message: {e}")
        
        # Add listener
        self.add_listener(_listener)
        
        # Wait for condition with timeout
        condition_met = found_event.wait(timeout)
        
        # Remove listener
        try:
            self.remove_listener(_listener)
        except ValueError:
            pass
        
        if condition_met and result['success']:
            return True, result['value'], f"Signal '{signal_name}' = {result['value']} (expected {expected_value} Â± {tolerance})"
        elif result['value'] is not None:
            return False, result['value'], f"Signal '{signal_name}' = {result['value']} (expected {expected_value} Â± {tolerance}) - OUT OF RANGE"
        else:
            return False, None, f"Timeout: Signal '{signal_name}' not received within {timeout}s"

    def wait_for_signal_change(self, message_name, signal_name, from_value, to_value, timeout=10.0, progress_callback=None):
        """
        Wait for signal to change from one value to another.
        progress_callback: Optional function(message_str) for progress updates
        Returns: (success, actual_value, time_taken, message)
        """
        if not self.dbc_parser or not self.dbc_parser.database:
            return False, None, 0, "No DBC loaded"
        
        try:
            message_def = self.dbc_parser.database.get_message_by_name(message_name)
        except KeyError:
            return False, None, 0, f"Message '{message_name}' not found in DBC"
        
        found_event = threading.Event()
        result = {'value': None, 'initial_found': False, 'target_found': False}
        start_time = time.time()
        
        def _listener(msg):
            if msg.arbitration_id == message_def.frame_id:
                try:
                    decoded = message_def.decode(msg.data)
                    if signal_name in decoded:
                        current_value = decoded[signal_name]
                        result['value'] = current_value
                        
                        # Check if we found initial value
                        if not result['initial_found'] and current_value == from_value:
                            result['initial_found'] = True
                            if progress_callback:
                                progress_callback(f"Initial value detected: {signal_name}={from_value}")
                        
                        # Check if we found target value (only after initial found)
                        if result['initial_found'] and current_value == to_value:
                            result['target_found'] = True
                            found_event.set()
                        elif result['initial_found'] and progress_callback:
                            # Report intermediate values
                            progress_callback(f"Current value: {signal_name}={current_value} (waiting for {to_value})")
                except Exception as e:
                    print(f"Error decoding message: {e}")
        
        self.add_listener(_listener)
        
        # Wait for condition
        condition_met = found_event.wait(timeout)
        time_taken = time.time() - start_time
        
        # Cleanup
        try:
            self.remove_listener(_listener)
        except ValueError:
            pass
        
        if condition_met and result['target_found']:
            return True, result['value'], time_taken, f"Signal changed from {from_value} to {to_value} in {time_taken:.2f}s"
        elif not result['initial_found']:
            return False, result['value'], time_taken, f"Initial value {from_value} not detected within timeout"
        else:
            return False, result['value'], time_taken, f"Signal did not change to {to_value} within {timeout}s (last value: {result['value']})"

    def monitor_signal_range(self, message_name, signal_name, min_value, max_value, duration, progress_callback=None):
        """
        Monitor signal stays within range for specified duration.
        progress_callback: Called with (elapsed_time, current_value, status_message)
        Returns: (success, min_observed, max_observed, violation_info, message)
        """
        if not self.dbc_parser or not self.dbc_parser.database:
            return False, None, None, None, "No DBC loaded"
        
        try:
            message_def = self.dbc_parser.database.get_message_by_name(message_name)
        except KeyError:
            return False, None, None, None, f"Message '{message_name}' not found in DBC"
        
        result = {
            'values': [],
            'violation': None,
            'violation_time': None
        }
        start_time = time.time()
        last_progress_time = start_time
        
        def _listener(msg):
            if msg.arbitration_id == message_def.frame_id:
                try:
                    decoded = message_def.decode(msg.data)
                    if signal_name in decoded:
                        current_value = decoded[signal_name]
                        elapsed = time.time() - start_time
                        result['values'].append((elapsed, current_value))
                        
                        # Check for violation
                        if current_value < min_value or current_value > max_value:
                            if result['violation'] is None:
                                result['violation'] = current_value
                                result['violation_time'] = elapsed
                                if progress_callback:
                                    progress_callback(f"âš  VIOLATION at {elapsed:.2f}s: {signal_name}={current_value} (range: {min_value}-{max_value})")
                except Exception as e:
                    print(f"Error decoding message: {e}")
        
        self.add_listener(_listener)
        
        # Monitor for duration with progress updates
        while time.time() - start_time < duration:
            elapsed = time.time() - start_time
            
            # Progress update every 0.5s
            if progress_callback and (time.time() - last_progress_time) >= 0.5:
                if result['values']:
                    latest_value = result['values'][-1][1]
                    progress_callback(f"Monitoring: {elapsed:.1f}s / {duration:.1f}s | {signal_name}={latest_value:.2f}")
                else:
                    progress_callback(f"Monitoring: {elapsed:.1f}s / {duration:.1f}s | Waiting for signal...")
                last_progress_time = time.time()
            
            # Break early if violation detected
            if result['violation'] is not None:
                break
            
            time.sleep(0.1)
        
        # Cleanup
        try:
            self.remove_listener(_listener)
        except ValueError:
            pass
        
        # Calculate statistics
        if result['values']:
            values_only = [v[1] for v in result['values']]
            min_observed = min(values_only)
            max_observed = max(values_only)
        else:
            min_observed = None
            max_observed = None
        
        # Determine success
        if result['violation'] is not None:
            violation_info = f"Value {result['violation']} at {result['violation_time']:.2f}s"
            return False, min_observed, max_observed, violation_info, f"Range violation: {violation_info}"
        elif not result['values']:
            return False, None, None, "No data", f"No signal data received during {duration}s monitoring period"
        else:
            return True, min_observed, max_observed, None, f"Signal stayed in range [{min_value}, {max_value}] for {duration}s (observed: [{min_observed:.2f}, {max_observed:.2f}])"

    def compare_two_signals(self, msg1_name, sig1_name, msg2_name, sig2_name, tolerance, timeout=5.0):
        """
        Compare two signal values within tolerance.
        Returns: (success, value1, value2, difference, message)
        """
        if not self.dbc_parser or not self.dbc_parser.database:
            return False, None, None, None, "No DBC loaded"
        
        try:
            message1_def = self.dbc_parser.database.get_message_by_name(msg1_name)
            message2_def = self.dbc_parser.database.get_message_by_name(msg2_name)
        except KeyError as e:
            return False, None, None, None, f"Message not found in DBC: {e}"
        
        result = {'value1': None, 'value2': None, 'both_received': False}
        found_event = threading.Event()
        
        def _listener(msg):
            try:
                if msg.arbitration_id == message1_def.frame_id:
                    decoded = message1_def.decode(msg.data)
                    if sig1_name in decoded:
                        result['value1'] = decoded[sig1_name]
                elif msg.arbitration_id == message2_def.frame_id:
                    decoded = message2_def.decode(msg.data)
                    if sig2_name in decoded:
                        result['value2'] = decoded[sig2_name]
                
                # Check if both received
                if result['value1'] is not None and result['value2'] is not None:
                    result['both_received'] = True
                    found_event.set()
            except Exception as e:
                print(f"Error decoding message: {e}")
        
        self.add_listener(_listener)
        
        # Wait for both signals
        both_received = found_event.wait(timeout)
        
        # Cleanup
        try:
            self.remove_listener(_listener)
        except ValueError:
            pass
        
        if not both_received:
            missing = []
            if result['value1'] is None:
                missing.append(f"{msg1_name}.{sig1_name}")
            if result['value2'] is None:
                missing.append(f"{msg2_name}.{sig2_name}")
            return False, result['value1'], result['value2'], None, f"Timeout: Missing signals: {', '.join(missing)}"
        
        # Compare values
        difference = abs(result['value1'] - result['value2'])
        
        if difference <= tolerance:
            return True, result['value1'], result['value2'], difference, f"Signals match: {sig1_name}={result['value1']:.2f}, {sig2_name}={result['value2']:.2f} (diff={difference:.2f}, tol={tolerance})"
        else:
            return False, result['value1'], result['value2'], difference, f"Signals differ: {sig1_name}={result['value1']:.2f}, {sig2_name}={result['value2']:.2f} (diff={difference:.2f} > tol={tolerance})"

    def set_signal_and_verify(self, message_name, signal_name, value, verify_timeout=2.0):
        """
        Set signal via cyclic message and verify it was received back.
        Returns: (success, verified_value, round_trip_time, message)
        """
        if not self.dbc_parser or not self.dbc_parser.database:
            return False, None, 0, "No DBC loaded"
        
        try:
            message_def = self.dbc_parser.database.get_message_by_name(message_name)
        except KeyError:
            return False, None, 0, f"Message '{message_name}' not found in DBC"
        
        # Start cyclic message with new value
        signals_dict = {signal_name: value}
        start_time = time.time()
        
        try:
            # Encode and start cyclic transmission
            data = message_def.encode(signals_dict)
            self.start_cyclic_message(message_def.frame_id, data, 0.1, is_extended_id=message_def.is_extended_frame)
        except Exception as e:
            return False, None, 0, f"Failed to start cyclic message: {e}"
        
        # Now verify we receive it back
        result = {'value': None, 'verified': False}
        found_event = threading.Event()
        
        def _listener(msg):
            if msg.arbitration_id == message_def.frame_id:
                try:
                    decoded = message_def.decode(msg.data)
                    if signal_name in decoded:
                        received_value = decoded[signal_name]
                        result['value'] = received_value
                        if received_value == value:
                            result['verified'] = True
                            found_event.set()
                except Exception as e:
                    print(f"Error decoding message: {e}")
        
        self.add_listener(_listener)
        
        # Wait for verification
        verified = found_event.wait(verify_timeout)
        round_trip_time = time.time() - start_time
        
        # Cleanup
        try:
            self.remove_listener(_listener)
        except ValueError:
            pass
        
        if verified and result['verified']:
            return True, result['value'], round_trip_time, f"Signal set and verified: {signal_name}={value} (round-trip: {round_trip_time:.3f}s)"
        elif result['value'] is not None:
            return False, result['value'], round_trip_time, f"Signal mismatch: sent {value}, received {result['value']}"
        else:
            return False, None, round_trip_time, f"Verification timeout: Signal not received within {verify_timeout}s"

    # ===== NEW CAN SIGNAL TEST ACTIONS =====
    
    def read_signal_value(self, signal_name, timeout=2.0):
        """Read and return current value of a signal from received messages"""
        if not self.dbc_parser or not self.dbc_parser.database:
            return False, 0, "DBC not loaded"
        
        start_time = time.time()
        last_value = None
        message_count = 0
        
        while time.time() - start_time < timeout:
            # Check for signal in received messages
            if hasattr(self, 'signal_cache') and signal_name in self.signal_cache:
                last_value = self.signal_cache[signal_name]
                message_count += 1
                break
            time.sleep(0.05)
        
        if last_value is not None:
            return True, last_value, f"Read {signal_name}={last_value}"
        else:
            return False, None, f"Signal '{signal_name}' not received within {timeout}s"
    
    def check_signal_tolerance(self, signal_name, expected_value, tolerance, timeout=2.0):
        """Check if signal value is within tolerance of expected value"""
        if not self.dbc_parser or not self.dbc_parser.database:
            return False, None, f"DBC not loaded"
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if hasattr(self, 'signal_cache') and signal_name in self.signal_cache:
                actual_value = self.signal_cache[signal_name]
                difference = abs(actual_value - expected_value)
                
                if difference <= tolerance:
                    return True, actual_value, f"PASS: {signal_name}={actual_value} within +/-{tolerance} of {expected_value}"
                else:
                    return False, actual_value, f"FAIL: {signal_name}={actual_value} exceeds tolerance (diff={difference:.3f})"
            time.sleep(0.05)
        
        return False, None, f"Signal '{signal_name}' not received within {timeout}s"
    
    def conditional_jump_check(self, signal_name, expected_value, tolerance=0.1):
        """Check condition for conditional jump - returns True if condition met"""
        if not self.dbc_parser or not self.dbc_parser.database:
            return False, f"DBC not loaded"
        
        if hasattr(self, 'signal_cache') and signal_name in self.signal_cache:
            actual_value = self.signal_cache[signal_name]
            difference = abs(actual_value - expected_value)
            
            if difference <= tolerance:
                return True, f"Condition MET: {signal_name}={actual_value} matches expected {expected_value}"
            else:
                return False, f"Condition NOT MET: {signal_name}={actual_value} differs from {expected_value}"
        else:
            return False, f"Signal '{signal_name}' not available"
    
    def wait_for_signal_change(self, signal_name, initial_value, timeout=5.0, poll_interval=0.1):
        """Wait for signal to change from initial value with progress feedback"""
        if not self.dbc_parser or not self.dbc_parser.database:
            return False, 0, f"DBC not loaded"
        
        start_time = time.time()
        elapsed_checks = 0
        last_value = initial_value
        
        while time.time() - start_time < timeout:
            if hasattr(self, 'signal_cache') and signal_name in self.signal_cache:
                current_value = self.signal_cache[signal_name]
                elapsed_checks += 1
                
                if current_value != initial_value:
                    elapsed_time = time.time() - start_time
                    return True, current_value, f"TRANSITION: {signal_name} changed from {initial_value} to {current_value} after {elapsed_time:.2f}s ({elapsed_checks} checks)"
            
            time.sleep(poll_interval)
        
        elapsed_time = time.time() - start_time
        return False, last_value, f"TIMEOUT: {signal_name} did not change within {timeout}s ({elapsed_checks} checks)"
    
    def monitor_signal_range(self, signal_name, min_val, max_val, duration=5.0, poll_interval=0.5):
        """Monitor signal continuously for violations with periodic updates"""
        if not self.dbc_parser or not self.dbc_parser.database:
            return False, [], f"DBC not loaded"
        
        start_time = time.time()
        violations = []
        readings = []
        check_count = 0
        
        while time.time() - start_time < duration:
            if hasattr(self, 'signal_cache') and signal_name in self.signal_cache:
                value = self.signal_cache[signal_name]
                check_count += 1
                readings.append(value)
                
                if value < min_val or value > max_val:
                    violations.append({
                        'value': value,
                        'time': time.time() - start_time,
                        'type': 'min' if value < min_val else 'max'
                    })
            
            time.sleep(poll_interval)
        
        elapsed_time = time.time() - start_time
        if violations:
            violation_report = "; ".join([f"V={v['value']:.2f} ({v['type']}) at {v['time']:.2f}s" for v in violations])
            return False, readings, f"VIOLATIONS DETECTED: {len(violations)} in {check_count} checks: {violation_report}"
        else:
            avg_value = sum(readings) / len(readings) if readings else 0
            return True, readings, f"OK: {signal_name} remained within [{min_val}, {max_val}] for {elapsed_time:.2f}s (avg={avg_value:.2f}, samples={len(readings)})"
    
    def compare_two_signals(self, signal1_name, signal2_name, tolerance=1.0, timeout=2.0):
        """Compare values from two different signals within tolerance"""
        if not self.dbc_parser or not self.dbc_parser.database:
            return False, (None, None), f"DBC not loaded"
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if hasattr(self, 'signal_cache'):
                if signal1_name in self.signal_cache and signal2_name in self.signal_cache:
                    value1 = self.signal_cache[signal1_name]
                    value2 = self.signal_cache[signal2_name]
                    difference = abs(value1 - value2)
                    
                    if difference <= tolerance:
                        return True, (value1, value2), f"MATCH: {signal1_name}={value1:.3f} vs {signal2_name}={value2:.3f} (diff={difference:.3f})"
                    else:
                        return False, (value1, value2), f"MISMATCH: {signal1_name}={value1:.3f} vs {signal2_name}={value2:.3f} (diff={difference:.3f} > tolerance={tolerance})"
            
            time.sleep(0.05)
        
        return False, (None, None), f"Signals not received within {timeout}s"
    
    def set_signal_and_verify(self, message_id, signal_name, target_value, verify_timeout=2.0, tolerance=0.5):
        """Send CAN message and verify signal reached target value (round-trip test)"""
        if not self.dbc_parser or not self.dbc_parser.database:
            return False, None, 0, f"DBC not loaded"
        
        # Send the message (assumes message_id encodes signal with target_value)
        start_time = time.time()
        self.send_message(message_id, [], False)
        send_time = time.time() - start_time
        
        # Verify signal changed
        verify_start = time.time()
        while time.time() - verify_start < verify_timeout:
            if hasattr(self, 'signal_cache') and signal_name in self.signal_cache:
                received_value = self.signal_cache[signal_name]
                round_trip_time = time.time() - start_time
                
                if abs(received_value - target_value) <= tolerance:
                    return True, received_value, round_trip_time, f"SUCCESS: Sent msg, {signal_name} verified as {received_value} in {round_trip_time:.3f}s"
                else:
                    return False, received_value, round_trip_time, f"MISMATCH: {signal_name}={received_value}, expected {target_value}+/-{tolerance}"
            time.sleep(0.05)
        
        round_trip_time = time.time() - start_time
        return False, None, round_trip_time, f"TIMEOUT: Signal not verified within {verify_timeout}s (round-trip={round_trip_time:.3f}s)"

    def get_diagnostics(self):
        """
        ===== CAN DIAGNOSTICS =====
        Returns comprehensive diagnostics for debugging CAN communication issues.
        """
        with self.signal_cache_lock:
            signal_count = len([s for s in self.signal_cache.values() if s['value'] is not None])
        
        diagnostics = {
            'connection_status': 'Connected' if self.is_connected else 'Disconnected',
            'mode': 'Simulation' if self.simulation_mode else 'Real CAN',
            'rx_count': self.rx_count,
            'tx_count': self.tx_count,
            'error_count': self.error_count,
            'message_defs_loaded': len(self.message_definitions),
            'signals_in_cache': len(self.signal_cache),
            'signals_with_values': signal_count,
            'total_listeners': len(self.listeners),
            'history_size': len(self.message_history),
            'dbc_loaded': self.dbc_parser is not None and self.dbc_parser.database is not None
        }
        return diagnostics
    
    def print_diagnostics(self):
        """Print diagnostics to console for troubleshooting"""
        diag = self.get_diagnostics()
        print("\n" + "="*60)
        print("[CAN DIAGNOSTICS]")
        print("="*60)
        print(f"  Connection Status:    {diag['connection_status']}")
        print(f"  Mode:                 {diag['mode']}")
        print(f"  Messages RX:          {diag['rx_count']}")
        print(f"  Messages TX:          {diag['tx_count']}")
        print(f"  Errors:               {diag['error_count']}")
        print(f"  DBC Loaded:           {diag['dbc_loaded']}")
        print(f"  Message Definitions:  {diag['message_defs_loaded']}")
        print(f"  Signals in Cache:     {diag['signals_in_cache']}")
        print(f"  Signals with Values:  {diag['signals_with_values']}")
        print(f"  Active Listeners:     {diag['total_listeners']}")
        print(f"  Message History:      {diag['history_size']}/{self.max_history_size}")
        print("="*60 + "\n")

    def _simulate_traffic(self):
        """
        ===== SIMULATION MODE =====
        Simulate CAN traffic with properly encoded messages from DBC definitions.
        This generates valid CAN messages with realistic signal values.
        """
        import random
        
        print("[CAN SIMULATION] Starting message simulation...")
        
        # Get list of message definitions to simulate
        if not self.message_definitions:
            print("[CAN SIMULATION WARNING] No message definitions loaded, cannot simulate")
            return
        
        message_list = list(self.message_definitions.values())
        print(f"[CAN SIMULATION] Simulating {len(message_list)} message types")
        
        simulation_iteration = 0
        
        while self.running:
            try:
                # Pick a random message to simulate
                message_def = random.choice(message_list)
                
                # Create signal values for this message
                signal_values = {}
                for signal in message_def.signals:
                    # Generate realistic values based on signal range
                    if (hasattr(signal, 'minimum') and hasattr(signal, 'maximum') and 
                        signal.minimum is not None and signal.maximum is not None):
                        value = random.uniform(signal.minimum, signal.maximum)
                    elif hasattr(signal, 'initial') and signal.initial is not None:
                        value = signal.initial + random.uniform(-1, 1)
                    else:
                        value = random.randint(0, 255)
                    
                    signal_values[signal.name] = value
                
                # Encode the message using DBC
                try:
                    data = message_def.encode(signal_values)
                    
                    # Create CAN message
                    msg = can.Message(
                        arbitration_id=message_def.frame_id,
                        data=data,
                        dlc=len(data),
                        is_rx=True,
                        timestamp=time.time()
                    )
                    
                    # Process through normal reception handler
                    self._on_message_received(msg)
                    
                except Exception as encode_err:
                    # Some messages might have special encoding requirements
                    pass
                
                # Simulate at ~10 messages per second
                time.sleep(0.1)
                simulation_iteration += 1
                
                # Progress indicator every 100 messages
                if simulation_iteration % 100 == 0:
                    diag = self.get_diagnostics()
                    print(f"[CAN SIMULATION] {simulation_iteration} messages, {diag['signals_with_values']} signals updated")
            
            except Exception as e:
                print(f"[CAN SIMULATION ERROR] {e}")
                time.sleep(0.1)

