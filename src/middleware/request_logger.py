"""Request/response logging middleware for Flask."""

import time
import uuid
from typing import Any

from flask import Flask, g, request
from flask_login import current_user

from logging_config import get_logger


class RequestLoggerMiddleware:
    """
    Middleware that logs request/response details.

    Logs:
    - Request method, path, query params
    - Response status code
    - Request duration (ms)
    - User ID (if authenticated)
    - Unique request ID for tracing
    """

    # Paths to skip logging (health checks, static files)
    SKIP_PATHS = frozenset([
        "/health",
        "/favicon.ico",
        "/static/",
    ])

    # Sensitive paths that should log less detail
    SENSITIVE_PATHS = frozenset([
        "/auth/login",
    ])

    def __init__(self, app: Flask | None = None, logger_name: str = "orb_tool"):
        self.logger = get_logger(logger_name)
        if app is not None:
            self.init_app(app)

    def init_app(self, app: Flask):
        """Initialize middleware with Flask app."""
        app.before_request(self._before_request)
        app.after_request(self._after_request)
        app.teardown_request(self._teardown_request)

    def _should_skip(self, path: str) -> bool:
        """Check if path should be skipped from logging."""
        if path in self.SKIP_PATHS:
            return True
        return any(path.startswith(skip) for skip in self.SKIP_PATHS if skip.endswith("/"))

    def _is_sensitive(self, path: str) -> bool:
        """Check if path contains sensitive data."""
        return any(path.startswith(sens) for sens in self.SENSITIVE_PATHS)

    def _before_request(self):
        """Called before each request."""
        # Generate unique request ID
        g.request_id = str(uuid.uuid4())[:8]
        g.request_start_time = time.perf_counter()

        # Skip logging for certain paths
        if self._should_skip(request.path):
            g.skip_logging = True
            return

        g.skip_logging = False

    def _after_request(self, response):
        """Called after each request (before response sent)."""
        if getattr(g, "skip_logging", True):
            return response

        # Calculate duration
        duration_ms = 0
        if hasattr(g, "request_start_time"):
            duration_ms = round((time.perf_counter() - g.request_start_time) * 1000, 2)

        # Get user info
        user_id = None
        if current_user and hasattr(current_user, "is_authenticated") and current_user.is_authenticated:
            user_id = current_user.id

        # Build log data
        log_data: dict[str, Any] = {
            "request_id": getattr(g, "request_id", "unknown"),
            "method": request.method,
            "path": request.path,
            "status": response.status_code,
            "duration_ms": duration_ms,
            "user_id": user_id,
            "ip": request.remote_addr,
            "user_agent": request.user_agent.string[:100] if request.user_agent.string else None,
        }

        # Add query params (but not for sensitive paths)
        if request.args and not self._is_sensitive(request.path):
            # Redact potentially sensitive query params
            safe_args = {
                k: v for k, v in request.args.items()
                if k.lower() not in ("password", "token", "secret", "key", "auth")
            }
            if safe_args:
                log_data["query"] = safe_args

        # Determine log level based on status code
        if response.status_code >= 500:
            self.logger.error("Request failed", extra={"extra": log_data})
        elif response.status_code >= 400:
            self.logger.warning("Request error", extra={"extra": log_data})
        elif duration_ms > 1000:  # Slow request (>1s)
            self.logger.warning("Slow request", extra={"extra": log_data})
        else:
            self.logger.info("Request completed", extra={"extra": log_data})

        # Add request ID to response headers for debugging
        response.headers["X-Request-ID"] = getattr(g, "request_id", "unknown")

        return response

    def _teardown_request(self, exception):
        """Called after request is complete, even if exception occurred."""
        if exception and not getattr(g, "skip_logging", True):
            self.logger.exception(
                "Request exception",
                extra={
                    "extra": {
                        "request_id": getattr(g, "request_id", "unknown"),
                        "method": request.method,
                        "path": request.path,
                        "error": str(exception),
                    }
                }
            )


def init_request_logging(app: Flask, logger_name: str = "orb_tool"):
    """
    Initialize request logging middleware for a Flask app.

    Usage:
        from middleware import init_request_logging
        app = Flask(__name__)
        init_request_logging(app)
    """
    middleware = RequestLoggerMiddleware(app, logger_name)
    return middleware
