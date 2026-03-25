"""Structured logging setup for the Code Review Agent."""

import logging
import sys
from typing import Optional


def get_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """Create and return a configured logger instance.

    Args:
        name: Logger name, typically __name__ of the calling module.
        level: Optional log level override (DEBUG, INFO, WARNING, ERROR).

    Returns:
        Configured Logger instance.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.propagate = False

    log_level = level or "WARNING"
    logger.setLevel(getattr(logging, log_level.upper(), logging.WARNING))
    return logger


def set_global_log_level(level: str) -> None:
    """Set the log level for all code_review_agent loggers.

    Args:
        level: Log level string (DEBUG, INFO, WARNING, ERROR).
    """
    numeric = getattr(logging, level.upper(), logging.WARNING)
    for name, logger in logging.Logger.manager.loggerDict.items():
        if isinstance(logger, logging.Logger) and name.startswith("agent"):
            logger.setLevel(numeric)
