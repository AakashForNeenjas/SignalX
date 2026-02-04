"""CAN cyclic message management module.

Handles periodic transmission of CAN messages.
"""

import logging
import os
import sys
import threading
import time
from typing import Callable, Dict, Optional, Tuple, List

import can

logger = logging.getLogger(__name__)


class CyclicMessageManager:
    """Manages cyclic (periodic) CAN message transmission."""

    def __init__(
        self,
        bus: Optional[can.BusABC],
        simulation_mode: bool,
        dbc_parser,
        log_callback: Callable,
        message_callback: Callable,
        signal_cache_lock: threading.RLock,
        signal_cache: Dict,
        last_sent_signals: Dict,
        build_full_values_func: Callable,
        log_message_func: Optional[Callable] = None,
        logging_enabled: bool = False
    ):
        """Initialize cyclic message manager.

        Args:
            bus: CAN bus instance
            simulation_mode: Whether in simulation mode
            dbc_parser: DBC parser instance
            log_callback: Callback for logging messages
            message_callback: Callback to process received messages
            signal_cache_lock: Lock for thread-safe signal cache access
            signal_cache: Signal cache dictionary
            last_sent_signals: Dictionary tracking last sent signal values
            build_full_values_func: Function to build complete signal values
            log_message_func: Optional function to log CAN messages to file
            logging_enabled: Whether CAN logging is enabled
        """
        self.bus = bus
        self.simulation_mode = simulation_mode
        self.dbc_parser = dbc_parser
        self.log_callback = log_callback
        self.message_callback = message_callback
        self.signal_cache_lock = signal_cache_lock
        self.signal_cache = signal_cache
        self.last_sent_signals = last_sent_signals
        self.build_full_values_func = build_full_values_func
        self.log_message_func = log_message_func
        self.logging_enabled = logging_enabled

        # Cyclic message state
        self.cyclic_tasks: Dict[int, can.CyclicSendTaskABC] = {}
        self.cyclic_periods: Dict[int, float] = {}
        self.metrics_threads: Dict[int, threading.Event] = {}

    def start_cyclic_message(
        self,
        arbitration_id: int,
        data: bytes,
        cycle_time: float,
        is_extended_id: bool = False
    ) -> None:
        """Start sending a cyclic CAN message.

        Args:
            arbitration_id: CAN message ID
            data: Message data bytes
            cycle_time: Cycle time in seconds
            is_extended_id: Whether the message uses extended ID
        """
        if self.simulation_mode:
            self.log_callback(10, f"SIMULATION CAN CYCLIC START: ID={hex(arbitration_id)}")
            return

        if not self.bus:
            raise RuntimeError("CAN bus not connected. Please connect first.")

        # Stop existing cyclic task if running
        if arbitration_id in self.cyclic_tasks:
            self.stop_cyclic_message(arbitration_id)

        msg = can.Message(
            arbitration_id=arbitration_id,
            data=data,
            is_extended_id=is_extended_id
        )
        msg.timestamp = time.time()

        # Log the first tick if logging enabled
        if self.logging_enabled and self.log_message_func:
            try:
                self.log_message_func(msg)
            except Exception as e:
                self.log_callback(30, f"Failed to log initial cyclic message: {e}")

        # Feed metrics/listeners for TX visibility
        try:
            self.message_callback(msg)
        except Exception as e:
            self.log_callback(30, f"Failed to notify listeners for cyclic start: {e}")

        # Start periodic transmission
        task = self.bus.send_periodic(msg, cycle_time)
        self.cyclic_tasks[arbitration_id] = task
        self.cyclic_periods[arbitration_id] = cycle_time

        # Start metrics tick thread
        stop_event = threading.Event()
        self.metrics_threads[arbitration_id] = stop_event

        def _tick_metrics():
            m = can.Message(
                arbitration_id=arbitration_id,
                data=data,
                is_extended_id=is_extended_id
            )
            while not stop_event.wait(cycle_time):
                m.timestamp = time.time()
                try:
                    self.message_callback(m)
                except Exception as e:
                    self.log_callback(30, f"Metrics tick failed for ID=0x{arbitration_id:X}: {e}")

        t = threading.Thread(
            target=_tick_metrics,
            daemon=True,
            name=f"CAN_Metrics_{arbitration_id:X}"
        )
        t.start()

    def stop_cyclic_message(self, arbitration_id: int) -> None:
        """Stop a cyclic CAN message.

        Args:
            arbitration_id: CAN message ID to stop
        """
        if self.simulation_mode:
            self.log_callback(10, f"SIMULATION CAN CYCLIC STOP: ID={hex(arbitration_id)}")
            return

        if arbitration_id in self.cyclic_tasks:
            self.cyclic_tasks[arbitration_id].stop()
            del self.cyclic_tasks[arbitration_id]

        if arbitration_id in self.cyclic_periods:
            del self.cyclic_periods[arbitration_id]

        if arbitration_id in self.metrics_threads:
            self.metrics_threads[arbitration_id].set()
            del self.metrics_threads[arbitration_id]

    def start_cyclic_message_by_name(
        self,
        message_name: str,
        signals_dict: Optional[Dict[str, float]],
        cycle_time_ms: float
    ) -> bool:
        """Start a cyclic CAN message using DBC encoding.

        Args:
            message_name: Name of the message in the DBC file
            signals_dict: Dictionary of signal names and values
            cycle_time_ms: Cycle time in milliseconds

        Returns:
            True if successful, False otherwise
        """
        if not self.dbc_parser or not self.dbc_parser.database:
            self.log_callback(30, f"No DBC loaded, cannot encode message '{message_name}'")
            return False

        try:
            # Get message from DBC
            message = self.dbc_parser.database.get_message_by_name(message_name)

            # Encode signals into CAN data
            full_values = self.build_full_values_func(message, signals_dict or {})
            data = message.encode(full_values)

            # Update cache and last sent signals
            now = time.time()
            self.last_sent_signals[message.name] = dict(full_values)
            with self.signal_cache_lock:
                for sig_name, val in full_values.items():
                    self.signal_cache[sig_name] = {
                        "value": val,
                        "timestamp": now,
                        "message": message.name
                    }

            # Start cyclic transmission
            self.start_cyclic_message(
                message.frame_id,
                data,
                cycle_time_ms / 1000.0,
                is_extended_id=message.is_extended_frame
            )

            self.log_callback(20, f"Started cyclic message: {message_name} (ID: 0x{message.frame_id:03X})")
            return True

        except KeyError:
            self.log_callback(40, f"Message '{message_name}' not found in DBC file")
            return False
        except Exception as e:
            self.log_callback(40, f"Error encoding message '{message_name}': {e}")
            return False

    def start_all_cyclic_messages(self) -> Tuple[List[str], List[str]]:
        """Start all cyclic messages defined in can_messages.py.

        Returns:
            Tuple of (started_messages, failed_messages) lists
        """
        # Add CAN Configuration to path
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(script_dir))
        config_path = os.path.join(project_root, "CAN Configuration")

        if config_path not in sys.path:
            sys.path.insert(0, config_path)

        try:
            import can_messages
            CYCLIC_CAN_MESSAGES = can_messages.CYCLIC_CAN_MESSAGES
        except ImportError as e:
            self.log_callback(40, f"Error importing can_messages: {e}")
            return [], []

        started_messages = []
        failed_messages = []

        for msg_name, msg_config in CYCLIC_CAN_MESSAGES.items():
            signals = msg_config['signals']
            cycle_time = msg_config['cycle_time']

            success = self.start_cyclic_message_by_name(msg_name, signals, cycle_time)
            if success:
                started_messages.append(msg_name)
            else:
                failed_messages.append(msg_name)

        self.log_callback(20, f"Started {len(started_messages)} cyclic messages, {len(failed_messages)} failed")
        return started_messages, failed_messages

    def stop_all_cyclic_messages(self) -> bool:
        """Stop all cyclic messages defined in can_messages.py.

        Returns:
            True if successful, False otherwise
        """
        # Add CAN Configuration to path
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(script_dir))
        config_path = os.path.join(project_root, "CAN Configuration")

        if config_path not in sys.path:
            sys.path.insert(0, config_path)

        try:
            import can_messages
            CYCLIC_CAN_MESSAGES = can_messages.CYCLIC_CAN_MESSAGES
        except ImportError as e:
            self.log_callback(40, f"Error importing can_messages: {e}")
            return False

        if not self.dbc_parser or not self.dbc_parser.database:
            self.log_callback(30, "No DBC loaded, cannot stop cyclic messages")
            return False

        stopped_count = 0
        for msg_name in CYCLIC_CAN_MESSAGES.keys():
            try:
                message = self.dbc_parser.database.get_message_by_name(msg_name)
                self.stop_cyclic_message(message.frame_id)
                stopped_count += 1
            except KeyError:
                self.log_callback(30, f"Message '{msg_name}' not found in DBC")
            except Exception as e:
                self.log_callback(40, f"Error stopping cyclic message '{msg_name}': {e}")

        self.log_callback(20, f"Stopped {stopped_count} cyclic messages")
        return True

    def stop_all(self) -> None:
        """Stop all active cyclic messages."""
        for arb_id in list(self.cyclic_tasks.keys()):
            self.stop_cyclic_message(arb_id)
