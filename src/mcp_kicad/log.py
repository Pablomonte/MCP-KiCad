"""
Structured logging for MCP-KiCad with correlation IDs and operation tracking.

Provides JSON-formatted logs with correlation ID tracking across operations,
automatic operation context management, and configurable output destinations.
"""

import logging
import sys
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
import uuid

import structlog
from structlog.types import Processor

from mcp_kicad.config import get_settings

# Context variable for correlation ID
correlation_id: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)
operation_id: ContextVar[Optional[str]] = ContextVar("operation_id", default=None)


class CorrelationIdFilter(logging.Filter):
    """Add correlation ID and operation ID to standard logging records."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id.get() or "no-correlation-id"
        record.operation_id = operation_id.get() or "no-operation-id"
        return True


def add_correlation_id(
    logger: logging.Logger, method_name: str, event_dict: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Add correlation ID and operation ID to event dict.

    This processor adds tracking IDs to every log event for request correlation.
    """
    event_dict["correlation_id"] = correlation_id.get() or "no-correlation-id"
    event_dict["operation_id"] = operation_id.get() or "no-operation-id"
    return event_dict


def setup_logging(
    log_level: str = "INFO",
    log_dir: Optional[Path] = None,
    log_to_file: bool = True,
    log_to_console: bool = True,
    json_format: bool = False,
) -> None:
    """
    Configure structured logging with JSON output and correlation tracking.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory for log files (None = use default from settings)
        log_to_file: Enable file logging
        log_to_console: Enable console logging
        json_format: Use JSON format (True) or human-readable (False)
    """
    settings = get_settings()

    if log_dir is None:
        log_dir = settings.log_dir

    # Ensure log directory exists
    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)

    # Convert log level string to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Configure shared processors for structlog
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        add_correlation_id,
    ]

    # Choose renderer based on format preference
    if json_format:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(
            colors=log_to_console and sys.stderr.isatty()
        )

    # Configure structlog
    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    # Setup handlers
    handlers: list[logging.Handler] = []

    if log_to_console:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setFormatter(formatter)
        console_handler.addFilter(CorrelationIdFilter())
        handlers.append(console_handler)

    if log_to_file and log_dir:
        from logging.handlers import RotatingFileHandler

        log_file = log_dir / "mcp-kicad.log"
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=settings.log_rotation_mb * 1024 * 1024,  # MB to bytes
            backupCount=settings.log_retention_days,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.addFilter(CorrelationIdFilter())
        handlers.append(file_handler)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    root_logger.handlers.clear()
    for handler in handlers:
        root_logger.addHandler(handler)

    # Silence noisy libraries
    logging.getLogger("anthropic").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str = "mcp_kicad") -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)


class LoggerContext:
    """Context manager for automatic logging setup."""

    def __init__(
        self,
        log_level: Optional[str] = None,
        json_format: bool = False,
    ):
        """
        Initialize logger context.

        Args:
            log_level: Override log level
            json_format: Use JSON format
        """
        settings = get_settings()
        self.log_level = log_level or settings.log_level
        self.json_format = json_format or settings.log_json

    def __enter__(self) -> structlog.stdlib.BoundLogger:
        """Setup logging and return logger."""
        settings = get_settings()
        setup_logging(
            log_level=self.log_level,
            log_dir=settings.log_dir,
            log_to_file=settings.log_to_file,
            log_to_console=settings.log_to_console,
            json_format=self.json_format,
        )
        return get_logger()

    def __exit__(self, *args: Any) -> None:
        """Cleanup (no-op for logging)."""
        pass


class OperationContext:
    """
    Context manager for operation logging with automatic timing and error capture.

    Automatically logs operation start, completion, duration, and errors.
    Sets operation ID for correlation across logs.
    """

    def __init__(
        self,
        logger: structlog.stdlib.BoundLogger,
        operation_name: str,
        **context_kwargs: Any,
    ):
        """
        Initialize operation context.

        Args:
            logger: Structlog logger instance
            operation_name: Name of the operation
            **context_kwargs: Additional context to log
        """
        self.logger = logger
        self.operation_name = operation_name
        self.context = context_kwargs
        self.start_time: Optional[datetime] = None
        self.op_id = str(uuid.uuid4())[:8]

    def __enter__(self) -> "OperationContext":
        """Start operation tracking."""
        operation_id.set(self.op_id)
        self.start_time = datetime.now()

        self.logger.info(
            "operation_started",
            operation=self.operation_name,
            operation_id=self.op_id,
            **self.context,
        )
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        """Complete operation tracking with duration and status."""
        duration_ms = 0.0
        if self.start_time:
            duration_ms = (datetime.now() - self.start_time).total_seconds() * 1000

        if exc_type is None:
            self.logger.info(
                "operation_completed",
                operation=self.operation_name,
                operation_id=self.op_id,
                duration_ms=duration_ms,
                status="success",
                **self.context,
            )
        else:
            self.logger.error(
                "operation_failed",
                operation=self.operation_name,
                operation_id=self.op_id,
                duration_ms=duration_ms,
                status="error",
                error_type=exc_type.__name__ if exc_type else None,
                error=str(exc_val) if exc_val else None,
                **self.context,
                exc_info=True,
            )

        # Clear operation ID
        operation_id.set(None)

        # Don't suppress exceptions
        return False

    def log_progress(self, message: str, **extra: Any) -> None:
        """Log progress message within operation context."""
        self.logger.info(
            message,
            operation=self.operation_name,
            operation_id=self.op_id,
            **extra,
        )


def set_correlation_id(corr_id: Optional[str] = None) -> str:
    """
    Set correlation ID for request tracking.

    Args:
        corr_id: Correlation ID (generates new UUID if None)

    Returns:
        The correlation ID that was set
    """
    if corr_id is None:
        corr_id = str(uuid.uuid4())
    correlation_id.set(corr_id)
    return corr_id


def get_correlation_id() -> Optional[str]:
    """
    Get current correlation ID.

    Returns:
        Current correlation ID or None
    """
    return correlation_id.get()


def clear_correlation_id() -> None:
    """Clear correlation ID from context."""
    correlation_id.set(None)
    operation_id.set(None)


# Convenience function to create operation context
def operation_context(
    operation_name: str,
    logger: Optional[structlog.stdlib.BoundLogger] = None,
    **kwargs: Any,
) -> OperationContext:
    """
    Create operation context for tracking.

    Args:
        operation_name: Name of the operation
        logger: Logger instance (creates new if None)
        **kwargs: Additional context

    Returns:
        OperationContext instance
    """
    if logger is None:
        logger = get_logger()
    return OperationContext(logger, operation_name, **kwargs)
