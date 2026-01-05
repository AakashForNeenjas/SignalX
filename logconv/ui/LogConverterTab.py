
import os
from pathlib import Path
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QFileDialog,
    QTextEdit,
    QProgressBar,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QAbstractItemView,
)
from PyQt6.QtCore import pyqtSignal, Qt, QThread
from logconv.engine import ConversionOrchestrator, ConversionPlan
from logconv.registry import load_builtin_plugins
from logconv.report import ConversionReport


class _Worker(QThread):
    progress = pyqtSignal(int, int, str)  # done, total, filename
    finished = pyqtSignal(str)

    def __init__(self, plan: ConversionPlan, logger=None):
        super().__init__()
        self.plan = plan
        self.logger = logger
        self.result_summary = ""
        self.report_json = None
        self.report_html = None

    def run(self):
        orch = ConversionOrchestrator(load_builtin_plugins(), logger=self.logger)

        def _cb(done, total, fname):
            try:
                self.progress.emit(done, total, fname)
            except Exception:
                pass

        report = orch.convert(self.plan, progress_cb=_cb)
        lines = []
        for entry in report.entries:
            # Support both dict and dataclass ConversionEntry
            e = entry.__dict__ if hasattr(entry, "__dict__") else entry
            status = e.get("status")
            inp = e.get("input")
            outputs = e.get("outputs") or e.get("output") or []
            if isinstance(outputs, str):
                outputs = [outputs]
            warnings = e.get("warnings") or []
            errors = e.get("errors") or []
            if status == "success":
                lines.append(f"[OK] {inp} -> {', '.join(outputs)}")
            elif status == "warning":
                lines.append(f"[WARN] {inp}: {errors or warnings}")
            else:
                lines.append(f"[ERROR] {inp}: {errors or warnings}")

        # Persist batch report (JSON + HTML) to Test Results
        out_dir = Path("Test Results")
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_path = out_dir / f"logconverter_{ts}.json"
        html_path = out_dir / f"logconverter_{ts}.html"
        try:
            json_path.write_text(report.to_json(), encoding="utf-8")
            self.report_json = json_path
        except Exception:
            pass
        try:
            html_path.write_text(report.to_html(), encoding="utf-8")
            self.report_html = html_path
        except Exception:
            pass

        self.result_summary = "\n".join(lines)
        if lines:
            self.result_summary += f"\nReports: {json_path} , {html_path}"
        self.finished.emit(self.result_summary)


class LogConverterTab(QWidget):
    def __init__(self, logger=None, parent=None):
        super().__init__(parent)
        self.logger = logger
        self.registry = self._safe_load_registry()
        self.last_report_paths = (None, None)
        self._setup_ui()
        self.worker = None

    def _safe_load_registry(self):
        try:
            return load_builtin_plugins()
        except Exception as e:
            # Degrade gracefully if plugin load fails
            if self.logger:
                try:
                    self.logger.error(f"Failed to load log converter plugins: {e}")
                except Exception:
                    pass
            return None

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        header = QLabel("Log Converter")
        header.setStyleSheet("font-size: 18px; font-weight: bold; color: #00ff88;")
        layout.addWidget(header)

        row_files = QHBoxLayout()
        self.btn_add_files = QPushButton("Add Input Files")
        self.btn_add_files.clicked.connect(self.on_add_files)
        row_files.addWidget(self.btn_add_files)
        self.btn_remove_files = QPushButton("Remove Selected")
        self.btn_remove_files.clicked.connect(self.on_remove_selected)
        row_files.addWidget(self.btn_remove_files)
        self.btn_clear_files = QPushButton("Clear")
        self.btn_clear_files.clicked.connect(self.file_clear)
        row_files.addWidget(self.btn_clear_files)
        row_files.addStretch()
        layout.addLayout(row_files)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Input file", "Detected", "Status"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

        row_outdir = QHBoxLayout()
        row_outdir.addWidget(QLabel("Output Dir:"))
        self.outdir_edit = QLineEdit(os.path.join(os.getcwd(), "converted_logs"))
        row_outdir.addWidget(self.outdir_edit)
        self.btn_browse_outdir = QPushButton("Browse")
        self.btn_browse_outdir.clicked.connect(self.on_browse_outdir)
        row_outdir.addWidget(self.btn_browse_outdir)
        layout.addLayout(row_outdir)

        row_formats = QHBoxLayout()
        row_formats.addWidget(QLabel("Output Formats:"))
        self.format_list = QListWidget()
        self.format_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        if self.registry:
            for plugin in self.registry.all():
                item = QListWidgetItem(plugin.name)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                # Pre-check a common export (trc/csv if present)
                if plugin.name.lower() in ("trc", "csv"):
                    item.setCheckState(Qt.CheckState.Checked)
                else:
                    item.setCheckState(Qt.CheckState.Unchecked)
                self.format_list.addItem(item)
        else:
            err_item = QListWidgetItem("No plugins loaded")
            err_item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.format_list.addItem(err_item)
        row_formats.addWidget(self.format_list)
        layout.addLayout(row_formats)

        self.btn_start = QPushButton("Start Conversion")
        self.btn_start.clicked.connect(self.on_start)
        layout.addWidget(self.btn_start)

        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view)

        self.last_report_label = QLabel("Last report: n/a")
        layout.addWidget(self.last_report_label)

    def on_add_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select log files", os.getcwd())
        for f in files:
            self._add_file(f)

    def file_clear(self):
        self.table.setRowCount(0)

    def on_browse_outdir(self):
        path = QFileDialog.getExistingDirectory(self, "Select output directory", os.getcwd())
        if path:
            self.outdir_edit.setText(path)

    def on_start(self):
        inputs = [self.table.item(r, 0).text() for r in range(self.table.rowCount())]
        if not inputs:
            self.log_view.append("No input files selected.")
            return
        outputs = [
            self.format_list.item(i).text()
            for i in range(self.format_list.count())
            if self.format_list.item(i).checkState() == Qt.CheckState.Checked
        ]
        if not outputs:
            self.log_view.append("Select at least one output format.")
            return
        if not self.registry:
            self.log_view.append("Converter plugins failed to load. Check installation.")
            return
        outdir = self.outdir_edit.text() or "converted_logs"
        plan = ConversionPlan(inputs=inputs, outputs=outputs, outdir=outdir)
        self.progress.setRange(0, 0)  # busy
        self.worker = _Worker(plan, logger=self.logger)
        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def on_finished(self, summary: str):
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        self.log_view.append(summary or "Done.")
        if self.worker:
            json_path = self.worker.report_json
            html_path = self.worker.report_html
            if json_path and html_path:
                self.last_report_label.setText(f"Last report: {json_path} | {html_path}")
            elif json_path:
                self.last_report_label.setText(f"Last report: {json_path}")
            elif html_path:
                self.last_report_label.setText(f"Last report: {html_path}")

    def on_progress(self, done: int, total: int, fname: str):
        if total <= 0:
            return
        self.progress.setRange(0, total)
        self.progress.setValue(done)
        self.log_view.append(f"Converted {done}/{total}: {os.path.basename(fname)}")
        # Update status column for the matching row
        for row in range(self.table.rowCount()):
            if self.table.item(row, 0).text() == fname:
                self.table.setItem(row, 2, QTableWidgetItem(f"{done}/{total}"))
                break

    def _add_file(self, path: str):
        if not path:
            return
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(path))
        detected_text = "n/a"
        if self.registry:
            plugin, reason = self.registry.detect_for_path(path)
            if plugin:
                detected_text = plugin.name
            elif reason:
                detected_text = f"Not detected ({reason})"
        self.table.setItem(row, 1, QTableWidgetItem(detected_text))
        self.table.setItem(row, 2, QTableWidgetItem("Pending"))

    def on_remove_selected(self):
        rows = sorted({idx.row() for idx in self.table.selectedIndexes()}, reverse=True)
        for r in rows:
            self.table.removeRow(r)
