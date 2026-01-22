import time

from core.driver_base import HealthStatus
from core.instruments import (
    Itech6006PS,
    Itech7900Grid,
    SiglentSDXScope,
    connect_dc_load,
    is_dc_load_connected,
)

try:
    from config import INSTRUMENT_ADDRESSES
except Exception:
    INSTRUMENT_ADDRESSES = {
        "Bi-Directional Power Supply": "TCPIP::192.168.4.53::INSTR",
        "Grid Emulator": "TCPIP::192.168.4.52::INSTR",
        "Oscilloscope": "TCPIP::192.168.4.51::INSTR",
        "DC Load": "COM3",
    }


class InstrumentManager:
    def __init__(self, simulation_mode=True, config=None):
        self.simulation_mode = simulation_mode
        self.itech6000 = None
        self.siglent = None
        self.itech7900 = None
        self.dc_load = None
        self._dc_load_last_mode = None
        self._dc_load_last_value = None
        self.addresses = config if config else INSTRUMENT_ADDRESSES

    def _addr(self, key, default):
        if not self.addresses:
            return default
        return self.addresses.get(key, default)

    def _ensure_ps(self):
        if self.itech6000 is None:
            addr_ps = self._addr("Bi-Directional Power Supply", "TCPIP::192.168.4.53::INSTR")
            self.itech6000 = Itech6006PS(addr_ps, self.simulation_mode)

    def _ensure_gs(self):
        if self.itech7900 is None:
            addr_grid = self._addr("Grid Emulator", "TCPIP::192.168.4.52::INSTR")
            self.itech7900 = Itech7900Grid(addr_grid, self.simulation_mode)

    def _ensure_os(self):
        if self.siglent is None:
            addr_scope = self._addr("Oscilloscope", "TCPIP::192.168.4.51::INSTR")
            self.siglent = SiglentSDXScope(addr_scope, self.simulation_mode)

    def initialize_instruments(self):
        messages = []
        success = True
        try:
            self._ensure_ps()
        except Exception as e:
            success = False
            messages.append(f"Bi-Directional Power Supply init failed: {e}")
        try:
            self._ensure_os()
        except Exception as e:
            success = False
            messages.append(f"Oscilloscope init failed: {e}")
        try:
            self._ensure_gs()
        except Exception as e:
            success = False
            messages.append(f"Grid Emulator init failed: {e}")

        if self.itech6000:
            try:
                s, m = self.itech6000.connect()
                if not s:
                    success = False
                    messages.append(f"Bi-Directional Power Supply Error: {m}")
                else:
                    messages.append(f"Bi-Directional Power Supply: {m}")
            except Exception as e:
                success = False
                messages.append(f"Bi-Directional Power Supply connect failed: {e}")

        if self.siglent:
            try:
                s, m = self.siglent.connect()
                if not s:
                    success = False
                    messages.append(f"Oscilloscope Error: {m}")
                else:
                    messages.append(f"Oscilloscope: {m}")
            except Exception as e:
                success = False
                messages.append(f"Oscilloscope connect failed: {e}")

        if self.itech7900:
            try:
                s, m = self.itech7900.connect()
                if not s:
                    success = False
                    messages.append(f"Grid Emulator Error: {m}")
                else:
                    messages.append(f"Grid Emulator: {m}")
            except Exception as e:
                success = False
                messages.append(f"Grid Emulator connect failed: {e}")

        try:
            s, m = self.init_load()
            if not s:
                success = False
                messages.append(f"DC Load Error: {m}")
            else:
                messages.append(f"DC Load: {m}")
        except Exception as e:
            success = False
            messages.append(f"DC Load init failed: {e}")

        return success, "\n".join(messages)

    # ---------- Independent init/disconnect helpers for sequencer INSTR actions ----------
    def init_ps(self):
        self._ensure_ps()
        if getattr(self.itech6000, "connected", False):
            return True, "PS already connected"
        return self.itech6000.connect()

    def end_ps(self):
        if self.itech6000:
            try:
                self.itech6000.disconnect()
                return True, "PS disconnected"
            except Exception as e:
                return False, f"PS disconnect failed: {e}"
        return True, "PS not initialized"

    def init_gs(self):
        self._ensure_gs()
        if getattr(self.itech7900, "connected", False):
            return True, "GS already connected"
        return self.itech7900.connect()

    def end_gs(self):
        if self.itech7900:
            try:
                self.itech7900.disconnect()
                return True, "GS disconnected"
            except Exception as e:
                return False, f"GS disconnect failed: {e}"
        return True, "GS not initialized"

    def init_os(self):
        self._ensure_os()
        if getattr(self.siglent, "connected", False):
            return True, "Oscilloscope already connected"
        return self.siglent.connect()

    def end_os(self):
        if self.siglent:
            try:
                self.siglent.disconnect()
                return True, "Oscilloscope disconnected"
            except Exception as e:
                return False, f"Oscilloscope disconnect failed: {e}"
        return True, "Oscilloscope not initialized"

    # ---------- DC Load (Maynuo M97 via RS232/USB) ----------
    def init_load(self, port=None, slave_addr=1, baudrate=9600, timeout=0.3, parity="N"):
        if self.dc_load and is_dc_load_connected(self.dc_load):
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
            return False, msg
        self.dc_load = inst
        return True, msg

    def end_load(self):
        if self.dc_load:
            try:
                self.dc_load.close()
                self.dc_load = None
                return True, "DC Load disconnected"
            except Exception as e:
                return False, f"DC Load disconnect failed: {e}"
        return True, "DC Load not initialized"

    def _require_dc_load(self):
        if not self.dc_load:
            return False, "DC Load not initialized"
        return True, ""

    def dc_load_enable_input(self, enable=True):
        ok, msg = self._require_dc_load()
        if not ok:
            return False, msg
        try:
            if enable:
                self.dc_load.enable_input()
                return True, "DC Load input ON"
            self.dc_load.disable_input()
            return True, "DC Load input OFF"
        except Exception as e:
            return False, f"DC Load input toggle failed: {e}"

    def dc_load_set_cc(self, current_a):
        ok, msg = self._require_dc_load()
        if not ok:
            return False, msg
        try:
            self.dc_load.set_cc_current(float(current_a))
            self._dc_load_last_mode = "CC"
            self._dc_load_last_value = float(current_a)
            return True, f"DC Load CC set to {current_a} A"
        except Exception as e:
            return False, f"DC Load CC failed: {e}"

    def dc_load_set_cv(self, voltage_v):
        ok, msg = self._require_dc_load()
        if not ok:
            return False, msg
        try:
            self.dc_load.set_cv_voltage(float(voltage_v))
            self._dc_load_last_mode = "CV"
            self._dc_load_last_value = float(voltage_v)
            return True, f"DC Load CV set to {voltage_v} V"
        except Exception as e:
            return False, f"DC Load CV failed: {e}"

    def dc_load_set_cp(self, power_w):
        ok, msg = self._require_dc_load()
        if not ok:
            return False, msg
        try:
            self.dc_load.set_cw_power(float(power_w))
            self._dc_load_last_mode = "CP"
            self._dc_load_last_value = float(power_w)
            return True, f"DC Load CP set to {power_w} W"
        except Exception as e:
            return False, f"DC Load CP failed: {e}"

    def dc_load_set_cr(self, resistance_ohm):
        ok, msg = self._require_dc_load()
        if not ok:
            return False, msg
        try:
            self.dc_load.set_cr_resistance(float(resistance_ohm))
            self._dc_load_last_mode = "CR"
            self._dc_load_last_value = float(resistance_ohm)
            return True, f"DC Load CR set to {resistance_ohm} Ohm"
        except Exception as e:
            return False, f"DC Load CR failed: {e}"

    def dc_load_measure_vi(self):
        ok, msg = self._require_dc_load()
        if not ok:
            return False, msg
        try:
            v, i = self.dc_load.read_voltage_current()
            return True, f"DC Load Meas V={v:.3f} V, I={i:.3f} A"
        except Exception as e:
            return False, f"DC Load measure failed: {e}"

    def dc_load_measure_power(self):
        ok, msg = self._require_dc_load()
        if not ok:
            return False, msg
        try:
            v, i = self.dc_load.read_voltage_current()
            p = v * i
            return True, f"DC Load Power: {p:.3f} W (V={v:.3f} V, I={i:.3f} A)"
        except Exception as e:
            return False, f"DC Load power failed: {e}"

    def dc_load_start_short_circuit(self):
        ok, msg = self._require_dc_load()
        if not ok:
            return False, msg
        if not hasattr(self.dc_load, "start_short_circuit"):
            return False, "DC Load short-circuit mode not supported"
        try:
            self.dc_load.start_short_circuit()
            return True, "DC Load short-circuit mode enabled"
        except Exception as e:
            return False, f"DC Load short-circuit failed: {e}"

    def dc_load_stop_short_circuit(self):
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
            return True, "DC Load short-circuit mode disabled"
        except Exception as e:
            return False, f"DC Load short-circuit stop failed: {e}"

    def dc_load_short_pulse(self, duration_s: float = 0.1):
        ok, msg = self._require_dc_load()
        if not ok:
            return False, msg
        if not hasattr(self.dc_load, "start_short_circuit"):
            return False, "DC Load short-circuit mode not supported"
        try:
            duration = float(duration_s)
        except Exception:
            return False, "Invalid short-circuit duration"
        if duration <= 0:
            return False, "Short-circuit duration must be > 0"
        try:
            self.dc_load.start_short_circuit()
            self.dc_load.enable_input()
            time.sleep(duration)
        except Exception as e:
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
        return True, f"DC Load short-circuit pulse {duration:.3f} s"

    def close_instruments(self):
        if self.itech6000:
            self.itech6000.disconnect()
        if self.siglent:
            self.siglent.disconnect()
        if self.itech7900:
            self.itech7900.disconnect()
        if self.dc_load:
            try:
                self.dc_load.close()
            except Exception:
                pass

    def safe_power_down(self):
        try:
            if self.itech6000:
                try:
                    self.itech6000.power_off()
                except Exception:
                    pass
        except Exception:
            pass
        try:
            if self.itech7900:
                try:
                    self.itech7900.power_off()
                except Exception:
                    pass
        except Exception:
            pass

    def health_report(self):
        report = {}
        if self.itech6000:
            try:
                if not getattr(self.itech6000, "connected", False):
                    report["power_supply"] = HealthStatus(False, "PS not connected")
                else:
                    report["power_supply"] = self.itech6000.health_check()
            except Exception as e:
                report["power_supply"] = HealthStatus(False, f"PS health error: {e}")
        if self.itech7900:
            try:
                if not getattr(self.itech7900, "connected", False):
                    report["grid_emulator"] = HealthStatus(False, "Grid not connected")
                else:
                    report["grid_emulator"] = self.itech7900.health_check()
            except Exception as e:
                report["grid_emulator"] = HealthStatus(False, f"Grid health error: {e}")
        if self.siglent:
            try:
                if not getattr(self.siglent, "connected", False):
                    report["oscilloscope"] = HealthStatus(False, "Scope not connected")
                else:
                    report["oscilloscope"] = self.siglent.health_check()
            except Exception as e:
                report["oscilloscope"] = HealthStatus(False, f"Scope health error: {e}")
        return report
