import logging
import os
import sys
from typing import Optional

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
SERVICE_NAME = os.getenv("SERVICE_NAME", "pokemon-api")


class ColoredFormatter(logging.Formatter):
    """Add colors to console output for better readability."""

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{log_color}{record.levelname}{self.RESET}"
        return super().format(record)


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Get a configured logger instance for a service or module.

    Args:
        name: Optional module name. If not provided, uses SERVICE_NAME env var.

    Returns:
        Configured logger instance.
    """
    logger_name = name or SERVICE_NAME
    logger = logging.getLogger(logger_name)

    if logger.handlers:
        return logger

    logger.setLevel(LOG_LEVEL)

    # Console handler with colored output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(LOG_LEVEL)

    # Format: [SERVICE] LEVEL: message
    formatter = ColoredFormatter(
        f"[{SERVICE_NAME}] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger
