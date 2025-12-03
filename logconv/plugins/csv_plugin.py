
from logconv.model import LogFormatPlugin, FormatCapabilities, LogDocument, WriteResult, BusType, TimeBase


class CsvPlugin(LogFormatPlugin):
    name = "csv"
    extensions = [".csv"]

    def capabilities(self) -> FormatCapabilities:
        return FormatCapabilities(supports_streaming=True, supports_signals=True, bus_types=[BusType.CAN, BusType.ETHERNET])

    def parse(self, path, options=None) -> LogDocument:
        meta = {"path": path, "format": "csv"}
        try:
            with open(path, "rb") as f:
                data = f.read()
            meta["raw_bytes"] = data
            try:
                meta["raw_text"] = data.decode("utf-8", errors="ignore")
            except Exception:
                pass
        except Exception:
            meta["raw_bytes"] = b""
        return LogDocument(source_info=meta, bus_type=BusType.CAN, time_base=TimeBase.REL_NS, frames=[], metadata=meta)

    def write(self, path, log_doc: LogDocument, options=None) -> WriteResult:
        try:
            raw_bytes = log_doc.metadata.get("raw_bytes")
            raw_text = log_doc.metadata.get("raw_text")
            if raw_bytes is not None:
                with open(path, "wb") as f:
                    f.write(raw_bytes)
            elif raw_text is not None:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(raw_text)
            else:
                with open(path, "w", encoding="utf-8") as f:
                    f.write("timestamp_ns,id,dlc,payload_hex\n")
            return WriteResult(success=True, output_paths=[path])
        except Exception as e:
            return WriteResult(success=False, messages=[str(e)])


plugin = CsvPlugin()
