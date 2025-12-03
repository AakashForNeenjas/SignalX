import os
import sys
import unittest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.Sequencer import Sequencer


class DummyGrid:
    def __init__(self):
        self.last = {}

    def set_grid_voltage(self, v):
        self.last["voltage"] = v

    def set_grid_current(self, c):
        self.last["current"] = c

    def set_grid_frequency(self, f):
        self.last["freq"] = f

    def get_grid_voltage(self):
        return self.last.get("voltage", 0.0)

    def get_grid_current(self):
        return self.last.get("current", 0.0)

    def get_grid_frequency(self):
        return self.last.get("freq", 0.0)

    def power_on(self):
        self.last["power"] = "on"

    def power_off(self):
        self.last["power"] = "off"

    def measure_power_real(self):
        return 1.0

    def measure_power_reactive(self):
        return 2.0

    def measure_power_apparent(self):
        return 3.0

    def measure_thd_current(self):
        return 4.0

    def measure_thd_voltage(self):
        return 5.0


class DummyPS:
    def __init__(self):
        self.voltage = 0.0
        self.current = 0.0
        self.power = "off"

    def connect(self):
        return True, "PS connected"

    def disconnect(self):
        self.power = "off"

    def power_on(self):
        self.power = "on"

    def power_off(self):
        self.power = "off"

    def measure_vi(self):
        return self.voltage, self.current

    def set_voltage(self, v):
        self.voltage = v

    def set_current(self, c):
        self.current = c

    def get_voltage(self):
        return self.voltage

    def get_current(self):
        return self.current


class DummyCAN:
    def __init__(self):
        self.connected = False
        self.logging = False

    def connect(self):
        self.connected = True
        return True, "CAN connected"

    def disconnect(self):
        self.connected = False

    def start_all_cyclic_messages(self):
        return ["msg1"], []

    def stop_all_cyclic_messages(self):
        return True

    def start_logging(self, filename_base):
        self.logging = True
        return f"Test Results/{filename_base}"

    def stop_logging(self):
        self.logging = False


class DummyInstMgr:
    def __init__(self):
        self.itech7900 = DummyGrid()
        self.itech6000 = DummyPS()
        self.itech6006 = self.itech6000
        self.siglent = None


class SequencerActionTests(unittest.TestCase):
    def setUp(self):
        self.inst_mgr = DummyInstMgr()
        self.can_mgr = DummyCAN()
        self.seq = Sequencer(self.inst_mgr, self.can_mgr)

    def test_can_connect_disconnect(self):
        ok, msg = self.seq._execute_action("CAN / Connect", "", 0)
        self.assertTrue(ok)
        self.assertIn("CAN", msg)
        ok, msg = self.seq._execute_action("CAN / Disconnect", "", 0)
        self.assertTrue(ok)

    def test_can_cyclic_and_trace(self):
        ok, msg = self.seq._execute_action("CAN / Start Cyclic CAN", "", 0)
        self.assertTrue(ok)
        ok, msg = self.seq._execute_action("CAN / Stop Cyclic CAN", "", 0)
        self.assertTrue(ok)
        ok, msg = self.seq._execute_action("CAN / Start Trace", "", 0)
        self.assertTrue(ok)
        ok, msg = self.seq._execute_action("CAN / Stop Trace", "", 0)
        self.assertTrue(ok)

    def test_gs_basic_setters(self):
        ok, msg = self.seq._execute_action("GS / Set Voltage AC", "230", 0)
        self.assertTrue(ok)
        ok, msg = self.seq._execute_action("GS / Set Current", "5", 0)
        self.assertTrue(ok)
        ok, msg = self.seq._execute_action("GS / Set Frequency", "50", 0)
        self.assertTrue(ok)
        ok, msg = self.seq._execute_action("GS / Power: ON", "", 0)
        self.assertTrue(ok)

    def test_ps_basic_setters(self):
        ok, msg = self.seq._execute_action("PS / Set Voltage", "48", 0)
        self.assertTrue(ok)
        ok, msg = self.seq._execute_action("PS / Set Current", "10", 0)
        self.assertTrue(ok)
        ok, msg = self.seq._execute_action("PS / Output ON", "", 0)
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
