"""
Siglent SDS1104X-U / Rigol MSO5000 Series - Control Library
===========================================================
Supports USB (VISA/USBTMC — default) and LAN (socket or VISA) connections.

Covers: Connection, Channels, Timebase, Trigger, Acquisition, Measurements,
        Cursors, Math, FFT, Waveform Capture, Display, Save/Recall,
        Screenshot, Serial Decode, Reference Waveforms, Pass/Fail, Utility,
        Limit/Alarm Monitoring, Automated Characterization, Bode Plot,
        Eye Diagram Analysis, Jitter Analysis, Power Integrity Analysis.

Requirements:  pip install pyvisa pyvisa-py numpy matplotlib Pillow scipy
               (pyvisa-py is a pure-Python VISA backend — no NI-VISA needed)
               For best USB performance, also:  pip install pyusb
"""

import socket
import struct
import time
import io
import csv
import json
import threading
import datetime
import math
import numpy as np
from typing import Optional, List, Tuple, Union, Callable, Dict, Any
from dataclasses import dataclass, field, asdict


@dataclass
class RippleNoiseResult:
    """Structured ripple/noise measurement result."""
    channel: int
    vpp: float
    vrms: float
    vmean: float
    method: str
    coupling: str
    bw_limit: str
    timestamp: str


# ─────────────────────────────────────────────────────────────────────────────
#  CORE CONNECTION  (USB default, LAN fallback)
# ─────────────────────────────────────────────────────────────────────────────

class SiglentSDS1104XU:
    """Complete control interface for the Siglent SDS1104X-U oscilloscope.
    Also supports Rigol MSO5000 series in compatibility mode.

    Connection modes:
        LAN  (default):  Raw TCP socket on port 5025.
        LAN (VISA):      VXI-11/LXI via PyVISA.
        USB  (optional): Uses PyVISA over USBTMC.

    Usage:
        # LAN (default socket — connects to 192.168.4.51)
        scope = SiglentSDS1104XU()
        scope.connect()

        # LAN via VISA (VXI-11/LXI)
        scope = SiglentSDS1104XU(interface="lan", lan_mode="visa",
                                 ip="192.168.4.51")

        # LAN with different IP
        scope = SiglentSDS1104XU(ip="192.168.4.100")

        # USB (auto-detect)
        scope = SiglentSDS1104XU(interface="usb")

        # USB (explicit resource string)
        scope = SiglentSDS1104XU(interface="usb",
            resource="USB0::0xF4EC::0x1012::SDSAHBAD7R0940::INSTR")
    """

    # Siglent USB identifiers
    SIGLENT_VENDOR_IDS = (0xF4EC, 0xF4ED)  # Siglent vendor IDs
    SDS_PRODUCT_IDS = (0x1012, 0xEE3A)     # SDS1000X-U / SDS1000X-E series

    # Rigol USB identifiers (MSO5000 series)
    RIGOL_VENDOR_IDS = (0x1AB1,)
    RIGOL_PRODUCT_IDS = (0x0515,)

    # Network defaults (only used when interface="lan")
    DEFAULT_IP = "192.168.4.51"
    DEFAULT_PORT = 5025
    TIMEOUT = 5.0                 # seconds

    # Valid identifiers
    CHANNELS = ("C1", "C2", "C3", "C4")
    TRIG_TYPES = ("EDGE", "PULSE", "SLOPE", "VIDEO", "WINDOW", "DROPOUT",
                  "RUNT", "PATTERN", "QUALIFIEDGATE", "SERIAL")
    COUPLING_MODES = ("A1M", "A50", "D1M", "D50", "GND")
    BW_LIMITS = ("FULL", "20M", "200M")
    ACQ_MODES = ("SAMPLING", "PEAK_DETECT", "AVERAGE", "HIGH_RES")
    MATH_OPS = ("+", "-", "*", "/", "FFT", "INTG", "DIFF", "SQRT")
    MEAS_TYPES = (
        "PKPK", "MAX", "MIN", "AMPL", "TOP", "BASE", "CMEAN", "MEAN",
        "STDEV", "VSTD", "RMS", "CRMS", "OVSN", "FPRE", "OVSP", "RPRE",
        "FREQ", "PER", "PWID", "NWID", "RISE", "FALL", "WID", "DUTY",
        "NDUTY", "DELAY", "TIMEL", "ALL"
    )
    CURSOR_TYPES = ("OFF", "MANUAL", "TRACK", "AUTO")

    # Rigol measurement name mapping (Siglent -> Rigol)
    RIGOL_MEAS_MAP = {
        "PKPK": "VPP",
        "MAX": "VMAX",
        "MIN": "VMIN",
        "AMPL": "VAMP",
        "TOP": "VTOP",
        "BASE": "VBASE",
        "MEAN": "VAVG",
        "CMEAN": "VAVG",
        "RMS": "VRMS",
        "CRMS": "VRMS",
        "FREQ": "FREQ",
        "PER": "PER",
        "PWID": "PWID",
        "NWID": "NWID",
        "RISE": "RTIM",
        "FALL": "FTIM",
        "WID": "PWID",
        "DUTY": "PDUT",
        "NDUTY": "NDUT",
        "OVSP": "OVER",
        "OVSN": "PRES",
        "RPRE": "PRES",
        "FPRE": "PRES",
    }

    # ── Connection ────────────────────────────────────────────────────────

    def __init__(self, interface: str = "lan",
                 resource: Optional[str] = None,
                 ip: str = DEFAULT_IP, port: int = DEFAULT_PORT,
                 timeout: float = TIMEOUT,
                 lan_mode: str = "socket"):
        """
        Args:
            interface: "lan" (default) or "usb".
            resource:  Explicit VISA resource string for USB, e.g.
                       "USB0::0xF4EC::0x1012::SDSAHBAD7R0940::INSTR".
                       If interface="lan" and lan_mode="visa", this can be a
                       TCPIP resource string, e.g. "TCPIP0::192.168.4.51::inst0::INSTR".
            ip:        IP address (only for interface="lan").
            port:      TCP port  (only for interface="lan", default 5025).
            timeout:   I/O timeout in seconds.
            lan_mode:  "socket" (raw TCP, default) or "visa" (LAN VISA/VXI-11).
        """
        self.interface = interface.lower()
        self.resource = resource
        self.ip = ip
        self.port = port
        self.timeout = timeout
        self.lan_mode = lan_mode.lower()

        # Backend handles (only one is used at a time)
        self._visa_inst = None       # pyvisa instrument object
        self._visa_rm = None         # pyvisa ResourceManager
        self._sock = None            # raw TCP socket (LAN mode)

        # Identification / dialect
        self._idn = None
        self._vendor = None
        self._model = None
        self._dialect = "siglent"

    def connect(self) -> str:
        """Open connection (USB or LAN) and return *IDN? string."""
        if self.interface == "usb":
            return self._connect_usb()
        elif self.interface in ("lan", "lanvisa", "visa"):
            if self.lan_mode == "visa" or self.interface in ("lanvisa", "visa") \
                    or (self.resource and self.resource.upper().startswith("TCPIP")):
                return self._connect_lan_visa()
            return self._connect_lan()
        else:
            raise ValueError("Unsupported interface. Use 'usb' or 'lan'.")

    def _connect_usb(self) -> str:
        """Connect via USB using PyVISA.

        Tries backends in order:
          1. NI-VISA  (requires NI-VISA runtime — best Windows support)
          2. pyvisa-py (pure Python — needs libusb/pyusb)
        """
        import pyvisa

        # Try NI-VISA first (best USB support on Windows), then pyvisa-py
        for backend in ("", "@py"):
            try:
                self._visa_rm = pyvisa.ResourceManager(backend)
                resources = self._visa_rm.list_resources()
                if resources:
                    backend_name = "NI-VISA" if backend == "" else "pyvisa-py"
                    print(f"Using backend: {backend_name}")
                    break
            except Exception:
                continue
        else:
            # Last resort: try default with no resources check
            self._visa_rm = pyvisa.ResourceManager()

        if self.resource:
            # Use the explicit resource string provided
            visa_addr = self.resource
        else:
            # Auto-detect: find the first supported oscilloscope on USB
            resources = self._visa_rm.list_resources()
            visa_addr = None
            for r in resources:
                r_upper = r.upper()
                # Match by any known Siglent or Rigol vendor ID
                for vid in (*self.SIGLENT_VENDOR_IDS, *self.RIGOL_VENDOR_IDS):
                    if f"0x{vid:04X}" in r_upper or f"{vid:04X}" in r_upper:
                        visa_addr = r
                        break
                if visa_addr:
                    break
                # Fallback: any USB INSTR resource
                if "USB" in r_upper and "INSTR" in r_upper:
                    visa_addr = r
                    break

            if visa_addr is None:
                # List what we found to help the user
                if resources:
                    print("Available VISA resources (no Siglent/Rigol USB found):")
                    for r in resources:
                        print(f"  {r}")
                raise ConnectionError(
                    "No Siglent/Rigol oscilloscope found on USB.\n"
                    "Troubleshooting:\n"
                    "  1. Check USB cable is firmly connected\n"
                    "  2. Ensure scope is powered on\n"
                    "  3. Install NI-VISA runtime from ni.com/visa\n"
                    "  4. Check Device Manager for 'USB Test and "
                    "Measurement Device'\n"
                    "  5. Try providing the resource string manually:\n"
                    "     SiglentSDS1104XU(resource='USB0::...::INSTR')\n"
                    "  6. Run  SiglentSDS1104XU.list_resources()  to see "
                    "all instruments"
                )

        print(f"Connecting to: {visa_addr}")
        self._visa_inst = self._visa_rm.open_resource(visa_addr)
        self._visa_inst.timeout = int(self.timeout * 1000)  # ms
        self._visa_inst.read_termination = "\n"
        self._visa_inst.write_termination = "\n"
        # Increase chunk size for waveform transfers
        self._visa_inst.chunk_size = 4 * 1024 * 1024

        idn = self.query("*IDN?")
        self._set_dialect_from_idn(idn)
        print(f"Connected (USB): {idn}")
        return idn

    def _connect_lan(self) -> str:
        """Connect via LAN (raw TCP socket)."""
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.settimeout(self.timeout)
        self._sock.connect((self.ip, self.port))
        idn = self.query("*IDN?")
        self._set_dialect_from_idn(idn)
        print(f"Connected (LAN): {idn}")
        return idn

    def _connect_lan_visa(self) -> str:
        """Connect via LAN using VISA (e.g., VXI-11/LXI)."""
        import pyvisa

        # Try NI-VISA first (best Windows support), then pyvisa-py
        for backend in ("", "@py"):
            try:
                self._visa_rm = pyvisa.ResourceManager(backend)
                backend_name = "NI-VISA" if backend == "" else "pyvisa-py"
                print(f"Using backend: {backend_name}")
                break
            except Exception:
                continue
        else:
            self._visa_rm = pyvisa.ResourceManager()

        if self.resource:
            visa_addr = self.resource
        else:
            visa_addr = f"TCPIP0::{self.ip}::inst0::INSTR"

        print(f"Connecting to: {visa_addr}")
        self._visa_inst = self._visa_rm.open_resource(visa_addr)
        self._visa_inst.timeout = int(self.timeout * 1000)  # ms
        self._visa_inst.read_termination = "\n"
        self._visa_inst.write_termination = "\n"
        self._visa_inst.chunk_size = 4 * 1024 * 1024

        idn = self.query("*IDN?")
        self._set_dialect_from_idn(idn)
        print(f"Connected (LAN VISA): {idn}")
        return idn

    def disconnect(self):
        """Close the connection."""
        if self._visa_inst:
            self._visa_inst.close()
            self._visa_inst = None
        if self._visa_rm:
            self._visa_rm.close()
            self._visa_rm = None
        if self._sock:
            self._sock.close()
            self._sock = None
        print("Disconnected.")

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *exc):
        self.disconnect()

    @staticmethod
    def list_resources() -> list:
        """List all VISA resources (USB, LAN, GPIB, etc.).
        Useful for finding the correct resource string.
        Tries NI-VISA first, then pyvisa-py backend."""
        import pyvisa
        all_resources = []
        for backend in ("", "@py"):
            try:
                rm = pyvisa.ResourceManager(backend)
                found = list(rm.list_resources())
                rm.close()
                backend_name = "NI-VISA" if backend == "" else "pyvisa-py"
                if found:
                    print(f"Resources via {backend_name}:")
                    for r in found:
                        print(f"  {r}")
                        if r not in all_resources:
                            all_resources.append(r)
            except Exception:
                continue
        if not all_resources:
            print("No VISA resources found.")
            print("Troubleshooting:")
            print("  1. Check USB cable is connected")
            print("  2. Install NI-VISA runtime from ni.com/visa")
            print("     (or) Install libusb: pip install libusb-package")
            print("  3. Check Windows Device Manager for the scope")
        return all_resources

    def _set_dialect_from_idn(self, idn: str):
        """Detect vendor/model from *IDN? and select SCPI dialect."""
        self._idn = idn
        parts = [p.strip() for p in idn.split(",")]
        self._vendor = parts[0].upper() if parts else ""
        self._model = parts[1] if len(parts) > 1 else ""
        if "RIGOL" in self._vendor:
            self._dialect = "rigol"
        elif "SIGLENT" in self._vendor:
            self._dialect = "siglent"
        else:
            # Default to Siglent dialect for unknown vendors
            self._dialect = "siglent"

    def _is_rigol(self) -> bool:
        return self._dialect == "rigol"

    def _rigol_chan(self, ch: int) -> str:
        assert 1 <= ch <= 4, "Channel must be 1-4"
        return f"CHANnel{ch}"

    def _rigol_onoff(self, on: bool) -> str:
        return "ON" if on else "OFF"

    def _rigol_parse_onoff(self, resp: str) -> str:
        val = resp.strip().upper()
        if val in ("1", "ON", "TRUE"):
            return "ON"
        return "OFF"

    def _rigol_meas_item(self, param: str) -> Optional[str]:
        return self.RIGOL_MEAS_MAP.get(param.upper())

    def _rigol_prepare_waveform(self, ch: int) -> Dict[str, Any]:
        """Configure Rigol waveform transfer and return preamble dict."""
        self.write(f":WAVeform:SOURce {self._rigol_chan(ch)}")
        self.write(":WAVeform:FORMat BYTE")
        try:
            status = self.query(":TRIGger:STATus?").strip().upper()
        except Exception:
            status = ""
        mode = "RAW" if status in ("STOP", "TD", "WAIT") else "NORM"
        self.write(f":WAVeform:MODE {mode}")
        pre = self.get_waveform_preamble(ch)
        pre["mode"] = mode
        try:
            points = int(float(pre.get("points", 0)))
        except (ValueError, TypeError):
            points = 0
        if points > 0:
            self.write(":WAVeform:STARt 1")
            self.write(f":WAVeform:STOP {points}")
        return pre

    # ── Low-level I/O ─────────────────────────────────────────────────────

    def write(self, cmd: str):
        """Send a SCPI command (no response expected)."""
        if self._visa_inst:
            self._visa_inst.write(cmd.strip())
        elif self._sock:
            self._sock.sendall((cmd.strip() + "\n").encode())
        else:
            raise ConnectionError("Not connected. Call connect() first.")

    def read(self, size: int = 1024 * 1024) -> str:
        """Read a text response."""
        if self._visa_inst:
            return self._visa_inst.read().strip()
        elif self._sock:
            time.sleep(0.05)
            data = b""
            while True:
                try:
                    chunk = self._sock.recv(size)
                    if not chunk:
                        break
                    data += chunk
                    if data.endswith(b"\n"):
                        break
                except socket.timeout:
                    break
            return data.decode().strip()
        else:
            raise ConnectionError("Not connected.")

    def read_raw(self, size: int = 4 * 1024 * 1024) -> bytes:
        """Read raw binary response (for waveform / screenshot data)."""
        if self._visa_inst:
            return self._visa_inst.read_raw(size)
        elif self._sock:
            time.sleep(0.1)
            data = b""
            while True:
                try:
                    chunk = self._sock.recv(size)
                    if not chunk:
                        break
                    data += chunk
                except socket.timeout:
                    break
            return data
        else:
            raise ConnectionError("Not connected.")

    def query(self, cmd: str) -> str:
        """Send command and return text response."""
        if self._visa_inst:
            return self._visa_inst.query(cmd.strip()).strip()
        else:
            self.write(cmd)
            return self.read()

    def query_raw(self, cmd: str) -> bytes:
        """Send command and return binary response."""
        if self._visa_inst:
            self._visa_inst.write(cmd.strip())
            return self._visa_inst.read_raw()
        else:
            self.write(cmd)
            return self.read_raw()

    def _read_ieee_block(self) -> bytes:
        """Read an IEEE 488.2 binary block from VISA or socket."""
        if self._visa_inst:
            def _visa_read_exact(count: int, chunk: int = 65536) -> bytes:
                buf = bytearray()
                while len(buf) < count:
                    to_read = min(chunk, count - len(buf))
                    part = self._visa_inst.read_bytes(
                        to_read, chunk_size=to_read, break_on_termchar=False
                    )
                    if not part:
                        break
                    buf.extend(part)
                if len(buf) < count:
                    raise TimeoutError(
                        f"Timed out reading binary block ({len(buf)}/{count} bytes)"
                    )
                return bytes(buf)

            first = self._visa_inst.read_bytes(1, break_on_termchar=False)
            if first != b"#":
                # Not a binary block; read the rest and return raw
                rest = self._visa_inst.read_raw()
                return first + rest
            n_digits = int(self._visa_inst.read_bytes(1, break_on_termchar=False))
            length = int(self._visa_inst.read_bytes(n_digits, break_on_termchar=False))
            data = _visa_read_exact(length)
            # Try to consume trailing terminator if present
            try:
                self._visa_inst.read_bytes(1, break_on_termchar=False)
            except Exception:
                pass
            return data
        elif self._sock:
            # Read header from socket
            first = self._sock.recv(1)
            if first != b"#":
                return first + self.read_raw()
            n_digits = int(self._sock.recv(1))
            length = int(self._sock.recv(n_digits))
            data = b""
            remaining = length
            while remaining > 0:
                chunk = self._sock.recv(min(remaining, 4096))
                if not chunk:
                    break
                data += chunk
                remaining -= len(chunk)
            return data
        else:
            raise ConnectionError("Not connected.")

    def _query_binary_block(self, cmd: str) -> bytes:
        """Send command and return IEEE binary block payload."""
        if self._visa_inst:
            self._visa_inst.write(cmd.strip())
            return self._read_ieee_block()
        else:
            self.write(cmd)
            return self._read_ieee_block()

    # ── System / Utility ──────────────────────────────────────────────────

    def idn(self) -> str:
        return self.query("*IDN?")

    def reset(self):
        """Reset to factory defaults."""
        self.write("*RST")

    def clear_status(self):
        self.write("*CLS")

    def opc(self) -> str:
        """Query operation complete."""
        return self.query("*OPC?")

    def wait(self):
        """Wait until all pending operations complete."""
        self.write("*WAI")

    def get_system_status(self) -> str:
        return self.query("*STB?")

    def get_error(self) -> str:
        return self.query("SYST:ERR?")

    def buzzer(self, on: bool = True):
        self.write(f"BUZZ {'ON' if on else 'OFF'}")

    def auto_setup(self):
        """Run Auto Setup."""
        if self._is_rigol():
            self.write(":AUToscale")
        else:
            self.write("ASET")

    def force_trigger(self):
        if self._is_rigol():
            self.write(":TFORce")
        else:
            self.write("FRTR")

    def run(self):
        """Start acquisition (Run)."""
        if self._is_rigol():
            self.write(":RUN")
        else:
            self.write("TRMD AUTO")

    def stop(self):
        """Stop acquisition."""
        if self._is_rigol():
            self.write(":STOP")
        else:
            self.write("STOP")

    def single(self):
        """Single trigger acquisition."""
        if self._is_rigol():
            self.write(":SINGle")
        else:
            self.write("TRMD SINGLE")

    def normal(self):
        """Normal trigger mode."""
        if self._is_rigol():
            self.write(":TRIGger:SWEep NORMal")
        else:
            self.write("TRMD NORM")

    def get_trigger_mode(self) -> str:
        if self._is_rigol():
            return self.query(":TRIGger:SWEep?")
        return self.query("TRMD?")

    # ── Network Info ──────────────────────────────────────────────────────

    def get_ip(self) -> str:
        return self.query("COMM_NET?")

    # ─────────────────────────────────────────────────────────────────────
    #  CHANNEL CONTROL
    # ─────────────────────────────────────────────────────────────────────

    def _ch(self, ch: int) -> str:
        assert 1 <= ch <= 4, "Channel must be 1-4"
        return f"C{ch}"

    def channel_on(self, ch: int):
        if self._is_rigol():
            self.write(f":{self._rigol_chan(ch)}:DISPlay ON")
        else:
            self.write(f"{self._ch(ch)}:TRA ON")

    def channel_off(self, ch: int):
        if self._is_rigol():
            self.write(f":{self._rigol_chan(ch)}:DISPlay OFF")
        else:
            self.write(f"{self._ch(ch)}:TRA OFF")

    def get_channel_state(self, ch: int) -> str:
        if self._is_rigol():
            return self._rigol_parse_onoff(
                self.query(f":{self._rigol_chan(ch)}:DISPlay?")
            )
        return self.query(f"{self._ch(ch)}:TRA?")

    def set_coupling(self, ch: int, mode: str):
        """Set coupling: A1M (AC 1MOhm), D1M (DC 1MOhm), A50 (AC 50Ohm),
        D50 (DC 50Ohm), GND."""
        mode = mode.upper()
        if self._is_rigol():
            if mode in ("A1M", "A50", "AC"):
                rigol_mode = "AC"
            elif mode in ("D1M", "D50", "DC"):
                rigol_mode = "DC"
            elif mode == "GND":
                rigol_mode = "GND"
            else:
                rigol_mode = mode
            self.write(f":{self._rigol_chan(ch)}:COUPling {rigol_mode}")
        else:
            self.write(f"{self._ch(ch)}:CPL {mode}")

    def get_coupling(self, ch: int) -> str:
        if self._is_rigol():
            return self.query(f":{self._rigol_chan(ch)}:COUPling?")
        return self.query(f"{self._ch(ch)}:CPL?")

    def set_vdiv(self, ch: int, volts_per_div: float):
        """Set vertical scale (V/div). E.g. 0.5 = 500 mV/div."""
        if self._is_rigol():
            self.write(f":{self._rigol_chan(ch)}:SCALe {volts_per_div:.4E}")
        else:
            self.write(f"{self._ch(ch)}:VDIV {volts_per_div:.4E}V")

    def get_vdiv(self, ch: int) -> str:
        if self._is_rigol():
            return self.query(f":{self._rigol_chan(ch)}:SCALe?")
        return self.query(f"{self._ch(ch)}:VDIV?")

    def set_offset(self, ch: int, volts: float):
        """Set vertical offset in volts."""
        if self._is_rigol():
            self.write(f":{self._rigol_chan(ch)}:OFFSet {volts:.4E}")
        else:
            self.write(f"{self._ch(ch)}:OFST {volts:.4E}V")

    def get_offset(self, ch: int) -> str:
        if self._is_rigol():
            return self.query(f":{self._rigol_chan(ch)}:OFFSet?")
        return self.query(f"{self._ch(ch)}:OFST?")

    def set_probe(self, ch: int, attenuation: float):
        """Set probe attenuation ratio: 0.1, 0.2, 0.5, 1, 2, 5, 10, 20,
        50, 100, 200, 500, 1000, 2000, 5000, 10000."""
        if self._is_rigol():
            self.write(f":{self._rigol_chan(ch)}:PROBe {attenuation}")
        else:
            self.write(f"{self._ch(ch)}:ATTN {attenuation}")

    def get_probe(self, ch: int) -> str:
        if self._is_rigol():
            return self.query(f":{self._rigol_chan(ch)}:PROBe?")
        return self.query(f"{self._ch(ch)}:ATTN?")

    def set_bw_limit(self, ch: int, bw: str = "FULL"):
        """Set bandwidth limit: FULL, 20M, 200M."""
        if self._is_rigol():
            bw_u = bw.upper()
            if bw_u == "FULL":
                bw_u = "OFF"
            self.write(f":{self._rigol_chan(ch)}:BWLimit {bw_u}")
        else:
            self.write(f"BWL {self._ch(ch)},{bw.upper()}")

    def get_bw_limit(self, ch: int) -> str:
        if self._is_rigol():
            return self.query(f":{self._rigol_chan(ch)}:BWLimit?")
        return self.query(f"{self._ch(ch)}:BWL?")

    def set_skew(self, ch: int, seconds: float):
        """Set channel deskew in seconds."""
        if self._is_rigol():
            # Rigol uses TCALibrate for per-channel time calibration
            self.write(f":{self._rigol_chan(ch)}:TCALibrate {seconds:.4E}")
        else:
            self.write(f"{self._ch(ch)}:SKEW {seconds:.4E}S")

    def get_skew(self, ch: int) -> str:
        if self._is_rigol():
            return self.query(f":{self._rigol_chan(ch)}:TCALibrate?")
        return self.query(f"{self._ch(ch)}:SKEW?")

    def set_invert(self, ch: int, on: bool):
        if self._is_rigol():
            self.write(f":{self._rigol_chan(ch)}:INVert {self._rigol_onoff(on)}")
        else:
            self.write(f"{self._ch(ch)}:INVS {'ON' if on else 'OFF'}")

    def get_invert(self, ch: int) -> str:
        if self._is_rigol():
            return self.query(f":{self._rigol_chan(ch)}:INVert?")
        return self.query(f"{self._ch(ch)}:INVS?")

    def set_unit(self, ch: int, unit: str = "V"):
        """Set vertical unit: V or A."""
        if self._is_rigol():
            unit_u = unit.upper()
            if unit_u in ("V", "VOLT", "VOLTAGE"):
                rigol_unit = "VOLTage"
            elif unit_u in ("A", "AMP", "AMPERE"):
                rigol_unit = "AMPere"
            else:
                rigol_unit = unit
            self.write(f":{self._rigol_chan(ch)}:UNITs {rigol_unit}")
        else:
            self.write(f"{self._ch(ch)}:UNIT {unit.upper()}")

    def get_unit(self, ch: int) -> str:
        if self._is_rigol():
            resp = self.query(f":{self._rigol_chan(ch)}:UNITs?")
            resp_u = resp.strip().upper()
            if resp_u.startswith("VOLT"):
                return "V"
            if resp_u.startswith("AMP"):
                return "A"
            return resp
        return self.query(f"{self._ch(ch)}:UNIT?")

    # ─────────────────────────────────────────────────────────────────────
    #  TIMEBASE
    # ─────────────────────────────────────────────────────────────────────

    def set_tdiv(self, seconds_per_div: float):
        """Set time/div. E.g. 1e-6 = 1 µs/div."""
        if self._is_rigol():
            self.write(f":TIMebase:MAIN:SCALe {seconds_per_div:.4E}")
        else:
            self.write(f"TDIV {seconds_per_div:.4E}S")

    def get_tdiv(self) -> str:
        if self._is_rigol():
            return self.query(":TIMebase:MAIN:SCALe?")
        return self.query("TDIV?")

    def set_time_offset(self, seconds: float):
        """Set horizontal trigger offset (delay)."""
        if self._is_rigol():
            self.write(f":TIMebase:MAIN:OFFSet {seconds:.4E}")
        else:
            self.write(f"TRDL {seconds:.4E}S")

    def get_time_offset(self) -> str:
        if self._is_rigol():
            return self.query(":TIMebase:MAIN:OFFSet?")
        return self.query("TRDL?")

    def set_sara(self) -> str:
        """Query the sample rate."""
        return self.get_sample_rate()

    def get_sample_rate(self) -> str:
        if self._is_rigol():
            try:
                return self.query(":ACQuire:SRATe?")
            except Exception:
                try:
                    self.write(f":WAVeform:SOURce {self._rigol_chan(1)}")
                    pre = self.get_waveform_preamble(1)
                    xinc = float(pre.get("xinc", 0))
                    if xinc > 0:
                        return f"{1.0 / xinc:.6E}"
                except Exception:
                    pass
                return "nan"
        return self.query("SARA?")

    def get_memory_size(self) -> str:
        if self._is_rigol():
            return self.query(":ACQuire:MDEPth?")
        return self.query("MSIZ?")

    def set_memory_size(self, size: str):
        """Set memory depth: 7K, 70K, 700K, 7M, 14K, 140K, 1.4M, 14M."""
        if self._is_rigol():
            self.write(f":ACQuire:MDEPth {size}")
        else:
            self.write(f"MSIZ {size}")

    def set_hor_magnify(self, on: bool):
        if self._is_rigol():
            self.write(f":TIMebase:DELay:ENABle {self._rigol_onoff(on)}")
        else:
            self.write(f"HMAG {'ON' if on else 'OFF'}")

    def set_hor_magnify_scale(self, seconds_per_div: float):
        if self._is_rigol():
            self.write(f":TIMebase:DELay:SCALe {seconds_per_div:.4E}")
        else:
            self.write(f"HMAG:TDIV {seconds_per_div:.4E}S")

    def set_hor_magnify_position(self, seconds: float):
        if self._is_rigol():
            self.write(f":TIMebase:DELay:OFFSet {seconds:.4E}")
        else:
            self.write(f"HMAG:POS {seconds:.4E}S")

    # ─────────────────────────────────────────────────────────────────────
    #  TRIGGER
    # ─────────────────────────────────────────────────────────────────────

    def set_trigger_type(self, trig_type: str):
        """EDGE, PULSE, SLOPE, VIDEO, WINDOW, DROPOUT, RUNT, PATTERN, etc."""
        if self._is_rigol():
            t = trig_type.upper()
            rigol_map = {
                "PULSE": "PULS",
                "SLOPE": "SLOP",
                "VIDEO": "VID",
                "WINDOW": "WIND",
                "RUNT": "RUNT",
                "EDGE": "EDGE",
            }
            self.write(f":TRIGger:MODE {rigol_map.get(t, t)}")
        else:
            self.write(f"TRSE {trig_type.upper()}")

    def get_trigger_type(self) -> str:
        if self._is_rigol():
            return self.query(":TRIGger:MODE?")
        return self.query("TRSE?")

    # ── Edge Trigger ──
    def set_trig_edge_source(self, ch: int):
        if self._is_rigol():
            self.write(f":TRIGger:EDGE:SOURce {self._rigol_chan(ch)}")
        else:
            self.write(f"{self._ch(ch)}:TRCP EDGE")

    def set_trig_level(self, ch: int, volts: float):
        """Set trigger level for a channel."""
        if self._is_rigol():
            self.write(f":TRIGger:EDGE:LEVel {volts:.4E}")
        else:
            self.write(f"{self._ch(ch)}:TRLV {volts:.4E}V")

    def get_trig_level(self, ch: int) -> str:
        if self._is_rigol():
            return self.query(":TRIGger:EDGE:LEVel?")
        return self.query(f"{self._ch(ch)}:TRLV?")

    def set_trig_slope(self, slope: str = "POS"):
        """Set edge trigger slope: POS, NEG, WINDOW."""
        if self._is_rigol():
            slope_u = slope.upper()
            if slope_u in ("POS", "POSITIVE", "RISING"):
                rigol_slope = "POSitive"
            elif slope_u in ("NEG", "NEGATIVE", "FALLING"):
                rigol_slope = "NEGative"
            else:
                rigol_slope = slope_u
            self.write(f":TRIGger:EDGE:SLOPe {rigol_slope}")
        else:
            self.write(f"TRSL {slope.upper()}")

    def get_trig_slope(self) -> str:
        if self._is_rigol():
            return self.query(":TRIGger:EDGE:SLOPe?")
        return self.query("TRSL?")

    def set_trig_coupling(self, mode: str = "DC"):
        """Set trigger coupling: AC, DC, HFREJ, LFREJ."""
        if self._is_rigol():
            mode_u = mode.upper()
            if mode_u in ("HFREJ", "HFREJECT"):
                rigol_mode = "HFR"
            elif mode_u in ("LFREJ", "LFREJECT"):
                rigol_mode = "LFR"
            else:
                rigol_mode = mode_u
            self.write(f":TRIGger:COUPling {rigol_mode}")
        else:
            self.write(f"TRCP {mode.upper()}")

    def get_trig_coupling(self) -> str:
        if self._is_rigol():
            return self.query(":TRIGger:COUPling?")
        return self.query("TRCP?")

    def set_trig_holdoff(self, seconds: float):
        if self._is_rigol():
            self.write(f":TRIGger:HOLDoff {seconds:.4E}")
        else:
            self.write(f"TRHO {seconds:.4E}S")

    def get_trig_holdoff(self) -> str:
        if self._is_rigol():
            return self.query(":TRIGger:HOLDoff?")
        return self.query("TRHO?")

    # ── Edge trigger (full setup) ──
    def setup_edge_trigger(self, source_ch: int, level: float,
                           slope: str = "POS", coupling: str = "DC",
                           mode: str = "AUTO"):
        """One-call edge trigger configuration."""
        if self._is_rigol():
            self.write(":TRIGger:MODE EDGE")
            self.write(f":TRIGger:EDGE:SOURce {self._rigol_chan(source_ch)}")
            self.write(f":TRIGger:EDGE:LEVel {level:.4E}")
            self.set_trig_slope(slope)
            self.set_trig_coupling(coupling)
            mode_u = mode.upper()
            if mode_u in ("AUTO",):
                rigol_mode = "AUTO"
            elif mode_u in ("NORM", "NORMAL"):
                rigol_mode = "NORMal"
            elif mode_u in ("SINGLE", "SING"):
                rigol_mode = "SINGle"
            else:
                rigol_mode = mode_u
            self.write(f":TRIGger:SWEep {rigol_mode}")
        else:
            self.write(f"TRSE EDGE,SR,{self._ch(source_ch)},HT,OFF")
            self.set_trig_level(source_ch, level)
            self.set_trig_slope(slope)
            self.set_trig_coupling(coupling)
            self.write(f"TRMD {mode.upper()}")

    # ── Pulse Trigger ──
    def setup_pulse_trigger(self, source_ch: int, level: float,
                            condition: str = "P2", width: float = 1e-6):
        """Pulse width trigger.
        condition: P1=positive >, P2=positive <, P9=positive =,
                   N1=negative >, N2=negative <, N9=negative =
        """
        self.write(f"TRSE PULSE,SR,{self._ch(source_ch)},HT,PL,"
                   f"HV,{width:.4E}S")
        self.set_trig_level(source_ch, level)

    # ── Slope Trigger ──
    def setup_slope_trigger(self, source_ch: int, level_high: float,
                            level_low: float, condition: str = "RIS",
                            time_limit: float = 1e-6):
        """Slope trigger. condition: RIS, FALL."""
        self.write(f"TRSE SLOPE,SR,{self._ch(source_ch)},HT,TI,"
                   f"HV,{time_limit:.4E}S")
        self.write(f"{self._ch(source_ch)}:TRLV {level_high:.4E}V")
        self.write(f"{self._ch(source_ch)}:TRLV2 {level_low:.4E}V")

    # ── Video Trigger ──
    def setup_video_trigger(self, source_ch: int, standard: str = "NTSC",
                            sync: str = "LINE", line_num: int = 1):
        """Video trigger. standard: NTSC, PAL, SECAM, 480P, 576P, 720P,
        1080I, 1080P. sync: LINE, FIELD, ODD, EVEN, LINEN."""
        self.write(f"TRSE VIDEO,SR,{self._ch(source_ch)},STAN,{standard},"
                   f"SYNC,{sync}")

    # ── Dropout Trigger ──
    def setup_dropout_trigger(self, source_ch: int, level: float,
                              time_val: float, slope: str = "POS"):
        self.write(f"TRSE DROPOUT,SR,{self._ch(source_ch)},HT,TI,"
                   f"HV,{time_val:.4E}S,SL,{slope}")
        self.set_trig_level(source_ch, level)

    # ── Runt Trigger ──
    def setup_runt_trigger(self, source_ch: int, level_high: float,
                           level_low: float, condition: str = "NONE"):
        """condition: NONE, GT (>), LT (<), EQ (=)."""
        self.write(f"TRSE RUNT,SR,{self._ch(source_ch)},HT,{condition}")
        self.write(f"{self._ch(source_ch)}:TRLV {level_high:.4E}V")
        self.write(f"{self._ch(source_ch)}:TRLV2 {level_low:.4E}V")

    # ── Window Trigger ──
    def setup_window_trigger(self, source_ch: int, level_high: float,
                             level_low: float):
        self.write(f"TRSE WINDOW,SR,{self._ch(source_ch)}")
        self.write(f"{self._ch(source_ch)}:TRLV {level_high:.4E}V")
        self.write(f"{self._ch(source_ch)}:TRLV2 {level_low:.4E}V")

    # ── Pattern Trigger ──
    def setup_pattern_trigger(self, c1: str = "X", c2: str = "X",
                              c3: str = "X", c4: str = "X"):
        """Pattern trigger. Each channel: H (high), L (low), X (don't care),
        R (rising), F (falling)."""
        self.write(f"TRSE PATTERN,SR,C1,PA,{c1},C2,PA,{c2},"
                   f"C3,PA,{c3},C4,PA,{c4}")

    # ── Trigger 50% ──
    def trig_50(self):
        """Set trigger level to signal midpoint."""
        self.write("SET50")

    # ─────────────────────────────────────────────────────────────────────
    #  ACQUISITION
    # ─────────────────────────────────────────────────────────────────────

    def set_acquire_mode(self, mode: str = "SAMPLING"):
        """SAMPLING, PEAK_DETECT, AVERAGE, HIGH_RES."""
        if self._is_rigol():
            mode_u = mode.upper()
            if mode_u == "SAMPLING":
                rigol_mode = "NORMal"
            elif mode_u == "PEAK_DETECT":
                rigol_mode = "PEAK"
            elif mode_u == "AVERAGE":
                rigol_mode = "AVERages"
            elif mode_u == "HIGH_RES":
                rigol_mode = "HRESolution"
            else:
                rigol_mode = mode_u
            self.write(f":ACQuire:TYPE {rigol_mode}")
        else:
            self.write(f"ACQW {mode.upper()}")

    def get_acquire_mode(self) -> str:
        if self._is_rigol():
            resp = self.query(":ACQuire:TYPE?")
            resp_u = resp.strip().upper()
            if resp_u.startswith("NORM"):
                return "SAMPLING"
            if resp_u.startswith("PEAK"):
                return "PEAK_DETECT"
            if resp_u.startswith("AVER"):
                return "AVERAGE"
            if resp_u.startswith("HRES"):
                return "HIGH_RES"
            return resp
        return self.query("ACQW?")

    def set_average_count(self, count: int):
        """Set number of averages: 4, 16, 32, 64, 128, 256, 512, 1024."""
        if self._is_rigol():
            self.write(f":ACQuire:AVERages {count}")
        else:
            self.write(f"AVGA {count}")

    def get_average_count(self) -> str:
        if self._is_rigol():
            return self.query(":ACQuire:AVERages?")
        return self.query("AVGA?")

    def set_interpolation(self, mode: str = "SINX"):
        """SINX (sin(x)/x) or LINEAR."""
        self.write(f"INTS {mode.upper()}")

    def set_sequence(self, on: bool, count: int = 1):
        """Enable/disable sequence (segmented) acquisition."""
        if on:
            self.write(f"SEQ ON,{count}")
        else:
            self.write("SEQ OFF")

    def get_sequence_count(self) -> str:
        return self.query("SEQ?")

    def set_xy_mode(self, on: bool):
        """Enable/disable X-Y display mode."""
        if self._is_rigol():
            self.write(f":TIMebase:MODE {'XY' if on else 'MAIN'}")
        else:
            self.write(f"XYDS {'ON' if on else 'OFF'}")

    # ─────────────────────────────────────────────────────────────────────
    #  MEASUREMENTS
    # ─────────────────────────────────────────────────────────────────────

    def measure(self, ch: int, param: str) -> str:
        """Take a single measurement.
        param: PKPK, MAX, MIN, AMPL, TOP, BASE, CMEAN, MEAN, STDEV,
               RMS, CRMS, OVSN, FPRE, OVSP, RPRE, FREQ, PER,
               PWID, NWID, RISE, FALL, WID, DUTY, NDUTY, ALL, etc.
        """
        if self._is_rigol():
            item = self._rigol_meas_item(param)
            if not item:
                raise ValueError(f"Unsupported measurement for Rigol: {param}")
            try:
                return self.query(f":MEASure:ITEM? {item},{self._rigol_chan(ch)}")
            except Exception:
                self.write(f":MEASure:SOURce {self._rigol_chan(ch)}")
                return self.query(f":MEASure:ITEM? {item}")
        return self.query(f"{self._ch(ch)}:PAVA? {param.upper()}")

    def measure_value(self, ch: int, param: str) -> float:
        """Return a numeric measurement value."""
        try:
            resp = self.measure(ch, param)
            # typical format: "C1:PAVA FREQ,1.000000E+03Hz"
            try:
                val_str = resp.split(",")[1]
            except IndexError:
                val_str = resp
            num = "".join(c for c in val_str if c in "0123456789.eE+-")
            val = float(num)
            if self._is_rigol() and abs(val) > 1e36:
                return float("nan")
            return val
        except Exception:
            return float("nan")

    def measure_pkpk(self, ch: int) -> float:
        """Convenience: measure peak-to-peak voltage."""
        return self.measure_value(ch, "PKPK")

    def measure_ripple_noise(
        self,
        ch: int,
        ac_coupling: bool = True,
        bw_limit: str = "20M",
        vdiv: Optional[float] = None,
        acquire_mode: str = "HIGH_RES",
        average_count: int = 16,
        settle: float = 0.5,
        fallback_waveform: bool = True,
    ) -> RippleNoiseResult:
        """Measure ripple (Vpp) and noise (Vrms) on a channel.

        Args:
            ch: Channel number (1-4)
            ac_coupling: If True, set AC coupling for ripple/noise measurement.
            bw_limit: Bandwidth limit (e.g., "20M", "FULL").
            vdiv: Optional vertical scale to set (V/div).
            acquire_mode: Acquisition mode ("HIGH_RES", "AVERAGE", etc.).
            average_count: Average count if using AVERAGE mode.
            settle: Seconds to wait after setup.
            fallback_waveform: If SCPI returns NaN, compute from waveform data.
        """
        coupling = "A1M" if ac_coupling else "D1M"
        try:
            self.set_coupling(ch, coupling)
        except Exception:
            pass
        try:
            if bw_limit:
                self.set_bw_limit(ch, bw_limit)
        except Exception:
            pass
        try:
            if vdiv is not None:
                self.set_vdiv(ch, vdiv)
        except Exception:
            pass

        try:
            if acquire_mode:
                self.set_acquire_mode(acquire_mode)
            if acquire_mode.upper() == "AVERAGE":
                self.set_average_count(average_count)
        except Exception:
            pass

        try:
            self.run()
        except Exception:
            pass
        if settle > 0:
            time.sleep(settle)

        vpp = self.measure_value(ch, "PKPK")
        vrms = self.measure_value(ch, "RMS")
        vmean = self.measure_value(ch, "MEAN")
        method = "scpi"

        if fallback_waveform and (math.isnan(vpp) or math.isnan(vrms)):
            try:
                _, v = self.get_waveform(ch)
                if v.size > 0:
                    vmean = float(np.mean(v))
                    v_ac = v - vmean
                    vpp = float(v_ac.max() - v_ac.min())
                    vrms = float(np.sqrt(np.mean(v_ac ** 2)))
                    method = "waveform"
            except Exception:
                pass

        return RippleNoiseResult(
            channel=ch,
            vpp=vpp,
            vrms=vrms,
            vmean=vmean,
            method=method,
            coupling=coupling,
            bw_limit=bw_limit,
            timestamp=datetime.datetime.now().isoformat(timespec="seconds"),
        )

    def measure_all(self, ch: int) -> str:
        """Return all automatic measurements for a channel."""
        if self._is_rigol():
            raise NotImplementedError("Rigol: measure_all is not supported.")
        return self.query(f"{self._ch(ch)}:PAVA? ALL")

    def add_measurement(self, ch: int, param: str):
        """Add a measurement to the on-screen display."""
        if self._is_rigol():
            item = self._rigol_meas_item(param)
            if not item:
                raise ValueError(f"Unsupported measurement for Rigol: {param}")
            try:
                self.write(f":MEASure:ITEM {item},{self._rigol_chan(ch)}")
            except Exception:
                self.write(f":MEASure:SOURce {self._rigol_chan(ch)}")
                self.write(f":MEASure:ITEM {item}")
        else:
            self.write(f"PACU {param.upper()},{self._ch(ch)}")

    def clear_measurements(self):
        """Remove all on-screen measurements."""
        if self._is_rigol():
            self.write(":MEASure:CLEar ALL")
        else:
            self.write("PACU CLR")

    def set_statistics(self, on: bool):
        """Enable/disable measurement statistics display."""
        if self._is_rigol():
            self.write(f":MEASure:STATistic:DISPlay {self._rigol_onoff(on)}")
        else:
            self.write(f"PAST {'ON' if on else 'OFF'}")

    def reset_statistics(self):
        if self._is_rigol():
            self.write(":MEASure:STATistic:RESet")
        else:
            self.write("PAST RESET")

    def get_statistics(self, ch: int, param: str) -> str:
        if self._is_rigol():
            return self.measure(ch, param)
        return self.query(f"{self._ch(ch)}:PAVA? {param.upper()}")

    # ── Frequency Counter ──
    def set_counter(self, on: bool, ch: int = 1):
        if self._is_rigol():
            self.write(f":COUNter:SOURce {self._rigol_chan(ch)}")
            self.write(f":COUNter:ENABle {self._rigol_onoff(on)}")
        else:
            if on:
                self.write(f"FCNT {self._ch(ch)}")
            else:
                self.write("FCNT OFF")

    def get_counter(self) -> str:
        if self._is_rigol():
            return self.query(":COUNter:ENABle?")
        return self.query("FCNT?")

    # ─────────────────────────────────────────────────────────────────────
    #  CURSORS
    # ─────────────────────────────────────────────────────────────────────

    def set_cursor_type(self, cursor_type: str = "MANUAL"):
        """OFF, MANUAL, TRACK, AUTO."""
        self.write(f"CRST {cursor_type.upper()}")

    def get_cursor_type(self) -> str:
        return self.query("CRST?")

    def set_cursor_mode(self, mode: str = "TIME"):
        """TIME or AMPL (voltage)."""
        self.write(f"CRMS {mode.upper()}")

    def set_cursor_source(self, ch: int):
        self.write(f"CRCH {self._ch(ch)}")

    def set_cursor_positions(self, pos_a: float, pos_b: float):
        """Set both cursor positions (time or voltage depending on mode)."""
        self.write(f"CRVA {pos_a:.4E}")
        self.write(f"CRVB {pos_b:.4E}")

    def get_cursor_values(self) -> str:
        """Get delta and individual cursor values."""
        return self.query("CRVA?") + " | " + self.query("CRVB?")

    def set_cursor_hpos(self, a: float, b: float):
        """Set horizontal cursor positions (time domain)."""
        self.write(f"CRHA {a:.4E}S")
        self.write(f"CRHB {b:.4E}S")

    def set_cursor_vpos(self, a: float, b: float):
        """Set vertical cursor positions (voltage domain)."""
        self.write(f"CRVA {a:.4E}V")
        self.write(f"CRVB {b:.4E}V")

    # ─────────────────────────────────────────────────────────────────────
    #  MATH / FFT
    # ─────────────────────────────────────────────────────────────────────

    def set_math(self, operation: str, src1: int = 1, src2: int = 2):
        """Set math operation: +, -, *, /, FFT, INTG, DIFF, SQRT."""
        op = operation.upper()
        if op == "FFT":
            self.write(f"MATH DEFINE,EQN,'FFT({self._ch(src1)})'")
        elif op in ("INTG", "DIFF", "SQRT"):
            self.write(f"MATH DEFINE,EQN,'{op}({self._ch(src1)})'")
        else:
            self.write(f"MATH DEFINE,EQN,"
                       f"'{self._ch(src1)}{op}{self._ch(src2)}'")

    def math_on(self):
        self.write("MATH:TRA ON")

    def math_off(self):
        self.write("MATH:TRA OFF")

    def get_math_define(self) -> str:
        return self.query("MATH:DEFINE?")

    def set_math_vdiv(self, volts_per_div: float):
        self.write(f"MATH:VDIV {volts_per_div:.4E}V")

    def set_math_offset(self, volts: float):
        self.write(f"MATH:OFST {volts:.4E}V")

    # ── FFT specific ──
    def set_fft_window(self, window: str = "HANNING"):
        """RECT, HANNING, HAMMING, BLACKMAN, FLATTOP."""
        self.write(f"FFT:WINDOW {window.upper()}")

    def set_fft_scale(self, db_per_div: float):
        self.write(f"FFT:VDIV {db_per_div:.4E}")

    def set_fft_center(self, freq_hz: float):
        self.write(f"FFT:CENTER {freq_hz:.4E}HZ")

    def set_fft_span(self, freq_hz: float):
        self.write(f"FFT:SPAN {freq_hz:.4E}HZ")

    def set_fft_source(self, ch: int):
        self.write(f"FFT:SRCCH {self._ch(ch)}")

    def fft_on(self):
        self.set_math("FFT", 1)
        self.math_on()

    def fft_off(self):
        self.math_off()

    # ─────────────────────────────────────────────────────────────────────
    #  WAVEFORM DATA TRANSFER
    # ─────────────────────────────────────────────────────────────────────

    def set_waveform_source(self, source: str = "C1"):
        """C1-C4, MATH, D0-D15, ALL_DISPLAYED."""
        if self._is_rigol():
            src = source.upper()
            if src.startswith("C") and len(src) == 2 and src[1].isdigit():
                src = f"CHANnel{int(src[1])}"
            self.write(f":WAVeform:SOURce {src}")
        else:
            self.write(f"WFSU SP,0,NP,0,FP,0")

    def get_waveform_preamble(self, ch: int) -> dict:
        """Get waveform descriptor fields needed to scale raw data."""
        if self._is_rigol():
            raw = self.query(":WAVeform:PREamble?")
            parts = [p.strip() for p in raw.split(",")]
            info = {}
            if len(parts) >= 10:
                info = {
                    "format": int(float(parts[0])),
                    "type": int(float(parts[1])),
                    "points": int(float(parts[2])),
                    "count": int(float(parts[3])),
                    "xinc": float(parts[4]),
                    "xorig": float(parts[5]),
                    "xref": float(parts[6]),
                    "yinc": float(parts[7]),
                    "yorig": float(parts[8]),
                    "yref": float(parts[9]),
                }
            return info
        raw = self.query(f"{self._ch(ch)}:INSP? 'WAVEDESC'")
        info = {}
        for line in raw.split("\n"):
            if ":" in line:
                key, _, val = line.partition(":")
                info[key.strip()] = val.strip()
        return info

    def get_waveform_raw(self, ch: int) -> bytes:
        """Download raw waveform data from channel."""
        if self._is_rigol():
            self._rigol_prepare_waveform(ch)
            return self._query_binary_block(":WAVeform:DATA?")
        self.write(f"WFSU SP,0,NP,0,FP,0")
        return self.query_raw(f"{self._ch(ch)}:WF? DAT2")

    def get_waveform(self, ch: int) -> Tuple[np.ndarray, np.ndarray]:
        """Download waveform and return (time_array, voltage_array).

        Returns numpy arrays ready for plotting.
        """
        if self._is_rigol():
            pre = self._rigol_prepare_waveform(ch)
            mode = pre.get("mode", "NORM")
            try:
                points = int(float(pre.get("points", 0)))
            except (ValueError, TypeError):
                points = 0

            prev_timeout = self._visa_inst.timeout if self._visa_inst else None
            if self._visa_inst and points > 1_000_000:
                self._visa_inst.timeout = max(self._visa_inst.timeout, 60000)

            try:
                wave_bytes = self._query_binary_block(":WAVeform:DATA?")
            except Exception:
                # Fallback: force a small NORM transfer
                try:
                    self.write(":WAVeform:MODE NORM")
                    self.write(":WAVeform:STARt 1")
                    self.write(":WAVeform:STOP 1000")
                    pre = self.get_waveform_preamble(ch)
                    wave_bytes = self._query_binary_block(":WAVeform:DATA?")
                except Exception:
                    raise
            finally:
                if self._visa_inst and prev_timeout is not None:
                    self._visa_inst.timeout = prev_timeout

            data = np.frombuffer(wave_bytes, dtype=np.uint8)

            xinc = float(pre.get("xinc", 1.0))
            xorig = float(pre.get("xorig", 0.0))
            xref = float(pre.get("xref", 0.0))
            yinc = float(pre.get("yinc", 1.0))
            yorig = float(pre.get("yorig", 0.0))
            yref = float(pre.get("yref", 0.0))

            voltage = (data - yorig - yref) * yinc
            time_arr = (np.arange(len(voltage)) - xref) * xinc + xorig
            return time_arr, voltage

        # Get parameters
        vdiv = float(self.query(f"{self._ch(ch)}:VDIV?").split()[-1]
                      .replace("V", ""))
        ofst = float(self.query(f"{self._ch(ch)}:OFST?").split()[-1]
                      .replace("V", ""))
        tdiv = float(self.query("TDIV?").split()[-1].replace("S", ""))
        sara_str = self.query("SARA?")
        sara_val = sara_str.split()[-1].replace("Sa/s", "").replace("GSa/s", "e9") \
            .replace("MSa/s", "e6").replace("kSa/s", "e3")
        try:
            sara = float(sara_val)
        except ValueError:
            sara = 1e9  # fallback

        # Download binary data
        raw = self.query_raw(f"{self._ch(ch)}:WF? DAT2")

        # Parse IEEE 488.2 binary block header
        # Format: #<n><length><data>
        header_start = raw.find(b"#")
        if header_start < 0:
            raise ValueError("No binary block header found in waveform data")

        n_digits = int(chr(raw[header_start + 1]))
        data_len = int(raw[header_start + 2:header_start + 2 + n_digits])
        data_start = header_start + 2 + n_digits
        wave_bytes = raw[data_start:data_start + data_len]

        # Convert to voltage
        adc = np.frombuffer(wave_bytes, dtype=np.int8)
        voltage = adc * (vdiv / 25.0) - ofst
        num_pts = len(voltage)

        # Generate time axis
        t_total = tdiv * 14  # 14 horizontal divisions
        time_arr = np.linspace(-t_total / 2, t_total / 2, num_pts)

        return time_arr, voltage

    def get_waveform_math(self) -> bytes:
        """Download math waveform raw data."""
        if self._is_rigol():
            self.write(":WAVeform:SOURce MATH")
            self.write(":WAVeform:FORMat BYTE")
            self.write(":WAVeform:MODE NORM")
            return self._query_binary_block(":WAVeform:DATA?")
        return self.query_raw("MATH:WF? DAT2")

    # ─────────────────────────────────────────────────────────────────────
    #  DISPLAY
    # ─────────────────────────────────────────────────────────────────────

    def set_grid(self, style: str = "FULL"):
        """FULL, HALF, OFF."""
        if self._is_rigol():
            self.write(f":DISPlay:GRID {style.upper()}")
        else:
            self.write(f"GRDS {style.upper()}")

    def get_grid(self) -> str:
        if self._is_rigol():
            return self.query(":DISPlay:GRID?")
        return self.query("GRDS?")

    def set_intensity(self, grid: int = 50, trace: int = 50):
        """Set grid and trace intensity (0-100)."""
        if self._is_rigol():
            self.write(f":DISPlay:GBRightness {grid}")
            self.write(f":DISPlay:WBRightness {trace}")
        else:
            self.write(f"INTS GRID,{grid},TRACE,{trace}")

    def set_persistence(self, mode: str = "OFF"):
        """OFF, 1S, 2S, 5S, 10S, INFINITE."""
        if self._is_rigol():
            mode_u = mode.upper()
            if mode_u == "OFF":
                self.write(":DISPlay:GRADing OFF")
            else:
                self.write(":DISPlay:GRADing ON")
                if mode_u == "INFINITE":
                    self.write(":DISPlay:GRADing:TIME INF")
                else:
                    val = mode_u.replace("S", "")
                    self.write(f":DISPlay:GRADing:TIME {val}")
        else:
            self.write(f"PESU {mode.upper()}")

    def get_persistence(self) -> str:
        if self._is_rigol():
            return self.query(":DISPlay:GRADing:TIME?")
        return self.query("PESU?")

    def clear_sweeps(self):
        """Clear persistence / accumulated display."""
        if self._is_rigol():
            self.write(":DISPlay:CLEar")
        else:
            self.write("CLSW")

    def set_display_type(self, dtype: str = "YT"):
        """YT or XY."""
        if self._is_rigol():
            dtype_u = dtype.upper()
            if dtype_u in ("DOTS", "VECT", "VECTORS"):
                self.write(f":DISPlay:TYPE {dtype_u}")
            elif dtype_u == "XY":
                self.set_xy_mode(True)
            else:
                self.set_xy_mode(False)
        else:
            self.write(f"DTJN {dtype.upper()}")

    def set_color_display(self, on: bool):
        """Temperature (color grading) display."""
        if self._is_rigol():
            self.write(f":DISPlay:COLor {self._rigol_onoff(on)}")
        else:
            self.write(f"COLR {'ON' if on else 'OFF'}")

    # ─────────────────────────────────────────────────────────────────────
    #  SCREENSHOT
    # ─────────────────────────────────────────────────────────────────────

    def screenshot(self, filename: str = "screenshot.bmp"):
        """Capture and save a screenshot (BMP format)."""
        if self._is_rigol():
            prev_timeout = self._visa_inst.timeout if self._visa_inst else None
            if self._visa_inst and (prev_timeout is None or prev_timeout < 20000):
                self._visa_inst.timeout = 20000  # allow larger transfers
            data = self._query_binary_block(":DISPlay:DATA?")
            if self._visa_inst and prev_timeout is not None:
                self._visa_inst.timeout = prev_timeout
        else:
            data = self.query_raw("SCDP")
        with open(filename, "wb") as f:
            f.write(data)
        print(f"Screenshot saved: {filename} ({len(data)} bytes)")
        return filename

    def screenshot_png(self, filename: str = "screenshot.png"):
        """Capture screenshot and convert to PNG (requires Pillow)."""
        from PIL import Image
        if self._is_rigol():
            prev_timeout = self._visa_inst.timeout if self._visa_inst else None
            if self._visa_inst and (prev_timeout is None or prev_timeout < 20000):
                self._visa_inst.timeout = 20000  # allow larger transfers
            bmp_data = self._query_binary_block(":DISPlay:DATA?")
            if self._visa_inst and prev_timeout is not None:
                self._visa_inst.timeout = prev_timeout
        else:
            bmp_data = self.query_raw("SCDP")
        img = Image.open(io.BytesIO(bmp_data))
        img.save(filename, "PNG")
        print(f"Screenshot saved: {filename}")
        return filename

    # ─────────────────────────────────────────────────────────────────────
    #  SAVE / RECALL
    # ─────────────────────────────────────────────────────────────────────

    def save_setup(self, slot: int):
        """Save current setup to internal memory (slot 1-20)."""
        self.write(f"*SAV {slot}")

    def recall_setup(self, slot: int):
        """Recall setup from internal memory."""
        self.write(f"*RCL {slot}")

    def save_waveform_csv(self, ch: int, filename: str):
        """Download waveform and save to CSV."""
        time_arr, voltage = self.get_waveform(ch)
        with open(filename, "w") as f:
            f.write("Time(s),Voltage(V)\n")
            for t, v in zip(time_arr, voltage):
                f.write(f"{t:.10E},{v:.6E}\n")
        print(f"Waveform CSV saved: {filename} ({len(time_arr)} points)")

    def save_waveform_numpy(self, ch: int, filename: str):
        """Download waveform and save as .npz."""
        time_arr, voltage = self.get_waveform(ch)
        np.savez(filename, time=time_arr, voltage=voltage)
        print(f"Waveform saved: {filename}")

    # ─────────────────────────────────────────────────────────────────────
    #  REFERENCE WAVEFORMS
    # ─────────────────────────────────────────────────────────────────────

    def ref_on(self, ref: str = "REFA"):
        """Enable reference waveform display: REFA, REFB, REFC, REFD."""
        self.write(f"{ref.upper()}:TRA ON")

    def ref_off(self, ref: str = "REFA"):
        self.write(f"{ref.upper()}:TRA OFF")

    def ref_save(self, ch: int, ref: str = "REFA"):
        """Store a channel waveform to reference."""
        self.write(f"REFSR {self._ch(ch)},{ref.upper()}")

    def set_ref_vdiv(self, ref: str, volts_per_div: float):
        self.write(f"{ref.upper()}:VDIV {volts_per_div:.4E}V")

    def set_ref_offset(self, ref: str, volts: float):
        self.write(f"{ref.upper()}:OFST {volts:.4E}V")

    # ─────────────────────────────────────────────────────────────────────
    #  PASS/FAIL TESTING
    # ─────────────────────────────────────────────────────────────────────

    def passfail_on(self):
        self.write("PFST ON")

    def passfail_off(self):
        self.write("PFST OFF")

    def passfail_source(self, ch: int):
        self.write(f"PFST:SRC {self._ch(ch)}")

    def passfail_create_mask(self, x_tolerance: float = 0.4,
                             y_tolerance: float = 0.4):
        """Create a pass/fail mask from the current signal."""
        self.write(f"PFST:XTOL {x_tolerance}")
        self.write(f"PFST:YTOL {y_tolerance}")
        self.write("PFST:CRMS")

    def passfail_set_action(self, stop_on_fail: bool = False,
                            buzzer_on_fail: bool = True):
        actions = []
        if stop_on_fail:
            actions.append("STOP")
        if buzzer_on_fail:
            actions.append("BUZZ")
        self.write(f"PFST:ACT {','.join(actions) if actions else 'NONE'}")

    def passfail_result(self) -> str:
        return self.query("PFST:RES?")

    # ─────────────────────────────────────────────────────────────────────
    #  SERIAL DECODE (UART / SPI / I2C / CAN / LIN)
    # ─────────────────────────────────────────────────────────────────────

    def decode_on(self, bus: int = 1):
        """Enable decode for bus 1 or 2."""
        self.write(f"D{bus}:TRA ON")

    def decode_off(self, bus: int = 1):
        self.write(f"D{bus}:TRA OFF")

    # ── UART ──
    def setup_uart_decode(self, bus: int = 1, rx_ch: int = 1,
                          baud: int = 9600, data_bits: int = 8,
                          parity: str = "NONE", stop_bits: float = 1,
                          polarity: str = "NORMAL"):
        """Configure UART decode."""
        self.write(f"D{bus}:TYPE UART")
        self.write(f"D{bus}:UART:RX {self._ch(rx_ch)}")
        self.write(f"D{bus}:UART:BAUD {baud}")
        self.write(f"D{bus}:UART:DLEN {data_bits}")
        self.write(f"D{bus}:UART:PAR {parity.upper()}")
        self.write(f"D{bus}:UART:STOP {stop_bits}")
        self.write(f"D{bus}:UART:POL {polarity.upper()}")
        self.decode_on(bus)

    def setup_uart_trigger(self, bus: int = 1, condition: str = "START",
                           data: int = 0):
        """Trigger on UART data. condition: START, DATA, ERROR, PARITY."""
        self.write(f"TRSE SERIAL,SR,D{bus}")
        self.write(f"D{bus}:UART:TRCOND {condition.upper()}")
        if condition.upper() == "DATA":
            self.write(f"D{bus}:UART:TRVAL {data}")

    # ── SPI ──
    def setup_spi_decode(self, bus: int = 1, clk_ch: int = 1,
                         mosi_ch: int = 2, miso_ch: int = 3,
                         cs_ch: int = 4, bit_order: str = "MSB",
                         word_size: int = 8, cpol: int = 0, cpha: int = 0):
        self.write(f"D{bus}:TYPE SPI")
        self.write(f"D{bus}:SPI:CLK {self._ch(clk_ch)}")
        self.write(f"D{bus}:SPI:MOSI {self._ch(mosi_ch)}")
        self.write(f"D{bus}:SPI:MISO {self._ch(miso_ch)}")
        self.write(f"D{bus}:SPI:CS {self._ch(cs_ch)}")
        self.write(f"D{bus}:SPI:BORD {bit_order.upper()}")
        self.write(f"D{bus}:SPI:DLEN {word_size}")
        self.write(f"D{bus}:SPI:CPOL {cpol}")
        self.write(f"D{bus}:SPI:CPHA {cpha}")
        self.decode_on(bus)

    # ── I2C ──
    def setup_i2c_decode(self, bus: int = 1, sda_ch: int = 1,
                         scl_ch: int = 2):
        self.write(f"D{bus}:TYPE I2C")
        self.write(f"D{bus}:I2C:SDA {self._ch(sda_ch)}")
        self.write(f"D{bus}:I2C:SCL {self._ch(scl_ch)}")
        self.decode_on(bus)

    def setup_i2c_trigger(self, bus: int = 1, condition: str = "START",
                          address: int = 0, data: int = 0,
                          direction: str = "WRITE"):
        """Trigger on I2C events."""
        self.write(f"TRSE SERIAL,SR,D{bus}")
        self.write(f"D{bus}:I2C:TRCOND {condition.upper()}")
        if condition.upper() in ("ADDRDATA", "ADDR"):
            self.write(f"D{bus}:I2C:ADDR {address}")
            self.write(f"D{bus}:I2C:DIR {direction.upper()}")
        if condition.upper() in ("ADDRDATA", "DATA"):
            self.write(f"D{bus}:I2C:DATA {data}")

    # ── CAN ──
    def setup_can_decode(self, bus: int = 1, src_ch: int = 1,
                         baud: int = 500000):
        self.write(f"D{bus}:TYPE CAN")
        self.write(f"D{bus}:CAN:SRC {self._ch(src_ch)}")
        self.write(f"D{bus}:CAN:BAUD {baud}")
        self.decode_on(bus)

    # ── LIN ──
    def setup_lin_decode(self, bus: int = 1, src_ch: int = 1,
                         baud: int = 19200, version: str = "2.0"):
        self.write(f"D{bus}:TYPE LIN")
        self.write(f"D{bus}:LIN:SRC {self._ch(src_ch)}")
        self.write(f"D{bus}:LIN:BAUD {baud}")
        self.write(f"D{bus}:LIN:VER {version}")
        self.decode_on(bus)

    # ─────────────────────────────────────────────────────────────────────
    #  DIGITAL CHANNELS (MSO)
    # ─────────────────────────────────────────────────────────────────────

    def digital_on(self, ch: int):
        """Enable digital channel D0-D15."""
        assert 0 <= ch <= 15, "Digital channel must be 0-15"
        self.write(f"D{ch}:TRA ON")

    def digital_off(self, ch: int):
        self.write(f"D{ch}:TRA OFF")

    def digital_threshold(self, group: str, volts: float):
        """Set digital threshold. group: 'D0-D7' or 'D8-D15'."""
        self.write(f"DGTH {group},{volts:.4E}V")

    def digital_bus_on(self, bus: int = 1):
        """Enable digital bus display (1 or 2)."""
        self.write(f"BUS{bus}:TRA ON")

    def digital_bus_off(self, bus: int = 1):
        self.write(f"BUS{bus}:TRA OFF")

    # ─────────────────────────────────────────────────────────────────────
    #  POWER ANALYSIS (if licensed)
    # ─────────────────────────────────────────────────────────────────────

    def power_analysis_on(self):
        self.write("POAN ON")

    def power_analysis_off(self):
        self.write("POAN OFF")

    def set_power_type(self, analysis: str = "QUALITY"):
        """QUALITY, SWITCH, HARMONICS, RIPPLE, MODULATION, EFFICIENCY, etc."""
        self.write(f"POAT {analysis.upper()}")

    def set_power_source(self, voltage_ch: int = 1, current_ch: int = 2):
        self.write(f"POAV {self._ch(voltage_ch)}")
        self.write(f"POAI {self._ch(current_ch)}")

    # ─────────────────────────────────────────────────────────────────────
    #  CONVENIENCE / HIGH-LEVEL METHODS
    # ─────────────────────────────────────────────────────────────────────

    def configure_channel(self, ch: int, vdiv: float, coupling: str = "D1M",
                          probe: float = 1, offset: float = 0,
                          bw: str = "FULL", enable: bool = True):
        """One-call full channel configuration."""
        if enable:
            self.channel_on(ch)
        else:
            self.channel_off(ch)
            return
        self.set_coupling(ch, coupling)
        self.set_probe(ch, probe)
        self.set_vdiv(ch, vdiv)
        self.set_offset(ch, offset)
        self.set_bw_limit(ch, bw)

    def quick_setup(self, ch: int = 1, vdiv: float = 1.0,
                    tdiv: float = 1e-3, trig_level: float = 0.0):
        """Minimal quick setup: one channel, timebase, trigger."""
        self.reset()
        time.sleep(1)
        self.configure_channel(ch, vdiv)
        self.set_tdiv(tdiv)
        self.setup_edge_trigger(ch, trig_level)

    def plot_waveform(self, ch: int, title: str = ""):
        """Download and plot waveform with matplotlib."""
        import matplotlib.pyplot as plt
        t, v = self.get_waveform(ch)
        plt.figure(figsize=(12, 5))
        plt.plot(t * 1e6, v, linewidth=0.5)
        plt.xlabel("Time (µs)")
        plt.ylabel("Voltage (V)")
        plt.title(title or f"Channel {ch} Waveform")
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.show()

    def plot_fft(self, ch: int):
        """Compute and plot FFT from downloaded waveform."""
        import matplotlib.pyplot as plt
        t, v = self.get_waveform(ch)
        dt = t[1] - t[0]
        n = len(v)
        freq = np.fft.rfftfreq(n, d=dt)
        fft_mag = 20 * np.log10(np.abs(np.fft.rfft(v)) / n + 1e-12)
        plt.figure(figsize=(12, 5))
        plt.plot(freq / 1e6, fft_mag, linewidth=0.5)
        plt.xlabel("Frequency (MHz)")
        plt.ylabel("Magnitude (dBV)")
        plt.title(f"FFT - Channel {ch}")
        plt.grid(True, alpha=0.3)
        plt.xlim(0, freq[-1] / 1e6)
        plt.tight_layout()
        plt.show()

    def capture_multi_channel(self, channels: List[int]) -> dict:
        """Download waveforms from multiple channels. Returns dict of arrays."""
        result = {}
        for ch in channels:
            t, v = self.get_waveform(ch)
            result[ch] = {"time": t, "voltage": v}
        return result

    def plot_multi_channel(self, channels: List[int]):
        """Download and plot multiple channels overlaid."""
        import matplotlib.pyplot as plt
        plt.figure(figsize=(14, 6))
        for ch in channels:
            t, v = self.get_waveform(ch)
            plt.plot(t * 1e6, v, linewidth=0.5, label=f"CH{ch}")
        plt.xlabel("Time (µs)")
        plt.ylabel("Voltage (V)")
        plt.title("Multi-Channel Waveform")
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.show()

    def wait_for_trigger(self, timeout: float = 10.0) -> bool:
        """Wait until the scope triggers or timeout."""
        start = time.time()
        while time.time() - start < timeout:
            if self._is_rigol():
                status = self.query(":TRIGger:STATus?").strip().upper()
                if status in ("TD", "STOP", "T'D", "TRIG"):
                    return True
            else:
                status = self.query("INR?")
                if "1" in status:
                    return True
            time.sleep(0.1)
        return False

    def measure_report(self, ch: int) -> dict:
        """Get a full measurement report for a channel."""
        params = ["FREQ", "PER", "PKPK", "AMPL", "MAX", "MIN", "MEAN",
                  "RMS", "RISE", "FALL", "PWID", "NWID", "DUTY", "NDUTY"]
        report = {}
        for p in params:
            try:
                report[p] = self.measure_value(ch, p)
            except Exception:
                report[p] = float("nan")
        return report

    def print_report(self, ch: int):
        """Print a formatted measurement report."""
        report = self.measure_report(ch)
        print(f"\n{'='*50}")
        print(f"  Measurement Report - Channel {ch}")
        print(f"{'='*50}")
        for k, v in report.items():
            print(f"  {k:>10s}: {v:>14.6g}")
        print(f"{'='*50}\n")

    def send_raw(self, cmd: str) -> str:
        """Send any arbitrary SCPI command and return response."""
        if "?" in cmd:
            return self.query(cmd)
        else:
            self.write(cmd)
            return "OK"

    # ─────────────────────────────────────────────────────────────────────
    #  LIMIT / ALARM MONITORING
    # ─────────────────────────────────────────────────────────────────────

    def limit_monitor(self, ch: int, param: str, low: float, high: float,
                      interval: float = 1.0, duration: float = 60.0,
                      on_alarm: Optional[Callable[[dict], None]] = None,
                      log_file: Optional[str] = None) -> List[dict]:
        """Watch a measurement and trigger alarms when out of bounds.

        Args:
            ch:        Channel (1-4).
            param:     Measurement type (FREQ, RMS, PKPK, MEAN, etc.).
            low:       Lower limit — alarm if value < low.
            high:      Upper limit — alarm if value > high.
            interval:  Seconds between samples.
            duration:  Total monitoring time in seconds (0 = infinite).
            on_alarm:  Optional callback fn(record) called on each violation.
            log_file:  Optional CSV path to log every sample.

        Returns:
            List of all alarm records.
        """
        alarms: List[dict] = []
        all_records: List[dict] = []
        csv_f = None
        csv_w = None

        if log_file:
            csv_f = open(log_file, "w", newline="")
            csv_w = csv.writer(csv_f)
            csv_w.writerow(["timestamp", "channel", "param", "value",
                            "low_limit", "high_limit", "status"])

        start = time.time()
        sample_idx = 0
        print(f"[MONITOR] CH{ch} {param}  limits=[{low}, {high}]  "
              f"interval={interval}s  duration={duration}s")
        print(f"{'─' * 70}")

        try:
            while True:
                elapsed = time.time() - start
                if duration > 0 and elapsed >= duration:
                    break

                value = self.measure_value(ch, param)
                ts = datetime.datetime.now().isoformat(timespec="milliseconds")
                in_range = low <= value <= high

                record = {
                    "index": sample_idx,
                    "timestamp": ts,
                    "channel": ch,
                    "param": param,
                    "value": value,
                    "low_limit": low,
                    "high_limit": high,
                    "in_range": in_range,
                    "elapsed_s": round(elapsed, 3),
                }
                all_records.append(record)

                status = "OK"
                if not in_range:
                    if value < low:
                        status = f"UNDER (delta={value - low:+.6g})"
                    else:
                        status = f"OVER  (delta={value - high:+.6g})"
                    record["status"] = status
                    alarms.append(record)
                    print(f"  ** ALARM ** [{ts}]  {param}={value:.6g}  {status}")

                    if on_alarm:
                        on_alarm(record)
                else:
                    record["status"] = "OK"
                    print(f"  [{ts}]  {param}={value:.6g}  OK")

                if csv_w:
                    csv_w.writerow([ts, ch, param, f"{value:.6g}",
                                    low, high, status])
                    csv_f.flush()

                sample_idx += 1
                time.sleep(interval)

        except KeyboardInterrupt:
            print("\n[MONITOR] Stopped by user.")
        finally:
            if csv_f:
                csv_f.close()

        total = len(all_records)
        violations = len(alarms)
        print(f"{'─' * 70}")
        print(f"[MONITOR] Done. {total} samples, {violations} alarms "
              f"({violations/max(total,1)*100:.1f}% violation rate)")
        if log_file:
            print(f"[MONITOR] Log saved: {log_file}")
        return alarms

    def limit_monitor_background(self, ch: int, param: str,
                                 low: float, high: float,
                                 interval: float = 1.0,
                                 duration: float = 60.0,
                                 on_alarm: Optional[Callable] = None,
                                 log_file: Optional[str] = None
                                 ) -> threading.Thread:
        """Run limit_monitor in a background thread. Returns the thread."""
        t = threading.Thread(
            target=self.limit_monitor,
            args=(ch, param, low, high, interval, duration, on_alarm, log_file),
            daemon=True
        )
        t.start()
        return t

    def limit_monitor_multi(self, monitors: List[dict],
                            interval: float = 1.0,
                            duration: float = 60.0,
                            log_file: Optional[str] = None) -> List[dict]:
        """Monitor multiple parameters simultaneously.

        Args:
            monitors: List of dicts, each with keys:
                      {ch, param, low, high}
                      e.g. [{"ch":1,"param":"FREQ","low":990,"high":1010},
                            {"ch":1,"param":"PKPK","low":3.0,"high":3.6}]
            interval: Seconds between sample sweeps.
            duration: Total monitoring time.
            log_file: CSV log path.

        Returns:
            List of all alarm records.
        """
        alarms = []
        csv_f = None
        csv_w = None

        if log_file:
            csv_f = open(log_file, "w", newline="")
            csv_w = csv.writer(csv_f)
            csv_w.writerow(["timestamp", "channel", "param", "value",
                            "low_limit", "high_limit", "status"])

        start = time.time()
        print(f"[MULTI-MONITOR] Watching {len(monitors)} parameters  "
              f"interval={interval}s")
        for m in monitors:
            print(f"  CH{m['ch']} {m['param']:>6s}  [{m['low']}, {m['high']}]")
        print(f"{'─' * 70}")

        try:
            while True:
                elapsed = time.time() - start
                if duration > 0 and elapsed >= duration:
                    break
                ts = datetime.datetime.now().isoformat(timespec="milliseconds")

                for m in monitors:
                    value = self.measure_value(m["ch"], m["param"])
                    in_range = m["low"] <= value <= m["high"]
                    status = "OK"
                    if not in_range:
                        delta = (value - m["low"]) if value < m["low"] \
                                else (value - m["high"])
                        status = f"{'UNDER' if value < m['low'] else 'OVER'}" \
                                 f" ({delta:+.6g})"
                        record = {"timestamp": ts, "channel": m["ch"],
                                  "param": m["param"], "value": value,
                                  "low": m["low"], "high": m["high"],
                                  "status": status}
                        alarms.append(record)
                        print(f"  ** ALARM ** [{ts}] CH{m['ch']} "
                              f"{m['param']}={value:.6g}  {status}")
                    if csv_w:
                        csv_w.writerow([ts, m["ch"], m["param"],
                                        f"{value:.6g}", m["low"],
                                        m["high"], status])
                if csv_f:
                    csv_f.flush()
                time.sleep(interval)

        except KeyboardInterrupt:
            print("\n[MULTI-MONITOR] Stopped by user.")
        finally:
            if csv_f:
                csv_f.close()

        print(f"{'─' * 70}")
        print(f"[MULTI-MONITOR] Done. {len(alarms)} total alarms.")
        return alarms

    # ─────────────────────────────────────────────────────────────────────
    #  AUTOMATED CHARACTERIZATION (PARAMETER SWEEP)
    # ─────────────────────────────────────────────────────────────────────

    def sweep_vdiv(self, ch: int, vdiv_list: List[float],
                   params: List[str] = None,
                   settle_time: float = 1.0) -> List[dict]:
        """Sweep vertical scale and record measurements at each step.

        Args:
            ch:          Channel to sweep.
            vdiv_list:   List of V/div values to test.
            params:      Measurements to record (default: PKPK, RMS, MEAN).
            settle_time: Wait time after each change.

        Returns:
            List of result dicts.
        """
        if params is None:
            params = ["PKPK", "RMS", "MEAN"]
        results = []
        print(f"[SWEEP V/div] CH{ch}  {len(vdiv_list)} steps  "
              f"params={params}")

        for vdiv in vdiv_list:
            self.set_vdiv(ch, vdiv)
            time.sleep(settle_time)
            row = {"vdiv": vdiv}
            for p in params:
                row[p] = self.measure_value(ch, p)
            results.append(row)
            vals = ", ".join(f"{p}={row[p]:.6g}" for p in params)
            print(f"  V/div={vdiv:<10.4g}  {vals}")

        return results

    def sweep_tdiv(self, ch: int, tdiv_list: List[float],
                   params: List[str] = None,
                   settle_time: float = 1.0) -> List[dict]:
        """Sweep timebase and record measurements at each step."""
        if params is None:
            params = ["FREQ", "PKPK", "RMS"]
        results = []
        print(f"[SWEEP T/div] CH{ch}  {len(tdiv_list)} steps  "
              f"params={params}")

        for tdiv in tdiv_list:
            self.set_tdiv(tdiv)
            time.sleep(settle_time)
            row = {"tdiv": tdiv}
            for p in params:
                row[p] = self.measure_value(ch, p)
            results.append(row)
            vals = ", ".join(f"{p}={row[p]:.6g}" for p in params)
            print(f"  T/div={tdiv:<12.4E}  {vals}")

        return results

    def sweep_trigger_level(self, ch: int, levels: List[float],
                            params: List[str] = None,
                            settle_time: float = 1.0) -> List[dict]:
        """Sweep trigger level and record measurements."""
        if params is None:
            params = ["FREQ", "PKPK", "DUTY"]
        results = []

        for level in levels:
            self.set_trig_level(ch, level)
            time.sleep(settle_time)
            row = {"trig_level": level}
            for p in params:
                row[p] = self.measure_value(ch, p)
            results.append(row)

        return results

    def sweep_custom(self, set_func: Callable[[Any], None],
                     values: list, ch: int,
                     params: List[str] = None,
                     settle_time: float = 1.0,
                     label: str = "value") -> List[dict]:
        """Generic parameter sweep.

        Args:
            set_func:    Function to call with each value, e.g. scope.set_tdiv
            values:      List of values to sweep through.
            ch:          Channel to measure.
            params:      Measurement parameters.
            settle_time: Wait between steps.
            label:       Name for the swept parameter in output.

        Returns:
            List of result dicts.
        """
        if params is None:
            params = ["FREQ", "PKPK", "RMS", "MEAN"]
        results = []
        print(f"[SWEEP {label}] {len(values)} steps  params={params}")

        for val in values:
            set_func(val)
            time.sleep(settle_time)
            row = {label: val}
            for p in params:
                row[p] = self.measure_value(ch, p)
            results.append(row)
            vals = ", ".join(f"{p}={row[p]:.6g}" for p in params)
            print(f"  {label}={val:<14.6g}  {vals}")

        return results

    def characterize_channel(self, ch: int,
                             vdiv_list: Optional[List[float]] = None,
                             tdiv_list: Optional[List[float]] = None,
                             settle_time: float = 1.5,
                             output_file: Optional[str] = None) -> dict:
        """Full channel characterization across V/div and T/div ranges.

        Returns dict with 'vdiv_sweep', 'tdiv_sweep', and 'summary'.
        """
        if vdiv_list is None:
            vdiv_list = [0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10]
        if tdiv_list is None:
            tdiv_list = [5e-9, 10e-9, 50e-9, 100e-9, 500e-9,
                         1e-6, 5e-6, 10e-6, 50e-6, 100e-6, 500e-6,
                         1e-3, 5e-3, 10e-3, 50e-3, 100e-3]

        print(f"\n{'='*60}")
        print(f"  CHANNEL {ch} CHARACTERIZATION")
        print(f"{'='*60}\n")

        vdiv_data = self.sweep_vdiv(ch, vdiv_list, settle_time=settle_time)
        tdiv_data = self.sweep_tdiv(ch, tdiv_list, settle_time=settle_time)

        # Summary statistics
        all_freq = [r.get("FREQ", float("nan")) for r in tdiv_data
                    if not math.isnan(r.get("FREQ", float("nan")))]
        all_rms = [r.get("RMS", float("nan")) for r in vdiv_data
                   if not math.isnan(r.get("RMS", float("nan")))]

        summary = {
            "channel": ch,
            "freq_mean": np.mean(all_freq) if all_freq else float("nan"),
            "freq_std": np.std(all_freq) if all_freq else float("nan"),
            "rms_mean": np.mean(all_rms) if all_rms else float("nan"),
            "rms_std": np.std(all_rms) if all_rms else float("nan"),
            "vdiv_steps": len(vdiv_data),
            "tdiv_steps": len(tdiv_data),
        }

        result = {"vdiv_sweep": vdiv_data, "tdiv_sweep": tdiv_data,
                  "summary": summary}

        if output_file:
            with open(output_file, "w") as f:
                json.dump(result, f, indent=2, default=str)
            print(f"\n[CHARACTERIZE] Saved to {output_file}")

        print(f"\n{'='*60}")
        print(f"  Summary: Freq={summary['freq_mean']:.2f} "
              f"+/- {summary['freq_std']:.2f} Hz")
        print(f"           RMS={summary['rms_mean']:.4f} "
              f"+/- {summary['rms_std']:.4f} V")
        print(f"{'='*60}\n")

        return result

    def plot_sweep(self, results: List[dict], x_key: str, y_key: str,
                   title: str = "", x_log: bool = False, y_log: bool = False):
        """Plot a parameter sweep result."""
        import matplotlib.pyplot as plt
        x = [r[x_key] for r in results]
        y = [r[y_key] for r in results]
        plt.figure(figsize=(10, 5))
        plt.plot(x, y, "o-", markersize=5)
        plt.xlabel(x_key)
        plt.ylabel(y_key)
        plt.title(title or f"{y_key} vs {x_key}")
        if x_log:
            plt.xscale("log")
        if y_log:
            plt.yscale("log")
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.show()

    # ─────────────────────────────────────────────────────────────────────
    #  BODE PLOT (Frequency Response with Signal Generator)
    # ─────────────────────────────────────────────────────────────────────

    def bode_plot(self, input_ch: int, output_ch: int,
                  freq_start: float, freq_stop: float,
                  points_per_decade: int = 10,
                  siggen_set_freq: Optional[Callable[[float], None]] = None,
                  siggen_amplitude: float = 1.0,
                  settle_time: float = 0.5,
                  auto_scale: bool = True,
                  output_file: Optional[str] = None
                  ) -> Dict[str, list]:
        """Automated Bode plot (gain & phase vs frequency).

        Requires a signal generator to drive the DUT input. The signal
        generator is controlled via the siggen_set_freq callback.

        Args:
            input_ch:       Scope channel connected to DUT input.
            output_ch:      Scope channel connected to DUT output.
            freq_start:     Start frequency in Hz.
            freq_stop:      Stop frequency in Hz.
            points_per_decade: Number of frequency points per decade.
            siggen_set_freq: Callback function(freq_hz) to set generator
                            frequency.  If None, uses scope's built-in AWG
                            (if available) via SCPI.
            siggen_amplitude: Signal generator amplitude (informational).
            settle_time:    Wait time after frequency change (seconds).
            auto_scale:     Auto-adjust scope scales at each frequency.
            output_file:    Optional CSV file to save results.

        Returns:
            Dict with keys: freq_hz, gain_db, phase_deg, vin_rms, vout_rms
        """
        # Generate logarithmic frequency list
        decades = math.log10(freq_stop / freq_start)
        num_points = max(int(decades * points_per_decade), 2)
        frequencies = np.logspace(math.log10(freq_start),
                                  math.log10(freq_stop),
                                  num_points).tolist()

        results = {"freq_hz": [], "gain_db": [], "phase_deg": [],
                   "vin_rms": [], "vout_rms": [], "vin_pkpk": [],
                   "vout_pkpk": []}

        print(f"\n{'='*65}")
        print(f"  BODE PLOT  -  {freq_start:.1f} Hz  to  {freq_stop:.1f} Hz")
        print(f"  Input: CH{input_ch}   Output: CH{output_ch}   "
              f"Points: {num_points}")
        print(f"{'='*65}")
        print(f"  {'Freq (Hz)':>12s}  {'Gain (dB)':>10s}  {'Phase (°)':>10s}"
              f"  {'Vin RMS':>10s}  {'Vout RMS':>10s}")
        print(f"  {'─'*12}  {'─'*10}  {'─'*10}  {'─'*10}  {'─'*10}")

        for freq in frequencies:
            # Set signal generator frequency
            if siggen_set_freq:
                siggen_set_freq(freq)
            else:
                # Try built-in AWG (Siglent SCPI)
                self.write(f"BSWV FRQ,{freq:.4E}")

            # Adjust timebase for ~2-4 visible cycles
            periods_visible = 3
            tdiv = (periods_visible / freq) / 14.0  # 14 divisions
            # Clamp to valid range
            tdiv = max(5e-9, min(tdiv, 100.0))
            self.set_tdiv(tdiv)

            time.sleep(settle_time)

            if auto_scale:
                # Quick auto-range: read current, adjust if clipping
                for _ in range(2):
                    vin_pkpk = self.measure_value(input_ch, "PKPK")
                    vout_pkpk = self.measure_value(output_ch, "PKPK")
                    if not math.isnan(vin_pkpk) and vin_pkpk > 0:
                        self.set_vdiv(input_ch,
                                      max(vin_pkpk / 6.0, 0.001))
                    if not math.isnan(vout_pkpk) and vout_pkpk > 0:
                        self.set_vdiv(output_ch,
                                      max(vout_pkpk / 6.0, 0.001))
                    time.sleep(0.3)

            # Measure
            vin_rms = self.measure_value(input_ch, "RMS")
            vout_rms = self.measure_value(output_ch, "RMS")
            vin_pkpk = self.measure_value(input_ch, "PKPK")
            vout_pkpk = self.measure_value(output_ch, "PKPK")

            # Gain in dB
            if vin_rms > 0 and not math.isnan(vin_rms) and \
               not math.isnan(vout_rms):
                gain_db = 20 * math.log10(max(vout_rms, 1e-12) /
                                          max(vin_rms, 1e-12))
            else:
                gain_db = float("nan")

            # Phase measurement via waveform cross-correlation
            phase_deg = self._measure_phase(input_ch, output_ch, freq)

            results["freq_hz"].append(freq)
            results["gain_db"].append(gain_db)
            results["phase_deg"].append(phase_deg)
            results["vin_rms"].append(vin_rms)
            results["vout_rms"].append(vout_rms)
            results["vin_pkpk"].append(vin_pkpk)
            results["vout_pkpk"].append(vout_pkpk)

            print(f"  {freq:>12.2f}  {gain_db:>+10.2f}  {phase_deg:>+10.1f}"
                  f"  {vin_rms:>10.4f}  {vout_rms:>10.4f}")

        # Save to CSV
        if output_file:
            with open(output_file, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["freq_hz", "gain_db", "phase_deg",
                            "vin_rms", "vout_rms"])
                for i in range(len(results["freq_hz"])):
                    w.writerow([results["freq_hz"][i],
                                results["gain_db"][i],
                                results["phase_deg"][i],
                                results["vin_rms"][i],
                                results["vout_rms"][i]])
            print(f"\n  Results saved: {output_file}")

        print(f"{'='*65}")

        # Find -3 dB point
        self._find_bandwidth(results)

        return results

    def _measure_phase(self, ch_ref: int, ch_sig: int,
                       freq: float) -> float:
        """Measure phase difference between two channels using
        cross-correlation of downloaded waveforms."""
        try:
            t1, v1 = self.get_waveform(ch_ref)
            t2, v2 = self.get_waveform(ch_sig)

            # Ensure same length
            n = min(len(v1), len(v2))
            v1 = v1[:n]
            v2 = v2[:n]
            dt = t1[1] - t1[0]

            # Normalize
            v1 = v1 - np.mean(v1)
            v2 = v2 - np.mean(v2)

            # Cross-correlation
            corr = np.correlate(v1, v2, mode="full")
            lag_idx = np.argmax(corr) - (n - 1)
            time_delay = lag_idx * dt

            # Convert to phase
            phase = (time_delay * freq * 360.0) % 360
            if phase > 180:
                phase -= 360
            return phase

        except Exception:
            return float("nan")

    def _find_bandwidth(self, results: Dict[str, list]):
        """Find and print the -3 dB bandwidth from Bode data."""
        gains = results["gain_db"]
        freqs = results["freq_hz"]
        valid = [(f, g) for f, g in zip(freqs, gains)
                 if not math.isnan(g)]
        if not valid:
            return

        max_gain = max(g for _, g in valid)
        cutoff_level = max_gain - 3.0

        for i in range(len(valid) - 1):
            f1, g1 = valid[i]
            f2, g2 = valid[i + 1]
            if g1 >= cutoff_level and g2 < cutoff_level:
                # Linear interpolation
                if g1 != g2:
                    ratio = (cutoff_level - g1) / (g2 - g1)
                    f_3db = f1 + ratio * (f2 - f1)
                else:
                    f_3db = (f1 + f2) / 2
                print(f"\n  -3 dB Bandwidth: {f_3db:.2f} Hz  "
                      f"(peak gain = {max_gain:.2f} dB)")
                return

    def plot_bode(self, results: Dict[str, list], title: str = "Bode Plot"):
        """Plot gain and phase vs frequency (standard Bode plot)."""
        import matplotlib.pyplot as plt

        freq = results["freq_hz"]
        gain = results["gain_db"]
        phase = results["phase_deg"]

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

        # Gain plot
        ax1.semilogx(freq, gain, "b-o", markersize=4, linewidth=1.5)
        ax1.set_ylabel("Gain (dB)")
        ax1.set_title(title)
        ax1.grid(True, which="both", alpha=0.3)
        ax1.axhline(y=-3, color="r", linestyle="--", alpha=0.5,
                     label="-3 dB")
        ax1.legend()

        # Phase plot
        ax2.semilogx(freq, phase, "r-o", markersize=4, linewidth=1.5)
        ax2.set_ylabel("Phase (degrees)")
        ax2.set_xlabel("Frequency (Hz)")
        ax2.grid(True, which="both", alpha=0.3)
        ax2.axhline(y=-45, color="gray", linestyle="--", alpha=0.5)
        ax2.axhline(y=-90, color="gray", linestyle="--", alpha=0.5)
        ax2.axhline(y=-180, color="gray", linestyle="--", alpha=0.5)

        plt.tight_layout()
        plt.show()

    # ─────────────────────────────────────────────────────────────────────
    #  EYE DIAGRAM ANALYSIS
    # ─────────────────────────────────────────────────────────────────────

    def capture_eye_diagram(self, ch: int, bit_rate: float,
                            num_acquisitions: int = 50,
                            bits_displayed: int = 2
                            ) -> Dict[str, Any]:
        """Capture and analyze an eye diagram for a serial data signal.

        Args:
            ch:               Channel carrying the serial data.
            bit_rate:         Data rate in bits/second (e.g. 1e6 for 1 Mbps).
            num_acquisitions: Number of waveform captures to overlay.
            bits_displayed:   Number of UI (unit intervals) in the eye.

        Returns:
            Dict with eye diagram data and measurements.
        """
        bit_period = 1.0 / bit_rate
        ui = bit_period  # unit interval

        # Configure scope for the data rate
        tdiv = (bits_displayed * ui) / 14.0
        self.set_tdiv(tdiv)
        time.sleep(0.5)

        all_traces = []
        time_axis = None

        print(f"\n{'='*60}")
        print(f"  EYE DIAGRAM CAPTURE  -  CH{ch}")
        print(f"  Bit rate: {bit_rate:.0f} bps  |  UI: {ui*1e9:.2f} ns  |  "
              f"Acquisitions: {num_acquisitions}")
        print(f"{'='*60}")

        for i in range(num_acquisitions):
            self.single()
            self.force_trigger()
            time.sleep(0.1)
            try:
                t, v = self.get_waveform(ch)
                if time_axis is None:
                    time_axis = t

                # Fold the waveform at the UI boundary (overlay bits)
                dt = t[1] - t[0]
                samples_per_ui = int(ui / dt)
                if samples_per_ui < 10:
                    all_traces.append(v)
                    continue

                num_uis = len(v) // samples_per_ui
                for k in range(num_uis):
                    segment = v[k * samples_per_ui:(k + 1) * samples_per_ui]
                    all_traces.append(segment)

                print(f"  Acquisition {i+1}/{num_acquisitions}  "
                      f"({num_uis} UIs extracted)")
            except Exception as e:
                print(f"  Acquisition {i+1} failed: {e}")

        if not all_traces:
            print("  No valid traces captured.")
            return {}

        # Normalize all traces to same length
        min_len = min(len(tr) for tr in all_traces)
        traces_array = np.array([tr[:min_len] for tr in all_traces])

        # Eye diagram measurements
        eye_data = self._analyze_eye(traces_array, ui, bit_rate)

        self.run()  # restore continuous mode
        return eye_data

    def _analyze_eye(self, traces: np.ndarray, ui: float,
                     bit_rate: float) -> Dict[str, Any]:
        """Compute eye diagram metrics from overlaid traces.

        Args:
            traces: 2D array (num_traces x samples_per_ui).
            ui:     Unit interval in seconds.
            bit_rate: Data rate.
        """
        num_traces, num_samples = traces.shape

        # Voltage levels at the center of the eye (middle 20%)
        center_start = int(num_samples * 0.4)
        center_end = int(num_samples * 0.6)
        center_data = traces[:, center_start:center_end].flatten()

        # Separate high and low levels using histogram thresholding
        v_mean = np.mean(center_data)
        high_samples = center_data[center_data > v_mean]
        low_samples = center_data[center_data <= v_mean]

        v_one = np.mean(high_samples) if len(high_samples) > 0 else v_mean
        v_zero = np.mean(low_samples) if len(low_samples) > 0 else v_mean

        sigma_one = np.std(high_samples) if len(high_samples) > 0 else 0
        sigma_zero = np.std(low_samples) if len(low_samples) > 0 else 0

        # Eye height = distance between mean levels minus noise
        eye_height = (v_one - 3 * sigma_one) - (v_zero + 3 * sigma_zero)
        eye_amplitude = v_one - v_zero

        # Eye width: find crossing points
        crossing_region = traces[:, :num_samples // 4]  # first quarter
        crossing_times = []
        threshold = (v_one + v_zero) / 2
        dt = ui / num_samples

        for trace in traces:
            for j in range(len(trace) - 1):
                if (trace[j] < threshold <= trace[j + 1]) or \
                   (trace[j] >= threshold > trace[j + 1]):
                    # Linear interpolation for exact crossing
                    if trace[j + 1] != trace[j]:
                        frac = (threshold - trace[j]) / \
                               (trace[j + 1] - trace[j])
                        crossing_times.append((j + frac) * dt)

        # Eye width from crossing time jitter
        if len(crossing_times) > 1:
            crossing_jitter = np.std(crossing_times)
            eye_width = ui - 6 * crossing_jitter  # 3-sigma on each side
        else:
            crossing_jitter = 0
            eye_width = ui

        # Signal-to-noise ratio
        total_noise = sigma_one + sigma_zero
        snr = eye_amplitude / total_noise if total_noise > 0 else float("inf")

        # Extinction ratio (for optical-style metrics)
        extinction_ratio = v_one / v_zero if v_zero != 0 else float("inf")

        # Q-factor
        q_factor = eye_amplitude / (sigma_one + sigma_zero) \
                   if (sigma_one + sigma_zero) > 0 else float("inf")

        # Estimated BER from Q-factor
        try:
            from scipy.special import erfc
            ber = 0.5 * erfc(q_factor / math.sqrt(2))
        except ImportError:
            ber = float("nan")

        results = {
            "traces": traces,
            "num_traces": num_traces,
            "bit_rate": bit_rate,
            "unit_interval_s": ui,
            "v_one": v_one,
            "v_zero": v_zero,
            "sigma_one": sigma_one,
            "sigma_zero": sigma_zero,
            "eye_height_v": eye_height,
            "eye_amplitude_v": eye_amplitude,
            "eye_width_s": eye_width,
            "eye_width_ui": eye_width / ui,
            "crossing_jitter_s": crossing_jitter,
            "snr_linear": snr,
            "snr_db": 20 * math.log10(snr) if snr > 0 else float("-inf"),
            "extinction_ratio": extinction_ratio,
            "q_factor": q_factor,
            "estimated_ber": ber,
        }

        print(f"\n  Eye Diagram Analysis Results:")
        print(f"  {'─'*45}")
        print(f"  V_one (mean high) : {v_one:>12.4f} V")
        print(f"  V_zero (mean low) : {v_zero:>12.4f} V")
        print(f"  Sigma_one         : {sigma_one:>12.6f} V")
        print(f"  Sigma_zero        : {sigma_zero:>12.6f} V")
        print(f"  Eye Height        : {eye_height*1e3:>12.2f} mV")
        print(f"  Eye Amplitude     : {eye_amplitude*1e3:>12.2f} mV")
        print(f"  Eye Width         : {eye_width*1e9:>12.2f} ns "
              f"({eye_width/ui*100:.1f}% UI)")
        print(f"  Crossing Jitter   : {crossing_jitter*1e12:>12.2f} ps RMS")
        print(f"  SNR               : {results['snr_db']:>12.1f} dB")
        print(f"  Q-Factor          : {q_factor:>12.2f}")
        print(f"  Est. BER          : {ber:>12.2E}")
        print(f"  {'─'*45}")

        return results

    def plot_eye_diagram(self, eye_data: Dict[str, Any],
                         title: str = "Eye Diagram"):
        """Plot the eye diagram from captured data."""
        import matplotlib.pyplot as plt

        traces = eye_data["traces"]
        ui = eye_data["unit_interval_s"]
        num_samples = traces.shape[1]
        t = np.linspace(0, ui * 1e9, num_samples)  # time in ns

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6),
                                        gridspec_kw={"width_ratios": [3, 1]})

        # Eye diagram (waveform overlay)
        for trace in traces:
            ax1.plot(t, trace, color="blue", alpha=0.05, linewidth=0.5)

        ax1.axhline(y=eye_data["v_one"], color="green", linestyle="--",
                     alpha=0.7, label=f"V_one = {eye_data['v_one']:.3f}V")
        ax1.axhline(y=eye_data["v_zero"], color="red", linestyle="--",
                     alpha=0.7, label=f"V_zero = {eye_data['v_zero']:.3f}V")
        threshold = (eye_data["v_one"] + eye_data["v_zero"]) / 2
        ax1.axhline(y=threshold, color="orange", linestyle=":",
                     alpha=0.5, label=f"Threshold = {threshold:.3f}V")
        ax1.set_xlabel("Time (ns)")
        ax1.set_ylabel("Voltage (V)")
        ax1.set_title(title)
        ax1.legend(fontsize=8)
        ax1.grid(True, alpha=0.2)

        # Histogram at eye center
        center_start = int(num_samples * 0.4)
        center_end = int(num_samples * 0.6)
        center_data = traces[:, center_start:center_end].flatten()
        ax2.hist(center_data, bins=100, orientation="horizontal",
                 color="blue", alpha=0.6, density=True)
        ax2.axhline(y=eye_data["v_one"], color="green", linestyle="--")
        ax2.axhline(y=eye_data["v_zero"], color="red", linestyle="--")
        ax2.set_xlabel("Density")
        ax2.set_title("Eye Center Histogram")
        ax2.set_ylim(ax1.get_ylim())
        ax2.grid(True, alpha=0.2)

        plt.tight_layout()
        plt.show()

    # ─────────────────────────────────────────────────────────────────────
    #  JITTER ANALYSIS
    # ─────────────────────────────────────────────────────────────────────

    def analyze_jitter(self, ch: int, num_acquisitions: int = 100,
                       threshold: Optional[float] = None,
                       edge: str = "rising",
                       output_file: Optional[str] = None
                       ) -> Dict[str, Any]:
        """Comprehensive jitter analysis from waveform data.

        Measures period jitter, cycle-to-cycle jitter, TIE (time interval
        error), and provides statistical analysis with histograms.

        Args:
            ch:               Channel to analyze.
            num_acquisitions: Number of waveform captures for statistics.
            threshold:        Crossing threshold voltage (None = auto-detect).
            edge:             "rising" or "falling" edges to analyze.
            output_file:      Optional CSV to save raw crossing data.

        Returns:
            Dict with all jitter metrics and raw data.
        """
        all_periods = []
        all_crossings_per_acq = []

        print(f"\n{'='*60}")
        print(f"  JITTER ANALYSIS  -  CH{ch}")
        print(f"  Acquisitions: {num_acquisitions}  |  Edge: {edge}")
        print(f"{'='*60}")

        for acq in range(num_acquisitions):
            self.single()
            self.force_trigger()
            time.sleep(0.1)

            try:
                t, v = self.get_waveform(ch)
            except Exception:
                continue

            # Auto-detect threshold if not specified
            if threshold is None and acq == 0:
                threshold = (np.max(v) + np.min(v)) / 2
                print(f"  Auto threshold: {threshold:.4f} V")

            # Find zero crossings
            crossings = self._find_crossings(t, v, threshold, edge)
            if len(crossings) >= 2:
                periods = np.diff(crossings)
                all_periods.extend(periods.tolist())
                all_crossings_per_acq.append(crossings)

            if (acq + 1) % 10 == 0:
                print(f"  Acquisition {acq+1}/{num_acquisitions} "
                      f"({len(all_periods)} periods collected)")

        if not all_periods:
            print("  ERROR: No valid periods measured.")
            return {}

        periods = np.array(all_periods)

        # Period jitter (deviation from mean period)
        mean_period = np.mean(periods)
        period_jitter_rms = np.std(periods)
        period_jitter_pp = np.max(periods) - np.min(periods)

        # Cycle-to-cycle jitter (difference between consecutive periods)
        c2c = np.diff(periods)
        c2c_jitter_rms = np.std(c2c) if len(c2c) > 0 else 0
        c2c_jitter_pp = (np.max(c2c) - np.min(c2c)) if len(c2c) > 0 else 0

        # TIE (Time Interval Error) - deviation from ideal clock
        ideal_period = mean_period
        ideal_crossings = np.arange(len(periods) + 1) * ideal_period
        actual_crossings = np.concatenate(([0], np.cumsum(periods)))
        tie = actual_crossings - ideal_crossings
        tie_rms = np.std(tie)
        tie_pp = np.max(tie) - np.min(tie)

        # Frequency statistics
        frequencies = 1.0 / periods
        freq_mean = np.mean(frequencies)
        freq_std = np.std(frequencies)

        # Determine if jitter is Gaussian (for bounded uncorrelated jitter)
        from scipy.stats import kurtosis as scipy_kurtosis, skew as scipy_skew
        try:
            kurt = scipy_kurtosis(periods)
            skewness = scipy_skew(periods)
        except ImportError:
            kurt = float("nan")
            skewness = float("nan")

        results = {
            "periods": periods,
            "num_periods": len(periods),
            "mean_period_s": mean_period,
            "mean_frequency_hz": freq_mean,
            "freq_std_hz": freq_std,

            "period_jitter_rms_s": period_jitter_rms,
            "period_jitter_pp_s": period_jitter_pp,

            "c2c_jitter_rms_s": c2c_jitter_rms,
            "c2c_jitter_pp_s": c2c_jitter_pp,
            "c2c_data": c2c,

            "tie_rms_s": tie_rms,
            "tie_pp_s": tie_pp,
            "tie_data": tie,

            "kurtosis": kurt,
            "skewness": skewness,
        }

        # Print report
        print(f"\n  Jitter Analysis Results:")
        print(f"  {'─'*50}")
        print(f"  Periods analyzed  : {len(periods)}")
        print(f"  Mean frequency    : {freq_mean:>14.4f} Hz")
        print(f"  Mean period       : {mean_period*1e9:>14.4f} ns")
        print(f"  ")
        print(f"  Period Jitter RMS : {period_jitter_rms*1e12:>14.2f} ps")
        print(f"  Period Jitter P-P : {period_jitter_pp*1e12:>14.2f} ps")
        print(f"  ")
        print(f"  C2C Jitter RMS    : {c2c_jitter_rms*1e12:>14.2f} ps")
        print(f"  C2C Jitter P-P    : {c2c_jitter_pp*1e12:>14.2f} ps")
        print(f"  ")
        print(f"  TIE RMS           : {tie_rms*1e12:>14.2f} ps")
        print(f"  TIE P-P           : {tie_pp*1e12:>14.2f} ps")
        print(f"  ")
        print(f"  Freq Std Dev      : {freq_std:>14.4f} Hz "
              f"({freq_std/freq_mean*1e6:.2f} ppm)")
        print(f"  Kurtosis          : {kurt:>14.4f}  "
              f"({'Gaussian~3' if abs(kurt) < 1 else 'Non-Gaussian'})")
        print(f"  Skewness          : {skewness:>14.4f}")
        print(f"  {'─'*50}")

        # Save raw data
        if output_file:
            with open(output_file, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["period_index", "period_s", "frequency_hz",
                            "tie_s", "c2c_jitter_s"])
                for i in range(len(periods)):
                    c2c_val = c2c[i] if i < len(c2c) else ""
                    w.writerow([i, periods[i], frequencies[i],
                                tie[i], c2c_val])
            print(f"  Data saved: {output_file}")

        return results

    def _find_crossings(self, t: np.ndarray, v: np.ndarray,
                        threshold: float,
                        edge: str = "rising") -> np.ndarray:
        """Find precise threshold crossing times using interpolation."""
        crossings = []
        for i in range(len(v) - 1):
            if edge == "rising":
                if v[i] < threshold <= v[i + 1]:
                    frac = (threshold - v[i]) / (v[i + 1] - v[i])
                    crossings.append(t[i] + frac * (t[i + 1] - t[i]))
            elif edge == "falling":
                if v[i] >= threshold > v[i + 1]:
                    frac = (threshold - v[i]) / (v[i + 1] - v[i])
                    crossings.append(t[i] + frac * (t[i + 1] - t[i]))
            else:  # both
                if (v[i] < threshold <= v[i + 1]) or \
                   (v[i] >= threshold > v[i + 1]):
                    frac = (threshold - v[i]) / (v[i + 1] - v[i])
                    crossings.append(t[i] + frac * (t[i + 1] - t[i]))

        return np.array(crossings)

    def plot_jitter(self, jitter_data: Dict[str, Any],
                    title: str = "Jitter Analysis"):
        """Plot comprehensive jitter analysis results."""
        import matplotlib.pyplot as plt

        fig, axes = plt.subplots(2, 3, figsize=(18, 10))

        periods = jitter_data["periods"]
        c2c = jitter_data["c2c_data"]
        tie = jitter_data["tie_data"]

        # 1. Period trend
        ax = axes[0, 0]
        ax.plot(periods * 1e9, linewidth=0.5, color="blue")
        ax.axhline(y=np.mean(periods) * 1e9, color="red", linestyle="--",
                    linewidth=1)
        ax.set_xlabel("Period Index")
        ax.set_ylabel("Period (ns)")
        ax.set_title("Period Trend")
        ax.grid(True, alpha=0.3)

        # 2. Period histogram
        ax = axes[0, 1]
        ax.hist(periods * 1e12, bins=50, color="steelblue", edgecolor="white",
                density=True)
        ax.set_xlabel("Period (ps)")
        ax.set_ylabel("Density")
        ax.set_title(f"Period Histogram "
                     f"(RMS={jitter_data['period_jitter_rms_s']*1e12:.1f}ps)")
        ax.grid(True, alpha=0.3)

        # 3. Cycle-to-cycle jitter trend
        ax = axes[0, 2]
        if len(c2c) > 0:
            ax.plot(c2c * 1e12, linewidth=0.5, color="green")
            ax.axhline(y=0, color="red", linestyle="--")
        ax.set_xlabel("Index")
        ax.set_ylabel("C2C Jitter (ps)")
        ax.set_title(f"Cycle-to-Cycle "
                     f"(RMS={jitter_data['c2c_jitter_rms_s']*1e12:.1f}ps)")
        ax.grid(True, alpha=0.3)

        # 4. C2C histogram
        ax = axes[1, 0]
        if len(c2c) > 0:
            ax.hist(c2c * 1e12, bins=50, color="mediumseagreen",
                    edgecolor="white", density=True)
        ax.set_xlabel("C2C Jitter (ps)")
        ax.set_ylabel("Density")
        ax.set_title("C2C Jitter Histogram")
        ax.grid(True, alpha=0.3)

        # 5. TIE trend
        ax = axes[1, 1]
        ax.plot(tie * 1e12, linewidth=0.5, color="purple")
        ax.axhline(y=0, color="red", linestyle="--")
        ax.set_xlabel("Edge Index")
        ax.set_ylabel("TIE (ps)")
        ax.set_title(f"Time Interval Error "
                     f"(RMS={jitter_data['tie_rms_s']*1e12:.1f}ps)")
        ax.grid(True, alpha=0.3)

        # 6. TIE histogram
        ax = axes[1, 2]
        ax.hist(tie * 1e12, bins=50, color="mediumpurple",
                edgecolor="white", density=True)
        ax.set_xlabel("TIE (ps)")
        ax.set_ylabel("Density")
        ax.set_title("TIE Histogram")
        ax.grid(True, alpha=0.3)

        plt.suptitle(title, fontsize=14, fontweight="bold")
        plt.tight_layout()
        plt.show()

    # ─────────────────────────────────────────────────────────────────────
    #  POWER INTEGRITY ANALYSIS
    # ─────────────────────────────────────────────────────────────────────

    def analyze_power_integrity(self, ch: int,
                                nominal_voltage: float = 3.3,
                                num_acquisitions: int = 20,
                                output_file: Optional[str] = None
                                ) -> Dict[str, Any]:
        """Comprehensive power integrity analysis for a DC power rail.

        Measures: ripple, PARD, noise floor, transient response,
        regulation metrics, spectral content.

        Args:
            ch:               Channel connected to the power rail.
            nominal_voltage:  Expected DC voltage (e.g. 1.2, 3.3, 5.0).
            num_acquisitions: Number of captures for statistical analysis.
            output_file:      Optional JSON file for full results.

        Returns:
            Dict with all power integrity metrics.
        """
        print(f"\n{'='*60}")
        print(f"  POWER INTEGRITY ANALYSIS  -  CH{ch}")
        print(f"  Nominal voltage: {nominal_voltage} V")
        print(f"{'='*60}")

        # Configure for DC analysis: AC coupling shows just ripple
        self.set_coupling(ch, "D1M")
        time.sleep(0.3)

        # ── DC Measurements ──
        dc_values = []
        ripple_values = []
        rms_noise_values = []
        max_values = []
        min_values = []
        all_waveforms = []

        for i in range(num_acquisitions):
            self.single()
            self.force_trigger()
            time.sleep(0.15)

            dc = self.measure_value(ch, "MEAN")
            pkpk = self.measure_value(ch, "PKPK")
            rms = self.measure_value(ch, "RMS")
            v_max = self.measure_value(ch, "MAX")
            v_min = self.measure_value(ch, "MIN")

            dc_values.append(dc)
            ripple_values.append(pkpk)
            rms_noise_values.append(rms)
            max_values.append(v_max)
            min_values.append(v_min)

            # Download waveform for spectral analysis
            try:
                t, v = self.get_waveform(ch)
                all_waveforms.append((t, v))
            except Exception:
                pass

            if (i + 1) % 5 == 0:
                print(f"  Acquisition {i+1}/{num_acquisitions}")

        self.run()

        dc_values = np.array(dc_values)
        ripple_values = np.array(ripple_values)
        rms_noise_values = np.array(rms_noise_values)
        max_values = np.array(max_values)
        min_values = np.array(min_values)

        # Filter out NaN values
        dc_valid = dc_values[~np.isnan(dc_values)]
        ripple_valid = ripple_values[~np.isnan(ripple_values)]

        # ── Core Metrics ──
        dc_mean = np.mean(dc_valid) if len(dc_valid) > 0 else float("nan")
        dc_std = np.std(dc_valid) if len(dc_valid) > 0 else float("nan")

        # PARD (Periodic And Random Deviation)
        pard_pkpk = np.mean(ripple_valid) if len(ripple_valid) > 0 \
                    else float("nan")
        pard_rms = np.mean(rms_noise_values[~np.isnan(rms_noise_values)]) \
                   if len(rms_noise_values) > 0 else float("nan")

        # Absolute worst-case excursions
        abs_max = np.nanmax(max_values)
        abs_min = np.nanmin(min_values)
        total_excursion = abs_max - abs_min

        # Load regulation error
        regulation_error = ((dc_mean - nominal_voltage) /
                            nominal_voltage * 100)

        # Ripple as percentage of nominal
        ripple_pct = (pard_pkpk / nominal_voltage * 100) \
                     if nominal_voltage != 0 else float("nan")

        # ── Spectral Analysis (from first valid waveform) ──
        spectral_results = {}
        if all_waveforms:
            t, v = all_waveforms[0]
            ac_component = v - np.mean(v)
            dt = t[1] - t[0]
            n = len(ac_component)
            freq = np.fft.rfftfreq(n, d=dt)
            fft_mag = np.abs(np.fft.rfft(ac_component)) / n

            # Find dominant ripple frequency
            fft_mag_db = 20 * np.log10(fft_mag + 1e-12)
            # Skip DC bin
            peak_idx = np.argmax(fft_mag[1:]) + 1
            dominant_freq = freq[peak_idx]
            dominant_amplitude = fft_mag[peak_idx] * 2  # peak-to-peak

            # Noise floor (median of spectrum excluding DC and peak)
            mask = np.ones(len(fft_mag), dtype=bool)
            mask[0] = False
            mask[max(1, peak_idx - 2):peak_idx + 3] = False
            noise_floor = np.median(fft_mag_db[mask]) if np.any(mask) \
                          else float("nan")

            # Harmonic content (first 5 harmonics of dominant frequency)
            harmonics = []
            for h in range(1, 6):
                h_freq = dominant_freq * h
                h_idx = np.argmin(np.abs(freq - h_freq))
                if h_idx < len(fft_mag):
                    harmonics.append({
                        "harmonic": h,
                        "frequency_hz": freq[h_idx],
                        "amplitude_v": fft_mag[h_idx] * 2,
                        "amplitude_db": fft_mag_db[h_idx],
                    })

            spectral_results = {
                "dominant_freq_hz": dominant_freq,
                "dominant_amplitude_vpp": dominant_amplitude,
                "noise_floor_dbv": noise_floor,
                "harmonics": harmonics,
                "freq_axis": freq.tolist(),
                "spectrum_db": fft_mag_db.tolist(),
            }

        # ── Transient Analysis ──
        transient_results = {}
        if all_waveforms:
            t, v = all_waveforms[0]
            dc = np.mean(v)
            # Find largest deviation from DC
            deviations = np.abs(v - dc)
            max_dev_idx = np.argmax(deviations)
            max_dev = deviations[max_dev_idx]
            max_dev_time = t[max_dev_idx]

            # Overshoot / undershoot
            overshoot = np.max(v) - nominal_voltage
            undershoot = nominal_voltage - np.min(v)

            # Settling: time to stay within 1% of DC
            settle_band = nominal_voltage * 0.01
            settled = np.abs(v - dc) < settle_band
            if not np.all(settled):
                # Find last excursion outside band
                outside = np.where(~settled)[0]
                if len(outside) > 0:
                    settle_time_val = t[outside[-1]] - t[0]
                else:
                    settle_time_val = 0
            else:
                settle_time_val = 0

            transient_results = {
                "max_deviation_v": max_dev,
                "max_deviation_time_s": max_dev_time,
                "overshoot_v": overshoot,
                "overshoot_pct": overshoot / nominal_voltage * 100,
                "undershoot_v": undershoot,
                "undershoot_pct": undershoot / nominal_voltage * 100,
                "settling_time_s": settle_time_val,
            }

        # ── Compile Results ──
        results = {
            "channel": ch,
            "nominal_voltage": nominal_voltage,
            "num_acquisitions": num_acquisitions,

            "dc_mean_v": dc_mean,
            "dc_std_v": dc_std,
            "dc_accuracy_pct": 100 - abs(regulation_error),
            "regulation_error_pct": regulation_error,

            "pard_pkpk_mv": pard_pkpk * 1000,
            "pard_rms_mv": pard_rms * 1000,
            "ripple_pct": ripple_pct,

            "abs_max_v": abs_max,
            "abs_min_v": abs_min,
            "total_excursion_mv": total_excursion * 1000,

            "spectral": spectral_results,
            "transient": transient_results,
        }

        # ── Print Report ──
        print(f"\n  Power Integrity Report:")
        print(f"  {'─'*55}")
        print(f"  DC Mean Voltage   : {dc_mean:>10.4f} V  "
              f"(nominal: {nominal_voltage} V)")
        print(f"  DC Std Deviation  : {dc_std*1e3:>10.4f} mV")
        print(f"  Regulation Error  : {regulation_error:>+10.3f} %")
        print(f"  DC Accuracy       : {100 - abs(regulation_error):>10.3f} %")
        print(f"  ")
        print(f"  PARD (Pk-Pk)      : {pard_pkpk*1e3:>10.3f} mV")
        print(f"  PARD (RMS)        : {pard_rms*1e3:>10.3f} mV")
        print(f"  Ripple (% of Vnom): {ripple_pct:>10.3f} %")
        print(f"  ")
        print(f"  Absolute Max      : {abs_max:>10.4f} V")
        print(f"  Absolute Min      : {abs_min:>10.4f} V")
        print(f"  Total Excursion   : {total_excursion*1e3:>10.3f} mV")

        if spectral_results:
            print(f"  ")
            print(f"  Dominant Ripple   : {spectral_results['dominant_freq_hz']:>10.1f} Hz  "
                  f"({spectral_results['dominant_amplitude_vpp']*1e3:.2f} mVpp)")
            print(f"  Noise Floor       : {spectral_results['noise_floor_dbv']:>10.1f} dBV")
            if spectral_results.get("harmonics"):
                print(f"  Harmonics:")
                for h in spectral_results["harmonics"]:
                    print(f"    H{h['harmonic']}: "
                          f"{h['frequency_hz']:>10.1f} Hz  "
                          f"{h['amplitude_v']*1e3:>8.3f} mVpp  "
                          f"({h['amplitude_db']:.1f} dBV)")

        if transient_results:
            print(f"  ")
            print(f"  Overshoot         : {transient_results['overshoot_v']*1e3:>10.3f} mV  "
                  f"({transient_results['overshoot_pct']:.2f}%)")
            print(f"  Undershoot        : {transient_results['undershoot_v']*1e3:>10.3f} mV  "
                  f"({transient_results['undershoot_pct']:.2f}%)")
            print(f"  Settling Time     : {transient_results['settling_time_s']*1e6:>10.2f} µs")

        print(f"  {'─'*55}")

        if output_file:
            save_data = {k: v for k, v in results.items()
                         if k not in ("spectral",)}
            # Spectral data can be huge, save summary only
            if spectral_results:
                save_data["dominant_freq_hz"] = \
                    spectral_results.get("dominant_freq_hz")
                save_data["noise_floor_dbv"] = \
                    spectral_results.get("noise_floor_dbv")
                save_data["harmonics"] = spectral_results.get("harmonics", [])
            if transient_results:
                save_data["transient"] = transient_results
            with open(output_file, "w") as f:
                json.dump(save_data, f, indent=2, default=str)
            print(f"  Results saved: {output_file}")

        return results

    def plot_power_integrity(self, pi_data: Dict[str, Any],
                             waveform_ch: Optional[int] = None):
        """Plot power integrity analysis results.

        If waveform_ch is provided, captures a fresh waveform for plotting.
        Otherwise uses spectral data from pi_data.
        """
        import matplotlib.pyplot as plt

        fig, axes = plt.subplots(2, 2, figsize=(16, 10))
        nominal = pi_data["nominal_voltage"]

        # 1. DC level gauge
        ax = axes[0, 0]
        categories = ["Nominal", "Measured", "Max", "Min"]
        values = [nominal, pi_data["dc_mean_v"],
                  pi_data["abs_max_v"], pi_data["abs_min_v"]]
        colors = ["gray", "steelblue", "red", "blue"]
        bars = ax.barh(categories, values, color=colors, height=0.5)
        ax.set_xlabel("Voltage (V)")
        ax.set_title("DC Voltage Levels")
        ax.axvline(x=nominal, color="black", linestyle="--", alpha=0.5)
        for bar, val in zip(bars, values):
            ax.text(val, bar.get_y() + bar.get_height() / 2,
                    f" {val:.4f}V", va="center", fontsize=9)
        ax.grid(True, alpha=0.3, axis="x")

        # 2. Ripple/noise summary
        ax = axes[0, 1]
        metrics = ["PARD\n(Pk-Pk)", "PARD\n(RMS)", "Total\nExcursion"]
        vals_mv = [pi_data["pard_pkpk_mv"], pi_data["pard_rms_mv"],
                   pi_data["total_excursion_mv"]]
        bar_colors = ["#e74c3c", "#3498db", "#e67e22"]
        ax.bar(metrics, vals_mv, color=bar_colors, width=0.5)
        ax.set_ylabel("Millivolts (mV)")
        ax.set_title("Noise & Ripple Metrics")
        for i, v in enumerate(vals_mv):
            ax.text(i, v, f" {v:.2f}", ha="center", va="bottom", fontsize=10)
        ax.grid(True, alpha=0.3, axis="y")

        # 3. Spectrum (if available)
        ax = axes[1, 0]
        spectral = pi_data.get("spectral", {})
        if spectral and "freq_axis" in spectral and "spectrum_db" in spectral:
            freq = np.array(spectral["freq_axis"])
            spec_db = np.array(spectral["spectrum_db"])
            # Skip DC, plot in kHz
            mask = freq > 0
            ax.semilogx(freq[mask] / 1e3, spec_db[mask],
                        linewidth=0.5, color="purple")
            ax.set_xlabel("Frequency (kHz)")
            ax.set_ylabel("Amplitude (dBV)")
            ax.set_title("Ripple Spectrum")
            if spectral.get("dominant_freq_hz"):
                ax.axvline(x=spectral["dominant_freq_hz"] / 1e3,
                           color="red", linestyle="--", alpha=0.5,
                           label=f"Dominant: "
                                 f"{spectral['dominant_freq_hz']:.0f}Hz")
                ax.legend(fontsize=8)
        else:
            ax.text(0.5, 0.5, "No spectral data",
                    transform=ax.transAxes, ha="center")
        ax.grid(True, alpha=0.3)

        # 4. Regulation / quality gauge
        ax = axes[1, 1]
        quality_metrics = {
            "DC Accuracy (%)": pi_data["dc_accuracy_pct"],
            "Ripple (% Vnom)": pi_data["ripple_pct"],
            "Reg Error (%)": abs(pi_data["regulation_error_pct"]),
        }
        names = list(quality_metrics.keys())
        vals = list(quality_metrics.values())
        qcolors = ["#2ecc71" if v > 99 else "#f39c12" if v > 95
                    else "#e74c3c" for v in [vals[0]]]
        qcolors += ["#2ecc71" if v < 1 else "#f39c12" if v < 5
                     else "#e74c3c" for v in vals[1:]]
        ax.barh(names, vals, color=qcolors, height=0.4)
        ax.set_xlabel("Percentage")
        ax.set_title("Power Quality Metrics")
        for i, v in enumerate(vals):
            ax.text(v, i, f" {v:.3f}%", va="center", fontsize=10)
        ax.grid(True, alpha=0.3, axis="x")

        plt.suptitle(f"Power Integrity - CH{pi_data['channel']}  "
                     f"({nominal}V Rail)",
                     fontsize=14, fontweight="bold")
        plt.tight_layout()
        plt.show()

    def quick_power_check(self, ch: int, nominal_voltage: float,
                          tolerance_pct: float = 5.0,
                          max_ripple_mv: float = 50.0) -> bool:
        """Quick pass/fail power rail check.

        Returns True if the rail is within tolerance and ripple spec.
        """
        dc = self.measure_value(ch, "MEAN")
        ripple = self.measure_value(ch, "PKPK")
        error = abs(dc - nominal_voltage) / nominal_voltage * 100

        dc_ok = error <= tolerance_pct
        ripple_ok = (ripple * 1000) <= max_ripple_mv

        status = "PASS" if (dc_ok and ripple_ok) else "FAIL"
        print(f"[POWER CHECK] CH{ch}: DC={dc:.4f}V "
              f"(err={error:.2f}%)  "
              f"Ripple={ripple*1e3:.2f}mV  -> {status}")
        return dc_ok and ripple_ok


# ─────────────────────────────────────────────────────────────────────────────
#  INTERACTIVE MODE
# ─────────────────────────────────────────────────────────────────────────────

def interactive_mode(interface: str = "lan", resource: str = None,
                     ip: str = SiglentSDS1104XU.DEFAULT_IP,
                     port: int = SiglentSDS1104XU.DEFAULT_PORT,
                     lan_mode: str = "socket"):
    """Open an interactive SCPI terminal to the oscilloscope.

    Args:
        interface: "lan" (default) or "usb".
        resource:  Explicit VISA resource string (USB or LAN VISA).
        ip:        IP address (LAN only).
        port:      TCP port (LAN socket only).
        lan_mode:  "socket" or "visa" for LAN.
    """
    scope = SiglentSDS1104XU(interface=interface, resource=resource,
                             ip=ip, port=port, lan_mode=lan_mode)
    scope.connect()
    print("\nInteractive SCPI Terminal  (type 'exit' to quit)")
    print("-" * 50)
    while True:
        try:
            cmd = input("SCPI> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if cmd.lower() in ("exit", "quit", "q"):
            break
        if not cmd:
            continue
        try:
            result = scope.send_raw(cmd)
            if result and result != "OK":
                print(f"  -> {result}")
        except Exception as e:
            print(f"  ERROR: {e}")
    scope.disconnect()


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN - DEMO
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 67)
    print("  Siglent SDS1104X-U / Rigol MSO5000 Control Library")
    print("  Default: LAN (192.168.4.51:5025)  |  Also supports USB")
    print("=" * 67)
    print()
    print("LAN connection (default):")
    print("    from siglent_sds1104xu import SiglentSDS1104XU")
    print()
    print("    with SiglentSDS1104XU() as scope:")
    print("        scope.auto_setup()")
    print("        scope.print_report(1)")
    print("        scope.plot_waveform(1)")
    print("        scope.screenshot_png('capture.png')")
    print()
    print("LAN with different IP:")
    print("    scope = SiglentSDS1104XU(ip='192.168.4.100')")
    print()
    print("LAN via VISA (VXI-11/LXI):")
    print("    scope = SiglentSDS1104XU(interface='lan', lan_mode='visa',")
    print("        ip='192.168.4.51')")
    print()
    print("USB connection:")
    print("    scope = SiglentSDS1104XU(interface='usb')")
    print()
    print("USB with explicit resource:")
    print("    scope = SiglentSDS1104XU(interface='usb',")
    print("        resource='USB0::0xF4EC::0x1012::SDSAHBAD7R0940::INSTR')")
    print()
    print("Interactive SCPI terminal:")
    print("    interactive_mode()                    # LAN (default)")
    print("    interactive_mode(interface='usb')     # USB")
    print()
    # Uncomment below to start interactive mode:
    # interactive_mode()
