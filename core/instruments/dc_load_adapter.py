from __future__ import annotations

import importlib
import importlib.util
import os
import sys
from types import ModuleType
from typing import List, Optional, Tuple

try:
    import core.DC_load  # noqa: F401
except Exception:
    pass


class SimDCLoader:
    def __init__(self):
        self.v = 0.0
        self.i = 0.0
        self.short_mode = False

    def open(self):
        pass

    def close(self):
        pass

    def set_remote_control(self, *_):
        pass

    def enable_input(self):
        pass

    def disable_input(self):
        pass

    def start_short_circuit(self):
        self.short_mode = True

    def stop_short_circuit(self):
        self.short_mode = False

    def set_cc_current(self, current_a):
        self.i = float(current_a)

    def set_cv_voltage(self, voltage_v):
        self.v = float(voltage_v)

    def set_cw_power(self, power_w):
        power_w = float(power_w)
        self.v = power_w ** 0.5
        self.i = power_w ** 0.5

    def set_cr_resistance(self, resistance_ohm):
        resistance_ohm = float(resistance_ohm)
        self.i = self.v / resistance_ohm if resistance_ohm else 0.0

    def read_voltage_current(self):
        return self.v, self.i


def _resolve_driver_path() -> str:
    core_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    module_path = os.path.join(core_dir, "DC_load")
    if not os.path.exists(module_path) and os.path.exists(module_path + ".py"):
        module_path = module_path + ".py"
    return module_path


def _load_dc_driver(module_path: Optional[str] = None) -> ModuleType:
    try:
        return importlib.import_module("core.DC_load")
    except Exception:
        pass
    module_path = module_path or _resolve_driver_path()
    # If running from PyInstaller, look inside the extracted bundle.
    if not os.path.exists(module_path) and hasattr(sys, "_MEIPASS"):
        bundled = os.path.join(sys._MEIPASS, "core", "DC_load.py")
        if os.path.exists(bundled):
            module_path = bundled
    spec = importlib.util.spec_from_file_location("core.dc_load_dynamic", module_path)
    if spec is None or spec.loader is None:
        raise ImportError("Cannot load DC_load driver file")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore
    return module


def _discover_ports() -> List[str]:
    ports = []
    try:
        import serial.tools.list_ports as lp
        for p in lp.comports():
            ports.append(p.device)
    except Exception:
        pass
    return ports


def connect_dc_load(
    simulation_mode: bool,
    addresses: Optional[dict] = None,
    port: Optional[str] = None,
    slave_addr: int = 1,
    baudrate: int = 9600,
    timeout: float = 0.3,
    parity: str = "N",
) -> Tuple[Optional[object], str]:
    if simulation_mode:
        return SimDCLoader(), "DC Load connected (simulation)"

    candidates: List[str] = []
    if port:
        candidates.append(port)
    cfg_port = None
    if addresses:
        cfg_port = addresses.get("DC Load")
    if cfg_port and cfg_port not in candidates:
        candidates.append(cfg_port)
    for detected in _discover_ports():
        if detected not in candidates:
            candidates.append(detected)

    try:
        module = _load_dc_driver()
    except Exception as exc:
        return None, f"DC Load driver load failed: {exc}"
    errors = []
    for addr in candidates:
        inst = None
        try:
            inst = module.MaynuoM97(
                port=addr,
                slave_addr=slave_addr,
                baudrate=baudrate,
                timeout=timeout,
                parity=parity,
            )
            inst.open()
            try:
                inst.set_remote_control(True)
            except Exception:
                pass
            return inst, f"DC Load connected on {addr}"
        except Exception as e:
            errors.append(f"{addr}: {e}")
            try:
                if inst:
                    inst.close()
            except Exception:
                pass
    return None, f"DC Load connect failed; tried {candidates}. Errors: {errors}"


def is_dc_load_connected(load) -> bool:
    if not load:
        return False
    ser = getattr(load, "ser", None)
    if ser is None:
        return True
    return bool(getattr(ser, "is_open", False))
