import logging
import os
from PyQt6.QtWidgets import QMainWindow, QTabWidget, QWidget, QVBoxLayout, QLabel, QHBoxLayout, QComboBox, QPushButton, QTextEdit, QMessageBox
from config_loader import load_profiles, get_profile
from PyQt6.QtCore import QTimer
from ui.resources import create_app_icon

class MainWindow(QMainWindow):
    def __init__(self, logger=None, log_path=None):
        super().__init__()
        self.setWindowTitle("AtomX - Instrument Control & CAN Analysis")
        self.resize(1400, 900)
        self.setWindowIcon(create_app_icon())
        # Load profiles (simulation/dev/hw)
        self.profiles = load_profiles()
        if 'hw' in self.profiles:
            self.active_profile = 'hw'
        elif 'sim' in self.profiles:
            self.active_profile = 'sim'
        else:
            self.active_profile = next(iter(self.profiles.keys()))
        self.logger = logger
        self.log_path = log_path
        
        # Apply futuristic dark theme
        self.apply_dark_theme()
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setContentsMargins(0, 0, 0, 0)
        # Header branding
        header = QLabel("AtomX")
        header.setStyleSheet("font-size: 34px; font-weight: bold; color: #00ff88; padding: 1px;")
        self.layout.addWidget(header)
        
        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)
        
        # Initialize Tabs
        self.config_tab = QWidget()
        self.instrument_tab = QWidget()
        self.data_tab = QWidget()
        self.error_tab = QWidget()
        self.tools_tab = QWidget()
        self.logconv_tab = QWidget()
        
        self.tabs.addTab(self.config_tab, "Configuration")
        self.tabs.addTab(self.instrument_tab, "Instrument")
        self.tabs.addTab(self.data_tab, "Data")
        self.tabs.addTab(self.error_tab, "Error and Warnings")
        self.tabs.addTab(self.tools_tab, "Tools")
        self.tabs.addTab(self.logconv_tab, "Log Converter")
        self.tools_tab_index = self.tabs.indexOf(self.tools_tab)
        self.logconv_tab_index = self.tabs.indexOf(self.logconv_tab)
        self.tabs.currentChanged.connect(self.on_tab_changed)
        # Lazy-load flags must be set before building tabs
        self.tools_built = False
        self.instrument_built = False
        self.data_built = False
        self.logconv_built = False
        
        # Placeholder content
        self.setup_config_tab()
        self.setup_tools_tab()
        # Log Converter tab lazy

    def ensure_data_tab_built(self):
        """Build data tab UI if not already built."""
        if not self.data_built:
            self.setup_data_tab()

    def ensure_instrument_tab_built(self):
        """Build instrument tab UI if not already built."""
        if not self.instrument_built:
            self.setup_instrument_tab()
    
    def ensure_logconv_tab_built(self):
        """Build Log Converter tab UI if not already built."""
        if not self.logconv_built:
            self.setup_logconv_tab()
        
    def setup_instrument_tab(self):
        layout = QVBoxLayout(self.instrument_tab)
        from ui.InstrumentView import InstrumentView
        self.instrument_view = InstrumentView()
        layout.addWidget(self.instrument_view)
        self.instrument_built = True
    
    def setup_tools_tab(self):
        layout = QVBoxLayout(self.tools_tab)
        header = QHBoxLayout()
        self.log_label = QLabel(f"Log file: {self.log_path or os.path.join('logs', 'app.log')}")
        self.btn_refresh_log = QPushButton("Refresh Logs")
        self.btn_health = QPushButton("Check Instrument Health")
        self.btn_health.clicked.connect(self.on_check_health)
        self.btn_refresh_log.clicked.connect(self.load_log_tail)
        header.addWidget(self.log_label)
        header.addStretch()
        header.addWidget(self.btn_health)
        header.addWidget(self.btn_refresh_log)
        layout.addLayout(header)
        
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view)
        # Timer to auto-refresh when tab is active
        self.log_timer = QTimer()
        self.log_timer.setInterval(2000)
        self.log_timer.timeout.connect(self.load_log_tail)
        self.load_log_tail()
        self.tools_built = True

    def setup_logconv_tab(self):
        """Initialize the Log Converter tab UI."""
        layout = QVBoxLayout(self.logconv_tab)
        try:
            from logconv.ui.LogConverterTab import LogConverterTab
            self.logconv_widget = LogConverterTab(logger=self.logger)
            layout.addWidget(self.logconv_widget)
            self.logconv_built = True
        except Exception as e:
            fallback = QLabel(f"Log Converter unavailable: {e}")
            layout.addWidget(fallback)
            self.logconv_built = True
        
    def setup_data_tab(self):
        """Setup the futuristic data dashboard with signal_cache reference"""
        if not hasattr(self, 'data_tab_layout'):
            self.data_tab_layout = QVBoxLayout(self.data_tab)
        else:
            while self.data_tab_layout.count():
                item = self.data_tab_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.setParent(None)
                    widget.deleteLater()
        from ui.DataDashboard import DataDashboard
        # Pass BOTH signal_manager AND can_mgr's signal_cache for real-time updates
        self.data_dashboard = DataDashboard(self.signal_manager, can_mgr=self.can_mgr)
        self.data_tab_layout.addWidget(self.data_dashboard)
        self.data_built = True
        
    def setup_config_tab(self):
        layout = QVBoxLayout(self.config_tab)
        
        # Profile selector
        profile_row = QHBoxLayout()
        profile_label = QLabel("Profile:")
        self.profile_combo = QComboBox()
        for name in self.profiles.keys():
            self.profile_combo.addItem(name)
        self.profile_combo.setCurrentText(self.active_profile)
        self.profile_combo.currentTextChanged.connect(self.on_profile_change)
        profile_row.addWidget(profile_label)
        profile_row.addWidget(self.profile_combo)
        profile_row.addStretch()
        layout.addLayout(profile_row)
        
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

        # Load DBC and mappings
        success, msg = self.dbc_parser.load_dbc_file("RE")
        if success:
            self.dashboard.output_log.append(f"�o\" {msg}")
            success, msg = self.signal_manager.load_signal_mapping()
            if success:
                self.dashboard.output_log.append(f"�o\" {msg}")
                
                # Setup UI updates with timer (100ms)
                self.dashboard.setup_ui_updates(self.signal_manager, self.can_mgr)
                
                # Add CAN message listener (for logging/debug only, UI updates are now polled)
                self.can_mgr.add_listener(self.on_can_message_received)
                
                # Setup Data Dashboard (after signal_manager is ready)
                self.ensure_data_tab_built()
                self.refresh_data_dashboard()
            else:
                self.dashboard.output_log.append(f"�s� {msg}")
        else:
            self.dashboard.output_log.append(f"�s� {msg}")

    def refresh_data_dashboard(self):
        """Recreate the Data dashboard to point at the current CAN manager."""
        self.ensure_data_tab_built()
        if hasattr(self, 'data_dashboard') and self.data_dashboard:
            self.data_dashboard.setParent(None)
            self.data_dashboard.deleteLater()
            self.data_dashboard = None
        self.setup_data_tab()

    def on_profile_change(self, profile_name):
        """Handle UI profile change and reinitialize core components."""
        self.initialize_core_components(profile_name)
        self.dashboard.output_log.append(f'Active profile: {profile_name}')
        self.log_label.setText(f"Log file: {self.log_path or os.path.join('logs', 'app.log')}")
        self._log(logging.INFO, f"Profile changed to {profile_name}")

    def on_init_instrument(self):
        self._log(logging.INFO, 'Initialize instruments requested')
        success, message = self.inst_mgr.initialize_instruments()
        if success:
            self.dashboard.output_log.append('Instruments Initialized')
            self.dashboard.output_log.append(message)
            self._log(logging.INFO, f'Instruments initialized: {message}')
        else:
            self.dashboard.output_log.append('Failed to Initialize Instruments')
            self.dashboard.output_log.append(message)
            self._log(logging.ERROR, f'Initialize instruments failed: {message}')

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
                prefix = "✓" if getattr(status, "ok", False) else "✗"
                self.dashboard.output_log.append(f"{prefix} {name}: {status.message}")
                self._log(logging.INFO if getattr(status, "ok", False) else logging.ERROR, f"{name}: {status.message}")
        except Exception as e:
            self.dashboard.output_log.append(f"Health check failed: {e}")
            self._log(logging.ERROR, f"Health check failed: {e}")

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
        
        self._log(logging.INFO, f'Sequence start requested: {test_name}')
        for row in range(self.dashboard.sequence_table.rowCount()):
            self.dashboard.update_step_status(row, 'Pending')
        self.dashboard.set_running_test_name(test_name)
        self.data_dashboard.set_test_name(test_name)
        self.sequencer.set_steps(steps)
        self.sequencer.start_sequence()
        self.dashboard.output_log.append(f'Sequence Started: {test_name}')
        self._log(logging.INFO, f'Sequence started: {test_name}')

    def on_step_completed(self, index, status):
        self.dashboard.output_log.append(f'Step {index + 1}: {status}')
        level = logging.INFO if status == 'Pass' else logging.WARNING if status == 'Running' else logging.ERROR
        self._log(level, f'Step {index + 1} status: {status}')
        self.dashboard.update_step_status(index, status)

    def on_sequence_finished(self):
        self.dashboard.output_log.append('Sequence Finished')
        self.dashboard.clear_running_test_name()
        self.data_dashboard.set_test_name(None)
        self._log(logging.INFO, 'Sequence finished')

    def on_action_info(self, index, message):
        # Append action result/diagnostic message to the Output Diagnosis log
        if message:
            self.dashboard.output_log.append(f'Step {index + 1}: {message}')
            self._log(logging.INFO, f'Step {index + 1} info: {message}')

    def on_can_message_received(self, msg):
        """
        Callback for CAN messages - logging/debug only.
        UI updates are handled by timers polling the cache.
        """
        pass
    
    def on_tab_changed(self, index):
        """Start/stop log auto-refresh depending on active tab."""
        if index == self.tabs.indexOf(self.instrument_tab):
            self.ensure_instrument_tab_built()
        if index == self.tabs.indexOf(self.data_tab):
            self.ensure_data_tab_built()
        if index == self.tools_tab_index and not self.tools_built:
            self.setup_tools_tab()
        if index == self.logconv_tab_index:
            self.ensure_logconv_tab_built()
        if index == self.tools_tab_index:
            self.load_log_tail()
            self.log_timer.start()
        else:
            if hasattr(self, 'log_timer'):
                self.log_timer.stop()
    
    def load_log_tail(self, max_lines=400):
        """Load the tail of the log file into the log viewer."""
        path = self.log_path or os.path.join("logs", "app.log")
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            tail = "".join(lines[-max_lines:])
            self.log_view.setPlainText(tail)
        except FileNotFoundError:
            self.log_view.setPlainText(f"No log file yet at {path}")
        except Exception as e:
            self.log_view.setPlainText(f"Error reading log: {e}")
    
    def _log(self, level, message):
        """Helper to log application events consistently."""
        if self.logger:
            try:
                self.logger.log(level, message)
            except Exception:
                pass
    
    def closeEvent(self, event):
        """Ensure background threads and connections stop on window close."""
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
