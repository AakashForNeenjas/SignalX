"""Background worker threads for UI operations.

This module contains QThread-based workers for long-running operations
that should not block the main UI thread.
"""

import threading
from typing import Any, Callable, Dict, List, Optional, Tuple

from PyQt6.QtCore import QThread, pyqtSignal

from core import updater


class InstrumentInitWorker(QThread):
    """Worker thread for initializing instruments with timeout and retry support.

    Signals:
        progress(str, str, int): Emitted with (instrument_name, status, completed_count)
        finished(bool, str): Emitted with (success, message) when done
    """

    progress = pyqtSignal(str, str, int)
    finished = pyqtSignal(bool, str)

    def __init__(
        self,
        inst_mgr,
        instruments: List[str],
        timeout_s: float = 5.0,
        retries: int = 2,
        parent=None
    ):
        """Initialize the worker.

        Args:
            inst_mgr: InstrumentManager instance
            instruments: List of instrument names to initialize
            timeout_s: Timeout per instrument in seconds
            retries: Number of retry attempts
            parent: Parent QObject
        """
        super().__init__(parent)
        self.inst_mgr = inst_mgr
        self.instruments = instruments
        self.timeout_s = max(0.5, float(timeout_s))
        self.retries = max(1, int(retries))
        self._cancel = False

    def cancel(self) -> None:
        """Request cancellation of the initialization process."""
        self._cancel = True

    def _run_with_timeout(self, func: Callable[[], Tuple[bool, str]]) -> Tuple[bool, str]:
        """Run a function with timeout.

        Args:
            func: Callable that returns (bool, str) tuple

        Returns:
            Tuple of (success, message)
        """
        result: Dict[str, Any] = {"done": False, "ok": False, "msg": ""}

        def _runner() -> None:
            try:
                ok, msg = func()
            except Exception as e:
                ok = False
                msg = str(e)
            result["done"] = True
            result["ok"] = ok
            result["msg"] = msg

        thread = threading.Thread(target=_runner, daemon=True)
        thread.start()
        thread.join(self.timeout_s)
        if not result["done"]:
            return False, f"Timeout after {self.timeout_s:.1f}s"
        return bool(result["ok"]), str(result["msg"])

    def _init_callable(self, name: str) -> Optional[Callable[[], Tuple[bool, str]]]:
        """Get the initialization callable for an instrument.

        Args:
            name: Instrument name

        Returns:
            Callable or None if instrument not supported
        """
        if name == "Bi-Directional Power Supply":
            return self.inst_mgr.init_ps  # type: ignore[no-any-return]
        if name == "Grid Emulator":
            return self.inst_mgr.init_gs  # type: ignore[no-any-return]
        if name == "Oscilloscope":
            return self.inst_mgr.init_os  # type: ignore[no-any-return]
        if name == "DC Load":
            return self.inst_mgr.init_load  # type: ignore[no-any-return]
        return None

    def run(self) -> None:
        """Execute the instrument initialization sequence."""
        messages = []
        success = True
        completed = 0

        try:
            for name in self.instruments:
                if self._cancel:
                    messages.append("Initialization cancelled by user.")
                    success = False
                    break

                func = self._init_callable(name)
                if func is None:
                    msg = "Unsupported instrument"
                    messages.append(f"{name}: {msg}")
                    try:
                        self.progress.emit(name, msg, completed)
                    except Exception:
                        pass
                    success = False
                    completed += 1
                    continue

                last_msg = ""
                ok = False
                for attempt in range(1, self.retries + 1):
                    if self._cancel:
                        break  # type: ignore[unreachable]
                    status = "Connecting" if attempt == 1 else f"Retry {attempt}/{self.retries}"
                    try:
                        self.progress.emit(name, status, completed)
                    except Exception:
                        pass
                    ok, msg = self._run_with_timeout(func)
                    last_msg = msg
                    if ok:
                        break

                if not ok:
                    success = False
                messages.append(f"{name}: {last_msg}")
                completed += 1
                try:
                    self.progress.emit(name, "OK" if ok else "Failed", completed)
                except Exception:
                    pass

        except Exception as e:
            messages.append(f"Initialization error: {e}")
            success = False

        try:
            self.finished.emit(success, "\n".join(messages))
        except Exception:
            pass


class UpdateDownloadWorker(QThread):
    """Worker thread for downloading application updates.

    Signals:
        progress(int, int): Emitted with (downloaded_bytes, total_bytes)
        finished(dict): Emitted with download result dictionary
    """

    progress = pyqtSignal(int, int)
    finished = pyqtSignal(dict)

    def __init__(self, manifest: Dict, parent=None):
        """Initialize the worker.

        Args:
            manifest: Update manifest dictionary from updater.check_for_update()
            parent: Parent QObject
        """
        super().__init__(parent)
        self.manifest = manifest
        self._cancel = False

    def cancel(self) -> None:
        """Request cancellation of the download."""
        self._cancel = True

    def _progress_cb(self, downloaded: int, total: int) -> bool:
        """Progress callback for updater.

        Args:
            downloaded: Bytes downloaded so far
            total: Total bytes to download

        Returns:
            True to continue, False to cancel
        """
        self.progress.emit(downloaded, total)
        return not self._cancel

    def run(self) -> None:
        """Execute the download."""
        result = updater.download_update(
            self.manifest,
            dest_dir="updates",
            progress_cb=self._progress_cb
        )
        self.finished.emit(result)
