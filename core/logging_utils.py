"""Logging utilities for standardized logging across AtomX modules."""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime


# Standard log format for consistency
DEFAULT_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Console format (shorter for readability)
CONSOLE_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(message)s"
CONSOLE_DATE_FORMAT = "%H:%M:%S"

# Structured log format for machine parsing
STRUCTURED_LOG_FORMAT = (
    '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
    '"logger": "%(name)s", "message": "%(message)s"}'
)

# Log level mapping for convenience
LOG_LEVELS: Dict[str, int] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


class AtomXFormatter(logging.Formatter):
    """Custom formatter with color support for console output."""

    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[35m",  # Magenta
        "RESET": "\033[0m",      # Reset
    }

    def __init__(
        self,
        fmt: Optional[str] = None,
        datefmt: Optional[str] = None,
        use_colors: bool = True
    ) -> None:
        """Initialize formatter.

        Args:
            fmt: Log format string
            datefmt: Date format string
            use_colors: Enable ANSI color codes
        """
        super().__init__(fmt or CONSOLE_LOG_FORMAT, datefmt or CONSOLE_DATE_FORMAT)
        self.use_colors = use_colors and sys.stdout.isatty()

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record with optional colors.

        Args:
            record: Log record to format

        Returns:
            Formatted log string
        """
        if self.use_colors:
            color = self.COLORS.get(record.levelname, "")
            reset = self.COLORS["RESET"]
            record.levelname = f"{color}{record.levelname}{reset}"

        return super().format(record)


def configure_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    log_dir: str = "logs",
    max_file_size: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5,
    console_output: bool = True,
    use_colors: bool = True,
    structured: bool = False
) -> logging.Logger:
    """Configure application-wide logging.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Log file name (default: app.log)
        log_dir: Directory for log files
        max_file_size: Maximum size of log file before rotation
        backup_count: Number of backup files to keep
        console_output: Enable console output
        use_colors: Enable colored console output
        structured: Use structured JSON format for file logging

    Returns:
        Root logger instance
    """
    # Get numeric log level
    log_level = LOG_LEVELS.get(level.upper(), logging.INFO)

    # Create log directory if needed
    if log_file:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        log_file_path = log_path / (log_file or "app.log")
    else:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        log_file_path = log_path / "app.log"

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add file handler with rotation
    file_format = STRUCTURED_LOG_FORMAT if structured else DEFAULT_LOG_FORMAT
    file_handler = RotatingFileHandler(
        log_file_path,
        maxBytes=max_file_size,
        backupCount=backup_count,
        encoding="utf-8"
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(logging.Formatter(file_format, DEFAULT_DATE_FORMAT))
    root_logger.addHandler(file_handler)

    # Add console handler if enabled
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(AtomXFormatter(use_colors=use_colors))
        root_logger.addHandler(console_handler)

    return root_logger


def get_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """Get a named logger.

    Args:
        name: Logger name (typically __name__)
        level: Optional log level override

    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)

    if level:
        log_level = LOG_LEVELS.get(level.upper(), logging.INFO)
        logger.setLevel(log_level)

    return logger


def get_module_logger(module_name: str) -> logging.Logger:
    """Get a logger for a specific module with standardized naming.

    Args:
        module_name: Module name (e.g., "InstrumentManager", "Sequencer")

    Returns:
        Logger instance with module prefix
    """
    return get_logger(f"atomx.{module_name}")


class LoggerMixin:
    """Mixin class to add logging capabilities to any class."""

    @property
    def logger(self) -> logging.Logger:
        """Get logger for this class.

        Returns:
            Logger instance named after the class
        """
        if not hasattr(self, "_logger"):
            self._logger = get_module_logger(self.__class__.__name__)
        return self._logger

    def log_debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message.

        Args:
            message: Log message
            **kwargs: Additional context to include
        """
        if kwargs:
            message = f"{message} | {kwargs}"
        self.logger.debug(message)

    def log_info(self, message: str, **kwargs: Any) -> None:
        """Log info message.

        Args:
            message: Log message
            **kwargs: Additional context to include
        """
        if kwargs:
            message = f"{message} | {kwargs}"
        self.logger.info(message)

    def log_warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message.

        Args:
            message: Log message
            **kwargs: Additional context to include
        """
        if kwargs:
            message = f"{message} | {kwargs}"
        self.logger.warning(message)

    def log_error(self, message: str, exc_info: bool = False, **kwargs: Any) -> None:
        """Log error message.

        Args:
            message: Log message
            exc_info: Include exception traceback
            **kwargs: Additional context to include
        """
        if kwargs:
            message = f"{message} | {kwargs}"
        self.logger.error(message, exc_info=exc_info)

    def log_critical(self, message: str, exc_info: bool = True, **kwargs: Any) -> None:
        """Log critical message.

        Args:
            message: Log message
            exc_info: Include exception traceback
            **kwargs: Additional context to include
        """
        if kwargs:
            message = f"{message} | {kwargs}"
        self.logger.critical(message, exc_info=exc_info)


class ContextLogger:
    """Logger with persistent context for related log entries."""

    def __init__(
        self,
        name: str,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Initialize context logger.

        Args:
            name: Logger name
            context: Initial context dictionary
        """
        self._logger = get_logger(name)
        self._context: Dict[str, Any] = context or {}

    def add_context(self, **kwargs: Any) -> None:
        """Add context values.

        Args:
            **kwargs: Context key-value pairs
        """
        self._context.update(kwargs)

    def remove_context(self, *keys: str) -> None:
        """Remove context values.

        Args:
            *keys: Context keys to remove
        """
        for key in keys:
            self._context.pop(key, None)

    def clear_context(self) -> None:
        """Clear all context values."""
        self._context.clear()

    def _format_message(self, message: str) -> str:
        """Format message with context.

        Args:
            message: Log message

        Returns:
            Message with context appended
        """
        if self._context:
            context_str = " | ".join(f"{k}={v}" for k, v in self._context.items())
            return f"{message} [{context_str}]"
        return message

    def debug(self, message: str) -> None:
        """Log debug message with context."""
        self._logger.debug(self._format_message(message))

    def info(self, message: str) -> None:
        """Log info message with context."""
        self._logger.info(self._format_message(message))

    def warning(self, message: str) -> None:
        """Log warning message with context."""
        self._logger.warning(self._format_message(message))

    def error(self, message: str, exc_info: bool = False) -> None:
        """Log error message with context."""
        self._logger.error(self._format_message(message), exc_info=exc_info)

    def critical(self, message: str, exc_info: bool = True) -> None:
        """Log critical message with context."""
        self._logger.critical(self._format_message(message), exc_info=exc_info)


def log_function_call(logger: Optional[logging.Logger] = None):
    """Decorator to log function entry and exit.

    Args:
        logger: Optional logger to use (default: function's module logger)

    Returns:
        Decorator function
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            log = logger or get_logger(func.__module__)
            func_name = func.__qualname__

            log.debug(f"Entering {func_name}")
            try:
                result = func(*args, **kwargs)
                log.debug(f"Exiting {func_name}")
                return result
            except Exception as e:
                log.error(f"Exception in {func_name}: {e}", exc_info=True)
                raise

        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper

    return decorator


def log_execution_time(logger: Optional[logging.Logger] = None):
    """Decorator to log function execution time.

    Args:
        logger: Optional logger to use

    Returns:
        Decorator function
    """
    import time

    def decorator(func):
        def wrapper(*args, **kwargs):
            log = logger or get_logger(func.__module__)
            func_name = func.__qualname__

            start_time = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                elapsed = time.perf_counter() - start_time
                log.debug(f"{func_name} completed in {elapsed:.3f}s")
                return result
            except Exception as e:
                elapsed = time.perf_counter() - start_time
                log.error(f"{func_name} failed after {elapsed:.3f}s: {e}")
                raise

        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper

    return decorator


# Initialize default logging on import
_default_configured = False


def ensure_logging_configured() -> None:
    """Ensure logging is configured with defaults if not already done."""
    global _default_configured
    if not _default_configured:
        configure_logging()
        _default_configured = True
