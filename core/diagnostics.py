import os
import sys
from typing import Dict, Any, List, Tuple


def _try_import(name: str):
    try:
        module = __import__(name)
        return True, getattr(module, "__version__", "")
    except Exception as exc:
        return False, str(exc)


def _list_serial_ports() -> Tuple[bool, str]:
    try:
        import serial.tools.list_ports as lp
        ports = [p.device for p in lp.comports()]
        return True, ", ".join(ports) if ports else "No serial ports detected"
    except Exception as exc:
        return False, str(exc)


def _visa_backend_status() -> List[Tuple[str, str, str]]:
    rows: List[Tuple[str, str, str]] = []
    ok, info = _try_import("pyvisa")
    rows.append(("PyVISA import", "OK" if ok else "Missing", info))

    ok_py, info_py = _try_import("pyvisa_py")
    rows.append(("pyvisa-py backend", "OK" if ok_py else "Missing", info_py))

    try:
        import pyvisa
        try:
            rm = pyvisa.ResourceManager()
            try:
                resources = rm.list_resources()
                rows.append(("VISA resources", "OK", ", ".join(resources) if resources else "None"))
            except Exception as exc:
                rows.append(("VISA resources", "Warn", str(exc)))
        except Exception as exc:
            rows.append(("VISA ResourceManager", "Fail", str(exc)))
    except Exception:
        pass

    library = os.environ.get("PYVISA_LIBRARY")
    rows.append(("PYVISA_LIBRARY", "Set" if library else "Unset", library or ""))
    return rows


def _can_backend_status() -> List[Tuple[str, str, str]]:
    rows: List[Tuple[str, str, str]] = []
    ok, info = _try_import("can")
    rows.append(("python-can import", "OK" if ok else "Missing", info))
    ok_pcan, info_pcan = _try_import("can.interfaces.pcan")
    rows.append(("PCAN backend", "OK" if ok_pcan else "Missing", info_pcan))
    return rows


def _dc_load_status() -> List[Tuple[str, str, str]]:
    rows: List[Tuple[str, str, str]] = []
    ok, info = _try_import("core.DC_load")
    rows.append(("DC Load driver", "OK" if ok else "Missing", info))
    return rows


def collect_diagnostics(profile_name: str, profile: Dict[str, Any]) -> List[Tuple[str, str, str]]:
    rows: List[Tuple[str, str, str]] = []
    rows.append(("App mode", "OK", "Frozen EXE" if getattr(sys, "frozen", False) else "Python"))
    rows.append(("Active profile", "OK", profile_name))

    can_cfg = profile.get("can", {})
    rows.append(("CAN interface", "OK", str(can_cfg.get("interface"))))
    rows.append(("CAN channel", "OK", str(can_cfg.get("channel"))))
    rows.append(("CAN bitrate", "OK", str(can_cfg.get("bitrate"))))

    inst_cfg = profile.get("instruments", {})
    for key, val in inst_cfg.items():
        rows.append((f"Instrument: {key}", "OK", str(val)))

    rows.extend(_visa_backend_status())
    rows.extend(_can_backend_status())
    rows.extend(_dc_load_status())

    ok_ports, info_ports = _list_serial_ports()
    rows.append(("Serial ports", "OK" if ok_ports else "Missing", info_ports))
    return rows
