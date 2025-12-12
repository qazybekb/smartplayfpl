"""
Structured logging configuration for SmartPlayFPL.

Provides consistent, machine-parseable JSON logs with context enrichment.
Supports correlation IDs for request tracing across services.
"""

import logging
import sys
import json
import os
from datetime import datetime
from typing import Any, Optional
from contextvars import ContextVar
from functools import wraps
import time

# Context variable for request ID (thread-safe)
request_id_ctx: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
user_id_ctx: ContextVar[Optional[int]] = ContextVar("user_id", default=None)


# =============================================================================
# JSON FORMATTER
# =============================================================================

class JSONLogFormatter(logging.Formatter):
    """
    Formats log records as JSON for structured logging.

    Output format:
    {
        "timestamp": "2024-01-15T10:30:00.000Z",
        "level": "INFO",
        "logger": "smartplayfpl.fpl_service",
        "message": "Fetched 600 players",
        "request_id": "abc123",
        "extra": {"player_count": 600}
    }
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add context from ContextVars
        request_id = request_id_ctx.get()
        if request_id:
            log_data["request_id"] = request_id

        user_id = user_id_ctx.get()
        if user_id:
            log_data["user_id"] = user_id

        # Add source location for errors
        if record.levelno >= logging.ERROR:
            log_data["location"] = {
                "file": record.pathname,
                "line": record.lineno,
                "function": record.funcName,
            }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add any extra fields passed via extra={}
        if hasattr(record, "extra_data") and record.extra_data:
            log_data["extra"] = record.extra_data

        return json.dumps(log_data, default=str)


class HumanReadableFormatter(logging.Formatter):
    """
    Human-readable log formatter for development.

    Output format:
    2024-01-15 10:30:00 | INFO     | smartplayfpl.fpl | Fetched 600 players [req:abc123]
    """

    LEVEL_COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def __init__(self, use_colors: bool = True):
        super().__init__()
        self.use_colors = use_colors and sys.stderr.isatty()

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        level = record.levelname

        if self.use_colors:
            color = self.LEVEL_COLORS.get(level, "")
            level = f"{color}{level:8}{self.RESET}"
        else:
            level = f"{level:8}"

        # Truncate logger name for readability
        logger_name = record.name
        if len(logger_name) > 25:
            parts = logger_name.split(".")
            logger_name = ".".join([p[:3] for p in parts[:-1]] + [parts[-1]])

        message = record.getMessage()

        # Add request ID suffix if available
        request_id = request_id_ctx.get()
        suffix = f" [req:{request_id}]" if request_id else ""

        base = f"{timestamp} | {level} | {logger_name:25} | {message}{suffix}"

        # Add exception if present
        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)

        return base


# =============================================================================
# LOGGING SETUP
# =============================================================================

def setup_logging(
    level: str = "INFO",
    json_format: bool = False,
    log_file: Optional[str] = None,
) -> None:
    """
    Configure logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_format: Use JSON format (for production) vs human-readable (for dev)
        log_file: Optional file path for log output
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create formatter
    if json_format:
        formatter = JSONLogFormatter()
    else:
        formatter = HumanReadableFormatter()

    # Console handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(JSONLogFormatter())  # Always JSON for files
        root_logger.addHandler(file_handler)

    # Reduce noise from third-party loggers
    for noisy_logger in ["httpx", "httpcore", "urllib3", "asyncio"]:
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)


# =============================================================================
# CONTEXT-AWARE LOGGER
# =============================================================================

class StructuredLogger:
    """
    Logger wrapper that adds structured context to all log calls.

    Usage:
        logger = StructuredLogger("smartplayfpl.service")
        logger.info("Processing request", player_count=100, team_id=123)
    """

    def __init__(self, name: str):
        self._logger = logging.getLogger(name)

    def _log(self, level: int, message: str, **kwargs) -> None:
        """Internal log method with extra data handling."""
        extra = {"extra_data": kwargs} if kwargs else {}
        self._logger.log(level, message, extra=extra)

    def debug(self, message: str, **kwargs) -> None:
        self._log(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs) -> None:
        self._log(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs) -> None:
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, exc_info: bool = False, **kwargs) -> None:
        self._logger.error(message, exc_info=exc_info, extra={"extra_data": kwargs})

    def critical(self, message: str, exc_info: bool = False, **kwargs) -> None:
        self._logger.critical(message, exc_info=exc_info, extra={"extra_data": kwargs})

    def exception(self, message: str, **kwargs) -> None:
        """Log an exception with traceback."""
        self._logger.exception(message, extra={"extra_data": kwargs})


def get_logger(name: str) -> StructuredLogger:
    """Get a structured logger instance."""
    return StructuredLogger(name)


# =============================================================================
# TIMING DECORATOR
# =============================================================================

def log_timing(logger: Optional[StructuredLogger] = None, level: str = "DEBUG"):
    """
    Decorator to log function execution time.

    Usage:
        @log_timing()
        async def slow_operation():
            ...
    """
    def decorator(func):
        nonlocal logger
        if logger is None:
            logger = get_logger(func.__module__)

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = await func(*args, **kwargs)
                elapsed = time.time() - start
                getattr(logger, level.lower())(
                    f"{func.__name__} completed",
                    duration_ms=round(elapsed * 1000, 2)
                )
                return result
            except Exception as e:
                elapsed = time.time() - start
                logger.error(
                    f"{func.__name__} failed",
                    duration_ms=round(elapsed * 1000, 2),
                    error=str(e)
                )
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = func(*args, **kwargs)
                elapsed = time.time() - start
                getattr(logger, level.lower())(
                    f"{func.__name__} completed",
                    duration_ms=round(elapsed * 1000, 2)
                )
                return result
            except Exception as e:
                elapsed = time.time() - start
                logger.error(
                    f"{func.__name__} failed",
                    duration_ms=round(elapsed * 1000, 2),
                    error=str(e)
                )
                raise

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# =============================================================================
# REQUEST CONTEXT MIDDLEWARE
# =============================================================================

def set_request_context(request_id: str, user_id: Optional[int] = None) -> None:
    """Set request context for logging."""
    request_id_ctx.set(request_id)
    if user_id:
        user_id_ctx.set(user_id)


def clear_request_context() -> None:
    """Clear request context after request completes."""
    request_id_ctx.set(None)
    user_id_ctx.set(None)


# =============================================================================
# AUTO-CONFIGURE ON IMPORT
# =============================================================================

# Auto-configure based on environment
_json_format = os.getenv("LOG_FORMAT", "").lower() == "json"
_log_level = os.getenv("LOG_LEVEL", "INFO")
setup_logging(level=_log_level, json_format=_json_format)
