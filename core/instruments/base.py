import logging
import re

logger = logging.getLogger(__name__)

try:
    import pyvisa
except ImportError as _visa_exc:
    pyvisa = None
    _visa_import_error = _visa_exc
else:
    _visa_import_error = None

try:
    import pyvisa_py  # type: ignore
except ImportError:
    pyvisa_py = None


class InstrumentDriver:
    def __init__(self, resource_name, simulation_mode=False):
        self.resource_name = resource_name
        self.simulation_mode = simulation_mode
        self.inst = None
        self.connected = False

    def connect(self):
        """
        Connect to the instrument using VISA.

        Returns:
            tuple: (success: bool, message: str)
        """
        if self.simulation_mode:
            logger.info(f"SIMULATION: Connected to {self.resource_name}")
            self.connected = True
            return True, "Connected (Simulation)"

        try:
            if pyvisa is None:
                raise ImportError(f"PyVISA not available: {_visa_import_error}")

            resource_names = self._candidate_resource_names(self.resource_name)
            rms = []

            # Try default ResourceManager
            try:
                rms.append(("default", pyvisa.ResourceManager()))
            except Exception as e:
                logger.debug(f"Default ResourceManager failed: {e}")
                rms.append(("default_error", e))

            # Try pyvisa-py backend if available
            if pyvisa_py is not None:
                try:
                    rms.append(("py", pyvisa.ResourceManager("@py")))
                except Exception as e:
                    logger.debug(f"pyvisa-py ResourceManager failed: {e}")
                    rms.append(("py_error", e))

            errors = []
            for label, rm in rms:
                if isinstance(rm, Exception):
                    errors.append(f"{label} ResourceManager failed: {rm}")
                    continue
                for res in resource_names:
                    try:
                        self.inst = rm.open_resource(res)
                        self.connected = True
                        logger.info(f"Connected to {res} using {label} backend")
                        return True, f"Connected ({label})"
                    except Exception as e:
                        errors.append(f"{label} {res}: {e}")

            # All connection attempts failed
            msg = " | ".join(errors)
            raise RuntimeError(msg)

        except Exception as e:
            hint = "Install NI-VISA Runtime or pyvisa-py and set PYVISA_LIBRARY if needed."
            msg = f"Error connecting to {self.resource_name}: {e}. {hint}"
            logger.error(msg)
            return False, msg

    @staticmethod
    def _candidate_resource_names(resource_name):
        names = [resource_name]
        if resource_name.upper().startswith("TCPIP::"):
            parts = resource_name.split("::")
            if len(parts) >= 2:
                ip = parts[1]
                alt = [
                    f"TCPIP0::{ip}::INSTR",
                    f"TCPIP0::{ip}::inst0::INSTR",
                    f"TCPIP::{ip}::inst0::INSTR",
                ]
                for a in alt:
                    if a not in names:
                        names.append(a)
        return names

    def disconnect(self):
        """Disconnect from the instrument and release resources."""
        if self.simulation_mode:
            self.connected = False
            return

        if self.inst:
            try:
                self.inst.close()
            except Exception as e:
                logger.warning(f"Error closing instrument connection: {e}")
            finally:
                self.inst = None
        self.connected = False

    def write(self, command):
        """Send a command to the instrument."""
        if self.simulation_mode:
            logger.debug(f"SIMULATION {self.resource_name} WRITE: {command}")
            return
        if not self.inst:
            raise RuntimeError("Instrument not connected")
        self.inst.write(command)

    def query(self, command, default="0.0"):
        """Send a query to the instrument and return the response."""
        if self.simulation_mode:
            logger.debug(f"SIMULATION {self.resource_name} QUERY: {command}")
            return default
        if not self.inst:
            raise RuntimeError("Instrument not connected")
        return self.inst.query(command)


class ScpiFloatMixin:
    def _parse_float(self, resp):
        if resp is None:
            raise ValueError("Empty response")
        if isinstance(resp, (int, float)):
            return float(resp)
        text = str(resp).strip()
        match = re.search(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", text)
        if not match:
            raise ValueError(f"Non-numeric response: {text}")
        return float(match.group(0))

    def _query_float(self, commands):
        if isinstance(commands, str):
            commands = [commands]
        last_err = None
        for cmd in commands:
            try:
                resp = self.query(cmd)
                return self._parse_float(resp)
            except Exception as e:
                last_err = e
                continue
        if last_err:
            raise last_err
        raise ValueError("No response")


class ScpiWriteMixin:
    def _write_any(self, commands):
        """Write command, trying multiple variants until one succeeds."""
        if isinstance(commands, str):
            commands = [commands]
        last_err = None
        for cmd in commands:
            try:
                self.write(cmd)
                if not getattr(self, "simulation_mode", False):
                    try:
                        err = self.query("SYST:ERR?")
                        err_text = str(err).strip() if err is not None else ""
                        if err_text:
                            upper = err_text.upper()
                            if upper.startswith("0") or "NO ERROR" in upper:
                                return
                            if "INVALID COMMAND" in upper or "170" in upper:
                                return
                            last_err = ValueError(f"SYST:ERR? {err_text}")
                            continue
                    except Exception as e:
                        logger.debug(f"Error checking SYST:ERR?: {e}")
                return
            except Exception as e:
                last_err = e
                continue
        if last_err:
            raise last_err
        raise ValueError("No write command provided")
