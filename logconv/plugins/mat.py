
from logconv.model import LogFormatPlugin, FormatCapabilities, LogDocument, WriteResult, BusType, TimeBase


class MatPlugin(LogFormatPlugin):
    name = "mat"
    extensions = [".mat"]

    def capabilities(self) -> FormatCapabilities:
        return FormatCapabilities(supports_streaming=False, supports_signals=True, bus_types=[BusType.CUSTOM])

    def detect(self, path: str, sample: bytes = None) -> bool:
        return bool(path and path.lower().endswith(".mat"))

    def parse(self, path, options=None) -> LogDocument:
        meta = {"path": path, "format": "mat"}
        try:
            import scipy.io
            data = scipy.io.loadmat(path)
            meta["mat_keys"] = list(data.keys())
        except Exception as e:
            meta["error"] = str(e)
        return LogDocument(source_info=meta, bus_type=BusType.CUSTOM, time_base=TimeBase.ABS_NS, frames=[], metadata=meta)

    def write(self, path, log_doc: LogDocument, options=None) -> WriteResult:
        try:
            src = (log_doc.source_info or {}).get("path")
            if src and os.path.exists(src):
                import shutil
                shutil.copyfile(src, path)
                return WriteResult(success=True, output_paths=[path], warnings=["MAT plugin performs passthrough copy."])
            import scipy.io
            scipy.io.savemat(path, log_doc.metadata or {"info": "empty"})
            return WriteResult(success=True, output_paths=[path], warnings=["MAT plugin wrote metadata only; signals not encoded."])
        except Exception as e:
            return WriteResult(success=False, messages=[str(e)])


plugin = MatPlugin()
