"""Unit tests for CAN connection module."""

from unittest.mock import Mock, patch
import pytest

from core.can.connection import CANConnection


@pytest.mark.unit
class TestCANConnection:
    """Test suite for CANConnection class."""

    def test_init(self):
        """Test CANConnection initialization."""
        conn = CANConnection(simulation_mode=False)

        assert not conn.simulation_mode
        assert conn.bus is None
        assert conn.interface is None
        assert conn.channel is None
        assert conn.bitrate is None

    def test_init_simulation_mode(self):
        """Test initialization in simulation mode."""
        conn = CANConnection(simulation_mode=True)

        assert conn.simulation_mode

    @patch('core.can.connection.can.Bus')
    def test_connect(self, mock_bus_class):
        """Test connecting to CAN bus."""
        mock_bus = Mock()
        mock_bus_class.return_value = mock_bus

        conn = CANConnection(simulation_mode=False)
        success, message = conn.connect('pcan', 'PCAN_USBBUS1', 500000)

        assert success
        assert "Connected" in message
        assert conn.bus == mock_bus
        assert conn.interface == 'pcan'
        assert conn.channel == 'PCAN_USBBUS1'
        assert conn.bitrate == 500000

        mock_bus_class.assert_called_once_with(
            interface='pcan',
            channel='PCAN_USBBUS1',
            bitrate=500000
        )

    def test_connect_simulation_mode(self):
        """Test connecting in simulation mode."""
        conn = CANConnection(simulation_mode=True)
        success, message = conn.connect()

        assert success
        assert "SIMULATION" in message
        assert conn.bus is None

    @patch('core.can.connection.can.Bus')
    def test_connect_with_defaults(self, mock_bus_class):
        """Test connecting with default parameters."""
        mock_bus = Mock()
        mock_bus_class.return_value = mock_bus

        conn = CANConnection(simulation_mode=False)
        success, message = conn.connect()

        assert success
        # Should use default values
        mock_bus_class.assert_called_once()
        call_kwargs = mock_bus_class.call_args[1]
        assert 'interface' in call_kwargs
        assert 'channel' in call_kwargs
        assert 'bitrate' in call_kwargs

    @patch('core.can.connection.can.Bus')
    def test_connect_failure(self, mock_bus_class):
        """Test connection failure."""
        mock_bus_class.side_effect = Exception("Connection failed")

        conn = CANConnection(simulation_mode=False)
        success, message = conn.connect()

        assert not success
        assert "failed" in message.lower()

    def test_disconnect(self):
        """Test disconnecting from CAN bus."""
        conn = CANConnection(simulation_mode=False)
        conn.bus = Mock()

        success, message = conn.disconnect()

        assert success
        assert "disconnected" in message.lower()
        assert conn.bus is None

    def test_disconnect_when_not_connected(self):
        """Test disconnecting when not connected."""
        conn = CANConnection(simulation_mode=False)

        success, message = conn.disconnect()

        assert success
        assert "not connected" in message.lower()

    def test_disconnect_simulation_mode(self):
        """Test disconnecting in simulation mode."""
        conn = CANConnection(simulation_mode=True)

        success, message = conn.disconnect()

        assert success
        assert "SIMULATION" in message

    def test_is_connected(self):
        """Test is_connected status."""
        conn = CANConnection(simulation_mode=False)

        assert not conn.is_connected()

        conn.bus = Mock()
        assert conn.is_connected()

        conn.bus = None
        assert not conn.is_connected()

    def test_is_connected_simulation_mode(self):
        """Test is_connected in simulation mode."""
        conn = CANConnection(simulation_mode=True)

        # Always connected in simulation mode
        assert conn.is_connected()
