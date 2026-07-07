"""Exception hierarchy for the Prophet SDK."""

from __future__ import annotations

from typing import Any


class ProphetError(Exception):
    """Base exception for all Prophet SDK errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ConfigurationError(ProphetError):
    """Invalid client configuration."""

    pass


class AuthenticationError(ProphetError):
    """Authentication or authorization failure."""

    def __init__(
        self,
        message: str,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details)
        self.code = code


class TokenExpiredError(AuthenticationError):
    """Token has expired and could not be refreshed."""

    pass


class APIError(ProphetError):
    """API request failure."""

    def __init__(
        self,
        message: str,
        status_code: int,
        error_type: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details)
        self.status_code = status_code
        self.error_type = error_type


class ValidationError(ProphetError):
    """Request validation failure."""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details)
        self.field = field


class PQLSyntaxError(ProphetError):
    """Invalid PQL query syntax."""

    def __init__(
        self,
        message: str,
        query: str | None = None,
        position: int | None = None,
    ) -> None:
        super().__init__(message)
        self.query = query
        self.position = position


class ConnectionError(ProphetError):
    """Network connection failure."""

    pass


class TimeoutError(ProphetError):
    """Request timeout."""

    pass


def parse_error(data: Any, fallback: str) -> tuple[str, str | None, dict[str, Any] | None]:
    """
    Extract ``(message, kind, details)`` from an error body of either shape.

    Prefers the nested envelope the search-api returns —
    ``{"error": {"code", "message", "type", "details"}, "timestamp": ...}`` —
    where ``kind`` is ``error.type`` (e.g. "authentication_error") and
    ``details`` is ``error.details``. Falls back to the flat
    ``{"error": "...", "code": "..."}`` shape other endpoints return, where
    ``kind`` is the top-level ``code``. ``fallback`` is used when no message
    can be found (including a non-dict / absent body).
    """
    if not isinstance(data, dict):
        return fallback, None, None

    err = data.get("error")
    if isinstance(err, dict):
        message = err.get("message") or data.get("message") or fallback
        details = err.get("details")
        return message, err.get("type"), details if isinstance(details, dict) else None

    message = (err if isinstance(err, str) else None) or data.get("message") or fallback
    return message, data.get("code"), None


def raise_for_response(response: Any) -> None:
    """
    Map a non-2xx HTTP response to the right Prophet exception, or return for 2xx.

    Single source of truth for the REST error contract so every API surface
    raises consistently. Understands both error envelopes (see parse_error) and
    tolerates a non-JSON error body (e.g. a bare 500 from a proxy) instead of
    crashing while trying to parse it.
    """
    if response.status_code in (200, 201):
        return

    try:
        data = response.json()
    except Exception:
        data = {}

    status = response.status_code
    message, kind, details = parse_error(data, f"Request failed with status {status}")

    if status == 401:
        raise AuthenticationError(message=message, code=kind, details=details)
    if status == 400:
        raise ValidationError(message=message, details=details)
    if status == 403:
        raise APIError(
            message=message,
            status_code=403,
            error_type=kind or "authorization_error",
            details=details,
        )
    if status == 404:
        raise APIError(message=message, status_code=404, error_type=kind or "not_found",
                       details=details)
    raise APIError(message=message, status_code=status, error_type=kind, details=details)
