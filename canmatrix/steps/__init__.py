
from .base import StepExecutor
from .send_signal_values import SendSignalValues
from .send_message import SendMessage
from .wait_time import WaitTime
from .wait_for_signal import WaitForSignal
from .wait_for_message import WaitForMessage
from .start_cyclic import StartCyclic
from .stop_cyclic import StopCyclic
from .assert_check import AssertCheck
from .inject_fault import InjectFault
from .stress_bus import StressBus
from .stability_monitor import StabilityMonitor


EXECUTORS = {
    "send_signal_values": SendSignalValues,
    "send_message": SendMessage,
    "wait_time": WaitTime,
    "wait_for_signal": WaitForSignal,
    "wait_for_message": WaitForMessage,
    "start_cyclic": StartCyclic,
    "stop_cyclic": StopCyclic,
    "assert_check": AssertCheck,
    "inject_fault": InjectFault,
    "stress_bus": StressBus,
    "stability_monitor": StabilityMonitor,
}
