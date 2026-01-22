import time

from core.driver_base import HealthStatus, PowerSupplyDriver
from core.instruments.base import InstrumentDriver, ScpiFloatMixin


class Itech6000Base(InstrumentDriver, ScpiFloatMixin):
    def set_voltage(self, voltage):
        self.write(f"VOLT {voltage}")

    def set_current(self, current):
        self.write(f"CURR {current}")

    def get_voltage(self):
        return self._query_float(["MEAS:VOLT?", "MEAS:VOLT:DC?"])

    def get_current(self):
        return self._query_float(["MEAS:CURR?", "MEAS:CURR:DC?"])

    def get_power(self):
        return self._query_float(["MEAS:POW?", "MEAS:POW:REAL?", "MEAS:POW:ACT?", "MEAS:WATT?"])


class Itech6006PS(Itech6000Base, PowerSupplyDriver):
    """ITECH-6006-C-500-40 (Bi-directional power supply) driver wrapper."""

    def power_on(self):
        self.write("OUTP ON")

    def power_off(self):
        self.write("OUTP OFF")

    def ramp_up_voltage(self, target_voltage, step=1.0, delay=0.5, tolerance=0.5, retries=3):
        current = self.get_voltage()
        if current is None:
            current = 0.0
        if target_voltage < current:
            self.set_voltage(target_voltage)
            return
        v = current
        while v <= target_voltage:
            self.set_voltage(v)
            time.sleep(0.1)
            for _ in range(retries + 1):
                try:
                    meas = self.get_voltage()
                except Exception:
                    meas = v
                if abs(meas - v) <= tolerance:
                    break
                self.set_voltage(v)
                time.sleep(0.1)
            v += abs(step)
            time.sleep(delay)

    def ramp_down_voltage(self, target_voltage, step=1.0, delay=0.5, tolerance=0.5, retries=3):
        current = self.get_voltage()
        if current is None:
            current = 0.0
        if target_voltage > current:
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
                self.set_voltage(v)
                time.sleep(0.1)
            v -= abs(step)
            time.sleep(delay)

    def battery_set_charge(self, voltage, current):
        self.set_voltage(float(voltage))
        self.set_current(float(current))
        self.power_on()
        return True

    def battery_set_discharge(self, voltage, current):
        self.set_voltage(float(voltage))
        self.set_current(float(current))
        self.power_on()
        return True

    def measure_vi(self):
        try:
            v = self.get_voltage()
        except Exception:
            v = 0.0
        try:
            c = self.get_current()
        except Exception:
            c = 0.0
        return v, c

    def measure_power_vi(self):
        v, c = self.measure_vi()
        return v, c, v * c

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
        results = []
        v = float(start)
        end = float(end)
        step = float(step)
        compare = (lambda a, b: a <= b) if v <= end else (lambda a, b: a >= b)
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
        if log_path:
            try:
                import csv
                with open(log_path, "w", newline="") as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(["set_v", "meas_v", "meas_i"])
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
        compare = (lambda a, b: a <= b) if v <= end else (lambda a, b: a >= b)
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
                with open(log_path, "w", newline="") as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(["set_i", "meas_v", "meas_i"])
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
