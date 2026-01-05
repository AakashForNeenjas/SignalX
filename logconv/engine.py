
import os
from typing import List, Dict, Any, Optional, Iterable
import time
from .model import LogDocument, WriteResult, ConversionEntry
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
            start_ts = time.time()
            detected, reason = self.registry.detect_for_path(input_path)
            entry = ConversionEntry(
                input=input_path,
                detected_format=detected.name if detected else None,
                status="pending",
                warnings=[],
                errors=[],
            )
            if not detected:
                msg = f"Could not detect format for {input_path}: {reason}"
                entry.status = "error"
                entry.errors.append(msg)
                report.add_entry(entry)
                self._log(40, msg)
                if progress_cb:
                    try:
                        progress_cb(idx + 1, total, input_path)
                    except Exception:
                        pass
                continue
            try:
                read_opts = plan.options.get("read", {}).get(detected.name, {})
                doc: LogDocument = detected.parse(input_path, read_opts)
                validate_document(doc, report)  # still populates warnings on report
                doc = apply_transforms(doc, plan.options.get("transforms", {}))
                entry.status = "success"
                for out_fmt in plan.outputs:
                    writer = self.registry.get(out_fmt)
                    if not writer:
                        warn = f"Output format {out_fmt} not registered"
                        entry.status = "warning"
                        entry.warnings.append(warn)
                        continue
                    out_opts = plan.options.get("write", {}).get(out_fmt, {})
                    basename = os.path.splitext(os.path.basename(input_path))[0]
                    out_name = plan.name_template.format(basename=basename, fmt=out_fmt)
                    ext = writer.extensions[0].lstrip('.') if getattr(writer, "extensions", None) else out_fmt
                    out_path = os.path.join(plan.outdir, f"{out_name}.{ext}")
                    write_result: WriteResult = writer.write(out_path, doc, out_opts)
                    if write_result.success:
                        entry.outputs.append(out_path)
                        entry.warnings.extend(write_result.warnings or [])
                        if write_result.messages:
                            entry.notes = entry.notes + write_result.messages if entry.notes else write_result.messages
                    else:
                        entry.status = "error"
                        entry.errors.append(f"Failed writing {out_fmt}: {'; '.join(write_result.messages)}")
            except Exception as e:
                entry.status = "error"
                entry.errors.append(f"Conversion failed: {e}")
                self._log(40, f"Conversion failed for {input_path}: {e}")
            entry.duration_ms = round((time.time() - start_ts) * 1000, 1)
            report.add_entry(entry)
            if progress_cb:
                try:
                    progress_cb(idx + 1, total, input_path)
                except Exception:
                    pass
        report.mark_finished()
        return report
