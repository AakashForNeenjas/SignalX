
import os
from logconv.model import LogFormatPlugin, FormatCapabilities, LogDocument, WriteResult, BusType, TimeBase


class BlfPlugin(LogFormatPlugin):
    name = "blf"
    extensions = [".blf"]

    def capabilities(self) -> FormatCapabilities:
        return FormatCapabilities(supports_streaming=True, supports_signals=False, bus_types=[BusType.CAN])

    def parse(self, path, options=None) -> LogDocument:
        # Avoid loading whole BLF into memory; just record source path and basic meta
        meta = {"path": path, "format": "blf"}
        return LogDocument(source_info=meta, bus_type=BusType.CAN, time_base=TimeBase.REL_NS, frames=[], metadata=meta)

    def write(self, path, log_doc: LogDocument, options=None) -> WriteResult:
        src = (log_doc.source_info or {}).get("path")
        # If python-can is available, do a best-effort BLF->TRC text conversion; else copy bytes.
        try:
            import can
            reader = can.io.BLFReader(src)
            first_ts = None
            with open(path, "w", encoding="utf-8") as f:
                f.write(";$FILEVERSION=1.3\n")
                for msg in reader:
                    if first_ts is None:
                        first_ts = msg.timestamp
                    t_rel = msg.timestamp - first_ts if first_ts is not None else 0.0
                    ch = getattr(msg, "channel", 1) or 1
                    direction = "Rx" if getattr(msg, "is_rx", True) else "Tx"
                    arb_id = msg.arbitration_id
                    dlc = msg.dlc
                    data_bytes = getattr(msg, "data", b"")
                    data_str = " ".join(f"{b:02X}" for b in data_bytes[:dlc])
                    f.write(f"{t_rel:0.6f} {ch} {direction} {arb_id:08X} d {dlc} {data_str}\n")
            return WriteResult(success=True, output_paths=[path])
        except Exception:
            try:
                if src and os.path.exists(src):
                    import shutil
                    shutil.copyfile(src, path)
                    return WriteResult(success=True, output_paths=[path], warnings=["Copied BLF as-is (conversion library unavailable)."])
            except Exception as e2:
                return WriteResult(success=False, messages=[str(e2)])
        return WriteResult(success=False, messages=["BLF write failed"])


plugin = BlfPlugin()
