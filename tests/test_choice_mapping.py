import sys
from pathlib import Path

# Ensure repo root is on path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from canmatrix.runner import TestExecutor
from canmatrix.models import TestCase


class _DummySignal:
    def __init__(self, name, choices=None):
        self.name = name
        self.choices = choices or {}


class _DummyMessage:
    def __init__(self, signals):
        self.signals = signals


class _DummyDb:
    def __init__(self, messages):
        self.messages = messages


class _DummyDbcMgr:
    def __init__(self, messages):
        self.db = _DummyDb(messages)


def _mk_executor(signals):
    """Helper to build a TestExecutor with a dummy DBC containing the provided signals."""
    msg = _DummyMessage(signals)
    dbc_mgr = _DummyDbcMgr([msg])
    case = TestCase(id="T1", name="dummy", description="", preconditions=[], main_steps=[], postconditions=[], assertions=[])
    return TestExecutor(case, None, dbc_mgr, logger=None, can_mgr=None, signal_manager=None, metrics=None)


def test_choice_mapping_from_dbc_choices():
    # DBC choices for a boolean-style signal
    sig = _DummySignal("Chrgr_Plugin", choices={0: "Charger Not Connected", 1: "Charger Connected"})
    ex = _mk_executor([sig])
    assert ex._coerce_choice("Charger Not Connected", "signal:Chrgr_Plugin") == 0
    assert ex._coerce_choice("Charger Connected", "signal:Chrgr_Plugin") == 1
    # Case-insensitive and punctuation-insensitive
    assert ex._coerce_choice("charger-not-connected", "signal:Chrgr_Plugin") == 0
    assert ex._coerce_choice("charger_connected", "signal:Chrgr_Plugin") == 1
    # _check_op should be able to evaluate range after coercion
    assert ex._check_op("Charger Not Connected", (0, 3), "in_range", target="signal:Chrgr_Plugin") is True


def test_choice_mapping_numeric_string_and_generic_fallback():
    sig = _DummySignal("Ignition_Sts", choices={0: "OFF", 1: "ON"})
    ex = _mk_executor([sig])
    # Numeric string should map through reverse map
    assert ex._coerce_choice("1", "signal:Ignition_Sts") == 1
    # Generic fallback still handles plain "on"/"off"
    assert ex._coerce_choice("off", "signal:Ignition_Sts") == 0
    assert ex._coerce_choice("on", "signal:Ignition_Sts") == 1


def test_choice_mapping_real_dbc_vcu_data():
    # Integration-style check against the real DBC to ensure choices are picked up
    import cantools
    from pathlib import Path

    db = cantools.database.load_file(Path("DBC/RE.dbc"))
    msg = db.get_message_by_name("VCU_Data")
    # Ensure choices exist on a signal we see as text in reports
    sig = next(s for s in msg.signals if s.name == "Chrgr_Plugin")
    assert sig.choices, "Chrgr_Plugin should have DBC choices"
    # Build executor from real DBC
    dummy_case = TestCase(id="T_real", name="real", description="", preconditions=[], main_steps=[], postconditions=[], assertions=[])
    ex = TestExecutor(dummy_case, None, type("DBCmgr", (), {"db": db}), logger=None, can_mgr=None, signal_manager=None, metrics=None)
    # Confirm reverse map resolves the choice label to numeric
    assert ex._coerce_choice("Charger Not Connected", "signal:Chrgr_Plugin") == 0
    # And that in_range comparison succeeds after coercion
    assert ex._check_op("Charger Not Connected", (0, 3), "in_range", target="signal:Chrgr_Plugin") is True


def test_read_signal_prefers_raw_value():
    dummy_case = TestCase(id="T_raw", name="raw", description="", preconditions=[], main_steps=[], postconditions=[], assertions=[])
    ex = TestExecutor(dummy_case, None, None, logger=None, can_mgr=None, signal_manager=None, metrics=None)
    # Inject a fake can_mgr cache entry with both value (string) and raw_value (numeric)
    ex.ctx.can_mgr = type("M", (), {"signal_cache": {"Foo": {"value": "ON", "raw_value": 1}}})()
    assert ex._read_signal("Foo") == 1
