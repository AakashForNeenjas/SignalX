"""
=========================================================
RAPTOR RS485 ADDRESS DETECTION SCRIPT
=========================================================

What it does:
- Scans RS485 addresses
- Sends READ VERSION command (Function 0x06)
- Detects which address responds correctly

Safe:
- Read-only command
- No control / no write
- Suitable for production devices

Requirements:
    pip install pyserial
=========================================================
"""

import time
import serial
import serial.tools.list_ports

# =========================
# USER CONFIG
# =========================
PORT = "COM3"          # <-- CHANGE to your actual COM port
BAUDRATE = 115200
TIMEOUT = 0.2

ADDR_START = 0x0001
#ADDR_END   = 0x00FF    # expand to 0xFFFF if needed (slower)
ADDR_END = 0x0FFF


HEADER = 0xAA

# =========================
# CRC16 (IBM / Modbus)
# =========================
def crc16_ibm(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return ((crc & 0xFF) << 8) | (crc >> 8)

# =========================
# FRAME BUILDER
# =========================
def build_read_version_frame(address: int) -> bytes:
    """
    Function 0x06 – Read Version
    Payload: 00 01
    """
    payload = b"\x00\x01"
    body = (
        address.to_bytes(2, "big") +
        b"\x06" +
        b"\x00\x00" +
        len(payload).to_bytes(2, "big") +
        payload
    )
    crc = crc16_ibm(body).to_bytes(2, "big")
    return bytes([HEADER]) + body + crc

# =========================
# FRAME PARSER (MINIMAL)
# =========================
def is_valid_response(rx: bytes) -> bool:
    try:
        if len(rx) < 9:
            return False
        if rx[0] != HEADER:
            return False

        length = int.from_bytes(rx[5:7], "big")
        crc_rx = int.from_bytes(rx[7+length:9+length], "big")
        crc_calc = crc16_ibm(rx[1:7+length])

        return crc_rx == crc_calc
    except Exception:
        return False

# =========================
# MAIN SCAN LOGIC
# =========================
def scan_address():
    print("\n--- Raptor RS485 Address Scan ---")

    # Show available ports
    print("\nAvailable COM ports:")
    for p in serial.tools.list_ports.comports():
        print(f"  {p.device} - {p.description}")

    print(f"\nUsing port: {PORT}")
    print(f"Scanning addresses 0x{ADDR_START:04X} → 0x{ADDR_END:04X}\n")

    ser = serial.Serial(
        port=PORT,
        baudrate=BAUDRATE,
        bytesize=8,
        parity=serial.PARITY_NONE,
        stopbits=1,
        timeout=TIMEOUT
    )

    try:
        for addr in range(ADDR_START, ADDR_END + 1):
            frame = build_read_version_frame(addr)

            ser.reset_input_buffer()
            ser.write(frame)
            ser.flush()
            time.sleep(0.05)

            rx = ser.read(64)
            if rx and is_valid_response(rx):
                print(f"✅ Device responded at address: 0x{addr:04X}")
                return addr

            if addr % 16 == 0:
                print(f"Scanning... 0x{addr:04X}")

        print("\n❌ No device found in scan range")
        return None

    finally:
        ser.close()

# =========================
# ENTRY POINT
# =========================
if __name__ == "__main__":
    found = scan_address()

    if found is not None:
        print(f"\n🎯 CONFIRMED DEVICE ADDRESS = 0x{found:04X}")
    else:
        print("\n⚠️  Device not detected. Check wiring, power, baudrate.")
