import logging
import os
import json
from pathlib import Path
from datetime import datetime
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QLabel, QHBoxLayout,
    QComboBox, QTextEdit, QMessageBox,
    QLineEdit, QListWidget, QListWidgetItem, QTableWidget,
    QDialog, QDialogButtonBox, QProgressDialog, QCheckBox, QLayout
)
from config_loader import load_profiles, get_profile
import config
from core import updater
from PyQt6.QtCore import QRect, Qt
from ui.resources import create_app_icon
from ui.window_geometry import (
    clamp_rect_to_screen,
    compute_adaptive_rect,
    find_target_screen,
    is_suspicious_saved_rect,
    load_window_settings,
    save_window_settings,
)
from ui.widgets import (
    ConfigHeader,
    ErrorMessageList,
    ErrorSignalForm,
    ErrorTabControls,
    HeaderBar,
    create_main_tabs,
)
# Import extracted modules
from ui.workers import InstrumentInitWorker, UpdateDownloadWorker
from ui.report_generator import generate_sequence_report

class MainWindow(QMainWindow):
    def __init__(self, logger=None, log_path=None):
        super().__init__()
        self.setWindowTitle("AtomX - Instrument Control & CAN Analysis")
        self.setWindowIcon(create_app_icon())
        self.current_version = updater.read_local_version()
        # Load profiles (simulation/dev/hw)
        self.profiles = load_profiles()
        preferred_profiles = ("lab_a", "hw", "sim")
        self.active_profile = next(
            (name for name in preferred_profiles if name in self.profiles),
            next(iter(self.profiles.keys())),
        )
        self.logger = logger
        self.log_path = log_path
        
        # Apply futuristic dark theme
        self.apply_dark_theme()
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        # Header branding
        self.header_bar = HeaderBar(on_check_updates=self.on_check_updates, version_text=f"Version: {self.current_version}")
        self.layout.addWidget(self.header_bar)

        self.tabs, tab_map, tab_indices = create_main_tabs()
        self.layout.addWidget(self.tabs, 1)  # stretch factor so tabs take all available space

        # Initialize Tabs
        self.config_tab = tab_map["config"]
        self.error_tab = tab_map["error"]
        self.tools_tab = tab_map["tools"]
        self.tracex_tab = tab_map["tracex"]
        self.canmatrix_tab = tab_map["canmatrix"]
        self.standards_tab = tab_map["standards"]
        self.knowledge_base_tab = tab_map["knowledge_base"]

        self.tools_tab_index = tab_indices["tools"]
        self.tracex_tab_index = tab_indices["tracex"]
        self.canmatrix_tab_index = tab_indices["canmatrix"]
        self.error_tab_index = tab_indices["error"]
        self.standards_tab_index = tab_indices["standards"]
        self.knowledge_base_tab_index = tab_indices["knowledge_base"]
        self.tabs.currentChanged.connect(self.on_tab_changed)
        # Lazy-load flags must be set before building tabs
        self.tools_built = False
        self.error_built = False
        self.tracex_built = False
        self.canmatrix_built = False
        self.standards_built = False
        self.knowledge_base_built = False
        self.err_state_cache = None
        self.sequence_run_report = None
        self._window_geometry_restored = False
        
        # Placeholder content
        self.setup_config_tab()
        self.setup_tools_tab()
        # Error tab lazy
        # TraceX tab lazy
        # CAN Matrix tab lazy

    def ensure_tracex_tab_built(self):
        """Build TraceX tab UI if not already built."""
        if not self.tracex_built:
            self.setup_tracex_tab()
    
    def ensure_canmatrix_tab_built(self):
        """Build CAN Matrix tab UI if not already built."""
        if not self.canmatrix_built:
            self.setup_canmatrix_tab()

    def ensure_standards_tab_built(self):
        """Build Standards tab UI if not already built."""
        if not self.standards_built:
            self.setup_standards_tab()

    def ensure_knowledge_base_tab_built(self):
        """Build Knowledge Base tab UI if not already built."""
        if not self.knowledge_base_built:
            self.setup_knowledge_base_tab()
    
    def ensure_error_tab_built(self):
        """Build CAN Tx Config tab UI if not already built."""
        if not self.error_built:
            self.setup_error_tab()
    
    def setup_tools_tab(self):
        layout = QVBoxLayout(self.tools_tab)
        from ui.widgets import SystemLogTab
        self.system_log_tab = SystemLogTab(log_path=self.log_path, on_check_health=self.on_check_health)
        layout.addWidget(self.system_log_tab)
        self.tools_built = True

    def on_check_updates(self):
        self.current_version = updater.read_local_version()
        if hasattr(self, "header_bar"):
            self.header_bar.set_version(f"Version: {self.current_version}")
        repo = getattr(config, "UPDATE_GITHUB_REPO", "") or ""
        asset_name = getattr(config, "UPDATE_GITHUB_ASSET", "") or ""
        include_prerelease = bool(getattr(config, "UPDATE_GITHUB_INCLUDE_PRERELEASE", False))

        if not repo:
            QMessageBox.information(
                self,
                "Update Check",
                "GitHub repo is not configured. Set UPDATE_GITHUB_REPO in config.py.",
            )
            return

        result = updater.check_for_update(repo, asset_name, self.current_version, include_prerelease)
        status = result.get("status")
        if status == "error":
            QMessageBox.warning(self, "Update Check", f"Failed to check updates: {result.get('error')}")
            return
        if status == "no_update":
            latest = result.get("latest_version", "n/a")
            QMessageBox.information(
                self,
                "Update Check",
                f"You are up to date.\nCurrent: {self.current_version}\nLatest: {latest}",
            )
            return
        if status == "update_available":
            latest = result.get("latest_version", "n/a")
            manifest = result.get("manifest", {})
            notes = manifest.get("notes", "A newer version is available.")
            if not self._show_update_dialog(latest, notes):
                return
            self._start_update_download(manifest)
            return
        else:
            return

    def _start_update_download(self, manifest):
        self.update_progress_dialog = QProgressDialog("Downloading update...", "Cancel", 0, 100, self)
        self.update_progress_dialog.setWindowTitle("Downloading Update")
        self.update_progress_dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.update_progress_dialog.setMinimumWidth(420)
        self.update_progress_dialog.setAutoClose(False)
        self.update_progress_dialog.setAutoReset(False)
        self.update_progress_dialog.show()

        self.update_worker = UpdateDownloadWorker(manifest)
        self.update_worker.progress.connect(self._on_update_progress)
        self.update_worker.finished.connect(self._on_update_download_finished)
        self.update_progress_dialog.canceled.connect(self.update_worker.cancel)
        self.update_worker.start()

    def _on_update_progress(self, downloaded, total):
        if not hasattr(self, "update_progress_dialog"):
            return
        if total > 0:
            percent = int((downloaded / total) * 100)
            self.update_progress_dialog.setRange(0, 100)
            self.update_progress_dialog.setValue(percent)
            self.update_progress_dialog.setLabelText(
                f"Downloading update... {downloaded / (1024 * 1024):.1f} / {total / (1024 * 1024):.1f} MB"
            )
        else:
            self.update_progress_dialog.setRange(0, 0)
            self.update_progress_dialog.setLabelText(
                f"Downloading update... {downloaded / (1024 * 1024):.1f} MB"
            )

    def _on_update_download_finished(self, dl):
        if hasattr(self, "update_progress_dialog"):
            self.update_progress_dialog.close()
        if dl.get("status") == "cancelled":
            QMessageBox.information(self, "Update Download", "Download cancelled.")
            return
        if dl.get("status") == "downloaded":
            path = dl.get("path")
            reply = QMessageBox.question(
                self,
                "Update Ready",
                f"Downloaded to:\n{path}\n\nInstall now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                result = updater.install_update(path, relaunch=True)
                if result.get("status") == "started":
                    QMessageBox.information(self, "Updating", "Update started. The app will now close.")
                    self.close()
                else:
                    QMessageBox.warning(self, "Update Install", f"Install failed: {result.get('error')}")
            else:
                QMessageBox.information(
                    self,
                    "Update Downloaded",
                    f"Downloaded to:\n{path}\n\nRun it manually to complete the update.",
                )
        else:
            QMessageBox.warning(self, "Update Download", f"Download failed: {dl.get('error')}")

    def _show_update_dialog(self, latest_version, notes_text):
        dialog = QDialog(self)
        dialog.setWindowTitle("Update Available")
        dialog.setModal(True)
        dialog.setSizeGripEnabled(True)
        dialog.setMinimumSize(520, 360)
        dialog.resize(720, 520)

        layout = QVBoxLayout(dialog)
        header = QLabel(
            f"Current version: {self.current_version}\nLatest version: {latest_version}\n\nDownload now?"
        )
        header.setWordWrap(True)
        layout.addWidget(header)

        notes = QTextEdit()
        notes.setReadOnly(True)
        notes.setPlainText(str(notes_text or "Release notes unavailable."))
        layout.addWidget(notes, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Yes | QDialogButtonBox.StandardButton.No
        )
        buttons.button(QDialogButtonBox.StandardButton.Yes).setText("Download")
        buttons.button(QDialogButtonBox.StandardButton.No).setText("Cancel")
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        return dialog.exec() == QDialog.DialogCode.Accepted

    def setup_tracex_tab(self):
        """Initialize the TraceX tab UI."""
        layout = QVBoxLayout(self.tracex_tab)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        try:
            from ui.TraceXTab import TraceXTab
            self.tracex_widget = TraceXTab(
                can_mgr=self.can_mgr,
                dbc_parser=self.dbc_parser,
                logger=self.logger,
            )
            layout.addWidget(self.tracex_widget)
            self.tracex_tab.setMinimumSize(0, 0)
            self.tracex_built = True
        except Exception as e:
            fallback = QLabel(f"TraceX unavailable: {e}")
            layout.addWidget(fallback)
            self.tracex_built = True
    

    def setup_canmatrix_tab(self):
        """Initialize the CAN Matrix tab UI."""
        layout = QVBoxLayout(self.canmatrix_tab)
        try:
            from ui.CANMatrixTab import CANMatrixTab
            self.canmatrix_widget = CANMatrixTab(can_mgr=self.can_mgr, dbc_parser=self.dbc_parser, logger=self.logger)
            layout.addWidget(self.canmatrix_widget)
            self.canmatrix_built = True
        except Exception as e:
            fallback = QLabel(f"CAN Matrix unavailable: {e}")
            layout.addWidget(fallback)
            self.canmatrix_built = True

    def setup_standards_tab(self):
        """Initialize the Standards tab UI to view Charger_Standard JSON."""
        layout = QVBoxLayout(self.standards_tab)
        header = QLabel("Charger Standards")
        header.setStyleSheet("font-size: 18px; font-weight: bold; color: #00ff88;")
        layout.addWidget(header)

        from pathlib import Path
        self.standards_path = Path(getattr(config, "STANDARDS_JSON", "docs/Charger_Standard.json"))
        self.standards_label = QLabel(f"File: {self.standards_path}")
        layout.addWidget(self.standards_label)

        # Filter row (one QLineEdit per column, built after JSON load)
        self.standards_filter_row = QHBoxLayout()
        layout.addLayout(self.standards_filter_row)
        self.standards_filter_edits = []

        self.standards_table = QTableWidget()
        self.standards_table.setColumnCount(0)
        self.standards_table.setRowCount(0)
        layout.addWidget(self.standards_table)

        self.standards_text = QTextEdit()
        self.standards_text.setReadOnly(True)
        self.standards_text.setVisible(False)
        layout.addWidget(self.standards_text)

        try:
            self.load_standards_json()
        except Exception as e:
            self.standards_table.setVisible(False)
            self.standards_text.setVisible(True)
            self.standards_text.setText(f"Failed to load standards: {e}")
        self.standards_built = True

    def _build_standards_filters(self, cols):
        """Create filter line-edits for each column to allow per-column filtering."""
        # Clear existing widgets in filter row
        while self.standards_filter_row.count():
            item = self.standards_filter_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.standards_filter_edits = []
        self.standards_filter_row.addWidget(QLabel("Filters:"))
        for col in cols:
            edit = QLineEdit()
            edit.setPlaceholderText(str(col))
            edit.setClearButtonEnabled(True)
            edit.textChanged.connect(self.apply_standards_filters)
            self.standards_filter_row.addWidget(edit)
            self.standards_filter_edits.append(edit)
        self.standards_filter_row.addStretch()

    def apply_standards_filters(self):
        """Apply substring filters per column on the standards table."""
        filters = [e.text().strip().lower() for e in self.standards_filter_edits]
        rows = self.standards_table.rowCount()
        cols = self.standards_table.columnCount()
        for r in range(rows):
            visible = True
            for c in range(min(cols, len(filters))):
                ftxt = filters[c]
                if not ftxt:
                    continue
                item = self.standards_table.item(r, c)
                cell = (item.text() if item else "").lower()
                if ftxt not in cell:
                    visible = False
                    break
            self.standards_table.setRowHidden(r, not visible)

    def load_standards_json(self):
        """Load Charger_Standard JSON and render in table if possible."""
        path = self.standards_path
        self.standards_label.setText(f"File: {path}")
        if not path.exists():
            self.standards_table.setVisible(False)
            self.standards_text.setVisible(True)
            self.standards_text.setText(f"Standards file not found: {path}")
            return
        import json
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Normalize common structures:
        # - If the JSON is a dict whose values are lists of dicts (e.g., {"ALL": [...]})
        #   take the first non-empty list.
        if isinstance(data, dict):
            list_candidate = None
            for v in data.values():
                if isinstance(v, list) and v:
                    list_candidate = v
                    break
            if list_candidate is not None:
                data = list_candidate

        # If data is a list of dicts, render as doc-style (knowledge base)
        if isinstance(data, list) and data and all(isinstance(item, dict) for item in data):
            self.standards_table.setVisible(False)
            # Clear filters row
            while self.standards_filter_row.count():
                item = self.standards_filter_row.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            self.standards_filter_edits = []
            # Build an HTML knowledge-base style view
            html_parts = ["<h2>Charger Standards</h2>"]
            for idx, row in enumerate(data, start=1):
                title = row.get("Standard") or row.get("Name") or f"Entry {idx}"
                html_parts.append(f"<h3>{title}</h3><ul>")
                for key, val in row.items():
                    if key in ("Standard", "Name"):
                        continue
                    html_parts.append(f"<li><b>{key}:</b> {val}</li>")
                html_parts.append("</ul>")
            html = "\n".join(html_parts)
            self.standards_text.setVisible(True)
            self.standards_text.setHtml(html)
        else:
            # Fallback: pretty print JSON
            self.standards_table.setVisible(False)
            # No filters in text-only mode
            while self.standards_filter_row.count():
                item = self.standards_filter_row.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            self.standards_filter_edits = []
            self.standards_text.setVisible(True)
            self.standards_text.setText(json.dumps(data, indent=2))

    def setup_knowledge_base_tab(self):
        """Initialize the bundled DVP knowledge base tab."""
        layout = QVBoxLayout(self.knowledge_base_tab)
        try:
            from ui.widgets.knowledge_base_tab import KnowledgeBaseTab

            self.knowledge_base_widget = KnowledgeBaseTab(
                logger=self.logger,
            )
            layout.addWidget(self.knowledge_base_widget)
            self.knowledge_base_built = True
        except Exception as e:
            fallback = QLabel(f"Knowledge base unavailable: {e}")
            layout.addWidget(fallback)
            self.knowledge_base_built = True

    def setup_error_tab(self):
        """Setup CAN transmit builder in CAN Tx Config tab."""
        layout = QVBoxLayout(self.error_tab)

        self.err_controls = ErrorTabControls()
        self.err_period_spin = self.err_controls.err_period_spin
        self.btn_err_build = self.err_controls.btn_err_build
        self.btn_err_send = self.err_controls.btn_err_send
        self.btn_err_start = self.err_controls.btn_err_start
        self.btn_err_stop = self.err_controls.btn_err_stop
        self.btn_err_build.clicked.connect(self.on_err_build_form)
        self.btn_err_send.clicked.connect(self.on_err_send_once)
        self.btn_err_start.clicked.connect(self.on_err_start_periodic)
        self.btn_err_stop.clicked.connect(self.on_err_stop_periodic)
        layout.addWidget(self.err_controls)

        # Main split: message list (left) and signal form (right)
        split = QHBoxLayout()

        self.err_msg_panel = ErrorMessageList()
        self.err_msg_list = self.err_msg_panel.list
        self.err_msg_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        # Populate from DBC if available
        try:
            messages = self.dbc_parser.database.messages if self.dbc_parser and self.dbc_parser.database else []
            for m in messages:
                item = QListWidgetItem(m.name)
                item.setData(Qt.ItemDataRole.UserRole, m)
                self.err_msg_list.addItem(item)
        except Exception:
            pass
        self.err_msg_list.setMinimumWidth(220)
        split.addWidget(self.err_msg_panel, 1)

        # Scrollable signal form on the right
        self.err_form_panel = ErrorSignalForm()
        self.err_scroll = self.err_form_panel.err_scroll
        self.err_form_container = self.err_form_panel.err_form_container
        self.err_form_layout = self.err_form_panel.err_form_layout
        split.addWidget(self.err_form_panel, 2)

        layout.addLayout(split)

        self.err_signal_editors = {}
        self.err_timer = None
        # Load persisted state if available
        try:
            self._err_load_state()
        except Exception:
            pass
        self.error_built = True

    # Legacy helper (kept for compatibility, not used in Error tab after rollback)
    def _err_apply_override_and_send(self, msg_name, signals_dict, verify=True):
        try:
            for sig, val in signals_dict.items():
                self.can_mgr.set_signal_override(msg_name, sig, val)
            self.can_mgr.send_message_with_overrides(msg_name, signals_dict)
        except Exception:
            pass
        
    def setup_config_tab(self):
        layout = QVBoxLayout(self.config_tab)
        self.config_header = ConfigHeader(
            self.profiles, self.active_profile, on_profile_change=self.on_profile_change
        )
        self.profile_combo = self.config_header.profile_combo
        layout.addWidget(self.config_header)
        
        from ui.Dashboard import Dashboard
        self.dashboard = Dashboard()
        layout.addWidget(self.dashboard)
        
        # Initialize core components for the active profile
        self.initialize_core_components(self.active_profile)
        
        # Connect Dashboard Signals
        self.dashboard.sig_init_instrument.connect(self.on_init_instrument)
        self.dashboard.sig_connect_can.connect(self.on_connect_can)
        self.dashboard.sig_disconnect_can.connect(self.on_disconnect_can)
        self.dashboard.sig_start_cyclic.connect(self.on_start_cyclic)
        self.dashboard.sig_stop_cyclic.connect(self.on_stop_cyclic)
        self.dashboard.sig_start_trace.connect(self.on_start_trace)
        self.dashboard.sig_run_sequence.connect(self.on_run_sequence)
        self.dashboard.sig_stop_sequence.connect(self.on_stop_sequence)
        self.dashboard.sig_estop.connect(self.on_estop)

    def initialize_core_components(self, profile_name):
        """(Re)initialize managers, sequencer, and DBC based on profile."""
        # Tear down existing components
        try:
            if hasattr(self, 'sequencer') and self.sequencer:
                self.sequencer.stop_sequence()
        except Exception:
            pass
        try:
            if hasattr(self, 'can_mgr') and self.can_mgr:
                self.can_mgr.disconnect()
        except Exception:
            pass
        try:
            if hasattr(self, 'inst_mgr') and self.inst_mgr:
                self.inst_mgr.close_instruments()
        except Exception:
            pass

        profile = get_profile(profile_name, self.profiles)
        self.active_profile = profile_name
        can_cfg = profile.get('can', {})
        simulation_mode = profile.get('simulation_mode', False)
        log_cfg = profile.get('logging', {})
        if self.logger and log_cfg:
            try:
                level = getattr(logging, log_cfg.get('level', 'INFO').upper(), logging.INFO)
                self.logger.setLevel(level)
            except Exception:
                pass

        from core.InstrumentManager import InstrumentManager
        from core.CANManager import CANManager
        from core.Sequencer import Sequencer
        from core.DBCParser import DBCParser
        from core.SignalManager import SignalManager

        self.inst_mgr = InstrumentManager(simulation_mode=simulation_mode, config=profile.get('instruments'))
        self.dbc_parser = DBCParser(dbc_folder="DBC")
        self.signal_manager = SignalManager(self.dbc_parser, config_folder="CAN Configuration")
        self.can_mgr = CANManager(simulation_mode=simulation_mode, dbc_parser=self.dbc_parser, logger=self.logger)
        self.can_mgr.interface = can_cfg.get('interface')
        self.can_mgr.channel = can_cfg.get('channel')
        self.can_mgr.bitrate = can_cfg.get('bitrate')

        # Rebuild sequencer connections for the new managers
        self.sequencer = Sequencer(self.inst_mgr, self.can_mgr, logger=self.logger)
        self.sequencer.step_completed.connect(self.on_step_completed)
        self.sequencer.sequence_finished.connect(self.on_sequence_finished)
        self.sequencer.action_info.connect(self.on_action_info)

        # Load DBC and mappings (auto-detect first .dbc file in DBC folder)
        success, msg = self.dbc_parser.load_dbc_file()
        if success:
            self.dashboard.output_log.append(f"{msg}")
            success, msg = self.signal_manager.load_signal_mapping()
            if success:
                self.dashboard.output_log.append(f"{msg}")
                
                # Setup UI updates with timer (100ms)
                self.dashboard.setup_ui_updates(self.signal_manager, self.can_mgr)
                
                # Add CAN message listener (for logging/debug only, UI updates are now polled)
                self.can_mgr.add_listener(self.on_can_message_received)
            else:
                self.dashboard.output_log.append(f"Mapping load failed: {msg}")
        else:
            self.dashboard.output_log.append(f"DBC load failed: {msg}")

        if hasattr(self, "tracex_widget") and self.tracex_widget:
            try:
                self.tracex_widget.update_context(can_mgr=self.can_mgr, dbc_parser=self.dbc_parser)
            except Exception as e:
                self._log(logging.WARNING, f"TraceX context refresh failed: {e}")

    def on_profile_change(self, profile_name):
        """Handle UI profile change and reinitialize core components."""
        self.initialize_core_components(profile_name)
        self.dashboard.output_log.append(f'Active profile: {profile_name}')
        if hasattr(self, "system_log_tab"):
            self.system_log_tab.set_log_path(self.log_path)
        self._log(logging.INFO, f"Profile changed to {profile_name}")

    def on_init_instrument(self):
        try:
            profile = get_profile(self.active_profile, self.profiles)
            instrument_map = (profile or {}).get("instruments") or getattr(config, "INSTRUMENT_ADDRESSES", {})
            instrument_names = list(instrument_map.keys()) or [
                "Bi-Directional Power Supply",
                "Grid Emulator",
                "Oscilloscope",
                "DC Load",
            ]
            selected = self._prompt_instrument_selection(instrument_names)
            if not selected:
                return

            timeout_s = float(getattr(config, "INSTRUMENT_INIT_TIMEOUT_S", 5.0))
            retries = int(getattr(config, "INSTRUMENT_INIT_RETRIES", 2))

            self._log(logging.INFO, 'Initialize instruments requested')
            self.dashboard.output_log.append(f"Initialize instruments requested: {', '.join(selected)}")
            self.init_progress_dialog = QProgressDialog(
                "Initializing instruments...", "Cancel", 0, len(selected), self
            )
            self.init_progress_dialog.setWindowTitle("Initialize Instruments")
            self.init_progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            self.init_progress_dialog.setValue(0)
            self.init_progress_dialog.canceled.connect(self._cancel_instrument_init)

            self._init_worker = InstrumentInitWorker(
                self.inst_mgr, selected, timeout_s=timeout_s, retries=retries
            )
            self._init_worker.progress.connect(self._on_instrument_init_progress)
            self._init_worker.finished.connect(self._on_instrument_init_finished)
            self._init_worker.start()
        except Exception as e:
            self._log(logging.ERROR, f'Initialize instruments failed with exception: {e}')
            self.dashboard.output_log.append(f'Initialize instruments error: {e}')
            if getattr(self, "init_progress_dialog", None):
                try:
                    self.init_progress_dialog.close()
                except Exception:
                    pass
                self.init_progress_dialog = None

    def _prompt_instrument_selection(self, instrument_names):
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Instruments")
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Choose instruments to initialize:"))

        checkboxes = []
        for name in instrument_names:
            cb = QCheckBox(name)
            cb.setChecked(True)
            layout.addWidget(cb)
            checkboxes.append(cb)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return []
        return [cb.text() for cb in checkboxes if cb.isChecked()]

    def _cancel_instrument_init(self):
        if hasattr(self, "_init_worker") and self._init_worker:
            self._init_worker.cancel()

    def _on_instrument_init_progress(self, name, status, completed):
        dialog = getattr(self, "init_progress_dialog", None)
        if dialog is not None:
            try:
                dialog.setValue(completed)
                dialog.setLabelText(f"{name}: {status}")
            except Exception as e:
                self._log(logging.WARNING, f"Progress dialog update failed: {e}")
        self.dashboard.output_log.append(f"{name}: {status}")

    def _on_instrument_init_finished(self, success, message):
        try:
            if getattr(self, "init_progress_dialog", None):
                self.init_progress_dialog.setValue(self.init_progress_dialog.maximum())
                self.init_progress_dialog.close()
                self.init_progress_dialog = None
        except Exception as e:
            self._log(logging.WARNING, f'Error closing progress dialog: {e}')
            self.init_progress_dialog = None

        try:
            if success:
                self.dashboard.output_log.append('Instruments Initialized')
                self.dashboard.output_log.append(message)
                self._log(logging.INFO, f'Instruments initialized: {message}')
            else:
                self.dashboard.output_log.append('Failed to Initialize Instruments')
                self.dashboard.output_log.append(message)
                self._log(logging.ERROR, f'Initialize instruments failed: {message}')
        except Exception as e:
            self._log(logging.ERROR, f'Error in instrument init finished handler: {e}')

    def on_connect_can(self):
        self._log(logging.INFO, 'Connect CAN requested')
        success, message = self.can_mgr.connect()
        if success:
            self.dashboard.output_log.append('CAN Connected')
            self.dashboard.output_log.append(message)
            self.can_mgr.print_diagnostics()
            self._log(logging.INFO, f'CAN connected: {message}')
        else:
            self.dashboard.output_log.append('Failed to Connect CAN')
            self.dashboard.output_log.append(message)
            self._log(logging.ERROR, f'CAN connect failed: {message}')

    def on_disconnect_can(self):
        self._log(logging.INFO, 'Disconnect CAN requested')
        try:
            self.can_mgr.disconnect()
            self.dashboard.output_log.append('CAN Disconnected')
            self._log(logging.INFO, 'CAN disconnected')
        except Exception as e:
            self.dashboard.output_log.append(f'Error disconnecting CAN: {e}')
            self._log(logging.ERROR, f'CAN disconnect error: {e}')
    
    def on_check_health(self):
        """Run instrument health checks and log the results."""
        try:
            report = self.inst_mgr.health_report()
            if not report:
                self.dashboard.output_log.append("No instruments initialized.")
                return
            for name, status in report.items():
                ok = getattr(status, "ok", False)
                prefix = "[OK]" if ok else "[ERR]"
                self.dashboard.output_log.append(f"{prefix} {name}: {status.message}")
                self._log(logging.INFO if ok else logging.ERROR, f"{name}: {status.message}")
        except Exception as e:
            self.dashboard.output_log.append(f"Health check failed: {e}")
            self._log(logging.ERROR, f"Health check failed: {e}")

    # ------------------ CAN Tx Config tab helpers (CAN TX builder) ------------------
    def _err_state_file(self):
        return Path("error_tab_state.json")

    def _err_save_state(self):
        """Persist selected messages, period, and signal values."""
        selected_items = self.err_msg_list.selectedItems() if hasattr(self, 'err_msg_list') else []
        msg_names = [i.text() for i in selected_items]
        signals = {}
        for key, editor in self.err_signal_editors.items():
            msg_name, sig_name = key
            if msg_name not in msg_names:
                continue
            if isinstance(editor, QComboBox):
                val = editor.currentData()
            elif isinstance(editor, QLineEdit):
                val = editor.text()
            else:
                val = None
            signals.setdefault(msg_name, {})[sig_name] = val
        state = {
            "period_ms": self.err_period_spin.value() if hasattr(self, 'err_period_spin') else 100,
            "messages": msg_names,
            "signals": signals,
        }
        try:
            self._err_state_file().write_text(json.dumps(state, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _err_load_state(self):
        """Load persisted state and apply selections/values."""
        path = self._err_state_file()
        if not path.exists():
            return
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return
        self.err_state_cache = state
        # Apply selection
        msg_names = state.get("messages", [])
        for i in range(self.err_msg_list.count()):
            item = self.err_msg_list.item(i)
            if item.text() in msg_names:
                item.setSelected(True)
        # Apply period
        try:
            self.err_period_spin.setValue(int(state.get("period_ms", 100)))
        except Exception:
            pass
        # Build form and apply values
        self.on_err_build_form(apply_state=True)

    def _err_apply_values(self, state):
        signals = state.get("signals", {}) if state else {}
        for (msg_name, sig_name), editor in self.err_signal_editors.items():
            if msg_name in signals and sig_name in signals[msg_name]:
                val = signals[msg_name][sig_name]
                if isinstance(editor, QComboBox):
                    # try match data
                    for idx in range(editor.count()):
                        if editor.itemData(idx) == val:
                            editor.setCurrentIndex(idx)
                            break
                elif isinstance(editor, QLineEdit):
                    editor.setText("" if val is None else str(val))

    def on_err_build_form(self):
        """Build signal form for selected message."""
        if not self.dbc_parser or not self.dbc_parser.database:
            self.dashboard.output_log.append("No DBC loaded; cannot build message form.")
            return
        selected_items = self.err_msg_list.selectedItems()
        if not selected_items:
            self.dashboard.output_log.append("No message selected.")
            return
        # Clear existing
        while self.err_form_layout.count():
            item = self.err_form_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self.err_signal_editors = {}
        for item in selected_items:
            msg_obj = item.data(Qt.ItemDataRole.UserRole)
            if not msg_obj:
                continue
            # Message header
            self.err_form_layout.addRow(QLabel(f"<b>{msg_obj.name}</b>"), QLabel(""))
            for sig in msg_obj.signals:
                if sig.choices:
                    editor = QComboBox()
                    for val, text in sig.choices.items():
                        editor.addItem(f"{text} ({val})", val)
                else:
                    editor = QLineEdit()
                    editor.setPlaceholderText("Enter value")
                self.err_signal_editors[(msg_obj.name, sig.name)] = editor
                self.err_form_layout.addRow(QLabel(sig.name), editor)
        self.dashboard.output_log.append(f"Loaded signals for {len(selected_items)} messages")
        # Apply persisted values if available
        if self.err_state_cache:
            self._err_apply_values(self.err_state_cache)

    def _err_collect_payload(self):
        selected_items = self.err_msg_list.selectedItems()
        if not selected_items:
            return None, "No message selected"
        payloads = []
        for item in selected_items:
            msg_obj = item.data(Qt.ItemDataRole.UserRole)
            if not msg_obj:
                continue
            values = {}
            for sig in msg_obj.signals:
                editor = self.err_signal_editors.get((msg_obj.name, sig.name))
                if isinstance(editor, QComboBox):
                    values[sig.name] = editor.currentData()
                elif isinstance(editor, QLineEdit):
                    text = editor.text().strip()
                    if text == "":
                        return None, f"Signal {sig.name} missing value"
                    try:
                        if "." in text:
                            values[sig.name] = float(text)
                        else:
                            values[sig.name] = int(text, 0) if text.lower().startswith("0x") else float(text)
                    except Exception:
                        return None, f"Invalid value for {sig.name}"
            try:
                data = msg_obj.encode(values)
                payloads.append((msg_obj, data))
            except Exception as e:
                return None, f"Encode failed for {msg_obj.name}: {e}"
        return payloads, None

    def on_err_send_once(self):
        if not getattr(self.can_mgr, "is_connected", False) or getattr(self.can_mgr, "bus", None) is None:
            msg = "CAN not connected; cannot send."
            self.dashboard.output_log.append(msg)
            self._log(logging.WARNING, msg)
            return
        result, err = self._err_collect_payload()
        if err:
            self.dashboard.output_log.append(err)
            self._log(logging.ERROR, err)
            return
        for msg_obj, data in result:
            try:
                self.can_mgr.send_message(msg_obj.frame_id, list(data), msg_obj.is_extended_frame)
                log_msg = f"Sent {msg_obj.name} ID=0x{msg_obj.frame_id:X} Data={list(data)}"
                self.dashboard.output_log.append(log_msg)
                self._log(logging.INFO, log_msg)
            except Exception as e:
                err_msg = f"Send failed: {e}"
                self.dashboard.output_log.append(err_msg)
                self._log(logging.ERROR, err_msg)
        self._err_save_state()

    def on_err_start_periodic(self):
        """
        Start periodic transmission using CANManager's driver-level cyclic support
        instead of a UI-thread QTimer. This reduces jitter and CPU load.
        """
        # Stop any existing periodic sends from this tab
        self.on_err_stop_periodic()
        if not getattr(self.can_mgr, "is_connected", False) or getattr(self.can_mgr, "bus", None) is None:
            msg = "CAN not connected; cannot start periodic send."
            self.dashboard.output_log.append(msg)
            self._log(logging.WARNING, msg)
            return
        # Build payloads once up-front
        payloads, err = self._err_collect_payload()
        if err:
            self.dashboard.output_log.append(err)
            self._log(logging.ERROR, err)
            return
        period_ms = self.err_period_spin.value()
        self.err_periodic_tasks = []
        started_names = []
        for msg_obj, data in payloads:
            try:
                # Use start_cyclic_message_by_name so it preserves other signals and caches values
                ok = self.can_mgr.start_cyclic_message_by_name(msg_obj.name, {}, period_ms)
                if ok:
                    self.err_periodic_tasks.append(msg_obj.frame_id)
                    started_names.append(msg_obj.name)
                else:
                    self.dashboard.output_log.append(f"Failed to start periodic {msg_obj.name}")
            except Exception as e:
                self.dashboard.output_log.append(f"Periodic send failed for {msg_obj.name}: {e}")
                self._log(logging.ERROR, f"Periodic send failed for {msg_obj.name}: {e}")
        if started_names:
            log_msg = f"Started periodic send: {', '.join(started_names)} every {period_ms} ms"
            self.dashboard.output_log.append(log_msg)
            self._log(logging.INFO, log_msg)
        self._err_save_state()

    def on_err_stop_periodic(self):
        # Stop driver-level cyclic tasks started from the Error/Warnings tab
        if hasattr(self, "err_periodic_tasks") and self.err_periodic_tasks:
            for arb_id in list(self.err_periodic_tasks):
                try:
                    self.can_mgr.stop_cyclic_message(arb_id)
                except Exception:
                    pass
            self.err_periodic_tasks = []
        if hasattr(self, 'err_timer') and self.err_timer:
            self.err_timer.stop()
            self.err_timer = None
        self.dashboard.output_log.append("Stopped periodic send.")
        self._log(logging.INFO, "Stopped periodic send.")

    def on_start_cyclic(self):
        """Start all configured cyclic CAN messages"""
        try:
            self._log(logging.INFO, 'Start Cyclic CAN requested')
            started_messages, failed_messages = self.can_mgr.start_all_cyclic_messages()
            if started_messages:
                joined = ', '.join(started_messages)
                self.dashboard.output_log.append(f'Cyclic CAN Started: {joined}')
                self._log(logging.INFO, f'Cyclic CAN started: {joined}')
            if failed_messages:
                failed = ', '.join(failed_messages)
                self.dashboard.output_log.append(f'Failed to start: {failed}')
                self._log(logging.WARNING, f'Cyclic CAN failed: {failed}')
            if started_messages or failed_messages:
                self.dashboard.output_log.append('Note: Bus errors are normal if no other CAN device is connected')
        except Exception as e:
            self.dashboard.output_log.append(f'Error starting cyclic CAN: {e}')
            self._log(logging.ERROR, f'Cyclic CAN start error: {e}')

    def on_stop_cyclic(self):
        """Stop all configured cyclic CAN messages"""
        try:
            self._log(logging.INFO, 'Stop Cyclic CAN requested')
            success = self.can_mgr.stop_all_cyclic_messages()
            if success:
                self.dashboard.output_log.append('All Cyclic CAN Messages Stopped')
                self._log(logging.INFO, 'Cyclic CAN stopped')
            else:
                self.dashboard.output_log.append('Some cyclic messages may not have stopped')
                self._log(logging.WARNING, 'Cyclic CAN stop returned partial/false')
        except Exception as e:
            self.dashboard.output_log.append(f'Error stopping cyclic CAN: {e}')
            self._log(logging.ERROR, f'Cyclic CAN stop error: {e}')

    def on_start_trace(self):
        """Start/Stop trace file recording in both CSV and TRC formats"""
        from datetime import datetime
        try:
            self._log(logging.INFO, 'Trace toggle requested')
            if not self.can_mgr.logging:
                filename_base = f"trace_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                full_path = self.can_mgr.start_logging(filename_base)
                self.dashboard.output_log.append('Trace Recording Started')
                self.dashboard.output_log.append('  Saved to: Test Results/')
                self.dashboard.output_log.append(f'  Files: {filename_base}.csv, {filename_base}.trc')
                self.dashboard.btn_start_trace.setText('Stop Trace')
                self._log(logging.INFO, f'Trace started: {full_path}')
            else:
                self.can_mgr.stop_logging()
                self.dashboard.output_log.append('Trace Recording Stopped')
                self.dashboard.btn_start_trace.setText('Start Trace')
                self._log(logging.INFO, 'Trace stopped')
        except Exception as e:
            self.dashboard.output_log.append(f'Error with trace recording: {e}')
            self._log(logging.ERROR, f'Trace error: {e}')

    def on_stop_sequence(self):
        try:
            self.sequencer.stop_sequence()
            self.dashboard.output_log.append('Sequence Stopped')
            self._log(logging.INFO, 'Sequence stop requested')
        except Exception as e:
            self.dashboard.output_log.append(f'Error stopping sequence: {e}')
            self._log(logging.ERROR, f'Sequence stop error: {e}')
    
    def on_estop(self):
        """Emergency stop: halt sequence, power down instruments, stop CAN cyclic, log warnings."""
        try:
            self.sequencer.stop_sequence()
            self._log(logging.WARNING, "E-Stop triggered: stopping sequence")
        except Exception:
            pass
        try:
            self.can_mgr.stop_all_cyclic_messages()
        except Exception:
            pass
        try:
            self.inst_mgr.safe_power_down()
        except Exception:
            pass
        try:
            self.dashboard.output_log.append("E-STOP ACTIVATED: sequence halted, instruments powered down, cyclic CAN stopped.")
        except Exception:
            pass
        self._log(logging.WARNING, "E-STOP completed")

    def on_run_sequence(self):
        import os
        steps = self.dashboard.get_sequence_steps()
        if not steps:
            self.dashboard.output_log.append('Sequence is empty!')
            self._log(logging.WARNING, 'Run sequence requested but sequence is empty')
            return
        
        # Preflight checks (warn only; allow user to proceed)
        preflight_warnings = []
        if not getattr(self.can_mgr, "is_connected", False):
            preflight_warnings.append("CAN not connected")
        # Instrument health
        health = self.inst_mgr.health_report() or {}
        for name, status in health.items():
            if not getattr(status, "ok", False):
                preflight_warnings.append(f"{name} not healthy: {status.message}")
        if preflight_warnings:
            msg = "Preflight warnings:\n" + "\n".join(preflight_warnings)
            self.dashboard.output_log.append(msg)
            self._log(logging.WARNING, msg)
            reply = QMessageBox.question(
                self.dashboard,
                "Preflight Warnings",
                msg + "\n\nProceed with sequence?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                self.dashboard.output_log.append('Sequence start canceled after preflight warnings')
                self._log(logging.INFO, 'Sequence start canceled by user after preflight warnings')
                return
            self.dashboard.output_log.append('User acknowledged warnings and chose to proceed')
            self._log(logging.INFO, 'User acknowledged preflight warnings and chose to proceed')
        
        test_name = 'Unsaved Test'
        
        if self.dashboard.is_modified or self.dashboard.loaded_sequence_name is None:
            reply = QMessageBox.question(
                self.dashboard,
                'Save Test Sequence',
                'Do you want to save this test sequence before running?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
            )
            if reply == QMessageBox.StandardButton.Cancel:
                self._log(logging.INFO, 'Run sequence canceled by user')
                return
            if reply == QMessageBox.StandardButton.Yes:
                saved_path = self.dashboard.save_sequence()
                if saved_path:
                    test_name = os.path.basename(saved_path).replace('.json', '')
        else:
            test_name = self.dashboard.loaded_sequence_name
            self.dashboard.output_log.append(f'Running saved sequence: {test_name}')
        
        # Build run report context
        test_meta = getattr(self.dashboard, "sequence_meta", {}) or {}
        self.sequence_run_report = {
            "name": test_name,
            "meta": test_meta,
            "start_time": datetime.now(),
            "steps": []
        }
        for idx, step in enumerate(steps):
            self.sequence_run_report["steps"].append({
                "index": idx + 1,
                "action": step.get("action"),
                "params": step.get("params"),
                "status": "Pending",
                "messages": []
            })

        self._log(logging.INFO, f'Sequence start requested: {test_name}')
        for row in range(self.dashboard.sequence_table.rowCount()):
            self.dashboard.update_step_status(row, 'Pending')
        self.dashboard.set_running_test_name(test_name)
        self.sequencer.set_steps(steps)
        self.sequencer.start_sequence()
        self.dashboard.output_log.append(f'Sequence Started: {test_name}')
        self._log(logging.INFO, f'Sequence started: {test_name}')

    def on_step_completed(self, index, status):
        self.dashboard.output_log.append(f'Step {index + 1}: {status}')
        level = logging.INFO if status == 'Pass' else logging.WARNING if status == 'Running' else logging.ERROR
        self._log(level, f'Step {index + 1} status: {status}')
        self.dashboard.update_step_status(index, status)
        try:
            if self.sequence_run_report and 0 <= index < len(self.sequence_run_report["steps"]):
                self.sequence_run_report["steps"][index]["status"] = status
        except Exception:
            pass

    def on_sequence_finished(self):
        self.dashboard.output_log.append('Sequence Finished')
        self.dashboard.clear_running_test_name()
        self._log(logging.INFO, 'Sequence finished')
        try:
            self._generate_sequence_report()
        except Exception as e:
            self.dashboard.output_log.append(f"Report generation failed: {e}")
            self._log(logging.ERROR, f"Report generation failed: {e}")

    def on_action_info(self, index, message):
        # Append action result/diagnostic message to the Output Diagnosis log
        if message:
            # Structured ramp data (JSON) is tagged to avoid polluting the log text
            if message.startswith("[RAMP_LOG]"):
                try:
                    import json
                    logs = json.loads(message[len("[RAMP_LOG]"):])
                    if self.sequence_run_report and 0 <= index < len(self.sequence_run_report["steps"]):
                        self.sequence_run_report["steps"][index]["ramp_logs"] = logs
                except Exception:
                    pass
                return
            if message.startswith("[LINELOAD_LOG]"):
                try:
                    import json
                    logs = json.loads(message[len("[LINELOAD_LOG]"):])
                    if self.sequence_run_report and 0 <= index < len(self.sequence_run_report["steps"]):
                        self.sequence_run_report["steps"][index]["line_load_logs"] = logs
                except Exception:
                    pass
                return
            if message.startswith("[SHORTCYCLE_LOG]"):
                try:
                    import json
                    logs = json.loads(message[len("[SHORTCYCLE_LOG]"):])
                    if self.sequence_run_report and 0 <= index < len(self.sequence_run_report["steps"]):
                        self.sequence_run_report["steps"][index]["short_cycle_logs"] = logs
                except Exception:
                    pass
                return

            self.dashboard.output_log.append(f'Step {index + 1}: {message}')
            self._log(logging.INFO, f'Step {index + 1} info: {message}')
            # Highlight warnings inline (message text only; does not change Pass/Fail status)
            if "failed" in message.lower() or "error" in message.lower():
                self.dashboard.show_warning(message)
            # Attach tooltip to row with last message for quick hover detail
            try:
                if index < self.dashboard.sequence_table.rowCount():
                    for col in range(self.dashboard.sequence_table.columnCount()):
                        item = self.dashboard.sequence_table.item(index, col)
                        if item:
                            item.setToolTip(message)
            except Exception:
                pass
            try:
                if self.sequence_run_report and 0 <= index < len(self.sequence_run_report["steps"]):
                    self.sequence_run_report["steps"][index]["messages"].append(message)
            except Exception:
                pass

    def _generate_sequence_report(self):
        """Generate an HTML report for the last sequence run.

        Delegates to the external report_generator module.
        """
        if not self.sequence_run_report:
            return

        # Use the extracted report generator module
        def output_callback(msg):
            if hasattr(self, 'dashboard') and hasattr(self.dashboard, 'output_log'):
                self.dashboard.output_log.append(msg)

        generate_sequence_report(
            report_data=self.sequence_run_report,
            output_callback=output_callback,
            logger=self.logger
        )
        # Clear report context
        self.sequence_run_report = None

    def on_can_message_received(self, msg):
        """
        Callback for CAN messages - logging/debug only.
        UI updates are handled by timers polling the cache.
        """
        pass
    
    def on_tab_changed(self, index):
        """Start/stop log auto-refresh depending on active tab."""
        if index == self.tools_tab_index and not self.tools_built:
            self.setup_tools_tab()
        if index == self.tracex_tab_index:
            self.ensure_tracex_tab_built()
        if index == self.canmatrix_tab_index:
            self.ensure_canmatrix_tab_built()
        if index == self.error_tab_index:
            self.ensure_error_tab_built()
        if index == self.standards_tab_index:
            self.ensure_standards_tab_built()
        if index == self.knowledge_base_tab_index:
            self.ensure_knowledge_base_tab_built()
        if index == self.tools_tab_index:
            if hasattr(self, "system_log_tab"):
                self.system_log_tab.start_auto_refresh()
        else:
            if hasattr(self, "system_log_tab"):
                self.system_log_tab.stop_auto_refresh()
    
    def _log(self, level, message):
        """Helper to log application events consistently."""
        if self.logger:
            try:
                self.logger.log(level, message)
            except Exception:
                pass

    def _restore_window_geometry_once(self):
        if self._window_geometry_restored:
            return

        screen = find_target_screen(self)
        if screen:
            available = screen.availableGeometry()
        else:
            own_screen = self.screen()
            available = own_screen.availableGeometry() if own_screen else QRect(0, 0, 1366, 768)
        settings = load_window_settings()

        rect = settings.get("normal_rect")
        if is_suspicious_saved_rect(rect):
            rect = compute_adaptive_rect(available)
        rect = clamp_rect_to_screen(rect, available)
        self.setGeometry(rect)

        # Ensure minimized state does not carry across startup.
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
        if settings.get("maximized", False):
            self.setWindowState(self.windowState() | Qt.WindowState.WindowMaximized)

        self._window_geometry_restored = True

    def _save_window_geometry(self):
        try:
            save_window_settings(self)
        except Exception as e:
            self._log(logging.WARNING, f"Failed to save window geometry: {e}")

    def showEvent(self, event):
        if not self._window_geometry_restored:
            self._restore_window_geometry_once()
        super().showEvent(event)

    def resizeEvent(self, event):
        if self.logger and self.logger.isEnabledFor(logging.DEBUG):
            try:
                new_size = event.size()
                old_size = event.oldSize()
                self.logger.debug(
                    "MainWindow resize: %sx%s (old=%sx%s, maximized=%s)",
                    new_size.width(),
                    new_size.height(),
                    old_size.width(),
                    old_size.height(),
                    self.isMaximized(),
                )
            except Exception:
                pass
        super().resizeEvent(event)
    
    def closeEvent(self, event):
        """Ensure background threads and connections stop on window close."""
        self._save_window_geometry()
        try:
            if hasattr(self, 'sequencer') and self.sequencer:
                self.sequencer.stop_sequence()
        except Exception:
            pass
        try:
            if hasattr(self, 'can_mgr') and self.can_mgr:
                self.can_mgr.disconnect()
        except Exception:
            pass
        try:
            if hasattr(self, 'inst_mgr') and self.inst_mgr:
                self.inst_mgr.close_instruments()
        except Exception:
            pass
        event.accept()
    
    def apply_dark_theme(self):
        """Apply futuristic dark theme to the application"""
        dark_stylesheet = """
            QMainWindow {
                background-color: #0a0e27;
            }
            QTabWidget {
                background-color: #0a0e27;
            }
            QTabBar::tab {
                background-color: #16213e;
                color: #00d4ff;
                padding: 8px 20px;
                border: 1px solid #00d4ff;
                border-bottom: 2px solid #0a0e27;
            }
            QTabBar::tab:selected {
                background-color: #0f3460;
                color: #00ff88;
                border-bottom: 2px solid #00ff88;
            }
            QTabBar::tab:hover {
                background-color: #1a4d7a;
            }
            QWidget {
                background-color: #0a0e27;
                color: #00d4ff;
            }
            QLabel {
                color: #00d4ff;
            }
            QLineEdit, QTextEdit, QPlainTextEdit {
                background-color: #16213e;
                color: #00ff88;
                border: 1px solid #00d4ff;
                border-radius: 4px;
                padding: 4px;
            }
            QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
                border: 2px solid #00ff88;
            }
            QPushButton {
                background-color: #00d4ff;
                color: #000;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #00ff88;
            }
            QPushButton:pressed {
                background-color: #00aa6f;
            }
            QComboBox {
                background-color: #16213e;
                color: #00d4ff;
                border: 1px solid #00d4ff;
                border-radius: 4px;
                padding: 4px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                color: #00d4ff;
            }
            QTableWidget {
                background-color: #0f3460;
                color: #00d4ff;
                border: 1px solid #00d4ff;
                gridline-color: #1a4d7a;
            }
            QTableWidget::item {
                padding: 4px;
            }
            QTableWidget::item:selected {
                background-color: #00d4ff;
                color: #000;
            }
            QHeaderView::section {
                background-color: #16213e;
                color: #00d4ff;
                padding: 4px;
                border: 1px solid #00d4ff;
            }
            QScrollBar:vertical {
                background-color: #0f3460;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #00d4ff;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #00ff88;
            }
            QScrollBar:horizontal {
                background-color: #0f3460;
                height: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:horizontal {
                background-color: #00d4ff;
                border-radius: 6px;
            }
            QScrollBar::handle:horizontal:hover {
                background-color: #00ff88;
            }
            QDialog {
                background-color: #0a0e27;
            }
            QMessageBox QLabel {
                color: #00d4ff;
            }
        """
        self.setStyleSheet(dark_stylesheet)


