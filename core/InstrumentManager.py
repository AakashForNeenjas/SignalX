import pyvisa
import time
import random
import sys
import os
from core.driver_base import PowerSupplyDriver, GridEmulatorDriver, OscilloscopeDriver, HealthStatus

# Add parent directory to path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from config import INSTRUMENT_ADDRESSES
except ImportError:
    # Fallback if config not found
    INSTRUMENT_ADDRESSES = {
        'Bi-Directional Power Supply': 'TCPIP::192.168.4.53::INSTR',
        'Grid Emulator': 'TCPIP::192.168.4.52::INSTR',
        'Oscilloscope': 'TCPIP::192.168.4.51::INSTR'
    }

class InstrumentDriver:
    def __init__(self, resource_name, simulation_mode=False):
        self.resource_name = resource_name
        self.simulation_mode = simulation_mode
        self.inst = None
        self.connected = False

    def connect(self):
        if self.simulation_mode:
            print(f"SIMULATION: Connected to {self.resource_name}")
            self.connected = True
            return True, "Connected (Simulation)"
        
        try:
            rm = pyvisa.ResourceManager()
            self.inst = rm.open_resource(self.resource_name)
            self.connected = True
            return True, "Connected"
        except Exception as e:
            msg = f"Error connecting to {self.resource_name}: {e}"
            print(msg)
            return False, msg

    def disconnect(self):
        if self.simulation_mode:
            self.connected = False
            return
        
        if self.inst:
            try:
                self.inst.close()
            except:
                pass
        self.connected = False

    def write(self, command):
        if self.simulation_mode:
            print(f"SIMULATION {self.resource_name} WRITE: {command}")
            return
        if self.inst:
            self.inst.write(command)

    def query(self, command):
        if self.simulation_mode:
            print(f"SIMULATION {self.resource_name} QUERY: {command}")
            return "0.0" # Default simulation response
        if self.inst:
            return self.inst.query(command)
        return ""

class ITECH6000(InstrumentDriver):
    def set_voltage(self, voltage):
        self.write(f"VOLT {voltage}")

    def set_current(self, current):
        self.write(f"CURR {current}")

    def get_voltage(self):
        return float(self.query("MEAS:VOLT?"))

    def get_current(self):
        return float(self.query("MEAS:CURR?"))


class ITECH6006(ITECH6000, PowerSupplyDriver):
    """Driver wrapper for ITECH-6006-C-500-40 (Bi-directional power supply)
    Implements commands for set/get voltage/current, output control, basic ramping and simple sweep logging.
    """
    def set_voltage(self, voltage):
        # Many ITECH instruments accept 'VOLT' command
        self.write(f"VOLT {voltage}")

    def set_current(self, current):
        # Set current limit
        self.write(f"CURR {current}")

    def get_voltage(self):
        return float(self.query("MEAS:VOLT?"))

    def get_current(self):
        return float(self.query("MEAS:CURR?"))

    def power_on(self):
        self.write("OUTP ON")

    def power_off(self):
        self.write("OUTP OFF")

    def ramp_up_voltage(self, target_voltage, step=1.0, delay=0.5, tolerance=0.5, retries=3):
        # Simple ramp loop implemented by repeatedly setting voltages and verifying measurement
        current = self.get_voltage()
        if current is None:
            current = 0.0
        if target_voltage < current:
            # Can't ramp up to smaller value
            self.set_voltage(target_voltage)
            return
        v = current
        while v <= target_voltage:
            self.set_voltage(v)
            time.sleep(0.1)
            # Verify measurement
            for _ in range(retries + 1):
                try:
                    meas = self.get_voltage()
                except Exception:
                    meas = v
                if abs(meas - v) <= tolerance:
                    break
                else:
                    # reissue
                    self.set_voltage(v)
                    time.sleep(0.1)
            v += abs(step)
            time.sleep(delay)

    def ramp_down_voltage(self, target_voltage, step=1.0, delay=0.5, tolerance=0.5, retries=3):
        current = self.get_voltage()
        if current is None:
            current = 0.0
        if target_voltage > current:
            # If target greater than current, just set value
            self.set_voltage(target_voltage)
            return
        v = current
        while v >= target_voltage:
            self.set_voltage(v)
            time.sleep(0.1)
            for _ in range(retries + 1):
                try:
                    meas = self.get_voltage()
                except Exception:
                    meas = v
                if abs(meas - v) <= tolerance:
                    break
                else:
                    self.set_voltage(v)
                    time.sleep(0.1)
            v -= abs(step)
            time.sleep(delay)

    def battery_set_charge(self, voltage, current):
        # Set voltage and current suitable for charging, then turn on output
        self.set_voltage(float(voltage))
        self.set_current(float(current))
        self.power_on()
        return True

    def battery_set_discharge(self, voltage, current):
        # For discharge mode, the instrument may need to be reversed; we model with similar commands.
        self.set_voltage(float(voltage))
        self.set_current(float(current))
        self.power_on()
        return True

    def measure_vi(self):
        # Measure voltage and current; return tuple
        try:
            v = self.get_voltage()
        except Exception:
            v = 0.0
        try:
            c = self.get_current()
        except Exception:
            c = 0.0
        return v, c

    def read_errors(self):
        try:
            return self.query("SYST:ERR?")
        except Exception:
            return ""

    def clear_errors(self):
        try:
            self.write("SYST:ERR:CLEAR")
        except Exception:
            pass

    def sweep_voltage_and_log(self, start, step, end, delay=0.5, log_path=None):
        # Sweep voltage and write CSV to log_path
        results = []
        v = float(start)
        end = float(end)
        step = float(step)
        # Determine direction
        if v <= end:
            compare = lambda a, b: a <= b
        else:
            compare = lambda a, b: a >= b
        while compare(v, end):
            self.set_voltage(v)
            time.sleep(delay)
            try:
                meas_v = self.get_voltage()
                meas_c = self.get_current()
            except Exception:
                meas_v = v
                meas_c = 0.0
            results.append((v, meas_v, meas_c))
            v = v + step if start < end else v - step
        # Optionally write CSV
        if log_path:
            try:
                import csv
                with open(log_path, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['set_v', 'meas_v', 'meas_i'])
                    for row in results:
                        writer.writerow(row)
            except Exception:
                pass
        return results

    def sweep_current_and_log(self, start, step, end, delay=0.5, log_path=None):
        results = []
        v = float(start)
        end = float(end)
        step = float(step)
        if v <= end:
            compare = lambda a, b: a <= b
        else:
            compare = lambda a, b: a >= b
        while compare(v, end):
            self.set_current(v)
            time.sleep(delay)
            try:
                meas_v = self.get_voltage()
                meas_c = self.get_current()
            except Exception:
                meas_v = 0.0
                meas_c = v
            results.append((v, meas_v, meas_c))
            v = v + step if start < end else v - step
        if log_path:
            try:
                import csv
                with open(log_path, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['set_i', 'meas_v', 'meas_i'])
                    for row in results:
                        writer.writerow(row)
            except Exception:
                pass
        return results

    def health_check(self):
        try:
            v = self.get_voltage()
            c = self.get_current()
            return HealthStatus(True, f"PS OK (V={v}, I={c})")
        except Exception as e:
            return HealthStatus(False, f"PS health failed: {e}")

class SiglentSDX(InstrumentDriver, OscilloscopeDriver):
    def run(self):
        self.write("TRMD AUTO") # Example command

    def stop(self):
        self.write("STOP")

    def get_waveform(self):
        # In real implementation, this would read binary data
        return self.query("C1:WF? DAT2")

    def health_check(self):
        if not self.connected:
            return HealthStatus(False, "Scope not connected")
        try:
            resp = self.query("*IDN?")
            if not resp:
                return HealthStatus(False, "Scope query returned empty IDN")
            return HealthStatus(True, f"Scope OK: {resp}")
        except Exception as e:
            return HealthStatus(False, f"Scope health failed: {e}")

class ITECH7900(InstrumentDriver, GridEmulatorDriver):
    def set_grid_voltage(self, voltage):
        self.write(f"VOLT {voltage}")

    def set_grid_frequency(self, freq):
        self.write(f"FREQ {freq}")

    def get_grid_voltage(self):
        return float(self.query("MEAS:VOLT?"))

    def get_grid_frequency(self):
        try:
            return float(self.query("MEAS:FREQ?"))
        except Exception:
            return 0.0

    def set_grid_current(self, current):
        """Set grid current (supports AC/DC depending on device config)"""
        self.write(f"CURR {current}")

    def get_grid_current(self):
        try:
            return float(self.query("MEAS:CURR?"))
        except Exception:
            return 0.0

    def measure_power_real(self):
        try:
            return float(self.query("MEAS:POW:REAL?"))
        except Exception:
            return 0.0

    def measure_power_reactive(self):
        try:
            return float(self.query("MEAS:POW:REAC?"))
        except Exception:
            return 0.0

    def measure_power_apparent(self):
        try:
            return float(self.query("MEAS:POW:APP?"))
        except Exception:
            return 0.0

    def measure_thd_current(self):
        try:
            return float(self.query("MEAS:CURR:HARMonic:THD?"))
        except Exception:
            return 0.0

    def measure_thd_voltage(self):
        try:
            return float(self.query("MEAS:VOLT:HARMonic:THD?"))
        except Exception:
            return 0.0

    def power_on(self):
        self.write("OUTP ON")

    def power_off(self):
        self.write("OUTP OFF")

    def health_check(self):
        try:
            v = self.get_grid_voltage()
            i = self.get_grid_current()
            return HealthStatus(True, f"Grid OK (V={v}, I={i})")
        except Exception as e:
            return HealthStatus(False, f"Grid health failed: {e}")

    def ramp_up_voltage(self, target_voltage, rate=None):
        # Some instruments support a ramp or slope API; simulate by setting voltage
        if rate:
            self.write(f"VOLT:RAMP:RATE {rate}")
        self.write(f"VOLT {target_voltage}")

    def ramp_down_voltage(self, target_voltage, rate=None):
        if rate:
            self.write(f"VOLT:RAMP:RATE {rate}")
        self.write(f"VOLT {target_voltage}")

    def reset_system(self):
        try:
            self.write("*RST")
        except Exception:
            pass

class InstrumentManager:
    def __init__(self, simulation_mode=True, config=None):
        self.simulation_mode = simulation_mode
        self.itech6000 = None
        self.siglent = None
        self.itech7900 = None
        # Allow callers to inject addresses per profile
        self.addresses = config if config else INSTRUMENT_ADDRESSES

    def initialize_instruments(self):
        # Load addresses from config
        addr_ps = self.addresses.get('Bi-Directional Power Supply', "TCPIP::192.168.4.53::INSTR")
        addr_scope = self.addresses.get('Oscilloscope', "TCPIP::192.168.4.51::INSTR")
        addr_grid = self.addresses.get('Grid Emulator', "TCPIP::192.168.4.52::INSTR")

        self.itech6000 = ITECH6006(addr_ps, self.simulation_mode)
        self.siglent = SiglentSDX(addr_scope, self.simulation_mode)
        self.itech7900 = ITECH7900(addr_grid, self.simulation_mode)
        
        messages = []
        success = True
        
        s, m = self.itech6000.connect()
        if not s:
            success = False
            messages.append(f"Bi-Directional Power Supply Error: {m}")
        else:
            messages.append(f"Bi-Directional Power Supply: {m}")
        
        s, m = self.siglent.connect()
        if not s:
            success = False
            messages.append(f"Oscilloscope Error: {m}")
        else:
            messages.append(f"Oscilloscope: {m}")
        
        s, m = self.itech7900.connect()
        if not s:
            success = False
            messages.append(f"Grid Emulator Error: {m}")
        else:
            messages.append(f"Grid Emulator: {m}")
        
        return success, "\n".join(messages)

    def close_instruments(self):
        if self.itech6000: self.itech6000.disconnect()
        if self.siglent: self.siglent.disconnect()
        if self.itech7900: self.itech7900.disconnect()

    def safe_power_down(self):
        """Attempt to power down PS and Grid gracefully."""
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
        """Return health status for all instruments."""
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
