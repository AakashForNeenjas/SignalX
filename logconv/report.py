
import json
import html
from datetime import datetime
from typing import List
from .model import ConversionEntry


class ConversionReport:
    def __init__(self):
        self.entries: List[ConversionEntry] = []
        self.started = datetime.now()
        self.finished = None

    def add_entry(self, entry: ConversionEntry):
        self.entries.append(entry)

    # Backward-compatible helpers (used by validators)
    def add_error(self, input_path, message):
        self.entries.append(ConversionEntry(input=input_path, detected_format=None, status="error", errors=[message]))

    def add_warning(self, input_path, message):
        self.entries.append(ConversionEntry(input=input_path, detected_format=None, status="warning", warnings=[message]))

    def add_success(self, input_path, output_path, warnings=None):
        self.entries.append(
            ConversionEntry(
                input=input_path,
                detected_format=None,
                status="success",
                outputs=[output_path],
                warnings=warnings or [],
            )
        )

    def mark_finished(self):
        self.finished = datetime.now()

    def to_dict(self):
        return {
            "started": self.started.isoformat(),
            "finished": (self.finished or datetime.now()).isoformat(),
            "entries": [entry.__dict__ for entry in self.entries],
        }

    def to_json(self, indent=2):
        return json.dumps(self.to_dict(), default=str, indent=indent)

    def to_html(self):
        def esc(s):
            return html.escape(str(s)) if s is not None else ""

        rows = []
        for e in self.entries:
            outs = "<br>".join(e.outputs) if e.outputs else ""
            warns = "<br>".join(e.warnings) if e.warnings else ""
            errs = "<br>".join(e.errors) if e.errors else ""
            rows.append(
                f"<tr><td>{esc(e.input)}</td><td>{esc(e.detected_format)}</td><td>{esc(e.status)}</td>"
                f"<td>{esc(e.duration_ms)} ms</td><td>{esc(outs)}</td><td>{esc(warns)}</td><td>{esc(errs)}</td></tr>"
            )
        html_doc = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Log Conversion Report</title>
<style>
body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #0b111a; color: #e7f1ff; padding: 24px; }}
table {{ width: 100%; border-collapse: collapse; margin-top: 12px; border: 1px solid #1f2b3d; }}
th, td {{ border: 1px solid #1f2b3d; padding: 8px; font-size: 13px; }}
th {{ background: #162133; color: #c8ddf5; text-align: left; }}
tr:nth-child(even) {{ background: #0f1726; }}
tr:nth-child(odd) {{ background: #0c141f; }}
</style>
</head>
<body>
<h2>Log Conversion Report</h2>
<div>Started: {esc(self.started)}<br>Finished: {esc(self.finished or datetime.now())}</div>
<table>
<thead><tr><th>Input</th><th>Detected</th><th>Status</th><th>Duration</th><th>Outputs</th><th>Warnings</th><th>Errors</th></tr></thead>
<tbody>
{''.join(rows)}
</tbody>
</table>
</body>
</html>"""
        return html_doc
