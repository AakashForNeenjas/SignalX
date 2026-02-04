"""CAN bus traffic simulation module.

Provides realistic CAN traffic simulation using DBC message definitions.
"""

import logging
import random
import threading
import time
from typing import Callable, Dict, Optional

import can

logger = logging.getLogger(__name__)


class CANSimulator:
    """Simulates CAN bus traffic using DBC message definitions."""

    def __init__(
        self,
        message_definitions: Dict,
        message_callback: Callable,
        diagnostics_callback: Optional[Callable] = None
    ):
        """Initialize CAN simulator.

        Args:
            message_definitions: Dict of message definitions from DBC parser
            message_callback: Callback to invoke with simulated messages
            diagnostics_callback: Optional callback to get diagnostics info
        """
        self.message_definitions = message_definitions
        self.message_callback = message_callback
        self.diagnostics_callback = diagnostics_callback
        self.running = False
        self._simulation_thread: Optional[threading.Thread] = None
        self._simulation_iteration = 0

    def start(self):
        """Start traffic simulation in a background thread."""
        if self.running:
            logger.warning("Simulation already running")
            return

        self.running = True
        self._simulation_thread = threading.Thread(
            target=self._simulate_traffic,
            daemon=True,
            name="CANSimulator"
        )
        self._simulation_thread.start()
        logger.info("CAN simulation started")

    def stop(self):
        """Stop traffic simulation."""
        if not self.running:
            return

        self.running = False
        if self._simulation_thread:
            self._simulation_thread.join(timeout=2.0)
            self._simulation_thread = None
        logger.info("CAN simulation stopped")

    def _simulate_traffic(self):
        """Generate simulated CAN traffic with realistic signal values.

        This generates valid CAN messages with realistic signal values based on
        DBC message definitions.
        """
        logger.info("Starting CAN message simulation...")

        if not self.message_definitions:
            logger.warning("No message definitions loaded, cannot simulate")
            return

        message_list = list(self.message_definitions.values())
        logger.info(f"Simulating {len(message_list)} message types")

        self._simulation_iteration = 0

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

                    # Process through callback
                    self.message_callback(msg)

                except Exception as encode_err:
                    # Some messages might have special encoding requirements
                    logger.debug(f"Message encoding failed: {encode_err}")

                # Simulate at ~10 messages per second
                time.sleep(0.1)
                self._simulation_iteration += 1

                # Progress indicator every 100 messages
                if self._simulation_iteration % 100 == 0:
                    if self.diagnostics_callback:
                        try:
                            diag = self.diagnostics_callback()
                            logger.info(
                                f"Simulation: {self._simulation_iteration} messages, "
                                f"{diag.get('signals_with_values', 0)} signals updated"
                            )
                        except Exception as e:
                            logger.warning(f"Failed to get diagnostics: {e}")

            except Exception as e:
                logger.error(f"Simulation error: {e}")
                time.sleep(0.1)
