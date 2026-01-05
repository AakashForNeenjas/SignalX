import os
import time
import types

import can

from core.CANManager import CANManager


class DummyDBC:
    def __init__(self):
        self.database = types.SimpleNamespace(messages=[])


class DummyBus:
    """Minimal bus to satisfy CANManager for logging tests without hardware."""

    def __init__(self):
        self.sent = []

    def send(self, msg):
        self.sent.append(msg)

    def send_periodic(self, msg, cycle):
        # Not used in this test
        return None

    def shutdown(self):
        pass


def test_trc_csv_logging(tmp_path):
    """Verify TRC/CSV logging ordering, formatting, and monotonic timestamps."""
    # Arrange
    cm = CANManager(simulation_mode=True, dbc_parser=DummyDBC(), logger=None)
    cm.bus = DummyBus()
    base = cm.start_logging(str(tmp_path / "trace_test"))
    # Two synthetic messages
    m1 = can.Message(arbitration_id=0x123, data=bytes([1, 2, 3, 4]), is_extended_id=False, is_rx=False)
    m2 = can.Message(arbitration_id=0x7FF, data=bytes([0xAA] * 8), is_extended_id=False, is_rx=True)
    # Act
    cm._log_message(m1)
    time.sleep(0.01)
    cm._log_message(m2)
    cm.stop_logging()

    # Assert CSV contents
    csv_path = base + ".csv"
    trc_path = base + ".trc"
    assert os.path.exists(csv_path)
    assert os.path.exists(trc_path)

    with open(csv_path, "r") as f:
        lines = [ln.strip() for ln in f.readlines() if ln.strip()]
    # header + 2 lines
    assert len(lines) == 3
    hdr = lines[0].split(",")
    assert hdr == ["Time", "Type", "ID", "DLC", "Data"]
    t1, ttype1, id1, dlc1, data1 = lines[1].split(",")
    t2, ttype2, id2, dlc2, data2 = lines[2].split(",")
    assert float(t1) >= 0
    assert float(t2) > float(t1)
    assert ttype1 == "Tx"
    assert ttype2 == "Rx"
    assert id1 == "123"
    assert id2 == "7FF"
    assert dlc1 == "4" and data1 == "01 02 03 04"
    assert dlc2 == "8" and data2 == "AA AA AA AA AA AA AA AA"

    # Assert TRC contents (first line is header after ;---)
    with open(trc_path, "r") as f:
        trc_lines = [ln.rstrip("\n") for ln in f.readlines()]
    body = [ln for ln in trc_lines if not ln.startswith(";")]
    # Should have two body lines numbered 1) and 2)
    assert any("1)" in ln for ln in body)
    assert any("2)" in ln for ln in body)
    # Ensure ordering and IDs present
    assert "123" in body[0]
    assert "7FF" in body[1]


def test_cyclic_logging(tmp_path):
    """Ensure cyclic-start logging writes first tick and keeps counters ordered."""
    cm = CANManager(simulation_mode=True, dbc_parser=DummyDBC(), logger=None)
    cm.bus = DummyBus()
    base = cm.start_logging(str(tmp_path / "cyclic_trace"))
    # Simulate start_cyclic_message directly with a constructed message
    msg = can.Message(arbitration_id=0x321, data=bytes([0xDE, 0xAD, 0xBE, 0xEF]), is_extended_id=False, is_rx=False)
    cm._log_message(msg)
    time.sleep(0.01)
    cm._log_message(msg)
    cm.stop_logging()

    trc_path = base + ".trc"
    with open(trc_path, "r") as f:
        body = [ln for ln in f.readlines() if not ln.startswith(";")]
    # Expect two entries with increasing counters and times
    assert body[0].lstrip().startswith("1)")
    assert body[1].lstrip().startswith("2)")
    # Time should increase (second token after counter)
    def extract_time(line: str) -> float:
        # line format: "     1)     10.1  Tx   321 ..."
        parts = line.replace(")", ") ").split()
        # parts[0]="1)", parts[1]=time
        return float(parts[1])
    t0 = extract_time(body[0])
    t1 = extract_time(body[1])
    assert t1 > t0
