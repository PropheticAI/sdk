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
