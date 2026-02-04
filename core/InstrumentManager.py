"""Instrument Manager for coordinating test equipment."""

import time
from typing import Dict, Optional, Tuple, Any

from core.driver_base import HealthStatus
from core.instruments import (
    Itech6006PS,
    Itech7900Grid,
    SiglentSDXScope,
    connect_dc_load,
    is_dc_load_connected,
)
from core.logging_utils import LoggerMixin

try:
    from config import INSTRUMENT_ADDRESSES  # type: ignore[attr-defined]
except Exception:
    INSTRUMENT_ADDRESSES = {
        "Bi-Directional Power Supply": "TCPIP::192.168.4.53::INSTR",
        "Grid Emulator": "TCPIP::192.168.4.52::INSTR",
        "Oscilloscope": "TCPIP::192.168.4.51::INSTR",
        "DC Load": "COM3",
    }


class InstrumentManager(LoggerMixin):
    """Manages initialization and control of test instruments."""

    def __init__(
        self,
        simulation_mode: bool = True,
        config: Optional[Dict[str, str]] = None
    ) -> None:
        """Initialize InstrumentManager.

        Args:
            simulation_mode: Enable simulation mode for testing without hardware
            config: Optional dictionary of instrument addresses
        """
        self.simulation_mode: bool = simulation_mode
        self.itech6000: Optional[Itech6006PS] = None
        self.siglent: Optional[SiglentSDXScope] = None
        self.itech7900: Optional[Itech7900Grid] = None
        self.dc_load: Optional[Any] = None  # DCLoadAdapter type
        self._dc_load_last_mode: Optional[str] = None
        self._dc_load_last_value: Optional[float] = None
        self.addresses: Dict[str, str] = config if config else INSTRUMENT_ADDRESSES
        self.log_info(
            "InstrumentManager initialized",
            simulation_mode=simulation_mode,
            config_provided=config is not None
        )

    def _addr(self, key: str, default: str) -> str:
        """Get instrument address from config or return default.

        Args:
            key: Instrument name key
            default: Default address if key not found

        Returns:
            Instrument address string
        """
        if not self.addresses:
            return default
        return self.addresses.get(key, default)

    def _ensure_ps(self) -> None:
        """Ensure power supply instance is created."""
        if self.itech6000 is None:
            addr_ps = self._addr("Bi-Directional Power Supply", "TCPIP::192.168.4.53::INSTR")
            self.log_debug("Creating power supply instance", address=addr_ps)
            self.itech6000 = Itech6006PS(addr_ps, self.simulation_mode)

    def _ensure_gs(self) -> None:
        """Ensure grid emulator instance is created."""
        if self.itech7900 is None:
            addr_grid = self._addr("Grid Emulator", "TCPIP::192.168.4.52::INSTR")
            self.log_debug("Creating grid emulator instance", address=addr_grid)
            self.itech7900 = Itech7900Grid(addr_grid, self.simulation_mode)

    def _ensure_os(self) -> None:
        """Ensure oscilloscope instance is created."""
        if self.siglent is None:
            addr_scope = self._addr("Oscilloscope", "TCPIP::192.168.4.51::INSTR")
            self.log_debug("Creating oscilloscope instance", address=addr_scope)
            self.siglent = SiglentSDXScope(addr_scope, self.simulation_mode)

    def initialize_instruments(self) -> Tuple[bool, str]:
        self.log_info("Initializing all instruments")
        messages = []
        success = True
        try:
            self._ensure_ps()
        except Exception as e:
            success = False
            self.log_error("Bi-Directional Power Supply init failed", exc_info=True)
            messages.append(f"Bi-Directional Power Supply init failed: {e}")
        try:
            self._ensure_os()
        except Exception as e:
            success = False
            self.log_error("Oscilloscope init failed", exc_info=True)
            messages.append(f"Oscilloscope init failed: {e}")
        try:
            self._ensure_gs()
        except Exception as e:
            success = False
            self.log_error("Grid Emulator init failed", exc_info=True)
            messages.append(f"Grid Emulator init failed: {e}")

        if self.itech6000:
            try:
                self.log_debug("Connecting to Bi-Directional Power Supply")
                s, m = self.itech6000.connect()
                if not s:
                    success = False
                    self.log_error("Bi-Directional Power Supply connection failed", result=m)
                    messages.append(f"Bi-Directional Power Supply Error: {m}")
                else:
                    self.log_info("Bi-Directional Power Supply connected", result=m)
                    messages.append(f"Bi-Directional Power Supply: {m}")
            except Exception as e:
                success = False
                self.log_error("Bi-Directional Power Supply connect exception", exc_info=True)
                messages.append(f"Bi-Directional Power Supply connect failed: {e}")

        if self.siglent:
            try:
                self.log_debug("Connecting to Oscilloscope")
                s, m = self.siglent.connect()
                if not s:
                    success = False
                    self.log_error("Oscilloscope connection failed", result=m)
                    messages.append(f"Oscilloscope Error: {m}")
                else:
                    self.log_info("Oscilloscope connected", result=m)
                    messages.append(f"Oscilloscope: {m}")
            except Exception as e:
                success = False
                self.log_error("Oscilloscope connect exception", exc_info=True)
                messages.append(f"Oscilloscope connect failed: {e}")

        if self.itech7900:
            try:
                self.log_debug("Connecting to Grid Emulator")
                s, m = self.itech7900.connect()
                if not s:
                    success = False
                    self.log_error("Grid Emulator connection failed", result=m)
                    messages.append(f"Grid Emulator Error: {m}")
                else:
                    self.log_info("Grid Emulator connected", result=m)
                    messages.append(f"Grid Emulator: {m}")
            except Exception as e:
                success = False
                self.log_error("Grid Emulator connect exception", exc_info=True)
                messages.append(f"Grid Emulator connect failed: {e}")

        try:
            self.log_debug("Initializing DC Load")
            s, m = self.init_load()
            if not s:
                success = False
                self.log_error("DC Load initialization failed", result=m)
                messages.append(f"DC Load Error: {m}")
            else:
                self.log_info("DC Load initialized", result=m)
                messages.append(f"DC Load: {m}")
        except Exception as e:
            success = False
            self.log_error("DC Load init exception", exc_info=True)
            messages.append(f"DC Load init failed: {e}")

        if success:
            self.log_info("All instruments initialized successfully")
        else:
            self.log_warning("Instrument initialization completed with errors")
        return success, "\n".join(messages)

    # ---------- Independent init/disconnect helpers for sequencer INSTR actions ----------
    def init_ps(self) -> Tuple[bool, str]:
        """Initialize power supply.

        Returns:
            Tuple of (success, message)
        """
        self.log_debug("init_ps called")
        self._ensure_ps()
        if getattr(self.itech6000, "connected", False):
            self.log_debug("PS already connected")
            return True, "PS already connected"
        result = self.itech6000.connect()  # type: ignore[no-any-return]
        if result[0]:
            self.log_info("Power supply connected")
        else:
            self.log_error("Power supply connection failed", result=result[1])
        return result

    def end_ps(self) -> Tuple[bool, str]:
        """Disconnect power supply.

        Returns:
            Tuple of (success, message)
        """
        self.log_debug("end_ps called")
        if self.itech6000:
            try:
                self.itech6000.disconnect()
                self.log_info("Power supply disconnected")
                return True, "PS disconnected"
            except Exception as e:
                self.log_error("PS disconnect failed", exc_info=True)
                return False, f"PS disconnect failed: {e}"
        return True, "PS not initialized"

    def init_gs(self) -> Tuple[bool, str]:
        """Initialize grid emulator.

        Returns:
            Tuple of (success, message)
        """
        self.log_debug("init_gs called")
        self._ensure_gs()
        if getattr(self.itech7900, "connected", False):
            self.log_debug("GS already connected")
            return True, "GS already connected"
        result = self.itech7900.connect()  # type: ignore[no-any-return]
        if result[0]:
            self.log_info("Grid emulator connected")
        else:
            self.log_error("Grid emulator connection failed", result=result[1])
        return result

    def end_gs(self) -> Tuple[bool, str]:
        """Disconnect grid emulator.

        Returns:
            Tuple of (success, message)
        """
        self.log_debug("end_gs called")
        if self.itech7900:
            try:
                self.itech7900.disconnect()
                self.log_info("Grid emulator disconnected")
                return True, "GS disconnected"
            except Exception as e:
                self.log_error("GS disconnect failed", exc_info=True)
                return False, f"GS disconnect failed: {e}"
        return True, "GS not initialized"

    def init_os(self) -> Tuple[bool, str]:
        """Initialize oscilloscope.

        Returns:
            Tuple of (success, message)
        """
        self.log_debug("init_os called")
        self._ensure_os()
        if getattr(self.siglent, "connected", False):
            self.log_debug("Oscilloscope already connected")
            return True, "Oscilloscope already connected"
        result = self.siglent.connect()  # type: ignore[no-any-return]
        if result[0]:
            self.log_info("Oscilloscope connected")
        else:
            self.log_error("Oscilloscope connection failed", result=result[1])
        return result

    def end_os(self) -> Tuple[bool, str]:
        """Disconnect oscilloscope.

        Returns:
            Tuple of (success, message)
        """
        self.log_debug("end_os called")
        if self.siglent:
            try:
                self.siglent.disconnect()
                self.log_info("Oscilloscope disconnected")
                return True, "Oscilloscope disconnected"
            except Exception as e:
                self.log_error("Oscilloscope disconnect failed", exc_info=True)
                return False, f"Oscilloscope disconnect failed: {e}"
        return True, "Oscilloscope not initialized"

    # ---------- DC Load (Maynuo M97 via RS232/USB) ----------
    def init_load(
        self,
        port: Optional[str] = None,
        slave_addr: int = 1,
        baudrate: int = 9600,
        timeout: float = 0.3,
        parity: str = "N"
    ) -> Tuple[bool, str]:
        self.log_debug("init_load called", port=port, slave_addr=slave_addr)
        if self.dc_load and is_dc_load_connected(self.dc_load):
            self.log_debug("DC Load already connected")
            return True, "DC Load already connected"
        inst, msg = connect_dc_load(
            self.simulation_mode,
            addresses=self.addresses,
            port=port,
            slave_addr=slave_addr,
            baudrate=baudrate,
            timeout=timeout,
            parity=parity,
        )
        if inst is None:
            self.log_error("DC Load connection failed", result=msg)
            return False, msg
        self.dc_load = inst
        self.log_info("DC Load connected", result=msg)
        return True, msg

    def end_load(self) -> Tuple[bool, str]:
        """Disconnect DC load.

        Returns:
            Tuple of (success, message)
        """
        self.log_debug("end_load called")
        if self.dc_load:
            try:
                self.dc_load.close()
                self.dc_load = None
                self.log_info("DC Load disconnected")
                return True, "DC Load disconnected"
            except Exception as e:
                self.log_error("DC Load disconnect failed", exc_info=True)
                return False, f"DC Load disconnect failed: {e}"
        return True, "DC Load not initialized"

    def _require_dc_load(self) -> Tuple[bool, str]:
        """Check if DC load is initialized.

        Returns:
            Tuple of (success, message)
        """
        if not self.dc_load:
            return False, "DC Load not initialized"
        return True, ""

    def dc_load_enable_input(self, enable: bool = True) -> Tuple[bool, str]:
        """Enable or disable DC load input.

        Args:
            enable: True to enable input, False to disable

        Returns:
            Tuple of (success, message)
        """
        ok, msg = self._require_dc_load()
        if not ok:
            return False, msg
        try:
            if enable:
                self.dc_load.enable_input()
                self.log_debug("DC Load input enabled")
                return True, "DC Load input ON"
            self.dc_load.disable_input()
            self.log_debug("DC Load input disabled")
            return True, "DC Load input OFF"
        except Exception as e:
            self.log_error("DC Load input toggle failed", exc_info=True, enable=enable)
            return False, f"DC Load input toggle failed: {e}"

    def dc_load_set_cc(self, current_a: float) -> Tuple[bool, str]:
        """Set DC load to constant current mode.

        Args:
            current_a: Current in amperes

        Returns:
            Tuple of (success, message)
        """
        ok, msg = self._require_dc_load()
        if not ok:
            return False, msg
        try:
            self.dc_load.set_cc_current(float(current_a))
            self._dc_load_last_mode = "CC"
            self._dc_load_last_value = float(current_a)
            self.log_debug("DC Load CC mode set", current_a=current_a)
            return True, f"DC Load CC set to {current_a} A"
        except Exception as e:
            self.log_error("DC Load CC failed", exc_info=True, current_a=current_a)
            return False, f"DC Load CC failed: {e}"

    def dc_load_set_cv(self, voltage_v: float) -> Tuple[bool, str]:
        """Set DC load to constant voltage mode.

        Args:
            voltage_v: Voltage in volts

        Returns:
            Tuple of (success, message)
        """
        ok, msg = self._require_dc_load()
        if not ok:
            return False, msg
        try:
            self.dc_load.set_cv_voltage(float(voltage_v))
            self._dc_load_last_mode = "CV"
            self._dc_load_last_value = float(voltage_v)
            self.log_debug("DC Load CV mode set", voltage_v=voltage_v)
            return True, f"DC Load CV set to {voltage_v} V"
        except Exception as e:
            self.log_error("DC Load CV failed", exc_info=True, voltage_v=voltage_v)
            return False, f"DC Load CV failed: {e}"

    def dc_load_set_cp(self, power_w: float) -> Tuple[bool, str]:
        """Set DC load to constant power mode.

        Args:
            power_w: Power in watts

        Returns:
            Tuple of (success, message)
        """
        ok, msg = self._require_dc_load()
        if not ok:
            return False, msg
        try:
            self.dc_load.set_cw_power(float(power_w))
            self._dc_load_last_mode = "CP"
            self._dc_load_last_value = float(power_w)
            self.log_debug("DC Load CP mode set", power_w=power_w)
            return True, f"DC Load CP set to {power_w} W"
        except Exception as e:
            self.log_error("DC Load CP failed", exc_info=True, power_w=power_w)
            return False, f"DC Load CP failed: {e}"

    def dc_load_set_cr(self, resistance_ohm: float) -> Tuple[bool, str]:
        """Set DC load to constant resistance mode.

        Args:
            resistance_ohm: Resistance in ohms

        Returns:
            Tuple of (success, message)
        """
        ok, msg = self._require_dc_load()
        if not ok:
            return False, msg
        try:
            self.dc_load.set_cr_resistance(float(resistance_ohm))
            self._dc_load_last_mode = "CR"
            self._dc_load_last_value = float(resistance_ohm)
            self.log_debug("DC Load CR mode set", resistance_ohm=resistance_ohm)
            return True, f"DC Load CR set to {resistance_ohm} Ohm"
        except Exception as e:
            self.log_error("DC Load CR failed", exc_info=True, resistance_ohm=resistance_ohm)
            return False, f"DC Load CR failed: {e}"

    def dc_load_measure_vi(self) -> Tuple[bool, str]:
        """Measure DC load voltage and current.

        Returns:
            Tuple of (success, message with measurements)
        """
        ok, msg = self._require_dc_load()
        if not ok:
            return False, msg
        try:
            v, i = self.dc_load.read_voltage_current()
            self.log_debug("DC Load measurement", voltage=v, current=i)
            return True, f"DC Load Meas V={v:.3f} V, I={i:.3f} A"
        except Exception as e:
            self.log_error("DC Load measure failed", exc_info=True)
            return False, f"DC Load measure failed: {e}"

    def dc_load_measure_power(self) -> Tuple[bool, str]:
        """Measure DC load power consumption.

        Returns:
            Tuple of (success, message with power measurement)
        """
        ok, msg = self._require_dc_load()
        if not ok:
            return False, msg
        try:
            v, i = self.dc_load.read_voltage_current()
            p = v * i
            self.log_debug("DC Load power measurement", voltage=v, current=i, power=p)
            return True, f"DC Load Power: {p:.3f} W (V={v:.3f} V, I={i:.3f} A)"
        except Exception as e:
            self.log_error("DC Load power measurement failed", exc_info=True)
            return False, f"DC Load power failed: {e}"

    def dc_load_start_short_circuit(self) -> Tuple[bool, str]:
        """Start DC load short-circuit mode.

        Returns:
            Tuple of (success, message)
        """
        ok, msg = self._require_dc_load()
        if not ok:
            return False, msg
        if not hasattr(self.dc_load, "start_short_circuit"):
            self.log_warning("DC Load short-circuit mode not supported")
            return False, "DC Load short-circuit mode not supported"
        try:
            self.dc_load.start_short_circuit()
            self.log_info("DC Load short-circuit mode enabled")
            return True, "DC Load short-circuit mode enabled"
        except Exception as e:
            self.log_error("DC Load short-circuit failed", exc_info=True)
            return False, f"DC Load short-circuit failed: {e}"

    def dc_load_stop_short_circuit(self) -> Tuple[bool, str]:
        ok, msg = self._require_dc_load()
        if not ok:
            return False, msg
        try:
            if hasattr(self.dc_load, "stop_short_circuit"):
                self.dc_load.stop_short_circuit()
            else:
                self.dc_load.disable_input()
            mode = self._dc_load_last_mode
            value = self._dc_load_last_value
            if mode and value is not None:
                self.log_debug("Restoring previous mode", mode=mode, value=value)
                if mode == "CC":
                    self.dc_load.set_cc_current(float(value))
                elif mode == "CV":
                    self.dc_load.set_cv_voltage(float(value))
                elif mode == "CP":
                    self.dc_load.set_cw_power(float(value))
                elif mode == "CR":
                    self.dc_load.set_cr_resistance(float(value))
            elif mode is None:
                try:
                    self.dc_load.set_cc_current(0.0)
                    self._dc_load_last_mode = "CC"
                    self._dc_load_last_value = 0.0
                except Exception:
                    pass
            self.log_info("DC Load short-circuit mode disabled")
            return True, "DC Load short-circuit mode disabled"
        except Exception as e:
            self.log_error("DC Load short-circuit stop failed", exc_info=True)
            return False, f"DC Load short-circuit stop failed: {e}"

    def dc_load_short_pulse(self, duration_s: float = 0.1) -> Tuple[bool, str]:
        """Execute a short-circuit pulse for specified duration.

        Args:
            duration_s: Duration of short-circuit pulse in seconds

        Returns:
            Tuple of (success, message)
        """
        ok, msg = self._require_dc_load()
        if not ok:
            return False, msg
        if not hasattr(self.dc_load, "start_short_circuit"):
            self.log_warning("DC Load short-circuit mode not supported")
            return False, "DC Load short-circuit mode not supported"
        try:
            duration = float(duration_s)
        except Exception:
            self.log_error("Invalid short-circuit duration", duration_s=duration_s)
            return False, "Invalid short-circuit duration"
        if duration <= 0:
            self.log_error("Short-circuit duration must be > 0", duration=duration)
            return False, "Short-circuit duration must be > 0"
        try:
            self.log_info("Starting short-circuit pulse", duration=duration)
            self.dc_load.start_short_circuit()
            self.dc_load.enable_input()
            time.sleep(duration)
        except Exception as e:
            self.log_error("DC Load short-circuit pulse failed", exc_info=True)
            return False, f"DC Load short-circuit pulse failed: {e}"
        finally:
            try:
                self.dc_load.disable_input()
            except Exception:
                pass
            try:
                self.dc_load_stop_short_circuit()
            except Exception:
                pass
        self.log_info("Short-circuit pulse completed", duration=duration)
        return True, f"DC Load short-circuit pulse {duration:.3f} s"

    def close_instruments(self) -> None:
        """Disconnect all connected instruments."""
        self.log_info("Closing all instruments")
        if self.itech6000:
            self.log_debug("Disconnecting power supply")
            self.itech6000.disconnect()
        if self.siglent:
            self.log_debug("Disconnecting oscilloscope")
            self.siglent.disconnect()
        if self.itech7900:
            self.log_debug("Disconnecting grid emulator")
            self.itech7900.disconnect()
        if self.dc_load:
            try:
                self.log_debug("Closing DC load")
                self.dc_load.close()
            except Exception:
                self.log_warning("Failed to close DC load gracefully")
        self.log_info("All instruments closed")

    def safe_power_down(self) -> None:
        """Safely power down all instruments."""
        self.log_info("Safe power down initiated")
        try:
            if self.itech6000:
                try:
                    self.log_debug("Powering off power supply")
                    self.itech6000.power_off()
                except Exception:
                    self.log_warning("Failed to power off power supply")
        except Exception:
            pass
        try:
            if self.itech7900:
                try:
                    self.log_debug("Powering off grid emulator")
                    self.itech7900.power_off()
                except Exception:
                    self.log_warning("Failed to power off grid emulator")
        except Exception:
            pass
        self.log_info("Safe power down completed")

    def health_report(self) -> Dict[str, HealthStatus]:
        """Generate health status report for all instruments.

        Returns:
            Dictionary mapping instrument names to HealthStatus objects
        """
        self.log_debug("Generating health report")
        report: Dict[str, HealthStatus] = {}
        if self.itech6000:
            try:
                if not getattr(self.itech6000, "connected", False):
                    report["power_supply"] = HealthStatus(False, "PS not connected")
                else:
                    report["power_supply"] = self.itech6000.health_check()
            except Exception as e:
                self.log_error("PS health check failed", exc_info=True)
                report["power_supply"] = HealthStatus(False, f"PS health error: {e}")
        if self.itech7900:
            try:
                if not getattr(self.itech7900, "connected", False):
                    report["grid_emulator"] = HealthStatus(False, "Grid not connected")
                else:
                    report["grid_emulator"] = self.itech7900.health_check()
            except Exception as e:
                self.log_error("Grid health check failed", exc_info=True)
                report["grid_emulator"] = HealthStatus(False, f"Grid health error: {e}")
        if self.siglent:
            try:
                if not getattr(self.siglent, "connected", False):
                    report["oscilloscope"] = HealthStatus(False, "Scope not connected")
                else:
                    report["oscilloscope"] = self.siglent.health_check()
            except Exception as e:
                self.log_error("Oscilloscope health check failed", exc_info=True)
                report["oscilloscope"] = HealthStatus(False, f"Scope health error: {e}")
        self.log_debug("Health report generated", instruments=len(report))
        return report
