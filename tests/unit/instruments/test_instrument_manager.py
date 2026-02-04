"""Unit tests for InstrumentManager."""

import pytest
from unittest.mock import Mock, MagicMock, patch

from core.InstrumentManager import InstrumentManager


@pytest.mark.unit
class TestInstrumentManager:
    """Test suite for InstrumentManager class."""

    def test_init_simulation_mode(self):
        """Test initialization in simulation mode."""
        mgr = InstrumentManager(simulation_mode=True)

        assert mgr.simulation_mode is True
        assert mgr.itech6000 is None
        assert mgr.siglent is None
        assert mgr.itech7900 is None
        assert mgr.dc_load is None

    def test_init_with_config(self):
        """Test initialization with custom config."""
        config = {
            "Bi-Directional Power Supply": "TCPIP::192.168.1.100::INSTR",
            "Grid Emulator": "TCPIP::192.168.1.101::INSTR"
        }
        mgr = InstrumentManager(simulation_mode=False, config=config)

        assert mgr.addresses == config

    def test_addr_with_config(self):
        """Test _addr method returns config value."""
        config = {"test_key": "test_value"}
        mgr = InstrumentManager(config=config)

        result = mgr._addr("test_key", "default")
        assert result == "test_value"

    def test_addr_with_default(self):
        """Test _addr method returns default when key missing."""
        mgr = InstrumentManager()

        result = mgr._addr("missing_key", "default_value")
        assert result == "default_value"

    @patch('core.InstrumentManager.Itech6006PS')
    def test_ensure_ps(self, mock_ps_class):
        """Test _ensure_ps creates power supply instance."""
        mock_ps = Mock()
        mock_ps_class.return_value = mock_ps

        mgr = InstrumentManager(simulation_mode=True)
        mgr._ensure_ps()

        assert mgr.itech6000 == mock_ps
        mock_ps_class.assert_called_once()

    @patch('core.InstrumentManager.Itech7900Grid')
    def test_ensure_gs(self, mock_gs_class):
        """Test _ensure_gs creates grid emulator instance."""
        mock_gs = Mock()
        mock_gs_class.return_value = mock_gs

        mgr = InstrumentManager(simulation_mode=True)
        mgr._ensure_gs()

        assert mgr.itech7900 == mock_gs
        mock_gs_class.assert_called_once()

    @patch('core.InstrumentManager.SiglentSDXScope')
    def test_ensure_os(self, mock_os_class):
        """Test _ensure_os creates oscilloscope instance."""
        mock_os = Mock()
        mock_os_class.return_value = mock_os

        mgr = InstrumentManager(simulation_mode=True)
        mgr._ensure_os()

        assert mgr.siglent == mock_os
        mock_os_class.assert_called_once()

    @patch('core.InstrumentManager.Itech6006PS')
    def test_init_ps_success(self, mock_ps_class):
        """Test init_ps returns success."""
        mock_ps = Mock()
        mock_ps.connected = False
        mock_ps.connect.return_value = (True, "Connected")
        mock_ps_class.return_value = mock_ps

        mgr = InstrumentManager(simulation_mode=True)
        success, message = mgr.init_ps()

        assert success is True
        assert "Connected" in message
        mock_ps.connect.assert_called_once()

    @patch('core.InstrumentManager.Itech6006PS')
    def test_init_ps_already_connected(self, mock_ps_class):
        """Test init_ps when already connected."""
        mock_ps = Mock()
        mock_ps.connected = True
        mock_ps_class.return_value = mock_ps

        mgr = InstrumentManager(simulation_mode=True)
        mgr._ensure_ps()
        success, message = mgr.init_ps()

        assert success is True
        assert "already connected" in message.lower()

    @patch('core.InstrumentManager.Itech6006PS')
    def test_init_ps_failure(self, mock_ps_class):
        """Test init_ps returns failure."""
        mock_ps = Mock()
        mock_ps.connected = False
        mock_ps.connect.return_value = (False, "Connection failed")
        mock_ps_class.return_value = mock_ps

        mgr = InstrumentManager(simulation_mode=True)
        success, message = mgr.init_ps()

        assert success is False
        assert "Connection failed" in message

    @patch('core.InstrumentManager.Itech6006PS')
    def test_end_ps(self, mock_ps_class):
        """Test end_ps disconnects power supply."""
        mock_ps = Mock()
        mock_ps.disconnect = Mock()
        mock_ps_class.return_value = mock_ps

        mgr = InstrumentManager(simulation_mode=True)
        mgr._ensure_ps()
        success, message = mgr.end_ps()

        assert success is True
        mock_ps.disconnect.assert_called_once()

    def test_end_ps_not_initialized(self):
        """Test end_ps when not initialized."""
        mgr = InstrumentManager(simulation_mode=True)
        success, message = mgr.end_ps()

        assert success is True
        assert "not initialized" in message.lower()

    @patch('core.InstrumentManager.connect_dc_load')
    def test_init_load_success(self, mock_connect):
        """Test init_load returns success."""
        mock_load = Mock()
        mock_connect.return_value = (mock_load, "DC Load connected")

        mgr = InstrumentManager(simulation_mode=True)
        success, message = mgr.init_load()

        assert success is True
        assert mgr.dc_load == mock_load
        assert "connected" in message.lower()

    @patch('core.InstrumentManager.connect_dc_load')
    def test_init_load_failure(self, mock_connect):
        """Test init_load returns failure."""
        mock_connect.return_value = (None, "Connection failed")

        mgr = InstrumentManager(simulation_mode=True)
        success, message = mgr.init_load()

        assert success is False
        assert "failed" in message.lower()

    @patch('core.InstrumentManager.is_dc_load_connected')
    @patch('core.InstrumentManager.connect_dc_load')
    def test_init_load_already_connected(self, mock_connect, mock_is_connected):
        """Test init_load when already connected."""
        mock_load = Mock()
        mock_is_connected.return_value = True

        mgr = InstrumentManager(simulation_mode=True)
        mgr.dc_load = mock_load

        success, message = mgr.init_load()

        assert success is True
        assert "already connected" in message.lower()
        mock_connect.assert_not_called()

    def test_end_load(self):
        """Test end_load disconnects DC load."""
        mock_load = Mock()
        mock_load.close = Mock()

        mgr = InstrumentManager(simulation_mode=True)
        mgr.dc_load = mock_load

        success, message = mgr.end_load()

        assert success is True
        mock_load.close.assert_called_once()
        assert mgr.dc_load is None

    def test_dc_load_enable_input(self):
        """Test enabling DC load input."""
        mock_load = Mock()
        mock_load.enable_input = Mock()

        mgr = InstrumentManager(simulation_mode=True)
        mgr.dc_load = mock_load

        success, message = mgr.dc_load_enable_input(True)

        assert success is True
        assert "ON" in message
        mock_load.enable_input.assert_called_once()

    def test_dc_load_disable_input(self):
        """Test disabling DC load input."""
        mock_load = Mock()
        mock_load.disable_input = Mock()

        mgr = InstrumentManager(simulation_mode=True)
        mgr.dc_load = mock_load

        success, message = mgr.dc_load_enable_input(False)

        assert success is True
        assert "OFF" in message
        mock_load.disable_input.assert_called_once()

    def test_dc_load_set_cc(self):
        """Test setting DC load constant current."""
        mock_load = Mock()
        mock_load.set_cc_current = Mock()

        mgr = InstrumentManager(simulation_mode=True)
        mgr.dc_load = mock_load

        success, message = mgr.dc_load_set_cc(5.0)

        assert success is True
        assert "5.0" in message
        mock_load.set_cc_current.assert_called_once_with(5.0)
        assert mgr._dc_load_last_mode == "CC"
        assert mgr._dc_load_last_value == 5.0

    def test_dc_load_set_cv(self):
        """Test setting DC load constant voltage."""
        mock_load = Mock()
        mock_load.set_cv_voltage = Mock()

        mgr = InstrumentManager(simulation_mode=True)
        mgr.dc_load = mock_load

        success, message = mgr.dc_load_set_cv(12.0)

        assert success is True
        assert "12.0" in message
        mock_load.set_cv_voltage.assert_called_once_with(12.0)
        assert mgr._dc_load_last_mode == "CV"

    def test_dc_load_measure_vi(self):
        """Test measuring voltage and current."""
        mock_load = Mock()
        mock_load.read_voltage_current.return_value = (12.5, 3.2)

        mgr = InstrumentManager(simulation_mode=True)
        mgr.dc_load = mock_load

        success, message = mgr.dc_load_measure_vi()

        assert success is True
        assert "12.5" in message
        assert "3.2" in message

    def test_dc_load_not_initialized_error(self):
        """Test DC load operations when not initialized."""
        mgr = InstrumentManager(simulation_mode=True)

        success, message = mgr.dc_load_set_cc(5.0)

        assert success is False
        assert "not initialized" in message.lower()

    @patch('core.InstrumentManager.Itech6006PS')
    @patch('core.InstrumentManager.Itech7900Grid')
    @patch('core.InstrumentManager.SiglentSDXScope')
    @patch('core.InstrumentManager.connect_dc_load')
    def test_initialize_instruments_success(
        self, mock_load_connect, mock_os_class, mock_gs_class, mock_ps_class
    ):
        """Test initialize_instruments with all instruments."""
        # Setup mocks
        mock_ps = Mock()
        mock_ps.connect.return_value = (True, "PS Connected")
        mock_ps_class.return_value = mock_ps

        mock_gs = Mock()
        mock_gs.connect.return_value = (True, "GS Connected")
        mock_gs_class.return_value = mock_gs

        mock_os = Mock()
        mock_os.connect.return_value = (True, "OS Connected")
        mock_os_class.return_value = mock_os

        mock_load = Mock()
        mock_load_connect.return_value = (mock_load, "Load Connected")

        mgr = InstrumentManager(simulation_mode=True)
        success, message = mgr.initialize_instruments()

        assert success is True
        assert "PS Connected" in message
        assert "GS Connected" in message
        assert "OS Connected" in message
        assert "Load Connected" in message

    def test_close_instruments(self):
        """Test close_instruments disconnects all."""
        mock_ps = Mock()
        mock_ps.disconnect = Mock()
        mock_gs = Mock()
        mock_gs.disconnect = Mock()

        mgr = InstrumentManager(simulation_mode=True)
        mgr.itech6000 = mock_ps
        mgr.itech7900 = mock_gs

        mgr.close_instruments()

        mock_ps.disconnect.assert_called_once()
        mock_gs.disconnect.assert_called_once()

    def test_safe_power_down(self):
        """Test safe_power_down turns off power."""
        mock_ps = Mock()
        mock_ps.power_off = Mock()

        mgr = InstrumentManager(simulation_mode=True)
        mgr.itech6000 = mock_ps

        mgr.safe_power_down()

        mock_ps.power_off.assert_called_once()
