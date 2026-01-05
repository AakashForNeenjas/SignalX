# AtomX Configuration File

# CAN Configuration
CAN_INTERFACE = 'pcan'
CAN_CHANNEL = 'PCAN_USBBUS1'
CAN_BITRATE = 500000

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
INSTRUMENT_ADDRESSES = {
    'Bi-Directional Power Supply': 'TCPIP::192.168.4.53::INSTR',  # ITECH6000
    'Grid Emulator': 'TCPIP::192.168.4.52::INSTR',            # ITECH7900
    'Oscilloscope': 'TCPIP::192.168.4.51::INSTR',             # SiglentSDX
    # DC Electronic Load (Maynuo M97 series) via RS-232/USB
    'DC Load': 'COM3'
}

# Optional update manifest location (JSON with version/url/sha256)
# Example: UPDATE_MANIFEST_URL = "https://example.com/atomx/latest.json"
UPDATE_MANIFEST_URL = ""

# Standards (JSON) file shown in the Standards tab
STANDARDS_JSON = r"docs/Charger_Standard.json"
