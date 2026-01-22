"""
maynuo_m97.py
-------------
Python driver for Maynuo M97 series programmable DC electronic loads.

Protocol:
  - Modbus-RTU style over serial (TTL via M-131/M-133 or RS-232 adapter).
  - Function codes used:
        0x01  Read Coils
        0x03  Read Holding Registers
        0x05  Force Single Coil
        0x10  Preset Multiple Registers
  - Floating-point values are IEEE-754 32-bit big-endian floats stored
    across 2 registers (high word first).

This module provides a high-level OO API around the register map from
the Maynuo M97 communication manual.
"""

from __future__ import annotations

import struct
from typing import Tuple, Optional, List

import serial
import serial.tools.list_ports as lp


# =============================================================================
# Helper: list serial ports
# =============================================================================

def list_ports() -> None:
    """Print all available COM ports (useful for debugging / selection)."""
    print("\n=== Available COM Ports ===")
    for p in lp.comports():
        print(f"{p.device:>6}  -  {p.description}")
    print("================================\n")


# =============================================================================
# Core driver class
# =============================================================================

class MaynuoM97:
    """
    Python driver for Maynuo M97 series programmable DC electronic load.

    Typical usage:

        from maynuo_m97 import MaynuoM97, list_ports

        list_ports()
        load = MaynuoM97(port="COM4", slave_addr=1, baudrate=9600, parity="N",
                         timeout=0.3, debug=True)

        with load:
            load.set_remote_control(True)
            load.set_cc_current(5.0)
            load.enable_input()
            v, i = load.read_voltage_current()
            print(v, i)
            load.disable_input()

    The API is modeled directly on the Maynuo register map and command table.
    """

    # -------------------------------------------------------------------------
    # Coil addresses (digital bits)
    # -------------------------------------------------------------------------
    COIL_PC1      = 0x0500   # Remote control enable (front panel lock)
    COIL_PC2      = 0x0501   # Local prohibition bit
    COIL_TRIG     = 0x0502   # Software trigger
    COIL_REMOTE   = 0x0503   # Remote input voltage tag
    COIL_ISTATE   = 0x0510   # Input ON/OFF state (read via 0x01)

    # -------------------------------------------------------------------------
    # XRAM holding registers (writeable control / setpoints)
    # -------------------------------------------------------------------------

    # Command / basic setpoints
    REG_CMD       = 0x0A00   # Command register (lower 8 bits used)
    REG_IFIX      = 0x0A01   # Constant current set, float32
    REG_UFIX      = 0x0A03   # Constant voltage set, float32
    REG_PFIX      = 0x0A05   # Constant power set, float32
    REG_RFIX      = 0x0A07   # Constant resistance set, float32

    # Soft-start times
    REG_TMCCS     = 0x0A09   # CC soft-start time, float32
    REG_TMCVS     = 0x0A0B   # CV soft-start time, float32

    # Load/unload voltage thresholds for CC/CV/CW/CR
    REG_UCCONSET  = 0x0A0D   # CC load voltage threshold, float32
    REG_UCCOFFSET = 0x0A0F   # CC unload voltage threshold, float32
    REG_UCVONSET  = 0x0A11   # CV load voltage threshold, float32
    REG_UCVOFFSET = 0x0A13   # CV unload voltage threshold, float32
    REG_UCPONSET  = 0x0A15   # CW load voltage threshold, float32
    REG_UCPOFFSET = 0x0A17   # CW unload voltage threshold, float32
    REG_UCRONSET  = 0x0A19   # CR load voltage threshold, float32
    REG_UCROFFSET = 0x0A1B   # CR unload voltage threshold, float32

    # CC/CR → CV switchover voltages
    REG_UCCCV     = 0x0A1D   # CC→CV switchover voltage, float32
    REG_UCRCV     = 0x0A1F   # CR→CV switchover voltage, float32

    # Dynamic mode registers
    REG_IA        = 0x0A21   # Dynamic A current, float32
    REG_IB        = 0x0A23   # Dynamic B current, float32
    REG_TMAWD     = 0x0A25   # A width, float32 (seconds)
    REG_TMBWD     = 0x0A27   # B width, float32 (seconds)
    REG_TMTRANRIS = 0x0A29   # Rise time, float32 (seconds)
    REG_TMTRANFAL = 0x0A2B   # Fall time, float32 (seconds)
    REG_MODETRAN  = 0x0A2D   # Dynamic mode (0–2), u16

    # Battery / list / auto test
    REG_UBATTEND  = 0x0A2E   # Battery end voltage, float32
    REG_BATT      = 0x0A30   # Battery capacity register, float32 (result)
    REG_SERLIST   = 0x0A32   # LIST number (1–8), u16
    REG_SERATEST  = 0x0A33   # Auto-test number (1–8), u16

    # System limits
    REG_IMAX      = 0x0A34   # Max current, float32
    REG_UMAX      = 0x0A36   # Max voltage, float32
    REG_PMAX      = 0x0A38   # Max power, float32

    # -------------------------------------------------------------------------
    # Measurement / status registers
    # -------------------------------------------------------------------------
    REG_U         = 0x0B00   # Measured voltage, float32
    REG_I         = 0x0B02   # Measured current, float32
    REG_SETMODE   = 0x0B04   # Operation mode, u16
    REG_INPUTMODE = 0x0B05   # Input status, u16
    REG_MODEL     = 0x0B06   # Model number, u16
    REG_EDITION   = 0x0B07   # Software version, u16

    # -------------------------------------------------------------------------
    # Command codes (values written to REG_CMD)
    # -------------------------------------------------------------------------
    CMD_CC             = 1
    CMD_CV             = 2
    CMD_CW             = 3
    CMD_CR             = 4
    CMD_CC_SOFT        = 20
    CMD_DYNAMIC        = 25
    CMD_SHORT          = 26
    CMD_LIST           = 27
    CMD_CC_LOAD_UNLOAD = 30
    CMD_CV_LOAD_UNLOAD = 31
    CMD_CW_LOAD_UNLOAD = 32
    CMD_CR_LOAD_UNLOAD = 33
    CMD_CC_TO_CV       = 34
    CMD_CR_TO_CV       = 36
    CMD_BATT           = 38
    CMD_CV_SOFT        = 39
    CMD_SYS_PARAMS     = 41
    CMD_INPUT_ON       = 42
    CMD_INPUT_OFF      = 43

    # -------------------------------------------------------------------------
    # Modbus function codes
    # -------------------------------------------------------------------------
    FC_READ_COILS       = 0x01
    FC_READ_HOLDING     = 0x03
    FC_FORCE_SINGLE_COIL = 0x05
    FC_PRESET_MULTIPLE  = 0x10

    # -------------------------------------------------------------------------

    def __init__(
        self,
        port: str,
        slave_addr: int = 1,
        baudrate: int = 9600,
        timeout: float = 0.3,
        parity: str = "N",
        debug: bool = False,
    ) -> None:
        """
        :param port:       Serial port name, e.g. "COM4" or "/dev/ttyUSB0".
        :param slave_addr: Device address (1–200), matches front-panel ADDRESS.
        :param baudrate:   Must match BAUDRATE SET in the load menu.
        :param timeout:    Serial read timeout in seconds.
        :param parity:     'N', 'E', or 'O', matches COMM.PARITY.
        :param debug:      If True, prints TX/RX frames and basic info.
        """
        self.port       = port
        self.slave_addr = slave_addr
        self.baudrate   = baudrate
        self.timeout    = timeout
        self.parity     = parity.upper()
        self.debug      = debug

        self.ser: Optional[serial.Serial] = None

    # =========================================================================
    # Connection helpers
    # =========================================================================

    def open(self) -> None:
        """Open the underlying serial port (idempotent)."""
        if self.ser and self.ser.is_open:
            return

        parity_map = {
            "N": serial.PARITY_NONE,
            "E": serial.PARITY_EVEN,
            "O": serial.PARITY_ODD,
        }
        if self.parity not in parity_map:
            raise ValueError("parity must be one of 'N', 'E', 'O'")

        self.ser = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            bytesize=serial.EIGHTBITS,
            parity=parity_map[self.parity],
            stopbits=serial.STOPBITS_ONE,
            timeout=self.timeout,
        )
        if self.debug:
            print(f"[INFO] Opened {self.port} @ {self.baudrate} baud, parity={self.parity}, addr={self.slave_addr}")

    def close(self) -> None:
        """Close the serial port."""
        if self.ser and self.ser.is_open:
            self.ser.close()
            if self.debug:
                print("[INFO] Port closed")

    def __enter__(self) -> "MaynuoM97":
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    # =========================================================================
    # Low-level Modbus helpers
    # =========================================================================

    @staticmethod
    def _crc16(data: bytes) -> int:
        """Modbus RTU CRC16 (poly 0xA001, init 0xFFFF, LSB first)."""
        crc = 0xFFFF
        for b in data:
            crc ^= b
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc & 0xFFFF

    def _ensure_open(self) -> None:
        if not self.ser or not self.ser.is_open:
            raise RuntimeError("Serial port not open. Call open() or use 'with MaynuoM97(...) as load:'.")

    def _send(self, payload: bytes) -> None:
        """
        Send a Modbus frame (without slave addr / CRC). Does not read.

        Helpers:
            - Build 'payload' (function code + data)
            - Call _send(payload)
            - Then perform one or more _read_exact() calls to parse response.
        """
        self._ensure_open()

        frame_wo_crc = bytes([self.slave_addr]) + payload
        crc = self._crc16(frame_wo_crc)
        frame = frame_wo_crc + struct.pack("<H", crc)  # CRC low, high

        if self.debug:
            print(f"[TX] {frame.hex()}")

        self.ser.reset_input_buffer()
        self.ser.write(frame)
        self.ser.flush()

    def _read_exact(self, n: int) -> bytes:
        """Read exactly n bytes or raise TimeoutError."""
        self._ensure_open()
        data = self.ser.read(n)
        while len(data) < n:
            chunk = self.ser.read(n - len(data))
            if not chunk:
                break
            data += chunk
        if len(data) != n:
            raise TimeoutError(f"Expected {n} bytes, got {len(data)}")
        if self.debug:
            print(f"[RX] {data.hex()}")
        return data

    # -------------------------------------------------------------------------
    # Coils (0x01, 0x05)
    # -------------------------------------------------------------------------

    def _read_coils(self, addr: int, count: int = 1) -> int:
        """
        Read 'count' coils starting at 'addr'.
        Returns an integer bitmask of coil states.
        """
        payload = struct.pack(">BHH", self.FC_READ_COILS, addr, count)
        self._send(payload)

        # Response: addr, fc, byte_count, data..., crc_lo, crc_hi
        header = self._read_exact(3)  # addr, fc, byte_count
        if header[0] != self.slave_addr or header[1] != self.FC_READ_COILS:
            raise RuntimeError("Unexpected response header for Read Coils")

        byte_count = header[2]
        data_plus_crc = self._read_exact(byte_count + 2)

        frame_wo_crc = header + data_plus_crc[:-2]
        crc_calc = self._crc16(frame_wo_crc)
        crc_recv = struct.unpack("<H", data_plus_crc[-2:])[0]
        if crc_calc != crc_recv:
            raise RuntimeError("CRC error in Read Coils")

        coil_bytes = data_plus_crc[:-2]
        value = 0
        for i, b in enumerate(coil_bytes):
            value |= b << (8 * i)
        return value

    def _force_single_coil(self, addr: int, value: bool) -> None:
        """
        Force a single coil ON (0xFF00) or OFF (0x0000).
        """
        force_word = 0xFF00 if value else 0x0000
        payload = struct.pack(">BHH", self.FC_FORCE_SINGLE_COIL, addr, force_word)
        self._send(payload)

        resp = self._read_exact(8)  # addr, fc, addr_hi, addr_lo, force_hi, force_lo, crc_lo, crc_hi
        if resp[0] != self.slave_addr or resp[1] != self.FC_FORCE_SINGLE_COIL:
            raise RuntimeError("Unexpected response for Force Single Coil")

        crc_calc = self._crc16(resp[:-2])
        crc_recv = struct.unpack("<H", resp[-2:])[0]
        if crc_calc != crc_recv:
            raise RuntimeError("CRC error in Force Single Coil")

    # -------------------------------------------------------------------------
    # Holding registers (0x03, 0x10)
    # -------------------------------------------------------------------------

    def _read_registers(self, addr: int, count: int) -> Tuple[int, ...]:
        """
        Read 'count' holding registers starting at 'addr'.
        Returns a tuple of 16-bit integers.
        """
        payload = struct.pack(">BHH", self.FC_READ_HOLDING, addr, count)
        self._send(payload)

        header = self._read_exact(3)  # addr, fc, byte_count
        if header[0] != self.slave_addr or header[1] != self.FC_READ_HOLDING:
            raise RuntimeError("Unexpected response header for Read Holding Registers")

        byte_count = header[2]
        data_plus_crc = self._read_exact(byte_count + 2)

        frame_wo_crc = header + data_plus_crc[:-2]
        crc_calc = self._crc16(frame_wo_crc)
        crc_recv = struct.unpack("<H", data_plus_crc[-2:])[0]
        if crc_calc != crc_recv:
            raise RuntimeError("CRC error in Read Holding Registers")

        if byte_count != 2 * count:
            raise RuntimeError("Byte count mismatch in Read Holding Registers")

        regs = struct.unpack(">" + "H" * count, data_plus_crc[:-2])
        if self.debug:
            print(f"[INFO] Read regs 0x{addr:04X} count={count}: {regs}")
        return regs

    def _write_registers(self, addr: int, regs: Tuple[int, ...]) -> None:
        """
        Write one or more 16-bit registers via function 0x10 (Preset Multiple Registers).
        """
        count = len(regs)
        byte_count = 2 * count
        payload = struct.pack(">BHHB", self.FC_PRESET_MULTIPLE, addr, count, byte_count)
        payload += struct.pack(">" + "H" * count, *regs)

        self._send(payload)

        resp = self._read_exact(8)  # addr, fc, addr_hi, addr_lo, count_hi, count_lo, crc_lo, crc_hi
        if resp[0] != self.slave_addr or resp[1] != self.FC_PRESET_MULTIPLE:
            raise RuntimeError("Unexpected response for Preset Multiple Registers")

        crc_calc = self._crc16(resp[:-2])
        crc_recv = struct.unpack("<H", resp[-2:])[0]
        if crc_calc != crc_recv:
            raise RuntimeError("CRC error in Preset Multiple Registers")

    # -------------------------------------------------------------------------
    # Float helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _float_to_regs(value: float) -> Tuple[int, int]:
        """
        Convert Python float -> two 16-bit registers (big-endian IEEE 754).
        Example: 2.3 A -> bytes 0x40 0x13 0x33 0x33 -> regs 0x4013, 0x3333.
        """
        b = struct.pack(">f", float(value))   # big-endian float32
        high, low = struct.unpack(">HH", b)
        return high, low

    @staticmethod
    def _regs_to_float(reg_hi: int, reg_lo: int) -> float:
        """Convert two 16-bit registers -> Python float (big-endian float32)."""
        b = struct.pack(">HH", reg_hi, reg_lo)
        return struct.unpack(">f", b)[0]

    def _write_float(self, addr: int, value: float) -> None:
        regs = self._float_to_regs(value)
        self._write_registers(addr, regs)

    def _read_float(self, addr: int) -> float:
        reg_hi, reg_lo = self._read_registers(addr, 2)
        return self._regs_to_float(reg_hi, reg_lo)

    def _write_u16(self, addr: int, value: int) -> None:
        self._write_registers(addr, (value & 0xFFFF,))

    # =========================================================================
    # High-level API
    # =========================================================================

    # --- Remote control & input ---

    def set_remote_control(self, enable: bool = True) -> None:
        """
        Enable/disable remote control (front panel lock) via PC1 coil.
        When enabled, the front panel is usually locked and remote control takes over.
        """
        self._force_single_coil(self.COIL_PC1, enable)

    def set_local_prohibit(self, prohibit: bool = True) -> None:
        """Enable/disable local prohibition via PC2 coil."""
        self._force_single_coil(self.COIL_PC2, prohibit)

    def enable_input(self) -> None:
        """
        Turn load input ON (equivalent to CMD=42).
        """
        self._write_u16(self.REG_CMD, self.CMD_INPUT_ON)

    def disable_input(self) -> None:
        """Turn load input OFF (CMD=43)."""
        self._write_u16(self.REG_CMD, self.CMD_INPUT_OFF)

    def read_input_state(self) -> bool:
        """
        Read ISTATE coil; returns True if input ON, False if OFF.
        """
        bits = self._read_coils(self.COIL_ISTATE, 1)
        return bool(bits & 0x01)

    # --- Measurement & identification ---

    def read_voltage_current(self) -> Tuple[float, float]:
        """
        Read present input voltage (U) and current (I).

        :return: (voltage_V, current_A)
        """
        u = self._read_float(self.REG_U)
        i = self._read_float(self.REG_I)
        if self.debug:
            print(f"[RESULT] Voltage={u:.4f} V, Current={i:.4f} A")
        return u, i

    def read_mode(self) -> int:
        """Read SETMODE register (0x0B04) to get current operation mode."""
        (mode,) = self._read_registers(self.REG_SETMODE, 1)
        return mode

    def read_input_mode(self) -> int:
        """Read INPUTMODE register (0x0B05)."""
        (m,) = self._read_registers(self.REG_INPUTMODE, 1)
        return m

    def read_model_code(self) -> int:
        """Read model number from REG_MODEL."""
        (m,) = self._read_registers(self.REG_MODEL, 1)
        if self.debug:
            print(f"[RESULT] Model code: {m} (0x{m:04X})")
        return m

    def read_software_version(self) -> int:
        """Read software version from REG_EDITION."""
        (v,) = self._read_registers(self.REG_EDITION, 1)
        if self.debug:
            print(f"[RESULT] Software version: {v}")
        return v

    # --- Simple CC / CV / CW / CR operations ---

    def set_cc_current(self, current_a: float, soft_start_s: float | None = None) -> None:
        """
        Configure constant current operation.

        If soft_start_s is None:
            - IFIX := current
            - CMD := CC (1)
        Else:
            - IFIX := current
            - TMCCS := soft_start_s
            - CMD := CC Soft Start (20)
        """
        self._write_float(self.REG_IFIX, current_a)
        if soft_start_s is None:
            self._write_u16(self.REG_CMD, self.CMD_CC)
        else:
            self._write_float(self.REG_TMCCS, soft_start_s)
            self._write_u16(self.REG_CMD, self.CMD_CC_SOFT)

    def set_cv_voltage(self, voltage_v: float, soft_start_s: float | None = None) -> None:
        """
        Configure constant voltage operation.

        If soft_start_s is None:
            - UFIX := voltage
            - CMD := CV (2)
        Else:
            - UFIX := voltage
            - TMCVS := soft_start_s
            - CMD := CV Soft Start (39)
        """
        self._write_float(self.REG_UFIX, voltage_v)
        if soft_start_s is None:
            self._write_u16(self.REG_CMD, self.CMD_CV)
        else:
            self._write_float(self.REG_TMCVS, soft_start_s)
            self._write_u16(self.REG_CMD, self.CMD_CV_SOFT)

    def set_cw_power(self, power_w: float) -> None:
        """Configure constant power operation (PFIX + CMD=3)."""
        self._write_float(self.REG_PFIX, power_w)
        self._write_u16(self.REG_CMD, self.CMD_CW)

    def set_cr_resistance(self, resistance_ohm: float) -> None:
        """Configure constant resistance operation (RFIX + CMD=4)."""
        self._write_float(self.REG_RFIX, resistance_ohm)
        self._write_u16(self.REG_CMD, self.CMD_CR)

    # --- Load/unload threshold modes ---

    def set_cc_load_unload(self, current_a: float, v_on: float, v_off: float) -> None:
        """
        CC loading/unloading:
            - IFIX      := current_a
            - UCCONSET  := v_on
            - UCCOFFSET := v_off
            - CMD       := 30 (CC_LOAD_UNLOAD)
        """
        self._write_float(self.REG_IFIX, current_a)
        self._write_float(self.REG_UCCONSET, v_on)
        self._write_float(self.REG_UCCOFFSET, v_off)
        self._write_u16(self.REG_CMD, self.CMD_CC_LOAD_UNLOAD)

    def set_cv_load_unload(self, voltage_v: float, v_on: float, v_off: float) -> None:
        """
        CV loading/unloading:
            - UFIX      := voltage_v
            - UCVONSET  := v_on
            - UCVOFFSET := v_off
            - CMD       := 31
        """
        self._write_float(self.REG_UFIX, voltage_v)
        self._write_float(self.REG_UCVONSET, v_on)
        self._write_float(self.REG_UCVOFFSET, v_off)
        self._write_u16(self.REG_CMD, self.CMD_CV_LOAD_UNLOAD)

    def set_cw_load_unload(self, power_w: float, v_on: float, v_off: float) -> None:
        """
        CW loading/unloading:
            - PFIX      := power_w
            - UCPONSET  := v_on
            - UCPOFFSET := v_off
            - CMD       := 32
        """
        self._write_float(self.REG_PFIX, power_w)
        self._write_float(self.REG_UCPONSET, v_on)
        self._write_float(self.REG_UCPOFFSET, v_off)
        self._write_u16(self.REG_CMD, self.CMD_CW_LOAD_UNLOAD)

    def set_cr_load_unload(self, resistance_ohm: float, v_on: float, v_off: float) -> None:
        """
        CR loading/unloading:
            - RFIX      := resistance_ohm
            - UCRONSET  := v_on
            - UCROFFSET := v_off
            - CMD       := 33
        """
        self._write_float(self.REG_RFIX, resistance_ohm)
        self._write_float(self.REG_UCRONSET, v_on)
        self._write_float(self.REG_UCROFFSET, v_off)
        self._write_u16(self.REG_CMD, self.CMD_CR_LOAD_UNLOAD)

    # --- CC/CR → CV switchover modes ---

    def set_cc_to_cv(self, current_a: float, v_cv: float) -> None:
        """
        CC→CV mode:
            - IFIX  := current_a
            - UCCCV := v_cv
            - CMD   := 34
        """
        self._write_float(self.REG_IFIX, current_a)
        self._write_float(self.REG_UCCCV, v_cv)
        self._write_u16(self.REG_CMD, self.CMD_CC_TO_CV)

    def set_cr_to_cv(self, resistance_ohm: float, v_cv: float) -> None:
        """
        CR→CV mode:
            - RFIX  := resistance_ohm
            - UCRCV := v_cv
            - CMD   := 36
        """
        self._write_float(self.REG_RFIX, resistance_ohm)
        self._write_float(self.REG_UCRCV, v_cv)
        self._write_u16(self.REG_CMD, self.CMD_CR_TO_CV)

    # --- Dynamic test mode ---

    def start_dynamic_test(
        self,
        ia_a: float,
        ib_a: float,
        ta_s: float,
        tb_s: float,
        rise_s: float,
        fall_s: float,
        mode: int = 0,
    ) -> None:
        """
        Configure and start dynamic test (CMD=25).

        The manual defines:
            IA        (REG_IA)        – A-level current
            IB        (REG_IB)        – B-level current
            TMAWD     (REG_TMAWD)     – A pulse width (seconds)
            TMBWD     (REG_TMBWD)     – B pulse width (seconds)
            TMTRANRIS (REG_TMTRANRIS) – transition rise time (seconds)
            TMTRANFAL (REG_TMTRANFAL) – transition fall time (seconds)
            MODETRAN  (REG_MODETRAN)  – 0=continuous,1=pulse,2=trigger
            CMD       = 25 (dynamic)

        :param ia_a:   A-level current in Amps
        :param ib_a:   B-level current in Amps
        :param ta_s:   A-level width in seconds
        :param tb_s:   B-level width in seconds
        :param rise_s: transition rising time in seconds
        :param fall_s: transition falling time in seconds
        :param mode:   dynamic mode (0, 1, or 2)
        """
        self._write_float(self.REG_IA, ia_a)
        self._write_float(self.REG_IB, ib_a)
        self._write_float(self.REG_TMAWD, ta_s)
        self._write_float(self.REG_TMBWD, tb_s)
        self._write_float(self.REG_TMTRANRIS, rise_s)
        self._write_float(self.REG_TMTRANFAL, fall_s)
        self._write_u16(self.REG_MODETRAN, int(mode) & 0xFFFF)
        self._write_u16(self.REG_CMD, self.CMD_DYNAMIC)

    # --- Battery test mode ---

    def start_battery_test(self, current_a: float, end_voltage_v: float) -> None:
        """
        Battery test:
            - IFIX     := current_a
            - UBATTEND := end_voltage_v
            - CMD      := 38
        """
        self._write_float(self.REG_IFIX, current_a)
        self._write_float(self.REG_UBATTEND, end_voltage_v)
        self._write_u16(self.REG_CMD, self.CMD_BATT)

    def read_battery_capacity(self) -> float:
        """
        Read battery capacity register (REG_BATT), in Ah or Wh depending on mode.
        Check manual for exact units.
        """
        return self._read_float(self.REG_BATT)

    # --- List mode ---

    def run_list(self, list_index: int) -> None:
        """
        Run LIST program:
            - SERLIST := list_index (1..8)
            - CMD     := 27 (LIST)

        Note: List content itself must be edited via front panel or vendor PC tool.
        """
        if not (1 <= list_index <= 8):
            raise ValueError("list_index must be between 1 and 8")
        self._write_u16(self.REG_SERLIST, list_index)
        self._write_u16(self.REG_CMD, self.CMD_LIST)

    # --- System limits / parameters ---

    def set_limits(self, imax_a: float, umax_v: float, pmax_w: float) -> None:
        """
        Set system maximum I/V/P and apply via CMD=41.

            - IMAX := imax_a
            - UMAX := umax_v
            - PMAX := pmax_w
            - CMD  := 41
        """
        self._write_float(self.REG_IMAX, imax_a)
        self._write_float(self.REG_UMAX, umax_v)
        self._write_float(self.REG_PMAX, pmax_w)
        self._write_u16(self.REG_CMD, self.CMD_SYS_PARAMS)

    # --- Short circuit ---

    def start_short_circuit(self) -> None:
        """Enter short-circuit mode (CMD=26)."""
        self._write_u16(self.REG_CMD, self.CMD_SHORT)

    def stop_short_circuit(self) -> None:
        """Exit short-circuit mode by disabling input."""
        self.disable_input()


# =============================================================================
# Simple demo when run as a script
# =============================================================================

if __name__ == "__main__":
    # Quick smoke test: adjust to your actual COM, baud, address.
    list_ports()

    load = MaynuoM97(
        port="COM4",
        slave_addr=1,
        baudrate=9600,
        parity="N",
        timeout=0.5,
        debug=True,
    )

    with load:
        # Optional: enable remote control
        load.set_remote_control(True)

        # Identify device
        load.read_model_code()
        load.read_software_version()

        # Basic CC example
        load.set_cc_current(1.0)    # 1 A CC
        load.enable_input()
        v, i = load.read_voltage_current()
        print(f"Measured: {v:.3f} V, {i:.3f} A")
        load.disable_input()

        # Example dynamic test (adjust values to your hardware)
        # load.start_dynamic_test(
        #     ia_a=1.0,
        #     ib_a=3.0,
        #     ta_s=1e-3,
        #     tb_s=1e-3,
        #     rise_s=50e-6,
        #     fall_s=50e-6,
        #     mode=0,   # continuous
        # )
        # load.enable_input()
        # time.sleep(2.0)
        # load.disable_input()
