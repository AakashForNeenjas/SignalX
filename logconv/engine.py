
import os
from typing import List, Dict, Any, Optional, Iterable
from .model import LogDocument, WriteResult
from .registry import load_builtin_plugins, FormatRegistry
from .transforms import apply_transforms
from .validators import validate_document
from .report import ConversionReport


class ConversionPlan:
    def __init__(
        self,
        inputs: List[str],
        outputs: List[str],
        outdir: str,
        name_template: str = "{basename}_{fmt}",
        options: Optional[Dict[str, Any]] = None,
    ):
        self.inputs = inputs
        self.outputs = outputs
        self.outdir = outdir
        self.name_template = name_template
        self.options = options or {}


class ConversionOrchestrator:
    """Core orchestrator that handles parse -> transform -> write pipeline."""

    def __init__(self, registry: Optional[FormatRegistry] = None, logger=None):
        self.registry = registry or load_builtin_plugins()
        self.logger = logger

    def _log(self, level, msg):
        if self.logger:
            try:
                self.logger.log(level, msg)
            except Exception:
                pass

    def convert(self, plan: ConversionPlan, progress_cb=None) -> ConversionReport:
        report = ConversionReport()
        os.makedirs(plan.outdir, exist_ok=True)
        total = len(plan.inputs)
        for idx, input_path in enumerate(plan.inputs):
            detected = self.registry.detect_for_path(input_path)
            if not detected:
                msg = f"Could not detect format for {input_path}"
                report.add_error(input_path, msg)
                self._log(40, msg)
                continue
            try:
                read_opts = plan.options.get("read", {}).get(detected.name, {})
                doc: LogDocument = detected.parse(input_path, read_opts)
                validate_document(doc, report)
                doc = apply_transforms(doc, plan.options.get("transforms", {}))
                for out_fmt in plan.outputs:
                    writer = self.registry.get(out_fmt)
                    if not writer:
                        report.add_warning(input_path, f"Output format {out_fmt} not registered")
                        continue
                    out_opts = plan.options.get("write", {}).get(out_fmt, {})
                    basename = os.path.splitext(os.path.basename(input_path))[0]
                    out_name = plan.name_template.format(basename=basename, fmt=out_fmt)
                    out_path = os.path.join(plan.outdir, f"{out_name}.{writer.extensions[0].lstrip('.') if writer.extensions else out_fmt}")
                    write_result: WriteResult = writer.write(out_path, doc, out_opts)
                    if write_result.success:
                        report.add_success(input_path, out_path, write_result.warnings)
                    else:
                        report.add_error(input_path, f"Failed writing {out_fmt}: {'; '.join(write_result.messages)}")
            except Exception as e:
                report.add_error(input_path, f"Conversion failed: {e}")
                self._log(40, f"Conversion failed for {input_path}: {e}")
            if progress_cb:
                try:
                    progress_cb(idx + 1, total, input_path)
                except Exception:
                    pass
        return report
