"""CAN signal management module.

Handles signal caching, decoding, and manipulation.
"""

import logging
import threading
import time
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class SignalManager:
    """Manages CAN signal caching and retrieval."""

    def __init__(self, dbc_parser, signal_cache_lock: threading.RLock):
        """Initialize signal manager.

        Args:
            dbc_parser: DBC parser instance
            signal_cache_lock: Thread-safe lock for signal cache
        """
        self.dbc_parser = dbc_parser
        self.signal_cache: Dict[str, Dict[str, Any]] = {}
        self.signal_cache_lock = signal_cache_lock
        self.signal_overrides: Dict[str, Dict[str, float]] = {}
        self.last_sent_signals: Dict[str, Dict[str, float]] = {}

    def cache_signals(
        self,
        message_id: int,
        decoded_signals: Dict[str, float],
        timestamp: float,
        raw_signals: Optional[Dict] = None
    ) -> None:
        """Cache decoded signal values.

        Args:
            message_id: CAN message ID
            decoded_signals: Dict of decoded signal values
            timestamp: Timestamp of the message
            raw_signals: Optional raw signal data
        """
        with self.signal_cache_lock:
            for signal_name, value in decoded_signals.items():
                self.signal_cache[signal_name] = {
                    "value": value,
                    "timestamp": timestamp,
                    "message_id": message_id
                }

    def get_signal_from_cache(self, signal_name: str) -> Optional[Tuple[Any, float]]:
        """Get signal value from cache.

        Args:
            signal_name: Name of the signal

        Returns:
            Tuple of (value, timestamp) or None if not found
        """
        with self.signal_cache_lock:
            if signal_name in self.signal_cache:
                entry = self.signal_cache[signal_name]
                return entry["value"], entry["timestamp"]
        return None

    def get_all_signals_from_cache(self) -> Dict[str, Dict[str, Any]]:
        """Get all cached signals.

        Returns:
            Dictionary of all cached signals
        """
        with self.signal_cache_lock:
            return dict(self.signal_cache)

    def set_signal_override(self, message_name: str, signal_name: str, value: float) -> None:
        """Set an override value for a signal.

        Args:
            message_name: Name of the message
            signal_name: Name of the signal
            value: Override value
        """
        if message_name not in self.signal_overrides:
            self.signal_overrides[message_name] = {}
        self.signal_overrides[message_name][signal_name] = value
        logger.info(f"Set override: {message_name}.{signal_name} = {value}")

    def clear_signal_override(
        self,
        message_name: Optional[str] = None,
        signal_name: Optional[str] = None
    ) -> None:
        """Clear signal overrides.

        Args:
            message_name: Optional message name to clear (all if None)
            signal_name: Optional signal name to clear (all if None)
        """
        if message_name is None:
            self.signal_overrides.clear()
            logger.info("Cleared all signal overrides")
        elif signal_name is None:
            if message_name in self.signal_overrides:
                del self.signal_overrides[message_name]
                logger.info(f"Cleared overrides for message: {message_name}")
        else:
            if message_name in self.signal_overrides:
                self.signal_overrides[message_name].pop(signal_name, None)
                logger.info(f"Cleared override: {message_name}.{signal_name}")

    def build_full_values(self, message_def, signals_dict: Dict[str, float]) -> Dict[str, float]:
        """Build complete signal values for a message.

        Merges provided signals with cached/default values to ensure all
        signals in the message have values.

        Args:
            message_def: DBC message definition
            signals_dict: Partial signal values

        Returns:
            Complete signal values dictionary
        """
        full_values = {}

        # Start with defaults or previously sent values
        if message_def.name in self.last_sent_signals:
            full_values.update(self.last_sent_signals[message_def.name])

        # Add default values for missing signals
        for signal in message_def.signals:
            if signal.name not in full_values:
                if hasattr(signal, 'initial') and signal.initial is not None:
                    full_values[signal.name] = signal.initial
                else:
                    full_values[signal.name] = 0

        # Apply user-provided values
        if signals_dict:
            full_values.update(signals_dict)

        # Apply overrides
        if message_def.name in self.signal_overrides:
            full_values.update(self.signal_overrides[message_def.name])

        return full_values
