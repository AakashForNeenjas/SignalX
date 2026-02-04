"""Unit tests for Sequencer."""

import time
import pytest
from unittest.mock import Mock, MagicMock, patch
from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QApplication

from core.Sequencer import Sequencer


@pytest.mark.unit
class TestSequencer:
    """Test suite for Sequencer class."""

    def test_init(self):
        """Test Sequencer initialization."""
        mock_inst_mgr = Mock()
        mock_can_mgr = Mock()
        mock_logger = Mock()

        seq = Sequencer(mock_inst_mgr, mock_can_mgr, mock_logger)

        assert seq.inst_mgr == mock_inst_mgr
        assert seq.can_mgr == mock_can_mgr
        # LoggerMixin provides the logger property now
        assert seq.logger is not None
        # External logger stored for backwards compatibility
        assert seq._external_logger == mock_logger
        assert seq.steps == []
        assert not seq.running
        assert seq.executor is not None

    def test_set_steps(self):
        """Test setting sequence steps."""
        mock_inst_mgr = Mock()
        mock_can_mgr = Mock()

        seq = Sequencer(mock_inst_mgr, mock_can_mgr)

        steps = [
            {"action": "delay", "params": {"duration": 1}},
            {"action": "ps_set_voltage", "params": {"voltage": 12}}
        ]

        seq.set_steps(steps)

        assert seq.steps == steps
        assert len(seq.steps) == 2

    def test_log_with_logger(self):
        """Test _log method uses LoggerMixin logging."""
        seq = Sequencer(Mock(), Mock())

        # _log now routes through LoggerMixin's log methods
        # Access the logger to create _logger attribute
        _ = seq.logger

        # Mock the internal _logger to verify logging calls
        mock_internal_logger = Mock()
        seq._logger = mock_internal_logger

        seq._log(20, "Test message")

        # Level 20 (INFO) should call log_info which calls logger.info
        mock_internal_logger.info.assert_called_once()

    def test_log_without_logger(self):
        """Test _log method without logger."""
        seq = Sequencer(Mock(), Mock(), None)

        # Should not raise exception
        seq._log(20, "Test message")

    def test_log_cmd(self):
        """Test _log_cmd logs command via LoggerMixin."""
        seq = Sequencer(Mock(), Mock())

        # Access the logger to create _logger attribute
        _ = seq.logger

        # Mock the internal _logger to verify logging calls
        mock_internal_logger = Mock()
        seq._logger = mock_internal_logger

        seq._log_cmd("Test command")

        # Should log via info level
        mock_internal_logger.info.assert_called_once()
        call_args = mock_internal_logger.info.call_args[0][0]
        assert "Test command" in call_args

    def test_start_sequence_when_not_running(self):
        """Test starting sequence when not running."""
        seq = Sequencer(Mock(), Mock())
        seq.set_steps([{"action": "delay", "params": {"duration": 0.1}}])

        seq.start_sequence()

        assert seq.running is True
        assert seq.sequence_thread is not None
        assert seq.sequence_thread.is_alive()

        # Clean up
        seq.stop_sequence()
        time.sleep(0.2)

    def test_start_sequence_when_already_running(self):
        """Test starting sequence when already running."""
        seq = Sequencer(Mock(), Mock())
        seq.running = True

        seq.start_sequence()

        # Thread should not be created
        assert seq.sequence_thread is None

    def test_stop_sequence(self):
        """Test stopping sequence."""
        seq = Sequencer(Mock(), Mock())
        seq.set_steps([{"action": "delay", "params": {"duration": 1.0}}])

        seq.start_sequence()
        time.sleep(0.1)  # Let it start
        seq.stop_sequence()

        assert not seq.running
        assert seq.stop_event.is_set()

        time.sleep(0.2)  # Let thread finish

    def test_run_sequence_success(self, qt_app):
        """Test running sequence with successful actions."""
        seq = Sequencer(Mock(), Mock())

        # Mock the executor to return success
        seq.executor.execute = Mock(return_value=(True, "Success"))

        steps = [
            {"action": "delay", "params": {"duration": 0.01}},
            {"action": "ps_set_voltage", "params": {"voltage": 12}}
        ]
        seq.set_steps(steps)

        # Track signal emissions
        step_completed_calls = []
        action_info_calls = []
        finished = [False]

        def on_step_completed(index, status):
            step_completed_calls.append((index, status))

        def on_action_info(index, message):
            action_info_calls.append((index, message))

        def on_finished():
            finished[0] = True

        seq.step_completed.connect(on_step_completed)
        seq.action_info.connect(on_action_info)
        seq.sequence_finished.connect(on_finished)

        seq.start_sequence()

        # Wait for sequence to finish (with timeout)
        max_wait = 2.0
        elapsed = 0.0
        while not finished[0] and elapsed < max_wait:
            QApplication.processEvents()
            time.sleep(0.05)
            elapsed += 0.05

        # Should have executed 2 actions
        assert seq.executor.execute.call_count == 2
        assert len(step_completed_calls) >= 2
        assert finished[0] is True

        # Clean up
        seq.stop_sequence()
        time.sleep(0.1)

    def test_run_sequence_with_failure(self, qt_app):
        """Test running sequence with failed action."""
        seq = Sequencer(Mock(), Mock())

        # Mock the executor to return failure
        seq.executor.execute = Mock(return_value=(False, "Action failed"))

        steps = [
            {"action": "ps_set_voltage", "params": {"voltage": 12}},
            {"action": "delay", "params": {"duration": 0.01}}
        ]
        seq.set_steps(steps)

        step_completed_calls = []
        finished = [False]

        def on_step_completed(index, status):
            step_completed_calls.append((index, status))

        def on_finished():
            finished[0] = True

        seq.step_completed.connect(on_step_completed)
        seq.sequence_finished.connect(on_finished)

        seq.start_sequence()

        # Wait for sequence to finish (with timeout)
        max_wait = 2.0
        elapsed = 0.0
        while not finished[0] and elapsed < max_wait:
            QApplication.processEvents()
            time.sleep(0.05)
            elapsed += 0.05

        # Should have tried first action and failed
        assert seq.executor.execute.call_count >= 1
        assert len(step_completed_calls) > 0
        assert any("Fail" in status for _, status in step_completed_calls)

        # Clean up
        seq.stop_sequence()
        time.sleep(0.1)

    def test_run_sequence_abort(self):
        """Test aborting sequence mid-execution."""
        seq = Sequencer(Mock(), Mock())
        steps = [
            {"action": "delay", "params": {"duration": 0.1}},
            {"action": "delay", "params": {"duration": 0.1}},
            {"action": "delay", "params": {"duration": 0.1}},
        ]
        seq.set_steps(steps)

        step_completed_calls = []

        def on_step_completed(index, status):
            step_completed_calls.append((index, status))

        seq.step_completed.connect(on_step_completed)

        seq.start_sequence()
        time.sleep(0.15)  # Let first action complete
        seq.stop_sequence()
        time.sleep(0.3)

        # Should not have completed all 3 actions
        assert len(step_completed_calls) < 6  # (Running + Pass) * 3

    def test_execute_action_invalid_result(self):
        """Test handling invalid action result."""
        seq = Sequencer(Mock(), Mock())

        # Mock executor to return invalid result
        seq.executor.execute = Mock(return_value="invalid")

        result = seq._execute_action("test_action", {}, 0)

        # _execute_action just returns what executor.execute returns
        # The run_sequence method handles validation
        assert result == "invalid"

    @patch('core.Sequencer.ActionExecutor')
    def test_executor_initialization(self, mock_executor_class):
        """Test that ActionExecutor is initialized."""
        mock_executor = Mock()
        mock_executor_class.return_value = mock_executor

        seq = Sequencer(Mock(), Mock())

        # Executor should be set (though we mocked the class)
        assert hasattr(seq, 'executor')

    def test_sequence_signals_exist(self):
        """Test that required signals exist."""
        seq = Sequencer(Mock(), Mock())

        assert hasattr(seq, 'step_completed')
        assert hasattr(seq, 'action_info')
        assert hasattr(seq, 'sequence_finished')

    def test_sequence_empty_steps(self, qt_app):
        """Test running sequence with no steps."""
        seq = Sequencer(Mock(), Mock())
        seq.set_steps([])

        finished_called = [False]

        def on_finished():
            finished_called[0] = True

        seq.sequence_finished.connect(on_finished)

        seq.start_sequence()

        # Wait for sequence to finish (with timeout)
        max_wait = 2.0
        elapsed = 0.0
        while not finished_called[0] and elapsed < max_wait:
            QApplication.processEvents()
            time.sleep(0.05)
            elapsed += 0.05

        assert finished_called[0] is True

        # Clean up
        seq.stop_sequence()
        time.sleep(0.1)

    def test_multiple_sequences_sequential(self):
        """Test running multiple sequences sequentially."""
        seq = Sequencer(Mock(), Mock())

        # First sequence
        seq.set_steps([{"action": "delay", "params": {"duration": 0.1}}])
        seq.start_sequence()
        time.sleep(0.3)
        seq.stop_sequence()

        # Second sequence
        seq.set_steps([{"action": "delay", "params": {"duration": 0.1}}])
        seq.start_sequence()
        time.sleep(0.3)
        seq.stop_sequence()

        # Should complete without errors

    def test_thread_daemon_mode(self):
        """Test that sequence thread is daemon."""
        seq = Sequencer(Mock(), Mock())
        seq.set_steps([{"action": "delay", "params": {"duration": 0.5}}])

        seq.start_sequence()

        assert seq.sequence_thread.daemon is True

        seq.stop_sequence()
        time.sleep(0.1)
