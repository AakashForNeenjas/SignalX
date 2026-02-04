# AtomX Configuration File
#
# Configuration values can be overridden using environment variables.
# Environment variable names use the format: ATOMX_<CONFIG_NAME>
# Example: ATOMX_CAN_INTERFACE=pcan
#
# For sensitive values like IP addresses, prefer using environment variables
# or the config_profiles/profiles.json file instead of hardcoding here.

import os


def _get_env(name, default):
    """Get configuration value from environment variable or use default."""
    return os.environ.get(f"ATOMX_{name}", default)


def _get_env_int(name, default):
    """Get integer configuration value from environment variable."""
    value = os.environ.get(f"ATOMX_{name}")
    if value is not None:
        try:
            return int(value)
        except ValueError:
            pass
    return default


def _get_env_float(name, default):
    """Get float configuration value from environment variable."""
    value = os.environ.get(f"ATOMX_{name}")
    if value is not None:
        try:
            return float(value)
        except ValueError:
            pass
    return default


def _get_env_bool(name, default):
    """Get boolean configuration value from environment variable."""
    value = os.environ.get(f"ATOMX_{name}")
    if value is not None:
        return value.lower() in ("true", "1", "yes", "on")
    return default


# CAN Configuration
CAN_INTERFACE = _get_env("CAN_INTERFACE", "pcan")
CAN_CHANNEL = _get_env("CAN_CHANNEL", "PCAN_USBBUS1")
CAN_BITRATE = _get_env_int("CAN_BITRATE", 500000)

# Cyclic CAN Messages Configuration
# Format: {message_id: {'data': [bytes], 'cycle_time': seconds}}
CYCLIC_CAN_MESSAGES = {
    0x100: {
        'data': [0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08],
        'cycle_time': 0.1  # 100ms
    },
    0x200: {
        'data': [0x10, 0x20, 0x30, 0x40, 0x50, 0x60, 0x70, 0x80],
        'cycle_time': 0.05  # 50ms
    },
    # Add more cyclic messages here as needed
}

# Instrument Configuration
# SECURITY NOTE: These are default addresses. For production deployments,
# use environment variables or config_profiles/profiles.json to configure
# actual instrument addresses.
#
# Environment variables:
#   ATOMX_PS_ADDRESS - Bi-Directional Power Supply VISA address
#   ATOMX_GS_ADDRESS - Grid Emulator VISA address
#   ATOMX_OSC_ADDRESS - Oscilloscope VISA address
#   ATOMX_DCLOAD_PORT - DC Load serial port
INSTRUMENT_ADDRESSES = {
    'Bi-Directional Power Supply': _get_env("PS_ADDRESS", "TCPIP::192.168.4.53::INSTR"),
    'Grid Emulator': _get_env("GS_ADDRESS", "TCPIP::192.168.4.52::INSTR"),
    'Oscilloscope': _get_env("OSC_ADDRESS", "TCPIP::192.168.4.51::INSTR"),
    'DC Load': _get_env("DCLOAD_PORT", "COM3")
}

# GitHub Releases updater configuration
# Set UPDATE_GITHUB_REPO to empty string to disable update checking
UPDATE_GITHUB_REPO = _get_env("UPDATE_GITHUB_REPO", "AakashForNeenjas/SignalX")
UPDATE_GITHUB_ASSET = _get_env("UPDATE_GITHUB_ASSET", "AtomX.zip")
UPDATE_GITHUB_INCLUDE_PRERELEASE = _get_env_bool("UPDATE_GITHUB_INCLUDE_PRERELEASE", False)

# Instrument initialization controls
INSTRUMENT_INIT_TIMEOUT_S = _get_env_float("INSTRUMENT_INIT_TIMEOUT_S", 5.0)
INSTRUMENT_INIT_RETRIES = _get_env_int("INSTRUMENT_INIT_RETRIES", 2)

# Standards (JSON) file shown in the Standards tab
STANDARDS_JSON = _get_env("STANDARDS_JSON", r"docs/Charger_Standard.json")
