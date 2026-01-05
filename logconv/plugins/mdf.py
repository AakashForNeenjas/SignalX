
from logconv.model import LogFormatPlugin, FormatCapabilities, LogDocument, WriteResult, BusType, TimeBase


class MdfPlugin(LogFormatPlugin):
    name = "mdf"
    extensions = [".mdf", ".mf4"]

    def capabilities(self) -> FormatCapabilities:
        return FormatCapabilities(supports_streaming=False, supports_signals=True, bus_types=[BusType.CAN, BusType.ETHERNET, BusType.CUSTOM])

    def detect(self, path: str, sample: bytes = None) -> bool:
        return bool(path and (path.lower().endswith(".mdf") or path.lower().endswith(".mf4")))

    def parse(self, path, options=None) -> LogDocument:
        meta = {"path": path, "format": "mdf"}
        try:
            import asammdf  # optional
            mdf = asammdf.MDF(path)
            meta["mdf_version"] = mdf.version
            meta["channel_count"] = len(mdf.channels_db)
        except Exception as e:
            meta["error"] = str(e)
        return LogDocument(source_info=meta, bus_type=BusType.CAN, time_base=TimeBase.ABS_NS, frames=[], metadata=meta)

    def write(self, path, log_doc: LogDocument, options=None) -> WriteResult:
        try:
            src = (log_doc.source_info or {}).get("path")
            if src and os.path.exists(src):
                import shutil
                shutil.copyfile(src, path)
                return WriteResult(success=True, output_paths=[path], warnings=["MDF/MF4 plugin performs passthrough copy."])
            return WriteResult(success=False, messages=["MDF write failed: no source bytes to copy"])
        except Exception as e:
            return WriteResult(success=False, messages=[str(e)])


plugin = MdfPlugin()
