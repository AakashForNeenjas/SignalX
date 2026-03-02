import logging
from typing import Optional, Tuple, Any

from core.driver_base import HealthStatus, OscilloscopeDriver
from core.instruments.Oscilloscope import SiglentSDS1104XU

logger = logging.getLogger(__name__)


class SiglentSDXScope(OscilloscopeDriver):
    """
    Adapter for the new SiglentSDS1104XU driver to the app's oscilloscope API.

    This replaces the old minimal driver and routes all I/O through the
    full-featured implementation in core/instruments/Oscilloscope.py.
    """

    def __init__(self, resource_name: str, simulation_mode: bool = False):
        self.resource_name = resource_name
        self.simulation_mode = simulation_mode
        self.connected = False
        self._driver: Optional[SiglentSDS1104XU] = None

    def _parse_tcpip_ip(self, resource_name: str) -> Optional[str]:
        if not resource_name:
            return None
        if not resource_name.upper().startswith("TCPIP"):
            return None
        # Example: TCPIP::192.168.4.51::INSTR
        parts = resource_name.split("::")
        if len(parts) >= 2:
            return parts[1]
        return None

    def _parse_tcpip_port(self, resource_name: str) -> Optional[int]:
        if not resource_name:
            return None
        if not resource_name.upper().startswith("TCPIP"):
            return None
        parts = resource_name.split("::")
        for part in parts:
            if part.isdigit():
                try:
                    return int(part)
                except ValueError:
                    continue
        return None

    def connect(self) -> Tuple[bool, str]:
        if self.simulation_mode:
            logger.info("SIMULATION: Oscilloscope connected")
            self.connected = True
            return True, "Connected (Simulation)"

        try:
            ip = self._parse_tcpip_ip(self.resource_name)
            port = self._parse_tcpip_port(self.resource_name)
            if self.resource_name.upper().startswith("USB"):
                self._driver = SiglentSDS1104XU(interface="usb", resource=self.resource_name)
            elif ip:
                # Prefer raw socket to avoid VISA dependency when possible.
                try:
                    if port:
                        self._driver = SiglentSDS1104XU(interface="lan", ip=ip, port=port, lan_mode="socket")
                    else:
                        self._driver = SiglentSDS1104XU(interface="lan", ip=ip, lan_mode="socket")
                    idn = self._driver.connect()
                    self.connected = True
                    return True, f"Connected: {idn}"
                except Exception as sock_exc:
                    logger.warning(f"Scope socket connect failed, trying VISA: {sock_exc}")
                    self._driver = SiglentSDS1104XU(interface="lan", lan_mode="visa", resource=self.resource_name, ip=ip)
            else:
                # Fallback: try VISA resource string if provided
                self._driver = SiglentSDS1104XU(interface="lan", lan_mode="visa", resource=self.resource_name)

            idn = self._driver.connect()
            self.connected = True
            return True, f"Connected: {idn}"
        except Exception as exc:
            self.connected = False
            self._driver = None
            msg = f"Error connecting to {self.resource_name}: {exc}"
            logger.error(msg)
            return False, msg

    def disconnect(self) -> None:
        if self.simulation_mode:
            self.connected = False
            return
        try:
            if self._driver:
                self._driver.disconnect()
        finally:
            self._driver = None
            self.connected = False

    def write(self, cmd: str) -> None:
        if self.simulation_mode:
            logger.debug(f"SIMULATION Oscilloscope WRITE: {cmd}")
            return
        if not self._driver:
            raise RuntimeError("Oscilloscope not connected")
        self._driver.write(cmd)

    def query(self, cmd: str, default: str = "0.0") -> Any:
        if self.simulation_mode:
            logger.debug(f"SIMULATION Oscilloscope QUERY: {cmd}")
            return default
        if not self._driver:
            raise RuntimeError("Oscilloscope not connected")
        # Special-case screenshot command to return raw bytes.
        if cmd.strip().upper() in ("SCDP?", "SCDP"):
            # Driver expects "SCDP" (no ?). Accept both.
            return self._driver.query_raw("SCDP")
        return self._driver.query(cmd)

    def run(self) -> None:
        if self.simulation_mode:
            logger.debug("SIMULATION Oscilloscope RUN")
            return
        if not self._driver:
            raise RuntimeError("Oscilloscope not connected")
        self._driver.run()

    def stop(self) -> None:
        if self.simulation_mode:
            logger.debug("SIMULATION Oscilloscope STOP")
            return
        if not self._driver:
            raise RuntimeError("Oscilloscope not connected")
        self._driver.stop()

    def get_waveform(self):
        """
        Returns waveform samples (voltage array) for CH1 by default,
        matching legacy behavior where only length was used.
        """
        if self.simulation_mode:
            return []
        if not self._driver:
            raise RuntimeError("Oscilloscope not connected")
        _, v = self._driver.get_waveform(1)
        return v

    def screenshot(self, filename: str = "screenshot.bmp") -> str:
        if self.simulation_mode:
            logger.debug(f"SIMULATION Oscilloscope SCREENSHOT: {filename}")
            # Create an empty placeholder to keep downstream steps happy.
            try:
                with open(filename, "wb") as f:
                    f.write(b"")
            except Exception:
                pass
            return filename
        if not self._driver:
            raise RuntimeError("Oscilloscope not connected")
        return self._driver.screenshot(filename)

    def screenshot_png(self, filename: str = "screenshot.png") -> str:
        if self.simulation_mode:
            logger.debug(f"SIMULATION Oscilloscope SCREENSHOT PNG: {filename}")
            try:
                with open(filename, "wb") as f:
                    f.write(b"")
            except Exception:
                pass
            return filename
        if not self._driver:
            raise RuntimeError("Oscilloscope not connected")
        return self._driver.screenshot_png(filename)

    def health_check(self) -> HealthStatus:
        if not self.connected or not self._driver:
            return HealthStatus(False, "Scope not connected")
        try:
            resp = self._driver.idn()
            if not resp:
                return HealthStatus(False, "Scope query returned empty IDN")
            return HealthStatus(True, f"Scope OK: {resp}")
        except Exception as exc:
            return HealthStatus(False, f"Scope health failed: {exc}")
