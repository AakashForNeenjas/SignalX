
import os
from logconv.model import (
    LogFormatPlugin,
    FormatCapabilities,
    LogDocument,
    WriteResult,
    BusType,
    TimeBase,
)


class BlfPlugin(LogFormatPlugin):
    name = "blf"
    extensions = [".blf"]

    def capabilities(self) -> FormatCapabilities:
        return FormatCapabilities(supports_streaming=True, supports_signals=False, bus_types=[BusType.CAN])

    def detect(self, path: str, sample: bytes = None) -> bool:
        if path and any(path.lower().endswith(ext) for ext in self.extensions):
            return True
        if sample:
            return sample[:4] == b"L\x04\x00\x00"  # BLF magic
        return False

    def parse(self, path, options=None) -> LogDocument:
        # Avoid loading whole BLF into memory; just record source path and basic meta
        meta = {"path": path, "format": "blf"}
        return LogDocument(source_info=meta, bus_type=BusType.CAN, time_base=TimeBase.REL_NS, frames=[], metadata=meta)

    def write(self, path, log_doc: LogDocument, options=None) -> WriteResult:
        src = (log_doc.source_info or {}).get("path")
        # If python-can is available, emit a BLF with frames; otherwise copy source if exists.
        try:
            import can

            if log_doc.frames:
                writer = can.BLFWriter(path)
                for fr in log_doc.frames:
                    msg = can.Message(
                        arbitration_id=fr.arbitration_id,
                        dlc=fr.dlc,
                        data=fr.payload,
                        is_extended_id=fr.arbitration_id > 0x7FF,
                        timestamp=fr.timestamp_ns / 1_000_000_000.0,
                        channel=int(fr.channel) if fr.channel and str(fr.channel).isdigit() else None,
                    )
                    writer.on_message_received(msg)
                writer.stop()
                return WriteResult(success=True, output_paths=[path], warnings=[])

            if src and os.path.exists(src):
                import shutil
                shutil.copyfile(src, path)
                return WriteResult(success=True, output_paths=[path], warnings=["Copied BLF as-is (no frames parsed)."])
        except Exception:
            if src and os.path.exists(src):
                try:
                    import shutil
                    shutil.copyfile(src, path)
                    return WriteResult(success=True, output_paths=[path], warnings=["BLF backend unavailable; copied source bytes."])
                except Exception as e2:
                    return WriteResult(success=False, messages=[str(e2)])
        return WriteResult(success=False, messages=["BLF write failed"])


plugin = BlfPlugin()
