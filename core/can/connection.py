"""CAN bus connection management module.

Handles CAN bus initialization and connection.
"""

import logging
from typing import Optional, Tuple

import can

logger = logging.getLogger(__name__)


class CANConnection:
    """Manages CAN bus connection."""

    def __init__(self, simulation_mode: bool = False):
        """Initialize CAN connection.

        Args:
            simulation_mode: Whether to run in simulation mode
        """
        self.simulation_mode = simulation_mode
        self.bus: Optional[can.BusABC] = None
        self.interface: Optional[str] = None
        self.channel: Optional[str] = None
        self.bitrate: Optional[int] = None

    def connect(
        self,
        interface: Optional[str] = None,
        channel: Optional[str] = None,
        bitrate: Optional[int] = None
    ) -> Tuple[bool, str]:
        """Connect to CAN bus.

        Args:
            interface: CAN interface (e.g., 'pcan', 'socketcan')
            channel: CAN channel
            bitrate: CAN bitrate

        Returns:
            Tuple of (success, message)
        """
        if self.simulation_mode:
            logger.info("CAN connection in simulation mode")
            return True, "[CAN SIMULATION] Connected (Simulation Mode)"

        try:
            # Use provided values or stored defaults
            interface = interface or self.interface or 'pcan'
            channel = channel or self.channel or 'PCAN_USBBUS1'
            bitrate = bitrate or self.bitrate or 500000

            # Store for future use
            self.interface = interface
            self.channel = channel
            self.bitrate = bitrate

            # Create CAN bus
            self.bus = can.Bus(
                interface=interface,
                channel=channel,
                bitrate=bitrate
            )

            logger.info(f"Connected to CAN: {interface}:{channel} @ {bitrate}")
            return True, f"Connected to {interface}:{channel} @ {bitrate} bps"

        except Exception as e:
            error_msg = f"CAN connection failed: {e}"
            logger.error(error_msg)
            return False, error_msg

    def disconnect(self) -> Tuple[bool, str]:
        """Disconnect from CAN bus.

        Returns:
            Tuple of (success, message)
        """
        if self.simulation_mode:
            logger.info("CAN disconnected (simulation mode)")
            return True, "[CAN SIMULATION] Disconnected"

        try:
            if self.bus:
                self.bus.shutdown()
                self.bus = None
                logger.info("CAN bus disconnected")
                return True, "CAN bus disconnected"
            return True, "CAN bus was not connected"

        except Exception as e:
            error_msg = f"CAN disconnect failed: {e}"
            logger.error(error_msg)
            return False, error_msg

    def is_connected(self) -> bool:
        """Check if connected to CAN bus.

        Returns:
            True if connected, False otherwise
        """
        if self.simulation_mode:
            return True
        return self.bus is not None
