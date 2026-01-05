
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QListWidget, QListWidgetItem, QTextEdit, QGroupBox, QGridLayout, QProgressBar
from PyQt6.QtCore import Qt, QThread, pyqtSignal
import json
import os
import datetime
import threading
from canmatrix.runner import TestRunner, build_auto_suite_from_dbc
from canmatrix.can_interface import CanInterface
from canmatrix.dbc_manager import DbcManager
from canmatrix.models import Project, TestSuite, TestCase, TestStep, Assertion, StepType
from canmatrix.dbc_manager import DbcManager
from canmatrix import report as cm_report

# Serialize report writes to avoid race between JSON/HTML generations when runs overlap
REPORT_WRITE_LOCK = threading.Lock()


class CANMatrixTab(QWidget):
    """Minimal CAN Matrix UI stub."""

    def __init__(self, can_mgr=None, dbc_parser=None, logger=None, signal_manager=None, parent=None):
        super().__init__(parent)
        self.can_mgr = can_mgr
        self.dbc_parser = dbc_parser
        self.logger = logger
        self.signal_manager = signal_manager
        self.dbc_mgr = DbcManager()
        if dbc_parser and getattr(dbc_parser, "database", None):
            self.dbc_mgr.use_existing(dbc_parser.database)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        header = QLabel("CAN Matrix Testing (prototype)")
        header.setStyleSheet("font-weight: bold; font-size: 16px;")
        layout.addWidget(header)

        top = QHBoxLayout()
        self.btn_run = QPushButton("Run Demo Suite")
        self.btn_run.clicked.connect(self.on_run_demo)
        top.addWidget(self.btn_run)
        self.btn_run_auto = QPushButton("Run Auto DBC Tests")
        self.btn_run_auto.clicked.connect(self.on_run_auto)
        top.addWidget(self.btn_run_auto)
        # Status strip with spinner/progress
        self.run_status = QLabel("Idle")
        self.run_status.setStyleSheet("color: #9db4d4;")
        self.run_progress = QProgressBar()
        self.run_progress.setMinimum(0)
        self.run_progress.setMaximum(0)  # indeterminate
        self.run_progress.setTextVisible(False)
        self.run_progress.setVisible(False)
        status_box = QHBoxLayout()
        status_box.addWidget(self.run_status)
        status_box.addWidget(self.run_progress)
        status_box.addStretch()
        top.addLayout(status_box)
        top.addStretch()
        layout.addLayout(top)

        lists_layout = QHBoxLayout()
        self.suite_list = QListWidget()
        self.case_list = QListWidget()
        lists_layout.addWidget(self.suite_list, 1)
        lists_layout.addWidget(self.case_list, 1)
        layout.addLayout(lists_layout)

        # Summary dashboard
        dash_box = QGroupBox("Coverage Dashboard")
        dash_grid = QGridLayout()
        self.lbl_static = QLabel("Static: 0 / 0")
        self.lbl_dynamic = QLabel("Dynamic: 0 / 0")
        self.lbl_timing = QLabel("Timing: n/a")
        self.static_cov = QListWidget()
        self.dynamic_cov = QListWidget()
        self.static_cov.setMinimumHeight(80)
        self.dynamic_cov.setMinimumHeight(80)
        dash_grid.addWidget(self.lbl_static, 0, 0)
        dash_grid.addWidget(self.lbl_dynamic, 0, 1)
        dash_grid.addWidget(self.lbl_timing, 0, 2)
        dash_grid.addWidget(self.static_cov, 1, 0)
        dash_grid.addWidget(self.dynamic_cov, 1, 1)
        dash_box.setLayout(dash_grid)
        layout.addWidget(dash_box)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view, 2)

        # demo project/suite/case
        demo_case = TestCase(
            id="CM-001",
            name="Demo Static Check",
            main_steps=[TestStep(type=StepType.WAIT_TIME, params={"ms": 100})],
            assertions=[Assertion(target="DemoSignal", op="==", expected=1)]
        )
        self.demo_suite = TestSuite(name="Demo Suite", cases=[demo_case])
        self.suite_list.addItem(QListWidgetItem(self.demo_suite.name))
        self.case_list.addItem(QListWidgetItem(demo_case.name))
        self.worker = None
        self._set_running(False, text="Idle")

    def on_run_demo(self):
        if not self.can_mgr or not self.dbc_mgr:
            self.log_view.append("CAN/DBC not initialized; running dry demo.")
        runner = TestRunner(CanInterface(self.can_mgr) if self.can_mgr else None, self.dbc_mgr, logger=self.logger, can_mgr=self.can_mgr, signal_manager=self.signal_manager)
        results = runner.run_suite(self.demo_suite)
        for res in results:
            self.log_view.append(f"{res.case_id} passed={res.passed} log={res.log}")

    def on_run_auto(self):
        if self.worker and self.worker.isRunning():
            self.log_view.append("Run already in progress.")
            return
        # Attempt to load DBC from DBC folder if not already
        if not self.dbc_mgr.db:
            import glob, os
            dbc_files = glob.glob(os.path.join("DBC", "*.dbc"))
            if dbc_files:
                try:
                    self.dbc_mgr.load(dbc_files[0])
                    self.log_view.append(f"Loaded DBC: {dbc_files[0]}")
                except Exception as e:
                    self.log_view.append(f"Failed to load DBC: {e}")
            else:
                self.log_view.append("No DBC files found in DBC folder.")
                return
        suite = build_auto_suite_from_dbc(self.dbc_mgr)
        if not suite.cases:
            self.log_view.append("No cases generated.")
            return
        self.suite_list.clear()
        self.case_list.clear()
        self.suite_list.addItem(QListWidgetItem(suite.name))
        for c in suite.cases:
            self.case_list.addItem(QListWidgetItem(c.name))
            # Show static/dynamic intent with signals
            tag_str = ",".join(c.tags)
            self.log_view.append(f"[PLAN] {c.id} ({tag_str}): {c.description}")
        runner = TestRunner(CanInterface(self.can_mgr) if self.can_mgr else None, self.dbc_mgr, logger=self.logger, can_mgr=self.can_mgr, signal_manager=self.signal_manager)
        self.worker = _RunnerWorker(runner, suite)
        self.worker.result_ready.connect(self.on_worker_result)
        self.worker.summary_ready.connect(self.on_worker_summary)
        self.worker.started.connect(self._on_worker_started)
        self.worker.start()

    def on_worker_result(self, text):
        self.log_view.append(text)

    def on_worker_summary(self, summary):
        # summary: dict with counts and coverage lists
        static_pass = summary.get("static_pass", 0)
        static_total = summary.get("static_total", 0)
        dyn_pass = summary.get("dynamic_pass", 0)
        dyn_total = summary.get("dynamic_total", 0)
        static_asserts = summary.get("static_asserts", {})
        dynamic_asserts = summary.get("dynamic_asserts", {})
        last_json = summary.get("json_path", "")
        last_html = summary.get("html_path", "")
        self.lbl_static.setText(f"Static: {static_pass} / {static_total}")
        self.lbl_dynamic.setText(f"Dynamic: {dyn_pass} / {dyn_total}")
        timing = summary.get("timing_stats", {})
        if timing:
            self.lbl_timing.setText(f"Timing: mean {timing.get('mean', 'n/a')} ms, max {timing.get('max', 'n/a')} ms")
        self.static_cov.clear()
        self.dynamic_cov.clear()
        for item in sorted(summary.get("static_coverage", [])):
            self.static_cov.addItem(QListWidgetItem(item))
        for item in sorted(summary.get("dynamic_coverage", [])):
            self.dynamic_cov.addItem(QListWidgetItem(item))
        self.log_view.append(f"[SUMMARY] Static {static_pass}/{static_total}, Dynamic {dyn_pass}/{dyn_total}")
        self.log_view.append(f"[ASSERTIONS] Static passed {static_asserts.get('passed',0)}/{static_asserts.get('total',0)}, Dynamic passed {dynamic_asserts.get('passed',0)}/{dynamic_asserts.get('total',0)}")
        if last_json and last_html:
            self.log_view.append(f"Reports saved: {last_json} , {last_html}")
            if self.logger:
                try:
                    self.logger.info(f"CAN Matrix reports saved JSON={last_json} HTML={last_html}")
                except Exception:
                    pass
        elif last_json:
            self.log_view.append(f"Report saved: {last_json}")
        elif last_html:
            self.log_view.append(f"Report saved: {last_html}")
        # Update UI status strip
        status_text = "Completed: PASS" if summary.get("suite_pass", False) else "Completed: FAIL"
        self._set_running(False, text=status_text, pass_state=summary.get("suite_pass", False))

    def _on_worker_started(self):
        self._set_running(True, text="Test in progress...")
        self.log_view.append("Starting auto DBC run...")

    def _set_running(self, running: bool, text: str = "Idle", pass_state: bool | None = None):
        self.btn_run.setEnabled(not running)
        self.btn_run_auto.setEnabled(not running)
        self.run_status.setText(text)
        if running:
            self.run_status.setStyleSheet("color: #5df0a1;")
            self.run_progress.setVisible(True)
        else:
            self.run_progress.setVisible(False)
            if pass_state is True:
                self.run_status.setStyleSheet("color: #5df0a1;")
            elif pass_state is False:
                self.run_status.setStyleSheet("color: #ff9b9b;")
            else:
                self.run_status.setStyleSheet("color: #9db4d4;")


class _RunnerWorker(QThread):
    result_ready = pyqtSignal(str)
    summary_ready = pyqtSignal(object)
    def __init__(self, runner, suite):
        super().__init__()
        self.runner = runner
        self.suite = suite
    def run(self):
        try:
            suite_start = datetime.datetime.now()
            results = self.runner.run_suite(self.suite)
            suite_end = datetime.datetime.now()
            for res in results:
                msg = f"{res.case_id} passed={res.passed}"
                self.result_ready.emit(msg)
            # Build summary
            static_total = sum(1 for c in self.suite.cases if "static" in c.tags)
            dynamic_total = sum(1 for c in self.suite.cases if "dynamic" in c.tags)
            static_pass = sum(1 for r in results if any(t in ["static"] for t in getattr(self._case_by_id(r.case_id), "tags", [])) and r.passed)
            dynamic_pass = sum(1 for r in results if any(t in ["dynamic"] for t in getattr(self._case_by_id(r.case_id), "tags", [])) and r.passed)
            suite_pass = all(r.passed for r in results) if results else True
            static_cov = set()
            dynamic_cov = set()
            timing_vals = []
            static_asserts = {"passed": 0, "total": 0}
            dynamic_asserts = {"passed": 0, "total": 0}
            for r in results:
                case = self._case_by_id(r.case_id)
                tagset = set(getattr(case, "tags", [])) if case else set()
                for a in r.assertions or []:
                    if "static" in tagset:
                        static_asserts["total"] += 1
                        if a.get("passed"):
                            static_asserts["passed"] += 1
                    if "dynamic" in tagset:
                        dynamic_asserts["total"] += 1
                        if a.get("passed"):
                            dynamic_asserts["passed"] += 1
                    if a.get("passed"):
                        label = a.get("msg") or a.get("target")
                        if "static" in tagset:
                            static_cov.add(label)
                        if "dynamic" in tagset:
                            dynamic_cov.add(label)
                    # track range coverage
                    if a.get("passed") and a.get("op") == "in_range":
                        dynamic_cov.add(f"RANGE:{a.get('target')}")
                    # capture timing stats if present
                    obs = a.get("value")
                    if isinstance(obs, dict) and "mean" in obs and "max" in obs:
                        timing_vals.append(obs)
            summary = {
                "static_pass": static_pass,
                "static_total": static_total,
                "dynamic_pass": dynamic_pass,
                "dynamic_total": dynamic_total,
                "suite_pass": suite_pass,
                "suite_start": suite_start.isoformat(),
                "suite_end": suite_end.isoformat(),
                "suite_duration_s": round((suite_end - suite_start).total_seconds(), 3),
                "static_coverage": list(static_cov),
                "dynamic_coverage": list(dynamic_cov),
                "static_asserts": static_asserts,
                "dynamic_asserts": dynamic_asserts,
            }
            if timing_vals:
                mean_vals = [v.get("mean") for v in timing_vals if v.get("mean") is not None]
                max_vals = [v.get("max") for v in timing_vals if v.get("max") is not None]
                if mean_vals and max_vals:
                    summary["timing_stats"] = {"mean": f"{sum(mean_vals)/len(mean_vals):.1f}", "max": f"{max(max_vals):.1f}"}
            # Persist JSON report
            report = {
                "suite": self.suite.name,
                "overall_pass": suite_pass,
                "summary": summary,
                "results": [_RunnerWorker._clean_result(r) for r in results],
            }
            try:
                os.makedirs("Test Results", exist_ok=True)
                ts_tag = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                json_path = os.path.join("Test Results", f"canmatrix_{ts_tag}.json")
                html_path = os.path.join("Test Results", f"canmatrix_{ts_tag}.html")
                with REPORT_WRITE_LOCK:
                    with open(json_path, "w") as f:
                        json.dump(report, f, indent=2)
                    summary["json_path"] = json_path
                    try:
                        cm_report.render_html_report(report, html_path)
                        summary["html_path"] = html_path
                    except Exception as e:
                        summary["html_path"] = f"HTML render failed: {e}"
            except Exception as e:
                summary["json_path"] = f"JSON render failed: {e}"
            self.summary_ready.emit(summary)
        except Exception as e:
            self.result_ready.emit(f"Run failed: {e}")

    def _case_by_id(self, case_id):
        for c in self.suite.cases:
            if c.id == case_id:
                return c
        return None

    @staticmethod
    def _clean_result(res):
        """
        Produce a JSON/HTML friendly dict from a TestResult.
        """
        def _clean_val(v):
            try:
                import json as _json
                _json.dumps(v)
                return v
            except Exception:
                if isinstance(v, bytes):
                    return v.hex()
                return str(v)

        data = {
            "case_id": res.case_id,
            "passed": res.passed,
            "log": [_clean_val(x) for x in getattr(res, "log", [])],
            "start_ts": getattr(res, "start_ts", None),
            "end_ts": getattr(res, "end_ts", None),
        }
        assertions = []
        for a in getattr(res, "assertions", []) or []:
            clean_a = {k: _clean_val(v) for k, v in a.items()}
            assertions.append(clean_a)
        data["assertions"] = assertions
        return data
