
from dataclasses import dataclass, field
from typing import Iterable, Iterator, List, Optional, Dict, Any, Union


class BusType:
    CAN = "CAN"
    LIN = "LIN"
    FLEXRAY = "FLEXRAY"
    ETHERNET = "ETH"
    CUSTOM = "CUSTOM"


class TimeBase:
    ABS_NS = "ABS_NS"
    ABS_S = "ABS_S"
    REL_NS = "REL_NS"
    REL_S = "REL_S"


@dataclass
class ChannelInfo:
    id: str
    name: Optional[str] = None
    interface: Optional[str] = None
    bitrate: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Frame:
    timestamp_ns: int
    arbitration_id: int
    dlc: int
    payload: bytes
    direction: str = "rx"
    channel: Optional[str] = None
    id_format: str = "standard"  # or "extended"
    flags: Dict[str, Any] = field(default_factory=dict)
    sequence_no: Optional[int] = None
    annotations: List[str] = field(default_factory=list)


@dataclass
class SignalSample:
    frame_ref: Optional[int]
    name: str
    value: Union[int, float, str]
    unit: Optional[str] = None
    raw: Optional[bytes] = None
    scaling: Optional[float] = None
    offset: Optional[float] = None
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    info: List[str] = field(default_factory=list)


@dataclass
class LogDocument:
    source_info: Dict[str, Any]
    bus_type: str
    time_base: str
    frames: Iterable[Frame]
    channels: List[ChannelInfo] = field(default_factory=list)
    signals: List[SignalSample] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    validation: Optional[ValidationResult] = None


@dataclass
class WriteResult:
    success: bool
    messages: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    output_paths: List[str] = field(default_factory=list)


class FormatCapabilities:
    def __init__(self, *, supports_streaming: bool, supports_signals: bool, bus_types: List[str]):
        self.supports_streaming = supports_streaming
        self.supports_signals = supports_signals
        self.bus_types = bus_types


class LogFormatPlugin:
    """Interface all log-converter plugins must implement."""

    name: str = ""
    extensions: List[str] = []

    def capabilities(self) -> FormatCapabilities:
        raise NotImplementedError

    def default_read_options(self) -> Dict[str, Any]:
        return {}

    def default_write_options(self) -> Dict[str, Any]:
        return {}

    def describe_options(self) -> Dict[str, Dict[str, Any]]:
        """Return option schema for UI/CLI generation."""
        return {}

    def detect(self, path: str, sample: Optional[bytes] = None) -> bool:
        """Optional sniff override; default uses extension match."""
        if not path:
            return False
        return any(path.lower().endswith(ext) for ext in self.extensions)

    def parse(self, path: str, options: Optional[Dict[str, Any]] = None) -> LogDocument:
        raise NotImplementedError

    def write(self, path: str, log_doc: LogDocument, options: Optional[Dict[str, Any]] = None) -> WriteResult:
        raise NotImplementedError
