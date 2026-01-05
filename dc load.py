"""
Maynuo M97 DC Electronic Load - Debug + Basic Control Script
-----------------------------------------------------------

Prerequisites:
    pip install pyserial

Usage:
    1. Set PORT, BAUD, ADDR below according to your setup.
    2. Run the script from VS Code or terminal.
    3. It will:
       - List available COM ports
       - Open the selected port
       - Try to read model register (debug "ping")
       - Try to read measured voltage & current
       - (Optional) set CC current and toggle input ON/OFF

NOTE:
    This assumes:
      - Rear DB9 is wired as TTL:
            Pin 2 (TXD from load) -> USB-TTL RXD
            Pin 3 (RXD to load)   -> USB-TTL TXD
            Pin 5 (GND)           -> USB-TTL GND
      - BAUDRATE / PARITY / ADDRESS on front panel
        match the values below.
"""

import serial
import serial.tools.list_ports as lp
import struct
import time

# ================== USER CONFIG ==================
PORT = "COM4"     # from the COM list
BAUD = 9600      # or 9600 – match the load CONFIG
ADDR = 1          # match ADDRESS SET on the load
PARITY = "N"      # match COMM.PARITY (N/E/O)
TIMEOUT = 5     # seconds
# =================================================


def list_ports():
    print("\n=== Available COM Ports ===")
    for p in lp.comports():
        print(f"{p.device:>6}  -  {p.description}")
    print("===========================\n")


def crc16_modbus(data: bytes) -> int:
    """Standard Modbus RTU CRC16 (poly 0xA001, init 0xFFFF)."""
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF


class MaynuoLoad:
    """
    Minimal debug + control wrapper for Maynuo M97 series.
    Uses Modbus-like RTU frames over serial.
    """

    # Registers (from manual)
    REG_U = 0x0B00       # measured voltage (float32, 2 regs)
    REG_I = 0x0B02       # measured current (float32, 2 regs)
    REG_MODEL = 0x0B06   # model number (u16)
    REG_CMD = 0x0A00     # command register (u16, low byte)
    REG_IFIX = 0x0A01    # constant current setpoint (float32)

    # Command values
    CMD_CC = 1           # CC mode
    CMD_INPUT_ON = 42    # input ON
    CMD_INPUT_OFF = 43   # input OFF

    def __init__(self, port: str, baud: int, addr: int, parity: str = "N", timeout: float = 0.5):
        self.port = port
        self.baud = baud
        self.addr = addr
        self.timeout = timeout

        parity = parity.upper()
        if parity not in ("N", "E", "O"):
            raise ValueError("parity must be 'N', 'E', or 'O'")
        self.parity = parity

        self.ser: serial.Serial | None = None

    # ---------- connection ----------

    def open(self):
        if self.ser and self.ser.is_open:
            return

        parity_map = {
            "N": serial.PARITY_NONE,
            "E": serial.PARITY_EVEN,
            "O": serial.PARITY_ODD,
        }

        self.ser = serial.Serial(
            port=self.port,
            baudrate=self.baud,
            bytesize=serial.EIGHTBITS,
            parity=parity_map[self.parity],
            stopbits=serial.STOPBITS_ONE,
            timeout=self.timeout,
        )
        print(f"[INFO] Opened {self.port} at {self.baud} baud, parity={self.parity}, addr={self.addr}")

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("[INFO] Port closed")

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # ---------- low-level helpers ----------

    def _send_frame(self, pdu: bytes) -> bytes:
        """
        Send one Modbus RTU frame and return raw response bytes.
        pdu = [function_code, ...] WITHOUT slave addr and CRC.
        """
        if not self.ser or not self.ser.is_open:
            raise RuntimeError("Serial port not open")

        frame_wo_crc = bytes([self.addr]) + pdu
        crc = crc16_modbus(frame_wo_crc)
        frame = frame_wo_crc + crc.to_bytes(2, "little")

        print(f"[TX] {frame.hex()}")
        self.ser.reset_input_buffer()
        self.ser.write(frame)
        self.ser.flush()

        # Just grab whatever comes within timeout
        time.sleep(0.1)
        rx = self.ser.read(256)
        print(f"[RX] {rx.hex()}")
        return rx

    def _check_crc_and_addr(self, resp: bytes, expected_fc: int) -> bytes:
        """
        Basic response validation:
          - min length
          - CRC
          - slave addr
          - function code
        Returns: resp without CRC (last 2 bytes stripped).
        """
        if len(resp) < 5:
            raise RuntimeError(f"Response too short ({len(resp)} bytes)")

        data = resp[:-2]
        crc_recv = int.from_bytes(resp[-2:], "little")
        crc_calc = crc16_modbus(data)
        if crc_calc != crc_recv:
            raise RuntimeError(f"CRC mismatch: recv=0x{crc_recv:04X}, calc=0x{crc_calc:04X}")

        if data[0] != self.addr:
            raise RuntimeError(f"Unexpected slave addr in response: {data[0]}")

        if data[1] != expected_fc:
            raise RuntimeError(f"Unexpected function code: {data[1]}")

        return data

    # ---------- Modbus operations ----------

    def read_holding_registers(self, start_addr: int, count: int) -> list[int]:
        """
        Read 'count' holding registers from 'start_addr' via function 0x03.
        Returns a list of 16-bit unsigned ints.
        """
        pdu = bytes([
            0x03,
            (start_addr >> 8) & 0xFF,
            start_addr & 0xFF,
            (count >> 8) & 0xFF,
            count & 0xFF,
        ])
        resp = self._send_frame(pdu)
        data = self._check_crc_and_addr(resp, expected_fc=0x03)

        if len(data) < 3:
            raise RuntimeError("Response too short (no byte count)")

        byte_count = data[2]
        if byte_count != 2 * count:
            raise RuntimeError(f"Unexpected byte count: {byte_count}, expected {2 * count}")

        raw_regs = data[3:3 + byte_count]
        regs = list(struct.unpack(">" + "H" * count, raw_regs))  # big-endian
        print(f"[INFO] Read regs 0x{start_addr:04X}.. count={count}: {regs}")
        return regs

    def write_single_register(self, addr: int, value: int):
        """
        Write one holding register via function 0x10 with count=1.
        (Some manuals show 0x06; using 0x10 is consistent with multi-write.)
        """
        pdu = bytes([
            0x10,
            (addr >> 8) & 0xFF,
            addr & 0xFF,
            0x00, 0x01,       # count=1
            0x02,             # byte count
            (value >> 8) & 0xFF,
            value & 0xFF,
        ])
        resp = self._send_frame(pdu)
        data = self._check_crc_and_addr(resp, expected_fc=0x10)

        # simple sanity: echo address + count
        addr_hi, addr_lo, cnt_hi, cnt_lo = data[2:6]
        addr_echo = (addr_hi << 8) | addr_lo
        cnt_echo = (cnt_hi << 8) | cnt_lo
        if addr_echo != addr or cnt_echo != 1:
            raise RuntimeError(f"Write echo mismatch: addr={addr_echo}, count={cnt_echo}")
        print(f"[INFO] Wrote reg 0x{addr:04X} = {value}")

    # ---------- float helpers ----------

    @staticmethod
    def regs_to_float(reg_hi: int, reg_lo: int) -> float:
        """Convert two 16-bit regs into big-endian float32."""
        b = struct.pack(">HH", reg_hi, reg_lo)
        return struct.unpack(">f", b)[0]

    @staticmethod
    def float_to_regs(value: float) -> tuple[int, int]:
        """Convert float32 value into two 16-bit big-endian regs."""
        b = struct.pack(">f", float(value))
        reg_hi, reg_lo = struct.unpack(">HH", b)
        return reg_hi, reg_lo

    def write_float(self, addr: int, value: float):
        """Write float32 into two consecutive regs via 0x10."""
        reg_hi, reg_lo = self.float_to_regs(value)
        pdu = bytes([
            0x10,
            (addr >> 8) & 0xFF,
            addr & 0xFF,
            0x00, 0x02,      # count = 2 regs
            0x04,            # byte count = 4
            (reg_hi >> 8) & 0xFF,
            reg_hi & 0xFF,
            (reg_lo >> 8) & 0xFF,
            reg_lo & 0xFF,
        ])
        resp = self._send_frame(pdu)
        data = self._check_crc_and_addr(resp, expected_fc=0x10)
        addr_hi, addr_lo, cnt_hi, cnt_lo = data[2:6]
        addr_echo = (addr_hi << 8) | addr_lo
        cnt_echo = (cnt_hi << 8) | cnt_lo
        if addr_echo != addr or cnt_echo != 2:
            raise RuntimeError(f"Write-float echo mismatch: addr={addr_echo}, count={cnt_echo}")
        print(f"[INFO] Wrote float {value} to regs 0x{addr:04X}..0x{addr+1:04X}")

    # ---------- High-level operations ----------

    def debug_ping_model(self):
        """
        Debug function: read model register 0x0B06 (1 reg).
        """
        print("\n[DEBUG] Pinging model register (0x0B06)...")
        regs = self.read_holding_registers(self.REG_MODEL, 1)
        model_code = regs[0]
        print(f"[RESULT] Model code: {model_code} (hex 0x{model_code:04X})")

    def read_voltage_current(self):
        """
        Read measured voltage (0x0B00) and current (0x0B02) as floats.
        """
        print("\n[DEBUG] Reading voltage & current...")
        u_regs = self.read_holding_registers(self.REG_U, 2)
        i_regs = self.read_holding_registers(self.REG_I, 2)

        u = self.regs_to_float(u_regs[0], u_regs[1])
        i = self.regs_to_float(i_regs[0], i_regs[1])

        print(f"[RESULT] Voltage = {u:.4f} V, Current = {i:.4f} A")
        return u, i

    def set_cc_current(self, current_a: float):
        """
        Set CC mode with given current setpoint.
        Sequence:
          - Write IFIX
          - Write CMD=1 (CC mode)
        """
        print(f"\n[DEBUG] Setting CC current to {current_a} A...")
        self.write_float(self.REG_IFIX, current_a)
        self.write_single_register(self.REG_CMD, self.CMD_CC)
        print("[RESULT] CC current configured")

    def enable_input(self):
        """Turn load input ON (CMD=42)."""
        print("\n[DEBUG] Enabling input...")
        self.write_single_register(self.REG_CMD, self.CMD_INPUT_ON)
        print("[RESULT] Input ON command sent")

    def disable_input(self):
        """Turn load input OFF (CMD=43)."""
        print("\n[DEBUG] Disabling input...")
        self.write_single_register(self.REG_CMD, self.CMD_INPUT_OFF)
        print("[RESULT] Input OFF command sent")


# ================== MAIN DEMO ==================

if __name__ == "__main__":
    list_ports()  # show what Windows sees

    load = MaynuoLoad(PORT, BAUD, ADDR, PARITY, TIMEOUT)

    try:
        with load:
            # 1) Debug ping - check if the instrument says *anything*
            try:
                load.debug_ping_model()
            except Exception as e:
                print(f"[ERROR] Model ping failed: {e}")

            # 2) Try reading voltage/current (will also show raw RX)
            try:
                load.read_voltage_current()
            except Exception as e:
                print(f"[ERROR] Read U/I failed: {e}")

            # 3) Example control: set CC = 1.0 A and turn input ON
            #    (Uncomment this when you are ready!)
            #
            # try:
            #     load.set_cc_current(1.0)
            #     load.enable_input()
            #     time.sleep(1.0)
            #     load.read_voltage_current()
            #     load.disable_input()
            # except Exception as e:
            #     print(f"[ERROR] CC control failed: {e}")

    except Exception as e:
        print(f"[FATAL] {e}")
