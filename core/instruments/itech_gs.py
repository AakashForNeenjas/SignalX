from core.driver_base import GridEmulatorDriver, HealthStatus
from core.instruments.base import InstrumentDriver, ScpiFloatMixin, ScpiWriteMixin


class Itech7900Grid(InstrumentDriver, GridEmulatorDriver, ScpiFloatMixin, ScpiWriteMixin):
    def set_grid_voltage(self, voltage):
        v = float(voltage)
        self._write_any([
            f"VOLT {v}",
            f"VOLT:AC {v}",
            f"SOUR:VOLT {v}",
            f"SOUR:VOLT:AC {v}",
        ])

    def set_grid_frequency(self, freq):
        f = float(freq)
        self._write_any([
            f"FREQ {f}",
            f"FREQ:AC {f}",
            f"SOUR:FREQ {f}",
            f"SOUR:FREQ:AC {f}",
        ])

    def get_grid_voltage(self):
        return self._query_float([
            "MEAS:VOLT?",
            "MEAS:VOLT:AC?",
            "MEAS:VOLT:DC?",
            "VOLT?",
            "SOUR:VOLT?",
            "SOUR:VOLT:AC?",
        ])

    def get_grid_frequency(self):
        return self._query_float([
            "MEAS:FREQ?",
            "MEAS:VOLT:FREQ?",
            "FREQ?",
            "SOUR:FREQ?",
            "SOUR:FREQ:AC?",
        ])

    def set_grid_current(self, current):
        self.write(f"CURR {current}")

    def get_grid_current(self):
        return self._query_float(["MEAS:CURR?", "MEAS:CURR:AC?", "MEAS:CURR:DC?"])

    def measure_power_real(self):
        return self._query_float(["MEAS:POW:REAL?", "MEAS:POW:ACT?", "MEAS:POW?"])

    def measure_power_reactive(self):
        return self._query_float(["MEAS:POW:REAC?", "MEAS:POW:REActive?"])

    def measure_power_apparent(self):
        return self._query_float(["MEAS:POW:APP?", "MEAS:POW:APPARENT?"])

    def measure_power_factor(self):
        try:
            return self._query_float(["MEAS:POW:PF?", "MEAS:PF?"])
        except Exception:
            real = self.measure_power_real()
            apparent = self.measure_power_apparent()
            if apparent in (None, 0):
                return 0.0
            return real / apparent

    def measure_thd_current(self):
        return self._query_float(["MEAS:CURR:HARMonic:THD?", "MEAS:CURR:THD?"])

    def measure_thd_voltage(self):
        return self._query_float(["MEAS:VOLT:HARMonic:THD?", "MEAS:VOLT:THD?"])

    def clear_errors(self):
        try:
            self._write_any([
                "SYST:ERR:CLEAR",
                "STAT:CLE",
                "*CLS",
            ])
        except Exception:
            pass

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
