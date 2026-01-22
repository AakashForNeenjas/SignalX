import time
from typing import Dict, Any, List

import serial


HEADER = 0xAA

CRC_TABLE: List[int] = []


def _init_crc_table() -> None:
    for i in range(256):
        crc = i
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
        CRC_TABLE.append(crc)


_init_crc_table()


def crc16(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc = (crc >> 8) ^ CRC_TABLE[(crc ^ b) & 0xFF]
    # swap bytes
    return ((crc & 0xFF) << 8) | (crc >> 8)


def build_frame(address: int, function: int, reg_addr: int, data: bytes) -> bytes:
    addr_b = address.to_bytes(2, "big")
    func_b = function.to_bytes(1, "big")
    reg_b = reg_addr.to_bytes(2, "big")
    len_b = len(data).to_bytes(2, "big")
    payload = addr_b + func_b + reg_b + len_b + data
    crc = crc16(payload).to_bytes(2, "big")
    return bytes([HEADER]) + payload + crc


def parse_response(resp: bytes) -> Dict[str, Any]:
    if len(resp) < 9:
        raise ValueError(f"Response too short: {len(resp)} bytes")
    if resp[0] != HEADER:
        raise ValueError(f"Bad header: 0x{resp[0]:02X}")
    addr = int.from_bytes(resp[1:3], "big")
    func = resp[3]
    status = resp[4]
    length = int.from_bytes(resp[5:7], "big")
    expected_len = 7 + length + 2
    if len(resp) < expected_len:
        raise ValueError(f"Incomplete frame: got {len(resp)} bytes, need {expected_len}")
    data = resp[7:7 + length]
    crc_rx = int.from_bytes(resp[7 + length:7 + length + 2], "big")
    crc_calc = crc16(resp[1:7 + length])
    if crc_rx != crc_calc:
        raise ValueError(f"CRC mismatch rx=0x{crc_rx:04X} calc=0x{crc_calc:04X}")
    return {"address": addr, "function": func, "status": status, "data": data}


REGISTER_MAP = {
    "running_data": {
        0: {"name": "INV_OUT_VOLTAGE", "unit": "V", "scale": 0.1},
        1: {"name": "INV_OUT_CURRENT", "unit": "A", "scale": 0.01},
        2: {"name": "INV_OUT_POWER", "unit": "W", "scale": 1.0},
        3: {"name": "INV_OUT_FREQUENCY", "unit": "Hz", "scale": 0.01},
        4: {"name": "BATTERY_CURRENT", "unit": "A", "scale": 0.01},
        5: {"name": "BATTERY_POWER", "unit": "W", "scale": 1.0},
        6: {"name": "DC_BUS_VOLTAGE", "unit": "V", "scale": 0.1},
        7: {"name": "DC_BUS_CURRENT", "unit": "A", "scale": 0.01},
        8: {"name": "DC_BUS_POWER", "unit": "W", "scale": 1.0},
        9: {"name": "GRID_VOLTAGE", "unit": "V", "scale": 0.1},
        10: {"name": "GRID_CURRENT", "unit": "A", "scale": 0.01},
        11: {"name": "PV_VOLTAGE", "unit": "V", "scale": 0.1},
        12: {"name": "PV_CURRENT", "unit": "A", "scale": 0.01},
        13: {"name": "BATTERY_VOLTAGE", "unit": "V", "scale": 0.1},
        14: {"name": "DCDC_OUT_VOLTAGE", "unit": "V", "scale": 0.1},
        15: {"name": "DCDC_OUT_CURRENT", "unit": "A", "scale": 0.01},
        16: {"name": "DCDC_OUT_POWER", "unit": "W", "scale": 1.0},
        31: {"name": "ENERGY_CHARGE_TOTAL", "unit": "kWh", "scale": 0.01},
        32: {"name": "ENERGY_DISCHARGE_TOTAL", "unit": "kWh", "scale": 0.01},
        33: {"name": "BATTERY_SOC", "unit": "%", "scale": 1.0},
        34: {"name": "BATTERY_SOH", "unit": "%", "scale": 1.0},
        35: {"name": "TEMP_POWER_BOARD", "unit": "C", "scale": 1.0},
        36: {"name": "TEMP_INVERTER", "unit": "C", "scale": 1.0},
        37: {"name": "TEMP_DCDC", "unit": "C", "scale": 1.0},
        38: {"name": "TEMP_BATTERY", "unit": "C", "scale": 1.0},
        39: {"name": "TEMP_AMBIENT", "unit": "C", "scale": 1.0},
        40: {"name": "TEMP_MOSFET", "unit": "C", "scale": 1.0},
    }
}


ALARM_BITS = {
    0: "Battery Over Voltage",
    1: "Battery Under Voltage",
    2: "Battery Over Current",
    3: "Battery Reverse",
    4: "Over Temperature",
    5: "Temperature Sensor Fault",
    6: "Grid Over Voltage",
    7: "Grid Under Voltage",
    8: "Output Short Circuit",
    9: "BMS Communication Timeout",
    10: "BMS Charge Overcurrent",
    11: "Manual Stop",
    12: "Output Relay Fault",
    13: "Parallel Communication Fault",
    14: "AC Input Over Voltage",
}


FAULT_BITS = {
    0: "Startup Failure",
    1: "AC Output Short",
    2: "Grid Over Voltage",
    3: "PV Under Voltage",
    4: "PV Over Voltage",
    5: "Output Over Current",
    6: "Bus Over Voltage",
    7: "Bus Under Voltage",
    8: "Inverter Hardware Fault",
    9: "Grid Phase Loss",
    10: "AC Over Current",
    11: "Battery Voltage Fault",
    12: "Battery Current Fault",
    13: "Charging Over Current",
    14: "MOS Over Temperature",
}


def decode_u16_words(data: bytes) -> List[int]:
    if len(data) % 2 != 0:
        raise ValueError("U16 payload length must be even")
    return [int.from_bytes(data[i:i + 2], "big") for i in range(0, len(data), 2)]


def decode_running_block(raw_data: bytes, start_addr: int) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    words = decode_u16_words(raw_data)
    for idx, raw in enumerate(words):
        addr = start_addr + idx
        meta = REGISTER_MAP["running_data"].get(addr)
        if not meta:
            continue
        scale = meta.get("scale", 1.0)
        out[meta["name"]] = {"value": raw * scale, "unit": meta.get("unit", ""), "raw": raw}
    return out


def decode_bitfield(word: int, mapping: Dict[int, str]) -> List[str]:
    return [desc for bit, desc in mapping.items() if word & (1 << bit)]


class RaptorDevice:
    def __init__(
        self,
        port: str,
        address: int = 0x000B,
        baudrate: int = 115200,
        timeout: float = 0.5,
        parity: str = "None",
        stopbits: int = 1,
        rs485_mode: bool = True,
    ):
        self.address = address
        parity_map = {
            "None": serial.PARITY_NONE,
            "Even": serial.PARITY_EVEN,
            "Odd": serial.PARITY_ODD,
        }
        parity_val = parity_map.get(parity, serial.PARITY_NONE)
        stop_val = serial.STOPBITS_ONE if stopbits == 1 else serial.STOPBITS_TWO
        self.ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=8,
            parity=parity_val,
            stopbits=stop_val,
            timeout=timeout,
            inter_byte_timeout=timeout,
        )
        if rs485_mode and hasattr(serial, "rs485"):
            try:
                settings = serial.rs485.RS485Settings(
                    rts_level_for_tx=True,
                    rts_level_for_rx=False,
                    delay_before_tx=0.0,
                    delay_before_rx=0.0,
                )
                self.ser.rs485_mode = settings
            except Exception:
                pass

    def close(self) -> None:
        try:
            self.ser.close()
        except Exception:
            pass

    def _read_frame(self, timeout_s: float) -> bytes:
        deadline = time.monotonic() + timeout_s
        buf = bytearray()
        while time.monotonic() < deadline:
            chunk = self.ser.read(64)
            if chunk:
                buf.extend(chunk)
            else:
                # No data this tick, continue until deadline
                continue
            while True:
                try:
                    header_index = buf.index(HEADER)
                except ValueError:
                    buf.clear()
                    break
                if header_index > 0:
                    del buf[:header_index]
                # Need header(1) + addr(2) + func(1) + status(1) + len(2)
                if len(buf) < 7:
                    break
                length = int.from_bytes(buf[5:7], "big")
                frame_len = 7 + length + 2
                if len(buf) < frame_len:
                    break
                frame = bytes(buf[:frame_len])
                del buf[:frame_len]
                return frame
        return b""

    def _txrx(self, function: int, reg_addr: int, data: bytes, rx_max: int = 512) -> Dict[str, Any]:
        frame = build_frame(self.address, function, reg_addr, data)
        self.ser.reset_input_buffer()
        self.ser.write(frame)
        self.ser.flush()
        time.sleep(0.05)
        resp = self._read_frame(timeout_s=max(self.ser.timeout or 0.0, 0.6))
        if not resp:
            raise TimeoutError("No response from device (check address/baud/wiring).")
        return parse_response(resp)

    def read_running(self, start_addr: int, count_words: int) -> Dict[str, Any]:
        req = count_words.to_bytes(2, "big")
        return self._txrx(function=0x01, reg_addr=start_addr, data=req)

    def read_alarm_fault(self) -> Dict[str, Any]:
        return self._txrx(function=0x03, reg_addr=0, data=b"\x00\x02")

    def read_version(self) -> Dict[str, Any]:
        return self._txrx(function=0x06, reg_addr=0, data=b"\x00\x01")
