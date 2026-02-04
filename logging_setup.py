"""Application logging setup using core.logging_utils."""

import json
import logging
import logging.handlers
import os
from typing import Tuple

from core.logging_utils import (
    AtomXFormatter,
    configure_logging,
    DEFAULT_LOG_FORMAT,
    DEFAULT_DATE_FORMAT,
)


DEFAULT_LOG_DIR = "logs"
DEFAULT_LOG_FILE = "app.log"


class JsonFormatter(logging.Formatter):
    """JSON formatter for structured file logging."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
            "time": self.formatTime(record, self.datefmt),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def setup_logging(
    log_dir: str = DEFAULT_LOG_DIR,
    filename: str = DEFAULT_LOG_FILE,
    level: str = "INFO",
    max_bytes: int = 10_000_000,  # 10 MB
    backup_count: int = 5,
    use_colors: bool = True,
) -> Tuple[logging.Logger, str]:
    """Configure root logger with rotating file and console handlers.

    Args:
        log_dir: Directory for log files
        filename: Log file name
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        max_bytes: Maximum log file size before rotation
        backup_count: Number of backup files to keep
        use_colors: Enable colored console output

    Returns:
        Tuple of (logger, log_path)
    """
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, filename)

    logger = logging.getLogger()
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.handlers.clear()

    # File handler with JSON formatting for structured logs
    file_handler = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
    )
    file_handler.setFormatter(JsonFormatter())

    # Console handler with AtomXFormatter for colored output
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(AtomXFormatter(use_colors=use_colors))

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logger.info(f"Logging initialized (level={level}, file={log_path})")

    return logger, log_path
