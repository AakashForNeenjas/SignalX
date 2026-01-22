from core.driver_base import HealthStatus, OscilloscopeDriver
from core.instruments.base import InstrumentDriver


class SiglentSDXScope(InstrumentDriver, OscilloscopeDriver):
    def run(self):
        self.write("TRMD AUTO")

    def stop(self):
        self.write("STOP")

    def get_waveform(self):
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
