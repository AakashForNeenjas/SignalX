import sys
import os
import time
from pathlib import Path
import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QTreeWidget, QTreeWidgetItem, QSplitter,
    QLabel, QSlider, QMessageBox, QTreeWidgetItemIterator, QComboBox,
    QLayout,
    QGroupBox
)
from PyQt6.QtCore import QSize, Qt, QThread, pyqtSignal, QTimer
import pyqtgraph as pg
import pyqtgraph.exporters
import json

from core.tracex.trace_parser import TRCParser
from core.tracex.live_can import LiveCANThread

class TraceLoaderThread(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(dict, float)
    error = pyqtSignal(str)

    def __init__(self, trc_path, parser):
        super().__init__()
        self.trc_path = trc_path
        self.parser = parser
        self._is_running = True

    def stop(self):
        self._is_running = False

    def run(self):
        try:
            signal_data = {} # "msg.signal" -> {"times": [], "values": []}
            max_time = 0.0
            
            file_size = os.path.getsize(self.trc_path)
            processed_size = 0
            
            # Localize lookup overhead outside the tight loop for large trace files
            parse_line = self.parser.parse_line
            decode_message = self.parser.decode_message
            is_numeric = (int, float)
            
            # Fast tracking block
            update_threshold = file_size / 50.0  # emit ~50 times total (every 2%)
            next_update = update_threshold

            with open(self.trc_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    if not self._is_running:
                        break
                    
                    processed_size += len(line)
                    if processed_size > next_update:
                        progress = int(processed_size / file_size * 100)
                        self.progress.emit(progress)
                        next_update += update_threshold

                    parsed = parse_line(line)
                    if parsed:
                        time_ms, can_id, data_bytes = parsed
                        decoded = decode_message(can_id, data_bytes)
                        if decoded:
                            msg_name, sig_dict = decoded
                            t = time_ms / 1000.0 # to seconds
                            if t > max_time:
                                max_time = t
                                
                            for sig_name, sig_val in sig_dict.items():
                                if isinstance(sig_val, is_numeric):
                                    path = f"{msg_name}.{sig_name}"
                                    if path not in signal_data:
                                        signal_data[path] = {"times": [], "values": []}
                                    signal_data[path]["times"].append(t)
                                    signal_data[path]["values"].append(float(sig_val))

            if self._is_running:
                # Convert to numpy arrays
                final_data = {}
                for path, data in signal_data.items():
                    if len(data["times"]) > 0:
                        final_data[path] = (np.array(data["times"]), np.array(data["values"]))
                self.finished.emit(final_data, max_time)
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QWidget):
    def __init__(self, project_root=None, can_mgr=None, dbc_parser=None):
        super().__init__()
        self.setWindowTitle("TraceX - CAN Signal Viewer")

        if project_root:
            self.project_root = Path(project_root).resolve()
        elif getattr(sys, "frozen", False):
            self.project_root = Path(sys.executable).resolve().parent
        else:
            self.project_root = Path(__file__).resolve().parents[1]

        self.dbc_dir = self.project_root / "DBC"
        self.trace_dir = self.project_root / "Test Results"
        self.workspace_dir = self.trace_dir / "TraceX_Workspaces"
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.live_channel = "PCAN_USBBUS1"
        self.can_mgr_ref = can_mgr
        self.dbc_parser_ref = dbc_parser

        self.parser = TRCParser()
        self.signal_data = {}
        self.max_time = 0.0
        
        self.current_time = 0.0
        self.is_playing = False
        self.plot_window_size = 10.0 # seconds of data to show at once
        
        self.is_static_mode = False
        self.curves = {}
        self.plots = []
        
        # Cursor parameters
        self.c1_pos = 0.0
        self.c2_pos = 1.0
        self.c1_active = False
        self.c2_active = False
        self.c1_lines = []
        self.c2_lines = []
        
        self.live_thread = None
        self.is_live_recording = False
        
        self.init_ui()
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_live_plot)
        self.last_update_time = time.time()
        
        # Tracking mouse hover on graphs
        self.proxy = pg.SignalProxy(self.graph_layout.scene().sigMouseMoved, rateLimit=60, slot=self.on_mouse_moved)

        self._adopt_can_defaults()
        if not self._import_existing_dbc_context():
            self.auto_load_dbc()

    # Prevent embedded TraceX widget from forcing parent window expansion.
    def minimumSizeHint(self):
        return QSize(0, 0)

    def sizeHint(self):
        return QSize(1200, 800)

    def _adopt_can_defaults(self):
        if not self.can_mgr_ref:
            return

        iface = getattr(self.can_mgr_ref, "interface", None)
        if iface:
            idx = self.combo_interface.findText(str(iface))
            if idx >= 0:
                self.combo_interface.setCurrentIndex(idx)

        bitrate = getattr(self.can_mgr_ref, "bitrate", None)
        if bitrate:
            bitrate_text = str(int(bitrate))
            idx = self.combo_baud.findText(bitrate_text)
            if idx < 0:
                self.combo_baud.addItem(bitrate_text)
                idx = self.combo_baud.findText(bitrate_text)
            if idx >= 0:
                self.combo_baud.setCurrentIndex(idx)

        channel = getattr(self.can_mgr_ref, "channel", None)
        if channel:
            self.live_channel = str(channel)

    def _import_existing_dbc_context(self):
        db = getattr(self.dbc_parser_ref, "database", None) if self.dbc_parser_ref else None
        if not db:
            return False
        try:
            self.parser.db = db
            self.parser._msg_cache = {msg.frame_id: msg for msg in db.messages}
            self.populate_tree()
            self.lbl_status.setText("Loaded DBC from AtomX context")
            return True
        except Exception:
            return False

    def update_context(self, can_mgr=None, dbc_parser=None):
        if can_mgr is not None:
            self.can_mgr_ref = can_mgr
        if dbc_parser is not None:
            self.dbc_parser_ref = dbc_parser
        self._adopt_can_defaults()
        if self._import_existing_dbc_context():
            self.lbl_status.setText("TraceX context updated from AtomX")

    def auto_load_dbc(self):
        search_dirs = [
            self.dbc_dir,
            self.project_root / "_internal" / "DBC",
            self.project_root / "dbc",
        ]

        for directory in search_dirs:
            if not directory.exists():
                continue
            for dbc_file in directory.glob("*.dbc"):
                try:
                    self.parser.load_dbc(str(dbc_file))
                    self.populate_tree()
                    self.lbl_status.setText(f"Auto-loaded DBC: {dbc_file.name}")
                    return
                except Exception as e:
                    print(f"Error auto-loading {dbc_file.name}: {e}")

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)

        # Top Controls Layout
        control_layout = QVBoxLayout()
        control_layout.setSpacing(10)
        
        # Row 1 (Files, Workspace, Live CAN)
        row1 = QHBoxLayout()
        row1.setSpacing(15)
        
        # --- Group 1: Files & Workspace ---
        group_files = QGroupBox("Data & Workspace")
        layout_files = QHBoxLayout()
        
        self.btn_load_dbc = QPushButton("Load DBC")
        self.btn_load_dbc.clicked.connect(self.load_dbc)
        self.btn_load_trc = QPushButton("Load TRC")
        self.btn_load_trc.clicked.connect(self.load_trc)
        
        self.btn_save_ws = QPushButton("Save WS")
        self.btn_save_ws.clicked.connect(self.save_workspace)
        
        self.btn_load_ws = QPushButton("Load WS")
        self.btn_load_ws.clicked.connect(self.load_workspace)
        
        self.btn_toggle_signals = QPushButton("Hide/Show Signals")
        self.btn_toggle_signals.clicked.connect(lambda: self.tree_signals.setVisible(not self.tree_signals.isVisible()))
        
        self.btn_toggle_cursors = QPushButton("Hide/Show Cursors")
        self.btn_toggle_cursors.clicked.connect(lambda: self.tree_cursor.setVisible(not self.tree_cursor.isVisible()))
        
        self.btn_export = QPushButton("Export to PNG")
        self.btn_export.clicked.connect(self.export_png)
        self.btn_export.setStyleSheet("background-color: #28a745;")
        
        self.lbl_status = QLabel("Status: Idle")
        self.lbl_status.setStyleSheet("color: #AAAAAA; padding-left: 10px;")
        
        layout_files.addWidget(self.btn_load_dbc)
        layout_files.addWidget(self.btn_load_trc)
        layout_files.addWidget(self.btn_save_ws)
        layout_files.addWidget(self.btn_load_ws)
        layout_files.addWidget(self.btn_toggle_signals)
        layout_files.addWidget(self.btn_toggle_cursors)
        layout_files.addWidget(self.btn_export)
        layout_files.addWidget(self.lbl_status)
        layout_files.addStretch()
        group_files.setLayout(layout_files)
        row1.addWidget(group_files, stretch=2)
        
        # --- Group 2: Live CAN ---
        group_live = QGroupBox("Live Connection")
        layout_live = QHBoxLayout()
        
        self.lbl_live = QLabel("Interface:")
        self.combo_interface = QComboBox()
        self.combo_interface.addItems(["pcan", "virtual", "peak", "ixxat", "kvaser", "socketcan"])
        
        self.combo_baud = QComboBox()
        self.combo_baud.addItems(["500000", "250000", "1000000", "125000"])
        
        self.btn_start_live = QPushButton("Start Live CAN")
        self.btn_start_live.setStyleSheet("background-color: #8D2663; color: white;")
        self.btn_start_live.clicked.connect(self.start_live_can)
        
        self.btn_stop_live = QPushButton("Stop Live CAN")
        self.btn_stop_live.setStyleSheet("background-color: #444444; color: white;")
        self.btn_stop_live.clicked.connect(self.stop_live_can)
        self.btn_stop_live.setEnabled(False)
        
        layout_live.addWidget(self.lbl_live)
        layout_live.addWidget(self.combo_interface)
        layout_live.addWidget(self.combo_baud)
        layout_live.addWidget(self.btn_start_live)
        layout_live.addWidget(self.btn_stop_live)
        group_live.setLayout(layout_live)
        row1.addWidget(group_live, stretch=1)
        
        # Row 2 (Playback & Cursors)
        row2 = QHBoxLayout()
        row2.setSpacing(15)
        
        # --- Group 3: Playback Controls ---
        group_play = QGroupBox("Trace Playback & Static Plot")
        layout_play = QHBoxLayout()
        
        self.btn_play = QPushButton("Play")
        self.btn_play.clicked.connect(self.play_pause)
        self.btn_stop = QPushButton("Stop")
        self.btn_stop.clicked.connect(self.stop_playback)
        
        self.slider_time = QSlider(Qt.Orientation.Horizontal)
        self.slider_time.setMinimum(0)
        self.slider_time.setMaximum(1000)
        self.slider_time.setMinimumWidth(300)
        self.slider_time.sliderPressed.connect(self.slider_pressed)
        self.slider_time.sliderReleased.connect(self.slider_released)
        self.slider_time.sliderMoved.connect(self.slider_moved)
        
        self.lbl_time = QLabel("0.00 s")
        self.lbl_time.setMinimumWidth(60)
        
        self.btn_plot_static = QPushButton("Plot Selected (Full Trace)")
        self.btn_plot_static.clicked.connect(self.plot_static)
        self.btn_plot_static.setEnabled(False)
        self.btn_plot_static.setStyleSheet("font-weight: bold; background-color: #0066CC;")
        
        layout_play.addWidget(self.btn_play)
        layout_play.addWidget(self.btn_stop)
        layout_play.addWidget(self.slider_time)
        layout_play.addWidget(self.lbl_time)
        layout_play.addStretch()
        layout_play.addWidget(self.btn_plot_static)
        group_play.setLayout(layout_play)
        row2.addWidget(group_play, stretch=2)
        
        # --- Group 4: Cursors ---
        group_cursor = QGroupBox("Measurement Cursors")
        layout_cursor = QHBoxLayout()
        
        self.btn_c1 = QPushButton("Cursor 1")
        self.btn_c1.setCheckable(True)
        self.btn_c1.clicked.connect(self.toggle_c1)
        self.btn_c1.setStyleSheet("QPushButton:checked {background-color: #FFA500; color: black;}")
        
        self.btn_c2 = QPushButton("Cursor 2")
        self.btn_c2.setCheckable(True)
        self.btn_c2.clicked.connect(self.toggle_c2)
        self.btn_c2.setStyleSheet("QPushButton:checked {background-color: #FF1493; color: white;}")
        
        self.lbl_dt = QLabel("Delta T: -- s")
        self.lbl_dt.setStyleSheet("font-weight: bold; padding: 5px; color: #00FFFF;")
        
        layout_cursor.addWidget(self.btn_c1)
        layout_cursor.addWidget(self.btn_c2)
        layout_cursor.addWidget(self.lbl_dt)
        group_cursor.setLayout(layout_cursor)
        row2.addWidget(group_cursor, stretch=1)

        control_layout.addLayout(row1)
        control_layout.addLayout(row2)
        main_layout.addLayout(control_layout)

        # Splitter for Tree and Plot
        splitter = QSplitter(Qt.Orientation.Horizontal)
        # Adding stretch factor of 1 guarantees the plot uses all available vertical space!
        main_layout.addWidget(splitter, 1)

        # Tree Widget for Signals (Left)
        self.tree_signals = QTreeWidget()
        self.tree_signals.setHeaderLabel("DBC Signals")
        self.tree_signals.itemChanged.connect(self.on_signal_toggled)
        splitter.addWidget(self.tree_signals)

        # Plot Widget Container (Center)
        self.graph_layout = pg.GraphicsLayoutWidget()
        splitter.addWidget(self.graph_layout)
        
        # Tree Widget for Cursor Values (Right)
        self.tree_cursor = QTreeWidget()
        self.tree_cursor.setHeaderLabels(["Active Signal", "Cursor 1", "Cursor 2", "Delta Y"])
        splitter.addWidget(self.tree_cursor)

        # Set sizes (left nav, plot center, right cursors)
        splitter.setSizes([200, 1000, 300])
        
        self._setup_live_plot()

    def _setup_live_plot(self):
        """Sets up the single overlaid plot used for Realtime Playback window playback"""
        self.graph_layout.clear()
        self.main_plot = self.graph_layout.addPlot()
        
        # PyQtGraph legends are natively draggable via the setMovable property if attached carefully
        legend = self.main_plot.addLegend(offset=(10, 10))
        if hasattr(legend, 'setMovable'): # Depends on exact pyqtgraph version config, but generally works implicitly
            pass 
        
        self.main_plot.setLabel('bottom', 'Time', units='s')
        self.curves = {}
        self.plots = [self.main_plot]
        self.sync_cursor_items()
        self.update_cursor_values()

    def _ensure_tooltip(self, p):
        if not hasattr(p, 'tooltip_text'):
            p.tooltip_text = pg.TextItem("", anchor=(0, 1))
            p.tooltip_vline = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen('#888888', width=1, style=Qt.PenStyle.DashLine))
            p.addItem(p.tooltip_text, ignoreBounds=True)
            p.addItem(p.tooltip_vline, ignoreBounds=True)

    def _resolve_curve_color(self, curve):
        pen = curve.opts.get('pen')
        if isinstance(pen, str):
            return pen
        if pen is None:
            return "#00d4ff"
        try:
            return pen.color().name()
        except Exception:
            return "#00d4ff"

    @staticmethod
    def _format_choice_code(code):
        try:
            if isinstance(code, float) and code.is_integer():
                return str(int(code))
            return str(code)
        except Exception:
            return str(code)

    @staticmethod
    def _lookup_choice_label(choices, value):
        if not choices:
            return None, None

        candidates = []
        try:
            fval = float(value)
            if not np.isnan(fval):
                candidates.append(fval)
                if fval.is_integer():
                    ival = int(fval)
                    candidates.insert(0, ival)
        except Exception:
            pass

        candidates.append(value)
        for key in candidates:
            if key in choices:
                return choices[key], key
        return None, None

    def _format_value_with_choices(self, value, choices):
        label, code = self._lookup_choice_label(choices, value)
        if label is not None:
            return f"{label} ({self._format_choice_code(code)})"
        try:
            return f"{float(value):.4f}"
        except Exception:
            return str(value)

    def on_mouse_moved(self, evt):
        if not hasattr(self, 'plots') or not self.plots:
            return
            
        pos = evt[0]
        for p in self.plots:
            if p.sceneBoundingRect().contains(pos):
                mousePoint = p.vb.mapSceneToView(pos)
                x = mousePoint.x()
                y = mousePoint.y()
                
                self._ensure_tooltip(p)
                p.tooltip_vline.setPos(x)
                
                # Offset tooltip slightly from cursor
                p.tooltip_text.setPos(x, y)
                
                tooltip_parts = [f"<span style='color: yellow;'>Time: {x:.3f} s</span>"]
                choices_dict = self.parser.get_signal_choices()
                
                for curve in p.listDataItems():
                    if isinstance(curve, pg.PlotDataItem) and curve.name() and "Cursor" not in curve.name():
                        path = curve.name()
                        if path in self.signal_data:
                            times, values = self.signal_data[path]
                            if len(times) > 0:
                                idx = np.searchsorted(times, x)
                                if idx >= len(times): idx = len(times) - 1
                                elif idx > 0 and abs(times[idx-1] - x) < abs(times[idx] - x):
                                    idx = idx - 1
                                val = values[idx]
                                
                                val_str = self._format_value_with_choices(val, None)
                                choices = choices_dict.get(path, None)
                                if choices:
                                    val_str = self._format_value_with_choices(val, choices)
                                
                                color = self._resolve_curve_color(curve)
                                tooltip_parts.append(f"<span style='color: {color};'>{path.split('.')[-1]}: {val_str}</span>")
                                
                p.tooltip_text.setHtml("<br>".join(tooltip_parts))
                p.tooltip_text.setVisible(True)
                p.tooltip_vline.setVisible(True)
            else:
                if hasattr(p, 'tooltip_text'):
                    p.tooltip_text.setVisible(False)
                    p.tooltip_vline.setVisible(False)

    def start_live_can(self):
        if not self.parser.db:
            self.lbl_status.setText("Please load a DBC file first before live connection.")
            return
            
        interface = self.combo_interface.currentText()
        baudrate = int(self.combo_baud.currentText())
        
        self.btn_start_live.setEnabled(False)
        self.btn_stop_live.setEnabled(True)
        self.btn_load_trc.setEnabled(False)
        self.btn_plot_static.setEnabled(False)
        self.btn_play.setEnabled(False)
        
        # Clear existing data and plots
        self.signal_data = {}
        for path in self._get_selected_paths():
            self.signal_data[path] = (np.array([]), np.array([]))

        self.max_time = 0.0
        self.current_time = 0.0
        self._setup_live_plot()
        
        self.is_live_recording = True
        self.timer.start(50) # Start GUI update loop for live plotting exactly like playback
        
        self.live_thread = LiveCANThread(
            self.parser,
            interface=interface,
            channel=self.live_channel,
            bitrate=baudrate,
            trace_dir=str(self.trace_dir),
        )
        self.live_thread.status.connect(self.update_status)
        self.live_thread.error.connect(self.update_status)
        self.live_thread.data_ready.connect(self.on_live_data)
        self.live_thread.start()
        
    def stop_live_can(self):
        if self.live_thread:
            self.live_thread.stop()
            self.live_thread.wait()
            self.live_thread = None
            
        self.timer.stop()
        self.is_live_recording = False
        self.btn_start_live.setEnabled(True)
        self.btn_stop_live.setEnabled(False)
        self.btn_load_trc.setEnabled(True)
        self.btn_plot_static.setEnabled(True)
        self.btn_play.setEnabled(True)
        self.lbl_status.setText("Live CAN Stopped. You can now use playback or static plots.")
        
    def update_status(self, text):
        self.lbl_status.setText(text)
        
    def on_live_data(self, chunk, max_time_sec):
        # Update global bounds
        self.max_time = max_time_sec
        
        # Merge chunk data
        for path, (c_times, c_values) in chunk.items():
            if path not in self.signal_data:
                self.signal_data[path] = (c_times, c_values)
                # Re-sync if this signal was already toggled in the tree 
                # (so it draws instantly when first packet arrives)
                self._ensure_curve(path)
            else:
                o_times, o_values = self.signal_data[path]
                self.signal_data[path] = (np.concatenate([o_times, c_times]), np.concatenate([o_values, c_values]))

        # Auto-advance time
        self.current_time = self.max_time

    def _ensure_curve(self, path):
        # Checks if UI says it should be checked, and ensures a curve exists
        iterator = QTreeWidgetItemIterator(self.tree_signals)
        while iterator.value():
            item = iterator.value()
            if item.checkState(0) == Qt.CheckState.Checked and item.data(0, Qt.ItemDataRole.UserRole) == path:
                if path not in self.curves:
                    colors = ['#FF4C4C', '#32CD32', '#1E90FF', '#FF1493', '#FFD700', '#00FFFF']
                    color = colors[len(self.curves) % len(colors)]
                    curve = self.main_plot.plot(pen=color, name=path)
                    self.curves[path] = curve
            iterator += 1

    def toggle_c1(self, checked):
        self.c1_active = checked
        if checked and not self.c1_lines:
            # Drop it in the center of the current view
            if self.is_static_mode:
                self.c1_pos = self.max_time * 0.25
            else:
                self.c1_pos = max(0, self.current_time - self.plot_window_size / 2)
        self.sync_cursor_items()
        self.update_cursor_values()

    def toggle_c2(self, checked):
        self.c2_active = checked
        if checked and not self.c2_lines:
            if self.is_static_mode:
                self.c2_pos = self.max_time * 0.75
            else:
                self.c2_pos = self.current_time
        self.sync_cursor_items()
        self.update_cursor_values()

    def sync_cursor_items(self):
        # Remove old lines
        for line in self.c1_lines:
            try:
                if line.scene():
                    line.scene().removeItem(line)
            except RuntimeError:
                pass
        for line in self.c2_lines:
            try:
                if line.scene():
                    line.scene().removeItem(line)
            except RuntimeError:
                pass
            
        self.c1_lines = []
        self.c2_lines = []
        
        if not self.plots:
            return
            
        if self.c1_active:
            for p in self.plots:
                line = pg.InfiniteLine(pos=self.c1_pos, angle=90, movable=True, pen=pg.mkPen('#FFA500', width=2, style=Qt.PenStyle.DashLine))
                line.sigPositionChanged.connect(self._on_c1_moved)
                p.addItem(line)
                self.c1_lines.append(line)
                
        if self.c2_active:
            for p in self.plots:
                line = pg.InfiniteLine(pos=self.c2_pos, angle=90, movable=True, pen=pg.mkPen('#FF1493', width=2, style=Qt.PenStyle.DashLine))
                line.sigPositionChanged.connect(self._on_c2_moved)
                p.addItem(line)
                self.c2_lines.append(line)

    def _on_c1_moved(self, line):
        self.c1_pos = line.value()
        for l in self.c1_lines:
            if l != line:
                l.blockSignals(True)
                l.setValue(self.c1_pos)
                l.blockSignals(False)
        self.update_cursor_values()

    def _on_c2_moved(self, line):
        self.c2_pos = line.value()
        for l in self.c2_lines:
            if l != line:
                l.blockSignals(True)
                l.setValue(self.c2_pos)
                l.blockSignals(False)
        self.update_cursor_values()

    def update_cursor_values(self):
        c1_pos = self.c1_pos if self.c1_active else None
        c2_pos = self.c2_pos if self.c2_active else None

        if c1_pos is not None and c2_pos is not None:
            self.lbl_dt.setText(f"Delta T: {abs(c2_pos - c1_pos):.4f} s")
        else:
            self.lbl_dt.setText("Delta T: -- s")

        self.tree_cursor.clear()
        paths = self._get_selected_paths()
        choices_dict = self.parser.get_signal_choices()
        
        for path in paths:
            if path not in self.signal_data:
                continue
            times, values = self.signal_data[path]
            if len(times) == 0:
                continue
                
            c1_val_str = "--"
            c2_val_str = "--"
            dv_str = "--"
            
            c1_val = None
            c2_val = None
            
            choices = choices_dict.get(path, None)

            def get_val_str(val):
                return self._format_value_with_choices(val, choices)

            if c1_pos is not None:
                idx = np.searchsorted(times, c1_pos)
                if idx >= len(times):
                    idx = len(times) - 1
                elif idx > 0 and abs(times[idx-1] - c1_pos) < abs(times[idx] - c1_pos):
                    idx = idx - 1
                c1_val = values[idx]
                c1_val_str = get_val_str(c1_val)
            
            if c2_pos is not None:
                idx = np.searchsorted(times, c2_pos)
                if idx >= len(times):
                    idx = len(times) - 1
                elif idx > 0 and abs(times[idx-1] - c2_pos) < abs(times[idx] - c2_pos):
                    idx = idx - 1
                c2_val = values[idx]
                c2_val_str = get_val_str(c2_val)

            if c1_val is not None and c2_val is not None:
                dv_str = f"{c2_val - c1_val:.4f}"
                
            item = QTreeWidgetItem(self.tree_cursor, [path.split('.')[-1], c1_val_str, c2_val_str, dv_str])

    def load_dbc(self):
        start_dir = str(self.dbc_dir)
        file_path, _ = QFileDialog.getOpenFileName(self, "Open DBC File", start_dir, "CAN Database (*.dbc)")
        if file_path:
            try:
                self.parser.load_dbc(file_path)
                self.populate_tree()
                self.lbl_status.setText(f"Loaded DBC: {os.path.basename(file_path)}")
            except Exception as e:
                self.lbl_status.setText(f"Error loading DBC: {e}")

    def populate_tree(self):
        self.tree_signals.clear()
        tree_data = self.parser.get_signal_tree()
        for msg, signals in sorted(tree_data.items()):
            msg_item = QTreeWidgetItem(self.tree_signals, [msg])
            for sig in sorted(signals):
                sig_item = QTreeWidgetItem(msg_item, [sig])
                sig_item.setFlags(sig_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                sig_item.setCheckState(0, Qt.CheckState.Unchecked)
                sig_item.setData(0, Qt.ItemDataRole.UserRole, f"{msg}.{sig}")

    def load_trc(self):
        if not self.parser.db:
            self.lbl_status.setText("Please load a DBC file first.")
            return

        start_dir = str(self.trace_dir)
        file_path, _ = QFileDialog.getOpenFileName(self, "Open TRC File", start_dir, "Trace Files (*.trc)")
        if file_path:
            self._load_trc_from_path(file_path)

    def _load_trc_from_path(self, file_path):
        self.loaded_trc_path = file_path
        self.lbl_status.setText(f"Loading TRC: {os.path.basename(file_path)}...")
        self.btn_load_trc.setEnabled(False)
        self.btn_plot_static.setEnabled(False)
        
        self.loader = TraceLoaderThread(file_path, self.parser)
        self.loader.progress.connect(lambda p: self.lbl_status.setText(f"Loading TRC... {p}%"))
        self.loader.finished.connect(self.on_trc_loaded)
        self.loader.error.connect(lambda e: self.lbl_status.setText(f"Error: {e}"))
        self.loader.start()

    def on_trc_loaded(self, signal_data, max_time):
        self.signal_data = signal_data
        self.max_time = max_time
        self.lbl_status.setText("TRC File Loaded. Ready to play playback or plot full trace.")
        self.btn_load_trc.setEnabled(True)
        self.btn_plot_static.setEnabled(True)
        self.current_time = 0.0
        self.update_slider_ui()
        
        if hasattr(self, '_ws_to_restore'):
            self._apply_workspace()
            del self._ws_to_restore

    def save_workspace(self):
        ws = {
            "trc_file": getattr(self, "loaded_trc_path", None),
            "signals": self._get_selected_paths(),
            "c1_active": self.c1_active,
            "c1_pos": self.c1_pos,
            "c2_active": self.c2_active,
            "c2_pos": self.c2_pos,
            "static_mode": self.is_static_mode,
            "separate_axes": getattr(self, "_use_separate_axes", False)
        }
        start_dir = str(self.workspace_dir)
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Workspace", start_dir, "JSON Files (*.json)")
        if file_path:
            try:
                with open(file_path, 'w') as f:
                    json.dump(ws, f, indent=4)
                self.lbl_status.setText(f"Workspace saved: {os.path.basename(file_path)}")
            except Exception as e:
                self.lbl_status.setText(f"Error saving workspace: {e}")

    def load_workspace(self):
        start_dir = str(self.workspace_dir)
        file_path, _ = QFileDialog.getOpenFileName(self, "Load Workspace", start_dir, "JSON Files (*.json)")
        if file_path:
            try:
                with open(file_path, 'r') as f:
                    ws = json.load(f)
                
                # Uncheck all tree nodes first
                iterator = QTreeWidgetItemIterator(self.tree_signals)
                while iterator.value():
                    item = iterator.value()
                    if item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                        item.setCheckState(0, Qt.CheckState.Unchecked)
                    iterator += 1
                    
                self._ws_to_restore = ws
                if self.parser.db and ws.get("trc_file") and os.path.exists(ws["trc_file"]):
                    self._load_trc_from_path(ws["trc_file"])
                else:
                    self._apply_workspace()
                    
            except Exception as e:
                self.lbl_status.setText(f"Error loading workspace: {e}")

    def _apply_workspace(self):
        ws = getattr(self, '_ws_to_restore', None)
        if not ws: return
        
        signals = ws.get("signals", [])
        
        # Check previously checked nodes
        iterator = QTreeWidgetItemIterator(self.tree_signals)
        while iterator.value():
            item = iterator.value()
            path = item.data(0, Qt.ItemDataRole.UserRole)
            if path in signals:
                item.setCheckState(0, Qt.CheckState.Checked)
            iterator += 1
            
        self._use_separate_axes = ws.get("separate_axes", False)
        
        if ws.get("static_mode", False):
            self.plot_static(auto=True)
            
        # Restore Cursors
        self.c1_pos = ws.get("c1_pos", 0.0)
        self.c2_pos = ws.get("c2_pos", 1.0)
        
        if ws.get("c1_active", False) != self.c1_active:
            self.btn_c1.setChecked(ws.get("c1_active", False))
            self.toggle_c1(ws.get("c1_active", False))
            
        if ws.get("c2_active", False) != self.c2_active:
            self.btn_c2.setChecked(ws.get("c2_active", False))
            self.toggle_c2(ws.get("c2_active", False))

    def _get_selected_paths(self):
        paths = []
        iterator = QTreeWidgetItemIterator(self.tree_signals)
        while iterator.value():
            item = iterator.value()
            if item.checkState(0) == Qt.CheckState.Checked:
                path = item.data(0, Qt.ItemDataRole.UserRole)
                if path and path in self.signal_data:
                    paths.append(path)
            iterator += 1
        return paths

    def on_signal_toggled(self, item, column):
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if not path:
            return # message node

        # If we are in static "full trace" mode, regenerate the full static plot
        if self.is_static_mode:
            self.plot_static(auto=True)
            self.update_cursor_values()
            return

        if item.checkState(0) == Qt.CheckState.Checked:
            if path in self.signal_data and path not in self.curves:
                colors = ['#FF4C4C', '#32CD32', '#1E90FF', '#FF1493', '#FFD700', '#00FFFF']
                color = colors[len(self.curves) % len(colors)]
                curve = self.main_plot.plot(pen=color, name=path)
                self.curves[path] = curve
        else:
            if path in self.curves:
                self.main_plot.removeItem(self.curves[path])
                del self.curves[path]
                
        # Force a plot update for live
        self.update_live_plot(force=True)
        self.update_cursor_values()

    def plot_static(self, auto=False):
        paths = self._get_selected_paths()
        if not paths:
            if self.is_static_mode:
                self.is_static_mode = False
                self._setup_live_plot()
            return
            
        self.is_static_mode = True
        self.stop_playback()
        
        separate_axes = False
        if not auto and len(paths) > 1:
            reply = QMessageBox.question(
                self, "Y-Axis Mode", 
                "You have multiple signals selected.\n\nDo you want to use different Y-axes (separate subplots) for each signal to better visualize scales independently?\n\n(Yes = Stacked Subplots, No = Overlay on a single shared Y-axis)",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            separate_axes = (reply == QMessageBox.StandardButton.Yes)
            self._use_separate_axes = separate_axes # cache preference for unchecking/checking more signals dynamically
        elif auto:
            separate_axes = getattr(self, '_use_separate_axes', False)

        self.graph_layout.clear()
        self.plots = []
        colors = ['#FF4C4C', '#32CD32', '#1E90FF', '#FF1493', '#FFD700', '#00FFFF', '#FF8C00', '#9932CC', '#00FA9A']
        choices_dict = self.parser.get_signal_choices()
        
        if separate_axes and len(paths) > 1:
            first_p = None
            for i, path in enumerate(paths):
                p = self.graph_layout.addPlot(row=i, col=0)
                if first_p is None:
                    first_p = p
                else:
                    p.setXLink(first_p) # link X axes to zoom all together seamlessly
                p.addLegend(offset=(10, 10))
                
                times, values = self.signal_data[path]
                p.plot(times, values, name=path, pen=pg.mkPen(colors[i % len(colors)], width=1.5))
                p.autoRange() # autoscale
                
                # Apply enum labels to Y-Axis if applicable
                if path in choices_dict:
                    axis = p.getAxis('left')
                    tick_items = []
                    for val, text in choices_dict[path].items():
                        try:
                            tick_items.append((float(val), str(text)))
                        except Exception:
                            continue
                    if tick_items:
                        tick_items.sort(key=lambda t: t[0])
                        axis.setTicks([tick_items])
                
                if i == len(paths) - 1:
                    p.setLabel('bottom', 'Time', units='s')
                self.plots.append(p)
        else:
            p = self.graph_layout.addPlot(row=0, col=0)
            p.addLegend(offset=(10, 10))
            p.setLabel('bottom', 'Time', units='s')
            for i, path in enumerate(paths):
                times, values = self.signal_data[path]
                p.plot(times, values, name=path, pen=pg.mkPen(colors[i % len(colors)], width=1.5))
            p.autoRange() # autoscale
            self.plots.append(p)
            
        self.sync_cursor_items()
        self.update_cursor_values()

    def export_png(self):
        try:
            exporter = pg.exporters.ImageExporter(self.graph_layout.scene())
            exporter.parameters()['width'] = 1920
            start_dir = str(self.workspace_dir)
            file_path, _ = QFileDialog.getSaveFileName(self, "Export Plot as PNG", start_dir, "PNG Image (*.png)")
            if file_path:
                exporter.export(file_path)
                self.lbl_status.setText(f"Exported successfully to: {os.path.basename(file_path)}")
        except Exception as e:
            self.lbl_status.setText(f"Error exporting image: {e}")

    def play_pause(self):
        if self.is_static_mode:
            # Drop out of static mode and return to playback window mode
            self.is_static_mode = False
            self._setup_live_plot()
            # Restore previously selected curves
            for path in self._get_selected_paths():
                colors = ['#FF4C4C', '#32CD32', '#1E90FF', '#FF1493', '#FFD700', '#00FFFF']
                color = colors[len(self.curves) % len(colors)]
                self.curves[path] = self.main_plot.plot(pen=color, name=path)

        if self.is_playing:
            self.is_playing = False
            self.btn_play.setText("Play")
            self.timer.stop()
        else:
            if not self.signal_data:
                return
            if self.current_time >= self.max_time:
                self.current_time = 0.0
            self.is_playing = True
            self.btn_play.setText("Pause")
            self.last_update_time = time.time()
            self.timer.start(50) # 20 fps update

    def stop_playback(self):
        self.is_playing = False
        self.btn_play.setText("Play")
        self.timer.stop()
        self.current_time = 0.0
        self.update_slider_ui()
        if not self.is_static_mode:
            self.update_live_plot(force=True)
            self.update_cursor_values()

    def slider_pressed(self):
        # Pause playback briefly if it was playing
        self.was_playing = self.is_playing
        if self.is_playing:
            self.timer.stop()
            self.is_playing = False

    def slider_released(self):
        if hasattr(self, 'was_playing') and self.was_playing:
            self.is_playing = True
            self.last_update_time = time.time()
            self.timer.start(50)

    def slider_moved(self, value):
        self.current_time = (value / 1000.0) * self.max_time
        self.lbl_time.setText(f"{self.current_time:.2f} s")
        if not self.is_static_mode:
            self.update_live_plot(force=True)

    def update_slider_ui(self):
        if self.max_time > 0:
            val = int((self.current_time / self.max_time) * 1000)
            self.slider_time.blockSignals(True)
            self.slider_time.setValue(val)
            self.slider_time.blockSignals(False)
            self.lbl_time.setText(f"{self.current_time:.2f} s")

    def update_live_plot(self, force=False):
        if self.is_static_mode:
            return

        if (self.is_playing or self.is_live_recording) and not force:
            now = time.time()
            dt = now - self.last_update_time
            self.last_update_time = now
            
            # If standard playback, advance current_time manually
            if self.is_playing:
                self.current_time += dt
                if self.current_time >= self.max_time:
                    self.current_time = self.max_time
                    self.stop_playback()
            
            self.update_slider_ui()

        # Show window [current_time - plot_window_size, current_time]
        t_start = max(0, self.current_time - self.plot_window_size)
        t_end = max(self.current_time, self.plot_window_size)
        
        self.main_plot.setXRange(t_start, t_end, padding=0)

        for path, curve in self.curves.items():
            times, values = self.signal_data.get(path, ([], []))
            if len(times) == 0:
                continue
            # Find indices for the current window
            idx_start = np.searchsorted(times, t_start)
            idx_end = np.searchsorted(times, t_end, side='right')
            
            if idx_start < idx_end:
                curve.setData(times[idx_start:idx_end], values[idx_start:idx_end])
            else:
                curve.setData([], [])
