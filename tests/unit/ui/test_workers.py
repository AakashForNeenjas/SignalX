"""Unit tests for UI worker threads."""

import time
import pytest
from unittest.mock import Mock, MagicMock, patch
from PyQt6.QtCore import QThread
from PyQt6.QtWidgets import QApplication

from ui.workers import InstrumentInitWorker, UpdateDownloadWorker


@pytest.mark.unit
class TestInstrumentInitWorker:
    """Test suite for InstrumentInitWorker class."""

    def test_init(self, qt_app):
        """Test worker initialization."""
        mock_inst_mgr = Mock()
        instruments = ["Bi-Directional Power Supply", "Grid Emulator"]

        worker = InstrumentInitWorker(
            inst_mgr=mock_inst_mgr,
            instruments=instruments,
            timeout_s=5.0,
            retries=2
        )

        assert worker.inst_mgr == mock_inst_mgr
        assert worker.instruments == instruments
        assert worker.timeout_s == 5.0
        assert worker.retries == 2
        assert worker._cancel is False

    def test_init_default_values(self, qt_app):
        """Test worker initialization with defaults."""
        mock_inst_mgr = Mock()
        worker = InstrumentInitWorker(mock_inst_mgr, [])

        assert worker.timeout_s == 5.0
        assert worker.retries == 2

    def test_init_timeout_minimum(self, qt_app):
        """Test timeout has minimum value."""
        mock_inst_mgr = Mock()
        worker = InstrumentInitWorker(mock_inst_mgr, [], timeout_s=0.1)

        assert worker.timeout_s == 0.5

    def test_init_retries_minimum(self, qt_app):
        """Test retries has minimum value."""
        mock_inst_mgr = Mock()
        worker = InstrumentInitWorker(mock_inst_mgr, [], retries=0)

        assert worker.retries == 1

    def test_cancel(self, qt_app):
        """Test cancel sets flag."""
        mock_inst_mgr = Mock()
        worker = InstrumentInitWorker(mock_inst_mgr, [])

        worker.cancel()

        assert worker._cancel is True

    def test_run_with_timeout_success(self, qt_app):
        """Test _run_with_timeout with successful function."""
        mock_inst_mgr = Mock()
        worker = InstrumentInitWorker(mock_inst_mgr, [], timeout_s=1.0)

        def fast_func():
            return (True, "Success")

        ok, msg = worker._run_with_timeout(fast_func)

        assert ok is True
        assert msg == "Success"

    def test_run_with_timeout_failure(self, qt_app):
        """Test _run_with_timeout with failing function."""
        mock_inst_mgr = Mock()
        worker = InstrumentInitWorker(mock_inst_mgr, [], timeout_s=1.0)

        def fail_func():
            return (False, "Failed")

        ok, msg = worker._run_with_timeout(fail_func)

        assert ok is False
        assert msg == "Failed"

    def test_run_with_timeout_exception(self, qt_app):
        """Test _run_with_timeout with exception."""
        mock_inst_mgr = Mock()
        worker = InstrumentInitWorker(mock_inst_mgr, [], timeout_s=1.0)

        def except_func():
            raise ValueError("Test error")

        ok, msg = worker._run_with_timeout(except_func)

        assert ok is False
        assert "Test error" in msg

    def test_run_with_timeout_timeout(self, qt_app):
        """Test _run_with_timeout with timeout."""
        mock_inst_mgr = Mock()
        worker = InstrumentInitWorker(mock_inst_mgr, [], timeout_s=0.5)

        def slow_func():
            time.sleep(2.0)
            return (True, "Done")

        ok, msg = worker._run_with_timeout(slow_func)

        assert ok is False
        assert "Timeout" in msg

    def test_init_callable_ps(self, qt_app):
        """Test _init_callable returns correct function for power supply."""
        mock_inst_mgr = Mock()
        mock_inst_mgr.init_ps = Mock()
        worker = InstrumentInitWorker(mock_inst_mgr, [])

        func = worker._init_callable("Bi-Directional Power Supply")

        assert func == mock_inst_mgr.init_ps

    def test_init_callable_gs(self, qt_app):
        """Test _init_callable returns correct function for grid emulator."""
        mock_inst_mgr = Mock()
        mock_inst_mgr.init_gs = Mock()
        worker = InstrumentInitWorker(mock_inst_mgr, [])

        func = worker._init_callable("Grid Emulator")

        assert func == mock_inst_mgr.init_gs

    def test_init_callable_os(self, qt_app):
        """Test _init_callable returns correct function for oscilloscope."""
        mock_inst_mgr = Mock()
        mock_inst_mgr.init_os = Mock()
        worker = InstrumentInitWorker(mock_inst_mgr, [])

        func = worker._init_callable("Oscilloscope")

        assert func == mock_inst_mgr.init_os

    def test_init_callable_load(self, qt_app):
        """Test _init_callable returns correct function for DC load."""
        mock_inst_mgr = Mock()
        mock_inst_mgr.init_load = Mock()
        worker = InstrumentInitWorker(mock_inst_mgr, [])

        func = worker._init_callable("DC Load")

        assert func == mock_inst_mgr.init_load

    def test_init_callable_unsupported(self, qt_app):
        """Test _init_callable returns None for unsupported instrument."""
        mock_inst_mgr = Mock()
        worker = InstrumentInitWorker(mock_inst_mgr, [])

        func = worker._init_callable("Unknown Instrument")

        assert func is None

    def test_run_empty_instruments(self, qt_app):
        """Test run with empty instruments list."""
        mock_inst_mgr = Mock()
        worker = InstrumentInitWorker(mock_inst_mgr, [])

        finished_signals = []

        def on_finished(success, message):
            finished_signals.append((success, message))

        worker.finished.connect(on_finished)
        worker.run()

        assert len(finished_signals) == 1
        assert finished_signals[0][0] is True

    def test_run_success(self, qt_app):
        """Test run with successful initialization."""
        mock_inst_mgr = Mock()
        mock_inst_mgr.init_ps = Mock(return_value=(True, "Connected"))
        worker = InstrumentInitWorker(
            mock_inst_mgr,
            ["Bi-Directional Power Supply"],
            timeout_s=1.0
        )

        finished_signals = []
        progress_signals = []

        def on_finished(success, message):
            finished_signals.append((success, message))

        def on_progress(name, status, count):
            progress_signals.append((name, status, count))

        worker.finished.connect(on_finished)
        worker.progress.connect(on_progress)
        worker.run()

        assert len(finished_signals) == 1
        assert finished_signals[0][0] is True
        assert "Connected" in finished_signals[0][1]

    def test_run_failure(self, qt_app):
        """Test run with failed initialization."""
        mock_inst_mgr = Mock()
        mock_inst_mgr.init_ps = Mock(return_value=(False, "Connection failed"))
        worker = InstrumentInitWorker(
            mock_inst_mgr,
            ["Bi-Directional Power Supply"],
            timeout_s=1.0
        )

        finished_signals = []

        def on_finished(success, message):
            finished_signals.append((success, message))

        worker.finished.connect(on_finished)
        worker.run()

        assert len(finished_signals) == 1
        assert finished_signals[0][0] is False

    def test_run_unsupported_instrument(self, qt_app):
        """Test run with unsupported instrument."""
        mock_inst_mgr = Mock()
        worker = InstrumentInitWorker(
            mock_inst_mgr,
            ["Unknown Instrument"],
            timeout_s=1.0
        )

        finished_signals = []

        def on_finished(success, message):
            finished_signals.append((success, message))

        worker.finished.connect(on_finished)
        worker.run()

        assert len(finished_signals) == 1
        assert finished_signals[0][0] is False
        assert "Unsupported" in finished_signals[0][1]

    def test_run_cancelled(self, qt_app):
        """Test run when cancelled."""
        mock_inst_mgr = Mock()
        mock_inst_mgr.init_ps = Mock(return_value=(True, "Connected"))
        worker = InstrumentInitWorker(
            mock_inst_mgr,
            ["Bi-Directional Power Supply", "Grid Emulator"],
            timeout_s=1.0
        )

        worker._cancel = True

        finished_signals = []

        def on_finished(success, message):
            finished_signals.append((success, message))

        worker.finished.connect(on_finished)
        worker.run()

        assert len(finished_signals) == 1
        assert finished_signals[0][0] is False
        assert "cancelled" in finished_signals[0][1].lower()

    def test_run_with_retries(self, qt_app):
        """Test run with retry on failure then success."""
        mock_inst_mgr = Mock()
        call_count = [0]

        def init_ps_side_effect():
            call_count[0] += 1
            if call_count[0] == 1:
                return (False, "First try failed")
            return (True, "Connected on retry")

        mock_inst_mgr.init_ps = init_ps_side_effect
        worker = InstrumentInitWorker(
            mock_inst_mgr,
            ["Bi-Directional Power Supply"],
            timeout_s=1.0,
            retries=3
        )

        finished_signals = []

        def on_finished(success, message):
            finished_signals.append((success, message))

        worker.finished.connect(on_finished)
        worker.run()

        assert call_count[0] == 2
        assert len(finished_signals) == 1
        assert finished_signals[0][0] is True


@pytest.mark.unit
class TestUpdateDownloadWorker:
    """Test suite for UpdateDownloadWorker class."""

    def test_init(self, qt_app):
        """Test worker initialization."""
        manifest = {"version": "1.0.0", "url": "http://example.com/update.zip"}

        worker = UpdateDownloadWorker(manifest)

        assert worker.manifest == manifest
        assert worker._cancel is False

    def test_cancel(self, qt_app):
        """Test cancel sets flag."""
        worker = UpdateDownloadWorker({})

        worker.cancel()

        assert worker._cancel is True

    def test_progress_callback_returns_true(self, qt_app):
        """Test progress callback returns True when not cancelled."""
        worker = UpdateDownloadWorker({})

        result = worker._progress_cb(1000, 10000)

        assert result is True

    def test_progress_callback_returns_false_when_cancelled(self, qt_app):
        """Test progress callback returns False when cancelled."""
        worker = UpdateDownloadWorker({})
        worker._cancel = True

        result = worker._progress_cb(1000, 10000)

        assert result is False

    def test_progress_callback_emits_signal(self, qt_app):
        """Test progress callback emits progress signal."""
        worker = UpdateDownloadWorker({})
        progress_signals = []

        def on_progress(downloaded, total):
            progress_signals.append((downloaded, total))

        worker.progress.connect(on_progress)
        worker._progress_cb(5000, 10000)

        assert len(progress_signals) == 1
        assert progress_signals[0] == (5000, 10000)

    @patch('core.updater.download_update')
    def test_run_success(self, mock_download, qt_app):
        """Test run with successful download."""
        manifest = {"version": "1.0.0", "url": "http://example.com/update.zip"}
        mock_download.return_value = {"success": True, "path": "/path/to/update"}

        worker = UpdateDownloadWorker(manifest)
        finished_signals = []

        def on_finished(result):
            finished_signals.append(result)

        worker.finished.connect(on_finished)
        worker.run()

        assert len(finished_signals) == 1
        assert finished_signals[0]["success"] is True
        mock_download.assert_called_once_with(
            manifest,
            dest_dir="updates",
            progress_cb=worker._progress_cb
        )

    @patch('core.updater.download_update')
    def test_run_failure(self, mock_download, qt_app):
        """Test run with failed download."""
        manifest = {"version": "1.0.0", "url": "http://example.com/update.zip"}
        mock_download.return_value = {"success": False, "error": "Download failed"}

        worker = UpdateDownloadWorker(manifest)
        finished_signals = []

        def on_finished(result):
            finished_signals.append(result)

        worker.finished.connect(on_finished)
        worker.run()

        assert len(finished_signals) == 1
        assert finished_signals[0]["success"] is False

    def test_worker_is_qthread(self, qt_app):
        """Test that worker inherits from QThread."""
        worker = UpdateDownloadWorker({})
        assert isinstance(worker, QThread)

    def test_instrument_worker_is_qthread(self, qt_app):
        """Test that InstrumentInitWorker inherits from QThread."""
        worker = InstrumentInitWorker(Mock(), [])
        assert isinstance(worker, QThread)
