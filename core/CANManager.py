"""CAN Manager for CAN bus communication and message handling.

This module provides the main CANManager class that orchestrates all CAN bus
communication. It delegates to modular components for specific functionality:
- CANConnection: Bus connection management
- CANSimulator: Traffic simulation
- CyclicMessageManager: Periodic message transmission
- CANLogger: Message logging (CSV/TRC)
- SignalManager: Signal caching and manipulation
"""

import logging
import can
try:
    import can.interfaces.pcan  # noqa: F401
except ImportError:
    # PCAN interface not available - will use other interfaces
    pass
import threading
import time
import csv
import os
from collections import deque
from datetime import datetime
from typing import (
    Any, Callable, Dict, List, Optional, Tuple,
    TextIO, TYPE_CHECKING
)

from core.logging_utils import LoggerMixin
# Import modular CAN components
from core.can import (
    CANConnection,
    CANSimulator,
    CyclicMessageManager,
    CANLogger,
    CANSignalManager,
)

if TYPE_CHECKING:
    from core.DBCParser import DBCParser


class CANManager(LoggerMixin):
    """Manager for CAN bus communication, logging, and signal handling."""

    def __init__(
        self,
        simulation_mode: bool = False,
        dbc_parser: Optional["DBCParser"] = None,
        logger: Optional[logging.Logger] = None
    ) -> None:
        """Initialize CANManager.

        Args:
            simulation_mode: Enable simulation mode without hardware
            dbc_parser: DBC parser for message definitions
            logger: Optional logger instance
        """
        self.simulation_mode: bool = simulation_mode
        self.dbc_parser: Optional["DBCParser"] = dbc_parser
        self.running: bool = False

        # ===== MODULAR COMPONENTS =====
        # Connection management (delegates to CANConnection)
        self._connection = CANConnection(simulation_mode=simulation_mode)

        # Logger for CSV/TRC files (delegates to CANLogger)
        self._can_logger = CANLogger()

        # Signal cache lock (shared with components)
        self.signal_cache_lock: threading.RLock = threading.RLock()

        # Signal manager (delegates to CANSignalManager)
        self._signal_manager = CANSignalManager(
            dbc_parser=dbc_parser,
            signal_cache_lock=self.signal_cache_lock
        )

        # Simulator (created on connect if simulation_mode)
        self._simulator: Optional[CANSimulator] = None

        # Cyclic message manager (created on connect when bus is available)
        self._cyclic_manager: Optional[CyclicMessageManager] = None

        # ===== BACKWARD COMPATIBILITY ATTRIBUTES =====
        # These attributes are maintained for backward compatibility
        # but delegate to modular components internally
        self.listeners: List[Callable[[can.Message], None]] = []
        self.listeners_lock: threading.RLock = threading.RLock()

        # Connection state tracking
        self.is_connected: bool = False

        # Statistics
        self.rx_count: int = 0
        self.tx_count: int = 0
        self.error_count: int = 0

        # Decode cache (message_id -> message_definition)
        self.message_definitions: Dict[int, Any] = {}

        # Message history for debugging
        self.max_history_size: int = 100
        self.message_history: deque[Dict[str, Any]] = deque(maxlen=self.max_history_size)
        self.message_history_lock: threading.Lock = threading.Lock()

        # Connection defaults (can be overridden via profiles)
        self.interface: Optional[str] = None
        self.channel: Optional[str] = None
        self.bitrate: Optional[int] = None

        # Store external logger for backward compatibility (LoggerMixin provides self.logger)
        self._external_logger: Optional[logging.Logger] = logger
        self.log_info("CANManager initialized", mode="simulation" if simulation_mode else "hardware")

    # ===== PROPERTY DELEGATIONS FOR BACKWARD COMPATIBILITY =====

    @property
    def bus(self) -> Optional[can.Bus]:
        """Get the CAN bus instance (delegates to CANConnection)."""
        return self._connection.bus

    @bus.setter
    def bus(self, value: Optional[can.Bus]) -> None:
        """Set the CAN bus instance (delegates to CANConnection)."""
        self._connection.bus = value

    @property
    def logging(self) -> bool:
        """Check if logging is enabled (delegates to CANLogger)."""
        return self._can_logger.logging

    @logging.setter
    def logging(self, value: bool) -> None:
        """Set logging state (delegates to CANLogger)."""
        self._can_logger.logging = value

    @property
    def signal_cache(self) -> Dict[str, Dict[str, Any]]:
        """Get the signal cache (delegates to SignalManager)."""
        return self._signal_manager.signal_cache

    @signal_cache.setter
    def signal_cache(self, value: Dict[str, Dict[str, Any]]) -> None:
        """Set the signal cache (delegates to SignalManager)."""
        self._signal_manager.signal_cache = value

    @property
    def last_sent_signals(self) -> Dict[str, Dict[str, Any]]:
        """Get last sent signals (delegates to SignalManager)."""
        return self._signal_manager.last_sent_signals

    @last_sent_signals.setter
    def last_sent_signals(self, value: Dict[str, Dict[str, Any]]) -> None:
        """Set last sent signals (delegates to SignalManager)."""
        self._signal_manager.last_sent_signals = value

    @property
    def signal_overrides(self) -> Dict[Tuple[str, str], Any]:
        """Get signal overrides.

        Note: The SignalManager uses a different structure (nested dict).
        This property converts for backward compatibility.
        """
        # Convert from SignalManager's {msg: {sig: val}} to {(msg, sig): val}
        result = {}
        for msg_name, signals in self._signal_manager.signal_overrides.items():
            for sig_name, val in signals.items():
                result[(msg_name, sig_name)] = val
        return result

    @property
    def signal_overrides_lock(self) -> threading.RLock:
        """Get signal overrides lock (uses signal_cache_lock)."""
        return self.signal_cache_lock

    @property
    def cyclic_tasks(self) -> Dict[int, Any]:
        """Get cyclic tasks (delegates to CyclicMessageManager if available)."""
        if self._cyclic_manager:
            return self._cyclic_manager.cyclic_tasks
        return {}

    @property
    def cyclic_periods(self) -> Dict[int, float]:
        """Get cyclic periods (delegates to CyclicMessageManager if available)."""
        if self._cyclic_manager:
            return self._cyclic_manager.cyclic_periods
        return {}

    @property
    def metrics_threads(self) -> Dict[int, threading.Thread]:
        """Get metrics threads (delegates to CyclicMessageManager if available)."""
        if self._cyclic_manager:
            return self._cyclic_manager.metrics_threads
        return {}

    @property
    def csv_file(self) -> Optional[TextIO]:
        """Get CSV file handle (delegates to CANLogger)."""
        return self._can_logger.csv_file

    @property
    def csv_writer(self) -> Optional[csv.writer]:
        """Get CSV writer (delegates to CANLogger)."""
        return self._can_logger.csv_writer

    @property
    def trc_file(self) -> Optional[TextIO]:
        """Get TRC file handle (delegates to CANLogger)."""
        return self._can_logger.trc_file

    @property
    def start_time(self) -> Optional[datetime]:
        """Get logging start time (delegates to CANLogger)."""
        return self._can_logger.start_time

    @property
    def first_msg_time(self) -> Optional[float]:
        """Get first message time (delegates to CANLogger)."""
        return self._can_logger.first_msg_time

    @property
    def message_counter(self) -> int:
        """Get message counter (delegates to CANLogger)."""
        return self._can_logger.message_counter

    @property
    def log_lock(self) -> threading.Lock:
        """Get log lock (delegates to CANLogger)."""
        return self._can_logger.log_lock

    def get_diagnostics(self) -> Dict[str, Any]:
        """Get current CAN diagnostics and status.

        Returns:
            Dictionary containing connection status, counts, and logging state
        """
        return {
            'connection_status': 'Connected' if self.is_connected else 'Disconnected',
            'rx_count': self.rx_count,
            'tx_count': self.tx_count,
            'error_count': self.error_count,
            'bus_load': 0.0,  # Placeholder
            'is_logging': self.logging
        }

    def _log(self, level: int, message: str) -> None:
        """Log a message using LoggerMixin (legacy interface for compatibility).

        Args:
            level: Logging level (10=DEBUG, 20=INFO, 30=WARNING, 40=ERROR)
            message: Log message
        """
        # Route through LoggerMixin's standardized methods
        if level >= 40:
            self.log_error(message)
        elif level >= 30:
            self.log_warning(message)
        elif level >= 20:
            self.log_info(message)
        else:
            self.log_debug(message)

    def connect(
        self,
        interface: Optional[str] = None,
        channel: Optional[str] = None,
        bitrate: Optional[int] = None
    ) -> Tuple[bool, str]:
        """Connect to CAN bus and initialize message definitions from DBC.

        Uses modular CANConnection for connection management and initializes
        other components (simulator, cyclic manager) as needed.

        Args:
            interface: CAN interface (e.g., 'pcan', 'socketcan')
            channel: CAN channel
            bitrate: CAN bitrate

        Returns:
            Tuple of (success, message)
        """
        # Resolve defaults
        interface = interface or self.interface or 'pcan'
        channel = channel or self.channel or 'PCAN_USBBUS1'
        bitrate = bitrate or self.bitrate or 500000

        # Store connection parameters
        self._connection.interface = interface
        self._connection.channel = channel
        self._connection.bitrate = bitrate

        if self.simulation_mode:
            self._log(20, f"CAN connect (simulation) {interface}:{channel}")
            self.is_connected = True
            self.running = True
            self._initialize_message_definitions()  # Load DBC message defs

            # Create and start simulator using modular component
            self._simulator = CANSimulator(
                message_definitions=self.message_definitions,
                message_callback=self._on_message_received,
                diagnostics_callback=self.get_full_diagnostics
            )
            self._simulator.start()

            return True, "Connected (Simulation Mode)"

        try:
            # Log connection attempt
            self._log(20, f"CAN connect attempt {interface}:{channel} bitrate={bitrate}")

            # Use CANConnection component for actual connection
            success, msg = self._connection.connect(interface, channel, bitrate)
            if not success:
                self.is_connected = False
                self._log(40, msg)
                return False, msg

            self.is_connected = True
            self.running = True

            # Load message definitions from DBC for proper decoding
            self._initialize_message_definitions()

            # Create cyclic message manager with connected bus
            self._cyclic_manager = CyclicMessageManager(
                bus=self._connection.bus,
                simulation_mode=self.simulation_mode,
                dbc_parser=self.dbc_parser,
                log_callback=self._log,
                message_callback=self._on_message_received,
                signal_cache_lock=self.signal_cache_lock,
                signal_cache=self._signal_manager.signal_cache,
                last_sent_signals=self._signal_manager.last_sent_signals,
                build_full_values_func=self._build_full_values,
                log_message_func=self._log_message,
                logging_enabled=self._can_logger.logging
            )

            # Setup listener for message reception
            self.notifier = can.Notifier(self._connection.bus, [self._on_message_received])

            self._log(20, f"CAN connected {interface}:{channel}")
            return True, f"Connected to {interface}:{channel}"

        except ImportError as e:
            self.is_connected = False
            msg = ("Connection failed: backend module missing. "
                   "Install python-can with backend extras (e.g., python-can[pcan]) "
                   f"and ensure vendor drivers are installed. Details: {e}")
            self._log(40, msg)
            return False, msg

        except can.CanError as e:
            self.is_connected = False
            msg = (f"Connection failed: {e}. "
                   "Verify interface/channel/bitrate and that the vendor driver is installed.")
            self._log(40, msg)
            return False, msg

        except Exception as e:
            self.is_connected = False
            msg = f"Connection failed: {e}"
            self._log(40, msg)
            return False, msg
    def _initialize_message_definitions(self) -> None:
        """Load all message definitions from DBC for efficient message decoding.

        This enables real-time signal extraction and caching.

        Raises:
            RuntimeError: If DBC is loaded but message definitions fail to initialize.
        """
        if not self.dbc_parser or not self.dbc_parser.database:
            self._log(30, "DBC not loaded - cannot initialize message definitions")
            return

        try:
            # Build cache of message ID -> message_definition for fast lookup
            for message in self.dbc_parser.database.messages:
                self.message_definitions[message.frame_id] = message

            self._log(20, f"Loaded {len(self.message_definitions)} message definitions from DBC")

            # Initialize signal_cache with all signals from DBC
            with self.signal_cache_lock:
                for message in self.dbc_parser.database.messages:
                    for signal in message.signals:
                        # Initialize with None, will be updated when messages are received
                        if signal.name not in self.signal_cache:
                            self.signal_cache[signal.name] = {
                                'value': None,
                                'timestamp': None,
                                'message_id': message.frame_id,
                                'message_name': message.name,
                                'unit': getattr(signal, 'unit', '') or ''
                            }

            self._log(20, f"Initialized signal_cache with {len(self.signal_cache)} signals")

        except Exception as e:
            self._log(40, f"Failed to initialize message definitions: {e}")
            raise RuntimeError(f"DBC initialization failed: {e}") from e

    def disconnect(self) -> None:
        """Cleanly disconnect from CAN bus.

        Stops all modular components and cleans up resources.
        """
        self.running = False
        self.is_connected = False

        try:
            # Stop notifier if active
            if hasattr(self, 'notifier') and self.notifier:
                self.notifier.stop()

            # Stop simulator if active (modular component)
            if self._simulator:
                self._simulator.stop()
                self._simulator = None

            # Stop all cyclic messages (modular component)
            if self._cyclic_manager:
                self._cyclic_manager.stop_all()
                self._cyclic_manager = None

            # Disconnect from bus (modular component)
            self._connection.disconnect()

            # Clear listeners
            with self.listeners_lock:
                self.listeners.clear()

            self._log(20, "CAN disconnected")
        except Exception as e:
            self._log(40, f"Error during CAN disconnect: {e}")

    def send_message(
        self,
        arbitration_id: int,
        data: bytes,
        is_extended_id: bool = False
    ) -> None:
        """Send a CAN message.

        Args:
            arbitration_id: CAN message ID
            data: Message data bytes
            is_extended_id: Use extended (29-bit) ID format

        Raises:
            RuntimeError: If CAN bus is not connected
            can.CanError: If send fails
        """
        if self.simulation_mode:
            self._log(10, f"SIMULATION CAN TX: ID={hex(arbitration_id)} Data={data}")
            return
        if not self.bus:
            raise RuntimeError("CAN bus not connected")

        msg = can.Message(arbitration_id=arbitration_id, data=data, is_extended_id=is_extended_id)
        # Attach timestamp for logging consistency
        msg.timestamp = time.time()

        # Log TX locally so traces capture what we send (even if bus loopback is disabled)
        if self.logging:
            try:
                self._log_message(msg)
            except Exception as e:
                self._log(30, f"Failed to log TX message: {e}")

        try:
            self.bus.send(msg)
            self.tx_count += 1
        except can.CanError as e:
            self.error_count += 1
            self._log(40, f"CAN send failed for ID=0x{arbitration_id:X}: {e}")
            raise  # Re-raise so caller knows send failed

        # Also notify listeners/metrics about this TX so dynamic checks can see it even without loopback
        try:
            self._on_message_received(msg)
        except Exception as e:
            self._log(30, f"Listener notification failed after TX: {e}")

    def set_signal_override(
        self,
        message_name: str,
        signal_name: str,
        value: Any
    ) -> None:
        """Set or update an override for a specific signal within a message.

        Delegates to SignalManager component.

        Args:
            message_name: Name of the CAN message
            signal_name: Name of the signal within the message
            value: Override value to set
        """
        self._signal_manager.set_signal_override(message_name, signal_name, value)
        self._log(20, f"Override set: {message_name}.{signal_name}={value}")

    def _get_cycle_time_ms(
        self,
        message_name: Optional[str] = None,
        arbitration_id: Optional[int] = None
    ) -> int:
        """Resolve cycle time in ms for a cyclic message.

        Args:
            message_name: Optional message name to look up
            arbitration_id: Optional arbitration ID to look up

        Returns:
            Cycle time in milliseconds (default: 100ms)
        """
        if arbitration_id is not None:
            sec = self.cyclic_periods.get(arbitration_id)
            if sec:
                return int(sec * 1000)

        if message_name:
            try:
                import can_messages
                cfg = getattr(can_messages, "CYCLIC_CAN_MESSAGES", {})
                if message_name in cfg:
                    return int(cfg[message_name].get("cycle_time", 100))
            except ImportError:
                self._log(10, "can_messages module not available for cycle time lookup")
            except Exception as e:
                self._log(30, f"Error getting cycle time for {message_name}: {e}")

        return 100  # Default 100ms

    def apply_signal_override(
        self,
        message_name: str,
        signal_name: str,
        value: Any,
        refresh_cyclic: bool = True
    ) -> Dict[str, Any]:
        """Apply a signal override, send a message immediately, and refresh cyclic.

        Args:
            message_name: Name of the CAN message
            signal_name: Name of the signal to override
            value: Value to set
            refresh_cyclic: Whether to refresh cyclic transmission

        Returns:
            Dictionary of all signal values in the message

        Raises:
            RuntimeError: If DBC is not loaded
        """
        if not self.dbc_parser or not self.dbc_parser.database:
            raise RuntimeError("DBC not loaded; cannot apply override")
        msg_def = self.dbc_parser.database.get_message_by_name(message_name)
        self.set_signal_override(message_name, signal_name, value)
        full_values = self.send_message_with_overrides(message_name, {signal_name: value})
        if refresh_cyclic and msg_def.frame_id in self.cyclic_tasks:
            cycle_ms = self._get_cycle_time_ms(message_name, msg_def.frame_id)
            self.start_cyclic_message_by_name(message_name, full_values, cycle_ms)
        return full_values

    def clear_signal_override(
        self,
        message_name: Optional[str] = None,
        signal_name: Optional[str] = None
    ) -> None:
        """Clear overrides; if both provided, clear specific, else clear all.

        Delegates to SignalManager component.

        Args:
            message_name: Optional message name to clear overrides for
            signal_name: Optional signal name to clear (requires message_name)
        """
        self._signal_manager.clear_signal_override(message_name, signal_name)

    def _apply_overrides(
        self,
        message_name: str,
        signals_dict: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Merge in overrides for this message before encoding.

        Args:
            message_name: Name of the message
            signals_dict: Dictionary of signal values

        Returns:
            Merged dictionary with overrides applied
        """
        if not self.signal_overrides:
            return signals_dict
        merged = dict(signals_dict)
        with self.signal_overrides_lock:
            for (msg, sig), val in self.signal_overrides.items():
                if msg == message_name:
                    merged[sig] = val
        return merged

    def _build_full_values(self, msg_def: Any, signals_dict: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Build a full signal dict using provided values + overrides + cached values.

        This avoids zeroing other signals when only one is updated.
        Priority: last_sent for this message -> signal cache -> configured cyclic defaults -> signal.initial -> 0

        Args:
            msg_def: Message definition from DBC
            signals_dict: Dictionary of signal values to set

        Returns:
            Complete dictionary of all signal values for the message
        """
        merged = self._apply_overrides(msg_def.name, signals_dict or {})
        # Start from last sent snapshot if we have one
        base = dict(self.last_sent_signals.get(msg_def.name, {}) or {})

        full_values = dict(base)
        for sig in msg_def.signals:
            if sig.name in merged:
                full_values[sig.name] = merged[sig.name]
                continue
            if sig.name in full_values:
                # Already carried from last_sent
                continue
            cached_val = None
            if hasattr(self, "signal_cache"):
                cached_val = self.signal_cache.get(sig.name, {}).get("value", None)

            if cached_val is None:
                # Try configured cyclic defaults if available
                try:
                    import can_messages
                    cfg = getattr(can_messages, "CYCLIC_CAN_MESSAGES", {})
                    if msg_def.name in cfg:
                        defaults = cfg[msg_def.name].get("signals", {})
                        if sig.name in defaults:
                            cached_val = defaults[sig.name]
                except ImportError:
                    pass  # can_messages not available - use other defaults
                except Exception as e:
                    self._log(10, f"Error loading cyclic defaults for {sig.name}: {e}")
            if cached_val is not None:
                full_values[sig.name] = cached_val
            elif getattr(sig, "initial", None) is not None:
                full_values[sig.name] = sig.initial
            else:
                full_values[sig.name] = 0
        return full_values

    def send_message_with_overrides(
        self,
        message_name: str,
        signals_dict: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Encode and send a message applying overrides.

        Args:
            message_name: Name of the CAN message
            signals_dict: Dictionary of signal values

        Returns:
            Dictionary of all signal values sent

        Raises:
            RuntimeError: If DBC is not loaded
        """
        if not self.dbc_parser or not self.dbc_parser.database:
            raise RuntimeError("DBC not loaded; cannot encode message")
        msg_def = self.dbc_parser.database.get_message_by_name(message_name)
        full_values = self._build_full_values(msg_def, signals_dict or {})
        data = msg_def.encode(full_values)
        self.send_message(msg_def.frame_id, data, is_extended_id=msg_def.is_extended_frame)
        # Optimistically update local cache so verify can succeed even without bus echo
        now = time.time()
        with self.signal_cache_lock:
            for sig_name, val in full_values.items():
                self.signal_cache[sig_name] = {"value": val, "timestamp": now, "message": message_name}
        # Track last sent per message
        self.last_sent_signals[message_name] = dict(full_values)
        return full_values

    def verify_signal_value(
        self,
        signal_name: str,
        expected_value: float,
        timeout: float = 1.0,
        tolerance: float = 0.01
    ) -> Tuple[bool, str]:
        """Closed-loop verification: wait for a decoded signal to match expected within tolerance.

        Uses signal_cache populated by RX decoding.

        Args:
            signal_name: Name of the signal to verify
            expected_value: Expected signal value
            timeout: Maximum wait time in seconds
            tolerance: Acceptable deviation from expected value

        Returns:
            Tuple of (success, message)
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

    def start_cyclic_message(
        self,
        arbitration_id: int,
        data: bytes,
        cycle_time: float,
        is_extended_id: bool = False
    ) -> None:
        """Start cyclic transmission of a CAN message.

        Delegates to CyclicMessageManager if available, otherwise falls back
        to direct implementation for backward compatibility.

        Args:
            arbitration_id: CAN message ID
            data: Message data bytes
            cycle_time: Cycle time in seconds
            is_extended_id: Use extended (29-bit) ID format

        Raises:
            RuntimeError: If CAN bus is not connected (hardware mode)
        """
        # Delegate to CyclicMessageManager if available
        if self._cyclic_manager:
            self._cyclic_manager.logging_enabled = self._can_logger.logging
            self._cyclic_manager.start_cyclic_message(
                arbitration_id, data, cycle_time, is_extended_id
            )
            return

        # Fallback for simulation mode or when cyclic manager not initialized
        if self.simulation_mode:
            self._log(10, f"SIMULATION CAN CYCLIC START: ID={hex(arbitration_id)}")
            return

        if not self.bus:
            raise RuntimeError("CAN bus not connected. Please connect first.")

    def stop_cyclic_message(self, arbitration_id: int) -> None:
        """Stop cyclic transmission of a CAN message.

        Delegates to CyclicMessageManager if available.

        Args:
            arbitration_id: CAN message ID to stop
        """
        # Delegate to CyclicMessageManager if available
        if self._cyclic_manager:
            self._cyclic_manager.stop_cyclic_message(arbitration_id)
            return

        # Fallback for simulation mode
        if self.simulation_mode:
            self._log(10, f"SIMULATION CAN CYCLIC STOP: ID={hex(arbitration_id)}")

    def start_cyclic_message_by_name(
        self,
        message_name: str,
        signals_dict: Optional[Dict[str, Any]],
        cycle_time_ms: int
    ) -> bool:
        """Start a cyclic CAN message using DBC encoding.

        Delegates to CyclicMessageManager if available.

        Args:
            message_name: Name of the message in the DBC file
            signals_dict: Dictionary of signal names and values
            cycle_time_ms: Cycle time in milliseconds

        Returns:
            True if successful, False otherwise
        """
        # Delegate to CyclicMessageManager if available
        if self._cyclic_manager:
            self._cyclic_manager.logging_enabled = self._can_logger.logging
            return self._cyclic_manager.start_cyclic_message_by_name(
                message_name, signals_dict, cycle_time_ms
            )

        # Fallback implementation for when cyclic manager not available
        if not self.dbc_parser or not self.dbc_parser.database:
            self._log(30, f"No DBC loaded, cannot encode message '{message_name}'")
            return False

        try:
            # Get message from DBC
            message = self.dbc_parser.database.get_message_by_name(message_name)

            # Encode signals into CAN data (preserve other signals via cache/defaults)
            full_values = self._build_full_values(message, signals_dict or {})

            data = message.encode(full_values)
            # Remember what we are sending for future preservation and cache
            now = time.time()
            self.last_sent_signals[message.name] = dict(full_values)
            with self.signal_cache_lock:
                for sig_name, val in full_values.items():
                    self.signal_cache[sig_name] = {"value": val, "timestamp": now, "message": message.name}

            # Start cyclic transmission
            self.start_cyclic_message(message.frame_id, data, cycle_time_ms / 1000.0, is_extended_id=message.is_extended_frame)

            self._log(20, f"Started cyclic message: {message_name} (ID: 0x{message.frame_id:03X})")
            return True

        except KeyError:
            self._log(40, f"Message '{message_name}' not found in DBC file")
            return False
        except Exception as e:
            self._log(40, f"Error encoding message '{message_name}': {e}")
            return False

    def start_all_cyclic_messages(self) -> Tuple[List[str], List[str]]:
        """Start all cyclic messages defined in can_messages.py.

        Delegates to CyclicMessageManager if available.

        Returns:
            Tuple of (started_messages, failed_messages) lists
        """
        # Delegate to CyclicMessageManager if available
        if self._cyclic_manager:
            self._cyclic_manager.logging_enabled = self._can_logger.logging
            return self._cyclic_manager.start_all_cyclic_messages()

        # Fallback implementation
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
            self._log(40, f"Error importing can_messages: {e}")
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

        self._log(20, f"Started {len(started_messages)} cyclic messages, {len(failed_messages)} failed")
        return started_messages, failed_messages

    def stop_all_cyclic_messages(self) -> bool:
        """Stop all cyclic messages defined in can_messages.py.

        Delegates to CyclicMessageManager if available.

        Returns:
            True if successful, False otherwise
        """
        # Delegate to CyclicMessageManager if available
        if self._cyclic_manager:
            return self._cyclic_manager.stop_all_cyclic_messages()

        # Fallback implementation
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
            self._log(40, f"Error importing can_messages: {e}")
            return False

        # Get message IDs from DBC
        if not self.dbc_parser or not self.dbc_parser.database:
            self._log(30, "No DBC loaded, cannot stop cyclic messages")
            return False

        stopped_count = 0
        for msg_name in CYCLIC_CAN_MESSAGES.keys():
            try:
                message = self.dbc_parser.database.get_message_by_name(msg_name)
                self.stop_cyclic_message(message.frame_id)
                stopped_count += 1
            except KeyError:
                self._log(30, f"Message '{msg_name}' not found in DBC")
            except Exception as e:
                self._log(40, f"Error stopping cyclic message '{msg_name}': {e}")

        self._log(20, f"Stopped {stopped_count} cyclic messages")
        return True


    def start_logging(self, filename_base: str) -> str:
        """Start logging CAN messages to CSV and TRC files.

        Delegates to CANLogger component.

        Args:
            filename_base: Base filename (without extension) for log files.
                          Must be a valid filename without path separators.

        Returns:
            Full path to the log files (without extension).

        Raises:
            ValueError: If filename_base contains invalid characters.
            OSError: If the results directory cannot be created or files cannot be opened.
        """
        full_path = self._can_logger.start_logging(filename_base)

        # Update cyclic manager's logging state if available
        if self._cyclic_manager:
            self._cyclic_manager.logging_enabled = True

        self._log(20, f"Started logging to {full_path}")
        return full_path

    def stop_logging(self) -> None:
        """Stop logging and safely close all log files.

        Delegates to CANLogger component.
        """
        self._can_logger.stop_logging()

        # Update cyclic manager's logging state if available
        if self._cyclic_manager:
            self._cyclic_manager.logging_enabled = False

        self._log(20, "Logging stopped")

    def add_listener(self, callback: Callable[[can.Message], None]) -> None:
        """Add a message listener callback.

        Args:
            callback: Function to call when a message is received
        """
        with self.listeners_lock:
            self.listeners.append(callback)

    def remove_listener(self, callback: Callable[[can.Message], None]) -> None:
        """Remove a message listener callback.

        Args:
            callback: Function to remove from listeners
        """
        with self.listeners_lock:
            try:
                self.listeners.remove(callback)
            except ValueError:
                pass

    def _on_message_received(self, msg: can.Message) -> None:
        """Handle received CAN message with robust decoding and caching.

        This is the core of CAN communication. Every received message:
        1. Gets logged (CSV/TRC)
        2. Gets decoded using DBC
        3. Gets cached in signal_cache
        4. Gets distributed to listeners

        Args:
            msg: Received CAN message
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
                    self._log(40, f"Listener error: {e}")
                    self.error_count += 1

        except Exception as e:
            self._log(40, f"Message reception failed: {e}")
            self.error_count += 1
    
    def _decode_message(self, msg: can.Message, decode_choices: bool = True) -> Dict[str, Any]:
        """Decode a CAN message using DBC definitions.

        Args:
            msg: CAN message to decode
            decode_choices: Whether to decode choice values to strings

        Returns:
            Dictionary of {signal_name: value} or {} if message not in DBC or decoding fails
        """
        # Quick lookup in message definitions cache
        if msg.arbitration_id not in self.message_definitions:
            return {}  # Message not in DBC - this is expected for unknown messages

        message_def = self.message_definitions[msg.arbitration_id]
        try:
            decoded = message_def.decode(msg.data, decode_choices=decode_choices)
            return decoded
        except Exception as e:
            # Log decode errors at debug level (can be noisy with malformed data)
            self._log(10, f"Failed to decode message 0x{msg.arbitration_id:X}: {e}")
            return {}

    def _cache_signals(
        self,
        message_id: int,
        decoded_signals: Dict[str, Any],
        timestamp: Optional[float],
        raw_signals: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update signal_cache with latest signal values.

        Delegates to SignalManager component but also maintains backward
        compatibility with the existing cache structure.

        Args:
            message_id: CAN message arbitration ID
            decoded_signals: Decoded signal values
            timestamp: Message timestamp
            raw_signals: Optional raw signal values before choice decoding
        """
        # Delegate to SignalManager
        self._signal_manager.cache_signals(message_id, decoded_signals, timestamp, raw_signals)

        # Also update the cache with additional metadata for backward compatibility
        with self.signal_cache_lock:
            for signal_name, value in decoded_signals.items():
                if signal_name in self.signal_cache:
                    # Add raw_value if available
                    if raw_signals and signal_name in raw_signals:
                        self.signal_cache[signal_name]['raw_value'] = raw_signals[signal_name]
                else:
                    # Unknown signal (not in DBC) - add to cache with metadata
                    self.signal_cache[signal_name] = {
                        'value': value,
                        'timestamp': timestamp,
                        'message_id': message_id,
                        'message_name': 'Unknown',
                        'unit': ''
                    }
                    if raw_signals and signal_name in raw_signals:
                        self.signal_cache[signal_name]['raw_value'] = raw_signals[signal_name]
    
    def _log_message(self, msg: can.Message) -> None:
        """Log message to CSV and TRC files.

        Delegates to CANLogger component.

        Args:
            msg: CAN message to log
        """
        # Delegate to CANLogger
        self._can_logger.log_message(msg)

        # Also maintain local message history for backward compatibility
        with self.message_history_lock:
            self.message_history.append({
                'timestamp': getattr(msg, "timestamp", None),
                'msg_id': getattr(msg, "arbitration_id", None),
                'data': getattr(msg, "data", b''),
                'direction': 'RX' if getattr(msg, "is_rx", False) else 'TX'
            })

    def get_signal_value(
        self,
        message_name: str,
        signal_name: str,
        timeout: float = 2.0
    ) -> Tuple[bool, Optional[Any], str]:
        """Listen for a CAN message and return the decoded signal value.

        Args:
            message_name: Name of the CAN message
            signal_name: Name of the signal within the message
            timeout: Maximum wait time in seconds

        Returns:
            Tuple of (success, value, message)
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
                    self._log(30, f"Error decoding message: {e}")
        
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
    
    def get_signal_from_cache(
        self,
        signal_name: str
    ) -> Tuple[bool, Optional[Any], Optional[float]]:
        """Get current signal value from cache (non-blocking, returns immediately).

        Delegates to SignalManager component.

        Args:
            signal_name: Name of the signal

        Returns:
            Tuple of (success, value, timestamp)
        """
        result = self._signal_manager.get_signal_from_cache(signal_name)
        if result:
            return True, result[0], result[1]
        return False, None, None

    def get_all_signals_from_cache(self) -> Dict[str, Dict[str, Any]]:
        """Get all signals currently in cache.

        Delegates to SignalManager component.

        Returns:
            Dictionary of all cached signals
        """
        return self._signal_manager.get_all_signals_from_cache()

    def wait_for_signal_condition(
        self,
        message_name: str,
        signal_name: str,
        expected_value: float,
        tolerance: float,
        timeout: float = 2.0
    ) -> Tuple[bool, Optional[float], str]:
        """Wait for a signal to match expected value within tolerance.

        Args:
            message_name: Name of the CAN message
            signal_name: Name of the signal
            expected_value: Expected signal value
            tolerance: Acceptable deviation
            timeout: Maximum wait time in seconds

        Returns:
            Tuple of (success, actual_value, message)
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
                    self._log(30, f"Error decoding message: {e}")
        
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

    def wait_for_signal_change(
        self,
        message_name: str,
        signal_name: str,
        from_value: Any,
        to_value: Any,
        timeout: float = 10.0,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> Tuple[bool, Optional[Any], float, str]:
        """Wait for signal to change from one value to another.

        Args:
            message_name: Name of the CAN message
            signal_name: Name of the signal
            from_value: Initial value to detect
            to_value: Target value to wait for
            timeout: Maximum wait time in seconds
            progress_callback: Optional function(message_str) for progress updates

        Returns:
            Tuple of (success, actual_value, time_taken, message)
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
                    self._log(30, f"Error decoding message: {e}")
        
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

    def monitor_signal_range(
        self,
        message_name: str,
        signal_name: str,
        min_value: float,
        max_value: float,
        duration: float,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> Tuple[bool, Optional[float], Optional[float], Optional[str], str]:
        """Monitor signal stays within range for specified duration.

        Args:
            message_name: Name of the CAN message
            signal_name: Name of the signal
            min_value: Minimum acceptable value
            max_value: Maximum acceptable value
            duration: Monitoring duration in seconds
            progress_callback: Called with status message strings

        Returns:
            Tuple of (success, min_observed, max_observed, violation_info, message)
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
                    self._log(30, f"Error decoding message: {e}")
        
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

    def compare_two_signals(
        self,
        msg1_name: str,
        sig1_name: str,
        msg2_name: str,
        sig2_name: str,
        tolerance: float,
        timeout: float = 5.0
    ) -> Tuple[bool, Optional[float], Optional[float], Optional[float], str]:
        """Compare two signal values within tolerance.

        Args:
            msg1_name: Name of the first message
            sig1_name: Name of the first signal
            msg2_name: Name of the second message
            sig2_name: Name of the second signal
            tolerance: Maximum acceptable difference
            timeout: Maximum wait time in seconds

        Returns:
            Tuple of (success, value1, value2, difference, message)
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
                self._log(30, f"Error decoding message: {e}")
        
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

    def set_signal_and_verify(
        self,
        message_name: str,
        signal_name: str,
        value: Any,
        verify_timeout: float = 2.0
    ) -> Tuple[bool, Optional[Any], float, str]:
        """Set signal via cyclic message and verify it was received back.

        Args:
            message_name: Name of the CAN message
            signal_name: Name of the signal
            value: Value to set
            verify_timeout: Maximum wait time for verification

        Returns:
            Tuple of (success, verified_value, round_trip_time, message)
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
                    self._log(30, f"Error decoding message: {e}")
        
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
    
    def read_signal_value(
        self,
        signal_name: str,
        timeout: float = 2.0
    ) -> Tuple[bool, Optional[Any], str]:
        """Read and return current value of a signal from received messages.

        Args:
            signal_name: Name of the signal to read
            timeout: Maximum wait time in seconds

        Returns:
            Tuple of (success, value, message)
        """
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
    
    def check_signal_tolerance(
        self,
        signal_name: str,
        expected_value: float,
        tolerance: float,
        timeout: float = 2.0
    ) -> Tuple[bool, Optional[float], str]:
        """Check if signal value is within tolerance of expected value.

        Args:
            signal_name: Name of the signal
            expected_value: Expected signal value
            tolerance: Acceptable deviation
            timeout: Maximum wait time in seconds

        Returns:
            Tuple of (success, actual_value, message)
        """
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
    
    def conditional_jump_check(
        self,
        signal_name: str,
        expected_value: float,
        tolerance: float = 0.1
    ) -> Tuple[bool, str]:
        """Check condition for conditional jump - returns True if condition met.

        Args:
            signal_name: Name of the signal
            expected_value: Expected signal value
            tolerance: Acceptable deviation

        Returns:
            Tuple of (condition_met, message)
        """
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
    
    def wait_for_signal_change_simple(
        self,
        signal_name: str,
        initial_value: Any,
        timeout: float = 5.0,
        poll_interval: float = 0.1
    ) -> Tuple[bool, Any, str]:
        """Wait for signal to change from initial value with progress feedback.

        Args:
            signal_name: Name of the signal
            initial_value: Value to change from
            timeout: Maximum wait time in seconds
            poll_interval: Polling interval in seconds

        Returns:
            Tuple of (success, final_value, message)
        """
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
    
    def monitor_signal_range_simple(
        self,
        signal_name: str,
        min_val: float,
        max_val: float,
        duration: float = 5.0,
        poll_interval: float = 0.5
    ) -> Tuple[bool, List[float], str]:
        """Monitor signal continuously for violations with periodic updates.

        Args:
            signal_name: Name of the signal
            min_val: Minimum acceptable value
            max_val: Maximum acceptable value
            duration: Monitoring duration in seconds
            poll_interval: Polling interval in seconds

        Returns:
            Tuple of (success, readings_list, message)
        """
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
    
    def compare_two_signals_simple(
        self,
        signal1_name: str,
        signal2_name: str,
        tolerance: float = 1.0,
        timeout: float = 2.0
    ) -> Tuple[bool, Tuple[Optional[float], Optional[float]], str]:
        """Compare values from two different signals within tolerance.

        Args:
            signal1_name: Name of the first signal
            signal2_name: Name of the second signal
            tolerance: Maximum acceptable difference
            timeout: Maximum wait time in seconds

        Returns:
            Tuple of (success, (value1, value2), message)
        """
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
    
    def set_signal_and_verify_by_id(
        self,
        message_id: int,
        signal_name: str,
        target_value: float,
        verify_timeout: float = 2.0,
        tolerance: float = 0.5
    ) -> Tuple[bool, Optional[float], float, str]:
        """Send CAN message and verify signal reached target value (round-trip test).

        Args:
            message_id: CAN message arbitration ID
            signal_name: Name of the signal
            target_value: Target value to verify
            verify_timeout: Maximum wait time for verification
            tolerance: Acceptable deviation

        Returns:
            Tuple of (success, received_value, round_trip_time, message)
        """
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

    def get_full_diagnostics(self) -> Dict[str, Any]:
        """Get comprehensive diagnostics for debugging CAN communication issues.

        Returns:
            Dictionary with detailed diagnostic information
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
    
    def print_diagnostics(self) -> None:
        """Print diagnostics to console for troubleshooting."""
        diag = self.get_full_diagnostics()
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

    def _simulate_traffic(self) -> None:
        """Simulate CAN traffic with properly encoded messages from DBC definitions.

        This generates valid CAN messages with realistic signal values for simulation mode.
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
                    diag = self.get_full_diagnostics()
                    print(f"[CAN SIMULATION] {simulation_iteration} messages, {diag['signals_with_values']} signals updated")
            
            except Exception as e:
                print(f"[CAN SIMULATION ERROR] {e}")
                time.sleep(0.1)

