"""Unit tests for logging utilities."""

import logging
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os

from core.logging_utils import (
    configure_logging,
    get_logger,
    get_module_logger,
    LoggerMixin,
    ContextLogger,
    AtomXFormatter,
    log_function_call,
    log_execution_time,
    ensure_logging_configured,
    LOG_LEVELS,
    DEFAULT_LOG_FORMAT,
)


@pytest.mark.unit
class TestConfigureLogging:
    """Test suite for configure_logging function."""

    def teardown_method(self):
        """Clean up logging after each test."""
        # Remove all handlers from root logger
        root = logging.getLogger()
        for handler in root.handlers[:]:
            root.removeHandler(handler)
            handler.close()

    def test_configure_logging_default(self, tmp_path):
        """Test default logging configuration."""
        logger = configure_logging(log_dir=str(tmp_path))

        assert logger is not None
        assert logger.level == logging.INFO

    def test_configure_logging_debug_level(self, tmp_path):
        """Test configuring debug log level."""
        logger = configure_logging(level="DEBUG", log_dir=str(tmp_path))

        assert logger.level == logging.DEBUG

    def test_configure_logging_creates_log_dir(self, tmp_path):
        """Test that log directory is created."""
        log_dir = tmp_path / "new_logs"
        configure_logging(log_dir=str(log_dir))

        assert log_dir.exists()

    def test_configure_logging_creates_log_file(self, tmp_path):
        """Test that log file is created."""
        configure_logging(log_file="test.log", log_dir=str(tmp_path))

        log_file = tmp_path / "test.log"
        # File created when first message logged
        logger = logging.getLogger()
        logger.info("Test message")

        assert log_file.exists()

    def test_configure_logging_with_console(self, tmp_path):
        """Test configuration with console output."""
        logger = configure_logging(
            console_output=True,
            log_dir=str(tmp_path)
        )

        # Should have both file and console handlers
        handler_types = [type(h).__name__ for h in logger.handlers]
        assert "RotatingFileHandler" in handler_types
        assert "StreamHandler" in handler_types

    def test_configure_logging_without_console(self, tmp_path):
        """Test configuration without console output."""
        logger = configure_logging(
            console_output=False,
            log_dir=str(tmp_path)
        )

        # Should only have file handler
        handler_types = [type(h).__name__ for h in logger.handlers]
        assert "RotatingFileHandler" in handler_types
        assert "StreamHandler" not in handler_types

    def test_configure_logging_structured_format(self, tmp_path):
        """Test structured JSON format configuration."""
        configure_logging(
            structured=True,
            log_dir=str(tmp_path),
            log_file="structured.log"
        )

        logger = logging.getLogger()
        logger.info("Test structured message")

        # Check file contains JSON-like format
        log_file = tmp_path / "structured.log"
        content = log_file.read_text()
        assert '"level":' in content
        assert '"message":' in content


@pytest.mark.unit
class TestGetLogger:
    """Test suite for get_logger function."""

    def test_get_logger(self):
        """Test getting a named logger."""
        logger = get_logger("test.module")

        assert logger is not None
        assert logger.name == "test.module"

    def test_get_logger_with_level(self):
        """Test getting logger with specific level."""
        logger = get_logger("test.level", level="DEBUG")

        assert logger.level == logging.DEBUG

    def test_get_logger_same_instance(self):
        """Test that same name returns same logger."""
        logger1 = get_logger("test.same")
        logger2 = get_logger("test.same")

        assert logger1 is logger2


@pytest.mark.unit
class TestGetModuleLogger:
    """Test suite for get_module_logger function."""

    def test_get_module_logger(self):
        """Test getting module logger with prefix."""
        logger = get_module_logger("TestModule")

        assert logger.name == "atomx.TestModule"

    def test_get_module_logger_different_modules(self):
        """Test different modules get different loggers."""
        logger1 = get_module_logger("Module1")
        logger2 = get_module_logger("Module2")

        assert logger1.name != logger2.name
        assert logger1 is not logger2


@pytest.mark.unit
class TestAtomXFormatter:
    """Test suite for AtomXFormatter class."""

    def test_formatter_init(self):
        """Test formatter initialization."""
        formatter = AtomXFormatter()

        assert formatter is not None

    def test_formatter_format_record(self):
        """Test formatting a log record."""
        formatter = AtomXFormatter(use_colors=False)

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )

        formatted = formatter.format(record)
        assert "Test message" in formatted
        assert "INFO" in formatted

    def test_formatter_no_colors_when_disabled(self):
        """Test that colors are not added when disabled."""
        formatter = AtomXFormatter(use_colors=False)

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=10,
            msg="Error message",
            args=(),
            exc_info=None
        )

        formatted = formatter.format(record)
        # Should not contain ANSI codes
        assert "\033[" not in formatted


@pytest.mark.unit
class TestLoggerMixin:
    """Test suite for LoggerMixin class."""

    def test_mixin_provides_logger(self):
        """Test that mixin provides logger property."""
        class TestClass(LoggerMixin):
            pass

        obj = TestClass()
        logger = obj.logger

        assert logger is not None
        assert "TestClass" in logger.name

    def test_mixin_log_methods(self):
        """Test mixin log methods."""
        class TestClass(LoggerMixin):
            pass

        obj = TestClass()

        # Access logger first to create _logger attribute
        _ = obj.logger

        # Mock the logger
        mock_logger = Mock()
        obj._logger = mock_logger

        obj.log_debug("Debug message")
        obj.log_info("Info message")
        obj.log_warning("Warning message")
        obj.log_error("Error message")
        obj.log_critical("Critical message")

        mock_logger.debug.assert_called()
        mock_logger.info.assert_called()
        mock_logger.warning.assert_called()
        mock_logger.error.assert_called()
        mock_logger.critical.assert_called()

    def test_mixin_log_with_kwargs(self):
        """Test logging with additional context."""
        class TestClass(LoggerMixin):
            pass

        obj = TestClass()

        # Access logger first to create _logger attribute
        _ = obj.logger

        mock_logger = Mock()
        obj._logger = mock_logger

        obj.log_info("Message", key1="value1", key2="value2")

        call_args = mock_logger.info.call_args[0][0]
        assert "key1" in call_args
        assert "value1" in call_args

    def test_mixin_same_logger_instance(self):
        """Test that same logger is returned each time."""
        class TestClass(LoggerMixin):
            pass

        obj = TestClass()
        logger1 = obj.logger
        logger2 = obj.logger

        assert logger1 is logger2


@pytest.mark.unit
class TestContextLogger:
    """Test suite for ContextLogger class."""

    def test_context_logger_init(self):
        """Test context logger initialization."""
        logger = ContextLogger("test.context")

        assert logger is not None
        assert logger._context == {}

    def test_context_logger_init_with_context(self):
        """Test initialization with context."""
        logger = ContextLogger("test.context", context={"user": "test"})

        assert logger._context == {"user": "test"}

    def test_add_context(self):
        """Test adding context values."""
        logger = ContextLogger("test.context")
        logger.add_context(request_id="123", user="admin")

        assert logger._context["request_id"] == "123"
        assert logger._context["user"] == "admin"

    def test_remove_context(self):
        """Test removing context values."""
        logger = ContextLogger("test.context", context={"a": 1, "b": 2})
        logger.remove_context("a")

        assert "a" not in logger._context
        assert logger._context["b"] == 2

    def test_clear_context(self):
        """Test clearing all context."""
        logger = ContextLogger("test.context", context={"a": 1, "b": 2})
        logger.clear_context()

        assert logger._context == {}

    def test_format_message_with_context(self):
        """Test message formatting with context."""
        logger = ContextLogger("test.context", context={"id": "123"})

        formatted = logger._format_message("Test message")
        assert "Test message" in formatted
        assert "id=123" in formatted

    def test_format_message_without_context(self):
        """Test message formatting without context."""
        logger = ContextLogger("test.context")

        formatted = logger._format_message("Test message")
        assert formatted == "Test message"

    def test_context_logger_log_methods(self):
        """Test context logger log methods."""
        logger = ContextLogger("test.context")

        with patch.object(logger, '_logger', Mock()) as mock_logger:
            logger.debug("Debug")
            logger.info("Info")
            logger.warning("Warning")
            logger.error("Error")
            logger.critical("Critical")

            assert mock_logger.debug.called
            assert mock_logger.info.called
            assert mock_logger.warning.called
            assert mock_logger.error.called
            assert mock_logger.critical.called


@pytest.mark.unit
class TestLogFunctionCall:
    """Test suite for log_function_call decorator."""

    def test_decorator_logs_entry_exit(self):
        """Test that decorator logs function entry and exit."""
        mock_logger = Mock()

        @log_function_call(mock_logger)
        def test_func():
            return "result"

        result = test_func()

        assert result == "result"
        # Should have logged entry and exit
        assert mock_logger.debug.call_count >= 2

    def test_decorator_logs_exception(self):
        """Test that decorator logs exceptions."""
        mock_logger = Mock()

        @log_function_call(mock_logger)
        def failing_func():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            failing_func()

        # Should have logged the error
        assert mock_logger.error.called

    def test_decorator_preserves_function_name(self):
        """Test that decorator preserves function metadata."""
        @log_function_call()
        def my_function():
            """My docstring."""
            pass

        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "My docstring."


@pytest.mark.unit
class TestLogExecutionTime:
    """Test suite for log_execution_time decorator."""

    def test_decorator_logs_time(self):
        """Test that decorator logs execution time."""
        mock_logger = Mock()

        @log_execution_time(mock_logger)
        def test_func():
            return "result"

        result = test_func()

        assert result == "result"
        # Should have logged completion with time
        assert mock_logger.debug.called
        call_args = str(mock_logger.debug.call_args)
        assert "completed" in call_args.lower() or "s" in call_args

    def test_decorator_logs_time_on_failure(self):
        """Test that decorator logs time even on failure."""
        mock_logger = Mock()

        @log_execution_time(mock_logger)
        def failing_func():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            failing_func()

        # Should have logged the error with time
        assert mock_logger.error.called


@pytest.mark.unit
class TestLogLevels:
    """Test suite for log level constants."""

    def test_log_levels_defined(self):
        """Test that all standard log levels are defined."""
        assert "DEBUG" in LOG_LEVELS
        assert "INFO" in LOG_LEVELS
        assert "WARNING" in LOG_LEVELS
        assert "ERROR" in LOG_LEVELS
        assert "CRITICAL" in LOG_LEVELS

    def test_log_levels_values(self):
        """Test log level values are correct."""
        assert LOG_LEVELS["DEBUG"] == logging.DEBUG
        assert LOG_LEVELS["INFO"] == logging.INFO
        assert LOG_LEVELS["WARNING"] == logging.WARNING
        assert LOG_LEVELS["ERROR"] == logging.ERROR
        assert LOG_LEVELS["CRITICAL"] == logging.CRITICAL


@pytest.mark.unit
class TestEnsureLoggingConfigured:
    """Test suite for ensure_logging_configured function."""

    def teardown_method(self):
        """Reset configuration flag after each test."""
        import core.logging_utils
        core.logging_utils._default_configured = False

        # Clean up handlers
        root = logging.getLogger()
        for handler in root.handlers[:]:
            root.removeHandler(handler)
            handler.close()

    def test_configures_on_first_call(self):
        """Test that logging is configured on first call."""
        import core.logging_utils
        core.logging_utils._default_configured = False

        ensure_logging_configured()

        assert core.logging_utils._default_configured is True

    def test_does_not_reconfigure(self):
        """Test that logging is not reconfigured on subsequent calls."""
        import core.logging_utils
        core.logging_utils._default_configured = False

        ensure_logging_configured()
        first_handlers = logging.getLogger().handlers[:]

        ensure_logging_configured()
        second_handlers = logging.getLogger().handlers

        # Should have same handlers
        assert len(first_handlers) == len(second_handlers)
