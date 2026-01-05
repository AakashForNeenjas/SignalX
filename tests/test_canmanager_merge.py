import os
import tempfile

import can
import pytest

from core.CANManager import CANManager


class DummySignal:
    def __init__(self, name, initial=None):
        self.name = name
        self.initial = initial


class DummyMessage:
    def __init__(self, name, signals):
        self.name = name
        self.signals = signals
        self.is_extended_frame = False
        self.frame_id = 0x123


def test_build_full_values_preserves_last_sent_and_overrides():
    mgr = CANManager(simulation_mode=True)
    msg_def = DummyMessage(
        "BATTERY_LIMITS",
        [DummySignal("Chrg_Curr_limit"), DummySignal("DisChrg_Curr_limit", initial=7.0)],
    )
    mgr.last_sent_signals["BATTERY_LIMITS"] = {"Chrg_Curr_limit": 5.0, "DisChrg_Curr_limit": 9.0}

    # Override only one signal and ensure the other stays untouched
    merged = mgr._build_full_values(msg_def, {"Chrg_Curr_limit": 14.0})

    assert merged["Chrg_Curr_limit"] == 14.0
    assert merged["DisChrg_Curr_limit"] == 9.0  # preserved from last sent, not zeroed


def test_build_full_values_uses_cache_when_no_last_sent():
    mgr = CANManager(simulation_mode=True)
    msg_def = DummyMessage("TEST_MSG", [DummySignal("A"), DummySignal("B", initial=1.0)])
    mgr.signal_cache["A"] = {"value": 11.0}

    merged = mgr._build_full_values(msg_def, {})

    assert merged["A"] == 11.0  # pulled from cache
    assert merged["B"] == 1.0   # falls back to initial


def test_trc_logging_skips_remote_and_logs_sane_offsets():
    mgr = CANManager(simulation_mode=True)
    with tempfile.TemporaryDirectory() as tmp:
        cwd = os.getcwd()
        os.chdir(tmp)
        try:
            base = mgr.start_logging("test_run")
            assert os.path.exists(base + ".trc")
            # Remote frame should be ignored
            remote = can.Message(arbitration_id=0x321, is_remote_frame=True, dlc=0, is_rx=True)
            mgr._log_message(remote)
            msg = can.Message(arbitration_id=0x123, data=bytes([1, 2, 3, 4]), is_rx=True)
            mgr._log_message(msg)
            mgr.stop_logging()
            with open(base + ".trc", "r") as f:
                lines = [l for l in f.readlines() if l and not l.startswith(";")]
            # Only one data line should be present (remote skipped)
            assert len(lines) == 1
            line = lines[0].strip()
            assert "123" in line
            # Offset should be non-negative
            offset = float(line.split(")")[1].split()[0])
            assert offset >= 0
        finally:
            os.chdir(cwd)
