
import os
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
)
from PyQt6.QtCore import pyqtSignal, Qt, QThread
from logconv.engine import ConversionOrchestrator, ConversionPlan
from logconv.registry import load_builtin_plugins


class _Worker(QThread):
    progress = pyqtSignal(int, int, str)  # done, total, filename
    finished = pyqtSignal(str)

    def __init__(self, plan: ConversionPlan, logger=None):
        super().__init__()
        self.plan = plan
        self.logger = logger
        self.result_summary = ""

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
            status = entry.get("status")
            if status == "success":
                lines.append(f"[OK] {entry.get('input')} -> {entry.get('output')}")
            elif status == "warning":
                lines.append(f"[WARN] {entry.get('input')}: {entry.get('message')}")
            else:
                lines.append(f"[ERROR] {entry.get('input')}: {entry.get('message')}")
        self.result_summary = "\n".join(lines)
        self.finished.emit(self.result_summary)


class LogConverterTab(QWidget):
    def __init__(self, logger=None, parent=None):
        super().__init__(parent)
        self.logger = logger
        self.registry = self._safe_load_registry()
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
        self.btn_clear_files = QPushButton("Clear")
        self.btn_clear_files.clicked.connect(self.file_clear)
        row_files.addWidget(self.btn_clear_files)
        row_files.addStretch()
        layout.addLayout(row_files)

        self.file_list = QListWidget()
        layout.addWidget(self.file_list)

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

    def on_add_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select log files", os.getcwd())
        for f in files:
            self.file_list.addItem(f)

    def file_clear(self):
        self.file_list.clear()

    def on_browse_outdir(self):
        path = QFileDialog.getExistingDirectory(self, "Select output directory", os.getcwd())
        if path:
            self.outdir_edit.setText(path)

    def on_start(self):
        inputs = [self.file_list.item(i).text() for i in range(self.file_list.count())]
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

    def on_progress(self, done: int, total: int, fname: str):
        if total <= 0:
            return
        self.progress.setRange(0, total)
        self.progress.setValue(done)
        self.log_view.append(f"Converted {done}/{total}: {os.path.basename(fname)}")
