"""Structured logging with safe, configurable verbosity."""

import logging
import sys


def configure_logging(level: str = "INFO") -> logging.Logger:
    """Configure the root logger with a structured-ish formatter.

    Args:
        level: One of DEBUG, INFO, WARNING, ERROR.

    Returns:
        The root logger.
    """
    logger = logging.getLogger("shorts_pipeline")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(logger.level)
        fmt = logging.Formatter(
            fmt="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
            datefmt="%H:%M:%S",
        )
        handler.setFormatter(fmt)
        logger.addHandler(handler)

    # Silence noisy third-party loggers unless DEBUG.
    if logger.level > logging.DEBUG:
        for name in ("httpx", "urllib3", "aiohttp", "googleapiclient", "google.auth"):
            logging.getLogger(name).setLevel(logging.WARNING)

    return logger
