
from logconv.model import LogFormatPlugin, FormatCapabilities, LogDocument, WriteResult, BusType, TimeBase


class PcapPlugin(LogFormatPlugin):
    name = "pcap"
    extensions = [".pcap", ".pcapng"]

    def capabilities(self) -> FormatCapabilities:
        return FormatCapabilities(supports_streaming=True, supports_signals=False, bus_types=[BusType.ETHERNET])

    def detect(self, path: str, sample: bytes = None) -> bool:
        return bool(path and (path.lower().endswith(".pcap") or path.lower().endswith(".pcapng")))

    def parse(self, path, options=None) -> LogDocument:
        meta = {"path": path, "format": "pcap"}
        try:
            with open(path, "rb") as f:
                data = f.read()
            meta["raw_bytes"] = data
        except Exception:
            meta["raw_bytes"] = b""
        return LogDocument(source_info=meta, bus_type=BusType.ETHERNET, time_base=TimeBase.ABS_NS, frames=[], metadata=meta)

    def write(self, path, log_doc: LogDocument, options=None) -> WriteResult:
        try:
            raw_bytes = log_doc.metadata.get("raw_bytes", b"")
            with open(path, "wb") as f:
                f.write(raw_bytes)
            warnings = ["PCAP plugin performs passthrough copy; protocol decoding not implemented."]
            return WriteResult(success=True, output_paths=[path], warnings=warnings)
        except Exception as e:
            return WriteResult(success=False, messages=[str(e)])


plugin = PcapPlugin()
