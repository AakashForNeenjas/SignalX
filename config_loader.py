import json
import os
from typing import Dict, Any


# Built-in defaults fall back to values from config.py when available.
try:
    from config import CAN_INTERFACE, CAN_CHANNEL, CAN_BITRATE, INSTRUMENT_ADDRESSES
except Exception:
    CAN_INTERFACE = "pcan"
    CAN_CHANNEL = "PCAN_USBBUS1"
    CAN_BITRATE = 500000
    INSTRUMENT_ADDRESSES = {
        "Bi-Directional Power Supply": "TCPIP::192.168.4.53::INSTR",
        "Grid Emulator": "TCPIP::192.168.4.52::INSTR",
        "Oscilloscope": "TCPIP::192.168.4.51::INSTR",
    }


DEFAULT_PROFILES: Dict[str, Dict[str, Any]] = {
    "sim": {
        "description": "Simulation only (no hardware required)",
        "simulation_mode": True,
        "can": {
            "interface": CAN_INTERFACE,
            "channel": CAN_CHANNEL,
            "bitrate": CAN_BITRATE,
        },
        "instruments": INSTRUMENT_ADDRESSES,
        "logging": {"level": "INFO", "file": "app.log", "dir": "logs"},
    },
    "dev": {
        "description": "Development bench settings",
        "simulation_mode": False,
        "can": {
            "interface": CAN_INTERFACE,
            "channel": CAN_CHANNEL,
            "bitrate": CAN_BITRATE,
        },
        "instruments": INSTRUMENT_ADDRESSES,
        "logging": {"level": "INFO", "file": "app.log", "dir": "logs"},
    },
    "hw": {
        "description": "Hardware lab settings (override as needed)",
        "simulation_mode": False,
        "can": {
            "interface": CAN_INTERFACE,
            "channel": CAN_CHANNEL,
            "bitrate": CAN_BITRATE,
        },
        "instruments": INSTRUMENT_ADDRESSES,
        "logging": {"level": "INFO", "file": "app.log", "dir": "logs"},
    },
}


def load_profiles(path: str = os.path.join("config_profiles", "profiles.json")) -> Dict[str, Dict[str, Any]]:
    """
    Load profile definitions from JSON. Falls back to DEFAULT_PROFILES if file is absent or invalid.
    Structure:
    {
      "sim": {"simulation_mode": true, "can": {...}, "instruments": {...}},
      "dev": {...}
    }
    """
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                profiles = json.load(f)
                if isinstance(profiles, dict) and profiles:
                    return profiles
        except Exception:
            # Fall through to defaults on any read/parse error
            pass
    return DEFAULT_PROFILES


def get_profile(name: str, profiles: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Return a profile by name; fall back to the first available."""
    if name in profiles:
        return profiles[name]
    # deterministic fallback
    first = next(iter(profiles.values()))
    return first
