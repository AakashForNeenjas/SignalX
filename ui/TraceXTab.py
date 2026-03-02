from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class TraceXTab(QWidget):
    def __init__(self, can_mgr=None, dbc_parser=None, logger=None, parent=None):
        super().__init__(parent)
        self.logger = logger
        self._tracex_window = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        try:
            from ui.TraceXView import MainWindow as TraceXMainWindow

            project_root = Path(__file__).resolve().parents[1]
            self._tracex_window = TraceXMainWindow(
                project_root=project_root,
                can_mgr=can_mgr,
                dbc_parser=dbc_parser,
            )
            self._tracex_window.setWindowFlags(Qt.WindowType.Widget)
            layout.addWidget(self._tracex_window)
        except Exception as exc:
            self._log_warning(f"TraceX init failed: {exc}")
            layout.addWidget(QLabel(f"TraceX unavailable: {exc}"))

    def update_context(self, can_mgr=None, dbc_parser=None):
        if self._tracex_window and hasattr(self._tracex_window, "update_context"):
            try:
                self._tracex_window.update_context(can_mgr=can_mgr, dbc_parser=dbc_parser)
            except Exception as exc:
                self._log_warning(f"TraceX context update failed: {exc}")

    def _log_warning(self, message: str):
        if self.logger:
            try:
                self.logger.warning(message)
            except Exception:
                pass
