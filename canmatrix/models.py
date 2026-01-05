
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Literal
from enum import Enum


class StepType(str, Enum):
    SEND_MESSAGE = "send_message"
    SEND_SIGNAL_VALUES = "send_signal_values"
    START_CYCLIC = "start_cyclic"
    STOP_CYCLIC = "stop_cyclic"
    WAIT_TIME = "wait_time"
    WAIT_FOR_SIGNAL = "wait_for_signal"
    WAIT_FOR_MESSAGE = "wait_for_message"
    ASSERT_CHECK = "assert_check"
    INJECT_FAULT = "inject_fault"
    STRESS_BUS = "stress_bus"
    STABILITY_MONITOR = "stability_monitor"
    CHECK_SIGNAL = "check_signal"
    INJECT_ERROR = "inject_error"
    BUS_LOAD = "bus_load"
    BURST = "burst"


@dataclass
class Assertion:
    target: str
    op: Literal["==", "!=", ">", "<", ">=", "<=", "in_range", "approx", "exists", "not_none"]
    expected: Any
    kind: Optional[str] = None  # e.g., cycle_time, range, dlc, checksum, counter, latency, plausibility
    tolerance: Optional[float] = None
    window_ms: Optional[float] = None
    message: Optional[str] = None


@dataclass
class TestStep:
    type: StepType
    params: Dict[str, Any] = field(default_factory=dict)
    timeout_ms: Optional[int] = None
    description: str = ""


@dataclass
class TestCase:
    id: str
    name: str
    description: str = ""
    tags: List[str] = field(default_factory=list)
    preconditions: List[TestStep] = field(default_factory=list)
    main_steps: List[TestStep] = field(default_factory=list)
    postconditions: List[TestStep] = field(default_factory=list)
    assertions: List[Assertion] = field(default_factory=list)
    requirement_ids: List[str] = field(default_factory=list)
    timeout_ms: Optional[int] = None
    priority: int = 5


@dataclass
class TestSuite:
    name: str
    description: str = ""
    cases: List[TestCase] = field(default_factory=list)


@dataclass
class Project:
    name: str
    ecu: str
    dbc_paths: List[str]
    can_config: Dict[str, Any] = field(default_factory=dict)
    dvp_meta: Dict[str, Any] = field(default_factory=dict)
    suites: List[TestSuite] = field(default_factory=list)


@dataclass
class TestResult:
    case_id: str
    passed: bool
    log: List[str] = field(default_factory=list)
    assertions: List[Dict[str, Any]] = field(default_factory=list)
    start_ts: float = 0.0
    end_ts: float = 0.0
    raw_log_path: Optional[str] = None
    decoded_log_path: Optional[str] = None
