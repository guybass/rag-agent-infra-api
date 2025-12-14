"""
Logging configuration for RAG Agent Infrastructure API.
Provides structured logging with request tracking and error capture.
"""
import logging
import sys
import json
from datetime import datetime
from typing import Optional
from uuid import uuid4


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add extra fields if present
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        if hasattr(record, "client_ip"):
            log_data["client_ip"] = record.client_ip
        if hasattr(record, "method"):
            log_data["method"] = record.method
        if hasattr(record, "path"):
            log_data["path"] = record.path
        if hasattr(record, "status_code"):
            log_data["status_code"] = record.status_code
        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id
        if hasattr(record, "error_type"):
            log_data["error_type"] = record.error_type
        if hasattr(record, "error_detail"):
            log_data["error_detail"] = record.error_detail

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


class RequestContextFilter(logging.Filter):
    """Filter that adds request context to log records."""

    def __init__(self):
        super().__init__()
        self.request_id: Optional[str] = None
        self.client_ip: Optional[str] = None
        self.user_id: Optional[str] = None

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = self.request_id or "no-request"
        record.client_ip = self.client_ip or "unknown"
        record.user_id = self.user_id or "anonymous"
        return True


def setup_logging(
    level: str = "INFO",
    json_format: bool = True,
) -> logging.Logger:
    """
    Configure application logging.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        json_format: Use JSON format (True for production, False for dev)

    Returns:
        Configured logger
    """
    logger = logging.getLogger("rag_agent")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Clear existing handlers
    logger.handlers.clear()

    # Console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)

    if json_format:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        ))

    logger.addHandler(handler)

    # Prevent propagation to root logger
    logger.propagate = False

    return logger


def get_logger(name: str = "rag_agent") -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)


# Create default logger
logger = setup_logging()
