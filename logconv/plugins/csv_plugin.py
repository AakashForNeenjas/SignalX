
import csv
from logconv.model import (
    LogFormatPlugin,
    FormatCapabilities,
    LogDocument,
    WriteResult,
    BusType,
    TimeBase,
    Frame,
)


class CsvPlugin(LogFormatPlugin):
    name = "csv"
    extensions = [".csv"]

    def capabilities(self) -> FormatCapabilities:
        return FormatCapabilities(supports_streaming=True, supports_signals=True, bus_types=[BusType.CAN, BusType.ETHERNET])

    def detect(self, path: str, sample: bytes = None) -> bool:
        return bool(path and path.lower().endswith(".csv"))

    def parse(self, path, options=None) -> LogDocument:
        meta = {"path": path, "format": "csv"}
        frames = []
        try:
            import can

            reader = can.CSVReader(path)
            base_ns = None
            for msg in reader:
                ts_ns = int(msg.timestamp * 1_000_000_000)
                if base_ns is None:
                    base_ns = ts_ns
                frames.append(
                    Frame(
                        timestamp_ns=ts_ns - base_ns,
                        arbitration_id=msg.arbitration_id,
                        dlc=msg.dlc,
                        payload=bytes(msg.data or b""),
                        direction="rx" if getattr(msg, "is_rx", True) else "tx",
                        channel=str(getattr(msg, "channel", 1) or "1"),
                        id_format="extended" if msg.is_extended_id else "standard",
                    )
                )
            meta["frame_count"] = len(frames)
        except Exception:
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

        if frames:
            return LogDocument(
                source_info=meta,
                bus_type=BusType.CAN,
                time_base=TimeBase.REL_NS,
                frames=frames,
                metadata=meta,
            )
        return LogDocument(source_info=meta, bus_type=BusType.CAN, time_base=TimeBase.REL_NS, frames=[], metadata=meta)

    def write(self, path, log_doc: LogDocument, options=None) -> WriteResult:
        try:
            if log_doc.frames:
                try:
                    import can

                    writer = can.CSVWriter(path)
                    base_ns = log_doc.frames[0].timestamp_ns if log_doc.frames else 0
                    for fr in log_doc.frames:
                        msg = can.Message(
                            arbitration_id=fr.arbitration_id,
                            dlc=fr.dlc,
                            data=fr.payload,
                            is_extended_id=fr.arbitration_id > 0x7FF,
                            timestamp=(fr.timestamp_ns + base_ns) / 1_000_000_000.0,
                        )
                        writer.on_message_received(msg)
                    writer.stop()
                    return WriteResult(success=True, output_paths=[path], warnings=[])
                except Exception:
                    pass

            raw_bytes = log_doc.metadata.get("raw_bytes")
            raw_text = log_doc.metadata.get("raw_text")
            if raw_bytes is not None:
                with open(path, "wb") as f:
                    f.write(raw_bytes)
            elif raw_text is not None:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(raw_text)
            else:
                with open(path, "w", encoding="utf-8", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(["timestamp_ns", "id", "dlc", "payload_hex"])
            warnings = ["CSV plugin performed raw passthrough (frames not re-encoded)."]
            return WriteResult(success=True, output_paths=[path], warnings=warnings)
        except Exception as e:
            return WriteResult(success=False, messages=[str(e)])


plugin = CsvPlugin()
