import json
import logging
import logging.handlers
import os
from typing import Tuple


DEFAULT_LOG_DIR = "logs"
DEFAULT_LOG_FILE = "app.log"


class JsonFormatter(logging.Formatter):
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
    max_bytes: int = 1_000_000,
    backup_count: int = 3,
) -> Tuple[logging.Logger, str]:
    """Configure root logger with rotating file and console handlers."""
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, filename)

    logger = logging.getLogger()
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.handlers.clear()

    file_handler = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
    )
    file_handler.setFormatter(JsonFormatter())

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger, log_path
