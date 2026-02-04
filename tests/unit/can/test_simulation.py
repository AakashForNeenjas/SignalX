"""Unit tests for CAN simulation module."""

import time
from unittest.mock import Mock, patch
import pytest

from core.can.simulation import CANSimulator


@pytest.mark.unit
class TestCANSimulator:
    """Test suite for CANSimulator class."""

    def test_init(self, mock_message_callback, mock_diagnostics_callback):
        """Test CANSimulator initialization."""
        message_defs = {"TestMsg": Mock()}
        simulator = CANSimulator(
            message_defs,
            mock_message_callback,
            mock_diagnostics_callback
        )

        assert simulator.message_definitions == message_defs
        assert simulator.message_callback == mock_message_callback
        assert simulator.diagnostics_callback == mock_diagnostics_callback
        assert not simulator.running

    def test_start_stop(self, mock_message_callback):
        """Test starting and stopping simulation."""
        message_defs = {"TestMsg": Mock()}
        simulator = CANSimulator(message_defs, mock_message_callback)

        # Start simulation
        simulator.start()
        assert simulator.running
        assert simulator._simulation_thread is not None

        # Stop simulation
        simulator.stop()
        assert not simulator.running

    def test_start_already_running(self, mock_message_callback, caplog):
        """Test starting simulation when already running."""
        message_defs = {"TestMsg": Mock()}
        simulator = CANSimulator(message_defs, mock_message_callback)

        simulator.start()
        simulator.start()  # Try starting again

        assert "already running" in caplog.text.lower()
        simulator.stop()

    def test_start_no_message_definitions(self, mock_message_callback, caplog):
        """Test starting simulation with no message definitions."""
        simulator = CANSimulator({}, mock_message_callback)

        simulator.start()
        time.sleep(0.2)  # Give thread time to start and exit

        assert "no message definitions" in caplog.text.lower()
        simulator.stop()

    @patch('core.can.simulation.time.sleep')
    def test_simulate_traffic(self, mock_sleep, mock_message_callback):
        """Test traffic simulation generates messages."""
        # Create mock message definition
        mock_signal = Mock()
        mock_signal.name = "TestSignal"
        mock_signal.minimum = 0
        mock_signal.maximum = 100

        mock_message = Mock()
        mock_message.frame_id = 0x100
        mock_message.signals = [mock_signal]
        mock_message.encode = Mock(return_value=b'\x00\x01\x02\x03\x04\x05\x06\x07')

        message_defs = {"TestMsg": mock_message}
        simulator = CANSimulator(message_defs, mock_message_callback)

        # Configure sleep to stop after a few iterations
        call_count = [0]

        def sleep_side_effect(duration):
            call_count[0] += 1
            if call_count[0] > 3:
                simulator.running = False

        mock_sleep.side_effect = sleep_side_effect

        simulator.start()
        time.sleep(0.5)  # Give real time for thread to complete

        # Verify message callback was called
        assert mock_message_callback.called
        assert mock_message_callback.call_count >= 3

    def test_stop_when_not_running(self, mock_message_callback):
        """Test stopping simulation when not running."""
        simulator = CANSimulator({}, mock_message_callback)
        simulator.stop()  # Should not raise exception
        assert not simulator.running
