import json
import random
import time
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QFileDialog, QTextEdit, QLineEdit
)
from PyQt6.QtCore import QTimer, Qt

try:
    import pyqtgraph as pg  # optional; prefer visual plotting
    from pyqtgraph import DateAxisItem
except Exception:
    pg = None


class SignalPlotTab(QWidget):
    """Realtime signal plotter with optional pyqtgraph backend."""

    def __init__(self, signal_manager=None, dbc_parser=None, can_mgr=None, parent=None):
        super().__init__(parent)
        self.signal_manager = signal_manager
        self.dbc_parser = dbc_parser
        self.can_mgr = can_mgr
        self.timer = QTimer()
        self.timer.setInterval(200)  # 5 Hz default
        self.timer.timeout.connect(self.on_tick)
        self.replay_timer = QTimer()
        self.replay_timer.timeout.connect(self.on_replay_tick)
        self.replay_data = []
        self.replay_index = 0

        self.traces = {}  # name -> list of (t, v)
        self.curves = {}  # name -> PlotDataItem
        self.color_index = 0
        self.max_points = 2000  # trim for performance
        self.start_time = time.time()

        self._setup_ui()
        self._refresh_signal_list()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        controls = QHBoxLayout()

        controls.addWidget(QLabel("Signals:"))
        self.sig_filter = QLineEdit()
        self.sig_filter.setPlaceholderText("Search signals...")
        self.sig_filter.textChanged.connect(self._apply_filter)
        controls.addWidget(self.sig_filter, 1)

        self.sig_list = QListWidget()
        self.sig_list.setSelectionMode(self.sig_list.SelectionMode.MultiSelection)
        controls.addWidget(self.sig_list, 2)

        btns = QVBoxLayout()
        self.btn_start = QPushButton("Start Plot")
        self.btn_stop = QPushButton("Stop Plot")
        self.btn_refresh = QPushButton("Refresh Signals")
        self.btn_save = QPushButton("Save Plot")
        self.btn_load = QPushButton("Load Plot")
        self.btn_replay = QPushButton("Replay")
        self.btn_clear = QPushButton("Clear")
        for b in [self.btn_start, self.btn_stop, self.btn_refresh, self.btn_save, self.btn_load, self.btn_replay, self.btn_clear]:
            btns.addWidget(b)
        btns.addStretch()
        controls.addLayout(btns, 1)
        layout.addLayout(controls)

        if pg:
            pg.setConfigOptions(antialias=True)
            self.plot_widget = pg.PlotWidget(title="Signal Plot", axisItems={"bottom": DateAxisItem()})
            self.plot_widget.setBackground("#0a0e27")
            self.plot_widget.getAxis('left').setPen('w')
            self.plot_widget.getAxis('bottom').setPen('w')
            self.plot_widget.addLegend()
            self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
            self.plot_widget.enableAutoRange(x=True, y=True)
            # Crosshair
            self.vLine = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen((120, 200, 255), style=pg.QtCore.Qt.PenStyle.DashLine))
            self.hLine = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen((120, 200, 255), style=pg.QtCore.Qt.PenStyle.DashLine))
            self.plot_widget.addItem(self.vLine, ignoreBounds=True)
            self.plot_widget.addItem(self.hLine, ignoreBounds=True)
            self.cursor_label = QLabel("Cursor: ")
            self.cursor_label.setStyleSheet("color: #00ff88;")
            layout.addWidget(self.cursor_label)
            self.proxy = pg.SignalProxy(self.plot_widget.scene().sigMouseMoved, rateLimit=20, slot=self.on_mouse_moved)
            layout.addWidget(self.plot_widget, 3)
            self.text_view = None
        else:
            self.plot_widget = None
            self.text_view = QTextEdit()
            self.text_view.setReadOnly(True)
            self.text_view.setText("pyqtgraph not available; install pyqtgraph for visual plotting.")
            layout.addWidget(self.text_view, 3)

        self.btn_start.clicked.connect(self.on_start)
        self.btn_stop.clicked.connect(self.on_stop)
        self.btn_clear.clicked.connect(self.on_clear)
        self.btn_save.clicked.connect(self.on_save)
        self.btn_load.clicked.connect(self.on_load)
        self.btn_replay.clicked.connect(self.on_replay)
        self.btn_refresh.clicked.connect(self._refresh_signal_list)

    def _refresh_signal_list(self):
        current_filter = self.sig_filter.text().strip().lower() if hasattr(self, "sig_filter") else ""
        selected = set(self._selected_signals())
        self.sig_list.clear()
        names = set()
        # Prefer DBC signals if available
        try:
            if self.dbc_parser and self.dbc_parser.database:
                for msg in self.dbc_parser.database.messages:
                    for sig in msg.signals:
                        names.add(sig.name)
        except Exception:
            pass
        # Fallback to CAN manager signal cache keys
        if not names and self.can_mgr and hasattr(self.can_mgr, "signal_cache"):
            names.update(self.can_mgr.signal_cache.keys())

        for name in sorted(names):
            if current_filter and current_filter not in name.lower():
                continue
            item = QListWidgetItem(name)
            self.sig_list.addItem(item)
            if name in selected:
                item.setSelected(True)

    def _selected_signals(self):
        return [i.text() for i in self.sig_list.selectedItems()]

    def _apply_filter(self, text):
        self._refresh_signal_list()

    def on_start(self):
        self.start_time = time.time()
        # Shift existing traces to absolute timestamps if not already
        if self.plot_widget:
            for name, pts in self.traces.items():
                abs_pts = []
                for t, v in pts:
                    abs_pts.append((self.start_time + t, v))
                self.traces[name] = abs_pts
        self.timer.start()

    def on_stop(self):
        self.timer.stop()

    def on_clear(self):
        self.traces.clear()
        self.curves.clear()
        self.color_index = 0
        if self.plot_widget:
            self.plot_widget.clear()
            self.plot_widget.addLegend()
            self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
            self.plot_widget.enableAutoRange(x=True, y=True)
        else:
            self.text_view.clear()

    def on_tick(self):
        now_abs = time.time()
        if self.start_time is None:
            self.start_time = now_abs
        now = now_abs  # absolute timestamp
        selected = self._selected_signals()
        for name in selected:
            val = self._read_signal(name)
            if val is None:
                continue
            self.traces.setdefault(name, []).append((now, val))
            # Trim for performance
            if len(self.traces[name]) > self.max_points:
                self.traces[name] = self.traces[name][-self.max_points:]
            if self.plot_widget:
                pts = self.traces[name]
                xs, ys = zip(*pts)
                if name not in self.curves:
                    pen = pg.mkPen(pg.intColor(self.color_index), width=2) if pg else None
                    self.color_index += 1
                    curve = self.plot_widget.plot(xs, ys, pen=pen, symbol=None, name=name)
                    self.curves[name] = curve
                self.curves[name].setData(xs, ys)
                self.plot_widget.enableAutoRange(y=True)
            else:
                self.text_view.append(f"{now:.2f}s {name} = {val}")

    def _read_signal(self, name):
        # Prefer CAN manager live cache
        if self.can_mgr and hasattr(self.can_mgr, "signal_cache"):
            try:
                cache = self.can_mgr.signal_cache.get(name, {})
                return cache.get("value")
            except Exception:
                pass
        # Fallback to SignalManager cache if present
        if self.signal_manager and hasattr(self.signal_manager, "signal_cache"):
            try:
                cache = self.signal_manager.signal_cache.get(name, {})
                return cache.get("value")
            except Exception:
                pass
        return None

    def on_mouse_moved(self, evt):
        if not self.plot_widget:
            return
        pos = evt[0]  # QPointF
        if self.plot_widget.plotItem.sceneBoundingRect().contains(pos):
            mouse_point = self.plot_widget.plotItem.vb.mapSceneToView(pos)
            x = mouse_point.x()
            y = mouse_point.y()
            self.vLine.setPos(x)
            self.hLine.setPos(y)
            # Show nearest values per curve
            texts = []
            for name, pts in self.traces.items():
                if not pts:
                    continue
                xs, ys = zip(*pts)
                # find nearest index
                idx = min(range(len(xs)), key=lambda i: abs(xs[i] - x))
                texts.append(f"{name}: t={xs[idx]:.2f}s, v={ys[idx]:.3f}")
            self.cursor_label.setText(" | ".join(texts))

    def on_save(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Plot", "plot.json", "JSON Files (*.json)")
        if not path:
            return
        payload = {
            "traces": self.traces,
        }
        try:
            Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            pass

    def on_load(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load Plot", "", "JSON Files (*.json)")
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            self.traces = data.get("traces", {})
            self._redraw_loaded()
        except Exception:
            pass

    def _redraw_loaded(self):
        if self.plot_widget:
            self.plot_widget.clear()
            self.plot_widget.addLegend()
            self.curves.clear()
            self.color_index = 0
            for name, pts in self.traces.items():
                if not pts:
                    continue
                xs, ys = zip(*pts)
                pen = pg.mkPen(pg.intColor(self.color_index), width=2) if pg else None
                self.color_index += 1
                curve = self.plot_widget.plot(xs, ys, pen=pen, symbol=None, name=name)
                self.curves[name] = curve
            self.plot_widget.enableAutoRange(x=True, y=True)
        else:
            self.text_view.clear()
            for name, pts in self.traces.items():
                for t, v in pts:
                    self.text_view.append(f"{t:.2f}s {name} = {v}")

    def on_replay(self):
        if not self.traces:
            return
        all_pts = []
        for name, pts in self.traces.items():
            for t, v in pts:
                all_pts.append((t, name, v))
        all_pts.sort(key=lambda x: x[0])
        self.replay_data = all_pts
        self.replay_index = 0
        self.replay_start = time.time()
        self.replay_timer.setInterval(50)
        self.replay_timer.start()

    def on_replay_tick(self):
        if self.replay_index >= len(self.replay_data):
            self.replay_timer.stop()
            return
        elapsed = time.time() - self.replay_start
        while self.replay_index < len(self.replay_data) and self.replay_data[self.replay_index][0] <= elapsed:
            t, name, v = self.replay_data[self.replay_index]
            if self.plot_widget:
                # append point
                abs_t = self.start_time + t
                self.traces.setdefault(name, []).append((abs_t, v))
                if len(self.traces[name]) > self.max_points:
                    self.traces[name] = self.traces[name][-self.max_points:]
                xs, ys = zip(*self.traces[name])
                if name not in self.curves:
                    pen = pg.mkPen(pg.intColor(self.color_index), width=2) if pg else None
                    self.color_index += 1
                    curve = self.plot_widget.plot(xs, ys, pen=pen, symbol=None, name=name)
                    self.curves[name] = curve
                self.curves[name].setData(xs, ys)
                self.plot_widget.enableAutoRange(y=True)
            else:
                self.text_view.append(f"[replay] {t:.2f}s {name} = {v}")
            self.replay_index += 1
