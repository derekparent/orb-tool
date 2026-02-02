"""Structured logging configuration for Oil Record Book Tool."""

import json
import logging
import logging.handlers
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

UTC = timezone.utc


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def __init__(self, include_traceback: bool = True):
        super().__init__()
        self.include_traceback = include_traceback

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add source location
        log_data["source"] = {
            "file": record.filename,
            "line": record.lineno,
            "function": record.funcName,
        }

        # Add request context if available
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id
        if hasattr(record, "method"):
            log_data["method"] = record.method
        if hasattr(record, "path"):
            log_data["path"] = record.path

        # Add extra fields
        if hasattr(record, "extra"):
            log_data["extra"] = record.extra

        # Add exception info if present
        if record.exc_info and self.include_traceback:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": traceback.format_exception(*record.exc_info),
            }

        return json.dumps(log_data, default=str)


class AuditLogger:
    """Dedicated audit logger for security-sensitive operations."""

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def _log(self, action: str, details: dict[str, Any], user_id: int | None = None):
        """Log an audit event."""
        extra = {
            "audit_action": action,
            "audit_details": details,
        }
        if user_id:
            extra["user_id"] = user_id

        self.logger.info(f"AUDIT: {action}", extra={"extra": extra})

    # Authentication events
    def login_success(self, user_id: int, username: str, ip_address: str | None = None):
        """Log successful login."""
        self._log("auth.login_success", {
            "username": username,
            "ip_address": ip_address,
        }, user_id=user_id)

    def login_failure(self, username: str, ip_address: str | None = None, reason: str = "invalid_credentials"):
        """Log failed login attempt."""
        self._log("auth.login_failure", {
            "username": username,
            "ip_address": ip_address,
            "reason": reason,
        })

    def logout(self, user_id: int, username: str):
        """Log user logout."""
        self._log("auth.logout", {"username": username}, user_id=user_id)

    def user_created(self, admin_user_id: int, new_user_id: int, username: str, role: str):
        """Log new user creation."""
        self._log("auth.user_created", {
            "new_user_id": new_user_id,
            "username": username,
            "role": role,
        }, user_id=admin_user_id)

    def user_status_changed(self, admin_user_id: int, target_user_id: int, is_active: bool):
        """Log user activation/deactivation."""
        self._log("auth.user_status_changed", {
            "target_user_id": target_user_id,
            "is_active": is_active,
        }, user_id=admin_user_id)

    # Hitch operations
    def hitch_started(self, user_id: int, hitch_id: int, data_cleared: bool):
        """Log new hitch start."""
        self._log("hitch.started", {
            "hitch_id": hitch_id,
            "data_cleared": data_cleared,
        }, user_id=user_id)

    def hitch_ended(self, user_id: int, hitch_id: int):
        """Log hitch end record creation."""
        self._log("hitch.ended", {"hitch_id": hitch_id}, user_id=user_id)

    def hitch_updated(self, user_id: int, hitch_id: int, fields: list[str]):
        """Log hitch record update."""
        self._log("hitch.updated", {
            "hitch_id": hitch_id,
            "fields_updated": fields,
        }, user_id=user_id)

    # Data operations
    def data_reset(self, user_id: int, tables_cleared: list[str]):
        """Log data reset operation."""
        self._log("data.reset", {
            "tables_cleared": tables_cleared,
        }, user_id=user_id)

    def sounding_created(self, user_id: int, sounding_id: int, tank_17p_m3: float, tank_17s_m3: float):
        """Log weekly sounding creation."""
        self._log("sounding.created", {
            "sounding_id": sounding_id,
            "tank_17p_m3": tank_17p_m3,
            "tank_17s_m3": tank_17s_m3,
        }, user_id=user_id)

    def fuel_ticket_created(self, user_id: int, ticket_id: int, consumption: float):
        """Log fuel ticket creation."""
        self._log("fuel.ticket_created", {
            "ticket_id": ticket_id,
            "consumption_gallons": consumption,
        }, user_id=user_id)

    # Equipment changes
    def equipment_status_changed(self, user_id: int, equipment_id: str, old_status: str | None, new_status: str):
        """Log equipment status change."""
        self._log("equipment.status_changed", {
            "equipment_id": equipment_id,
            "old_status": old_status,
            "new_status": new_status,
        }, user_id=user_id)


def setup_logging(
    app_name: str = "oil_record_book",
    log_level: str | None = None,
    log_dir: str | Path | None = None,
    json_format: bool = True,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
) -> tuple[logging.Logger, AuditLogger]:
    """
    Configure application logging.

    Args:
        app_name: Logger name prefix
        log_level: Log level (DEBUG, INFO, WARNING, ERROR). Defaults to env var or INFO.
        log_dir: Directory for log files. Defaults to 'logs/' in project root.
        json_format: Use JSON formatting (True for prod, can disable for dev readability)
        max_bytes: Max log file size before rotation (default 10MB)
        backup_count: Number of backup files to keep (default 5)

    Returns:
        Tuple of (main logger, audit logger)
    """
    # Determine log level from env or parameter
    if log_level is None:
        env = os.environ.get("FLASK_ENV", "development")
        log_level = os.environ.get(
            "LOG_LEVEL",
            "DEBUG" if env == "development" else "INFO"
        )

    level = getattr(logging, log_level.upper(), logging.INFO)

    # Setup log directory
    if log_dir is None:
        log_dir = Path(__file__).parent.parent / "logs"
    else:
        log_dir = Path(log_dir)

    log_dir.mkdir(parents=True, exist_ok=True)

    # Create formatters
    if json_format:
        formatter = JSONFormatter()
    else:
        # Human-readable format for development
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

    # --- Main Application Logger ---
    app_logger = logging.getLogger(app_name)
    app_logger.setLevel(level)
    app_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    app_logger.addHandler(console_handler)

    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / f"{app_name}.log",
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    app_logger.addHandler(file_handler)

    # --- Audit Logger (always INFO+, separate file) ---
    audit_logger = logging.getLogger(f"{app_name}.audit")
    audit_logger.setLevel(logging.INFO)
    audit_logger.handlers.clear()
    audit_logger.propagate = False  # Don't duplicate to main logger

    audit_file_handler = logging.handlers.RotatingFileHandler(
        log_dir / f"{app_name}_audit.log",
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    audit_file_handler.setLevel(logging.INFO)
    audit_file_handler.setFormatter(JSONFormatter())  # Always JSON for audit
    audit_logger.addHandler(audit_file_handler)

    # Also log audit to console in development
    if os.environ.get("FLASK_ENV") == "development":
        audit_console = logging.StreamHandler(sys.stdout)
        audit_console.setLevel(logging.INFO)
        audit_console.setFormatter(formatter)
        audit_logger.addHandler(audit_console)

    # --- Error Logger (ERROR+ only, separate file for quick scanning) ---
    error_logger = logging.getLogger(f"{app_name}.errors")
    error_logger.setLevel(logging.ERROR)
    error_logger.handlers.clear()

    error_file_handler = logging.handlers.RotatingFileHandler(
        log_dir / f"{app_name}_errors.log",
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.setFormatter(JSONFormatter())
    error_logger.addHandler(error_file_handler)

    # Ensure main logger errors also go to error log
    app_logger.addHandler(error_file_handler)

    app_logger.info(f"Logging initialized: level={log_level}, dir={log_dir}")

    return app_logger, AuditLogger(audit_logger)


def get_logger(name: str = "oil_record_book") -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)


def get_audit_logger() -> AuditLogger:
    """Get the audit logger instance."""
    return AuditLogger(logging.getLogger("oil_record_book.audit"))
